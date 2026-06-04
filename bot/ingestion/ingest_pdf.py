# bot/ingestion/ingest_pdf.py
# ============================
# Reads your actual PDF book and loads it into pgvector.
#
# SUPPORTS: Any Prabhupada book PDF
# (Bhagavat Gita As It Is, Shrimad Bhagavatam, etc.)
#
# HOW TO RUN:
#   python bot/ingestion/ingest_pdf.py --pdf "Bhagavad_Gita.pdf" --source "Bhagavat Gita"
#
# REQUIREMENTS:
#   pip install PyMuPDF  (already in requirements.txt)

import os
import sys
import argparse
import psycopg2
import fitz          # PyMuPDF — reads PDF
import numpy as np
from sentence_transformers import SentenceTransformer
from config.settings import Config

# ─────────────────────────────────────────────
# SPIRITUAL THEME KEYWORDS
# Used to auto-tag chunks with themes
# ─────────────────────────────────────────────
THEME_KEYWORDS = {
    "karma":       ["karma", "action", "result", "fruit", "deed", "work"],
    "dharma":      ["dharma", "duty", "purpose", "righteousness", "responsibility"],
    "death":       ["death", "die", "soul", "eternal", "rebirth", "body", "impermanent"],
    "devotion":    ["devotion", "bhakti", "worship", "devotee", "love", "surrender"],
    "detachment":  ["attachment", "detachment", "renunciation", "vairagya", "letting go"],
    "maya":        ["maya", "illusion", "material", "temporary", "false", "ignorance"],
    "meditation":  ["meditation", "mind", "concentrate", "yoga", "focus", "control"],
    "surrender":   ["surrender", "sharanagati", "refuge", "protect", "deliver"],
    "knowledge":   ["knowledge", "wisdom", "jnana", "understand", "realize", "truth"],
    "anger":       ["anger", "wrath", "passion", "desire", "lust", "greed"],
    "liberation":  ["liberation", "moksha", "freedom", "mukti", "transcend", "free"],
    "relationships":["family", "friend", "husband", "wife", "son", "daughter", "love"],
}

EMOTION_KEYWORDS = {
    "grief":       ["grief", "mourn", "weep", "sorrow", "lamentation", "cry"],
    "confusion":   ["confused", "bewildered", "doubt", "uncertain", "lost"],
    "fear":        ["fear", "afraid", "terrified", "anxiety", "worry", "dread"],
    "anger":       ["anger", "furious", "rage", "hatred", "enmity"],
    "guilt":       ["sin", "sinful", "mistake", "regret", "wrong", "evil"],
    "surrender":   ["surrender", "helpless", "refuge", "protect", "save"],
    "joy":         ["joy", "bliss", "happiness", "delight", "pleasure", "ananda"],
}


def extract_text_from_pdf(pdf_path: str) -> list:
    """
    Extracts text page by page from PDF.
    Returns list of (page_number, text) tuples.
    """
    print(f"📄 Reading PDF: {pdf_path}")
    doc = fitz.open(pdf_path)
    pages = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        text = text.strip()
        if len(text) > 100:   # skip mostly empty pages
            pages.append((page_num + 1, text))

    print(f"✅ Extracted {len(pages)} pages with content")
    doc.close()
    return pages


def chunk_pages(pages: list, chunk_size: int = 600, overlap: int = 100) -> list:
    """
    Splits page text into overlapping chunks.
    
    chunk_size = ~600 chars = roughly half a page
    overlap = 100 chars = ensures no wisdom is cut mid-thought
    
    Returns list of chunk dicts.
    """
    chunks = []
    full_text = ""
    page_map  = []   # tracks which page each char belongs to

    # Combine all pages into one stream with page tracking
    for page_num, text in pages:
        start = len(full_text)
        full_text += " " + text
        page_map.append((start, len(full_text), page_num))

    def get_page_for_pos(pos):
        for start, end, pg in page_map:
            if start <= pos < end:
                return pg
        return 0

    # Slide window through full text
    pos = 0
    while pos < len(full_text):
        end  = min(pos + chunk_size, len(full_text))
        text = full_text[pos:end].strip()

        if len(text) > 150:   # skip tiny fragments
            page_num = get_page_for_pos(pos)
            themes, emotions = auto_tag(text)

            chunks.append({
                "text":      text,
                "page":      page_num,
                "themes":    themes,
                "emotions":  emotions,
            })

        pos += chunk_size - overlap   # slide with overlap

    return chunks


def auto_tag(text: str) -> tuple:
    """
    Automatically detects themes and emotions
    in a text chunk using keyword matching.
    """
    text_lower = text.lower()
    themes   = [t for t, kws in THEME_KEYWORDS.items()
                if any(kw in text_lower for kw in kws)]
    emotions = [e for e, kws in EMOTION_KEYWORDS.items()
                if any(kw in text_lower for kw in kws)]
    return themes or ["general"], emotions or ["seeking"]


def ingest_pdf(pdf_path: str, source_name: str):
    """
    Main ingestion function.
    Reads PDF → chunks → embeds → stores in pgvector.
    """
    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found: {pdf_path}")
        sys.exit(1)

    print(f"\n🕉️  Starting ingestion of: {source_name}")
    print("━" * 50)

    # Step 1: Extract text from PDF
    pages = extract_text_from_pdf(pdf_path)

    # Step 2: Chunk into pieces
    print("✂️  Chunking text...")
    chunks = chunk_pages(pages)
    print(f"✅ Created {len(chunks)} chunks from {len(pages)} pages")

    # Step 3: Load embedding model
    print("\n🧠 Loading embedding model (downloads ~90MB first time)...")
    model = SentenceTransformer(Config.EMBEDDING_MODEL)
    print("✅ Embedding model ready")

    # Step 4: Connect to database
    conn = psycopg2.connect(Config.DATABASE_URL)
    cur  = conn.cursor()

    # Step 5: Remove existing chunks for this source
    cur.execute("DELETE FROM scripture_chunks WHERE source = %s", (source_name,))
    print(f"🗑️  Cleared old {source_name} chunks")

    # Step 6: Embed and store each chunk
    print(f"\n📥 Storing {len(chunks)} chunks into pgvector...")
    batch_size = 32   # embed 32 at a time for speed

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        texts = [c["text"] for c in batch]

        # Generate embeddings for whole batch at once (faster)
        embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

        for chunk, embedding in zip(batch, embeddings):
            cur.execute("""
                INSERT INTO scripture_chunks
                    (source, chapter, verse, text, themes, emotions, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                source_name,
                str(chunk["page"]),   # use page as chapter
                f"p.{chunk['page']}",
                chunk["text"],
                chunk["themes"],
                chunk["emotions"],
                embedding.tolist()
            ))

        conn.commit()
        done = min(i + batch_size, len(chunks))
        print(f"  ✅ {done}/{len(chunks)} chunks stored...", end="\r")

    cur.close()
    conn.close()

    print(f"\n\n🙏 Ingestion complete!")
    print(f"   Source  : {source_name}")
    print(f"   Pages   : {len(pages)}")
    print(f"   Chunks  : {len(chunks)}")
    print(f"\nYour bot now knows this scripture. Hare Krishna! 🌸")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest a PDF book into pgvector")
    parser.add_argument("--pdf",    required=True, help="Path to PDF file")
    parser.add_argument("--source", required=True, help="Book name (e.g. 'Bhagavat Gita')")
    args = parser.parse_args()

    ingest_pdf(args.pdf, args.source)
