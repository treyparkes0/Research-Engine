"""Sports promos, film scope, and ticker associations."""

from __future__ import annotations

import unittest

from research_intel.ingest.tmdb import _movie_summary
from research_intel.markets.impact import _symbols_for_topic
from research_intel.process.movies_focus import is_film_related, movies_bucket, movies_focus_bonus
from research_intel.process.sports_focus import is_betting_promo, is_soccer, sports_focus_bonus


class SportsTests(unittest.TestCase):
    def test_betting_promotions_are_dropped(self) -> None:
        headlines = [
            "Week 3 NFL betting promos: Score almost $3,000 in bonuses from DraftKings",
            "Buccaneers vs. Bears odds: NFL Week 9 Sunday Night Football first touchdown scorer picks, predictions",
            "Expert's best bets and player props for Sunday Night Football",
            "https://www.cbssports.com/betting/news/bears-preview/",
        ]
        for headline in headlines:
            self.assertTrue(is_betting_promo(headline), headline)
            self.assertIsNone(sports_focus_bonus(headline))

    def test_legitimate_sports_reporting_is_kept(self) -> None:
        headlines = [
            "AP Top 25 poll: Florida climbs after a win over Ole Miss",
            "Star quarterback listed as questionable with an ankle injury",
            "Mets re-sign pitcher Stock, 36-year-old righty, to a one-year contract",
            "Playoff odds improve for the Giants after a road win",
            "Receiver agrees to a contract that includes a signing bonus",
        ]
        for headline in headlines:
            self.assertFalse(is_betting_promo(headline), headline)
            self.assertIsNotNone(sports_focus_bonus(headline), headline)

    def test_soccer_is_out_of_scope_and_nfl_is_not(self) -> None:
        self.assertTrue(is_soccer("Manchester City win the Premier League"))
        self.assertFalse(is_soccer("Chiefs quarterback leaves the game with a shoulder injury"))


class MovieTests(unittest.TestCase):
    def test_summary_keeps_title_and_release_and_caps_the_plot(self) -> None:
        overview = (
            "When eccentric young governess Winifred Notty arrives at a remote Gothic manor, "
            "a string of unsettling events leads the household to suspect she isn't who she claims to be, "
            "but the truth may be far more dangerous than they imagine. "
            "The household then discovers a second secret in the east wing."
        )
        text = _movie_summary(
            {
                "title": "Victorian Psycho",
                "overview": overview,
                "release_date": "2026-11-14",
                "vote_average": 6.4,
                "vote_count": 80,
            },
            "This Week",
        )
        self.assertIn("Victorian Psycho", text)
        self.assertIn("2026-11-14", text)
        self.assertIn("audience score", text)
        self.assertNotIn("Viewer notes", text)
        self.assertLess(len(text), 420)
        self.assertLess(text.lower().count("winifred"), 2)

    def test_tv_and_celebrity_items_are_not_film_coverage(self) -> None:
        self.assertFalse(is_film_related("Netflix renews its flagship streaming series for three seasons"))
        self.assertIsNone(movies_bucket("Netflix renews its flagship streaming series for three seasons"))
        self.assertIsNone(movies_focus_bonus("A radio host wins a music award"))
        self.assertTrue(is_film_related("Director discusses his new film after the festival premiere"))
        self.assertEqual(
            movies_bucket("[This Week] Victorian Psycho is scheduled to open in theaters"),
            "this_week",
        )


class TickerTests(unittest.TestCase):
    def test_invalid_associations_are_refused(self) -> None:
        cases = [
            "Most of UK's essential food supply grown in drought-risk areas, report warns",
            "Huge crowds greet Pope in Paris for open-air Mass",
            "China wholesale inflation hits highest in more than four years",
            "Nvidia launches investigation into CEO's affair with suspected Chinese spy",
            "US chipmaker Nvidia investigates CEO Jensen Huang over affair",
            "Missile strike raises tensions in the region",
            "Democrats amp up Trump investigation threats",
        ]
        for title in cases:
            self.assertEqual(_symbols_for_topic([], title, "world"), [], title)
            self.assertEqual(_symbols_for_topic(["Geopolitics", "Energy Markets"], title, "business"), [], title)

    def test_defensible_market_headlines_keep_context(self) -> None:
        rates = [sym for sym, _ in _symbols_for_topic([], "Fed holds interest rates steady", "markets")]
        self.assertEqual(rates, ["SPY"])
        ai = [sym for sym, _ in _symbols_for_topic([], "Meta thinks it has an AI device", "business")]
        self.assertIn("QQQ", ai)
        oil = [sym for sym, _ in _symbols_for_topic([], "Oil prices jump after a tanker scare near Hormuz", "markets")]
        self.assertEqual(oil, ["FNARX"])
        self.assertEqual(_symbols_for_topic([], "Quarterback injury report", "sports"), [])

    def test_ticker_language_is_not_a_prediction(self) -> None:
        from research_intel.markets.impact import DISCLAIMER, _reason_for

        for symbol in ("SPY", "QQQ", "FNARX", "IBB", "CIBR", "SCHG"):
            reason = _reason_for(symbol, "context", "Fed holds interest rates steady").lower()
            self.assertNotIn("nudge", reason)
            self.assertNotIn("forecast", reason.split("not a forecast")[0])
            self.assertTrue("not a forecast" in reason or "not a recommendation" in reason)
        self.assertIn("not a prediction", DISCLAIMER.lower())
        self.assertIn("not a claim", DISCLAIMER.lower())


if __name__ == "__main__":
    unittest.main()
