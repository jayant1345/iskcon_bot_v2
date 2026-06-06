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
import re
import sys
import argparse
import psycopg2
import fitz          # PyMuPDF — reads PDF
import numpy as np
from sentence_transformers import SentenceTransformer
from config.settings import Config

# Maps English ordinals to digits (Prabhupada books use "CHAPTER TWO" etc.)
ORDINAL_TO_NUM = {
    "ONE": "1", "TWO": "2", "THREE": "3", "FOUR": "4", "FIVE": "5",
    "SIX": "6", "SEVEN": "7", "EIGHT": "8", "NINE": "9", "TEN": "10",
    "ELEVEN": "11", "TWELVE": "12", "THIRTEEN": "13", "FOURTEEN": "14",
    "FIFTEEN": "15", "SIXTEEN": "16", "SEVENTEEN": "17", "EIGHTEEN": "18",
}

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


def _parse_chapter_verse(text: str, prev_chapter: str, prev_verse: str):
    """
    Scans page text for CHAPTER / TEXT headings common in Prabhupada books.
    Returns (chapter, verse) — carries forward previous values when not found on this page.

    Key rule: ONLY update chapter when a valid ordinal or digit 1-18 is found.
    Articles like THE, OF, THIS are skipped — they appear in headings like
    "CHAPTER THE YOGA OF..." and must not be stored as chapter numbers.
    """
    ch_match = re.search(r'CHAPTER\s+([A-Z]+|\d+)', text, re.IGNORECASE)
    vs_match = re.search(r'(?:TEXT|VERSE)\s+(\d+)', text, re.IGNORECASE)

    chapter = prev_chapter   # carry forward by default
    verse   = prev_verse

    if ch_match:
        raw = ch_match.group(1).upper()
        if raw in ORDINAL_TO_NUM:
            chapter = ORDINAL_TO_NUM[raw]        # "TWO" → "2"
        elif raw.isdigit() and 1 <= int(raw) <= 18:
            chapter = raw                        # "2" stays "2"
        # else: skip — "THE", "OF", "THIS" etc. are not chapter numbers

    if vs_match:
        verse = vs_match.group(1)

    return chapter, verse


def chunk_pages(pages: list, chunk_size: int = 600, overlap: int = 100) -> list:
    """
    Splits page text into overlapping chunks, tracking real chapter/verse headings.

    chunk_size = ~600 chars  ≈ one purport paragraph
    overlap    = 100 chars   = ensures no wisdom is cut mid-thought
    """
    chunks = []
    current_chapter = None
    current_verse   = None

    for page_num, text in pages:
        # Update running chapter/verse from this page's headings
        current_chapter, current_verse = _parse_chapter_verse(
            text, current_chapter, current_verse
        )

        pos = 0
        while pos < len(text):
            end        = min(pos + chunk_size, len(text))
            chunk_text = text[pos:end].strip()

            if len(chunk_text) > 150:
                # Check if this window itself starts a new verse
                _, local_verse = _parse_chapter_verse(chunk_text, current_chapter, current_verse)
                themes, emotions = auto_tag(chunk_text)

                chunks.append({
                    "text":    chunk_text,
                    "page":    page_num,
                    "chapter": current_chapter,
                    "verse":   local_verse,
                    "themes":  themes,
                    "emotions": emotions,
                })

            pos += chunk_size - overlap

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

    # Step 4: Clear old chunks for this source (fresh connection)
    with psycopg2.connect(Config.DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM scripture_chunks WHERE source = %s", (source_name,))
        conn.commit()
    print(f"🗑️  Cleared old {source_name} chunks")

    # Step 5: Embed and store — reconnect each batch to avoid Railway proxy timeout
    print(f"\n📥 Storing {len(chunks)} chunks into pgvector...")
    batch_size = 32

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        texts = [c["text"] for c in batch]

        embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

        # New connection per batch — Railway closes long-lived connections
        with psycopg2.connect(Config.DATABASE_URL) as conn:
            with conn.cursor() as cur:
                for chunk, embedding in zip(batch, embeddings):
                    cur.execute("""
                        INSERT INTO scripture_chunks
                            (source, chapter, verse, text, themes, emotions, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        source_name,
                        chunk.get("chapter"),
                        chunk.get("verse"),
                        chunk["text"],
                        chunk["themes"],
                        chunk["emotions"],
                        embedding.tolist()
                    ))
            conn.commit()

        done = min(i + batch_size, len(chunks))
        print(f"  ✅ {done}/{len(chunks)} chunks stored...", end="\r")

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
