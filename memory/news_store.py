import json
import logging
import sqlite3
from contextlib import contextmanager

import config

logger = logging.getLogger(__name__)


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS news (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT,
            url TEXT,
            source TEXT,
            published_at TEXT,
            category TEXT,
            tags TEXT,
            run_date TEXT
        );
        CREATE TABLE IF NOT EXISTS runs (
            run_date TEXT PRIMARY KEY,
            collected INTEGER,
            deduped INTEGER,
            critic_score REAL,
            retry_count INTEGER,
            status TEXT
        );
        """
    )
    conn.commit()


@contextmanager
def _connect():
    conn = sqlite3.connect(config.SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    _init_db(conn)
    try:
        yield conn
    finally:
        conn.close()


def save_news(items: list[dict], run_date: str) -> None:
    with _connect() as conn:
        for item in items:
            conn.execute(
                """
                INSERT OR REPLACE INTO news
                (id, title, content, url, source, published_at, category, tags, run_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    item.get("title", ""),
                    item.get("content", ""),
                    item.get("url", ""),
                    item.get("source", ""),
                    item.get("published_at", ""),
                    item.get("category", "unknown"),
                    json.dumps(item.get("tags", []), ensure_ascii=False),
                    run_date,
                ),
            )
        conn.commit()
    logger.info("已保存 %d 条新闻到 SQLite", len(items))


def save_run_meta(
    run_date: str,
    collected: int,
    deduped: int,
    critic_score: float,
    retry_count: int,
    status: str,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO runs
            (run_date, collected, deduped, critic_score, retry_count, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_date, collected, deduped, critic_score, retry_count, status),
        )
        conn.commit()


def get_news_by_date(run_date: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM news WHERE run_date = ? ORDER BY published_at DESC",
            (run_date,),
        ).fetchall()
    items = []
    for row in rows:
        items.append(
            {
                "id": row["id"],
                "title": row["title"],
                "content": row["content"],
                "url": row["url"],
                "source": row["source"],
                "published_at": row["published_at"],
                "category": row["category"],
                "tags": json.loads(row["tags"] or "[]"),
            }
        )
    return items


def get_run_meta(run_date: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM runs WHERE run_date = ?", (run_date,)).fetchone()
    if not row:
        return None
    return {
        "run_date": row["run_date"],
        "collected": row["collected"],
        "deduped": row["deduped"],
        "critic_score": row["critic_score"],
        "retry_count": row["retry_count"],
        "status": row["status"],
    }


def list_run_dates() -> list[str]:
    with _connect() as conn:
        rows = conn.execute("SELECT run_date FROM runs ORDER BY run_date DESC").fetchall()
    return [r["run_date"] for r in rows]
