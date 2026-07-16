"""Repository interfaces and durable SQLite implementation."""
from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel

from mission_control.models import (
    ApprovalRequest, ArtifactRecord, EventRecord, MissionRecord, TaskRecord,
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


class InMemoryMissionControlRepository(MissionControlRepository):
    def __init__(self) -> None:
        self.missions: dict[UUID, MissionRecord] = {}
        self.tasks: dict[UUID, TaskRecord] = {}
        self.artifacts: dict[UUID, ArtifactRecord] = {}
        self.approvals: dict[UUID, ApprovalRequest] = {}
        self.events: list[EventRecord] = []

    def _insert(self, store: dict, key: UUID, value: T) -> None:
        if key in store:
            raise ValueError(f"Duplicate identity: {key}")
        store[key] = value.model_copy(deep=True)

    def save_mission(self, value): self._insert(self.missions, value.mission_id, value)
    def get_mission(self, mission_id): return self.missions.get(mission_id)
    def list_missions(self): return list(self.missions.values())
    def save_task(self, value): self._insert(self.tasks, value.task_id, value)
    def get_task(self, task_id): return self.tasks.get(task_id)
    def list_tasks(self, mission_id=None): return [v for v in self.tasks.values() if mission_id is None or v.mission_id == mission_id]
    def save_artifact(self, value): self._insert(self.artifacts, value.artifact_id, value)
    def list_artifacts(self, mission_id=None): return [v for v in self.artifacts.values() if mission_id is None or v.mission_id == mission_id]
    def save_approval(self, value): self.approvals[value.approval_id] = value.model_copy(deep=True)
    def get_approval(self, approval_id): return self.approvals.get(approval_id)
    def list_approvals(self, mission_id=None): return [v for v in self.approvals.values() if mission_id is None or v.mission_id == mission_id]
    def append_event(self, value):
        stored=value.model_copy(update={"sequence":len(self.events)+1}); self.events.append(stored); return stored
    def list_events(self, mission_id=None): return [v for v in self.events if mission_id is None or v.mission_id == mission_id]
    def update_mission(self, value): self.missions[value.mission_id] = value.model_copy(deep=True)
    def update_task(self, value): self.tasks[value.task_id] = value.model_copy(deep=True)


class SQLiteMissionControlRepository(MissionControlRepository):
    """SQLite JSON-record repository with foreign keys and atomic writes."""
    SCHEMA_VERSION = 1

    def __init__(self, database_path: Path, *, allowed_root: Path) -> None:
        root = allowed_root.resolve()
        path = database_path.resolve()
        if path != root and root not in path.parents:
            raise ValueError("Mission Control database path escapes allowed root.")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._initialize()

    def _initialize(self) -> None:
        with self.connection:
            self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS missions(id TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, mission_id TEXT NOT NULL REFERENCES missions(id), data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY, mission_id TEXT NOT NULL REFERENCES missions(id), task_id TEXT REFERENCES tasks(id), data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY, mission_id TEXT NOT NULL REFERENCES missions(id), task_id TEXT REFERENCES tasks(id), artifact_id TEXT REFERENCES artifacts(id), data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, mission_id TEXT REFERENCES missions(id), task_id TEXT REFERENCES tasks(id), event_type TEXT NOT NULL, data TEXT NOT NULL);
            """)
            row=self.connection.execute("SELECT version FROM schema_version").fetchone()
            if row is None: self.connection.execute("INSERT INTO schema_version(version) VALUES (?)",(self.SCHEMA_VERSION,))
            elif row[0] != self.SCHEMA_VERSION: raise RuntimeError("Unsupported Mission Control schema version.")

    @staticmethod
    def _json(value: BaseModel) -> str: return value.model_dump_json()
    def _insert(self, sql, params):
        try:
            with self.connection: self.connection.execute(sql, params)
        except sqlite3.IntegrityError as error: raise ValueError(str(error)) from error
    def _get(self, table, identity, model):
        row=self.connection.execute(f"SELECT data FROM {table} WHERE id = ?",(str(identity),)).fetchone()
        return model.model_validate_json(row[0]) if row else None
    def _list(self, table, model, mission_id=None):
        sql=f"SELECT data FROM {table}"; params=()
        if mission_id is not None: sql += " WHERE mission_id = ?"; params=(str(mission_id),)
        return [model.model_validate_json(row[0]) for row in self.connection.execute(sql,params)]
    def save_mission(self,v): self._insert("INSERT INTO missions(id,data) VALUES (?,?)",(str(v.mission_id),self._json(v)))
    def get_mission(self,i): return self._get("missions",i,MissionRecord)
    def list_missions(self): return self._list("missions",MissionRecord)
    def save_task(self,v): self._insert("INSERT INTO tasks(id,mission_id,data) VALUES (?,?,?)",(str(v.task_id),str(v.mission_id),self._json(v)))
    def get_task(self,i): return self._get("tasks",i,TaskRecord)
    def list_tasks(self,mission_id=None): return self._list("tasks",TaskRecord,mission_id)
    def save_artifact(self,v): self._insert("INSERT INTO artifacts(id,mission_id,task_id,data) VALUES (?,?,?,?)",(str(v.artifact_id),str(v.mission_id),str(v.task_id) if v.task_id else None,self._json(v)))
    def list_artifacts(self,mission_id=None): return self._list("artifacts",ArtifactRecord,mission_id)
    def save_approval(self,v):
        data=(str(v.mission_id),str(v.task_id) if v.task_id else None,str(v.artifact_id) if v.artifact_id else None,self._json(v),str(v.approval_id))
        with self.connection:
            self.connection.execute("INSERT INTO approvals(mission_id,task_id,artifact_id,data,id) VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",data)
    def get_approval(self,i): return self._get("approvals",i,ApprovalRequest)
    def list_approvals(self,mission_id=None): return self._list("approvals",ApprovalRequest,mission_id)
    def append_event(self,v):
        with self.connection:
            cursor=self.connection.execute("INSERT INTO events(id,mission_id,task_id,event_type,data) VALUES (?,?,?,?,?)",(str(v.event_id),str(v.mission_id) if v.mission_id else None,str(v.task_id) if v.task_id else None,v.event_type,self._json(v)))
        return v.model_copy(update={"sequence":cursor.lastrowid})
    def list_events(self,mission_id=None):
        sql="SELECT sequence,data FROM events"; params=()
        if mission_id is not None: sql += " WHERE mission_id = ?"; params=(str(mission_id),)
        sql += " ORDER BY sequence"
        return [EventRecord.model_validate_json(data).model_copy(update={"sequence":seq}) for seq,data in self.connection.execute(sql,params)]
    def _update(self,table,identity,value):
        with self.connection: self.connection.execute(f"UPDATE {table} SET data=? WHERE id=?",(self._json(value),str(identity)))
    def update_mission(self,v): self._update("missions",v.mission_id,v)
    def update_task(self,v): self._update("tasks",v.task_id,v)
