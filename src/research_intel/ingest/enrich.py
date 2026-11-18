"""Optional longer blurbs from Guardian, NYT, and NewsAPI.

Used only when a key is set. A hit is kept only when its headline is the same
story as the card, not merely the same person. If no key is set, this module
returns nothing and the brief uses the RSS blurb alone.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from html import unescape

import httpx

from research_intel.process.text import tokenize

USER_AGENT = "ResearchIntelligenceEngine/0.4 (personal educational research)"

# Words that show up in many headlines and should not count as a match.
_GENERIC = frozenset(
    """
    week weeks odds picks news says after first world times today game games
    season state could would their about report reports view editorial
    """.split()
)


@dataclass
class Enrichment:
    """A longer blurb from an optional API, kept only when the headline matches."""
    provider: str
    extra_text: str
    url: str = ""


def _guardian_key() -> str:
    """Guardian key, or empty when that API is off."""
    return (os.getenv("GUARDIAN_API_KEY") or "").strip()


def _newsapi_key() -> str:
    """NewsAPI key, or empty when that API is off."""
    return (os.getenv("NEWS_API_KEY") or "").strip()


def _nyt_key() -> str:
    """New York Times key, or empty when that API is off."""
    return (os.getenv("NYT_API_KEY") or os.getenv("NYTIMES_API_KEY") or "").strip()


def headline_matches(topic: str, headline: str) -> bool:
    """True when an API hit is about the same story, not just the same person."""
    topic_spec = {
        tok
        for tok in tokenize(topic)
        if len(tok) >= 5 and tok not in _GENERIC
    }
    hit_spec = {
        tok
        for tok in tokenize(headline)
        if len(tok) >= 5 and tok not in _GENERIC
    }
    if len(topic_spec) < 2 or not hit_spec:
        return False
    shared = topic_spec & hit_spec
    if len(shared) < 2:
        return False
    return len(shared) / len(topic_spec) >= 0.34


def _clean(text: str) -> str:
    """Strip HTML and collapse whitespace in an API blurb."""
    text = unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def enrich_topic(title: str, timeout: float = 20.0) -> Enrichment | None:
    """
    Pull longer blurbs from free/personal news APIs to deepen analysis cards.
    Tries Guardian, then NYT, then NewsAPI. Returns the first useful hit,
    or a merged blurb if multiple return text.
    """
    hits: list[Enrichment] = []
    if _guardian_key():
        hit = _enrich_guardian(title, timeout=timeout)
        if hit:
            hits.append(hit)
    if _nyt_key():
        hit = _enrich_nyt(title, timeout=timeout)
        if hit:
            hits.append(hit)
    if _newsapi_key():
        hit = _enrich_newsapi(title, timeout=timeout)
        if hit:
            hits.append(hit)

    if not hits:
        return None
    if len(hits) == 1:
        return hits[0]

    # Merge unique sentences from multiple free sources.
    chunks: list[str] = []
    seen: set[str] = set()
    providers: list[str] = []
    url = ""
    for hit in hits:
        providers.append(hit.provider)
        url = url or hit.url
        for part in re.split(r"(?<=[.!?])\s+", hit.extra_text):
            key = part.lower().strip()
            if len(key) < 40 or key in seen:
                continue
            seen.add(key)
            chunks.append(part.strip())
            if len(chunks) >= 4:
                break
        if len(chunks) >= 4:
            break
    if not chunks:
        return hits[0]
    return Enrichment(
        provider="+".join(providers),
        extra_text=" ".join(chunks),
        url=url,
    )


def _enrich_guardian(title: str, timeout: float) -> Enrichment | None:
    """One Guardian match for this headline, or None."""
    url = "https://content.guardianapis.com/search"
    params = {
        "api-key": _guardian_key(),
        "q": title[:120],
        "page-size": 3,
        "show-fields": "trailText,headline,standfirst",
        "order-by": "relevance",
    }
    try:
        with httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            results = response.json().get("response", {}).get("results") or []
        chunks: list[str] = []
        link = ""
        for item in results[:2]:
            fields = item.get("fields") or {}
            headline = _clean(fields.get("headline") or item.get("webTitle") or "")
            if not headline_matches(title, headline):
                continue
            for key in ("standfirst", "trailText"):
                value = _clean(fields.get(key) or "")
                if value:
                    chunks.append(value)
            link = link or item.get("webUrl") or ""
        text = " ".join(chunks).strip()
        if not text:
            return None
        return Enrichment(provider="guardian", extra_text=text, url=link)
    except Exception:
        return None


def _enrich_nyt(title: str, timeout: float) -> Enrichment | None:
    # NYT Article Search — free non-commercial developer key.
    # Usually returns headline + abstract + URL, not full body text.
    """One New York Times match for this headline, or None."""
    url = "https://api.nytimes.com/svc/search/v2/articlesearch.json"
    params = {
        "q": title[:100],
        "api-key": _nyt_key(),
        "sort": "relevance",
    }
    try:
        with httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            docs = response.json().get("response", {}).get("docs") or []
        chunks: list[str] = []
        link = ""
        for item in docs[:2]:
            headline = _clean(((item.get("headline") or {}).get("main") or ""))
            if not headline_matches(title, headline):
                continue
            abstract = _clean(item.get("abstract") or item.get("snippet") or "")
            lead = _clean(item.get("lead_paragraph") or "")
            for value in (abstract, lead):
                if value:
                    chunks.append(value)
            link = link or item.get("web_url") or ""
        text = " ".join(chunks).strip()
        if not text:
            return None
        return Enrichment(provider="nyt", extra_text=text, url=link)
    except Exception:
        return None


def _enrich_newsapi(title: str, timeout: float) -> Enrichment | None:
    """One NewsAPI match for this headline, or None."""
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": title[:100],
        "pageSize": 3,
        "sortBy": "relevancy",
        "language": "en",
        "apiKey": _newsapi_key(),
    }
    try:
        with httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            articles = response.json().get("articles") or []
        chunks: list[str] = []
        link = ""
        for item in articles[:2]:
            headline = _clean(item.get("title") or "")
            if not headline_matches(title, headline):
                continue
            for key in ("description", "content"):
                value = _clean(item.get(key) or "")
                if value and value != "[Removed]":
                    value = value.split(" [+")[0].strip()
                    chunks.append(value)
            link = link or item.get("url") or ""
        text = " ".join(chunks).strip()
        if not text:
            return None
        return Enrichment(provider="newsapi", extra_text=text, url=link)
    except Exception:
        return None


def api_status() -> str:
    """Which optional API keys are present. Does not call the APIs."""
    parts = []
    if _guardian_key():
        parts.append("guardian")
    if _nyt_key():
        parts.append("nyt")
    if _newsapi_key():
        parts.append("newsapi")
    return ",".join(parts) if parts else "none"
