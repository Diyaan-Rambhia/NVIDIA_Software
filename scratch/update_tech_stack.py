from pathlib import Path

path = Path("project_docs/tech_stack.md")
text = path.read_text(encoding="utf-8")
norm_text = text.replace("\r\n", "\n")

# 1. Add endpoint /agent/ask/stream
old_endpoint = "| `/agent/ask` | `POST` | No | Ask Agent |"
new_endpoint = """| `/agent/ask` | `POST` | No | Ask Agent |
| `/agent/ask/stream` | `POST` | No | Ask Agent Stream |"""

# 2. Update section 9.5 with agent parameters and model-driven tool calling
old_section = """### 9.5 Multi-Step Agent Loop
The orchestrator in `backend/app/agent/orchestrator.py` runs multi-turn tool loops:
1. Receives user query.
2. Formulates tool-calling request to Nemotron model.
3. Validates tool arguments against strict Pydantic schemas.
4. Executes requested tool in local execution sandbox.
5. Feeds tool execution results back to model.
6. Terminates when model yields final answer or step limit is reached."""

new_section = """### 9.5 Multi-Step Agent Loop
The orchestrator in `backend/app/agent/orchestrator.py` runs multi-turn tool loops using model-driven tool calling without keyword routing:
1. Receives user query, active conversation history up to `agent_history_max_messages` and `agent_history_max_chars`, and optional attachment text.
2. Constructs system instructions using clock dates and configured application identity `agent_product_name` and decline response `agent_decline_text`.
3. Passes standard tools (`market_scan`, `filings_check`, `market_news`) through the OpenAI tools parameter.
4. Executes selected tools with in-tool plan entitlement checks, enforcing derived numbers only with as_of and fetched_at timestamps.
5. Handles stale market scan data older than `agent_stale_data_days` with delayed data warnings.
6. Enforces grounding verification for all numeric claims above `agent_grounding_number_limit` with a single retry before falling back to deterministic summaries."""

# 3. Add decision D-91
old_dec = "| `DECISIONS.md D-87` | Live agent tools, Contagion news TTL caching, and trade log file verification help |"
new_dec = """| `DECISIONS.md D-87` | Live agent tools, Contagion news TTL caching, and trade log file verification help |
| `DECISIONS.md D-91` | Removal of agent keyword router and adoption of model-driven tool calling |"""

if old_endpoint in norm_text and old_section in norm_text and old_dec in norm_text:
    res = norm_text.replace(old_endpoint, new_endpoint, 1)
    res = res.replace(old_section, new_section, 1)
    res = res.replace(old_dec, new_dec, 1)
    path.write_text(res, encoding="utf-8", newline="\n")
    print("SUCCESS")
else:
    print("FAILURE")

