import json
import os
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv()


def _get_client() -> genai.Client:
    """Create and return an authenticated Gemini client."""

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY was not found. Add it to the .env file."
        )

    return genai.Client(api_key=api_key)


def _parse_json_response(response_text: str) -> dict[str, Any]:
    """
    Convert Gemini's response into a Python dictionary.

    Handles JSON wrapped in Markdown fences or followed by extra text.
    """

    text = response_text.strip()

    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    text = text.strip()

    try:
        result = json.loads(text)

    except json.JSONDecodeError:
        # Try reading the first valid JSON object if Gemini added extra text.
        object_start = text.find("{")

        if object_start == -1:
            raise RuntimeError(
                "Gemini response did not contain a JSON object."
            )

        decoder = json.JSONDecoder()

        try:
            result, _ = decoder.raw_decode(text[object_start:])
        except json.JSONDecodeError as error:
            preview = text[:500]

            raise RuntimeError(
                "Gemini returned invalid JSON.\n"
                f"Response preview:\n{preview}"
            ) from error

    if not isinstance(result, dict):
        raise RuntimeError(
            "Gemini returned JSON, but it was not a JSON object."
        )

    return result


def generate_json_with_gemini(prompt: str) -> dict[str, Any]:
    """
    Send a custom prompt to Gemini and return its JSON response.
    """

    if not prompt.strip():
        raise ValueError("Gemini prompt cannot be empty.")

    client = _get_client()

    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )

    if not response.text:
        raise RuntimeError("Gemini returned an empty response.")

    return _parse_json_response(response.text)


def analyze_text_with_gemini(
    transcript: str,
) -> dict[str, Any]:
    """
    Analyze transcript text and return structured analysis.
    """

    if not transcript.strip():
        raise ValueError("Transcript text is empty.")

    prompt = f"""
You are an expert video transcript analyst.

Analyze the transcript below and return only valid JSON with exactly
these fields:

{{
    "summary": "",
    "keywords": [],
    "language": "",
    "sentiment": "",
    "viral_score": 0,
    "clip_candidates": [
        {{
            "quote": "",
            "reason": ""
        }}
    ]
}}

Rules:
- viral_score must be an integer from 0 to 100
- return no more than 8 keywords
- return no more than 5 clip candidates
- do not create or guess timestamps
- use only information present in the transcript
- do not use Markdown code fences
- return JSON only

Transcript:

{transcript}
"""

    return generate_json_with_gemini(prompt)