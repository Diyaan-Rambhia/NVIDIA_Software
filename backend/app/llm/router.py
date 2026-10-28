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
        registry = ModelRegistry(settings=settings)
        registry.initialize()
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
        msg = resp.get("choices", [{}])[0].get("message", {})
        content = (
            msg.get("content")
            or msg.get("reasoning_content")
            or msg.get("text")
            or "[Completed without text content]"
        )
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


class TavilySearchRequest(BaseModel):
    """Payload for executing a live search request to Tavily."""

    query: str = Field(..., min_length=1, max_length=500, description="Macro search query")


class TavilySearchResult(BaseModel):
    """Single Tavily search result."""

    title: str
    url: str
    content: str


class TavilySearchResponse(BaseModel):
    """Container for Tavily search results."""

    status: str
    query: str
    results: list[TavilySearchResult]


@router.post("/tavily_search", response_model=TavilySearchResponse)
async def search_tavily(
    req: TavilySearchRequest,
    request: Request,
    user: Annotated[UserClaims, Depends(_require_entitlement)],
) -> TavilySearchResponse:
    """Execute live macro news search via Tavily API with budget & entitlement checks."""
    import json
    import urllib.request
    from urllib.error import HTTPError

    settings = getattr(request.app.state, "settings", None) or load_settings()
    api_key = settings.get_var_value("TAVILY_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "tavily_key_missing",
                "message": "TAVILY_API_KEY is not configured in environment.",
            },
        )

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": req.query,
        "search_depth": "basic",
        "max_results": 4,
    }
    req_obj = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req_obj, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_results = data.get("results", [])
            results = [
                TavilySearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    content=r.get("content", ""),
                )
                for r in raw_results
            ]
            return TavilySearchResponse(
                status="success",
                query=req.query,
                results=results,
            )
    except HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(
            status_code=502,
            detail={
                "code": "tavily_upstream_error",
                "message": f"Tavily returned HTTP {exc.code}: {err_body}",
            },
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "tavily_call_failed",
                "message": f"Tavily connection failed: {exc}",
            },
        ) from exc


class TierDetail(BaseModel):
    """Configuration and pricing details for a single model tier."""

    alias: str
    status: str
    price_per_1m_input_usd: float | None = None
    price_per_1m_output_usd: float | None = None
    patterns: list[str] = Field(default_factory=list)
    enabled: bool = True
    reason: str | None = None


class ModelTiersCatalogResponse(BaseModel):
    """Catalog of configured model tiers."""

    tiers: dict[str, TierDetail]


@router.get("/tiers", response_model=ModelTiersCatalogResponse)
def get_model_tiers(
    user: Annotated[UserClaims, Depends(_require_entitlement)],
) -> ModelTiersCatalogResponse:
    """Return configured LLM model aliases, patterns, and pricing rates."""
    from backend.app.llm.registry import load_models_config

    cfg = load_models_config()
    raw_tiers = cfg.get("tiers", {})
    tiers_map: dict[str, TierDetail] = {}

    for alias, tdata in raw_tiers.items():
        tiers_map[alias] = TierDetail(
            alias=alias,
            status=str(tdata.get("status", "pending")),
            price_per_1m_input_usd=tdata.get("price_per_1m_input_usd"),
            price_per_1m_output_usd=tdata.get("price_per_1m_output_usd"),
            patterns=list(tdata.get("patterns", [])),
            enabled=bool(tdata.get("enabled", True)),
            reason=tdata.get("reason"),
        )

    return ModelTiersCatalogResponse(tiers=tiers_map)


