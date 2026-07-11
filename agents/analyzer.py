from pathlib import Path


def analyze_transcript(transcript_path: str | Path) -> dict:
    """
    Placeholder AI analyzer.

    Later this will call OpenAI/Gemini.
    """

    transcript_path = Path(transcript_path)

    if not transcript_path.exists():
        raise FileNotFoundError(
            f"Transcript not found: {transcript_path}"
        )

    text = transcript_path.read_text(
        encoding="utf-8",
        errors="ignore"
    )

    word_count = len(text.split())

    analysis = {
        "transcript": transcript_path,
        "word_count": word_count,
        "character_count": len(text),
        "preview": text[:300]
    }

    print("Transcript analyzed.")

    return analysis