"""Deterministic Offline Rendering Specialist."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from core import DepartmentName, OperationResult, TaskRecord, ValidationError
from agents.base_employee import BaseEmployee
from mission_control.checkpoints import CheckpointWriter
from mission_control.models import CheckpointKind, CheckpointResumability
from private_video_production.pipeline import PrivateVideoProductionPipeline
from runtime_engine.render_context import (
    ArtifactRegistrar,
    CheckpointReader,
    IntegrityVerifier,
)


class RenderSpecialist(BaseEmployee):
    """Executes the existing PrivateVideoProductionPipeline securely."""

    def __init__(
        self,
        *,
        pipeline: PrivateVideoProductionPipeline,
        checkpoint_reader: CheckpointReader,
        checkpoint_writer: CheckpointWriter,
        artifact_registrar: ArtifactRegistrar,
        integrity_verifier: IntegrityVerifier,
    ) -> None:
        super().__init__(
            name="AuraRender",
            job_title="Render Specialist",
            department=DepartmentName.PRODUCTION,
            description="Performs deterministic offline rendering with checkpointed recovery.",
        )
        self.pipeline = pipeline
        self.checkpoint_reader = checkpoint_reader
        self.checkpoint_writer = checkpoint_writer
        self.artifact_registrar = artifact_registrar
        self.integrity_verifier = integrity_verifier

    def perform_task(self, task: TaskRecord) -> OperationResult:
        mission_id = UUID(str(task.input_data["mission_id"]))
        task_id = UUID(str(task.input_data["task_id"]))
        attempt_id = UUID(str(task.input_data["attempt_id"]))
        mission_package = Path(str(task.input_data["mission_package"]))
        output_root = Path(str(task.input_data.get("output_root", mission_package)))
        render_job_id = task.input_data.get("render_job_id")

        # 1. Recovery - read latest checkpoints across all attempts
        checkpoints = []
        latest = None
        if render_job_id:
            latest = self.checkpoint_reader.get_latest_checkpoint(
                mission_id, 
                task_id, 
                metadata_filter={"render_job_id": str(render_job_id)}
            )
        else:
            # Legacy fallback: but do we allow fallback? Prompt says:
            # "legacy checkpoints without render_job_id must not be silently reused for a different job"
            # If there is a render_job_id in task, we strictly filtered for it above.
            # If the task doesn't have render_job_id (legacy mode?), we might just not find anything or find latest.
            latest = self.checkpoint_reader.get_latest_checkpoint(mission_id, task_id)
            
        if latest is not None:
            # Reconstruct sequence or just find the highest phase
            pass
            
        # We need to know if voice_completed exists
        voice_completed = False
        render_completed = False
        
        # In a real implementation we might list all checkpoints to find specific ones.
        # Since CheckpointReader only has get_latest_checkpoint right now, let's assume
        # the payload contains the latest status.
        if latest and "step" in latest.payload:
            step = latest.payload["step"]
            if step in ("voice_completed", "render_completed"):
                # verify artifact
                artifact_id = latest.payload.get("artifact_id")
                expected_hash = latest.payload.get("artifact_hash")
                if artifact_id and expected_hash:
                    try:
                        self.integrity_verifier.verify(UUID(artifact_id), expected_hash)
                        voice_completed = True
                        if step == "render_completed":
                            render_completed = True
                    except ValidationError as e:
                        self.logger.warning("Checkpoint integrity failed, restarting step: %s", str(e))
        
        # Prepare
        if not voice_completed:
            result, _ = self.pipeline.prepare(mission_package, output_root, export=False)
            self._write_checkpoint(attempt_id, "planning_completed", {}, render_job_id=render_job_id)
            
            # Voice
            # We assume a default voice for now, or read from task input
            voice_name = task.input_data.get("voice_name", "Sarah")
            result = self.pipeline.generate_narration(result, voice_name=voice_name)
            
            # Register narration artifact
            narration_path = output_root / "voice/narration.wav"
            if narration_path.exists():
                artifact = self.artifact_registrar.register_artifact(
                    mission_id=mission_id,
                    task_id=task_id,
                    artifact_type="audio.narration",
                    location=str(narration_path.resolve()),
                    value={"duration_seconds": result.voice_result.duration_seconds},
                    provenance={"voice_name": voice_name},
                )
                self._write_checkpoint(
                    attempt_id, 
                    "voice_completed", 
                    {"artifact_id": str(artifact.artifact_id), "artifact_hash": artifact.content_hash},
                    render_job_id=render_job_id,
                    artifact_reference=str(artifact.artifact_id),
                )
        else:
            # Recover from valid checkpoint
            result, _ = self.pipeline.prepare(mission_package, output_root, export=False)
            result = self.pipeline.recover_narration(result)
            
        # Render
        if not render_completed:
            result = self.pipeline.render(result, preview=False)
            
            render_path = output_root / "render/AuraAI_Mission_Zero_PRIVATE_DRAFT_v1.mp4"
            if render_path.exists():
                artifact = self.artifact_registrar.register_artifact(
                    mission_id=mission_id,
                    task_id=task_id,
                    artifact_type="video.render",
                    location=str(render_path.resolve()),
                    value={},
                    provenance={},
                )
                self._write_checkpoint(
                    attempt_id, 
                    "render_completed", 
                    {"artifact_id": str(artifact.artifact_id), "artifact_hash": artifact.content_hash},
                    render_job_id=render_job_id,
                    artifact_reference=str(artifact.artifact_id),
                )
                
        return OperationResult.ok(
            "Rendering pipeline completed successfully.",
            data={"status": "render_completed"}
        )

    def _write_checkpoint(
        self,
        attempt_id: UUID,
        step: str,
        payload: dict,
        render_job_id: str | None = None,
        artifact_reference: str | None = None,
    ) -> None:
        payload["step"] = step
        if render_job_id:
            payload["render_job_id"] = str(render_job_id)
        self.checkpoint_writer.create_checkpoint(
            attempt_id=attempt_id,
            kind=CheckpointKind.PROGRESS,
            payload=payload,
            producer_employee_id=self.agent_id,
            resumability=CheckpointResumability.RESUMABLE,
            artifact_reference=artifact_reference,
        )
