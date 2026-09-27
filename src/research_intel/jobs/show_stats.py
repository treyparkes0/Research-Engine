from __future__ import annotations

from research_intel.db import init_db


def main() -> None:
    conn = init_db()
    total = conn.execute("SELECT COUNT(*) AS n FROM articles").fetchone()["n"]
    sources = conn.execute("SELECT COUNT(*) AS n FROM sources WHERE active = 1").fetchone()["n"]
    print(f"Active feeds: {sources}")
    print(f"Articles stored: {total}")
    print("\nBy domain:")
    rows = conn.execute(
        """
        SELECT domain, COUNT(*) AS n
        FROM articles
        GROUP BY domain
        ORDER BY domain
        """
    ).fetchall()
    for row in rows:
        print(f"  {row['domain']:10} {row['n']}")

    print("\nLatest 5 articles:")
    latest = conn.execute(
        """
        SELECT a.domain, a.title, s.name AS source, a.published_at
        FROM articles a
        JOIN sources s ON s.id = a.source_id
        ORDER BY COALESCE(a.published_at, a.fetched_at) DESC
        LIMIT 5
        """
    ).fetchall()
    for row in latest:
        when = row["published_at"] or "unknown time"
        print(f"  [{row['domain']}] {row['title'][:90]}")
        print(f"           {row['source']} | {when}")
    conn.close()


if __name__ == "__main__":
    main()
