from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from backend.llm_provider.models import LLMRequest

log = logging.getLogger(__name__)

SYSTEM_PROMPTS: dict[str, str] = {
    "default": "You are CortexPrime, an autonomous AI assistant.",
    "code": "You are CortexPrime, an expert software engineer. Generate clean, well-structured code.",
    "reasoning": "You are CortexPrime, a reasoning expert. Think step by step and provide thorough analysis.",
    "creative": "You are CortexPrime, a creative assistant. Be imaginative and engaging.",
    "concise": "You are CortexPrime. Be concise and direct. Answer in 1-3 sentences when possible.",
    "analysis": "You are CortexPrime, a data analyst. Provide quantitative analysis with clear insights.",
    "research": "You are CortexPrime, a research assistant. Synthesize information from multiple sources.",
}


@dataclass
class PromptTemplate:
    template_id: str = field(default_factory=lambda: f"pt-{uuid.uuid4().hex[:8]}")
    name: str = ""
    version: str = "1.0"
    system_prompt: str = ""
    template: str = ""
    variables: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


class PromptRuntime:
    def __init__(self) -> None:
        self._templates: dict[str, PromptTemplate] = {}
        self._system_prompts: dict[str, str] = dict(SYSTEM_PROMPTS)

    def register_template(self, template: PromptTemplate) -> None:
        key = f"{template.name}:{template.version}"
        self._templates[key] = template
        log.info("Prompt template registered: %s (v%s)", template.name, template.version)

    def get_template(self, name: str, version: str = "1.0") -> Optional[PromptTemplate]:
        key = f"{name}:{version}"
        return self._templates.get(key)

    def list_templates(self) -> list[PromptTemplate]:
        return list(self._templates.values())

    def set_system_prompt(self, name: str, prompt: str) -> None:
        self._system_prompts[name] = prompt

    def get_system_prompt(self, name: str = "default") -> str:
        return self._system_prompts.get(name, self._system_prompts["default"])

    def list_system_prompts(self) -> dict[str, str]:
        return dict(self._system_prompts)

    def render_template(
        self,
        template: PromptTemplate,
        variables: Optional[dict[str, str]] = None,
    ) -> str:
        text = template.template
        if variables:
            for key, value in variables.items():
                text = text.replace(f"{{{{{key}}}}}", value)
        return text

    def build_request(
        self,
        prompt: str,
        *,
        system_prompt_name: str = "default",
        custom_system_prompt: Optional[str] = None,
        template_name: Optional[str] = None,
        template_version: str = "1.0",
        template_variables: Optional[dict[str, str]] = None,
        messages: Optional[list[dict[str, str]]] = None,
        **kwargs: Any,
    ) -> LLMRequest:
        system = custom_system_prompt or self.get_system_prompt(system_prompt_name)

        if template_name:
            tmpl = self.get_template(template_name, template_version)
            if tmpl:
                prompt = self.render_template(tmpl, template_variables)
                if tmpl.system_prompt:
                    system = tmpl.system_prompt

        combined_messages: list[dict[str, str]] = list(messages or [])
        if prompt:
            combined_messages.append({"role": "user", "content": prompt})

        return LLMRequest(
            system_prompt=system,
            messages=combined_messages,
            **{k: v for k, v in kwargs.items() if k in [
                "model", "temperature", "max_tokens", "stop",
                "functions", "function_call", "response_format",
                "stream", "timeout_seconds",
            ]},
        )

    def validate_prompt(self, prompt: str, max_length: int = 100000) -> Optional[str]:
        if not prompt or not prompt.strip():
            return "Prompt cannot be empty"
        if len(prompt) > max_length:
            return f"Prompt exceeds maximum length of {max_length} characters"
        return None


prompt_runtime = PromptRuntime()
