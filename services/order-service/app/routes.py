import time
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.database import get_db
from app.models import CreateOrderRequest
from shared.logging_config import setup_logging

logger = setup_logging("order-service")

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    correlation_id = request.state.correlation_id
    return {"status": "ok", "service": "order-service", "correlation_id": correlation_id}


@router.post("/orders")
async def create_order(body: CreateOrderRequest, request: Request):
    correlation_id = request.state.correlation_id
    db = get_db()

    order_id = f"ord_{uuid.uuid4().hex[:12]}"

    logger.info(
        "order_creation_started",
        extra={
            "event": "order_creation_started",
            "correlation_id": correlation_id,
            "user_id": body.user_id,
            "order_id": order_id,
        },
    )

    order_doc = {
        "order_id": order_id,
        "user_id": body.user_id,
        "items": [item.model_dump() for item in body.items],
        "payment": body.payment.model_dump(),
        "reservation_id": body.reservation_id,
        "total_amount": body.total_amount,
        "currency": body.currency,
        "status": "created",
    }

    start = time.monotonic()
    db.orders.insert_one(order_doc)
    duration_ms = int((time.monotonic() - start) * 1000)

    logger.info(
        "database_write",
        extra={
            "event": "database_write",
            "correlation_id": correlation_id,
            "database": "order_db",
            "collection": "orders",
            "operation": "insert_one",
            "duration_ms": duration_ms,
            "order_id": order_id,
        },
    )

    logger.info(
        "order_creation_completed",
        extra={
            "event": "order_creation_completed",
            "correlation_id": correlation_id,
            "order_id": order_id,
            "user_id": body.user_id,
            "total_amount": body.total_amount,
        },
    )

    return {
        "status": "created",
        "order_id": order_id,
        "correlation_id": correlation_id,
    }


@router.get("/orders/{order_id}")
async def get_order(order_id: str, request: Request):
    correlation_id = request.state.correlation_id
    db = get_db()

    start = time.monotonic()
    order = db.orders.find_one({"order_id": order_id}, {"_id": 0})
    duration_ms = int((time.monotonic() - start) * 1000)

    logger.info(
        "database_query",
        extra={
            "event": "database_query",
            "correlation_id": correlation_id,
            "database": "order_db",
            "collection": "orders",
            "operation": "find_one",
            "duration_ms": duration_ms,
            "order_id": order_id,
        },
    )

    if not order:
        return JSONResponse(
            status_code=404,
            content={"detail": "Order not found", "correlation_id": correlation_id},
        )

    order["correlation_id"] = correlation_id
    return order
