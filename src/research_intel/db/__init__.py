from __future__ import annotations

import sqlite3
from pathlib import Path

from research_intel.config import SEED_THEMES, database_path

_TOPIC_COLUMNS = {
    "score": "REAL NOT NULL DEFAULT 0",
    "article_count": "INTEGER NOT NULL DEFAULT 0",
    "source_count": "INTEGER NOT NULL DEFAULT 0",
    "selected_rank": "INTEGER",
    "as_of": "TEXT",
}


def _schema_path() -> Path:
    return Path(__file__).with_name("schema.sql")


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection | None = None) -> sqlite3.Connection:
    conn = conn or connect()
    schema = _schema_path().read_text(encoding="utf-8")
    conn.executescript(schema)
    _migrate(conn)
    _seed_themes(conn)
    conn.commit()
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(topics)").fetchall()
    }
    for name, ddl in _TOPIC_COLUMNS.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE topics ADD COLUMN {name} {ddl}")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_topics_domain_rank "
        "ON topics(domain, selected_rank)"
    )
    _migrate_sources_domain_check(conn)


def _migrate_sources_domain_check(conn: sqlite3.Connection) -> None:
    """Recreate sources table so domain CHECK allows 'movies'."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='sources'"
    ).fetchone()
    if not row or not row["sql"]:
        return
    if "'movies'" in row["sql"]:
        # Clean up any leftover partial migration artifact.
        conn.execute("DROP TABLE IF EXISTS sources_new")
        return

    # FK children (articles) block DROP TABLE while foreign_keys is ON.
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("DROP TABLE IF EXISTS sources_new")
        conn.executescript(
            """
            CREATE TABLE sources_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                domain TEXT NOT NULL CHECK (
                    domain IN ('markets', 'business', 'world', 'sports', 'movies')
                ),
                feed_url TEXT NOT NULL UNIQUE,
                homepage_url TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            INSERT INTO sources_new
                (id, name, domain, feed_url, homepage_url, active, created_at)
            SELECT id, name, domain, feed_url, homepage_url, active, created_at
            FROM sources;
            DROP TABLE sources;
            ALTER TABLE sources_new RENAME TO sources;
            """
        )
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _seed_themes(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO themes (name, status) VALUES (?, 'core')",
        [(name,) for name in SEED_THEMES],
    )
