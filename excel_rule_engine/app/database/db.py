"""
Database module - SQLite setup và session management.
"""

from __future__ import annotations

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DB_PATH: Path | None = None


def set_db_path(path: str | Path) -> None:
    global _DB_PATH
    _DB_PATH = Path(path)
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_db_path() -> Path:
    if _DB_PATH is None:
        default = Path(__file__).resolve().parents[2] / "excel_rule_engine.db"
        return default
    return _DB_PATH


def get_connection() -> sqlite3.Connection:
    """Trả về kết nối SQLite với row_factory."""
    conn = sqlite3.connect(str(get_db_path()))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Khởi tạo database schema."""
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT    NOT NULL,
                intent      TEXT    NOT NULL,
                raw_command TEXT    NOT NULL,
                status      TEXT    NOT NULL DEFAULT 'pending',
                result_path TEXT,
                error_msg   TEXT,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                project     TEXT NOT NULL DEFAULT 'demo_project',
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        logger.info("Database initialized: %s", get_db_path())
    finally:
        conn.close()

