"""Headline text helpers used by clustering and dedup.

Tokenizing strips stopwords. `same_story` decides whether two headlines are
one event. It requires a shared name plus a second detail, and it refuses
parallel headlines that name different subjects (Fed vs ECB).
"""

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
    """Lowercase the title and strip movie tags like [This Week] so they do not glue films together."""
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


# Words that show up across unrelated headlines and must not glue them together.
GLUE_TOKENS = frozenset(
    """
    week weeks odds picks schedule sports predictions preview previews season
    game games today times after first years year could would their about news
    report reports said says saying update updates live ahead watch watching
    big top best new day days win wins won loss losses over under versus into
    from with that this have has had been being were was will can may might
    just than then also more most some any all out not but its they them his
    her she him who what when where why how holds hold held steady rise rises
    rose fall falls fell high low higher lower plan plans planned expected
    expect thing things amid near still back next last amid
    """.split()
)

# Capitalized words that are too common to prove two headlines are one event.
GENERIC_PROPER = frozenset(
    """
    new york white house united states north south east west city president
    minister government national international world week report news today
    day days state american america sunday monday tuesday wednesday thursday
    friday saturday january february march april may june july august
    september october november december
    """.split()
)

_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’&-]*")
_SENTENCE_STARTERS = frozenset(
    """
    a an the and or but if in on at to for of from by with as this that these
    those it its they we you he she his her their after before over when where
    why how what who which while during amid here there
    """.split()
)


def tokenize(title: str) -> frozenset[str]:
    """Content words from a title. Short words and stopwords are dropped."""
    tokens = {
        tok
        for tok in _TOKEN_RE.findall(normalize_title(title))
        if len(tok) > 2 and tok not in STOPWORDS
    }
    return frozenset(tokens)


def content_tokens(title: str) -> frozenset[str]:
    """Headline tokens with glue words removed, for same-story checks."""
    return frozenset(tok for tok in tokenize(title) if tok not in GLUE_TOKENS and not tok.isdigit())


def _norm_word(word: str) -> str:
    """Lowercase a word and drop a trailing possessive ('s)."""
    word = word.lower().replace("’", "'")
    if word.endswith("'s"):
        word = word[:-2]
    return re.sub(r"[^a-z0-9]", "", word)


def proper_tokens(title: str) -> frozenset[str]:
    """Capitalized tokens from the raw headline (names, places, tickers)."""
    text = re.sub(
        r"^\[(?:This Week|Now Playing|Upcoming|Trending)\]\s+",
        "",
        (title or "").strip(),
        flags=re.I,
    )
    found: set[str] = set()
    words = _WORD_RE.findall(text)
    for index, word in enumerate(words):
        letters = re.sub(r"[^A-Za-z]", "", word)
        if not letters:
            continue
        is_acronym = letters.isupper() and len(letters) >= 2
        is_name = letters[0].isupper() and not letters.isupper()
        if not is_acronym and not is_name:
            continue
        if index == 0 and not is_acronym and letters.lower() in _SENTENCE_STARTERS:
            continue
        token = _norm_word(word)
        if len(token) <= 1 or token in STOPWORDS or token in _SENTENCE_STARTERS:
            continue
        if not is_acronym and len(token) < 3:
            continue
        found.add(token)
    return frozenset(found)


def _soft_share(left: frozenset[str], right: frozenset[str]) -> frozenset[str]:
    """Exact overlap, plus a shared 8-character stem (investigation / investigates)."""
    shared = set(left & right)
    for token_a in left:
        if len(token_a) < 8:
            continue
        for token_b in right:
            if token_a == token_b or len(token_b) < 8:
                continue
            if token_a[:8] == token_b[:8]:
                shared.add(token_a)
    return frozenset(shared)


def same_story(left: str, right: str) -> bool:
    """
    True when two headlines are the same event, not merely the same theme.

    Parallel headlines with different named subjects stay apart
    ("Fed holds rates" vs "ECB holds rates"). Shared names are not enough
    without a second overlapping detail ("Apple earnings" vs "Apple opens a store").
    """
    if not left or not right:
        return False
    if normalize_title(left) == normalize_title(right) and normalize_title(left):
        return True

    left_content = content_tokens(left)
    right_content = content_tokens(right)
    if len(left_content) < 2 or len(right_content) < 2:
        return False

    shared = _soft_share(left_content, right_content)
    if len(shared) < 2:
        return False
    jaccard_score = len(shared) / len(left_content | right_content)

    left_anchors = proper_tokens(left) - GENERIC_PROPER
    right_anchors = proper_tokens(right) - GENERIC_PROPER
    shared_anchors = left_anchors & right_anchors
    # Both headlines name a subject, and the subjects do not overlap.
    if left_anchors and right_anchors and not shared_anchors:
        return False

    non_anchor = shared - shared_anchors - GENERIC_PROPER
    long_detail = any(len(token) >= 6 for token in non_anchor)
    if len(shared_anchors) >= 2 and len(shared) >= 2:
        return True
    if shared_anchors and len(non_anchor) >= 2 and jaccard_score >= 0.2:
        return True
    if shared_anchors and long_detail and jaccard_score >= 0.18:
        return True
    if not left_anchors and not right_anchors and jaccard_score >= 0.62 and len(shared) >= 3:
        return True
    return False


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Overlap of two token sets, from 0 (nothing shared) to 1 (identical)."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    return inter / len(a | b)
