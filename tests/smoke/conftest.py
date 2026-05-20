from __future__ import annotations

import json
import os
from typing import Generator
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from tests.smoke._helpers import (
    BASE_URL,
    CHECKOUT_PAYLOAD,
    CORE_SERVICES,
    REPO_ROOT,
    run_compose,
    wait_for_stack_ready,
    wait_for_trace_in_elasticsearch,
)


@pytest.fixture(scope="session")
def smoke_environment() -> Generator[None, None, None]:
    # Clean up any previous environment.
    try:
        run_compose(["down", "-v", "--remove-orphans"], timeout=240)
    except Exception:
        pass  # Ignore errors on cleanup if stack doesn't exist

    # Start the full stack automatically for smoke tests.
    run_compose(["up", "--build", "-d"], timeout=900)
    wait_for_stack_ready(timeout_seconds=300)

    yield

    keep_env = os.getenv("SMOKE_KEEP_ENV", "").lower() in {"1", "true", "yes"}
    if not keep_env:
        try:
            run_compose(["down", "-v", "--remove-orphans"], timeout=240)
        except Exception:
            pass


@pytest.fixture(scope="session")
def checkout_trace(smoke_environment: None) -> dict:
    request_body = json.dumps(CHECKOUT_PAYLOAD).encode("utf-8")
    request = Request(
        f"{BASE_URL}/cart/student-1/checkout",
        data=request_body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urlopen(request, timeout=30.0) as response:
            status_code = response.getcode()
            response_text = response.read().decode("utf-8")
            correlation_id = response.headers.get("Correlation-ID", "")
    except HTTPError as exc:
        error_text = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise AssertionError(f"Checkout failed: {exc.code} {error_text}") from exc

    assert status_code == 200, f"Checkout failed: {status_code} {response_text}"

    body = json.loads(response_text)

    assert correlation_id, "Response missing Correlation-ID header"
    assert body.get("correlation_id") == correlation_id, "Correlation-ID mismatch between body and header"

    hits = wait_for_trace_in_elasticsearch(
        correlation_id,
        timeout_seconds=180,
        min_hits=20,
        required_services=CORE_SERVICES,
    )

    return {
        "correlation_id": correlation_id,
        "checkout_body": body,
        "hits": hits,
    }
