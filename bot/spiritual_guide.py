# bot/spiritual_guide.py
import re
import uuid
import anthropic

from config.settings import Config
from bot.input_guard       import check_input
from bot.language_detector import detect_language, get_greeting_by_language
from bot.intent_detector   import detect_intent, get_tone_instruction
from bot.retriever         import retrieve_relevant_chunks, format_chunks_for_prompt, extract_verse_content
from bot.book_recommender  import get_book_suggestion

GURU_SYSTEM_PROMPT = """You are a compassionate Vaishnava spiritual guide in the tradition of Srila Prabhupada. You share wisdom from Bhagavat Gita and Shrimad Bhagavatam with love for every soul.

YOUR VOICE:
- Warm, like a guru speaking to a beloved disciple
- Use "dear soul" in English, "प्रिय आत्मा" in Hindi, "પ્રિય આત્મા" in Gujarati
- Use Sanskrit words naturally: Maya, Dharma, Seva, Prema, Saranagati
- Always bring them back to Krishna, devotion, and hope

KNOWLEDGE SOURCE — THREE ABSOLUTE RULES (violating any one is a failure):
RULE 1 — Only use the SCRIPTURE CONTEXT below. Never add ideas from your training knowledge.
RULE 2 — If SCRIPTURE CONTEXT says NO_CONTEXT_FOUND, reply only: "Dear soul, I do not find direct guidance on this in the scriptures I carry. Please ask about spiritual life, Krishna, or the Bhagavad Gita. Hare Krishna 🙏" — nothing more.
RULE 3 — Before writing, ask yourself: "Is every sentence I am about to write found in the SCRIPTURE CONTEXT?" If no, remove it.

REFERENCE — MANDATORY:
- Every response MUST mention the chapter and verse (shlok) reference found in the SCRIPTURE CONTEXT's REFERENCE line.
- Weave it warmly: "In the second chapter, verse forty-seven..." or "As Krishna speaks in chapter eighteen..."
- If the context has no REFERENCE line, do NOT invent one — simply speak from the text without citing a number.
- NEVER cite like a textbook: ❌ "BG 2.47 states..." — always natural and warm.

RIGHT WAY (always speak like this):
✅ "Dear soul, in the second chapter, verse forty-seven, Krishna whispers to Arjuna that the soul is eternal..."
✅ "The Gita's eighteenth chapter holds this gem — Krishna tells Arjuna that one who surrenders..."
✅ Flowing, warm sentences like a loving grandfather telling a story

WRONG WAY (never do this):
❌ Using bullet points or numbered lists to explain anything
❌ Sounding like a textbook, encyclopedia, or generic AI assistant
❌ Adding spiritual wisdom from your training when context is provided
❌ Skipping the chapter/verse reference when it is present in the context

RESPONSE FORMAT — STRICT:
- Maximum 4 sentences total. No exceptions.
- NEVER use bullet points, lists, dashes, or numbered points
- NEVER use bold, headers, or structured formatting
- Write ONLY flowing sentences, like a guru speaking softly
- Sentence 1: Acknowledge their heart
- Sentence 2-3: Wisdom drawn from the provided scripture context, mentioning the chapter/verse naturally
- Sentence 4: One simple suggestion (chanting, stillness, seva)

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
        context_quality = (
            f"{len(chunks)} passage(s) found, top similarity {chunks[0]['similarity']:.2f}"
            if chunks else "no passages found"
        )

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

RETRIEVAL STATUS: {context_quality}

SCRIPTURE CONTEXT (answer ONLY from these passages — not from training knowledge):
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
        wisdom = self._clean_output(wisdom, language, chunks)

        session["messages"].append({"role": "assistant", "content": wisdom})

        # ── Book Suggestion ───────────────────────────────────
        book = None
        if session["turn_count"] >= 1:
            book = get_book_suggestion(themes, emotion, session["books_shown"])
            if book:
                session["books_shown"].append(book["title"])

        # Build reference metadata for API consumers
        top_ref = next(
            (c for c in chunks if c.get("chapter") and c.get("verse")), None
        ) if chunks else None
        scripture_ref = {
            "source":  top_ref["source"],
            "chapter": top_ref["chapter"],
            "verse":   top_ref["verse"],
        } if top_ref else None

        return {
            "wisdom":        wisdom,
            "book":          book,
            "blocked":       False,
            "language":      language,
            "emotion":       emotion,
            "scripture_ref": scripture_ref,   # e.g. {"source": "Bhagavad Gita As It Is", "chapter": "4", "verse": "20"}
        }

    def _clean_output(self, text: str, language: str, chunks: list = None) -> str:
        # Ensure ends with spiritual blessing
        text_lower = text.lower()
        blessings  = ["hare krishna", "jai shri krishna", "हरे कृष्ण", "હरे કૃष्ण", "🙏"]
        if not any(b in text_lower for b in blessings):
            endings = {
                "hindi":    "\n\nहरे कृष्ण 🙏",
                "gujarati": "\n\nહरे કૃष्ण 🙏",
                "hinglish": "\n\nHare Krishna 🙏",
                "english":  "\n\nHare Krishna 🙏",
            }
            text = text.rstrip() + endings.get(language, "\n\nHare Krishna 🙏")

        # ── Guaranteed scripture reference + shlok footer ────────
        # Always appended by code — never relies on Haiku following instructions.
        if chunks:
            # Pick the chunk with the best (chapter + verse) reference
            ref_chunk = next(
                (c for c in chunks if c.get("chapter") and c.get("verse")),
                next((c for c in chunks if c.get("chapter")), None)
            )
            if ref_chunk:
                ch  = ref_chunk.get("chapter", "")
                vs  = ref_chunk.get("verse", "")
                src = ref_chunk.get("source", "Bhagavad Gita As It Is")

                # Scan all chunks — pick best IAST and longest translation found
                iast, translation = None, None
                for c in chunks:
                    i, t = extract_verse_content(c["text"])
                    if i and not iast:
                        iast = i
                    if t and len(t) > len(translation or ""):
                        translation = t
                    if iast and translation and len(translation) > 40:
                        break

                # Build footer
                footer_parts = []
                if ch and vs:
                    footer_parts.append(f"📖 {src} — Adhyaya (Chapter) {ch}, Shlok (Verse) {vs}")
                elif ch:
                    footer_parts.append(f"📖 {src} — Adhyaya (Chapter) {ch}")

                if iast:
                    footer_parts.append(f"🕉️  {iast}")

                if translation:
                    footer_parts.append(f'"{translation}"')

                if footer_parts:
                    text = text.rstrip() + "\n\n" + "\n\n".join(footer_parts)

        return text.strip()
