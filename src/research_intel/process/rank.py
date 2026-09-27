from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from research_intel.config import TOPICS_PER_DOMAIN
from research_intel.process.cluster import TopicCluster
from research_intel.process.movies_focus import movies_bucket, movies_focus_bonus
from research_intel.process.sports_focus import primary_bucket, sports_focus_bonus


@dataclass
class RankedTopic:
    cluster: TopicCluster
    score: float
    selected_rank: int | None


def _hours_ago(when: datetime, now: datetime) -> float:
    return max((now - when).total_seconds() / 3600.0, 0.0)


def score_cluster(
    cluster: TopicCluster,
    now: datetime | None = None,
    *,
    domain: str | None = None,
) -> float | None:
    """
    Higher is better.
    Rewards multiple outlets covering the same story, more articles,
    and fresher coverage. Sports domain applies league preferences.
    Returns None when the cluster should be dropped (e.g. soccer).
    """
    now = now or datetime.now(timezone.utc)
    sources = cluster.source_count()
    articles = cluster.article_count()
    age_hours = _hours_ago(max(a.when() for a in cluster.articles), now)

    # Newer stories get up to +5; older than ~36h fade toward 0.
    recency = max(0.0, 5.0 - (age_hours / 7.2))
    score = (sources * 3.0) + (articles * 1.0) + recency

    if domain == "sports":
        titles = [a.title for a in cluster.articles]
        bonus = sports_focus_bonus(*titles)
        if bonus is None:
            return None
        score += bonus
    elif domain == "movies":
        titles = [a.title for a in cluster.articles]
        bonus = movies_focus_bonus(*titles)
        if bonus is None:
            return None
        score += bonus
    return score


def _select_with_sports_diversity(
    scored: list[tuple[float, TopicCluster]],
    limit: int,
) -> list[tuple[float, TopicCluster, int | None]]:
    """
    Pick top topics while spreading across preferred sports buckets
    so NFL does not fill every slot.
    """
    selected: list[tuple[float, TopicCluster, int | None]] = []
    used_buckets: set[str] = set()
    remaining = list(scored)

    # Pass 1: one story per preferred bucket (highest score in that bucket).
    for score, cluster in list(remaining):
        if len(selected) >= limit:
            break
        # Classify from the display label so dual-topic headlines in the
        # cluster (e.g. NFL + CFB power rankings) do not steal the wrong slot.
        bucket = primary_bucket(cluster.label()) or "other"
        if bucket in {"other", "mlb_other"}:
            continue
        if bucket in used_buckets:
            continue
        used_buckets.add(bucket)
        selected.append((score, cluster, None))
        remaining.remove((score, cluster))

    # Pass 2: fill remaining slots by score (allow second NFL, etc.).
    for score, cluster in remaining:
        if len(selected) >= limit:
            break
        selected.append((score, cluster, None))

    # Attach ranks; leftover unselected stay as candidates below.
    out: list[tuple[float, TopicCluster, int | None]] = []
    chosen_ids = {id(c) for _, c, _ in selected}
    for idx, (score, cluster, _) in enumerate(selected):
        out.append((score, cluster, idx + 1))
    for score, cluster in scored:
        if id(cluster) in chosen_ids:
            continue
        out.append((score, cluster, None))
    return out


def _select_with_movies_diversity(
    scored: list[tuple[float, TopicCluster]],
    limit: int,
) -> list[tuple[float, TopicCluster, int | None]]:
    """Spread across this-week releases, reviews, and industry news."""
    selected: list[tuple[float, TopicCluster, int | None]] = []
    used_buckets: set[str] = set()
    remaining = list(scored)
    preferred = ("this_week", "review", "industry")

    for want in preferred:
        for score, cluster in list(remaining):
            if len(selected) >= limit:
                break
            bucket = movies_bucket(cluster.label())
            if bucket != want:
                continue
            if bucket in used_buckets:
                continue
            used_buckets.add(bucket)
            selected.append((score, cluster, None))
            remaining.remove((score, cluster))
            break

    for score, cluster in remaining:
        if len(selected) >= limit:
            break
        selected.append((score, cluster, None))

    out: list[tuple[float, TopicCluster, int | None]] = []
    chosen_ids = {id(c) for _, c, _ in selected}
    for idx, (score, cluster, _) in enumerate(selected):
        out.append((score, cluster, idx + 1))
    for score, cluster in scored:
        if id(cluster) in chosen_ids:
            continue
        out.append((score, cluster, None))
    return out


def rank_and_select(
    clusters: list[TopicCluster],
    limit: int = TOPICS_PER_DOMAIN,
    now: datetime | None = None,
    *,
    domain: str | None = None,
) -> list[RankedTopic]:
    now = now or datetime.now(timezone.utc)
    scored_pairs: list[tuple[float, TopicCluster]] = []
    for cluster in clusters:
        score = score_cluster(cluster, now, domain=domain)
        if score is None:
            continue
        scored_pairs.append((score, cluster))
    scored = sorted(scored_pairs, key=lambda pair: pair[0], reverse=True)

    if domain == "sports":
        ordered = _select_with_sports_diversity(scored, limit)
        return [
            RankedTopic(cluster=cluster, score=score, selected_rank=rank)
            for score, cluster, rank in ordered
        ]

    if domain == "movies":
        ordered = _select_with_movies_diversity(scored, limit)
        return [
            RankedTopic(cluster=cluster, score=score, selected_rank=rank)
            for score, cluster, rank in ordered
        ]

    ranked: list[RankedTopic] = []
    for idx, (score, cluster) in enumerate(scored):
        selected_rank = idx + 1 if idx < limit else None
        ranked.append(
            RankedTopic(cluster=cluster, score=score, selected_rank=selected_rank)
        )
    return ranked
