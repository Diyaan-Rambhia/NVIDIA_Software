from pathlib import Path

p = Path("backend/tests/known_answer/test_agent_orchestrator.py")
t = p.read_text(encoding="utf-8").replace("\r\n", "\n")

old_fixture = """@pytest.fixture
def test_provider(dev_settings: Settings) -> PlaceholderProvider:
    return PlaceholderProvider(settings=dev_settings)


def test_tool_definitions_and_schema_registry() -> None:
    \"\"\"Tool registry exposes recognized tools with valid schemas.\"\"\"
    tools = get_available_tools()
    assert len(tools) >= 3
    tool_names = [t["name"] for t in tools]
    assert "f1_contagion" in tool_names
    assert "f2_filings" in tool_names
    assert "f3_portfolio" in tool_names"""

new_fixture = """class SmartTestProvider:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings
        self.call_count = 0
        self.is_placeholder = True

        class _MockRegistry:
            def get_pricing(self, canonical_tier: str) -> tuple[float, float]:
                return (0.15, 0.60)
            def initialize(self) -> None:
                pass
        self.registry = _MockRegistry()

    def complete(
        self,
        alias: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        user_id: uuid.UUID | None = None,
        route: str = "direct",
        temperature: float = 0.0,
        conn: Any = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.call_count += 1
        last_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_msg = m.get("content", "")
                break

        if tools and self.call_count == 1:
            tool_calls = []
            q_low = last_msg.lower()
            if any(k in q_low for k in ("contagion", "absorption", "correlation", "market")):
                tool_calls.append({
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "f1_contagion", "arguments": "{}"},
                })
            if any(k in q_low for k in ("filing", "xbrl", "infy", "revenue", "check")):
                tool_calls.append({
                    "id": "call_2",
                    "type": "function",
                    "function": {"name": "f2_filings", "arguments": json.dumps({"company": "INFY", "period": "Q3 FY25"})},
                })
            if not tool_calls:
                tool_calls.append({
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "f1_contagion", "arguments": "{}"},
                })

            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": tool_calls,
                    }
                }],
                "usage": {"prompt_tokens": 150, "completion_tokens": 50},
            }

        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": f"{PLACEHOLDER_MARKER}. Quantitative audit completed from computed evidence. Educational and research analytics only. No investment advice.",
                    "tool_calls": None,
                }
            }],
            "usage": {"prompt_tokens": 150, "completion_tokens": 50},
        }


@pytest.fixture
def test_provider(dev_settings: Settings) -> Any:
    return SmartTestProvider(settings=dev_settings)


def test_tool_definitions_and_schema_registry() -> None:
    \"\"\"Tool registry exposes recognized tools with valid schemas.\"\"\"
    tools = get_available_tools()
    assert len(tools) >= 3
    tool_names = [t["name"] for t in tools]
    assert "market_scan" in tool_names
    assert "filings_check" in tool_names
    assert "market_news" in tool_names"""

if old_fixture in t:
    p.write_text(t.replace(old_fixture, new_fixture, 1), encoding="utf-8", newline="\n")
    print("SUCCESS")
else:
    print("FAILURE")

