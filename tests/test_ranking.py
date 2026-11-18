"""Ranking uses independent publishers, not duplicate rows from one feed."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from research_intel.db import connect, init_db
from research_intel.process.cluster import ArticleRef, TopicCluster
from research_intel.process.pick_topics import _drop_cross_domain_duplicates
from research_intel.process.rank import score_cluster
from research_intel.process.text import tokenize
import tempfile
from pathlib import Path


NOW = datetime(2026, 11, 17, 15, tzinfo=timezone.utc)
BLURB = (
    "Dockworkers walked out at the harbor before dawn and shippers said containers "
    "will miss this week's departures."
)


def _article(
    article_id: int,
    source_id: int,
    title: str,
    *,
    summary: str = BLURB,
    hours_ago: float = 2,
) -> ArticleRef:
    when = (NOW - timedelta(hours=hours_ago)).isoformat()
    return ArticleRef(
        id=article_id,
        source_id=source_id,
        title=title,
        published_at=when,
        fetched_at=when,
        domain="business",
        tokens=tokenize(title),
        summary=summary,
    )


def _cluster(*articles: ArticleRef) -> TopicCluster:
    cluster = TopicCluster()
    for article in articles:
        cluster.add(article)
    return cluster


class RankingTests(unittest.TestCase):
    def test_duplicate_rows_from_one_publisher_do_not_raise_the_score(self) -> None:
        title = "Port strike delays shipments at major harbors"
        one = _cluster(_article(1, 10, title))
        copies = _cluster(
            _article(1, 10, title),
            _article(2, 10, title, hours_ago=2),
            _article(3, 10, title, hours_ago=2),
        )
        self.assertEqual(score_cluster(one, NOW, domain="business"), score_cluster(copies, NOW, domain="business"))

    def test_two_publishers_outrank_one_publisher_with_extra_copies(self) -> None:
        title = "Port strike delays shipments at major harbors"
        other = "Harbor backlog grows as the port strike delays shipments"
        single = _cluster(_article(1, 10, title), _article(2, 10, title))
        multi = _cluster(_article(1, 10, title), _article(2, 20, other))
        self.assertGreater(
            score_cluster(multi, NOW, domain="business"),
            score_cluster(single, NOW, domain="business"),
        )

    def test_a_real_blurb_outranks_a_headline_only_cluster(self) -> None:
        title = "Port strike delays shipments at major harbors"
        thin = _cluster(_article(1, 10, title, summary=""))
        full = _cluster(_article(1, 10, title, summary=BLURB))
        self.assertGreater(
            score_cluster(full, NOW, domain="business"),
            score_cluster(thin, NOW, domain="business"),
        )

    def test_old_copy_loses_to_a_fresh_one(self) -> None:
        title = "Port strike delays shipments at major harbors"
        fresh = _cluster(_article(1, 10, title, hours_ago=1))
        stale = _cluster(_article(1, 10, title, hours_ago=40))
        self.assertGreater(
            score_cluster(fresh, NOW, domain="business"),
            score_cluster(stale, NOW, domain="business"),
        )

    def test_same_story_is_not_selected_in_two_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = init_db(connect(Path(tmp) / "rank.db"))
            rows = [
                (1, "Nvidia launches investigation into CEO's affair with suspected Chinese spy", "business", 12),
                (2, "US chipmaker Nvidia investigates CEO Jensen Huang over affair", "world", 9),
                (3, "Fed holds interest rates steady", "markets", 8),
                (4, "ECB holds interest rates steady", "markets", 7),
            ]
            for topic_id, label, domain, score in rows:
                conn.execute(
                    """
                    INSERT INTO topics (id, label, domain, status, score, selected_rank, as_of)
                    VALUES (?, ?, ?, 'selected', ?, 1, ?)
                    """,
                    (topic_id, label, domain, score, NOW.isoformat()),
                )
            conn.execute(
                """
                INSERT INTO topics (id, label, domain, status, score, as_of)
                VALUES (5, 'Harbor backlog grows after the Oakland port strike', 'world', 'candidate', 4, ?)
                """,
                (NOW.isoformat(),),
            )
            conn.commit()
            _drop_cross_domain_duplicates(conn)
            selected = {
                (row["domain"], row["label"])
                for row in conn.execute("SELECT domain, label FROM topics WHERE status = 'selected'")
            }
            nvidia = [label for domain, label in selected if "Nvidia" in label or "nvidia" in label]
            self.assertEqual(len(nvidia), 1)
            fed = [label for _, label in selected if label.startswith("Fed")]
            ecb = [label for _, label in selected if label.startswith("ECB")]
            self.assertEqual(len(fed), 1)
            self.assertEqual(len(ecb), 1)
            conn.close()


if __name__ == "__main__":
    unittest.main()
