from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .analysis import AnalysisSnapshot, build_analysis_snapshot
from .models import (
    ClarifyingQuestion,
    EvidenceSnippet,
    KPIResult,
    PilotActuals,
    PostPilotReview,
    WorkflowCase,
)
from .retrieval import SimpleRetriever
from .utils import clamp, normalize_whitespace


@dataclass(slots=True)
class PostPilotSnapshot:
    planning_snapshot: AnalysisSnapshot
    review: PostPilotReview
    clarifying_questions: list[ClarifyingQuestion]

    def to_dict(self) -> dict[str, Any]:
        return {
            "planning_snapshot": self.planning_snapshot.to_dict(),
            "review": self.review.to_dict(),
            "clarifying_questions": [item.to_dict() for item in self.clarifying_questions],
        }


def build_post_pilot_snapshot(
    case: WorkflowCase,
    actuals: PilotActuals,
    retriever: SimpleRetriever,
) -> PostPilotSnapshot:
    planning_snapshot = build_analysis_snapshot(case, retriever)
    clarifying_questions = build_post_pilot_clarifying_questions(actuals)
    review = build_post_pilot_review(case, actuals, planning_snapshot, retriever)
    return PostPilotSnapshot(
        planning_snapshot=planning_snapshot,
        review=review,
        clarifying_questions=clarifying_questions,
    )


def build_post_pilot_clarifying_questions(actuals: PilotActuals) -> list[ClarifyingQuestion]:
    questions: list[ClarifyingQuestion] = []
    if actuals.actual_manual_hours_per_week is None:
        questions.append(
            ClarifyingQuestion(
                field="actual_manual_hours_per_week",
                question="How many hours per week does the workflow take after the pilot changes?",
                rationale="Manual effort is the clearest measure of realized ROI.",
            )
        )
    if actuals.actual_cycle_time_hours is None:
        questions.append(
            ClarifyingQuestion(
                field="actual_cycle_time_hours",
                question="What is the current average cycle time per item after the pilot?",
                rationale="Cycle time shows whether the pilot improved operational speed.",
            )
        )
    if actuals.actual_on_time_completion_pct is None:
        questions.append(
            ClarifyingQuestion(
                field="actual_on_time_completion_pct",
                question="What share of pilot items finished on time?",
                rationale="On-time completion shows whether reliability improved, not just speed.",
            )
        )
    if actuals.actual_error_rate_pct is None:
        questions.append(
            ClarifyingQuestion(
                field="actual_error_rate_pct",
                question="What is the current error or rework rate after the pilot?",
                rationale="Quality drift can erase the value of faster automation.",
            )
        )
    return questions[:4]


