from pathlib import Path
import yt_dlp

# Folder where downloaded videos will be stored
DOWNLOAD_FOLDER = Path("data/videos")


def download_video(url):
    """
    Downloads a video from the given URL.

    Returns:
        Path of the downloaded file.
    """

    # Create folder if it doesn't exist
    DOWNLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

    options = {
        "outtmpl": str(DOWNLOAD_FOLDER / "%(title)s.%(ext)s"),
        "format": "best",
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

    return filename