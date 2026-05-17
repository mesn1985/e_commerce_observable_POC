#!/usr/bin/env python3
"""
demo_checkout.py — Send a checkout request through Nginx and print a Kibana search query.

Usage:
    python scripts/demo_checkout.py
"""

import json
import sys

import httpx

BASE_URL = "http://localhost:8080"

payload = {
    "items": [
        {"product_id": "p1001", "quantity": 2}
    ]
}


def main() -> None:
    print(f"Sending checkout request to {BASE_URL}/cart/student-1/checkout ...")
    print()

    try:
        response = httpx.post(
            f"{BASE_URL}/cart/student-1/checkout",
            json=payload,
            timeout=30.0,
        )
    except httpx.RequestError as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Status      : {response.status_code}")

    try:
        body = response.json()
        print(f"Body        : {json.dumps(body, indent=2)}")
    except Exception:
        print(f"Body        : {response.text}")
        body = {}

    corr_id = response.headers.get("Correlation-ID", "")
    print(f"Correlation-ID (header): {corr_id}")

    body_corr_id = body.get("correlation_id", "")
    if body_corr_id and body_corr_id != corr_id:
        print(f"WARNING: Body correlation_id ({body_corr_id}) does not match header ({corr_id})")

    if corr_id:
        print()
        print("Open Kibana Discover at http://localhost:5601 and search:")
        print(f'  correlation_id : "{corr_id}"')
    else:
        print("WARNING: Correlation-ID header not found in response.")
        sys.exit(1)


if __name__ == "__main__":
    main()
