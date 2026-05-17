"""
Integration tests: verify all service health endpoints return HTTP 200 through Nginx.

Requires the full Docker Compose stack to be running:
    docker compose up --build -d

Run with:
    pip install pytest httpx
    pytest tests/test_health.py -v
"""

import httpx
import pytest

BASE_URL = "http://localhost:8080"


@pytest.mark.parametrize(
    "service,path",
    [
        ("product-service", "/product-health"),
        ("cart-service", "/cart-health"),
        ("inventory-service", "/inventory-health"),
        ("payment-service", "/payment-health"),
        ("order-service", "/order-health"),
    ],
)
def test_health_endpoint(service: str, path: str) -> None:
    response = httpx.get(f"{BASE_URL}{path}", timeout=15.0)
    assert response.status_code == 200, f"{service} returned HTTP {response.status_code}"

    body = response.json()
    assert body["status"] == "ok", f"{service} status field is not 'ok': {body}"
    assert "Correlation-ID" in response.headers, f"{service} did not return Correlation-ID header"
