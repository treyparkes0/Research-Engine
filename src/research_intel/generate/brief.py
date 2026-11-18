"""Load selected topics from SQLite and save the finished brief.

This is the step that ties ranking to writing. It does not re-rank. Optional
enrichment and ticker context are applied here, then the Markdown and JSON
files are written next to a row in the briefs table.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from research_intel.config import DOMAINS, briefs_dir
from research_intel.generate.render import render_markdown
from research_intel.generate.template_writer import (
    ResearchBrief,
    SourceLink,
    build_closing,
    build_topic_card,
    dumps_card_lists,
    now_iso,
)
from research_intel.ingest.enrich import api_status, enrich_topic
from research_intel.markets.impact import fetch_quotes_once, tickers_for_topic


def _load_selected_topics(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Selected topics in brief order: markets, business, world, sports, movies."""
    return conn.execute(
        """
        SELECT id, label, domain, selected_rank, score, article_count, source_count
        FROM topics
        WHERE status = 'selected'
        ORDER BY
            CASE domain
                WHEN 'markets' THEN 1
                WHEN 'business' THEN 2
                WHEN 'world' THEN 3
                WHEN 'sports' THEN 4
                WHEN 'movies' THEN 5
                ELSE 6
            END,
            selected_rank
        """
    ).fetchall()


def _load_sources_for_topic(conn: sqlite3.Connection, topic_id: int) -> list[SourceLink]:
    """Publisher links for one topic, newest first."""
    rows = conn.execute(
        """
        SELECT a.title, a.url, a.summary, a.published_at, a.fetched_at, s.name AS source_name
        FROM article_topics at
        JOIN articles a ON a.id = at.article_id
        JOIN sources s ON s.id = a.source_id
        WHERE at.topic_id = ?
        ORDER BY COALESCE(a.published_at, a.fetched_at) DESC
        """,
        (topic_id,),
    ).fetchall()
    return [
        SourceLink(
            title=row["title"],
            url=row["url"],
            source_name=row["source_name"],
            summary=row["summary"] or "",
            published_at=row["published_at"] or row["fetched_at"],
        )
        for row in rows
    ]


def _load_monitor_candidates(conn: sqlite3.Connection, limit: int = 8) -> list[tuple[int, str, float, str]]:
    """High-scoring stories that did not make the top five. Shown as 'also watching'."""
    rows = conn.execute(
        """
        SELECT id, label, score, domain
        FROM topics
        WHERE status = 'candidate'
        ORDER BY score DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [(int(r["id"]), r["label"], float(r["score"]), r["domain"]) for r in rows]


def build_brief(conn: sqlite3.Connection, brief_type: str = "evening") -> ResearchBrief:
    """Build the brief object. Does not write files. Quotes are fetched once for the whole run."""
    if brief_type not in {"morning", "evening"}:
        raise ValueError("brief_type must be 'morning' or 'evening'")

    selected = _load_selected_topics(conn)
    cards_by_domain: dict[str, list] = {d: [] for d in DOMAINS}
    quotes = fetch_quotes_once()
    print(f"   News enrichment APIs: {api_status()}")

    for row in selected:
        sources = _load_sources_for_topic(conn, int(row["id"]))
        title = row["label"]
        domain = row["domain"]
        enrichment = None
        if domain in {"markets", "business", "world"}:
            enrichment = enrich_topic(title)

        # Temporary themes from title only for ticker mapping; card rebuilds themes too.
        from research_intel.generate.themes import match_themes

        theme_names = [
            t.name
            for t in match_themes(title, *[s.summary for s in sources], *[s.title for s in sources])
        ]
        related = []
        if domain not in {"sports", "movies"}:
            related = tickers_for_topic(
                themes=theme_names,
                title=title,
                domain=domain,
                quotes=quotes,
            )

        card = build_topic_card(
            topic_id=int(row["id"]),
            domain=domain,
            rank=int(row["selected_rank"]),
            title=title,
            sources=sources,
            related_tickers=related,
            enrichment=enrichment,
        )
        cards_by_domain[domain].append(card)

    monitor_rows = _load_monitor_candidates(conn)
    monitor_labels = [f"[{domain}] {label}" for _, label, _, domain in monitor_rows]
    closing = build_closing(cards_by_domain, monitor_labels, brief_type=brief_type)

    return ResearchBrief(
        brief_type=brief_type,
        created_at=now_iso(),
        cards_by_domain=cards_by_domain,
        closing=closing,
        watchlist_quotes=quotes,
        writer="analysis-v1",
    )


def save_brief(
    conn: sqlite3.Connection,
    brief: ResearchBrief,
) -> tuple[int, Path]:
    """Write the Markdown and JSON files and store a briefs row."""
    payload = json.dumps(brief.to_dict(), ensure_ascii=True, indent=2)
    cursor = conn.execute(
        """
        INSERT INTO briefs (brief_type, created_at, payload_json)
        VALUES (?, ?, ?)
        """,
        (brief.brief_type, brief.created_at, payload),
    )
    brief_id = int(cursor.lastrowid)

    for domain, cards in brief.cards_by_domain.items():
        for card in cards:
            lists = dumps_card_lists(card)
            conn.execute(
                """
                INSERT INTO topic_cards (
                    brief_id, topic_id, domain, rank, title,
                    executive_summary, why_it_matters,
                    key_takeaways_json, research_snapshot,
                    further_research_json, questions_json,
                    sources_json, card_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    brief_id,
                    card.topic_id,
                    domain,
                    card.rank,
                    card.title,
                    card.executive_summary,
                    card.why_it_matters,
                    lists["key_takeaways_json"],
                    card.research_snapshot,
                    lists["further_research_json"],
                    lists["questions_json"],
                    lists["sources_json"],
                    lists["card_json"],
                ),
            )

    for label in brief.closing.topics_to_monitor:
        conn.execute(
            """
            INSERT INTO monitor_list (brief_id, label, reason, as_of)
            VALUES (?, ?, ?, ?)
            """,
            (brief_id, label, "near-miss / follow-up candidate", brief.created_at),
        )

    out_dir = briefs_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = brief.created_at.replace(":", "").replace("+00:00", "Z")[:15]
    md_path = out_dir / f"{brief.brief_type}_{stamp}.md"
    json_path = out_dir / f"{brief.brief_type}_{stamp}.json"
    md_path.write_text(render_markdown(brief), encoding="utf-8")
    json_path.write_text(payload, encoding="utf-8")

    conn.commit()
    return brief_id, md_path
