from __future__ import annotations

from datetime import datetime, timezone

import httpx

from research_intel.markets.watchlist import WATCHLIST, Quote

USER_AGENT = "ResearchIntelligenceEngine/0.2 (personal educational research)"


def fetch_quote(symbol: str, name: str, timeout: float = 20.0) -> Quote:
    """Educational personal-use quote pull via Yahoo chart endpoint. Not advice."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"range": "5d", "interval": "1d"}
    try:
        with httpx.Client(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        result = (payload.get("chart") or {}).get("result") or []
        if not result:
            return Quote(symbol=symbol, name=name, price=None, change_pct=None, error="No data")
        closes = [
            value
            for value in (result[0]["indicators"]["quote"][0].get("close") or [])
            if value is not None
        ]
        if not closes:
            return Quote(symbol=symbol, name=name, price=None, change_pct=None, error="No closes")
        price = float(closes[-1])
        change_pct = None
        if len(closes) >= 2 and closes[-2]:
            change_pct = (price / float(closes[-2]) - 1.0) * 100.0
        ts = result[0].get("meta", {}).get("regularMarketTime")
        as_of = (
            datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            if isinstance(ts, (int, float))
            else datetime.now(timezone.utc).isoformat()
        )
        return Quote(
            symbol=symbol,
            name=name,
            price=price,
            change_pct=change_pct,
            as_of=as_of,
        )
    except Exception as exc:  # noqa: BLE001
        return Quote(symbol=symbol, name=name, price=None, change_pct=None, error=str(exc))


def fetch_watchlist_quotes() -> list[Quote]:
    return [fetch_quote(symbol, name) for symbol, name in WATCHLIST]
