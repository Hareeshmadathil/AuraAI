"""Repository interfaces and durable SQLite implementation."""
from __future__ import annotations

import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, TypeVar
from uuid import UUID

from pydantic import BaseModel

from mission_control.models import (
    DuplicateRecordError,
    RepositoryIntegrityError,
    AnalyticsSnapshot,
    ApprovalRequest,
    ArtifactRecord,
    EventRecord,
    ExecutionAttempt,
    MissionRecord,
    TaskCheckpoint,
    TaskRecord,
    TaskStatus,
    RenderJob,
    PublishingQueueItem,
    PublicationRecord,
)

T = TypeVar("T", bound=BaseModel)


class MissionControlRepository(ABC):
    @abstractmethod
    def save_mission(self, value: MissionRecord) -> None: ...
    @abstractmethod
    def get_mission(self, mission_id: UUID) -> MissionRecord | None: ...
    @abstractmethod
    def list_missions(self) -> list[MissionRecord]: ...
    @abstractmethod
    def update_mission(self, value: MissionRecord) -> None: ...
    @abstractmethod
    def save_task(self, value: TaskRecord) -> None: ...
    @abstractmethod
    def get_task(self, task_id: UUID) -> TaskRecord | None: ...
    @abstractmethod
    def list_tasks(self, mission_id: UUID | None = None) -> list[TaskRecord]: ...
    @abstractmethod
    def update_task(self, value: TaskRecord) -> None: ...
    @abstractmethod
    def save_artifact(self, value: ArtifactRecord) -> None: ...
    @abstractmethod
    def list_artifacts(self, mission_id: UUID | None = None) -> list[ArtifactRecord]: ...
    @abstractmethod
    def save_approval(self, value: ApprovalRequest) -> None: ...
    @abstractmethod
    def get_approval(self, approval_id: UUID) -> ApprovalRequest | None: ...
    @abstractmethod
    def list_approvals(self, mission_id: UUID | None = None) -> list[ApprovalRequest]: ...
    @abstractmethod
    def append_event(self, value: EventRecord) -> EventRecord: ...
    @abstractmethod
    def list_events(self, mission_id: UUID | None = None) -> list[EventRecord]: ...
    @abstractmethod
    def save_attempt(self, value: ExecutionAttempt) -> None: ...
    @abstractmethod
    def update_attempt(self, value: ExecutionAttempt) -> None: ...
    @abstractmethod
    def get_attempt(self, attempt_id: UUID) -> ExecutionAttempt | None: ...
    @abstractmethod
    def list_attempts(self, mission_id: UUID | None = None) -> list[ExecutionAttempt]: ...
    @abstractmethod
    def save_checkpoint(self, value: TaskCheckpoint) -> None: ...
    @abstractmethod
    def get_checkpoint(self, checkpoint_id: UUID) -> TaskCheckpoint | None: ...
    @abstractmethod
    def list_checkpoints(self, mission_id: UUID | None = None) -> list[TaskCheckpoint]: ...
    @abstractmethod
    def save_render_job(self, value: RenderJob) -> None: ...
    @abstractmethod
    def update_render_job(self, value: RenderJob) -> None: ...
    @abstractmethod
    def get_render_job(self, job_id: UUID) -> RenderJob | None: ...
    @abstractmethod
    def list_render_jobs(self, mission_id: UUID | None = None) -> list[RenderJob]: ...
    @abstractmethod
    def save_publishing_queue_item(self, value: PublishingQueueItem) -> None: ...
    @abstractmethod
    def update_publishing_queue_item(self, value: PublishingQueueItem) -> None: ...
    @abstractmethod
    def get_publishing_queue_item(self, queue_item_id: UUID) -> PublishingQueueItem | None: ...
    @abstractmethod
    def list_publishing_queue_items(self, mission_id: UUID | None = None) -> list[PublishingQueueItem]: ...
    @abstractmethod
    def save_publication_record(self, value: 'PublicationRecord') -> None: ...
    @abstractmethod
    def get_publication_record_by_id(self, publication_id: UUID) -> 'PublicationRecord' | None: ...
    @abstractmethod
    def get_publication_record(self, queue_item_id: UUID) -> 'PublicationRecord' | None: ...
    @abstractmethod
    def save_analytics_snapshot(self, snapshot: AnalyticsSnapshot) -> None: ...
    @abstractmethod
    def find_snapshot_by_id(self, snapshot_id: UUID) -> AnalyticsSnapshot | None: ...
    @abstractmethod
    def find_observation_snapshot(
        self,
        publication_id: UUID,
        observed_at: datetime,
    ) -> AnalyticsSnapshot | None: ...
    @abstractmethod
    def list_analytics_snapshots(
        self,
        publication_id: UUID,
    ) -> list[AnalyticsSnapshot]: ...
    @abstractmethod
    @contextmanager
    def transaction(self) -> Iterator[None]: ...


