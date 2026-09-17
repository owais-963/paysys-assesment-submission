from app.models import customer_model
from app.schemas.customer_schema import CustomerCreate, CustomerOut


def create_customer(conn, payload: CustomerCreate) -> CustomerOut:
    row = customer_model.insert_customer(conn, payload.customer_ref, payload.name)
    return CustomerOut(**row)
