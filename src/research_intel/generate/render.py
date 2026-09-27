from __future__ import annotations

import re
from datetime import datetime, timezone

from research_intel.config import DOMAINS
from research_intel.generate.template_writer import ResearchBrief
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


_ABBREV = re.compile(r"\b(Mr|Mrs|Ms|Dr|Inc|Ltd|Jr|Sr|U\.S|U\.K|Gen)\.")


def first_sentence(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    protected = _ABBREV.sub(lambda match: match.group(0).replace(".", "\u0001"), text)
    sentence = re.split(r"(?<=[.!?])\s+", protected, maxsplit=1)[0].strip()
    sentence = sentence.replace("\u0001", ".")
    if len(sentence) > 220:
        sentence = sentence[:217].rsplit(" ", 1)[0] + "..."
    return sentence


def at_a_glance(brief: ResearchBrief) -> list[tuple[str, str]]:
    """One line per domain: the top story, in a single sentence."""
    rows: list[tuple[str, str]] = []
    for domain in DOMAINS:
        label = DOMAIN_TITLES.get(domain, domain.title())
        cards = brief.cards_by_domain.get(domain) or []
        if not cards:
            rows.append((label, "Nothing selected."))
            continue
        top = cards[0]
        sentence = first_sentence(top.executive_summary) or top.title
        rows.append((label, sentence))
    return rows


_TITLE_TAIL = re.compile(
    r"\s+\|\s*(Editorial|Opinion|Comment|Analysis)\s*$",
    re.IGNORECASE,
)


def polish_title(title: str) -> str:
    return unwrap_repeated_phrase(_TITLE_TAIL.sub("", (title or "").strip()))


def _as_local(raw: str | None) -> datetime | None:
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
    clock = dt.strftime("%I:%M %p").lstrip("0")
    return f"{dt.strftime('%b')} {dt.day}, {clock}"


def format_published(raw: str | None) -> str:
    """Local time for when an article was released."""
    dt = _as_local(raw)
    if dt is None:
        return raw or "time unknown"
    return _clock(dt)


def format_created(raw: str) -> str:
    dt = _as_local(raw)
    if dt is None:
        return raw
    return f"{dt.strftime('%A')}, {_clock(dt)}"


def stock_line(item) -> str:
    if item.price is None:
        move = "price unavailable"
    else:
        pct = "n/a" if item.change_pct is None else f"{item.change_pct:+.2f}%"
        move = f"${item.price:.2f} ({pct})"
    reason = first_sentence(item.reason)
    return f"{item.symbol} · {move}. {reason}" if reason else f"{item.symbol} · {move}"


def _fmt_quote_line(symbol: str, name: str, price: float | None, change_pct: float | None) -> str:
    if price is None:
        return f"- {symbol} ({name}): unavailable"
    pct = "n/a" if change_pct is None else f"{change_pct:+.2f}%"
    return f"- {symbol} ({name}): ${price:.2f} ({pct})"


def render_markdown(brief: ResearchBrief) -> str:
    title = "Morning Brief" if brief.brief_type == "morning" else "Evening Brief"
    lines: list[str] = [
        f"# Research Intelligence Engine - {title}",
        "",
        f"{format_created(brief.created_at)}",
        "",
        "A short briefing: the lead in each area, then what happened and where to read it.",
        "",
        f"_{DISCLAIMER}_",
        "",
    ]

    if brief.watchlist_quotes:
        lines.append("## Watchlist Tape")
        lines.append("")
        for q in brief.watchlist_quotes:
            lines.append(_fmt_quote_line(q.symbol, q.name, q.price, q.change_pct))
        lines.append("")

    lines.append("## At a glance")
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
            lines.append(card.executive_summary)
            lines.append("")
            if card.why_it_matters:
                lines.append(f"**Why it matters:** {card.why_it_matters}")
                lines.append("")
            if card.definitions:
                lines.append("**Definitions**")
                for item in card.definitions:
                    lines.append(f"- {item}")
                lines.append("")
            if card.related_tickers:
                lines.append("**Stocks in play**")
                for item in card.related_tickers:
                    lines.append(f"- {stock_line(item)}")
                lines.append("")
            shown = card.sources[:SOURCE_LINKS_SHOWN]
            lines.append("**Sources**")
            for src in shown:
                when = format_published(src.published_at)
                lines.append(
                    f"- [{src.source_name}]({src.url}) - {polish_title(src.title)} _(released {when})_"
                )
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
            f"Section: {DOMAIN_TITLES.get(c.article_domain, c.article_domain)}",
            "",
            c.why_learn,
            "",
        ]
    )
    if c.source_url:
        lines.append(f"Source: [{c.source_name}]({c.source_url})")
        lines.append("")
    if c.definitions:
        lines.append("**Key terms to learn**")
        for item in c.definitions:
            lines.append(f"- {item}")
        lines.append("")
    lines.append(f"**Related backdrop:** {c.emerging_trend}")
    lines.append("")
    lines.append("**Also worth monitoring**")
    for item in c.topics_to_monitor:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("---")
    lines.append("End of brief.")
    lines.append("")
    return "\n".join(lines)
