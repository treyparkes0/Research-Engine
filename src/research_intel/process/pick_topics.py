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
from research_intel.process.text import jaccard, tokenize


def _cutoff_iso(hours: int = TOPIC_LOOKBACK_HOURS) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def load_recent_articles(
    conn: sqlite3.Connection,
    domain: str,
    hours: int = TOPIC_LOOKBACK_HOURS,
) -> list[ArticleRef]:
    cutoff = _cutoff_iso(hours)
    # Movies: TMDB release dates are calendar dates; use fetched_at so this week's
    # slate stays visible after ingest refreshes.
    if domain == "movies":
        rows = conn.execute(
            """
            SELECT a.id, a.source_id, a.title, a.published_at, a.fetched_at, a.domain
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
            SELECT a.id, a.source_id, a.title, a.published_at, a.fetched_at, a.domain
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


def _drop_cross_domain_duplicates(conn: sqlite3.Connection) -> None:
    """One Heathrow story should not lead both markets and business."""
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
        tokens = tokenize(row["label"])
        if any(jaccard(tokens, tokenize(other["label"])) >= 0.42 for other in kept):
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
            tokens = tokenize(cand["label"])
            if any(jaccard(tokens, tokenize(other["label"])) >= 0.42 for other in kept):
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
            ORDER BY score DESC, id
            """,
            (domain,),
        ).fetchall()
        for rank, row in enumerate(selected, start=1):
            conn.execute(
                "UPDATE topics SET selected_rank = ? WHERE id = ?",
                (rank, row["id"]),
            )
