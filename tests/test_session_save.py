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

    def test_marker_closed_before_plan_link_fails(self):
        """Marker is closed BEFORE plan-link block, preventing duplicate logs.

        This test locks in Finding 1 (earlier review): deactivate() happens
        before save_plan(). If plan-link fails after the log is written, the
        marker is already gone, so a retry does not append a second log block.

        Finding 5 (this wave) changed what happens to the exception itself:
        the plan-link block is now wrapped in try/except so a plan-link
        failure no longer propagates out of save_and_close and no longer
        skips commit() — see test_plan_link_failure_does_not_skip_commit
        below for that half. This test still locks in the ordering: even
        though the failure is now swallowed rather than raised, the marker
        must still be closed before the (failing) plan-link block runs, and
        a retry must not duplicate the log.
        """
        import session_save

        store.save_plan({"topic": "Grafos", "status": "active"})
        store.activate("s1", "Grafos", "grafos")

        original_save_plan = store.save_plan
        call_count = [0]

        def failing_save_plan(plan):
            call_count[0] += 1
            raise RuntimeError("simulated plan-link failure")

        store.save_plan = failing_save_plan

        try:
            # First call: save_and_close writes the log, closes the marker,
            # and then save_plan fails inside the plan-link block. With the
            # Finding 5 fix, that failure is caught, so this must NOT raise.
            result = session_save.save_and_close("s1")

            # Verify the failure path was actually hit.
            self.assertEqual(call_count[0], 1, "save_plan should have been called")
            # save_and_close still reports success (log was written; commit ran).
            self.assertTrue(result["saved"])

            # CRITICAL ASSERTION (discriminates old vs new ordering):
            # Under fixed ordering: marker is gone (deactivate ran before save_plan)
            # Under old ordering: marker still exists (deactivate at end never ran)
            self.assertIsNone(
                store.active_record("s1"),
                "Marker must be closed before plan-link block, even if plan-link fails",
            )
        finally:
            store.save_plan = original_save_plan

        # Second call: should return saved=False because marker is gone
        second = session_save.save_and_close("s1")
        self.assertFalse(second["saved"])

        # CRITICAL ASSERTION (discriminates old vs new ordering):
        # Under fixed ordering: only one "## " block (second call returned saved=False)
        # Under old ordering: two "## " blocks (second call appended again)
        logs = list((store.home() / "sessions").glob("*.md"))
        self.assertEqual(len(logs), 1)
        log_text = logs[0].read_text(encoding="utf-8")
        block_count = log_text.count("\n## ")
        self.assertEqual(
            block_count,
            1,
            f"Log should have exactly one session block, not {block_count}. "
            f"If this fails, deactivate() is running after plan-link, not before.",
        )

    def test_plan_link_failure_does_not_skip_commit(self):
        """Finding 5: a failure in the plan-link block must not stop commit()
        from running. Before the fix, the plan-link block was unguarded, so
        an exception there propagated past `store.commit(...)` — on the
        SessionEnd path the outer handler in main() swallows it and exits 0,
        so the session gets logged but never versioned (git/git-remote
        tracks), with no warning at all.

        This test patches save_plan to raise and asserts save_and_close still
        returns *a* commit result (i.e. execution reached store.commit(...))
        instead of letting the exception propagate out of save_and_close.
        """
        import session_save

        store.save_plan({"topic": "Grafos", "status": "active"})
        store.activate("s1", "Grafos", "grafos")

        original_save_plan = store.save_plan

        def failing_save_plan(plan):
            raise RuntimeError("simulated plan-link failure")

        store.save_plan = failing_save_plan
        try:
            result = session_save.save_and_close("s1")
        finally:
            store.save_plan = original_save_plan

        self.assertTrue(result["saved"])
        self.assertIsNotNone(result["commit"])
        self.assertIn("mode", result["commit"])


if __name__ == "__main__":
    unittest.main()
