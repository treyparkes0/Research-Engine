"""Download public RSS and store title, blurb, link, and time.

Each feed is isolated: one failure does not stop the others. Sports and film
filters run before a row is inserted. After the RSS loop, optional TMDB
ingest runs. We never scrape a full article page.
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx

from research_intel.config import DEFAULT_FEEDS, Feed
from research_intel.ingest.tmdb import run_tmdb_ingest
from research_intel.process.sports_focus import is_betting_promo, is_mets_baseball, is_soccer
from research_intel.process.movies_focus import is_film_related, is_foreign_film_blurb


USER_AGENT = "ResearchIntelligenceEngine/0.1 (+personal research bot)"


def ensure_sources(conn: sqlite3.Connection, feeds: tuple[Feed, ...] = DEFAULT_FEEDS) -> dict[str, int]:
    """Insert or update the configured feeds and return feed URL to source id. Feeds removed from config are marked inactive."""
    """Upsert starter feeds and return feed_url -> source_id."""
    mapping: dict[str, int] = {}
    active_urls = {feed.feed_url for feed in feeds}
    for feed in feeds:
        conn.execute(
            """
            INSERT INTO sources (name, domain, feed_url, homepage_url, active)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(feed_url) DO UPDATE SET
                name = excluded.name,
                domain = excluded.domain,
                homepage_url = excluded.homepage_url,
                active = 1
            """,
            (feed.name, feed.domain, feed.feed_url, feed.homepage_url or None),
        )
        row = conn.execute(
            "SELECT id FROM sources WHERE feed_url = ?",
            (feed.feed_url,),
        ).fetchone()
        source_id = int(row["id"])
        mapping[feed.feed_url] = source_id
        conn.execute(
            """
            UPDATE articles
            SET domain = ?
            WHERE source_id = ? AND domain != ?
            """,
            (feed.domain, source_id, feed.domain),
        )

    if active_urls:
        placeholders = ",".join("?" for _ in active_urls)
        # Retire feeds removed from config; keep synthetic sources (TMDB).
        conn.execute(
            f"""
            UPDATE sources
            SET active = 0
            WHERE feed_url NOT IN ({placeholders})
              AND feed_url NOT LIKE 'tmdb:%'
            """,
            tuple(active_urls),
        )
    conn.commit()
    return mapping


def _parse_published(entry: dict[str, Any]) -> str | None:
    """Turn an RSS date into a UTC ISO timestamp. Unparseable dates become None."""
    for key in ("published", "updated"):
        raw = entry.get(key)
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError, IndexError):
            continue
    return None


def _content_hash(title: str, summary: str, url: str) -> str:
    """Stable hash of the stored fields, so a later run can see that the item changed."""
    blob = f"{title.strip()}|{summary.strip()}|{url.strip()}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def fetch_feed(feed_url: str, timeout: float = 20.0) -> feedparser.FeedParserDict:
    """Download one feed and parse it. Raises if the HTTP request fails."""
    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        response = client.get(feed_url)
        response.raise_for_status()
        return feedparser.parse(response.content)


def should_store_article(feed: Feed, title: str, summary: str, url: str = "") -> bool:
    """Domain rules applied before a feed item is written."""
    if feed.domain == "sports":
        if is_soccer(title, summary, url) or is_betting_promo(title, summary, url):
            return False
        # MLB wire: Mets only (a light baseball slice).
        if "mlb" in feed.name.lower() or "/mlb/" in feed.feed_url.lower():
            return is_mets_baseball(title, summary)
    if feed.domain == "movies":
        if is_foreign_film_blurb(title, summary):
            return False
        # BBC Culture mixes TV and arts. Keep film items.
        if "bbc" in feed.name.lower() and not is_film_related(title, summary):
            return False
    return True


def prepare_article(feed: Feed, entry: dict) -> dict | None:
    """Return a row dict, or None when the entry is empty or out of scope."""
    url = (entry.get("link") or "").strip()
    title = (entry.get("title") or "").strip()
    if not url or not title:
        return None
    # Only keep what the publisher put in the feed (not a scraped full article).
    summary = (entry.get("summary") or entry.get("description") or "").strip()
    if len(summary) > 2000:
        summary = summary[:2000].rstrip() + "..."
    if not should_store_article(feed, title, summary, url):
        return None
    return {
        "url": url,
        "title": title,
        "summary": summary,
        "published_at": _parse_published(entry),
        "content_hash": _content_hash(title, summary, url),
        "domain": feed.domain,
    }


def ingest_feed(
    conn: sqlite3.Connection,
    feed: Feed,
    source_id: int,
) -> tuple[int, int]:
    """Store one feed. Returns (new rows, items that passed the filters)."""
    parsed = fetch_feed(feed.feed_url)
    new_count = 0
    seen_count = 0

    for entry in parsed.entries:
        prepared = prepare_article(feed, entry)
        if prepared is None:
            continue
        url = prepared["url"]
        title = prepared["title"]
        summary = prepared["summary"]
        published_at = prepared["published_at"]
        content_hash = prepared["content_hash"]
        seen_count += 1

        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO articles (
                source_id, url, title, summary, published_at, content_hash, domain
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (source_id, url, title, summary, published_at, content_hash, feed.domain),
        )
        if cursor.rowcount:
            new_count += 1

    conn.commit()
    return new_count, seen_count


def run_ingest(conn: sqlite3.Connection, feeds: tuple[Feed, ...] = DEFAULT_FEEDS) -> dict[str, int]:
    """Ingest every configured feed, record the run, then pull TMDB if a key is set."""
    source_ids = ensure_sources(conn, feeds)
    started = datetime.now(timezone.utc).isoformat()
    run_id = conn.execute(
        "INSERT INTO ingest_runs (started_at) VALUES (?)",
        (started,),
    ).lastrowid
    conn.commit()

    sources_ok = 0
    sources_failed = 0
    articles_new = 0
    articles_seen = 0
    notes: list[str] = []

    for feed in feeds:
        try:
            new_count, seen_count = ingest_feed(conn, feed, source_ids[feed.feed_url])
            sources_ok += 1
            articles_new += new_count
            articles_seen += seen_count
            print(f"[ok] {feed.domain:8} {feed.name}: +{new_count} new / {seen_count} seen")
        except Exception as exc:  # noqa: BLE001 — log per-feed failures and continue
            sources_failed += 1
            msg = f"{feed.name}: {exc}"
            notes.append(msg)
            print(f"[fail] {feed.domain:8} {msg}")

    finished = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        UPDATE ingest_runs
        SET finished_at = ?,
            sources_ok = ?,
            sources_failed = ?,
            articles_new = ?,
            articles_seen = ?,
            notes = ?
        WHERE id = ?
        """,
        (
            finished,
            sources_ok,
            sources_failed,
            articles_new,
            articles_seen,
            "\n".join(notes) if notes else None,
            run_id,
        ),
    )
    conn.commit()
    tmdb_stats = run_tmdb_ingest(conn)
    return {
        "sources_ok": sources_ok + tmdb_stats["sources_ok"],
        "sources_failed": sources_failed + tmdb_stats["sources_failed"],
        "articles_new": articles_new + tmdb_stats["articles_new"],
        "articles_seen": articles_seen + tmdb_stats["articles_seen"],
    }
