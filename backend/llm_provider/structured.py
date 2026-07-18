from __future__ import annotations

import json
import logging
from typing import Any, Optional, TypeVar

from backend.llm_provider.models import FinishReason, LLMRequest, LLMResponse

log = logging.getLogger(__name__)

T = TypeVar("T")


class SchemaValidationError(Exception):
    pass


class StructuredOutputHandler:
    def __init__(self, max_retries: int = 3) -> None:
        self._max_retries = max_retries

    async def generate_structured(
        self,
        generate_fn: Any,
        request: LLMRequest,
        schema: dict[str, Any],
        max_retries: Optional[int] = None,
    ) -> LLMResponse:
        retries = max_retries or self._max_retries
        request.response_format = {"type": "json_object"}

        schema_desc = self._schema_to_instruction(schema)
        if request.system_prompt:
            request.system_prompt += f"\n\n{schema_desc}"
        else:
            request.system_prompt = schema_desc

        last_error: Optional[str] = None
        for attempt in range(retries + 1):
            response = await generate_fn(request)
            if response.error:
                return response

            content = response.content.strip()
            parsed, error = self._validate_json(content, schema)
            if parsed is not None:
                response.raw = {"parsed": parsed, "schema": schema}
                return response

            last_error = error
            log.warning("Structured output validation failed (attempt %d/%d): %s",
                        attempt + 1, retries + 1, error)
            if attempt < retries:
                request.system_prompt = (request.system_prompt or "") + (
                    f"\n\nPrevious attempt failed JSON validation: {error}. "
                    "Please respond with valid JSON matching the schema."
                )

        return LLMResponse(
            content="", model=response.model if response else "",
            provider=response.provider if response else "",
            error=f"Structured output failed after {retries + 1} attempts: {last_error}",
            finish_reason=FinishReason.ERROR,
        )

    def _validate_json(self, content: str, schema: dict[str, Any]) -> tuple[Optional[Any], Optional[str]]:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            json_match = self._extract_json(content)
            if json_match:
                try:
                    parsed = json.loads(json_match)
                except json.JSONDecodeError:
                    return None, f"Invalid JSON: {exc}"
            else:
                return None, f"Invalid JSON: {exc}"

        props = schema.get("properties", {})
        required = schema.get("required", [])
        for field_name in required:
            if field_name not in parsed:
                return None, f"Missing required field: {field_name}"

        for field_name, field_schema in props.items():
            if field_name in parsed:
                expected_type = field_schema.get("type", "string")
                value = parsed[field_name]
                if expected_type == "string" and not isinstance(value, str):
                    return None, f"Field '{field_name}' should be string, got {type(value).__name__}"
                elif expected_type == "number" and not isinstance(value, (int, float)):
                    return None, f"Field '{field_name}' should be number, got {type(value).__name__}"
                elif expected_type == "integer" and not isinstance(value, int):
                    return None, f"Field '{field_name}' should be integer, got {type(value).__name__}"
                elif expected_type == "boolean" and not isinstance(value, bool):
                    return None, f"Field '{field_name}' should be boolean, got {type(value).__name__}"
                elif expected_type == "array" and not isinstance(value, list):
                    return None, f"Field '{field_name}' should be array, got {type(value).__name__}"
                elif expected_type == "object" and not isinstance(value, dict):
                    return None, f"Field '{field_name}' should be object, got {type(value).__name__}"

        return parsed, None

    @staticmethod
    def _extract_json(text: str) -> Optional[str]:
        import re
        match = re.search(r'\{[\s\S]*\}', text)
        return match.group(0) if match else None

    @staticmethod
    def _schema_to_instruction(schema: dict[str, Any]) -> str:
        parts = ["You must respond with valid JSON matching this schema:"]
        parts.append(f"```json\n{json.dumps(schema, indent=2)}\n```")
        parts.append("Respond with ONLY the JSON object, no other text.")
        return "\n".join(parts)
