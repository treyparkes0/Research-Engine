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
from research_intel.generate.glossary import definitions_for_text
from research_intel.generate.render import first_sentence, overview_line, polish_title
from research_intel.generate.template_writer import TopicCard
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

    def test_second_article_cannot_change_the_headline_story(self) -> None:
        title = "Thames Water should be placed in temporary public control"
        sources = [
            _Source(
                title,
                "Bill payers should not fund another Thames Water rescue. "
                "A parliamentary committee said the company should be placed in temporary state control.",
            ),
            _Source(
                "Burnham wardrobe era begins in Westminster",
                "The new prime minister is ushering in a Westminster dressing era with a relaxed new look.",
            ),
        ]
        body = what_happened(title, collect_facts(title, sources))
        self.assertIn("Thames Water", body)
        self.assertNotIn("wardrobe", body.lower())
        self.assertNotIn("dressing", body.lower())

    def test_empty_feed_summary_stays_short(self) -> None:
        title = "Mets re-sign pitcher Stock to a one-year contract"
        body = what_happened(title, collect_facts(title, [_Source(title, "")]))
        self.assertIn("feeds only repeat the headline", body)
        self.assertNotIn("expected to", body.lower())

    def test_repeated_paraphrase_is_collapsed(self) -> None:
        text = (
            "Bailiffs reportedly seized digital records before a court case over the Land Rover Defender. "
            "Bailiffs acting for Jaguar Land Rover raided BYD offices over whether its Defender clone infringes intellectual property rights. "
            "Bailiffs reportedly seized digital records from BYD offices in the Netherlands before that court case."
        )
        collapsed = collapse_repeated_text(text)
        self.assertEqual(collapsed.lower().count("seized digital records"), 1)
        self.assertIn("Defender", collapsed)

    def test_distinct_sentences_are_kept(self) -> None:
        text = (
            "The company raised its full-year guidance after earnings beat estimates. "
            "Shares rose in early trading as investors reacted to the outlook."
        )
        collapsed = collapse_repeated_text(text)
        self.assertIn("guidance", collapsed)
        self.assertIn("Shares rose", collapsed)

    def test_no_abbreviation_is_not_a_sentence_break(self) -> None:
        glance = first_sentence(
            "Georgia is No. 1 for the second time this season after a win over Ole Miss."
        )
        self.assertIn("No. 1", glance)
        self.assertIn("Ole Miss", glance)

    def test_ordinary_options_is_not_a_derivative(self) -> None:
        lines = definitions_for_text(
            "US employers keep passing rising healthcare costs to workers. There are better options."
        )
        self.assertFalse(any(line.lower().startswith("options:") for line in lines))
        self.assertFalse(any("buy or sell" in line.lower() for line in lines))

    def test_overview_drops_a_sentence_that_does_not_support_the_headline(self) -> None:
        card = TopicCard(
            topic_id=1,
            domain="business",
            rank=1,
            title="Thames Water should be placed in temporary public control",
            executive_summary="A wardrobe era has begun in Westminster this season.",
            why_it_matters="",
            key_takeaways=[],
            research_snapshot="",
            further_research=[],
            definitions=[],
            sources=[],
        )
        line = overview_line(card)
        self.assertIn("Thames Water", line)
        self.assertNotIn("wardrobe", line.lower())


if __name__ == "__main__":
    unittest.main()
