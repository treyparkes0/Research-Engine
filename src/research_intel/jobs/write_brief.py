"""CLI: write a Markdown and JSON brief from the current selected topics."""

from __future__ import annotations

import argparse

from research_intel.db import init_db
from research_intel.generate.brief import build_brief, save_brief


def main(argv: list[str] | None = None) -> None:
    """Parse arguments and write one brief."""
    parser = argparse.ArgumentParser(description="Write a research brief from selected topics")
    parser.add_argument(
        "brief_type",
        nargs="?",
        default="evening",
        choices=("morning", "evening"),
        help="morning or evening (default: evening)",
    )
    args = parser.parse_args(argv)

    conn = init_db()
    selected = conn.execute(
        "SELECT COUNT(*) AS n FROM topics WHERE status = 'selected'"
    ).fetchone()["n"]
    if selected == 0:
        print("No selected topics found. Run this first:")
        print("  python -m research_intel.jobs.pick_topics")
        conn.close()
        return

    print(f"Writing {args.brief_type} brief from {selected} selected topics...")
    brief = build_brief(conn, brief_type=args.brief_type)
    brief_id, path = save_brief(conn, brief)
    print(f"Saved brief #{brief_id}")
    print(f"Markdown: {path}")
    print(f"Article of the day: {brief.closing.article_title[:100]}")
    conn.close()


if __name__ == "__main__":
    main()
