# bot/book_recommender.py
# ========================
# Suggests ISKCON books naturally — like a guru's personal recommendation.

BOOK_MAP = {
    "karma":        ("Bhagavad Gita As It Is",  "Srila Prabhupada explains selfless action so beautifully here", "https://iskconbooks.in/product/bhagavad-gita-as-it-is/"),
    "dharma":       ("Perfect Questions Perfect Answers", "A young seeker asked Prabhupada exactly what you are asking", "https://iskconbooks.in/product/perfect-questions-perfect-answers/"),
    "death":        ("Beyond Birth and Death",  "This small book holds answers to the soul's deepest questions", "https://iskconbooks.in/product/beyond-birth-and-death/"),
    "devotion":     ("Nectar of Devotion",      "The complete science of Bhakti — written with so much love", "https://iskconbooks.in/product/nectar-of-devotion/"),
    "maya":         ("Raja Vidya",              "Krishna reveals the highest knowledge about this material world", "https://iskconbooks.in/product/raja-vidya/"),
    "surrender":    ("Bhagavad Gita As It Is",  "Krishna's final teaching on surrender is the heart of this book", "https://iskconbooks.in/product/bhagavad-gita-as-it-is/"),
    "liberation":   ("Coming Back",            "The science of reincarnation — where does the soul truly go?", "https://iskconbooks.in/product/coming-back/"),
    "meditation":   ("Bhagavad Gita As It Is",  "Chapter 6 speaks directly about the path of yoga and the mind", "https://iskconbooks.in/product/bhagavad-gita-as-it-is/"),
    "general":      ("Bhagavad Gita As It Is",  "Begin here, dear one — this is Krishna speaking directly to you", "https://iskconbooks.in/product/bhagavad-gita-as-it-is/"),
}

PHRASES = [
    "If these words have touched something in you, Srila Prabhupada has gone even deeper in **{title}**. Available at iskconbooks.in 🙏",
    "Dear one, when you are ready to go deeper — **{title}** will be a beautiful companion. iskconbooks.in 🙏",
    "Srila Prabhupada poured his heart into **{title}** — it speaks directly to what you carry. iskconbooks.in 🙏",
    "There is a book I would lovingly place in your hands — **{title}**. Read it when your heart is quiet. iskconbooks.in 🙏",
]
_pidx = 0


def get_book_suggestion(themes: list, emotion: str, books_shown: list) -> dict | None:
    global _pidx

    # Don't suggest on first grief/hopeless response — comfort first
    if emotion in ["grief","hopelessness"] and not books_shown:
        return None

    # Max 2 books per conversation
    if len(books_shown) >= 2:
        return None

    book = None
    for theme in themes:
        if theme in BOOK_MAP:
            title, why, url = BOOK_MAP[theme]
            if title not in books_shown:
                book = {"title": title, "why": why, "url": url}
                break

    if not book:
        title, why, url = BOOK_MAP["general"]
        if title in books_shown:
            return None
        book = {"title": title, "why": why, "url": url}

    phrase = PHRASES[_pidx % len(PHRASES)]
    _pidx += 1

    return {
        "title":           book["title"],
        "url":             book["url"],
        "why":             book["why"],
        "suggestion_text": phrase.format(title=book["title"]),
    }
