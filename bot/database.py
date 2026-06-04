# bot/database.py
# ================
# Run ONCE before anything else:
#   python bot/database.py

import psycopg2
from config.settings import Config


def setup_database():
    print("🔧 Setting up database...")
    conn = psycopg2.connect(Config.DATABASE_URL)
    cur  = conn.cursor()

    # Enable pgvector
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    print("✅ pgvector enabled")

    # Scripture chunks — stores every passage + its vector embedding
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS scripture_chunks (
            id          SERIAL PRIMARY KEY,
            source      TEXT NOT NULL,
            chapter     TEXT,
            verse       TEXT,
            text        TEXT NOT NULL,
            themes      TEXT[],
            emotions    TEXT[],
            situations  TEXT[],
            embedding   vector({Config.EMBEDDING_DIMENSION}),
            created_at  TIMESTAMP DEFAULT NOW()
        );
    """)
    print("✅ scripture_chunks table ready")

    # Fast similarity search index
    cur.execute("""
        CREATE INDEX IF NOT EXISTS scripture_embedding_idx
        ON scripture_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """)
    print("✅ Vector index ready")

    # Book recommendations
    cur.execute("""
        CREATE TABLE IF NOT EXISTS book_recommendations (
            id          SERIAL PRIMARY KEY,
            title       TEXT NOT NULL,
            author      TEXT DEFAULT 'Srila Prabhupada',
            description TEXT,
            themes      TEXT[],
            url         TEXT,
            image_url   TEXT,
            is_active   BOOLEAN DEFAULT TRUE
        );
    """)
    print("✅ book_recommendations table ready")

    # Chat sessions — keeps conversation history per user
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id          SERIAL PRIMARY KEY,
            session_id  TEXT UNIQUE NOT NULL,
            messages    JSONB DEFAULT '[]',
            created_at  TIMESTAMP DEFAULT NOW(),
            updated_at  TIMESTAMP DEFAULT NOW()
        );
    """)
    print("✅ chat_sessions table ready")

    # Seed ISKCON books
    _seed_books(cur)

    conn.commit()
    cur.close()
    conn.close()
    print("\n🙏 Database ready! Hare Krishna!")


def _seed_books(cur):
    books = [
        ("Bhagavad Gita As It Is",
         "Krishna's direct words — the foundation of all spiritual wisdom",
         ["karma","dharma","detachment","duty","soul","yoga","knowledge","anger","surrender","maya"],
         "https://iskconbooks.in/product/bhagavad-gita-as-it-is/"),

        ("Shrimad Bhagavatam",
         "The complete story of Krishna and the soul's eternal journey",
         ["devotion","stories","creation","liberation","bhakti","death"],
         "https://iskconbooks.in/product/srimad-bhagavatam/"),

        ("Nectar of Devotion",
         "The complete science of Bhakti Yoga — pure devotional service",
         ["devotion","bhakti","love","service","worship"],
         "https://iskconbooks.in/product/nectar-of-devotion/"),

        ("Beyond Birth and Death",
         "Understanding the eternal soul beyond this temporary body",
         ["death","soul","afterlife","rebirth","eternal","grief"],
         "https://iskconbooks.in/product/beyond-birth-and-death/"),

        ("Perfect Questions Perfect Answers",
         "A young seeker's deep conversation with Srila Prabhupada",
         ["purpose","seeking","life meaning","youth","questions"],
         "https://iskconbooks.in/product/perfect-questions-perfect-answers/"),

        ("Raja Vidya — The King of Knowledge",
         "Krishna reveals the highest and most confidential knowledge",
         ["maya","illusion","knowledge","material world"],
         "https://iskconbooks.in/product/raja-vidya/"),

        ("Coming Back",
         "The science of reincarnation — where does the soul go?",
         ["reincarnation","death","afterlife","soul journey"],
         "https://iskconbooks.in/product/coming-back/"),

        ("Nectar of Instruction",
         "Essential guidance for rapid spiritual advancement",
         ["spiritual practice","guru","advancement","devotee"],
         "https://iskconbooks.in/product/nectar-of-instruction/"),
    ]

    for title, desc, themes, url in books:
        cur.execute("""
            INSERT INTO book_recommendations (title, description, themes, url)
            SELECT %s, %s, %s, %s
            WHERE NOT EXISTS (
                SELECT 1 FROM book_recommendations WHERE title = %s
            );
        """, (title, desc, themes, url, title))

    print("✅ Books seeded")


if __name__ == "__main__":
    setup_database()
