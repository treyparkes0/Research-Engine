"""Delete old articles, old brief rows, and old brief files.

Feed times are ISO-8601. SQLite's own defaults look like 'YYYY-MM-DD HH:MM:SS'.
Comparisons use the first 19 characters of a normalized stamp so both formats
sort the same way.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_intel.config import (
    ARTICLE_KEEP_DAYS,
    BRIEF_FILES_KEEP,
    BRIEF_KEEP_DAYS,
    briefs_dir,
)


def comparable_stamp(raw: str | None) -> str:
    """Normalize ISO-8601 and SQLite datetime strings to 'YYYY-MM-DD HH:MM:SS'."""
    text = (raw or "").strip().replace("T", " ").replace("Z", "")
    text = text.replace("+00:00", "")
    return text[:19]


def cleanup_storage(
    conn: sqlite3.Connection,
    *,
    article_keep_days: int = ARTICLE_KEEP_DAYS,
    brief_keep_days: int = BRIEF_KEEP_DAYS,
    brief_files_keep: int = BRIEF_FILES_KEEP,
    briefs_directory: Path | None = None,
) -> dict[str, int]:
    """Prune the database and the brief folder. Returns how many rows and files were removed."""
    now = datetime.now(timezone.utc)
    article_cutoff = comparable_stamp((now - timedelta(days=article_keep_days)).isoformat())
    brief_cutoff = comparable_stamp((now - timedelta(days=brief_keep_days)).isoformat())
    article_when = (
        "substr(replace(replace(replace(COALESCE(published_at, fetched_at), 'T', ' '), 'Z', ''), '+00:00', ''), 1, 19)"
    )
    brief_when = "substr(replace(replace(replace(created_at, 'T', ' '), 'Z', ''), '+00:00', ''), 1, 19)"
    topic_when = (
        "substr(replace(replace(replace(COALESCE(as_of, last_seen, first_seen), 'T', ' '), 'Z', ''), '+00:00', ''), 1, 19)"
    )

    # Remove old article links first, then articles.
    conn.execute(
        f"""
        DELETE FROM article_topics
        WHERE article_id IN (
            SELECT id FROM articles
            WHERE {article_when} < ?
        )
        """,
        (article_cutoff,),
    )
    conn.execute(
        f"""
        DELETE FROM article_entities
        WHERE article_id IN (
            SELECT id FROM articles
            WHERE {article_when} < ?
        )
        """,
        (article_cutoff,),
    )
    articles_deleted = conn.execute(
        f"""
        DELETE FROM articles
        WHERE {article_when} < ?
        """,
        (article_cutoff,),
    ).rowcount

    # Old briefs cascade to topic_cards / monitor_list via FK.
    briefs_deleted = conn.execute(
        f"""
        DELETE FROM briefs
        WHERE {brief_when} < ?
        """,
        (brief_cutoff,),
    ).rowcount

    # Archive-only topics that are old and unused.
    topics_deleted = conn.execute(
        f"""
        DELETE FROM topics
        WHERE status = 'archived'
          AND {topic_when} < ?
        """,
        (brief_cutoff,),
    ).rowcount

    files_deleted = _prune_brief_files(briefs_directory or briefs_dir(), keep=brief_files_keep)
    conn.commit()
    return {
        "articles_deleted": max(articles_deleted, 0),
        "briefs_deleted": max(briefs_deleted, 0),
        "topics_deleted": max(topics_deleted, 0),
        "files_deleted": files_deleted,
    }


def _prune_brief_files(directory: Path, keep: int) -> int:
    """Keep the newest Markdown files and the newest JSON files. Delete the rest."""
    if not directory.exists():
        return 0
    deleted = 0
    for pattern in ("*.md", "*.json"):
        files = sorted(
            directory.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for path in files[keep:]:
            path.unlink(missing_ok=True)
            deleted += 1
    return deleted
