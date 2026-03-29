from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Protocol
from urllib import error, request

from .analysis import AnalysisSnapshot
from .models import KPI, PainPoint, PilotBrief, RiskItem, RolloutStep, WorkflowCase
from .utils import normalize_whitespace


class LLMError(RuntimeError):
    """Raised when the configured LLM provider fails or returns invalid output."""


@dataclass(slots=True)
class TransportResponse:
    status: int
    headers: dict[str, str]
    body: bytes


class JsonTransport(Protocol):
    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> TransportResponse: ...


class UrllibJsonTransport:
    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> TransportResponse:
        raw_payload = json.dumps(payload).encode("utf-8")
        http_request = request.Request(url, data=raw_payload, headers=headers, method="POST")
        try:
            with request.urlopen(http_request, timeout=timeout_seconds) as response:
                return TransportResponse(
                    status=response.status,
                    headers=dict(response.headers.items()),
                    body=response.read(),
                )
        except error.HTTPError as exc:
            return TransportResponse(
                status=exc.code,
                headers=dict(exc.headers.items()) if exc.headers is not None else {},
                body=exc.read(),
            )


@dataclass(slots=True)
class StructuredOutputResult:
    payload: dict[str, Any]
    request_id: str | None
    model: str | None


@dataclass(slots=True)
class LLMBriefDraft:
    problem_statement: str
    current_state: str
    why_now: str
    proposed_solution: str
    recommendation_detail: str
    pain_points: list[PainPoint]
    kpis: list[KPI]
    risks: list[RiskItem]
    rollout_steps: list[RolloutStep]
    next_steps: list[str]
    assumptions: list[str]


class OpenAIResponsesClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        max_output_tokens: int = 2200,
        transport: JsonTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.max_output_tokens = max_output_tokens
        self.transport = transport or UrllibJsonTransport()

    def create_structured_output(
        self,
        *,
        instructions: str,
        user_input: str,
        schema_name: str,
        schema: dict[str, Any],
    ) -> StructuredOutputResult:
        if not self.api_key:
            raise LLMError("OPENAI_API_KEY is not configured.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "instructions": instructions,
            "input": user_input,
            "max_output_tokens": self.max_output_tokens,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
        }

        last_error: str | None = None
        for attempt in range(self.max_retries + 1):
            response = self.transport.post_json(
                f"{self.base_url}/responses",
                headers,
                payload,
                self.timeout_seconds,
            )
            if 200 <= response.status < 300:
                return self._parse_success(response)

            error_message = self._parse_error(response)
            last_error = error_message
            should_retry = response.status in {408, 409, 429, 500, 502, 503, 504} and attempt < self.max_retries
            if should_retry:
                time.sleep(min(2**attempt, 4))
                continue
            raise LLMError(error_message)

        raise LLMError(last_error or "Unknown LLM request failure.")

    def _parse_success(self, response: TransportResponse) -> StructuredOutputResult:
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise LLMError(f"LLM provider returned invalid JSON: {exc}") from exc

        output_text = _extract_output_text(payload)
        try:
            structured = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Structured output could not be parsed as JSON: {exc}") from exc

        return StructuredOutputResult(
            payload=structured,
            request_id=response.headers.get("x-request-id") or payload.get("id"),
            model=payload.get("model") or self.model,
        )

    def _parse_error(self, response: TransportResponse) -> str:
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except json.JSONDecodeError:
            body = response.body.decode("utf-8", errors="replace").strip()
            return f"LLM request failed with status {response.status}: {body or 'no response body'}"

        error_payload = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error_payload, dict):
            message = error_payload.get("message") or error_payload.get("type") or "Unknown API error."
            return f"LLM request failed with status {response.status}: {message}"
        return f"LLM request failed with status {response.status}."


