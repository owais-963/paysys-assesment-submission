from fastapi import APIRouter, Query, Response

from app.controllers import payment_controller
from app.database import get_connection
from app.schemas.payment_schema import PaymentCreate, PaymentListOut, PaymentOut, PaymentSearchOut

payments_router = APIRouter(prefix="/api/payments", tags=["payments"])
customer_payments_router = APIRouter(prefix="/api/customers", tags=["payments"])


@payments_router.post("", response_model=PaymentOut, status_code=201)
def create_payment(payload: PaymentCreate, response: Response):
    with get_connection() as conn:
        payment = payment_controller.create_payment(conn, payload)
    response.headers["Location"] = f"/api/payments/{payment.id}"
    return payment


# Registered before /{payment_id} deliberately: a static path
# ("/api/payments/search") must be matched before a dynamic one
# ("/api/payments/{payment_id}") to avoid any path-matching ambiguity.
@payments_router.get("/search", response_model=PaymentSearchOut)
def search_payments_by_reference(
    transaction_ref: str = Query(..., min_length=1, max_length=50),
):
    with get_connection() as conn:
        return payment_controller.search_payments_by_transaction_ref(conn, transaction_ref)


@payments_router.get("/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: int):
    with get_connection() as conn:
        return payment_controller.get_payment(conn, payment_id)


@customer_payments_router.get("/{customer_id}/payments", response_model=PaymentListOut)
def list_customer_payments(
    customer_id: int,
    limit: int = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
):
    with get_connection() as conn:
        return payment_controller.list_customer_payments(conn, customer_id, limit, offset)
