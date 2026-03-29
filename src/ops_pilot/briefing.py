from __future__ import annotations

from .models import PilotBrief, PostPilotReview


def brief_to_markdown(brief: PilotBrief) -> str:
    evidence_lines = "\n".join(
        f"- `{item.source_name}`: {item.quote}" for item in brief.evidence[:5]
    )
    pain_lines = "\n".join(
        f"- **{pain.title}** ({pain.severity}, {pain.frequency}): {pain.description}"
        for pain in brief.pain_points
    )
    kpi_lines = "\n".join(
        f"- **{item.name}**: {item.target} ({item.rationale})" for item in brief.kpis
    )
    risk_lines = "\n".join(
        f"- **{item.name}** [{item.level}] {item.mitigation}" for item in brief.risks
    )
    rollout_lines = "\n".join(
        f"- **{step.phase}**: {step.action} Owner: {step.owner}. Gate: {step.success_gate}"
        for step in brief.rollout_steps
    )
    assumption_lines = "\n".join(f"- {item}" for item in brief.assumptions)
    next_step_lines = "\n".join(f"- {item}" for item in brief.next_steps)

    return f"""# {brief.title}

## Problem Statement
{brief.problem_statement}

## Current State
{brief.current_state}

## Why Now
{brief.why_now}

## Proposed AI Pilot
{brief.proposed_solution}

## Evidence
{evidence_lines}

## Pain Points
{pain_lines}

## Opportunity Score
- **Recommendation**: {brief.opportunity_score.recommendation}
- **Total score**: {brief.opportunity_score.total}/100
- **Impact / Effort / Risk / Confidence**: {brief.opportunity_score.impact} / {brief.opportunity_score.effort} / {brief.opportunity_score.risk} / {brief.opportunity_score.confidence}
- **Rationale**: {brief.opportunity_score.rationale}

## ROI Estimate
- **Baseline manual effort**: {brief.roi_estimate.baseline_hours_per_week:.1f} hours/week
- **Projected savings**: {brief.roi_estimate.projected_hours_saved_per_week:.1f} hours/week
- **Cycle time reduction**: {brief.roi_estimate.projected_cycle_time_reduction_pct:.0f}%
- **Annual hours saved**: {brief.roi_estimate.annual_hours_saved:.1f}
- **Annual cost savings**: ${brief.roi_estimate.annual_cost_savings:,.0f}
- **Confidence note**: {brief.roi_estimate.confidence_note}

## KPIs
{kpi_lines}

## Risks
{risk_lines}

## Rollout Plan
{rollout_lines}

## Recommendation
{brief.recommendation}

## Assumptions
{assumption_lines}

## Next Steps
{next_step_lines}
"""


def post_pilot_review_to_markdown(review: PostPilotReview) -> str:
    kpi_lines = "\n".join(
        f"- **{item.name}** [{item.status}] target: {item.target}; actual: {item.actual}; variance: {item.variance}"
        for item in review.kpi_results
    )
    evidence_lines = "\n".join(
        f"- `{item.source_name}`: {item.quote}" for item in review.evidence[:5]
    )
    risk_lines = "\n".join(f"- {item}" for item in review.risks_to_watch)
    next_step_lines = "\n".join(f"- {item}" for item in review.next_steps)
    assumption_lines = "\n".join(f"- {item}" for item in review.assumptions)

    actual_hours_saved = (
        f"{review.actual_hours_saved_per_week:.1f} hours/week"
        if review.actual_hours_saved_per_week is not None
        else "Not measured yet"
    )
    actual_annualized_savings = (
        f"${review.actual_annualized_cost_savings:,.0f}"
        if review.actual_annualized_cost_savings is not None
        else "Not measured yet"
    )
    actual_cycle_reduction = (
        f"{review.actual_cycle_time_reduction_pct:.0f}%"
        if review.actual_cycle_time_reduction_pct is not None
        else "Not measured yet"
    )

    return f"""# {review.title}

## Executive Summary
{review.executive_summary}

## Final Decision
- **Decision**: {review.final_decision}
- **Rationale**: {review.decision_rationale}
- **KPI attainment**: {review.kpi_attainment_pct:.0f}%

## KPI Review
{kpi_lines}

## Planned vs Actual Value
- **Projected weekly hours saved**: {review.projected_hours_saved_per_week:.1f} hours/week
- **Actual weekly hours saved**: {actual_hours_saved}
- **Projected annual cost savings**: ${review.projected_annual_cost_savings:,.0f}
- **Actual annualized cost savings**: {actual_annualized_savings}
- **Projected cycle-time reduction**: {review.projected_cycle_time_reduction_pct:.0f}%
- **Actual cycle-time reduction**: {actual_cycle_reduction}

## Evidence
{evidence_lines}

## Blockers
{review.blocker_summary}

## Risks To Watch
{risk_lines}

## Next Steps
{next_step_lines}

## Assumptions
{assumption_lines}
"""
