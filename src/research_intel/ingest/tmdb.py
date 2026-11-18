"""Optional movie listings from TMDB.

Skipped when TMDB_API_KEY is empty. Keeps English-language titles that open
this week or are newly in theaters. The stored blurb is a release line, an
audience score when TMDB has one, and one plot sentence. The release date is
what the brief shows; fetch time is what keeps the slate inside the lookback
window.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone

import httpx

from research_intel.process.movies_focus import (
    is_english_speaking_movie,
    parse_release_date,
    week_window,
)

USER_AGENT = "ResearchIntelligenceEngine/0.4 (personal educational research)"
TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_SITE = "https://www.themoviedb.org/movie"


def _api_key() -> str:
    """TMDB key from the environment, or an empty string when movies should be skipped."""
    return (os.getenv("TMDB_API_KEY") or "").strip()


def _content_hash(title: str, summary: str, url: str) -> str:
    """Hash of the stored movie fields. Same idea as the RSS hash."""
    blob = f"{title.strip()}|{summary.strip()}|{url.strip()}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _ensure_tmdb_source(conn: sqlite3.Connection) -> int:
    """Make sure the synthetic TMDB source row exists and return its id."""
    feed_url = "tmdb://movies"
    conn.execute(
        """
        INSERT INTO sources (name, domain, feed_url, homepage_url, active)
        VALUES (?, 'movies', ?, ?, 1)
        ON CONFLICT(feed_url) DO UPDATE SET
            name = excluded.name,
            domain = excluded.domain,
            homepage_url = excluded.homepage_url,
            active = 1
        """,
        ("TMDB Movies", feed_url, "https://www.themoviedb.org"),
    )
    row = conn.execute(
        "SELECT id FROM sources WHERE feed_url = ?",
        (feed_url,),
    ).fetchone()
    conn.commit()
    return int(row["id"])


def _get(client: httpx.Client, path: str, params: dict | None = None) -> dict:
    """GET one TMDB path with the API key attached."""
    key = _api_key()
    query = {"api_key": key}
    if params:
        query.update(params)
    response = client.get(f"{TMDB_BASE}{path}", params=query)
    response.raise_for_status()
    return response.json()


def _classify_kind(release: str | None, list_kind: str) -> str | None:
    """
    Map a movie into This Week / Now Playing / skip.
    Only keep releases in the current week (upcoming) or currently in theaters.
    """
    week_start, week_end = week_window()
    rel = parse_release_date(release)
    if list_kind == "Now Playing":
        # In theaters now — treat as new-release review candidates.
        if rel and rel < week_start - timedelta(days=21):
            # Been out a long time — skip for the brief.
            return None
        return "Now Playing"
    if list_kind == "Upcoming":
        if rel and week_start <= rel <= week_end:
            return "This Week"
        # Also allow next few days past Sunday if still "this week" feeling — no, stick to week.
        return None
    # Trending: only if release is this week or very recent now-playing window.
    if rel and week_start <= rel <= week_end:
        return "This Week"
    if rel and (week_start - timedelta(days=14)) <= rel <= week_end:
        return "Now Playing"
    return None


def _short_plot(overview: str, limit: int = 240) -> str:
    """First plot sentence, cut only when it is still longer than the limit."""
    text = " ".join((overview or "").split())
    if not text:
        return ""
    sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0].strip()
    if len(sentence) <= limit:
        return sentence
    cut = sentence[: limit - 3].rsplit(" ", 1)[0].rstrip(".,;:")
    return cut + "..."


def _movie_summary(movie: dict, kind: str) -> str:
    """Release line, optional audience score, and a short plot. Not a full overview."""
    title = (movie.get("title") or movie.get("name") or "Untitled").strip()
    overview = (movie.get("overview") or "").strip()
    release = (movie.get("release_date") or "").strip()[:10]
    rating = movie.get("vote_average")
    votes = movie.get("vote_count")
    if kind == "This Week":
        lead = f"{title} is scheduled to open in theaters"
    else:
        lead = f"{title} is currently in theaters"
    lead += f" on {release}." if release else "."
    parts = [lead]
    if rating is not None and votes:
        parts.append(
            f"TMDB lists an audience score of {float(rating):.1f} out of 10 from {int(votes)} ratings."
        )
    plot = _short_plot(overview)
    if plot:
        parts.append(plot)
    return " ".join(parts)


def _display_title(title: str, kind: str) -> str:
    """Prefix the title with [This Week] or [Now Playing], without stacking prefixes."""
    prefix = "[This Week]" if kind == "This Week" else "[Now Playing]"
    # Avoid double-prefix on refresh.
    clean = title
    for p in ("[This Week] ", "[Now Playing] ", "[Upcoming] ", "[Trending] "):
        if clean.startswith(p):
            clean = clean[len(p) :]
    return f"{prefix} {clean}"


def _published_stamp(movie: dict) -> str:
    """Use the theatrical date when TMDB has one. Otherwise use the current time."""
    release = (movie.get("release_date") or "").strip()
    if len(release) >= 10:
        return f"{release[:10]}T12:00:00+00:00"
    return datetime.now(timezone.utc).isoformat()


def _upsert_movie(
    conn: sqlite3.Connection,
    source_id: int,
    movie: dict,
    kind: str,
) -> bool:
    """Insert or update one TMDB title in the articles table."""
    movie_id = movie.get("id")
    raw_title = (movie.get("title") or movie.get("name") or "").strip()
    if not movie_id or not raw_title:
        return False
    title = _display_title(raw_title, kind)
    url = f"{TMDB_SITE}/{movie_id}"
    summary = _movie_summary(movie, kind)
    # Release date is what the brief should show. fetched_at still refreshes,
    # and the topic picker uses fetched_at for the movies window.
    published = _published_stamp(movie)
    content_hash = _content_hash(title, summary, url)
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO articles (
            source_id, url, title, summary, published_at, content_hash, domain
        ) VALUES (?, ?, ?, ?, ?, ?, 'movies')
        """,
        (source_id, url, title, summary, published, content_hash),
    )
    if cursor.rowcount:
        return True
    conn.execute(
        """
        UPDATE articles
        SET title = ?, summary = ?, published_at = ?,
            content_hash = ?, fetched_at = datetime('now')
        WHERE url = ?
        """,
        (title, summary, published, content_hash, url),
    )
    return False


