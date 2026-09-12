import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = str(ROOT / "lib" / "oracle_store.py")
SKILL = ROOT / "skills" / "oracle-plan" / "SKILL.md"


def run(*args, stdin=None):
    return subprocess.run(
        [sys.executable, CLI, *args], capture_output=True, text=True, input=stdin, check=False
    )


class TestPlanSkillContent(unittest.TestCase):
    def setUp(self):
        text = SKILL.read_text(encoding="utf-8")
        # Normalize whitespace: collapse runs of whitespace (including newlines) to single space
        import re
        self.text = re.sub(r'\s+', ' ', text)

    def test_reads_concepts_before_planning(self):
        self.assertIn("concepts-list", self.text)

    def test_requires_calibration_rather_than_trusting_the_file(self):
        self.assertIn("calibr", self.text.lower())

    def test_documents_skipped_reason(self):
        self.assertIn("skipped_reason", self.text)

    def test_does_not_branch_on_the_absent_initialized_field(self):
        """Finding 2: `concepts-list` never emits `initialized` (only
        `status` does), so a literal-minded model told to stop when
        `initialized` is absent would abort on every run. The skill must not
        reference that field at all."""
        self.assertNotIn("initialized", self.text)

    def test_still_stops_on_exit_code_2(self):
        """The exit-code-2 branch must remain: concepts-list is in
        NEEDS_STATE, so it already exits 2 when state is missing."""
        self.assertIn("código 2", self.text)


class TestPlanRoundTrip(unittest.TestCase):
    """The exact JSON shape the skill is told to emit must survive plan-save."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["ORACLE_HOME"] = self._tmp.name + "/.oracle"
        run("init", "--mode", "plain")
        self.plan = {
            "topic": "Teoria dos Grafos",
            "goal": "resolver as questões de grafos da prova de 01/10",
            "deadline": "2026-10-01",
            "status": "active",
            "milestones": [
                {
                    "title": "Representação: lista vs matriz de adjacência",
                    "status": "todo",
                    "skipped_reason": None,
                },
                {
                    "title": "BFS",
                    "status": "done",
                    "skipped_reason": "já domina: confirmado na calibração",
                },
            ],
        }

    def tearDown(self):
        os.environ.pop("ORACLE_HOME", None)
        self._tmp.cleanup()

    def test_saves_and_reloads_unchanged(self):
        saved = json.loads(run("plan-save", stdin=json.dumps(self.plan)).stdout)
        reloaded = json.loads(run("plan-show", "--slug", saved["slug"]).stdout)["plan"]
        self.assertEqual(reloaded["milestones"], self.plan["milestones"])
        self.assertEqual(reloaded["deadline"], "2026-10-01")

    def test_skipped_milestones_carry_their_reason(self):
        saved = json.loads(run("plan-save", stdin=json.dumps(self.plan)).stdout)
        skipped = [
            m for m in saved["plan"]["milestones"] if m["skipped_reason"] is not None
        ]
        self.assertEqual(len(skipped), 1)
        self.assertIn("já domina", skipped[0]["skipped_reason"])

    def test_plan_becomes_the_active_plan(self):
        run("plan-save", stdin=json.dumps(self.plan))
        active = json.loads(run("plan-show").stdout)["plan"]
        self.assertEqual(active["topic"], "Teoria dos Grafos")


if __name__ == "__main__":
    unittest.main()
