import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = str(ROOT / "lib" / "oracle_store.py")


def run(*args, env=None):
    merged = dict(os.environ)
    merged.update(env or {})
    return subprocess.run(
        [sys.executable, CLI, *args], capture_output=True, text=True, env=merged, check=False
    )


class TestSessionIdDefault(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["ORACLE_HOME"] = self._tmp.name + "/.oracle"
        os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        run("init", "--mode", "plain")

    def tearDown(self):
        os.environ.pop("ORACLE_HOME", None)
        os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        self._tmp.cleanup()

    def test_uses_env_session_id_when_flag_omitted(self):
        env = {"CLAUDE_CODE_SESSION_ID": "abc-123"}
        run("session-activate", "--topic", "Grafos", env=env)
        shown = json.loads(run("session-show", env=env).stdout)
        self.assertEqual(shown["active"]["session_id"], "abc-123")

    def test_explicit_flag_wins_over_env(self):
        env = {"CLAUDE_CODE_SESSION_ID": "abc-123"}
        run("session-activate", "--session-id", "xyz-789", "--topic", "Grafos", env=env)
        shown = json.loads(run("session-show", "--session-id", "xyz-789", env=env).stdout)
        self.assertIsNotNone(shown["active"])
        self.assertIsNone(json.loads(run("session-show", env=env).stdout)["active"])

    def test_error_when_neither_flag_nor_env(self):
        result = run("session-activate", "--topic", "Grafos")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("session", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
