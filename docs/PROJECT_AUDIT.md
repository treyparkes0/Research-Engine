# Project audit

Audit of the Research Intelligence Engine as it stood before the quality revision in this repository. The pipeline shape was kept. Fixes that followed this audit are marked **Addressed**.

The system is a local Python pipeline: public RSS (and optional TMDB) into SQLite, greedy headline clustering, a transparent score, a template writer, and an optional Gmail SMTP send. It does not call an LLM.

## Architecture and workflow

```
RSS feeds (+ optional TMDB)
    -> ingest.feeds / ingest.tmdb
    -> SQLite (sources, articles, ingest_runs)
    -> process.pick_topics
         cluster headlines (process.cluster, process.text)
         score and select (process.rank, sports_focus, movies_focus)
         drop a story that was selected in more than one slot
    -> generate.brief
         optional enrichment (Guardian / NYT / NewsAPI if a key is set)
         ticker context (markets.impact)
         template card (generate.template_writer, generate.analyze)
    -> Markdown + JSON on disk, rows in briefs / topic_cards
    -> deliver.email + deliver.html_email (optional)
    -> process.cleanup
```

Orchestration lives in `jobs/run_daily.py`. Windows Task Scheduler runs the morning brief at 6:30 AM local via `scripts/install_schedule.ps1`. A morning run at or after 9:00 AM local is skipped unless `--allow-late` is passed. Evening runs are manual.

Domains are fixed: markets, business, world, sports, movies. Default feeds are in `config.py`. Storage defaults: articles 21 days, brief rows 90 days, four newest brief files per extension.

## What was implemented and functioning

- Feed ingest with per-feed failure isolation, URL uniqueness, and a content hash.
- Sports filters for soccer and some betting-app brands. MLB is limited to Mets coverage.
- Movie ingest from Guardian Film and BBC culture, plus optional TMDB now-playing and upcoming lists restricted to English-speaking productions in a current-week or new-release window.
- Greedy title clustering and a top-five selection per domain, with sports and movie diversity passes.
- A cross-section pass that tries not to select the same label twice.
- Template cards built from feed blurbs, with a same-story check on enrichment headlines.
- Ticker lines limited to a personal watchlist and a short keyword list, with a written disclaimer.
- Markdown and HTML email of the same brief, plus quote context from Yahoo's chart endpoint.
- Retention cleanup and a morning cutoff so a late wake-up does not send a stale morning brief.
- One unittest module covering a handful of known brief failures.

No paid API is required. Guardian, NewsAPI, NYT, and TMDB keys are optional. If they are absent, the brief still runs from RSS.

## Differences from the README (before this revision)

The README described the intended rules more strictly than the code enforced them.

| README claim | What the code actually did |
|---|---|
| Stock lines only for rates, oil, AI, cyber, or biotech | Bare words such as `inflation`, `nvidia`, `fed`, and `ai` attached broad ETFs, including on a China inflation print and an executive-misconduct story. The explanation text said the headline can "nudge" the market. |
| Betting-app promos are dropped | Brand names and a few promo phrases were dropped. Odds, best-bet, player-prop, and `/betting/` headlines still led the sports section. |
| The same story is not repeated in two sections | Dedup compared label token overlap at 0.42. Nvidia's investigation and the Dana White press-secretary story each appeared twice, because the headlines did not share enough tokens. |
| Enrichment is kept only when it is the same story | API hits are filtered with `headline_matches`. The card writer could still blend several articles in one cluster into one paragraph, and could fall back to unsupported sentences. |
| Original brief wording | The writer mostly concatenates publisher feed sentences. It does not paraphrase with a model. |
| Checks live in `tests/test_brief_quality.py` | True, and that was the only test module. Retention, ingest edges, ranking, and email were untested. |

`FREE_AND_LEGAL.md` also said the writer produces original wording and mentioned Ollama as a possible later addition. Ollama is not implemented.

## Bugs and edge cases

**Addressed.**

1. **Over-merge.** Clustering used Jaccard at 0.28, plus a bonus when two long tokens matched. Distinct headlines that shared a person and a generic word could become one topic. The cluster label preferred the shortest title, which favored teasers over the latest development.
2. **Under-merge across sections.** The same event copied in different words (Nvidia investigation, Dana White) survived in two domains. Token overlap on the raw label was too weak, and there is no stemmer in the old dedup.
3. **One publisher inflating rank.** Score was `sources * 3 + articles * 1 + recency`. Extra copies of the same headline from one feed raised the score.
4. **Betting copy in the sports lead.** The November 8 sample led sports with a first-touchdown betting preview. `is_betting_promo` did not treat odds, best bets, player props, or `/betting/` URLs as promotions. "Playoff odds" and "signing bonus" needed to stay.
5. **Ticker false associations.** China wholesale inflation received SPY and SCHG with text that claimed a U.S. market reaction. The Nvidia affair received QQQ and SCHG with AI-sector text. Reasons were causal ("can nudge", "can move"). `IMPACT_MAP` in `watchlist.py` was unused dead weight beside the live title rules.
6. **Glossary false hits.** The word `options` in "better options" was defined as a derivatives contract. Theme *names* were passed into the glossary, so a card was given a "Geopolitics" definition when the article never used that word. Movie plots that mentioned a country picked up the same tag.
7. **Truncated sentences.** Abbreviations such as `No.` were treated as sentence ends, so a rankings blurb became "1 for the second time this season...".
8. **Repeated blurbs.** Exact doubled paragraphs were collapsed. Paraphrased repeats in one feed field (the BYD raid blurb) were not.
9. **Movie cards were plot dumps.** TMDB summaries stored a long overview and review excerpts. The writer then stripped the release-date and audience-score sentences as boilerplate, so the card kept the plot and the at-a-glance line truncated it. Fetch time was labeled as the publication time.
10. **BBC culture was a wide net.** `actor`, `actress`, `director`, and `streaming` alone were enough to treat a TV or celebrity item as film coverage.
11. **Retention timestamps did not compare cleanly.** Feed times are ISO-8601 (`T`, offset). SQLite defaults are `YYYY-MM-DD HH:MM:SS`. String comparison is wrong around the separator. Cleanup could drop or keep boundary rows for the wrong reason.
12. **Bad timestamps looked brand new.** `ArticleRef.when()` fell back to `datetime.now()` when a date failed to parse, which could rank a broken row as fresh.
13. **Diversity order was overwritten.** After the sports diversity pass, a later update sorted selected rows by score only, so the lead could ignore the bucket order the selector had just chosen.
14. **HTML and Markdown drifted.** HTML omitted source headlines that Markdown included. Neither layout had a stable "what happened / why it matters / read more" structure. The at-a-glance line was whatever first sentence survived, including betting copy and truncated plots.
15. **Filler analysis.** `what_is_open` wrote speculative gaps ("we still may not know the other side"). It was stored on the card even though the email did not show it. The article-of-the-day blurb implied a thematic conclusion ("see how it sits with Geopolitics") from a keyword count.

