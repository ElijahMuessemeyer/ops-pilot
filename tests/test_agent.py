from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ops_pilot.config import AgentConfig
from ops_pilot.llm import OpenAIResponsesClient, OpsPilotLLMPlanner, TransportResponse
from ops_pilot.models import PilotActuals, SourceDocument, WorkflowCase
from ops_pilot.parsing import load_documents
from ops_pilot.service import OpsPilotAgent


class FakeTransport:
    def __init__(self, responses: list[TransportResponse]) -> None:
        self.responses = responses
        self.requests: list[dict] = []

    def post_json(self, url: str, headers: dict, payload: dict, timeout_seconds: float) -> TransportResponse:
        self.requests.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        if not self.responses:
            raise AssertionError("No fake responses left.")
        return self.responses.pop(0)


class AgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = OpsPilotAgent(config=AgentConfig(mode="deterministic"))
        self.seed_case = WorkflowCase(
            title="Student org event follow-up",
            team_type="Student organization",
            workflow_goal="Coordinate sponsor follow-up, volunteer recap, and next-step assignments after each weekly event planning meeting.",
            current_process="The president and operations lead review notes, rewrite action items into a spreadsheet, send recap emails, and manually check who responded.",
            desired_outcome="reduce coordination overhead and make follow-up more reliable without removing the human lead from approvals",
            cost_per_hour=22.0,
            source_documents=load_documents(
                [
                    ROOT / "data" / "examples" / "club_ops_notes.md",
                    ROOT / "data" / "examples" / "club_metrics.csv",
                ]
            ),
        )
        self.seed_actuals = PilotActuals(
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
            notes="The pilot reduced recap drafting time and improved follow-up reliability after the second week.",
        )

    def test_agent_generates_strong_recommendation_for_seeded_case(self) -> None:
        response = self.agent.analyze(self.seed_case)

        self.assertEqual(response.brief.opportunity_score.recommendation, "Pilot now")
        self.assertGreaterEqual(response.brief.opportunity_score.total, 75)
        self.assertGreaterEqual(len(response.brief.pain_points), 3)
        self.assertIn("## ROI Estimate", response.markdown)
        self.assertEqual(response.clarifying_questions, [])
        self.assertEqual(response.runtime.mode, "deterministic")

    def test_agent_still_asks_for_missing_metrics_when_context_is_thin(self) -> None:
        case = WorkflowCase(
            title="Lab intake triage",
            team_type="Campus lab",
            workflow_goal="Review incoming equipment requests and assign the right owner.",
            current_process="One coordinator scans email threads and forwards each request by hand.",
        )

        response = self.agent.analyze(case)

        fields = {item.field for item in response.clarifying_questions}
        self.assertIn("manual_hours_per_week", fields)
        self.assertIn("task_volume_per_week", fields)
        self.assertIn("average_cycle_time_hours", fields)
        self.assertIn("## Recommendation", response.markdown)
        self.assertEqual(response.runtime.mode, "deterministic")

    def test_sensitive_data_case_surfaces_privacy_risk(self) -> None:
        case = WorkflowCase(
            title="Clinic intake follow-up",
            team_type="Volunteer clinic",
            workflow_goal="Prepare intake summaries for student volunteers.",
            current_process="Staff review medical histories, copy key notes into a shared tracker, and send approval emails.",
            source_documents=[
                SourceDocument(
                    name="clinic_notes.md",
                    kind="text",
                    content="The team handles medical histories and student addresses. Manual spreadsheet re-entry creates delays and approval bottlenecks.",
                )
            ],
        )

        response = self.agent.analyze(case)

        risk_names = {item.name for item in response.brief.risks}
        self.assertIn("Sensitive data exposure", risk_names)

    def test_post_pilot_review_recommends_scaling_when_results_meet_targets(self) -> None:
        response = self.agent.review_pilot(self.seed_case, self.seed_actuals)

        self.assertEqual(response.review.final_decision, "Scale")
        self.assertGreaterEqual(response.review.kpi_attainment_pct, 75)
        self.assertIn("## Final Decision", response.markdown)
        self.assertEqual(response.runtime.mode, "deterministic")

    def test_post_pilot_review_asks_for_missing_actuals_when_measurement_is_thin(self) -> None:
        actuals = PilotActuals(notes="The team feels better about the workflow, but formal metrics were not tracked.")

        response = self.agent.review_pilot(self.seed_case, actuals)

        fields = {item.field for item in response.clarifying_questions}
        self.assertIn("actual_manual_hours_per_week", fields)
        self.assertIn("actual_cycle_time_hours", fields)
        self.assertIn("actual_error_rate_pct", fields)
        self.assertIn("actual_on_time_completion_pct", fields)
        self.assertEqual(response.review.final_decision, "Extend measurement before scaling")

    def test_agent_uses_llm_pipeline_when_configured(self) -> None:
        llm_payload = {
            "problem_statement": "The workflow still depends on leaders rewriting meeting notes into operational follow-up tasks by hand.",
            "current_state": "Meeting notes, recap emails, and sponsor outreach are split across docs, spreadsheets, and manual follow-up.",
            "why_now": "The team handles the same coordination pattern every week, so a small pilot could save time quickly without major system changes.",
            "proposed_solution": "Deploy an LLM-backed planning copilot that reads meeting notes, drafts follow-up summaries, and prepares a pilot brief for human review.",
            "recommendation_detail": "Start with sponsor and volunteer follow-up, keep a human approver on every message, and measure the pilot for four weeks.",
            "pain_points": [
                {
                    "title": "Manual recap drafting",
                    "description": "Leads rewrite the same meeting notes into different formats each week.",
                    "frequency": "Very frequent",
                    "severity": "high",
                },
                {
                    "title": "Delayed sponsor outreach",
                    "description": "Sponsor follow-up waits on manual approvals and polished drafts.",
                    "frequency": "Recurring",
                    "severity": "medium",
                },
            ],
            "kpis": [
                {
                    "name": "Manual effort",
                    "target": "Reduce weekly follow-up effort below 4 hours.",
                    "rationale": "This shows whether the pilot actually removes repeated coordination work.",
                },
                {
                    "name": "Turnaround time",
                    "target": "Bring sponsor follow-up under 32 hours.",
                    "rationale": "Faster sponsor response is the clearest operational gain.",
                },
            ],
            "risks": [
                {
                    "name": "Adoption drift",
                    "level": "medium",
                    "mitigation": "Keep the pilot inside one team lead's workflow until output quality is stable.",
                }
            ],
            "rollout_steps": [
                {
                    "phase": "Week 1 baseline",
                    "action": "Measure current recap drafting time and sponsor turnaround.",
                    "owner": "Operations lead",
                    "success_gate": "Baseline metrics are recorded for one week.",
                },
                {
                    "phase": "Weeks 2-4 pilot",
                    "action": "Run the copilot on live meetings with human approval on every output.",
                    "owner": "President",
                    "success_gate": "The pilot improves at least two KPIs without new failure modes.",
                },
            ],
            "next_steps": [
                "Confirm the pilot slice and baseline metrics with the team lead.",
                "Run the copilot on one weekly meeting cycle before expanding.",
            ],
            "assumptions": [
                "The pilot will only draft outputs and will not send messages automatically.",
            ],
        }
        transport = FakeTransport(
            [
                TransportResponse(
                    status=200,
                    headers={"x-request-id": "req_test_123"},
                    body=json.dumps(
                        {
                            "id": "resp_test_123",
                            "model": "gpt-4.1-mini",
                            "output": [
                                {
                                    "type": "message",
                                    "content": [
                                        {
                                            "type": "output_text",
                                            "text": json.dumps(llm_payload),
                                        }
                                    ],
                                }
                            ],
                        }
                    ).encode("utf-8"),
                )
            ]
        )
        config = AgentConfig(
            mode="llm",
            provider="openai",
            api_key="test-key",
            model="gpt-4.1-mini",
            base_url="https://example.com/v1",
        )
        client = OpenAIResponsesClient(
            api_key=config.api_key or "",
            model=config.model,
            base_url=config.base_url,
            transport=transport,
        )
        agent = OpsPilotAgent(config=config, llm_planner=OpsPilotLLMPlanner(client))

        response = agent.analyze(self.seed_case)

        self.assertEqual(response.runtime.mode, "llm")
        self.assertEqual(response.runtime.request_id, "req_test_123")
        self.assertIn("LLM-backed planning copilot", response.brief.proposed_solution)
        self.assertEqual(transport.requests[0]["payload"]["text"]["format"]["type"], "json_schema")
        self.assertIn("Pilot now.", response.brief.recommendation)

    def test_post_pilot_review_uses_llm_pipeline_when_configured(self) -> None:
        llm_payload = {
            "executive_summary": "The pilot delivered enough measured value to justify scaling, with the strongest evidence in labor savings and turnaround time.",
            "decision_detail": "Scale to one adjacent workflow slice while keeping human approval on exceptions.",
            "blocker_summary": "A few edge-case approvals remained manual, but no blocker was large enough to offset the KPI gains.",
            "risks_to_watch": [
                "Adoption should still be monitored as the pilot expands to adjacent workflows.",
            ],
            "next_steps": [
                "Expand to one adjacent workflow slice and keep the same KPI scorecard.",
                "Document a standard operating procedure for weekly KPI review.",
            ],
            "assumptions": [
                "The measured results are representative of the next rollout phase.",
            ],
        }
        transport = FakeTransport(
            [
                TransportResponse(
                    status=200,
                    headers={"x-request-id": "req_review_123"},
                    body=json.dumps(
                        {
                            "id": "resp_review_123",
                            "model": "gpt-4.1-mini",
                            "output": [
                                {
                                    "type": "message",
                                    "content": [
                                        {
                                            "type": "output_text",
                                            "text": json.dumps(llm_payload),
                                        }
                                    ],
                                }
                            ],
                        }
                    ).encode("utf-8"),
                )
            ]
        )
        config = AgentConfig(
            mode="llm",
            provider="openai",
            api_key="test-key",
            model="gpt-4.1-mini",
            base_url="https://example.com/v1",
        )
        client = OpenAIResponsesClient(
            api_key=config.api_key or "",
            model=config.model,
            base_url=config.base_url,
            transport=transport,
        )
        agent = OpsPilotAgent(config=config, llm_planner=OpsPilotLLMPlanner(client))

        response = agent.review_pilot(self.seed_case, self.seed_actuals)

        self.assertEqual(response.runtime.mode, "llm")
        self.assertEqual(response.runtime.request_id, "req_review_123")
        self.assertEqual(response.review.final_decision, "Scale")
        self.assertIn("justify scaling", response.review.executive_summary)
        self.assertEqual(transport.requests[0]["payload"]["text"]["format"]["name"], "ops_pilot_post_pilot_review")

    def test_agent_falls_back_when_llm_request_fails_in_auto_mode(self) -> None:
        transport = FakeTransport(
            [
                TransportResponse(
                    status=500,
                    headers={},
                    body=json.dumps({"error": {"message": "temporary upstream failure"}}).encode("utf-8"),
                )
            ]
        )
        config = AgentConfig(
            mode="auto",
            provider="openai",
            api_key="test-key",
            model="gpt-4.1-mini",
            base_url="https://example.com/v1",
            max_retries=0,
        )
        client = OpenAIResponsesClient(
            api_key=config.api_key or "",
            model=config.model,
            base_url=config.base_url,
            max_retries=0,
            transport=transport,
        )
        agent = OpsPilotAgent(config=config, llm_planner=OpsPilotLLMPlanner(client))

        response = agent.analyze(self.seed_case)

        self.assertEqual(response.runtime.mode, "deterministic")
        self.assertTrue(response.runtime.used_fallback)
        self.assertTrue(any("temporary upstream failure" in item for item in response.runtime.warnings))
        self.assertEqual(response.brief.opportunity_score.recommendation, "Pilot now")


if __name__ == "__main__":
    unittest.main()
