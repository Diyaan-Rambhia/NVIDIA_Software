from pathlib import Path

p = Path("backend/app/agent/tools.py")
t = p.read_text(encoding="utf-8").replace("\r\n", "\n")

old = """    for tool_name, tool_info in TOOL_DEFINITIONS.items():
        tools.append({
            "type": "function",
            "function": {"""

new = """    for tool_name, tool_info in TOOL_DEFINITIONS.items():
        tools.append({
            "name": tool_name,
            "type": "function",
            "description": tool_info["description"],
            "parameters": tool_info["parameters"],
            "function": {"""

if old in t:
    p.write_text(t.replace(old, new, 1), encoding="utf-8", newline="\n")
    print("SUCCESS")
else:
    print("FAILURE")

