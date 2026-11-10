"""
Rendering tests for issue #44: model-written and user-supplied text must print
literally, never as Rich markup, and must not carry control characters to the
terminal. Normal reports keep their styling.

No API calls: reports are built by hand and the agent is mocked.
"""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rich.console import Console

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

from test_agent_run import _make_input

import cli
from saaf.core.agent import ComplianceReportError
from saaf.core.mapper import FrameworkMapper
from saaf.core.models import ComplianceReport
from saaf.output import formatter

# (text the model writes, text the reader should see)
PAYLOADS = [
    ("See clause [/dim] for detail.", "See clause [/dim] for detail."),
    ("See clause [/nonsense] for detail.", "See clause [/nonsense] for detail."),
    ("Click [link=https://example.invalid/x]here[/link]",
     "Click [link=https://example.invalid/x]here[/link]"),
    ("\x1b[31mred\x1b[0m and \x9b31m", "[31mred[0m and 31m"),
    # A control character must not hide a tag that appears once it is stripped
    ("Hidden [\x00/dim] tag", "Hidden [/dim] tag"),
    ("Art. 32[1]", "Art. 32[1]"),
    ("Art. 5(1)[b]", "Art. 5(1)[b]"),
]

# (path to a free-text field, times it is printed in a verbose report)
FIELDS = [
    ("report_id", 1),
    ("generated_at", 1),
    ("warnings.0", 1),
    ("audit_input.company_name", 1),
    ("audit_input.country", 1),
    ("mandatory_regulations.0.regulation_name", 1),
    ("mandatory_regulations.0.jurisdiction", 1),
    ("mandatory_regulations.0.applicable_sections.0", 1),
    ("mandatory_regulations.0.compliance_notes", 1),
    ("framework_assessments.0.framework_name", 1),
    ("framework_assessments.0.applicability_rationale", 1),
    ("framework_assessments.0.key_gaps.0", 1),
    # Controls appear in the table and again in the verbose detail panel
    ("framework_assessments.0.control_objectives.0.control_id", 2),
    ("framework_assessments.0.control_objectives.0.description", 2),
    ("framework_assessments.0.control_objectives.0.requirement_source", 2),
    ("framework_assessments.0.control_objectives.0.testing_approach", 1),
    ("gap_risk_summary.executive_summary", 1),
    ("gap_risk_summary.critical_gaps.0", 1),
    ("gap_risk_summary.recommended_priority_actions.0", 1),
    ("reference_checks.0.location", 1),
    ("reference_checks.0.reference", 1),
    ("reference_checks.0.note", 1),
]


def _report_data() -> dict:
    """A schema-valid report with one entry in every list, using plain text."""
    return {
        "report_id": "report-1",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "audit_input": _make_input().model_dump(),
        "warnings": ["warning text"],
        "mandatory_regulations": [{
            "regulation_name": "regulation",
            "jurisdiction": "jurisdiction",
            "mandatory": True,
            "applicable_sections": ["section"],
            "compliance_notes": "notes",
        }],
        "framework_assessments": [{
            "framework_name": "framework",
            "applicability_rationale": "rationale",
            "risk_rating": "High",
            "key_gaps": ["key gap"],
            "control_objectives": [{
                "control_id": "CTRL-1",
                "description": "description",
                "requirement_source": "source",
                "testing_approach": "approach",
                "priority": "High",
            }],
        }],
        "gap_risk_summary": {
            "overall_risk_rating": "Critical",
            "critical_gaps": ["critical gap"],
            "recommended_priority_actions": ["action"],
            "estimated_remediation_effort": "Medium",
            "executive_summary": "summary",
        },
        "reference_checks": [{
            "location": "location",
            "field": "requirement_source",
            "reference": "reference",
            "check": "identifier_not_found",
            "confidence": 0.2,
            "note": "note",
        }],
    }


def _report_with(path: str, value: str) -> ComplianceReport:
    data = _report_data()
    *parents, last = [int(p) if p.isdigit() else p for p in path.split(".")]
    node = data
    for key in parents:
        node = node[key]
    node[last] = value
    return ComplianceReport(**data)


