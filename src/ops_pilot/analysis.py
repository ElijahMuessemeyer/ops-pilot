from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .models import (
    ClarifyingQuestion,
    EvidenceSnippet,
    KPI,
    OpportunityScore,
    PainPoint,
    PilotBrief,
    RiskItem,
    RoiEstimate,
    RolloutStep,
    WorkflowCase,
)
from .retrieval import SimpleRetriever
from .utils import clamp, normalize_whitespace, sentence_split

PAIN_PATTERNS = [
    (
        "Manual data handling",
        ("manual", "copy", "paste", "spreadsheet", "rekey", "duplicate", "re-enter"),
        "high",
        "Repeated copying or spreadsheet work creates avoidable labor and inconsistency.",
    ),
    (
        "Slow handoffs",
        ("handoff", "waiting", "follow up", "delay", "pending", "approval"),
        "medium",
        "The workflow depends on manual handoffs or approvals that extend turnaround time.",
    ),
    (
        "Status reporting overhead",
        ("status", "summary", "report", "recap", "update", "weekly email"),
        "medium",
        "People spend time assembling updates instead of moving the work forward.",
    ),
    (
        "Rework and missed details",
        ("error", "mistake", "rework", "missed", "forgot", "wrong", "incomplete"),
        "high",
        "The current process creates quality issues that should be caught earlier.",
    ),
    (
        "Unclear ownership",
        ("who owns", "unclear", "ownership", "assigned", "tracking down"),
        "medium",
        "The team loses time because ownership and follow-up are not visible.",
    ),
]

PRIVACY_KEYWORDS = {
    "student id",
    "social security",
    "ssn",
    "medical",
    "health",
    "payroll",
    "gpa",
    "grade",
    "pii",
    "address",
}

INTEGRATION_KEYWORDS = {"crm", "erp", "database", "salesforce", "api", "excel", "sheet", "form"}


@dataclass(slots=True)
class InferredMetrics:
    task_volume_per_week: int | None
    manual_hours_per_week: float | None
    average_cycle_time_hours: float | None
    average_error_rate_pct: float | None
    assumptions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_volume_per_week": self.task_volume_per_week,
            "manual_hours_per_week": self.manual_hours_per_week,
            "average_cycle_time_hours": self.average_cycle_time_hours,
            "average_error_rate_pct": self.average_error_rate_pct,
            "assumptions": self.assumptions,
        }


@dataclass(slots=True)
class KPITargets:
    baseline_manual_hours_per_week: float
    target_manual_hours_per_week: float
    baseline_cycle_time_hours: float
    target_cycle_time_hours: float
    target_on_time_completion_pct: float
    baseline_error_rate_pct: float
    target_error_rate_pct: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_manual_hours_per_week": self.baseline_manual_hours_per_week,
            "target_manual_hours_per_week": self.target_manual_hours_per_week,
            "baseline_cycle_time_hours": self.baseline_cycle_time_hours,
            "target_cycle_time_hours": self.target_cycle_time_hours,
            "target_on_time_completion_pct": self.target_on_time_completion_pct,
            "baseline_error_rate_pct": self.baseline_error_rate_pct,
            "target_error_rate_pct": self.target_error_rate_pct,
        }


@dataclass(slots=True)
class AnalysisSnapshot:
    metrics: InferredMetrics
    clarifying_questions: list[ClarifyingQuestion]
    evidence: list[EvidenceSnippet]
    pain_points: list[PainPoint]
    opportunity_score: OpportunityScore
    roi_estimate: RoiEstimate
    kpi_targets: KPITargets
    kpis: list[KPI]
    risks: list[RiskItem]
    rollout_steps: list[RolloutStep]
    brief: PilotBrief

    def to_dict(self) -> dict[str, Any]:
        return {
            "metrics": self.metrics.to_dict(),
            "clarifying_questions": [item.to_dict() for item in self.clarifying_questions],
            "evidence": [item.to_dict() for item in self.evidence],
            "pain_points": [item.to_dict() for item in self.pain_points],
            "opportunity_score": self.opportunity_score.to_dict(),
            "roi_estimate": self.roi_estimate.to_dict(),
            "kpi_targets": self.kpi_targets.to_dict(),
            "kpis": [item.to_dict() for item in self.kpis],
            "risks": [item.to_dict() for item in self.risks],
            "rollout_steps": [item.to_dict() for item in self.rollout_steps],
            "brief": self.brief.to_dict(),
        }


def analyze_workflow(case: WorkflowCase, retriever: SimpleRetriever) -> tuple[PilotBrief, list[ClarifyingQuestion]]:
    snapshot = build_analysis_snapshot(case, retriever)
    return snapshot.brief, snapshot.clarifying_questions


