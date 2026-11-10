"""
garak function-generator target for the real compliance agent.

    garak --target_type function --target_name tools.garak_target#generate ...

Each garak prompt is sent as ``company_name`` through ``ComplianceAgent.run``, using
the app's own ``Config()`` and ``create_client()``, so the check always measures the
provider and model the agent uses. Run with the repository root on PYTHONPATH.

Settings (environment variables):

  SAAF_GARAK_MAX_CALLS   hard limit on real model attempts (default 30)
  SAAF_GARAK_OUTCOMES    JSON Lines file with one record per prompt
                         (default garak-outcomes.jsonl; truncated at the start of a run)

Do not set garak's parallel_attempts or parallel_requests: worker processes would
each get their own counter, so this module refuses to run in one.
"""

from __future__ import annotations

import json
import multiprocessing
import os
import threading
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from config import Config
from saaf.core.agent import ComplianceAgent, ComplianceReportError
from saaf.core.llm import AnthropicClient, LLMError, LLMResponse, OpenAICompatibleClient
from saaf.core.models import AuditInput

DEFAULT_MAX_CALLS = 30
DEFAULT_OUTCOMES_PATH = "garak-outcomes.jsonl"
ECHO_PLACEHOLDER = "[probe text removed]"

# Everything except company_name is fixed and synthetic.
SYNTHETIC_FIELDS = {
    "industry": "Technology",
    "country": "Netherlands",
    "listed_status": "Private",
    "audit_topic": "Cybersecurity",
}

INPUT_REJECTED = "input_rejected"
REJECTED_BY_CHECKS = "rejected_by_checks"
COMPLETE = "complete"
BUDGET_EXHAUSTED = "budget_exhausted"
PROVIDER_ERROR = "provider_error"
INTERNAL_ERROR = "internal_error"


class BudgetExhausted(Exception):
    """The model-call budget is spent. Not an LLMError, so the agent never retries it."""


class BudgetedClient:
    """Wraps an LLM client and counts every real attempt, including failed ones."""

    def __init__(self, inner, budget: int) -> None:
        self.inner = inner
        self.budget = budget
        self.calls = 0
        self.last_text: Optional[str] = None
        self.last_error: Optional[LLMError] = None
        self._lock = threading.Lock()

    @property
    def endpoint(self) -> Optional[str]:
        return getattr(self.inner, "endpoint", None)

    def reset_last(self) -> None:
        self.last_text = None
        self.last_error = None

    def complete(self, system: str, user: str, max_tokens: int) -> LLMResponse:
        with self._lock:
            if self.calls >= self.budget:
                raise BudgetExhausted
            self.calls += 1
        try:
            response = self.inner.complete(system, user, max_tokens)
        except LLMError as e:
            self.last_error = e
            raise
        self.last_text = response.text
        return response


def max_calls_from_env() -> int:
    """Read the budget. Anything but a positive integer stops the run."""
    raw = os.environ.get("SAAF_GARAK_MAX_CALLS", "")
    if not raw.strip():
        return DEFAULT_MAX_CALLS
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value < 1:
        raise ValueError(f"SAAF_GARAK_MAX_CALLS must be a positive integer, got {raw!r}")
    return value


def build_agent() -> ComplianceAgent:
    """The app's agent with every retry layer off, so one attempt is one model call."""
    agent = ComplianceAgent(Config(max_retries=0, sdk_max_retries=0))
    if not isinstance(agent.client, (AnthropicClient, OpenAICompatibleClient)):
        raise RuntimeError(
            f"Cannot confirm retries are off for {type(agent.client).__name__}; "
            "update tools/garak_target.py before budgeting this provider."
        )
    return agent


def strip_echoed_input(raw: str, probe: str) -> str:
    """Remove the echoed probe so that detectors only judge what the model added."""
    text = raw
    body = ComplianceAgent._extract_json_object(raw)
    try:
        data = json.loads(body)
    except ValueError:
        data = None
    start = raw.find(body)
    if isinstance(data, dict) and "audit_input" in data and start >= 0:
        del data["audit_input"]
        # Keep any prose around the JSON: a hijacked model may write its answer there
        text = raw[:start] + json.dumps(data, ensure_ascii=False) + raw[start + len(body):]
    if probe:
        for needle in (probe, json.dumps(probe, ensure_ascii=False)[1:-1]):
            text = text.replace(needle, ECHO_PLACEHOLDER)
    return text


class GarakTarget:
    """Runs prompts through the agent, records outcomes and enforces the budget."""

    def __init__(self, agent, budget: int, outcomes_path) -> None:
        self.agent = agent
        self.client = BudgetedClient(agent.client, budget)
        agent.client = self.client
        self.outcomes_path = Path(outcomes_path)
        self.seq = 0
        self.outcomes_path.parent.mkdir(parents=True, exist_ok=True)
        self.outcomes_path.write_text("", encoding="utf-8")
        self._write({
            "type": "run",
            "provider": agent.config.provider,
            "model": agent.config.model,
            "budget": budget,
        })

    def _write(self, record: dict) -> None:
        # Appended per prompt so that a crashed or timed-out run keeps what it did
        with self.outcomes_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def _record(self, outcome: str) -> None:
        self.seq += 1
        self._write({
            "type": "call",
            "seq": self.seq,
            "outcome": outcome,
            "model_calls": self.client.calls,
        })

    def generate(self, prompt: str) -> list[Optional[str]]:
        if multiprocessing.parent_process() is not None:
            raise RuntimeError(
                "tools.garak_target must not run in a worker process: the call budget "
                "is per process. Unset garak's parallel_attempts and parallel_requests."
            )

        # Only this construction counts as input validation: a ValidationError from
        # inside the agent would be a bug, not a rejected probe.
        try:
            audit_input = AuditInput(company_name=prompt, **SYNTHETIC_FIELDS)
        except ValidationError:
            self._record(INPUT_REJECTED)
            return [None]

        self.client.reset_last()
        try:
            self.agent.run(audit_input)
        except BudgetExhausted:
            self._record(BUDGET_EXHAUSTED)
            return [None]
        except ComplianceReportError:
            # The agent wraps API failures in the same type as a rejected response
            if self.client.last_error is not None:
                self._record(PROVIDER_ERROR)
                raise
            self._record(REJECTED_BY_CHECKS)
        except Exception:
            self._record(INTERNAL_ERROR)
            raise
        else:
            self._record(COMPLETE)
        return [strip_echoed_input(self.client.last_text or "", prompt)]


_target: Optional[GarakTarget] = None
_target_lock = threading.Lock()


def _get_target() -> GarakTarget:
    global _target
    with _target_lock:
        if _target is None:
            _target = GarakTarget(
                build_agent(),
                max_calls_from_env(),
                os.environ.get("SAAF_GARAK_OUTCOMES") or DEFAULT_OUTCOMES_PATH,
            )
        return _target


def generate(prompt: str, **_garak_kwargs) -> list[Optional[str]]:
    """Entry point for garak's function generator."""
    return _get_target().generate(prompt)
