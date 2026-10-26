"""Router for in-memory document text extraction."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import UserClaims
from backend.app.config.env import load_settings
from backend.app.config.loader import load_all_config
from backend.app.db.connection import get_connection
from backend.app.entitlements.atomic import get_today_usage, increment_quota_atomic
from backend.app.features.files.extractor import extract_file_content

logger = logging.getLogger("backend.app.features.files")

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/extract", response_class=PlainTextResponse)
async def extract_file(
    request: Request,
    filename: str = "document",
    user: UserClaims = Depends(get_current_user),
) -> PlainTextResponse:
    """Extract plain text from uploaded PDF, .xlsx, or .docx document in-memory.

    Enforces authentication, user entitlements, and daily quotas.
    Never stores files or extracted text to disk. Never logs file contents.
    """
    settings = getattr(request.app.state, "settings", None) or load_settings()
    all_cfg = getattr(request.app.state, "all_config", None) or load_all_config()

    # Quota check like agent call
    daily_limit = 1000 if user.plan == "judge_all" else 20
    conn = None
    try:
        conn = get_connection(settings)
        usage = get_today_usage(conn, user.user_id, "file_extract", settings=settings)
        if usage >= daily_limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "quota_exceeded",
                    "message": f"Daily document extraction limit of {daily_limit} reached.",
                },
            )
        increment_quota_atomic(conn, user.user_id, "file_extract", max_quota=daily_limit, settings=settings)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Could not record file extract quota usage: %s", exc)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    limits_dict = {}
    if all_cfg and all_cfg.parameters:
        for k, p in all_cfg.parameters.parameters.items():
            if k.startswith("file_extract_"):
                limits_dict[k] = p.default

    try:
        content = await request.body()
        content_type = request.headers.get("content-type")
        file_name = request.headers.get("x-filename") or filename
        extracted_text = extract_file_content(
            filename=file_name,
            content=content,
            content_type=content_type,
            limits=limits_dict,
        )
        return PlainTextResponse(content=extracted_text, media_type="text/plain")
    except ValueError as exc:
        err_msg = str(exc)
        if "not available yet" in err_msg.lower():
            raise HTTPException(
                status_code=400,
                detail={"code": "feature_unavailable", "message": "not available yet (v2)"},
            ) from exc
        raise HTTPException(
            status_code=400,
            detail={"code": "file_extraction_error", "message": err_msg},
        ) from exc
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail={"code": "extraction_timeout", "message": str(exc)},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "internal_extraction_error", "message": f"Document extraction failed: {exc}"},
        ) from exc
