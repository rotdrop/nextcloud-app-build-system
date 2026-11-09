import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github/workflows/build-appstore.yml"


def step_script(name):
    text = WORKFLOW.read_text()
    match = re.search(
        rf"      - name: {re.escape(name)}\n(.*?)(?=\n      - name: |\n  [a-z-]+:|\Z)",
        text, re.S)
    assert match, f"{name} step not found"
    run = re.search(r"        run: \|\n(.*)", match.group(1), re.S)
    assert run, f"{name} run script not found"
    return "\n".join(line[10:] for line in run.group(1).rstrip().splitlines())


def select_archive_script():
    return step_script("Sanity-check the archive")


class SelectArchiveTest(unittest.TestCase):
    source_sha = "0123456789abcdef0123456789abcdef01234567"

    def run_step(self, files, release=False):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp, "build/artifacts/appstore")
            directory.mkdir(parents=True)
            for name in files:
                (directory / name).write_text("x")
            env_file = Path(tmp, "env")
            output_file = Path(tmp, "output")
            result = subprocess.run(
                ["bash", "-e", "-c", select_archive_script()], cwd=tmp, text=True,
                capture_output=True,
                env={**os.environ, "APP_ID": "app", "APP_VERSION": "1.0.0-rc1",
                     "APP_ARTIFACT": f"app-1.0.0-rc1{'-ci-' + self.source_sha if not release else ''}",
                     "IS_RELEASE": str(release).lower(), "CHECK_JS": "false",
                     "GITHUB_ENV": str(env_file), "GITHUB_OUTPUT": str(output_file)},
            )
            written = env_file.read_text() if env_file.exists() else ""
            outputs = output_file.read_text() if output_file.exists() else ""
            return result, written, outputs

    def test_signed_build_selects_only_the_archive(self):
        result, written, outputs = self.run_step(
            ["app-1.0.0-rc1.tar.gz", "app-1.0.0-rc1.tar.gz.sig"], release=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(written, "ARCHIVE=build/artifacts/appstore/app-1.0.0-rc1.tar.gz\n")
        self.assertEqual(outputs, "archive-filename=app-1.0.0-rc1.tar.gz\n")

    def test_unsigned_build(self):
        result, written, outputs = self.run_step(["app-1.0.0-rc1.tar.gz"], release=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("tar.gz\n", written)
        self.assertEqual(outputs, "archive-filename=app-1.0.0-rc1.tar.gz\n")

    def test_ci_archive_uses_full_checkout_sha(self):
        result, written, outputs = self.run_step(["app-1.0.0-rc1.tar.gz"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(
            written,
            rf"^ARCHIVE=.*/build/artifacts/appstore/app-1.0.0-rc1-ci-{self.source_sha}\.tar\.gz\n$",
        )
        self.assertEqual(
            outputs,
            f"archive-filename=app-1.0.0-rc1-ci-{self.source_sha}.tar.gz\n",
        )

    def test_ci_archive_preserves_compression_extension(self):
        result, _, outputs = self.run_step(["app-1.0.0-rc1.tar.xz"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            outputs, f"archive-filename=app-1.0.0-rc1-ci-{self.source_sha}.tar.xz\n")

    def test_no_archive_fails(self):
        result, _, _ = self.run_step(["app-1.0.0-rc1.tar.gz.sig"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exactly one archive", result.stdout + result.stderr)

    def test_two_archives_fail(self):
        result, _, _ = self.run_step(["app-1.0.0-rc1.tar.gz", "app-1.0.0-rc1.tar.xz"])
        self.assertNotEqual(result.returncode, 0)


class BuildMetadataTest(unittest.TestCase):
    source_sha = "0123456789abcdef0123456789abcdef01234567"

    def run_step(self, release):
        with tempfile.TemporaryDirectory() as tmp:
            appinfo = Path(tmp, "appinfo")
            appinfo.mkdir()
            appinfo.joinpath("info.xml").write_text(
                "<info><id>app</id><version>1.0.0</version></info>")
            output_file = Path(tmp, "output")
            result = subprocess.run(
                ["bash", "-e", "-c", step_script("Read app id and version")],
                cwd=tmp, text=True, capture_output=True,
                env={
                    **os.environ,
                    "SOURCE_SHA": self.source_sha,
                    "IS_RELEASE": str(release).lower(),
                    "GITHUB_OUTPUT": str(output_file),
                },
            )
            return result, output_file.read_text() if output_file.exists() else ""

    def test_release_artifact_keeps_version_only_name(self):
        result, outputs = self.run_step(release=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("artifact=app-1.0.0\n", outputs)

    def test_ci_artifact_includes_full_source_sha(self):
        result, outputs = self.run_step(release=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"artifact=app-1.0.0-ci-{self.source_sha}\n", outputs)


class ArchiveProvenanceTest(unittest.TestCase):
    def test_checksum_manifest_and_summary_are_collected(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp, "app-1.0.0-ci-0123456789abcdef.tar.gz")
            archive.write_text("archive")
            summary = Path(tmp, "summary")
            result = subprocess.run(
                ["bash", "-e", "-c", step_script("Collect release files")],
                cwd=tmp, text=True, capture_output=True,
                env={
                    **os.environ,
                    "ARCHIVE": str(archive),
                    "APP_ID": "app",
                    "APP_VERSION": "1.0.0",
                    "APP_ARTIFACT": archive.name.removesuffix(".tar.gz"),
                    "SOURCE_SHA": "0123456789abcdef0123456789abcdef01234567",
                    "SOURCE_REF": "refs/pull/42/merge",
                    "RUNNER_TEMP": tmp,
                    "GITHUB_SERVER_URL": "https://github.com",
                    "GITHUB_REPOSITORY": "owner/repo",
                    "GITHUB_RUN_ID": "123",
                    "GITHUB_STEP_SUMMARY": str(summary),
                },
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            out = Path(tmp, "out")
            self.assertTrue((out / f"{archive.name}.sha256").is_file())
            provenance = (out / "provenance.json").read_text()
            self.assertIn('"source_sha": "0123456789abcdef0123456789abcdef01234567"', provenance)
            self.assertIn('"source_ref": "refs/pull/42/merge"', provenance)
            self.assertIn('"archive_filename": "app-1.0.0-ci-0123456789abcdef.tar.gz"', provenance)
            self.assertIn("SHA-256:", summary.read_text())


class WorkflowOutputsTest(unittest.TestCase):
    def test_build_uses_checkout_sha_and_exposes_provenance(self):
        text = WORKFLOW.read_text()
        self.assertIn('echo "sha=$(git rev-parse HEAD)" >> "$GITHUB_OUTPUT"', text)
        self.assertIn('echo "ref=$GITHUB_REF" >> "$GITHUB_OUTPUT"', text)
        for output in ("source-sha", "source-ref", "artifact", "archive-filename"):
            self.assertRegex(text, rf"(?m)^      {re.escape(output)}:")
            self.assertIn(f"value: ${{{{ jobs.build.outputs.{output} }}}}", text)

    def test_ci_forwards_archive_filename_output(self):
        text = CI.read_text()
        self.assertIn("archive-filename:", text)
        self.assertIn("value: ${{ jobs.build.outputs.archive-filename }}", text)

    def test_release_appstore_uses_exact_archive_filename(self):
        text = RELEASE.read_text()
        self.assertIn("ARCHIVE_FILENAME: ${{ needs.build.outputs.archive-filename }}", text)
        self.assertIn('archive="assets/$ARCHIVE_FILENAME"', text)


RELEASE = ROOT / ".github/workflows/release.yml"
README = ROOT / "README.md"


class ReleasePermissionsDocumentationTest(unittest.TestCase):
    def test_release_workflow_header_documents_caller_permission(self):
        header = RELEASE.read_text().split("name: Release", 1)[0]
        self.assertIn("permissions: contents: write", header)
        self.assertIn("cannot elevate permissions", header)

    def test_readme_release_caller_grants_and_explains_write_permission(self):
        readme = " ".join(README.read_text().split())
        self.assertIn("permissions: contents: write", readme)
        self.assertIn("called workflow cannot receive more permissions than its caller", readme)
        self.assertIn("without a useful job log", readme)


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


class EslintTest(unittest.TestCase):
    def test_install_uses_locked_dependencies(self):
        job = CI.read_text().split("  eslint:\n", 1)[1].split("  php-lint:\n", 1)[0]
        self.assertIn("npm ci\n", job)
        self.assertNotIn("npm install", job)
        self.assertLess(job.index("npm ci\n"), job.index("npm run lint"))


class PythonSetupTest(unittest.TestCase):
    def test_python_is_opt_in_everywhere(self):
        for path in (WORKFLOW, CI, RELEASE):
            with self.subTest(workflow=path.name):
                match = re.search(
                    r"\n      python-version:\n(.*?)\n      [a-z-]+:\n",
                    path.read_text(), re.S)
                self.assertIsNotNone(match)
                self.assertIn("type: string", match.group(1))
                self.assertIn("default: ''", match.group(1))
                self.assertNotIn("required: true", match.group(1))

    def test_python_version_is_forwarded_to_archive_build(self):
        for path in (CI, RELEASE):
            with self.subTest(workflow=path.name):
                job = path.read_text().split("\n  build:\n", 1)[1].split("\n  publish:", 1)[0]
                self.assertIn("uses: rotdrop/nextcloud-app-build-system/.github/workflows/build-appstore.yml@v1", job)
                self.assertIn("      python-version: ${{ inputs.python-version }}", job)

    def test_python_setup_is_conditional_and_precedes_build(self):
        for path, job_name, build_command in (
                (CI, "realclean", "make build"),
                (WORKFLOW, "build", "make appstore")):
            with self.subTest(workflow=path.name):
                text = path.read_text()
                job = text.split(f"\n  {job_name}:\n", 1)[1].split("\n  build:\n", 1)[0]
                steps = re.split(r"\n      - ", job)[1:]
                setup = [step for step in steps if "uses: actions/setup-python@" in step]
                self.assertEqual(len(setup), 1)
                self.assertIn("if: inputs.python-version != ''", setup[0])
                self.assertIn("python-version: ${{ inputs.python-version }}", setup[0])
                self.assertLess(job.index(setup[0]), job.index(build_command))
                self.assertEqual(text.count("uses: actions/setup-python@"), 1)


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
