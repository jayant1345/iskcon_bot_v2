# bot/book_recommender.py
# ========================
# Suggests ISKCON books after 4+ turns.
# Book is chosen by Claude reading the actual conversation direction —
# not by counting theme keywords.

import logging
logger = logging.getLogger(__name__)

BOOK_MAP = {
    "karma":        ("Bhagavad Gita As It Is",
                     "Srila Prabhupada explains selfless action so beautifully here",
                     "https://iskconbooks.in/product/bhagavad-gita-as-it-is/"),
    "dharma":       ("Perfect Questions Perfect Answers",
                     "A young seeker asked Prabhupada exactly what you are asking",
                     "https://iskconbooks.in/product/perfect-questions-perfect-answers/"),
    "death":        ("Beyond Birth and Death",
                     "This small book holds answers to the soul's deepest questions",
                     "https://iskconbooks.in/product/beyond-birth-and-death/"),
    "devotion":     ("Nectar of Devotion",
                     "The complete science of Bhakti — written with so much love",
                     "https://iskconbooks.in/product/nectar-of-devotion/"),
    "maya":         ("Raja Vidya",
                     "Krishna reveals the highest knowledge about this material world",
                     "https://iskconbooks.in/product/raja-vidya/"),
    "surrender":    ("Bhagavad Gita As It Is",
                     "Krishna's final teaching on surrender is the heart of this book",
                     "https://iskconbooks.in/product/bhagavad-gita-as-it-is/"),
    "liberation":   ("Coming Back",
                     "The science of reincarnation — where does the soul truly go?",
                     "https://iskconbooks.in/product/coming-back/"),
    "meditation":   ("Bhagavad Gita As It Is",
                     "Chapter 6 speaks directly about the path of yoga and the mind",
                     "https://iskconbooks.in/product/bhagavad-gita-as-it-is/"),
    "detachment":   ("Renunciation Through Wisdom",
                     "Prabhupada explains how to live in the world without being bound by it",
                     "https://iskconbooks.in/product/renunciation-through-wisdom/"),
    "anger":        ("Nectar of Instruction",
                     "These eleven verses from Prabhupada are a direct remedy for the restless mind",
                     "https://iskconbooks.in/product/nectar-of-instruction/"),
    "suffering":    ("Beyond Birth and Death",
                     "The soul's journey through pain and liberation — Prabhupada explains with great compassion",
                     "https://iskconbooks.in/product/beyond-birth-and-death/"),
    "relationships":("Perfect Questions Perfect Answers",
                     "The deepest questions about love, family, and purpose answered by Prabhupada himself",
                     "https://iskconbooks.in/product/perfect-questions-perfect-answers/"),
    "knowledge":    ("Raja Vidya",
                     "The king of all knowledge — Krishna's most confidential wisdom explained by Prabhupada",
                     "https://iskconbooks.in/product/raja-vidya/"),
    "scripture":    ("Bhagavad Gita As It Is",
                     "The original Gita with Prabhupada's purports — the most complete edition available",
                     "https://iskconbooks.in/product/bhagavad-gita-as-it-is/"),
    "tradition":    ("Teachings of Lord Chaitanya",
                     "The philosophy and practice of the Vaishnava tradition explained in full",
                     "https://iskconbooks.in/product/teachings-of-lord-chaitanya/"),
    "avatar":       ("Krishna — The Supreme Personality of Godhead",
                     "Prabhupada narrates Krishna's pastimes — the most beautiful book ever written",
                     "https://iskconbooks.in/product/krishna-the-supreme-personality-of-godhead/"),
    "general":      ("Bhagavad Gita As It Is",
                     "Begin here, dear one — this is Krishna speaking directly to you",
                     "https://iskconbooks.in/product/bhagavad-gita-as-it-is/"),
}

