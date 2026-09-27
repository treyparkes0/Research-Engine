"""Sports preference: boost preferred US leagues, drop soccer."""

from __future__ import annotations

import re

# Hard drop — soccer / football (association) noise from general sport wires.
SOCCER_PATTERNS: tuple[str, ...] = (
    r"\bsoccer\b",
    r"\bmls\b",
    r"\bpremier league\b",
    r"\bepl\b",
    r"\bla liga\b",
    r"\bserie a\b",
    r"\bbundesliga\b",
    r"\bligue 1\b",
    r"\bchampions league\b",
    r"\buefa\b",
    r"\bworld cup\b",
    r"\bfifa\b",
    r"\bmancity\b",
    r"\bmanchester (united|city)\b",
    r"\bliverpool\b",
    r"\barsenal\b",
    r"\bchelsea\b",
    r"\btottenham\b",
    r"\breal madrid\b",
    r"\bbarcelona\b",
    r"\bpsg\b",
    r"\binter miami\b",
    r"\bwomen'?s world cup\b",
    r"\bfa cup\b",
    r"\bnwsl\b",
    r"\btransfer window\b",
)

# Preferred coverage buckets (title/summary keyword hits).
PREFERRED_BUCKETS: tuple[tuple[str, tuple[str, ...], float], ...] = (
    (
        "nfl",
        (
            "nfl",
            "super bowl",
            "touchdown",
            "quarterback",
            "monday night football",
            "thursday night football",
            "afc",
            "nfc",
        ),
        3.5,
    ),
    (
        "college_football",
        (
            "college football",
            "ncaaf",
            "cfb",
            "big ten",
            "big 12",
            "heisman",
            "college game day",
            "sec championship",
            "cfp",
        ),
        3.2,
    ),
    (
        "nba",
        ("nba", "nba finals", "all-star"),
        3.0,
    ),
    (
        "march_madness",
        (
            "march madness",
            "ncaa tournament",
            "ncaa basketball",
            "final four",
            "sweet 16",
            "elite eight",
            "selection sunday",
            "college basketball",
            "ncaab",
        ),
        3.5,
    ),
    (
        "tennis",
        (
            "tennis",
            "atp",
            "wta",
            "grand slam",
            "wimbledon",
            "us open",
            "french open",
            "australian open",
            "roland garros",
        ),
        2.8,
    ),
    (
        "hockey",
        ("nhl", "hockey", "stanley cup", "power play", "hat trick"),
        2.8,
    ),
    (
        "ufc",
        ("ufc", "mma", "octagon", "pay-per-view", "ppv"),
        2.8,
    ),
    (
        "mets",
        (
            "mets",
            "new york mets",
            "citi field",
            "francisco lindor",
            "pete alonso",
        ),
        4.0,
    ),
)

# Non-Mets baseball is allowed lightly; do not let it crowd out preferred sports.
OTHER_BASEBALL = (
    "mlb",
    "baseball",
    "world series",
    "yankees",
    "dodgers",
    "red sox",
    "home run",
    "pitcher",
)

_SOCCER_RE = [re.compile(p, re.I) for p in SOCCER_PATTERNS]


def _blob(*parts: str) -> str:
    return " ".join(p for p in parts if p).lower()


_PROMO_RE = re.compile(
    r"\b("
    r"sportsbooks?|draftkings|fanduel|betmgm|bet365|caesars|fanatics|"
    r"betting apps?|betting promos?|how to bet|promo codes?|bonuses|"
    r"sportsbook"
    r")\b",
    re.I,
)


def is_betting_promo(*parts: str) -> bool:
    """Affiliate betting-app copy, not a game story."""
    return _PROMO_RE.search(_blob(*parts)) is not None


def is_soccer(*parts: str) -> bool:
    text = _blob(*parts)
    return any(rx.search(text) for rx in _SOCCER_RE)


def is_mets_baseball(*parts: str) -> bool:
    text = _blob(*parts)
    return any(re.search(rf"\b{re.escape(k)}\b", text) for k in PREFERRED_BUCKETS[-1][1])


def is_other_baseball(*parts: str) -> bool:
    text = _blob(*parts)
    if is_mets_baseball(text):
        return False
    return any(re.search(rf"\b{re.escape(k)}\b", text) for k in OTHER_BASEBALL)


def primary_bucket(*parts: str) -> str | None:
    """Best-matching preferred bucket name, or None for soccer."""
    if is_soccer(*parts):
        return None
    text = _blob(*parts)
    best_name: str | None = None
    best_weight = -1.0
    for name, keywords, weight in PREFERRED_BUCKETS:
        if any(re.search(rf"\b{re.escape(k)}\b", text) for k in keywords):
            if weight > best_weight:
                best_weight = weight
                best_name = name
    if best_name:
        return best_name
    if is_other_baseball(text):
        return "mlb_other"
    return "other"


def sports_focus_bonus(*parts: str) -> float | None:
    """
    Additive score for topic ranking.
    Returns None when the item should be dropped (soccer).
    """
    if is_soccer(*parts) or is_betting_promo(*parts):
        return None
    text = _blob(*parts)
    bonus = 0.0
    for _name, keywords, weight in PREFERRED_BUCKETS:
        if any(re.search(rf"\b{re.escape(k)}\b", text) for k in keywords):
            bonus = max(bonus, weight)
    if is_other_baseball(text):
        bonus = max(bonus, 0.4)
    if bonus == 0.0:
        # Unclassified sports (cricket, golf, F1, etc.) — soft demote.
        bonus = -2.0
    return bonus