def build_analysis_snapshot(case: WorkflowCase, retriever: SimpleRetriever) -> AnalysisSnapshot:
    metrics = infer_metrics(case)
    clarifying_questions = build_clarifying_questions(case, metrics)
    evidence = collect_evidence(case, retriever)
    pain_points = extract_pain_points(case, retriever)
    score = score_opportunity(case, metrics, pain_points)
    roi = estimate_roi(case, metrics, score)
    kpi_targets = build_kpi_targets(metrics, roi)
    kpis = build_kpis(kpi_targets)
    risks = build_risks(case)
    rollout_steps = build_rollout_steps(case)
    brief = build_brief(case, metrics, evidence, pain_points, score, roi, kpis, risks, rollout_steps)
    return AnalysisSnapshot(
        metrics=metrics,
        clarifying_questions=clarifying_questions,
        evidence=evidence,
        pain_points=pain_points,
        opportunity_score=score,
        roi_estimate=roi,
        kpi_targets=kpi_targets,
        kpis=kpis,
        risks=risks,
        rollout_steps=rollout_steps,
        brief=brief,
    )


def infer_metrics(case: WorkflowCase) -> InferredMetrics:
    assumptions: list[str] = []
    text = case.combined_text().lower()

    task_volume = case.task_volume_per_week
    if task_volume is None:
        task_volume = _extract_int(
            text,
            [
                r"(?:around\s+)?(\d+)\s+(?:[\w-]+\s+){0,2}(?:tasks|requests|tickets|submissions|reports|emails|forms|items)\s+per\s+week",
                r"weekly_(?:follow_up_)?items.*?value:\s*(\d+)",
            ],
        )
        if task_volume is not None:
            assumptions.append("Task volume was inferred from the workflow notes.")

    manual_hours = case.manual_hours_per_week
    if manual_hours is None:
        manual_hours = _extract_float(
            text,
            [
                r"(\d+(?:\.\d+)?)\s+(?:hours|hrs)\s+per\s+week",
                r"spend[s]?\s+(\d+(?:\.\d+)?)\s+(?:hours|hrs)\s+(?:each\s+week|weekly)",
                r"manual_effort_hours.*?value:\s*(\d+(?:\.\d+)?)",
            ],
        )
        if manual_hours is not None:
            assumptions.append("Manual effort was inferred from the workflow notes.")

    cycle_time = case.average_cycle_time_hours
    if cycle_time is None:
        cycle_time_days = _extract_float(
            text,
            [
                r"(\d+(?:\.\d+)?)\s+days?\s+(?:turnaround|cycle time|to complete)",
                r"take[s]?\s+(\d+(?:\.\d+)?)\s+days?",
            ],
        )
        cycle_time_hours = _extract_float(
            text,
            [
                r"(\d+(?:\.\d+)?)\s+hours?\s+(?:turnaround|cycle time|to complete)",
                r"take[s]?\s+(\d+(?:\.\d+)?)\s+hours?",
                r"turnaround_hours.*?value:\s*(\d+(?:\.\d+)?)",
            ],
        )
        if cycle_time_hours is not None:
            cycle_time = cycle_time_hours
            assumptions.append("Cycle time was inferred from the workflow notes.")
        elif cycle_time_days is not None:
            cycle_time = cycle_time_days * 24
            assumptions.append("Cycle time was inferred from the workflow notes.")

    error_rate = case.average_error_rate_pct
    if error_rate is None:
        error_rate = _extract_float(
            text,
            [
                r"(\d+(?:\.\d+)?)\s*%\s+(?:of\s+[\w\s]+\s+)?(?:error|rework|mistake)",
                r"rework_rate_pct.*?value:\s*(\d+(?:\.\d+)?)",
            ],
        )
        if error_rate is not None:
            assumptions.append("Error rate was inferred from the workflow notes.")

    if task_volume is None:
        assumptions.append("Task volume remains unconfirmed and should be validated before launch.")
    if manual_hours is None:
        assumptions.append("Manual effort remains unconfirmed and should be validated during baseline tracking.")

    return InferredMetrics(
        task_volume_per_week=task_volume,
        manual_hours_per_week=manual_hours,
        average_cycle_time_hours=cycle_time,
        average_error_rate_pct=error_rate,
        assumptions=assumptions,
    )


