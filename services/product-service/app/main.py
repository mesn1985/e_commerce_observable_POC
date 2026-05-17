import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.database import close_db, connect_db
from app.routes import router
from shared.correlation import CORRELATION_ID_HEADER
from shared.logging_config import setup_logging

SERVICE_NAME = "product-service"
logger = setup_logging(SERVICE_NAME)


@asynccontextmanager
async def lifespan(app: FastAPI):
    connect_db()
    yield
    close_db()


app = FastAPI(title=SERVICE_NAME, lifespan=lifespan)


@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    correlation_id = request.headers.get(CORRELATION_ID_HEADER) or str(uuid.uuid4())
    request.state.correlation_id = correlation_id

    start = time.monotonic()
    logger.info(
        "request_received",
        extra={
            "event": "request_received",
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
        },
    )

    response = await call_next(request)
    duration_ms = int((time.monotonic() - start) * 1000)

    response.headers[CORRELATION_ID_HEADER] = correlation_id
    logger.info(
        "request_completed",
        extra={
            "event": "request_completed",
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )

    return response


app.include_router(router)