def build_post_pilot_review(
    case: WorkflowCase,
    actuals: PilotActuals,
    snapshot: AnalysisSnapshot,
    retriever: SimpleRetriever,
) -> PostPilotReview:
    targets = snapshot.kpi_targets
    kpi_results = [
        _evaluate_lower_is_better_kpi(
            name="Manual effort",
            target=f"{targets.target_manual_hours_per_week:.1f} hours/week or lower",
            actual_value=actuals.actual_manual_hours_per_week,
            baseline=targets.baseline_manual_hours_per_week,
            target_value=targets.target_manual_hours_per_week,
            unit="hours/week",
            rationale="This measures whether the pilot captured the labor savings promised in the original business case.",
        ),
        _evaluate_lower_is_better_kpi(
            name="Turnaround time",
            target=f"{targets.target_cycle_time_hours:.0f} hours or lower",
            actual_value=actuals.actual_cycle_time_hours,
            baseline=targets.baseline_cycle_time_hours,
            target_value=targets.target_cycle_time_hours,
            unit="hours",
            rationale="Cycle time is the clearest operational speed metric for a pilot rollout.",
        ),
        _evaluate_higher_is_better_kpi(
            name="On-time completion",
            target=f"{targets.target_on_time_completion_pct:.0f}% or higher",
            actual_value=actuals.actual_on_time_completion_pct,
            target_value=targets.target_on_time_completion_pct,
            unit="%",
            rationale="This checks that the pilot improved reliability, not just throughput.",
        ),
        _evaluate_lower_is_better_kpi(
            name="Quality / rework rate",
            target=f"{targets.target_error_rate_pct:.0f}% or lower",
            actual_value=actuals.actual_error_rate_pct,
            baseline=targets.baseline_error_rate_pct,
            target_value=targets.target_error_rate_pct,
            unit="%",
            rationale="A pilot should reduce rework rather than shift hidden cleanup work downstream.",
        ),
    ]

    actual_hours_saved = (
        round(targets.baseline_manual_hours_per_week - actuals.actual_manual_hours_per_week, 1)
        if actuals.actual_manual_hours_per_week is not None
        else None
    )
    actual_annualized_cost_savings = (
        round(actual_hours_saved * 52 * case.cost_per_hour, 2)
        if actual_hours_saved is not None
        else None
    )
    actual_cycle_reduction_pct = (
        round(
            max(
                (targets.baseline_cycle_time_hours - actuals.actual_cycle_time_hours)
                / targets.baseline_cycle_time_hours
                * 100,
                -100.0,
            ),
            1,
        )
        if actuals.actual_cycle_time_hours is not None and targets.baseline_cycle_time_hours > 0
        else None
    )
    kpi_attainment_pct = round(_kpi_attainment_pct(kpi_results), 1)
    blocker_summary = _build_blocker_summary(actuals)
    final_decision, decision_rationale = _make_scale_decision(
        kpi_results=kpi_results,
        actual_hours_saved=actual_hours_saved,
        projected_hours_saved=snapshot.roi_estimate.projected_hours_saved_per_week,
        adoption_rate_pct=actuals.adoption_rate_pct,
        blocker_count=len(actuals.blockers),
    )
    risks_to_watch = _build_risks_to_watch(actuals, kpi_results)
    next_steps = _build_next_steps(final_decision, actuals, kpi_results)
    evidence = collect_post_pilot_evidence(actuals, snapshot, retriever)
    assumptions = _build_review_assumptions(actuals, snapshot)
    executive_summary = _build_executive_summary(
        case=case,
        decision=final_decision,
        actual_hours_saved=actual_hours_saved,
        actual_cycle_reduction_pct=actual_cycle_reduction_pct,
        kpi_attainment_pct=kpi_attainment_pct,
    )

    return PostPilotReview(
        title=f"{case.title}: Post-Pilot Review",
        executive_summary=executive_summary,
        final_decision=final_decision,
        decision_rationale=decision_rationale,
        kpi_results=kpi_results,
        evidence=evidence,
        projected_hours_saved_per_week=snapshot.roi_estimate.projected_hours_saved_per_week,
        actual_hours_saved_per_week=actual_hours_saved,
        projected_annual_cost_savings=snapshot.roi_estimate.annual_cost_savings,
        actual_annualized_cost_savings=actual_annualized_cost_savings,
        projected_cycle_time_reduction_pct=snapshot.roi_estimate.projected_cycle_time_reduction_pct,
        actual_cycle_time_reduction_pct=actual_cycle_reduction_pct,
        kpi_attainment_pct=kpi_attainment_pct,
        blocker_summary=blocker_summary,
        risks_to_watch=risks_to_watch,
        next_steps=next_steps,
        assumptions=assumptions,
    )


def collect_post_pilot_evidence(
    actuals: PilotActuals,
    snapshot: AnalysisSnapshot,
    retriever: SimpleRetriever,
) -> list[EvidenceSnippet]:
    review_query = "pilot results actual hours cycle time rework blockers adoption on time completion"
    evidence = retriever.search(review_query, limit=5)
    if evidence:
        return evidence
    return snapshot.evidence[:4]


