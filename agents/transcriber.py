import json
from pathlib import Path
from typing import Any

import whisper

from config.settings import TIMESTAMP_DIR, TRANSCRIPT_DIR


def transcribe_audio(
    audio_path: str | Path,
) -> tuple[Path, Path]:
    """
    Transcribe audio and save both plain text and timestamped JSON.

    Returns:
        Transcript text path and timestamp JSON path.
    """

    audio_path = Path(audio_path)

    if not audio_path.exists():
        raise FileNotFoundError(
            f"Audio file not found: {audio_path}"
        )

    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    TIMESTAMP_DIR.mkdir(parents=True, exist_ok=True)

    transcript_path = TRANSCRIPT_DIR / f"{audio_path.stem}.txt"
    timestamp_path = TIMESTAMP_DIR / f"{audio_path.stem}.json"

    print("\nLoading Whisper model (tiny)...")
    model = whisper.load_model("tiny")

    print("Transcribing audio...")

    result: dict[str, Any] = model.transcribe(
        str(audio_path),
        fp16=False,
    )

    transcript_text = str(result.get("text", "")).strip()

    if not transcript_text:
        raise RuntimeError(
            "Whisper completed, but no transcript text was produced."
        )

    transcript_path.write_text(
        transcript_text,
        encoding="utf-8",
    )

    timestamped_segments = []

    for segment in result.get("segments", []):
        timestamped_segments.append(
            {
                "id": segment.get("id"),
                "start": round(float(segment.get("start", 0)), 2),
                "end": round(float(segment.get("end", 0)), 2),
                "text": str(segment.get("text", "")).strip(),
            }
        )

    timestamp_data = {
        "source_audio": str(audio_path),
        "language": result.get("language"),
        "text": transcript_text,
        "segments": timestamped_segments,
    }

    timestamp_path.write_text(
        json.dumps(
            timestamp_data,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("Transcription completed.")
    print(f"Transcript saved to: {transcript_path}")
    print(f"Timestamps saved to: {timestamp_path}")

    return transcript_path, timestamp_path