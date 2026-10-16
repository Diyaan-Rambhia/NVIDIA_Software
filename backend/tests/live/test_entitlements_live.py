"""Live entitlement check through the API with seeded accounts per Batch X13."""

import json
import urllib.request
import pytest
from fastapi.testclient import TestClient

from backend.app.config.env import load_settings
from backend.app.db.connection import get_connection
from backend.app.main import create_app


def test_live_entitlements_seeded_accounts() -> None:
    """Verify live entitlements with three seeded accounts:
    - demo_retail on Feature 1 gives 403
    - demo_institutional on Feature 1 gives 402 with upgrade target
    - judge gives 200 on all features
    - 429 with reset time at daily quota (removes test usage rows after)
    Never prints passwords or tokens.
    """
    settings = load_settings()
    supabase_url = settings.get_var_value("SUPABASE_URL")
    anon_key = settings.get_var_value("SUPABASE_ANON_KEY")
    service_key = settings.get_var_value("SUPABASE_SERVICE_ROLE_KEY")

    judge_pw = settings.get_var_value("JUDGE_PASSWORD")
    retail_pw = settings.get_var_value("DEMO_RETAIL_PASSWORD")
    inst_pw = settings.get_var_value("DEMO_INSTITUTIONAL_PASSWORD")

    if not (supabase_url and anon_key and service_key and judge_pw and retail_pw and inst_pw):
        pytest.skip("not run: missing required live environment keys or seeded passwords")

    accounts = {
        "judge": {"email": "judge@fininsight.local", "pw": judge_pw},
        "demo_retail": {"email": "demo_retail@fininsight.local", "pw": retail_pw},
        "demo_institutional": {"email": "demo_institutional@fininsight.local", "pw": inst_pw},
    }

    tokens = {}
    for name, acc in accounts.items():
        login_url = f"{supabase_url.rstrip('/')}/auth/v1/token?grant_type=password"
        req = urllib.request.Request(
            login_url,
            data=json.dumps({"email": acc["email"], "password": acc["pw"]}).encode("utf-8"),
            headers={"apikey": anon_key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                tokens[name] = data["access_token"]
        except Exception as exc:
            pytest.fail(f"Authentication failed for seeded account '{name}' without printing credentials: {exc}")

    app = create_app()
    client = TestClient(app)

    # 1. demo_retail on Feature 1 gives 403
    r_retail_f1 = client.get("/f1/demo", headers={"Authorization": f"Bearer {tokens['demo_retail']}"})
    assert r_retail_f1.status_code == 403
    assert r_retail_f1.json()["error"]["code"] == "denied"

    # 2. demo_institutional on Feature 1 gives 402 with upgrade target
    r_inst_f1 = client.get("/f1/demo", headers={"Authorization": f"Bearer {tokens['demo_institutional']}"})
    assert r_inst_f1.status_code == 402
    inst_data = r_inst_f1.json()
    assert "upgrade_targets" in inst_data["error"]
    assert "institutional_paid" in inst_data["error"]["upgrade_targets"]

    # 3. judge gives 200 on all features
    r_judge_f1 = client.get("/f1/demo", headers={"Authorization": f"Bearer {tokens['judge']}"})
    r_judge_f2 = client.get("/f2/demo", headers={"Authorization": f"Bearer {tokens['judge']}"})
    r_judge_f3 = client.get("/f3/demo", headers={"Authorization": f"Bearer {tokens['judge']}"})
    assert r_judge_f1.status_code == 200
    assert r_judge_f2.status_code == 200
    assert r_judge_f3.status_code == 200

    # 4. 429 with reset time at daily quota (clean up test usage rows after)
    conn = get_connection(settings)
    retail_user_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM public.profiles WHERE plan = 'retail_free' LIMIT 1;")
            row = cur.fetchone()
            assert row is not None
            retail_user_id = row[0]

            # Upsert usage counter to daily quota limit (3)
            cur.execute(
                """
                INSERT INTO public.usage (user_id, feature, utc_date, count)
                VALUES (%s, 'filing_consistency', CURRENT_DATE, 3)
                ON CONFLICT (user_id, feature, utc_date) DO UPDATE SET count = 3;
                """,
                (retail_user_id,),
            )
            conn.commit()

        r_quota = client.get("/f2/demo", headers={"Authorization": f"Bearer {tokens['demo_retail']}"})
        assert r_quota.status_code == 429
        quota_data = r_quota.json()
        assert quota_data["error"]["code"] == "denied"
        assert quota_data["error"]["reset_time"] is not None
        assert "Daily quota of 3 exceeded" in quota_data["error"]["message"]
    finally:
        if retail_user_id:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM public.usage WHERE user_id = %s AND feature = 'filing_consistency' AND utc_date = CURRENT_DATE;",
                    (retail_user_id,),
                )
                conn.commit()
        conn.close()
