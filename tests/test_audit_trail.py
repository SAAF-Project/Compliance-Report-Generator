"""Unit tests for the opt-in audit trail (no API needed)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from saaf.core.audit_trail import (
    RECORD_VERSION, REDACTED, AuditTrail, hash_prompt, sanitize_endpoint, utc_now,
)


def _kwargs(report_id: str = "abc-123") -> dict:
    return dict(
        report_id=report_id,
        inputs={"company_name": "Secret Corp", "country": "US"},
        framework_keys=["sox", "coso"],
        model="test-model",
        system_prompt="sys",
        user_message="user",
        started_at=utc_now(),
        finished_at=utc_now(),
        raw_response='{"x": 1}',
    )


class TestAuditTrail(unittest.TestCase):
    def test_record_redacts_company_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = AuditTrail(Path(d) / "sub").record(**_kwargs())
            data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(path.name, "abc-123.json")
        self.assertEqual(data["inputs"]["company_name"], REDACTED)
        self.assertTrue(data["company_name_redacted"])
        self.assertEqual(data["inputs"]["country"], "US")
        self.assertEqual(data["framework_keys"], ["sox", "coso"])
        self.assertEqual(data["model"], "test-model")
        self.assertEqual(data["raw_response"], '{"x": 1}')
        self.assertEqual(data["prompt_sha256"], hash_prompt("sys", "user"))

    def test_company_kept_when_opted_in(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = AuditTrail(Path(d), redact_company=False).record(**_kwargs())
            data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["inputs"]["company_name"], "Secret Corp")

    def test_prompt_hash_separates_parts(self) -> None:
        self.assertNotEqual(hash_prompt("ab", "c"), hash_prompt("a", "bc"))

    def test_unsafe_report_id_not_written(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(AuditTrail(Path(d)).record(**_kwargs("../evil")))
            self.assertEqual(list(Path(d).iterdir()), [])


class TestProviderMetadata(unittest.TestCase):
    def _record(self, **extra) -> dict:
        with tempfile.TemporaryDirectory() as d:
            path = AuditTrail(Path(d)).record(**_kwargs(), **extra)
            return json.loads(path.read_text(encoding="utf-8"))

    def test_records_provider_endpoint_settings_usage_and_kb_version(self) -> None:
        data = self._record(
            provider="openai",
            endpoint="https://llm.example.com:8443/v1/chat/completions",
            settings={"max_tokens": 100, "max_retries": 2, "timeout_seconds": 30},
            kb_version="0.1.0",
            call={"attempts": 2, "input_tokens": 5, "output_tokens": 7, "stop_reason": "stop"},
        )
        self.assertEqual(data["record_version"], RECORD_VERSION)
        self.assertEqual(data["provider"], "openai")
        self.assertEqual(data["model"], "test-model")
        self.assertEqual(data["endpoint_host"], "llm.example.com:8443")
        self.assertEqual(data["endpoint_url"], "https://llm.example.com:8443/v1/chat/completions")
        self.assertEqual(data["settings"]["max_retries"], 2)
        self.assertEqual(data["kb_version"], "0.1.0")
        self.assertEqual(data["call"]["attempts"], 2)
        self.assertEqual(data["call"]["stop_reason"], "stop")

    def test_old_style_calls_still_work_and_fields_are_empty(self) -> None:
        data = self._record()
        self.assertIsNone(data["provider"])
        self.assertIsNone(data["endpoint_host"])
        self.assertEqual(data["settings"], {})
        self.assertEqual(data["call"], {})

    def test_credentials_and_query_never_reach_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = AuditTrail(Path(d)).record(
                **_kwargs(), endpoint="https://user:hunter2@gw.example.com/v1?api_key=SECRET#frag")
            text = path.read_text(encoding="utf-8")
        for leaked in ("hunter2", "SECRET", "api_key", "frag", "user:"):
            self.assertNotIn(leaked, text)
        self.assertIn("gw.example.com", text)


class TestSanitizeEndpoint(unittest.TestCase):
    def test_strips_userinfo_query_fragment_and_trailing_slash(self) -> None:
        self.assertEqual(
            sanitize_endpoint("https://u:p@h.example.com/v1/?k=v#f"),
            ("https://h.example.com/v1", "h.example.com"))

    def test_keeps_port_and_handles_ipv6_and_loopback(self) -> None:
        self.assertEqual(sanitize_endpoint("http://localhost:11434/v1"),
                         ("http://localhost:11434/v1", "localhost:11434"))
        self.assertEqual(sanitize_endpoint("http://[::1]:8000/v1"),
                         ("http://[::1]:8000/v1", "[::1]:8000"))

    def test_unusable_values_give_none(self) -> None:
        for bad in (None, 123, "", "not a url", "ftp://h.example.com", "https://", object()):
            with self.subTest(bad=bad):
                self.assertEqual(sanitize_endpoint(bad), (None, None))


if __name__ == "__main__":
    unittest.main()
