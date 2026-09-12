import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CLI = str(Path(__file__).resolve().parents[1] / "lib" / "oracle_store.py")


def run(*args, stdin: str = None):
    return subprocess.run(
        [sys.executable, CLI, *args],
        capture_output=True,
        text=True,
        input=stdin,
        check=False,
    )


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["ORACLE_HOME"] = self._tmp.name + "/.oracle"

    def tearDown(self):
        os.environ.pop("ORACLE_HOME", None)
        self._tmp.cleanup()

    def json_of(self, result):
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        return json.loads(result.stdout)


class TestStatus(CliTestCase):
    def test_status_before_init(self):
        result = run("status")
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["initialized"])

    def test_status_after_init(self):
        run("init", "--mode", "plain")
        payload = self.json_of(run("status"))
        self.assertTrue(payload["initialized"])
        self.assertEqual(payload["storage_mode"], "plain")
        self.assertEqual(payload["concepts"], 0)
        self.assertIsNone(payload["active_plan"])

    def test_commands_needing_state_exit_2_before_init(self):
        result = run("concepts-list")
        self.assertEqual(result.returncode, 2)
        self.assertIn("oracle-setup", result.stderr)


class TestInit(CliTestCase):
    def test_init_reports_mode(self):
        payload = self.json_of(run("init", "--mode", "git"))
        self.assertEqual(payload["storage_mode"], "git")

    def test_init_rejects_bad_mode(self):
        result = run("init", "--mode", "dropbox")
        self.assertEqual(result.returncode, 1)


class TestConcepts(CliTestCase):
    def setUp(self):
        super().setUp()
        run("init", "--mode", "plain")

    def test_set_then_list(self):
        self.json_of(
            run(
                "concepts-set",
                "--concept", "grafos",
                "--domain", "matemática",
                "--level", "known",
                "--evidence", "explicou BFS sozinho",
            )
        )
        payload = self.json_of(run("concepts-list"))
        self.assertEqual(len(payload["concepts"]), 1)
        self.assertEqual(payload["concepts"][0]["level"], "known")

    def test_list_filters_by_level(self):
        run("concepts-set", "--concept", "a", "--domain", "d", "--level", "known", "--evidence", "e")
        run("concepts-set", "--concept", "b", "--domain", "d", "--level", "gap", "--evidence", "e")
        payload = self.json_of(run("concepts-list", "--level", "known"))
        self.assertEqual([c["concept"] for c in payload["concepts"]], ["a"])

    def test_bad_level_exits_nonzero(self):
        result = run(
            "concepts-set", "--concept", "a", "--domain", "d",
            "--level", "mastered", "--evidence", "e",
        )
        self.assertEqual(result.returncode, 1)


class TestProfile(CliTestCase):
    def setUp(self):
        super().setUp()
        run("init", "--mode", "plain")

    def test_set_then_read_back_through_status(self):
        self.json_of(
            run("profile-set", "--key", "explanation_style",
                "--value", "analogias com futebol funcionam")
        )
        payload = self.json_of(run("status"))
        self.assertEqual(
            payload["profile"]["explanation_style"], "analogias com futebol funcionam"
        )


class TestPlans(CliTestCase):
    def setUp(self):
        super().setUp()
        run("init", "--mode", "plain")
        self.plan = {
            "topic": "Teoria dos Grafos",
            "goal": "resolver questões de prova",
            "deadline": "2026-10-01",
            "status": "active",
            "milestones": [{"title": "BFS", "status": "todo", "skipped_reason": None}],
        }

    def test_save_reads_stdin_and_returns_slug(self):
        payload = self.json_of(run("plan-save", stdin=json.dumps(self.plan)))
        self.assertEqual(payload["slug"], "teoria-dos-grafos")

    def test_show_without_slug_returns_active_plan(self):
        run("plan-save", stdin=json.dumps(self.plan))
        payload = self.json_of(run("plan-show"))
        self.assertEqual(payload["plan"]["topic"], "Teoria dos Grafos")

    def test_show_missing_plan_returns_null(self):
        payload = self.json_of(run("plan-show", "--slug", "nao-existe"))
        self.assertIsNone(payload["plan"])

    def test_invalid_json_on_stdin_exits_nonzero(self):
        result = run("plan-save", stdin="not json")
        # Exactly 1 (other error) per the CLI's exit-code contract, not just
        # "non-zero" — that looser check is what let this kind of bug through.
        self.assertEqual(result.returncode, 1)
        self.assertIn("inválido", result.stderr)

    def test_list_filters_by_status(self):
        run("plan-save", stdin=json.dumps(self.plan))
        payload = self.json_of(run("plan-list", "--status", "done"))
        self.assertEqual(payload["plans"], [])


class TestSession(CliTestCase):
    def setUp(self):
        super().setUp()
        run("init", "--mode", "plain")

    def test_activate_show_deactivate_cycle(self):
        self.json_of(run("session-activate", "--session-id", "s1", "--topic", "Grafos"))
        shown = self.json_of(run("session-show", "--session-id", "s1"))
        self.assertEqual(shown["active"]["topic"], "Grafos")
        self.json_of(run("session-deactivate", "--session-id", "s1"))
        after = self.json_of(run("session-show", "--session-id", "s1"))
        self.assertIsNone(after["active"])

    def test_log_reads_stdin(self):
        payload = self.json_of(run("log", "--topic", "Grafos", stdin="cobriu BFS\n"))
        self.assertTrue(payload["path"].startswith("sessions/"))
        self.assertIn("cobriu BFS", (Path(os.environ["ORACLE_HOME"]) / payload["path"]).read_text())

    def test_missing_required_flag_exits_1(self):
        env = dict(os.environ)
        env.pop("CLAUDE_CODE_SESSION_ID", None)
        result = subprocess.run(
            [sys.executable, CLI, "session-activate", "--topic", "Grafos"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("session", result.stderr.lower())


class TestCommit(CliTestCase):
    def test_commit_in_plain_mode_is_a_noop(self):
        run("init", "--mode", "plain")
        payload = self.json_of(run("commit", "--message", "estudou grafos"))
        self.assertFalse(payload["committed"])


if __name__ == "__main__":
    unittest.main()
