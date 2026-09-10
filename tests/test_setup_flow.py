import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = str(ROOT / "lib" / "oracle_store.py")
SKILL = ROOT / "skills" / "oracle-setup" / "SKILL.md"


def run(*args):
    return subprocess.run(
        [sys.executable, CLI, *args], capture_output=True, text=True, check=False
    )


class TestSetupSkillContent(unittest.TestCase):
    """The setup skill is the only page a non-developer will ever read."""

    def setUp(self):
        self.text = SKILL.read_text(encoding="utf-8")

    def test_explains_all_three_tracks(self):
        for mode in ("plain", "git", "git-remote"):
            self.assertIn(mode, self.text)

    def test_avoids_unexplained_jargon_for_the_plain_track(self):
        self.assertIn("não sabe o que é git", self.text.lower())

    def test_tells_the_model_not_to_overwrite_existing_state(self):
        self.assertIn("status", self.text)


class TestSetupIsSafeToRerun(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["ORACLE_HOME"] = self._tmp.name + "/.oracle"

    def tearDown(self):
        os.environ.pop("ORACLE_HOME", None)
        self._tmp.cleanup()

    def test_rerun_switches_mode_and_keeps_data(self):
        run("init", "--mode", "plain")
        run("concepts-set", "--concept", "grafos", "--domain", "mat",
            "--level", "known", "--evidence", "demonstrou")
        run("init", "--mode", "git")
        status = json.loads(run("status").stdout)
        self.assertEqual(status["storage_mode"], "git")
        self.assertEqual(status["concepts"], 1)

    def test_status_on_a_fresh_machine_is_not_an_error(self):
        result = run("status")
        self.assertEqual(result.returncode, 0)
        self.assertFalse(json.loads(result.stdout)["initialized"])


if __name__ == "__main__":
    unittest.main()
