"""Adapters from legacy/projection mission models into Mission Control."""
from mission_control.models import MissionRecord, RiskLevel


def from_mission_engine(value, *, founder_owner: str) -> MissionRecord:
    """Create an authoritative record while preserving the legacy identity."""
    return MissionRecord(mission_id=value.mission_id,title=value.title,objective=value.objective,priority=value.priority,risk=RiskLevel.LOW,current_stage=value.status.value,founder_owner=founder_owner)
