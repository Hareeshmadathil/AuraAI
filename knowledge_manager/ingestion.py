"""Bounded, provenance-required knowledge ingestion."""
import re
from knowledge_manager.approvals import require_store_approval
from knowledge_manager.deduplication import classify_duplicate
from knowledge_manager.enums import ApprovalStatus,DuplicateKind,RetentionAction
from knowledge_manager.exceptions import KnowledgeManagerError
from knowledge_manager.models import KnowledgeIngestionRequest,KnowledgeIngestionResult,KnowledgeItem
from knowledge_manager.retention import decide
SECRET=re.compile(r"(?i)(api[_-]?key|authorization|bearer\s+[a-z0-9._-]+|password|secret|cookie|private[_-]?key)")
def ingest(repository,request:KnowledgeIngestionRequest)->KnowledgeIngestionResult:
    version=request.proposed_version
    serialized=version.model_dump_json()
    if len(serialized.encode("utf-8"))>200_000: raise KnowledgeManagerError("Knowledge import exceeds bounded size.",code="OVERSIZED_IMPORT")
    if SECRET.search(serialized): raise KnowledgeManagerError("Credential-shaped content is prohibited.",code="SECRET_PROHIBITED")
    if request.private_data_risk: raise KnowledgeManagerError("Private or sensitive data cannot be retained.",code="PRIVATE_DATA_PROHIBITED")
    if request.source_artifact_hash not in {x.artifact_hash for x in version.sources}: raise KnowledgeManagerError("Source provenance hash is missing.",code="PROVENANCE_REQUIRED")
    retention=decide(version,private_data=request.private_data_risk)
    if retention.action in {RetentionAction.PROHIBITED,RetentionAction.DISCARD}: raise KnowledgeManagerError("Retention policy prohibits storage.",code="RETENTION_PROHIBITED")
    if version.retention_policy.founder_approval_required: require_store_approval(version,request.founder_approval)
    duplicate,matched=classify_duplicate(version,list(repository.list_versions()))
    if duplicate in {DuplicateKind.EXACT,DuplicateKind.EQUIVALENT}: return KnowledgeIngestionResult(request_id=request.request_id,accepted=False,knowledge_id=matched.knowledge_id,version_id=matched.version_id,duplicate_kind=duplicate,reasons=["Existing immutable version already contains this knowledge"],founder_review_required=False)
    item=repository.get_item(version.knowledge_id)
    if item is None: repository.save_new(KnowledgeItem(knowledge_id=version.knowledge_id,current_version_id=version.version_id),version)
    else: repository.save_version(version)
    return KnowledgeIngestionResult(request_id=request.request_id,accepted=True,knowledge_id=version.knowledge_id,version_id=version.version_id,duplicate_kind=duplicate,reasons=["Validated provenance, retention, freshness, and approval"],founder_review_required=False)
