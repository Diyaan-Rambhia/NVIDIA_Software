"""Feature 1 Contagion API router."""

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.app.auth.models import UserClaims
from backend.app.entitlements.guard import require_feature

router = APIRouter(prefix="/f1", tags=["feature1_contagion"])
_require_f1 = require_feature("feature1_contagion")

F1_DEMO_PATH = Path("demo_data") / "f1_scan_demo.json" if (Path("demo_data") / "f1_scan_demo.json").is_file() else Path("data") / "f1_scan_demo.json"


@router.get("/demo")
async def get_f1_demo(
    user: Annotated[UserClaims, Depends(_require_f1)],
) -> dict:
    """Return precomputed Feature 1 correlation scan demo JSON."""
    if not F1_DEMO_PATH.is_file():
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "F1 demo data not precomputed"},
        )
    return json.loads(F1_DEMO_PATH.read_text(encoding="utf-8"))
