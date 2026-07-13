"""
Shared constants and enumerations for AuraAI Creator OS.

Values reused across agents, missions, workflows, decisions, services,
databases, APIs, and the dashboard should be defined here rather than
duplicated throughout the project.
"""

from __future__ import annotations

from enum import StrEnum


class AgentStatus(StrEnum):
    """Possible runtime states for an AuraAI employee-agent."""

    OFFLINE = "offline"
    IDLE = "idle"
    WORKING = "working"
    WAITING = "waiting"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    DISABLED = "disabled"


class JobStatus(StrEnum):
    """Possible states for an AuraAI task or workflow job."""

    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MissionStatus(StrEnum):
    """Lifecycle states for an AuraAI company mission."""

    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PLANNING = "planning"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ApprovalStatus(StrEnum):
    """Possible approval states for missions and workflow steps."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class DecisionType(StrEnum):
    """Categories of executive decisions made inside AuraAI."""

    STRATEGIC = "strategic"
    OPERATIONAL = "operational"
    FINANCIAL = "financial"
    PUBLISHING = "publishing"
    TECHNOLOGY = "technology"
    HIRING = "hiring"
    COMPLIANCE = "compliance"
    EMERGENCY = "emergency"


class DecisionOutcome(StrEnum):
    """Possible outcomes of an AuraAI executive decision."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    REQUIRES_RESEARCH = "requires_research"
    REQUIRES_USER_INPUT = "requires_user_input"
    ESCALATED = "escalated"
    AUTOMATED = "automated"


class DecisionReviewStatus(StrEnum):
    """Status of a later review of a completed decision."""

    NOT_REVIEWED = "not_reviewed"
    SUCCESSFUL = "successful"
    PARTIALLY_SUCCESSFUL = "partially_successful"
    UNSUCCESSFUL = "unsuccessful"
    INCONCLUSIVE = "inconclusive"


class TaskPriority(StrEnum):
    """Supported priority levels for missions and tasks."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class DepartmentName(StrEnum):
    """Official department identifiers used inside AuraAI."""

    EXECUTIVE = "executive"
    STRATEGY = "strategy"
    RESEARCH = "research"
    INTELLIGENCE = "intelligence"
    MARKETING = "marketing"
    EDITORIAL = "editorial"
    PRODUCTION = "production"
    DISTRIBUTION = "distribution"
    ANALYTICS = "analytics"
    REVENUE = "revenue"
    ENGINEERING = "engineering"


class ContentPlatform(StrEnum):
    """Platforms AuraAI can prepare content for."""

    YOUTUBE = "youtube"
    YOUTUBE_SHORTS = "youtube_shorts"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"


class ContentType(StrEnum):
    """Content formats supported by AuraAI."""

    LONG_FORM_VIDEO = "long_form_video"
    SHORT_VIDEO = "short_video"
    IMAGE_POST = "image_post"
    TEXT_POST = "text_post"
    ARTICLE = "article"


DEFAULT_AGENT_NAME = "Aura"
DEFAULT_TASK_PRIORITY = TaskPriority.NORMAL
DEFAULT_LOGGER_NAME = "auraai"
