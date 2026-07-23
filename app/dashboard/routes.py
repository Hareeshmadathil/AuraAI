"""FastAPI routes for the AuraAI local dashboard."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
import secrets
from typing import Annotated
from urllib.parse import parse_qs
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.dashboard.brand_models import create_brand_review, status_label
from app.dashboard.models import DashboardSnapshot
from app.dashboard.service import DashboardService
from production_research.service import ProductionResearchService
from mission_control.models import MissionControlProjection
from mission_control.models import ApprovalState
from app.dashboard.founder_review import build_founder_review
from app.dashboard.operations_v2 import build_operations_projection
from app.runtime.mission_commands import (
    MissionCommandService,
    RunNextTaskResult,
)
from mission_control.models import MissionRecord
from runtime_engine.recovery import RecoveryReport, RecoveryStatusProjection, build_recovery_projection


from enum import StrEnum

class FounderPublishDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"

class FounderPublishDecisionForm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csrf_token: str = Field(min_length=32, max_length=200)
    approval_id: UUID
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision: FounderPublishDecision
    reason: str | None = None

class ManualPublicationConfirmationForm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csrf_token: str = Field(min_length=32, max_length=200)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    external_url: str | None = None
    external_post_id: str | None = None
    confirmation_note: str | None = None


class AnalyticsImportForm(BaseModel):
    """Strict local analytics import form."""

    model_config = ConfigDict(extra="forbid")

    csrf_token: str = Field(min_length=32, max_length=200)
    observed_at: str = Field(min_length=1, max_length=50)
    views: int | None = Field(default=None, ge=0)
    impressions: int | None = Field(default=None, ge=0)
    likes: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)
    saves: int | None = Field(default=None, ge=0)
    clicks: int | None = Field(default=None, ge=0)
    watch_time_seconds: int | None = Field(default=None, ge=0)
    followers_gained: int | None = Field(default=None, ge=0)
    revenue_amount: Decimal | None = Field(default=None, ge=0)
    revenue_currency: str | None = None
    import_note: str | None = Field(default=None, max_length=2000)


class AnalyticsInterpretationForm(BaseModel):
    """CSRF-only request for authoritative deterministic interpretation."""

    model_config = ConfigDict(extra="forbid")

    csrf_token: str = Field(min_length=32, max_length=200)


class MissionLessonForm(BaseModel):
    """CSRF-only request for authoritative mission lesson creation."""

    model_config = ConfigDict(extra="forbid")

    csrf_token: str = Field(min_length=32, max_length=200)


class MissionRecommendationForm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    csrf_token: str = Field(min_length=32, max_length=200)


class MissionRecommendationDecisionForm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    csrf_token: str = Field(min_length=32, max_length=200)
    founder_note: str | None = Field(default=None, max_length=2000)


class RecommendationMissionCreationForm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    csrf_token: str = Field(min_length=32, max_length=200)


class FounderDecisionForm(BaseModel):
    """Strict hash-bound local founder mutation payload."""

    model_config = ConfigDict(extra="forbid")

    csrf_token: str = Field(min_length=32, max_length=200)
    approval_id: UUID
    task_id: UUID
    requested_action: str = Field(min_length=1, max_length=150)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision: ApprovalState
    reason: str = Field(min_length=1, max_length=2000)


class ResumeTaskRequest(BaseModel):
    """Optional checkpoint binding for a controlled resume command."""

    checkpoint_id: UUID | None = None


def get_dashboard_service(request: Request) -> DashboardService:
    """Resolve the application-scoped dashboard service."""

    return request.app.state.dashboard_service


DashboardServiceDependency = Annotated[
    DashboardService,
    Depends(get_dashboard_service),
]


def get_production_research_service(request: Request) -> ProductionResearchService:
    """Resolve the isolated offline production-research service."""

    return request.app.state.production_research_service


ProductionResearchServiceDependency = Annotated[
    ProductionResearchService,
    Depends(get_production_research_service),
]


def create_dashboard_router(template_directory: Path) -> APIRouter:
    """Create dashboard routes using an explicit template directory."""

    router = APIRouter()
    templates = Jinja2Templates(directory=template_directory)
    templates.env.filters["status_label"] = status_label

    def mission_control(request: Request):
        control = request.app.state.mission_control_service
        if control is None:
            raise HTTPException(status_code=503, detail="Mission Control is not configured.")
        return control

    def operations(request: Request):
        control = request.app.state.mission_control_service
        return build_operations_projection(control) if control is not None else None

    def mission_commands(request: Request) -> MissionCommandService:
        commands = request.app.state.mission_command_service
        if commands is None:
            raise HTTPException(
                status_code=503,
                detail="Mission commands are not configured.",
            )
        return commands

    def require_local(request: Request) -> None:
        host = request.client.host if request.client else ""
        if host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
            raise HTTPException(status_code=403, detail="Founder review is local-only.")

    def _raise_recommendation_http_error(error: Exception) -> None:
        from mission_control.models import (
            ConflictingDecisionError,
            ItemNotFoundError,
            MalformedCommandError,
            MismatchError,
            RepositoryConsistencyError,
            RepositoryIntegrityError,
            StaleContentError,
        )

        if isinstance(error, ItemNotFoundError):
            raise HTTPException(status_code=404, detail=str(error)) from error
        if isinstance(error, (MismatchError, MalformedCommandError)):
            raise HTTPException(status_code=422, detail=str(error)) from error
        if isinstance(
            error, (ConflictingDecisionError, StaleContentError)
        ):
            raise HTTPException(status_code=409, detail=str(error)) from error
        if isinstance(
            error, (RepositoryIntegrityError, RepositoryConsistencyError)
        ):
            raise HTTPException(
                status_code=503,
                detail="Mission recommendation persistence is unavailable.",
            ) from error
        raise error

    def parse_utc_timestamp(value: str) -> datetime:
        """Parse an explicitly timezone-qualified UTC ISO-8601 timestamp."""

        from mission_control.models import require_utc_datetime

        if not value.endswith("Z") and "+" not in value:
            raise ValueError("Timestamp must include an explicit UTC timezone.")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return require_utc_datetime(parsed, field_name="observed_at")

    def render(
        *,
        request: Request,
        service: DashboardService,
        template_name: str,
        page_title: str,
        active_path: str,
        extra_context: dict[str, object] | None = None,
    ) -> HTMLResponse:
        """Render one page from a shared dashboard snapshot."""

        context: dict[str, object] = {
            "snapshot": service.build_snapshot(),
            "page_title": page_title,
            "active_path": active_path,
        }
        context.update(extra_context or {})
        return templates.TemplateResponse(
            request=request,
            name=template_name,
            context=context,
        )

    @router.get("/", response_class=HTMLResponse)
    def dashboard_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render the AuraAI command center."""

        return render(
            request=request,
            service=service,
            template_name="dashboard.html",
            page_title="Command Center",
            active_path="/",
            extra_context={"operations": operations(request)},
        )

    @router.get("/employees", response_class=HTMLResponse)
    def employees_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render the grouped company roster."""

        return render(
            request=request,
            service=service,
            template_name="employees.html",
            page_title="Employees",
            active_path="/employees",
        )

    @router.get("/brand", response_class=HTMLResponse)
    def brand_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render deterministic local brand concepts for founder review."""

        return render(
            request=request,
            service=service,
            template_name="brand.html",
            page_title="Brand System",
            active_path="/brand",
            extra_context={"brand_review": create_brand_review()},
        )

    @router.get("/missions", response_class=HTMLResponse)
    def missions_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render supplied missions or an empty state."""

        return render(
            request=request,
            service=service,
            template_name="collection.html",
            page_title="Missions",
            active_path="/missions",
            extra_context={
                "collection_kind": "missions",
                "operations": operations(request),
            },
        )

    @router.get("/missions/{mission_id}/review", response_class=HTMLResponse)
    def founder_review_page(
        mission_id: UUID,
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render one canonical Mission Control mission for local review."""

        require_local(request)
        try:
            review = build_founder_review(mission_control(request), mission_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Mission was not found.") from error
        csrf_token = secrets.token_urlsafe(32)
        source_lineage = (
            mission_control(request).repository
            .find_successor_mission_lineage(mission_id)
        )
        response = render(
            request=request,
            service=service,
            template_name="founder_review.html",
            page_title="Founder Mission Review",
            active_path="/missions",
            extra_context={
                "review": review,
                "csrf_token": csrf_token,
                "source_lineage": source_lineage,
            },
        )
        response.set_cookie(
            "auraai_csrf",
            csrf_token,
            httponly=True,
            samesite="strict",
            secure=False,
            max_age=1800,
        )
        return response

    @router.post("/missions/{mission_id}/review/decision")
    async def founder_review_decision(
        mission_id: UUID,
        request: Request,
    ) -> RedirectResponse:
        """Apply a POST-only, CSRF-protected, exact-bound founder decision."""

        require_local(request)
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        if content_type != "application/x-www-form-urlencoded":
            raise HTTPException(status_code=415, detail="Unsupported form content type.")
        body = await request.body()
        if len(body) > 12_000:
            raise HTTPException(status_code=413, detail="Founder decision form is too large.")
        try:
            values = parse_qs(body.decode("utf-8"), keep_blank_values=True, strict_parsing=True)
            if any(len(value) != 1 for value in values.values()):
                raise ValueError("Repeated form field.")
            form = FounderDecisionForm.model_validate(
                {key: value[0] for key, value in values.items()}
            )
        except (UnicodeDecodeError, ValueError, ValidationError) as error:
            raise HTTPException(status_code=422, detail="Invalid founder decision form.") from error
        cookie_token = request.cookies.get("auraai_csrf", "")
        if not cookie_token or not secrets.compare_digest(cookie_token, form.csrf_token):
            raise HTTPException(status_code=403, detail="CSRF validation failed.")
        if form.decision not in {
            ApprovalState.APPROVED,
            ApprovalState.REJECTED,
            ApprovalState.REVISION_REQUESTED,
        }:
            raise HTTPException(status_code=422, detail="Invalid founder decision.")
        try:
            mission_control(request).apply_founder_decision(
                form.approval_id,
                form.decision,
                mission_id=mission_id,
                task_id=form.task_id,
                requested_action=form.requested_action,
                content_hash=form.content_hash,
                reason=form.reason,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Mission review record was not found.") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        return RedirectResponse(
            url=f"/missions/{mission_id}/review",
            status_code=303,
        )

    @router.post("/missions/{mission_id}/publishing-queue/{queue_item_id}/decision")
    async def founder_publish_decision(
        mission_id: UUID,
        queue_item_id: UUID,
        request: Request,
    ) -> RedirectResponse:
        """Apply a POST-only, CSRF-protected founder publish decision."""
        from mission_control.models import (
            ItemNotFoundError,
            StaleContentError,
            ConflictingDecisionError,
            MalformedCommandError,
            MismatchError,
        )

        require_local(request)
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        if content_type != "application/x-www-form-urlencoded":
            raise HTTPException(status_code=415, detail="Unsupported form content type.")
        body = await request.body()
        if len(body) > 12_000:
            raise HTTPException(status_code=413, detail="Founder decision form is too large.")
        try:
            values = parse_qs(body.decode("utf-8"), keep_blank_values=True, strict_parsing=True)
            if any(len(value) != 1 for value in values.values()):
                raise ValueError("Repeated form field.")
            form = FounderPublishDecisionForm.model_validate(
                {key: value[0] for key, value in values.items()}
            )
        except (UnicodeDecodeError, ValueError, ValidationError) as error:
            raise HTTPException(status_code=422, detail=f"Invalid founder publish decision form: {error}") from error

        cookie_token = request.cookies.get("auraai_csrf", "")
        if not cookie_token or not secrets.compare_digest(cookie_token, form.csrf_token):
            raise HTTPException(status_code=403, detail="CSRF validation failed.")

        try:
            mission_commands(request).submit_publish_decision(
                mission_id=mission_id,
                queue_item_id=queue_item_id,
                approval_id=form.approval_id,
                content_hash=form.content_hash,
                decision=form.decision,
                reason=form.reason,
                actor="Local Founder",
            )
        except ItemNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (StaleContentError, ConflictingDecisionError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (MalformedCommandError, MismatchError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        return RedirectResponse(
            url="/distribution",
            status_code=303,
        )

    @router.get("/workflows", response_class=HTMLResponse)
    def workflows_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render supplied workflows or an empty state."""

        return render(
            request=request,
            service=service,
            template_name="collection.html",
            page_title="Workflows",
            active_path="/workflows",
            extra_context={"collection_kind": "workflows"},
        )

    @router.get("/decisions", response_class=HTMLResponse)
    def decisions_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render supplied decisions or an empty state."""

        return render(
            request=request,
            service=service,
            template_name="collection.html",
            page_title="Decisions",
            active_path="/decisions",
            extra_context={"collection_kind": "decisions"},
        )

    @router.get("/system", response_class=HTMLResponse)
    def system_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render local system health information."""

        return render(
            request=request,
            service=service,
            template_name="system.html",
            page_title="System",
            active_path="/system",
        )

    @router.get("/production", response_class=HTMLResponse)
    def production_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render the structured production package or an empty state."""

        return render(
            request=request,
            service=service,
            template_name="production.html",
            page_title="Production",
            active_path="/production",
        )

    @router.get("/intelligence", response_class=HTMLResponse)
    def intelligence_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render all deterministic Intelligence reports."""

        return render(
            request=request,
            service=service,
            template_name="intelligence.html",
            page_title="Intelligence",
            active_path="/intelligence",
        )

    @router.get("/renders", response_class=HTMLResponse)
    def renders_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render local-review artifacts or a neutral empty state."""

        return render(
            request=request,
            service=service,
            template_name="renders.html",
            page_title="Renders",
            active_path="/renders",
        )

    @router.get("/creative-quality", response_class=HTMLResponse)
    def creative_quality_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render deterministic quality scores, gate, and revisions."""

        return render(
            request=request,
            service=service,
            template_name="creative_quality.html",
            page_title="Creative Quality",
            active_path="/creative-quality",
        )

    @router.get("/distribution", response_class=HTMLResponse)
    def distribution_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render local publish preparation and founder approval state."""

        require_local(request)
        csrf_token = secrets.token_urlsafe(32)
        response = render(
            request=request,
            service=service,
            template_name="distribution.html",
            page_title="Distribution",
            active_path="/distribution",
            extra_context={
                "operations": operations(request),
                "csrf_token": csrf_token,
            },
        )
        response.set_cookie(
            "auraai_csrf",
            csrf_token,
            httponly=True,
            samesite="strict",
            secure=False,
            max_age=1800,
        )
        return response

    @router.get("/analytics", response_class=HTMLResponse)
    def analytics_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render manually supplied metrics and calculated rates."""

        return render(
            request=request,
            service=service,
            template_name="analytics.html",
            page_title="Analytics",
            active_path="/analytics",
        )

    @router.get("/learning", response_class=HTMLResponse)
    def learning_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render deterministic learning recommendations."""

        return render(
            request=request,
            service=service,
            template_name="learning.html",
            page_title="Learning",
            active_path="/learning",
        )

    @router.get("/providers", response_class=HTMLResponse)
    def providers_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render provider availability, fallback, cache, and safe usage."""

        return render(
            request=request,
            service=service,
            template_name="providers.html",
            page_title="AI Providers",
            active_path="/providers",
        )

    @router.get("/production-research", response_class=HTMLResponse)
    def production_research_page(
        request: Request,
        service: DashboardServiceDependency,
        research_service: ProductionResearchServiceDependency,
    ) -> HTMLResponse:
        """Render the manually maintained offline provider research catalog."""

        return render(
            request=request,
            service=service,
            template_name="production_research.html",
            page_title="AI Production Research",
            active_path="/production-research",
            extra_context={"research_report": research_service.build_report()},
        )

    @router.get("/mission-pilot", response_class=HTMLResponse)
    def mission_pilot_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render the safe Real Content Pilot founder-review package."""

        return render(
            request=request,
            service=service,
            template_name="mission_pilot.html",
            page_title="Mission Pilot",
            active_path="/mission-pilot",
        )

    @router.get("/first-content-mission", response_class=HTMLResponse)
    def first_content_mission_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render the first complete founder content-review package."""

        return render(
            request=request,
            service=service,
            template_name="first_content_mission.html",
            page_title="First Content Mission",
            active_path="/first-content-mission",
        )

    @router.get("/private-video-production", response_class=HTMLResponse)
    def private_video_production_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render safe private-video production readiness and approval state."""

        return render(
            request=request,
            service=service,
            template_name="private_video_production.html",
            page_title="Private Video Production",
            active_path="/private-video-production",
        )

    @router.get("/production-connector", response_class=HTMLResponse)
    def production_connector_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render deterministic offline connector readiness without script text."""
        from production_connector.composition import create_demo_service

        return render(
            request=request,
            service=service,
            template_name="production_connector.html",
            page_title="Production Connector",
            active_path="/production-connector",
            extra_context={"connector": create_demo_service().status()},
        )

    @router.get("/web-intelligence", response_class=HTMLResponse)
    def web_intelligence_page(request: Request, service: DashboardServiceDependency) -> HTMLResponse:
        """Render the offline founder-controlled web intelligence status."""
        from web_intelligence.composition import create_offline_demo_service
        return render(request=request,service=service,template_name="web_intelligence.html",
            page_title="Web Intelligence",active_path="/web-intelligence",
            extra_context={"web":create_offline_demo_service().dashboard_state()})

    @router.get("/intelligence-director", response_class=HTMLResponse)
    def intelligence_director_page(request: Request, service: DashboardServiceDependency) -> HTMLResponse:
        """Render safe deterministic intelligence recommendations."""
        from intelligence_director.composition import create_demo_result
        return render(request=request,service=service,template_name="intelligence_director.html",
            page_title="Intelligence Director",active_path="/intelligence-director",
            extra_context={"director":create_demo_result()})

    @router.get("/knowledge-manager", response_class=HTMLResponse)
    def knowledge_manager_page(request: Request, service: DashboardServiceDependency) -> HTMLResponse:
        """Render the in-memory, founder-controlled knowledge demo."""
        from knowledge_manager.composition import create_demo_result
        return render(request=request,service=service,template_name="knowledge_manager.html",
            page_title="Knowledge Manager",active_path="/knowledge-manager",
            extra_context={"knowledge":create_demo_result(),"schema_version":1,"storage_status":"in-memory demo"})

    @router.get("/artifacts/{artifact_id}")
    def render_artifact(
        artifact_id: UUID,
        service: DashboardServiceDependency,
    ) -> FileResponse:
        """Serve a registered artifact ID; arbitrary paths are never accepted."""

        artifact = service.get_render_artifact(artifact_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Render artifact not found.")
        inline_types = {"video/mp4", "image/png", "image/jpeg"}
        return FileResponse(
            artifact.path,
            media_type=artifact.mime_type,
            filename=artifact.path.name,
            content_disposition_type=(
                "inline" if artifact.mime_type in inline_types else "attachment"
            ),
        )

    @router.get("/research", response_class=HTMLResponse)
    @router.get("/marketing", response_class=HTMLResponse)
    def placeholder_page(
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render non-404 placeholders for planned dashboard sections."""

        section_name = request.url.path.removeprefix("/")
        title = section_name.title()
        return render(
            request=request,
            service=service,
            template_name="collection.html",
            page_title=title,
            active_path=f"/{section_name}",
            extra_context={"collection_kind": "placeholder"},
        )

    @router.get("/health")
    def health(service: DashboardServiceDependency) -> dict[str, object]:
        """Report local web-service health as structured JSON."""

        system_health = service.build_snapshot().system_health
        return {
            "status": system_health.status.value,
            "service": "AuraAI Dashboard",
            "operational": system_health.web_service_operational,
            "test_status": system_health.test_status,
        }

    @router.get("/api/dashboard", response_model=DashboardSnapshot)
    def dashboard_api(
        service: DashboardServiceDependency,
    ) -> DashboardSnapshot:
        """Return the current dashboard snapshot as JSON."""

        return service.build_snapshot()

    @router.get(
        "/api/mission-control",
        response_model=MissionControlProjection,
    )
    def mission_control_api(request: Request) -> MissionControlProjection:
        """Return the injected authoritative Mission Control projection."""

        return mission_control(request).projection()

    @router.post(
        "/api/missions",
        response_model=MissionRecord,
        status_code=201,
    )
    def submit_mission(
        mission: MissionRecord,
        request: Request,
    ) -> MissionRecord:
        """Submit a mission through the shared authoritative runtime."""

        require_local(request)
        try:
            return mission_commands(request).submit(mission)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @router.post("/missions/{mission_id}/publishing-queue/{queue_item_id}/confirm-publication")
    async def manual_publish_confirmation(
        mission_id: UUID,
        queue_item_id: UUID,
        request: Request,
    ) -> RedirectResponse:
        """Apply a POST-only, CSRF-protected manual publication confirmation."""
        from mission_control.models import (
            ItemNotFoundError,
            StaleContentError,
            ConflictingDecisionError,
            MalformedCommandError,
            MismatchError,
        )

        require_local(request)
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        if content_type != "application/x-www-form-urlencoded":
            raise HTTPException(status_code=415, detail="Unsupported form content type.")
        body = await request.body()
        if len(body) > 12_000:
            raise HTTPException(status_code=413, detail="Confirmation form is too large.")
        try:
            values = parse_qs(body.decode("utf-8"), keep_blank_values=True, strict_parsing=True)
            if any(len(value) != 1 for value in values.values()):
                raise ValueError("Repeated form field.")
            form = ManualPublicationConfirmationForm.model_validate(
                {key: value[0] for key, value in values.items()}
            )
        except (UnicodeDecodeError, ValueError, ValidationError) as error:
            raise HTTPException(status_code=422, detail=f"Invalid confirmation form: {error}") from error

        cookie_token = request.cookies.get("auraai_csrf", "")
        if not cookie_token or not secrets.compare_digest(cookie_token, form.csrf_token):
            raise HTTPException(status_code=403, detail="CSRF validation failed.")

        try:
            mission_commands(request).confirm_manual_publication(
                mission_id=mission_id,
                queue_item_id=queue_item_id,
                content_hash=form.content_hash,
                external_url=form.external_url,
                external_post_id=form.external_post_id,
                confirmation_note=form.confirmation_note,
                actor="Local Founder",
            )
        except ItemNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (StaleContentError, ConflictingDecisionError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (MismatchError, MalformedCommandError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

        return RedirectResponse(
            url=f"/missions/{mission_id}/distribution",
            status_code=303,
        )


    @router.post("/missions/{mission_id}/publications/{publication_id}/analytics/import", response_class=RedirectResponse)
    async def import_analytics_snapshot(
        mission_id: UUID,
        publication_id: UUID,
        request: Request,
    ) -> RedirectResponse:
        from mission_control.models import (
            ItemNotFoundError,
            StaleContentError,
            ConflictingDecisionError,
            MalformedCommandError,
            MismatchError,
            AnalyticsMetrics,
            RepositoryConsistencyError,
            RepositoryIntegrityError,
        )

        require_local(request)
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        if content_type != "application/x-www-form-urlencoded":
            raise HTTPException(status_code=415, detail="Unsupported form content type.")
        body = await request.body()
        if len(body) > 12_000:
            raise HTTPException(status_code=413, detail="Form is too large.")
        try:
            values = parse_qs(body.decode("utf-8"), keep_blank_values=True, strict_parsing=True)
            if any(len(value) != 1 for value in values.values()):
                raise ValueError("Repeated form field.")
            form_data = {key: value[0] for key, value in values.items()}
            for key, value in tuple(form_data.items()):
                if key not in {"csrf_token", "observed_at"} and not value.strip():
                    form_data[key] = None
            form = AnalyticsImportForm.model_validate(form_data)
            cookie_token = request.cookies.get("auraai_csrf", "")
            if not cookie_token or not secrets.compare_digest(
                cookie_token,
                form.csrf_token,
            ):
                raise HTTPException(
                    status_code=403,
                    detail="CSRF validation failed.",
                )
            observed_at = parse_utc_timestamp(form.observed_at)
            metrics = AnalyticsMetrics.model_validate(
                form.model_dump(
                    exclude={"csrf_token", "observed_at"},
                    exclude_none=True,
                )
            )
        except HTTPException:
            raise
        except (UnicodeDecodeError, ValueError, ValidationError, KeyError) as error:
            raise HTTPException(
                status_code=422,
                detail="Invalid analytics import form.",
            ) from error

        try:
            mission_commands(request).import_analytics_snapshot(
                mission_id=mission_id,
                publication_id=publication_id,
                observed_at=observed_at,
                metrics=metrics,
                actor="Local Founder",
            )
        except ItemNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (ConflictingDecisionError, StaleContentError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (MismatchError, MalformedCommandError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except (RepositoryIntegrityError, RepositoryConsistencyError) as error:
            raise HTTPException(
                status_code=503,
                detail="Analytics persistence is temporarily unavailable.",
            ) from error

        return RedirectResponse(
            url=request.url_for("distribution_page").include_query_params(mission=mission_id),
            status_code=303,
        )

    @router.get("/missions/{mission_id}/publications/{publication_id}/analytics/import", response_class=HTMLResponse)
    def analytics_import_page(
        mission_id: UUID,
        publication_id: UUID,
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render one persisted publication's local analytics import page."""

        require_local(request)
        control = mission_control(request)
        mission = control.repository.get_mission(mission_id)
        if mission is None:
            raise HTTPException(status_code=404, detail="Mission was not found.")
        publication = control.repository.get_publication_record_by_id(
            publication_id
        )
        if publication is None:
            raise HTTPException(
                status_code=404,
                detail="Publication was not found.",
            )
        if publication.mission_id != mission_id:
            raise HTTPException(
                status_code=422,
                detail="Publication mission ID mismatch.",
            )
        queue_item = control.repository.get_publishing_queue_item(
            publication.queue_item_id
        )
        if queue_item is None:
            raise HTTPException(
                status_code=404,
                detail="Publishing queue item was not found.",
            )
        projection = build_operations_projection(control)
        queue_view = next(
            (
                item
                for item in projection.publishing_queue
                if item.publication_id == publication_id
                and item.mission_id == mission_id
            ),
            None,
        )
        if queue_view is None:
            raise HTTPException(
                status_code=404,
                detail="Publication was not found in the dashboard projection.",
            )

        csrf_token = secrets.token_urlsafe(32)
        response = render(
            request=request,
            service=service,
            template_name="analytics_import.html",
            page_title="Import Analytics",
            active_path="/distribution",
            extra_context={
                "mission": mission,
                "publication": publication,
                "queue_item": queue_view,
                "analytics": queue_view.analytics,
                "csrf_token": csrf_token,
            },
        )
        response.set_cookie(
            "auraai_csrf",
            csrf_token,
            httponly=True,
            samesite="strict",
            secure=False,
            max_age=1800,
        )
        return response

    @router.post(
        "/missions/{mission_id}/analytics/{analytics_snapshot_id}/interpret",
        response_class=RedirectResponse,
    )
    async def interpret_analytics_snapshot(
        mission_id: UUID,
        analytics_snapshot_id: UUID,
        request: Request,
    ) -> RedirectResponse:
        """Create one deterministic interpretation through Mission Control."""

        from mission_control.models import (
            ConflictingDecisionError,
            ItemNotFoundError,
            MalformedCommandError,
            MismatchError,
            RepositoryConsistencyError,
            RepositoryIntegrityError,
            StaleContentError,
        )

        require_local(request)
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        if content_type != "application/x-www-form-urlencoded":
            raise HTTPException(status_code=415, detail="Unsupported form content type.")
        body = await request.body()
        if len(body) > 12_000:
            raise HTTPException(status_code=413, detail="Form is too large.")
        try:
            values = parse_qs(
                body.decode("utf-8"),
                keep_blank_values=True,
                strict_parsing=True,
            )
            if any(len(value) != 1 for value in values.values()):
                raise ValueError("Repeated form field.")
            form = AnalyticsInterpretationForm.model_validate(
                {key: value[0] for key, value in values.items()}
            )
        except (UnicodeDecodeError, ValueError, ValidationError) as error:
            raise HTTPException(
                status_code=422,
                detail="Invalid analytics interpretation form.",
            ) from error
        cookie_token = request.cookies.get("auraai_csrf", "")
        if not cookie_token or not secrets.compare_digest(
            cookie_token,
            form.csrf_token,
        ):
            raise HTTPException(status_code=403, detail="CSRF validation failed.")
        try:
            mission_commands(request).interpret_analytics_snapshot(
                mission_id=mission_id,
                analytics_snapshot_id=analytics_snapshot_id,
                actor="Local Founder",
            )
        except ItemNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (ConflictingDecisionError, StaleContentError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (MismatchError, MalformedCommandError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except (RepositoryIntegrityError, RepositoryConsistencyError) as error:
            raise HTTPException(
                status_code=503,
                detail="Analytics interpretation persistence is unavailable.",
            ) from error
        return RedirectResponse(
            url=request.url_for(
                "analytics_interpretation_page",
                mission_id=mission_id,
                analytics_snapshot_id=analytics_snapshot_id,
            ),
            status_code=303,
        )

    @router.get(
        "/missions/{mission_id}/analytics/{analytics_snapshot_id}/interpretation",
        response_class=HTMLResponse,
    )
    def analytics_interpretation_page(
        mission_id: UUID,
        analytics_snapshot_id: UUID,
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render durable evidence and deterministic interpretations."""

        require_local(request)
        control = mission_control(request)
        mission = control.repository.get_mission(mission_id)
        if mission is None:
            raise HTTPException(status_code=404, detail="Mission was not found.")
        snapshot = control.repository.find_snapshot_by_id(analytics_snapshot_id)
        if snapshot is None:
            raise HTTPException(
                status_code=404,
                detail="Analytics snapshot was not found.",
            )
        if snapshot.mission_id != mission_id:
            raise HTTPException(
                status_code=422,
                detail="Analytics snapshot mission ID mismatch.",
            )
        publication = control.repository.get_publication_record_by_id(
            snapshot.publication_id
        )
        if publication is None:
            raise HTTPException(status_code=404, detail="Publication was not found.")
        interpretations = [
            item
            for item in control.repository.list_analytics_interpretations(
                snapshot.publication_id
            )
            if item.analytics_snapshot_id == analytics_snapshot_id
        ]
        csrf_token = secrets.token_urlsafe(32)
        response = render(
            request=request,
            service=service,
            template_name="analytics_interpretation.html",
            page_title="Analytics Interpretation",
            active_path="/analytics",
            extra_context={
                "mission": mission,
                "publication": publication,
                "source_snapshot": snapshot,
                "latest_interpretation": (
                    interpretations[0] if interpretations else None
                ),
                "interpretation_history": interpretations[1:],
                "interpretation_count": len(interpretations),
                "csrf_token": csrf_token,
            },
        )
        response.set_cookie(
            "auraai_csrf",
            csrf_token,
            httponly=True,
            samesite="strict",
            secure=False,
            max_age=1800,
        )
        return response

    @router.post(
        "/missions/{mission_id}/analytics/interpretations/"
        "{analytics_interpretation_id}/lesson",
        response_class=RedirectResponse,
    )
    async def create_mission_lesson(
        mission_id: UUID,
        analytics_interpretation_id: UUID,
        request: Request,
    ) -> RedirectResponse:
        """Create one deterministic lesson through Mission Control."""

        from mission_control.models import (
            ConflictingDecisionError,
            ItemNotFoundError,
            MalformedCommandError,
            MismatchError,
            RepositoryConsistencyError,
            RepositoryIntegrityError,
            StaleContentError,
        )

        require_local(request)
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        if content_type != "application/x-www-form-urlencoded":
            raise HTTPException(
                status_code=415,
                detail="Unsupported form content type.",
            )
        body = await request.body()
        if len(body) > 12_000:
            raise HTTPException(status_code=413, detail="Form is too large.")
        try:
            values = parse_qs(
                body.decode("utf-8"),
                keep_blank_values=True,
                strict_parsing=True,
            )
            if any(len(value) != 1 for value in values.values()):
                raise ValueError("Repeated form field.")
            form = MissionLessonForm.model_validate(
                {key: value[0] for key, value in values.items()}
            )
        except (UnicodeDecodeError, ValueError, ValidationError) as error:
            raise HTTPException(
                status_code=422,
                detail="Invalid mission lesson form.",
            ) from error
        cookie_token = request.cookies.get("auraai_csrf", "")
        if not cookie_token or not secrets.compare_digest(
            cookie_token,
            form.csrf_token,
        ):
            raise HTTPException(status_code=403, detail="CSRF validation failed.")
        try:
            mission_commands(request).create_mission_lesson(
                mission_id=mission_id,
                analytics_interpretation_id=analytics_interpretation_id,
                actor="Local Founder",
            )
        except ItemNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (ConflictingDecisionError, StaleContentError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (MismatchError, MalformedCommandError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except (RepositoryIntegrityError, RepositoryConsistencyError) as error:
            raise HTTPException(
                status_code=503,
                detail="Mission lesson persistence is unavailable.",
            ) from error
        return RedirectResponse(
            url=request.url_for(
                "mission_lesson_page",
                mission_id=mission_id,
                analytics_interpretation_id=analytics_interpretation_id,
            ),
            status_code=303,
        )

    @router.get(
        "/missions/{mission_id}/analytics/interpretations/"
        "{analytics_interpretation_id}/lesson",
        response_class=HTMLResponse,
    )
    def mission_lesson_page(
        mission_id: UUID,
        analytics_interpretation_id: UUID,
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        """Render the durable interpretation and its mission lesson history."""

        require_local(request)
        control = mission_control(request)
        mission = control.repository.get_mission(mission_id)
        if mission is None:
            raise HTTPException(status_code=404, detail="Mission was not found.")
        interpretation = (
            control.repository.find_interpretation_by_id(
                analytics_interpretation_id
            )
        )
        if interpretation is None:
            raise HTTPException(
                status_code=404,
                detail="Analytics interpretation was not found.",
            )
        if interpretation.mission_id != mission_id:
            raise HTTPException(
                status_code=422,
                detail="Analytics interpretation mission ID mismatch.",
            )
        snapshot = control.repository.find_snapshot_by_id(
            interpretation.analytics_snapshot_id
        )
        if snapshot is None:
            raise HTTPException(
                status_code=404,
                detail="Analytics snapshot was not found.",
            )
        publication = control.repository.get_publication_record_by_id(
            interpretation.publication_id
        )
        if publication is None:
            raise HTTPException(
                status_code=404,
                detail="Publication was not found.",
            )
        lessons = [
            item
            for item in control.repository.list_mission_lessons(
                interpretation.publication_id
            )
            if item.analytics_interpretation_id
            == analytics_interpretation_id
        ]
        csrf_token = secrets.token_urlsafe(32)
        response = render(
            request=request,
            service=service,
            template_name="mission_lesson.html",
            page_title="Mission Lesson",
            active_path="/analytics",
            extra_context={
                "mission": mission,
                "publication": publication,
                "source_snapshot": snapshot,
                "source_interpretation": interpretation,
                "latest_lesson": lessons[0] if lessons else None,
                "lesson_history": lessons[1:],
                "lesson_count": len(lessons),
                "csrf_token": csrf_token,
            },
        )
        response.set_cookie(
            "auraai_csrf",
            csrf_token,
            httponly=True,
            samesite="strict",
            secure=False,
            max_age=1800,
        )
        return response

    @router.post(
        "/missions/{mission_id}/lessons/{mission_lesson_id}/recommendation",
        response_class=RedirectResponse,
    )
    async def create_mission_recommendation(
        mission_id: UUID,
        mission_lesson_id: UUID,
        request: Request,
    ) -> RedirectResponse:
        """Create an advisory recommendation through Mission Control."""

        from mission_control.models import (
            ConflictingDecisionError,
            ItemNotFoundError,
            MalformedCommandError,
            MismatchError,
            RepositoryConsistencyError,
            RepositoryIntegrityError,
            StaleContentError,
        )

        require_local(request)
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        if content_type != "application/x-www-form-urlencoded":
            raise HTTPException(status_code=415, detail="Unsupported form content type.")
        body = await request.body()
        if len(body) > 12_000:
            raise HTTPException(status_code=413, detail="Form is too large.")
        try:
            values = parse_qs(
                body.decode("utf-8"), keep_blank_values=True,
                strict_parsing=True,
            )
            if any(len(value) != 1 for value in values.values()):
                raise ValueError("Repeated form field.")
            form = MissionRecommendationForm.model_validate(
                {key: value[0] for key, value in values.items()}
            )
        except (UnicodeDecodeError, ValueError, ValidationError) as error:
            raise HTTPException(
                status_code=422, detail="Invalid recommendation form."
            ) from error
        if not secrets.compare_digest(
            request.cookies.get("auraai_csrf", ""), form.csrf_token
        ):
            raise HTTPException(status_code=403, detail="CSRF validation failed.")
        try:
            mission_commands(request).create_mission_recommendation(
                mission_id=mission_id,
                mission_lesson_id=mission_lesson_id,
                actor="Local Founder",
            )
        except (
            ConflictingDecisionError,
            ItemNotFoundError,
            MalformedCommandError,
            MismatchError,
            RepositoryConsistencyError,
            RepositoryIntegrityError,
            StaleContentError,
        ) as error:
            _raise_recommendation_http_error(error)
        return RedirectResponse(
            url=request.url_for(
                "mission_recommendation_page",
                mission_id=mission_id,
                mission_lesson_id=mission_lesson_id,
            ),
            status_code=303,
        )

    @router.get(
        "/missions/{mission_id}/lessons/{mission_lesson_id}/recommendation",
        response_class=HTMLResponse,
    )
    def mission_recommendation_page(
        mission_id: UUID,
        mission_lesson_id: UUID,
        request: Request,
        service: DashboardServiceDependency,
    ) -> HTMLResponse:
        require_local(request)
        control = mission_control(request)
        mission = control.repository.get_mission(mission_id)
        if mission is None:
            raise HTTPException(status_code=404, detail="Mission was not found.")
        lesson = control.repository.find_mission_lesson_by_id(
            mission_lesson_id
        )
        if lesson is None:
            raise HTTPException(
                status_code=404, detail="Mission lesson was not found."
            )
        if lesson.mission_id != mission_id:
            raise HTTPException(
                status_code=422, detail="Mission lesson mission ID mismatch."
            )
        recommendations = [
            item
            for item in control.repository.list_mission_recommendations(
                lesson.publication_id
            )
            if item.mission_lesson_id == mission_lesson_id
        ]
        latest_recommendation = (
            recommendations[0] if recommendations else None
        )
        successor_lineage = (
            control.repository.find_recommendation_mission_lineage(
                latest_recommendation.mission_recommendation_id
            )
            if latest_recommendation
            else None
        )
        successor_mission = (
            control.repository.get_mission(
                successor_lineage.successor_mission_id
            )
            if successor_lineage
            else None
        )
        csrf_token = secrets.token_urlsafe(32)
        response = render(
            request=request,
            service=service,
            template_name="mission_recommendation.html",
            page_title="Mission Recommendation",
            active_path="/analytics",
            extra_context={
                "mission": mission,
                "source_lesson": lesson,
                "latest_recommendation": latest_recommendation,
                "recommendation_history": recommendations[1:],
                "successor_lineage": successor_lineage,
                "successor_mission": successor_mission,
                "csrf_token": csrf_token,
            },
        )
        response.set_cookie(
            "auraai_csrf", csrf_token, httponly=True, samesite="strict",
            secure=False, max_age=1800,
        )
        return response

    @router.post(
        "/missions/{source_mission_id}/recommendations/"
        "{mission_recommendation_id}/create-mission",
        response_class=RedirectResponse,
    )
    async def create_mission_from_recommendation(
        source_mission_id: UUID,
        mission_recommendation_id: UUID,
        request: Request,
    ) -> RedirectResponse:
        from mission_control.models import (
            ConflictingDecisionError,
            ItemNotFoundError,
            MalformedCommandError,
            MismatchError,
            RepositoryConsistencyError,
            RepositoryIntegrityError,
            StaleContentError,
        )

        require_local(request)
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        if content_type != "application/x-www-form-urlencoded":
            raise HTTPException(
                status_code=415, detail="Unsupported form content type."
            )
        body = await request.body()
        if len(body) > 12_000:
            raise HTTPException(status_code=413, detail="Form is too large.")
        try:
            values = parse_qs(
                body.decode("utf-8"),
                keep_blank_values=True,
                strict_parsing=True,
            )
            if any(len(value) != 1 for value in values.values()):
                raise ValueError("Repeated form field.")
            form = RecommendationMissionCreationForm.model_validate(
                {key: value[0] for key, value in values.items()}
            )
        except (UnicodeDecodeError, ValueError, ValidationError) as error:
            raise HTTPException(
                status_code=422,
                detail="Invalid successor mission form.",
            ) from error
        if not secrets.compare_digest(
            request.cookies.get("auraai_csrf", ""),
            form.csrf_token,
        ):
            raise HTTPException(status_code=403, detail="CSRF validation failed.")
        try:
            successor = (
                mission_commands(request).create_mission_from_recommendation(
                    source_mission_id=source_mission_id,
                    mission_recommendation_id=mission_recommendation_id,
                    actor="Local Founder",
                )
            )
        except (
            ConflictingDecisionError,
            ItemNotFoundError,
            MalformedCommandError,
            MismatchError,
            RepositoryConsistencyError,
            RepositoryIntegrityError,
            StaleContentError,
        ) as error:
            _raise_recommendation_http_error(error)
        return RedirectResponse(
            url=request.url_for(
                "founder_review_page",
                mission_id=successor.mission_id,
            ),
            status_code=303,
        )

    @router.post(
        "/missions/{mission_id}/recommendations/"
        "{mission_recommendation_id}/{decision}",
        response_class=RedirectResponse,
    )
    async def review_mission_recommendation(
        mission_id: UUID,
        mission_recommendation_id: UUID,
        decision: str,
        request: Request,
    ) -> RedirectResponse:
        from mission_control.models import (
            ConflictingDecisionError,
            ItemNotFoundError,
            MalformedCommandError,
            MismatchError,
            RecommendationDecision,
            RepositoryConsistencyError,
            RepositoryIntegrityError,
            StaleContentError,
        )

        require_local(request)
        try:
            typed_decision = RecommendationDecision(decision)
        except ValueError as error:
            raise HTTPException(
                status_code=404, detail="Review action was not found."
            ) from error
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        if content_type != "application/x-www-form-urlencoded":
            raise HTTPException(status_code=415, detail="Unsupported form content type.")
        body = await request.body()
        if len(body) > 12_000:
            raise HTTPException(status_code=413, detail="Form is too large.")
        try:
            values = parse_qs(
                body.decode("utf-8"), keep_blank_values=True,
                strict_parsing=True,
            )
            if any(len(value) != 1 for value in values.values()):
                raise ValueError("Repeated form field.")
            form = MissionRecommendationDecisionForm.model_validate(
                {key: value[0] for key, value in values.items()}
            )
        except (UnicodeDecodeError, ValueError, ValidationError) as error:
            raise HTTPException(
                status_code=422, detail="Invalid recommendation review form."
            ) from error
        if not secrets.compare_digest(
            request.cookies.get("auraai_csrf", ""), form.csrf_token
        ):
            raise HTTPException(status_code=403, detail="CSRF validation failed.")
        try:
            updated = mission_commands(request).review_mission_recommendation(
                mission_id=mission_id,
                mission_recommendation_id=mission_recommendation_id,
                decision=typed_decision,
                actor="Local Founder",
                founder_note=form.founder_note,
            )
        except (
            ConflictingDecisionError,
            ItemNotFoundError,
            MalformedCommandError,
            MismatchError,
            RepositoryConsistencyError,
            RepositoryIntegrityError,
            StaleContentError,
        ) as error:
            _raise_recommendation_http_error(error)
        return RedirectResponse(
            url=request.url_for(
                "mission_recommendation_page",
                mission_id=mission_id,
                mission_lesson_id=updated.mission_lesson_id,
            ),
            status_code=303,
        )

    @router.post(
        "/api/missions/{mission_id}/run-next",
        response_model=RunNextTaskResult,
    )
    def run_next_mission_task(
        mission_id: UUID,
        request: Request,
    ) -> RunNextTaskResult:
        """Execute only Mission Control's next eligible mission task."""

        require_local(request)
        try:
            return mission_commands(request).run_next(mission_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @router.post(
        "/api/missions/{mission_id}/recover",
        response_model=RecoveryReport,
    )
    def recover_mission(mission_id: UUID, request: Request) -> RecoveryReport:
        """Explicitly rerun reconciliation without dispatching work."""

        require_local(request)
        try:
            return mission_commands(request).recover(mission_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @router.post(
        "/api/missions/{mission_id}/tasks/{task_id}/retry",
        response_model=RunNextTaskResult,
    )
    def retry_mission_task(
        mission_id: UUID, task_id: UUID, request: Request
    ) -> RunNextTaskResult:
        """Explicitly retry one task through the shared runtime manager."""

        require_local(request)
        try:
            return mission_commands(request).retry(mission_id, task_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @router.post(
        "/api/missions/{mission_id}/tasks/{task_id}/resume",
        response_model=RunNextTaskResult,
    )
    def resume_mission_task(
        mission_id: UUID,
        task_id: UUID,
        payload: ResumeTaskRequest,
        request: Request,
    ) -> RunNextTaskResult:
        """Explicitly resume using a validated checkpoint or restart policy."""

        require_local(request)
        try:
            return mission_commands(request).resume(
                mission_id, task_id, payload.checkpoint_id
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @router.get("/api/recovery", response_model=RecoveryStatusProjection)
    def recovery_status(request: Request) -> RecoveryStatusProjection:
        """Expose the shared recovery gate and canonical recovery views."""

        control = mission_control(request)
        gate = getattr(request.app.state, "recovery_gate", None)
        if gate is None:
            raise HTTPException(status_code=503, detail="Recovery is not configured.")
        return build_recovery_projection(control, gate)

    return router
