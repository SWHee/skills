import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("resolve-route.py")
spec = importlib.util.spec_from_file_location("route", SCRIPT)
route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(route)


class RouteTests(unittest.TestCase):
    def test_independent_roles_and_precedence(self):
        result = route.resolve({"architect": "astra/high", "implementer": "terra/high",
                                "reviewer": "claude:opus/high"}, {"implementer": "sol/medium"})
        self.assertEqual(result["roles"]["implementer"]["model"], "sol")
        self.assertEqual(result["roles"]["architect"]["model"], "astra")
        self.assertEqual(result["roles"]["reviewer"]["provider"], "claude")
        self.assertEqual(result["roles"]["repairer"]["source"], "implementer")
        self.assertFalse(result["availability_checked"])

    def test_repairer_and_verifier_can_be_selected(self):
        result = route.resolve({}, {"verifier": "sol/high", "repairer": "terra/high"})
        self.assertEqual(result["roles"]["verifier"]["model"], "sol")
        self.assertEqual(result["roles"]["repairer"]["model"], "terra")

    def test_explicit_id_preserved(self):
        model = "claude-opus-4-1-20250805"
        self.assertEqual(route.selection(f"claude:{model}/high", "reviewer")["model"], model)

    def test_bad_configs_rejected(self):
        for config in ({"review": "sol"}, {"max_calls": True}, {"max_repairs": -1},
                       {"timeout": 0}, {"mode": []}, {"mode": "weird"}, {"implementer": "mystery"},
                       {"reviewer": "claude:opus/ultra"}, {"architect": "parent/high"},
                       {"implementer": "codex:sol;exit"},
                       {"mode": "solo", "implementer": "sol"},
                       {"mode": "cross", "reviewer": "off"}):
            with self.subTest(config=config), self.assertRaises(ValueError):
                route.resolve(config, {})

    def test_cli_config_and_override(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, ".atelier.json").write_text(json.dumps({"implementer": "terra/high"}))
            proc = subprocess.run([sys.executable, str(SCRIPT), "--workdir", directory,
                                   "--implementer", "sol/medium", "--phase", "plan"],
                                  text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(proc.stdout)
            self.assertEqual(result["roles"]["implementer"]["model"], "sol")
            self.assertEqual(result["phase"], "plan")

    def test_explicit_missing_config_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            proc = subprocess.run([sys.executable, str(SCRIPT), "--config", directory + "/absent.json"],
                                  text=True, capture_output=True)
            self.assertNotEqual(proc.returncode, 0)

    def test_unknown_short_option_and_missing_workdir_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            for options in (["--impl", "sol"], ["--workdir", directory + "/missing"]):
                proc = subprocess.run([sys.executable, str(SCRIPT), *options],
                                      text=True, capture_output=True)
                self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
