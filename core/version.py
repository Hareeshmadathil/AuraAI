"""
AuraAI Creator OS
Version Information

This module is the single source of truth for the application's
version number.
"""

from __future__ import annotations

VERSION_MAJOR = 2
VERSION_MINOR = 0
VERSION_PATCH = 0
VERSION_STAGE = "dev"


def get_version() -> str:
    """
    Return the current AuraAI version.
    """

    version = f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}"

    if VERSION_STAGE:
        return f"{version}-{VERSION_STAGE}"

    return version


__version__ = get_version()