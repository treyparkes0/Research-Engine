"""Markdown version of the brief.

The HTML email uses the same section names and the same helper functions, so
the two formats do not drift. The overview line is the headline, plus a
supporting sentence only when that sentence belongs to the headline.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from research_intel.config import DOMAINS
from research_intel.generate.analyze import sentence_supports_title
from research_intel.generate.template_writer import ResearchBrief, TopicCard
from research_intel.process.text import unwrap_repeated_phrase
from research_intel.markets.impact import DISCLAIMER

SOURCE_LINKS_SHOWN = 3


DOMAIN_TITLES = {
    "markets": "Stock Market & Investing",
    "business": "Business & Corporate News",
    "world": "World News & Geopolitics",
    "sports": "Sports",
    "movies": "Movies & Film",
}


_ABBREV = re.compile(
    r"\b(Mr|Mrs|Ms|Dr|Inc|Ltd|Jr|Sr|U\.S|U\.K|Gen|No|St|Mt|Sen|Rep|Gov|Col|Lt|Sgt|Prof|vs|Fig)\."
)


def first_sentence(text: str) -> str:
    """First sentence, without splitting on Mr., No., or U.S."""
    text = (text or "").strip()
    if not text:
        return ""
    protected = _ABBREV.sub(lambda match: match.group(0).replace(".", "\u0001"), text)
    sentence = re.split(r"(?<=[.!?])\s+", protected, maxsplit=1)[0].strip()
    sentence = sentence.replace("\u0001", ".")
    if len(sentence) > 220:
        sentence = sentence[:217].rsplit(" ", 1)[0] + "..."
    return sentence


def _norm_words(text: str) -> str:
    """Letters and digits only, for a 'is this the same sentence' check."""
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def overview_line(card: TopicCard) -> str:
    """The lead headline, plus a supporting sentence only when it belongs to that headline."""
    title = polish_title(card.title)
    summary = (card.executive_summary or "").strip()
    if not title:
        return first_sentence(summary) or "No headline."
    if not summary or summary.lower().startswith("the feeds only repeat"):
        return title
    sentence = first_sentence(summary)
    if not sentence or sentence.endswith("..."):
        return title
    if not sentence_supports_title(title, sentence):
        return title
    if _norm_words(sentence) == _norm_words(title):
        return title
    if _norm_words(title) and _norm_words(title) in _norm_words(sentence):
        return sentence
    combined = f"{title} — {sentence}"
    if len(combined) > 280:
        return title
    return combined


def at_a_glance(brief: ResearchBrief) -> list[tuple[str, str]]:
    """One line per domain: the leading story, not a stray sentence from another item."""
    rows: list[tuple[str, str]] = []
    for domain in DOMAINS:
        label = DOMAIN_TITLES.get(domain, domain.title())
        cards = brief.cards_by_domain.get(domain) or []
        if not cards:
            rows.append((label, "Nothing selected."))
            continue
        rows.append((label, overview_line(cards[0])))
    return rows


_TITLE_TAIL = re.compile(
    r"\s+\|\s*(Editorial|Opinion|Comment|Analysis)\s*$",
    re.IGNORECASE,
)


def polish_title(title: str) -> str:
    """Drop a repeated title phrase and a trailing '| Editorial' label."""
    return unwrap_repeated_phrase(_TITLE_TAIL.sub("", (title or "").strip()))


def _as_local(raw: str | None) -> datetime | None:
    """Parse an ISO timestamp and convert it to the machine's local time."""
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()


def _clock(dt: datetime) -> str:
    """Short local clock, such as 'Nov 8, 9:50 PM'."""
    clock = dt.strftime("%I:%M %p").lstrip("0")
    return f"{dt.strftime('%b')} {dt.day}, {clock}"


def format_published(raw: str | None) -> str:
    """Local time for when an article was released."""
    dt = _as_local(raw)
    if dt is None:
        return raw or "time unknown"
    return _clock(dt)


def format_created(raw: str) -> str:
    """When the brief was written, in local time."""
    dt = _as_local(raw)
    if dt is None:
        return raw
    return f"{dt.strftime('%A')}, {_clock(dt)}"


def stock_line(item) -> str:
    """One ticker line: symbol, recent price, and the non-forecast explanation."""
    if item.price is None:
        move = "price unavailable"
    else:
        pct = "n/a" if item.change_pct is None else f"{item.change_pct:+.2f}%"
        move = f"${item.price:.2f} ({pct})"
    reason = first_sentence(item.reason)
    return f"{item.symbol} · {move}. {reason}" if reason else f"{item.symbol} · {move}"


