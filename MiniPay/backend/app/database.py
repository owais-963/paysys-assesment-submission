"""Connection-pooled access to the existing Postgres database. No ORM: every
query elsewhere in the app is plain, parameterized SQL executed through a
connection borrowed from this pool.
"""
import logging
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
import psycopg2.pool

from app.config import settings

logger = logging.getLogger("minipay.database")

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def init_pool() -> None:
    global _pool
    if _pool is not None:
        return
    _pool = psycopg2.pool.ThreadedConnectionPool(
        settings.db_pool_min,
        settings.db_pool_max,
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        connect_timeout=5,
    )
    logger.info("Database connection pool initialized (min=%s, max=%s)",
                settings.db_pool_min, settings.db_pool_max)


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None
        logger.info("Database connection pool closed")


@contextmanager
def get_connection():
    """Borrow a connection from the pool; always returns it, even on error."""
    if _pool is None:
        raise RuntimeError("Database pool not initialized")
    conn = _pool.getconn()
    try:
        yield conn
    finally:
        _pool.putconn(conn)


@contextmanager
def get_dict_cursor(conn):
    """A cursor that returns rows as dict-like objects, committing on success
    and rolling back on any exception raised inside the block.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
