"""The personal watchlist and the shape of one quote.

Tickers here are the only symbols the brief will mention. Adding a symbol to
this list does not make it appear on a story; the headline still has to match.
"""

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


@dataclass(frozen=True)
class Quote:
    """A recent price. price and change_pct are None when the fetch failed."""
    symbol: str
    name: str
    price: float | None
    change_pct: float | None
    as_of: str | None = None
    error: str | None = None