# Phrases rotate so each suggestion feels personal and earned
PHRASES = [
    "After our conversation today, I feel Srila Prabhupada's **{title}** would speak directly to your heart. Available at iskconbooks.in 🙏",
    "Dear soul, the questions you carry today — **{title}** holds their deepest answers. iskconbooks.in 🙏",
    "Srila Prabhupada poured his heart into **{title}** — it speaks to exactly what we have been exploring together. iskconbooks.in 🙏",
    "There is a book I would lovingly place in your hands — **{title}**. Read it when your heart is quiet. iskconbooks.in 🙏",
]
_pidx = 0

MIN_TURNS = 4  # wait until the conversation has real depth before suggesting

_SELECTOR_PROMPT = """\
You are helping a Vaishnava spiritual guide recommend exactly one book to a spiritual seeker.

Read the seeker's questions below and understand the TRUE DIRECTION of their spiritual journey — \
not just the words, but what they are really seeking, where their heart is going.

SEEKER'S CONVERSATION:
{conversation}

AVAILABLE BOOKS (each line: key | title | what it offers):
{book_list}

GUIDELINES:
- Philosophy / tattva / deep questions about reality → knowledge, tradition, scripture, maya
- Pain, grief, loss, death → death, suffering
- How to act / duty / career / family decisions → karma, dharma, relationships
- Devotion, chanting, temple, wanting to love Krishna → devotion, surrender
- Anger, ego, mind control, inner peace → anger, detachment, meditation
- Soul, afterlife, reincarnation, what happens after death → liberation, death
- General curiosity about Krishna, his stories, his forms → avatar
- Beginning spiritual life, general seeking → general

Reply with ONLY the book key (one word, lowercase). Nothing else."""


def get_book_suggestion(session_messages: list, emotion: str,
                        books_shown: list, turn_count: int,
                        client) -> "dict | None":
    """
    After MIN_TURNS turns, asks Claude to read the actual conversation and
    pick the most fitting book based on the direction of the seeker's journey.
    Falls back to 'general' if the Claude call fails.
    """
    global _pidx

    if turn_count < MIN_TURNS:
        return None

    if emotion in ["grief", "hopelessness"] and not books_shown:
        return None

    if len(books_shown) >= 2:
        return None

    # Build the book list excluding already-shown titles
    available = {
        k: v for k, v in BOOK_MAP.items()
        if k != "general" and v[0] not in books_shown
    }
    if not available:
        return None

    book_list_text = "\n".join(
        f"{key} | {title} | {why}"
        for key, (title, why, _) in available.items()
    )

    # Use only user turns so Claude reads the seeker's voice, not the bot's answers
    user_turns = [
        m["content"] for m in session_messages
        if m["role"] == "user"
    ]
    conversation_text = "\n".join(
        f"Q{i+1}: {msg}" for i, msg in enumerate(user_turns)
    )

    chosen_key = _ask_claude_for_book(
        client, conversation_text, book_list_text, available
    )

    # Resolve chosen key → book entry
    if chosen_key and chosen_key in available:
        title, why, url = available[chosen_key]
    else:
        # Fallback: general (if not already shown)
        title, why, url = BOOK_MAP["general"]
        if title in books_shown:
            return None

    phrase = PHRASES[_pidx % len(PHRASES)]
    _pidx += 1

    return {
        "title":           title,
        "url":             url,
        "why":             why,
        "suggestion_text": phrase.format(title=title),
    }


def _ask_claude_for_book(client, conversation_text: str,
                         book_list_text: str, available: dict) -> "str | None":
    """
    Calls Claude Haiku with the conversation + book list.
    Returns a book key string, or None on failure.
    """
    try:
        prompt = _SELECTOR_PROMPT.format(
            conversation=conversation_text,
            book_list=book_list_text,
        )
        response = client.messages.create(
            model      = "claude-haiku-4-5-20251001",
            max_tokens = 10,
            messages   = [{"role": "user", "content": prompt}],
        )
        key = response.content[0].text.strip().lower().strip('"').strip("'")
        return key if key in available else None
    except Exception as e:
        logger.warning("Book selector Claude call failed: %s", e)
        return None
