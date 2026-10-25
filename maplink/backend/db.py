"""PostgreSQL access. All transfer mutations occur under row locks in a transaction."""
import os
from contextlib import contextmanager
from pathlib import Path

SCHEMA = Path(__file__).with_name("schema.sql")

def connect():
    import psycopg
    from psycopg.rows import dict_row
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("Set DATABASE_URL to a PostgreSQL DSN")
    return psycopg.connect(dsn, row_factory=dict_row)

@contextmanager
def transaction():
    with connect() as conn:
        with conn.cursor() as cur:
            yield cur
        conn.commit()

def migrate():
    with connect() as conn:
        conn.execute(SCHEMA.read_text(encoding="utf-8"))
        conn.commit()
