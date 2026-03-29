from __future__ import annotations

import argparse
import json
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .llm import LLMError
from .models import SourceDocument, WorkflowCase
from .service import OpsPilotAgent

STATIC_DIR = Path(__file__).resolve().parent / "static"


class OpsPilotHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def server_bind(self) -> None:
        self.socket.bind(self.server_address)
        self.server_address = self.socket.getsockname()
        host, port = self.server_address[:2]
        self.server_name = host
        self.server_port = port


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    agent: OpsPilotAgent | None = None,
) -> ThreadingHTTPServer:
    agent = agent or OpsPilotAgent()
    handler = partial(OpsPilotRequestHandler, agent=agent)
    return OpsPilotHTTPServer((host, port), handler)


class OpsPilotRequestHandler(BaseHTTPRequestHandler):
    server_version = "OpsPilotHTTP/1.0"
    protocol_version = "HTTP/1.0"

    def __init__(self, *args, agent: OpsPilotAgent, **kwargs) -> None:
        self.agent = agent
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self._serve_static("index.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/static/style.css":
            self._serve_static("style.css", "text/css; charset=utf-8")
            return
        if parsed.path == "/static/app.js":
            self._serve_static("app.js", "application/javascript; charset=utf-8")
            return
        if parsed.path == "/api/health":
            self._send_json({"ok": True, "service": "ops_pilot", **self.agent.runtime_status()})
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/analyze":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON body."}, status=HTTPStatus.BAD_REQUEST)
            return

        try:
            case = workflow_case_from_payload(payload)
        except ValueError as error:
            self._send_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
            return

        try:
            response = self.agent.analyze(case)
        except LLMError as error:
            self._send_json({"error": str(error)}, status=HTTPStatus.BAD_GATEWAY)
            return
        self._send_json(response.to_dict())

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _serve_static(self, filename: str, content_type: str) -> None:
        file_path = STATIC_DIR / filename
        if not file_path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Static file missing")
            return
        content = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def workflow_case_from_payload(payload: dict) -> WorkflowCase:
    title = str(payload.get("title", "")).strip()
    team_type = str(payload.get("team_type", "")).strip() or "Small team"
    workflow_goal = str(payload.get("workflow_goal", "")).strip()
    current_process = str(payload.get("current_process", "")).strip()
    desired_outcome = str(payload.get("desired_outcome", "")).strip()

    if not title:
        raise ValueError("`title` is required.")
    if not workflow_goal and not current_process:
        raise ValueError("Provide at least `workflow_goal` or `current_process`.")

    documents = payload.get("documents", [])
    source_documents = [
        SourceDocument(
            name=str(document.get("name", "uploaded.txt")),
            kind="text",
            content=str(document.get("content", "")),
        )
        for document in documents
        if str(document.get("content", "")).strip()
    ]

    return WorkflowCase(
        title=title,
        team_type=team_type,
        workflow_goal=workflow_goal,
        current_process=current_process,
        desired_outcome=desired_outcome,
        task_volume_per_week=_maybe_int(payload.get("task_volume_per_week")),
        manual_hours_per_week=_maybe_float(payload.get("manual_hours_per_week")),
        average_cycle_time_hours=_maybe_float(payload.get("average_cycle_time_hours")),
        average_error_rate_pct=_maybe_float(payload.get("average_error_rate_pct")),
        cost_per_hour=_maybe_float(payload.get("cost_per_hour")) or 25.0,
        source_documents=source_documents,
    )


def _maybe_int(value: object) -> int | None:
    if value in ("", None):
        return None
    return int(value)


def _maybe_float(value: object) -> float | None:
    if value in ("", None):
        return None
    return float(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Ops Pilot web server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = create_server(host=args.host, port=args.port)
    host, port = server.server_address
    print(f"Ops Pilot running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
