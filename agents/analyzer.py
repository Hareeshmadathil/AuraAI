import json
from pathlib import Path
from typing import Any

from agents.llm import analyze_text_with_gemini
from config.settings import ANALYSIS_DIR


def analyze_transcript(
    transcript_path: str | Path,
) -> tuple[dict[str, Any], Path]:
    """
    Analyze a transcript with Gemini and save the result as JSON.
    """

    transcript_path = Path(transcript_path)

    if not transcript_path.exists():
        raise FileNotFoundError(
            f"Transcript not found: {transcript_path}"
        )

    text = transcript_path.read_text(
        encoding="utf-8",
        errors="ignore",
    ).strip()

    if not text:
        raise ValueError("The transcript is empty.")

    print("Sending transcript to Gemini...")

    ai_analysis = analyze_text_with_gemini(text)

    analysis = {
        "source_transcript": str(transcript_path),
        "word_count": len(text.split()),
        "character_count": len(text),
        "preview": text[:300],
        "summary": ai_analysis.get("summary", ""),
        "keywords": ai_analysis.get("keywords", []),
        "language": ai_analysis.get("language", ""),
        "sentiment": ai_analysis.get("sentiment", ""),
        "viral_score": ai_analysis.get("viral_score", 0),
        "clip_candidates": ai_analysis.get("clip_candidates", []),
    }

    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    analysis_path = ANALYSIS_DIR / f"{transcript_path.stem}.json"

    analysis_path.write_text(
        json.dumps(
            analysis,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("Transcript analyzed.")
    print(f"Analysis saved to: {analysis_path}")

    return analysis, analysis_path