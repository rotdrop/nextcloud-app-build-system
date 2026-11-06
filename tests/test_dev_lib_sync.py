import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@e", GIT_COMMITTER_NAME="t",
           GIT_COMMITTER_EMAIL="t@e", GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null",
           GIT_ALLOW_PROTOCOL="file")


def git(cwd, *args, check=True):
    return subprocess.run(["git", "-c", "protocol.file.allow=always", "-C", str(cwd), *args],
                          capture_output=True, text=True, check=check, env=ENV)


class DevLibSyncReleaseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        # "library" remote: a work clone with commits and a bare origin
        self.lib_origin = t / "lib.git"
        git(t, "init", "-q", "--bare", "-b", "main", str(self.lib_origin))
        self.lib_work = t / "libwork"
        git(t, "clone", "-q", str(self.lib_origin), str(self.lib_work))
        self.c1 = self.lib_commit("one")
        git(self.lib_work, "tag", "-a", "v1", "-m", "v1", self.c1)
        self.c2 = self.lib_commit("two")  # main is ahead of v1
        git(self.lib_work, "push", "-q", "origin", "main", "--tags")
        # app remote and clone with the submodule
        self.app_origin = t / "app.git"
        git(t, "init", "-q", "--bare", "-b", "main", str(self.app_origin))
        self.app = t / "app"
        git(t, "clone", "-q", str(self.app_origin), str(self.app))
        (self.app / "f").write_text("x")
        git(self.app, "add", "f")
        git(self.app, "commit", "-q", "-m", "init")
        git(self.app, "submodule", "add", "-q", str(self.lib_origin), "dev-scripts/lib")
        git(self.app / "dev-scripts/lib", "checkout", "-q", "--detach", self.c1)
        git(self.app, "add", "-A")
        git(self.app, "commit", "-q", "-m", "submodule")
        git(self.app, "push", "-q", "origin", "main")
        (self.app / "Makefile").write_text(
            "ABSSRCDIR = %s\nDEV_LIB_DIR = %s/dev-scripts/lib\n"
            "include %s/makefile/dev-lib-sync.mk\n" % (self.app, self.app, ROOT))

    def tearDown(self):
        self.tmp.cleanup()

    def lib_commit(self, name):
        (self.lib_work / name).write_text(name)
        git(self.lib_work, "add", name)
        git(self.lib_work, "commit", "-q", "-m", name)
        return git(self.lib_work, "rev-parse", "HEAD").stdout.strip()

    def run_release(self, *args):
        return subprocess.run(["make", "-s", "-C", str(self.app), "dev-lib-sync-release", *args],
                              capture_output=True, text=True, env=ENV)

    def head_lib(self):
        return git(self.app / "dev-scripts/lib", "rev-parse", "HEAD").stdout.strip()

    def test_moves_to_the_tag_commit_not_main(self):
        res = self.run_release("DEV_LIB_SYNC_TAG=v1")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("already at tag v1", res.stdout)
        self.assertEqual(self.head_lib(), self.c1)

    def test_follows_a_force_moved_annotated_tag_and_pushes(self):
        git(self.lib_work, "tag", "-f", "-a", "v1", "-m", "moved", self.c2)
        git(self.lib_work, "push", "-q", "--force", "origin", "--tags")
        res = self.run_release()
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.head_lib(), self.c2)
        msg = git(self.app, "log", "-1", "--format=%B").stdout
        self.assertIn("Update dev-scripts/lib to v1 (%s)" % self.c2[:7], msg)
        self.assertIn("Co-authored-by: Copilot App", msg)
        pushed = subprocess.run(["git", "--git-dir", str(self.app_origin), "rev-parse", "refs/heads/main"],
                                capture_output=True, text=True, env=ENV).stdout
        self.assertEqual(pushed, git(self.app, "rev-parse", "HEAD").stdout)
        self.assertEqual(git(self.app, "status", "--porcelain", "--untracked-files=no").stdout, "")

    def test_other_tag(self):
        git(self.lib_work, "tag", "-a", "v2", "-m", "v2", self.c2)
        git(self.lib_work, "push", "-q", "--tags")
        res = self.run_release("DEV_LIB_SYNC_TAG=v2")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.head_lib(), self.c2)

    def test_missing_tag(self):
        res = self.run_release("DEV_LIB_SYNC_TAG=v9")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("tag v9 not found", res.stderr)

    def test_refuses_detached_app_head(self):
        git(self.app, "checkout", "-q", "--detach")
        res = self.run_release()
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("detached HEAD", res.stderr)

    def test_refuses_dirty_submodule(self):
        (self.app / "dev-scripts/lib/dirty").write_text("x")
        git(self.app / "dev-scripts/lib", "add", "dirty")
        res = self.run_release()
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("uncommitted changes", res.stderr)

    def test_refuses_local_submodule_commits(self):
        lib = self.app / "dev-scripts/lib"
        (lib / "local").write_text("x")
        git(lib, "add", "local")
        git(lib, "commit", "-q", "-m", "local")
        res = self.run_release()
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("local commits not in tag v1", res.stderr)


if __name__ == "__main__":
    unittest.main()