def build_clarifying_questions(
    case: WorkflowCase,
    metrics: InferredMetrics,
) -> list[ClarifyingQuestion]:
    questions: list[ClarifyingQuestion] = []

    if metrics.manual_hours_per_week is None:
        questions.append(
            ClarifyingQuestion(
                field="manual_hours_per_week",
                question="About how many hours does the team spend on this workflow each week?",
                rationale="Manual effort is the strongest driver of ROI in the pilot brief.",
            )
        )
    if metrics.task_volume_per_week is None:
        questions.append(
            ClarifyingQuestion(
                field="task_volume_per_week",
                question="How many tasks, requests, or records move through this workflow each week?",
                rationale="Task volume helps size the benefit and the pilot sample.",
            )
        )
    if metrics.average_cycle_time_hours is None:
        questions.append(
            ClarifyingQuestion(
                field="average_cycle_time_hours",
                question="How long does one item usually take from intake to completion?",
                rationale="Turnaround time helps define the KPI target and rollout gate.",
            )
        )

    if case.desired_outcome.strip() == "":
        questions.append(
            ClarifyingQuestion(
                field="desired_outcome",
                question="What would success look like after a small pilot?",
                rationale="A clear target keeps the recommendation anchored to a business outcome.",
            )
        )

    return questions[:4]


def collect_evidence(case: WorkflowCase, retriever: SimpleRetriever) -> list[EvidenceSnippet]:
    query = "manual bottleneck delays follow up reporting errors approvals automation"
    evidence = retriever.search(query, limit=6)
    if evidence:
        return evidence

    fallback_text = normalize_whitespace(case.combined_text())
    if not fallback_text:
        return []

    return [EvidenceSnippet(source_name="workflow input", quote=fallback_text[:220], score=0.1)]


def extract_pain_points(case: WorkflowCase, retriever: SimpleRetriever) -> list[PainPoint]:
    text = case.combined_text().lower()
    sentences = sentence_split(case.combined_text())
    pain_points: list[PainPoint] = []

    for title, keywords, severity, description in PAIN_PATTERNS:
        matched_sentences = [
            sentence for sentence in sentences if any(keyword in sentence.lower() for keyword in keywords)
        ]
        if not matched_sentences:
            continue

        evidence = retriever.search(" ".join(keywords), limit=2)
        frequency = _frequency_label(text, keywords)
        pain_points.append(
            PainPoint(
                title=title,
                description=description,
                frequency=frequency,
                severity=severity,
                evidence=evidence,
            )
        )

    if pain_points:
        return pain_points[:4]

    evidence = retriever.search(case.workflow_goal or case.current_process, limit=2)
    return [
        PainPoint(
            title="Fragmented workflow visibility",
            description="The process lacks enough structured visibility to quickly decide what should be automated first.",
            frequency="Recurring",
            severity="medium",
            evidence=evidence,
        )
    ]


def score_opportunity(
    case: WorkflowCase,
    metrics: InferredMetrics,
    pain_points: list[PainPoint],
) -> OpportunityScore:
    combined = case.combined_text().lower()
    impact = 2
    if (metrics.manual_hours_per_week or 0) >= 6:
        impact += 2
    elif (metrics.manual_hours_per_week or 0) >= 3:
        impact += 1
    if (metrics.task_volume_per_week or 0) >= 20:
        impact += 1
    if len(pain_points) >= 3:
        impact += 1
    impact = int(clamp(impact, 1, 5))

    effort = 3
    if any(keyword in combined for keyword in INTEGRATION_KEYWORDS):
        effort += 1
    if any(keyword in combined for keyword in PRIVACY_KEYWORDS):
        effort += 1
    if "spreadsheet" in combined or "email" in combined or "notes" in combined:
        effort -= 1
    effort = int(clamp(effort, 1, 5))

    risk = 2
    if any(keyword in combined for keyword in PRIVACY_KEYWORDS):
        risk += 2
    if "approval" in combined or "funding" in combined or "budget" in combined:
        risk += 1
    if "manual" in combined and "different" in combined:
        risk += 1
    risk = int(clamp(risk, 1, 5))

    confidence = 2
    if metrics.manual_hours_per_week is not None:
        confidence += 1
    if metrics.task_volume_per_week is not None:
        confidence += 1
    if metrics.average_cycle_time_hours is not None:
        confidence += 1
    if len(metrics.assumptions) > 3:
        confidence -= 1
    confidence = int(clamp(confidence, 1, 5))

    total = round(
        (
            impact * 0.4
            + (6 - effort) * 0.2
            + (6 - risk) * 0.2
            + confidence * 0.2
        )
        / 5
        * 100
    )

    if total >= 78:
        recommendation = "Pilot now"
        rationale = "The workflow is repeated often enough and is text-heavy enough to justify a scoped pilot immediately."
    elif total >= 60:
        recommendation = "Run a narrow pilot after a one-week baseline"
        rationale = "The opportunity looks credible, but the team should validate workload assumptions before committing more scope."
    else:
        recommendation = "Collect more data before automating"
        rationale = "The current evidence is too thin or the workflow carries enough friction that a pilot should wait."

    return OpportunityScore(
        impact=impact,
        effort=effort,
        risk=risk,
        confidence=confidence,
        total=total,
        recommendation=recommendation,
        rationale=rationale,
    )


