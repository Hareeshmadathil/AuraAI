"""Founder-controlled composition over existing Mission Zero production artifacts."""

from __future__ import annotations

import json
import hashlib
import wave
from pathlib import Path

from core import DependencyUnavailableError, ValidationError
from mission_engine import (
    ArtifactRegistry,
    InMemoryMissionRepository,
    Mission,
    MissionManager,
)
from production.rendering.models import RenderCapability
from runtime_engine import RuntimeEventBus
from runtime_engine.models import RuntimeEventType

from private_video_production.approvals import PrivateVideoApprovalService
from private_video_production.assets.validator import AssetValidator
from private_video_production.exporter import PrivateVideoProductionExporter
from private_video_production.loader import MissionZeroPackageLoader
from private_video_production.models import (
    AssetRecord,
    NarrationSegment,
    PrivateVideoApproval,
    PrivateVideoProductionResult,
    PrivateVideoReview,
    PrivateVideoStatus,
    RenderSpecification,
    ReviewDecision,
    VoiceProfile,
    VoiceSynthesisRequest,
    VoiceSynthesisResult,
)
from private_video_production.render import PrivateRenderService, build_render_manifest
from private_video_production.scenes import MissionZeroScenePlanner, PrivateSceneRenderer
from private_video_production.subtitles import PrivateSubtitleBuilder
from private_video_production.timeline import PrivateTimelineBuilder, TimelineValidator
from private_video_production.voice.models import PRONUNCIATION_OVERRIDES
from private_video_production.voice.service import VoiceSynthesisService


