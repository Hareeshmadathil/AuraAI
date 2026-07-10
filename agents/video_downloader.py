
from config.settings import VIDEO_DIR
import yt_dlp





def download_video(url):
    """
    Downloads a video from the given URL.

    Returns:
        Path of the downloaded file.
    """

    
    

    options = {
        "outtmpl": str(VIDEO_DIR / "%(title)s.%(ext)s"),
        "format": "best",
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

    return filename