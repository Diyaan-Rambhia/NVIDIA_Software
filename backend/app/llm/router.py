"""Live Nemotron runtime call router for hackathon evaluation.

Per hackathon requirements:
- Live, budget-guarded Nemotron endpoint in the hosted app.
- Returns a clear error if NEBIUS_API_KEY is missing.
- Never falls back to the placeholder provider.
- Marked unverified until a real call succeeds.
"""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app.auth.models import UserClaims
from backend.app.config.env import load_settings
from backend.app.entitlements.guard import require_feature
from backend.app.llm.client import LLMClient
from backend.app.llm.exceptions import LLMError
from backend.app.llm.registry import ModelRegistry

router = APIRouter(prefix="/llm", tags=["llm_runtime"])
_require_entitlement = require_feature("feature1_contagion")


class NemotronCallRequest(BaseModel):
    """Payload for executing a live runtime call to Nemotron."""

    prompt: str = Field(..., min_length=1, max_length=2000, description="User prompt")
    alias: str = Field(default="fast", description="Model alias (fast, mid, deep)")


class NemotronCallResponse(BaseModel):
    """Response containing live Nemotron completion."""

    status: str
    alias: str
    model_id: str
    response: str
    unverified_note: str


@router.post("/runtime_call", response_model=NemotronCallResponse)
async def call_nemotron_runtime(
    req: NemotronCallRequest,
    request: Request,
    user: Annotated[UserClaims, Depends(_require_entitlement)],
) -> NemotronCallResponse:
    """Execute a live, budget-guarded Nemotron runtime call via Nebius Token Factory.

    Returns a loud failure if NEBIUS_API_KEY is unconfigured. Never falls back to placeholder.
    Marked unverified until a real call succeeds.
    """
    settings = getattr(request.app.state, "settings", None) or load_settings()
    raw_env = (settings.get_var_value("APP_ENV") or settings.app_env or "development").strip().lower()
    api_key = settings.get_var_value("NEBIUS_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "provider_not_configured" if raw_env in ("production", "prod") else "nebius_key_missing",
                "message": (
                    "NEBIUS_API_KEY is not configured in environment. "
                    "Runtime Nemotron calls require a valid Nebius Token Factory key."
                ),
            },
        )

    base_url = settings.get_var_value("NEBIUS_BASE_URL")
    if not base_url:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "nebius_base_url_missing",
                "message": "NEBIUS_BASE_URL is not configured in environment.",
            },
        )

    try:
        registry = ModelRegistry.from_token_factory(
            base_url=base_url,
            api_key=api_key,
            cache_ttl_seconds=3600,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "model_catalog_unavailable",
                "message": f"Failed to retrieve Token Factory model catalog: {exc}",
            },
        ) from exc

    client = LLMClient(registry=registry, settings=settings)

    try:
        resp = client.complete(
            alias=req.alias,
            messages=[{"role": "user", "content": req.prompt}],
            user_id=None,
        )
        content = resp["choices"][0]["message"]["content"]
        model_id = registry.get_model_id(req.alias)
        return NemotronCallResponse(
            status="success",
            alias=req.alias,
            model_id=model_id,
            response=content,
            unverified_note="Marked unverified until real runtime verification succeeds in staging.",
        )
    except LLMError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "llm_upstream_error", "message": str(exc)},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "llm_call_failed", "message": str(exc)},
        ) from exc
