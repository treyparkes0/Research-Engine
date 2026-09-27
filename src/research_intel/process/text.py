from __future__ import annotations

import re

STOPWORDS = frozenset(
    """
    a an the and or but if in on at to for of from by with as is are was were be been being
    this that these those it its they them their we our you your he she his her
    about into over after before under again further then once here there when where why how
    all any both each few more most other some such no nor not only own same so than too very
    can will just don should now also new says say said amid after ahead near still
    report reports reuters bbc npr ap update live breaking news analysis opinion
    guardian editorial view column commentary letters
    """.split()
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def normalize_title(title: str) -> str:
    text = title.lower()
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&amp;", "and")
    # Strip TMDB brief tags so they do not glue unrelated movies together.
    text = re.sub(
        r"\[(this week|now playing|upcoming|trending)\]\s*",
        " ",
        text,
        flags=re.I,
    )
    return re.sub(r"\s+", " ", text).strip()


def unwrap_repeated_phrase(title: str) -> str:
    """Turn 'Your Mother Your Mother Your Mother' into 'Your Mother'."""
    raw = (title or "").strip()
    prefix = ""
    match = re.match(r"^(\[(?:This Week|Now Playing|Upcoming|Trending)\]\s+)", raw, re.I)
    body = raw
    if match:
        prefix = match.group(1)
        body = raw[match.end() :]
    words = body.split()
    for size in range(1, len(words) // 2 + 1):
        if len(words) % size:
            continue
        times = len(words) // size
        chunk = words[:size]
        if times >= 2 and words == chunk * times:
            return prefix + " ".join(chunk)
    return raw


def tokenize(title: str) -> frozenset[str]:
    tokens = {
        tok
        for tok in _TOKEN_RE.findall(normalize_title(title))
        if len(tok) > 2 and tok not in STOPWORDS
    }
    return frozenset(tokens)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    return inter / len(a | b)
