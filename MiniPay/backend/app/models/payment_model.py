"""Raw SQL data access for the transactions table (exposed to the API as
"payments"). No ORM.
"""
from decimal import Decimal

from app.database import get_dict_cursor


def insert_payment(conn, transaction_ref: str, customer_id: int, amount: Decimal) -> dict:
    with get_dict_cursor(conn) as cur:
        cur.execute(
            """
            INSERT INTO transactions (transaction_ref, customer_id, amount, status, created_at)
            VALUES (%s, %s, %s, 'PROCESSING', NOW())
            RETURNING id, transaction_ref, customer_id, amount, status, created_at, completed_at, failure_code
            """,
            (transaction_ref, customer_id, amount),
        )
        return cur.fetchone()


def get_payments_by_transaction_ref(conn, transaction_ref: str) -> list[dict]:
    # transaction_ref has no uniqueness constraint in database/schema.sql,
    # and the Objective 1 seed data intentionally contains duplicates (see
    # sql/04_duplicate_transaction_references.sql) -- this returns every
    # matching row rather than assuming there is only one.
    with get_dict_cursor(conn) as cur:
        cur.execute(
            """
            SELECT id, transaction_ref, customer_id, amount, status, created_at, completed_at, failure_code
            FROM transactions
            WHERE transaction_ref = %s
            ORDER BY created_at DESC
            """,
            (transaction_ref,),
        )
        return cur.fetchall()


def get_payment_by_id(conn, payment_id: int) -> dict | None:
    with get_dict_cursor(conn) as cur:
        cur.execute(
            """
            SELECT id, transaction_ref, customer_id, amount, status, created_at, completed_at, failure_code
            FROM transactions
            WHERE id = %s
            """,
            (payment_id,),
        )
        return cur.fetchone()


def list_payments_by_customer(conn, customer_id: int, limit: int, offset: int) -> list[dict]:
    # Ordered by (created_at, id) with a limit/offset bound by the caller
    # (see PAYMENTS_PAGE_SIZE_MAX) so a single request can't force a scan of
    # the entire transactions table for a customer with a large history.
    # Fetches one extra row beyond `limit` so the controller can report
    # has_more without running a separate COUNT(*) over the customer's rows.
    with get_dict_cursor(conn) as cur:
        cur.execute(
            """
            SELECT id, transaction_ref, customer_id, amount, status, created_at, completed_at, failure_code
            FROM transactions
            WHERE customer_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT %s OFFSET %s
            """,
            (customer_id, limit + 1, offset),
        )
        return cur.fetchall()
