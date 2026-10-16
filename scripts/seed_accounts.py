"""Seed judge and demo accounts idempotently without printing passwords."""

import json
import logging
import sys
import urllib.request
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

import yaml

from backend.app.config.env import load_settings
from backend.app.db.connection import get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_accounts")

PASSWORD_ENV_MAP = {
    "judge": "JUDGE_PASSWORD",
    "demo_retail": "DEMO_RETAIL_PASSWORD",
    "demo_institutional": "DEMO_INSTITUTIONAL_PASSWORD",
}


def load_accounts_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load provisional accounts from YAML."""
    if config_path is None:
        config_path = Path(__file__).resolve().parent.parent / "config" / "accounts.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Accounts config not found at: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data.get("accounts", {})


def seed_accounts() -> None:
    """Create or update judge and demo accounts in Supabase Auth and public.profiles."""
    settings = load_settings()
    supabase_url = settings.get_var_value("SUPABASE_URL")
    service_key = settings.get_var_value("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not service_key:
        logger.error("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not configured. Aborting.")
        sys.exit(1)

    accounts = load_accounts_config()
    conn = get_connection(settings)

    try:
        for acc_key, acc_info in accounts.items():
            email = acc_info["email"]
            segment = acc_info["segment"]
            plan = acc_info["plan"]
            role = acc_info.get("role", "user")

            env_var = PASSWORD_ENV_MAP.get(acc_key)
            password = settings.get_var_value(env_var) if env_var else None

            if not password:
                logger.warning(
                    "No password provided in environment for account '%s' (%s), skipping.",
                    acc_key,
                    env_var,
                )
                continue

            if len(password) < 6:
                logger.error(
                    "Password for account '%s' (%s) is shorter than 6 characters. Rejected.",
                    acc_key,
                    env_var,
                )
                continue

            # Check if user already exists in auth.users via database
            user_id: uuid.UUID | None = None
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM auth.users WHERE email = %s;", (email,))
                row = cur.fetchone()
                if row:
                    user_id = row[0]

            admin_api_base = f"{supabase_url.rstrip('/')}/auth/v1/admin/users"
            headers = {
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json",
            }

            if user_id:
                # Update existing user
                update_url = f"{admin_api_base}/{user_id}"
                body = {
                    "password": password,
                    "email_confirm": True,
                    "app_metadata": {"role": role},
                    "user_metadata": {"segment": segment, "email_verified": True},
                }
                req = urllib.request.Request(
                    update_url,
                    data=json.dumps(body).encode("utf-8"),
                    headers=headers,
                    method="PUT",
                )
                try:
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        logger.info(
                            "Updated existing user credentials for '%s' (%s)", acc_key, email
                        )
                except HTTPError as exc:
                    logger.error("Failed to update user '%s': HTTP %s", acc_key, exc.code)
                    continue
            else:
                # Create new user
                body = {
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "app_metadata": {"role": role},
                    "user_metadata": {"segment": segment, "email_verified": True},
                }
                req = urllib.request.Request(
                    admin_api_base,
                    data=json.dumps(body).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        created_data = json.loads(resp.read().decode("utf-8"))
                        user_id = uuid.UUID(created_data["id"])
                        logger.info("Created new user for '%s' (%s)", acc_key, email)
                except HTTPError as exc:
                    logger.error("Failed to create user '%s': HTTP %s", acc_key, exc.code)
                    continue

            # Upsert into public.profiles
            if user_id:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.profiles (
                            user_id, segment, plan, role, status
                        ) VALUES (
                            %s, %s, %s, %s, 'active'
                        ) ON CONFLICT (user_id) DO UPDATE SET
                            segment = EXCLUDED.segment,
                            plan = EXCLUDED.plan,
                            role = EXCLUDED.role,
                            status = 'active';
                        """,
                        (user_id, segment, plan, role),
                    )
                conn.commit()
                logger.info("Synchronized profile for '%s' to plan '%s'", acc_key, plan)

    finally:
        conn.close()


if __name__ == "__main__":
    seed_accounts()
