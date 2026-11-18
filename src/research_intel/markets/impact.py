"""Attach a watchlist ticker only when the headline is about that market.

The match is the title, not the theme tags. Sports and movies get no ticker.
Reasons describe recent context and say they are not a forecast. A story about
one company, a country-specific inflation print, or a personal headline does
not inherit a broad index.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from research_intel.markets.quotes import fetch_watchlist_quotes
from research_intel.markets.watchlist import Quote


DISCLAIMER = (
    "Educational context only — not a prediction or an investment recommendation. "
    "A ticker is shown only when the headline is about that market, sector, or company. "
    "The percentage is a recent move, not a claim that this story caused it."
)


# One sentence each. The first clause is the context; it is not a forecast.
_TICKER_WHY: dict[str, str] = {
    "SPY": "SPY is broad U.S. stock-market context, not a forecast or a claim that this story moved the fund.",
    "VOO": "VOO is broad S&P 500 context, not a forecast or a claim that this story moved the fund.",
    "VTI": "VTI is broad U.S. stock-market context, not a forecast or a claim that this story moved the fund.",
    "SCHG": "SCHG is large-cap growth context, not a forecast or a recommendation.",
    "QQQ": "QQQ is large-cap tech context for an AI, chip, or Nasdaq-related headline, not a forecast or a recommendation.",
    "FNARX": "FNARX is natural-resources context for an energy-supply headline, not a forecast or a recommendation.",
    "IBB": "IBB is biotech-sector context, not a forecast or a recommendation.",
    "CIBR": "CIBR is cybersecurity-sector context, not a forecast or a recommendation.",
}


@dataclass
class TickerContext:
    """One ticker line: symbol, recent move, and the sentence that explains why it is listed."""
    symbol: str
    name: str
    price: float | None
    change_pct: float | None
    reason: str

    def to_dict(self) -> dict:
        """Ticker line as a plain dict, for JSON."""
        return asdict(self)

    def display_line(self) -> str:
        """Ticker + short plain-language why (no price jargon)."""
        return f"{self.symbol}: {self.reason}"


def _reason_for(symbol: str, angle: str, title: str) -> str:
    """One sentence of context for a ticker, ending with not a forecast."""
    del title
    base = _TICKER_WHY.get(symbol)
    if base:
        return base
    return (
        f"{symbol} is {angle} context only. "
        "This is not a forecast or a recommendation, and it is not a claim that the headline moved the fund."
    )


def _title_has(title: str, phrase: str) -> bool:
    """True when the headline contains any of these phrases."""
    return re.search(rf"\b{re.escape(phrase)}\b", title, re.IGNORECASE) is not None


def _foreign_macro(title: str) -> bool:
    """True when the headline is about another country's rates or inflation."""
    return re.search(
        r"\b(china|chinese|eurozone|europe|uk|u\.k\.|britain|india|japan|japanese)\b",
        title,
        re.IGNORECASE,
    ) is not None


def _rates_story(title: str) -> bool:
    """True for a US rates headline, including a Fed decision."""
    if any(
        _title_has(title, phrase)
        for phrase in (
            "federal reserve",
            "fomc",
            "interest rate",
            "interest rates",
            "rate cut",
            "rate hike",
            "rate cuts",
            "rate hikes",
        )
    ):
        return True
    return bool(re.search(r"\bfed\b", title, re.I) and re.search(r"\b(rate|rates|hike|cut|powell)\b", title, re.I))


def _us_inflation_story(title: str) -> bool:
    """True for a US inflation print. A China or Europe print does not match."""
    if _foreign_macro(title):
        return False
    if any(_title_has(title, phrase) for phrase in ("cpi", "consumer price index", "ppi", "producer price")):
        return True
    has_us = re.search(r"\b(u\.s\.|usa|fed|federal|american)\b", title, re.I) or re.search(
        r"\bUS\b", title
    )
    return bool(_title_has(title, "inflation") and has_us)


def _ai_or_chip_market(title: str) -> bool:
    """Sector context for an AI or chip *market* story, not any mention of a company."""
    if _title_has(title, "artificial intelligence") or _title_has(title, "generative ai"):
        return True
    mentions_ai = re.search(r"\bai\b", title, re.I) is not None
    marketish = any(
        _title_has(title, phrase)
        for phrase in (
            "stock",
            "stocks",
            "shares",
            "earnings",
            "market",
            "chip",
            "chips",
            "nvidia",
            "microsoft",
            "google",
            "meta",
            "amazon",
            "apple",
            "device",
            "semiconductor",
        )
    )
    if mentions_ai and marketish:
        return True
    if any(
        _title_has(title, phrase)
        for phrase in ("chip stocks", "chip stock", "chip demand", "semiconductor stocks", "semiconductor shortage")
    ):
        return True
    return bool(
        _title_has(title, "nvidia")
        and any(_title_has(title, phrase) for phrase in ("earnings", "shares", "stock", "revenue", "guidance"))
    )


def _energy_story(title: str) -> bool:
    """True when the headline is about oil, gas, or a supply chokepoint."""
    return any(
        _title_has(title, phrase)
        for phrase in ("crude oil", "crude prices", "oil prices", "oil price", "opec", "natural gas", "hormuz")
    )


def _cyber_story(title: str) -> bool:
    """True for a breach, ransomware, or cyberattack headline."""
    return any(
        _title_has(title, phrase)
        for phrase in ("ransomware", "data breach", "cyberattack", "cyber attack", "cybersecurity")
    )


def _biotech_story(title: str) -> bool:
    """True for an FDA, drugmaker, or biotech headline."""
    return any(
        _title_has(title, phrase) for phrase in ("fda approval", "drugmaker", "pharmaceutical", "biotech")
    )


def _broad_market_story(title: str) -> bool:
    """True when the headline is about the stock market itself."""
    return any(
        _title_has(title, phrase)
        for phrase in ("stock market", "stock futures", "stocks rise", "stocks fall", "wall street", "s&p 500", "s&p")
    )


def _symbols_for_topic(themes: list[str], title: str, domain: str) -> list[tuple[str, str]]:
    """Tickers only when the headline itself supports that market context. Themes are ignored."""
    del themes
    if domain in {"sports", "movies"} or not title.strip():
        return []

    rules: list[tuple[bool, tuple[str, ...], str]] = [
        (_energy_story(title), ("FNARX",), "energy supply"),
        (_rates_story(title) or _us_inflation_story(title), ("SPY",), "U.S. rates or inflation"),
        (_ai_or_chip_market(title), ("QQQ",), "tech and AI"),
        (_cyber_story(title), ("CIBR",), "cybersecurity"),
        (_biotech_story(title), ("IBB",), "biotech"),
        (_broad_market_story(title), ("SPY",), "the U.S. stock market"),
    ]
    scored: dict[str, tuple[int, str]] = {}
    for matched, symbols, angle in rules:
        if not matched:
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
    """Tickers for this headline, at most two. Sports and movies return none."""
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
    """Fetch every watchlist quote a single time for this brief."""
    return fetch_watchlist_quotes()
