"""Render the committed sample brief from the current writer. No network calls."""

from __future__ import annotations

from pathlib import Path

from research_intel.deliver.html_email import render_html
from research_intel.generate.render import render_markdown
from research_intel.generate.template_writer import (
    ResearchBrief,
    SourceLink,
    build_closing,
    build_topic_card,
)
from research_intel.ingest.tmdb import _movie_summary
from research_intel.markets.impact import tickers_for_topic
from research_intel.markets.watchlist import Quote

ROOT_DOCS = Path(__file__).resolve().parents[1] / "docs"


def _quotes() -> list[Quote]:
    """Saved tape from the November 8, 2026 evening run. Not a live fetch."""
    tape = (
        ("SPY", "S&P 500 ETF", 735.29, 0.31),
        ("VOO", "S&P 500 (Vanguard)", 675.99, 0.30),
        ("VTI", "Total US stock market", 361.93, 0.39),
        ("SCHG", "Schwab US Large-Cap Growth", 33.14, 1.01),
        ("QQQ", "Nasdaq-100 / large growth-tech", 656.10, 1.40),
        ("FNARX", "Fidelity Natural Resources", 68.55, 0.12),
        ("IBB", "Biotech", 213.63, 1.73),
        ("CIBR", "Cybersecurity", 91.04, 0.03),
    )
    return [
        Quote(symbol=symbol, name=name, price=price, change_pct=change, as_of="2026-11-09T03:29:00+00:00")
        for symbol, name, price, change in tape
    ]


def _card(domain: str, rank: int, title: str, summary: str, sources: list[SourceLink], quotes: list[Quote]):
    related = tickers_for_topic(themes=[], title=title, domain=domain, quotes=quotes)
    return build_topic_card(
        topic_id=rank,
        domain=domain,
        rank=rank,
        title=title,
        sources=sources,
        related_tickers=related,
        enrichment=None,
    )


