from __future__ import annotations

from dataclasses import dataclass

# Personal watchlist for market-impact context (education only, not advice).
# FNAR was requested but is not a valid common ticker; FNARX is used instead.
WATCHLIST: tuple[tuple[str, str], ...] = (
    ("SPY", "S&P 500 ETF"),
    ("VOO", "S&P 500 (Vanguard)"),
    ("VTI", "Total US stock market"),
    ("SCHG", "Schwab US Large-Cap Growth"),
    ("QQQ", "Nasdaq-100 / large growth-tech"),
    ("FNARX", "Fidelity Natural Resources (FNAR request)"),
    ("IBB", "Biotech"),
    ("CIBR", "Cybersecurity"),
)


# Theme/domain cues -> which tickers are most relevant to discuss.
IMPACT_MAP: dict[str, tuple[str, ...]] = {
    "Artificial Intelligence": ("QQQ", "SCHG", "SPY", "VOO"),
    "Cybersecurity": ("CIBR", "QQQ", "SCHG"),
    "Interest Rates": ("SCHG", "QQQ", "SPY", "VOO", "VTI"),
    "Inflation": ("FNARX", "SPY", "VTI"),
    "Energy Markets": ("FNARX", "SPY", "VTI"),
    "Earnings": ("SPY", "VOO", "QQQ", "SCHG"),
    "Trade Policy": ("SPY", "VOO", "VTI", "QQQ"),
    "Geopolitics": ("SPY", "VOO", "VTI", "FNARX"),
    "Consumer Spending": ("SPY", "VOO", "VTI"),
    "biotech": ("IBB", "SPY"),
    "health": ("IBB", "SPY"),
    "oil": ("FNARX", "SPY"),
    "cyber": ("CIBR", "QQQ"),
    "tech": ("QQQ", "SCHG", "SPY"),
    "growth": ("SCHG", "QQQ"),
}


@dataclass(frozen=True)
class Quote:
    symbol: str
    name: str
    price: float | None
    change_pct: float | None
    as_of: str | None = None
    error: str | None = None
