from pathlib import Path
from typing import Any

from agents.analyzer import analyze_transcript
from agents.audio_extractor import extract_audio
from agents.content_generator import generate_content
from agents.transcriber import transcribe_audio
from agents.video_downloader import download_video


def process_video(
    url: str,
) -> tuple[
    Path,
    Path,
    Path,
    Path,
    dict[str, Any],
    Path,
    Path,
]:
    """
    Run the complete AuraAI content-processing pipeline.

    Returns:
        Video path, audio path, transcript path, timestamp JSON path,
        analysis dictionary, analysis JSON path, and content JSON path.
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
    transcript_path, timestamp_path = transcribe_audio(audio_path)

    print("\nTranscription completed.")
    print(f"Transcript saved to: {transcript_path}")
    print(f"Timestamps saved to: {timestamp_path}")

    print("\nStep 4: Analyzing transcript...")
    analysis, analysis_path = analyze_transcript(transcript_path)

    print("\nTranscript analysis completed.")
    print(f"Analysis saved to: {analysis_path}")

    print("\nStep 5: Generating AI content...")

    transcript_text = transcript_path.read_text(
        encoding="utf-8",
        errors="ignore",
    ).strip()

    if not transcript_text:
        raise ValueError("The transcript is empty.")

    content_path = generate_content(
        transcript=transcript_text,
        analysis=analysis,
        video_name=transcript_path.stem,
    )

    print("\nAI content generation completed.")
    print(f"Content saved to: {content_path}")

    return (
        video_path,
        audio_path,
        transcript_path,
        timestamp_path,
        analysis,
        analysis_path,
        content_path,
    )