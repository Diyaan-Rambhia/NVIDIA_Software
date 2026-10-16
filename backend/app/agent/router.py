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
    LLMTimeoutError,
    ProviderNotConfiguredError,
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

    raw_env = (settings.get_var_value("APP_ENV") or settings.app_env or "development").strip().lower()
    api_key = settings.get_var_value("NEBIUS_API_KEY")
    if raw_env in ("production", "prod") and not api_key:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "provider_not_configured",
                "message": (
                    "No real LLM provider is configured in production. "
                    "Placeholder provider is strictly forbidden in production."
                ),
            },
        )

    try:
        response = run_agent_loop(
            query=req.query,
            user=user,
            settings=settings,
            all_config=all_config,
            conn=conn,
            max_steps_override=req.max_steps,
            budget_usd_override=req.budget_usd,
        )
        return response
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
    except RuntimeError as exc:
        if raw_env in ("production", "prod") or "production" in str(exc).lower():
            raise HTTPException(
                status_code=503,
                detail={"code": "provider_not_configured", "message": str(exc)},
            )
        raise HTTPException(
            status_code=500,
            detail={"code": "AGENT_ERROR", "message": str(exc)},
        )
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
