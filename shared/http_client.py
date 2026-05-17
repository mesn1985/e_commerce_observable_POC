"""
Outbound HTTP client with automatic Correlation-ID forwarding,
structured logging, and per-call retry logic.
"""

import time
from typing import Any, Optional

import httpx

from shared.correlation import CORRELATION_ID_HEADER

MAX_ATTEMPTS = 3


async def call_service(
    correlation_id: str,
    method: str,
    url: str,
    target_service: str,
    logger,
    json: Optional[Any] = None,
    params: Optional[dict] = None,
) -> httpx.Response:
    """
    Make an HTTP call to a downstream service.

    - Forwards Correlation-ID automatically.
    - Logs outbound_http_request and outbound_http_response for every attempt,
      including attempt 1 when it succeeds.
    - Retries up to MAX_ATTEMPTS on HTTP or network errors.
    """
    async with httpx.AsyncClient(
        headers={CORRELATION_ID_HEADER: correlation_id},
        timeout=10.0,
    ) as client:
        last_exc: Optional[Exception] = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            start = time.monotonic()

            logger.info(
                "outbound_http_request",
                extra={
                    "event": "outbound_http_request",
                    "correlation_id": correlation_id,
                    "target_service": target_service,
                    "target_url": url,
                    "method": method.upper(),
                    "retry_attempt": attempt,
                    "max_attempts": MAX_ATTEMPTS,
                },
            )

            try:
                response = await client.request(method, url, json=json, params=params)
                duration_ms = int((time.monotonic() - start) * 1000)

                logger.info(
                    "outbound_http_response",
                    extra={
                        "event": "outbound_http_response",
                        "correlation_id": correlation_id,
                        "target_service": target_service,
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                        "retry_attempt": attempt,
                        "max_attempts": MAX_ATTEMPTS,
                    },
                )

                response.raise_for_status()
                return response

            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                duration_ms = int((time.monotonic() - start) * 1000)
                last_exc = exc

                if attempt < MAX_ATTEMPTS:
                    logger.warning(
                        "retry_attempt",
                        extra={
                            "event": "retry_attempt",
                            "correlation_id": correlation_id,
                            "target_service": target_service,
                            "target_url": url,
                            "retry_attempt": attempt,
                            "max_attempts": MAX_ATTEMPTS,
                            "error": str(exc),
                            "duration_ms": duration_ms,
                        },
                    )

        raise last_exc or RuntimeError("call_service exhausted all attempts")
