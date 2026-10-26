"""Elevate an existing user account to admin role in Supabase Auth.

Requirements:
- Takes email as a command-line argument only; never from code.
- Uses service role key via Supabase Admin API to update app_metadata.role = 'admin'.
- Never touches or overwrites user_metadata.
- Stops with clear error if user does not exist; never creates the user.
- Idempotent and safe to run multiple times.
- Never prints keys, passwords, or tokens.
- Refuses to run under APP_ENV=production unless --allow-production is passed (Decision D-55).
"""

import argparse
import json
import logging
import sys
import urllib.error
import urllib.request
import uuid
from typing import Any

from backend.app.config.env import Settings, load_settings
from backend.app.db.connection import get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("set_admin")


def find_user_by_email(
    admin_api_base: str, headers: dict[str, str], email: str
) -> dict[str, Any] | None:
    """Find a Supabase user by email using the Admin API."""
    target_email = email.strip().lower()
    page = 1
    per_page = 100
    while True:
        url = f"{admin_api_base}?page={page}&per_page={per_page}"
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            logger.error("Failed to list users from Supabase Admin API: HTTP %s - %s", exc.code, body)
            return None

        users = data.get("users", [])
        if not users:
            break

        for u in users:
            if str(u.get("email", "")).strip().lower() == target_email:
                return u

        if len(users) < per_page:
            break
        page += 1

    return None


def set_admin_role(email: str, allow_production: bool = False) -> str:
    """Set app_metadata.role = 'admin' for an existing user.

    Returns:
        "set" if role was updated to admin
        "already set" if role was already admin
        "user not found" if account does not exist
    """
    settings = load_settings()

    raw_env = (settings.get_var_value("APP_ENV") or settings.app_env or "production").strip().lower()
    if raw_env in ("production", "prod") and not allow_production:
        sys.stderr.write(
            "Refused: scripts/set_admin.py cannot run in production mode without --allow-production flag (Decision D-55).\n"
        )
        sys.exit(1)

    supabase_url = settings.get_var_value("SUPABASE_URL")
    service_key = settings.get_var_value("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not service_key:
        sys.stderr.write("Error: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not configured.\n")
        sys.exit(1)

    admin_api_base = f"{supabase_url.rstrip('/')}/auth/v1/admin/users"
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }

    user = find_user_by_email(admin_api_base, headers, email)
    if not user:
        sys.stderr.write(f"Error: User with email '{email}' does not exist. Halting without creation.\n")
        return "user not found"

    user_id = user["id"]
    app_meta = dict(user.get("app_metadata") or {})

    if app_meta.get("role") == "admin":
        print(f"Account '{email}' already has admin role.")
        return "already set"

    app_meta["role"] = "admin"
    update_body = {"app_metadata": app_meta}

    update_url = f"{admin_api_base}/{user_id}"
    req = urllib.request.Request(
        update_url,
        data=json.dumps(update_body).encode("utf-8"),
        headers=headers,
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status not in (200, 204):
                sys.stderr.write(f"Error: Unexpected HTTP status {resp.status} updating role.\n")
                sys.exit(1)
    except urllib.error.HTTPError as exc:
        sys.stderr.write(f"Error: HTTP {exc.code} updating user role.\n")
        sys.exit(1)

    # Sync public.profiles if database connection is available
    try:
        conn = get_connection(settings)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE public.profiles SET role = 'admin' WHERE user_id = %s;",
                (uuid.UUID(user_id),),
            )
        conn.commit()
        conn.close()
    except Exception:
        pass

    print(f"Successfully granted admin role to '{email}'.")
    return "set"


def main() -> None:
    parser = argparse.ArgumentParser(description="Grant admin role to an existing Supabase user account.")
    parser.add_argument("email", type=str, help="Email of the existing account to elevate")
    parser.add_argument(
        "--allow-production",
        action="store_true",
        help="Explicitly permit execution when APP_ENV is production",
    )

    args = parser.parse_args()
    result = set_admin_role(args.email, allow_production=args.allow_production)
    if result == "user not found":
        sys.exit(1)


if __name__ == "__main__":
    main()
