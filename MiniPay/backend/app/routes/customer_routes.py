from fastapi import APIRouter, Response

from app.controllers import customer_controller
from app.database import get_connection
from app.schemas.customer_schema import CustomerCreate, CustomerOut

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(payload: CustomerCreate, response: Response):
    with get_connection() as conn:
        customer = customer_controller.create_customer(conn, payload)
    response.headers["Location"] = f"/api/customers/{customer.id}"
    return customer
