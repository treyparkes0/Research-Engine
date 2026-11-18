"""CLI: cluster and rank the articles already in SQLite."""

from __future__ import annotations

from research_intel.config import TOPIC_LOOKBACK_HOURS, TOPICS_PER_DOMAIN
from research_intel.db import init_db
from research_intel.process.pick_topics import run_topic_picker


def main() -> None:
    """Parse arguments and rebuild the ranked topics."""
    conn = init_db()
    print(
        f"Picking top {TOPICS_PER_DOMAIN} topics per domain "
        f"(last {TOPIC_LOOKBACK_HOURS} hours, code only - no AI)..."
    )
    results = run_topic_picker(conn)
    print("\nSelected topics:")
    for domain, ranked in results.items():
        print(f"\n== {domain.upper()} ==")
        selected = [r for r in ranked if r.selected_rank is not None]
        if not selected:
            print("  (none - try pulling more news or widening the time window)")
            continue
        for item in selected:
            c = item.cluster
            print(
                f"  {item.selected_rank}. {c.label()[:100]}\n"
                f"     score={item.score:.1f} | "
                f"{c.article_count()} articles | "
                f"{c.source_count()} sources"
            )
    conn.close()


if __name__ == "__main__":
    main()
