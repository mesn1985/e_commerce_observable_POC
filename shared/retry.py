"""
Retry configuration using tenacity.
Exposed as reusable decorators and settings for service code.
"""

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
import httpx

MAX_ATTEMPTS = 3


def get_retry_decorator():
    """
    Return a tenacity retry decorator configured for HTTP calls.
    Retries up to MAX_ATTEMPTS on HTTP or network errors.
    """
    return retry(
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=0.1, min=0.1, max=1.0),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
        reraise=True,
    )
