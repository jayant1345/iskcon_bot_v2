# bot/retriever.py
# =================
# Retrieves most relevant scripture chunks from pgvector.

import psycopg2
from sentence_transformers import SentenceTransformer
from config.settings import Config

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

    return final


def format_chunks_for_prompt(chunks: list) -> str:
    """Formats chunks as context for the LLM prompt."""
    if not chunks:
        return "Draw from general Bhagavat Gita and Bhagavatam wisdom."

    parts = []
    for i, c in enumerate(chunks, 1):
        parts.append(f"[Teaching {i} — {c['source']}]\n{c['text']}")

    return "\n\n---\n\n".join(parts)
