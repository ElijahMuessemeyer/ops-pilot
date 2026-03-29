from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class SourceDocument:
    name: str
    kind: str
    content: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class WorkflowCase:
    title: str
    team_type: str
    workflow_goal: str
    current_process: str
    desired_outcome: str = ""
    task_volume_per_week: int | None = None
    manual_hours_per_week: float | None = None
    average_cycle_time_hours: float | None = None
    average_error_rate_pct: float | None = None
    cost_per_hour: float = 25.0
    source_documents: list[SourceDocument] = field(default_factory=list)

    def combined_text(self) -> str:
        parts = [self.workflow_goal, self.current_process, self.desired_outcome]
        parts.extend(document.content for document in self.source_documents)
        return "\n\n".join(part for part in parts if part).strip()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_documents"] = [document.to_dict() for document in self.source_documents]
        return data


@dataclass(slots=True)
class PilotActuals:
    pilot_duration_weeks: int | None = None
    actual_manual_hours_per_week: float | None = None
    actual_cycle_time_hours: float | None = None
    actual_error_rate_pct: float | None = None
    actual_on_time_completion_pct: float | None = None
    adoption_rate_pct: float | None = None
    blockers: list[str] = field(default_factory=list)
    notes: str = ""
    source_documents: list[SourceDocument] = field(default_factory=list)

    def combined_text(self) -> str:
        parts = [self.notes]
        parts.extend(document.content for document in self.source_documents)
        parts.extend(self.blockers)
        return "\n\n".join(part for part in parts if part).strip()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_documents"] = [document.to_dict() for document in self.source_documents]
        return data


@dataclass(slots=True)
class Chunk:
    source_name: str
    text: str
    index: int


@dataclass(slots=True)
class EvidenceSnippet:
    source_name: str
    quote: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PainPoint:
    title: str
    description: str
    frequency: str
    severity: str
    evidence: list[EvidenceSnippet] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence"] = [item.to_dict() for item in self.evidence]
        return data


@dataclass(slots=True)
class OpportunityScore:
    impact: int
    effort: int
    risk: int
    confidence: int
    total: int
    recommendation: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RoiEstimate:
    baseline_hours_per_week: float
    projected_hours_saved_per_week: float
    projected_cycle_time_reduction_pct: float
    annual_hours_saved: float
    annual_cost_savings: float
    assumptions: list[str]
    confidence_note: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class KPI:
    name: str
    target: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RiskItem:
    name: str
    level: str
    mitigation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RolloutStep:
    phase: str
    action: str
    owner: str
    success_gate: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ClarifyingQuestion:
    field: str
    question: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PilotBrief:
    title: str
    problem_statement: str
    current_state: str
    why_now: str
    proposed_solution: str
    evidence: list[EvidenceSnippet]
    pain_points: list[PainPoint]
    opportunity_score: OpportunityScore
    roi_estimate: RoiEstimate
    kpis: list[KPI]
    risks: list[RiskItem]
    rollout_steps: list[RolloutStep]
    recommendation: str
    next_steps: list[str]
    assumptions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "problem_statement": self.problem_statement,
            "current_state": self.current_state,
            "why_now": self.why_now,
            "proposed_solution": self.proposed_solution,
            "evidence": [item.to_dict() for item in self.evidence],
            "pain_points": [item.to_dict() for item in self.pain_points],
            "opportunity_score": self.opportunity_score.to_dict(),
            "roi_estimate": self.roi_estimate.to_dict(),
            "kpis": [item.to_dict() for item in self.kpis],
            "risks": [item.to_dict() for item in self.risks],
            "rollout_steps": [item.to_dict() for item in self.rollout_steps],
            "recommendation": self.recommendation,
            "next_steps": self.next_steps,
            "assumptions": self.assumptions,
        }


@dataclass(slots=True)
class AgentResponse:
    brief: PilotBrief
    markdown: str
    clarifying_questions: list[ClarifyingQuestion] = field(default_factory=list)
    runtime: AgentRuntime | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "brief": self.brief.to_dict(),
            "markdown": self.markdown,
            "clarifying_questions": [item.to_dict() for item in self.clarifying_questions],
        }
        if self.runtime is not None:
            payload["runtime"] = self.runtime.to_dict()
        return payload


@dataclass(slots=True)
class AgentRuntime:
    trace_id: str
    mode: str
    provider: str | None
    model: str | None
    request_id: str | None = None
    used_fallback: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class KPIResult:
    name: str
    target: str
    actual: str
    status: str
    variance: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PostPilotReview:
    title: str
    executive_summary: str
    final_decision: str
    decision_rationale: str
    kpi_results: list[KPIResult]
    evidence: list[EvidenceSnippet]
    projected_hours_saved_per_week: float
    actual_hours_saved_per_week: float | None
    projected_annual_cost_savings: float
    actual_annualized_cost_savings: float | None
    projected_cycle_time_reduction_pct: float
    actual_cycle_time_reduction_pct: float | None
    kpi_attainment_pct: float
    blocker_summary: str
    risks_to_watch: list[str]
    next_steps: list[str]
    assumptions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "executive_summary": self.executive_summary,
            "final_decision": self.final_decision,
            "decision_rationale": self.decision_rationale,
            "kpi_results": [item.to_dict() for item in self.kpi_results],
            "evidence": [item.to_dict() for item in self.evidence],
            "projected_hours_saved_per_week": self.projected_hours_saved_per_week,
            "actual_hours_saved_per_week": self.actual_hours_saved_per_week,
            "projected_annual_cost_savings": self.projected_annual_cost_savings,
            "actual_annualized_cost_savings": self.actual_annualized_cost_savings,
            "projected_cycle_time_reduction_pct": self.projected_cycle_time_reduction_pct,
            "actual_cycle_time_reduction_pct": self.actual_cycle_time_reduction_pct,
            "kpi_attainment_pct": self.kpi_attainment_pct,
            "blocker_summary": self.blocker_summary,
            "risks_to_watch": self.risks_to_watch,
            "next_steps": self.next_steps,
            "assumptions": self.assumptions,
        }


@dataclass(slots=True)
class PostPilotResponse:
    review: PostPilotReview
    markdown: str
    clarifying_questions: list[ClarifyingQuestion] = field(default_factory=list)
    runtime: AgentRuntime | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "review": self.review.to_dict(),
            "markdown": self.markdown,
            "clarifying_questions": [item.to_dict() for item in self.clarifying_questions],
        }
        if self.runtime is not None:
            payload["runtime"] = self.runtime.to_dict()
        return payload
