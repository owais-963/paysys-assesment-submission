from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, condecimal


class PaymentCreate(BaseModel):
    transaction_ref: str = Field(..., min_length=1, max_length=50)
    customer_id: int = Field(..., gt=0)
    amount: condecimal(gt=Decimal("0"), max_digits=14, decimal_places=2)


class PaymentOut(BaseModel):
    id: int
    transaction_ref: str
    customer_id: int
    amount: Decimal
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    failure_code: Optional[str] = None


class PaymentListOut(BaseModel):
    items: list[PaymentOut]
    limit: int
    offset: int
    returned_count: int
    has_more: bool


class PaymentSearchOut(BaseModel):
    query_ref: str
    count: int
    items: list[PaymentOut]
