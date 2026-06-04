# bot/intent_detector.py
# =======================
# Detects emotion + spiritual theme from user message.
# Pure Python — FREE, no API call needed.

EMOTION_MAP = {
    "grief":            ["died","death","passed away","lost someone","miss them","grief","mourning","devastated","heartbroken","gone forever"],
    "anxiety":          ["worried","anxious","anxiety","panic","nervous","scared","stress","stressed","overthinking","cannot sleep","restless","tension"],
    "confusion":        ["confused","don't know","lost","what to do","no direction","unclear","which path","help me decide","samajh nahi","kya karu"],
    "anger":            ["angry","anger","furious","rage","hate","frustrated","irritated","cannot forgive","revenge","gussa","nafrat"],
    "guilt":            ["guilty","guilt","sinned","mistake","regret","ashamed","shame","bad person","done wrong","paap","galti"],
    "hopelessness":     ["hopeless","give up","no point","useless","worthless","meaningless","nothing works","haar gaya","thak gaya","himmat nahi"],
    "seeking_purpose":  ["purpose","meaning","why am i here","dharma","what should i do","direction","calling","mission","zindagi ka matlab"],
    "loneliness":       ["alone","lonely","no one","isolated","nobody cares","abandoned","friendless","akela","akeli"],
    "gratitude":        ["grateful","thankful","blessed","hare krishna","jai shri krishna","happy","joy","shukriya","dhanyavad"],
    "spiritual_seeking":["how to meditate","how to pray","how to chant","want to know krishna","start spiritual","bhakti","surrender","pooja"],
}

THEME_MAP = {
    "karma":        ["karma","action","result","fruit","consequence","work","karm"],
    "dharma":       ["dharma","duty","purpose","responsibility","dharm"],
    "death":        ["death","die","soul","eternal","rebirth","reincarnation","mrityu","aatma"],
    "devotion":     ["devotion","bhakti","worship","prayer","love for krishna","bhajan","pooja"],
    "detachment":   ["attachment","detachment","letting go","vairagya","material","moh"],
    "maya":         ["maya","illusion","material world","temporary","sansaar","duniya"],
    "meditation":   ["meditation","mind","yoga","focus","concentration","dhyan","mann"],
    "surrender":    ["surrender","give to god","sharanagati","accept","samarpan"],
    "relationships":["family","marriage","husband","wife","children","parents","friend","parivar","rishta"],
    "suffering":    ["pain","suffering","hardship","difficult","struggle","dukh","takleef"],
    "anger":        ["anger","forgiveness","forgive","hate","krodh","maafi"],
    "liberation":   ["moksha","liberation","freedom","mukti","transcend"],
}


def detect_intent(message: str) -> dict:
    msg_lower = message.lower()

    # Detect emotion
    emotion = "general_seeking"
    best_score = 0
    for emo, keywords in EMOTION_MAP.items():
        score = sum(1 for kw in keywords if kw in msg_lower)
        if score > best_score:
            best_score = score
            emotion = emo

    # Detect themes
    themes = [t for t, kws in THEME_MAP.items()
              if any(kw in msg_lower for kw in kws)]

    if not themes:
        fallback = {
            "grief": ["death","soul"], "anxiety": ["meditation","surrender"],
            "confusion": ["dharma","karma"], "anger": ["anger","detachment"],
            "guilt": ["karma","devotion"], "hopelessness": ["surrender","suffering"],
            "seeking_purpose": ["dharma","karma"], "loneliness": ["devotion","surrender"],
            "gratitude": ["devotion"], "spiritual_seeking": ["devotion","meditation"],
        }
        themes = fallback.get(emotion, ["devotion"])

    urgency = "high" if any(w in msg_lower for w in [
        "give up","no point","end it","why live","hopeless","desperate","please help"
    ]) else "medium"

    return {"emotion": emotion, "themes": themes, "urgency": urgency}


def get_tone_instruction(emotion: str) -> str:
    tones = {
        "grief":            "Speak very softly, like a loving parent with a grieving child. No solutions yet — just deep presence and warmth.",
        "anxiety":          "Speak calmly and steadily like still water. Ground them in the eternal. Slow, reassuring words.",
        "confusion":        "Speak with warm clarity, like lighting a lamp in a dark room. Patient, clear, unhurried.",
        "anger":            "Speak with peaceful steadiness. Be the calm in their storm. Do not match their energy.",
        "guilt":            "Speak with great compassion. Remind them of Krishna's infinite mercy. Absolutely no judgment.",
        "hopelessness":     "Speak with deep warmth and hope. Make them feel Krishna has not abandoned them.",
        "seeking_purpose":  "Speak with gentle inspiration. Awaken their higher self. Call them toward their dharma.",
        "loneliness":       "Speak as a close companion. Let them feel they are truly not alone.",
        "gratitude":        "Celebrate with them! Share in their joy. Encourage their devotion warmly.",
        "spiritual_seeking":"Speak as a welcoming guide. Make the spiritual path feel beautiful and accessible.",
        "general_seeking":  "Speak with warmth and wisdom. Meet them exactly where they are.",
    }
    return tones.get(emotion, tones["general_seeking"])
