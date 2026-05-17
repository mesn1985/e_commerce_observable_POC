from fastapi import APIRouter, Request

from app.checkout import process_checkout
from app.models import CheckoutRequest

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    correlation_id = request.state.correlation_id
    return {"status": "ok", "service": "cart-service", "correlation_id": correlation_id}


@router.post("/cart/{user_id}/checkout")
async def checkout(user_id: str, body: CheckoutRequest, request: Request):
    correlation_id = request.state.correlation_id
    items = [item.model_dump() for item in body.items]
    result = await process_checkout(
        user_id=user_id,
        items=items,
        correlation_id=correlation_id,
    )
    return result
