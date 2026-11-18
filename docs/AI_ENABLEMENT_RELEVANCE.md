# What this project shows for AI enablement work

This system does not call a language model. That is deliberate. The parts below are the parts an AI enablement or solutions role actually has to design: a workflow, structured inputs and outputs, rules you can explain, and checks that catch bad output before a person sees it.

A model can be added later in one place, the card writer, without rebuilding ingest or ranking. It is not included here because the feed blurb is already the source of the facts, and a model is not required to demonstrate the workflow.

## Automating a repeated information task

The manual version is opening several news sites, skipping repeats, and writing a note. `jobs/run_daily.py` does the pull, the selection, the file, the optional email, and the cleanup. Windows Task Scheduler starts the morning run at 6:30 AM local. A run that starts at or after 9:00 AM is skipped, so a laptop that wakes at noon does not send a stale morning brief.

## A modular pipeline

Ingest, clustering, ranking, writing, delivery, and retention are separate modules with a SQLite boundary between them. A feed can fail without stopping the others. Quote lookups can fail without dropping the brief. Enrichment keys are optional. The brief still runs on RSS alone.

## Unstructured inputs, structured output

RSS items are uneven: missing dates, HTML in the blurb, the same story under two headlines, a plot pasted where a release date should be. The database stores a small fixed record (title, blurb, link, time, domain). The brief is a fixed shape: overview, then for each story what happened, why it matters when the blurb says so, and links.

## Classification and priority without a model

Domains are assigned by which feed the item came from, then adjusted by rules (Mets-only on the MLB feed, film-only on BBC culture). Same-event matching is a lexical test with explicit exceptions for parallel headlines. Priority is the formula in [RANKING_METHODOLOGY.md](RANKING_METHODOLOGY.md): independent publishers, recency, blurb quality, and a subject bonus. Duplicate rows from one publisher do not raise the score.

## Quality controls

The checks are tests, not a prompt:

- A summary has to come from the article that matches the headline. A second article in the cluster cannot change the paragraph.
- Enrichment text is kept only when the sentence supports the headline.
- Betting promotions and `/betting/` URLs are dropped. Injury reports, polls, and signings stay.
- A ticker is attached only for a rates, U.S. inflation, energy-supply, AI-market, cyber, or biotech headline, and the sentence says it is not a forecast.
- Glossary hits are whole phrases, so "better options" is not defined as a derivative.
- Empty feeds, malformed items, mixed timestamp formats, and emails with missing links have tests.

## Several sources, one report

Default inputs are the Federal Reserve, CNBC, BBC, NPR, The Guardian, Al Jazeera, ESPN, and CBS, plus optional TMDB. The report lists more than one publisher when they covered the event, and it does not blend their blurbs into a paragraph that no single source wrote.

## A report someone can use

The email is the product: an overview, a short card, a timestamp, and links. Market lines are context next to a disclaimer. The system does not invent a "why it matters" sentence when the feed did not say what happens next.

## What this is not

It is not a production newsroom system. It runs on one PC. Clustering misses paraphrases that share no distinctive words and can still join a fast-moving story that reuses the same names. Theme tags are keywords. Quotes depend on a public chart endpoint that can change. Those limits are documented in the README and in the audit so the design can be discussed honestly.