def estimate_roi(
    case: WorkflowCase,
    metrics: InferredMetrics,
    score: OpportunityScore,
) -> RoiEstimate:
    baseline_hours = metrics.manual_hours_per_week
    assumptions: list[str] = []
    if baseline_hours is None:
        estimated_from_volume = (metrics.task_volume_per_week or 12) * 0.18
        baseline_hours = round(max(2.0, estimated_from_volume), 1)
        assumptions.append("Baseline manual effort was estimated from weekly task volume.")

    automation_factor = clamp(0.18 + score.impact * 0.08 - score.effort * 0.03 - score.risk * 0.02, 0.15, 0.62)
    hours_saved = round(baseline_hours * automation_factor, 1)
    cycle_time_reduction = round(
        clamp(12 + score.impact * 6 - score.effort * 2 - score.risk, 10, 45),
        1,
    )
    annual_hours_saved = round(hours_saved * 52, 1)
    annual_cost_savings = round(annual_hours_saved * case.cost_per_hour, 2)

    assumptions.extend(metrics.assumptions)
    assumptions.append("Savings assume the pilot automates drafting, triage, and status preparation but leaves final approval with a human owner.")

    confidence_note = (
        "High enough for a pilot business case, but validate baseline metrics during the first week."
        if score.confidence >= 4
        else "Directionally useful only; confirm workload assumptions before scaling beyond the pilot."
    )

    return RoiEstimate(
        baseline_hours_per_week=baseline_hours,
        projected_hours_saved_per_week=hours_saved,
        projected_cycle_time_reduction_pct=cycle_time_reduction,
        annual_hours_saved=annual_hours_saved,
        annual_cost_savings=annual_cost_savings,
        assumptions=assumptions,
        confidence_note=confidence_note,
    )


def build_kpi_targets(metrics: InferredMetrics, roi: RoiEstimate) -> KPITargets:
    baseline_cycle_time = metrics.average_cycle_time_hours or 48.0
    baseline_error_rate = metrics.average_error_rate_pct or 12.0
    return KPITargets(
        baseline_manual_hours_per_week=roi.baseline_hours_per_week,
        target_manual_hours_per_week=max(roi.baseline_hours_per_week - roi.projected_hours_saved_per_week, 0),
        baseline_cycle_time_hours=baseline_cycle_time,
        target_cycle_time_hours=baseline_cycle_time * (1 - roi.projected_cycle_time_reduction_pct / 100),
        target_on_time_completion_pct=95.0,
        baseline_error_rate_pct=baseline_error_rate,
        target_error_rate_pct=max(baseline_error_rate * 0.7, 3),
    )


def build_kpis(targets: KPITargets) -> list[KPI]:
    return [
        KPI(
            name="Manual effort",
            target=f"Reduce from {targets.baseline_manual_hours_per_week:.1f} to {targets.target_manual_hours_per_week:.1f} hours/week.",
            rationale="This is the clearest direct savings metric for a small-team pilot.",
        ),
        KPI(
            name="Turnaround time",
            target=f"Cut average cycle time from {targets.baseline_cycle_time_hours:.0f} to {targets.target_cycle_time_hours:.0f} hours.",
            rationale="Faster cycle time shows whether the pilot removes the slowest workflow steps.",
        ),
        KPI(
            name="On-time completion",
            target=f"Reach {targets.target_on_time_completion_pct:.0f}% on-time completion for the pilot sample.",
            rationale="The pilot should improve reliability, not just speed.",
        ),
        KPI(
            name="Quality / rework rate",
            target=f"Reduce rework below {targets.target_error_rate_pct:.0f}%.",
            rationale="Automation should reduce missed details and prevent extra follow-up work.",
        ),
    ]


