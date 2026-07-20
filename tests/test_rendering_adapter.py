import hashlib
from pathlib import Path
from uuid import uuid4

import pytest

from core import ValidationError, DepartmentName, TaskRecord
from mission_control.models import CheckpointKind, CheckpointResumability, ArtifactRecord
from agents.specialists.render_specialist import RenderSpecialist
from runtime_engine.render_context import DefaultIntegrityVerifier


class MockPipeline:
    def __init__(self):
        self.prepare_called = False
        self.generate_narration_called = False
        self.recover_narration_called = False
        self.render_called = False
        self.output_root = None
        self.export = None

    def prepare(self, package, output_root, export=True):
        self.prepare_called = True
        self.output_root = output_root
        self.export = export
        return "result", Path("video")

    def generate_narration(self, result, voice_name=None):
        self.generate_narration_called = True
        class VoiceResult:
            duration_seconds = 10.0
        class Res:
            voice_result = VoiceResult()
        
        # Create mock artifact on disk
        voice_dir = self.output_root / "voice"
        voice_dir.mkdir(parents=True, exist_ok=True)
        (voice_dir / "narration.wav").write_text("voice audio content")
        
        return Res()

    def recover_narration(self, result):
        self.recover_narration_called = True
        return result

    def render(self, result, preview=False):
        self.render_called = True
        render_dir = self.output_root / "render"
        render_dir.mkdir(parents=True, exist_ok=True)
        (render_dir / "AuraAI_Mission_Zero_PRIVATE_DRAFT_v1.mp4").write_text("video content")
        return result


class MockCheckpointReader:
    def __init__(self):
        self.latest = None
    def get_latest_checkpoint(self, mission_id, task_id, sequence=None, metadata_filter=None):
        if not self.latest:
            return None
        if metadata_filter:
            for k, v in metadata_filter.items():
                if str(self.latest.payload.get(k)) != str(v):
                    return None
        return self.latest


class MockCheckpointWriter:
    def __init__(self):
        self.checkpoints = []
    def create_checkpoint(self, **kwargs):
        self.checkpoints.append(kwargs)


class MockArtifactRegistrar:
    def register_artifact(self, **kwargs):
        artifact = ArtifactRecord(
            mission_id=kwargs["mission_id"],
            task_id=kwargs["task_id"],
            artifact_type=kwargs["artifact_type"],
            location=kwargs["location"],
            content_hash=hashlib.sha256(Path(kwargs["location"]).read_bytes()).hexdigest(),
        )
        return artifact


class MockArtifactResolver:
    def __init__(self):
        self.artifacts = {}
    def resolve_artifact(self, artifact_id):
        return self.artifacts.get(artifact_id)


def test_render_specialist_success_no_checkpoints(tmp_path):
    pipeline = MockPipeline()
    reader = MockCheckpointReader()
    writer = MockCheckpointWriter()
    registrar = MockArtifactRegistrar()
    resolver = MockArtifactResolver()
    verifier = DefaultIntegrityVerifier(resolver, [tmp_path])

    specialist = RenderSpecialist(
        pipeline=pipeline,
        checkpoint_reader=reader,
        checkpoint_writer=writer,
        artifact_registrar=registrar,
        integrity_verifier=verifier,
    )
    specialist.identity.agent_id = uuid4()

    mission_id = uuid4()
    task_id = uuid4()
    attempt_id = uuid4()

    task = TaskRecord(
        task_id=task_id,
        department=DepartmentName.PRODUCTION,
        title="Render Video",
        input_data={
            "mission_id": str(mission_id),
            "task_id": str(task_id),
            "attempt_id": str(attempt_id),
            "render_job_id": "test-job-id-1234",
            "mission_package": str(tmp_path / "package"),
            "output_root": str(tmp_path / "output"),
        }
    )

    result = specialist.perform_task(task)
    assert result.success
    assert pipeline.prepare_called
    assert pipeline.generate_narration_called
    assert not pipeline.recover_narration_called
    assert pipeline.render_called

    assert len(writer.checkpoints) == 3
    assert writer.checkpoints[0]["payload"]["step"] == "planning_completed"
    assert writer.checkpoints[1]["payload"]["step"] == "voice_completed"
    assert writer.checkpoints[2]["payload"]["step"] == "render_completed"
    assert writer.checkpoints[2]["attempt_id"] == attempt_id
    assert writer.checkpoints[2]["payload"]["render_job_id"] == task.input_data["render_job_id"]

def test_render_specialist_resume_voice(tmp_path):
    # Simulate a prior attempt that finished voice, but crashed during render.
    pipeline = MockPipeline()
    reader = MockCheckpointReader()
    writer = MockCheckpointWriter()
    registrar = MockArtifactRegistrar()
    resolver = MockArtifactResolver()
    verifier = DefaultIntegrityVerifier(resolver, [tmp_path])
    
    specialist = RenderSpecialist(
        pipeline=pipeline,
        checkpoint_reader=reader,
        checkpoint_writer=writer,
        artifact_registrar=registrar,
        integrity_verifier=verifier,
    )
    specialist.identity.agent_id = uuid4()

    mission_id = uuid4()
    task_id = uuid4()
    attempt_id = uuid4()
    artifact_id = uuid4()
    
    voice_file = tmp_path / "output/voice/narration.wav"
    voice_file.parent.mkdir(parents=True)
    voice_file.write_text("voice audio content")
    expected_hash = hashlib.sha256(voice_file.read_bytes()).hexdigest()
    
    resolver.artifacts[artifact_id] = ArtifactRecord(
        artifact_id=artifact_id,
        mission_id=mission_id,
        artifact_type="audio.narration",
        location=str(voice_file.resolve()),
        content_hash=expected_hash,
    )
    
    render_job_id = uuid4()
    
    class MockCp:
        payload = {
            "step": "voice_completed", 
            "artifact_id": str(artifact_id), 
            "artifact_hash": expected_hash,
            "render_job_id": str(render_job_id),
        }
    reader.latest = MockCp()

    task = TaskRecord(
        task_id=task_id,
        department=DepartmentName.PRODUCTION,
        title="Render Video",
        input_data={
            "mission_id": str(mission_id),
            "task_id": str(task_id),
            "attempt_id": str(attempt_id),
            "render_job_id": str(render_job_id),
            "mission_package": str(tmp_path / "package"),
            "output_root": str(tmp_path / "output"),
        }
    )

    result = specialist.perform_task(task)
    assert result.success
    assert pipeline.prepare_called
    assert not pipeline.generate_narration_called
    assert pipeline.recover_narration_called
    assert pipeline.render_called

