import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from agents.llm import generate_json_with_gemini
from config.settings import CONTENT_DIR


class CreatorContent(BaseModel):
    youtube_title: str
    youtube_description: str
    hashtags: list[str]
    youtube_tags: list[str]
    shorts_titles: list[str]
    instagram_caption: str
    twitter_post: str
    linkedin_post: str


def generate_content(
    transcript: str,
    analysis: dict[str, Any],
    video_name: str,
) -> Path:
    """
    Generate creator-ready social media content using Gemini.
    """

    if not transcript.strip():
        raise ValueError("Transcript text is empty.")

    prompt = f"""
You are an expert content strategist, copywriter, and YouTube SEO
specialist.

Create creator-ready content using the transcript and analysis below.

Rules:
- create one engaging YouTube title
- keep the YouTube title under 100 characters
- create a useful YouTube description
- return between 5 and 12 hashtags
- every hashtag must begin with #
- return no more than 15 YouTube tags
- return exactly 5 Shorts title ideas
- keep the Twitter/X post concise
- do not invent facts absent from the transcript

Transcript:

{transcript}

Existing analysis:

{json.dumps(analysis, indent=2, ensure_ascii=False)}
"""

    content = generate_json_with_gemini(
        prompt,
        response_model=CreatorContent,
    )

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