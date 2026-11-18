"""The single route for outbound HTTP from the clause-source scripts (issue #49).

Every download in ``tools/clause_sources/`` goes through :func:`open_url`, which
only allows HTTPS to the official hosts in :data:`ALLOWED_HOSTS`. Redirects are
checked the same way, so a source cannot send a script to another host.

This module narrows what the scripts can reach. It has not been approved as an
API connector under SAAF's ``regulatory/guardrails/allowed-commands.md``.
"""

from __future__ import annotations

import urllib.request
from urllib.parse import urlsplit, urlunsplit

ALLOWED_HOSTS = frozenset({
    "publications.europa.eu",
    "www.legislation.gov.uk",
    "downloads.leginfo.legislature.ca.gov",
    "www.ecfr.gov",
    "www.govinfo.gov",
    "csrc.nist.gov",
    "nvlpubs.nist.gov",
    "raw.githubusercontent.com",
})


class EgressRefused(RuntimeError):
    """A URL or redirect target is outside the allowlist. Retrying cannot help."""


def check_url(url: str) -> None:
    """Raise :class:`EgressRefused` unless ``url`` is HTTPS to an allowlisted host."""
    parts = urlsplit(url)
    try:
        port = parts.port
    except ValueError:
        raise EgressRefused(f"refused URL with invalid port: {url}") from None
    if parts.scheme != "https":
        raise EgressRefused(f"refused non-https URL: {url}")
    if "@" in parts.netloc or port not in (None, 443):
        raise EgressRefused(f"refused URL with credentials or a non-standard port: {url}")
    if parts.hostname not in ALLOWED_HOSTS:
        raise EgressRefused(f"refused host outside the allowlist: {url}")


class _AllowlistRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # The EU Publications Office resolver answers every CELEX lookup with a
        # 303 to plain http:// on its own host. The same path serves the same
        # document over https, so upgrade instead of leaving HTTPS.
        parts = urlsplit(newurl)
        if parts.scheme == "http":
            newurl = urlunsplit(parts._replace(scheme="https"))
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_AllowlistRedirectHandler)


def open_url(url: str, *, headers: dict[str, str], timeout: int, method: str = "GET"):
    """Open ``url`` after the allowlist check and return the response object."""
    check_url(url)
    request = urllib.request.Request(url, headers=headers, method=method)
    return _OPENER.open(request, timeout=timeout)
