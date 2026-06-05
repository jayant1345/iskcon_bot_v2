# bot/spiritual_guide.py
import re
import uuid
import anthropic

from config.settings import Config
from bot.input_guard       import check_input
from bot.language_detector import detect_language, get_greeting_by_language
from bot.intent_detector   import detect_intent, get_tone_instruction
from bot.retriever         import retrieve_relevant_chunks, format_chunks_for_prompt
from bot.book_recommender  import get_book_suggestion

GURU_SYSTEM_PROMPT = """You are a compassionate Vaishnava spiritual guide in the tradition of Srila Prabhupada. You share wisdom from Bhagavat Gita and Shrimad Bhagavatam with love for every soul.

YOUR VOICE:
- Warm, like a guru speaking to a beloved disciple
- Use "dear soul" in English, "प्रिय आत्मा" in Hindi, "પ્રિય આત્મા" in Gujarati
- Use Sanskrit words naturally: Maya, Dharma, Seva, Prema, Saranagati
- Always bring them back to Krishna, devotion, and hope

KNOWLEDGE SOURCE — MOST IMPORTANT:
- You MUST answer ONLY from the SCRIPTURE CONTEXT provided below.
- Do NOT use your general training knowledge about spirituality, Gita, or Bhagavatam.
- If the provided context says NO_CONTEXT_FOUND — say warmly: "Dear soul, I do not find direct guidance on this in the scriptures I carry. Please ask about spiritual life, Krishna, or the Bhagavad Gita."
- Every answer must be rooted in the provided scripture passages only.

RIGHT WAY (always speak like this):
✅ "Dear soul, in the second chapter, Krishna whispers to Arjuna that the soul is eternal..."
✅ "The Gita speaks of this beautifully — Krishna says that one who sees inaction in action..."
✅ Flowing, warm sentences like a loving grandfather telling a story

WRONG WAY (never do this):
❌ "According to Bhagavad Gita 2.47, you should perform your duty..."
❌ Using bullet points or numbered lists to explain anything
❌ Sounding like a textbook, encyclopedia, or generic AI assistant
❌ Answering from your own training knowledge when context is provided

RESPONSE FORMAT — STRICT:
- Maximum 4 sentences total. No exceptions.
- NEVER use bullet points, lists, dashes, or numbered points
- NEVER use bold, headers, or structured formatting
- Write ONLY flowing sentences, like a guru speaking softly
- Sentence 1: Acknowledge their heart
- Sentence 2-3: Wisdom drawn from the provided scripture context
- Sentence 4: One simple suggestion (chanting, stillness, seva)

If the user asks about a specific verse or chapter — mention it naturally and warmly, like "In the second chapter, Krishna tells Arjuna..." — never like a textbook citation.

NEVER: use bullet points, sound like an AI, discuss politics/news/business, give medical/legal advice, shame anyone, leave someone without hope.

End every response with "Hare Krishna 🙏" or "Jai Shri Krishna 🙏\""""

ROLE_ANCHOR = (
    "You are a Vaishnava spiritual guide. "
    "Answer ONLY from the scripture context provided. "
    "Speak in warm flowing sentences. Never use bullet points."
)


