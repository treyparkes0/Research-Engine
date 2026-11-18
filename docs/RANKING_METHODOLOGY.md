# Ranking methodology

Stories are ranked with a fixed formula. There is no model, no learned weight, and no hidden score. The constants live in `src/research_intel/process/rank.py`.

## What gets a score

Headlines from the last 36 hours (seven days for movies, using fetch time so a release date in the past does not hide this week's slate) are clustered into events. Each cluster is one story. The score is:

```
score = 4.0 * independent publishers
      + recency
      + substance
      + subject bonus
```

`independent publishers` is the number of distinct sources in the cluster. A second or third copy of the same headline from one feed does not change this number and does not add any other points.

`recency` uses the newest timestamp in the cluster. It is 5.0 when the story is new and falls in a straight line to 0 at 36 hours. Older than that, the recency term is 0. A timestamp that cannot be parsed sorts as ancient, so a broken date cannot float to the top.

`substance` is 1.0 when at least one publisher saved a blurb of 80 characters or more that is not a copy of the headline. It is 1.5 when two or more publishers did. Headline-only items score 0 on this term. The bonus is small on purpose: a thin exclusive item can still appear, but it does not outrank several outlets covering a story that actually has a blurb.

`subject bonus` applies only in sports and movies. Preferred leagues (NFL, college football, NBA, college basketball, tennis, NHL, UFC, Mets) add about 2.8 to 4.0. Other sports get a small penalty and can still fill a leftover slot. Soccer and betting promotions score nothing and are removed. Movies add 4.0 for a this-week release, 3.5 for now-playing, and 3.0 for industry coverage. A television or celebrity item with no film cue is removed.

## What the score is not

The formula does not measure importance beyond "more independent outlets covered it, it is recent, and the feed actually said something." A single-source scoop can lose to a widely copied item. That is a limitation of headline clustering, and it is stated here rather than papered over with a second score.

There is no sentiment model, no entity graph, and no click history. Theme tags (a keyword list in `generate/themes.py`) are labels on the card. They are not added to the rank.

## Selection after the score

Each domain keeps five stories.

Sports takes the highest story in each preferred league first, then fills the remaining slots by score, so one league does not occupy every line. Movies reserve a slot for a this-week title, a now-playing title, and an industry item when those exist. The lead story in the overview is still rank 1 after that pass. A later cleanup does not re-sort the sports list by raw score, which used to undo the spread.

If the same event is selected in two sections, the lower score is archived and the next candidate in that section is promoted when it is not the same event. "Fed holds rates" and "ECB holds rates" both stay. Two wordings of the Nvidia investigation do not.

## Why a duplicate feed row cannot inflate a story

Before this rule, the score added one point per article. A publisher that repeated a betting preview nine times could outrank a game story carried by two outlets. The article count is no longer in the formula. Tests in `tests/test_ranking.py` lock that behavior: three copies from one source score the same as one copy, and two publishers score higher than those copies.
