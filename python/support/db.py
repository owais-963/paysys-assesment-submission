"""Read-only, parameterized SQL access to the MiniPay database. No ORM."""
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from support.config import Settings
from support.exceptions import DependencyError


def connect(settings: Settings):
    try:
        return psycopg2.connect(
            host=settings.db_host,
            port=settings.db_port,
            dbname=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            connect_timeout=settings.db_connect_timeout,
        )
    except psycopg2.OperationalError as exc:
        raise DependencyError(f"Could not connect to the database: {exc}") from exc


@contextmanager
def dict_cursor(conn):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield cur
    finally:
        cur.close()


def fetch_transactions_by_ref(conn, transaction_ref: str) -> list[dict]:
    with dict_cursor(conn) as cur:
        cur.execute(
            """
            SELECT t.id, t.transaction_ref, t.customer_id, t.amount, t.status,
                   t.created_at, t.completed_at, t.failure_code,
                   c.customer_ref, c.name AS customer_name
            FROM transactions t
            JOIN customers c ON c.id = t.customer_id
            WHERE t.transaction_ref = %s
            ORDER BY t.created_at DESC
            """,
            (transaction_ref,),
        )
        return cur.fetchall()


def fetch_callbacks_for_transaction(conn, transaction_id: int) -> list[dict]:
    with dict_cursor(conn) as cur:
        cur.execute(
            """
            SELECT attempt_no, http_status, callback_status, attempted_at
            FROM callbacks
            WHERE transaction_id = %s
            ORDER BY attempt_no ASC
            """,
            (transaction_id,),
        )
        return cur.fetchall()


def fetch_stuck_processing(conn, stuck_processing_minutes: int) -> list[dict]:
    with dict_cursor(conn) as cur:
        cur.execute(
            """
            SELECT id, transaction_ref, customer_id, amount, created_at
            FROM transactions
            WHERE status = 'PROCESSING'
              AND created_at < NOW() - (%s || ' minutes')::interval
            ORDER BY created_at ASC
            """,
            (stuck_processing_minutes,),
        )
        return cur.fetchall()


def fetch_recent_failed(conn, lookback_hours: int) -> list[dict]:
    with dict_cursor(conn) as cur:
        cur.execute(
            """
            SELECT id, transaction_ref, customer_id, amount, failure_code, created_at
            FROM transactions
            WHERE status = 'FAILED'
              AND created_at > NOW() - (%s || ' hours')::interval
            ORDER BY created_at DESC
            """,
            (lookback_hours,),
        )
        return cur.fetchall()
