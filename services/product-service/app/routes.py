import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.database import get_db
from shared.logging_config import setup_logging

logger = setup_logging("product-service")

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    correlation_id = request.state.correlation_id
    return {"status": "ok", "service": "product-service", "correlation_id": correlation_id}


@router.get("/products")
async def list_products(request: Request):
    correlation_id = request.state.correlation_id
    db = get_db()

    start = time.monotonic()
    products = list(db.products.find({}, {"_id": 0}))
    duration_ms = int((time.monotonic() - start) * 1000)

    logger.info(
        "database_query",
        extra={
            "event": "database_query",
            "correlation_id": correlation_id,
            "database": "product_db",
            "collection": "products",
            "operation": "find",
            "duration_ms": duration_ms,
            "result_count": len(products),
        },
    )

    for product in products:
        product["correlation_id"] = correlation_id

    return products


@router.get("/products/{product_id}")
async def get_product(product_id: str, request: Request):
    correlation_id = request.state.correlation_id
    db = get_db()

    start = time.monotonic()
    product = db.products.find_one({"product_id": product_id}, {"_id": 0})
    duration_ms = int((time.monotonic() - start) * 1000)

    logger.info(
        "database_query",
        extra={
            "event": "database_query",
            "correlation_id": correlation_id,
            "database": "product_db",
            "collection": "products",
            "operation": "find_one",
            "duration_ms": duration_ms,
            "product_id": product_id,
        },
    )

    if not product:
        return JSONResponse(status_code=404, content={"detail": "Product not found", "correlation_id": correlation_id})

    product["correlation_id"] = correlation_id
    return product
