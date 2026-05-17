from pydantic import BaseModel
from typing import List


class OrderItem(BaseModel):
    product_id: str
    quantity: int
    unit_price: float


class PaymentInfo(BaseModel):
    transaction_id: str
    status: str


class CreateOrderRequest(BaseModel):
    user_id: str
    items: List[OrderItem]
    payment: PaymentInfo
    reservation_id: str
    total_amount: float
    currency: str
