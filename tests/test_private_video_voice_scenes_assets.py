"""Local voice, scene planning, asset, and placeholder tests."""

import wave
from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from private_video_production.assets import AssetRegistry, AssetValidator, PlaceholderFactory
from private_video_production.loader import MissionZeroPackageLoader
from private_video_production.models import AssetRecord, AssetType, VoiceProfile
from private_video_production.scenes import MissionZeroScenePlanner
from private_video_production.voice import VoiceSynthesisService


PACKAGE = Path("outputs/mission-zero-revision/f7385664-ac50-4e16-83c1-339781135a0a")


class FakeVoiceAdapter:
    def list_voices(self):
        return [VoiceProfile(name="Local Test Voice", culture="en-US", gender="Neutral")]

    def synthesize_chunk(self, *, text, voice, output_path):
        with wave.open(str(output_path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16_000)
            audio.writeframes(b"\x00\x00" * 16_000)


def test_local_voice_listing_and_chunked_audition(tmp_path: Path) -> None:
    service = VoiceSynthesisService(FakeVoiceAdapter(), tmp_path)
    voice = service.list_voices()[0]
    result = service.create_audition(
        mission_id=MissionZeroPackageLoader().load(PACKAGE, tmp_path).mission_id,
        voice=voice,
        opening_text="AuraAI demonstrates a founder-controlled Mission Zero workflow. " * 10,
    )

    assert result.success is True
    assert result.chunks_created == 1
    assert result.duration_seconds == 1
    assert (tmp_path / "voice/voice-audition.wav").is_file()
    assert not list(tmp_path.rglob("*.input.txt"))


def test_voice_rejects_unavailable_and_cloned_profiles(tmp_path: Path) -> None:
    service = VoiceSynthesisService(FakeVoiceAdapter(), tmp_path)
    unavailable = VoiceProfile(name="Missing", culture="en-US")
    value = MissionZeroPackageLoader().load(PACKAGE, tmp_path)
    result = service.create_audition(
        mission_id=value.mission_id,
        voice=unavailable,
        opening_text=value.hook,
    )

    assert result.success is False
    assert result.available is False
    with pytest.raises(PydanticValidationError):
        VoiceProfile(name="Celebrity Clone", culture="en-US", cloned=True)


def test_scene_plan_covers_full_script_and_marks_missing_evidence(tmp_path: Path) -> None:
    value = MissionZeroPackageLoader().load(PACKAGE, tmp_path)
    scenes, requirements = MissionZeroScenePlanner().plan(value)

    assert scenes[0].expected_start_seconds == 0
    assert scenes[-1].expected_end_seconds == pytest.approx(510)
    assert all(3 <= scene.expected_end_seconds - scene.expected_start_seconds <= 8 for scene in scenes)
    assert all(scene.fallback_visual for scene in scenes)
    assert requirements
    assert any(item.asset_id == "quality-breakdown" for item in requirements)
    assert all(
        scene.visual.placeholder_watermark == "INTERNAL DRAFT — PLACEHOLDER"
        for scene in scenes
        if scene.founder_capture_required
    )


def test_asset_validation_hashes_safe_founder_file(tmp_path: Path) -> None:
    value = MissionZeroPackageLoader().load(PACKAGE, tmp_path)
    _, requirements = MissionZeroScenePlanner().plan(value)
    requirement = requirements[0]
    target = tmp_path / requirement.target_relative_path
    target.parent.mkdir(parents=True)
    target.write_bytes(b"safe-founder-asset")
    record = AssetRecord(
        asset_id=requirement.asset_id,
        asset_type=requirement.asset_type,
        relative_path=requirement.target_relative_path,
        supplied=True,
    )
    validation = AssetValidator().validate(tmp_path, [requirement], [record])

    assert validation.valid is True
    assert validation.supplied_asset_ids == [requirement.asset_id]


def test_asset_registry_duplicates_and_placeholder_label(tmp_path: Path) -> None:
    record = AssetRecord(
        asset_id="asset-one",
        asset_type=AssetType.IMAGE,
        relative_path="screenshots/asset-one.png",
        supplied=False,
        placeholder=True,
    )
    registry = AssetRegistry()
    registry.register(record)
    with pytest.raises(Exception, match="Duplicate"):
        registry.register(record)
    value = MissionZeroPackageLoader().load(PACKAGE, tmp_path)
    _, requirements = MissionZeroScenePlanner().plan(value)
    placeholder = PlaceholderFactory(tmp_path).create(requirements[0])
    assert "INTERNAL DRAFT — PLACEHOLDER" in placeholder.read_text(encoding="utf-8")
