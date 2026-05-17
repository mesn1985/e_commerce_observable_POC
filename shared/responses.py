"""
Helpers for building consistent JSON response bodies.
"""

from typing import Any, Dict


def with_correlation_id(data: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    """Merge correlation_id into a response dict."""
    return {**data, "correlation_id": correlation_id}
