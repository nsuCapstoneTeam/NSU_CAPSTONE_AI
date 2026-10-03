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
    # DB 장애를 서버 프로세스 장애로 취급하지 않도록 liveness에서는 DB를 조회하지 않는다.
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
        # 프로세스는 살아 있어도 의존성이 준비되지 않았다면 트래픽 수신 준비 상태는 실패다.
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
