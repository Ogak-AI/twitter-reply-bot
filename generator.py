import logging
import re
import requests
import random

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


# Category-specific tone hints — strictly World Cup 2026 focused
_CATEGORY_HINTS = {
    "worldcup": "You are an excited football/soccer fan who is hyped for the FIFA World Cup 2026 in North America (USA, Canada, Mexico). Use football terms and slang naturally (e.g., 'absolute cinema', 'pitch', 'group of death', 'baller', 'it's coming home', 'W tournament', 'the beautiful game'). Reference World Cup 2026 venues, teams, groups, and matchups when relevant.",
}

# Default hint for any article — always stays on World Cup 2026 topic
_DEFAULT_HINT = _CATEGORY_HINTS["worldcup"]

# Dynamic angles to vary the writing style across posts
_POST_ANGLES = [
    "a casual hot take or personal opinion",
    "a witty, slightly humorous observation",
    "a curious, thoughtful question that invites conversation",
    "an enthusiastic, hype-filled reaction",
    "a grounded, constructive perspective",
    "a clever, lighthearted piece of banter"
]


def generate_tweet(article: dict, ai_config: dict) -> str:
    """
    Generates an engaging original Twitter/X post about a World Cup 2026 news article using Groq API.
    Uses category context and dynamic style angles to produce diverse, topic-appropriate posts.
    """
    api_key = ai_config.get("groq_api_key")
    model = ai_config.get("model", "llama3-70b-8192")

    headline = article.get("title", "").strip()
    category = article.get("category", "general")

    if not api_key:
        logger.warning("Groq API key (GROQ_API_KEY) is missing. Using fallback post.")
        return "World Cup 2026 is going to be something special."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Get category-specific personality and random post angle
    category_hint = _CATEGORY_HINTS.get(category, _DEFAULT_HINT)
    angle = random.choice(_POST_ANGLES)

    # Generate an organic, casual, human-like original post under 240 characters.
    # We use a system prompt and user instructions optimized to avoid AI detector detection.
    prompt = (
        f"You are a real, casual Twitter/X user posting about World Cup 2026 news.\n"
        f"Context: {category_hint}\n"
        f"Write an original, standalone tweet about this World Cup 2026 news headline:\n\n"
        f"\"{headline}\"\n\n"
        f"To bypass AI content detectors, strictly adhere to these rules:\n"
        f"1. Write in a highly casual, informal human tone. Use natural sentence structures.\n"
        f"2. Always write in grammatically complete sentences. Each post must begin with a capital letter and end with proper punctuation (like a period, question mark, or exclamation mark). Do not write sentence fragments, hanging phrases, or run-on sentences without punctuation.\n"
        f"3. Do not reuse the exact same words, cliches, or predictable phrasing templates across different posts. Vary your vocabulary and sentence structure dynamically so no two posts sound alike.\n"
        f"4. Adopt the following specific writing style/angle for this post: {angle}. This helps vary your writing style dynamically across posts so they do not all sound similar.\n"
        f"5. Do NOT use overly formal words, robotic transitions, exclamation mark overload, or bullet-point reasoning.\n"
        f"6. Avoid typical AI introductory phrases or summaries.\n"
        f"7. Do NOT include any @mentions or links in your post.\n"
        f"8. Do NOT use any emojis whatsoever. Plain text only.\n"
        f"9. Strictly keep the post under 220 characters and do NOT wrap it in quotes.\n"
        f"10. Output ONLY the raw post text."
    )

    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": f"You write like a real, casual person on Twitter/X, posting original thoughts about World Cup 2026 news. {category_hint} Never sound like a formal AI assistant."},
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
            timeout=10,
        )
        response.raise_for_status()
        post_content = response.json()["choices"][0]["message"]["content"].strip()

        # Clean any wrapping quotes
        if post_content.startswith('"') and post_content.endswith('"'):
            post_content = post_content[1:-1].strip()
        if post_content.startswith("'") and post_content.endswith("'"):
            post_content = post_content[1:-1].strip()

        post_content = strip_emojis(post_content).strip()
        if not post_content:
            post_content = "World Cup 2026 is shaping up to be absolutely massive."

        return post_content

    except Exception as e:
        logger.error(f"Error calling Groq API: {e}", exc_info=True)
        return "The World Cup 2026 hype is real, this tournament is going to be something else."
