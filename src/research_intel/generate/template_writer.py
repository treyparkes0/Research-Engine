from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import unescape

from research_intel.generate.analyze import collect_facts, what_happened, what_is_open, why_it_matters
from research_intel.generate.glossary import definitions_for_text
from research_intel.generate.themes import match_themes
from research_intel.ingest.enrich import Enrichment
from research_intel.markets.impact import TickerContext
from research_intel.markets.watchlist import Quote


def _clean_html(text: str | None) -> str:
    if not text:
        return ""
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _first_sentences(text: str, max_chars: int = 420) -> str:
    text = _clean_html(text)
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(".,;:") + "..."


@dataclass
class SourceLink:
    title: str
    url: str
    source_name: str
    summary: str = ""
    published_at: str | None = None


@dataclass
class TopicCard:
    topic_id: int
    domain: str
    rank: int
    title: str
    executive_summary: str
    why_it_matters: str
    key_takeaways: list[str]
    research_snapshot: str
    further_research: list[str]
    definitions: list[str]
    sources: list[SourceLink]
    related_tickers: list[TickerContext] = field(default_factory=list)
    themes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BriefClosing:
    # Shown under the "Article of the Day" section.
    article_title: str
    article_domain: str
    why_learn: str
    source_url: str
    source_name: str
    definitions: list[str]
    # Kept for light context under the learning article.
    emerging_trend: str
    topics_to_monitor: list[str]


@dataclass
class ResearchBrief:
    brief_type: str
    created_at: str
    cards_by_domain: dict[str, list[TopicCard]]
    closing: BriefClosing
    watchlist_quotes: list[Quote] = field(default_factory=list)
    writer: str = "analysis-v1"

    def to_dict(self) -> dict:
        return {
            "brief_type": self.brief_type,
            "created_at": self.created_at,
            "writer": self.writer,
            "cards_by_domain": {
                domain: [c.to_dict() for c in cards]
                for domain, cards in self.cards_by_domain.items()
            },
            "closing": asdict(self.closing),
            "watchlist_quotes": [asdict(q) for q in self.watchlist_quotes],
        }


def build_topic_card(
    *,
    topic_id: int,
    domain: str,
    rank: int,
    title: str,
    sources: list[SourceLink],
    related_tickers: list[TickerContext] | None = None,
    enrichment: Enrichment | None = None,
) -> TopicCard:
    theme_hits = match_themes(title, *[s.summary for s in sources], *[s.title for s in sources])
    theme_names = [t.name for t in theme_hits]

    facts = collect_facts(title, sources, enrichment)
    executive = what_happened(title, facts)
    why = why_it_matters(facts, title=title)
    named_sources = {name for name, _ in facts}
    snapshot = what_is_open(facts, source_count=len({s.source_name for s in sources}) or len(named_sources))

    takeaways: list[str] = []
    for src in sources[:5]:
        blurb = _first_sentences(src.summary, max_chars=220)
        if not blurb:
            continue
        if blurb.lower().strip(" .") == title.lower().strip(" ."):
            continue
        takeaways.append(f"{src.source_name}: {blurb}")
    if not takeaways:
        takeaways = ["No feed lead added a fact beyond the headline."]

    further_unique = [] if domain in {"sports", "movies"} else theme_names[:6]

    definitions = definitions_for_text(
        title,
        *[s.title for s in sources],
        *[s.summary for s in sources],
        *theme_names,
    )

    return TopicCard(
        topic_id=topic_id,
        domain=domain,
        rank=rank,
        title=title,
        executive_summary=executive,
        why_it_matters=why,
        key_takeaways=takeaways,
        research_snapshot=snapshot,
        further_research=further_unique,
        definitions=definitions,
        sources=sources,
        related_tickers=related_tickers or [],
        themes=theme_names,
    )


def build_closing(
    cards_by_domain: dict[str, list[TopicCard]],
    monitor_labels: list[str],
    brief_type: str,
) -> BriefClosing:
    all_cards = [card for cards in cards_by_domain.values() for card in cards]
    theme_scores: dict[str, float] = {}
    for card in all_cards:
        for theme in card.themes:
            theme_scores[theme] = theme_scores.get(theme, 0.0) + 1.0

    ranked_themes = sorted(theme_scores.items(), key=lambda kv: kv[1], reverse=True)
    emerging = ranked_themes[0][0] if ranked_themes else "today's coverage"

    # The story covered by the most outlets, not a random card.
    pick = (
        max(
            all_cards,
            key=lambda card: (
                len({src.source_name for src in card.sources}),
                len(card.sources),
                -card.rank,
            ),
        )
        if all_cards
        else None
    )
    if pick is None:
        return BriefClosing(
            article_title="No topic available",
            article_domain="",
            why_learn="Run the topic picker first.",
            source_url="",
            source_name="",
            definitions=[],
            emerging_trend=emerging,
            topics_to_monitor=monitor_labels[:5],
        )

    source = pick.sources[0] if pick.sources else None
    section = {
        "markets": "markets",
        "business": "business",
        "world": "world news",
        "sports": "sports",
        "movies": "film",
    }.get(pick.domain, pick.domain)
    if pick.definitions:
        why_learn = (
            f"Widest coverage in {section} today. Read one source, learn the terms below, "
            f"and see how it sits with {emerging}."
        )
    else:
        why_learn = (
            f"Widest coverage in {section} today. Read one source and see how it sits with {emerging}."
        )
    monitor = monitor_labels[:5] or [
        f"Follow-ups on {pick.title[:80]}",
        f"Fresh developments tied to {emerging}",
    ]

    return BriefClosing(
        article_title=pick.title,
        article_domain=pick.domain,
        why_learn=why_learn,
        source_url=source.url if source else "",
        source_name=source.source_name if source else "",
        definitions=pick.definitions[:5],
        emerging_trend=emerging,
        topics_to_monitor=monitor,
    )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def dumps_card_lists(card: TopicCard) -> dict[str, str]:
    return {
        "key_takeaways_json": json.dumps(card.key_takeaways, ensure_ascii=True),
        "further_research_json": json.dumps(card.further_research, ensure_ascii=True),
        # DB column remains questions_json; it now stores definitions.
        "questions_json": json.dumps(card.definitions, ensure_ascii=True),
        "sources_json": json.dumps([asdict(s) for s in card.sources], ensure_ascii=True),
        "card_json": json.dumps(card.to_dict(), ensure_ascii=True),
    }
