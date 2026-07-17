"""AuraAI local application interfaces without application side effects."""

from __future__ import annotations

from typing import Any


def create_app(*args: Any, **kwargs: Any):
    """Lazily create the dashboard app and avoid package import cycles."""

    from app.main import create_app as application_factory

    return application_factory(*args, **kwargs)


__all__ = ["create_app"]
