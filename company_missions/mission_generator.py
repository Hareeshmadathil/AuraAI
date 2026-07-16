"""Deterministic mission generation using existing AuraAI intelligence systems."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from agents.executive import AuraCEO
from agents.specialists.trend_hunter import TrendCandidate, TrendHunter, TrendOpportunity
from core import DepartmentName, MissionObjective, MissionRecord as ExecutiveMission
from core import TaskPriority, utc_now
from intelligence_director.enums import SignalSource, VerificationStatus
from intelligence_director.models import IntelligenceSignal, SignalContext
from intelligence_director.service import IntelligenceDirectorService
from knowledge_manager.models import KnowledgeQuery
from knowledge_manager.service import KnowledgeManagerService
from mission_control import MissionControlService
from mission_control.models import MissionDifficulty, MissionRecord, RiskLevel
from web_intelligence.evidence_layer import EvidenceLayer


@dataclass(frozen=True, slots=True)
class ScoredOpportunity:
    """Combined existing-system score used to select one mission."""

    opportunity: TrendOpportunity
    intelligence_score: float
    mission_score: float


class MissionGenerator:
    """Generate and register one canonical offline mission."""

    def __init__(
        self,
        *,
        control: MissionControlService,
        trend_hunter: TrendHunter,
        intelligence_director: IntelligenceDirectorService,
        knowledge_manager: KnowledgeManagerService,
        ceo: AuraCEO,
        evidence_layer: EvidenceLayer | None = None,
    ) -> None:
        self.control = control
        self.trend_hunter = trend_hunter
        self.intelligence_director = intelligence_director
        self.knowledge_manager = knowledge_manager
        self.ceo = ceo
        self.evidence_layer = evidence_layer or EvidenceLayer()

    def generate(
        self,
        founder_goal: str,
        *,
        candidates: list[TrendCandidate] | None = None,
    ) -> MissionRecord:
        """Generate, deduplicate, rank, and persist one mission."""

        goal = founder_goal.strip()
        if not goal:
            raise ValueError("Founder goal is required.")
        self._review_goal(goal)
        evidence = (
            self.evidence_layer.from_candidates(candidates)
            if candidates is not None
            else self.evidence_layer.fixtures(goal)
        )
        unique = self._unique_candidates(self.evidence_layer.candidates(evidence))
        opportunities = self.trend_hunter.rank_candidates(unique)
        scored = self._score_with_intelligence(opportunities)
        novel = [
            item for item in scored if not self._known(item.opportunity.name)
        ]
        if not novel:
            raise ValueError("Knowledge Manager found no novel mission opportunity.")
        selected = sorted(
            novel,
            key=lambda item: (-item.mission_score, item.opportunity.name.casefold()),
        )[0]
        mission = self._mission(goal, selected)
        return self.control.create_mission(mission)

    def _review_goal(self, goal: str) -> None:
        executive = ExecutiveMission(
            title=f"Generate mission for: {goal[:120]}",
            description=goal,
            lead_department=DepartmentName.RESEARCH,
            objectives=[
                MissionObjective(
                    description="Select one non-duplicate offline opportunity.",
                    success_metric="One canonical Mission Control mission",
                )
            ],
        )
        decision = self.ceo.review_mission(executive)
        if decision.outcome.value != "approved":
            raise ValueError("CEO did not approve mission generation.")

    @staticmethod
    def _unique_candidates(values: list[TrendCandidate]) -> list[TrendCandidate]:
        unique: dict[str, TrendCandidate] = {}
        for value in values:
            unique.setdefault(value.name.strip().casefold(), value)
        if not unique:
            raise ValueError("At least one opportunity is required.")
        return list(unique.values())

    def _known(self, name: str) -> bool:
        result = self.knowledge_manager.query(KnowledgeQuery(text=name, limit=10))
        normalized = name.strip().casefold()
        return any(
            match.version.topic.normalized_name.strip().casefold() == normalized
            for match in result.matches
        )

    def _score_with_intelligence(
        self,
        opportunities: list[TrendOpportunity],
    ) -> list[ScoredOpportunity]:
        signals = [self._signal(item) for item in opportunities]
        result = self.intelligence_director.analyze(signals)
        return [
            ScoredOpportunity(
                opportunity=opportunity,
                intelligence_score=round(priority.overall, 2),
                mission_score=round(
                    opportunity.opportunity_score * 0.6 + priority.overall * 0.4,
                    2,
                ),
            )
            for opportunity, priority in zip(
                opportunities, result.priorities, strict=True
            )
        ]

    @staticmethod
    def _signal(opportunity: TrendOpportunity) -> IntelligenceSignal:
        return IntelligenceSignal(
            source=SignalSource.FIXTURE,
            source_name="Mission Generator deterministic opportunity",
            topic=opportunity.name,
            summary=opportunity.recommendation,
            entities=[],
            evidence_references=["mission-generator://offline"],
            observed_at=utc_now(),
            freshness_window_hours=24,
            context=SignalContext(
                business_relevance=opportunity.opportunity_score,
                audience_relevance=opportunity.opportunity_score,
                urgency=60,
            ),
            confidence=min(0.95, opportunity.opportunity_score / 100),
            verification_status=VerificationStatus.UNVERIFIED,
            synthetic=True,
        )

    @staticmethod
    def _mission(goal: str, selected: ScoredOpportunity) -> MissionRecord:
        score = selected.mission_score
        priority = (
            TaskPriority.HIGH
            if score >= 70
            else TaskPriority.NORMAL
            if score >= 50
            else TaskPriority.LOW
        )
        opportunity = selected.opportunity
        production_difficulty = 100 - (
            opportunity.score_breakdown["production_advantage"] / 0.15
        )
        difficulty = (
            MissionDifficulty.HIGH
            if production_difficulty >= 70
            else MissionDifficulty.MEDIUM
            if production_difficulty >= 40
            else MissionDifficulty.LOW
        )
        mission_id = uuid5(
            NAMESPACE_URL,
            f"https://auraai.local/generated-missions/{goal.casefold()}",
        )
        return MissionRecord(
            mission_id=mission_id,
            title=opportunity.name,
            objective=f"Advance the founder goal '{goal}' through one offline founder-review package.",
            expected_outcome="A complete, quality-reviewed offline Mission Zero package awaiting founder approval.",
            business_value="Validate one ranked content opportunity without external cost or publication risk.",
            priority=priority,
            risk=RiskLevel.MEDIUM,
            difficulty=difficulty,
            estimated_execution_minutes=45,
            required_departments=[DepartmentName.EXECUTIVE,DepartmentName.RESEARCH,DepartmentName.INTELLIGENCE,DepartmentName.PRODUCTION,DepartmentName.CREATIVE_QUALITY],
            required_approvals=["approve_mission_zero_content"],
            success_criteria=["All offline stages complete", "Creative Quality completes", "Founder approval request is pending"],
            failure_criteria=["Any dependency fails", "Quality pipeline fails", "External operation is attempted"],
            artifacts_expected=["canonical evidence", "trend opportunity", "intelligence result", "knowledge result", "research plan", "script", "production package", "quality package"],
            mission_dependencies=["reviewed Mission Zero script-v2 package", "offline deterministic fixtures"],
            offline_execution=True,
            provider_requirements=["Provider Router composed with unavailable transports", "No provider request"],
            publishing_required=False,
            rendering_required=False,
            confidence=round((selected.intelligence_score / 100 + opportunity.opportunity_score / 100) / 2, 4),
            mission_score=score,
            reasoning_summary=f"Selected from deduplicated, authority- and freshness-ranked canonical evidence using 60% Trend Hunter opportunity score and 40% Intelligence Director priority. Contradictions remain explicit in evidence risks. Knowledge Manager found no exact prior mission titled '{opportunity.name}'.",
            founder_owner="Hareesh",
            founder_goal=goal,
        )
