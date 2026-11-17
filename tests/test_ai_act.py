"""
SAAF — EU AI Act and harmonised standards mapping tests, no API calls (issue #57).

Run with:
    python -m unittest tests.test_ai_act -v
"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from saaf.core.mapper import FrameworkMapper
from saaf.core.models import AuditInput
from saaf.knowledge.frameworks import (
    AI_ACT_STANDARDS,
    AI_ACT_STANDARDS_MAPPING,
    AI_ACT_STANDARDS_REVIEWED,
    FRAMEWORK_REGISTRY,
)
from saaf.prompts.system_prompt import build_system_prompt


def _map(country: str, topic: str = "AI Governance", industry: str = "Technology"):
    return FrameworkMapper(AuditInput(
        company_name="Test Corp", industry=industry, country=country,
        listed_status="Private", audit_topic=topic,
    )).map()


def _keys(country: str, topic: str = "AI Governance", industry: str = "Technology") -> list:
    return [m.key for m in _map(country, topic, industry).framework_matches]


class TestSelection(unittest.TestCase):
    def test_selected_for_ai_governance_in_eu(self):
        for country in ("EU", "Germany", "Netherlands", "France"):
            with self.subTest(country=country):
                self.assertIn("EU_AI_ACT", _keys(country))

    def test_selected_outside_eu_as_extraterritorial(self):
        for country in ("US", "UK", "Singapore", "Japan"):
            with self.subTest(country=country):
                match = next(m for m in _map(country).framework_matches if m.key == "EU_AI_ACT")
                self.assertIn("Extraterritorial", match.rationale)

    def test_selected_for_every_industry(self):
        for industry in ("Healthcare", "Financial Services", "Government", "Retail"):
            with self.subTest(industry=industry):
                self.assertIn("EU_AI_ACT", _keys("EU", industry=industry))

    def test_not_selected_for_other_topics(self):
        for topic in ("Cybersecurity", "Data Privacy", "Financial Reporting", "Anti-Money Laundering"):
            with self.subTest(topic=topic):
                self.assertNotIn("EU_AI_ACT", _keys("EU", topic=topic))


class TestStandardsMapping(unittest.TestCase):
    def test_covers_high_risk_requirements(self):
        # Arts. 9-15 and 17 are the high-risk requirements the standardisation request covers
        expected = {f"Art. {n}" for n in (9, 10, 11, 12, 13, 14, 15, 17)}
        self.assertEqual(set(AI_ACT_STANDARDS_MAPPING), expected)

    def test_every_mapped_standard_is_defined(self):
        for article, (_, codes) in AI_ACT_STANDARDS_MAPPING.items():
            self.assertTrue(codes, f"{article} has no standard")
            for code in codes:
                with self.subTest(article=article, code=code):
                    self.assertIn(code, AI_ACT_STANDARDS)

    def test_every_standard_is_mapped(self):
        mapped = {c for _, codes in AI_ACT_STANDARDS_MAPPING.values() for c in codes}
        self.assertEqual(mapped, set(AI_ACT_STANDARDS))

    def test_only_cited_standards_drop_the_draft_prefix(self):
        # A standard is "EN" once published; a draft keeps "prEN" and cannot be cited
        for code, std in AI_ACT_STANDARDS.items():
            with self.subTest(code=code):
                self.assertEqual(code.startswith("prEN"), not std["cited"])
                if std["cited"]:
                    self.assertEqual(std["stage"], 60)

    def test_quality_management_is_the_cited_standard(self):
        self.assertTrue(AI_ACT_STANDARDS["EN 18286"]["cited"])
        self.assertIn("EN 18286", AI_ACT_STANDARDS_MAPPING["Art. 17"][1])

    def test_former_numbers_kept_for_renumbered_drafts(self):
        self.assertEqual(AI_ACT_STANDARDS["prEN 18229-8"]["formerly"], "prEN 18282")
        self.assertEqual(AI_ACT_STANDARDS["prEN 18229-1"]["formerly"], "prEN 18284")


class TestRegistryEntry(unittest.TestCase):
    def setUp(self):
        self.entry = FRAMEWORK_REGISTRY["EU_AI_ACT"]

    def test_one_domain_per_article_with_status(self):
        domains = self.entry["domains"]
        self.assertEqual(len(domains), len(AI_ACT_STANDARDS_MAPPING))
        art15 = next(d for d in domains if "Art. 15 " in d)
        self.assertIn("prEN 18229-8", art15)
        self.assertIn("not cited", art15)
        art17 = next(d for d in domains if "Art. 17 " in d)
        self.assertIn("cited in the OJEU", art17)

    def test_provenance(self):
        self.assertEqual(self.entry["source"], "https://eur-lex.europa.eu/eli/reg/2024/1689/oj")
        self.assertEqual(self.entry["last_reviewed"], AI_ACT_STANDARDS_REVIEWED)
        date.fromisoformat(AI_ACT_STANDARDS_REVIEWED)

    def test_all_domains_reach_the_prompt(self):
        mapping = _map("EU")
        match = next(m for m in mapping.framework_matches if m.key == "EU_AI_ACT")
        self.assertEqual(match.relevant_domains, self.entry["domains"])
        audit_input = AuditInput(
            company_name="Test Corp", industry="Technology", country="EU",
            listed_status="Private", audit_topic="AI Governance",
        )
        prompt = build_system_prompt(audit_input, mapping)
        self.assertIn("EN 18286", prompt)
        self.assertIn("prEN 18228", prompt)


if __name__ == "__main__":
    unittest.main()
