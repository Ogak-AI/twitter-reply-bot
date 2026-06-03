"""
viral_scorer.py — AI-powered viral potential scorer for World Cup 2026 headlines.
Uses a fast Groq API call to rate headlines 1–10. Only high-scoring content gets posted.
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


def score_viral_potential(headline: str, ai_config: dict, timeout: int = 8) -> int:
    """
    Scores a headline for viral potential on Twitter/X using Groq API.

    Args:
        headline: The article headline to score.
        ai_config: AI configuration dict (must contain groq_api_key, model).
        timeout: API request timeout in seconds.

    Returns:
        Integer score 1–10. Returns _FALLBACK_SCORE on any failure.
    """
    api_key = ai_config.get("groq_api_key")
    model = ai_config.get("model", "llama-3.3-70b-versatile")

    if not api_key:
        logger.warning("[VIRAL] Groq API key missing — returning fallback score")
        return _FALLBACK_SCORE

    if not headline or not headline.strip():
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
