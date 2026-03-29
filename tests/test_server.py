from __future__ import annotations

import json
import sys
import threading
import time
import unittest
from http.client import HTTPConnection
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ops_pilot.config import AgentConfig
from ops_pilot.server import create_server
from ops_pilot.service import OpsPilotAgent


class ServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = create_server(
            host="127.0.0.1",
            port=0,
            agent=OpsPilotAgent(config=AgentConfig(mode="deterministic")),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.05)
        host, port = self.server.server_address
        self.connection = HTTPConnection(host, port, timeout=5)

    def tearDown(self) -> None:
        self.connection.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_health_endpoint(self) -> None:
        self.connection.request("GET", "/api/health")
        response = self.connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(response.status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["agent_mode"], "deterministic")
        self.assertFalse(payload["llm_ready"])

    def test_analyze_endpoint_returns_brief(self) -> None:
        payload = {
            "title": "Student org event follow-up",
            "team_type": "Student organization",
            "workflow_goal": "Coordinate sponsor follow-up, volunteer recap, and next-step assignments after each weekly event planning meeting.",
            "current_process": "The president and operations lead review notes, rewrite action items into a spreadsheet, send recap emails, and manually check who responded.",
            "desired_outcome": "reduce coordination overhead and make follow-up more reliable",
            "documents": [
                {
                    "name": "notes.md",
                    "content": "The team handles 20 tasks per week, spends 6 hours per week on manual follow-up, and sees 12% rework because updates are missed.",
                }
            ],
        }

        self.connection.request(
            "POST",
            "/api/analyze",
            body=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        response = self.connection.getresponse()
        result = json.loads(response.read().decode("utf-8"))

        self.assertEqual(response.status, 200)
        self.assertEqual(result["brief"]["opportunity_score"]["recommendation"], "Pilot now")
        self.assertIn("markdown", result)


if __name__ == "__main__":
    unittest.main()
