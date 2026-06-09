# config/settings.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    ANTHROPIC_API_KEY   = os.getenv("ANTHROPIC_API_KEY")
    DATABASE_URL        = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/iskcon_bot")
    SECRET_KEY          = os.getenv("FLASK_SECRET_KEY", "dev-secret")
    DEBUG               = os.getenv("FLASK_ENV", "development") == "development"
    PORT                = int(os.getenv("PORT", 5000))
    BOT_MAX_TOKENS      = int(os.getenv("BOT_MAX_TOKENS", 1024))
    RETRIEVE_TOP_K      = int(os.getenv("RETRIEVE_TOP_K", 4))
    ISKCON_BOOKS_URL    = os.getenv("ISKCON_BOOKS_URL", "https://iskconbooks.in")

    # Free local embedding model — no API cost
    # Downloads ~90MB once, then runs offline forever
    EMBEDDING_MODEL     = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION = 384
    ADMIN_PASSWORD      = os.getenv("ADMIN_PASSWORD", "hare-krishna-admin")
