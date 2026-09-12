import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import oracle_store as store


class StoreTestCase(unittest.TestCase):
    """Base class: every test gets its own throwaway ORACLE_HOME."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["ORACLE_HOME"] = self._tmp.name + "/.oracle"

    def tearDown(self):
        os.environ.pop("ORACLE_HOME", None)
        self._tmp.cleanup()


class TestHome(StoreTestCase):
    def test_home_follows_env_var(self):
        self.assertEqual(store.home(), Path(os.environ["ORACLE_HOME"]))

    def test_not_initialized_before_init(self):
        self.assertFalse(store.is_initialized())


class TestInit(StoreTestCase):
    def test_init_creates_layout(self):
        store.init("plain")
        self.assertTrue(store.is_initialized())
        self.assertTrue((store.home() / "config.json").exists())
        self.assertTrue((store.home() / "profile.json").exists())
        self.assertTrue((store.home() / "concepts.json").exists())
        self.assertTrue((store.home() / "plans").is_dir())
        self.assertTrue((store.home() / "sessions").is_dir())

    def test_init_records_mode(self):
        cfg = store.init("git")
        self.assertEqual(cfg["storage_mode"], "git")
        self.assertEqual(store.config()["storage_mode"], "git")

    def test_init_rejects_unknown_mode(self):
        with self.assertRaises(ValueError):
            store.init("dropbox")

    def test_init_is_idempotent_and_preserves_data(self):
        store.init("plain")
        store.write_json("concepts.json", [{"concept": "recursão"}])
        store.init("git")
        self.assertEqual(store.read_json("concepts.json", []), [{"concept": "recursão"}])
        self.assertEqual(store.config()["storage_mode"], "git")

    def test_config_before_init_raises(self):
        with self.assertRaises(store.OracleNotInitialized):
            store.config()


class TestJson(StoreTestCase):
    def test_write_then_read_roundtrip(self):
        store.init("plain")
        store.write_json("plans/algebra.json", {"topic": "álgebra"})
        self.assertEqual(store.read_json("plans/algebra.json", None), {"topic": "álgebra"})

    def test_read_missing_returns_default(self):
        store.init("plain")
        self.assertEqual(store.read_json("nope.json", []), [])

    def test_corrupt_json_is_backed_up_not_destroyed(self):
        store.init("plain")
        (store.home() / "concepts.json").write_text("{ this is not json", encoding="utf-8")
        self.assertEqual(store.read_json("concepts.json", []), [])
        backup = store.home() / "concepts.json.bak"
        self.assertTrue(backup.exists())
        self.assertEqual(backup.read_text(encoding="utf-8"), "{ this is not json")

    def test_write_leaves_no_temp_files(self):
        store.init("plain")
        store.write_json("concepts.json", [1, 2, 3])
        leftovers = [p.name for p in store.home().iterdir() if p.name.startswith(".tmp")]
        self.assertEqual(leftovers, [])

    def test_unicode_survives_roundtrip(self):
        store.init("plain")
        store.write_json("profile.json", {"goal": "aprender coração e ação"})
        self.assertEqual(store.read_json("profile.json", {})["goal"], "aprender coração e ação")


class TestText(StoreTestCase):
    def test_append_creates_and_appends(self):
        store.init("plain")
        store.append_text("sessions/2026-09-10-grafos.md", "linha 1\n")
        store.append_text("sessions/2026-09-10-grafos.md", "linha 2\n")
        self.assertEqual(store.read_text("sessions/2026-09-10-grafos.md"), "linha 1\nlinha 2\n")

    def test_read_text_missing_returns_default(self):
        store.init("plain")
        self.assertEqual(store.read_text("sessions/nope.md", "vazio"), "vazio")


if __name__ == "__main__":
    unittest.main()
