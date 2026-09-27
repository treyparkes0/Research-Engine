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


def cleanup_storage(
    conn: sqlite3.Connection,
    *,
    article_keep_days: int = ARTICLE_KEEP_DAYS,
    brief_keep_days: int = BRIEF_KEEP_DAYS,
    brief_files_keep: int = BRIEF_FILES_KEEP,
) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    article_cutoff = (now - timedelta(days=article_keep_days)).isoformat()
    brief_cutoff = (now - timedelta(days=brief_keep_days)).isoformat()

    # Remove old article links first, then articles.
    conn.execute(
        """
        DELETE FROM article_topics
        WHERE article_id IN (
            SELECT id FROM articles
            WHERE COALESCE(published_at, fetched_at) < ?
        )
        """,
        (article_cutoff,),
    )
    conn.execute(
        """
        DELETE FROM article_entities
        WHERE article_id IN (
            SELECT id FROM articles
            WHERE COALESCE(published_at, fetched_at) < ?
        )
        """,
        (article_cutoff,),
    )
    articles_deleted = conn.execute(
        """
        DELETE FROM articles
        WHERE COALESCE(published_at, fetched_at) < ?
        """,
        (article_cutoff,),
    ).rowcount

    # Old briefs cascade to topic_cards / monitor_list via FK.
    briefs_deleted = conn.execute(
        """
        DELETE FROM briefs
        WHERE created_at < ?
        """,
        (brief_cutoff,),
    ).rowcount

    # Archive-only topics that are old and unused.
    topics_deleted = conn.execute(
        """
        DELETE FROM topics
        WHERE status = 'archived'
          AND COALESCE(as_of, last_seen, first_seen) < ?
        """,
        (brief_cutoff,),
    ).rowcount

    files_deleted = _prune_brief_files(briefs_dir(), keep=brief_files_keep)
    conn.commit()
    return {
        "articles_deleted": max(articles_deleted, 0),
        "briefs_deleted": max(briefs_deleted, 0),
        "topics_deleted": max(topics_deleted, 0),
        "files_deleted": files_deleted,
    }


def _prune_brief_files(directory: Path, keep: int) -> int:
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
