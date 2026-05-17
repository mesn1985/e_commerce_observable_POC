from pydantic import BaseModel
from typing import List, Optional


class ReserveItem(BaseModel):
    product_id: str
    quantity: int


class ReserveRequest(BaseModel):
    items: List[ReserveItem]
