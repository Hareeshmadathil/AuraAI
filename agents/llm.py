import json
import os
from typing import Any, Type

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel


load_dotenv()


def _get_client() -> genai.Client:
    """Create an authenticated Gemini client."""

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY was not found. Add it to the .env file."
        )

    return genai.Client(api_key=api_key)


def generate_json_with_gemini(
    prompt: str,
    response_model: Type[BaseModel] | None = None,
) -> dict[str, Any]:
    """
    Send a prompt to Gemini and return a validated JSON dictionary.
    """

    if not prompt.strip():
        raise ValueError("Gemini prompt cannot be empty.")

    client = _get_client()

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.2,
        max_output_tokens=4096,
        response_schema=response_model,
    )

    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=prompt,
        config=config,
    )

    if not response.text:
        raise RuntimeError("Gemini returned an empty response.")

    try:
        if response_model is not None:
            validated = response_model.model_validate_json(response.text)
            return validated.model_dump()

        result = json.loads(response.text)

    except Exception as error:
        preview = response.text[:1000]

        raise RuntimeError(
            "Gemini returned invalid structured JSON.\n"
            f"Response preview:\n{preview}"
        ) from error

    if not isinstance(result, dict):
        raise RuntimeError(
            "Gemini returned JSON, but it was not an object."
        )

    return result


class ClipCandidate(BaseModel):
    quote: str
    reason: str


class TranscriptAnalysis(BaseModel):
    summary: str
    keywords: list[str]
    language: str
    sentiment: str
    viral_score: int
    clip_candidates: list[ClipCandidate]


def analyze_text_with_gemini(
    transcript: str,
) -> dict[str, Any]:
    """Analyze transcript text and return structured analysis."""

    if not transcript.strip():
        raise ValueError("Transcript text is empty.")

    prompt = f"""
You are an expert video transcript analyst.

Analyze the transcript below.

Rules:
- viral_score must be an integer from 0 to 100
- return no more than 8 keywords
- return no more than 5 clip candidates
- do not create or guess timestamps
- use only information present in the transcript

Transcript:

{transcript}
"""

    return generate_json_with_gemini(
        prompt,
        response_model=TranscriptAnalysis,
    )