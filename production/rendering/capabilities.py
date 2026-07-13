"""Explicit, injectable detection of local rendering capabilities."""

from __future__ import annotations

import platform
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from production.rendering.models import RenderCapability


class RenderCapabilityDetector:
    """Detect local tools without installation, network, or import-time work."""

    def __init__(
        self,
        *,
        which: Callable[[str], str | None] = shutil.which,
        command_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        system_name: str | None = None,
    ) -> None:
        self._which = which
        self._command_runner = command_runner
        self._system_name = system_name or platform.system()

    def detect(self) -> list[RenderCapability]:
        """Return FFmpeg, FFprobe, and local Windows speech capabilities."""

        return [
            self._executable_capability("ffmpeg"),
            self._executable_capability("ffprobe"),
            self._sapi_capability(),
        ]

    def locate_executables(self) -> dict[str, str | None]:
        """Return local executable paths without running any commands."""

        return {
            "ffmpeg": self._which("ffmpeg"),
            "ffprobe": self._which("ffprobe"),
            "powershell": self._which("powershell"),
        }

    def _executable_capability(self, name: str) -> RenderCapability:
        executable = self._which(name)
        if executable is None:
            return RenderCapability(
                capability_name=name,
                available=False,
                message=f"{name} is not available on the local PATH.",
            )
        version = None
        try:
            completed = self._command_runner(
                [executable, "-version"],
                shell=False,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            first_line = (completed.stdout or completed.stderr).splitlines()[0]
            version = first_line[:500]
            available = completed.returncode == 0
        except (OSError, subprocess.SubprocessError) as error:
            return RenderCapability(
                capability_name=name,
                available=False,
                executable_path=str(Path(executable).resolve()),
                message=f"{name} version check failed: {error.__class__.__name__}.",
            )
        return RenderCapability(
            capability_name=name,
            available=available,
            executable_path=str(Path(executable).resolve()),
            version=version,
            message=f"{name} is available locally." if available else f"{name} returned an error.",
        )

    def _sapi_capability(self) -> RenderCapability:
        if self._system_name != "Windows":
            return RenderCapability(
                capability_name="windows_sapi",
                available=False,
                message="Windows System.Speech is only supported on Windows.",
            )
        powershell = self._which("powershell")
        if powershell is None:
            return RenderCapability(
                capability_name="windows_sapi",
                available=False,
                message="Windows PowerShell is unavailable for local SAPI synthesis.",
            )
        script = (
            "Add-Type -AssemblyName System.Speech -ErrorAction Stop; "
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$n=@($s.GetInstalledVoices()).Count; $s.Dispose(); "
            "if($n -gt 0){Write-Output $n; exit 0}else{exit 2}"
        )
        try:
            completed = self._command_runner(
                [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
                shell=False,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            return RenderCapability(
                capability_name="windows_sapi",
                available=False,
                executable_path=str(Path(powershell).resolve()),
                message=f"Local SAPI check failed: {error.__class__.__name__}.",
            )
        available = completed.returncode == 0
        count = completed.stdout.strip() if available else "0"
        return RenderCapability(
            capability_name="windows_sapi",
            available=available,
            executable_path=str(Path(powershell).resolve()),
            version=f"installed_voices={count}" if available else None,
            message=(
                f"Windows local speech is available with {count} installed voice(s)."
                if available
                else "Windows local speech has no usable installed voice."
            ),
        )
