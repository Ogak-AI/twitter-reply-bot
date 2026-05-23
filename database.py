import sqlite3
from pathlib import Path

DB_PATH = Path("data/bot.db")


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            title TEXT,
            source TEXT,
            tweet TEXT,
            status TEXT,
            buffer_post_id TEXT,
            error TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def is_seen(url):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT 1 FROM posts WHERE url = ? LIMIT 1", (url,))
    seen = cursor.fetchone() is not None
    conn.close()
    return seen


def get_stats():
    conn = sqlite3.connect(DB_PATH)
    posted = conn.execute("SELECT COUNT(*) FROM posts WHERE status = 'posted'").fetchone()[0]
    failed = conn.execute("SELECT COUNT(*) FROM posts WHERE status = 'failed'").fetchone()[0]
    conn.close()
    return {"posted": posted, "failed": failed}


def mark_seen(url, title, source):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO posts (url, title, source, status) VALUES (?, ?, ?, ?)",
        (url, title, source, "seen"),
    )
    conn.commit()
    conn.close()


def save_post(url, tweet):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "INSERT OR REPLACE INTO posts (url, tweet, status) VALUES (?, ?, ?)",
        (url, tweet, "pending"),
    )
    conn.commit()
    post_id = cursor.lastrowid
    conn.close()
    return post_id


def update_post(post_id, status, buffer_post_id=None, error=None):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE posts SET status = ?, buffer_post_id = ?, error = ? WHERE id = ?",
        (status, buffer_post_id, error, post_id),
    )
    conn.commit()
    conn.close()


from datetime import datetime

def get_posts_count_last_24h() -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT COUNT(*) FROM posts WHERE status = 'posted' AND created_at > datetime('now', '-24 hours')"
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_last_posted_time() -> datetime | None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT created_at FROM posts WHERE status = 'posted' ORDER BY created_at DESC LIMIT 1"
    )
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        try:
            ts_str = row[0].replace("T", " ")
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(ts_str, fmt)
                except ValueError:
                    continue
        except Exception:
            pass
    return None


def get_last_rate_limit_failure() -> datetime | None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        """
        SELECT created_at FROM posts 
        WHERE status = 'failed' 
          AND (error LIKE '%RATE_LIMIT_EXCEEDED%' OR error LIKE '%Too many requests%')
        ORDER BY created_at DESC LIMIT 1
        """
    )
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        try:
            ts_str = row[0].replace("T", " ")
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(ts_str, fmt)
                except ValueError:
                    continue
        except Exception:
            pass
    return None
