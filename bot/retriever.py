# bot/retriever.py
# =================
# Retrieves most relevant scripture chunks from pgvector.

import re
import psycopg2
import logging
from sentence_transformers import SentenceTransformer
from config.settings import Config

logger = logging.getLogger(__name__)

# Semantic threshold for pure similarity results.
# Theme-matched results use a lower threshold (THEME_THRESHOLD) since
# vocabulary mismatch between natural queries and Prabhupada's English is common.
SIMILARITY_THRESHOLD = 0.28
THEME_THRESHOLD      = 0.05

_model = None

# English ordinals used in Prabhupada chapter headings ("CHAPTER TWO" etc.)
_ORDINALS = {
    "ONE": "1", "TWO": "2", "THREE": "3", "FOUR": "4", "FIVE": "5",
    "SIX": "6", "SEVEN": "7", "EIGHT": "8", "NINE": "9", "TEN": "10",
    "ELEVEN": "11", "TWELVE": "12", "THIRTEEN": "13", "FOURTEEN": "14",
    "FIFTEEN": "15", "SIXTEEN": "16", "SEVENTEEN": "17", "EIGHTEEN": "18",
}
_CH_RE = re.compile(r'CHAPTER\s+([A-Z]+|\d+)', re.IGNORECASE)
_VS_RE = re.compile(r'TEXT\s+(\d+)', re.IGNORECASE)

# Expands natural language queries with Gita-specific vocabulary.
# Prabhupada's English uses classical/Sanskrit terms — this bridges the gap
# so the embedding model can match relevant chunks even when words differ.
_QUERY_EXPANSIONS = {
    "anger":        "anger krodha wrath passion fury rage hatred agitation",
    "death":        "death die soul eternal body transmigration reincarnation afterlife immortal",
    "fear":         "fear anxiety worry dread courage fearless bold",
    "love":         "love devotion bhakti prema surrender worship affection",
    "purpose":      "purpose dharma duty meaning life goal mission",
    "peace":        "peace liberation moksha stillness mind calm meditation tranquil",
    "karma":        "karma action fruit result work deed activity",
    "soul":         "soul atma eternal body spirit self consciousness",
    "god":          "god krishna supreme lord vishnu bhagavan divine",
    "mind":         "mind control senses meditation yoga concentrate thought",
    "grief":        "grief sorrow lamentation mourn weep cry loss pain",
    "detachment":   "detachment renunciation attachment letting go vairagya",
    "maya":         "maya illusion material world temporary false ignorance",
    "liberation":   "liberation moksha freedom mukti transcend eternal",
    "duty":         "duty dharma obligation responsibility action work",
    "surrender":    "surrender refuge sharanagati protect deliver submit",
    "chant":        "chant mantra hare krishna japa kirtan naam prayer",
    "yoga":         "yoga meditation practice discipline control path",
    "knowledge":    "knowledge wisdom jnana truth realize understand",
    "reincarnation":"reincarnation rebirth soul transmigration body death new life",
    "stress":       "stress anxiety worry mind peace control senses",
    "depression":   "depression sorrow grief hopeless lamentation despair",
    "desire":       "desire lust kama attachment craving passion want",
    "ego":          "ego false self pride ahankara identity body material",
    "family":       "family relations duty attachment love grief lamentation",
    "suffering":    "suffering pain misery duality happiness distress",
}


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(Config.EMBEDDING_MODEL)
    return _model


def _expand_query(text: str) -> str:
    """
    Adds Gita vocabulary synonyms to the query so the embedding model
    can match Prabhupada's classical English from colloquial questions.
    e.g. "how to control anger" → "how to control anger krodha wrath passion..."
    """
    text_lower = text.lower()
    additions  = []
    for keyword, expansion in _QUERY_EXPANSIONS.items():
        if keyword in text_lower:
            additions.append(expansion)
    return (text + " " + " ".join(additions)).strip() if additions else text


def _resolve_ref(chapter, verse, text: str):
    """
    Returns (chapter_str, verse_str) that are genuinely meaningful.

    Priority: stored metadata → text scan fallback.
    Rejects bad metadata (page numbers >18, articles like THE/OF/THIS).
    """
    ch = (chapter or "").strip()
    vs = (verse   or "").strip()

    # Validate stored chapter
    try:
        ch_num = int(ch)
        ch = str(ch_num) if 1 <= ch_num <= 18 else ""
    except (ValueError, TypeError):
        # Word — only keep if it is a known ordinal (ONE..EIGHTEEN)
        ch = _ORDINALS.get(ch.upper(), "")

    # Validate stored verse — discard "p.42" placeholders
    if vs.startswith("p.") or not vs:
        vs = ""

    # Fallback: scan the chunk text for headings Prabhupada books always contain
    if not ch:
        m = _CH_RE.search(text)
        if m:
            raw = m.group(1).upper()
            if raw in _ORDINALS:
                ch = _ORDINALS[raw]
            else:
                try:
                    n = int(raw)
                    ch = str(n) if 1 <= n <= 18 else ""
                except ValueError:
                    pass   # skip articles like "THE", "OF"

    if not vs:
        m = _VS_RE.search(text)
        if m:
            vs = m.group(1)

    return ch, vs


