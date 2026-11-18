"""Build the in-memory brief: one card per selected story, plus the closing.

A card's paragraph is the feed blurb. Theme tags are keyword hits. Glossary
lines are included only when the term actually appears in the title or the
paragraph. Movies do not get a 'why it matters' line, because a plot sentence
is not a consequence.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from research_intel.generate.analyze import collect_facts, what_happened, what_is_open, why_it_matters
from research_intel.generate.glossary import definitions_for_text
from research_intel.generate.themes import match_themes
from research_intel.ingest.enrich import Enrichment
from research_intel.markets.impact import TickerContext
from research_intel.markets.watchlist import Quote


@dataclass
class SourceLink:
    """One publisher link attached to a card."""
    title: str
    url: str
    source_name: str
    summary: str = ""
    published_at: str | None = None


@dataclass
class TopicCard:
    """One story in the brief: headline, what happened, optional why, terms, and links."""
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
        """Card fields as a plain dict, for JSON."""
        return asdict(self)


@dataclass
class BriefClosing:
    """The article of the day and the short list of stories that did not make the main slots."""
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
    """The full morning or evening brief, ready to render or save."""
    brief_type: str
    created_at: str
    cards_by_domain: dict[str, list[TopicCard]]
    closing: BriefClosing
    watchlist_quotes: list[Quote] = field(default_factory=list)
    writer: str = "analysis-v1"

    def to_dict(self) -> dict:
        """The whole brief as a plain dict, for the JSON file."""
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
    """Assemble one card from its sources. The paragraph is not a blend of every article."""
    theme_hits = match_themes(title, *[s.summary for s in sources], *[s.title for s in sources])
    theme_names = [t.name for t in theme_hits]

    if domain == "movies":
        theme_hits = [hit for hit in theme_hits if hit.name in {"Film & Streaming", "Box Office"}]
        theme_names = [hit.name for hit in theme_hits]
    elif domain == "sports":
        theme_hits = []
        theme_names = []

    facts = collect_facts(title, sources, enrichment)
    executive = what_happened(title, facts, limit=3 if domain == "movies" else 2)
    why = "" if domain == "movies" else why_it_matters(facts, title=title)
    named_sources = {name for name, _ in facts}
    snapshot = what_is_open(facts, source_count=len({s.source_name for s in sources}) or len(named_sources))

    takeaways = [f"{name}: {sentence}" for name, sentence in facts[:3]]
    if not takeaways:
        takeaways = ["No feed lead added a fact beyond the headline."]

    further_unique = [] if domain in {"sports", "movies"} else theme_names[:6]

    # Terms have to appear in the headline or the feed text. Theme labels are not injected.
    definitions = definitions_for_text(
        title,
        executive,
        why,
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
    """Pick the article of the day and the short also-watching list."""
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
    outlet_count = len({src.source_name for src in pick.sources}) or 1
    outlet_word = "outlet" if outlet_count == 1 else "outlets"
    why_learn = (
        f"Widest coverage in this brief: {outlet_count} {outlet_word} in {section}. "
        "The card uses the feed blurb for that headline and links back to the publisher."
    )
    monitor = monitor_labels[:5] or [f"No other near-miss stories in this run."]

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
    """Current UTC time as an ISO timestamp."""
    return datetime.now(timezone.utc).isoformat()


def dumps_card_lists(card: TopicCard) -> dict[str, str]:
    """JSON strings for the list columns on the topic_cards table."""
    return {
        "key_takeaways_json": json.dumps(card.key_takeaways, ensure_ascii=True),
        "further_research_json": json.dumps(card.further_research, ensure_ascii=True),
        # DB column remains questions_json; it now stores definitions.
        "questions_json": json.dumps(card.definitions, ensure_ascii=True),
        "sources_json": json.dumps([asdict(s) for s in card.sources], ensure_ascii=True),
        "card_json": json.dumps(card.to_dict(), ensure_ascii=True),
    }
