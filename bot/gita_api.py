# bot/gita_api.py
# ================
# Fetches real Sanskrit shlok from vedicscriptures.github.io (free, no API key).
# URL: https://vedicscriptures.github.io/slok/{chapter}/{verse}/
#
# In-memory cache ensures each chapter/verse is fetched only once per server lifetime.

import json
import logging
from urllib.request import urlopen, Request
from urllib.error   import URLError, HTTPError

logger  = logging.getLogger(__name__)
_cache  = {}   # {(chapter, verse): result_dict}

BASE_URL = "https://vedicscriptures.github.io/slok"


def fetch_shlok(chapter: str, verse: str, timeout: int = 3) -> dict:
    """
    Returns dict with keys:
      sanskrit        — Devanagari text  e.g. "नियतं कुरु कर्म त्वं..."
      transliteration — IAST/Roman       e.g. "niyataṁ kuru karma tvaṁ..."
      translation     — English meaning  e.g. "Do your prescribed duty..."

    Returns {} on any failure — caller must fall back gracefully.
    Results are cached in memory; same verse is never fetched twice.
    """
    key = (str(chapter), str(verse))
    if key in _cache:
        return _cache[key]

    url = f"{BASE_URL}/{chapter}/{verse}/"
    try:
        req  = Request(url, headers={"User-Agent": "iskcon-spiritual-bot/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        # The API has multiple translators — pick English translation in priority order
        translation = (
            (data.get("siva")    or {}).get("et") or
            (data.get("purohit") or {}).get("et") or
            (data.get("rams")    or {}).get("et") or
            (data.get("tej")     or {}).get("ht") or   # Hindi fallback
            ""
        )

        # Clean up the translation — remove leading/trailing whitespace and newlines
        translation = " ".join(translation.split()) if translation else ""
        if len(translation) > 300:
            translation = translation[:300].rsplit(" ", 1)[0] + "..."

        result = {
            "sanskrit":        data.get("slok", "").strip(),
            "transliteration": data.get("transliteration", "").strip(),
            "translation":     translation,
        }

        _cache[key] = result
        logger.info("✅ Gita API: fetched Ch %s V %s", chapter, verse)
        return result

    except HTTPError as e:
        logger.warning("⚠️  Gita API 404/error for Ch %s V %s: %s", chapter, verse, e)
    except URLError as e:
        logger.warning("⚠️  Gita API network error: %s", e)
    except Exception as e:
        logger.warning("⚠️  Gita API unexpected error: %s", e)

    _cache[key] = {}   # cache the failure so we don't retry on every request
    return {}
