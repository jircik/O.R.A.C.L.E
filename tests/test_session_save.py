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

    def test_empty_stdin_exits_zero(self):
        self.assertEqual(run_hook(None).returncode, 0)

    def test_invalid_json_stdin_exits_zero(self):
        """Invalid JSON on stdin is silently ignored and hook exits 0."""
        result = subprocess.run(
            [sys.executable, HOOK],
            capture_output=True,
            text=True,
            input="not json at all",
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

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

    def test_handles_nonexistent_plan(self):
        """Marker with plan_slug pointing to a plan that doesn't exist."""
        import session_save

        store.activate("s1", "Tema", "tema-inexistente")
        result = session_save.save_and_close("s1")
        # Still succeeds and writes the log
        self.assertTrue(result["saved"])
        self.assertIsNotNone(result["log"])
        logs = list((store.home() / "sessions").glob("*.md"))
        self.assertEqual(len(logs), 1)
        # Marker is closed
        self.assertIsNone(store.active_record("s1"))

    def test_idempotent_even_if_plan_link_fails(self):
        """If plan-link fails, marker is already gone (test Finding 1).

        Patch load_plan to return None so the if plan guard prevents
        the append, or patch save_plan to raise. Either way, verify that
        a second save_and_close() sees the marker as gone.
        """
        import session_save

        store.save_plan({"topic": "Algebra", "status": "active"})
        store.activate("s1", "Algebra", "algebra")

        # First, let's verify a normal call works
        first = session_save.save_and_close("s1")
        self.assertTrue(first["saved"])

        # Now activate again and patch save_plan to fail
        store.activate("s2", "Algebra", "algebra")
        original_save_plan = store.save_plan

        def failing_save_plan(plan):
            raise RuntimeError("simulated plan-link failure")

        store.save_plan = failing_save_plan

        try:
            # This will raise because save_plan fails, but the marker
            # should already be gone by then (deactivate happened first)
            try:
                session_save.save_and_close("s2")
            except RuntimeError:
                pass  # Expected: plan-link failed
        finally:
            store.save_plan = original_save_plan

        # Now verify that the marker for s2 is actually gone
        self.assertIsNone(store.active_record("s2"))

        # And a second call to save_and_close would return saved=False
        second = session_save.save_and_close("s2")
        self.assertFalse(second["saved"])


if __name__ == "__main__":
    unittest.main()
