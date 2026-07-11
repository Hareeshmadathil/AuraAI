from pathlib import Path

import whisper

from config.settings import TRANSCRIPT_DIR


def transcribe_audio(audio_path: str | Path) -> Path:
    """
    Transcribes an audio file using OpenAI Whisper.

    Args:
        audio_path: Path to the MP3 file.

    Returns:
        Path to the generated transcript (.txt).
    """

    audio_path = Path(audio_path)

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)

    transcript_path = TRANSCRIPT_DIR / f"{audio_path.stem}.txt"

    print("\nLoading Whisper model (tiny)...")

    model = whisper.load_model("tiny")

    print("Transcribing audio...")

    result = model.transcribe(str(audio_path))

    transcript = result["text"]

    transcript_path.write_text(
        transcript,
        encoding="utf-8"
    )

    print("Transcription completed.")

    return transcript_path