"""Ops console endpoints: status, configuration presence, and parameter tables."""

import platform
import sys
import time
from typing import Any

from fastapi import APIRouter, Depends, Request

from backend.app.auth.dependencies import require_admin
from backend.app.config.env import REGISTRY_BY_GROUP, is_var_present
from backend.app.db.connection import get_connection
from backend.app.version import get_code_version

router = APIRouter(prefix="/ops", tags=["ops"], dependencies=[Depends(require_admin)])

# Record server boot timestamp (relative monotonic or epoch for uptime seconds)
SERVER_START_TIME = time.monotonic()


@router.get("/status")
async def get_ops_status(request: Request) -> dict[str, Any]:
    """Return operational status, versions, uptime, and enabled groups."""
    settings = request.app.state.settings
    runtime_groups = request.app.state.runtime_groups

    uptime_seconds = int(time.monotonic() - SERVER_START_TIME)

    return {
        "app_env": settings.app_env,
        "code_version": get_code_version(),
        "python_version": f"{platform.python_implementation()} {sys.version.split()[0]}",
        "uptime_seconds": uptime_seconds,
        "enabled_groups": runtime_groups,
    }


@router.get("/config")
async def get_ops_config(request: Request) -> dict[str, Any]:
    """Return environment variables grouped with presence and required-when-enabled status.

    Never exposes actual variable values.
    """
    settings = request.app.state.settings
    runtime_groups = set(request.app.state.runtime_groups)

    groups_data: dict[str, list[dict[str, Any]]] = {}

    for group_name, var_defs in REGISTRY_BY_GROUP.items():
        var_list: list[dict[str, Any]] = []
        is_group_enabled = group_name in runtime_groups

        for var_def in var_defs:
            present = is_var_present(settings, var_def)
            var_list.append(
                {
                    "name": var_def.name,
                    "present": present,
                    "required_when_enabled": var_def.required_when_group_enabled,
                    "group_enabled": is_group_enabled,
                }
            )
        groups_data[group_name] = var_list

    return {
        "enabled_groups": sorted(runtime_groups),
        "groups": groups_data,
    }


@router.get("/parameters")
async def get_ops_parameters(request: Request) -> dict[str, Any]:
    """Return the loaded parameter register table with bounds and defaults."""
    all_config = request.app.state.all_config
    params_data: dict[str, Any] = {}

    for param_name, entry in all_config.parameters.parameters.items():
        params_data[param_name] = {
            "type": entry.type,
            "default": entry.default,
            "min": entry.min,
            "max": entry.max,
            "override_allowed": entry.override_allowed,
            "unit": entry.unit,
        }

    return {
        "parameters": params_data,
    }


@router.get("/activity/events")
async def get_ops_activity_events(request: Request) -> list[dict[str, Any]]:
    """Return recent system events. Never exposes prompts, emails, or keys."""
    settings = request.app.state.settings
    conn = get_connection(settings)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, ts, kind, subject, status, duration_ms
                FROM public.events
                ORDER BY ts DESC
                LIMIT 50;
                """
            )
            rows = cur.fetchall()
            return [
                {
                    "id": str(r[0]),
                    "ts": r[1].isoformat() if r[1] else None,
                    "kind": str(r[2]),
                    "subject": str(r[3]),
                    "status": str(r[4]),
                    "duration_ms": r[5],
                }
                for r in rows
            ]
    finally:
        conn.close()


@router.get("/activity/llm")
async def get_ops_activity_llm(request: Request) -> list[dict[str, Any]]:
    """Return recent LLM ledger rows. Never exposes prompts, user emails, or keys."""
    settings = request.app.state.settings
    conn = get_connection(settings)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, ts, route, alias, model_id,
                       input_tokens, output_tokens, est_cost_usd, cache_hit
                FROM public.llm_ledger
                ORDER BY ts DESC
                LIMIT 50;
                """
            )
            rows = cur.fetchall()
            return [
                {
                    "id": str(r[0]),
                    "ts": r[1].isoformat() if r[1] else None,
                    "route": str(r[2]),
                    "alias": str(r[3]),
                    "model_id": str(r[4]),
                    "input_tokens": int(r[5]),
                    "output_tokens": int(r[6]),
                    "est_cost_usd": float(r[7]),
                    "cache_hit": bool(r[8]),
                }
                for r in rows
            ]
    finally:
        conn.close()
