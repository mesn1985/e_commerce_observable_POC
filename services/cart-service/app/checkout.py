"""
Checkout orchestration logic for cart-service.

Calls Product, Inventory, Payment, and Order services in sequence,
forwarding the same Correlation-ID on every outbound HTTP request.
"""

import os
from typing import List

from shared.http_client import call_service
from shared.logging_config import setup_logging

logger = setup_logging("cart-service")

PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://product-service:8001")
INVENTORY_SERVICE_URL = os.getenv("INVENTORY_SERVICE_URL", "http://inventory-service:8003")
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:8004")
ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://order-service:8005")


async def process_checkout(user_id: str, items: List[dict], correlation_id: str) -> dict:
    logger.info(
        "checkout_started",
        extra={
            "event": "checkout_started",
            "correlation_id": correlation_id,
            "user_id": user_id,
            "item_count": len(items),
        },
    )

    # ── Step 1: Fetch product details ────────────────────────────────────────
    order_items = []
    total_amount = 0.0

    for item in items:
        product_id = item["product_id"]
        quantity = item["quantity"]

        logger.info(
            "product_lookup_started",
            extra={
                "event": "product_lookup_started",
                "correlation_id": correlation_id,
                "product_id": product_id,
            },
        )

        resp = await call_service(
            correlation_id=correlation_id,
            method="GET",
            url=f"{PRODUCT_SERVICE_URL}/products/{product_id}",
            target_service="product-service",
            logger=logger,
        )
        product = resp.json()

        logger.info(
            "product_lookup_completed",
            extra={
                "event": "product_lookup_completed",
                "correlation_id": correlation_id,
                "product_id": product_id,
                "name": product.get("name"),
                "price": product.get("price"),
            },
        )

        total_amount += product["price"] * quantity
        order_items.append(
            {
                "product_id": product_id,
                "quantity": quantity,
                "unit_price": product["price"],
            }
        )

    # ── Step 2: Reserve inventory ─────────────────────────────────────────────
    logger.info(
        "inventory_reservation_started",
        extra={
            "event": "inventory_reservation_started",
            "correlation_id": correlation_id,
            "item_count": len(items),
        },
    )

    inv_resp = await call_service(
        correlation_id=correlation_id,
        method="POST",
        url=f"{INVENTORY_SERVICE_URL}/inventory/reserve",
        target_service="inventory-service",
        logger=logger,
        json={"items": items},
    )
    reservation = inv_resp.json()

    logger.info(
        "inventory_reservation_completed",
        extra={
            "event": "inventory_reservation_completed",
            "correlation_id": correlation_id,
            "reservation_id": reservation.get("reservation_id"),
        },
    )

    # ── Step 3: Authorize payment ─────────────────────────────────────────────
    logger.info(
        "payment_authorization_started",
        extra={
            "event": "payment_authorization_started",
            "correlation_id": correlation_id,
            "total_amount": total_amount,
            "currency": "DKK",
        },
    )

    pay_resp = await call_service(
        correlation_id=correlation_id,
        method="POST",
        url=f"{PAYMENT_SERVICE_URL}/payments/authorize",
        target_service="payment-service",
        logger=logger,
        json={"user_id": user_id, "amount": total_amount, "currency": "DKK"},
    )
    payment = pay_resp.json()

    logger.info(
        "payment_authorization_completed",
        extra={
            "event": "payment_authorization_completed",
            "correlation_id": correlation_id,
            "transaction_id": payment.get("transaction_id"),
            "status": payment.get("status"),
        },
    )

    # ── Step 4: Create order ──────────────────────────────────────────────────
    logger.info(
        "order_creation_started",
        extra={
            "event": "order_creation_started",
            "correlation_id": correlation_id,
            "user_id": user_id,
        },
    )

    order_resp = await call_service(
        correlation_id=correlation_id,
        method="POST",
        url=f"{ORDER_SERVICE_URL}/orders",
        target_service="order-service",
        logger=logger,
        json={
            "user_id": user_id,
            "items": order_items,
            "payment": {
                "transaction_id": payment["transaction_id"],
                "status": payment["status"],
            },
            "reservation_id": reservation["reservation_id"],
            "total_amount": total_amount,
            "currency": "DKK",
        },
    )
    order = order_resp.json()

    logger.info(
        "checkout_completed",
        extra={
            "event": "checkout_completed",
            "correlation_id": correlation_id,
            "order_id": order.get("order_id"),
            "user_id": user_id,
            "total_amount": total_amount,
        },
    )

    return {
        "status": "success",
        "order_id": order["order_id"],
        "correlation_id": correlation_id,
        "message": "Order created successfully",
    }
