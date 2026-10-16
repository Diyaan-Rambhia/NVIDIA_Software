"""Feature 2 Filing Consistency API router."""

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.app.auth.models import UserClaims
from backend.app.entitlements.guard import require_feature

router = APIRouter(prefix="/f2", tags=["feature2_filings"])
_require_f2 = require_feature("feature2_filings")

F2_DEMO_PATH = Path("demo_data") / "f2_filings_demo.json" if (Path("demo_data") / "f2_filings_demo.json").is_file() else Path("data") / "f2_filings_demo.json"


@router.get("/demo")
async def get_f2_demo(
    user: Annotated[UserClaims, Depends(_require_f2)],
) -> dict:
    """Return precomputed Feature 2 filings consistency demo JSON."""
    if not F2_DEMO_PATH.is_file():
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "F2 demo data not precomputed"},
        )
    return json.loads(F2_DEMO_PATH.read_text(encoding="utf-8"))
