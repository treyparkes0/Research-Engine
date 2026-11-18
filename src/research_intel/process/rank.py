"""Score events and pick the ones that make the brief.

Independent publishers are the main signal. Recency fades over 36 hours. A
real feed blurb adds a small bonus. Extra copies from the same publisher do
not raise the score. Sports and movies add a subject bonus or are dropped.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from research_intel.config import TOPICS_PER_DOMAIN
from research_intel.process.cluster import TopicCluster
from research_intel.process.movies_focus import movies_bucket, movies_focus_bonus
from research_intel.process.sports_focus import primary_bucket, sports_focus_bonus

# Independent publishers dominate. Extra copies from the same feed add nothing.
PUBLISHER_WEIGHT = 4.0
RECENCY_MAX = 5.0
RECENCY_WINDOW_HOURS = 36.0
SUBSTANCE_ONE = 1.0
SUBSTANCE_MULTI = 1.5
MIN_SUMMARY_CHARS = 80


@dataclass
class RankedTopic:
    """A scored cluster. `selected_rank` is 1-based when the story made the brief, else None."""
    cluster: TopicCluster
    score: float
    selected_rank: int | None


def _hours_ago(when: datetime, now: datetime) -> float:
    """Hours between a timestamp and now. Future times count as zero."""
    return max((now - when).total_seconds() / 3600.0, 0.0)


def _substantive(summary: str, title: str) -> bool:
    """True when the blurb is long enough to add something beyond the headline."""
    text = " ".join((summary or "").split())
    if len(text) < MIN_SUMMARY_CHARS:
        return False
    return text.lower().strip(" .") != (title or "").lower().strip(" .")


def substance_bonus(cluster: TopicCluster) -> float:
    """Reward blurbs that add information. Count each publisher once."""
    publishers_with_blurb = 0
    seen: set[int] = set()
    for article in cluster.articles:
        if article.source_id in seen:
            continue
        if _substantive(article.summary, article.title):
            seen.add(article.source_id)
            publishers_with_blurb += 1
    if publishers_with_blurb >= 2:
        return SUBSTANCE_MULTI
    if publishers_with_blurb == 1:
        return SUBSTANCE_ONE
    return 0.0


def score_cluster(
    cluster: TopicCluster,
    now: datetime | None = None,
    *,
    domain: str | None = None,
) -> float | None:
    """
    Higher is better.

    Independent publishers are the main signal. A second copy of the same
    headline from one feed does not raise the score. Recency fades to zero
    at 36 hours. A real feed blurb adds a small substance bonus. Sports and
    movies add a subject-area bonus, or return None when the cluster is out
    of scope (soccer, betting promo, non-film item).
    """
    if not cluster.articles:
        return None
    now = now or datetime.now(timezone.utc)
    sources = cluster.source_count()
    age_hours = _hours_ago(max(a.when() for a in cluster.articles), now)
    if age_hours >= RECENCY_WINDOW_HOURS:
        recency = 0.0
    else:
        recency = RECENCY_MAX * (1.0 - age_hours / RECENCY_WINDOW_HOURS)
    score = (sources * PUBLISHER_WEIGHT) + recency + substance_bonus(cluster)

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
    """Score every cluster and mark the top ones. Sports and movies use a diversity pass first."""
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
