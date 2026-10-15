
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "kittycat.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection(db_path=None):
    path = Path(db_path) if db_path is not None else DB_PATH

    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")

    return conn


def initialize_database(db_path=None):
    conn = get_connection(db_path)

    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(
            SCHEMA_PATH.read_text(encoding="utf-8")
        )
        conn.commit()
    finally:
        conn.close()
