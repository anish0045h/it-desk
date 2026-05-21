import os
import logging
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Connection string configuration
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    db_host = os.environ.get("DB_HOST", "localhost")
    db_port = os.environ.get("DB_PORT", "5432")
    db_name = os.environ.get("DB_NAME", "deskmate")
    db_user = os.environ.get("DB_USER", "postgres")
    db_password = os.environ.get("DB_PASSWORD", "postgres")
    DATABASE_URL = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

# Initialise connection pool
_pool = None

def get_pool():
    global _pool
    if _pool is None:
        try:
            logger.info("Initialising PostgreSQL connection pool...")
            _pool = SimpleConnectionPool(
                minconn=1,
                maxconn=15,
                dsn=DATABASE_URL
            )
        except Exception as e:
            logger.error("Failed to create PostgreSQL connection pool: %s", e)
            raise e
    return _pool

@contextmanager
def get_db_cursor():
    """
    Context manager to fetch a connection from the pool, 
    yield a dictionary-based cursor, and return the connection to the pool.
    """
    pool = get_pool()
    conn = pool.getconn()
    try:
        # DictCursor allows accessing columns by name (like a dictionary)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
            conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error("Database query failed, transaction rolled back: %s", e)
        raise e
    finally:
        pool.putconn(conn)


def is_db_configured() -> bool:
    """
    Check if the database connection parameters are configured and active.
    If placeholder strings are in the URL or the connection test fails, returns False.
    """
    url = DATABASE_URL
    if not url or "your_database_name" in url or "your_password" in url:
        return False
    try:
        pool = get_pool()
        conn = pool.getconn()
        pool.putconn(conn)
        return True
    except Exception:
        return False

