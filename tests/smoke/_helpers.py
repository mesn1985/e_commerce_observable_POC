from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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


def _http_get_json(url: str, *, params: dict[str, object] | None = None, timeout: float = 20.0) -> dict:
    full_url = url
    if params:
        full_url = f"{url}?{urlencode(params)}"

    request = Request(full_url, method="GET")
    with urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


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
    deadline = time.time() + timeout_seconds
    last_error = "stack not ready yet"

    while time.time() < deadline:
        try:
            for path in HEALTH_PATHS:
                _http_get_json(f"{BASE_URL}{path}", timeout=5.0)
            return
        except Exception as exc:  # pragma: no cover - best effort retry loop
            last_error = str(exc)
            time.sleep(3)

    raise TimeoutError(f"Timed out waiting for stack to become healthy: {last_error}")


def search_trace(correlation_id: str) -> list[dict]:
    request = Request(
        f"{ELASTICSEARCH_URL}/filebeat-*/_search",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "size": 500,
                "sort": [{"@timestamp": {"order": "asc"}}],
                "query": {
                    "bool": {
                        "should": [
                            {"term": {"correlation_id.keyword": correlation_id}},
                            {"term": {"correlation_id": correlation_id}},
                        ],
                        "minimum_should_match": 1,
                    }
                },
            }
        ).encode("utf-8"),
    )

    with urlopen(request, timeout=20.0) as response:
        payload = json.loads(response.read().decode("utf-8"))

    return payload.get("hits", {}).get("hits", [])


def wait_for_trace_in_elasticsearch(
    correlation_id: str,
    timeout_seconds: int = 120,
    min_hits: int = 1,
    required_services: set[str] | None = None,
) -> list[dict]:
    deadline = time.time() + timeout_seconds
    last_count = 0
    best_hits: list[dict] = []

    def _services_in_hits(hits: list[dict]) -> set[str]:
        return {
            hit.get("_source", {}).get("service_name")
            for hit in hits
            if hit.get("_source", {}).get("service_name")
        }

    while time.time() < deadline:
        try:
            hits = search_trace(correlation_id)
            last_count = len(hits)
            if len(hits) > len(best_hits):
                best_hits = hits

            enough_hits = len(hits) >= min_hits
            required_ok = True
            if required_services:
                required_ok = required_services.issubset(_services_in_hits(hits))

            if enough_hits and required_ok:
                return hits
        except Exception:
            # Elasticsearch can briefly return 503 while the cluster is warming up.
            pass
        time.sleep(2)

    raise TimeoutError(
        "Timed out waiting for Elasticsearch trace indexing "
        f"for correlation_id={correlation_id}; "
        f"last hit count={last_count}; best hit count={len(best_hits)}"
    )
