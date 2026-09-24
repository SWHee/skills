import importlib.util
import contextlib
import io
import json
import os
import signal
import sys
import time
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

SCRIPT = Path(__file__).resolve().parents[1] / "skills/prism/scripts/review.py"
spec = importlib.util.spec_from_file_location("review", SCRIPT)
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.PIPE)

    def baseline(self):
        (self.root / "app.txt").write_text("base\n")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.git("branch", "baseline")

    def test_staged_unstaged_and_untracked(self):
        self.baseline()
        (self.root / "app.txt").write_text("staged\n")
        self.git("add", ".")
        (self.root / "app.txt").write_text("final\n")
        (self.root / "new file.txt").write_text("new\n")
        before = self.git("status", "--porcelain")
        _, snapshot = review.collect(self.root)
        self.assertIn("+final", snapshot["input"])
        self.assertIn("1: new", snapshot["input"])
        self.assertEqual(before, self.git("status", "--porcelain"))
        (self.root / "app.txt").write_text("changed again\n")
        self.assertNotEqual(snapshot["fingerprint"], review.collect(self.root)[1]["fingerprint"])

    def test_unborn_and_empty(self):
        self.assertTrue(review.collect(self.root)[1]["empty"])
        (self.root / "new.txt").write_text("new\n")
        self.git("add", ".")
        self.assertIn("+new", review.collect(self.root)[1]["input"])

    def test_branch_review_and_dirty_rejection(self):
        self.baseline()
        (self.root / "app.txt").write_text("feature\n")
        self.git("commit", "-qam", "feature")
        self.assertIn("+feature", review.collect(self.root, "baseline")[1]["input"])
        (self.root / "untracked").write_text("local")
        with self.assertRaisesRegex(ValueError, "clean checkout"):
            review.collect(self.root, "baseline")

    def test_literal_paths_and_size_limit(self):
        self.baseline()
        (self.root / "[literal].txt").write_text("one\n")
        (self.root / "l.txt").write_text("two\n")
        data = review.collect(self.root, paths=["[literal].txt"])[1]["input"]
        self.assertIn("one", data)
        self.assertNotIn("two", data)
        with patch.object(review, "LIMIT", 2):
            with self.assertRaisesRegex(ValueError, "too large"):
                review.collect(self.root)

    def test_untracked_symlink_is_not_followed(self):
        (self.root / "outside").symlink_to("/etc/hosts")
        with self.assertRaisesRegex(ValueError, "non-regular"):
            review.collect(self.root)

    def test_structured_result_and_failures(self):
        payload = {"verdict": "approve", "summary": "No supported findings", "findings": [], "limitations": ["Tests not run"]}
        envelope = {"subtype": "success", "is_error": False, "structured_output": payload}
        self.assertEqual(review.parse_result(json.dumps(envelope))[0], payload)
        for invalid in [{"subtype": "error_max_turns"}, {"subtype": "success", "is_error": True},
                        {"subtype": "success", "structured_output": {}}]:
            with self.assertRaises(ValueError):
                review.parse_result(json.dumps(invalid))
        payload["verdict"] = "needs-attention"
        with self.assertRaisesRegex(ValueError, "contradicts"):
            review.parse_result(json.dumps(envelope))

    def test_read_only_cli_and_timeout(self):
        args = review.claude_args(SimpleNamespace(effort=None))
        self.assertEqual(args[args.index("--tools") + 1], "Read,Glob,Grep")
        self.assertIn("--safe-mode", args)
        self.assertIn("--strict-mcp-config", args)
        self.assertEqual(args[args.index("--model") + 1], "claude-opus-5-5")
        self.assertEqual(args[args.index("--effort") + 1], "high")
        strong = review.claude_args(SimpleNamespace(effort="xhigh"))
        self.assertEqual(strong[strong.index("--effort") + 1], "xhigh")
        with self.assertRaises(subprocess.TimeoutExpired):
            review.run(["python3", "-c", "import time; time.sleep(10)"], timeout=0.05)

    def test_full_flow_saved_report_and_stale_detection(self):
        self.baseline()
        (self.root / "app.txt").write_text("to review\n")
        actual_run = review.run
        def fake_claude(argv, **kwargs):
            if argv[0] != "claude":
                return actual_run(argv, **kwargs)
            self.assertIn(b"+to review", kwargs["input"])
            self.assertIn("--json-schema", argv)
            (self.root / "app.txt").write_text("concurrent change\n")
            return json.dumps({"subtype": "success", "is_error": False,
                "structured_output": {"verdict": "approve", "summary": "No findings",
                    "findings": [], "limitations": ["Tests not run"]}}).encode()
        output = self.root / "report.json"
        with patch.object(review, "run", side_effect=fake_claude), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            review.main(["--cwd", str(self.root), "--output", str(output)])
            report = json.loads(output.read_text())
            self.assertTrue(report["stale"])
            self.assertEqual(report["review"]["verdict"], "approve")
            with self.assertRaisesRegex(ValueError, "new absolute path"):
                review.main(["--cwd", str(self.root), "--output", str(output)])

    def test_host_signals_reap_child(self):
        self.baseline()
        (self.root / "app.txt").write_text("changed\n")
        bindir = self.root / "bin"
        bindir.mkdir()
        fake = bindir / "claude"
        fake.write_text("#!/usr/bin/env python3\nimport os,time\nfrom pathlib import Path\n"
                        "Path(os.environ['REVIEW_TEST_PID']).write_text(str(os.getpid()))\n"
                        "time.sleep(30)\n")
        fake.chmod(0o700)
        for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            with self.subTest(signal=sig):
                pidfile = self.root / f"child-{sig}.pid"
                env = dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ['PATH'],
                           REVIEW_TEST_PID=str(pidfile))
                parent = subprocess.Popen([sys.executable, str(SCRIPT), '--cwd', str(self.root),
                    '--path', 'app.txt'], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    start_new_session=True)
                child = None
                try:
                    deadline = time.monotonic() + 5
                    while not pidfile.exists() and time.monotonic() < deadline:
                        time.sleep(0.02)
                    child = int(pidfile.read_text())
                    self.assertEqual(os.getpgid(child), os.getpgid(parent.pid))
                    parent.send_signal(sig)
                    parent.communicate(timeout=5)
                    self.assertEqual(parent.returncode, 130)
                    with self.assertRaises(ProcessLookupError):
                        os.kill(child, 0)
                finally:
                    if child is not None:
                        try:
                            os.kill(child, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    if parent.poll() is None:
                        parent.kill()
                    parent.communicate()


if __name__ == "__main__":
    unittest.main()
