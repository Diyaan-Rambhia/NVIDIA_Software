"""FastAPI router for agent orchestration endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.agent.orchestrator import run_agent_loop
from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import UserClaims
from backend.app.config.env import load_settings
from backend.app.config.loader import load_all_config
from backend.app.contracts.agent import AgentAskRequest, AgentAskResponse
from backend.app.db.connection import get_connection
from backend.app.llm.exceptions import (
    BudgetExceededError,
    FinancialAdviceError,
    LLMError,
    LLMTimeoutError,
    LLMUpstreamError,
    NonProseAnswerError,
    PriceNotSetError,
    ProviderNotConfiguredError,
    TierUnavailableError,
)

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/ask", response_model=AgentAskResponse)
async def ask_agent(
    req: AgentAskRequest,
    request: Request,
    user: Annotated[UserClaims, Depends(get_current_user)],
) -> AgentAskResponse:
    """Execute multi-step agent query across analytical features with entitlement verification."""
    settings = getattr(request.app.state, "settings", None) or load_settings()
    all_config = getattr(request.app.state, "all_config", None) or load_all_config()

    conn = None
    try:
        conn = get_connection(settings)
    except Exception:
        conn = None

    try:
        provider = getattr(request.app.state, "llm_provider", None)
        if provider is None:
            api_key = settings.get_var_value("NEBIUS_API_KEY")
            if not api_key:
                raise HTTPException(
                    status_code=503,
                    detail={
                        "code": "provider_not_configured",
                        "message": (
                            "No real LLM provider is configured in production. "
                            "NEBIUS_API_KEY is required."
                        ),
                    },
                )
            from backend.app.llm.client import LLMClient
            from backend.app.llm.registry import ModelRegistry

            try:
                registry = ModelRegistry(settings=settings)
                registry.initialize()
                provider = LLMClient(registry=registry, settings=settings)
            except Exception as init_exc:
                raise LLMUpstreamError(
                    status_code=502,
                    message=f"LLM provider initialization failed: {init_exc}",
                ) from init_exc

        response = run_agent_loop(
            query=req.query,
            user=user,
            settings=settings,
            all_config=all_config,
            conn=conn,
            max_steps_override=req.max_steps,
            budget_usd_override=req.budget_usd,
            model_tier=req.model_tier,
            attachment_text=req.attachment_text,
            provider=provider,
        )
        return response
    except TierUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "tier_unavailable", "message": str(exc), "tier": exc.tier, "reason": exc.reason},
        )
    except PriceNotSetError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "price_not_set", "message": exc.message, "tier": exc.tier},
        )
    except NonProseAnswerError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "non_prose_answer", "message": "model returned a non-prose answer"},
        )
    except ProviderNotConfiguredError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": exc.code, "message": exc.message},
        )
    except BudgetExceededError as exc:
        raise HTTPException(
            status_code=429,
            detail={"code": "BUDGET_EXCEEDED", "message": str(exc)},
        )
    except LLMTimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail={"code": "TIMEOUT", "message": str(exc)},
        )
    except LLMUpstreamError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": exc.code, "message": str(exc), "status": exc.status_code},
        )
    except FinancialAdviceError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "FINANCIAL_ADVICE_PROHIBITED", "message": str(exc)},
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": str(exc)},
        )
    except LLMError as exc:
        raise HTTPException(
            status_code=exc.status_code if exc.status_code != 500 else 503,
            detail={"code": exc.code, "message": str(exc)},
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "PROVIDER_ERROR", "message": str(exc), "status": 502},
        )
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
