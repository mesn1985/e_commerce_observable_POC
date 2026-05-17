from __future__ import annotations

import os
from typing import Generator

import pytest

from tests.smoke._helpers import (
    BASE_URL,
    CHECKOUT_PAYLOAD,
    REPO_ROOT,
    require_module,
    run_compose,
    wait_for_stack_ready,
    wait_for_trace_in_elasticsearch,
)


@pytest.fixture(scope="session")
def smoke_environment() -> Generator[None, None, None]:
    compose_module = require_module("testcontainers.compose")
    DockerCompose = compose_module.DockerCompose

    run_compose(["down", "-v"], timeout=240)
    compose = DockerCompose(str(REPO_ROOT), compose_file_name="docker-compose.yml")
    compose.start()
    wait_for_stack_ready(timeout_seconds=300)

    yield

    if os.getenv("SMOKE_KEEP_ENV", "0") != "1":
        compose.stop()
        run_compose(["down", "-v"], timeout=240)


@pytest.fixture(scope="session")
def checkout_trace(smoke_environment: None) -> dict:
    httpx = require_module("httpx")
    with httpx.Client(timeout=30.0) as client:
        response = client.post(f"{BASE_URL}/cart/student-1/checkout", json=CHECKOUT_PAYLOAD)

    assert response.status_code == 200, f"Checkout failed: {response.status_code} {response.text}"

    body = response.json()
    correlation_id = response.headers.get("Correlation-ID", "")

    assert correlation_id, "Response missing Correlation-ID header"
    assert body.get("correlation_id") == correlation_id, "Correlation-ID mismatch between body and header"

    hits = wait_for_trace_in_elasticsearch(correlation_id)

    return {
        "correlation_id": correlation_id,
        "checkout_body": body,
        "hits": hits,
    }
