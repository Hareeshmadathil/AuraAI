import subprocess

from production.rendering.capabilities import RenderCapabilityDetector


def test_capability_detection_is_injected_and_truthful() -> None:
    def run(command, **kwargs):
        output = "2\n" if "powershell" in command[0] else "tool version 1\n"
        return subprocess.CompletedProcess(command, 0, output, "")

    detector = RenderCapabilityDetector(
        which=lambda name: f"C:/tools/{name}.exe",
        command_runner=run,
        system_name="Windows",
    )
    values = {item.capability_name: item for item in detector.detect()}
    assert all(item.available for item in values.values())
    assert values["windows_sapi"].version == "installed_voices=2"
    assert detector.locate_executables()["ffmpeg"] == "C:/tools/ffmpeg.exe"
