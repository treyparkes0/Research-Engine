"""Film rules: English-language focus, this-week releases, and real film coverage.

Television and celebrity items that never say film, movie, or cinema are
dropped. Foreign-language film cues are dropped. The week window is Monday
through Sunday on the machine's local calendar.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

# Production countries treated as English-speaking film industries.
EN_SPEAKING_COUNTRIES = frozenset({"US", "GB", "CA", "AU", "IE", "NZ"})

# Soft drop: clearly non-English film cues. A country name alone is not enough.
FOREIGN_FILM_PATTERNS: tuple[str, ...] = (
    r"\bfrench film\b",
    r"\bkorean film\b",
    r"\bjapanese film\b",
    r"\bchinese film\b",
    r"\bin korean\b",
    r"\bin japanese\b",
    r"\bbollywood\b",
    r"\banime\b",
    r"\bspanish[- ]language\b",
    r"\bsubtitled\b",
    r"\bin translation\b",
)

# Industry / Hollywood news cues (RSS).
INDUSTRY_KEYWORDS: tuple[str, ...] = (
    "box office",
    "hollywood",
    "studio",
    "streaming",
    "netflix",
    "disney",
    "warner",
    "paramount",
    "universal",
    "sony pictures",
    "oscar",
    "academy awards",
    "premiere",
    "release date",
    "theatrical",
    "cinema",
    "film industry",
    "movie industry",
    "opening weekend",
    "gross",
)

REVIEW_KEYWORDS: tuple[str, ...] = (
    "review",
    "stars",
    "critic",
    "rated",
    "verdict",
    "first look",
)

# Strong cues only. "Actor", "streaming", or "Netflix" alone is often TV.
FILM_NEWS_KEYWORDS: tuple[str, ...] = (
    "film",
    "movie",
    "cinema",
    "hollywood",
    "oscar",
    "box office",
    "trailer",
    "screenplay",
    "theatrical",
)

_FOREIGN_RE = [re.compile(p, re.I) for p in FOREIGN_FILM_PATTERNS]


def _blob(*parts: str) -> str:
    """Join title, blurb, and URL into one lowercase string."""
    return " ".join(p for p in parts if p).lower()


def week_window(today: date | None = None) -> tuple[date, date]:
    """Monday–Sunday of the current week on the machine's local calendar."""
    today = today or datetime.now().astimezone().date()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end


def parse_release_date(raw: str | None) -> date | None:
    """Read a YYYY-MM-DD release date out of a movie blurb."""
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def is_english_speaking_movie(
    *,
    original_language: str | None,
    production_countries: list[dict] | None = None,
) -> bool:
    """Keep US/UK/other English-speaking productions (English language)."""
    lang = (original_language or "").strip().lower()
    if lang and lang != "en":
        return False
    countries = {
        (c.get("iso_3166_1") or "").upper()
        for c in (production_countries or [])
        if isinstance(c, dict)
    }
    countries.discard("")
    if not countries:
        # Language en, country unknown — keep (common for sparse TMDB rows).
        return lang == "en"
    return bool(countries & EN_SPEAKING_COUNTRIES)


def is_foreign_film_blurb(*parts: str) -> bool:
    """True when the item is marked as a foreign-language film."""
    text = _blob(*parts)
    return any(rx.search(text) for rx in _FOREIGN_RE)


def is_film_related(*parts: str) -> bool:
    """True when the item is actually about a film, not a TV show or a celebrity note."""
    text = _blob(*parts)
    return any(re.search(rf"\b{re.escape(k)}\b", text) for k in FILM_NEWS_KEYWORDS)


def movies_bucket(*parts: str) -> str | None:
    """
    Classify a movies topic for diversity.
    Returns None when the item should be dropped.
    """
    text = _blob(*parts)
    if is_foreign_film_blurb(text):
        return None
    film = is_film_related(text)
    if "[this week]" in text or "opens this week" in text or "this week release" in text:
        return "this_week"
    if "[now playing]" in text:
        return "review"
    if "[upcoming]" in text:
        return "this_week"
    if not film:
        return None
    if any(k in text for k in REVIEW_KEYWORDS):
        return "review"
    if any(k in text for k in INDUSTRY_KEYWORDS) or film:
        return "industry"
    return None


def movies_focus_bonus(*parts: str) -> float | None:
    """Additive score; None = drop."""
    bucket = movies_bucket(*parts)
    if bucket is None:
        return None
    weights = {
        "this_week": 4.0,
        "review": 3.5,
        "industry": 3.0,
    }
    return weights.get(bucket, 1.0)
