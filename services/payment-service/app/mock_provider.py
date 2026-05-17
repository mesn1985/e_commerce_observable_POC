"""
Static mock payment provider.
Always approves valid requests and returns a fake transaction ID.
No real payment processing occurs.
"""

import uuid


class MockPaymentProvider:
    """Simulates a payment gateway. Always approves valid requests."""

    def authorize(self, user_id: str, amount: float, currency: str) -> dict:
        transaction_id = f"txn_{uuid.uuid4().hex[:12]}"
        return {
            "status": "approved",
            "transaction_id": transaction_id,
        }


# Module-level singleton — instantiated once at import time
provider = MockPaymentProvider()
