import pathlib

p_test = pathlib.Path("backend/tests/known_answer/test_agent_orchestrator.py")
content = p_test.read_text(encoding="utf-8")

old_text = """        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": f"{PLACEHOLDER_MARKER}. Quantitative audit completed from computed evidence. Educational and research analytics only. No investment advice.",
                    "tool_calls": None,
                }
            }],
            "usage": {"prompt_tokens": 150, "completion_tokens": 50},
        }"""

new_text = """        obs_snippets = []
        for line in last_msg.splitlines():
            line_str = line.strip()
            if any(k in line_str for k in ("was denied", "verified findings", "Reference data observed")):
                obs_snippets.append(line_str)
        obs_str = (" " + " ".join(obs_snippets)) if obs_snippets else ""

        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": f"{PLACEHOLDER_MARKER}. Quantitative audit completed from computed evidence.{obs_str} Educational and research analytics only. No investment advice.",
                    "tool_calls": None,
                }
            }],
            "usage": {"prompt_tokens": 150, "completion_tokens": 50},
        }"""

# Normalize CRLF to LF for reliable replace, then write back
content = content.replace("\r\n", "\n")
old_text = old_text.replace("\r\n", "\n")
new_text = new_text.replace("\r\n", "\n")

assert old_text in content, "old_text not found in content"
content = content.replace(old_text, new_text)

p_test.write_text(content, encoding="utf-8")
print("Successfully replaced SmartTestProvider return block")

