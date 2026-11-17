"""
SAAF — ISO/IEC JTC 1/SC 42 AI standards catalogue tests, no API calls (issue #55).

Run with:
    python -m unittest tests.test_iso_sc42 -v
"""

from __future__ import annotations

import re
import sys
import unittest
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "tools" / "standards_sources"))

import iso_sc42  # noqa: E402  (tools/standards_sources/iso_sc42.py)

from saaf.core.mapper import FrameworkMapper
from saaf.core.models import AuditInput
from saaf.knowledge.frameworks import (
    FRAMEWORK_REGISTRY,
    ISO_SC42_CATALOGUE,
    ISO_SC42_STANDARDS,
)
from saaf.prompts.system_prompt import build_system_prompt

# Prefixes ISO uses for a project that is not a published deliverable yet
DRAFT_PREFIX = re.compile(r"/(?:PWI|NP|AWI|WD|CD|DIS|FDIS|DTR|DTS|PRF)\b|/(?:CD|FD|D)Amd\b")


def _input(country: str = "EU", topic: str = "AI Governance") -> AuditInput:
    return AuditInput(
        company_name="Test Corp", industry="Technology", country=country,
        listed_status="Private", audit_topic=topic,
    )


def _match(country: str = "EU", topic: str = "AI Governance"):
    mapping = FrameworkMapper(_input(country, topic)).map()
    return mapping, next((m for m in mapping.framework_matches if m.key == "ISO_IEC_SC42"), None)


class TestCatalogue(unittest.TestCase):
    def test_provenance(self):
        self.assertEqual(ISO_SC42_CATALOGUE["committee"], "ISO/IEC JTC 1/SC 42")
        self.assertTrue(ISO_SC42_CATALOGUE["source"].startswith("https://"))
        date.fromisoformat(ISO_SC42_CATALOGUE["retrieved_on"])

    def test_covers_the_catalogue(self):
        # Issue #55 counted 98 published and under-development items; the
        # catalogue grows, so only guard against a truncated file.
        self.assertGreaterEqual(len(ISO_SC42_STANDARDS), 98)
        refs = [s["reference"] for s in ISO_SC42_STANDARDS]
        self.assertEqual(len(refs), len(set(refs)), "duplicate references")

    def test_key_standards_present_and_published(self):
        by_ref = {s["reference"]: s for s in ISO_SC42_STANDARDS}
        for ref in ("ISO/IEC 42001:2023", "ISO/IEC 23894:2023", "ISO/IEC 22989:2022",
                    "ISO/IEC 42005:2025", "ISO/IEC 42006:2025", "ISO/IEC 5338:2023"):
            with self.subTest(ref=ref):
                self.assertEqual(by_ref[ref]["status"], "published")

    def test_status_matches_stage_and_reference(self):
        for std in ISO_SC42_STANDARDS:
            with self.subTest(ref=std["reference"]):
                self.assertIn(std["status"], ("published", "under development"))
                published = std["stage"] >= "60.60"
                self.assertEqual(std["status"] == "published", published)
                if published:
                    self.assertIsNotNone(std["publication_date"])
                    self.assertIsNone(DRAFT_PREFIX.search(std["reference"]))
                self.assertFalse(std["stage"].startswith("95."), "withdrawn")
                self.assertFalse(std["stage"].endswith(".98"), "deleted")


class TestBuilder(unittest.TestCase):
    def _line(self, ref: str, stage: int, committee: str = "ISO/IEC JTC 1/SC 42") -> str:
        return (
            '{"reference": "%s", "title": {"en": "T"}, "deliverableType": "IS", '
            '"currentStage": %d, "ownerCommittee": "%s", "publicationDate": null}'
            % (ref, stage, committee)
        )

    def test_keeps_published_and_drafts_drops_withdrawn_deleted_and_others(self):
        rows = iso_sc42.build([
            self._line("ISO/IEC 1:2020", 6060),
            self._line("ISO/IEC 2:2020", 9092),
            self._line("ISO/IEC CD 3", 3020),
            self._line("ISO/IEC 4:2010", 9599),
            self._line("ISO/IEC WD 5", 2098),
            self._line("ISO 6:2020", 6060, committee="ISO/TC 22"),
        ])
        got = {r["reference"]: (r["status"], r["stage"], r["under_revision"]) for r in rows}
        self.assertEqual(got, {
            "ISO/IEC 1:2020": ("published", "60.60", False),
            "ISO/IEC 2:2020": ("published", "90.92", True),
            "ISO/IEC CD 3": ("under development", "30.20", False),
        })
        self.assertEqual(rows[-1]["reference"], "ISO/IEC CD 3", "published first")


class TestMapping(unittest.TestCase):
    def test_selected_for_ai_governance_everywhere(self):
        for country in ("EU", "US", "UK", "Singapore", "Japan"):
            with self.subTest(country=country):
                self.assertIsNotNone(_match(country)[1])

    def test_not_selected_for_other_topics(self):
        for topic in ("Cybersecurity", "Data Privacy", "Financial Reporting"):
            with self.subTest(topic=topic):
                self.assertIsNone(_match(topic=topic)[1])

    def test_every_catalogue_entry_reaches_the_prompt(self):
        mapping, match = _match()
        self.assertEqual(match.relevant_domains, FRAMEWORK_REGISTRY["ISO_IEC_SC42"]["domains"])
        self.assertEqual(len(match.relevant_domains), len(ISO_SC42_STANDARDS))
        prompt = build_system_prompt(_input(), mapping)
        for std in ISO_SC42_STANDARDS:
            with self.subTest(ref=std["reference"]):
                self.assertIn(std["reference"], prompt)

    def test_drafts_are_labelled_as_not_published(self):
        domains = FRAMEWORK_REGISTRY["ISO_IEC_SC42"]["domains"]
        for std, label in zip(ISO_SC42_STANDARDS, domains, strict=True):
            with self.subTest(ref=std["reference"]):
                if std["status"] == "published":
                    self.assertNotIn("not a published standard", label)
                else:
                    self.assertIn(f"stage {std['stage']}, not a published standard", label)

    def test_no_maintainer_review_yet(self):
        self.assertIsNone(FRAMEWORK_REGISTRY["ISO_IEC_SC42"]["last_reviewed"])


if __name__ == "__main__":
    unittest.main()
