"""SQLite 会话状态存储。

单表 sessions, 按 candidate_id 跟踪招聘阶段 (stage) 与最近一份简历快照。
对话历史本身由 RPA 每轮抓取传入, 不在此持久化。
"""
import sqlite3
from contextlib import contextmanager
from typing import Optional

from app.config import settings
from app.schemas import DEFAULT_STAGE


@contextmanager
def _conn():
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                candidate_id TEXT PRIMARY KEY,
                stage        TEXT NOT NULL DEFAULT '初步接触',
                resume       TEXT NOT NULL DEFAULT '',
                turns        INTEGER NOT NULL DEFAULT 0,
                updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )


def get_session(candidate_id: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT candidate_id, stage, resume, turns, updated_at FROM sessions WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
        return dict(row) if row else None


def upsert_session(candidate_id: str, stage: str, resume: str, turns: int) -> None:
    """写入或更新会话状态。"""
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO sessions (candidate_id, stage, resume, turns, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(candidate_id) DO UPDATE SET
                stage      = excluded.stage,
                resume     = excluded.resume,
                turns      = excluded.turns,
                updated_at = excluded.updated_at
            """,
            (candidate_id, stage, resume, turns),
        )


def reset_session(candidate_id: str) -> bool:
    """删除某候选人的会话状态, 返回是否删到了记录。"""
    with _conn() as conn:
        cur = conn.execute(
            "DELETE FROM sessions WHERE candidate_id = ?", (candidate_id,)
        )
        return cur.rowcount > 0


def get_or_default(candidate_id: str) -> dict:
    """读取会话, 不存在则返回默认值 (不落库)。"""
    return get_session(candidate_id) or {
        "candidate_id": candidate_id,
        "stage": DEFAULT_STAGE,
        "resume": "",
        "turns": 0,
        "updated_at": None,
    }
