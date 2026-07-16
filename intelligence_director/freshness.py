"""Knowledge freshness and expiry policy."""
from datetime import timedelta
from core import utc_now
from intelligence_director.enums import FreshnessStatus
from intelligence_director.models import FreshnessAssessment,FreshnessPolicy,IntelligenceSignal
POLICIES={"pricing":FreshnessPolicy(category="pricing",refresh_hours=24,expiry_hours=72),"platform_policy":FreshnessPolicy(category="platform_policy",refresh_hours=24,expiry_hours=168),"breaking_news":FreshnessPolicy(category="breaking_news",refresh_hours=6,expiry_hours=24),"evergreen":FreshnessPolicy(category="evergreen",refresh_hours=2160,expiry_hours=8760,timeless=True)}
def assess_freshness(signal:IntelligenceSignal,category:str="general",*,now=None,replacement_version=None)->FreshnessAssessment:
    now=now or utc_now(); policy=POLICIES.get(category,FreshnessPolicy(category=category,refresh_hours=signal.freshness_window_hours,expiry_hours=signal.freshness_window_hours*2))
    refresh=signal.observed_at+timedelta(hours=policy.refresh_hours); expiry=signal.observed_at+timedelta(hours=policy.expiry_hours)
    status=FreshnessStatus.SUPERSEDED if replacement_version else FreshnessStatus.EXPIRED if now>=expiry else FreshnessStatus.STALE if now>=refresh+timedelta(hours=policy.refresh_hours/2) else FreshnessStatus.DUE if now>=refresh else FreshnessStatus.FRESH
    return FreshnessAssessment(item_id=signal.signal_id,observed_at=signal.observed_at,valid_from=signal.observed_at,last_verified_at=signal.observed_at if signal.verification_status.value=="verified" else None,refresh_after=refresh,expires_at=expiry,status=status,replacement_version=replacement_version,archive_reason="Superseded" if replacement_version else None)
