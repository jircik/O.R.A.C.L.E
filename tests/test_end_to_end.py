import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = str(ROOT / "lib" / "oracle_store.py")
GUARD = str(ROOT / "hooks" / "tutor_guard.py")
SAVE = str(ROOT / "hooks" / "session_save.py")

SESSION = "e2e-session"


def cli(*args, stdin=None):
    env = dict(os.environ)
    env["CLAUDE_CODE_SESSION_ID"] = SESSION
    return subprocess.run(
        [sys.executable, CLI, *args], capture_output=True, text=True, input=stdin, env=env,
        check=False,
    )


def hook(script, payload):
    return subprocess.run(
        [sys.executable, script], capture_output=True, text=True,
        input=json.dumps(payload), check=False,
    )


class TestFullJourney(unittest.TestCase):
    """setup -> plan -> study -> close, the way a real week looks."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["ORACLE_HOME"] = self._tmp.name + "/.oracle"

    def tearDown(self):
        os.environ.pop("ORACLE_HOME", None)
        self._tmp.cleanup()

    def test_journey(self):
        # 1. A quick question before setup must not be touched by the hook.
        self.assertEqual(hook(GUARD, {"session_id": SESSION, "prompt": "for em C?"}).stdout, "")

        # 2. Setup.
        self.assertEqual(cli("init", "--mode", "plain").returncode, 0)

        # 3. Still silent — installed but not studying.
        self.assertEqual(hook(GUARD, {"session_id": SESSION, "prompt": "for em C?"}).stdout, "")

        # 4. A plan is created.
        plan = {
            "topic": "Teoria dos Grafos",
            "goal": "prova de 01/10",
            "deadline": "2026-10-01",
            "status": "active",
            "milestones": [{"title": "BFS", "status": "todo", "skipped_reason": None}],
        }
        slug = json.loads(cli("plan-save", stdin=json.dumps(plan)).stdout)["slug"]

        # 5. Study starts: now the contract is injected.
        cli("session-activate", "--topic", "Teoria dos Grafos", "--plan-slug", slug)
        injected = hook(GUARD, {"session_id": SESSION, "prompt": "e agora?"}).stdout
        self.assertIn("Teoria dos Grafos", injected)

        # 6. The student demonstrates something.
        cli("concepts-set", "--concept", "BFS", "--domain", "grafos",
            "--level", "known", "--evidence", "explicou a fila sozinho")

        # 7. The session ends.
        hook(SAVE, {"session_id": SESSION, "reason": "exit"})

        # 8. State reflects the session, and the hook is silent again.
        status = json.loads(cli("status").stdout)
        self.assertEqual(status["known"], ["BFS"])
        self.assertEqual(len(list((Path(os.environ["ORACLE_HOME"]) / "sessions").glob("*.md"))), 1)
        self.assertEqual(hook(GUARD, {"session_id": SESSION, "prompt": "outra coisa"}).stdout, "")

        # 9. The next plan can now skip what was demonstrated.
        self.assertIn("BFS", json.loads(cli("concepts-list", "--level", "known").stdout)
                      ["concepts"][0]["concept"])


if __name__ == "__main__":
    unittest.main()
