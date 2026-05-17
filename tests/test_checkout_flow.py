"""
Integration test: end-to-end checkout flow through Nginx.

Requires the full Docker Compose stack to be running:
    docker compose up --build -d

Run with:
    pip install pytest httpx
    pytest tests/test_checkout_flow.py -v
"""

import httpx
import pytest

BASE_URL = "http://localhost:8080"

CHECKOUT_PAYLOAD = {
    "items": [
        {"product_id": "p1001", "quantity": 1}
    ]
}


def test_checkout_returns_200() -> None:
    response = httpx.post(
        f"{BASE_URL}/cart/student-1/checkout",
        json=CHECKOUT_PAYLOAD,
        timeout=30.0,
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"


def test_checkout_response_body() -> None:
    response = httpx.post(
        f"{BASE_URL}/cart/student-1/checkout",
        json=CHECKOUT_PAYLOAD,
        timeout=30.0,
    )
    body = response.json()

    assert body.get("status") == "success", f"Expected status='success', got: {body}"
    assert "order_id" in body, f"Response body missing 'order_id': {body}"
    assert "correlation_id" in body, f"Response body missing 'correlation_id': {body}"


def test_checkout_correlation_id_header() -> None:
    response = httpx.post(
        f"{BASE_URL}/cart/student-1/checkout",
        json=CHECKOUT_PAYLOAD,
        timeout=30.0,
    )
    assert "Correlation-ID" in response.headers, "Response is missing the Correlation-ID header"


def test_checkout_correlation_id_matches() -> None:
    """The Correlation-ID header and body correlation_id must be identical."""
    response = httpx.post(
        f"{BASE_URL}/cart/student-1/checkout",
        json=CHECKOUT_PAYLOAD,
        timeout=30.0,
    )
    header_id = response.headers.get("Correlation-ID", "")
    body_id = response.json().get("correlation_id", "")

    assert header_id, "Correlation-ID header is empty"
    assert body_id, "correlation_id in body is empty"
    assert header_id == body_id, (
        f"Header Correlation-ID ({header_id}) does not match body correlation_id ({body_id})"
    )


def test_checkout_propagates_supplied_correlation_id() -> None:
    """When the client supplies a Correlation-ID, the same value must be echoed back."""
    custom_id = "test-correlation-id-abc123"
    response = httpx.post(
        f"{BASE_URL}/cart/student-1/checkout",
        json=CHECKOUT_PAYLOAD,
        headers={"Correlation-ID": custom_id},
        timeout=30.0,
    )
    assert response.headers.get("Correlation-ID") == custom_id, (
        f"Expected Correlation-ID={custom_id!r}, got {response.headers.get('Correlation-ID')!r}"
    )
    assert response.json().get("correlation_id") == custom_id
