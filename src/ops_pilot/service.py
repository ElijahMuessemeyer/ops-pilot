from __future__ import annotations

from uuid import uuid4

from .analysis import build_analysis_snapshot
from .briefing import brief_to_markdown, post_pilot_review_to_markdown
from .config import AgentConfig
from .llm import LLMError, OpenAIResponsesClient, OpsPilotLLMPlanner
from .models import AgentResponse, AgentRuntime, PilotActuals, PostPilotResponse, SourceDocument, WorkflowCase
from .parsing import chunk_document
from .post_pilot import build_post_pilot_snapshot
from .retrieval import SimpleRetriever


class OpsPilotAgent:
    def __init__(
        self,
        *,
        config: AgentConfig | None = None,
        llm_planner: OpsPilotLLMPlanner | None = None,
    ) -> None:
        self.config = config or AgentConfig.from_env()
        self.llm_planner = llm_planner or self._build_llm_planner()

    def analyze(self, case: WorkflowCase) -> AgentResponse:
        trace_id = uuid4().hex[:12]
        chunks = self._build_chunks(case.source_documents, fallback_text=case.combined_text())
        retriever = SimpleRetriever(chunks)
        snapshot = build_analysis_snapshot(case, retriever)
        warnings = self._preflight_warnings()

        if self.llm_planner is None:
            return self._build_response(
                brief=snapshot.brief,
                clarifying_questions=snapshot.clarifying_questions,
                runtime=AgentRuntime(
                    trace_id=trace_id,
                    mode="deterministic",
                    provider=self.config.provider if self.config.wants_llm() else None,
                    model=self.config.model if self.config.wants_llm() else None,
                    warnings=warnings,
                ),
            )

        try:
            llm_brief, request_id = self.llm_planner.generate_brief(case, snapshot)
        except LLMError as error:
            if self.config.llm_required():
                raise
            return self._build_response(
                brief=snapshot.brief,
                clarifying_questions=snapshot.clarifying_questions,
                runtime=AgentRuntime(
                    trace_id=trace_id,
                    mode="deterministic",
                    provider=self.config.provider,
                    model=self.config.model,
                    request_id=None,
                    used_fallback=True,
                    warnings=[*warnings, str(error), "Fell back to the deterministic planner."],
                ),
            )

        return self._build_response(
            brief=llm_brief,
            clarifying_questions=snapshot.clarifying_questions,
            runtime=AgentRuntime(
                trace_id=trace_id,
                mode="llm",
                provider=self.config.provider,
                model=self.config.model,
                request_id=request_id,
                warnings=warnings,
            ),
        )

    def review_pilot(self, case: WorkflowCase, actuals: PilotActuals) -> PostPilotResponse:
        trace_id = uuid4().hex[:12]
        chunks = self._build_chunks(
            [*case.source_documents, *actuals.source_documents],
            fallback_text="\n\n".join(part for part in [case.combined_text(), actuals.combined_text()] if part).strip(),
        )
        retriever = SimpleRetriever(chunks)
        snapshot = build_post_pilot_snapshot(case, actuals, retriever)
        warnings = self._preflight_warnings()

        if self.llm_planner is None:
            return self._build_post_pilot_response(
                review=snapshot.review,
                clarifying_questions=snapshot.clarifying_questions,
                runtime=AgentRuntime(
                    trace_id=trace_id,
                    mode="deterministic",
                    provider=self.config.provider if self.config.wants_llm() else None,
                    model=self.config.model if self.config.wants_llm() else None,
                    warnings=warnings,
                ),
            )

        try:
            llm_review, request_id = self.llm_planner.generate_post_pilot_review(case, actuals, snapshot)
        except LLMError as error:
            if self.config.llm_required():
                raise
            return self._build_post_pilot_response(
                review=snapshot.review,
                clarifying_questions=snapshot.clarifying_questions,
                runtime=AgentRuntime(
                    trace_id=trace_id,
                    mode="deterministic",
                    provider=self.config.provider,
                    model=self.config.model,
                    request_id=None,
                    used_fallback=True,
                    warnings=[*warnings, str(error), "Fell back to the deterministic post-pilot review."],
                ),
            )

        return self._build_post_pilot_response(
            review=llm_review,
            clarifying_questions=snapshot.clarifying_questions,
            runtime=AgentRuntime(
                trace_id=trace_id,
                mode="llm",
                provider=self.config.provider,
                model=self.config.model,
                request_id=request_id,
                warnings=warnings,
            ),
        )

    def runtime_status(self) -> dict[str, object]:
        return {
            "agent_mode": self.config.mode,
            "provider": self.config.provider if self.config.wants_llm() else None,
            "model": self.config.model if self.config.wants_llm() else None,
            "llm_ready": self.llm_planner is not None,
        }

    def _build_llm_planner(self) -> OpsPilotLLMPlanner | None:
        if not self.config.wants_llm():
            return None
        if self.config.provider != "openai":
            if self.config.llm_required():
                raise ValueError(f"Unsupported LLM provider `{self.config.provider}`.")
            return None
        if not self.config.llm_ready():
            if self.config.llm_required():
                raise ValueError("LLM mode requires OPENAI_API_KEY.")
            return None

        client = OpenAIResponsesClient(
            api_key=self.config.api_key or "",
            model=self.config.model,
            base_url=self.config.base_url,
            timeout_seconds=self.config.timeout_seconds,
            max_retries=self.config.max_retries,
            max_output_tokens=self.config.max_output_tokens,
        )
        return OpsPilotLLMPlanner(client)

    def _preflight_warnings(self) -> list[str]:
        if not self.config.wants_llm():
            return []
        if self.config.provider != "openai":
            return [f"Provider `{self.config.provider}` is not supported yet. Using deterministic planning."]
        if not self.config.llm_ready():
            return ["OPENAI_API_KEY is not configured. Using deterministic planning."]
        return []

    def _build_response(
        self,
        *,
        brief,
        clarifying_questions,
        runtime: AgentRuntime,
    ) -> AgentResponse:
        return AgentResponse(
            brief=brief,
            markdown=brief_to_markdown(brief),
            clarifying_questions=clarifying_questions,
            runtime=runtime,
        )

    def _build_post_pilot_response(
        self,
        *,
        review,
        clarifying_questions,
        runtime: AgentRuntime,
    ) -> PostPilotResponse:
        return PostPilotResponse(
            review=review,
            markdown=post_pilot_review_to_markdown(review),
            clarifying_questions=clarifying_questions,
            runtime=runtime,
        )

    def _build_chunks(self, documents, *, fallback_text: str) -> list:
        chunks = []
        for document in documents:
            chunks.extend(chunk_document(document))
        if not chunks and fallback_text:
            chunks = chunk_document(SourceDocument(name="workflow_input.txt", kind="text", content=fallback_text))
        return chunks
