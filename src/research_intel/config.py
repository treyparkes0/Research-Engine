from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DOMAINS = ("markets", "business", "world", "sports", "movies")


@dataclass(frozen=True)
class Feed:
    name: str
    domain: str
    feed_url: str
    homepage_url: str = ""


# Four publishers with a real feed summary, plus the Fed's own press feed.
# We store title + short feed summary + link. We never scrape full paywalled pages.
DEFAULT_FEEDS: tuple[Feed, ...] = (
    Feed("Federal Reserve Monetary Policy", "markets", "https://www.federalreserve.gov/feeds/press_monetary.xml", "https://www.federalreserve.gov"),
    Feed("CNBC Top News", "markets", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", "https://www.cnbc.com"),
    Feed("Guardian Business", "business", "https://www.theguardian.com/uk/business/rss", "https://www.theguardian.com/business"),
    Feed("BBC Business", "business", "https://feeds.bbci.co.uk/news/business/rss.xml", "https://www.bbc.com/news/business"),
    Feed("NPR Business", "business", "https://feeds.npr.org/1006/rss.xml", "https://www.npr.org/sections/business/"),
    Feed("BBC World", "world", "https://feeds.bbci.co.uk/news/world/rss.xml", "https://www.bbc.com/news/world"),
    Feed("BBC US and Canada", "world", "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml", "https://www.bbc.com/news/world/us_and_canada"),
    Feed("NPR World", "world", "https://feeds.npr.org/1004/rss.xml", "https://www.npr.org/sections/world/"),
    Feed("The Guardian World", "world", "https://www.theguardian.com/world/rss", "https://www.theguardian.com/world"),
    Feed("Guardian US News", "world", "https://www.theguardian.com/us-news/rss", "https://www.theguardian.com/us-news"),
    Feed("Al Jazeera", "world", "https://www.aljazeera.com/xml/rss/all.xml", "https://www.aljazeera.com"),
    # Sports focus: NFL, CFB, NBA, March Madness, tennis, NHL, Mets, UFC — no soccer
    Feed("ESPN NFL", "sports", "https://www.espn.com/espn/rss/nfl/news", "https://www.espn.com/nfl"),
    Feed("CBS NFL", "sports", "https://www.cbssports.com/rss/headlines/nfl/", "https://www.cbssports.com/nfl"),
    Feed("ESPN College Sports", "sports", "https://www.espn.com/espn/rss/espnu/news", "https://www.espn.com/college-sports"),
    Feed("CBS College Football", "sports", "https://www.cbssports.com/rss/headlines/college-football/", "https://www.cbssports.com/college-football"),
    Feed("ESPN NBA", "sports", "https://www.espn.com/espn/rss/nba/news", "https://www.espn.com/nba"),
    Feed("CBS NBA", "sports", "https://www.cbssports.com/rss/headlines/nba/", "https://www.cbssports.com/nba"),
    Feed("ESPN College Basketball", "sports", "https://www.espn.com/espn/rss/ncb/news", "https://www.espn.com/mens-college-basketball"),
    Feed("CBS College Basketball", "sports", "https://www.cbssports.com/rss/headlines/college-basketball/", "https://www.cbssports.com/college-basketball"),
    Feed("ESPN Tennis", "sports", "https://www.espn.com/espn/rss/tennis/news", "https://www.espn.com/tennis"),
    Feed("CBS Tennis", "sports", "https://www.cbssports.com/rss/headlines/tennis/", "https://www.cbssports.com/tennis"),
    Feed("ESPN NHL", "sports", "https://www.espn.com/espn/rss/nhl/news", "https://www.espn.com/nhl"),
    Feed("CBS NHL", "sports", "https://www.cbssports.com/rss/headlines/nhl/", "https://www.cbssports.com/nhl"),
    Feed("ESPN MMA", "sports", "https://www.espn.com/espn/rss/mma/news", "https://www.espn.com/mma"),
    Feed("CBS UFC", "sports", "https://www.cbssports.com/rss/headlines/ufc/", "https://www.cbssports.com/mma/ufc"),
    Feed("ESPN MLB", "sports", "https://www.espn.com/espn/rss/mlb/news", "https://www.espn.com/mlb"),
    # Movies / film
    Feed("Guardian Film", "movies", "https://www.theguardian.com/film/rss", "https://www.theguardian.com/film"),
    Feed("BBC Culture", "movies", "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml", "https://www.bbc.com/news/entertainment_and_arts"),
)

SEED_THEMES: tuple[str, ...] = (
    "Artificial Intelligence",
    "Cybersecurity",
    "Interest Rates",
    "Consumer Spending",
    "Energy Markets",
    "Telecom Industry",
    "Trade Policy",
    "Inflation",
    "Earnings",
    "Geopolitics",
    "Film & Streaming",
    "Box Office",
)

TOPICS_PER_DOMAIN = 5
TOPIC_LOOKBACK_HOURS = 36
TOPIC_SIMILARITY_THRESHOLD = 0.28

# Morning brief is scheduled at 6:30 AM local. Runs that start at or after this
# time are catch-ups (PC was asleep) and are not emailed.
MORNING_CUTOFF_HOUR = 9
MORNING_CUTOFF_MINUTE = 0

# Storage cleanup defaults
ARTICLE_KEEP_DAYS = int(os.getenv("ARTICLE_KEEP_DAYS", "21"))
BRIEF_KEEP_DAYS = int(os.getenv("BRIEF_KEEP_DAYS", "90"))
BRIEF_FILES_KEEP = int(os.getenv("BRIEF_FILES_KEEP", "4"))


def database_path() -> Path:
    raw = os.getenv("DATABASE_PATH", "data/research_intel.db")
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def briefs_dir() -> Path:
    raw = os.getenv("BRIEFS_DIR", "data/briefs")
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def logs_dir() -> Path:
    path = ROOT / "data" / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass(frozen=True)
class EmailSettings:
    enabled: bool
    host: str
    port: int
    username: str
    password: str
    mail_from: str
    mail_to: str
    use_tls: bool


def email_settings() -> EmailSettings:
    password = (os.getenv("EMAIL_APP_PASSWORD") or "").replace(" ", "").strip()
    mail_to = (os.getenv("EMAIL_TO") or "").strip()
    mail_from = (os.getenv("EMAIL_FROM") or mail_to).strip()
    username = (os.getenv("EMAIL_USERNAME") or mail_from).strip()
    host = (os.getenv("SMTP_HOST") or "smtp.gmail.com").strip()
    port = int(os.getenv("SMTP_PORT") or "587")
    use_tls = (os.getenv("SMTP_TLS") or "true").strip().lower() in {"1", "true", "yes"}
    enabled = bool(password and mail_to and mail_from)
    return EmailSettings(
        enabled=enabled,
        host=host,
        port=port,
        username=username,
        password=password,
        mail_from=mail_from,
        mail_to=mail_to,
        use_tls=use_tls,
    )
