# db.py — PostgreSQL connection pool (optional; falls back to mock_data if unconfigured)

import logging
import os
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL") or (
    "postgresql://{user}:{pw}@{host}:{port}/{db}".format(
        user=os.getenv("DB_USER", "postgres"),
        pw=os.getenv("DB_PASSWORD", "postgres"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        db=os.getenv("DB_NAME", "deskmate"),
    )
)

_pool: SimpleConnectionPool | None = None


def _get_pool() -> SimpleConnectionPool:
    global _pool
    if _pool is None:
        _pool = SimpleConnectionPool(1, 10, dsn=DATABASE_URL)
        logger.info("PostgreSQL connection pool initialised.")
    return _pool


@contextmanager
def get_db_cursor():
    """Yield a RealDictCursor; commit on success, rollback on error."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def is_db_configured() -> bool:
    """Return True only if a real DB connection can be established."""
    if "your_password" in DATABASE_URL or "your_database" in DATABASE_URL:
        return False
    try:
        pool = _get_pool()
        conn = pool.getconn()
        pool.putconn(conn)
        return True
    except Exception:
        return False
