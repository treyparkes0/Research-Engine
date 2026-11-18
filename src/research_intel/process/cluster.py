"""Group recent headlines into events.

Articles join a cluster only when `same_story` says they are the same event,
or when the titles are near-copies (token overlap of 0.82 or higher). The
cluster label is the newest headline, which is the development the card should
stand for.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from research_intel.config import TOPIC_SIMILARITY_THRESHOLD
from research_intel.process.text import jaccard, same_story, tokenize, unwrap_repeated_phrase


@dataclass
class ArticleRef:
    """One stored article, light enough to cluster without holding the whole row."""
    id: int
    source_id: int
    title: str
    published_at: str | None
    fetched_at: str
    domain: str
    tokens: frozenset[str] = field(default_factory=frozenset)
    summary: str = ""

    @classmethod
    def from_row(cls, row) -> ArticleRef:
        """Build a ref from a SQLite row. Summary is optional for older queries."""
        title = row["title"]
        try:
            summary = row["summary"] or ""
        except (KeyError, IndexError, TypeError):
            summary = ""
        return cls(
            id=int(row["id"]),
            source_id=int(row["source_id"]),
            title=title,
            published_at=row["published_at"],
            fetched_at=row["fetched_at"],
            domain=row["domain"],
            tokens=tokenize(title),
            summary=summary,
        )

    def when(self) -> datetime:
        """Publication time. Unparseable dates sort as ancient, not as 'just now'."""
        for raw in (self.published_at, self.fetched_at):
            if not raw:
                continue
            try:
                dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        return datetime.min.replace(tzinfo=timezone.utc)


@dataclass
class TopicCluster:
    """Headlines that describe one event. Compared one title at a time, not as a growing bag of words."""
    articles: list[ArticleRef] = field(default_factory=list)
    token_union: frozenset[str] = field(default_factory=frozenset)

    def add(self, article: ArticleRef) -> None:
        """Attach an article and keep the union of its title tokens."""
        self.articles.append(article)
        self.token_union = self.token_union | article.tokens

    def best_similarity(self, article: ArticleRef) -> float:
        # Compare only to individual headlines. The token union grows as
        # unrelated stories get chained on, so it is not used for the score.
        """How well this headline fits the cluster. 1.0 means it is the same event."""
        if not self.articles:
            return 0.0
        best = 0.0
        for other in self.articles:
            if same_story(article.title, other.title):
                return 1.0
            best = max(best, jaccard(article.tokens, other.tokens))
        return best

    def label(self) -> str:
        # The latest headline is the development the card should stand for.
        """The newest headline, which is the development the card should use."""
        ranked = sorted(self.articles, key=lambda article: article.when(), reverse=True)
        return unwrap_repeated_phrase(ranked[0].title.strip())

    def first_seen(self) -> str:
        """Earliest usable timestamp in the cluster."""
        return min(a.when() for a in self.articles).isoformat()

    def last_seen(self) -> str:
        """Latest usable timestamp in the cluster."""
        return max(a.when() for a in self.articles).isoformat()

    def source_count(self) -> int:
        """How many distinct publishers are in the cluster. Duplicate rows from one feed count once."""
        return len({a.source_id for a in self.articles})

    def article_count(self) -> int:
        """How many article rows are in the cluster, including repeats from the same publisher."""
        return len(self.articles)


def cluster_articles(
    articles: list[ArticleRef],
    threshold: float = TOPIC_SIMILARITY_THRESHOLD,
) -> list[TopicCluster]:
    """Walk headlines newest-first and attach each one to the closest matching event."""
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
        # Same-event headlines score 1.0. Raw overlap merges only near-copies.
        # The configured threshold cannot fall below 0.82; a 0.28 bar was
        # chaining unrelated stories that happened to share two words.
        overlap_bar = max(threshold, 0.82)
        if best_idx >= 0 and best_score >= overlap_bar:
            clusters[best_idx].add(article)
        else:
            cluster = TopicCluster()
            cluster.add(article)
            clusters.append(cluster)
    return clusters
