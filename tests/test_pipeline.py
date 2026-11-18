"""Ingest edges, retention, and email rendering with missing fields."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from research_intel.config import Feed
from research_intel.db import connect, init_db
from research_intel.deliver.html_email import render_html
from research_intel.generate.render import render_markdown
from research_intel.generate.template_writer import BriefClosing, ResearchBrief, SourceLink, TopicCard
from research_intel.ingest.feeds import ingest_feed, prepare_article
from research_intel.process.cleanup import cleanup_storage


def _empty_card(**overrides) -> TopicCard:
    card = TopicCard(
        topic_id=1,
        domain="world",
        rank=1,
        title="Harbor backlog grows after the port strike",
        executive_summary="",
        why_it_matters="",
        key_takeaways=[],
        research_snapshot="",
        further_research=[],
        definitions=[],
        sources=[],
        related_tickers=[],
        themes=[],
    )
    for key, value in overrides.items():
        setattr(card, key, value)
    return card


def _brief(card: TopicCard) -> ResearchBrief:
    return ResearchBrief(
        brief_type="evening",
        created_at="2026-11-17T20:00:00+00:00",
        cards_by_domain={
            "markets": [],
            "business": [],
            "world": [card],
            "sports": [],
            "movies": [],
        },
        closing=BriefClosing(
            article_title=card.title,
            article_domain=card.domain,
            why_learn="Widest coverage in this brief.",
            source_url="",
            source_name="",
            definitions=[],
            emerging_trend="today's coverage",
            topics_to_monitor=[],
        ),
        watchlist_quotes=[],
    )


class IngestEdgeTests(unittest.TestCase):
    def test_malformed_entries_and_an_empty_feed(self) -> None:
        feed = Feed("Example World", "world", "https://example.com/rss.xml", "https://example.com")
        self.assertIsNone(prepare_article(feed, {"title": "", "link": "https://example.com/a"}))
        self.assertIsNone(prepare_article(feed, {"title": "Missing link", "link": ""}))
        kept = prepare_article(
            feed,
            {
                "title": "Port strike delays shipments",
                "link": "https://example.com/port",
                "summary": "",
                "published": "not-a-date",
            },
        )
        self.assertIsNotNone(kept)
        assert kept is not None
        self.assertEqual(kept["summary"], "")
        self.assertIsNone(kept["published_at"])
        self.assertTrue(kept["url"].startswith("https://"))

        with tempfile.TemporaryDirectory() as tmp:
            conn = init_db(connect(Path(tmp) / "ingest.db"))
            conn.execute(
                """
                INSERT INTO sources (name, domain, feed_url, active)
                VALUES ('Example World', 'world', 'https://example.com/rss.xml', 1)
                """
            )
            source_id = int(conn.execute("SELECT id FROM sources").fetchone()["id"])
            conn.commit()
            empty = SimpleNamespace(entries=[])
            with patch("research_intel.ingest.feeds.fetch_feed", return_value=empty):
                new_count, seen_count = ingest_feed(conn, feed, source_id)
            self.assertEqual((new_count, seen_count), (0, 0))
            malformed = SimpleNamespace(
                entries=[
                    {"title": "", "link": "https://example.com/a"},
                    {"title": "No link here", "link": ""},
                    {
                        "title": "Port strike delays shipments",
                        "link": "https://example.com/port",
                        "summary": "",
                        "published": "not-a-date",
                    },
                ]
            )
            with patch("research_intel.ingest.feeds.fetch_feed", return_value=malformed):
                new_count, seen_count = ingest_feed(conn, feed, source_id)
            self.assertEqual(seen_count, 1)
            self.assertEqual(new_count, 1)
            row = conn.execute("SELECT summary, published_at, url FROM articles").fetchone()
            self.assertEqual(row["summary"], "")
            self.assertIsNone(row["published_at"])
            self.assertEqual(row["url"], "https://example.com/port")
            conn.close()

    def test_betting_url_is_not_stored(self) -> None:
        feed = Feed("CBS NFL", "sports", "https://www.cbssports.com/rss/headlines/nfl/", "https://www.cbssports.com/nfl")
        dropped = prepare_article(
            feed,
            {
                "title": "Bears versus Buccaneers preview",
                "link": "https://www.cbssports.com/betting/news/bears-preview/",
                "summary": "A look at the Sunday night matchup.",
            },
        )
        self.assertIsNone(dropped)
        kept = prepare_article(
            feed,
            {
                "title": "Star quarterback listed as questionable with an ankle injury",
                "link": "https://www.cbssports.com/nfl/news/quarterback-injury/",
                "summary": "The team called him questionable for Sunday.",
            },
        )
        self.assertIsNotNone(kept)


class RetentionTests(unittest.TestCase):
    def test_old_rows_go_and_recent_rows_stay_across_timestamp_formats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            conn = init_db(connect(root / "retain.db"))
            conn.execute(
                "INSERT INTO sources (name, domain, feed_url) VALUES ('BBC', 'world', 'https://example.com/rss')"
            )
            source_id = int(conn.execute("SELECT id FROM sources").fetchone()["id"])
            conn.execute(
                """
                INSERT INTO articles (source_id, url, title, summary, published_at, domain)
                VALUES (?, 'https://example.com/old-iso', 'Old ISO', 'stale', '2020-01-01T00:00:00+00:00', 'world')
                """,
                (source_id,),
            )
            conn.execute(
                """
                INSERT INTO articles (source_id, url, title, summary, published_at, fetched_at, domain)
                VALUES (?, 'https://example.com/old-sql', 'Old SQL', 'stale', NULL, '2020-01-02 00:00:00', 'world')
                """,
                (source_id,),
            )
            conn.execute(
                """
                INSERT INTO articles (source_id, url, title, summary, published_at, domain)
                VALUES (?, 'https://example.com/new', 'New', 'fresh', '2026-11-16T12:00:00+00:00', 'world')
                """,
                (source_id,),
            )
            conn.execute(
                """
                INSERT INTO briefs (brief_type, created_at, payload_json)
                VALUES ('evening', '2020-01-01 00:00:00', '{}')
                """
            )
            conn.execute(
                """
                INSERT INTO briefs (brief_type, created_at, payload_json)
                VALUES ('morning', '2026-11-16T12:00:00+00:00', '{}')
                """
            )
            briefs = root / "briefs"
            briefs.mkdir()
            for index in range(6):
                path = briefs / f"evening_old_{index}.md"
                path.write_text("brief", encoding="utf-8")
            cleaned = cleanup_storage(
                conn,
                article_keep_days=21,
                brief_keep_days=90,
                brief_files_keep=4,
                briefs_directory=briefs,
            )
            urls = {row["url"] for row in conn.execute("SELECT url FROM articles")}
            self.assertEqual(urls, {"https://example.com/new"})
            self.assertGreaterEqual(cleaned["articles_deleted"], 2)
            brief_types = {row["brief_type"] for row in conn.execute("SELECT brief_type FROM briefs")}
            self.assertEqual(brief_types, {"morning"})
            self.assertEqual(len(list(briefs.glob("*.md"))), 4)
            conn.close()


class EmailRenderTests(unittest.TestCase):
    def test_missing_optional_fields_still_render(self) -> None:
        card = _empty_card(
            sources=[
                SourceLink(
                    title="Harbor backlog grows after the port strike",
                    url="",
                    source_name="BBC World",
                    summary="",
                    published_at=None,
                )
            ]
        )
        brief = _brief(card)
        markdown = render_markdown(brief)
        html = render_html(brief)
        self.assertIn("What happened", markdown)
        self.assertIn("What happened", html)
        self.assertIn("Executive overview", markdown)
        self.assertIn("Executive overview", html)
        self.assertIn("Harbor backlog", markdown)
        self.assertIn("Harbor backlog", html)
        self.assertIn("link unavailable", markdown)
        self.assertIn("link unavailable", html)
        self.assertNotIn("]()", markdown)
        self.assertNotIn('href=""', html)
        self.assertIn("viewport", html)
        self.assertNotIn("Why it matters", markdown)

    def test_markdown_and_html_share_the_headline(self) -> None:
        card = _empty_card(
            executive_summary="Dockworkers walked out and shippers said containers will miss this week's departures.",
            why_it_matters="Shippers said the backlog will last into next week.",
            sources=[
                SourceLink(
                    title="Harbor backlog grows after the port strike",
                    url="https://example.com/port",
                    source_name="BBC World",
                    summary="Dockworkers walked out.",
                    published_at="2026-11-17T12:00:00+00:00",
                )
            ],
        )
        brief = _brief(card)
        markdown = render_markdown(brief)
        html = render_html(brief)
        self.assertIn("Why it matters", markdown)
        self.assertIn("Why it matters", html)
        self.assertIn("https://example.com/port", markdown)
        self.assertIn("https://example.com/port", html)
        self.assertIn("Read more", markdown)
        self.assertIn("Read more", html)


if __name__ == "__main__":
    unittest.main()
