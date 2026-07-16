"""Focused regression tests for the offline production connector."""
from pathlib import Path
import json
from fastapi.testclient import TestClient
import pytest
from core import ValidationError
from app.main import create_production_connector_demo_app
from production_connector.loader import MissionPackageLoader
from production_connector.segmentation import segment_script
from production_connector.service import ProductionConnectorService

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"outputs"/"mission-zero-revision"/"f7385664-ac50-4e16-83c1-339781135a0a"

def test_valid_loading_segmentation_and_hashes():
    package=MissionPackageLoader(ROOT).load(SOURCE); segments=segment_script(package)
    assert package.quality_score==89.28 and package.blocker_count==0
    assert [s.narration_text for s in segments]==package.sections
    assert all(len(s.content_hash)==64 for s in segments)
    assert any(s.avatar_visible for s in segments) and any(not s.avatar_visible for s in segments)
    assert all(s.estimated_duration_seconds < 120 for s in segments if s.avatar_visible)
    assert {x for s in segments for x in s.asset_requirement_ids} >= {"early-code","quality-breakdown","founder-review"}

def test_no_v1_fallback_and_safe_path(tmp_path: Path):
    with pytest.raises(ValidationError): MissionPackageLoader(tmp_path).load(tmp_path)
    with pytest.raises(ValidationError): MissionPackageLoader(ROOT).load(ROOT.parent)

def test_deterministic_full_export_and_subtitles(tmp_path: Path):
    service=ProductionConnectorService(MissionPackageLoader(ROOT).load(SOURCE)); out=tmp_path/"package"
    service.prepare(out)
    status=json.loads((out/"youtube-package/publishing-status.json").read_text())
    assert status=={"founder_publish_approval":False,"published":False,"uploaded":False}
    assert len(json.loads((out/"founder-capture/capture-manifest.json").read_text()))==12
    assert "AuraAI" in (out/"provider-packages/elevenlabs/pronunciation-dictionary.json").read_text()
    for block in (out/"editor-package/subtitle-track.srt").read_text().split("\n\n"):
        lines=block.splitlines()[2:]
        assert len(lines)<=2 and all(len(line)<=42 for line in lines)
    with pytest.raises(ValidationError): service.prepare(out)

def test_dashboard_is_safe_and_cli_route_exists():
    response=TestClient(create_production_connector_demo_app()).get("/production-connector")
    assert response.status_code==200 and "FOUNDER ACTION REQUIRED" in response.text
    package=MissionPackageLoader(ROOT).load(SOURCE)
    assert package.sections[0] not in response.text and "Publishing</dt><dd>false" in response.text
