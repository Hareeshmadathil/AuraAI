import json
from pathlib import Path
from typing import Any

from agents.llm import generate_json_with_gemini
from config.settings import CONTENT_DIR


def generate_content(
    transcript: str,
    analysis: dict[str, Any],
    video_name: str,
) -> Path:
    """
    Generate creator-ready social media content using Gemini.

    Returns:
        Path to the generated content JSON file.
    """

    if not transcript.strip():
        raise ValueError("Transcript text is empty.")

    prompt = f"""
You are an expert content strategist, copywriter, and YouTube SEO
specialist.

Create creator-ready content using the transcript and analysis below.

Return ONLY valid JSON with exactly this structure:

{{
    "youtube_title": "",
    "youtube_description": "",
    "hashtags": [],
    "youtube_tags": [],
    "shorts_titles": [],
    "instagram_caption": "",
    "twitter_post": "",
    "linkedin_post": ""
}}

Rules:
- create one engaging YouTube title
- keep the YouTube title under 100 characters
- create a useful YouTube description
- return between 5 and 12 hashtags
- every hashtag must begin with #
- return no more than 15 YouTube tags
- return exactly 5 Shorts title ideas
- keep the Twitter/X post concise
- do not invent facts that are absent from the transcript
- do not include markdown code fences
- return JSON only

Transcript:

{transcript}

Existing analysis:

{json.dumps(analysis, indent=2, ensure_ascii=False)}
"""

    generated_content = generate_json_with_gemini(prompt)

    required_fields = {
        "youtube_title": "",
        "youtube_description": "",
        "hashtags": [],
        "youtube_tags": [],
        "shorts_titles": [],
        "instagram_caption": "",
        "twitter_post": "",
        "linkedin_post": "",
    }

    # Ensure every expected field exists.
    content = {
        field: generated_content.get(field, default)
        for field, default in required_fields.items()
    }

    CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    content_path = CONTENT_DIR / f"{video_name}.json"

    content_path.write_text(
        json.dumps(
            content,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("AI creator content generated.")
    print(f"Content saved to: {content_path}")

    return content_path