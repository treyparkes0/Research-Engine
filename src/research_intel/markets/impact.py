from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from research_intel.markets.quotes import fetch_watchlist_quotes
from research_intel.markets.watchlist import Quote


DISCLAIMER = (
    "Educational only — not investment advice. "
    "Related tickers show sleeves people often watch with this theme; day % is context, not a forecast."
)


# Plain-language explanations keyed by symbol (1–2 sentences).
_TICKER_WHY: dict[str, str] = {
    "SPY": (
        "This kind of headline can nudge the whole U.S. stock market. "
        "SPY holds a broad basket of large American companies, so it is a simple way to see that reaction."
    ),
    "VOO": (
        "Stories like this often show up across the S&P 500. "
        "VOO tracks those same large companies, so it tends to move with the overall market mood."
    ),
    "VTI": (
        "When the news hits the wider economy or many industries at once, the whole market can feel it. "
        "VTI owns large, mid, and small U.S. stocks, so it reflects that broader backdrop."
    ),
    "SCHG": (
        "Growth companies are often more sensitive to rates, tech news, and big-picture optimism. "
        "SCHG focuses on large-cap growth names, so it can move more when those themes are in play."
    ),
    "QQQ": (
        "Tech and growth names often lead when AI, chips, or big Nasdaq stories dominate. "
        "QQQ is heavy in those companies, so it is a common place to watch that effect."
    ),
    "FNARX": (
        "Energy and resource prices can jump when oil, geopolitics, or commodity news hits. "
        "FNARX holds natural-resource companies, so it is a way to see that pressure."
    ),
    "IBB": (
        "Drug approvals, biotech headlines, and healthcare policy can move the sector quickly. "
        "IBB groups biotech stocks together, so it reflects that industry reaction."
    ),
    "CIBR": (
        "Hacks, breaches, and cybersecurity spending news can lift or shake cyber-focused firms. "
        "CIBR holds companies in that space, so it tracks how the theme is trading."
    ),
}


@dataclass
class TickerContext:
    symbol: str
    name: str
    price: float | None
    change_pct: float | None
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)

    def display_line(self) -> str:
        """Ticker + short plain-language why (no price jargon)."""
        return f"{self.symbol}: {self.reason}"


def _reason_for(symbol: str, angle: str, title: str) -> str:
    base = _TICKER_WHY.get(symbol)
    if base:
        return base
    # Fallback if a new symbol is added without a template.
    short = title.strip().rstrip(".")
    if len(short) > 90:
        short = short[:87].rsplit(" ", 1)[0] + "..."
    return (
        f"This fund is often watched when headlines like \"{short}\" land. "
        f"In short: {angle}."
    )


def _title_has(title: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(phrase)}\b", title, re.IGNORECASE) is not None


def _symbols_for_topic(themes: list[str], title: str, domain: str) -> list[tuple[str, str]]:
    """Tickers only when the headline itself is a market story. Themes are ignored."""
    del themes
    if domain in {"sports", "movies"}:
        return []

    rules: tuple[tuple[tuple[str, ...], tuple[str, ...], str], ...] = (
        (
            ("crude", "opec", "oil", "natural gas", "hormuz"),
            ("FNARX",),
            "energy prices",
        ),
        (
            ("federal reserve", "fomc", "fed", "interest rate", "interest rates", "rate cut", "rate hike", "inflation"),
            ("SPY", "SCHG"),
            "interest rates",
        ),
        (
            ("nvidia", "semiconductor", "artificial intelligence", "ai"),
            ("QQQ", "SCHG"),
            "tech and AI",
        ),
        (
            ("ransomware", "data breach", "cyberattack"),
            ("CIBR",),
            "cybersecurity",
        ),
        (
            ("fda", "drugmaker", "pharmaceutical"),
            ("IBB",),
            "biotech",
        ),
    )
    scored: dict[str, tuple[int, str]] = {}
    for phrases, symbols, angle in rules:
        if not any(_title_has(title, phrase) for phrase in phrases):
            continue
        for sym in symbols:
            score = scored.get(sym, (0, angle))[0] + 3
            scored[sym] = (score, angle)

    ordered = sorted(scored.items(), key=lambda kv: kv[1][0], reverse=True)
    return [(sym, angle) for sym, (_score, angle) in ordered[:2]]


def tickers_for_topic(
    *,
    themes: list[str],
    title: str,
    domain: str,
    quotes: list[Quote] | None = None,
) -> list[TickerContext]:
    quotes = quotes if quotes is not None else fetch_watchlist_quotes()
    by_symbol = {q.symbol: q for q in quotes}
    pairs = _symbols_for_topic(themes, title, domain)
    out: list[TickerContext] = []
    for sym, angle in pairs:
        q = by_symbol.get(sym)
        if not q:
            continue
        out.append(
            TickerContext(
                symbol=q.symbol,
                name=q.name,
                price=q.price,
                change_pct=q.change_pct,
                reason=_reason_for(sym, angle, title),
            )
        )
    return out


def fetch_quotes_once() -> list[Quote]:
    return fetch_watchlist_quotes()
