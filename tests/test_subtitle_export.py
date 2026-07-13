from pathlib import Path

from company_missions.local_render_pilot import create_review_ready_production_package
from production.rendering.models import RenderSettings
from production.rendering.subtitle_renderer import SubtitleFileExporter


def test_subtitle_export_writes_utf8_sidecars(tmp_path: Path) -> None:
    package = create_review_ready_production_package()
    artifacts = SubtitleFileExporter(tmp_path).export(
        package.subtitle_package, tmp_path / "subtitles", RenderSettings(output_root=tmp_path)
    )
    assert {artifact.path.suffix for artifact in artifacts} == {".srt", ".vtt"}
    assert all(artifact.path.read_text(encoding="utf-8") for artifact in artifacts)
