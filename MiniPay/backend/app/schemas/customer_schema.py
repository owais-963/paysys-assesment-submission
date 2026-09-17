from datetime import datetime

from pydantic import BaseModel, Field


class CustomerCreate(BaseModel):
    customer_ref: str = Field(..., min_length=1, max_length=40)
    name: str = Field(..., min_length=1, max_length=120)


class CustomerOut(BaseModel):
    id: int
    customer_ref: str
    name: str
    created_at: datetime
