from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ops_pilot.models import WorkflowCase
from ops_pilot.parsing import load_documents
from ops_pilot.service import OpsPilotAgent


def main() -> None:
    documents = load_documents(
        [
            ROOT / "data" / "examples" / "club_ops_notes.md",
            ROOT / "data" / "examples" / "club_metrics.csv",
        ]
    )
    case = WorkflowCase(
        title="Student org event follow-up",
        team_type="Student organization",
        workflow_goal="Coordinate sponsor follow-up, volunteer recap, and next-step assignments after each weekly event planning meeting.",
        current_process="The president and operations lead review notes, rewrite action items into a spreadsheet, send recap emails, and manually check who responded.",
        desired_outcome="reduce coordination overhead and make follow-up more reliable without removing the human lead from approvals",
        cost_per_hour=22.0,
        source_documents=documents,
    )

    agent = OpsPilotAgent()
    response = agent.analyze(case)
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
