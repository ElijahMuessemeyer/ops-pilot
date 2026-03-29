from __future__ import annotations

import os
from dataclasses import dataclass


VALID_AGENT_MODES = {"auto", "llm", "deterministic"}


@dataclass(slots=True)
class AgentConfig:
    mode: str = "auto"
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    api_key: str | None = None
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: float = 30.0
    max_retries: int = 2
    max_output_tokens: int = 2200

    @classmethod
    def from_env(cls) -> AgentConfig:
        mode = os.getenv("OPS_PILOT_AGENT_MODE", "auto").strip().lower() or "auto"
        if mode not in VALID_AGENT_MODES:
            raise ValueError(
                f"Unsupported OPS_PILOT_AGENT_MODE `{mode}`. Expected one of: {', '.join(sorted(VALID_AGENT_MODES))}."
            )

        provider = os.getenv("OPS_PILOT_LLM_PROVIDER", "openai").strip().lower() or "openai"
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPS_PILOT_OPENAI_API_KEY")
        base_url = (
            os.getenv("OPENAI_BASE_URL")
            or os.getenv("OPS_PILOT_OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")

        return cls(
            mode=mode,
            provider=provider,
            model=os.getenv("OPS_PILOT_OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini",
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=float(os.getenv("OPS_PILOT_TIMEOUT_SECONDS", "30")),
            max_retries=int(os.getenv("OPS_PILOT_MAX_RETRIES", "2")),
            max_output_tokens=int(os.getenv("OPS_PILOT_MAX_OUTPUT_TOKENS", "2200")),
        )

    def wants_llm(self) -> bool:
        return self.mode in {"auto", "llm"}

    def llm_required(self) -> bool:
        return self.mode == "llm"

    def llm_ready(self) -> bool:
        return self.provider == "openai" and bool(self.api_key)
