"""Real parse/render/mapping paths with synthetic responses; no provider calls.

Mapping expectations are invariants of the shipped registry/matrix, not an
independent assessment of the legal applicability of those entries.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sentinel_adapter as adapter
from saaf.core.agent import ComplianceReportError
from saaf.core.mapper import FrameworkMapper
from saaf.core.models import DISCLAIMER, AuditInput, ComplianceReport
from saaf.knowledge.frameworks import FRAMEWORK_REGISTRY
from saaf.prompts.system_prompt import build_system_prompt


class AdapterContractTests(unittest.TestCase):
    def setUp(self):
        # Fail immediately if the adapter starts constructing a real provider.
        factory = patch("saaf.core.agent.create_client", side_effect=AssertionError("No provider"))
        factory.start()
        self.addCleanup(factory.stop)

    def test_valid_response_runs_real_pipeline(self):
        report = adapter.parse(json.dumps(adapter.model_output()), adapter.trusted_input())
        self.assertIsInstance(report, ComplianceReport)
        self.assertEqual(report.audit_input, adapter.trusted_input())
        self.assertEqual(report.disclaimer, DISCLAIMER)
        self.assertEqual(len(report.reference_checks), 3)
        self.assertTrue(all(r.status == "unverified" for r in report.reference_checks))
        self.assertTrue(all(r.confidence < 1 for r in report.reference_checks))

    def test_model_cannot_overwrite_trusted_fields_or_reference_checks(self):
        payload = {**adapter.model_output(), **adapter.AGENT_OWNED}
        report = adapter.parse(json.dumps(payload), adapter.trusted_input())
        self.assertEqual(report.audit_input, adapter.trusted_input())
        self.assertEqual(report.disclaimer, DISCLAIMER)
        self.assertNotIn("Model-written warning", report.warnings)
        self.assertEqual(len(report.reference_checks), 3)
        self.assertTrue(all(r.confidence < 0.99 for r in report.reference_checks))
        # report_id/generated_at are a separately documented open issue (#74).

    def test_invalid_json_and_schema_are_rejected(self):
        for raw in ("not JSON", '{"gap_risk_summary": {}}'):
            with self.subTest(raw=raw), self.assertRaises(ComplianceReportError):
                adapter.parse(raw, adapter.trusted_input())

    def test_unmapped_framework_is_rejected(self):
        payload = adapter.model_output()
        payload["framework_assessments"][0]["framework_name"] = "Invented Test Framework"
        with self.assertRaisesRegex(ComplianceReportError, "outside the mapped set"):
            adapter.parse(json.dumps(payload), adapter.trusted_input())

    def test_actual_verbose_render_shows_synthetic_output_and_restores_console(self):
        previous = adapter.formatter.console
        report = adapter.parse(json.dumps(adapter.model_output()), adapter.trusted_input())
        rendered = adapter.render(report)
        self.assertIn("Entity A", rendered)
        self.assertIn("GDPR-SEC-01", rendered)
        self.assertIn("Inspect the risk assessment.", rendered)
        self.assertIn("supplier oversight", rendered)
        self.assertIs(adapter.formatter.console, previous)

    def test_render_failure_restores_console_and_propagates(self):
        previous = adapter.formatter.console
        with patch.object(adapter.formatter, "render_report", side_effect=RuntimeError("fixture")):
            with self.assertRaisesRegex(RuntimeError, "fixture"):
                adapter.render(None)
        self.assertIs(adapter.formatter.console, previous)

    def test_all_2400_mapping_cases_retain_matrix_entries(self):
        cases = list(adapter.mapping_cases())
        self.assertEqual(len(cases), 2400)
        self.assertEqual(len({c["id"] for c in cases}), len(cases))
        for case in cases:
            with self.subTest(profile=case["id"]):
                self.assertFalse(case["problems"])
                self.assertLessEqual(case["mandatory"], case["selected"])
                self.assertLessEqual(case["selected"], FRAMEWORK_REGISTRY.keys())

    def test_previously_truncated_regulation_reaches_prompt_and_grounding(self):
        inp = AuditInput(company_name="Entity A", country="Australia",
                         industry="Financial Services", listed_status="Public",
                         audit_topic="Vendor Management")
        mapping = FrameworkMapper(inp).map()
        self.assertIn("APRA_CPS234", mapping.regulation_keys)
        self.assertIn("APRA_CPS234", mapping.applicable_framework_keys)
        self.assertIn(FRAMEWORK_REGISTRY["APRA_CPS234"]["full_name"],
                      build_system_prompt(inp, mapping))
        payload = adapter.model_output()
        payload["mandatory_regulations"] = []
        payload["framework_assessments"][0]["framework_name"] = "APRA_CPS234"
        payload["framework_assessments"][0]["control_objectives"] = []
        report = adapter.parse(json.dumps(payload), inp)
        self.assertEqual(report.framework_assessments[0].framework_name, "APRA_CPS234")

    def test_mapping_key_order_matches_report_order_and_is_repeatable(self):
        first = FrameworkMapper(adapter.trusted_input()).map()
        second = FrameworkMapper(adapter.trusted_input()).map()
        self.assertEqual(first, second)
        self.assertEqual(first.applicable_framework_keys, [m.key for m in first.framework_matches])
        self.assertEqual(first.regulation_keys, sorted(first.regulation_keys))
