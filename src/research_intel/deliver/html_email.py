"""HTML email that follows the same sections as the Markdown brief.

Layout is a single column with a 640px cap so it stays readable on a phone.
A source with no URL is labeled 'link unavailable' instead of an empty link.
"""

from __future__ import annotations

from html import escape

from research_intel.config import DOMAINS
from research_intel.generate.render import (
    DOMAIN_TITLES,
    at_a_glance,
    format_created,
    format_published,
    polish_title,
    sources_for_display,
    stock_line,
)
from research_intel.generate.template_writer import ResearchBrief
from research_intel.markets.impact import DISCLAIMER


def _p(text: str) -> str:
    """One body paragraph with the email type styles."""
    return (
        '<p style="margin:0 0 12px;font-size:16px;line-height:1.55;color:#1c1c1c;">'
        f"{text}</p>"
    )


def _source_html(src) -> str:
    """One source line. A missing URL is labeled instead of linked."""
    when = format_published(src.published_at)
    headline = polish_title(src.title) if src.title else "Untitled"
    if src.url:
        name = (
            f'<a href="{escape(src.url, quote=True)}" style="color:#1c1c1c;">'
            f"{escape(src.source_name or 'Source')}</a>"
        )
    else:
        name = f"{escape(src.source_name or 'Source')} (link unavailable)"
    return (
        '<li style="margin:0 0 6px;font-size:14px;line-height:1.45;">'
        f"{name}"
        f' <span style="color:#6b645b;">— {escape(headline)} · {escape(when)}</span>'
        "</li>"
    )


