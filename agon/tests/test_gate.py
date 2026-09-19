#!/usr/bin/env python3
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "gate.py"
CORE_TOPICS = [
    "eligibility", "team", "work_window", "reuse", "ai_usage",
    "required_tech", "data_rights", "ip_licensing", "submission",
    "judging", "demo_environment",
]


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "brief.md").write_text("# Reviewed brief\n", encoding="utf-8")
        (self.root / "rules.txt").write_text("official rules\n", encoding="utf-8")
        self.gate = self.root / "gate.json"
        self.data = {
            "schema_version": 1,
            "event": {
                "name": "Example Hack",
                "track": "Open",
                "award": "Grand Prize",
                "coding_start": "2030-01-01T09:00:00+09:00",
                "deadline": "2030-01-03T09:00:00+09:00",
            },
            "sources": [{
                "id": "rules",
                "uri": "https://example.test/rules",
                "retrieved_at": "2029-12-31T10:00:00+09:00",
                "authority": "official",
                "snapshot": "rules.txt",
            }],
            "rules": [{
                "id": "rule-" + topic,
                "topic": topic,
                "status": "resolved",
                "source_ids": ["rules"],
                "locator": "section " + topic,
                "resolution": "The compliant plan is recorded in the brief.",
            } for topic in CORE_TOPICS],
            "rubric": {
                "award": "Grand Prize",
                "weighting": "published",
                "criteria": [
                    {"id": "impact", "name": "Impact", "source_id": "rules", "locator": "Judging 1", "weight": 60,
                     "feature": "A judge completes the primary workflow.", "proof": "Live replay succeeds in under two minutes."},
                    {"id": "execution", "name": "Execution", "source_id": "rules", "locator": "Judging 2", "weight": 40,
                     "feature": "The fallback keeps the demo usable.", "proof": "A forced provider failure shows the fallback."},
                ],
            },
            "artifacts": {"brief": "brief.md"},
            "budget": {"implementation_minutes": 600, "verification_minutes": 120, "submission_minutes": 60},
            "review": {"verdict": "pending", "reviewer": "", "reviewed_at": "", "fingerprint": "", "rationale": ""},
        }

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, data=None, raw=None):
        if raw is not None:
            self.gate.write_text(raw, encoding="utf-8")
        else:
            self.gate.write_text(json.dumps(self.data if data is None else data, allow_nan=True), encoding="utf-8")

    def run_gate(self, *args):
        before = self.snapshot_tree()
        result = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], text=True, capture_output=True)
        after = self.snapshot_tree()
        self.assertEqual(before, after, "gate.py mutated the fixture directory")
        payload = json.loads(result.stdout) if result.stdout else None
        return result, payload

    def snapshot_tree(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def fingerprint(self):
        self.write()
        result, payload = self.run_gate("fingerprint", self.gate)
        self.assertEqual(result.returncode, 0, result.stderr)
        return payload["fingerprint"]

    def make_ready(self, reviewed_at="2030-01-01T09:01:00+09:00"):
        digest = self.fingerprint()
        self.data["review"] = {
            "verdict": "ready", "reviewer": "A. Reviewer", "reviewed_at": reviewed_at,
            "fingerprint": digest, "rationale": "All six readiness responsibilities were reviewed.",
        }
        self.write()

    def assert_invalid(self, data=None, raw=None):
        self.write(data, raw)
        result, payload = self.run_gate("check", self.gate, "--now", "2030-01-01T10:00:00+09:00")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(payload["status"], "invalid")

    def test_ready_and_deterministic_fingerprint(self):
        first = self.fingerprint()
        reordered = {key: self.data[key] for key in reversed(self.data)}
        self.write(reordered)
        result, payload = self.run_gate("fingerprint", self.gate)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(first, payload["fingerprint"])
        self.make_ready()
        result, payload = self.run_gate("check", self.gate, "--now", "2030-01-01T10:00:00+09:00")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(payload["status"], "ready")
        self.assertIn("local", payload["scope"].lower())
        self.assertEqual(payload["checked_at"], "2030-01-01T10:00:00+09:00")
        self.assertTrue(payload["now_overridden"])

    def test_pending_template_is_well_formed_but_blocked(self):
        self.write()
        result, payload = self.run_gate("check", self.gate, "--now", "2030-01-01T10:00:00+09:00")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(any("pending" in item for item in payload["blockers"]))

    def test_blocked_review_may_leave_review_fields_blank(self):
        self.data["review"]["verdict"] = "blocked"
        self.write()
        result, payload = self.run_gate("check", self.gate, "--now", "2030-01-01T10:00:00+09:00")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(any("blocked" in item for item in payload["blockers"]))

    def test_unknown_conflict_and_violated_rules_block(self):
        for status in ("unknown", "conflict", "violated"):
            with self.subTest(status=status):
                self.data["rules"][0]["status"] = status
                self.make_ready()
                result, payload = self.run_gate("check", self.gate, "--now", "2030-01-01T10:00:00+09:00")
                self.assertEqual(result.returncode, 1)
                self.assertTrue(any(status in item for item in payload["blockers"]))
                self.data["rules"][0]["status"] = "resolved"

    def test_missing_core_coverage_and_bad_source_reference_are_invalid(self):
        data = deepcopy(self.data); data["rules"].pop()
        self.assert_invalid(data)
        data = deepcopy(self.data); data["rules"][0]["source_ids"] = ["missing"]
        self.assert_invalid(data)

    def test_award_mix_and_weight_contract(self):
        data = deepcopy(self.data); data["rubric"]["award"] = "Sponsor Prize"
        self.assert_invalid(data)
        data = deepcopy(self.data); data["rubric"]["criteria"][0]["weight"] = 59
        self.assert_invalid(data)
        data = deepcopy(self.data); data["rubric"]["criteria"][0]["weight"] = None
        self.assert_invalid(data)
        data = deepcopy(self.data); data["rubric"]["weighting"] = "unpublished"
        for criterion in data["rubric"]["criteria"]: criterion["weight"] = None
        self.data = data; self.make_ready()
        result, payload = self.run_gate("check", self.gate, "--now", "2030-01-01T10:00:00+09:00")
        self.assertEqual(result.returncode, 0, payload)

    def test_rubric_criterion_requires_official_source(self):
        data = deepcopy(self.data)
        data["sources"].append({
            "id": "blog", "uri": "https://example.test/blog", "retrieved_at": "2029-12-31T10:00:00+09:00",
            "authority": "supporting", "snapshot": "rules.txt",
        })
        data["rubric"]["criteria"][0]["source_id"] = "blog"
        self.assert_invalid(data)

    def test_nan_infinity_and_boolean_numbers_are_invalid(self):
        for value in (math.nan, math.inf, True):
            with self.subTest(value=value):
                data = deepcopy(self.data); data["budget"]["implementation_minutes"] = value
                self.assert_invalid(data)
        data = deepcopy(self.data)
        for key in data["budget"]:
            data["budget"][key] = 1e308
        self.assert_invalid(data)

    def test_changed_snapshot_brief_or_budget_stales_review(self):
        for target in ("snapshot", "brief", "budget"):
            with self.subTest(target=target):
                self.make_ready()
                if target == "snapshot": (self.root / "rules.txt").write_text("changed", encoding="utf-8")
                elif target == "brief": (self.root / "brief.md").write_text("changed", encoding="utf-8")
                else:
                    self.data["budget"]["implementation_minutes"] += 1; self.write()
                result, payload = self.run_gate("check", self.gate, "--now", "2030-01-01T10:00:00+09:00")
                self.assertEqual(result.returncode, 1)
                self.assertTrue(any("fingerprint" in item for item in payload["blockers"]))
                (self.root / "rules.txt").write_text("official rules\n", encoding="utf-8")
                (self.root / "brief.md").write_text("# Reviewed brief\n", encoding="utf-8")
                self.data["budget"]["implementation_minutes"] = 600

    def test_time_window_and_reserve_boundaries(self):
        self.make_ready()
        cases = [
            ("2029-12-31T23:59:59Z", "not started"),
            ("2030-01-03T00:00:00Z", "deadline"),
            ("2030-01-02T11:01:00Z", "budget"),
        ]
        for now, word in cases:
            with self.subTest(now=now):
                result, payload = self.run_gate("check", self.gate, "--now", now)
                self.assertEqual(result.returncode, 1)
                self.assertTrue(any(word in item for item in payload["blockers"]), payload)
        data = deepcopy(self.data); data["event"]["deadline"] = data["event"]["coding_start"]
        self.assert_invalid(data)

    def test_timezone_offsets_are_normalized(self):
        self.make_ready(reviewed_at="2030-01-01T00:01:00Z")
        result, payload = self.run_gate("check", self.gate, "--now", "2030-01-01T00:02:00Z")
        self.assertEqual(result.returncode, 0, payload)

    def test_future_source_or_review_blocks(self):
        data = deepcopy(self.data); data["sources"][0]["retrieved_at"] = "2030-01-01T11:00:00+09:00"
        self.data = data; self.make_ready(reviewed_at="2030-01-01T11:01:00+09:00")
        result, payload = self.run_gate("check", self.gate, "--now", "2030-01-01T10:00:00+09:00")
        self.assertEqual(result.returncode, 1); self.assertTrue(any("source" in x for x in payload["blockers"]))
        self.data["sources"][0]["retrieved_at"] = "2029-12-31T10:00:00+09:00"
        self.make_ready(reviewed_at="2030-01-01T11:00:00+09:00")
        result, payload = self.run_gate("check", self.gate, "--now", "2030-01-01T10:00:00+09:00")
        self.assertEqual(result.returncode, 1); self.assertTrue(any("review" in x for x in payload["blockers"]))

    def test_review_before_source_is_invalid(self):
        self.make_ready(reviewed_at="2029-12-30T10:00:00+09:00")
        result, payload = self.run_gate("check", self.gate, "--now", "2030-01-01T10:00:00+09:00")
        self.assertEqual(result.returncode, 1); self.assertEqual(payload["status"], "blocked")
        self.assertTrue(any("predates" in item for item in payload["blockers"]))

    def test_fingerprint_can_refresh_after_source_update(self):
        self.make_ready()
        self.data["sources"][0]["retrieved_at"] = "2030-01-01T09:02:00+09:00"
        self.write()
        result, payload = self.run_gate("fingerprint", self.gate)
        self.assertEqual(result.returncode, 0, payload)

    def test_malformed_duplicate_keys_unknown_fields_and_timestamp_are_invalid(self):
        self.assert_invalid(raw="{")
        raw = json.dumps(self.data).replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1', 1)
        self.assert_invalid(raw=raw)
        data = deepcopy(self.data); data["typo"] = 1
        self.assert_invalid(data)
        data = deepcopy(self.data); data["event"]["deadline"] = "2030-01-03"
        self.assert_invalid(data)

    def test_paths_reject_absolute_parent_symlink_directory_and_missing(self):
        with tempfile.TemporaryDirectory() as outside_tmp:
            outside = Path(outside_tmp) / "rules.txt"
            outside.write_text("outside", encoding="utf-8")
            variants = [str(outside), "../outside-rules.txt", "missing.txt", "."]
            link = self.root / "escape.txt"
            try:
                link.symlink_to(outside)
                variants.append("escape.txt")
            except OSError:
                pass
            for path in variants:
                with self.subTest(path=path):
                    data = deepcopy(self.data); data["sources"][0]["snapshot"] = path
                    self.assert_invalid(data)

    def test_empty_snapshot_and_brief_are_invalid(self):
        for filename, field in (("rules.txt", "snapshot"), ("brief.md", "brief")):
            with self.subTest(filename=filename):
                path = self.root / filename
                original = path.read_text(encoding="utf-8")
                path.write_text("", encoding="utf-8")
                try:
                    self.assert_invalid(self.data)
                finally:
                    path.write_text(original, encoding="utf-8")

    def test_cli_usage_errors_return_two_as_json(self):
        self.write()
        for args in (("wat", self.gate), ("check", self.gate, "--wat"), ("check",)):
            with self.subTest(args=args):
                result, payload = self.run_gate(*args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(payload["status"], "invalid")


if __name__ == "__main__":
    unittest.main()
