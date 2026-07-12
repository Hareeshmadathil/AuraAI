from pathlib import Path
import subprocess
from typing import Any

from config.settings import CLIPS_DIR


def create_clips(
    video_path: str | Path,
    clip_candidates: list[dict[str, Any]],
) -> list[Path]:
    """
    Create MP4 clips from timestamped clip candidates.

    Returns:
        List of created clip paths.
    """

    video_path = Path(video_path)

    if not video_path.exists():
        raise FileNotFoundError(
            f"Video not found: {video_path}"
        )

    CLIPS_DIR.mkdir(parents=True, exist_ok=True)

    created_clips: list[Path] = []

    for index, clip in enumerate(clip_candidates, start=1):

        start = float(clip["start"])
        duration = float(clip["duration"])

        output_file = (
            CLIPS_DIR /
            f"clip_{index:02d}.mp4"
        )

        command = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start),
            "-i",
            str(video_path),
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-preset",
            "fast",
            "-crf",
            "23",
            str(output_file),
        ]

        print(
            f"Creating clip {index}..."
        )

        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        created_clips.append(output_file)

        print(
            f"Saved: {output_file}"
        )

    return created_clips