class OpsPilotLLMPlanner:
    def __init__(self, client: OpenAIResponsesClient) -> None:
        self.client = client

    def generate_brief(self, case: WorkflowCase, snapshot: AnalysisSnapshot) -> tuple[PilotBrief, str | None]:
        instructions = (
            "You are Ops Pilot, an AI transformation advisor for small teams. "
            "Write a concise, executive-ready pilot brief grounded in the provided case, evidence, and deterministic analysis. "
            "Do not invent evidence. Do not change numeric ROI values or the recommendation label. "
            "Keep the plan human-in-the-loop and production-minded. "
            "Return only valid JSON matching the schema."
        )
        user_input = json.dumps(
            {
                "workflow_case": case.to_dict(),
                "analysis_snapshot": snapshot.to_dict(),
                "task": {
                    "goal": "Refine the deterministic draft into a production-ready brief.",
                    "deterministic_recommendation_label": snapshot.opportunity_score.recommendation,
                    "rules": [
                        "recommendation_detail should not repeat the recommendation label",
                        "pain_points, kpis, risks, and rollout_steps should stay tightly scoped to a small-team pilot",
                        "assumptions should call out uncertainty rather than hiding it",
                        "preserve ROI and scoring numbers from the deterministic analysis",
                    ],
                },
            },
            indent=2,
        )
        result = self.client.create_structured_output(
            instructions=instructions,
            user_input=user_input,
            schema_name="ops_pilot_brief",
            schema=_ops_pilot_brief_schema(),
        )
        draft = _parse_brief_draft(result.payload)
        return _merge_brief(case, snapshot, draft), result.request_id


def _ops_pilot_brief_schema() -> dict[str, Any]:
    text_field = {"type": "string"}
    pain_point = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": text_field,
            "description": text_field,
            "frequency": {"type": "string", "enum": ["Occasional", "Recurring", "Very frequent"]},
            "severity": {"type": "string", "enum": ["low", "medium", "high"]},
        },
        "required": ["title", "description", "frequency", "severity"],
    }
    kpi = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "name": text_field,
            "target": text_field,
            "rationale": text_field,
        },
        "required": ["name", "target", "rationale"],
    }
    risk = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "name": text_field,
            "level": {"type": "string", "enum": ["low", "medium", "high"]},
            "mitigation": text_field,
        },
        "required": ["name", "level", "mitigation"],
    }
    rollout_step = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "phase": text_field,
            "action": text_field,
            "owner": text_field,
            "success_gate": text_field,
        },
        "required": ["phase", "action", "owner", "success_gate"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "problem_statement": text_field,
            "current_state": text_field,
            "why_now": text_field,
            "proposed_solution": text_field,
            "recommendation_detail": text_field,
            "pain_points": {"type": "array", "items": pain_point},
            "kpis": {"type": "array", "items": kpi},
            "risks": {"type": "array", "items": risk},
            "rollout_steps": {"type": "array", "items": rollout_step},
            "next_steps": {"type": "array", "items": text_field},
            "assumptions": {"type": "array", "items": text_field},
        },
        "required": [
            "problem_statement",
            "current_state",
            "why_now",
            "proposed_solution",
            "recommendation_detail",
            "pain_points",
            "kpis",
            "risks",
            "rollout_steps",
            "next_steps",
            "assumptions",
        ],
    }


