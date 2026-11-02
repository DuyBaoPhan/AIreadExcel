"""
Task Repository - CRUD operations cho bảng tasks.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.database.db import get_connection

logger = logging.getLogger(__name__)


def create_task(
    session_id: str,
    intent: str,
    raw_command: str,
) -> int:
    """Tạo task mới, trả về task_id."""
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO tasks (session_id, intent, raw_command, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (session_id, intent, raw_command),
        )
        conn.commit()
        task_id = cur.lastrowid
        logger.info("Created task id=%d intent=%s", task_id, intent)
        return task_id
    finally:
        conn.close()


def update_task_status(
    task_id: int,
    status: str,
    result_path: str | None = None,
    error_msg: str | None = None,
) -> None:
    """Cập nhật trạng thái task."""
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE tasks
            SET status=?, result_path=?, error_msg=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (status, result_path, error_msg, task_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_task(task_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_tasks(session_id: str, limit: int = 20) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE session_id=? ORDER BY created_at DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def ensure_session(session_id: str, project: str = "demo_project") -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO sessions (id, project) VALUES (?, ?)",
            (session_id, project),
        )
        conn.commit()
    finally:
        conn.close()

