from fastapi import APIRouter, Request

from app.mock_provider import provider
from app.models import PaymentRequest
from shared.logging_config import setup_logging

logger = setup_logging("payment-service")

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    correlation_id = request.state.correlation_id
    return {"status": "ok", "service": "payment-service", "correlation_id": correlation_id}


@router.post("/payments/authorize")
async def authorize_payment(body: PaymentRequest, request: Request):
    correlation_id = request.state.correlation_id

    logger.info(
        "payment_authorization_started",
        extra={
            "event": "payment_authorization_started",
            "correlation_id": correlation_id,
            "user_id": body.user_id,
            "amount": body.amount,
            "currency": body.currency,
        },
    )

    result = provider.authorize(
        user_id=body.user_id,
        amount=body.amount,
        currency=body.currency,
    )

    logger.info(
        "payment_authorization_completed",
        extra={
            "event": "payment_authorization_completed",
            "correlation_id": correlation_id,
            "transaction_id": result["transaction_id"],
            "status": result["status"],
        },
    )

    return {**result, "correlation_id": correlation_id}