def build_sample() -> ResearchBrief:
    quotes = _quotes()
    movie = _movie_summary(
        {
            "title": "Victorian Psycho",
            "overview": (
                "When eccentric young governess Winifred Notty arrives at a remote Gothic manor, "
                "a string of unsettling events leads the household to suspect she isn't who she claims to be, "
                "but the truth may be far more dangerous than they imagine."
            ),
        },
        "This Week",
    )
    cards = {
        "markets": [
            _card(
                "markets",
                1,
                "China wholesale inflation hits highest in more than four years",
                "The PPI for October came in at 5.7%, compared with the 5.3% expected by economists polled by Reuters.",
                [
                    SourceLink(
                        title="China wholesale inflation hits highest in more than four years",
                        url="https://www.cnbc.com/2026/11/09/china-wholesale-inflation-rises-consumer.html",
                        source_name="CNBC",
                        summary="The PPI for October came in at 5.7%, compared with the 5.3% expected by economists polled by Reuters.",
                        published_at="2026-11-09T02:50:00+00:00",
                    )
                ],
                quotes,
            ),
            _card(
                "markets",
                2,
                "Stock futures rise as investors eye the AI trade and the next data print",
                "Stock futures were higher in early trading. Key inflation data and AI earnings could set the tone for the U.S. market this week.",
                [
                    SourceLink(
                        title="Stock futures rise as investors eye the AI trade and the next data print",
                        url="https://www.cnbc.com/2026/11/08/stock-market-today-live-updates.html",
                        source_name="CNBC",
                        summary="Stock futures were higher in early trading. Key inflation data and AI earnings could set the tone for the U.S. market this week.",
                        published_at="2026-11-09T02:36:00+00:00",
                    )
                ],
                quotes,
            ),
        ],
        "business": [
            _card(
                "business",
                1,
                "Nvidia launches investigation into CEO's affair with suspected Chinese spy",
                "Jensen Huang said he had been unfaithful to his wife and that he will cooperate with the company's security investigation.",
                [
                    SourceLink(
                        title="Nvidia launches investigation into CEO's affair with suspected Chinese spy",
                        url="https://www.bbc.co.uk/news/articles/c3dxw10rjn9no",
                        source_name="BBC Business",
                        summary="Jensen Huang said he had been unfaithful to his wife and that he will cooperate with the company's security investigation.",
                        published_at="2026-11-09T00:50:00+00:00",
                    )
                ],
                quotes,
            ),
            _card(
                "business",
                2,
                "US employers keep passing rising healthcare costs to workers. There are better options",
                "Choosing a healthcare plan is complicated, and charities say workers are paying a larger share of the bill than they did a few years ago.",
                [
                    SourceLink(
                        title="US employers keep passing rising healthcare costs to workers. There are better options",
                        url="https://www.theguardian.com/business/2026/nov/08/employer-healthcare-plans",
                        source_name="Guardian Business",
                        summary="Choosing a healthcare plan is complicated, and charities say workers are paying a larger share of the bill than they did a few years ago.",
                        published_at="2026-11-08T15:00:00+00:00",
                    )
                ],
                quotes,
            ),
        ],
        "world": [
            _card(
                "world",
                1,
                "Israel's president tasks Eisenkot with forming a government",
                "Israel's president officially tasked the opposition leader with forming a new government. Gadi Eisenkot ran as the main rival to Benjamin Netanyahu, but neither side won enough support to command a majority.",
                [
                    SourceLink(
                        title="Israel's president tasks Eisenkot with forming a government",
                        url="https://www.aljazeera.com/news/2026/11/8/israels-president-tasks-eisenkot-to-form-new-coalition-government",
                        source_name="Al Jazeera",
                        summary=(
                            "Israel's president officially tasks the opposition leader with forming a new government. "
                            "Gadi Eisenkot ran as the main rival to Prime Minister Benjamin Netanyahu, "
                            "but neither won enough support to command a majority."
                        ),
                        published_at="2026-11-08T18:12:00+00:00",
                    ),
                    SourceLink(
                        title="Gadi Eisenkot reaches out to Netanyahu allies as he strives to form a government",
                        url="https://www.theguardian.com/world/2026/nov/08/gadi-eisenkot-netanyahu-allies-form-israel-government",
                        source_name="The Guardian",
                        summary="Gadi Eisenkot has approached Netanyahu allies while trying to form a government.",
                        published_at="2026-11-08T17:53:00+00:00",
                    ),
                    SourceLink(
                        title="Israel's president picks Gadi Eisenkot to form a government",
                        url="https://www.theguardian.com/world/2026/nov/07/israel-president-gadi-eisenkot-form-government",
                        source_name="The Guardian",
                        summary="Israel's president picked Gadi Eisenkot to try to form the next government.",
                        published_at="2026-11-08T14:26:00+00:00",
                    ),
                ],
                quotes,
            ),
        ],
        "sports": [
            _card(
                "sports",
                1,
                "AP Top 25 poll: Georgia reclaims No. 1 spot, Ohio State plummets in college football rankings",
                "Georgia is No. 1 for the second time this season after a big win over Ole Miss and Miami's loss to Notre Dame.",
                [
                    SourceLink(
                        title="AP Top 25 poll: Georgia reclaims No. 1 spot, Ohio State plummets in college football rankings",
                        url="https://www.cbssports.com/college-football/news/college-football-rankings-ap-top-25-poll-week-11-georgia-ohio-state/",
                        source_name="CBS Sports",
                        summary="Georgia is No. 1 for the second time this season after a big win over Ole Miss and Miami's loss to Notre Dame.",
                        published_at="2026-11-08T19:41:00+00:00",
                    )
                ],
                quotes,
            ),
            _card(
                "sports",
                2,
                "Alcaraz shakes Shelton to win Paris title, continue late-season surge",
                "Carlos Alcaraz beat Ben Shelton to win the Paris Masters. Alcaraz will carry that result into the ATP Finals.",
                [
                    SourceLink(
                        title="Alcaraz shakes Shelton to win Paris title, continue late-season surge",
                        url="https://www.espn.com/tennis/story/_/id/50421284/carlos-alcaraz-beats-ben-shelton-win-paris-masters-title",
                        source_name="ESPN",
                        summary="Carlos Alcaraz beat Ben Shelton to win the Paris Masters. Alcaraz will carry that result into the ATP Finals.",
                        published_at="2026-11-08T19:35:00+00:00",
                    )
                ],
                quotes,
            ),
        ],
        "movies": [
            _card(
                "movies",
                1,
                "[This Week] Victorian Psycho",
                movie,
                [
                    SourceLink(
                        title="[This Week] Victorian Psycho",
                        url="https://www.themoviedb.org/movie/1379486",
                        source_name="TMDB",
                        summary=movie,
                        published_at="2026-11-09T03:28:00+00:00",
                    )
                ],
                quotes,
            ),
            _card(
                "movies",
                2,
                "Bluey's Daley Pearson on how losing his brother inspired his new film: 'He was the best thing ever to me'",
                "Allen is a new Netflix family film by Daley Pearson, co-founder of Ludo Studio, the company behind Bluey.",
                [
                    SourceLink(
                        title="Bluey's Daley Pearson on how losing his brother inspired his new film: 'He was the best thing ever to me'",
                        url="https://www.theguardian.com/film/ng-interactive/2026/nov/09/allen-netflix-australian-film-bluey-studio-daley-pearson-interview",
                        source_name="Guardian Film",
                        summary="Allen is a new Netflix family film by Daley Pearson, co-founder of Ludo Studio, the company behind Bluey.",
                        published_at="2026-11-08T14:00:00+00:00",
                    )
                ],
                quotes,
            ),
        ],
    }
    closing = build_closing(cards, ["[world] Pope Leo visits Argentina", "[sports] Mets re-sign pitcher Stock"], "evening")
    return ResearchBrief(
        brief_type="evening",
        created_at="2026-11-09T03:29:00+00:00",
        cards_by_domain=cards,
        closing=closing,
        watchlist_quotes=quotes,
        writer="analysis-v1",
    )


def main() -> None:
    brief = build_sample()
    preface = (
        "Sample rendered by the current writer from representative public-feed leads "
        "(headlines in the style of the November 8, 2026 run). "
        "Watchlist prices are that run's saved tape, not a live quote. "
        "Nothing here was fetched from the network when this file was generated.\n\n"
    )
    markdown = preface + render_markdown(brief)
    html = render_html(brief)
    ROOT_DOCS.mkdir(parents=True, exist_ok=True)
    (ROOT_DOCS / "sample-brief.md").write_text(markdown, encoding="utf-8")
    (ROOT_DOCS / "evening-brief.html").write_text(html, encoding="utf-8")
    print(f"Wrote {ROOT_DOCS / 'sample-brief.md'}")
    print(f"Wrote {ROOT_DOCS / 'evening-brief.html'}")


if __name__ == "__main__":
    main()
