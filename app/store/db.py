"""SQLite 会话状态存储。

单表 sessions, 按 candidate_id 跟踪招聘阶段 (stage)、简历快照、对话指纹。
对话历史本身由 RPA 每轮抓取传入, 不在此持久化全文。
"""

import sqlite3
from contextlib import contextmanager
from typing import Optional

from app.config import settings
from app.schemas import DEFAULT_STAGE


@contextmanager
def _conn():
    conn = sqlite3.connect(settings.db_path_abs)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    candidate_id       TEXT PRIMARY KEY,
    stage              TEXT NOT NULL DEFAULT '初步接触',
    resume             TEXT NOT NULL DEFAULT '',
    turns              INTEGER NOT NULL DEFAULT 0,
    conversation_hash  TEXT NOT NULL DEFAULT '',
    resume_hash        TEXT NOT NULL DEFAULT '',
    resume_score       INTEGER,
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

_EXTRA_COLUMNS = (
    ("conversation_hash", "TEXT NOT NULL DEFAULT ''"),
    ("resume_hash", "TEXT NOT NULL DEFAULT ''"),
    ("resume_score", "INTEGER"),
)


def _ensure_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
    for name, ddl in _EXTRA_COLUMNS:
        if name not in existing:
            conn.execute(f"ALTER TABLE sessions ADD COLUMN {name} {ddl}")


def init_db() -> None:
    with _conn() as conn:
        conn.execute(_SCHEMA)
        _ensure_columns(conn)


def get_session(candidate_id: str) -> Optional[dict]:
    with _conn() as conn:
        conn.execute(_SCHEMA)
        _ensure_columns(conn)
        row = conn.execute(
            """
            SELECT candidate_id, stage, resume, turns,
                   conversation_hash, resume_hash, resume_score, updated_at
            FROM sessions WHERE candidate_id = ?
            """,
            (candidate_id,),
        ).fetchone()
        return dict(row) if row else None


def upsert_session(
    candidate_id: str,
    stage: str,
    resume: str,
    turns: int,
    *,
    conversation_hash: str = "",
    resume_hash: str = "",
    resume_score: int | None = None,
) -> None:
    with _conn() as conn:
        _ensure_columns(conn)
        conn.execute(
            """
            INSERT INTO sessions (
                candidate_id, stage, resume, turns,
                conversation_hash, resume_hash, resume_score, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(candidate_id) DO UPDATE SET
                stage             = excluded.stage,
                resume            = excluded.resume,
                turns             = excluded.turns,
                conversation_hash = excluded.conversation_hash,
                resume_hash       = excluded.resume_hash,
                resume_score      = excluded.resume_score,
                updated_at        = excluded.updated_at
            """,
            (
                candidate_id,
                stage,
                resume,
                turns,
                conversation_hash,
                resume_hash,
                resume_score,
            ),
        )


def update_conversation_hash(candidate_id: str, conversation_hash: str) -> None:
    with _conn() as conn:
        _ensure_columns(conn)
        conn.execute(
            """
            UPDATE sessions
            SET conversation_hash = ?, updated_at = datetime('now')
            WHERE candidate_id = ?
            """,
            (conversation_hash, candidate_id),
        )


def reset_session(candidate_id: str) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "DELETE FROM sessions WHERE candidate_id = ?", (candidate_id,)
        )
        return cur.rowcount > 0


def get_or_default(candidate_id: str) -> dict:
    return get_session(candidate_id) or {
        "candidate_id": candidate_id,
        "stage": DEFAULT_STAGE,
        "resume": "",
        "turns": 0,
        "conversation_hash": "",
        "resume_hash": "",
        "resume_score": None,
        "updated_at": None,
    }