class SpiritualGuide:

    def __init__(self):
        self.client    = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self._sessions = {}

    def get_greeting(self, user_message: str = "") -> dict:
        lang_info  = detect_language(user_message) if user_message else {"language": "english"}
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

        # ── Input Guard ───────────────────────────────────────
        guard = check_input(message)
        if not guard["allowed"]:
            return {"wisdom": guard["redirect"], "book": None, "blocked": True, "language": "unknown"}

        # ── Language Detection ────────────────────────────────
        lang_info        = detect_language(message)
        language         = lang_info["language"]
        lang_instruction = lang_info["reply_instruction"]
        msg_lower        = message.lower()

        if language == "english":
            if any(w in msg_lower for w in ["gujarati", "in gujarati", "gujaratima", "gujarati ma"]):
                lang_info        = detect_language("ગ")
                language         = "gujarati"
                lang_instruction = lang_info["reply_instruction"]
            elif any(w in msg_lower for w in ["in hindi", "hindi mein", "hindi me ", "hindi please", "hindi main"]):
                lang_info        = detect_language("क")
                language         = "hindi"
                lang_instruction = lang_info["reply_instruction"]
            elif not any(w in msg_lower for w in ["in english", "english please"]):
                prev_lang = self._sessions.get(session_id, {}).get("language", "english")
                if prev_lang in ("gujarati", "hindi", "hinglish"):
                    language = prev_lang
                    lang_info = detect_language("ગ" if prev_lang == "gujarati" else "क")
                    lang_instruction = lang_info["reply_instruction"]

        # ── Intent Detection ──────────────────────────────────
        intent  = detect_intent(message)
        emotion = intent["emotion"]
        themes  = intent["themes"]
        tone    = get_tone_instruction(emotion)

        # ── Context-aware Retrieval ───────────────────────────
        # For follow-up messages ("tell me more", "explain"), combine with recent context
        session_data     = self._sessions.get(session_id, {})
        recent_user_msgs = [m["content"] for m in session_data.get("messages", [])[-4:]
                            if m["role"] == "user"]
        follow_up_words  = ["more", "explain", "tell me", "continue", "again",
                            "what about", "further", "and", "also", "why"]
        is_follow_up     = (len(message.split()) < 10 and
                            any(w in msg_lower for w in follow_up_words))
        search_text      = " ".join(recent_user_msgs[-2:] + [message]) if is_follow_up else message

        chunks  = retrieve_relevant_chunks(search_text, themes)
        context = format_chunks_for_prompt(chunks)

        # ── Session Management ────────────────────────────────
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "messages": [], "books_shown": [],
                "turn_count": 0, "language": language
            }

        session = self._sessions[session_id]
        session["turn_count"] += 1
        session["language"]    = language

        session["messages"].append({"role": "user", "content": message})
        recent_messages = session["messages"][-4:]

        # ── Role Anchor every 3 turns to prevent drift ────────
        if session["turn_count"] % 3 == 0:
            recent_messages = [
                {"role": "user",      "content": ROLE_ANCHOR},
                {"role": "assistant", "content": "I understand. I will answer only from the provided Gita and Bhagavatam scripture context, speaking as a warm Vaishnava guide. Hare Krishna 🙏"},
            ] + recent_messages

        # ── Build System Prompt ───────────────────────────────
        full_system = f"""{GURU_SYSTEM_PROMPT}

LANGUAGE (most important): {lang_instruction}

SCRIPTURE CONTEXT (answer ONLY from this):
{context}

TONE: {tone} | EMOTION: {emotion}"""

        # ── Call Claude Haiku ─────────────────────────────────
        lang_token_multiplier = 3 if language == "gujarati" else (2 if language == "hindi" else 1)
        effective_max_tokens  = Config.BOT_MAX_TOKENS * lang_token_multiplier

        response = self.client.messages.create(
            model      = "claude-haiku-4-5-20251001",
            max_tokens = effective_max_tokens,
            system     = full_system,
            messages   = recent_messages,
        )

        wisdom = response.content[0].text
        wisdom = self._clean_output(wisdom, language)

        session["messages"].append({"role": "assistant", "content": wisdom})

        # ── Book Suggestion ───────────────────────────────────
        book = None
        if session["turn_count"] >= 1:
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

    def _clean_output(self, text: str, language: str) -> str:
        # Ensure ends with spiritual blessing
        text_lower = text.lower()
        blessings  = ["hare krishna", "jai shri krishna", "हरे कृष्ण", "હરે કૃષ્ણ", "🙏"]
        if not any(b in text_lower for b in blessings):
            endings = {
                "hindi":    "\n\nहरे कृष्ण 🙏",
                "gujarati": "\n\nહરે કૃષ્ણ 🙏",
                "hinglish": "\n\nHare Krishna 🙏",
                "english":  "\n\nHare Krishna 🙏",
            }
            text = text.rstrip() + endings.get(language, "\n\nHare Krishna 🙏")
        return text.strip()
