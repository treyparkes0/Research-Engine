"""Same-event clustering: join real matches, keep parallel headlines apart."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from research_intel.process.cluster import ArticleRef, TopicCluster, cluster_articles
from research_intel.process.text import same_story, tokenize


def _article(article_id: int, source_id: int, title: str, *, hours_ago: float = 1) -> ArticleRef:
    when = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    return ArticleRef(
        id=article_id,
        source_id=source_id,
        title=title,
        published_at=when,
        fetched_at=when,
        domain="world",
        tokens=tokenize(title),
        summary="A publisher blurb long enough to count as source text for this headline. " * 2,
    )


class SameStoryTests(unittest.TestCase):
    def test_same_event_from_different_publishers(self) -> None:
        left = "Nvidia launches investigation into CEO's affair with suspected Chinese spy"
        right = "US chipmaker Nvidia investigates CEO Jensen Huang over affair"
        self.assertTrue(same_story(left, right))
        clusters = cluster_articles([_article(1, 1, left), _article(2, 2, right, hours_ago=3)])
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0].source_count(), 2)
        self.assertEqual(clusters[0].label(), left)

    def test_parallel_headlines_stay_separate(self) -> None:
        fed = "Fed holds interest rates steady"
        ecb = "ECB holds interest rates steady"
        self.assertFalse(same_story(fed, ecb))
        clusters = cluster_articles([_article(1, 1, fed), _article(2, 2, ecb)])
        self.assertEqual(len(clusters), 2)

    def test_same_company_different_events_stay_separate(self) -> None:
        earnings = "Apple earnings beat estimates on iPhone demand"
        store = "Apple opens a new store in Chicago"
        self.assertFalse(same_story(earnings, store))
        self.assertEqual(len(cluster_articles([_article(1, 1, earnings), _article(2, 2, store)])), 2)

    def test_different_chambers_are_not_one_bill_story(self) -> None:
        senate = "Senate passes spending bill before the Friday deadline"
        house = "House passes spending bill before the Friday deadline"
        self.assertFalse(same_story(senate, house))

    def test_shared_person_is_not_enough(self) -> None:
        iran = "Trump says renewed Iran strikes are unlikely if talks progress"
        probe = "Democrats amp up Trump investigation threats against the White House"
        self.assertFalse(same_story(iran, probe))

    def test_dana_white_wording_is_one_story(self) -> None:
        left = "Why Trump joked about having Dana White as his White House press secretary"
        right = "Trump offers press secretary role to White; UFC boss to meet with president"
        self.assertTrue(same_story(left, right))

    def test_malformed_timestamp_does_not_look_fresh(self) -> None:
        article = _article(1, 1, "Port strike delays shipments")
        broken = ArticleRef(
            id=2,
            source_id=1,
            title=article.title,
            published_at="not-a-date",
            fetched_at="also-bad",
            domain="business",
            tokens=article.tokens,
        )
        self.assertEqual(broken.when().year, 1)

    def test_empty_titles_do_not_form_a_cluster(self) -> None:
        blank = ArticleRef(
            id=1,
            source_id=1,
            title="!!!",
            published_at=None,
            fetched_at="2026-11-17T00:00:00+00:00",
            domain="world",
            tokens=tokenize("!!!"),
        )
        self.assertEqual(cluster_articles([blank]), [])
        cluster = TopicCluster()
        self.assertEqual(cluster.article_count(), 0)


if __name__ == "__main__":
    unittest.main()
