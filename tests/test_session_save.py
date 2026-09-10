import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = str(ROOT / "hooks" / "session_save.py")
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(ROOT / "hooks"))
import oracle_store as store


def run_hook(payload):
    return subprocess.run(
        [sys.executable, HOOK],
        capture_output=True,
        text=True,
        input=json.dumps(payload) if payload is not None else "",
        check=False,
    )


class SaveTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["ORACLE_HOME"] = self._tmp.name + "/.oracle"
        store.init("plain")

    def tearDown(self):
        os.environ.pop("ORACLE_HOME", None)
        self._tmp.cleanup()


class TestHookBehaviour(SaveTestCase):
    def test_inactive_session_writes_nothing(self):
        result = run_hook({"session_id": "s1", "reason": "exit"})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(list((store.home() / "sessions").glob("*.md")), [])

    def test_active_session_is_logged_and_closed(self):
        store.activate("s1", "Teoria dos Grafos", "teoria-dos-grafos")
        result = run_hook({"session_id": "s1", "reason": "exit"})
        self.assertEqual(result.returncode, 0)
        logs = list((store.home() / "sessions").glob("*.md"))
        self.assertEqual(len(logs), 1)
        self.assertIn("Teoria dos Grafos", logs[0].read_text(encoding="utf-8"))
        self.assertIsNone(store.active_record("s1"))

    def test_garbage_stdin_exits_zero(self):
        self.assertEqual(run_hook(None).returncode, 0)

    def test_prunes_orphan_markers(self):
        from datetime import datetime, timedelta, timezone

        store.activate("dead", "Cálculo")
        path = store.home() / ".active" / "dead.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["started_at"] = (
            datetime.now(timezone.utc) - timedelta(hours=48)
        ).isoformat(timespec="seconds")
        path.write_text(json.dumps(record), encoding="utf-8")

        run_hook({"session_id": "unrelated", "reason": "exit"})
        self.assertIsNone(store.active_record("dead"))


class TestSaveAndClose(SaveTestCase):
    def test_is_idempotent(self):
        """/oracle-off then SessionEnd must not log the session twice."""
        import session_save

        store.activate("s1", "Grafos")
        first = session_save.save_and_close("s1")
        second = session_save.save_and_close("s1")
        self.assertTrue(first["saved"])
        self.assertFalse(second["saved"])
        self.assertEqual(len(list((store.home() / "sessions").glob("*.md"))), 1)

    def test_links_session_into_its_plan(self):
        import session_save

        store.save_plan({"topic": "Teoria dos Grafos", "status": "active"})
        store.activate("s1", "Teoria dos Grafos", "teoria-dos-grafos")
        session_save.save_and_close("s1")
        plan = store.load_plan("teoria-dos-grafos")
        self.assertEqual(len(plan["sessions"]), 1)

    def test_does_not_duplicate_the_plan_link(self):
        import session_save

        store.save_plan({"topic": "Teoria dos Grafos", "status": "active"})
        store.activate("s1", "Teoria dos Grafos", "teoria-dos-grafos")
        session_save.save_and_close("s1")
        store.activate("s2", "Teoria dos Grafos", "teoria-dos-grafos")
        session_save.save_and_close("s2")
        plan = store.load_plan("teoria-dos-grafos")
        self.assertEqual(len(plan["sessions"]), 1)  # same day, same log file


if __name__ == "__main__":
    unittest.main()