def _evaluate_lower_is_better_kpi(
    *,
    name: str,
    target: str,
    actual_value: float | None,
    baseline: float,
    target_value: float,
    unit: str,
    rationale: str,
) -> KPIResult:
    if actual_value is None:
        return KPIResult(
            name=name,
            target=target,
            actual="Not measured yet",
            status="not_measured",
            variance="Missing post-pilot measurement",
            rationale=rationale,
        )

    planned_improvement = max(baseline - target_value, 0.0)
    actual_improvement = baseline - actual_value
    attainment = actual_improvement / planned_improvement if planned_improvement > 0 else 1.0

    if actual_value <= target_value * 1.05:
        status = "met"
    elif actual_value < baseline and attainment >= 0.5:
        status = "partial"
    else:
        status = "missed"

    variance = (
        f"{actual_improvement:+.1f} {unit} improvement vs baseline; "
        f"{(actual_value - target_value):+.1f} {unit} vs target"
    )
    return KPIResult(
        name=name,
        target=target,
        actual=f"{actual_value:.1f} {unit}",
        status=status,
        variance=variance,
        rationale=rationale,
    )


def _evaluate_higher_is_better_kpi(
    *,
    name: str,
    target: str,
    actual_value: float | None,
    target_value: float,
    unit: str,
    rationale: str,
) -> KPIResult:
    if actual_value is None:
        return KPIResult(
            name=name,
            target=target,
            actual="Not measured yet",
            status="not_measured",
            variance="Missing post-pilot measurement",
            rationale=rationale,
        )

    if actual_value >= target_value:
        status = "met"
    elif actual_value >= target_value - 10:
        status = "partial"
    else:
        status = "missed"

    variance = f"{(actual_value - target_value):+.1f} {unit} vs target"
    return KPIResult(
        name=name,
        target=target,
        actual=f"{actual_value:.1f}{unit}",
        status=status,
        variance=variance,
        rationale=rationale,
    )


def _kpi_attainment_pct(kpi_results: list[KPIResult]) -> float:
    weights = {"met": 1.0, "partial": 0.5, "missed": 0.0, "not_measured": 0.25}
    if not kpi_results:
        return 0.0
    score = sum(weights.get(item.status, 0.0) for item in kpi_results)
    return clamp(score / len(kpi_results) * 100, 0, 100)


def _build_blocker_summary(actuals: PilotActuals) -> str:
    if actuals.blockers:
        return f"{len(actuals.blockers)} blocker(s) were logged during the pilot: " + "; ".join(actuals.blockers[:3])
    if normalize_whitespace(actuals.notes):
        return "No structured blockers were logged, but the pilot owner provided additional notes for review."
    return "No blockers were explicitly logged during the pilot."


def _make_scale_decision(
    *,
    kpi_results: list[KPIResult],
    actual_hours_saved: float | None,
    projected_hours_saved: float,
    adoption_rate_pct: float | None,
    blocker_count: int,
) -> tuple[str, str]:
    met_count = sum(item.status == "met" for item in kpi_results)
    missed_count = sum(item.status == "missed" for item in kpi_results)
    measured_count = sum(item.status != "not_measured" for item in kpi_results)
    actual_vs_plan = (
        actual_hours_saved / projected_hours_saved
        if actual_hours_saved is not None and projected_hours_saved > 0
        else None
    )

    if measured_count < 2:
        return (
            "Extend measurement before scaling",
            "The pilot does not have enough measured KPI coverage yet to support a confident scale decision.",
        )
    if (
        met_count >= 3
        and missed_count == 0
        and blocker_count <= 2
        and (adoption_rate_pct is None or adoption_rate_pct >= 70)
        and (actual_vs_plan is None or actual_vs_plan >= 0.7)
    ):
        return (
            "Scale",
            "The pilot met most of its KPI targets, the measured savings are close to plan, and execution risk appears manageable.",
        )
    if met_count >= 1 or (actual_vs_plan is not None and actual_vs_plan > 0):
        return (
            "Revise and extend pilot",
            "The pilot produced some measurable value, but the team should tighten workflow design, adoption, or measurement before scaling further.",
        )
    return (
        "Stop or redesign",
        "The pilot missed the core outcome targets or failed to show enough value to justify a broader rollout in its current form.",
    )


