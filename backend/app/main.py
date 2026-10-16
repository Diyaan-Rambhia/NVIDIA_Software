"""FastAPI application factory, middleware, standard error handlers, and health endpoints."""

import logging
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from backend.app.auth.dependencies import require_admin
from backend.app.config import (
    REGISTRY_BY_GROUP,
    AllConfig,
    Settings,
    is_var_present,
    load_all_config,
    load_runtime_config,
    load_settings,
    validate_enabled_groups,
)
from backend.app.contracts.common import ErrorDetail, ErrorEnvelope
from backend.app.logging import configure_logging, request_id_ctx
from backend.app.ops.routes import router as ops_router
from backend.app.version import get_code_version

logger = logging.getLogger("backend.app")

REQUEST_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware ensuring every request has a validated or generated X-Request-ID."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        header_req_id = request.headers.get("X-Request-ID")
        if header_req_id and REQUEST_ID_REGEX.match(header_req_id):
            req_id = header_req_id
        else:
            req_id = uuid.uuid4().hex

        token = request_id_ctx.set(req_id)
        request.state.request_id = req_id

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        except Exception as exc:
            # Catch unhandled exceptions at the middleware boundary so that
            # we return the standard ErrorEnvelope with the request ID header
            logger.error("Unhandled server exception: %s", exc, exc_info=exc)
            envelope = ErrorEnvelope(
                error=ErrorDetail(
                    code="INTERNAL_SERVER_ERROR",
                    message="Internal server error",
                    request_id=req_id,
                )
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=envelope.model_dump(),
                headers={"X-Request-ID": req_id},
            )
        finally:
            request_id_ctx.reset(token)


