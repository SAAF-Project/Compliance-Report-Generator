#!/usr/bin/env python3
"""
Turn a garak report and the outcomes from tools/garak_target.py into Markdown.

    python tools/garak_summary.py --report garak.report.jsonl --outcomes outcomes.jsonl

Standard library only. Prints the summary and exits non-zero only when the run itself
is broken (missing files, provider or wrapper errors, budget overrun, no results).
Findings never change the exit code. The output has aggregate counts only, no model
text, because it is posted as a PR comment.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

OUTCOME_LABELS = {
    "input_rejected": "Rejected by input validation (no model call)",
    "rejected_by_checks": "Rejected by schema or grounding checks",
    "complete": "Reached a complete report",
    "budget_exhausted": "Skipped, budget spent (no model call)",
    "provider_error": "Provider error",
    "internal_error": "Wrapper error",
}


def _read_jsonl(path: Path) -> Optional[list[dict]]:
    """Parsed lines, or None if the file is missing or not JSON Lines."""
    try:
        with path.open(encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except (OSError, ValueError):
        return None


def build_summary(report: Optional[list[dict]], outcomes: Optional[list[dict]]) -> tuple[str, list[str]]:
    """Return (markdown, infrastructure problems)."""
    problems: list[str] = []
    lines = ["## garak LLM security check", ""]

    run = next((r for r in outcomes or [] if r.get("type") == "run"), None)
    calls = [r for r in outcomes or [] if r.get("type") == "call"]
    counts = Counter(r.get("outcome") for r in calls)
    used = max((r.get("model_calls", 0) for r in calls), default=0)

    if run is None:
        problems.append("No outcomes were recorded: the target never started.")
    else:
        lines += [
            f"- Provider: `{run.get('provider')}`",
            f"- Model: `{run.get('model')}`",
            f"- Model calls: {used} of {run.get('budget')} allowed",
            "",
            "Hit rates cannot be compared across models.",
            "",
        ]
        if used > run.get("budget", 0):
            problems.append(f"Budget overrun: {used} model calls.")

    for outcome, what in (
        ("provider_error", "the model provider returned an error"),
        ("internal_error", "the wrapper raised an unexpected error"),
    ):
        if counts[outcome]:
            problems.append(f"{counts[outcome]} prompt(s) failed because {what}.")

    if calls:
        lines += ["| Prompt outcome | Count |", "| --- | ---: |"]
        lines += [f"| {label} | {counts[key]} |" for key, label in OUTCOME_LABELS.items()]
        lines.append("")
        if not counts["complete"] + counts["rejected_by_checks"]:
            lines += ["**No prompt got a model response, so this run measured nothing.**", ""]
        if counts["budget_exhausted"]:
            lines += ["**The budget ran out, so later probes have no results.**", ""]

    evals = [r for r in report or [] if r.get("entry_type") == "eval"]
    if report is None:
        problems.append("The garak report is missing or unreadable.")
    elif not evals:
        problems.append("The garak report has no probe results.")
    if evals:
        lines += [
            "| Probe | Detector | Hits | Evaluated | No output | Hit rate |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
        for e in evals:
            hits, total = e.get("fails", 0), e.get("total_evaluated", 0)
            rate = f"{hits / total:.0%}" if total else "n/a"
            lines.append(
                f"| {e.get('probe')} | {e.get('detector')} | {hits} | {total} "
                f"| {e.get('nones', 0)} | {rate} |"
            )
        lines += [
            "",
            "Detectors are heuristics built for chat-style text, and this app returns JSON. "
            "Expect false positives and false negatives. A hit is a prompt to review, "
            "not a confirmed vulnerability.",
            "",
        ]

    if problems:
        lines += ["### The run did not complete properly", ""]
        lines += [f"- {p}" for p in problems]
        lines.append("")
    return "\n".join(lines), problems


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--outcomes", type=Path, required=True)
    args = parser.parse_args(argv)
    markdown, problems = build_summary(_read_jsonl(args.report), _read_jsonl(args.outcomes))
    print(markdown)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