def _build_risks_to_watch(actuals: PilotActuals, kpi_results: list[KPIResult]) -> list[str]:
    risks: list[str] = []
    if actuals.adoption_rate_pct is not None and actuals.adoption_rate_pct < 70:
        risks.append("Adoption remains uneven; the team should standardize the workflow before a wider rollout.")
    if any(item.name == "Quality / rework rate" and item.status == "missed" for item in kpi_results):
        risks.append("Quality gains did not hold; review prompt logic, approval steps, and exception handling.")
    if any(item.name == "Turnaround time" and item.status == "missed" for item in kpi_results):
        risks.append("The pilot is still bottlenecked by handoffs or approvals, so scaling now would not unlock the expected speed gains.")
    if any("privacy" in blocker.lower() or "security" in blocker.lower() for blocker in actuals.blockers):
        risks.append("A governance blocker surfaced during execution and should be resolved before scale-up.")
    if not risks:
        risks.append("No major new risks surfaced, but keep human review in place during the next expansion step.")
    return risks[:4]


def _build_next_steps(
    decision: str,
    actuals: PilotActuals,
    kpi_results: list[KPIResult],
) -> list[str]:
    if decision == "Scale":
        return [
            "Expand the pilot to one adjacent workflow slice while keeping the same KPI scorecard.",
            "Document the operating procedure and assign an owner for weekly KPI review.",
            "Keep exception handling and final approval human-in-the-loop for the next rollout phase.",
        ]
    if decision == "Revise and extend pilot":
        missed = [item.name for item in kpi_results if item.status == "missed"]
        focus = ", ".join(missed[:2]) or "the weakest measured KPI"
        return [
            f"Run one more pilot cycle focused on improving {focus}.",
            "Tighten the workflow scope and eliminate one or two recurring blockers before expanding.",
            "Capture another week of measured results so the scale decision is based on a fuller baseline.",
        ]
    return [
        "Pause broader rollout and document what failed in the current pilot design.",
        "Re-scope the use case or replace the workflow slice with a lower-risk pilot candidate.",
        "Review whether adoption, data quality, or process design issues blocked the expected gains.",
    ]


def _build_review_assumptions(actuals: PilotActuals, snapshot: AnalysisSnapshot) -> list[str]:
    assumptions = list(snapshot.roi_estimate.assumptions)
    if actuals.actual_manual_hours_per_week is None:
        assumptions.append("Actual labor savings are still partially estimated because post-pilot manual effort was not fully measured.")
    if actuals.actual_cycle_time_hours is None:
        assumptions.append("Cycle-time conclusions remain directional until post-pilot turnaround is measured.")
    if actuals.actual_error_rate_pct is None:
        assumptions.append("Quality conclusions remain partial because post-pilot rework data is missing.")
    return list(dict.fromkeys(assumptions))


def _build_executive_summary(
    *,
    case: WorkflowCase,
    decision: str,
    actual_hours_saved: float | None,
    actual_cycle_reduction_pct: float | None,
    kpi_attainment_pct: float,
) -> str:
    pieces = [f"The post-pilot review for `{case.title}` supports a decision to {decision.lower()}."]
    if actual_hours_saved is not None:
        pieces.append(f"The pilot is currently saving about {actual_hours_saved:.1f} hours per week.")
    if actual_cycle_reduction_pct is not None:
        pieces.append(f"Measured turnaround improved by roughly {actual_cycle_reduction_pct:.0f}%.")
    pieces.append(f"Across the KPI scorecard, the pilot achieved about {kpi_attainment_pct:.0f}% of the target outcome.")
    return " ".join(pieces)
