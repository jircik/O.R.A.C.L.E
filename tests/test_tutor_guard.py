import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = str(ROOT / "hooks" / "tutor_guard.py")
sys.path.insert(0, str(ROOT / "lib"))
import oracle_store as store


def run_hook(payload):
    return subprocess.run(
        [sys.executable, HOOK],
        capture_output=True,
        text=True,
        input=json.dumps(payload) if payload is not None else "",
        check=False,
    )


class GuardTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["ORACLE_HOME"] = self._tmp.name + "/.oracle"

    def tearDown(self):
        os.environ.pop("ORACLE_HOME", None)
        self._tmp.cleanup()


class TestSilentWhenOff(GuardTestCase):
    """The opt-in promise: with the mode off, the hook costs nothing."""

    def test_silent_when_state_missing(self):
        result = run_hook({"session_id": "s1", "prompt": "como faço um for em C?"})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_silent_when_session_not_active(self):
        store.init("plain")
        store.activate("other-session", "Grafos")
        result = run_hook({"session_id": "s1", "prompt": "qualquer coisa"})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_silent_and_zero_on_garbage_stdin(self):
        result = run_hook(None)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_silent_and_zero_on_missing_session_id(self):
        store.init("plain")
        result = run_hook({"prompt": "sem session id"})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


class TestActive(GuardTestCase):
    def setUp(self):
        super().setUp()
        store.init("plain")
        store.activate("s1", "Teoria dos Grafos", "teoria-dos-grafos")

    def test_injects_contract(self):
        result = run_hook({"session_id": "s1", "prompt": "e agora?"})
        self.assertEqual(result.returncode, 0)
        self.assertIn("O.R.A.C.L.E", result.stdout)
        self.assertIn("Teoria dos Grafos", result.stdout)

    def test_contract_states_the_three_guards(self):
        out = run_hook({"session_id": "s1", "prompt": "x"}).stdout
        self.assertIn("resposta", out)      # escape hatch
        self.assertIn("demonstr", out)      # known only by demonstration
        self.assertIn("tópico", out)        # scope limited to the study topic

    def test_contract_stays_compact(self):
        """It is injected on every turn; bloat here is paid forever."""
        out = run_hook({"session_id": "s1", "prompt": "x"}).stdout
        self.assertLess(len(out), 1800)

    def test_survives_broken_marker(self):
        """A corrupt active marker reads as 'not studying' — must be silent."""
        # Corrupt the .active marker file that the hook actually reads
        marker_path = store.home() / ".active" / "s1.json"
        marker_path.write_bytes(b"\x80\x81\x82\x83")  # invalid UTF-8
        result = run_hook({"session_id": "s1", "prompt": "x"})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")  # corrupt marker = not studying

    def test_contract_contains_concepts_set_command_with_continuation(self):
        """The contract must show the concepts-set command with a trailing backslash."""
        out = run_hook({"session_id": "s1", "prompt": "x"}).stdout
        # Check for the exact line with continuation backslash
        self.assertIn("concepts-set \\\n", out)


if __name__ == "__main__":
    unittest.main()