def _movie_details(client: httpx.Client, movie_id: int) -> dict:
    """Full movie record, which carries language and production countries the list endpoints omit."""
    return _get(client, f"/movie/{movie_id}")


def run_tmdb_ingest(conn: sqlite3.Connection) -> dict[str, int]:
    """
    Pull US now-playing + upcoming, keep English-speaking (US/UK/etc.) titles
    that open this week or are newly in theaters (review slate).
    """
    if not _api_key():
        print("[skip] movies  TMDB: no TMDB_API_KEY in .env")
        return {
            "sources_ok": 0,
            "sources_failed": 0,
            "articles_new": 0,
            "articles_seen": 0,
        }

    source_id = _ensure_tmdb_source(conn)
    new_count = 0
    seen_count = 0
    skipped = 0

    try:
        with httpx.Client(timeout=25.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
            buckets = [
                ("Now Playing", "/movie/now_playing", {"region": "US", "page": 1}),
                ("Now Playing", "/movie/now_playing", {"region": "GB", "page": 1}),
                ("Upcoming", "/movie/upcoming", {"region": "US", "page": 1}),
                ("Upcoming", "/movie/upcoming", {"region": "GB", "page": 1}),
            ]
            candidates: list[tuple[str, dict]] = []
            for list_kind, path, params in buckets:
                payload = _get(client, path, params)
                for movie in payload.get("results") or []:
                    candidates.append((list_kind, movie))

            unique: dict[int, tuple[str, dict]] = {}
            for list_kind, movie in candidates:
                mid = movie.get("id")
                if not isinstance(mid, int):
                    continue
                kind = _classify_kind(movie.get("release_date"), list_kind)
                if not kind:
                    skipped += 1
                    continue
                # Prefer This Week over Now Playing when both appear.
                prev = unique.get(mid)
                if prev is None or (kind == "This Week" and prev[0] != "This Week"):
                    unique[mid] = (kind, movie)

            for idx, (mid, (kind, movie)) in enumerate(list(unique.items())):
                try:
                    details = _movie_details(client, mid)
                except Exception:
                    details = movie
                if not is_english_speaking_movie(
                    original_language=details.get("original_language") or movie.get("original_language"),
                    production_countries=details.get("production_countries"),
                ):
                    skipped += 1
                    unique.pop(mid, None)
                    continue

                release = details.get("release_date") or movie.get("release_date")
                # Re-check window with authoritative release date from details.
                list_kind = "Upcoming" if kind == "This Week" else "Now Playing"
                kind = _classify_kind(release, list_kind)
                if not kind:
                    skipped += 1
                    unique.pop(mid, None)
                    continue
                unique[mid] = (kind, {**movie, **details})

            kept = list(unique.items())
            kept_urls: list[str] = []
            for mid, (kind, movie) in kept:
                seen_count += 1
                url = f"{TMDB_SITE}/{mid}"
                kept_urls.append(url)
                if _upsert_movie(conn, source_id, movie, kind):
                    new_count += 1

            # Drop stale TMDB rows (foreign / old releases) so they leave the brief.
            if kept_urls:
                placeholders = ",".join("?" for _ in kept_urls)
                conn.execute(
                    f"""
                    DELETE FROM articles
                    WHERE source_id = ?
                      AND url NOT IN ({placeholders})
                    """,
                    (source_id, *kept_urls),
                )
            else:
                conn.execute("DELETE FROM articles WHERE source_id = ?", (source_id,))

        conn.commit()
        print(
            f"[ok] movies   TMDB: +{new_count} new / {seen_count} kept "
            f"(skipped {skipped} non-EN or out-of-window)"
        )
        return {
            "sources_ok": 1,
            "sources_failed": 0,
            "articles_new": new_count,
            "articles_seen": seen_count,
        }
    except Exception as exc:  # noqa: BLE001
        print(f"[fail] movies   TMDB: {exc}")
        return {
            "sources_ok": 0,
            "sources_failed": 1,
            "articles_new": 0,
            "articles_seen": 0,
        }