class InMemoryMissionControlRepository(MissionControlRepository):
    def __init__(self) -> None:
        self.missions: dict[UUID, MissionRecord] = {}
        self.tasks: dict[UUID, TaskRecord] = {}
        self.artifacts: dict[UUID, ArtifactRecord] = {}
        self.approvals: dict[UUID, ApprovalRequest] = {}
        self.events: list[EventRecord] = []
        self.attempts: dict[UUID, ExecutionAttempt] = {}
        self.checkpoints: dict[UUID, TaskCheckpoint] = {}
        self.render_jobs: dict[UUID, RenderJob] = {}
        self.publishing_queue: dict[UUID, PublishingQueueItem] = {}
        self.publication_records: dict[UUID, PublicationRecord] = {}
        self.analytics_snapshots: dict[UUID, AnalyticsSnapshot] = {}
        self._lock = threading.RLock()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self._lock:
            yield

    def _insert(self, store: dict, key: UUID, value: T) -> None:
        if key in store:
            raise ValueError(f"Duplicate identity: {key}")
        store[key] = value.model_copy(deep=True)

    def save_mission(self, value): self._insert(self.missions, value.mission_id, value)
    def get_mission(self, mission_id): return self.missions.get(mission_id)
    def list_missions(self): return list(self.missions.values())
    def update_mission(self, value): self.missions[value.mission_id] = value.model_copy(deep=True)
    def save_task(self, value): self._insert(self.tasks, value.task_id, value)
    def get_task(self, task_id): return self.tasks.get(task_id)
    def list_tasks(self, mission_id=None): return [v for v in self.tasks.values() if mission_id is None or v.mission_id == mission_id]
    def update_task(self, value): self.tasks[value.task_id] = value.model_copy(deep=True)
    def save_artifact(self, value): self._insert(self.artifacts, value.artifact_id, value)
    def list_artifacts(self, mission_id=None): return [v for v in self.artifacts.values() if mission_id is None or v.mission_id == mission_id]
    def save_approval(self, value): self.approvals[value.approval_id] = value.model_copy(deep=True)
    def get_approval(self, approval_id): return self.approvals.get(approval_id)
    def list_approvals(self, mission_id=None): return [v for v in self.approvals.values() if mission_id is None or v.mission_id == mission_id]
    def append_event(self, value):
        new_val = value.model_copy(update={"sequence": len(self.events) + 1})
        self.events.append(new_val)
        return new_val
    def list_events(self, mission_id=None): return [v for v in self.events if mission_id is None or v.mission_id == mission_id]
    def save_attempt(self, value): self._insert(self.attempts, value.attempt_id, value)
    def update_attempt(self, value): self.attempts[value.attempt_id] = value.model_copy(deep=True)
    def get_attempt(self, attempt_id): return self.attempts.get(attempt_id)
    def list_attempts(self, mission_id=None): return [v for v in self.attempts.values() if mission_id is None or v.mission_id == mission_id]
    def save_checkpoint(self, value): self._insert(self.checkpoints, value.checkpoint_id, value)
    def get_checkpoint(self, checkpoint_id): return self.checkpoints.get(checkpoint_id)
    def list_checkpoints(self, mission_id=None): return [v for v in self.checkpoints.values() if mission_id is None or v.mission_id == mission_id]
    def save_render_job(self, value): self._insert(self.render_jobs, value.job_id, value)
    def update_render_job(self, value): self.render_jobs[value.job_id] = value.model_copy(deep=True)
    def get_render_job(self, job_id): return self.render_jobs.get(job_id)
    def list_render_jobs(self, mission_id=None): return [v for v in self.render_jobs.values() if mission_id is None or v.mission_id == mission_id]
    def save_publishing_queue_item(self, value): self._insert(self.publishing_queue, value.queue_item_id, value)
    def update_publishing_queue_item(self, value): self.publishing_queue[value.queue_item_id] = value.model_copy(deep=True)
    def get_publishing_queue_item(self, queue_item_id): return self.publishing_queue.get(queue_item_id)
    def list_publishing_queue_items(self, mission_id=None): return [v for v in self.publishing_queue.values() if mission_id is None or v.mission_id == mission_id]
    def save_publication_record(self, value): self._insert(self.publication_records, value.queue_item_id, value)

    def get_publication_record_by_id(self, publication_id: UUID) -> 'PublicationRecord' | None:
        with self._lock:
            return next(
                (
                    record.model_copy(deep=True)
                    for record in self.publication_records.values()
                    if record.publication_id == publication_id
                ),
                None,
            )

    def get_publication_record(self, queue_item_id): return self.publication_records.get(queue_item_id)

    def save_analytics_snapshot(self, snapshot: AnalyticsSnapshot) -> None:
        with self._lock:
            if self.find_observation_snapshot(
                snapshot.publication_id,
                snapshot.observed_at,
            ) is not None:
                raise DuplicateRecordError(
                    "Analytics snapshot already exists for this publication "
                    "and observation time."
                )
            self._insert(
                self.analytics_snapshots,
                snapshot.analytics_snapshot_id,
                snapshot,
            )

    def find_snapshot_by_id(
        self,
        snapshot_id: UUID,
    ) -> AnalyticsSnapshot | None:
        with self._lock:
            snapshot = self.analytics_snapshots.get(snapshot_id)
            return snapshot.model_copy(deep=True) if snapshot else None

    def find_observation_snapshot(
        self,
        publication_id: UUID,
        observed_at: datetime,
    ) -> AnalyticsSnapshot | None:
        with self._lock:
            return next(
                (
                    snapshot.model_copy(deep=True)
                    for snapshot in self.analytics_snapshots.values()
                    if snapshot.publication_id == publication_id
                    and snapshot.observed_at == observed_at
                ),
                None,
            )

    def list_analytics_snapshots(
        self,
        publication_id: UUID,
    ) -> list[AnalyticsSnapshot]:
        with self._lock:
            snapshots = [
                snapshot.model_copy(deep=True)
                for snapshot in self.analytics_snapshots.values()
                if snapshot.publication_id == publication_id
            ]
        return sorted(
            snapshots,
            key=lambda snapshot: (
                snapshot.observed_at,
                snapshot.imported_at,
                snapshot.analytics_snapshot_id.int,
            ),
            reverse=True,
        )


