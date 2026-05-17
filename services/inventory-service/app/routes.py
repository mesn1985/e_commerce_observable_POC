import time
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.database import get_db
from app.models import ReserveRequest
from shared.logging_config import setup_logging

logger = setup_logging("inventory-service")

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    correlation_id = request.state.correlation_id
    return {"status": "ok", "service": "inventory-service", "correlation_id": correlation_id}


@router.get("/inventory/{product_id}")
async def get_inventory(product_id: str, request: Request):
    correlation_id = request.state.correlation_id
    db = get_db()

    start = time.monotonic()
    item = db.inventory.find_one({"product_id": product_id}, {"_id": 0})
    duration_ms = int((time.monotonic() - start) * 1000)

    logger.info(
        "database_query",
        extra={
            "event": "database_query",
            "correlation_id": correlation_id,
            "database": "inventory_db",
            "collection": "inventory",
            "operation": "find_one",
            "duration_ms": duration_ms,
            "product_id": product_id,
        },
    )

    if not item:
        return JSONResponse(
            status_code=404,
            content={"detail": "Product not found in inventory", "correlation_id": correlation_id},
        )

    item["correlation_id"] = correlation_id
    return item


@router.post("/inventory/reserve")
async def reserve_inventory(body: ReserveRequest, request: Request):
    correlation_id = request.state.correlation_id
    db = get_db()

    logger.info(
        "inventory_reservation_started",
        extra={
            "event": "inventory_reservation_started",
            "correlation_id": correlation_id,
            "item_count": len(body.items),
        },
    )

    for item in body.items:
        start = time.monotonic()
        result = db.inventory.find_one_and_update(
            {"product_id": item.product_id, "stock": {"$gte": item.quantity}},
            {"$inc": {"stock": -item.quantity}},
            return_document=True,
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        logger.info(
            "database_write",
            extra={
                "event": "database_write",
                "correlation_id": correlation_id,
                "database": "inventory_db",
                "collection": "inventory",
                "operation": "find_one_and_update",
                "duration_ms": duration_ms,
                "product_id": item.product_id,
                "quantity": item.quantity,
            },
        )

        if result is None:
            return JSONResponse(
                status_code=409,
                content={
                    "detail": f"Insufficient stock for product {item.product_id}",
                    "correlation_id": correlation_id,
                },
            )

    reservation_id = f"res_{uuid.uuid4().hex[:12]}"

    logger.info(
        "inventory_reservation_completed",
        extra={
            "event": "inventory_reservation_completed",
            "correlation_id": correlation_id,
            "reservation_id": reservation_id,
        },
    )

    return {
        "status": "reserved",
        "reservation_id": reservation_id,
        "correlation_id": correlation_id,
    }
