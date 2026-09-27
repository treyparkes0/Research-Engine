from __future__ import annotations

from research_intel.db import init_db
from research_intel.ingest.feeds import run_ingest


def main() -> None:
    conn = init_db()
    print(f"Database ready: {conn.execute('PRAGMA database_list').fetchone()['file']}")
    stats = run_ingest(conn)
    print(
        "Done. "
        f"{stats['articles_new']} new articles, "
        f"{stats['articles_seen']} seen, "
        f"{stats['sources_ok']} feeds ok, "
        f"{stats['sources_failed']} failed."
    )
    conn.close()


if __name__ == "__main__":
    main()
