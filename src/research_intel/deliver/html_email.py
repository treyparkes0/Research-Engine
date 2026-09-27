from __future__ import annotations

from html import escape

from research_intel.config import DOMAINS
from research_intel.generate.render import (
    DOMAIN_TITLES,
    SOURCE_LINKS_SHOWN,
    at_a_glance,
    format_created,
    format_published,
    polish_title,
    stock_line,
)
from research_intel.generate.template_writer import ResearchBrief
from research_intel.markets.impact import DISCLAIMER


def _p(text: str) -> str:
    return (
        '<p style="margin:0 0 12px;font-size:16px;line-height:1.55;color:#1c1c1c;">'
        f"{text}</p>"
    )


def render_html(brief: ResearchBrief) -> str:
    title = "Morning Brief" if brief.brief_type == "morning" else "Evening Brief"
    parts: list[str] = [
        "<!DOCTYPE html><html><body style=\"margin:0;padding:0;background:#f3f1ec;"
        "font-family:Georgia,'Iowan Old Style',Palatino,'Times New Roman',serif;color:#1c1c1c;\">",
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background:#f3f1ec;padding:24px 12px;">',
        '<tr><td align="center">',
        '<table role="presentation" width="640" cellpadding="0" cellspacing="0" '
        'style="max-width:640px;width:100%;background:#fffefb;border:1px solid #e4dfd4;">',
        '<tr><td style="padding:28px 32px 8px;border-bottom:3px solid #1c1c1c;">',
        '<p style="margin:0 0 6px;font-family:Calibri,Arial,sans-serif;font-size:11px;'
        'letter-spacing:0.16em;text-transform:uppercase;color:#6b645b;">'
        "Research Intelligence</p>",
        f'<h1 style="margin:0;font-size:32px;line-height:1.15;font-weight:normal;">{escape(title)}</h1>',
        f'<p style="margin:8px 0 0;font-family:Calibri,Arial,sans-serif;font-size:13px;color:#6b645b;">'
        f"{escape(format_created(brief.created_at))}</p>",
        "</td></tr>",
        '<tr><td style="padding:22px 32px 8px;">',
        _p("A short briefing: the lead in each area, then what happened and where to read it."),
        f'<p style="margin:0 0 18px;font-family:Calibri,Arial,sans-serif;font-size:12px;'
        f'line-height:1.45;color:#6b645b;">{escape(DISCLAIMER)}</p>',
        "</td></tr>",
    ]

    if brief.watchlist_quotes:
        parts.append(
            '<tr><td style="padding:4px 32px 8px;">'
            '<h2 style="margin:0 0 10px;font-family:Calibri,Arial,sans-serif;font-size:13px;'
            'letter-spacing:0.12em;text-transform:uppercase;color:#6b645b;font-weight:normal;">'
            "Watchlist</h2>"
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            'style="font-family:Calibri,Arial,sans-serif;font-size:14px;">'
        )
        for q in brief.watchlist_quotes:
            if q.price is None:
                value = "unavailable"
            else:
                pct = "n/a" if q.change_pct is None else f"{q.change_pct:+.2f}%"
                value = f"${q.price:.2f} ({pct})"
            parts.append(
                "<tr>"
                f'<td style="padding:4px 0;color:#1c1c1c;">{escape(q.symbol)}</td>'
                f'<td style="padding:4px 8px;color:#6b645b;">{escape(q.name)}</td>'
                f'<td style="padding:4px 0;text-align:right;">{escape(value)}</td>'
                "</tr>"
            )
        parts.append("</table></td></tr>")

    parts.append(
        '<tr><td style="padding:18px 32px 8px;">'
        '<h2 style="margin:0 0 10px;font-family:Calibri,Arial,sans-serif;font-size:13px;'
        'letter-spacing:0.12em;text-transform:uppercase;color:#6b645b;font-weight:normal;">'
        "At a glance</h2>"
    )
    for label, sentence in at_a_glance(brief):
        parts.append(
            '<p style="margin:0 0 10px;font-size:15px;line-height:1.5;">'
            f'<strong style="font-family:Calibri,Arial,sans-serif;font-size:13px;">'
            f"{escape(label)}.</strong> {escape(sentence)}</p>"
        )
    parts.append("</td></tr>")

    for domain in DOMAINS:
        cards = brief.cards_by_domain.get(domain) or []
        parts.append(
            '<tr><td style="padding:22px 32px 4px;">'
            f'<h2 style="margin:0;padding-top:8px;border-top:1px solid #e4dfd4;'
            f'font-size:22px;font-weight:normal;">'
            f"{escape(DOMAIN_TITLES.get(domain, domain.title()))}</h2>"
            "</td></tr>"
        )
        if not cards:
            parts.append(
                '<tr><td style="padding:8px 32px 4px;">'
                '<p style="margin:0;color:#6b645b;font-size:15px;">Nothing selected.</p>'
                "</td></tr>"
            )
            continue
        for card in cards:
            parts.append('<tr><td style="padding:14px 32px 6px;">')
            parts.append(
                f'<h3 style="margin:0 0 6px;font-size:18px;line-height:1.3;font-weight:normal;">'
                f"{card.rank}. {escape(polish_title(card.title))}</h3>"
            )
            latest = next((s.published_at for s in card.sources if s.published_at), None)
            if latest:
                parts.append(
                    '<p style="margin:0 0 8px;font-family:Calibri,Arial,sans-serif;'
                    f'font-size:12px;color:#6b645b;">{escape(format_published(latest))}</p>'
                )
            parts.append(_p(escape(card.executive_summary)))
            if card.why_it_matters:
                parts.append(
                    '<p style="margin:0 0 12px;padding-left:12px;border-left:2px solid #1c1c1c;'
                    'font-size:15px;line-height:1.5;">'
                    f"<strong>Why it matters.</strong> {escape(card.why_it_matters)}</p>"
                )
            if card.definitions:
                parts.append(
                    '<p style="margin:0 0 6px;font-family:Calibri,Arial,sans-serif;'
                    'font-size:12px;letter-spacing:0.08em;text-transform:uppercase;color:#6b645b;">'
                    "Terms</p><ul style=\"margin:0 0 12px;padding-left:18px;\">"
                )
                for item in card.definitions:
                    parts.append(
                        f'<li style="margin:0 0 4px;font-size:14px;line-height:1.45;">{escape(item)}</li>'
                    )
                parts.append("</ul>")
            if card.related_tickers:
                parts.append(
                    '<p style="margin:0 0 6px;font-family:Calibri,Arial,sans-serif;'
                    'font-size:12px;letter-spacing:0.08em;text-transform:uppercase;color:#6b645b;">'
                    "Stocks in play</p><ul style=\"margin:0 0 12px;padding-left:18px;\">"
                )
                for item in card.related_tickers:
                    parts.append(
                        f'<li style="margin:0 0 4px;font-size:14px;line-height:1.45;">'
                        f"{escape(stock_line(item))}</li>"
                    )
                parts.append("</ul>")
            shown = card.sources[:SOURCE_LINKS_SHOWN]
            parts.append(
                '<p style="margin:0 0 6px;font-family:Calibri,Arial,sans-serif;'
                'font-size:12px;letter-spacing:0.08em;text-transform:uppercase;color:#6b645b;">'
                "Sources</p><ul style=\"margin:0;padding-left:18px;\">"
            )
            for src in shown:
                when = format_published(src.published_at)
                parts.append(
                    '<li style="margin:0 0 4px;font-size:14px;line-height:1.45;">'
                    f'<a href="{escape(src.url, quote=True)}" style="color:#1c1c1c;">'
                    f"{escape(src.source_name)}</a>"
                    f' <span style="color:#6b645b;">· {escape(when)}</span>'
                    "</li>"
                )
            extra = len(card.sources) - len(shown)
            if extra > 0:
                parts.append(
                    f'<li style="margin:0;font-size:13px;color:#6b645b;">'
                    f"{extra} more source{'s' if extra != 1 else ''}</li>"
                )
            parts.append("</ul></td></tr>")

    c = brief.closing
    parts.append(
        '<tr><td style="padding:24px 32px 28px;">'
        '<h2 style="margin:0 0 8px;padding-top:12px;border-top:1px solid #e4dfd4;'
        'font-size:22px;font-weight:normal;">Article of the day</h2>'
        f'<p style="margin:0 0 8px;font-size:17px;">{escape(polish_title(c.article_title))}</p>'
        f'<p style="margin:0 0 8px;font-family:Calibri,Arial,sans-serif;font-size:12px;color:#6b645b;">'
        f"{escape(DOMAIN_TITLES.get(c.article_domain, c.article_domain))}</p>"
        + _p(escape(c.why_learn))
    )
    if c.source_url:
        parts.append(
            f'<p style="margin:0 0 12px;font-size:15px;">'
            f'<a href="{escape(c.source_url, quote=True)}" style="color:#1c1c1c;">'
            f"{escape(c.source_name or 'Source')}</a></p>"
        )
    if c.definitions:
        parts.append('<ul style="margin:0 0 12px;padding-left:18px;">')
        for item in c.definitions:
            parts.append(
                f'<li style="margin:0 0 4px;font-size:14px;line-height:1.45;">{escape(item)}</li>'
            )
        parts.append("</ul>")
    parts.append(
        f'<p style="margin:0 0 8px;font-size:14px;color:#3d3a36;">'
        f"<strong>Backdrop.</strong> {escape(c.emerging_trend)}</p>"
        '<p style="margin:12px 0 6px;font-family:Calibri,Arial,sans-serif;font-size:12px;'
        'letter-spacing:0.08em;text-transform:uppercase;color:#6b645b;">Also watching</p>'
        '<ul style="margin:0;padding-left:18px;">'
    )
    for item in c.topics_to_monitor:
        parts.append(
            f'<li style="margin:0 0 4px;font-size:14px;line-height:1.45;">{escape(item)}</li>'
        )
    parts.append("</ul></td></tr>")
    parts.append("</table></td></tr></table></body></html>")
    return "".join(parts)
