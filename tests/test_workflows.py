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
        # the token is an environment secret, so the job needs the environment
        self.assertIn("environment: ${{ inputs.environment }}", job.split("steps:")[0])

    def test_missing_token_guard(self):
        text = RELEASE.read_text()
        job = text[text.index("  publish-appstore:"):]
        guard = re.search(r'if \[ -z "\$APPSTORE_TOKEN" \]; then\n(.*?)\n {10}fi\n', job, re.S).group(1)
        self.assertIn('if [ "$NIGHTLY" = true ]', guard)
        self.assertIn("::warning::", guard)
        self.assertIn("::error::", guard)
        self.assertLess(guard.index("::warning::"), guard.index("exit 0"))
        self.assertLess(guard.index("exit 0"), guard.index("::error::"))
        self.assertLess(guard.index("::error::"), guard.rindex("exit 1"))

    def test_missing_token_behaviour(self):
        text = RELEASE.read_text()
        job = text[text.index("  publish-appstore:"):]
        guard = re.search(r'(if \[ -z "\$APPSTORE_TOKEN" \]; then\n.*?\n {10}fi)\n', job, re.S).group(1)
        guard = guard.replace("${{ inputs.environment }}", "release")
        for nightly, code in (("true", 0), ("false", 1)):
            res = subprocess.run(["bash", "-c", guard],
                                 env={"APPSTORE_TOKEN": "", "NIGHTLY": nightly, "PATH": os.environ["PATH"]},
                                 capture_output=True, text=True)
            self.assertEqual(res.returncode, code, res.stdout)


ACTION = ROOT / ".github/actions/nextcloud-server/action.yml"
CI = ROOT / ".github/workflows/ci.yml"


class BuildServerTest(unittest.TestCase):
    def test_build_server_is_opt_in_everywhere(self):
        for path in (WORKFLOW, CI, RELEASE):
            text = path.read_text()
            m = re.search(r"\n      build-server:\n(.*?)\n      [a-z-]+:\n", text, re.S)
            self.assertIsNotNone(m, path.name)
            self.assertIn("default: false", m.group(1), path.name)

    def test_build_server_is_passed_down(self):
        for path in (CI, RELEASE):
            text = path.read_text()
            for name in ("build-server", "signing-server-repository", "signing-server-ref"):
                self.assertIn("%s: ${{ inputs.%s }}" % (name, name), text, path.name)

    def test_build_runs_in_the_mounted_app(self):
        for path in (WORKFLOW, CI):
            text = path.read_text()
            self.assertIn(
                "working-directory: ${{ inputs.build-server && steps.server.outputs.app-dir || github.workspace }}", text)
            self.assertIn("if: inputs.build-server", text)

    def test_signing_reuses_the_server(self):
        text = WORKFLOW.read_text()
        self.assertIn("if: inputs.build-server || (inputs.release && inputs.sign)", text)
        self.assertNotIn("/.signing-server", text)
        self.assertIn("steps.server.outputs.occ", text)

    def test_action_mounts_instead_of_symlinking(self):
        # console-setup.php uses realpath(), which resolves symlinks
        text = ACTION.read_text()
        self.assertIn("mount --bind", text)
        self.assertNotIn("ln -s", text)
        self.assertIn('"$server/apps/$app_id"', text)

    def test_nested_references_use_the_tag(self):
        for path in (WORKFLOW, CI, RELEASE):
            for ref in re.findall(r"uses: rotdrop/nextcloud-app-build-system/\S+", path.read_text()):
                self.assertTrue(ref.endswith("@v1"), ref)

    def test_composer_is_authenticated_for_every_step(self):
        auth = "COMPOSER_AUTH: '{\"github-oauth\":{\"github.com\":\"${{ github.token }}\"}}'"
        for path, job in ((WORKFLOW, "build"), (CI, "realclean")):
            text = path.read_text()
            m = re.search(r"\n  %s:\n(.*?)\n    steps:" % job, text, re.S)
            self.assertIsNotNone(m, path.name)
            self.assertIn("env:\n      " + auth, m.group(1), path.name)
            self.assertEqual(text.count("COMPOSER_AUTH"), 1, path.name)

    def test_github_api_for_composer_is_opt_out(self):
        for path in (WORKFLOW, CI, RELEASE):
            text = path.read_text()
            m = re.search(r"\n      composer-use-github-api:\n(.*?)\n      [a-z-]+:\n", text, re.S)
            self.assertIsNotNone(m, path.name)
            self.assertIn("default: true", m.group(1), path.name)
        for path in (CI, RELEASE):
            self.assertIn("composer-use-github-api: ${{ inputs.composer-use-github-api }}", path.read_text())
        for path in (WORKFLOW, CI):
            self.assertIn("composer config --global use-github-api false", path.read_text())


if __name__ == "__main__":
    unittest.main()
