import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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
