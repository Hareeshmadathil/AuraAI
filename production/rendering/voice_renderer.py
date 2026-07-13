"""Offline Windows SAPI voice rendering with explicit silent fallback."""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path

from pydantic import Field

from core import AuraBaseModel, ValidationError
from production.models import VoiceoverPlan
from production.rendering.models import (
    RenderArtifactType,
    RenderCapability,
    RenderEngine,
    RenderStatus,
    RenderedArtifact,
)
from production.rendering.validation import completed_artifact


class VoiceRenderOutcome(AuraBaseModel):
    """Structured voice result that distinguishes speech from silence."""

    status: RenderStatus
    engine: RenderEngine
    artifact: RenderedArtifact | None = None
    command_summary: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    message: str


class OfflineVoiceRenderer:
    """Render local SAPI speech or an explicitly labelled silent WAV."""

    def __init__(
        self,
        *,
        output_root: Path,
        powershell_runner=subprocess.run,
    ) -> None:
        self.output_root = output_root.resolve()
        self._powershell_runner = powershell_runner

    def render(
        self,
        plan: VoiceoverPlan,
        output_path: Path,
        capability: RenderCapability,
        *,
        allow_silent_fallback: bool,
        maximum_duration_seconds: float,
        rate: int = 0,
        volume: int = 100,
    ) -> VoiceRenderOutcome:
        """Create one WAV inside the configured output root."""

        target = self._safe_path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not capability.available:
            if not allow_silent_fallback:
                return VoiceRenderOutcome(
                    status=RenderStatus.BLOCKED,
                    engine=RenderEngine.SILENT_FALLBACK,
                    warnings=["Local speech synthesis is unavailable."],
                    message="Voice rendering is blocked without explicit silent fallback.",
                )
            duration = min(maximum_duration_seconds, 60.0)
            self._write_silence(target, duration, plan.profile.pace_words_per_minute)
            artifact = self._wav_artifact(
                target,
                plan,
                warnings=["SILENT REVIEW PREVIEW: no narration was synthesized."],
            )
            return VoiceRenderOutcome(
                status=RenderStatus.REVIEW_REQUIRED,
                engine=RenderEngine.SILENT_FALLBACK,
                artifact=artifact,
                warnings=list(artifact.warnings),
                message="Explicit silent fallback WAV created for local review testing.",
            )

        text = self._abridged_text(plan, maximum_duration_seconds)
        text_path = target.with_suffix(".narration.txt")
        text_path.write_text(text, encoding="utf-8")
        powershell = capability.executable_path or "powershell"
        safe_text_path = str(text_path).replace("'", "''")
        safe_target = str(target).replace("'", "''")
        safe_rate = max(-10, min(10, rate))
        safe_volume = max(0, min(100, volume))
        script = (
            "Add-Type -AssemblyName System.Speech -ErrorAction Stop; "
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Rate={safe_rate}; $s.Volume={safe_volume}; "
            f"$t=[IO.File]::ReadAllText('{safe_text_path}',[Text.Encoding]::UTF8); "
            f"$s.SetOutputToWaveFile('{safe_target}'); $s.Speak($t); "
            "$s.Dispose()"
        )
        command = [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ]
        try:
            completed = self._powershell_runner(
                command,
                shell=False,
                capture_output=True,
                text=True,
                timeout=maximum_duration_seconds + 45,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            return VoiceRenderOutcome(
                status=RenderStatus.FAILED,
                engine=RenderEngine.WINDOWS_SAPI,
                command_summary=[Path(powershell).name, "-NoProfile", "[controlled SAPI script]"],
                message=f"Local SAPI execution failed: {error.__class__.__name__}.",
            )
        finally:
            if text_path.exists():
                text_path.unlink()
        summary = [Path(powershell).name, "-NoProfile", "[controlled SAPI script]"]
        if completed.returncode != 0 or not target.is_file():
            return VoiceRenderOutcome(
                status=RenderStatus.FAILED,
                engine=RenderEngine.WINDOWS_SAPI,
                command_summary=summary,
                message="Local SAPI did not create a usable WAV file.",
            )
        truncated = self._truncate_wav(target, maximum_duration_seconds)
        warnings = (
            ["Narration was bounded to the configured local review duration."]
            if truncated
            else []
        )
        artifact = self._wav_artifact(target, plan, warnings=warnings)
        return VoiceRenderOutcome(
            status=RenderStatus.REVIEW_REQUIRED,
            engine=RenderEngine.WINDOWS_SAPI,
            artifact=artifact,
            command_summary=summary,
            message="Real local Windows SAPI voiceover rendered for review.",
        )

    def _wav_artifact(
        self,
        path: Path,
        plan: VoiceoverPlan,
        *,
        warnings: list[str] | None = None,
    ) -> RenderedArtifact:
        try:
            with wave.open(str(path), "rb") as audio:
                duration = audio.getnframes() / audio.getframerate()
        except (wave.Error, OSError) as error:
            raise ValidationError("Rendered WAV is invalid.") from error
        if duration <= 0 or path.stat().st_size <= 44:
            raise ValidationError("Rendered WAV must be nonempty and have duration.")
        return completed_artifact(
            artifact_type=RenderArtifactType.VOICEOVER_AUDIO,
            path=path,
            mime_type="audio/wav",
            sample_data=plan.sample_data,
            source_references=[f"voiceover-plan:{plan.plan_id}"],
            warnings=warnings or [],
            duration_seconds=duration,
        )

    @staticmethod
    def _abridged_text(plan: VoiceoverPlan, maximum_duration_seconds: float) -> str:
        word_limit = max(
            20,
            int(plan.profile.pace_words_per_minute * maximum_duration_seconds / 60),
        )
        words = " ".join(segment.text for segment in plan.segments).split()
        return " ".join(words[:word_limit])

    @staticmethod
    def _write_silence(path: Path, duration: float, pace: int) -> None:
        sample_rate = 48_000
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(sample_rate)
            audio.writeframes(b"\x00\x00" * int(sample_rate * duration))

    @staticmethod
    def _truncate_wav(path: Path, maximum_duration_seconds: float) -> bool:
        """Bound a valid PCM WAV without invoking another external process."""

        with wave.open(str(path), "rb") as source:
            frame_rate = source.getframerate()
            maximum_frames = int(frame_rate * maximum_duration_seconds)
            if source.getnframes() <= maximum_frames:
                return False
            parameters = source.getparams()
            frames = source.readframes(maximum_frames)
        temporary = path.with_suffix(".bounded.wav")
        with wave.open(str(temporary), "wb") as output:
            output.setparams(parameters)
            output.writeframes(frames)
        temporary.replace(path)
        return True

    def _safe_path(self, path: Path) -> Path:
        resolved = path.resolve()
        try:
            resolved.relative_to(self.output_root)
        except ValueError as error:
            raise ValidationError("Voice output path escapes the configured root.") from error
        return resolved
