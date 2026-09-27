from __future__ import annotations

from research_intel.config import DOMAINS
from research_intel.db import init_db


def main() -> None:
    conn = init_db()
    print("Current selected topics (from last picker run):\n")
    for domain in DOMAINS:
        rows = conn.execute(
            """
            SELECT selected_rank, label, score, article_count, source_count, as_of
            FROM topics
            WHERE domain = ? AND status = 'selected'
            ORDER BY selected_rank
            """,
            (domain,),
        ).fetchall()
        print(f"== {domain.upper()} ==")
        if not rows:
            print("  (none yet - run: python -m research_intel.jobs.pick_topics)\n")
            continue
        for row in rows:
            print(
                f"  {row['selected_rank']}. {row['label'][:100]}\n"
                f"     score={row['score']:.1f} | "
                f"{row['article_count']} articles | "
                f"{row['source_count']} sources"
            )
        print()
    conn.close()


if __name__ == "__main__":
    main()
