"""Safe local Windows System.Speech adapter."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

from core import ValidationError

from private_video_production.models import VoiceProfile
from private_video_production.voice.wav import TARGET_SAMPLE_RATE


class WindowsSapiAdapter:
    """List installed voices and synthesize WAV chunks without network calls."""

    def __init__(
        self,
        *,
        powershell_path: str = "powershell",
        command_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        timeout_seconds: float = 90,
    ) -> None:
        self._powershell = powershell_path
        self._runner = command_runner
        self._timeout = timeout_seconds

    def list_voices(self) -> list[VoiceProfile]:
        """Return safe metadata for enabled local voices."""

        script = (
            "Add-Type -AssemblyName System.Speech -ErrorAction Stop; "
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$v=@($s.GetInstalledVoices()|Where-Object {$_.Enabled}|ForEach-Object {"
            "[pscustomobject]@{name=$_.VoiceInfo.Name;culture=$_.VoiceInfo.Culture.Name;"
            "gender=$_.VoiceInfo.Gender.ToString()}});$s.Dispose();"
            "$v|ConvertTo-Json -Compress"
        )
        completed = self._run(script, timeout=20)
        if completed.returncode != 0:
            return []
        try:
            payload = json.loads(completed.stdout or "[]")
        except json.JSONDecodeError:
            return []
        rows = payload if isinstance(payload, list) else [payload]
        return [
            VoiceProfile(
                name=str(row["name"]),
                culture=str(row["culture"]),
                gender=str(row.get("gender") or "") or None,
            )
            for row in rows
            if isinstance(row, dict) and row.get("name") and row.get("culture")
        ]

    def synthesize_chunk(
        self,
        *,
        text: str,
        voice: VoiceProfile,
        output_path: Path,
    ) -> None:
        """Synthesize one PCM WAV using transient text beside the output."""

        output_path.parent.mkdir(parents=True, exist_ok=True)
        text_path = output_path.with_suffix(".input.txt")
        text_path.write_text(text, encoding="utf-8")
        escaped_input = str(text_path.resolve()).replace("'", "''")
        escaped_output = str(output_path.resolve()).replace("'", "''")
        escaped_voice = voice.name.replace("'", "''")
        script = (
            "Add-Type -AssemblyName System.Speech -ErrorAction Stop;"
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
            f"$s.SelectVoice('{escaped_voice}');$s.Rate={voice.rate};"
            f"$t=[IO.File]::ReadAllText('{escaped_input}',[Text.Encoding]::UTF8);"
            "$f=[System.Speech.AudioFormat.SpeechAudioFormatInfo]::new("
            f"{TARGET_SAMPLE_RATE},"
            "[System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,"
            "[System.Speech.AudioFormat.AudioChannel]::Mono);"
            f"$s.SetOutputToWaveFile('{escaped_output}',$f);"
            "$s.Speak($t);$s.Dispose()"
        )
        try:
            completed = self._run(script, timeout=self._timeout)
        finally:
            text_path.unlink(missing_ok=True)
        if completed.returncode != 0 or not output_path.is_file():
            raise ValidationError(
                "Local Windows voice synthesis failed.",
                error_code="LOCAL_VOICE_SYNTHESIS_FAILED",
            )

    def _run(
        self,
        script: str,
        *,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return self._runner(
                [
                    self._powershell,
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    script,
                ],
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise ValidationError(
                "Windows System.Speech is unavailable.",
                error_code="LOCAL_VOICE_UNAVAILABLE",
            ) from error
