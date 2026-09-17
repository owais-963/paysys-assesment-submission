import logging

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth import require_api_key
from app.config import settings
from app.database import close_pool, init_pool
from app.exceptions import ConflictError, NotFoundError
from app.routes.customer_routes import router as customer_router
from app.routes.health_routes import router as health_router
from app.routes.payment_routes import customer_payments_router, payments_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("minipay.main")

app = FastAPI(title="MiniPay API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# /health is intentionally unauthenticated (used as a liveness/readiness
# check). Every /api/* route requires the X-API-Key header.
app.include_router(health_router)
app.include_router(customer_router, dependencies=[Depends(require_api_key)])
app.include_router(payments_router, dependencies=[Depends(require_api_key)])
app.include_router(customer_payments_router, dependencies=[Depends(require_api_key)])


@app.on_event("startup")
def on_startup():
    init_pool()


@app.on_event("shutdown")
def on_shutdown():
    close_pool()


@app.exception_handler(NotFoundError)
def handle_not_found(request: Request, exc: NotFoundError):
    return JSONResponse(status_code=404, content={"error": "not_found", "message": exc.message})


@app.exception_handler(ConflictError)
def handle_conflict(request: Request, exc: ConflictError):
    return JSONResponse(status_code=409, content={"error": "conflict", "message": exc.message})


@app.exception_handler(Exception)
def handle_unexpected(request: Request, exc: Exception):
    logger.exception("Unhandled error while processing %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "message": "An unexpected error occurred"},
    )
