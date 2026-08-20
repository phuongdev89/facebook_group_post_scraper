import sqlite3
import os
from contextlib import contextmanager
from src.config.constants import DEFAULT_DB_PATH

@contextmanager
def get_connection(db_path: str = None):
    """Tạo kết nối SQLite với Row factory và bật foreign keys, WAL mode, tự động commit và close"""
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
