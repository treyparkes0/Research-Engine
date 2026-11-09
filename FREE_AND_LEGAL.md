# Free and legal rules

This project is for **personal learning**, not a commercial news product.

These rules are practical guidelines, not formal legal advice.

## What we use (free)

| Piece | Free choice |
|---|---|
| News | Public RSS feeds publishers already offer |
| Database | SQLite on your computer |
| Ranking topics | Your own code (no paid API needed) |
| Writing briefs | Your own template code, from the feed headline and blurb |
| Delivery | Save a file to disk first; email yourself with Gmail if you want |

No paid news API is required.

## What is allowed

- Read **official RSS feeds** (title, link, short description the publisher put in the feed)
- Store that feed text in your private database
- Write **your own** summaries and research notes from that material
- Link back to the original article
- Use it for yourself

## What we do not do

- Scrape full paywalled articles
- Copy full article text into emails or a public site
- Resell or republish other people’s news as a product
- Bypass login walls, CAPTCHAs, or site blocks
- Pretend AI text is the original reporting

## Writing briefs the right way

The template writer should:

1. Read only what we already saved from the feed
2. Write original wording
3. Always include source links
4. Say when something is uncertain

If a feed only gives a headline and one sentence, the brief stays short. That is fine and legal.

## Sources in this project

Prefer publishers that publish RSS on purpose (BBC, NPR, Guardian, Al Jazeera, and similar).

Commercial feeds (CNBC, MarketWatch, ESPN, Yahoo) are only used when they provide a public RSS URL. We still only keep feed title/summary/link — never a scraped full page.

Edit `src/research_intel/config.py` anytime. If a site blocks or removes its feed, drop it.

## Cost floor

You can run the whole pipeline at **$0**:

1. Pull RSS → SQLite  
2. Rank topics with code  
3. Write briefs with your own template code  
4. Save HTML/Markdown to `data/briefs/`  

Email is optional. A local model such as Ollama can be added later.
