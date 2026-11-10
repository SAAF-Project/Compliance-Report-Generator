"""Tests for the clause-source egress allowlist (issue #49). No network is used.

``FakeTransport`` replaces the HTTPS handler on the real opener in ``egress``, so
requests still pass through the real redirect handling but no socket is opened.
"""

from __future__ import annotations

import email.message
import gzip
import io
import re
import sys
import unittest
import urllib.error
import urllib.request
import urllib.response
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "tools" / "clause_sources"
sys.path.insert(0, str(SCRIPTS_DIR))

import common
import egress
import eu_oj
import nist
import uk_ca_law
import us_law

ISSUE_49_HOSTS = {
    "publications.europa.eu",
    "www.legislation.gov.uk",
    "downloads.leginfo.legislature.ca.gov",
    "www.ecfr.gov",
    "www.govinfo.gov",
    "csrc.nist.gov",
    "nvlpubs.nist.gov",
    "raw.githubusercontent.com",
}
GOOD_URL = "https://www.ecfr.gov/api/versioner/v1/titles.json"
BAD_HOST_URL = "https://evil.example/data"
EU_URL = "https://publications.europa.eu/resource/celex/32016R0679"
EU_CELLAR_PATH = "publications.europa.eu/resource/cellar/abc/DOC_1"


def response(body: bytes = b"", code: int = 200, headers: dict | None = None):
    message = email.message.Message()
    for name, value in (headers or {}).items():
        message[name] = value
    resp = urllib.response.addinfourl(io.BytesIO(body), message, GOOD_URL, code)
    resp.msg = "fake"
    return resp


