from pathlib import Path
import subprocess

from config.settings import AUDIO_DIR


def extract_audio(video_path: str | Path) -> Path:
    """
    Extract audio from a video and save it as an MP3 file.

    Args:
        video_path: Location of the input video file.

    Returns:
        Path to the created MP3 file.
    """

    input_video = Path(video_path)

    if not input_video.exists():
        raise FileNotFoundError(
            f"Video file was not found: {input_video}"
        )

    audio_path = AUDIO_DIR / f"{input_video.stem}.mp3"

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_video),
        "-vn",
        "-acodec",
        "libmp3lame",
        "-b:a",
        "128k",
        str(audio_path),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg failed to extract the audio:\n{result.stderr}"
        )

    if not audio_path.exists():
        raise RuntimeError(
            "FFmpeg finished, but the audio file was not created."
        )

    return audio_path