"""
Central configuration for AuraAI Creator OS.

All application settings, filesystem paths, model choices, limits, and
runtime behaviour should be defined here or supplied through environment
variables.

Other AuraAI modules should import configuration from this file instead
of reading environment variables directly.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


# ==========================================================
# Environment loading
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=ENV_FILE)


# ==========================================================
# Application identity
# ==========================================================

APP_NAME = os.getenv("AURAAI_APP_NAME", "AuraAI Creator OS")
APP_VERSION = os.getenv("AURAAI_APP_VERSION", "2.0.0-dev")
APP_ENV = os.getenv("AURAAI_ENV", "development").strip().lower()
DEBUG = os.getenv("AURAAI_DEBUG", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


# ==========================================================
# AI provider configuration
# ==========================================================

DEFAULT_AI_PROVIDER = os.getenv(
    "AURAAI_DEFAULT_AI_PROVIDER",
    "gemini",
).strip().lower()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

GEMINI_MODEL = os.getenv(
    "AURAAI_GEMINI_MODEL",
    "gemini-flash-latest",
).strip()

AI_TEMPERATURE = float(
    os.getenv("AURAAI_AI_TEMPERATURE", "0.2")
)

AI_MAX_OUTPUT_TOKENS = int(
    os.getenv("AURAAI_AI_MAX_OUTPUT_TOKENS", "4096")
)


# ==========================================================
# Transcription configuration
# ==========================================================

WHISPER_MODEL = os.getenv(
    "AURAAI_WHISPER_MODEL",
    "tiny",
).strip().lower()

WHISPER_LANGUAGE = (
    os.getenv("AURAAI_WHISPER_LANGUAGE", "").strip() or None
)

WHISPER_USE_FP16 = os.getenv(
    "AURAAI_WHISPER_USE_FP16",
    "false",
).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


# ==========================================================
# Video download configuration
# ==========================================================

VIDEO_DOWNLOAD_FORMAT = os.getenv(
    "AURAAI_VIDEO_DOWNLOAD_FORMAT",
    (
        "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
        "bestvideo+bestaudio/best"
    ),
).strip()

VIDEO_DOWNLOAD_TIMEOUT_SECONDS = int(
    os.getenv("AURAAI_VIDEO_DOWNLOAD_TIMEOUT_SECONDS", "60")
)

VIDEO_DOWNLOAD_RETRIES = int(
    os.getenv("AURAAI_VIDEO_DOWNLOAD_RETRIES", "5")
)

MAX_VIDEO_DURATION_SECONDS = int(
    os.getenv("AURAAI_MAX_VIDEO_DURATION_SECONDS", "7200")
)


# ==========================================================
# Logging configuration
# ==========================================================

LOG_LEVEL = os.getenv(
    "AURAAI_LOG_LEVEL",
    "INFO",
).strip().upper()

LOG_TO_CONSOLE = os.getenv(
    "AURAAI_LOG_TO_CONSOLE",
    "true",
).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

LOG_TO_FILE = os.getenv(
    "AURAAI_LOG_TO_FILE",
    "true",
).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


# ==========================================================
# Core directories
# ==========================================================

CONFIG_DIR = PROJECT_ROOT / "config"
AGENTS_DIR = PROJECT_ROOT / "agents"
SERVICES_DIR = PROJECT_ROOT / "services"
APP_DIR = PROJECT_ROOT / "app"
DOCS_DIR = PROJECT_ROOT / "docs"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
TESTS_DIR = PROJECT_ROOT / "tests"
UTILS_DIR = PROJECT_ROOT / "utils"

DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
LOG_DIR = PROJECT_ROOT / "logs"


# ==========================================================
# Data directories
# ==========================================================

VIDEO_DIR = DATA_DIR / "videos"
AUDIO_DIR = DATA_DIR / "audio"
TRANSCRIPT_DIR = DATA_DIR / "transcripts"
TIMESTAMP_DIR = DATA_DIR / "timestamps"
DATABASE_DIR = DATA_DIR / "database"
CACHE_DIR = DATA_DIR / "cache"


# ==========================================================
# Output directories
# ==========================================================

ANALYSIS_DIR = OUTPUT_DIR / "analysis"
CONTENT_DIR = OUTPUT_DIR / "content"
CLIPS_DIR = OUTPUT_DIR / "clips"
THUMBNAILS_DIR = OUTPUT_DIR / "thumbnails"
RENDERS_DIR = OUTPUT_DIR / "renders"
REPORTS_DIR = OUTPUT_DIR / "reports"


# ==========================================================
# Database configuration
# ==========================================================

DATABASE_FILE = DATABASE_DIR / "auraai.db"
DATABASE_URL = os.getenv(
    "AURAAI_DATABASE_URL",
    f"sqlite:///{DATABASE_FILE.as_posix()}",
).strip()


# ==========================================================
# Runtime files
# ==========================================================

APPLICATION_LOG_FILE = LOG_DIR / "auraai.log"
ERROR_LOG_FILE = LOG_DIR / "errors.log"


# ==========================================================
# Directory management
# ==========================================================

REQUIRED_DIRECTORIES: tuple[Path, ...] = (
    APP_DIR,
    DOCS_DIR,
    PROMPTS_DIR,
    TESTS_DIR,
    UTILS_DIR,
    DATA_DIR,
    VIDEO_DIR,
    AUDIO_DIR,
    TRANSCRIPT_DIR,
    TIMESTAMP_DIR,
    DATABASE_DIR,
    CACHE_DIR,
    OUTPUT_DIR,
    ANALYSIS_DIR,
    CONTENT_DIR,
    CLIPS_DIR,
    THUMBNAILS_DIR,
    RENDERS_DIR,
    REPORTS_DIR,
    LOG_DIR,
)


def ensure_directories() -> None:
    """
    Create every directory required by AuraAI.

    This operation is safe to run repeatedly.
    """

    for directory in REQUIRED_DIRECTORIES:
        directory.mkdir(parents=True, exist_ok=True)


def validate_settings() -> list[str]:
    """
    Return configuration warnings without exposing secret values.

    Returns:
        A list of human-readable warning messages.
    """

    warnings: list[str] = []

    if DEFAULT_AI_PROVIDER == "gemini" and not GEMINI_API_KEY:
        warnings.append(
            "GEMINI_API_KEY is not configured in the .env file."
        )

    if AI_MAX_OUTPUT_TOKENS <= 0:
        warnings.append(
            "AURAAI_AI_MAX_OUTPUT_TOKENS must be greater than zero."
        )

    if not 0.0 <= AI_TEMPERATURE <= 2.0:
        warnings.append(
            "AURAAI_AI_TEMPERATURE must be between 0.0 and 2.0."
        )

    if VIDEO_DOWNLOAD_RETRIES < 0:
        warnings.append(
            "AURAAI_VIDEO_DOWNLOAD_RETRIES cannot be negative."
        )

    if MAX_VIDEO_DURATION_SECONDS <= 0:
        warnings.append(
            "AURAAI_MAX_VIDEO_DURATION_SECONDS must be greater than zero."
        )

    return warnings


ensure_directories()