import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github/workflows/build-appstore.yml"


def select_archive_script():
    text = WORKFLOW.read_text()
    match = re.search(r"- name: Sanity-check the archive\n.*?run: \|\n(.*?)\n\n", text, re.S)
    assert match, "step not found"
    lines = [line[10:] for line in match.group(1).splitlines()]
    # keep only the archive selection, the JS check needs a real tarball
    end = next(i for i, line in enumerate(lines) if line.startswith('echo "ARCHIVE='))
    return "\n".join(lines[:end + 1])


class SelectArchiveTest(unittest.TestCase):
    def run_step(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp, "build/artifacts/appstore")
            directory.mkdir(parents=True)
            for name in files:
                (directory / name).write_text("x")
            env_file = Path(tmp, "env")
            result = subprocess.run(
                ["bash", "-e", "-c", select_archive_script()], cwd=tmp, text=True,
                capture_output=True,
                env={**os.environ, "APP_ID": "app", "APP_VERSION": "1.0.0-rc1",
                     "GITHUB_ENV": str(env_file)},
            )
            written = env_file.read_text() if env_file.exists() else ""
            return result, written

    def test_signed_build_selects_only_the_archive(self):
        result, written = self.run_step(["app-1.0.0-rc1.tar.gz", "app-1.0.0-rc1.tar.gz.sig"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(written, "ARCHIVE=build/artifacts/appstore/app-1.0.0-rc1.tar.gz\n")

    def test_unsigned_build(self):
        result, written = self.run_step(["app-1.0.0-rc1.tar.gz"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("tar.gz\n", written)

    def test_no_archive_fails(self):
        result, _ = self.run_step(["app-1.0.0-rc1.tar.gz.sig"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exactly one archive", result.stdout + result.stderr)

    def test_two_archives_fail(self):
        result, _ = self.run_step(["app-1.0.0-rc1.tar.gz", "app-1.0.0-rc1.tar.xz"])
        self.assertNotEqual(result.returncode, 0)


RELEASE = ROOT / ".github/workflows/release.yml"


def appstore_payload(prerelease):
    text = RELEASE.read_text()
    match = re.search(r"jq -n (.*?) \\\n\s+'(.*?)' \\\n", text, re.S)
    assert match, "jq call not found"
    arguments = match.group(1).replace('$BASE_URL/$(basename "$archive")', "http://x/a.tar.gz")
    arguments = arguments.replace('"$signature"', "SIG").replace('"$NIGHTLY"', prerelease)
    result = subprocess.run(["bash", "-c", f"jq -cn {arguments} '{match.group(2)}'"],
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


class AppstoreUploadTest(unittest.TestCase):
    def test_prerelease_is_nightly(self):
        self.assertIn('"nightly":true', appstore_payload("true"))

    def test_stable_release_is_not_nightly(self):
        self.assertIn('"nightly":false', appstore_payload("false"))

    def test_upload_job_conditions(self):
        text = RELEASE.read_text()
        job = text[text.index("  publish-appstore:"):]
        condition = re.search(r"if: (.*)", job).group(1)
        self.assertEqual(condition, "inputs.upload-to-appstore && inputs.sign")


if __name__ == "__main__":
    unittest.main()
