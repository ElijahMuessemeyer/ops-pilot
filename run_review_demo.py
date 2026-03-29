from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ops_pilot.models import PilotActuals, WorkflowCase
from ops_pilot.parsing import load_documents
from ops_pilot.service import OpsPilotAgent


def main() -> None:
    workflow_documents = load_documents(
        [
            ROOT / "data" / "examples" / "club_ops_notes.md",
            ROOT / "data" / "examples" / "club_metrics.csv",
        ]
    )
    review_documents = load_documents([ROOT / "data" / "examples" / "club_post_pilot_notes.md"])

    case = WorkflowCase(
        title="Student org event follow-up",
        team_type="Student organization",
        workflow_goal="Coordinate sponsor follow-up, volunteer recap, and next-step assignments after each weekly event planning meeting.",
        current_process="The president and operations lead review notes, rewrite action items into a spreadsheet, send recap emails, and manually check who responded.",
        desired_outcome="reduce coordination overhead and make follow-up more reliable without removing the human lead from approvals",
        task_volume_per_week=22,
        manual_hours_per_week=6.5,
        average_cycle_time_hours=48,
        average_error_rate_pct=15,
        cost_per_hour=22.0,
        source_documents=workflow_documents,
    )
    actuals = PilotActuals(
        pilot_duration_weeks=4,
        actual_manual_hours_per_week=3.8,
        actual_cycle_time_hours=30,
        actual_error_rate_pct=8,
        actual_on_time_completion_pct=96,
        adoption_rate_pct=88,
        blockers=[
            "Sponsor outreach still needed manual approval on edge cases.",
            "One volunteer report format was inconsistent in week two.",
        ],
        notes="The pilot improved after the team standardized its meeting note template in week two.",
        source_documents=review_documents,
    )

    agent = OpsPilotAgent()
    response = agent.review_pilot(case, actuals)
    if response.runtime is not None:
        print(
            f"[runtime] mode={response.runtime.mode} provider={response.runtime.provider} "
            f"model={response.runtime.model} fallback={response.runtime.used_fallback}"
        )
        if response.runtime.warnings:
            for warning in response.runtime.warnings:
                print(f"[warning] {warning}")
    print(response.markdown)


if __name__ == "__main__":
    main()
