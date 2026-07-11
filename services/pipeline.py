from pathlib import Path
from typing import Any

from agents.analyzer import analyze_transcript
from agents.audio_extractor import extract_audio
from agents.transcriber import transcribe_audio
from agents.video_downloader import download_video


def process_video(url: str) -> tuple[Path, Path, Path, dict[str, Any]]:
    """
    Run the AuraAI content-processing pipeline.

    Returns:
        Video path, audio path, transcript path, and analysis data.
    """

    cleaned_url = url.strip()

    if not cleaned_url:
        raise ValueError("A video URL is required.")

    print("\nStep 1: Downloading video...")
    video_path = Path(download_video(cleaned_url))

    print("\nVideo download completed.")
    print(f"Video saved to: {video_path}")

    print("\nStep 2: Extracting audio...")
    audio_path = Path(extract_audio(video_path))

    print("\nAudio extraction completed.")
    print(f"Audio saved to: {audio_path}")

    print("\nStep 3: Transcribing audio...")
    transcript_path = Path(transcribe_audio(audio_path))

    print("\nTranscript created.")
    print(f"Transcript saved to: {transcript_path}")

    print("\nStep 4: Analyzing transcript...")
    analysis = analyze_transcript(transcript_path)

    print("\nTranscript analysis completed.")

    return (
        video_path,
        audio_path,
        transcript_path,
        analysis,
    )