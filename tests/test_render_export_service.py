from pathlib import Path

import pytest

from core import ValidationError
from production.rendering.export_service import RenderExportService
from production.rendering.models import RenderSettings


def test_export_directory_refuses_unapproved_overwrite(tmp_path: Path) -> None:
    root = tmp_path / "package"
    root.mkdir()
    (root / "existing.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(ValidationError):
        RenderExportService._prepare_directories(root, RenderSettings(output_root=tmp_path))
