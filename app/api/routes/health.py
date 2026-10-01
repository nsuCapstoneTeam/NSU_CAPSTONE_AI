from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.schemas.health import (
    LiveResponse,
    ReadyResponse,
    NotReadyResponse,
)
from app.core.database import check_database
from app.core.exceptions import DatabaseNotReady


router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=LiveResponse)
def live():
    return {"status": "ok"}


@router.get(
    "/ready",
    response_model=ReadyResponse,
    responses={503: {"model": NotReadyResponse}},
)
def ready():
    try:
        version = check_database()
    except DatabaseNotReady as error:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "reason": error.reason,
            },
        )

    return {
        "status": "ok",
        "database": "ok",
        "pgvector": version,
    }