# Research Intelligence Engine

A local pipeline that turns public news feeds into a daily research brief for markets, business, world news, sports, and film. It clusters headlines into events, ranks those events with an explicit formula, and writes a short brief with source links. The default path does not call a language model and does not need a paid API.

## The problem

A person covering several beats cannot read every RSS item. A raw feed is chronological, full of repeats, and mixed with betting promotions and off-topic blurbs. The useful output is a short list: what happened, why the source says it matters, and where to read it, with the same story appearing once.

## What the system does

Once a day, or whenever you run it, the engine:

- Pulls public RSS (and, if you add a free TMDB key, current film releases).
- Drops soccer items outside the personal sports scope, betting promotions, and non-film entertainment on the BBC culture feed.
- Groups headlines that are the same event and keeps parallel headlines apart.
- Ranks stories by independent publishers, recency, and whether the feed included a real blurb.
- Writes a Markdown file and an HTML email. Tickers appear only as market context, and only when the headline supports them.
- Deletes old articles and old brief files.

## How to talk about it

This is an information-processing and automation project. The quality rules are code: same-story matching, a published ranking formula, and tests that fail if a card mixes two stories or attaches a fund the headline does not support. It is a good example of designing a workflow, putting controls on messy inputs, and delivering a report on a schedule.

It is not a claim that the brief is model-generated. Where a sentence in the brief comes from a feed, the feed said it.

Suggested GitHub description:

> Local pipeline that clusters public RSS into events, ranks them with an explicit formula, and delivers a sourced research brief. No LLM required.

Suggested profile line:

> Built a local research-brief pipeline: RSS to SQLite, same-event clustering, publisher-based ranking, and a scheduled email with tests around headline accuracy and bad ticker matches.

## Resume lines

AI Enablement / AI Solutions:

- Built a scheduled research-brief pipeline that turns public RSS into sourced event cards, with lexical clustering, an explicit ranking formula, and automated checks that keep headlines, summaries, and market context aligned.
- Designed a modular ingest-rank-deliver workflow with quality gates for duplicate stories, betting promotions, and unsupported ticker associations, replacing a manual multi-feed scan with one local brief.

Data Analyst / Business Operations:

- Automated a daily information workflow from public feeds into SQLite and a ranked brief, including retention rules, Windows scheduling, and tests for empty feeds, bad timestamps, and missing source links.
- Defined a transparent story-ranking method based on independent publishers, recency, and source-blurb quality so duplicate feed rows could not inflate a story's priority.

## Stack

Python 3.11+, SQLite, `feedparser`, `httpx`, `python-dotenv`. Standard-library email and Windows Task Scheduler. Optional free keys for TMDB and for longer blurbs from Guardian, NYT, or NewsAPI. No LangChain, no paid model API, no cloud host.

## Sample

[sample-brief.md](sample-brief.md) is rendered by the current writer from representative feed leads. The HTML email of that sample is [evening-brief.html](evening-brief.html), and [evening-brief.png](evening-brief.png) is the top of that email.

## More detail

- [Architecture](architecture.md)
- [Ranking methodology](RANKING_METHODOLOGY.md)
- [Project audit](PROJECT_AUDIT.md)
- [Why this maps to AI enablement work](AI_ENABLEMENT_RELEVANCE.md)
- Setup and commands are in the repository README.
