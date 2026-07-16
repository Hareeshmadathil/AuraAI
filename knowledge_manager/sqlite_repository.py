"""Standard-library SQLite durable knowledge repository."""
from __future__ import annotations
import json,sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID
from knowledge_manager.exceptions import KnowledgeManagerError
from knowledge_manager.models import KnowledgeItem,KnowledgeVersion
SCHEMA_VERSION=1
class SQLiteKnowledgeRepository:
    def __init__(self,path:Path,*,allowed_root:Path):
        self.path=path.resolve(); self.root=allowed_root.resolve()
        try:self.path.relative_to(self.root)
        except ValueError as exc: raise KnowledgeManagerError("Database path escapes configured data root.",code="UNSAFE_DATABASE_PATH") from exc
    def initialize(self)->None:
        self.path.parent.mkdir(parents=True,exist_ok=True)
        try:
            with self._connect() as db:
                db.executescript("CREATE TABLE IF NOT EXISTS schema_meta(version INTEGER NOT NULL); CREATE TABLE IF NOT EXISTS knowledge_items(knowledge_id TEXT PRIMARY KEY,current_version_id TEXT NOT NULL,created_at TEXT NOT NULL,archived_at TEXT); CREATE TABLE IF NOT EXISTS knowledge_versions(version_id TEXT PRIMARY KEY,knowledge_id TEXT NOT NULL,version INTEGER NOT NULL,parent_version_id TEXT,topic TEXT NOT NULL,category TEXT NOT NULL,content_hash TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL,FOREIGN KEY(knowledge_id) REFERENCES knowledge_items(knowledge_id),UNIQUE(knowledge_id,version)); CREATE INDEX IF NOT EXISTS idx_knowledge_topic ON knowledge_versions(topic); CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge_versions(category);")
                row=db.execute("SELECT version FROM schema_meta LIMIT 1").fetchone()
                if row is None: db.execute("INSERT INTO schema_meta(version) VALUES (?)",(SCHEMA_VERSION,))
                elif row[0]!=SCHEMA_VERSION: raise KnowledgeManagerError("Unsupported knowledge schema version.",code="SCHEMA_VERSION")
        except sqlite3.DatabaseError as exc: raise KnowledgeManagerError("Knowledge database is unavailable or corrupt.",code="DATABASE_ERROR") from exc
    def schema_version(self)->int:
        with self._connect() as db:
            row=db.execute("SELECT version FROM schema_meta LIMIT 1").fetchone(); return int(row[0]) if row else 0
    def save_new(self,item,version):
        try:
            with self._connect() as db:
                db.execute("INSERT INTO knowledge_items VALUES (?,?,?,?)",(str(item.knowledge_id),str(item.current_version_id),item.created_at.isoformat(),item.archived_at.isoformat() if item.archived_at else None)); self._insert(db,version)
        except sqlite3.IntegrityError as exc: raise KnowledgeManagerError("Duplicate or invalid knowledge item.",code="DATABASE_CONFLICT") from exc
    def save_version(self,version):
        try:
            with self._connect() as db:
                row=db.execute("SELECT payload FROM knowledge_versions WHERE version_id=?",(str(version.parent_version_id),)).fetchone()
                if row is None: raise KnowledgeManagerError("Parent version not found.",code="INVALID_LINEAGE")
                parent=KnowledgeVersion.model_validate_json(row[0])
                if parent.knowledge_id!=version.knowledge_id or version.version!=parent.version+1: raise KnowledgeManagerError("Invalid version lineage.",code="INVALID_LINEAGE")
                updated=parent.model_copy(update={"superseded_by":version.version_id}); db.execute("UPDATE knowledge_versions SET payload=? WHERE version_id=?",(updated.model_dump_json(),str(parent.version_id))); self._insert(db,version); db.execute("UPDATE knowledge_items SET current_version_id=? WHERE knowledge_id=?",(str(version.version_id),str(version.knowledge_id)))
        except sqlite3.IntegrityError as exc: raise KnowledgeManagerError("Concurrent or duplicate knowledge update.",code="DATABASE_CONFLICT") from exc
    def get_item(self,knowledge_id):
        with self._connect() as db:
            row=db.execute("SELECT knowledge_id,current_version_id,created_at,archived_at FROM knowledge_items WHERE knowledge_id=?",(str(knowledge_id),)).fetchone()
        return KnowledgeItem(knowledge_id=row[0],current_version_id=row[1],created_at=row[2],archived_at=row[3]) if row else None
    def get_version(self,version_id):
        with self._connect() as db: row=db.execute("SELECT payload FROM knowledge_versions WHERE version_id=?",(str(version_id),)).fetchone()
        return KnowledgeVersion.model_validate_json(row[0]) if row else None
    def list_versions(self,knowledge_id=None):
        sql="SELECT payload FROM knowledge_versions"; params=()
        if knowledge_id is not None: sql+=" WHERE knowledge_id=?"; params=(str(knowledge_id),)
        sql+=" ORDER BY knowledge_id,version"
        with self._connect() as db: rows=db.execute(sql,params).fetchall()
        return tuple(KnowledgeVersion.model_validate_json(x[0]) for x in rows)
    def list_items(self):
        with self._connect() as db: rows=db.execute("SELECT knowledge_id,current_version_id,created_at,archived_at FROM knowledge_items ORDER BY knowledge_id").fetchall()
        return tuple(KnowledgeItem(knowledge_id=x[0],current_version_id=x[1],created_at=x[2],archived_at=x[3]) for x in rows)
    @contextmanager
    def _connect(self):
        db=None
        try:
            db=sqlite3.connect(self.path,timeout=5); db.execute("PRAGMA foreign_keys=ON"); yield db; db.commit()
        except sqlite3.Error as exc:
            if db is not None: db.rollback()
            raise KnowledgeManagerError("Knowledge database connection failed.",code="DATABASE_ERROR") from exc
        finally:
            if db is not None: db.close()
    @staticmethod
    def _insert(db,version): db.execute("INSERT INTO knowledge_versions VALUES (?,?,?,?,?,?,?,?,?)",(str(version.version_id),str(version.knowledge_id),version.version,str(version.parent_version_id) if version.parent_version_id else None,version.topic.normalized_name,version.category.value,version.content_hash,version.model_dump_json(),version.created_at.isoformat()))
