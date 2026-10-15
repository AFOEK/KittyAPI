import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "kittycat.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    return conn

def initialize_database():
    conn = get_connection()

    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(
            SCHEMA_PATH.read_text(encoding="utf-8")
        )
        conn.commit()
    finally:
        conn.close()