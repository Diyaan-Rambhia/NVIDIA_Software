"""Deterministic tool execution loop per FR-LLM-005."""

import json
import logging
from collections.abc import Callable
from typing import Any

from backend.app.llm.client import LLMClient
from backend.app.llm.exceptions import LLMError

logger = logging.getLogger("backend.app.llm")


def execute_tool_loop(
    client: LLMClient,
    alias: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_handlers: dict[str, Callable[..., Any]],
    step_cap: int = 5,
    token_cap: int = 4000,
    **kwargs: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Execute tool-calling conversation loop with step cap and token cap.

    The model proposes tool calls; ONLY our deterministic code executes them.
    Returns (final_response, conversation_history).
    """
    history = list(messages)
    cumulative_tokens = 0

    for step in range(step_cap):
        resp = client.complete(
            alias=alias,
            messages=history,
            tools=tools,
            **kwargs,
        )

        usage = resp.get("usage", {})
        cumulative_tokens += usage.get("total_tokens", 0)
        if cumulative_tokens > token_cap:
            err_msg = (
                f"Cumulative token cap of {token_cap} exceeded in tool loop "
                f"({cumulative_tokens} tokens)"
            )
            raise LLMError(err_msg)

        choice = resp.get("choices", [{}])[0]
        msg = choice.get("message", {})
        tool_calls = msg.get("tool_calls", [])

        history.append(msg)

        if not tool_calls:
            # Model emitted final response without tool calls
            return resp, history

        # Execute proposed tool calls deterministically
        for call in tool_calls:
            call_id = call.get("id", f"call_{step}")
            func = call.get("function", {})
            name = func.get("name")
            args_str = func.get("arguments", "{}")

            if name not in tool_handlers:
                result_str = json.dumps({"error": f"Tool '{name}' not found"})
            else:
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                    result = tool_handlers[name](**args)
                    result_str = json.dumps(result) if not isinstance(result, str) else result
                except Exception as exc:
                    logger.warning("Tool execution error for %s: %s", name, exc)
                    result_str = json.dumps({"error": f"Execution failed: {exc}"})

            history.append({
                "role": "tool",
                "tool_call_id": call_id,
                "name": name,
                "content": result_str,
            })

    raise LLMError(f"Step cap of {step_cap} reached in tool-call loop without termination")
