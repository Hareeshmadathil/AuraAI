from pathlib import Path

from agents.audio_extractor import extract_audio
from agents.video_downloader import download_video
from config.settings import AUDIO_DIR, VIDEO_DIR


def process_video(url: str) -> tuple[Path, Path]:
    """
    Run the AuraAI processing pipeline.

    Steps:
        1. Download the video.
        2. Extract audio from the video.

    Args:
        url: Authorized video URL.

    Returns:
        A tuple containing:
        - downloaded video path
        - extracted audio path
    """

    cleaned_url = url.strip()

    if not cleaned_url:
        raise ValueError("A video URL is required.")

    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    print("\nStep 1: Downloading video...")
    video_path = download_video(cleaned_url)

    print("\nVideo download completed.")
    print(f"Video saved to: {video_path}")

    print("\nStep 2: Extracting audio...")
    audio_path = extract_audio(video_path)

    print("\nAudio extraction completed.")
    print(f"Audio saved to: {audio_path}")

    return video_path, audio_path