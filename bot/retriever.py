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
# BROAD_THRESHOLD is the last-resort fallback when primary retrieval finds nothing.
SIMILARITY_THRESHOLD = 0.18
THEME_THRESHOLD      = 0.05
BROAD_THRESHOLD      = 0.08

_model = None

# Exact verse counts per chapter in Bhagavad Gita As It Is (used to reject bad metadata)
_CHAPTER_MAX_VERSE = {
    "1": 47, "2": 72, "3": 43, "4": 42, "5": 29,
    "6": 47, "7": 30, "8": 28, "9": 34, "10": 42,
    "11": 55, "12": 20, "13": 35, "14": 27, "15": 20,
    "16": 24, "17": 28, "18": 78,
}

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
    # Sanskrit / Vaishnava philosophical concepts
    "tattva":       "tattva five elements truth nature principle reality substance ishvara jiva prakriti kala karma",
    "panch":        "panch five tattva elements eternal truths nature principle philosophy",
    "five":         "five pancha tattva elements truths nature eternal five truths philosophy",
    "consciousness":"consciousness awareness pure spirit atma soul chit being presence transcendental",
    "devotee":      "devotee bhakta vaishnava servant surrender devotion service disciple pure",
    "guru":         "guru spiritual master teacher guide acharya prabhupada disciplic succession parampara",
    "chaitanya":    "chaitanya mahaprabhu golden avatar bhakti movement sankirtan devotion",
    "creation":     "creation manifest prakriti universe material nature three modes gunas",
    "nature":       "nature prakriti material creation manifest world modes gunas three",
    "time":         "time eternal kala cycle age yuga duration birth death",
    "service":      "service seva devotion bhakti surrender worship action",
    "material":     "material nature prakriti world illusion maya temporary body senses",
    "eternal":      "eternal soul spirit permanent transcendental beyond time deathless",
    "worship":      "worship devotion prayer bhajan kirtan pooja arati service temple",
    "truth":        "truth reality tattva brahman absolute self nature knowledge eternal",
    "bhagavad":     "bhagavad gita krishna arjuna battle kurukshetra wisdom teaching chapter",
    "gita":         "gita bhagavad krishna arjuna chapter verse teaching wisdom purport",
    "prabhupada":   "prabhupada srila founder acharya iskcon devotion teaching purport",
    "iskcon":       "iskcon hare krishna movement prabhupada devotion temple",
    "avatar":       "avatar incarnation form lord vishnu krishna descent purpose yuga",
    "bhagavatam":   "bhagavatam srimad purana story devotion krishna vishnu creation eternal",
    "philosophy":   "philosophy tattva principle truth knowledge wisdom understand reality",
    "scripture":    "scripture gita bhagavatam shastras verse chapter teaching purport",
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

    # Reject verse number if it exceeds the known max for that chapter.
    # "TEXT 49" in a Chapter 10 purport is a paragraph counter, not a verse.
    if vs and ch:
        try:
            vs_num  = int(vs)
            max_vs  = _CHAPTER_MAX_VERSE.get(ch, 999)
            if vs_num < 1 or vs_num > max_vs:
                vs = ""
        except ValueError:
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
            candidate = m.group(1)
            try:
                vs_num = int(candidate)
                max_vs = _CHAPTER_MAX_VERSE.get(ch, 999)
                if 1 <= vs_num <= max_vs:
                    vs = candidate
            except ValueError:
                pass

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

    # Strategy 3: Broad fallback — when primary retrieval finds nothing,
    # cast a very wide net at a very low threshold to surface *any* related passage.
    # This prevents "I don't know" responses for abstract Sanskrit/Vaishnava concepts
    # like "Panch Tatva" or "Navadha Bhakti" where vocabulary distance is high but
    # the question is genuinely spiritual and answerable from scripture.
    if not final:
        cur.execute("""
            SELECT source, chapter, verse, text, themes, emotions,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM scripture_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """, (embedding, embedding, top_k * 5))
        broad_results = cur.fetchall()

        for row in broad_results:
            key = row[3][:100]
            sim = float(row[6])
            if key not in seen and len(final) < top_k and sim > BROAD_THRESHOLD:
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
                    "matched_by": "broad_fallback",
                })

    cur.close()
    conn.close()

    if not final:
        logger.warning("⚠️  No relevant chunks found for: '%s'", question[:80])
    else:
        logger.info(
            "✅ %d chunks | top sim=%.3f | matched_by=%s | refs=%s",
            len(final),
            max(c["similarity"] for c in final),
            final[0].get("matched_by", "?"),
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
