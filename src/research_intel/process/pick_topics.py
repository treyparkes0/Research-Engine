"""Load recent articles, cluster them, rank them, and save the result.

Each run archives the previous topic rows, writes a fresh set, then drops a
story that was selected more than once (including across sections). Movies use
a wider window because release dates are not the same as fetch time.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from research_intel.config import (
    DOMAINS,
    TOPIC_LOOKBACK_HOURS,
    TOPIC_SIMILARITY_THRESHOLD,
    TOPICS_PER_DOMAIN,
)
from research_intel.process.cluster import ArticleRef, cluster_articles
from research_intel.process.rank import RankedTopic, rank_and_select
from research_intel.process.text import same_story


def _cutoff_iso(hours: int = TOPIC_LOOKBACK_HOURS) -> str:
    """UTC timestamp for 'this many hours ago', used as the SQL cutoff."""
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def load_recent_articles(
    conn: sqlite3.Connection,
    domain: str,
    hours: int = TOPIC_LOOKBACK_HOURS,
) -> list[ArticleRef]:
    """Articles new enough to rank. Movies use fetch time; other sections use publish time."""
    cutoff = _cutoff_iso(hours)
    # Movies: TMDB release dates are calendar dates; use fetched_at so this week's
    # slate stays visible after ingest refreshes.
    if domain == "movies":
        rows = conn.execute(
            """
            SELECT a.id, a.source_id, a.title, a.summary, a.published_at, a.fetched_at, a.domain
            FROM articles a
            JOIN sources s ON s.id = a.source_id
            WHERE a.domain = ?
              AND s.active = 1
              AND a.fetched_at >= ?
            ORDER BY a.fetched_at DESC
            """,
            (domain, cutoff),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT a.id, a.source_id, a.title, a.summary, a.published_at, a.fetched_at, a.domain
            FROM articles a
            JOIN sources s ON s.id = a.source_id
            WHERE a.domain = ?
              AND s.active = 1
              AND COALESCE(a.published_at, a.fetched_at) >= ?
            ORDER BY COALESCE(a.published_at, a.fetched_at) DESC
            """,
            (domain, cutoff),
        ).fetchall()
    return [ArticleRef.from_row(row) for row in rows]


def archive_previous_topics(conn: sqlite3.Connection, domain: str | None = None) -> None:
    """Mark the last picker run as archived so this run starts clean."""
    if domain:
        conn.execute(
            """
            UPDATE topics
            SET status = 'archived'
            WHERE domain = ?
              AND status IN ('active', 'selected', 'candidate')
            """,
            (domain,),
        )
    else:
        conn.execute(
            """
            UPDATE topics
            SET status = 'archived'
            WHERE status IN ('active', 'selected', 'candidate')
            """
        )


def save_ranked_topics(
    conn: sqlite3.Connection,
    domain: str,
    ranked: list[RankedTopic],
    as_of: str,
) -> list[int]:
    """Write clusters to the topics table and link each article to its topic."""
    topic_ids: list[int] = []
    for item in ranked:
        cluster = item.cluster
        status = "selected" if item.selected_rank is not None else "candidate"
        cursor = conn.execute(
            """
            INSERT INTO topics (
                label, domain, first_seen, last_seen, status,
                score, article_count, source_count, selected_rank, as_of
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cluster.label(),
                domain,
                cluster.first_seen(),
                cluster.last_seen(),
                status,
                item.score,
                cluster.article_count(),
                cluster.source_count(),
                item.selected_rank,
                as_of,
            ),
        )
        topic_id = int(cursor.lastrowid)
        topic_ids.append(topic_id)
        for article in cluster.articles:
            conn.execute(
                """
                INSERT OR REPLACE INTO article_topics (article_id, topic_id, score)
                VALUES (?, ?, ?)
                """,
                (article.id, topic_id, item.score),
            )
    return topic_ids


def pick_topics_for_domain(
    conn: sqlite3.Connection,
    domain: str,
    limit: int = TOPICS_PER_DOMAIN,
    hours: int = TOPIC_LOOKBACK_HOURS,
    threshold: float = TOPIC_SIMILARITY_THRESHOLD,
) -> list[RankedTopic]:
    """Cluster and rank one section. Movies need a closer title match so different films do not merge."""
    # Movies need a wider window so this-week releases and reviews stay in play.
    if domain == "movies" and hours == TOPIC_LOOKBACK_HOURS:
        hours = max(hours, 168)
    articles = load_recent_articles(conn, domain, hours=hours)
    # TMDB titles share "[Now Playing]" tokens — require near-duplicate titles to merge.
    movie_threshold = max(threshold, 0.72) if domain == "movies" else threshold
    clusters = cluster_articles(articles, threshold=movie_threshold)
    return rank_and_select(clusters, limit=limit, domain=domain)


def run_topic_picker(
    conn: sqlite3.Connection,
    domains: tuple[str, ...] = DOMAINS,
    limit: int = TOPICS_PER_DOMAIN,
    hours: int = TOPIC_LOOKBACK_HOURS,
) -> dict[str, list[RankedTopic]]:
    """Rebuild topics for every domain and remove a story that was selected twice."""
    as_of = datetime.now(timezone.utc).isoformat()
    archive_previous_topics(conn)
    results: dict[str, list[RankedTopic]] = {}

    for domain in domains:
        ranked = pick_topics_for_domain(conn, domain, limit=limit, hours=hours)
        save_ranked_topics(conn, domain, ranked, as_of=as_of)
        results[domain] = ranked
        selected = sum(1 for r in ranked if r.selected_rank is not None)
        print(
            f"[{domain}] {len(ranked)} topics from recent articles "
            f"-> top {selected} selected"
        )

    _drop_cross_domain_duplicates(conn)
    conn.commit()
    return results


def _same_selected_story(label: str, other_label: str) -> bool:
    """True when two selected headlines are the same event and one of them should be dropped."""
    return same_story(label, other_label)


def _drop_cross_domain_duplicates(conn: sqlite3.Connection) -> None:
    """One event should not be selected twice, including across sections."""
    rows = conn.execute(
        """
        SELECT id, label, domain, score
        FROM topics
        WHERE status = 'selected'
        ORDER BY score DESC, id
        """
    ).fetchall()
    kept: list[sqlite3.Row] = []
    dropped_domains: list[str] = []
    for row in rows:
        if any(_same_selected_story(row["label"], other["label"]) for other in kept):
            conn.execute(
                """
                UPDATE topics
                SET status = 'archived', selected_rank = NULL
                WHERE id = ?
                """,
                (row["id"],),
            )
            dropped_domains.append(row["domain"])
        else:
            kept.append(row)

    for domain in dropped_domains:
        candidates = conn.execute(
            """
            SELECT id, label, score
            FROM topics
            WHERE status = 'candidate' AND domain = ?
            ORDER BY score DESC, id
            """,
            (domain,),
        ).fetchall()
        for cand in candidates:
            if any(_same_selected_story(cand["label"], other["label"]) for other in kept):
                continue
            conn.execute(
                "UPDATE topics SET status = 'selected' WHERE id = ?",
                (cand["id"],),
            )
            kept.append(cand)
            break

    for domain in DOMAINS:
        selected = conn.execute(
            """
            SELECT id FROM topics
            WHERE status = 'selected' AND domain = ?
            ORDER BY selected_rank IS NULL, selected_rank, score DESC, id
            """,
            (domain,),
        ).fetchall()
        for rank, row in enumerate(selected, start=1):
            conn.execute(
                "UPDATE topics SET selected_rank = ? WHERE id = ?",
                (rank, row["id"]),
            )