def create_app(
    settings: Settings | None = None,
    runtime_groups: list[str] | None = None,
    config_dir: Path | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    1. Loads application settings.
    2. Loads and validates all YAML configs from config_dir (or default 'config').
    3. Reads runtime configuration and validates enabled environment groups.
    4. Configures JSON-line structured logging with secret redaction.
    5. Registers Request-ID middleware and ErrorEnvelope exception handlers.
    6. Mounts /health and /ready routes.
    7. Mounts /ops, /console static files, and / redirect under development guard.
    """
    if settings is None:
        settings = load_settings()

    # Load all configuration YAMLs; raises ConfigError if missing or invalid
    all_config: AllConfig = load_all_config(config_dir)

    # Resolve runtime enabled groups
    if runtime_groups is None:
        runtime_groups = load_runtime_config()

    # Validate enabled environment groups
    validate_enabled_groups(settings, runtime_groups)

    # Initialize structured JSON logging with secret redaction
    configure_logging(settings)

    docs_url = None if settings.app_env == "production" else "/docs"
    redoc_url = None if settings.app_env == "production" else "/redoc"
    openapi_url = None if settings.app_env == "production" else "/openapi.json"

    app = FastAPI(
        title="FinInsight",
        version=get_code_version(),
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    # Store loaded configs in app state
    app.state.settings = settings
    app.state.all_config = all_config
    app.state.runtime_groups = runtime_groups
    app.state.config_dir = config_dir

    # Add Request-ID middleware
    app.add_middleware(RequestIDMiddleware)

    # CORS origins loaded from config; never defaults to "*"
    from fastapi.middleware.cors import CORSMiddleware

    cors_origins: list[str] = []
    if all_config and "cors_origins" in all_config.parameters.parameters:
        val = all_config.parameters.parameters["cors_origins"].default
        if isinstance(val, str):
            cors_origins = [o.strip() for o in val.split(",") if o.strip() and o.strip() != "*"]
        elif isinstance(val, list):
            cors_origins = [str(o).strip() for o in val if str(o).strip() != "*"]

    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # -----------------------------------------------------------------------
    # Exception Handlers with ErrorEnvelope
    # -----------------------------------------------------------------------
    def _get_request_id(request: Request) -> str:
        return getattr(request.state, "request_id", None) or request_id_ctx.get() or "unknown"

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        req_id = _get_request_id(request)
        code = f"HTTP_{exc.status_code}"
        message = str(exc.detail)
        envelope = ErrorEnvelope(
            error=ErrorDetail(
                code=code,
                message=message,
                request_id=req_id,
            )
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope.model_dump(),
            headers={"X-Request-ID": req_id},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        req_id = _get_request_id(request)
        resp_headers = {"X-Request-ID": req_id}
        if isinstance(exc.detail, dict):
            code = str(exc.detail.get("code", f"HTTP_{exc.status_code}"))
            message = str(exc.detail.get("message", "Error"))
            upstream = exc.detail.get("upstream")
            upgrade_targets = exc.detail.get("upgrade_targets")
            reset_time = exc.detail.get("reset_time")
        else:
            code = f"HTTP_{exc.status_code}"
            message = str(exc.detail)
            upstream = None
            upgrade_targets = None
            reset_time = None
        envelope = ErrorEnvelope(
            error=ErrorDetail(
                code=code,
                message=message,
                request_id=req_id,
                upstream=upstream,
                upgrade_targets=upgrade_targets,
                reset_time=reset_time,
            )
        )
        if reset_time:
            resp_headers["X-Reset-Time"] = str(reset_time)
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope.model_dump(),
            headers=resp_headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        req_id = _get_request_id(request)
        upstream_errors = [
            {
                "loc": list(err.get("loc", [])),
                "msg": str(err.get("msg", "")),
                "type": str(err.get("type", "")),
            }
            for err in exc.errors()
        ]
        envelope = ErrorEnvelope(
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message="Request validation failed",
                request_id=req_id,
                upstream=upstream_errors,
            )
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=envelope.model_dump(),
            headers={"X-Request-ID": req_id},
        )

    # -----------------------------------------------------------------------
    # Health and Readiness Endpoints
    # -----------------------------------------------------------------------
    @app.get("/health")
    async def health() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok"}

    @app.get("/ready")
    async def ready(response: Response) -> dict[str, Any]:
        """Readiness probe checking configuration and enabled groups."""
        missing_vars: list[str] = []

        # Verify all required variables in currently enabled groups
        for group in app.state.runtime_groups:
            if group in REGISTRY_BY_GROUP:
                for var_def in REGISTRY_BY_GROUP[group]:
                    if var_def.required_when_group_enabled and not is_var_present(
                        app.state.settings, var_def
                    ):
                        missing_vars.append(var_def.name)

        is_ready = len(missing_vars) == 0
        checks: dict[str, Any] = {
            "config_loaded": app.state.all_config is not None,
            "enabled_groups": app.state.runtime_groups,
            "missing": missing_vars,
        }

        if not is_ready:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        else:
            response.status_code = status.HTTP_200_OK

        return {
            "ready": is_ready,
            "checks": checks,
        }

    # -----------------------------------------------------------------------
    # Production Admin Guard: /ops, /console, and / redirect
    # Protected by require_admin (Decision D-45, superseding D-10)
    # -----------------------------------------------------------------------
    app.include_router(ops_router)

    console_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "console"
    if console_dir.is_dir():
        assets_dir = console_dir / "assets"
        if assets_dir.is_dir():
            app.mount(
                "/console/assets",
                StaticFiles(directory=str(assets_dir)),
                name="console_assets",
            )

        @app.get("/console", response_class=FileResponse)
        @app.get("/console/", response_class=FileResponse)
        @app.get(
            "/console/index.html",
            response_class=FileResponse,
        )
        async def console_index() -> FileResponse:
            return FileResponse(console_dir / "index.html", media_type="text/html")

        @app.get(
            "/console/config.html",
            response_class=FileResponse,
        )
        async def console_config() -> FileResponse:
            return FileResponse(console_dir / "config.html", media_type="text/html")

    @app.get("/")
    async def root_redirect() -> RedirectResponse:
        return RedirectResponse(url="/app")

    from backend.app.admin.router import router as admin_router
    from backend.app.agent.router import router as agent_router
    from backend.app.auth.router import router as auth_router
    from backend.app.entitlements.router import router as entitlements_router
    from backend.app.features.f1_contagion.router import router as f1_router
    from backend.app.features.f2_filings.router import router as f2_router
    from backend.app.features.f3_log.router import router as f3_router
    from backend.app.llm.router import router as llm_router

    app.include_router(auth_router)
    app.include_router(entitlements_router)
    app.include_router(admin_router)
    app.include_router(f1_router)
    app.include_router(f2_router)
    app.include_router(f3_router)
    app.include_router(llm_router)
    app.include_router(agent_router)

    app_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "app"
    if app_dir.is_dir():
        app.mount("/app", StaticFiles(directory=str(app_dir), html=True), name="frontend_app")

    return app
