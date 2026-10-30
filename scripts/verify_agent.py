"""Script verifying agent tool calling, grounding, scope, and output checks on live provider."""

import json
import sys
import uuid
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from backend.app.agent.orchestrator import run_agent_loop
from backend.app.auth.models import UserClaims
from backend.app.config.env import load_settings
from backend.app.config.loader import load_all_config


def main() -> None:
    settings = load_settings()
    all_config = load_all_config()

    user = UserClaims(
        user_id=uuid.uuid4(),
        email="verifier@fininsight.internal",
        role="admin",
        segment="institutional",
        plan="institutional_paid",
    )

    attachment_text = None
    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1])
        if file_path.is_file():
            attachment_text = file_path.read_text(encoding="utf-8")
    if not attachment_text:
        attachment_text = "Corporate Financial Filing Review: Revenue from operations is 1500.0 INR Cr. Net profit margin is 12.5%."

    questions = [
        ("Question 1 (a scan)", "Execute a systemic market contagion scan across benchmark Indian equities.", None),
        ("Question 2 (the same for the USA)", "The same for the USA", None),
        ("Question 3 (the same as of 27 October)", "The same as of 27 October", None),
        ("Question 4 (write a three-sum program)", "Write a three-sum program in Python.", None),
        ("Question 5 (analyze text file)", "Analyze the attached corporate financial text file.", attachment_text),
        ("Question 6 (filings check Rajesh Exports Q3 FY25)", "Check filings for Rajesh Exports Q3 FY25.", None),
    ]

    history: list[dict[str, str]] = []

    for label, query, att in questions:
        try:
            resp = run_agent_loop(
                query=query,
                user=user,
                settings=settings,
                all_config=all_config,
                attachment_text=att,
                history=history,
                model_tier="balanced",
            )

            tools_called = [s.tool_name for s in resp.steps]
            ans = resp.answer or ""
            ans_len = len(ans)

            as_of_val = None
            for s in resp.steps:
                try:
                    inp = json.loads(s.input_summary)
                    if "as_of" in inp:
                        as_of_val = inp["as_of"]
                    elif "period" in inp:
                        as_of_val = inp["period"]
                except Exception:
                    pass

            checks_fired = []
            if "I cover Indian markets only." in ans:
                checks_fired.append("india_only_scope")
            if "I can only assist" in ans or "decline" in ans.lower():
                checks_fired.append("scope_decline")
            if "Summary built from the data." in ans:
                checks_fired.append("grounding_summary_fallback")
            if "delayed" in ans.lower():
                checks_fired.append("stale_data_delayed")
            if "could not retrieve data" in ans.lower():
                checks_fired.append("no_data_numeric_decline")
            if not checks_fired:
                checks_fired.append("none")

            print(f"{label}:")
            print(f"  Tools called: {tools_called}")
            print(f"  as_of date: {as_of_val}")
            print(f"  Answer length: {ans_len}")
            print(f"  Checks fired: {', '.join(checks_fired)}")

            history.append({"role": "user", "content": query})
            history.append({"role": "assistant", "content": ans})

        except Exception as exc:
            print(f"{label}:")
            print(f"  Tools called: []")
            print(f"  as_of date: None")
            print(f"  Answer length: 0")
            print(f"  Checks fired: error ({type(exc).__name__})")


if __name__ == "__main__":
    main()

