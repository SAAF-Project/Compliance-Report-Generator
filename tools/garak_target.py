"""
Target for garak's function generator (issue #46).

    python -m garak --target_type function --target_name tools.garak_target#generate ...

Run from the repository root. garak's text goes in as ``company_name`` and passes
through the agent's real prompt and output checks. The provider and model come from
the app's own ``Config()``: this module has no model setting of its own.

Input validation is deliberately skipped here. ``company_name`` allows 200 characters
on one line, and nearly all garak probes are longer or multi-line, so with validation
on almost none reach the model (1 of about 443 in a local run). Skipping it measures
the model and the prompt delimiting behind validation. A hit therefore does not mean
that text could be delivered through the CLI. Validation has its own unit tests.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from config import Config
from saaf.core.agent import ComplianceAgent, ComplianceReportError
from saaf.core.models import AuditInput

MAX_MODEL_CALLS = 30
MAX_MODEL_CALLS_ENV = "SAAF_GARAK_MAX_CALLS"  # for local tests only; the workflow never sets it
OUTCOMES_PATH_ENV = "SAAF_GARAK_OUTCOMES"
DEFAULT_OUTCOMES_PATH = "garak-output/outcomes.json"

REJECTED_BY_SCHEMA_OR_GROUNDING = "rejected_by_schema_or_grounding"
COMPLETE_REPORT = "complete_report"
BUDGET_EXHAUSTED = "budget_exhausted"
# The call itself failed (bad key, outage, ...). Not a finding: the workflow fails on it.
INFRASTRUCTURE_ERROR = "infrastructure_error"
OUTCOMES = (
    REJECTED_BY_SCHEMA_OR_GROUNDING,
    COMPLETE_REPORT,
    BUDGET_EXHAUSTED,
    INFRASTRUCTURE_ERROR,
)

# Only company_name carries probe text; the rest are fixed and synthetic.
_FIXED_FIELDS = {
    "industry": "Technology",
    "country": "Netherlands",
    "listed_status": "Private",
    "audit_topic": "Cybersecurity",
}

# Output checks re-validate audit_input, which would reject the probe text and count
# every long probe as a bad response. They get this valid stand-in instead.
_VALID_INPUT = AuditInput(company_name="Synthetic Entity", **_FIXED_FIELDS)


class _BudgetExhausted(Exception):
    """The model-call budget is used up. Deliberately not an LLMError, so nothing retries it."""


def strip_audit_input(raw: str) -> str:
    """
    Remove the echoed ``audit_input`` from a JSON response.

    The echo repeats the probe text, so detectors would score it as a hit. Text around
    the JSON object is kept, because an injection can show up there.
    """
    json_text = ComplianceAgent._extract_json_object(raw)
    try:
        data = json.loads(json_text)
    except (ValueError, RecursionError):
        return raw
    if not isinstance(data, dict):
        return raw
    data.pop("audit_input", None)
    return raw.replace(json_text, json.dumps(data, ensure_ascii=False), 1)


def _is_json_object(raw: str) -> bool:
    try:
        return isinstance(json.loads(ComplianceAgent._extract_json_object(raw)), dict)
    except (ValueError, RecursionError):
        return False


class GarakTarget:
    """One agent, one call budget and one set of outcome counts for a garak run."""

    def __init__(self) -> None:
        self.budget = int(os.environ.get(MAX_MODEL_CALLS_ENV) or MAX_MODEL_CALLS)
        self.outcomes_path = Path(os.environ.get(OUTCOMES_PATH_ENV) or DEFAULT_OUTCOMES_PATH)
        self.counts = dict.fromkeys(OUTCOMES, 0)
        self.model_calls = 0
        self._last_raw: Optional[str] = None

        # Agent-level retries are off here, SDK-level retries just below. A retry
        # would be a model call that the budget never sees.
        self.agent = ComplianceAgent(Config(max_retries=0))
        client = self.agent.client
        if self.agent.config.provider == "anthropic":
            client.client = client.client.with_options(max_retries=0)

        self._complete = client.complete
        client.complete = self._counted_complete

        parse = self.agent._parse_and_validate
        self.agent._parse_and_validate = lambda raw, _input: parse(raw, _VALID_INPUT)
        self._write_outcomes()

    def _counted_complete(self, system: str, user: str, max_tokens: int):
        """The one place every model call goes through, so the budget cannot be bypassed."""
        if self.model_calls >= self.budget:
            raise _BudgetExhausted
        self.model_calls += 1
        response = self._complete(system, user, max_tokens)
        self._last_raw = response.text
        return response

    def _write_outcomes(self) -> None:
        """Rewritten after every call, so the counts survive a crash later in the run."""
        self.outcomes_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.outcomes_path.with_name(self.outcomes_path.name + ".tmp")
        temp.write_text(
            json.dumps(
                {
                    "provider": self.agent.config.provider,
                    "model": self.agent.config.model,
                    "budget": self.budget,
                    "model_calls": self.model_calls,
                    "outcomes": self.counts,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        os.replace(temp, self.outcomes_path)

    def _finish(self, outcome: str, output: Optional[str]) -> list[Optional[str]]:
        self.counts[outcome] += 1
        self._write_outcomes()
        return [output]

    def call(self, prompt: str) -> list[Optional[str]]:
        # None means "no model output": garak does not score it. A placeholder
        # string would be scored and count as a pass.
        # model_construct skips input validation on purpose: see the module docstring
        audit_input = AuditInput.model_construct(company_name=prompt, **_FIXED_FIELDS)

        self._last_raw = None
        try:
            self.agent.run(audit_input)
        except _BudgetExhausted:
            return self._finish(BUDGET_EXHAUSTED, None)
        except ComplianceReportError as e:
            if self._last_raw is None:  # the call failed, so there is no response to reject
                return self._finish(INFRASTRUCTURE_ERROR, None)
            return self._finish(REJECTED_BY_SCHEMA_OR_GROUNDING, strip_audit_input(e.raw_response))
        except Exception:
            # e.g. a bare JSON array, which the agent does not expect. That is a
            # rejected response; anything else is a fault and must stay visible.
            if self._last_raw is None or _is_json_object(self._last_raw):
                return self._finish(INFRASTRUCTURE_ERROR, None)
            return self._finish(REJECTED_BY_SCHEMA_OR_GROUNDING, strip_audit_input(self._last_raw))
        return self._finish(COMPLETE_REPORT, strip_audit_input(self._last_raw))


_target: Optional[GarakTarget] = None


def reset() -> None:
    """Forget the current run (for tests)."""
    global _target
    _target = None


def generate(prompt: str, **kwargs) -> list[Optional[str]]:
    """Signature required by garak's function generator; keeps state across a run."""
    global _target
    if _target is None:
        _target = GarakTarget()
    return _target.call(prompt)
