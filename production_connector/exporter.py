"""Safe deterministic filesystem export primitives."""
from __future__ import annotations
import csv
import io
import json
import tempfile
from pathlib import Path
from typing import Any
from core import ValidationError


class PackageWriter:
    """Write UTF-8 package files beneath a new, bounded output root."""
    def __init__(self, root: Path, *, workspace_root: Path | None = None) -> None:
        self.root = root.resolve()
        allowed_roots = [(workspace_root or Path.cwd()).resolve(), Path(tempfile.gettempdir()).resolve()]
        if not any(self.root == allowed or self.root.is_relative_to(allowed) for allowed in allowed_roots):
            raise ValidationError("Output path is unsafe.", error_code="UNSAFE_OUTPUT_PATH")

    def ensure_new(self) -> None:
        if self.root.exists():
            raise ValidationError("Output root already exists; overwrite refused.", error_code="OUTPUT_EXISTS")
        self.root.mkdir(parents=True)

    def text(self, relative: str, value: str) -> None:
        target = self._target(relative); target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value.rstrip() + "\n", encoding="utf-8", newline="\n")

    def json(self, relative: str, value: Any) -> None:
        self.text(relative, json.dumps(value, indent=2, sort_keys=True, default=str, ensure_ascii=False))

    def csv(self, relative: str, rows: list[dict[str, Any]]) -> None:
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else [])
        if rows: writer.writeheader(); writer.writerows(rows)
        self.text(relative, stream.getvalue())

    def _target(self, relative: str) -> Path:
        target = (self.root / relative).resolve()
        try: target.relative_to(self.root)
        except ValueError as error:
            raise ValidationError("Export path traversal rejected.", error_code="UNSAFE_EXPORT_PATH") from error
        return target
