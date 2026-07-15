"""Safe path, format, hash, and requirement validation for local assets."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from private_video_production.models import (
    AssetRecord,
    AssetRequirement,
    AssetValidationResult,
)


class AssetValidator:
    """Validate assets under an injected root without reading private locations."""

    SUPPORTED = {".mp4", ".mov", ".mkv", ".png", ".jpg", ".jpeg", ".wav"}
    SENSITIVE_NAME = re.compile(r"(?i)(\.env|api.?key|token|secret|password|recovery)")

    def validate(
        self,
        root: Path,
        requirements: list[AssetRequirement],
        records: list[AssetRecord],
    ) -> AssetValidationResult:
        supplied: list[str] = []
        warnings: list[str] = []
        seen: set[str] = set()
        duplicates: list[str] = []
        for record in records:
            if record.asset_id in seen:
                duplicates.append(record.asset_id)
                continue
            seen.add(record.asset_id)
            target = (root.resolve() / record.relative_path).resolve()
            if root.resolve() not in target.parents:
                warnings.append(f"Unsafe path rejected for {record.asset_id}.")
                continue
            if self.SENSITIVE_NAME.search(target.name):
                warnings.append(f"Sensitive-looking filename rejected for {record.asset_id}.")
                continue
            if target.suffix.lower() not in self.SUPPORTED or not target.is_file():
                warnings.append(f"Missing or unsupported asset: {record.asset_id}.")
                continue
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            if record.content_hash and record.content_hash != digest:
                warnings.append(f"Content hash mismatch for {record.asset_id}.")
                continue
            supplied.append(record.asset_id)
        required = {item.asset_id for item in requirements}
        missing = sorted(required - set(supplied))
        return AssetValidationResult(
            valid=not missing and not duplicates and not warnings,
            supplied_asset_ids=sorted(supplied),
            missing_asset_ids=missing,
            duplicate_asset_ids=sorted(set(duplicates)),
            warnings=warnings,
        )
