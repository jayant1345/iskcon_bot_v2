# bot/retriever.py
# =================
# Retrieves most relevant scripture chunks from pgvector.

import psycopg2
import logging
from sentence_transformers import SentenceTransformer
from config.settings import Config

logger = logging.getLogger(__name__)
SIMILARITY_THRESHOLD = 0.15

_model = None

def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(Config.EMBEDDING_MODEL)
    return _model


def retrieve_relevant_chunks(question: str, themes: list, top_k: int = None) -> list:
    """
    Finds the most relevant scripture passages for a question.
    Combines semantic similarity + theme filtering.
    """
    top_k = top_k or Config.RETRIEVE_TOP_K
    model = _get_model()
    embedding = model.encode(question, normalize_embeddings=True).tolist()

    conn = psycopg2.connect(Config.DATABASE_URL)
    cur  = conn.cursor()

    # Strategy 1: Semantic similarity search
    cur.execute("""
        SELECT source, chapter, verse, text, themes, emotions,
               1 - (embedding <=> %s::vector) AS similarity
        FROM scripture_chunks
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
    """, (embedding, embedding, top_k * 2))
    semantic_results = cur.fetchall()

    # Strategy 2: Theme-filtered search
    theme_results = []
    if themes:
        cur.execute("""
            SELECT source, chapter, verse, text, themes, emotions,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM scripture_chunks
            WHERE themes && %s::text[]
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """, (embedding, themes, embedding, top_k))
        theme_results = cur.fetchall()

    cur.close()
    conn.close()

    # Combine — theme results get priority
    seen  = set()
    final = []

    for row in (theme_results + semantic_results):
        key = f"{row[0]}-{row[2]}"
        if key not in seen and len(final) < top_k:
            seen.add(key)
            final.append({
                "source":    row[0],
                "chapter":   row[1],
                "verse":     row[2],
                "text":      row[3],
                "themes":    row[4],
                "emotions":  row[5],
                "similarity": float(row[6]),
            })

    # Filter out low-quality matches
    final = [c for c in final if c["similarity"] > SIMILARITY_THRESHOLD]

    if not final:
        logger.warning("⚠️  No relevant chunks found for: '%s'", question[:80])
    else:
        logger.info("✅ Retrieved %d chunks (top similarity: %.2f)", len(final), final[0]["similarity"])

    return final


def get_chunk_count() -> int:
    """Returns total number of chunks in DB — used for health checks."""
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


def format_chunks_for_prompt(chunks: list) -> str:
    """Formats chunks as context for the LLM prompt."""
    if not chunks:
        return "NO_CONTEXT_FOUND"

    parts = []
    for i, c in enumerate(chunks, 1):
        ref = ""
        if c.get("chapter") and c.get("verse"):
            ref = f" — Chapter {c['chapter']}, Verse {c['verse']}"
        parts.append(f"[{c['source']}{ref}]\n{c['text']}")

    return "\n\n---\n\n".join(parts)
