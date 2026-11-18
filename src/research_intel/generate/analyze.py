"""Turn feed blurbs into the sentences a card is allowed to say.

The paragraph comes from one article whose headline matches the card. Other
articles stay in the link list and are not blended in. Enrichment is appended
only when each sentence supports the headline. Nothing here invents a fact.
"""

from __future__ import annotations

import re
from html import unescape

from research_intel.ingest.enrich import Enrichment
from research_intel.process.text import jaccard, same_story, tokenize

_JUNK = re.compile(
    r"sign up|newsletter|subscribe|click here|photo:|live blog",
    re.IGNORECASE,
)


def _clean(text: str | None) -> str:
    """Strip HTML and collapse whitespace."""
    if not text:
        return ""
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokens(text: str) -> set[str]:
    """Lowercase words, used to spot a repeated or paraphrased sentence."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _near_duplicate(left: str, right: str) -> bool:
    """True when two sentences say the same thing in different words."""
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return True
    shared = len(a & b)
    overlap = shared / min(len(a), len(b))
    if overlap >= 0.72:
        return True
    # Paraphrase of the same blurb pasted twice (shared facts, different wording).
    return shared >= 6 and overlap >= 0.5


_ABBREV = re.compile(
    r"\b(Mr|Mrs|Ms|Dr|Inc|Ltd|Jr|Sr|U\.S|U\.K|Gen|No|St|Mt|Sen|Rep|Gov|Col|Lt|Sgt|Prof|vs|Fig)\."
)


def _protect_abbreviations(text: str) -> str:
    """Hide periods in Mr., No., U.S., and similar so they are not treated as sentence ends."""
    return _ABBREV.sub(lambda match: match.group(0).replace(".", "\u0001"), text)


def _split_sentences(text: str) -> list[str]:
    """Split on sentence punctuation after abbreviations have been protected."""
    protected = _protect_abbreviations(text)
    parts = re.split(r"(?<=[.!?])\s+", protected)
    return [part.replace("\u0001", ".").strip() for part in parts if part.strip()]


def collapse_repeated_text(text: str) -> str:
    """Drop a blurb that is pasted twice, including a close paraphrase."""
    cleaned = _clean(text)
    if not cleaned:
        return ""
    sentences = _split_sentences(cleaned)
    if len(sentences) >= 2:
        kept: list[str] = []
        for sentence in sentences:
            if any(_near_duplicate(sentence, prior) for prior in kept):
                continue
            kept.append(sentence)
        return " ".join(kept).strip()

    words = cleaned.split()
    if len(words) < 16:
        return cleaned
    lowered = [word.lower() for word in words]
    for size in range(min(28, len(words) // 2), 7, -1):
        head = lowered[:size]
        for start in range(size, len(words) - size + 1):
            if lowered[start : start + size] == head:
                return " ".join(words[:start]).strip()
    return cleaned


_SENTENCE_START = frozenset(
    "The This That Plans After In As If When While It".split()
)


def separate_glued_sentences(text: str) -> str:
    """Put a period back when a feed omits it before a new sentence."""

    def _fix(match: re.Match[str]) -> str:
        """Insert the missing period only when the next word starts a new sentence."""
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
    """Sentences from a blurb, skipping any that repeat an earlier sentence."""
    cleaned = collapse_repeated_text(separate_glued_sentences(_clean(text)))
    out: list[str] = []
    for part in _split_sentences(cleaned):
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
    """Collect on-story sentences, dropping ones that only restate the headline."""
    facts: list[tuple[str, str]] = []
    seen: list[str] = [title]
    for name, text in chunks:
        cleaned = _clean(text)
        for sentence in _sentences(cleaned):
            if require_support and not sentence_supports_title(title, sentence):
                continue
            if any(_near_duplicate(sentence, prior) for prior in seen):
                continue
            seen.append(sentence)
            facts.append((name, sentence))
            if len(facts) >= 5:
                return facts
    return facts


def _on_story(title: str, source_title: str) -> bool:
    """True when this source headline is the card's story, not a neighbor that got clustered loosely."""
    if same_story(title, source_title):
        return True
    return jaccard(tokenize(title), tokenize(source_title)) >= 0.45


def collect_facts(
    title: str,
    sources: list,
    enrichment: Enrichment | None = None,
) -> list[tuple[str, str]]:
    """
    Sentences from one on-story feed blurb.

    Other articles stay in the source list. They are not blended into the
    paragraph, so a neighboring story cannot change what the headline says.
    Enrichment is appended only when each sentence supports the headline.
    """
    ranked = sorted(
        [src for src in sources if getattr(src, "summary", None)],
        key=lambda src: (
            1 if same_story(title, src.title) else 0,
            jaccard(tokenize(title), tokenize(src.title)),
        ),
        reverse=True,
    )
    anchor = next((src for src in ranked if _on_story(title, src.title)), None)
    facts: list[tuple[str, str]] = []
    if anchor is not None:
        facts = _gather(title, [(anchor.source_name, anchor.summary)], require_support=False)
    if enrichment and enrichment.extra_text:
        extra = _gather(title, [(enrichment.provider, enrichment.extra_text)], require_support=True)
        seen = [sentence for _, sentence in facts]
        for name, sentence in extra:
            if any(_near_duplicate(sentence, prior) for prior in seen):
                continue
            facts.append((name, sentence))
            seen.append(sentence)
            if len(facts) >= 5:
                break
    return facts[:5]


def what_happened(title: str, facts: list[tuple[str, str]], *, limit: int = 2) -> str:
    """Two sentences from the matching leads. The title is already the heading."""
    if not facts:
        return (
            f"The feeds only repeat the headline \"{title.rstrip('.')}.\" "
            "Open a source link for the full story."
        )
    return collapse_repeated_text(" ".join(sentence for _, sentence in facts[:limit]))


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
    """Factual coverage note. It does not guess at missing consequences."""
    outlets = "1 outlet" if source_count <= 1 else f"{source_count} outlets"
    if not facts:
        return f"Feed coverage: {outlets}. The saved blurb does not add facts beyond the headline."
    return (
        f"Feed coverage: {outlets}. "
        "The summary uses that feed text and does not add facts from outside it."
    )
