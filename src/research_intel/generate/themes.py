from __future__ import annotations

import re
from dataclasses import dataclass

from research_intel.config import SEED_THEMES

# Simple keyword hints for free theme tagging (no AI).
THEME_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Artificial Intelligence": ("ai", "artificial intelligence", "chatgpt", "openai", "machine learning", "llm"),
    "Cybersecurity": ("cyber", "hack", "breach", "ransomware", "malware", "security"),
    "Interest Rates": ("fed", "federal reserve", "interest rate", "rate cut", "rate hike", "yield", "fomc"),
    "Consumer Spending": ("consumer", "retail sales", "spending", "shopper"),
    "Energy Markets": ("oil", "gas", "energy", "opec", "diesel", "crude", "renewable"),
    "Telecom Industry": ("telecom", "5g", "verizon", "at&t", "t-mobile", "broadband"),
    "Trade Policy": ("tariff", "trade", "import", "export", "customs", "wto"),
    "Inflation": ("inflation", "cpi", "prices rose", "cost of living"),
    "Earnings": ("earnings", "profit", "revenue", "quarterly results", "eps"),
    "Geopolitics": (
        "war",
        "ukraine",
        "russia",
        "china",
        "sanctions",
        "nato",
        "israel",
        "gaza",
        "diplomacy",
        "military",
        "greenland",
        "iran",
    ),
    "Film & Streaming": (
        "film",
        "movie",
        "cinema",
        "streaming",
        "netflix",
        "premiere",
        "trailer",
        "oscar",
        "review",
        "tmdb",
        "now playing",
        "upcoming",
    ),
    "Box Office": (
        "box office",
        "ticket sales",
        "opening weekend",
        "gross",
        "theatrical",
    ),
}


@dataclass(frozen=True)
class ThemeHit:
    name: str
    score: float


def _blob(*parts: str) -> str:
    return " ".join(p for p in parts if p).lower()


def _keyword_hit(text: str, keyword: str) -> bool:
    kw = keyword.lower()
    # Short tokens like "ai" must match as whole words (avoid "margin", "said").
    if len(kw) <= 3:
        return re.search(rf"\b{re.escape(kw)}\b", text) is not None
    return kw in text


def match_themes(*parts: str, limit: int = 3) -> list[ThemeHit]:
    text = _blob(*parts)
    hits: list[ThemeHit] = []
    for theme in SEED_THEMES:
        keywords = THEME_KEYWORDS.get(theme, (theme.lower(),))
        score = 0.0
        for kw in keywords:
            if _keyword_hit(text, kw):
                score += 1.0 + (0.25 if " " in kw else 0.0)
        if score > 0:
            hits.append(ThemeHit(name=theme, score=score))
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:limit]


def extract_explore_terms(title: str, limit: int = 5) -> list[str]:
    """Pull capitalized multi-word-ish cues from the title for further research."""
    # Keep simple proper-noun candidates from the headline.
    words = re.findall(r"[A-Z][a-zA-Z0-9&'-]+(?:\s+[A-Z][a-zA-Z0-9&'-]+)*", title)
    cleaned: list[str] = []
    skip = {
        "The", "A", "An", "And", "For", "With", "From", "After", "Over", "As", "Is",
        "US", "UK", "EU", "What", "Will", "How", "Why", "Best", "New", "Lock",
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
        "January", "February", "March", "April", "May", "June", "July", "August",
        "September", "October", "November", "December", "Today", "Sources",
    }
    for w in words:
        if w in skip or len(w) < 3:
            continue
        if w not in cleaned:
            cleaned.append(w)
        if len(cleaned) >= limit:
            break
    return cleaned
