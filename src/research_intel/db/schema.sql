PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    domain TEXT NOT NULL CHECK (
        domain IN (
            'markets',
            'business',
            'world',
            'sports',
            'movies'
        )
    ),
    feed_url TEXT NOT NULL UNIQUE,
    homepage_url TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    summary TEXT,
    published_at TEXT,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
    content_hash TEXT,
    domain TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_articles_domain_published
    ON articles(domain, published_at DESC);

CREATE INDEX IF NOT EXISTS idx_articles_fetched_at
    ON articles(fetched_at DESC);

CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    domain TEXT NOT NULL,
    first_seen TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL DEFAULT 'active',
    score REAL NOT NULL DEFAULT 0,
    article_count INTEGER NOT NULL DEFAULT 0,
    source_count INTEGER NOT NULL DEFAULT 0,
    selected_rank INTEGER,
    as_of TEXT
);

CREATE TABLE IF NOT EXISTS article_topics (
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    score REAL NOT NULL DEFAULT 1.0,
    PRIMARY KEY (article_id, topic_id)
);

CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT 'unknown',
    canonical_name TEXT,
    UNIQUE(name, entity_type)
);

CREATE TABLE IF NOT EXISTS article_entities (
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    salience REAL NOT NULL DEFAULT 1.0,
    PRIMARY KEY (article_id, entity_id)
);

CREATE TABLE IF NOT EXISTS themes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'core'
);

CREATE TABLE IF NOT EXISTS topic_themes (
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    theme_id INTEGER NOT NULL REFERENCES themes(id) ON DELETE CASCADE,
    score REAL NOT NULL DEFAULT 1.0,
    PRIMARY KEY (topic_id, theme_id)
);

CREATE TABLE IF NOT EXISTS related (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    left_type TEXT NOT NULL,
    left_id INTEGER NOT NULL,
    right_type TEXT NOT NULL,
    right_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 0,
    detail TEXT,
    as_of TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_related_left
    ON related(left_type, left_id, as_of DESC);

CREATE TABLE IF NOT EXISTS briefs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brief_type TEXT NOT NULL CHECK (brief_type IN ('morning', 'evening')),
    sent_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    payload_json TEXT,
    rating INTEGER CHECK (rating IS NULL OR (rating BETWEEN 1 AND 5))
);

CREATE TABLE IF NOT EXISTS topic_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brief_id INTEGER NOT NULL REFERENCES briefs(id) ON DELETE CASCADE,
    topic_id INTEGER REFERENCES topics(id),
    domain TEXT NOT NULL,
    rank INTEGER NOT NULL,
    title TEXT NOT NULL,
    executive_summary TEXT,
    why_it_matters TEXT,
    key_takeaways_json TEXT,
    research_snapshot TEXT,
    further_research_json TEXT,
    questions_json TEXT,
    sources_json TEXT,
    card_json TEXT
);

CREATE TABLE IF NOT EXISTS monitor_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brief_id INTEGER REFERENCES briefs(id) ON DELETE CASCADE,
    topic_id INTEGER REFERENCES topics(id),
    label TEXT NOT NULL,
    reason TEXT,
    score REAL,
    as_of TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brief_id INTEGER REFERENCES briefs(id) ON DELETE CASCADE,
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ingest_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT,
    sources_ok INTEGER NOT NULL DEFAULT 0,
    sources_failed INTEGER NOT NULL DEFAULT 0,
    articles_new INTEGER NOT NULL DEFAULT 0,
    articles_seen INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);
