from pydantic import BaseModel
from typing import Optional


class Product(BaseModel):
    product_id: str
    name: str
    price: float
    currency: str
    correlation_id: Optional[str] = None
