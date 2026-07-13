from pathlib import Path

import pytest

from production.rendering.models import RenderSettings


def test_render_settings_require_review(tmp_path: Path) -> None:
    settings = RenderSettings(output_root=tmp_path)
    assert settings.review_required is True
    assert settings.output_root == tmp_path.resolve()
    with pytest.raises(ValueError):
        RenderSettings(output_root=tmp_path, review_required=False)
