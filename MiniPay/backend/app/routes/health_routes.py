import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.database import get_connection

logger = logging.getLogger("minipay.health")

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return {"status": "ok", "db": "reachable"}
    except Exception:
        logger.exception("Health check failed: database unreachable")
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "db": "unreachable"},
        )
