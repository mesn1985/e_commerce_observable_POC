from __future__ import annotations

import importlib
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

BASE_URL = "http://localhost:8080"
ELASTICSEARCH_URL = "http://localhost:9200"

HEALTH_PATHS = [
    "/product-health",
    "/cart-health",
    "/inventory-health",
    "/payment-health",
    "/order-health",
]

CHECKOUT_PAYLOAD = {
    "items": [
        {"product_id": "p1001", "quantity": 1},
    ]
}

CORE_SERVICES = {
    "nginx",
    "cart-service",
    "product-service",
    "inventory-service",
    "payment-service",
    "order-service",
}

EVENT_FIELD_RULES = {
    ("cart-service", "checkout_started"): ["user_id", "item_count"],
    ("cart-service", "product_lookup_started"): ["product_id"],
    ("cart-service", "product_lookup_completed"): ["product_id", "product_name", "price"],
    ("cart-service", "inventory_reservation_started"): ["item_count"],
    ("inventory-service", "inventory_reservation_started"): ["item_count"],
    ("inventory-service", "database_write"): ["database", "collection", "operation", "duration_ms", "product_id", "quantity"],
    ("cart-service", "inventory_reservation_completed"): ["reservation_id"],
    ("inventory-service", "inventory_reservation_completed"): ["reservation_id"],
    ("cart-service", "payment_authorization_started"): ["total_amount", "currency"],
    ("payment-service", "payment_authorization_started"): ["user_id", "amount", "currency"],
    ("payment-service", "payment_authorization_completed"): ["transaction_id", "status_text"],
    ("cart-service", "payment_authorization_completed"): ["transaction_id", "status_text"],
    ("cart-service", "order_creation_started"): ["user_id"],
    ("order-service", "order_creation_started"): ["user_id", "order_id"],
    ("order-service", "database_write"): ["database", "collection", "operation", "duration_ms", "order_id"],
    ("order-service", "order_creation_completed"): ["order_id", "user_id", "total_amount"],
    ("cart-service", "checkout_completed"): ["order_id", "user_id", "total_amount"],
}

COMMON_EVENT_RULES = {
    "request_received": ["method", "path", "correlation_id_source"],
    "request_completed": ["method", "path", "status_code", "duration_ms", "correlation_id_source"],
    "outbound_http_request": ["target_service", "target_url", "method", "retry_attempt", "max_attempts"],
    "outbound_http_response": ["target_service", "status_code", "duration_ms", "retry_attempt", "max_attempts"],
    "database_query": ["database", "collection", "operation", "duration_ms"],
}

REPO_ROOT = Path(__file__).resolve().parents[2]


def require_module(module_name: str) -> Any:
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError:
        pytest.skip(f"Optional dependency {module_name!r} is required for smoke tests")


def run_compose(args: list[str], timeout: int = 600) -> str:
    result = subprocess.run(
        ["docker", "compose", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "docker compose command failed\n"
            f"Command: docker compose {' '.join(args)}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
    return result.stdout


def wait_for_stack_ready(timeout_seconds: int = 240) -> None:
    httpx = require_module("httpx")
    deadline = time.time() + timeout_seconds
    last_error = "stack not ready yet"

    while time.time() < deadline:
        try:
            with httpx.Client(timeout=5.0) as client:
                for path in HEALTH_PATHS:
                    response = client.get(f"{BASE_URL}{path}")
                    if response.status_code != 200:
                        raise RuntimeError(f"{path} returned {response.status_code}")
            return
        except Exception as exc:  # pragma: no cover - best effort retry loop
            last_error = str(exc)
            time.sleep(3)

    raise TimeoutError(f"Timed out waiting for stack to become healthy: {last_error}")


def search_trace(correlation_id: str) -> list[dict]:
    httpx = require_module("httpx")
    with httpx.Client(timeout=20.0) as client:
        response = client.get(
            f"{ELASTICSEARCH_URL}/filebeat-*/_search",
            params={
                "q": f"correlation_id:{correlation_id}",
                "size": 200,
                "sort": "@timestamp:asc",
            },
        )
        response.raise_for_status()
        payload = response.json()

    return payload.get("hits", {}).get("hits", [])


def wait_for_trace_in_elasticsearch(correlation_id: str, timeout_seconds: int = 120) -> list[dict]:
    deadline = time.time() + timeout_seconds
    last_count = 0

    while time.time() < deadline:
        hits = search_trace(correlation_id)
        last_count = len(hits)
        if hits:
            return hits
        time.sleep(2)

    raise TimeoutError(
        "Timed out waiting for Elasticsearch trace indexing "
        f"for correlation_id={correlation_id}; last hit count={last_count}"
    )
