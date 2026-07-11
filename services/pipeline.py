from pathlib import Path

from agents.audio_extractor import extract_audio
from agents.transcriber import transcribe_audio
from agents.video_downloader import download_video


def process_video(url: str) -> tuple[Path, Path, Path]:
    """
    Run the AuraAI content-processing pipeline.

    Returns:
        Video path, audio path, and transcript path.
    """

    cleaned_url = url.strip()

    if not cleaned_url:
        raise ValueError("A video URL is required.")

    print("\nStep 1: Downloading video...")
    video_path = download_video(cleaned_url)

    print("\nVideo download completed.")
    print(f"Video saved to: {video_path}")

    print("\nStep 2: Extracting audio...")
    audio_path = extract_audio(video_path)

    print("\nAudio extraction completed.")
    print(f"Audio saved to: {audio_path}")

    print("\nStep 3: Transcribing audio...")
    transcript_path = transcribe_audio(audio_path)

    print("\nTranscript created.")
    print(f"Transcript saved to: {transcript_path}")

    return video_path, audio_path, transcript_path