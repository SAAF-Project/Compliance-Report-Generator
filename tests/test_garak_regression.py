"""
SAAF — weekly garak scan: regression logic and GitHub decisions. No network, no garak.

Run with:
    python -m unittest tests.test_garak_regression -v
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools import garak_regression as reg
from tools import garak_weekly_github as gh_tools

PAIR = "promptinject.HijackHateHumans / promptinject.AttackRogueString"


def _snapshot(hits=2, evaluated=20, provider="anthropic", model="stub-model", pairs=None,
              responses=20):
    return {
        "schema": reg.SCHEMA_VERSION,
        "provider": provider,
        "model": model,
        "garak_version": "0.17.1",
        "probe_spec": "probes.promptinject",
        "prompt_cap": "8",
        "seed": "20260105",
        "model_responses": responses,
        "pairs": pairs if pairs is not None else {PAIR: {"hits": hits, "evaluated": evaluated}},
    }


class TestRegressionDefinition(unittest.TestCase):

    def _result(self, base_hits, now_hits, n=20):
        return reg.compare_pair({"hits": base_hits, "evaluated": n},
                                {"hits": now_hits, "evaluated": n})["result"]

    def test_clear_rise_is_a_regression(self):
        self.assertEqual(self._result(0, 10), "regression")

    def test_rise_within_the_margin_is_not_a_regression(self):
        self.assertEqual(self._result(2, 5), "ok")

    def test_a_fall_is_not_a_regression(self):
        self.assertEqual(self._result(15, 3), "ok")

    def test_boundary_of_the_noise_margin_from_zero(self):
        # 0/20 -> 5/20: rise 25%, margin 26%. 0/20 -> 6/20: rise 30%, margin 28%.
        self.assertEqual(self._result(0, 5), "ok")
        self.assertEqual(self._result(0, 6), "regression")

    def test_margin_never_drops_below_the_floor(self):
        self.assertEqual(reg.margin_for(0, 2000, 0, 2000), reg.MIN_RATE_MARGIN)

    def test_margin_widens_with_fewer_responses(self):
        self.assertGreater(reg.margin_for(5, 10, 5, 10), reg.margin_for(50, 100, 50, 100))

    def test_a_rise_at_the_floor_on_large_samples_is_not_over_the_margin(self):
        # Exactly 10 points: the rule is "more than the margin", and float error must not decide
        self.assertEqual(self._result(200, 400, n=2000), "ok")

    def test_too_few_responses_on_either_side_is_not_compared(self):
        small = {"hits": 1, "evaluated": reg.MIN_EVALUATED - 1}
        big = {"hits": 0, "evaluated": reg.MIN_EVALUATED}
        for base, now in ((small, big), (big, small)):
            with self.subTest(base=base):
                row = reg.compare_pair(base, now)
                self.assertEqual(row["result"], "not_compared")
                self.assertIn("fewer than", row["reason"])

    def test_exactly_the_minimum_is_compared(self):
        n = reg.MIN_EVALUATED
        row = reg.compare_pair({"hits": 0, "evaluated": n}, {"hits": n, "evaluated": n})
        self.assertEqual(row["result"], "regression")

    def test_pair_in_only_one_run_is_not_compared(self):
        entry = {"hits": 1, "evaluated": 20}
        self.assertEqual(reg.compare_pair(None, entry)["reason"], "not in the baseline")
        self.assertEqual(reg.compare_pair(entry, None)["reason"], "not in this run")


class TestCompare(unittest.TestCase):

    def test_first_run_reports_no_baseline_and_compares_nothing(self):
        result = reg.compare(_snapshot(), None)
        self.assertEqual(result["status"], reg.NO_BASELINE)
        self.assertNotIn("pairs", result)

    def test_regression_and_no_regression(self):
        self.assertEqual(reg.compare(_snapshot(hits=12), _snapshot(hits=0))["status"], reg.REGRESSION)
        self.assertEqual(reg.compare(_snapshot(hits=1), _snapshot(hits=0))["status"], reg.NO_REGRESSION)

    def test_different_provider_or_model_is_a_mismatch_not_a_regression(self):
        for field, current in (("model", _snapshot(hits=20, model="other-model")),
                               ("provider", _snapshot(hits=20, provider="openai"))):
            with self.subTest(field):
                result = reg.compare(current, _snapshot(hits=0))
                self.assertEqual(result["status"], reg.MISMATCH)
                self.assertIn(field, result["mismatches"])
                self.assertNotIn("pairs", result)

    def test_different_settings_are_a_mismatch(self):
        for field in ("garak_version", "probe_spec", "prompt_cap", "seed"):
            with self.subTest(field):
                result = reg.compare({**_snapshot(hits=20), field: "changed"}, _snapshot(hits=0))
                self.assertEqual(result["status"], reg.MISMATCH)

    def test_run_with_no_model_response_is_never_a_result(self):
        for name, current in (
            ("no responses", _snapshot(responses=0)),
            ("nothing evaluated", _snapshot(hits=0, evaluated=0)),
            ("no pairs", _snapshot(pairs={})),
        ):
            with self.subTest(name):
                self.assertEqual(reg.compare(current, _snapshot())["status"], reg.NOTHING_MEASURED)
                self.assertEqual(reg.compare(current, None)["status"], reg.NOTHING_MEASURED)

    def test_reset_skips_the_comparison(self):
        result = reg.compare(_snapshot(hits=20), _snapshot(hits=0), reset=True)
        self.assertEqual(result["status"], reg.BASELINE_RESET)

    def test_reset_does_not_store_a_run_that_measured_nothing(self):
        result = reg.compare(_snapshot(responses=0), _snapshot(), reset=True)
        self.assertEqual(result["status"], reg.NOTHING_MEASURED)

    def test_only_a_new_or_reset_baseline_changes_what_is_stored(self):
        now, old = _snapshot(hits=1), _snapshot(hits=2)
        for status, expected in (
            (reg.NO_BASELINE, now),
            (reg.BASELINE_RESET, now),
            (reg.REGRESSION, old),
            (reg.NO_REGRESSION, old),
            (reg.MISMATCH, old),
            (reg.NOTHING_MEASURED, old),
        ):
            with self.subTest(status):
                self.assertIs(reg.next_baseline(status, now, old), expected)
        self.assertIsNone(reg.next_baseline(reg.NOTHING_MEASURED, now, None))


class TestSnapshot(unittest.TestCase):

    def test_reads_counts_identity_and_settings(self):
        report = [
            {"entry_type": "start_run setup", "_config.version": "0.17.1",
             "run.spec": {"include": ["probes.promptinject"], "exclude": []},
             "run.soft_probe_prompt_cap": 8, "run.seed": 42},
            {"entry_type": "eval", "probe": "p.A", "detector": "d.X",
             "fails": 3, "total_evaluated": 18, "nones": 2},
            {"entry_type": "attempt", "outputs": ["model text"]},
        ]
        outcomes = [
            {"type": "run", "provider": "anthropic", "model": "stub-model", "budget": 300},
            {"type": "call", "seq": 1, "outcome": "complete", "model_calls": 1},
            {"type": "call", "seq": 2, "outcome": "rejected_by_checks", "model_calls": 2},
            {"type": "call", "seq": 3, "outcome": "input_rejected", "model_calls": 2},
        ]
        snap = reg.build_snapshot(report, outcomes)
        self.assertEqual(snap["pairs"], {"p.A / d.X": {"hits": 3, "evaluated": 18}})
        self.assertEqual((snap["provider"], snap["model"]), ("anthropic", "stub-model"))
        self.assertEqual(snap["garak_version"], '"0.17.1"')
        self.assertEqual(snap["probe_spec"], '{"exclude": [], "include": ["probes.promptinject"]}')
        self.assertEqual((snap["prompt_cap"], snap["seed"]), ("8", "42"))
        self.assertEqual(snap["model_responses"], 2)
        self.assertNotIn("model text", json.dumps(snap))


class TestCli(unittest.TestCase):

    EVAL = {"entry_type": "eval", "probe": "p.A", "detector": "d.X",
            "fails": 12, "total_evaluated": 20, "nones": 0}
    RUN = {"type": "run", "provider": "anthropic", "model": "stub-model", "budget": 300}
    CALL = {"type": "call", "seq": 1, "outcome": "complete", "model_calls": 1}

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.out = self.dir / "out"
        self.report = self.dir / "r.jsonl"
        self.outcomes = self.dir / "o.jsonl"
        self.baseline = self.dir / "baseline.json"
        self._write(self.report, [self.EVAL])
        self._write(self.outcomes, [self.RUN, self.CALL])

    def _write(self, path, records):
        path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")

    def _run(self, *extra):
        args = ["--report", str(self.report), "--outcomes", str(self.outcomes),
                "--baseline", str(self.baseline), "--output-dir", str(self.out), *extra]
        with patch("builtins.print"):
            return reg.main(args)

    def _json(self, name):
        return json.loads((self.out / name).read_text(encoding="utf-8"))

    def _store_baseline(self, hits, model="stub-model", run_id="111"):
        pairs = {"p.A / d.X": {"hits": hits, "evaluated": 20}}
        self.baseline.write_text(json.dumps({
            **_snapshot(pairs=pairs, model=model), "garak_version": None, "probe_spec": None,
            "prompt_cap": None, "seed": None,
            "run_id": run_id, "created_at": "2026-01-05 06:17 UTC",
        }), encoding="utf-8")

    def test_first_run_stores_a_baseline_and_says_so(self):
        self.assertEqual(self._run(), 0)
        self.assertEqual(self._json("comparison.json")["status"], reg.NO_BASELINE)
        self.assertEqual(self._json("baseline.json")["pairs"]["p.A / d.X"]["hits"], 12)
        self.assertIn("regression comparison was skipped",
                      (self.out / "summary.md").read_text(encoding="utf-8"))

    def test_regression_exits_zero_and_keeps_the_old_baseline(self):
        self._store_baseline(0)
        self.assertEqual(self._run(), 0)
        self.assertEqual(self._json("comparison.json")["status"], reg.REGRESSION)
        self.assertEqual(self._json("baseline.json")["pairs"]["p.A / d.X"]["hits"], 0)
        self.assertEqual(self._json("baseline.json")["run_id"], "111")

    def test_mismatch_exits_zero_and_keeps_the_old_baseline(self):
        self._store_baseline(0, model="older-model")
        self.assertEqual(self._run(), 0)
        comparison = self._json("comparison.json")
        self.assertEqual(comparison["status"], reg.MISMATCH)
        self.assertEqual(self._json("baseline.json")["model"], "older-model")
        summary = (self.out / "summary.md").read_text(encoding="utf-8")
        self.assertIn("older-model", summary)
        self.assertNotIn("**Regression", summary)

    def test_reset_replaces_the_baseline(self):
        self._store_baseline(0)
        self.assertEqual(self._run("--reset-baseline"), 0)
        self.assertEqual(self._json("baseline.json")["pairs"]["p.A / d.X"]["hits"], 12)

    def test_measured_nothing_stores_nothing_and_exits_zero(self):
        self._write(self.report, [{**self.EVAL, "fails": 0, "total_evaluated": 0, "nones": 20}])
        self._write(self.outcomes, [self.RUN, {**self.CALL, "outcome": "input_rejected"}])
        self.assertEqual(self._run(), 0)
        self.assertEqual(self._json("comparison.json")["status"], reg.NOTHING_MEASURED)
        self.assertFalse((self.out / "baseline.json").exists())

    def test_measured_nothing_keeps_the_existing_baseline(self):
        self._store_baseline(3)
        self._write(self.outcomes, [self.RUN, {**self.CALL, "outcome": "input_rejected"}])
        self.assertEqual(self._run(), 0)
        self.assertEqual(self._json("baseline.json")["pairs"]["p.A / d.X"]["hits"], 3)

    def test_infrastructure_failure_exits_non_zero_and_stores_nothing(self):
        self._write(self.outcomes, [self.RUN, {**self.CALL, "outcome": "provider_error"}])
        self.assertEqual(self._run(), 1)
        self.assertFalse((self.out / "baseline.json").exists())
        self.assertFalse((self.out / "comparison.json").exists())

    def test_damaged_baseline_fails_instead_of_counting_as_a_first_run(self):
        for name, text in (
            ("not json", "{"),
            ("wrong schema", json.dumps({"schema": 99, "provider": "x", "model": "y",
                                         "pairs": {"a": {}}})),
            ("no model", json.dumps({**_snapshot(), "model": ""})),
            ("no results", json.dumps({**_snapshot(pairs={})})),
        ):
            with self.subTest(name):
                self.baseline.write_text(text, encoding="utf-8")
                self.assertEqual(self._run(), 1)
                self.assertFalse((self.out / "baseline.json").exists())
                self.assertFalse((self.out / "comparison.json").exists())

    def test_output_has_no_model_text(self):
        self._write(self.report, [self.EVAL, {"entry_type": "attempt", "outputs": ["SECRET-MODEL-TEXT"]}])
        self._run()
        for path in self.out.iterdir():
            self.assertNotIn("SECRET-MODEL-TEXT", path.read_text(encoding="utf-8"))

    def test_garak_is_not_imported(self):
        done = subprocess.run(
            [sys.executable, "-c",
             "import sys, tools.garak_regression, tools.garak_weekly_github;"
             "sys.exit('garak' in sys.modules)"],
            cwd=PROJECT_ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)


def _issue(number, state="open", author=gh_tools.ISSUE_AUTHOR, body=gh_tools.MARKER, **extra):
    return {"number": number, "state": state, "user": {"login": author}, "body": body, **extra}


class TestTrackingIssueSelection(unittest.TestCase):

    def test_finds_a_bot_issue_with_the_marker(self):
        self.assertEqual([i["number"] for i in gh_tools.tracking_issues([_issue(5)])], [5])

    def test_ignores_a_person_pasting_the_marker(self):
        self.assertEqual(gh_tools.tracking_issues([_issue(5, author="someone")]), [])

    def test_ignores_bot_issues_without_the_marker(self):
        self.assertEqual(gh_tools.tracking_issues([_issue(5, body="other")]), [])
        self.assertEqual(gh_tools.tracking_issues([_issue(5, body=None)]), [])

    def test_ignores_pull_requests(self):
        pr = _issue(5, pull_request={"url": "x"})
        self.assertEqual(gh_tools.tracking_issues([pr]), [])

    def test_sorted_by_number(self):
        found = gh_tools.tracking_issues([_issue(9), _issue(3)])
        self.assertEqual([i["number"] for i in found], [3, 9])


class TestTrackingPlan(unittest.TestCase):

    def test_regression_with_no_issue_creates_one(self):
        self.assertEqual(gh_tools.plan_tracking(reg.REGRESSION, []), gh_tools.Plan(gh_tools.CREATE))

    def test_regression_with_an_open_issue_updates_it(self):
        self.assertEqual(gh_tools.plan_tracking(reg.REGRESSION, [_issue(7)]),
                         gh_tools.Plan(gh_tools.UPDATE, 7))

    def test_repeated_regressions_never_create_a_second_issue(self):
        # Replays what a second run sees after the first one created the issue
        calls = []

        def fake_gh(*args, stdin=None):
            calls.append((args, stdin))
            if "--paginate" in args:
                created = [c for c in calls if "POST" in c[0]]
                issues = [_issue(i + 1, body=json.loads(c[1])["body"]) for i, c in enumerate(created)]
                return "\n".join(json.dumps(i) for i in issues)
            return ""

        comparison = {"status": reg.REGRESSION}
        for _ in range(3):
            gh_tools.apply_tracking(comparison, "o/r", "https://example.test/run", fake_gh)
        self.assertEqual(len([c for c in calls if "POST" in c[0]]), 1)
        self.assertEqual(len([c for c in calls if "PATCH" in c[0]]), 2)

    def test_regression_with_only_a_closed_issue_reopens_it(self):
        self.assertEqual(gh_tools.plan_tracking(reg.REGRESSION, [_issue(2, state="closed")]),
                         gh_tools.Plan(gh_tools.REOPEN, 2))

    def test_duplicates_pick_the_oldest_open_issue_and_create_nothing(self):
        tracked = [_issue(2, state="closed"), _issue(4), _issue(8)]
        self.assertEqual(gh_tools.plan_tracking(reg.REGRESSION, tracked),
                         gh_tools.Plan(gh_tools.UPDATE, 4))

    def test_clean_run_updates_only_an_open_issue(self):
        self.assertEqual(gh_tools.plan_tracking(reg.NO_REGRESSION, [_issue(7)]),
                         gh_tools.Plan(gh_tools.UPDATE, 7))
        self.assertEqual(gh_tools.plan_tracking(reg.NO_REGRESSION, [_issue(7, state="closed")]),
                         gh_tools.Plan(gh_tools.NOTHING))
        self.assertEqual(gh_tools.plan_tracking(reg.NO_REGRESSION, []),
                         gh_tools.Plan(gh_tools.NOTHING))

    def test_statuses_without_a_comparison_never_touch_the_issue(self):
        for status in (reg.NO_BASELINE, reg.BASELINE_RESET, reg.MISMATCH, reg.NOTHING_MEASURED):
            for tracked in ([], [_issue(7)]):
                with self.subTest(status=status, tracked=bool(tracked)):
                    self.assertEqual(gh_tools.plan_tracking(status, tracked),
                                     gh_tools.Plan(gh_tools.NOTHING))


class TestApplyTracking(unittest.TestCase):

    COMPARISON = {"status": reg.REGRESSION, "pairs": {
        "p.A / d.X": {"baseline": {"hits": 0, "evaluated": 20}, "current": {"hits": 12, "evaluated": 20},
                      "margin": 0.3, "result": "regression"}}}

    def _fake(self, issues):
        self.calls = []

        def run(*args, stdin=None):
            self.calls.append((args, stdin))
            return "\n".join(json.dumps(i) for i in issues) if "--paginate" in args else ""

        return run

    def _write_call(self):
        writes = [c for c in self.calls if "-X" in c[0]]
        self.assertEqual(len(writes), 1)
        return writes[0][0], json.loads(writes[0][1])

    def test_creates_with_marker_title_and_aggregates(self):
        gh_tools.apply_tracking(self.COMPARISON, "o/r", "https://example.test/run/1", self._fake([]))
        args, payload = self._write_call()
        self.assertIn("POST", args)
        self.assertIn("repos/o/r/issues", args)
        self.assertEqual(payload["title"], gh_tools.ISSUE_TITLE)
        self.assertIn(gh_tools.MARKER, payload["body"])
        self.assertIn("https://example.test/run/1", payload["body"])
        self.assertIn("p.A / d.X", payload["body"])

    def test_update_keeps_the_marker_and_does_not_change_state(self):
        gh_tools.apply_tracking(self.COMPARISON, "o/r", "u", self._fake([_issue(7)]))
        args, payload = self._write_call()
        self.assertIn("repos/o/r/issues/7", args)
        self.assertIn(gh_tools.MARKER, payload["body"])
        self.assertNotIn("state", payload)

    def test_reopen_sets_the_state(self):
        gh_tools.apply_tracking(self.COMPARISON, "o/r", "u", self._fake([_issue(7, state="closed")]))
        _, payload = self._write_call()
        self.assertEqual(payload["state"], "open")

    def test_no_action_writes_nothing(self):
        gh_tools.apply_tracking({"status": reg.MISMATCH}, "o/r", "u", self._fake([_issue(7)]))
        self.assertEqual([c for c in self.calls if "-X" in c[0]], [])

    def test_null_pull_request_field_from_jq_is_a_plain_issue(self):
        issues = gh_tools.list_issues("o/r", self._fake([_issue(7, pull_request=None)]))
        self.assertEqual([i["number"] for i in gh_tools.tracking_issues(issues)], [7])


class TestSelectBaselineRun(unittest.TestCase):

    def _run(self, id_, branch="main", event="schedule"):
        return {"id": id_, "run_number": id_, "head_branch": branch, "event": event}

    def _artifact(self, name=gh_tools.BASELINE_ARTIFACT, expired=False):
        return {"name": name, "expired": expired}

    def test_picks_the_newest_run_with_a_live_baseline(self):
        runs = [self._run(1), self._run(3), self._run(2)]
        artifacts = {1: [self._artifact()], 2: [self._artifact()], 3: [self._artifact(expired=True)]}
        self.assertEqual(gh_tools.select_baseline_run(runs, artifacts.__getitem__), 2)

    def test_none_when_nothing_holds_a_baseline(self):
        runs = [self._run(1)]
        self.assertIsNone(gh_tools.select_baseline_run(runs, lambda _: [self._artifact("garak-weekly-report")]))
        self.assertIsNone(gh_tools.select_baseline_run([], lambda _: []))

    def test_other_branches_and_events_are_never_used(self):
        for run in (self._run(5, branch="feature"), self._run(5, event="pull_request")):
            with self.subTest(run=run):
                self.assertIsNone(gh_tools.select_baseline_run([run], lambda _: [self._artifact()]))

    def test_workflow_dispatch_on_main_is_used(self):
        run = self._run(5, event="workflow_dispatch")
        self.assertEqual(gh_tools.select_baseline_run([run], lambda _: [self._artifact()]), 5)


class TestFetchBaseline(unittest.TestCase):

    def test_downloads_the_selected_artifact(self):
        calls = []

        def fake(*args, stdin=None):
            calls.append(args)
            if args[0] == "api" and "workflows" in args[1]:
                return json.dumps({"workflow_runs": [
                    {"id": 9, "run_number": 9, "head_branch": "main", "event": "schedule"}]})
            if args[0] == "api":
                return json.dumps({"artifacts": [{"name": gh_tools.BASELINE_ARTIFACT, "expired": False}]})
            return ""

        self.assertEqual(gh_tools.fetch_baseline("o/r", Path("d"), fake), 9)
        self.assertEqual(calls[-1], ("run", "download", "9", "-R", "o/r",
                                     "-n", gh_tools.BASELINE_ARTIFACT, "-D", "d"))

    def test_no_runs_downloads_nothing(self):
        calls = []

        def fake(*args, stdin=None):
            calls.append(args)
            return json.dumps({"workflow_runs": []})

        self.assertIsNone(gh_tools.fetch_baseline("o/r", Path("d"), fake))
        self.assertEqual(len(calls), 1)

    def test_api_failure_exits_non_zero_rather_than_looking_like_no_baseline(self):
        error = subprocess.CalledProcessError(1, "gh", stderr="HTTP 502")
        with patch.object(gh_tools.subprocess, "run", side_effect=error), \
                patch.dict("os.environ", {"GITHUB_REPOSITORY": "o/r"}), \
                patch("builtins.print"):
            self.assertEqual(gh_tools.main(["fetch-baseline", "--dest", "d"]), 1)


if __name__ == "__main__":
    unittest.main()
