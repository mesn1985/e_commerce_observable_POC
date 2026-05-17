"""
Correlation ID helpers shared across all services.
"""

CORRELATION_ID_HEADER = "Correlation-ID"


def get_correlation_id(headers: dict) -> str:
    """Extract the Correlation-ID from a headers mapping (case-insensitive key lookup)."""
    for key, value in headers.items():
        if key.lower() == CORRELATION_ID_HEADER.lower():
            return value
    return ""