class PrivateVideoProductionPipeline:
    """Prepare, audition, synthesize, and founder-gated render Mission Zero."""

    def __init__(
        self,
        *,
        voice_service: VoiceSynthesisService,
        capabilities: tuple[RenderCapability, ...] = (),
        ffmpeg_runner=None,
        event_bus: RuntimeEventBus | None = None,
        loader: MissionZeroPackageLoader | None = None,
    ) -> None:
        self.voice_service = voice_service
        self.capabilities = capabilities
        self.ffmpeg_runner = ffmpeg_runner
        self.event_bus = event_bus or RuntimeEventBus()
        self.loader = loader or MissionZeroPackageLoader()
        self.approvals = PrivateVideoApprovalService()

    def prepare(
        self,
        mission_package: Path,
        output_root: Path,
        *,
        asset_records: list[AssetRecord] | None = None,
        export: bool = True,
    ) -> tuple[PrivateVideoProductionResult, Path | None]:
        """Validate the package and export capture/timeline plans without approval."""

        production_input = self.loader.load(mission_package, output_root)
        self._emit(RuntimeEventType.PRIVATE_VIDEO_PRODUCTION_STARTED, "Private production planning started.", production_input)
        self._emit(RuntimeEventType.PRODUCTION_PACKAGE_VALIDATED, "Approved Mission Zero package validated.", production_input)
        scenes, requirements = MissionZeroScenePlanner().plan(production_input)
        self._emit(RuntimeEventType.SCENE_PLAN_CREATED, f"Scene plan created with {len(scenes)} scenes.", production_input)
        self._emit(RuntimeEventType.ASSET_REQUIREMENTS_CREATED, f"Created {len(requirements)} founder asset requirements.", production_input)
        records = asset_records if asset_records is not None else self._discover_assets(output_root, requirements)
        validation = AssetValidator().validate(output_root, requirements, records)
        self._emit(RuntimeEventType.ASSET_VALIDATION_COMPLETED, "Founder asset validation completed.", production_input)
        duration = production_input.estimated_duration_seconds
        subtitles = PrivateSubtitleBuilder().build(production_input.source_subtitles, duration)
        self._emit(RuntimeEventType.SUBTITLE_TRACK_CREATED, f"Created {len(subtitles)} subtitle cues.", production_input)
        tracks, transitions, markers = PrivateTimelineBuilder().build(scenes, subtitles, None)
        TimelineValidator().validate(tracks, subtitles, duration)
        self._emit(RuntimeEventType.TIMELINE_CREATED, "Deterministic private timeline created.", production_input)
        specification = RenderSpecification()
        manifest = build_render_manifest(
            mission_id=production_input.mission_id,
            specification=specification,
            scenes=scenes,
            voice_result=None,
            missing_asset_ids=validation.missing_asset_ids,
        )
        result = PrivateVideoProductionResult(
            production_input=production_input,
            scenes=scenes,
            asset_requirements=requirements,
            asset_validation=validation,
            subtitles=subtitles,
            timeline_tracks=tracks,
            transitions=transitions,
            markers=markers,
            render_manifest=manifest,
            review=PrivateVideoReview(
                mission_id=production_input.mission_id,
                render_manifest_id=manifest.manifest_id,
                decision=ReviewDecision.PENDING,
                placeholder_count=manifest.placeholder_count,
                publishing_approved=False,
            ),
            status=PrivateVideoStatus.BLOCKED,
            runtime_events=[event.event_type.value for event in self.event_bus.list_events()],
        )
        export_path = PrivateVideoProductionExporter(output_root).export(result) if export else None
        return result, export_path

    def record_approval(
        self,
        result: PrivateVideoProductionResult,
        *,
        content_approved: bool,
        private_render_approved: bool,
        founder_confirmed: bool,
        founder_notes: str = "",
    ) -> PrivateVideoProductionResult:
        approval = self.approvals.record(
            result.production_input,
            content_approved=content_approved,
            private_render_approved=private_render_approved,
            founder_confirmed=founder_confirmed,
            founder_notes=founder_notes,
        )
        manager = self._mission_manager(result.production_input.mission_package)
        self.approvals.register_artifact(manager, approval)
        if content_approved:
            self._emit(RuntimeEventType.CONTENT_APPROVAL_RECORDED, "Content approval recorded.", result.production_input)
        if private_render_approved:
            self._emit(RuntimeEventType.PRIVATE_RENDER_APPROVAL_RECORDED, "Private render approval recorded.", result.production_input)
        return result.model_copy(update={
            "approval": approval,
            "runtime_events": [event.event_type.value for event in self.event_bus.list_events()],
        })

    def audition(
        self,
        result: PrivateVideoProductionResult,
        voice_name: str,
    ):
        self._emit(RuntimeEventType.VOICE_AUDITION_STARTED, "Local voice audition started.", result.production_input)
        voice = self._select_voice(voice_name)
        opening = f"{result.production_input.hook} {result.production_input.sections[0]}"
        voice_result = self.voice_service.create_audition(
            mission_id=result.production_input.mission_id,
            voice=voice,
            opening_text=opening,
        )
        self._emit(RuntimeEventType.VOICE_AUDITION_COMPLETED, "Local voice audition completed.", result.production_input)
        return voice_result

    def generate_narration(
        self,
        result: PrivateVideoProductionResult,
        voice_name: str,
    ) -> PrivateVideoProductionResult:
        self.approvals.require_content(result.approval, result.production_input)
        voice = self._select_voice(voice_name)
        self._emit(RuntimeEventType.NARRATION_SYNTHESIS_STARTED, "Local narration synthesis started.", result.production_input)
        segments = self._narration_segments(result)
        request = VoiceSynthesisRequest(
            mission_id=result.production_input.mission_id,
            voice=voice,
            segments=segments,
            output_relative_path=Path("voice/narration.wav"),
            pronunciation_overrides=PRONUNCIATION_OVERRIDES,
        )
        voice_result = self.voice_service.synthesize(request)
        selection_path = result.production_input.output_root / "voice/voice-selection.json"
        selection_path.parent.mkdir(parents=True, exist_ok=True)
        selection_path.write_text(
            json.dumps(
                {"voice_name": voice.name, "culture": voice.culture, "provider": voice.provider},
                indent=2,
            ),
            encoding="utf-8",
        )
        self._emit(RuntimeEventType.NARRATION_SYNTHESIS_COMPLETED, "Local narration synthesis completed.", result.production_input)
        subtitles = PrivateSubtitleBuilder().build(
            result.production_input.source_subtitles,
            voice_result.duration_seconds or result.production_input.estimated_duration_seconds,
        )
        scenes = self._retime_scenes(result.scenes, voice_result.duration_seconds or result.production_input.estimated_duration_seconds)
        tracks, transitions, markers = PrivateTimelineBuilder().build(scenes, subtitles, voice_result)
        TimelineValidator().validate(tracks, subtitles, voice_result.duration_seconds or 0)
        manifest = build_render_manifest(
            mission_id=result.production_input.mission_id,
            specification=result.render_manifest.specification if result.render_manifest else RenderSpecification(),
            scenes=scenes,
            voice_result=voice_result,
            missing_asset_ids=result.asset_validation.missing_asset_ids if result.asset_validation else [],
        )
        return result.model_copy(update={
            "selected_voice": voice,
            "voice_result": voice_result,
            "scenes": scenes,
            "subtitles": subtitles,
            "timeline_tracks": tracks,
            "transitions": transitions,
            "markers": markers,
            "render_manifest": manifest,
            "runtime_events": [event.event_type.value for event in self.event_bus.list_events()],
        })

    def recover_narration(
        self,
        result: PrivateVideoProductionResult,
    ) -> PrivateVideoProductionResult:
        """Recover previously generated local narration without synthesizing again."""

        root = result.production_input.output_root
        audio_path = root / "voice/narration.wav"
        selection_path = root / "voice/voice-selection.json"
        if not audio_path.is_file() or not selection_path.is_file():
            raise ValidationError("Generate and select local narration before rendering.")
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
        voice = self._select_voice(str(selection.get("voice_name", "")))
        with wave.open(str(audio_path), "rb") as audio:
            duration = audio.getnframes() / audio.getframerate()
            sample_rate = audio.getframerate()
            channels = audio.getnchannels()
        voice_result = VoiceSynthesisResult(
            request_id=result.render_manifest.manifest_id if result.render_manifest else result.production_input.mission_id,
            success=True,
            available=True,
            voice_name=voice.name,
            output_relative_path=Path("voice/narration.wav"),
            duration_seconds=duration,
            sample_rate=sample_rate,
            channels=channels,
            content_hash=hashlib.sha256(audio_path.read_bytes()).hexdigest(),
            chunks_created=0,
            message="Existing local narration recovered for founder-approved rendering.",
        )
        subtitles = PrivateSubtitleBuilder().build(result.production_input.source_subtitles, duration)
        scenes = self._retime_scenes(result.scenes, duration)
        tracks, transitions, markers = PrivateTimelineBuilder().build(scenes, subtitles, voice_result)
        TimelineValidator().validate(tracks, subtitles, duration)
        manifest = build_render_manifest(
            mission_id=result.production_input.mission_id,
            specification=result.render_manifest.specification if result.render_manifest else RenderSpecification(),
            scenes=scenes,
            voice_result=voice_result,
            missing_asset_ids=result.asset_validation.missing_asset_ids if result.asset_validation else [],
        )
        return result.model_copy(update={
            "selected_voice": voice,
            "voice_result": voice_result,
            "scenes": scenes,
            "subtitles": subtitles,
            "timeline_tracks": tracks,
            "transitions": transitions,
            "markers": markers,
            "render_manifest": manifest,
        })

    def render(
        self,
        result: PrivateVideoProductionResult,
        *,
        preview: bool,
    ) -> PrivateVideoProductionResult:
        if self.ffmpeg_runner is None:
            raise DependencyUnavailableError("FFmpeg and FFprobe are required.", dependency_name="ffmpeg")
        self.approvals.require_private_render(result.approval, result.production_input)
        if result.voice_result is None or not result.voice_result.success:
            raise ValidationError("Full local narration is required before rendering.")
        specification = RenderSpecification(
            width=1280 if preview else 1920,
            height=720 if preview else 1080,
            preview=preview,
            output_relative_path=Path(
                "render/AuraAI_Mission_Zero_PRIVATE_PREVIEW_v1.mp4"
                if preview else "render/AuraAI_Mission_Zero_PRIVATE_DRAFT_v1.mp4"
            ),
        )
        manifest = result.render_manifest.model_copy(update={"specification": specification})
        renderer = PrivateSceneRenderer(self.ffmpeg_runner, result.production_input.output_root)
        requirement_by_id = {item.asset_id: item for item in result.asset_requirements}
        for scene, relative in zip(result.scenes, manifest.scene_relative_paths):
            source_asset = None
            if scene.required_asset_ids:
                requirement = requirement_by_id.get(scene.required_asset_ids[0])
                if requirement is not None:
                    candidate = result.production_input.output_root / requirement.target_relative_path
                    if candidate.is_file():
                        source_asset = candidate
            renderer.render(scene, specification, relative, source_asset=source_asset)
        self._emit(RuntimeEventType.RENDER_STARTED, "Founder-approved private render started.", result.production_input)
        render_result = PrivateRenderService(
            self.ffmpeg_runner,
            result.production_input.output_root,
        ).render(
            production_input=result.production_input,
            approval=result.approval,
            manifest=manifest,
            voice_result=result.voice_result,
            asset_validation=result.asset_validation,
            allow_placeholder_preview=preview,
        )
        event_type = RuntimeEventType.RENDER_COMPLETED if render_result.verified else RuntimeEventType.RENDER_FAILED
        self._emit(event_type, "Private render completed." if render_result.verified else "Private render failed.", result.production_input)
        if render_result.verified:
            self._emit(RuntimeEventType.RENDER_VERIFIED, "Private render verified with FFprobe.", result.production_input)
            self._emit(RuntimeEventType.PRIVATE_VIDEO_REVIEW_REQUIRED, "Founder private-video review required.", result.production_input)
        return result.model_copy(update={
            "render_manifest": manifest,
            "render_result": render_result,
            "status": render_result.status,
            "runtime_events": [event.event_type.value for event in self.event_bus.list_events()],
        })

    def _select_voice(self, name: str) -> VoiceProfile:
        voices = self.voice_service.list_voices()
        self.event_bus.emit(RuntimeEventType.VOICE_LISTED, f"Listed {len(voices)} safe local voices.")
        for voice in voices:
            if voice.name == name:
                return voice
        raise ValidationError("Selected local voice is unavailable.", error_code="VOICE_NOT_FOUND")

    @staticmethod
    def _discover_assets(output_root: Path, requirements) -> list[AssetRecord]:
        """Discover only explicitly named files inside the prepared output root."""

        root = output_root.resolve()
        return [
            AssetRecord(
                asset_id=requirement.asset_id,
                asset_type=requirement.asset_type,
                relative_path=requirement.target_relative_path,
                supplied=True,
            )
            for requirement in requirements
            if (root / requirement.target_relative_path).resolve().is_file()
            and root in (root / requirement.target_relative_path).resolve().parents
        ]

    @staticmethod
    def _narration_segments(result: PrivateVideoProductionResult) -> list[NarrationSegment]:
        total_words = sum(len(text.split()) for text in result.production_input.sections)
        return [
            NarrationSegment(
                segment_id=f"section-{index:02d}",
                sequence=index,
                heading=f"Section {index}",
                text=text,
                expected_duration_seconds=(
                    result.production_input.estimated_duration_seconds * len(text.split()) / total_words
                ),
            )
            for index, text in enumerate(result.production_input.sections, start=1)
        ]

    @staticmethod
    def _retime_scenes(scenes, duration: float):
        original = max(scene.expected_end_seconds for scene in scenes)
        scale = duration / original
        return [scene.model_copy(update={
            "expected_start_seconds": round(scene.expected_start_seconds * scale, 3),
            "expected_end_seconds": round(scene.expected_end_seconds * scale, 3),
        }) for scene in scenes]

    @staticmethod
    def _mission_manager(package_root: Path) -> MissionManager:
        payload = json.loads((package_root / "mission/mission.json").read_text(encoding="utf-8"))
        mission = Mission.model_validate(payload)
        return MissionManager(
            InMemoryMissionRepository([mission]),
            ArtifactRegistry(mission.produced_artifacts),
            audit_actions=True,
        )

    def _emit(self, event_type, message: str, production_input) -> None:
        self.event_bus.emit(
            event_type,
            message,
            mission_id=production_input.mission_id,
            metadata={"script_version": production_input.script_version, "published": False},
        )
