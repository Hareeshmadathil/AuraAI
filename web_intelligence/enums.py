"""Enums for founder-controlled web intelligence."""
from enum import StrEnum

class OperatingMode(StrEnum):
    OFFLINE="offline"; PUBLIC_READ_ONLY="public_read_only"; INTERACTIVE_READ_ONLY="interactive_read_only"; FOUNDER_APPROVED_ACTION="founder_approved_action"
class AdapterKind(StrEnum):
    HTTP_PUBLIC="http_public"; CRAWL4AI="crawl4ai"; BROWSER_USE="browser_use"
class ApprovalState(StrEnum):
    PENDING="pending"; APPROVED="approved"; REJECTED="rejected"
class EvidenceClassification(StrEnum):
    OFFICIAL="official"; PUBLIC_PRIMARY="public_primary"; PUBLIC_SECONDARY="public_secondary"; CONFLICTING="conflicting"; UNVERIFIED="unverified"
class BrowserAction(StrEnum):
    NAVIGATE="navigate"; CLICK="click"; SCROLL="scroll"; PUBLIC_SEARCH="public_search"; SCREENSHOT="screenshot"