def retrieve_relevant_chunks(question: str, themes: list, top_k: int = None) -> list:
    """
    Finds the most relevant scripture passages for a question.
    Strategy:
      1. Theme-filtered similarity (lower threshold — Gita vocabulary differs from queries)
      2. Pure semantic similarity (higher threshold)
    """
    top_k    = top_k or Config.RETRIEVE_TOP_K
    model    = _get_model()
    expanded = _expand_query(question)
    embedding = model.encode(expanded, normalize_embeddings=True).tolist()

    conn = psycopg2.connect(Config.DATABASE_URL)
    cur  = conn.cursor()

    # Strategy 1: Theme-filtered search — include even low-similarity results
    # because theme tags are more reliable than embeddings for topical matching
    theme_results = []
    if themes:
        cur.execute("""
            SELECT source, chapter, verse, text, themes, emotions,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM scripture_chunks
            WHERE themes && %s::text[]
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """, (embedding, themes, embedding, top_k * 2))
        theme_results = cur.fetchall()

    # Strategy 2: Pure semantic similarity search
    cur.execute("""
        SELECT source, chapter, verse, text, themes, emotions,
               1 - (embedding <=> %s::vector) AS similarity
        FROM scripture_chunks
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
    """, (embedding, embedding, top_k * 3))
    semantic_results = cur.fetchall()

    cur.close()
    conn.close()

    seen  = set()
    final = []

    # Theme results first (lower threshold — already filtered by topic)
    for row in theme_results:
        key = row[3][:100]
        sim = float(row[6])
        if key not in seen and len(final) < top_k and sim > THEME_THRESHOLD:
            seen.add(key)
            ch, vs = _resolve_ref(row[1], row[2], row[3])
            final.append({
                "source":     row[0],
                "chapter":    ch,
                "verse":      vs,
                "text":       row[3],
                "themes":     row[4],
                "emotions":   row[5],
                "similarity": sim,
                "matched_by": "theme",
            })

    # Semantic results second (higher threshold)
    for row in semantic_results:
        key = row[3][:100]
        sim = float(row[6])
        if key not in seen and len(final) < top_k and sim > SIMILARITY_THRESHOLD:
            seen.add(key)
            ch, vs = _resolve_ref(row[1], row[2], row[3])
            final.append({
                "source":     row[0],
                "chapter":    ch,
                "verse":      vs,
                "text":       row[3],
                "themes":     row[4],
                "emotions":   row[5],
                "similarity": sim,
                "matched_by": "semantic",
            })

    if not final:
        logger.warning("⚠️  No relevant chunks found for: '%s'", question[:80])
    else:
        logger.info(
            "✅ %d chunks | top sim=%.3f | refs=%s",
            len(final),
            max(c["similarity"] for c in final),
            [(c["chapter"], c["verse"]) for c in final],
        )

    return final


def get_chunk_count() -> int:
    try:
        conn = psycopg2.connect(Config.DATABASE_URL)
        cur  = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM scripture_chunks;")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count
    except Exception as e:
        logger.error("DB error: %s", e)
        return -1


def extract_verse_content(text: str):
    """
    Parses a scripture chunk to extract:
      - iast  : IAST transliteration of the shlok (romanized Sanskrit)
      - translation: English translation of the verse

    Returns (iast, translation) — either can be None if not found in this chunk
    (purport-only chunks won't have verse text).
    """
    iast        = None
    translation = None

    # Only verse chunks have "TEXT\n N" marker
    text_marker = re.search(r'TEXT\s*\n?\s*\d+\s*\n', text, re.IGNORECASE)
    if not text_marker:
        return None, None

    # IAST sits between the garbled Sanskrit encoding and the SYNONYMS section.
    # Garbled lines are all-uppercase; IAST lines start lowercase.
    synonyms_pos = text.upper().find('SYNONYMS', text_marker.end())
    if synonyms_pos > 0:
        between = text[text_marker.end():synonyms_pos].strip()
        iast_lines = [
            ln.strip() for ln in between.split('\n')
            if ln.strip() and ln.strip()[0].islower()
        ]
        if iast_lines:
            iast = '\n'.join(iast_lines[:6])   # max 6 lines of verse

    # TRANSLATION section sits between TRANSLATION and PURPORT markers
    trans_match = re.search(
        r'TRANSLATION\s*\n(.*?)(?:\nPURPORT|\Z)', text, re.DOTALL | re.IGNORECASE
    )
    if trans_match:
        raw = ' '.join(trans_match.group(1).strip().split())
        translation = (raw[:280].rsplit(' ', 1)[0] + '...') if len(raw) > 280 else raw

    return iast, translation


def format_chunks_for_prompt(chunks: list) -> str:
    """
    Formats chunks as context for the LLM prompt.
    Uses clear SOURCE / REFERENCE / TEXT labels so Claude cannot miss the slok reference.
    """
    if not chunks:
        return "NO_CONTEXT_FOUND"

    parts = []
    for c in chunks:
        ch = c.get("chapter") or ""
        vs = c.get("verse")   or ""

        header = f"SOURCE: {c['source']}"
        if ch and vs:
            header += f"\nREFERENCE: Chapter {ch}, Verse {vs}   ← mention this naturally in your answer"
        elif ch:
            header += f"\nREFERENCE: Chapter {ch}   ← mention this naturally in your answer"

        parts.append(f"{header}\nTEXT: {c['text']}")

    return "\n\n---\n\n".join(parts)