class FakeTransport:
    """Stands in for the HTTPS handler: records requests and replays outcomes."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.requests = []

    def https_open(self, req):
        self.requests.append(req)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class EgressTestCase(unittest.TestCase):
    def use_transport(self, *outcomes) -> FakeTransport:
        transport = FakeTransport(*outcomes)
        patcher = mock.patch.dict(egress._OPENER.handle_open, {"https": [transport]})
        patcher.start()
        self.addCleanup(patcher.stop)
        return transport

    def setUp(self):
        # Anything that bypasses the fake transport must fail rather than touch the network.
        for target in ("urllib.request.urlopen", "socket.create_connection", "time.sleep"):
            patcher = mock.patch(target)
            setattr(self, target.rsplit(".", 1)[1], patcher.start())
            self.addCleanup(patcher.stop)
        self.urlopen.side_effect = AssertionError("direct urlopen call")
        self.create_connection.side_effect = AssertionError("real socket opened")


class TestSingleRoute(unittest.TestCase):
    def test_no_http_client_use_outside_egress_module(self):
        forbidden = re.compile(
            r"\b(?:urlopen|build_opener|urllib\.request|http\.client)\b"
            r"|^\s*(?:import|from)\s+(?:socket|requests|httpx|urllib3|aiohttp)\b",
            re.MULTILINE,
        )
        scanned = 0
        for path in (PROJECT_ROOT / "tools").rglob("*.py"):
            if path == SCRIPTS_DIR / "egress.py":
                continue
            scanned += 1
            match = forbidden.search(path.read_text(encoding="utf-8"))
            self.assertIsNone(match, f"{path}: {match and match.group(0)}")
        self.assertGreaterEqual(scanned, 6)

    def test_allowlist_is_the_issue_host_list(self):
        self.assertEqual(set(egress.ALLOWED_HOSTS), ISSUE_49_HOSTS)

    def test_every_source_url_used_by_the_scripts_is_allowed(self):
        urls = [
            eu_oj.BASE + "32016R0679",
            eu_oj.SPARQL,
            uk_ca_law.LEG + "/eur/2016/679/data.xml",
            "https://downloads.leginfo.legislature.ca.gov/pubinfo_2025.zip",
            us_law.ECFR + "/titles.json",
            us_law.USC_URL,
            nist.CSF_XLSX_URL,
            nist.CSF_PDF_URL,
            nist.OSCAL_URL,
        ]
        for url in urls:
            with self.subTest(url=url):
                egress.check_url(url)


class TestCheckUrl(EgressTestCase):
    def test_refused_urls_never_reach_the_transport(self):
        refused = [
            BAD_HOST_URL,
            "http://www.ecfr.gov/api",
            "ftp://www.ecfr.gov/api",
            "file:///etc/passwd",
            "www.ecfr.gov/api",
            "https://www.ecfr.gov.evil.example/api",
            "https://evil.example/www.ecfr.gov",
            "https://www.ecfr.gov@evil.example/api",
            "https://user@www.ecfr.gov/api",
            "https://www.ecfr.gov:8443/api",
            "https://www.ecfr.gov:notaport/api",
        ]
        transport = self.use_transport()
        for url in refused:
            with self.subTest(url=url), self.assertRaises(egress.EgressRefused):
                egress.open_url(url, headers={}, timeout=1)
        self.assertEqual(transport.requests, [])

    def test_allowed_url_keeps_headers_timeout_and_method(self):
        transport = self.use_transport(response(b"body"))
        with egress.open_url(GOOD_URL, method="HEAD", headers={"X-Test": "1"}, timeout=7) as r:
            self.assertEqual(r.read(), b"body")
        req = transport.requests[0]
        self.assertEqual(req.full_url, GOOD_URL)
        self.assertEqual(req.get_method(), "HEAD")
        self.assertEqual(req.timeout, 7)
        self.assertEqual(req.get_header("X-test"), "1")


class TestRedirects(EgressTestCase):
    def redirect(self, location: str, code: int = 303):
        return response(code=code, headers={"Location": location})

    def test_same_host_http_redirect_is_upgraded_to_https(self):
        # What publications.europa.eu really answers for a CELEX lookup.
        transport = self.use_transport(self.redirect(f"http://{EU_CELLAR_PATH}"), response(b"doc"))
        headers = {"Accept": "application/xhtml+xml", "Accept-Language": "eng"}
        with egress.open_url(EU_URL, headers=headers, timeout=5) as r:
            self.assertEqual(r.read(), b"doc")
        followed = transport.requests[1]
        self.assertEqual(followed.full_url, f"https://{EU_CELLAR_PATH}")
        self.assertEqual(followed.get_header("Accept"), "application/xhtml+xml")
        self.assertEqual(followed.get_header("Accept-language"), "eng")

    def test_redirect_within_allowlist_is_followed(self):
        transport = self.use_transport(self.redirect("https://www.govinfo.gov/x", 302), response())
        egress.open_url(GOOD_URL, headers={"X-Test": "1"}, timeout=5).close()
        self.assertEqual(transport.requests[1].full_url, "https://www.govinfo.gov/x")
        self.assertEqual(transport.requests[1].get_header("X-test"), "1")

    def test_redirect_outside_allowlist_is_refused(self):
        for location in (BAD_HOST_URL, "http://evil.example/x", "//evil.example/x",
                         "ftp://www.ecfr.gov/x"):
            with self.subTest(location=location):
                transport = self.use_transport(self.redirect(location))
                with self.assertRaises(egress.EgressRefused):
                    egress.open_url(GOOD_URL, headers={}, timeout=5)
                self.assertEqual(len(transport.requests), 1)


class TestCommonFetch(EgressTestCase):
    def test_sends_headers_and_timeout(self):
        transport = self.use_transport(response(b"body"))
        self.assertEqual(common.fetch(EU_URL, accept="text/csv", lang="eng", timeout=33), b"body")
        req = transport.requests[0]
        self.assertEqual(req.get_header("User-agent"), common.USER_AGENT)
        self.assertEqual(req.get_header("Accept"), "text/csv")
        self.assertEqual(req.get_header("Accept-language"), "eng")
        self.assertEqual(req.timeout, 33)

    def test_transient_errors_are_still_retried(self):
        error = urllib.error.URLError("down")
        transport = self.use_transport(error, error, response(b"ok"))
        self.assertEqual(common.fetch(EU_URL), b"ok")
        self.assertEqual(len(transport.requests), 3)
        self.assertEqual([c.args[0] for c in self.sleep.call_args_list], [2, 4])

    def test_gives_up_after_retries(self):
        error = urllib.error.URLError("down")
        self.use_transport(error, error, error)
        with self.assertRaisesRegex(RuntimeError, "failed to fetch"):
            common.fetch(EU_URL)

    def test_refusal_is_immediate_and_not_retried(self):
        self.use_transport()
        with self.assertRaises(egress.EgressRefused):
            common.fetch(BAD_HOST_URL)
        self.sleep.assert_not_called()
        self.urlopen.assert_not_called()


class TestUkRangeFile(EgressTestCase):
    ZIP_URL = "https://downloads.leginfo.legislature.ca.gov/pubinfo_2025.zip"
    HEAD_HEADERS = {"Content-Length": "10", "ETag": "tag", "Last-Modified": "then",
                    "Accept-Ranges": "bytes"}

    def test_head_then_range_get(self):
        transport = self.use_transport(response(headers=self.HEAD_HEADERS), response(b"abcd", 206))
        rf = uk_ca_law.RangeFile(self.ZIP_URL)
        self.assertEqual((rf.size, rf.etag, rf.last_modified), (10, "tag", "then"))
        buffer = bytearray(4)
        self.assertEqual(rf.readinto(buffer), 4)
        self.assertEqual(bytes(buffer), b"abcd")
        head, get = transport.requests
        self.assertEqual((head.get_method(), head.timeout), ("HEAD", 60))
        self.assertEqual(head.get_header("User-agent"), uk_ca_law.USER_AGENT)
        self.assertEqual((get.get_method(), get.timeout), ("GET", 120))
        self.assertEqual(get.get_header("Range"), "bytes=0-3")
        self.assertEqual(get.get_header("User-agent"), uk_ca_law.USER_AGENT)

    def test_refuses_host_outside_allowlist(self):
        self.use_transport()
        with self.assertRaises(egress.EgressRefused):
            uk_ca_law.RangeFile(BAD_HOST_URL)
        self.urlopen.assert_not_called()


class TestUsEcfrGet(EgressTestCase):
    def test_sends_headers_and_decompresses_gzip(self):
        transport = self.use_transport(
            response(gzip.compress(b"plain"), headers={"Content-Encoding": "gzip"}))
        self.assertEqual(us_law.ecfr_get(GOOD_URL, None), b"plain")
        req = transport.requests[0]
        self.assertEqual(req.get_header("User-agent"), us_law.USER_AGENT)
        self.assertEqual(req.get_header("Accept-encoding"), "gzip")
        self.assertEqual(req.timeout, 180)

    def test_transient_errors_are_still_retried(self):
        transport = self.use_transport(urllib.error.URLError("down"), response(b"ok"))
        self.assertEqual(us_law.ecfr_get(GOOD_URL, None), b"ok")
        self.assertEqual(len(transport.requests), 2)

    def test_refusal_is_immediate_and_not_retried(self):
        self.use_transport()
        with self.assertRaises(egress.EgressRefused):
            us_law.ecfr_get(BAD_HOST_URL, None)
        self.sleep.assert_not_called()
        self.urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
