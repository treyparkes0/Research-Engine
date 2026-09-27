from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from research_intel.config import TOPIC_SIMILARITY_THRESHOLD
from research_intel.process.text import jaccard, tokenize, unwrap_repeated_phrase

# Shared words that should not glue unrelated headlines together.
_BOOST_SKIP = frozenset(
    """
    week weeks odds picks schedule football college sports predictions preview
    previews season game games today times world state after first years could
    would their about news report reports
    """.split()
)


@dataclass
class ArticleRef:
    id: int
    source_id: int
    title: str
    published_at: str | None
    fetched_at: str
    domain: str
    tokens: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_row(cls, row) -> ArticleRef:
        title = row["title"]
        return cls(
            id=int(row["id"]),
            source_id=int(row["source_id"]),
            title=title,
            published_at=row["published_at"],
            fetched_at=row["fetched_at"],
            domain=row["domain"],
            tokens=tokenize(title),
        )

    def when(self) -> datetime:
        raw = self.published_at or self.fetched_at
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            dt = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt


@dataclass
class TopicCluster:
    articles: list[ArticleRef] = field(default_factory=list)
    token_union: frozenset[str] = field(default_factory=frozenset)

    def add(self, article: ArticleRef) -> None:
        self.articles.append(article)
        self.token_union = self.token_union | article.tokens

    def best_similarity(self, article: ArticleRef) -> float:
        # Compare only to the closest headline. The token union grows as
        # unrelated stories get chained on, so it is not used for the score.
        if not self.articles:
            return 0.0
        closest = max(
            self.articles,
            key=lambda other: jaccard(article.tokens, other.tokens),
        )
        base = jaccard(article.tokens, closest.tokens)

        # Boost when two specific shared words match (names, places, teams).
        rare_hits = {
            tok
            for tok in article.tokens & closest.tokens
            if len(tok) >= 5 and tok not in _BOOST_SKIP
        }
        if len(rare_hits) >= 2:
            base = min(1.0, base + 0.12)
        return base

    def label(self) -> str:
        # Prefer a recent, reasonably short title as the human-readable label.
        ranked = sorted(
            self.articles,
            key=lambda a: (len(a.title), -a.when().timestamp()),
        )
        return unwrap_repeated_phrase(ranked[0].title.strip())

    def first_seen(self) -> str:
        return min(a.when() for a in self.articles).isoformat()

    def last_seen(self) -> str:
        return max(a.when() for a in self.articles).isoformat()

    def source_count(self) -> int:
        return len({a.source_id for a in self.articles})

    def article_count(self) -> int:
        return len(self.articles)


def cluster_articles(
    articles: list[ArticleRef],
    threshold: float = TOPIC_SIMILARITY_THRESHOLD,
) -> list[TopicCluster]:
    """Greedy title clustering — free, local, no AI."""
    usable = [a for a in articles if a.tokens]
    usable.sort(key=lambda a: a.when(), reverse=True)

    clusters: list[TopicCluster] = []
    for article in usable:
        best_idx = -1
        best_score = 0.0
        for idx, cluster in enumerate(clusters):
            score = cluster.best_similarity(article)
            if score > best_score:
                best_score = score
                best_idx = idx
        if best_idx >= 0 and best_score >= threshold:
            clusters[best_idx].add(article)
        else:
            cluster = TopicCluster()
            cluster.add(article)
            clusters.append(cluster)
    return clusters
