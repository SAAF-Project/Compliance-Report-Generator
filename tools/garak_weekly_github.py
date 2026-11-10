#!/usr/bin/env python3
"""
GitHub side of the weekly garak scan, through the gh CLI.

    python -m tools.garak_weekly_github fetch-baseline --dest baseline
    python -m tools.garak_weekly_github track --comparison comparison.json

fetch-baseline finds the newest baseline artifact from an earlier run of the weekly
workflow on main. It is fine for none to exist, but a failed API call is an error:
treating it as "no baseline" would replace a good baseline with this run's results.

track keeps exactly one tracking issue, found by a hidden marker in an issue written by
github-actions[bot]. Search is not used, because its index lags and could cause a
duplicate. The marker alone is not enough either: anyone can paste it into an issue.
If the issue was closed and a regression is found again, it is reopened. A run without a
regression only updates an issue that is open; a person decides when to close it.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from tools.garak_regression import NO_REGRESSION, REGRESSION, comparison_markdown

WORKFLOW_FILE = "garak-weekly-scan.yml"
BASELINE_ARTIFACT = "garak-weekly-baseline"
DEFAULT_BRANCH = "main"
ALLOWED_EVENTS = ("schedule", "workflow_dispatch")

MARKER = "<!-- saaf-garak-weekly-regression-tracker -->"
ISSUE_TITLE = "garak weekly scan: hit-rate regression"
ISSUE_AUTHOR = "github-actions[bot]"

CREATE, UPDATE, REOPEN, NOTHING = "create", "update", "reopen", "nothing"


@dataclass(frozen=True)
class Plan:
    action: str
    number: Optional[int] = None


def select_baseline_run(runs: list[dict], artifacts_of: Callable[[int], list[dict]]) -> Optional[int]:
    """The newest eligible run that still holds a baseline artifact."""
    eligible = [r for r in runs
                if r.get("head_branch") == DEFAULT_BRANCH and r.get("event") in ALLOWED_EVENTS]
    for run in sorted(eligible, key=lambda r: r["run_number"], reverse=True):
        if any(a.get("name") == BASELINE_ARTIFACT and not a.get("expired")
               for a in artifacts_of(run["id"])):
            return run["id"]
    return None


def tracking_issues(issues: list[dict]) -> list[dict]:
    """The tracking issues in ascending number order. Normally zero or one."""
    return sorted(
        (i for i in issues
         if "pull_request" not in i
         and (i.get("user") or {}).get("login") == ISSUE_AUTHOR
         and MARKER in (i.get("body") or "")),
        key=lambda i: i["number"],
    )


def plan_tracking(status: str, tracked: list[dict]) -> Plan:
    """What to do with the tracking issue. Pure: tested without network."""
    open_issues = [i for i in tracked if i.get("state") == "open"]
    if status == REGRESSION:
        if open_issues:
            return Plan(UPDATE, open_issues[0]["number"])
        if tracked:
            return Plan(REOPEN, tracked[-1]["number"])
        return Plan(CREATE)
    if status == NO_REGRESSION and open_issues:
        return Plan(UPDATE, open_issues[0]["number"])
    return Plan(NOTHING)


def issue_body(comparison: dict, run_url: str) -> str:
    note = ""
    if comparison["status"] == NO_REGRESSION:
        note = "The latest run shows no regression. Close this issue if that settles it.\n\n"
    return (
        f"{MARKER}\n"
        "Maintained by the weekly garak scan. Each run replaces this text.\n\n"
        f"{note}Latest run: {run_url}\n\n"
        f"{comparison_markdown(comparison)}\n"
        "A hit is a prompt to review, not a confirmed vulnerability. "
        'See "Weekly LLM security scan" in the README for the definition of a regression '
        "and how to accept a new baseline.\n"
    )


def gh(*args: str, stdin: Optional[str] = None) -> str:
    """Run gh and return its stdout. A failure raises CalledProcessError."""
    done = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True, check=True)
    return done.stdout


def fetch_baseline(repo: str, dest: Path, run_gh: Callable[..., str] = gh) -> Optional[int]:
    # 30 completed runs is well past the 90-day artifact retention at one run a week.
    runs = json.loads(run_gh(
        "api", f"repos/{repo}/actions/workflows/{WORKFLOW_FILE}/runs"
               f"?branch={DEFAULT_BRANCH}&status=completed&per_page=30"))["workflow_runs"]

    def artifacts_of(run_id: int) -> list[dict]:
        return json.loads(run_gh(
            "api", f"repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100"))["artifacts"]

    run_id = select_baseline_run(runs, artifacts_of)
    if run_id is not None:
        run_gh("run", "download", str(run_id), "-R", repo, "-n", BASELINE_ARTIFACT, "-D", str(dest))
    return run_id


def list_issues(repo: str, run_gh: Callable[..., str] = gh) -> list[dict]:
    # tojson: gh prints strings as they are, so each line is one compact object
    jq = ".[] | {number, state, body, pull_request, user: {login: .user.login}} | tojson"
    out = run_gh("api", "--paginate", f"repos/{repo}/issues?state=all&per_page=100", "--jq", jq)
    issues = [json.loads(line) for line in out.splitlines() if line.strip()]
    for issue in issues:
        if issue.get("pull_request") is None:
            issue.pop("pull_request", None)
    return issues


def apply_tracking(comparison: dict, repo: str, run_url: str,
                   run_gh: Callable[..., str] = gh) -> Plan:
    tracked = tracking_issues(list_issues(repo, run_gh))
    if len(tracked) > 1:
        print(f"::warning::{len(tracked)} tracking issues carry the marker; using one of them.")
    plan = plan_tracking(comparison["status"], tracked)
    body = issue_body(comparison, run_url)
    if plan.action == CREATE:
        run_gh("api", "-X", "POST", f"repos/{repo}/issues", "--input", "-",
               stdin=json.dumps({"title": ISSUE_TITLE, "body": body}))
    elif plan.action in (UPDATE, REOPEN):
        fields = {"body": body}
        if plan.action == REOPEN:
            fields["state"] = "open"
        run_gh("api", "-X", "PATCH", f"repos/{repo}/issues/{plan.number}", "--input", "-",
               stdin=json.dumps(fields))
    return plan


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("fetch-baseline")
    fetch.add_argument("--dest", type=Path, required=True)
    track = commands.add_parser("track")
    track.add_argument("--comparison", type=Path, required=True)
    args = parser.parse_args(argv)

    repo = os.environ["GITHUB_REPOSITORY"]
    try:
        if args.command == "fetch-baseline":
            run_id = fetch_baseline(repo, args.dest)
            print(f"Baseline from run {run_id}." if run_id else "No stored baseline found.")
        else:
            comparison = json.loads(args.comparison.read_text(encoding="utf-8"))
            server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
            run_url = f"{server}/{repo}/actions/runs/{os.environ.get('GITHUB_RUN_ID', 'local')}"
            plan = apply_tracking(comparison, repo, run_url)
            print(f"Tracking issue: {plan.action} {plan.number or ''}".rstrip())
    except subprocess.CalledProcessError as e:
        print(f"::error::gh failed with exit code {e.returncode}: {e.stderr}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
