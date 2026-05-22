import logging
import re
import requests

logger = logging.getLogger(__name__)

_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]",
    flags=re.UNICODE,
)

def strip_emojis(text: str) -> str:
    if not text:
        return text
    text = _EMOJI_PATTERN.sub("", text)
    text = re.sub(r"[\ufe00-\ufe0f]", "", text)
    return text


def generate_tweet(article: dict, ai_config: dict) -> str:
    """
    Generates an engaging Twitter/X reply to the article/tweet using Groq API.
    """
    api_key = ai_config.get("groq_api_key")
    model = ai_config.get("model", "llama3-70b-8192")

    tweet_text = article.get("title", "").strip()
    username = article.get("source", "user").strip()

    if not api_key:
        logger.warning("Groq API key (GROQ_API_KEY) is missing. Using fallback reply.")
        return "Wow, that's really interesting! Thanks for sharing."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Generate an organic, casual, human-like reply under 180 characters.
    # We use a system prompt and user instructions optimized to avoid AI detector detection.
    prompt = (
        f"You are a real, casual Twitter/X user reacting in the replies.\n"
        f"Write a short, natural reaction to this tweet posted by @{username}:\n\n"
        f"\"{tweet_text}\"\n\n"
        f"To bypass AI content detectors, strictly adhere to these rules:\n"
        f"1. Write in a highly casual, informal human tone. Use natural sentence structures.\n"
        f"2. Incorporate standard internet abbreviations or slight colloquialisms where natural (e.g., 'tbh', 'imo', 'fr', 'lowkey', 'crazy how').\n"
        f"3. Do NOT use overly formal words, robotic transitions, exclamation mark overload, or bullet-point reasoning.\n"
        f"4. Avoid typical AI introductory phrases or summaries.\n"
        f"5. Do NOT include @{username} or any link in your response.\n"
        f"6. Do NOT use any emojis whatsoever. Plain text only.\n"
        f"7. Strictly keep the response under 170 characters and do NOT wrap it in quotes.\n"
        f"8. Output ONLY the raw reply text."
    )

    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You write like a real, casual person on Twitter/X, using informal language and internet slang. Never sound like a formal AI assistant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.85,
        "max_tokens": 100,
    }

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=15,
        )
        response.raise_for_status()
        reply_content = response.json()["choices"][0]["message"]["content"].strip()

        # Clean any wrapping quotes
        if reply_content.startswith('"') and reply_content.endswith('"'):
            reply_content = reply_content[1:-1].strip()
        if reply_content.startswith("'") and reply_content.endswith("'"):
            reply_content = reply_content[1:-1].strip()

        reply_content = strip_emojis(reply_content).strip()
        if not reply_content:
            reply_content = "Interesting point, thanks for sharing."

        return reply_content

    except Exception as e:
        logger.error(f"Error calling Groq API: {e}", exc_info=True)
        return "Insightful update! Appreciate you sharing this."