def build_risks(case: WorkflowCase) -> list[RiskItem]:
    combined = case.combined_text().lower()
    risks = [
        RiskItem(
            name="Source inconsistency",
            level="medium",
            mitigation="Start with one canonical intake format and log every exception the pilot cannot handle.",
        ),
        RiskItem(
            name="Team adoption",
            level="medium",
            mitigation="Keep a human reviewer in the loop and compare pilot outputs against the current manual process for two weeks.",
        ),
        RiskItem(
            name="Over-automation of edge cases",
            level="low",
            mitigation="Limit the pilot to high-volume routine cases and route anything ambiguous back to the team lead.",
        ),
    ]

    if any(keyword in combined for keyword in PRIVACY_KEYWORDS):
        risks.insert(
            0,
            RiskItem(
                name="Sensitive data exposure",
                level="high",
                mitigation="Redact sensitive fields, restrict access, and keep the pilot inside approved systems before handling real records.",
            ),
        )

    return risks[:4]


def build_rollout_steps(case: WorkflowCase) -> list[RolloutStep]:
    return [
        RolloutStep(
            phase="Week 1 baseline",
            action="Track current volume, manual effort, cycle time, and rework on the selected workflow.",
            owner="Workflow owner",
            success_gate="Baseline metrics are complete for at least five business days.",
        ),
        RolloutStep(
            phase="Week 2 prototype",
            action="Use the agent to draft recommendations, summaries, or triage suggestions on historical examples.",
            owner="Project builder",
            success_gate="The agent produces acceptable outputs for at least 80% of the sample cases.",
        ),
        RolloutStep(
            phase="Weeks 3-4 pilot",
            action="Run the agent on a limited live sample while a human approves every output.",
            owner="Team lead",
            success_gate="At least two KPI signals improve without introducing new failure modes.",
        ),
        RolloutStep(
            phase="Review and scale decision",
            action="Compare pilot metrics against the baseline, document risks, and decide whether to expand, revise, or stop.",
            owner="Team lead and sponsor",
            success_gate="The business case still holds after measured results and the team wants to continue.",
        ),
    ]


def build_brief(
    case: WorkflowCase,
    metrics: InferredMetrics,
    evidence: list[EvidenceSnippet],
    pain_points: list[PainPoint],
    score: OpportunityScore,
    roi: RoiEstimate,
    kpis: list[KPI],
    risks: list[RiskItem],
    rollout_steps: list[RolloutStep],
) -> PilotBrief:
    top_pain_titles = ", ".join(pain.title.lower() for pain in pain_points[:2])
    current_state = (
        f"The team currently manages `{case.title}` through a largely manual workflow. "
        f"Common friction includes {top_pain_titles or 'fragmented coordination'}, which slows follow-up and makes the process harder to scale."
    )

    why_now = (
        f"This workflow is a reasonable pilot target because it appears to consume about "
        f"{roi.baseline_hours_per_week:.1f} hours each week and should be reducible with a narrow, human-reviewed automation layer."
    )

    proposed_solution = (
        "Create a small-team copilot that ingests the workflow notes and structured inputs, identifies the next action, "
        "drafts the required summary or recommendation, and records a pilot brief with ROI, KPIs, and risks before any broader rollout."
    )

    recommendation = (
        f"{score.recommendation}. Start with one workflow owner, one approved data source, and a live pilot sample that is small enough to review manually."
    )

    next_steps = [
        "Confirm the weekly workload and baseline manual effort with one week of tracking.",
        "Pick one narrow workflow slice for the first pilot instead of automating the full process.",
        "Review the generated brief with the team lead and agree on KPI targets before launch.",
    ]

    assumptions = list(dict.fromkeys(roi.assumptions))

    problem_statement = (
        f"The `{case.title}` workflow relies on manual coordination that creates avoidable delay, inconsistent follow-up, and reporting overhead for a small team."
    )
    if case.desired_outcome:
        problem_statement += f" The desired outcome is to {case.desired_outcome.strip()}."

    return PilotBrief(
        title=f"{case.title}: AI Pilot Brief",
        problem_statement=problem_statement,
        current_state=current_state,
        why_now=why_now,
        proposed_solution=proposed_solution,
        evidence=evidence,
        pain_points=pain_points,
        opportunity_score=score,
        roi_estimate=roi,
        kpis=kpis,
        risks=risks,
        rollout_steps=rollout_steps,
        recommendation=recommendation,
        next_steps=next_steps,
        assumptions=assumptions,
    )


def _frequency_label(text: str, keywords: tuple[str, ...]) -> str:
    count = sum(text.count(keyword) for keyword in keywords)
    if count >= 4:
        return "Very frequent"
    if count >= 2:
        return "Recurring"
    return "Occasional"


def _extract_int(text: str, patterns: list[str]) -> int | None:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None


def _extract_float(text: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1))
    return None
