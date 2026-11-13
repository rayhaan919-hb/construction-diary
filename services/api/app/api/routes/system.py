from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.errors import ProblemException
from app.db.session import get_db

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str = "ok"


@router.get("/healthz", response_model=HealthResponse)
def healthz(db: Annotated[Session, Depends(get_db)]) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise ProblemException(
            status_code=503,
            code="DB_UNAVAILABLE",
            title="Service Unavailable",
            detail="Database connectivity check failed",
        ) from exc
    return HealthResponse(status="ok")