def test_render_specialist_ignores_different_job_checkpoints(tmp_path):
    pipeline = MockPipeline()
    reader = MockCheckpointReader()
    writer = MockCheckpointWriter()
    registrar = MockArtifactRegistrar()
    resolver = MockArtifactResolver()
    verifier = DefaultIntegrityVerifier(resolver, [tmp_path])
    
    specialist = RenderSpecialist(
        pipeline=pipeline,
        checkpoint_reader=reader,
        checkpoint_writer=writer,
        artifact_registrar=registrar,
        integrity_verifier=verifier,
    )
    specialist.identity.agent_id = uuid4()

    mission_id = uuid4()
    task_id = uuid4()
    attempt_id = uuid4()
    
    class MockCp:
        payload = {
            "step": "voice_completed", 
            "artifact_id": str(uuid4()), 
            "artifact_hash": "mock",
            "render_job_id": str(uuid4()), # different job id!
        }
    reader.latest = MockCp()

    task = TaskRecord(
        task_id=task_id,
        department=DepartmentName.PRODUCTION,
        title="Render Video",
        input_data={
            "mission_id": str(mission_id),
            "task_id": str(task_id),
            "attempt_id": str(attempt_id),
            "render_job_id": str(uuid4()), # active job
            "mission_package": str(tmp_path / "package"),
            "output_root": str(tmp_path / "output"),
        }
    )

    result = specialist.perform_task(task)
    assert result.success
    # Because job_ids did not match, it must not recover, it must generate again.
    assert pipeline.generate_narration_called
    assert not pipeline.recover_narration_called

def test_integrity_verifier_validations(tmp_path):
    resolver = MockArtifactResolver()
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    verifier = DefaultIntegrityVerifier(resolver, [allowed_root])
    
    valid_hash = "a" * 64
    diff_hash = "b" * 64
    
    # 1. Missing artifact
    with pytest.raises(ValidationError, match="Unknown artifact"):
        verifier.verify(uuid4(), valid_hash)
        
    # 2. Hash mismatch against registry metadata
    artifact_id = uuid4()
    resolver.artifacts[artifact_id] = ArtifactRecord(
        artifact_id=artifact_id,
        mission_id=uuid4(),
        artifact_type="text",
        location=str(allowed_root / "file.txt"),
        content_hash=valid_hash,
    )
    with pytest.raises(ValidationError, match="hash mismatch"):
        verifier.verify(artifact_id, diff_hash)
        
    # 3. Path outside allowed roots
    artifact_id_outside = uuid4()
    outside_path = tmp_path / "outside.txt"
    outside_path.write_text("secret")
    resolver.artifacts[artifact_id_outside] = ArtifactRecord(
        artifact_id=artifact_id_outside,
        mission_id=uuid4(),
        artifact_type="text",
        location=str(outside_path),
        content_hash=valid_hash,
    )
    with pytest.raises(ValidationError, match="outside allowed roots"):
        verifier.verify(artifact_id_outside, valid_hash)
        
    # 4. Path traversal / Symlink escape
    artifact_id_traversal = uuid4()
    traversal_path = allowed_root / ".." / "outside.txt"
    resolver.artifacts[artifact_id_traversal] = ArtifactRecord(
        artifact_id=artifact_id_traversal,
        mission_id=uuid4(),
        artifact_type="text",
        location=str(traversal_path),
        content_hash=valid_hash,
    )
    with pytest.raises(ValidationError, match="outside allowed roots"):
        verifier.verify(artifact_id_traversal, valid_hash)
        
    # 5. Missing file on disk
    artifact_id_missing = uuid4()
    missing_path = allowed_root / "missing.txt"
    resolver.artifacts[artifact_id_missing] = ArtifactRecord(
        artifact_id=artifact_id_missing,
        mission_id=uuid4(),
        artifact_type="text",
        location=str(missing_path),
        content_hash=valid_hash,
    )
    with pytest.raises(ValidationError, match="does not exist"):
        verifier.verify(artifact_id_missing, valid_hash)
        
    # 6. Actual contents hash mismatch
    artifact_id_mismatch = uuid4()
    mismatch_path = allowed_root / "mismatch.txt"
    mismatch_path.write_text("actual_content")
    wrong_hash = "0" * 64
    resolver.artifacts[artifact_id_mismatch] = ArtifactRecord(
        artifact_id=artifact_id_mismatch,
        mission_id=uuid4(),
        artifact_type="text",
        location=str(mismatch_path),
        content_hash=wrong_hash,
    )
    with pytest.raises(ValidationError, match="contents do not match"):
        verifier.verify(artifact_id_mismatch, wrong_hash)