class SQLiteMissionControlRepository(MissionControlRepository):
    """SQLite JSON-record repository with foreign keys and atomic writes."""
    SCHEMA_VERSION = 2

    def __init__(self, database_path: Path, *, allowed_root: Path) -> None:
        root = allowed_root.resolve()
        path = database_path.resolve()
        if path != root and root not in path.parents:
            raise ValueError("Mission Control database path escapes allowed root.")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.RLock()
        self._local = threading.local()
        self._initialize()

    def _initialize(self) -> None:
        with self._lock:
            self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS missions(id TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, mission_id TEXT NOT NULL REFERENCES missions(id), data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY, mission_id TEXT NOT NULL REFERENCES missions(id), task_id TEXT REFERENCES tasks(id), data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY, mission_id TEXT NOT NULL REFERENCES missions(id), task_id TEXT REFERENCES tasks(id), artifact_id TEXT REFERENCES artifacts(id), data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, mission_id TEXT REFERENCES missions(id), task_id TEXT REFERENCES tasks(id), event_type TEXT NOT NULL, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY, mission_id TEXT NOT NULL REFERENCES missions(id), task_id TEXT NOT NULL REFERENCES tasks(id), data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS checkpoints(id TEXT PRIMARY KEY, mission_id TEXT NOT NULL REFERENCES missions(id), task_id TEXT NOT NULL REFERENCES tasks(id), attempt_id TEXT NOT NULL REFERENCES attempts(id), data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS render_jobs(id TEXT PRIMARY KEY, mission_id TEXT NOT NULL REFERENCES missions(id), task_id TEXT NOT NULL REFERENCES tasks(id), data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS publishing_queue(id TEXT PRIMARY KEY, mission_id TEXT NOT NULL REFERENCES missions(id), data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS publication_records(id TEXT PRIMARY KEY, mission_id TEXT NOT NULL REFERENCES missions(id), queue_item_id TEXT UNIQUE NOT NULL REFERENCES publishing_queue(id), data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS analytics_snapshots(
                id TEXT PRIMARY KEY,
                mission_id TEXT NOT NULL REFERENCES missions(id),
                publication_id TEXT NOT NULL REFERENCES publication_records(id),
                queue_item_id TEXT NOT NULL REFERENCES publishing_queue(id),
                destination TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                data TEXT NOT NULL,
                UNIQUE(publication_id, observed_at)
            );
            CREATE INDEX IF NOT EXISTS idx_analytics_publication_observed ON analytics_snapshots(publication_id, observed_at DESC);
            """)
            row=self.connection.execute("SELECT version FROM schema_version").fetchone()
            if row is None: self.connection.execute("INSERT INTO schema_version(version) VALUES (?)",(self.SCHEMA_VERSION,))
            elif row[0] == 1: self.connection.execute("UPDATE schema_version SET version = ?", (self.SCHEMA_VERSION,))
            elif row[0] != self.SCHEMA_VERSION: raise RuntimeError("Unsupported Mission Control schema version.")

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self._lock:
            depth = getattr(self._local, "transaction_depth", 0)
            self._local.transaction_depth = depth + 1

            if self._local.transaction_depth == 1:
                self.connection.execute("BEGIN IMMEDIATE")
            else:
                from uuid import uuid4
                savepoint = f"sp_{uuid4().hex}"
                self.connection.execute(f"SAVEPOINT {savepoint}")

            try:
                yield
                if self._local.transaction_depth == 1:
                    self.connection.execute("COMMIT")
                else:
                    self.connection.execute(f"RELEASE SAVEPOINT {savepoint}")
            except Exception:
                if self._local.transaction_depth == 1:
                    self.connection.execute("ROLLBACK")
                else:
                    self.connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    self.connection.execute(f"RELEASE SAVEPOINT {savepoint}")
                raise
            finally:
                self._local.transaction_depth -= 1

    @staticmethod
    def _json(value: BaseModel) -> str: return value.model_dump_json()

    def _insert(self, sql, params):
        try:
            self.connection.execute(sql, params)
        except sqlite3.IntegrityError as error:
            raise ValueError(str(error)) from error

    def _get(self, table, identity, model):
        row=self.connection.execute(f"SELECT data FROM {table} WHERE id = ?",(str(identity),)).fetchone()
        return model.model_validate_json(row[0]) if row else None

    def _list(self, table, model, mission_id=None):
        sql=f"SELECT data FROM {table}"; params=()
        if mission_id is not None: sql += " WHERE mission_id = ?"; params=(str(mission_id),)
        return [model.model_validate_json(row[0]) for row in self.connection.execute(sql,params)]

    def _update(self,table,identity,value):
        self.connection.execute(f"UPDATE {table} SET data=? WHERE id=?",(self._json(value),str(identity)))

    def save_mission(self,v):
        with self._lock: self._insert("INSERT INTO missions(id,data) VALUES (?,?)",(str(v.mission_id),self._json(v)))
    def get_mission(self,i):
        with self._lock: return self._get("missions",i,MissionRecord)
    def list_missions(self):
        with self._lock: return self._list("missions",MissionRecord)

    def save_task(self,v):
        with self._lock: self._insert("INSERT INTO tasks(id,mission_id,data) VALUES (?,?,?)",(str(v.task_id),str(v.mission_id),self._json(v)))
    def get_task(self,i):
        with self._lock: return self._get("tasks",i,TaskRecord)
    def list_tasks(self,mission_id=None):
        with self._lock: return self._list("tasks",TaskRecord,mission_id)

    def save_artifact(self,v):
        with self._lock: self._insert("INSERT INTO artifacts(id,mission_id,task_id,data) VALUES (?,?,?,?)",(str(v.artifact_id),str(v.mission_id),str(v.task_id) if v.task_id else None,self._json(v)))
    def list_artifacts(self,mission_id=None):
        with self._lock: return self._list("artifacts",ArtifactRecord,mission_id)

    def save_approval(self,v):
        data=(str(v.mission_id),str(v.task_id) if v.task_id else None,str(v.artifact_id) if v.artifact_id else None,self._json(v),str(v.approval_id))
        with self._lock:
            self.connection.execute("INSERT INTO approvals(mission_id,task_id,artifact_id,data,id) VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",data)
    def get_approval(self,i):
        with self._lock: return self._get("approvals",i,ApprovalRequest)
    def list_approvals(self,mission_id=None):
        with self._lock: return self._list("approvals",ApprovalRequest,mission_id)

    def append_event(self,v):
        with self._lock:
            try:
                cursor=self.connection.execute("INSERT INTO events(id,mission_id,task_id,event_type,data) VALUES (?,?,?,?,?)",(str(v.event_id),str(v.mission_id) if v.mission_id else None,str(v.task_id) if v.task_id else None,v.event_type,self._json(v)))
                return v.model_copy(update={"sequence":cursor.lastrowid})
            except sqlite3.IntegrityError:
                row = self.connection.execute("SELECT sequence, data FROM events WHERE id = ?", (str(v.event_id),)).fetchone()
                if row:
                    return EventRecord.model_validate_json(row[1]).model_copy(update={"sequence": row[0]})
                raise ValueError("Integrity error appending event, but event not found.")

    def list_events(self,mission_id=None):
        sql="SELECT sequence,data FROM events"; params=()
        if mission_id is not None: sql += " WHERE mission_id = ?"; params=(str(mission_id),)
        sql += " ORDER BY sequence"
        with self._lock:
            return [EventRecord.model_validate_json(data).model_copy(update={"sequence":seq}) for seq,data in self.connection.execute(sql,params)]

    def update_mission(self,v):
        with self._lock: self._update("missions",v.mission_id,v)
    def update_task(self,v):
        with self._lock: self._update("tasks",v.task_id,v)
    def save_attempt(self,v):
        with self._lock: self._insert("INSERT INTO attempts(id,mission_id,task_id,data) VALUES (?,?,?,?)",(str(v.attempt_id),str(v.mission_id),str(v.task_id),self._json(v)))
    def update_attempt(self,v):
        with self._lock: self._update("attempts",v.attempt_id,v)
    def get_attempt(self,i):
        with self._lock: return self._get("attempts",i,ExecutionAttempt)
    def list_attempts(self,mission_id=None):
        with self._lock: return self._list("attempts",ExecutionAttempt,mission_id)
    def save_checkpoint(self,v):
        with self._lock: self._insert("INSERT INTO checkpoints(id,mission_id,task_id,attempt_id,data) VALUES (?,?,?,?,?)",(str(v.checkpoint_id),str(v.mission_id),str(v.task_id),str(v.attempt_id),self._json(v)))
    def get_checkpoint(self,i):
        with self._lock: return self._get("checkpoints",i,TaskCheckpoint)
    def list_checkpoints(self,mission_id=None):
        with self._lock: return self._list("checkpoints",TaskCheckpoint,mission_id)
    def save_render_job(self,v):
        with self._lock: self._insert("INSERT INTO render_jobs(id,mission_id,task_id,data) VALUES (?,?,?,?)",(str(v.job_id),str(v.mission_id),str(v.task_id),self._json(v)))
    def update_render_job(self,v):
        with self._lock: self._update("render_jobs",v.job_id,v)
    def get_render_job(self,i):
        with self._lock: return self._get("render_jobs",i,RenderJob)
    def list_render_jobs(self,mission_id=None):
        with self._lock: return self._list("render_jobs",RenderJob,mission_id)
    def save_publishing_queue_item(self,v):
        with self._lock: self._insert("INSERT INTO publishing_queue(id,mission_id,data) VALUES (?,?,?)",(str(v.queue_item_id),str(v.mission_id),self._json(v)))
    def update_publishing_queue_item(self,v):
        with self._lock: self._update("publishing_queue",v.queue_item_id,v)
    def get_publishing_queue_item(self,i):
        with self._lock: return self._get("publishing_queue",i,PublishingQueueItem)
    def list_publishing_queue_items(self,mission_id=None):
        with self._lock: return self._list("publishing_queue",PublishingQueueItem,mission_id)

    def save_publication_record(self, v):
        with self._lock: self._insert("INSERT INTO publication_records(id,mission_id,queue_item_id,data) VALUES (?,?,?,?)",(str(v.publication_id),str(v.mission_id),str(v.queue_item_id),self._json(v)))

    def get_publication_record_by_id(self, publication_id: UUID) -> 'PublicationRecord' | None:
        row = self.connection.execute(
            'SELECT data FROM publication_records WHERE id = ?',
            (str(publication_id),),
        ).fetchone()
        return PublicationRecord.model_validate_json(row[0]) if row else None

    def get_publication_record(self, queue_item_id):
        with self._lock:
            row = self.connection.execute("SELECT data FROM publication_records WHERE queue_item_id = ?", (str(queue_item_id),)).fetchone()
            return PublicationRecord.model_validate_json(row[0]) if row else None

    def save_analytics_snapshot(self, snapshot: AnalyticsSnapshot) -> None:
        with self._lock:
            try:
                self.connection.execute(
                    "INSERT INTO analytics_snapshots(id, mission_id, publication_id, queue_item_id, destination, observed_at, imported_at, payload_hash, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(snapshot.analytics_snapshot_id),
                        str(snapshot.mission_id),
                        str(snapshot.publication_id),
                        str(snapshot.queue_item_id),
                        snapshot.destination,
                        snapshot.observed_at.isoformat(),
                        snapshot.imported_at.isoformat(),
                        snapshot.payload_hash,
                        snapshot.model_dump_json(exclude_none=True),
                    ),
                )
            except sqlite3.IntegrityError as error:
                error_msg = str(error).lower()
                expected_collision = (
                    "unique constraint failed: "
                    "analytics_snapshots.publication_id, "
                    "analytics_snapshots.observed_at"
                )
                if expected_collision in error_msg:
                    raise DuplicateRecordError(
                        "Analytics snapshot already exists for this "
                        "publication and observation time."
                    ) from error
                raise RepositoryIntegrityError(
                    f"Database integrity error: {error}"
                ) from error

    def find_snapshot_by_id(self, snapshot_id: UUID) -> AnalyticsSnapshot | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT data FROM analytics_snapshots WHERE id = ?",
                (str(snapshot_id),),
            ).fetchone()
            return AnalyticsSnapshot.model_validate_json(row[0]) if row else None

    def list_analytics_snapshots(self, publication_id: UUID) -> list[AnalyticsSnapshot]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT data FROM analytics_snapshots "
                "WHERE publication_id = ? "
                "ORDER BY observed_at DESC, imported_at DESC, id DESC",
                (str(publication_id),),
            ).fetchall()
            return [
                AnalyticsSnapshot.model_validate_json(row[0])
                for row in rows
            ]

    def find_observation_snapshot(self, publication_id: UUID, observed_at: datetime) -> AnalyticsSnapshot | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT data FROM analytics_snapshots "
                "WHERE publication_id = ? AND observed_at = ?",
                (str(publication_id), observed_at.isoformat()),
            ).fetchone()
            return AnalyticsSnapshot.model_validate_json(row[0]) if row else None
