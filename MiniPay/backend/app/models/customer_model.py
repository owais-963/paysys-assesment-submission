"""Raw SQL data access for the customers table. No ORM."""
import psycopg2

from app.database import get_dict_cursor
from app.exceptions import ConflictError


def insert_customer(conn, customer_ref: str, name: str) -> dict:
    with get_dict_cursor(conn) as cur:
        try:
            cur.execute(
                """
                INSERT INTO customers (customer_ref, name)
                VALUES (%s, %s)
                RETURNING id, customer_ref, name, created_at
                """,
                (customer_ref, name),
            )
        except psycopg2.errors.UniqueViolation as exc:
            raise ConflictError(
                f"customer_ref '{customer_ref}' already exists"
            ) from exc
        return cur.fetchone()


def get_customer_by_id(conn, customer_id: int) -> dict | None:
    with get_dict_cursor(conn) as cur:
        cur.execute(
            "SELECT id, customer_ref, name, created_at FROM customers WHERE id = %s",
            (customer_id,),
        )
        return cur.fetchone()
