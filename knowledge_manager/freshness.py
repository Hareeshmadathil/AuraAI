"""Align stored knowledge with Intelligence Director freshness semantics."""
from core import utc_now
from knowledge_manager.enums import FreshnessStatus
from knowledge_manager.models import KnowledgeFreshness,RefreshQueueItem
def current_status(value:KnowledgeFreshness,*,superseded:bool=False,archived:bool=False,now=None)->FreshnessStatus:
    now=now or utc_now()
    if archived:return FreshnessStatus.ARCHIVED
    if superseded:return FreshnessStatus.SUPERSEDED
    if now>=value.expires_at:return FreshnessStatus.EXPIRED
    if now>=value.refresh_after:return FreshnessStatus.DUE if now<value.expires_at else FreshnessStatus.EXPIRED
    return FreshnessStatus.FRESH
def refresh_item(version,*,now=None)->RefreshQueueItem|None:
    status=current_status(version.freshness,superseded=version.superseded_by is not None,now=now)
    if status not in {FreshnessStatus.DUE,FreshnessStatus.STALE,FreshnessStatus.EXPIRED,FreshnessStatus.VERIFY}:return None
    return RefreshQueueItem(knowledge_id=version.knowledge_id,reason=status.value,priority=95 if status==FreshnessStatus.EXPIRED else 70,expected_source_type="current applicable primary source",deadline=version.freshness.expires_at,previous_verification_date=version.freshness.last_verified_at,risk_if_not_refreshed="Stale information could be misrepresented as current",intelligence_director_handoff="Create a founder-approved research candidate; do not execute it")
