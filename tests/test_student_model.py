import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import oracle_store as store


class ModelTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["ORACLE_HOME"] = self._tmp.name + "/.oracle"
        store.init("plain")

    def tearDown(self):
        os.environ.pop("ORACLE_HOME", None)
        self._tmp.cleanup()


class TestSlugify(ModelTestCase):
    def test_lowercases_and_hyphenates(self):
        self.assertEqual(store.slugify("Teoria dos Grafos"), "teoria-dos-grafos")

    def test_strips_accents_and_punctuation(self):
        self.assertEqual(store.slugify("Cálculo II: derivadas!"), "calculo-ii-derivadas")

    def test_collapses_repeated_separators(self):
        self.assertEqual(store.slugify("a   --  b"), "a-b")

    def test_empty_input_yields_placeholder(self):
        self.assertEqual(store.slugify("!!!"), "sem-titulo")


class TestConcepts(ModelTestCase):
    def test_starts_empty(self):
        self.assertEqual(store.list_concepts(), [])
        self.assertIsNone(store.concept_level("grafos"))

    def test_upsert_creates_record(self):
        record = store.upsert_concept("grafos", "matemática", "shaky", "travou em BFS")
        self.assertEqual(record["concept"], "grafos")
        self.assertEqual(record["domain"], "matemática")
        self.assertEqual(record["level"], "shaky")
        self.assertEqual(record["evidence"], "travou em BFS")
        self.assertIn("updated_at", record)
        self.assertEqual(len(store.list_concepts()), 1)

    def test_upsert_updates_in_place(self):
        store.upsert_concept("grafos", "matemática", "shaky", "travou em BFS")
        store.upsert_concept("grafos", "matemática", "known", "explicou BFS sozinho")
        self.assertEqual(len(store.list_concepts()), 1)
        self.assertEqual(store.concept_level("grafos"), "known")
        self.assertEqual(store.list_concepts()[0]["evidence"], "explicou BFS sozinho")

    def test_lookup_is_case_insensitive(self):
        store.upsert_concept("Grafos", "matemática", "known", "demonstrou")
        self.assertEqual(store.concept_level("grafos"), "known")

    def test_rejects_unknown_level(self):
        with self.assertRaises(ValueError):
            store.upsert_concept("grafos", "matemática", "mastered", "…")

    def test_known_concepts_filters(self):
        store.upsert_concept("grafos", "mat", "known", "demonstrou")
        store.upsert_concept("recursão", "prog", "gap", "nunca viu")
        store.upsert_concept("pilha", "prog", "shaky", "confunde com fila")
        self.assertEqual(store.known_concepts(), ["grafos"])

    def test_known_without_evidence_is_rejected(self):
        """Finding 3: `known` is enforced only by prose without this check —
        a level of 'known' with empty (or whitespace-only) evidence must be
        rejected, or concepts.json becomes optimistic about what the student
        has actually demonstrated."""
        with self.assertRaises(ValueError):
            store.upsert_concept("grafos", "matemática", "known", "")
        with self.assertRaises(ValueError):
            store.upsert_concept("grafos", "matemática", "known", "   ")

    def test_known_with_evidence_is_accepted(self):
        record = store.upsert_concept("grafos", "matemática", "known", "explicou BFS sozinho")
        self.assertEqual(record["level"], "known")

    def test_shaky_and_gap_allow_empty_evidence(self):
        shaky = store.upsert_concept("grafos", "matemática", "shaky", "")
        self.assertEqual(shaky["level"], "shaky")
        gap = store.upsert_concept("recursão", "prog", "gap", "")
        self.assertEqual(gap["level"], "gap")


class TestPlans(ModelTestCase):
    def _plan(self, topic="Teoria dos Grafos", status="active"):
        return {
            "topic": topic,
            "goal": "resolver questões de prova",
            "deadline": "2026-10-01",
            "status": status,
            "milestones": [
                {"title": "representação", "status": "todo", "skipped_reason": None},
                {"title": "BFS", "status": "done", "skipped_reason": "já domina: BFS"},
            ],
        }

    def test_save_returns_slug_and_fills_defaults(self):
        slug = store.save_plan(self._plan())
        self.assertEqual(slug, "teoria-dos-grafos")
        saved = store.load_plan(slug)
        self.assertEqual(saved["id"], slug)
        self.assertEqual(saved["sessions"], [])
        self.assertIn("created_at", saved)

    def test_save_writes_one_file_per_plan(self):
        store.save_plan(self._plan())
        self.assertTrue((store.home() / "plans" / "teoria-dos-grafos.json").exists())

    def test_load_missing_returns_none(self):
        self.assertIsNone(store.load_plan("nao-existe"))

    def test_save_requires_topic(self):
        with self.assertRaises(ValueError):
            store.save_plan({"goal": "sem tópico"})

    def test_resave_preserves_created_at_and_sessions(self):
        slug = store.save_plan(self._plan())
        first = store.load_plan(slug)
        updated = dict(first)
        updated["sessions"] = ["2026-09-10-teoria-dos-grafos"]
        store.save_plan(updated)
        again = store.load_plan(slug)
        self.assertEqual(again["created_at"], first["created_at"])
        self.assertEqual(again["sessions"], ["2026-09-10-teoria-dos-grafos"])

    def test_list_plans_filters_by_status(self):
        store.save_plan(self._plan("Grafos", "active"))
        store.save_plan(self._plan("Cálculo", "done"))
        self.assertEqual(len(store.list_plans()), 2)
        self.assertEqual(len(store.list_plans(status="done")), 1)

    def test_active_plan_returns_the_active_one(self):
        store.save_plan(self._plan("Cálculo", "done"))
        store.save_plan(self._plan("Grafos", "active"))
        self.assertEqual(store.active_plan()["topic"], "Grafos")

    def test_active_plan_is_none_when_nothing_active(self):
        store.save_plan(self._plan("Cálculo", "done"))
        self.assertIsNone(store.active_plan())


if __name__ == "__main__":
    unittest.main()
