"""Explicit in-memory registry for founder-supplied production assets."""

from core import ValidationError

from private_video_production.models import AssetRecord


class AssetRegistry:
    """Register unique assets without global mutable state."""

    def __init__(self) -> None:
        self._records: dict[str, AssetRecord] = {}

    def register(self, record: AssetRecord) -> None:
        if record.asset_id in self._records:
            raise ValidationError("Duplicate asset ID was rejected.")
        self._records[record.asset_id] = record

    def records(self) -> tuple[AssetRecord, ...]:
        return tuple(self._records.values())
