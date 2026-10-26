"""Structured-output helper validating against Pydantic models with feedback retry."""

import json
import logging
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from backend.app.llm.client import LLMClient
from backend.app.llm.exceptions import LLMError

logger = logging.getLogger("backend.app.llm")
T = TypeVar("T", bound=BaseModel)


def complete_structured(
    client: LLMClient,
    alias: str,
    messages: list[dict[str, Any]],
    schema_model: type[T],
    max_retries: int = 2,
    temperature: float = 0.0,
    **kwargs: Any,
) -> T:
    """Request structured JSON and validate against Pydantic schema with feedback retry.

    Per FR-LLM-004: if validation fails, feeds back validation error in subsequent retry.
    """
    json_schema = schema_model.model_json_schema()
    response_format = {
        "type": "json_object",
        "schema": json_schema,
    }

    current_messages = list(messages)

    for attempt in range(max_retries + 1):
        resp = client.complete(
            alias=alias,
            messages=current_messages,
            response_format=response_format,
            temperature=temperature,
            **kwargs,
        )

        choice = resp.get("choices", [{}])[0]
        msg = choice.get("message", {})
        content_raw = (msg.get("content") or msg.get("reasoning_content") or "").strip()

        try:
            return schema_model.model_validate_json(content_raw)
        except (ValidationError, json.JSONDecodeError) as parse_err:
            cleaned = content_raw
            if "```json" in cleaned:
                cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "```" in cleaned:
                cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()
            elif "{" in cleaned and "}" in cleaned:
                start = cleaned.find("{")
                end = cleaned.rfind("}") + 1
                cleaned = cleaned[start:end].strip()
            try:
                try:
                    parsed_dict = json.loads(cleaned, strict=False)
                    return schema_model.model_validate(parsed_dict)
                except Exception:
                    return schema_model.model_validate_json(cleaned)
            except (ValidationError, json.JSONDecodeError) as exc:
                logger.warning(
                    "Structured output validation failed (attempt %d/%d): %s",
                    attempt + 1,
                    max_retries,
                    exc,
                )
                if attempt < max_retries:
                    # Append assistant attempt and user correction prompt
                    current_messages.append({"role": "assistant", "content": content_raw})
                    current_messages.append({
                        "role": "user",
                        "content": (
                            f"Your output did not conform to the expected schema. Error: {exc}. "
                            "Please respond with valid JSON matching the schema exactly."
                        ),
                    })
                else:
                    err_msg = f"Structured output validation failed after {max_retries} retries: {exc}"
                    raise LLMError(err_msg) from exc

    raise LLMError("Structured completion loop terminated unexpectedly")
