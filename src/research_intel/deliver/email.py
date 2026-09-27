from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

from research_intel.config import EmailSettings, email_settings
from research_intel.deliver.html_email import render_html
from research_intel.generate.render import render_markdown
from research_intel.generate.template_writer import ResearchBrief


class EmailNotConfiguredError(RuntimeError):
    pass


def send_brief_email(
    brief: ResearchBrief,
    settings: EmailSettings | None = None,
) -> str:
    settings = settings or email_settings()
    if not settings.enabled:
        raise EmailNotConfiguredError(
            "Email is not configured. Add EMAIL_TO and EMAIL_APP_PASSWORD to your .env file."
        )

    label = "Morning Brief" if brief.brief_type == "morning" else "Evening Brief"
    day = datetime.now().strftime("%b %d, %Y")
    subject = f"Research Intel — {label} — {day}"

    text_body = render_markdown(brief)
    html_body = render_html(brief)

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = settings.mail_from
    message["To"] = settings.mail_to
    message.attach(MIMEText(text_body, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(settings.host, settings.port, timeout=45) as smtp:
        if settings.use_tls:
            smtp.starttls()
        smtp.login(settings.username, settings.password)
        smtp.sendmail(settings.mail_from, [settings.mail_to], message.as_string())

    return subject