def _render(report: ComplianceReport, console: Console) -> None:
    with patch.object(formatter, "console", console):
        formatter.render_report(report, verbose=True)


class TestReportRendersTextLiterally(unittest.TestCase):
    def test_every_field_renders_each_payload_literally(self):
        for path, times in FIELDS:
            for payload, expected in PAYLOADS:
                with self.subTest(field=path, payload=payload):
                    buf = io.StringIO()
                    _render(_report_with(path, payload),
                            Console(file=buf, width=2000, force_terminal=False))
                    out = buf.getvalue()
                    self.assertEqual(out.count(expected), times)
                    self.assertNotIn("\x1b", out)
                    self.assertNotIn("\x9b", out)

    def test_every_field_creates_no_hyperlink_on_a_terminal(self):
        payload = "Click [link=https://example.invalid/x]here[/link]"
        for path, _ in FIELDS:
            with self.subTest(field=path):
                buf = io.StringIO()
                _render(_report_with(path, payload),
                        Console(file=buf, width=2000, force_terminal=True, color_system="standard"))
                self.assertNotIn("\x1b]8;", buf.getvalue())

    def test_normal_report_keeps_styling(self):
        buf = io.StringIO()
        _render(ComplianceReport(**_report_data()),
                Console(file=buf, width=200, force_terminal=True, color_system="standard",
                        highlight=False))
        out = buf.getvalue()
        self.assertIn("\x1b[1;31mCritical Gaps:\x1b[0m", out)
        self.assertIn("\x1b[31mcritical gap\x1b[0m", out)
        self.assertIn("\x1b[1;31m[MANDATORY]\x1b[0m", out)
        self.assertIn("\x1b[1mregulation\x1b[0m", out)
        self.assertIn("\x1b[36msection\x1b[0m", out)
        self.assertIn("\x1b[3msummary\x1b[0m", out)


class TestCliRendersTextLiterally(unittest.TestCase):
    MARKUP = "[/nonsense]"

    def _main(self, extra: list[str], *, country: str = "US", run=None):
        out, err = io.StringIO(), io.StringIO()
        argv = ["saaf", "--company", "X", "--industry", "Healthcare", "--country", country,
                "--listed-status", "Private", "--audit-topic", "Cybersecurity", "--yes"] + extra
        with patch.object(sys, "argv", argv), \
             patch.object(cli, "Config"), \
             patch.object(cli, "ComplianceAgent") as agent_cls, \
             patch.object(cli, "console", Console(file=out, width=2000)), \
             patch.object(cli, "err_console", Console(file=err, width=2000)):
            agent_cls.return_value.run.side_effect = run
            rc = cli.main()
        return rc, out.getvalue(), err.getvalue()

    def test_country_warning_renders_literally(self):
        rc, _, err = self._main(["--dry-run"], country=self.MARKUP)
        self.assertEqual(rc, 0)
        self.assertIn(self.MARKUP, err)

    def test_agent_error_and_raw_response_render_literally(self):
        def run(_):
            raise ComplianceReportError(f"Bad {self.MARKUP}", raw_response=f"raw {self.MARKUP}")

        rc, _, err = self._main([], run=run)
        self.assertEqual(rc, 1)
        self.assertIn(f"Bad {self.MARKUP}", err)
        self.assertIn(f"raw {self.MARKUP}", err)

    def test_output_file_path_renders_literally(self):
        report = ComplianceReport(**_report_data())
        mapping = FrameworkMapper(_make_input()).map()
        with tempfile.TemporaryDirectory() as tmp:
            for fmt, label in (("json", "Report saved to:"), ("report", "JSON also saved to:")):
                with self.subTest(output=fmt):
                    name = Path(tmp) / f"[x]{fmt}.json"
                    rc, out, _ = self._main(
                        ["--output", fmt, "--output-file", str(name)],
                        run=lambda _: (report, mapping),
                    )
                    self.assertEqual(rc, 0)
                    self.assertIn(label, out)
                    self.assertIn(f"[x]{fmt}.json", out)


if __name__ == "__main__":
    unittest.main()
