"""Morning and evening pipeline: ingest, rank, write, email, then prune.

The scheduled morning run skips itself at or after 9:00 local time so a late
wake-up does not send a stale brief. Pass --allow-late to run anyway. Evening
is started by hand.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from research_intel.config import (
    MORNING_CUTOFF_HOUR,
    MORNING_CUTOFF_MINUTE,
    email_settings,
    logs_dir,
)
from research_intel.db import init_db
from research_intel.deliver.email import EmailNotConfiguredError, send_brief_email
from research_intel.generate.brief import build_brief, save_brief
from research_intel.ingest.feeds import run_ingest
from research_intel.process.cleanup import cleanup_storage
from research_intel.process.pick_topics import run_topic_picker


def past_morning_cutoff(now: datetime | None = None) -> bool:
    """True at or after 9:00 on the machine's local clock."""
    local = datetime.now().astimezone() if now is None else now
    if local.tzinfo is not None:
        local = local.astimezone()
    return (local.hour, local.minute) >= (MORNING_CUTOFF_HOUR, MORNING_CUTOFF_MINUTE)


def run_daily(
    brief_type: str,
    *,
    send_email: bool = True,
    skip_cleanup: bool = False,
    allow_late: bool = False,
) -> int:
    """Ingest, rank, write, optionally email, then prune. Returns 0, or 2 when the morning window has closed."""
    if brief_type not in {"morning", "evening"}:
        raise ValueError("brief_type must be morning or evening")

    logs_dir().mkdir(parents=True, exist_ok=True)
    if brief_type == "morning" and not allow_late and past_morning_cutoff():
        local = datetime.now().astimezone().strftime("%Y-%m-%d %I:%M %p %Z")
        print(
            f"SKIPPED: morning brief only sends before "
            f"{MORNING_CUTOFF_HOUR:02d}:{MORNING_CUTOFF_MINUTE:02d} local. Now is {local}."
        )
        print("This was a late catch-up (PC was asleep at 6:30). It was not emailed.")
        print("To write one anyway, rerun with --allow-late.")
        return 0
    conn = init_db()
    print(f"=== Research Intel daily ({brief_type}) ===")

    print("1) Ingesting news...")
    ingest_stats = run_ingest(conn)
    print(
        f"   +{ingest_stats['articles_new']} new / {ingest_stats['articles_seen']} seen "
        f"({ingest_stats['sources_ok']} ok, {ingest_stats['sources_failed']} failed)"
    )

    print("2) Picking topics...")
    ranked = run_topic_picker(conn)
    selected = sum(
        1 for items in ranked.values() for item in items if item.selected_rank is not None
    )
    print(f"   Selected {selected} topics")

    print("3) Writing brief...")
    brief = build_brief(conn, brief_type=brief_type)
    brief_id, path = save_brief(conn, brief)
    print(f"   Brief #{brief_id} -> {path}")
    print(f"   Theme: {brief.closing.article_title[:80]}")

    if send_email:
        print("4) Emailing brief...")
        settings = email_settings()
        if not settings.enabled:
            print("   SKIPPED: set EMAIL_TO and EMAIL_APP_PASSWORD in .env")
        else:
            try:
                subject = send_brief_email(brief, settings=settings)
                conn.execute(
                    "UPDATE briefs SET sent_at = ? WHERE id = ?",
                    (datetime.now(timezone.utc).isoformat(), brief_id),
                )
                conn.commit()
                print(f"   Sent: {subject}")
                print(f"   To: {settings.mail_to}")
            except EmailNotConfiguredError as exc:
                print(f"   SKIPPED: {exc}")
            except Exception as exc:  # noqa: BLE001
                print(f"   EMAIL FAILED: {exc}")
                conn.close()
                return 1
    else:
        print("4) Email skipped (--no-email)")

    if not skip_cleanup:
        print("5) Cleaning old storage...")
        cleaned = cleanup_storage(conn)
        print(
            "   "
            f"articles={cleaned['articles_deleted']}, "
            f"briefs={cleaned['briefs_deleted']}, "
            f"topics={cleaned['topics_deleted']}, "
            f"files={cleaned['files_deleted']}"
        )
    else:
        print("5) Cleanup skipped")

    conn.close()
    print("Done.")
    return 0


def main(argv: list[str] | None = None) -> None:
    """Parse arguments and start a morning or evening run."""
    parser = argparse.ArgumentParser(description="Run the full daily research brief pipeline")
    parser.add_argument(
        "brief_type",
        nargs="?",
        default="evening",
        choices=("morning", "evening"),
    )
    parser.add_argument("--no-email", action="store_true", help="Write brief but do not email")
    parser.add_argument("--skip-cleanup", action="store_true", help="Do not prune old rows/files")
    parser.add_argument(
        "--allow-late",
        action="store_true",
        help="Write a morning brief even after the 9:00 AM local cutoff",
    )
    args = parser.parse_args(argv)
    raise SystemExit(
        run_daily(
            args.brief_type,
            send_email=not args.no_email,
            skip_cleanup=args.skip_cleanup,
            allow_late=args.allow_late,
        )
    )


if __name__ == "__main__":
    main()