def render_html(brief: ResearchBrief) -> str:
    """Full HTML email, using the same sections as the Markdown brief."""
    title = "Morning Brief" if brief.brief_type == "morning" else "Evening Brief"
    parts: list[str] = [
        "<!DOCTYPE html><html><head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<style>",
        "@media only screen and (max-width:620px){",
        ".rie-pad{padding-left:16px !important;padding-right:16px !important;}",
        ".rie-title{font-size:26px !important;}",
        "}",
        "</style></head>",
        '<body style="margin:0;padding:0;background:#f3f1ec;'
        "font-family:Georgia,'Iowan Old Style',Palatino,'Times New Roman',serif;color:#1c1c1c;\">",
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background:#f3f1ec;padding:24px 12px;">',
        '<tr><td align="center">',
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:640px;width:100%;background:#fffefb;border:1px solid #e4dfd4;">',
        '<tr><td class="rie-pad" style="padding:28px 28px 8px;border-bottom:3px solid #1c1c1c;">',
        '<p style="margin:0 0 6px;font-family:Calibri,Arial,sans-serif;font-size:11px;'
        'letter-spacing:0.16em;text-transform:uppercase;color:#6b645b;">'
        "Research Intelligence</p>",
        f'<h1 class="rie-title" style="margin:0;font-size:32px;line-height:1.15;font-weight:normal;">'
        f"{escape(title)}</h1>",
        f'<p style="margin:8px 0 0;font-family:Calibri,Arial,sans-serif;font-size:13px;color:#6b645b;">'
        f"{escape(format_created(brief.created_at))}</p>",
        "</td></tr>",
        '<tr><td class="rie-pad" style="padding:22px 28px 8px;">',
        _p("Executive overview first, then each story as what happened, why it matters, and where to read more."),
        f'<p style="margin:0 0 18px;font-family:Calibri,Arial,sans-serif;font-size:12px;'
        f'line-height:1.45;color:#6b645b;">{escape(DISCLAIMER)}</p>',
        "</td></tr>",
    ]

    if brief.watchlist_quotes:
        parts.append(
            '<tr><td class="rie-pad" style="padding:4px 28px 8px;">'
            '<h2 style="margin:0 0 8px;font-family:Calibri,Arial,sans-serif;font-size:13px;'
            'letter-spacing:0.12em;text-transform:uppercase;color:#6b645b;font-weight:normal;">'
            "Watchlist</h2>"
            '<p style="margin:0 0 8px;font-size:13px;line-height:1.45;color:#6b645b;">'
            "Recent prices for a personal watchlist. Not tied to one story, and not a recommendation.</p>"
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            'style="font-family:Calibri,Arial,sans-serif;font-size:14px;">'
        )
        for quote in brief.watchlist_quotes:
            if quote.price is None:
                value = "unavailable"
            else:
                pct = "n/a" if quote.change_pct is None else f"{quote.change_pct:+.2f}%"
                value = f"${quote.price:.2f} ({pct})"
            parts.append(
                "<tr>"
                f'<td style="padding:4px 8px 4px 0;color:#1c1c1c;">{escape(quote.symbol)}</td>'
                f'<td style="padding:4px 8px;color:#6b645b;">{escape(quote.name)}</td>'
                f'<td style="padding:4px 0;text-align:right;">{escape(value)}</td>'
                "</tr>"
            )
        parts.append("</table></td></tr>")

    parts.append(
        '<tr><td class="rie-pad" style="padding:18px 28px 8px;">'
        '<h2 style="margin:0 0 10px;font-family:Calibri,Arial,sans-serif;font-size:13px;'
        'letter-spacing:0.12em;text-transform:uppercase;color:#6b645b;font-weight:normal;">'
        "Executive overview</h2>"
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
            '<tr><td class="rie-pad" style="padding:22px 28px 4px;">'
            f'<h2 style="margin:0;padding-top:8px;border-top:1px solid #e4dfd4;'
            f'font-size:22px;font-weight:normal;">'
            f"{escape(DOMAIN_TITLES.get(domain, domain.title()))}</h2>"
            "</td></tr>"
        )
        if not cards:
            parts.append(
                '<tr><td class="rie-pad" style="padding:8px 28px 4px;">'
                '<p style="margin:0;color:#6b645b;font-size:15px;">Nothing selected.</p>'
                "</td></tr>"
            )
            continue
        for card in cards:
            parts.append('<tr><td class="rie-pad" style="padding:14px 28px 6px;">')
            parts.append(
                f'<h3 style="margin:0 0 6px;font-size:18px;line-height:1.3;font-weight:normal;">'
                f"{card.rank}. {escape(polish_title(card.title))}</h3>"
            )
            latest = next((src.published_at for src in card.sources if src.published_at), None)
            if latest:
                parts.append(
                    '<p style="margin:0 0 8px;font-family:Calibri,Arial,sans-serif;'
                    f'font-size:12px;color:#6b645b;">Published {escape(format_published(latest))}</p>'
                )
            parts.append(
                '<p style="margin:0 0 4px;font-family:Calibri,Arial,sans-serif;font-size:11px;'
                'letter-spacing:0.08em;text-transform:uppercase;color:#6b645b;">What happened</p>'
            )
            parts.append(_p(escape(card.executive_summary or "")))
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
                    "Terms in the source text</p><ul style=\"margin:0 0 12px;padding-left:18px;\">"
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
                    "Market context</p><ul style=\"margin:0 0 12px;padding-left:18px;\">"
                )
                for item in card.related_tickers:
                    parts.append(
                        f'<li style="margin:0 0 4px;font-size:14px;line-height:1.45;">'
                        f"{escape(stock_line(item))}</li>"
                    )
                parts.append("</ul>")
            shown = sources_for_display(card.sources)
            parts.append(
                '<p style="margin:0 0 6px;font-family:Calibri,Arial,sans-serif;'
                'font-size:12px;letter-spacing:0.08em;text-transform:uppercase;color:#6b645b;">'
                "Read more</p>"
            )
            if not shown:
                parts.append('<p style="margin:0;font-size:14px;color:#6b645b;">No source link was saved.</p>')
            else:
                parts.append('<ul style="margin:0;padding-left:18px;">')
                for src in shown:
                    parts.append(_source_html(src))
                extra = len(card.sources) - len(shown)
                if extra > 0:
                    parts.append(
                        f'<li style="margin:0;font-size:13px;color:#6b645b;">'
                        f"{extra} more source{'s' if extra != 1 else ''}</li>"
                    )
                parts.append("</ul>")
            parts.append("</td></tr>")

    closing = brief.closing
    section = DOMAIN_TITLES.get(closing.article_domain, closing.article_domain) or "Not available"
    parts.append(
        '<tr><td class="rie-pad" style="padding:24px 28px 28px;">'
        '<h2 style="margin:0 0 8px;padding-top:12px;border-top:1px solid #e4dfd4;'
        'font-size:22px;font-weight:normal;">Article of the day</h2>'
        f'<p style="margin:0 0 8px;font-size:17px;">{escape(polish_title(closing.article_title))}</p>'
        f'<p style="margin:0 0 8px;font-family:Calibri,Arial,sans-serif;font-size:12px;color:#6b645b;">'
        f"{escape(section)}</p>"
        + _p(escape(closing.why_learn or ""))
    )
    if closing.source_url:
        parts.append(
            f'<p style="margin:0 0 12px;font-size:15px;">'
            f'<a href="{escape(closing.source_url, quote=True)}" style="color:#1c1c1c;">'
            f"{escape(closing.source_name or 'Source')}</a></p>"
        )
    elif closing.source_name:
        parts.append(
            f'<p style="margin:0 0 12px;font-size:15px;">{escape(closing.source_name)} (link unavailable)</p>'
        )
    if closing.definitions:
        parts.append('<ul style="margin:0 0 12px;padding-left:18px;">')
        for item in closing.definitions:
            parts.append(
                f'<li style="margin:0 0 4px;font-size:14px;line-height:1.45;">{escape(item)}</li>'
            )
        parts.append("</ul>")
    parts.append(
        f'<p style="margin:0 0 8px;font-size:14px;color:#3d3a36;">'
        f"<strong>Most common theme tag.</strong> {escape(closing.emerging_trend or '')}</p>"
        '<p style="margin:12px 0 6px;font-family:Calibri,Arial,sans-serif;font-size:12px;'
        'letter-spacing:0.08em;text-transform:uppercase;color:#6b645b;">Also watching</p>'
        '<ul style="margin:0;padding-left:18px;">'
    )
    for item in closing.topics_to_monitor:
        parts.append(
            f'<li style="margin:0 0 4px;font-size:14px;line-height:1.45;">{escape(item)}</li>'
        )
    parts.append("</ul></td></tr>")
    parts.append("</table></td></tr></table></body></html>")
    return "".join(parts)
