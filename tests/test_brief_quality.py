"""Locks the brief failures that made cards disagree with their headlines."""

from __future__ import annotations

import unittest

from research_intel.generate.analyze import (
    collapse_repeated_text,
    collect_facts,
    sentence_supports_title,
    separate_glued_sentences,
    what_happened,
    why_it_matters,
)
from research_intel.generate.render import first_sentence, polish_title
from research_intel.ingest.enrich import headline_matches
from research_intel.markets.impact import _symbols_for_topic
from research_intel.process.sports_focus import is_betting_promo, sports_focus_bonus
from research_intel.process.text import unwrap_repeated_phrase


class _Source:
    def __init__(self, title: str, summary: str, source_name: str = "BBC") -> None:
        self.title = title
        self.summary = summary
        self.source_name = source_name


class BriefQualityTests(unittest.TestCase):
    def test_enrichment_requires_the_same_story_not_the_same_person(self) -> None:
        topic = "The Guardian view on Thames Water: Andy Burnham should nationalise this failed monopoly"
        other = "Burnham's relaxed new look ushers in a Westminster wardrobe era"
        same = "Andy Burnham should nationalise Thames Water, the failed monopoly"
        self.assertFalse(headline_matches(topic, other))
        self.assertTrue(headline_matches(topic, same))

    def test_off_topic_sentence_is_not_the_card_body(self) -> None:
        title = "The Guardian view on Thames Water: Andy Burnham should nationalise this failed monopoly"
        sources = [
            _Source(
                title,
                "Bill payers should not fund another rescue. "
                "A parliamentary committee said Thames Water should be placed in temporary state control.",
            )
        ]
        facts = collect_facts(
            title,
            sources,
            enrichment=type(
                "E",
                (),
                {
                    "extra_text": (
                        "The new British prime minister is ushering in a new era of Westminster dressing. "
                        "Charismatic and northern, Mr. Burnham is a contrast to Keir Starmer."
                    ),
                    "provider": "guardian",
                },
            )(),
        )
        body = what_happened(title, facts)
        self.assertIn("Thames Water", body)
        self.assertNotIn("wardrobe", body.lower())
        self.assertNotIn("dressing", body.lower())

    def test_injury_time_is_not_a_player_injury(self) -> None:
        facts = [
            (
                "Guardian",
                "If a guilty verdict is upheld, the club's modern titles will be tainted.",
            ),
            (
                "Guardian",
                "Scored in injury time on the last day of the season, the goal delivered the title.",
            ),
            (
                "Guardian",
                "Supporters still rank that goal among the greatest moments.",
            ),
        ]
        why = why_it_matters(facts, title="The Guardian view on Manchester City: a strange kind of glory")
        self.assertNotIn("who can play", why)

    def test_stocks_follow_the_headline_only(self) -> None:
        drought = _symbols_for_topic(
            ["Energy Markets", "Geopolitics"],
            "Most of UK's essential food supply grown in drought-risk areas, report warns",
            "business",
        )
        self.assertEqual(drought, [])
        pope = _symbols_for_topic(
            ["Artificial Intelligence"],
            "Huge crowds greet Pope in Paris for open-air Mass",
            "world",
        )
        self.assertEqual(pope, [])
        rates = [sym for sym, _ in _symbols_for_topic([], "Fed holds interest rates steady", "markets")]
        self.assertIn("SPY", rates)
        ai = [sym for sym, _ in _symbols_for_topic([], "Meta thinks it has an AI device", "business")]
        self.assertIn("QQQ", ai)

    def test_repeated_blurb_collapses_and_glance_keeps_mr(self) -> None:
        glued = (
            "Airport chiefs say the 2035 deadline is unachievable as critics object. "
            "Airport chiefs say the 2035 deadline is unachievable as critics object."
        )
        collapsed = collapse_repeated_text(glued)
        self.assertEqual(collapsed.lower().count("airport chiefs"), 1)
        glance = first_sentence(
            "Andy Burnham has not yet met President Trump, but the two men spoke shortly after Mr. Burnham became prime minister."
        )
        self.assertIn("Mr. Burnham", glance)
        self.assertFalse(sentence_supports_title("Thames Water monopoly", "A wardrobe era has begun in Westminster."))
        glued = separate_glued_sentences(
            "Public ownership can end the cycle of failure This month, a committee said Thames Water should be placed in temporary state control."
        )
        self.assertIn("failure. This month", glued)
        self.assertIn("Thames Water", glued)
        self.assertNotIn("Thames. Water", glued)

    def test_betting_promo_and_repeated_movie_title(self) -> None:
        promo = "Week 3 NFL betting promos: Score almost $3,000 in bonuses from DraftKings"
        self.assertTrue(is_betting_promo(promo))
        self.assertIsNone(sports_focus_bonus(promo))
        self.assertFalse(is_betting_promo("AP Top 25 poll: Florida climbs after win over Ole Miss"))
        self.assertEqual(
            unwrap_repeated_phrase("[This Week] Your Mother Your Mother Your Mother"),
            "[This Week] Your Mother",
        )
        self.assertEqual(
            polish_title("The Guardian view on Manchester City: a strange kind of glory | Editorial"),
            "The Guardian view on Manchester City: a strange kind of glory",
        )


if __name__ == "__main__":
    unittest.main()
