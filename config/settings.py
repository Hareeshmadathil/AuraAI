from pathlib import Path


# ==========================================================
# Project Root
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ==========================================================
# Data Directories
# ==========================================================

DATA_DIR = PROJECT_ROOT / "data"

VIDEO_DIR = DATA_DIR / "videos"
AUDIO_DIR = DATA_DIR / "audio"
TRANSCRIPT_DIR = DATA_DIR / "transcripts"
TIMESTAMP_DIR = DATA_DIR / "timestamps"


# ==========================================================
# Output Directories
# ==========================================================

OUTPUT_DIR = PROJECT_ROOT / "outputs"

ANALYSIS_DIR = OUTPUT_DIR / "analysis"
CONTENT_DIR = OUTPUT_DIR / "content"


# ==========================================================
# Create Required Directories
# ==========================================================

VIDEO_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
TIMESTAMP_DIR.mkdir(parents=True, exist_ok=True)

ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
CONTENT_DIR.mkdir(parents=True, exist_ok=True)