def sources_for_display(sources: list, limit: int = SOURCE_LINKS_SHOWN) -> list:
    """Prefer one link per publisher, then fill with further coverage of the same story."""
    unique: list = []
    seen_names: set[str] = set()
    for src in sources:
        name = (getattr(src, "source_name", "") or "").strip().lower()
        if name and name in seen_names:
            continue
        if name:
            seen_names.add(name)
        unique.append(src)
        if len(unique) >= limit:
            return unique
    if len(unique) >= limit:
        return unique
    chosen = {id(src) for src in unique}
    for src in sources:
        if id(src) in chosen:
            continue
        unique.append(src)
        if len(unique) >= limit:
            break
    return unique


def _source_markdown(src) -> str:
    """One source bullet. A missing URL is labeled instead of emitting an empty link."""
    when = format_published(src.published_at)
    headline = polish_title(src.title) if src.title else "Untitled"
    if src.url:
        return f"- [{src.source_name}]({src.url}) — {headline} _(released {when})_"
    return f"- {src.source_name} — {headline} _(released {when}; link unavailable)_"


def _fmt_quote_line(symbol: str, name: str, price: float | None, change_pct: float | None) -> str:
    """One watchlist row. A failed quote is shown as unavailable."""
    if price is None:
        return f"- {symbol} ({name}): unavailable"
    pct = "n/a" if change_pct is None else f"{change_pct:+.2f}%"
    return f"- {symbol} ({name}): ${price:.2f} ({pct})"


def render_markdown(brief: ResearchBrief) -> str:
    """Full Markdown brief: overview, sections, and the article of the day."""
    title = "Morning Brief" if brief.brief_type == "morning" else "Evening Brief"
    lines: list[str] = [
        f"# Research Intelligence Engine - {title}",
        "",
        f"{format_created(brief.created_at)}",
        "",
        "Executive overview first, then each story as what happened, why it matters, and where to read more.",
        "",
        f"_{DISCLAIMER}_",
        "",
    ]

    if brief.watchlist_quotes:
        lines.append("## Watchlist")
        lines.append("")
        lines.append("Recent prices for a personal watchlist. Not tied to one story, and not a recommendation.")
        lines.append("")
        for q in brief.watchlist_quotes:
            lines.append(_fmt_quote_line(q.symbol, q.name, q.price, q.change_pct))
        lines.append("")

    lines.append("## Executive overview")
    lines.append("")
    for label, sentence in at_a_glance(brief):
        lines.append(f"- **{label}:** {sentence}")
    lines.append("")

    for domain in DOMAINS:
        cards = brief.cards_by_domain.get(domain) or []
        lines.append(f"## {DOMAIN_TITLES.get(domain, domain.title())}")
        lines.append("")
        if not cards:
            lines.append("_No selected topics for this domain yet._")
            lines.append("")
            continue

        for card in cards:
            lines.append(f"### {card.rank}. {polish_title(card.title)}")
            lines.append("")
            latest = next((s.published_at for s in card.sources if s.published_at), None)
            if latest:
                lines.append(f"**Published:** {format_published(latest)}")
                lines.append("")
            lines.append("**What happened**")
            lines.append("")
            lines.append(card.executive_summary)
            lines.append("")
            if card.why_it_matters:
                lines.append(f"**Why it matters:** {card.why_it_matters}")
                lines.append("")
            if card.definitions:
                lines.append("**Terms in the source text**")
                for item in card.definitions:
                    lines.append(f"- {item}")
                lines.append("")
            if card.related_tickers:
                lines.append("**Market context**")
                lines.append("")
                for item in card.related_tickers:
                    lines.append(f"- {stock_line(item)}")
                lines.append("")
            shown = sources_for_display(card.sources)
            lines.append("**Read more**")
            lines.append("")
            if not shown:
                lines.append("- No source link was saved for this item.")
            for src in shown:
                lines.append(_source_markdown(src))
            extra = len(card.sources) - len(shown)
            if extra > 0:
                lines.append(f"- _{extra} more source{'s' if extra != 1 else ''} on this story._")
            lines.append("")

    c = brief.closing
    lines.extend(
        [
            "## Article of the Day",
            "",
            f"**{polish_title(c.article_title)}**",
            "",
            f"Section: {DOMAIN_TITLES.get(c.article_domain, c.article_domain) or 'Not available'}",
            "",
            c.why_learn,
            "",
        ]
    )
    if c.source_url:
        lines.append(f"Source: [{c.source_name or 'Source'}]({c.source_url})")
        lines.append("")
    elif c.source_name:
        lines.append(f"Source: {c.source_name} (link unavailable)")
        lines.append("")
    if c.definitions:
        lines.append("**Terms in the source text**")
        for item in c.definitions:
            lines.append(f"- {item}")
        lines.append("")
    lines.append(f"**Most common theme tag:** {c.emerging_trend}")
    lines.append("")
    lines.append("**Also worth monitoring**")
    for item in c.topics_to_monitor:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("---")
    lines.append("End of brief.")
    lines.append("")
    return "\n".join(lines)
