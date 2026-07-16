"""Injected knowledge persistence contract and defensive in-memory store."""
from collections.abc import Iterable
from typing import Protocol
from uuid import UUID
from knowledge_manager.exceptions import KnowledgeManagerError
from knowledge_manager.models import KnowledgeItem,KnowledgeVersion
class KnowledgeRepository(Protocol):
    def save_new(self,item:KnowledgeItem,version:KnowledgeVersion)->None: ...
    def save_version(self,version:KnowledgeVersion)->None: ...
    def get_item(self,knowledge_id:UUID)->KnowledgeItem|None: ...
    def get_version(self,version_id:UUID)->KnowledgeVersion|None: ...
    def list_versions(self,knowledge_id:UUID|None=None)->tuple[KnowledgeVersion,...]: ...
    def list_items(self)->tuple[KnowledgeItem,...]: ...
class InMemoryKnowledgeRepository:
    def __init__(self,versions:Iterable[KnowledgeVersion]=()):
        self._versions={v.version_id:v.model_copy(deep=True) for v in versions}; self._items={}
        for v in versions:
            item=self._items.get(v.knowledge_id)
            if item is None or self._versions[item.current_version_id].version<v.version: self._items[v.knowledge_id]=KnowledgeItem(knowledge_id=v.knowledge_id,current_version_id=v.version_id)
    def save_new(self,item,version):
        if item.knowledge_id in self._items or version.version_id in self._versions: raise KnowledgeManagerError("Duplicate knowledge identifier.",code="DUPLICATE_ID")
        if item.current_version_id!=version.version_id or item.knowledge_id!=version.knowledge_id: raise KnowledgeManagerError("Item/version relationship mismatch.",code="INVALID_LINEAGE")
        self._items[item.knowledge_id]=item.model_copy(deep=True); self._versions[version.version_id]=version.model_copy(deep=True)
    def save_version(self,version):
        item=self._items.get(version.knowledge_id)
        if item is None: raise KnowledgeManagerError("Knowledge item not found.",code="NOT_FOUND")
        if version.version_id in self._versions: raise KnowledgeManagerError("Historical versions are immutable.",code="IMMUTABLE_VERSION")
        parent=self._versions.get(version.parent_version_id)
        if parent is None or parent.knowledge_id!=version.knowledge_id or version.version!=parent.version+1: raise KnowledgeManagerError("Invalid version lineage.",code="INVALID_LINEAGE")
        self._versions[parent.version_id]=parent.model_copy(update={"superseded_by":version.version_id}); self._versions[version.version_id]=version.model_copy(deep=True); self._items[item.knowledge_id]=item.model_copy(update={"current_version_id":version.version_id})
    def get_item(self,knowledge_id):
        x=self._items.get(knowledge_id); return x.model_copy(deep=True) if x else None
    def get_version(self,version_id):
        x=self._versions.get(version_id); return x.model_copy(deep=True) if x else None
    def list_versions(self,knowledge_id=None): return tuple(x.model_copy(deep=True) for x in sorted((v for v in self._versions.values() if knowledge_id is None or v.knowledge_id==knowledge_id),key=lambda x:(str(x.knowledge_id),x.version)))
    def list_items(self): return tuple(x.model_copy(deep=True) for x in sorted(self._items.values(),key=lambda x:str(x.knowledge_id)))
