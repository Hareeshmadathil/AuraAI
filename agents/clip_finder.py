import json
from pathlib import Path
from typing import Any


def _normalize(text: str) -> str:
    """Normalize text for fuzzy matching."""

    return (
        text.lower()
        .replace(".", "")
        .replace(",", "")
        .replace("!", "")
        .replace("?", "")
        .replace("'", "")
        .replace('"', "")
        .strip()
    )


def find_clip_candidates(
    timestamp_json: str | Path,
    analysis: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Match Gemini's clip candidates with Whisper timestamp segments.
    """

    timestamp_json = Path(timestamp_json)

    if not timestamp_json.exists():
        raise FileNotFoundError(timestamp_json)

    data = json.loads(
        timestamp_json.read_text(
            encoding="utf-8"
        )
    )

    segments = data["segments"]

    clips = []

    for candidate in analysis.get("clip_candidates", []):

        quote = candidate["quote"]
        reason = candidate["reason"]

        quote_norm = _normalize(quote)

        best_match = None
        best_score = 0

        for segment in segments:

            segment_text = segment["text"]
            segment_norm = _normalize(segment_text)

            score = 0

            for word in quote_norm.split():

                if word in segment_norm:
                    score += 1

            if score > best_score:
                best_score = score
                best_match = segment

        if best_match:

            clips.append(
                {
                    "quote": quote,
                    "reason": reason,
                    "start": best_match["start"],
                    "end": best_match["end"],
                    "duration": round(
                        best_match["end"] - best_match["start"],
                        2,
                    ),
                    "confidence": best_score,
                }
            )

    return clips