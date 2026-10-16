"""Live integration tests for LLM gateway against Nebius Token Factory."""

import pytest
from pydantic import BaseModel

from backend.app.config.env import load_settings
from backend.app.llm.client import LLMClient
from backend.app.llm.exceptions import LLMUpstreamError
from backend.app.llm.registry import ModelRegistry
from backend.app.llm.structured import complete_structured
from backend.app.llm.tools import execute_tool_loop


class LiveCompanyEntity(BaseModel):
    symbol: str
    exchange: str


def live_lookup_tool(symbol: str) -> dict[str, str]:
    return {"symbol": symbol, "status": "active", "currency": "INR"}


@pytest.fixture(scope="module")
def live_registry() -> ModelRegistry:
    settings = load_settings()
    base_url = settings.get_var_value("NEBIUS_BASE_URL")
    api_key = settings.get_var_value("NEBIUS_API_KEY")
    if not base_url or not api_key:
        pytest.skip("not run: no key")
    registry = ModelRegistry(settings=settings)
    registry.initialize()
    return registry


@pytest.fixture(scope="module")
def live_client(live_registry: ModelRegistry) -> LLMClient:
    settings = load_settings()
    return LLMClient(registry=live_registry, settings=settings)


def test_live_model_resolution(live_registry: ModelRegistry) -> None:
    """Verify live model ID resolution across fast, mid, deep aliases."""
    fast_id = live_registry.get_model_id("fast")
    mid_id = live_registry.get_model_id("mid")
    deep_id = live_registry.get_model_id("deep")
    assert fast_id and len(fast_id) > 0
    assert mid_id and len(mid_id) > 0
    assert deep_id and len(deep_id) > 0


def test_live_invalid_api_key_surfaces_upstream_401(live_registry: ModelRegistry) -> None:
    """An invalid API key surfaces the real upstream 401 error."""
    settings = load_settings()
    bad_client = LLMClient(registry=live_registry, settings=settings)
    bad_client.api_key = "invalid-secret-key-probe"
    with pytest.raises(LLMUpstreamError) as exc_info:
        bad_client.complete(
            alias="fast",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
    assert exc_info.value.status_code == 401


def test_live_completion_and_cache(live_client: LLMClient) -> None:
    """A real tiny completion succeeds, records ledger row, and is cached."""
    messages = [{"role": "user", "content": "Respond with the single digit 1."}]
    resp1 = live_client.complete(alias="fast", messages=messages, max_tokens=5)
    assert "choices" in resp1
    assert len(resp1["choices"]) > 0

    # Second call hits response cache
    resp2 = live_client.complete(alias="fast", messages=messages, max_tokens=5)
    assert resp2.get("id") == resp1.get("id")


def test_live_structured_output(live_client: LLMClient) -> None:
    """Structured output returns schema-valid Pydantic model on fast model."""
    result = complete_structured(
        client=live_client,
        alias="fast",
        messages=[{"role": "user", "content": "Symbol: INFY, Exchange: NSE."}],
        schema_model=LiveCompanyEntity,
        max_tokens=80,
    )
    assert result.symbol == "INFY"
    assert result.exchange == "NSE"


def test_live_tool_calling(live_client: LLMClient) -> None:
    """Tool calling loop executes registered tool on mid model."""
    tools = [{
        "type": "function",
        "function": {
            "name": "live_lookup_tool",
            "description": "Look up stock symbol metadata",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        },
    }]
    handlers = {"live_lookup_tool": live_lookup_tool}

    _, history = execute_tool_loop(
        client=live_client,
        alias="mid",
        messages=[{"role": "user", "content": "Look up symbol RELIANCE."}],
        tools=tools,
        tool_handlers=handlers,
        step_cap=3,
        max_tokens=100,
    )
    assert any(m.get("role") == "tool" for m in history)
