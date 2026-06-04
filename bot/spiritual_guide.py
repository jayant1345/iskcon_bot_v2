# bot/spiritual_guide.py
# =======================
# The heart of the bot.
# Combines: language detection + intent detection
#           + RAG retrieval + Claude Haiku
#           + multilingual guru persona

import re
import uuid
import anthropic

from config.settings import Config
from bot.input_guard       import check_input
from bot.language_detector import detect_language, get_greeting_by_language
from bot.intent_detector   import detect_intent, get_tone_instruction
from bot.retriever         import retrieve_relevant_chunks, format_chunks_for_prompt
from bot.book_recommender  import get_book_suggestion

# ─────────────────────────────────────────────────────────────
# GURU SYSTEM PROMPT
# This is the soul of the bot.
# ─────────────────────────────────────────────────────────────

GURU_SYSTEM_PROMPT = """You are a compassionate Vaishnava spiritual guide in the tradition of Srila Prabhupada. You share wisdom from Bhagavat Gita and Shrimad Bhagavatam with love for every soul.

YOUR VOICE:
- Warm, like a guru speaking to a beloved disciple
- Use "dear soul" in English, "प्रिय आत्मा" in Hindi, "પ્રિય આત્મા" in Gujarati
- Use Sanskrit words naturally: Maya, Dharma, Seva, Prema, Saranagati
- Always bring them back to Krishna, devotion, and hope

RESPONSE FORMAT — STRICT:
- Maximum 4 sentences total. No exceptions.
- NEVER use bullet points, lists, dashes, or numbered points
- NEVER use bold, headers, or structured formatting
- Write ONLY flowing sentences, like a guru speaking softly
- Sentence 1: Acknowledge their heart
- Sentence 2-3: One piece of Krishna's wisdom
- Sentence 4: One simple suggestion (chanting, stillness, seva)

NEVER: cite chapter/verse numbers, use bullet points or lists, sound like a textbook, discuss politics/news/business, give medical/legal advice, shame anyone, leave someone without hope. Redirect inappropriate questions with love.

End every response with "Hare Krishna 🙏" or "Jai Shri Krishna 🙏\""""


class SpiritualGuide:

    def __init__(self):
        self.client   = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self._sessions = {}   # session_id → {messages, books_shown, turn_count, language}

    # ── Public API ────────────────────────────────────────────

    def get_greeting(self, user_message: str = "") -> dict:
        """
        Returns opening greeting + session ID.
        Detects language from any initial text if provided.
        """
        lang_info = detect_language(user_message) if user_message else {"language": "english"}
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = {
            "messages":    [],
            "books_shown": [],
            "turn_count":  0,
            "language":    lang_info["language"],
        }
        greeting = get_greeting_by_language(lang_info["language"])
        return {"session_id": session_id, "message": greeting, "language": lang_info["language"]}

    def respond(self, message: str, session_id: str) -> dict:
        """
        Main entry point. Processes user message → returns guru response.

        Returns:
        {
            "wisdom":   "response text",
            "book":     {book suggestion} or None,
            "blocked":  True/False,
            "language": detected language
        }
        """

        # ── Layer 1: Input Guard ──────────────────────────────
        guard = check_input(message)
        if not guard["allowed"]:
            return {"wisdom": guard["redirect"], "book": None, "blocked": True, "language": "unknown"}

        # ── Detect Language ───────────────────────────────────
        lang_info = detect_language(message)
        language  = lang_info["language"]
        lang_instruction = lang_info["reply_instruction"]

        # ── Detect Spiritual Intent ───────────────────────────
        intent   = detect_intent(message)
        emotion  = intent["emotion"]
        themes   = intent["themes"]
        tone     = get_tone_instruction(emotion)

        # ── Retrieve Relevant Scripture ───────────────────────
        chunks  = retrieve_relevant_chunks(message, themes)
        context = format_chunks_for_prompt(chunks)

        # ── Session Management ────────────────────────────────
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "messages": [], "books_shown": [],
                "turn_count": 0, "language": language
            }

        session = self._sessions[session_id]
        session["turn_count"] += 1
        session["language"]    = language   # update language each turn

        session["messages"].append({"role": "user", "content": message})
        recent_messages = session["messages"][-4:]   # last 4 messages only

        # ── Build Complete System Prompt ──────────────────────
        full_system = f"""{GURU_SYSTEM_PROMPT}

LANGUAGE (most important): {lang_instruction}

SCRIPTURE CONTEXT (absorb — never quote directly):
{context}

TONE: {tone} | EMOTION: {emotion}"""

        # ── Call Claude Haiku ─────────────────────────────────
        # Indic scripts use more tokens per word than English
        # Gujarati is less common in training data → needs even more headroom
        lang_token_multiplier = 3 if language == "gujarati" else (2 if language == "hindi" else 1)
        effective_max_tokens  = Config.BOT_MAX_TOKENS * lang_token_multiplier

        response = self.client.messages.create(
            model      = "claude-haiku-4-5-20251001",
            max_tokens = effective_max_tokens,
            system     = full_system,
            messages   = recent_messages,
        )

        wisdom = response.content[0].text

        # ── Layer 3: Output Cleaning ──────────────────────────
        wisdom = self._clean_output(wisdom, language)

        # Store bot response in history
        session["messages"].append({"role": "assistant", "content": wisdom})

        # ── Book Suggestion ───────────────────────────────────
        book = None
        if session["turn_count"] >= 2:
            book = get_book_suggestion(themes, emotion, session["books_shown"])
            if book:
                session["books_shown"].append(book["title"])

        return {
            "wisdom":   wisdom,
            "book":     book,
            "blocked":  False,
            "language": language,
            "emotion":  emotion,
        }

    # ── Private Helpers ───────────────────────────────────────

    def _clean_output(self, text: str, language: str) -> str:
        """Layer 3: Final output sanitization."""

        # Remove accidental verse number citations
        text = re.sub(r'\bChapter \d+,?\s*[Vv]erse \d+[\.\:]?\s*', '', text)
        text = re.sub(r'\b\d+\.\d+\s*[\-:]\s*', '', text)

        # Ensure ends with spiritual blessing
        text_lower = text.lower()
        blessings  = ["hare krishna", "jai shri krishna", "हरे कृष्ण", "હરે કૃષ્ણ", "🙏"]
        if not any(b in text_lower for b in blessings):
            endings = {
                "hindi":     "\n\nहरे कृष्ण 🙏",
                "gujarati":  "\n\nહરે કૃષ્ણ 🙏",
                "hinglish":  "\n\nHare Krishna 🙏",
                "english":   "\n\nHare Krishna 🙏",
            }
            text = text.rstrip() + endings.get(language, "\n\nHare Krishna 🙏")

        return text.strip()
