# bot/language_detector.py
# ==========================
# Detects which language the user is writing in.
# No external API needed — pure Python character detection.
# Supports: English, Hindi, Gujarati, Marathi, Bengali + Hinglish

def detect_language(text: str) -> dict:
    """
    Detects language from Unicode character ranges.
    
    Returns:
    {
        "language": "hindi" | "gujarati" | "english" | "hinglish" | etc.,
        "script":   "devanagari" | "gujarati" | "latin",
        "reply_instruction": "instruction for LLM about which language to reply in"
    }
    """
    if not text:
        return _english()

    # Count characters by script
    devanagari = sum(1 for c in text if '\u0900' <= c <= '\u097F')   # Hindi/Marathi
    gujarati   = sum(1 for c in text if '\u0A80' <= c <= '\u0AFF')   # Gujarati
    bengali    = sum(1 for c in text if '\u0980' <= c <= '\u09FF')   # Bengali
    latin      = sum(1 for c in text if c.isascii() and c.isalpha()) # English/Roman

    total = len(text.replace(" ", ""))
    if total == 0:
        return _english()

    deva_ratio = devanagari / total
    guj_ratio  = gujarati   / total
    ben_ratio  = bengali    / total
    latin_ratio = latin     / total

    # Pure Gujarati script
    if guj_ratio > 0.3:
        return {
            "language": "gujarati",
            "script":   "gujarati",
            "reply_instruction": (
                "The user is writing in Gujarati. "
                "You MUST reply entirely in Gujarati script. "
                "Use warm, respectful Gujarati. "
                "Sanskrit words like Krishna, Dharma, Maya can stay in Sanskrit. "
                "Address them as 'પ્રિય આત્મા' (dear soul)."
            )
        }

    # Pure Hindi / Devanagari
    if deva_ratio > 0.3:
        return {
            "language": "hindi",
            "script":   "devanagari",
            "reply_instruction": (
                "The user is writing in Hindi. "
                "You MUST reply entirely in Hindi (Devanagari script). "
                "Use warm, respectful Hindi. "
                "Sanskrit words like Krishna, Dharma, Maya can stay in Sanskrit. "
                "Address them as 'प्रिय आत्मा' (dear soul)."
            )
        }

    # Bengali
    if ben_ratio > 0.3:
        return {
            "language": "bengali",
            "script":   "bengali",
            "reply_instruction": (
                "The user is writing in Bengali. "
                "Reply entirely in Bengali script. "
                "Address them warmly as 'প্রিয় আত্মা'."
            )
        }

    # Hinglish — mix of Hindi words in Roman/Latin script
    hinglish_words = [
        "mujhe","mera","meri","kya","kaise","kyun","bahut",
        "acha","theek","bhai","yaar","matlab","samajh","dil",
        "zindagi","mushkil","pareshan","khush","dukh","sukh",
        "soch","raha","rahi","hoon","hai","hain","nahi","nahin",
        "lagta","lagti","chahiye","karna","karo","karte"
    ]
    text_lower = text.lower()
    hinglish_count = sum(1 for w in hinglish_words if w in text_lower)

    if hinglish_count >= 2:
        return {
            "language": "hinglish",
            "script":   "latin",
            "reply_instruction": (
                "The user is writing in Hinglish (Hindi words in English/Roman script). "
                "Reply in the SAME Hinglish style — Hindi words written in English letters. "
                "For example: 'Priya aatma, Krishna kehte hain ki aatma amar hai...'. "
                "This feels most natural and close to them. "
                "Do NOT switch to pure English or pure Hindi Devanagari."
            )
        }

    # Default: English
    return _english()


def _english():
    return {
        "language": "english",
        "script":   "latin",
        "reply_instruction": (
            "The user is writing in English. "
            "Reply in warm, compassionate English."
        )
    }


def get_greeting_by_language(language: str) -> str:
    """
    Returns opening greeting in the user's language.
    Called when chat widget first opens.
    """
    greetings = {
        "hindi": """हरे कृष्ण 🙏

प्रिय आत्मा, स्वागत है।

यह स्थान भागवत गीता और श्रीमद् भागवतम् के 
ज्ञान का पवित्र स्थान है।

आज आपके मन में क्या है? 
जो भी बोझ हो, जो भी खोज हो — 
निःसंकोच बताइए।

कृष्ण सुन रहे हैं, और मैं भी 🌸""",

        "gujarati": """હરે કૃષ્ણ 🙏

પ્રિય આત્મા, સ્વાગત છે।

આ સ્થાન ભગવત ગીતા અને શ્રીમદ્ ભાગવતમ્ ના
જ્ઞાનનું પવિત્ર સ્થળ છે।

આજે તમારા મનમાં શું છે?
જે પણ ભાર હોય, જે પણ જિજ્ઞાસા હોય —
નિઃસંકોચ જણાવો।

કૃષ્ણ સાંભળી રહ્યા છે, અને હું પણ 🌸""",

        "hinglish": """Hare Krishna 🙏

Priya aatma, aapka swagat hai.

Yeh jagah Bhagavat Gita aur Shrimad Bhagavatam ke
gyan ka pavitra sthan hai.

Aaj aapke mann mein kya hai?
Jo bhi bojh ho, jo bhi khoj ho —
bejhijhak batayein.

Krishna sun rahe hain, aur main bhi 🌸""",

        "english": """Hare Krishna 🙏

Dear soul, welcome.

This is a sacred space for spiritual guidance,
drawn from the wisdom of Bhagavat Gita and
Shrimad Bhagavatam.

What is in your heart today?
Whatever you are carrying, whatever you are seeking —
share freely.

Krishna is listening, and so am I 🌸""",
    }
    return greetings.get(language, greetings["english"])
