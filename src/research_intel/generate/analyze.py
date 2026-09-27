"""Analysis written only from feed leads. It does not add facts the leads do not state."""

from __future__ import annotations

import re
from html import unescape

from research_intel.ingest.enrich import Enrichment
from research_intel.process.text import jaccard, tokenize

_JUNK = re.compile(
    r"sign up|newsletter|subscribe|click here|photo:|live blog",
    re.IGNORECASE,
)


def _clean(text: str | None) -> str:
    if not text:
        return ""
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _near_duplicate(left: str, right: str) -> bool:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return True
    overlap = len(a & b) / min(len(a), len(b))
    return overlap >= 0.72


_BOILER = re.compile(
    r"tmdb audience score|early reviews and audience scores|"
    r"opens in the us/uk theatrical|theatrical release date is",
    re.IGNORECASE,
)


def collapse_repeated_text(text: str) -> str:
    """Drop a blurb that is pasted twice in one feed field."""
    words = text.split()
    if len(words) < 16:
        return text
    lowered = [word.lower() for word in words]
    for size in range(min(28, len(words) // 2), 7, -1):
        head = lowered[:size]
        for start in range(size, len(words) - size + 1):
            if lowered[start : start + size] == head:
                return " ".join(words[:start]).strip()
    return text


_SENTENCE_START = frozenset(
    "The This That Plans After In As If When While It".split()
)


def separate_glued_sentences(text: str) -> str:
    """Put a period back when a feed omits it before a new sentence."""

    def _fix(match: re.Match[str]) -> str:
        word = match.group(3)
        if word not in _SENTENCE_START:
            return match.group(0)
        return f"{match.group(1)}{match.group(2)}. {word}"

    return re.sub(r"([a-z])(['’\"]?)\s+([A-Z][a-z]+)", _fix, text)


def sentence_supports_title(title: str, sentence: str) -> bool:
    """True when the sentence is about the headline, not a neighboring story."""
    title_spec = {tok for tok in tokenize(title) if len(tok) >= 5}
    if not title_spec:
        return True
    shared = title_spec & tokenize(sentence)
    if len(shared) >= 2:
        return True
    return len(shared) == 1 and len(title_spec) <= 2


def _sentences(text: str) -> list[str]:
    cleaned = _clean(text)
    cleaned = re.sub(
        r"\b(Mr|Mrs|Ms|Dr|Inc|Ltd|Jr|Sr|Bros|U\.S|U\.K|Gen)\.",
        lambda match: match.group(0).replace(".", "\u0001"),
        cleaned,
    )
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    parts = [part.replace("\u0001", ".") for part in parts]
    out: list[str] = []
    for part in parts:
        sentence = part.strip()
        if len(sentence) < 40 or _JUNK.search(sentence):
            continue
        out.append(sentence if sentence.endswith((".", "!", "?")) else sentence + ".")
    return out


def _gather(
    title: str,
    chunks: list[tuple[str, str]],
    *,
    require_support: bool,
) -> list[tuple[str, str]]:
    facts: list[tuple[str, str]] = []
    seen: list[str] = [title]
    for name, text in chunks:
        cleaned = separate_glued_sentences(collapse_repeated_text(_clean(text)))
        for sentence in _sentences(cleaned):
            sentence = collapse_repeated_text(sentence)
            if _BOILER.search(sentence):
                continue
            if require_support and not sentence_supports_title(title, sentence):
                continue
            if any(_near_duplicate(sentence, prior) for prior in seen):
                continue
            seen.append(sentence)
            facts.append((name, sentence))
            if len(facts) >= 5:
                return facts
    return facts


def collect_facts(
    title: str,
    sources: list,
    enrichment: Enrichment | None = None,
) -> list[tuple[str, str]]:
    """Sentences from the matching article. Enrichment is used only if it stays on topic."""
    ranked = sorted(
        [src for src in sources if src.summary],
        key=lambda src: jaccard(tokenize(title), tokenize(src.title)),
        reverse=True,
    )
    chunks = [(src.source_name, src.summary) for src in ranked]
    if enrichment and enrichment.extra_text:
        chunks.append((enrichment.provider, enrichment.extra_text))

    facts = _gather(title, chunks, require_support=True)
    if facts:
        return facts
    # The labeled article can still be thin. Use that source only, never a stray enrichment hit.
    if ranked:
        return _gather(title, [(ranked[0].source_name, ranked[0].summary)], require_support=False)
    return []


def what_happened(title: str, facts: list[tuple[str, str]]) -> str:
    """Two sentences from the matching leads. The title is already the heading."""
    if not facts:
        return (
            f"The feeds only repeat the headline \"{title.rstrip('.')}.\" "
            "Open a source link for the full story."
        )
    return collapse_repeated_text(" ".join(sentence for _, sentence in facts[:2]))


_FORWARD = re.compile(
    r"\b(will|could|would|because|expected|plans|refused|rejected|leaves|forces)\b",
    re.IGNORECASE,
)


def why_it_matters(facts: list[tuple[str, str]], title: str = "") -> str:
    """A later on-topic sentence about what happens next. Empty when the leads do not say."""
    if len(facts) < 3:
        return ""
    opening = " ".join(sentence for _, sentence in facts[:2])
    for _, sentence in facts[2:]:
        if sentence in opening or _near_duplicate(sentence, opening):
            continue
        if title and not sentence_supports_title(title, sentence):
            continue
        if _FORWARD.search(sentence):
            return sentence
    return ""


def what_is_open(facts: list[tuple[str, str]], source_count: int) -> str:
    outlets = "one outlet" if source_count <= 1 else f"{source_count} outlets"
    if not facts:
        return (
            f"Only {outlets} covered this so far, and the blurb is short. "
            "It is too early to say who wins, how big the effect is, or what happens next."
        )
    forward = next(
        (
            sentence
            for _, sentence in facts
            if re.search(r"\b(will|could|ahead|next|if|unless|until)\b", sentence, re.I)
        ),
        "",
    )
    gap = (
        f"This is based on {outlets}. We still may not know the other side’s full response, "
        "how large the effect is, or the next official step unless the reporting already says so."
    )
    if forward:
        return f"{gap} One forward-looking line from the feeds: {forward}"
    return gap