**Left as limitations (not fully solvable with feed headlines).**

- Clustering is lexical. A paraphrase that shares no distinctive words will not join. A fast-moving storyline that reuses the same names can still join.
- "Why it matters" is only a later sentence from the same blurb when that sentence is explicitly forward-looking. Many cards will not have one. That is preferable to a generated consequence.
- Country and conflict keywords are still a blunt theme tagger. They are not shown as definitions unless the word appears in the text.
- Yahoo quotes and optional news APIs can fail or change without notice. Failures are skipped per call.
- The morning job only runs when the PC is on and the user is logged in. That is Task Scheduler behavior, not a service.
- SQLite string dates remain mixed in older rows. New comparisons normalize both formats. The project does not migrate every legacy timestamp.
- Schema tables `entities`, `article_entities`, `topic_themes`, `related`, and `user_feedback` are unused. They were left in place so existing database files still open. `extract_explore_terms` is unused.
- TMDB "this week" follows the machine's local calendar week (Monday–Sunday). A title near the boundary can fall in or out depending on the clock.
- Soccer filtering is keyword-based and can drop a non-soccer "World Cup" story. That matches the existing personal scope (no soccer) and is documented as a limitation.

## Redundant or easy-to-simplify pieces

- `IMPACT_MAP` duplicated ticker ideas that the live path no longer consulted. **Addressed** by removing it.
- Review excerpts were fetched from TMDB and then pasted into the blurb. **Addressed** by stopping that fetch and storing a short release line plus a capped plot sentence.
- `research_snapshot` and `key_takeaways` were computed and stored but not rendered. They still are stored, now as factual coverage notes and the sentences actually used, so the database does not hold speculative filler.
- Enrichment, themes, glossary, and ticker code overlap on keywords. They were not folded into one framework. Each rule stays local and testable.

## Reliability and content-quality weaknesses

The November 8, 2026 evening sample (`docs/sample-brief.md` as it was) showed the user-visible result:

- Sports at-a-glance was a betting promo, and that promo occupied three of the displayed sports links.
- Movies at-a-glance was a plot sentence cut off with an ellipsis.
- Business and world both carried the Nvidia affair. World and sports both carried Dana White.
- China inflation and the Nvidia affair were paired with Nasdaq or S&P funds and causal wording.
- A healthcare story defined "options" as a derivative.
- A movie plot that mentioned the Russian mafia was tagged geopolitics.
- Several summaries repeated themselves or started mid-thought.

Trust fails when the headline, the paragraph, and the ticker disagree. Those were the highest-priority fixes. Ranking and presentation were next. Documentation was behind the code and overclaimed "original wording."

## Recommended fixes, in the order they were applied

1. Make each card's paragraph come from one on-story feed blurb. Keep other outlets as links. Reject enrichment sentences that do not support the headline. **Addressed.**
2. Replace low-threshold clustering with a same-story test that refuses parallel headlines with different named subjects (Fed vs ECB, two clubs, two companies' different events). **Addressed.**
3. Score independent publishers, recency, and whether a real blurb exists. Do not add points for extra rows from the same feed. **Addressed.** Documented in `docs/RANKING_METHODOLOGY.md`.
4. Widen betting detection without dropping injury reports, polls, signings, or playoff odds. **Addressed.**
5. Attach a ticker only on a defensible market, sector, or company headline, and describe it as context. **Addressed.**
6. Shorten movie cards to title, release, audience score, and a short plot sentence. Tighten film-vs-TV filtering. **Addressed.**
7. Fix glossary word boundaries, abbreviation splitting, paraphrase repeats, retention timestamps, and bad-date ranking. **Addressed.**
8. Align Markdown and HTML around an executive overview, what happened, why it matters, and where to read more. **Addressed.**
9. Expand tests around those business rules and run them. **Addressed.** See the test modules under `tests/`.
10. Rewrite the README and add architecture, overview, and AI-enablement notes that match the code. **Addressed.**

No new services, paid APIs, or model dependencies were added.
