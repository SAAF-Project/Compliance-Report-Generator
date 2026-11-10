"""
Turn a garak run into a markdown summary of counts (issue #46). Standard library only.

    python tools/garak_summary.py --report PREFIX.report.jsonl \
        --hitlog PREFIX.hitlog.jsonl --outcomes outcomes.json --output summary.md

The summary goes into a PR comment, so it never contains model output or probe text.
Exit status is 0 whatever the hit rates are, and 1 when the run itself did not work:
garak exits 0 even after a crash, so only its "completion" record shows that it finished.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

COMMENT_MARKER = "<!-- garak-pr-check -->"
INFRASTRUCTURE_ERROR = "infrastructure_error"

_SAFE_NAME = re.compile(r"[\w.:/-]+")


def _safe(value: object) -> str:
    """Names come from data files; only ever print them if they look like names."""
    text = str(value)
    return f"`{text}`" if _SAFE_NAME.fullmatch(text) else "(unprintable)"


def _records(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as file:
        for line in file:
            try:
                record = json.loads(line)
            except ValueError:  # a line cut off by a crash; the completion check catches that
                continue
            if isinstance(record, dict):
                records.append(record)
    return records


def _read_report(path: Path) -> tuple[list[dict], list[str]]:
    if not path.is_file():
        return [], [f"garak report not found: {path.name}"]
    records = _records(path)
    if not any(r.get("entry_type") == "completion" for r in records):
        return [], ["garak report has no completion record, so the run did not finish"]
    return [r for r in records if r.get("entry_type") == "eval"], []


def _read_hits(path: Path | None) -> Counter:
    """garak only creates the hit log on the first hit, so no file means no hits."""
    if path is None or not path.is_file():
        return Counter()
    return Counter((r.get("probe"), r.get("detector")) for r in _records(path))


def _read_outcomes(path: Path) -> tuple[dict, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, [f"outcome counts not found or unreadable: {path.name}"]
    if not isinstance(data, dict) or not isinstance(data.get("outcomes"), dict):
        return {}, [f"outcome counts have an unexpected shape: {path.name}"]
    errors = []
    failed = data["outcomes"].get(INFRASTRUCTURE_ERROR, 0)
    if failed:
        errors.append(f"{failed} model call(s) failed for infrastructure reasons")
    return data, errors


def build_summary(evals: list[dict], hits: Counter, outcomes: dict, errors: list[str]) -> str:
    lines = [COMMENT_MARKER, "## garak injection check", ""]
    if errors:
        lines += ["**The check did not complete. Hit rates below are not usable.**", ""]
        lines += [f"- {error}" for error in errors]
        lines.append("")

    if outcomes:
        lines += [
            f"Provider {_safe(outcomes.get('provider'))}, model {_safe(outcomes.get('model'))}. "
            f"Model calls: {int(outcomes.get('model_calls', 0))} of "
            f"{int(outcomes.get('budget', 0))} budgeted. "
            "Hit rates cannot be compared across models.",
            "",
        ]
        if not outcomes.get("model_calls"):
            lines += [
                "**No probe prompt reached the model, so this run says nothing about "
                "how the model responds to injection.**",
                "",
            ]
        lines += [
            "| Outcome per probe prompt | Count |",
            "|---|---|",
        ]
        lines += [
            f"| {_safe(name)} | {int(count)} |" for name, count in outcomes["outcomes"].items()
        ]
        lines.append("")

    if evals:
        lines += [
            "| Probe | Detector | Hits | Scored | Not scored | Hit rate |",
            "|---|---|---|---|---|---|",
        ]
        for e in evals:
            scored = int(e.get("total_evaluated", 0))
            fails = int(e.get("fails", 0))
            rate = f"{fails / scored:.0%}" if scored else "n/a"
            lines.append(
                f"| {_safe(e.get('probe'))} | {_safe(e.get('detector'))} | "
                f"{fails} | {scored} | {int(e.get('nones', 0))} | {rate} |"
            )
        lines.append("")
        total_fails = sum(int(e.get("fails", 0)) for e in evals)
        if sum(hits.values()) != total_fails:
            lines += [
                f"Warning: the hit log has {sum(hits.values())} entries "
                f"but the report counts {total_fails} hits.",
                "",
            ]
    elif not errors:
        lines += ["garak scored no probes in this run.", ""]

    lines += [
        "**Input validation is deliberately skipped in this check**, so it measures the "
        "model and the prompt delimiting behind validation. A hit does not mean that text "
        "could be delivered through the CLI.",
        "",
        "Not scored means no model output, for example stopped by the budget. "
        "garak's detectors expect chat text and this app returns JSON, so expect "
        "false positives and false negatives. Injections that stay within the schema, and "
        "whether a citation is correct, are not visible to this check.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--hitlog", type=Path)
    parser.add_argument("--outcomes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    evals, errors = _read_report(args.report)
    outcomes, outcome_errors = _read_outcomes(args.outcomes)
    errors += outcome_errors
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        build_summary(evals, _read_hits(args.hitlog), outcomes, errors), encoding="utf-8"
    )

    for error in errors:
        print(f"::error::{error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
