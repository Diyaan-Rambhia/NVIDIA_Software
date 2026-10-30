import pathlib

p_orch = pathlib.Path("backend/app/agent/orchestrator.py")
text = p_orch.read_text(encoding="utf-8")

old_block = '''        status_str = tool_res.get("status", "error")
        step_status = "denied" if status_str == "denied" else ("success" if status_str == "success" else "error")

        if step_status == "error":
            raise RuntimeError(f"Invalid tool output from '{name}': {tool_res.get('reason', 'Corrupted tool response format')}")
        elif step_status == "denied":
            out_summary = f"{tool_res.get('status_code', 403)}: {tool_res.get('reason', 'Entitlement denied')}"
        elif step_status == "success":
            out_summary = f"Success ({len(tool_res.get('data', {}))} keys returned)"
        else:
            out_summary = f"Error: {tool_res.get('reason', 'Failed')}"'''

new_block = '''        status_str = tool_res.get("status", "error")
        reason_str = str(tool_res.get("reason", ""))
        if "Corrupted" in reason_str:
            raise RuntimeError(f"Invalid tool output from '{name}': {reason_str}")

        if status_str == "denied":
            step_status = "denied"
            out_summary = f"{tool_res.get('status_code', 403)}: {reason_str or 'Entitlement denied'}"
        elif status_str == "success":
            step_status = "success"
            out_summary = f"Success ({len(tool_res.get('data', {}))} keys returned)"
        elif status_str == "unsupported":
            step_status = "unsupported"
            out_summary = f"Unsupported: {reason_str}"
        elif status_str == "not_found":
            step_status = "not_found"
            out_summary = f"Not found: {reason_str}"
        else:
            step_status = "error"
            out_summary = f"Error: {reason_str or 'Failed'}"'''

text = text.replace(old_block, new_block)

# Also update prompt_lines to include unsupported / error reasons
old_prompt_lines = '''        for obs in tool_observations:
            if obs.get("status") == "denied":
                prompt_lines.append(f"Tool '{obs.get('tool')}' was denied: {obs.get('reason')}")
            else:
                prompt_lines.append(json.dumps(obs, default=str))'''

new_prompt_lines = '''        for obs in tool_observations:
            if obs.get("status") == "denied":
                prompt_lines.append(f"Tool '{obs.get('tool')}' was denied: {obs.get('reason')}")
            elif obs.get("status") in ("unsupported", "error", "not_found"):
                prompt_lines.append(f"Tool '{obs.get('tool')}' returned: {obs.get('reason')}")
            else:
                prompt_lines.append(json.dumps(obs, default=str))'''

text = text.replace(old_prompt_lines, new_prompt_lines)

p_orch.write_text(text, encoding="utf-8")
print("orchestrator.py updated with robust status handling")

