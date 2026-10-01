from contextlib import contextmanager
from collections.abc import Iterator
import psycopg
from app.config import get_settings

@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    with psycopg.connect(get_settings().database_url) as conn:
        yield conn
