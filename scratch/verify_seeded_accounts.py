import json
import urllib.request
from datetime import datetime, timezone
from backend.app.config.env import load_settings
from backend.app.config.loader import load_all_config
from backend.app.db.connection import get_connection
from backend.app.entitlements.atomic import increment_quota_atomic
from fastapi.testclient import TestClient
from backend.app.main import create_app

def check_entitlements():
    settings = load_settings()
    supabase_url = settings.get_var_value("SUPABASE_URL")
    anon_key = settings.get_var_value("SUPABASE_ANON_KEY")
    service_key = settings.get_var_value("SUPABASE_SERVICE_ROLE_KEY")
    
    judge_pw = settings.get_var_value("JUDGE_PASSWORD")
    retail_pw = settings.get_var_value("DEMO_RETAIL_PASSWORD")
    inst_pw = settings.get_var_value("DEMO_INSTITUTIONAL_PASSWORD")
    
    if not (supabase_url and anon_key and service_key and judge_pw and retail_pw and inst_pw):
        print("MISSING_ENV")
        return

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
        except Exception as e:
            print(f"LOGIN_FAIL_{name}: {type(e).__name__} {e}")
            return

    app = create_app()
    client = TestClient(app)

    # 1. demo_retail on Feature 1 gives 403
    r_retail_f1 = client.get("/f1/demo", headers={"Authorization": f"Bearer {tokens['demo_retail']}"})
    print(f"demo_retail_f1_status={r_retail_f1.status_code}")
    print(f"demo_retail_f1_body={r_retail_f1.json()}")

    # 2. demo_institutional on Feature 1 gives 402 with upgrade target
    r_inst_f1 = client.get("/f1/demo", headers={"Authorization": f"Bearer {tokens['demo_institutional']}"})
    print(f"demo_inst_f1_status={r_inst_f1.status_code}")
    print(f"demo_inst_f1_body={r_inst_f1.json()}")

    # 3. judge gives 200 on all features
    r_judge_f1 = client.get("/f1/demo", headers={"Authorization": f"Bearer {tokens['judge']}"})
    r_judge_f2 = client.get("/f2/demo", headers={"Authorization": f"Bearer {tokens['judge']}"})
    r_judge_f3 = client.get("/f3/demo", headers={"Authorization": f"Bearer {tokens['judge']}"})
    print(f"judge_f1_status={r_judge_f1.status_code}")
    print(f"judge_f2_status={r_judge_f2.status_code}")
    print(f"judge_f3_status={r_judge_f3.status_code}")

    # 4. 429 with reset time at daily quota (test on demo_institutional or demo_retail for f2_filings)
    # demo_retail has quota 3 for feature2_filings
    conn = get_connection(settings)
    try:
        # Get demo_retail user_id from profiles
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM public.profiles WHERE plan = 'retail_free' LIMIT 1;")
            retail_user_id = cur.fetchone()[0]
            # Insert usage rows to reach quota
            today = datetime.now(timezone.utc).date()
            cur.execute(
                "INSERT INTO public.usage (user_id, feature, utc_date, count) "
                "VALUES (%s, 'filing_consistency', CURRENT_DATE, 3) "
                "ON CONFLICT (user_id, feature, utc_date) DO UPDATE SET count = 3;",
                (retail_user_id,)
            )
            conn.commit()
        
        r_quota = client.get("/f2/demo", headers={"Authorization": f"Bearer {tokens['demo_retail']}"})
        print(f"quota_429_status={r_quota.status_code}")
        print(f"quota_429_body={r_quota.json()}")

        # Clean up test usage rows
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM public.usage WHERE user_id = %s AND feature = 'filing_consistency' AND utc_date = CURRENT_DATE;",
                (retail_user_id,)
            )
            conn.commit()
        print("CLEANUP_SUCCESS")
    finally:
        conn.close()

if __name__ == "__main__":
    check_entitlements()
