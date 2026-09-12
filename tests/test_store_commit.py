import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import oracle_store as store


def git(*args, cwd):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )


class CommitTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["ORACLE_HOME"] = self._tmp.name + "/.oracle"
        # Keep the test independent of the developer's global git identity.
        os.environ["GIT_AUTHOR_NAME"] = "Oracle Test"
        os.environ["GIT_AUTHOR_EMAIL"] = "test@example.invalid"
        os.environ["GIT_COMMITTER_NAME"] = "Oracle Test"
        os.environ["GIT_COMMITTER_EMAIL"] = "test@example.invalid"

    def tearDown(self):
        for var in (
            "ORACLE_HOME",
            "GIT_AUTHOR_NAME",
            "GIT_AUTHOR_EMAIL",
            "GIT_COMMITTER_NAME",
            "GIT_COMMITTER_EMAIL",
        ):
            os.environ.pop(var, None)
        self._tmp.cleanup()


class TestPlainMode(CommitTestCase):
    def test_commit_is_a_noop(self):
        store.init("plain")
        result = store.commit("estudou grafos")
        self.assertEqual(result["mode"], "plain")
        self.assertFalse(result["committed"])
        self.assertFalse(result["pushed"])
        self.assertIsNone(result["warning"])

    def test_no_git_repo_is_created(self):
        store.init("plain")
        store.commit("estudou grafos")
        self.assertFalse((store.home() / ".git").exists())


class TestGitMode(CommitTestCase):
    def test_init_creates_repo(self):
        store.init("git")
        self.assertTrue((store.home() / ".git").is_dir())

    def test_commit_records_changes(self):
        store.init("git")
        store.write_json("concepts.json", [{"concept": "grafos", "level": "shaky"}])
        result = store.commit("estudou grafos")
        self.assertTrue(result["committed"])
        self.assertFalse(result["pushed"])
        log = git("log", "--oneline", cwd=store.home()).stdout
        self.assertIn("estudou grafos", log)

    def test_commit_without_changes_is_not_an_error(self):
        store.init("git")
        store.commit("primeira")
        result = store.commit("nada mudou")
        self.assertFalse(result["committed"])
        self.assertIsNone(result["warning"])

    def test_failed_git_add_warns_and_does_not_claim_committed(self):
        """Finding 7: `git add -A`'s return code was unchecked in commit(),
        so a failing add fell through to `status --porcelain`, which (with
        nothing staged) can read as if nothing changed — the student is told
        committed: false, warning: None, indistinguishable from "nothing to
        commit" when in fact `git add` blew up.

        This patches store._git so "add" reports failure and asserts (a) the
        commit is never claimed and a warning is surfaced, and (b) commit()
        bails out on the failed add instead of still probing `status` and
        attempting `commit` behind the student's back.
        """
        store.init("git")
        store.write_json("concepts.json", [{"concept": "x"}])

        original_git = store._git
        calls = []

        def fake_git(*args, **kwargs):
            calls.append(args)
            if args and args[0] == "add":
                return subprocess.CompletedProcess(
                    ("git", *args), 1, stdout="", stderr="fatal: simulated add failure"
                )
            return original_git(*args, **kwargs)

        with mock.patch.object(store, "_git", side_effect=fake_git):
            result = store.commit("estudou x")

        self.assertFalse(result["committed"])
        self.assertIsNotNone(result["warning"])
        self.assertNotIn(("status", "--porcelain"), calls)


class TestGitRemoteMode(CommitTestCase):
    def _bare_remote(self):
        remote = Path(self._tmp.name) / "remote.git"
        subprocess.run(
            ["git", "init", "--bare", "-q", str(remote)], check=True, capture_output=True
        )
        return remote

    def test_commit_pushes_to_remote(self):
        store.init("git-remote")
        remote = self._bare_remote()
        git("remote", "add", "origin", str(remote), cwd=store.home())
        store.write_json("concepts.json", [{"concept": "ponteiros"}])
        result = store.commit("estudou ponteiros")
        self.assertTrue(result["committed"])
        self.assertTrue(result["pushed"])
        self.assertIsNone(result["warning"])
        self.assertIn("estudou ponteiros", git("log", "--oneline", cwd=remote).stdout)

    def test_failed_push_keeps_local_commit_and_warns(self):
        store.init("git-remote")
        git("remote", "add", "origin", "/nonexistent/path/to.git", cwd=store.home())
        store.write_json("concepts.json", [{"concept": "offline"}])
        result = store.commit("estudou offline")
        self.assertTrue(result["committed"])
        self.assertFalse(result["pushed"])
        self.assertIsNotNone(result["warning"])
        self.assertIn("estudou offline", git("log", "--oneline", cwd=store.home()).stdout)

    def test_missing_remote_warns_but_commits(self):
        store.init("git-remote")
        store.write_json("concepts.json", [{"concept": "sem remoto"}])
        result = store.commit("sem remoto configurado")
        self.assertTrue(result["committed"])
        self.assertFalse(result["pushed"])
        self.assertIsNotNone(result["warning"])


if __name__ == "__main__":
    unittest.main()
