"""Injectable in-memory persistence boundaries for missions and artifacts."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol
from uuid import UUID

from core.exceptions import ValidationError
from mission_engine.models import Mission, MissionArtifact


class MissionRepository(Protocol):
    """Persistence contract used by the mission manager."""

    def save(self, mission: Mission) -> None:
        """Persist one mission snapshot."""

    def load(self, mission_id: UUID) -> Mission | None:
        """Load one mission snapshot if present."""

    def list_all(self) -> tuple[Mission, ...]:
        """Return every persisted mission snapshot."""


class InMemoryMissionRepository:
    """Deterministic process-local repository with defensive copies."""

    def __init__(self, missions: Iterable[Mission] = ()) -> None:
        self._missions: dict[UUID, Mission] = {
            mission.mission_id: mission.model_copy(deep=True)
            for mission in missions
        }

    def save(self, mission: Mission) -> None:
        """Persist a defensive copy of one validated mission."""

        self._missions[mission.mission_id] = mission.model_copy(deep=True)

    def load(self, mission_id: UUID) -> Mission | None:
        """Return a defensive copy so callers cannot mutate stored state."""

        mission = self._missions.get(mission_id)
        return mission.model_copy(deep=True) if mission is not None else None

    def list_all(self) -> tuple[Mission, ...]:
        """Return stable creation-ordered defensive copies."""

        return tuple(
            mission.model_copy(deep=True)
            for mission in sorted(
                self._missions.values(),
                key=lambda item: (item.created_at, str(item.mission_id)),
            )
        )


class ArtifactRegistry:
    """Metadata-only registry for employee-produced mission outputs."""

    def __init__(self, artifacts: Iterable[MissionArtifact] = ()) -> None:
        self._artifacts: dict[UUID, MissionArtifact] = {
            artifact.artifact_id: artifact.model_copy(deep=True)
            for artifact in artifacts
        }

    def register(self, artifact: MissionArtifact) -> None:
        """Register a unique artifact or reject identifier collisions."""

        if artifact.artifact_id in self._artifacts:
            raise ValidationError(
                "Mission artifact identifier already exists.",
                error_code="DUPLICATE_MISSION_ARTIFACT",
                details={"artifact_id": str(artifact.artifact_id)},
            )
        self._artifacts[artifact.artifact_id] = artifact.model_copy(deep=True)

    def load(self, artifact_id: UUID) -> MissionArtifact | None:
        """Load one artifact metadata record."""

        artifact = self._artifacts.get(artifact_id)
        return artifact.model_copy(deep=True) if artifact is not None else None

    def for_mission(self, mission_id: UUID) -> tuple[MissionArtifact, ...]:
        """Return creation-ordered artifacts belonging to one mission."""

        return tuple(
            artifact.model_copy(deep=True)
            for artifact in sorted(
                (
                    item
                    for item in self._artifacts.values()
                    if item.mission_id == mission_id
                ),
                key=lambda item: (item.created_at, str(item.artifact_id)),
            )
        )
