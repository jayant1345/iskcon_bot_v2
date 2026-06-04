# bot/input_guard.py
# ===================
# Layer 1: Checks every message BEFORE reaching the LLM.
# Blocks vulgar, off-topic, manipulative inputs.

import re

BLOCKED_WORDS = [
    "sex","porn","nude","naked","rape","murder someone",
    "ignore your instructions","forget your rules",
    "pretend you are","act as a different ai",
    "jailbreak","dan mode","developer mode",
    "curse someone","destroy my enemy",
    "black magic","voodoo","harm someone","kill",
]

OFF_TOPIC_PATTERNS = [
    r"\bstock market\b", r"\bshare price\b", r"\bcrypto\b", r"\bnifty\b",
    r"\bpolitics\b", r"\belection\b", r"\bvote\b",
    r"\bcricket score\b", r"\bipl\b", r"\bfootball score\b",
    r"\bcode\b.*\bpython\b", r"\bjavascript\b", r"\bprogramming help\b",
    r"\bbollywood\b", r"\bmovie review\b", r"\bcelebrity gossip\b",
]

REDIRECTS = [
    "Dear one, this sacred space holds only Krishna's wisdom.\n\nWhat is truly in your heart today? 🙏",
    "This humble guide exists only to share the Gita's light.\n\nPerhaps there is a deeper question your soul is asking? 🙏",
    "Dear soul, let us return to what truly matters — your inner journey.\n\nWhat are you carrying today? 🙏",
]
_idx = 0

def _get_redirect():
    global _idx
    msg = REDIRECTS[_idx % len(REDIRECTS)]
    _idx += 1
    return msg


def check_input(message: str) -> dict:
    """
    Returns {"allowed": True} or {"allowed": False, "redirect": "..."}
    """
    if not message or len(message.strip()) < 2:
        return {"allowed": False, "redirect": "Please share what is in your heart, dear one 🙏"}

    if len(message) > 2000:
        return {"allowed": False, "redirect": "Dear one, please share your question simply, from the heart 🙏"}

    msg_lower = message.lower()

    for word in BLOCKED_WORDS:
        if word in msg_lower:
            return {
                "allowed": False,
                "redirect": "Dear one, this space is sacred — like sitting before Krishna.\n\nPlease bring your heart's true questions here 🙏"
            }

    for pattern in OFF_TOPIC_PATTERNS:
        if re.search(pattern, msg_lower):
            return {"allowed": False, "redirect": _get_redirect()}

    return {"allowed": True}
