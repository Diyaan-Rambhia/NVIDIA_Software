import pathlib

p_test = pathlib.Path("backend/tests/known_answer/test_agent_orchestrator.py")
text = p_test.read_text(encoding="utf-8")

old_return = '''        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": f"{PLACEHOLDER_MARKER}. Quantitative audit completed from computed evidence. Educational and research analytics only. No investment advice.",
                    "tool_calls": None,
                }
            }],
            "usage": {"prompt_tokens": 100, "completion_tokens": 40},
        }'''

new_return = '''        obs_snippets = []
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
            "usage": {"prompt_tokens": 100, "completion_tokens": 40},
        }'''

text = text.replace(old_return, new_return)
p_test.write_text(text, encoding="utf-8")
print("SmartTestProvider updated to echo obs_snippets")