def _parse_brief_draft(payload: dict[str, Any]) -> LLMBriefDraft:
    if not isinstance(payload, dict):
        raise LLMError("Structured output payload must be a JSON object.")

    return LLMBriefDraft(
        problem_statement=_require_text(payload, "problem_statement"),
        current_state=_require_text(payload, "current_state"),
        why_now=_require_text(payload, "why_now"),
        proposed_solution=_require_text(payload, "proposed_solution"),
        recommendation_detail=_require_text(payload, "recommendation_detail"),
        pain_points=[
            PainPoint(
                title=_require_text(item, "title"),
                description=_require_text(item, "description"),
                frequency=_require_text(item, "frequency"),
                severity=_require_text(item, "severity"),
            )
            for item in _require_list(payload, "pain_points")
        ],
        kpis=[
            KPI(
                name=_require_text(item, "name"),
                target=_require_text(item, "target"),
                rationale=_require_text(item, "rationale"),
            )
            for item in _require_list(payload, "kpis")
        ],
        risks=[
            RiskItem(
                name=_require_text(item, "name"),
                level=_require_text(item, "level"),
                mitigation=_require_text(item, "mitigation"),
            )
            for item in _require_list(payload, "risks")
        ],
        rollout_steps=[
            RolloutStep(
                phase=_require_text(item, "phase"),
                action=_require_text(item, "action"),
                owner=_require_text(item, "owner"),
                success_gate=_require_text(item, "success_gate"),
            )
            for item in _require_list(payload, "rollout_steps")
        ],
        next_steps=[normalize_whitespace(item) for item in _require_string_list(payload, "next_steps")],
        assumptions=[normalize_whitespace(item) for item in _require_string_list(payload, "assumptions")],
    )


def _merge_brief(case: WorkflowCase, snapshot: AnalysisSnapshot, draft: LLMBriefDraft) -> PilotBrief:
    deterministic = snapshot.brief
    detail = _strip_recommendation_prefix(
        draft.recommendation_detail,
        snapshot.opportunity_score.recommendation,
    )
    recommendation = f"{snapshot.opportunity_score.recommendation}. {detail}".strip()

    assumptions = list(dict.fromkeys([*deterministic.assumptions, *draft.assumptions]))
    next_steps = draft.next_steps[:4] or deterministic.next_steps

    return PilotBrief(
        title=deterministic.title,
        problem_statement=draft.problem_statement or deterministic.problem_statement,
        current_state=draft.current_state or deterministic.current_state,
        why_now=draft.why_now or deterministic.why_now,
        proposed_solution=draft.proposed_solution or deterministic.proposed_solution,
        evidence=deterministic.evidence,
        pain_points=draft.pain_points[:4] or deterministic.pain_points,
        opportunity_score=deterministic.opportunity_score,
        roi_estimate=deterministic.roi_estimate,
        kpis=draft.kpis[:4] or deterministic.kpis,
        risks=draft.risks[:4] or deterministic.risks,
        rollout_steps=draft.rollout_steps[:4] or deterministic.rollout_steps,
        recommendation=recommendation,
        next_steps=next_steps,
        assumptions=assumptions,
    )


def _extract_output_text(payload: dict[str, Any]) -> str:
    direct_text = payload.get("output_text")
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text

    parts: list[str] = []
    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                parts.append(content["text"])

    if parts:
        return "\n".join(parts)
    raise LLMError("LLM response did not contain any output text.")


def _require_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not normalize_whitespace(value):
        raise LLMError(f"Structured output field `{key}` must be a non-empty string.")
    return normalize_whitespace(value)


def _require_list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise LLMError(f"Structured output field `{key}` must be a non-empty list.")
    for item in value:
        if not isinstance(item, dict):
            raise LLMError(f"Structured output field `{key}` must contain only JSON objects.")
    return value


def _require_string_list(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise LLMError(f"Structured output field `{key}` must be a non-empty list.")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not normalize_whitespace(item):
            raise LLMError(f"Structured output field `{key}` must contain only non-empty strings.")
        items.append(normalize_whitespace(item))
    return items


def _strip_recommendation_prefix(text: str, label: str) -> str:
    normalized_text = normalize_whitespace(text)
    normalized_label = normalize_whitespace(label)
    lowered_text = normalized_text.lower()
    lowered_label = normalized_label.lower()
    if lowered_text.startswith(lowered_label):
        trimmed = normalized_text[len(normalized_label) :].lstrip(" .:-")
        return trimmed or "Proceed with a scoped, measurable pilot."
    return normalized_text
