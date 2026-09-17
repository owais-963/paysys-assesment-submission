from app.config import settings
from app.exceptions import NotFoundError
from app.models import customer_model, payment_model
from app.schemas.payment_schema import PaymentCreate, PaymentListOut, PaymentOut


def create_payment(conn, payload: PaymentCreate) -> PaymentOut:
    customer = customer_model.get_customer_by_id(conn, payload.customer_id)
    if customer is None:
        raise NotFoundError(f"customer {payload.customer_id} not found")
    row = payment_model.insert_payment(
        conn, payload.transaction_ref, payload.customer_id, payload.amount
    )
    return PaymentOut(**row)


def get_payment(conn, payment_id: int) -> PaymentOut:
    row = payment_model.get_payment_by_id(conn, payment_id)
    if row is None:
        raise NotFoundError(f"payment {payment_id} not found")
    return PaymentOut(**row)


def list_customer_payments(conn, customer_id: int, limit: int | None, offset: int) -> PaymentListOut:
    customer = customer_model.get_customer_by_id(conn, customer_id)
    if customer is None:
        raise NotFoundError(f"customer {customer_id} not found")

    effective_limit = limit or settings.payments_page_size_default
    effective_limit = min(effective_limit, settings.payments_page_size_max)

    rows = payment_model.list_payments_by_customer(conn, customer_id, effective_limit, offset)
    has_more = len(rows) > effective_limit
    rows = rows[:effective_limit]

    return PaymentListOut(
        items=[PaymentOut(**row) for row in rows],
        limit=effective_limit,
        offset=offset,
        returned_count=len(rows),
        has_more=has_more,
    )
