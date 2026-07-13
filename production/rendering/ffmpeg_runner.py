"""Safe argument-list execution for local FFmpeg and FFprobe."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

from core import ValidationError, get_logger
from production.rendering.models import FFmpegCommandResult, MediaProbe


_SENSITIVE = re.compile(
    r"(?i)(api[_-]?key|token|secret|password)=([^\s]+)"
)
_FORBIDDEN_FILTER_ARGUMENTS = {
    "-filter_script",
    "-filter_complex_script",
    "-filter_script:v",
    "-filter_script:a",
}


class FFmpegRunner:
    """Run only controlled local media commands with ``shell=False``."""

    def __init__(
        self,
        *,
        ffmpeg_path: str,
        ffprobe_path: str,
        output_root: Path,
        timeout_seconds: float = 120,
        command_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self.ffmpeg_path = str(Path(ffmpeg_path).resolve())
        self.ffprobe_path = str(Path(ffprobe_path).resolve())
        self.output_root = output_root.resolve()
        self.timeout_seconds = timeout_seconds
        self._command_runner = command_runner
        self.logger = get_logger("production.rendering.ffmpeg_runner")

    def run(
        self,
        arguments: Sequence[str],
        *,
        output_path: Path | None = None,
        timeout_seconds: float | None = None,
    ) -> FFmpegCommandResult:
        """Execute FFmpeg from a validated list of arguments."""

        self._validate_arguments(arguments)
        if output_path is not None:
            self.require_output_path(output_path)
        command = [self.ffmpeg_path, *[str(argument) for argument in arguments]]
        summary = self._safe_summary(command)
        self.logger.info("Running local FFmpeg command: %s", " ".join(summary))
        try:
            completed = self._command_runner(
                command,
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds or self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return FFmpegCommandResult(
                success=False,
                return_code=-1,
                command_summary=summary,
                timed_out=True,
                error_message="Local FFmpeg command timed out.",
            )
        except OSError as error:
            return FFmpegCommandResult(
                success=False,
                return_code=-1,
                command_summary=summary,
                error_message=f"Local FFmpeg execution failed: {error.__class__.__name__}.",
            )
        return FFmpegCommandResult(
            success=completed.returncode == 0,
            return_code=completed.returncode,
            command_summary=summary,
            stdout=self._redact((completed.stdout or "")[-20_000:]),
            stderr=self._redact((completed.stderr or "")[-20_000:]),
            error_message=(
                None
                if completed.returncode == 0
                else "Local FFmpeg command returned a nonzero exit code."
            ),
        )

    def probe(self, path: Path) -> MediaProbe:
        """Probe a local output artifact and normalize its stream metadata."""

        safe_path = self.require_output_path(path)
        command = [
            self.ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,codec_name,width,height",
            "-of",
            "json",
            str(safe_path),
        ]
        try:
            completed = self._command_runner(
                command,
                shell=False,
                capture_output=True,
                text=True,
                timeout=min(self.timeout_seconds, 30),
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise ValidationError(
                "FFprobe execution failed.",
                details={"exception_type": error.__class__.__name__},
            ) from error
        if completed.returncode != 0:
            raise ValidationError(
                "FFprobe could not inspect the local artifact.",
                details={"stderr": self._redact((completed.stderr or "")[-1000:])},
            )
        try:
            data = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise ValidationError("FFprobe returned invalid JSON.") from error
        streams = data.get("streams", [])
        video = next(
            (stream for stream in streams if stream.get("codec_type") == "video"),
            None,
        )
        audio = next(
            (stream for stream in streams if stream.get("codec_type") == "audio"),
            None,
        )
        return MediaProbe(
            path=safe_path,
            duration_seconds=float(data.get("format", {}).get("duration") or 0),
            width=video.get("width") if video else None,
            height=video.get("height") if video else None,
            video_codec=video.get("codec_name") if video else None,
            audio_codec=audio.get("codec_name") if audio else None,
            has_video=video is not None,
            has_audio=audio is not None,
        )

    def require_output_path(self, path: Path) -> Path:
        """Resolve a path and reject traversal outside the injected root."""

        resolved = path.resolve()
        try:
            resolved.relative_to(self.output_root)
        except ValueError as error:
            raise ValidationError(
                "Media output path escapes the configured output root."
            ) from error
        return resolved

    @staticmethod
    def _validate_arguments(arguments: Sequence[str]) -> None:
        if isinstance(arguments, (str, bytes)):
            raise ValidationError("FFmpeg arguments must be a list, not a command string.")
        for argument in arguments:
            value = str(argument)
            if "\x00" in value or "\n" in value or "\r" in value:
                raise ValidationError("FFmpeg arguments contain forbidden control characters.")
            if value in _FORBIDDEN_FILTER_ARGUMENTS:
                raise ValidationError("External FFmpeg filter scripts are not allowed.")

    @classmethod
    def _safe_summary(cls, command: Sequence[str]) -> list[str]:
        summary: list[str] = []
        for index, argument in enumerate(command):
            value = Path(argument).name if index == 0 else str(argument)
            summary.append(cls._redact(value)[:500])
        return summary

    @staticmethod
    def _redact(value: str) -> str:
        return _SENSITIVE.sub(r"\1=[REDACTED]", value)
