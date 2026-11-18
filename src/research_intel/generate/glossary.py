"""Small local glossary.

A definition is included only when the phrase appears as a whole word in the
card text. Theme names are not injected, so a story is not given a
'Geopolitics' definition just because a keyword tag fired.
"""

from __future__ import annotations

import re

# Local jargon glossary for definition slides (free, no API).
# Keys are lowercase match phrases; longer phrases are checked first.
GLOSSARY: dict[str, str] = {
    # Markets / macro
    "federal reserve": "The U.S. central bank that influences interest rates and money conditions.",
    "fomc": "Federal Open Market Committee — the Fed group that decides rate policy.",
    "interest rate": "The cost of borrowing money; higher rates usually cool spending and markets.",
    "basis points": "One basis point is 0.01%. So 25 basis points = 0.25%.",
    "bond yield": "The return an investor gets from a bond, usually shown as a yearly percent.",
    "treasury yield": "The return on U.S. government debt, watched as a signal of rate expectations.",
    "treasury": "U.S. government debt securities (bills, notes, bonds).",
    "inflation": "A general rise in prices that reduces what one dollar can buy.",
    "cpi": "Consumer Price Index — a common measure of inflation in everyday goods and services.",
    "gdp": "Gross Domestic Product — the total value of goods and services produced in an economy.",
    "recession": "A significant, widespread decline in economic activity lasting months.",
    "bull market": "A market period when prices are generally rising and sentiment is optimistic.",
    "bear market": "A market period when prices fall substantially and sentiment is pessimistic.",
    "volatility": "How much and how quickly prices move up and down.",
    "liquidity": "How easily an asset can be bought or sold without moving its price a lot.",
    "private equity": "Investment firms that buy whole companies, often with borrowed money.",
    "equity market": "The stock market — where ownership shares in companies are traded.",
    "ipo": "Initial Public Offering — when a private company first sells shares to the public.",
    "market cap": "Market capitalization — share price times shares outstanding; a size measure for a company.",
    "etf": "Exchange-Traded Fund — a basket of assets that trades like a stock.",
    "stock option": "A contract that gives the right, not the obligation, to buy or sell a stock at a set price.",
    "call option": "A contract that gives the right to buy an asset at a set price before it expires.",
    "put option": "A contract that gives the right to sell an asset at a set price before it expires.",
    "margin call": "A broker's demand for more cash when a loan used to buy investments falls short.",
    "buying on margin": "Borrowing money from a broker to buy investments, which magnifies both gains and losses.",
    "short selling": "Betting a price will fall by selling borrowed shares and buying them back later.",
    "prediction market": "A market where people trade contracts tied to the outcome of future events.",
    "cftc": "Commodity Futures Trading Commission — U.S. regulator for futures and many derivatives markets.",
    "sec": "Securities and Exchange Commission — U.S. regulator for stocks and public companies.",
    "bitcoin": "A digital cryptocurrency that can be transferred on a public blockchain.",
    "cryptocurrency": "Digital money secured by cryptography and usually recorded on a blockchain.",
    # Business
    "merger": "When two companies combine into one.",
    "acquisition": "When one company buys another.",
    "antitrust": "Laws meant to prevent monopolies and protect competition.",
    "take-private": "When investors buy a public company and remove it from the stock market.",
    "revenue": "Total sales before costs are subtracted.",
    "earnings": "Profit after expenses; often reported every quarter.",
    "guidance": "A company's own forecast for future results.",
    "supply chain": "The network that moves products from suppliers to customers.",
    "tariff": "A tax on imported goods, often used in trade policy.",
    # World / geopolitics
    "sanctions": "Penalties (often financial or trade limits) used to pressure a country or group.",
    "nato": "A military alliance of North American and European countries.",
    "geopolitics": "How geography, power, and international relationships shape world events.",
    "diplomacy": "Managing international relationships through negotiation rather than force.",
    "sovereignty": "A country's authority to govern itself without outside control.",
    "ceasefire": "A temporary or agreed pause in fighting.",
    "oligarch": "A very wealthy person with outsized political or economic influence.",
    # Sports
    "qb": "Quarterback — the offensive player who usually throws passes and directs plays.",
    "quarterback": "The offensive player who usually throws passes and directs plays.",
    "concussion": "A brain injury from a hit or jolt; often requires rest and medical clearance.",
    "practice squad": "A reserve group of players who practice with the team but are not on the main roster.",
    "free agency": "The period when players can sign with a new team after their contract ends.",
    "power rankings": "An ordered list of teams by perceived strength, often updated weekly.",
    "odi": "One-Day International — a form of cricket limited to one day / 50 overs per side.",
    "transfer window": "The limited period when clubs can buy and sell players.",
    "transfer fee": "The money one club pays another to sign a player who is under contract.",
    "contract extension": "A deal that keeps a player or coach under contract for more years.",
}


def definitions_for_text(*parts: str, limit: int = 5) -> list[str]:
    """Return 'Term: meaning' lines for jargon found in the topic text."""
    blob = " ".join(p for p in parts if p).lower()
    blob = re.sub(r"<[^>]+>", " ", blob)
    hits: list[tuple[int, str, str]] = []
    for term, meaning in GLOSSARY.items():
        if re.search(rf"\b{re.escape(term)}\b", blob):
            # Prefer longer/more specific matches.
            hits.append((len(term), term, meaning))
    hits.sort(key=lambda row: row[0], reverse=True)

    out: list[str] = []
    seen: set[str] = set()
    for _, term, meaning in hits:
        label = term.title() if term.islower() else term
        # Keep common acronyms uppercase-ish
        pretty = {
            "fomc": "FOMC",
            "cpi": "CPI",
            "gdp": "GDP",
            "ipo": "IPO",
            "etf": "ETF",
            "cftc": "CFTC",
            "sec": "SEC",
            "nato": "NATO",
            "qb": "QB",
            "odi": "ODI",
        }.get(term, label)
        if pretty.lower() in seen:
            continue
        seen.add(pretty.lower())
        out.append(f"{pretty}: {meaning}")
        if len(out) >= limit:
            break
    return out
