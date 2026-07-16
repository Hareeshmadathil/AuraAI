"""Stable vocabulary for deterministic intelligence decisions."""
from enum import StrEnum

class SignalSource(StrEnum):
    TREND_HUNTER="trend_hunter"; RESEARCH_DIRECTOR="research_director"; COMPETITOR_ANALYST="competitor_analyst"; AUDIENCE_ANALYST="audience_analyst"; SEO_DIRECTOR="seo_director"; PRODUCTION_RESEARCH="production_research"; WEB_INTELLIGENCE="web_intelligence"; FOUNDER="founder"; MISSION_ARTIFACT="mission_artifact"; OWNED_ANALYTICS="owned_analytics"; OFFICIAL_SUMMARY="official_summary"; FIXTURE="fixture"
class VerificationStatus(StrEnum): UNVERIFIED="unverified"; PARTIAL="partial"; VERIFIED="verified"; DISPUTED="disputed"
class AuthorityUse(StrEnum): FACTUAL="factual_support"; CONTEXT="contextual_support"; DEMAND="demand_signal_only"; PROHIBITED="not_usable"
class ContradictionStatus(StrEnum): NONE="none"; MINOR="minor_context_difference"; RESOLVABLE="resolvable"; MATERIAL="material_conflict"; REGION="region_specific"; VERSION="time_version_conflict"; UNRESOLVED="unresolved"; CORRECTED="withdrawn_or_corrected"
class FreshnessStatus(StrEnum): FRESH="fresh"; DUE="refresh_due"; STALE="stale"; EXPIRED="expired"; SUPERSEDED="superseded"; TIMELESS="timeless_with_review"; VERIFY="verification_required"
class PriorityBand(StrEnum): NOW="research_now"; SOON="research_soon"; MONITOR="monitor"; ARCHIVE="archive"; REJECT="reject"
class ResearchDepth(StrEnum): NONE="no_research_needed"; QUICK="quick_verification"; STANDARD="standard_research"; DEEP="deep_research"; MONITOR="continuous_monitoring"; FOUNDER="founder_manual_review"
class QueueStatus(StrEnum): DRAFTED="drafted"; AWAITING="awaiting_founder_approval"; APPROVED="approved"; HELD="held"; REJECTED="rejected"; READY="ready_for_web_plan"; COMPLETED="completed"; STALE="stale"; ARCHIVED="archived"
class RetentionAction(StrEnum): DISCARD="discard_after_run"; TEMPORARY="retain_temporarily"; UNTIL_EXPIRY="retain_until_expiry"; VERIFIED="retain_as_verified_knowledge"; ARCHIVE="archive_for_history"; FOUNDER="founder_review_required"
class FounderDecision(StrEnum): PENDING="pending"; APPROVED="approved"; HELD="held"; REJECTED="rejected"
