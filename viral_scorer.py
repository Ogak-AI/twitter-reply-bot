"""
viral_scorer.py — AI-powered viral potential scorer for World Cup 2026 headlines.
Uses a fast Groq API call to rate headlines 1–10. Only high-scoring content gets posted.
Includes a keyword fast-track to bypass AI scoring for obviously explosive headlines.
"""

import logging
import re
import requests

logger = logging.getLogger(__name__)

# Default score when the API fails — low enough to skip by default (safe fallback)
_FALLBACK_SCORE = 5

_SYSTEM_PROMPT = (
    "You are a Twitter/X viral content analyst specializing in FIFA World Cup 2026. "
    "Your job is to rate news headlines on a scale of 1 to 10 for viral potential on Twitter/X. "
    "You must respond with ONLY a single integer from 1 to 10, nothing else.\n\n"
    "Scoring guide:\n"
    "9-10: EXPLOSIVE — major breaking news, star player drama (Messi, Mbappe, Ronaldo, Haaland, Vinicius), "
    "shocking upsets, controversial referee decisions, tournament-shaking events, "
    "record-breaking moments, unexpected eliminations, host nation drama\n"
    "7-8: HIGH VIRAL — significant transfers/injuries affecting WC squads, group of death reveals, "
    "big nation squad announcements, viral fan moments, dramatic match results, "
    "manager sackings, doping scandals, major policy changes\n"
    "5-6: MODERATE — routine match previews, general squad updates, venue news, "
    "schedule announcements, minor team news\n"
    "3-4: LOW — administrative updates, minor logistics, ticket info, "
    "training camp reports, kit reveals for smaller teams\n"
    "1-2: NOT VIRAL — parking guidelines, volunteer programs, press credential info, "
    "broadcast schedules, corporate sponsorship deals\n"
)

_USER_PROMPT_TEMPLATE = (
    "Rate this World Cup 2026 headline for Twitter/X viral potential (1-10):\n\n"
    "\"{headline}\"\n\n"
    "Reply with ONLY a single integer."
)

# ── Keyword Fast-Track ──────────────────────────────────
# Headlines matching these patterns are auto-scored 10/10 without an API call.
# Saves ~1-2s on the most time-critical breaking news.
_FAST_TRACK_PATTERNS = re.compile(
    r"(?i)(?:"
    # Breaking news markers
    r"BREAKING|JUST\s*IN|OFFICIAL|CONFIRMED|EXCLUSIVE"
    r"|signs?\s+for|transfer\s+confirmed|deal\s+done|official\s+signing"
    # Injury / ban drama
    r"|ruled\s+out|torn\s+ACL|injury\s+blow|out\s+of\s+(?:the\s+)?World\s+Cup"
    r"|banned|suspended|doping|scandal"
    # Match drama
    r"|eliminated|knocked\s+out|stunned|upset|last[- ]minute|penalty\s+shootout|red\s+card"
    # Star players (first or last name is enough)
    r"|Messi|Mbapp[eé]|Ronaldo|Haaland|Vinicius|Bellingham|Neymar|Salah|De\s+Bruyne"
    r")"
)


def _check_fast_track(headline: str) -> int | None:
    """Returns 10 if headline matches fast-track keywords, else None."""
    if _FAST_TRACK_PATTERNS.search(headline):
        return 10
    return None


def score_viral_potential(headline: str, ai_config: dict, timeout: int = 5) -> int:
    """
    Scores a headline for viral potential on Twitter/X using Groq API.

    Args:
        headline: The article headline to score.
        ai_config: AI configuration dict (must contain groq_api_key, model).
        timeout: API request timeout in seconds.

    Returns:
        Integer score 1–10. Returns _FALLBACK_SCORE on any failure.
    """
    if not headline or not headline.strip():
        return _FALLBACK_SCORE

    # Fast-track: skip API call for obviously explosive headlines
    fast_score = _check_fast_track(headline)
    if fast_score is not None:
        logger.info(f"[FAST-TRACK {fast_score}/10] {headline[:60]}")
        return fast_score

    api_key = ai_config.get("groq_api_key")
    model = ai_config.get("model", "llama-3.3-70b-versatile")

    if not api_key:
        logger.warning("[VIRAL] Groq API key missing — returning fallback score")
        return _FALLBACK_SCORE

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _USER_PROMPT_TEMPLATE.format(headline=headline.strip())},
        ],
        "temperature": 0.1,
        "max_tokens": 5,
    }

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=timeout,
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"].strip()

        # Extract the first integer from the response
        match = re.search(r"\b(\d{1,2})\b", raw)
        if match:
            score = int(match.group(1))
            score = max(1, min(10, score))  # Clamp to 1–10
            return score

        logger.warning(f"[VIRAL] Could not parse score from API response: '{raw}'")
        return _FALLBACK_SCORE

    except Exception as e:
        logger.error(f"[VIRAL] Scoring API call failed: {e}")
        return _FALLBACK_SCORE

