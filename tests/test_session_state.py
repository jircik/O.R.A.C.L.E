import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import oracle_store as store


class SessionTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["ORACLE_HOME"] = self._tmp.name + "/.oracle"
        store.init("plain")

    def tearDown(self):
        os.environ.pop("ORACLE_HOME", None)
        self._tmp.cleanup()


class TestActivation(SessionTestCase):
    def test_no_record_before_activate(self):
        self.assertIsNone(store.active_record("sess-1"))

    def test_activate_writes_record(self):
        record = store.activate("sess-1", "Teoria dos Grafos", "teoria-dos-grafos")
        self.assertEqual(record["session_id"], "sess-1")
        self.assertEqual(record["topic"], "Teoria dos Grafos")
        self.assertEqual(record["plan_slug"], "teoria-dos-grafos")
        self.assertIn("started_at", record)
        self.assertEqual(store.active_record("sess-1"), record)

    def test_sessions_are_isolated_from_each_other(self):
        store.activate("sess-studying", "Grafos")
        self.assertIsNone(store.active_record("sess-working"))

    def test_deactivate_removes_and_returns_record(self):
        store.activate("sess-1", "Grafos")
        removed = store.deactivate("sess-1")
        self.assertEqual(removed["topic"], "Grafos")
        self.assertIsNone(store.active_record("sess-1"))

    def test_deactivate_twice_is_safe(self):
        store.activate("sess-1", "Grafos")
        store.deactivate("sess-1")
        self.assertIsNone(store.deactivate("sess-1"))

    def test_corrupt_active_record_reads_as_inactive(self):
        store.activate("sess-1", "Grafos")
        (store.home() / ".active" / "sess-1.json").write_text("nope", encoding="utf-8")
        self.assertIsNone(store.active_record("sess-1"))

    def test_session_id_with_path_separators_is_sanitized(self):
        store.activate("../../escape", "Grafos")
        files = list((store.home() / ".active").glob("*.json"))
        self.assertEqual(len(files), 1)
        self.assertIsNotNone(store.active_record("../../escape"))


class TestSessionLog(SessionTestCase):
    def test_log_path_is_dated_and_slugged(self):
        rel = store.session_log_rel("Teoria dos Grafos", date="2026-09-10")
        self.assertEqual(rel, "sessions/2026-09-10-teoria-dos-grafos.md")

    def test_log_session_appends(self):
        rel = store.log_session("Grafos", "## sessão 1\ncobriu BFS\n")
        store.log_session("Grafos", "## sessão 2\ncobriu DFS\n")
        content = store.read_text(rel)
        self.assertIn("cobriu BFS", content)
        self.assertIn("cobriu DFS", content)


class TestPrune(SessionTestCase):
    def _age_record(self, session_id, hours):
        path = store.home() / ".active" / f"{session_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        old = datetime.now(timezone.utc) - timedelta(hours=hours)
        record["started_at"] = old.isoformat(timespec="seconds")
        path.write_text(json.dumps(record), encoding="utf-8")

    def test_prunes_stale_records_only(self):
        store.activate("fresh", "Grafos")
        store.activate("stale", "Cálculo")
        self._age_record("stale", 48)
        removed = store.prune_active(max_age_hours=24)
        self.assertEqual(removed, 1)
        self.assertIsNotNone(store.active_record("fresh"))
        self.assertIsNone(store.active_record("stale"))

    def test_prunes_unparseable_records(self):
        (store.home() / ".active" / "junk.json").write_text("{{{", encoding="utf-8")
        self.assertEqual(store.prune_active(), 1)

    def test_prune_on_empty_dir_returns_zero(self):
        self.assertEqual(store.prune_active(), 0)


if __name__ == "__main__":
    unittest.main()
