import os

os.environ["LC_ALL"] = "C"
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


FRAGMENT = Path(__file__).resolve().parents[1] / "makefile" / "npm.mk"


class NpmMakefileTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.app = Path(self.temporary.name)
        for name in ("package.json", "vite.config.ts", "eslint.config.mjs",
                     "source.js", "legacy.js"):
            self.write(name, "")
        self.write("package-lock.json", "")
        (self.app / "node_modules").mkdir()
        self.write("build-flavour", "build\n")
        self.write(
            "npm",
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" >> npm.log\n"
            "case \"$1\" in\n"
            "  ci) test -z \"$FAIL_CI\" || exit 24; mkdir -p node_modules ;;\n"
            "  update) test \"$2\" = --package-lock-only || exit 98 ;;\n"
            "  run) mkdir -p js css; echo built > \"${OUTPUT:-js/asset-meta.json}\"; "
            "echo built > css/app.css; test -z \"$FAIL_BUILD\" || exit 23 ;;\n"
            "  *) exit 99 ;;\n"
            "esac\n",
        )
        (self.app / "npm").chmod(0o755)
        self.configure()

    def write(self, name, content):
        path = self.app / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def configure(self, variables="", config="vite.config.ts"):
        self.write(
            "Makefile",
            f"ABSSRCDIR = {self.app}\n"
            "MAKEFILE_DEP = Makefile\n"
            f"NPM = {self.app / 'npm'}\n"
            f"BUNDLER_CONFIG = {config}\n"
            f"{variables}"
            f"include {FRAGMENT}\n"
            "clean:\n"
            "\t@echo clean >> clean.log\n"
            ".PHONY: clean\n"
            "print-deps:\n"
            "\t@echo $(BUNDLER_DEPS)\n"
            "\t@echo $(WEBPACK_DEPS)\n"
            "print-targets:\n"
            "\t@echo $(BUNDLER_TARGETS)\n"
            "\t@echo $(WEBPACK_TARGETS)\n",
        )
        # Keep dependency installation out of these build-only fixtures.
        (self.app / "package-lock.json").touch()
        (self.app / "node_modules").mkdir(exist_ok=True)
        (self.app / "node_modules").touch()

    def make(self, *arguments, success=True, env=None):
        result = subprocess.run(
            ["make", "--no-print-directory", "-C", str(self.app), *arguments],
            text=True, capture_output=True, env=env,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_build_with_neutral_or_legacy_dependencies(self):
        for variable in ("BUNDLER_DEPS", "WEBPACK_DEPS"):
            with self.subTest(variable=variable):
                self.configure(f"{variable} = source.js\n")
                self.write("js/stale.js", "")
                self.write("css/stale.css", "")
                self.make("npm-build")
                self.assertEqual(
                    (self.app / "js/asset-meta.json").read_text(), "built\n"
                )
                self.assertFalse((self.app / "js/stale.js").exists())
                self.assertFalse((self.app / "css/stale.css").exists())
                self.make("npm-build")
                self.assertEqual((self.app / "npm.log").read_text(), "run build\n")
                output = self.app / "js/asset-meta.json"
                older = (self.app / "source.js").stat().st_mtime_ns - 1_000_000_000
                os.utime(output, ns=(older, older))
                self.make("npm-build")
                self.assertEqual(
                    (self.app / "npm.log").read_text(), "run build\nrun build\n"
                )
                (self.app / "npm.log").unlink()
                output.unlink()

    def test_fresh_install_uses_lockfile_and_precedes_parallel_build(self):
        for parallel in (False, True):
            for target in ("npm-dev", "npm-build"):
                with self.subTest(parallel=parallel, target=target):
                    self.configure()
                    shutil.rmtree(self.app / "node_modules")
                    (self.app / "npm.log").unlink(missing_ok=True)
                    lockfile = (self.app / "package-lock.json").read_bytes()

                    arguments = (["-j4"] if parallel else []) + [target]
                    self.make(*arguments)

                    self.assertEqual(
                        (self.app / "npm.log").read_text(),
                        f"ci\nrun {'dev' if target == 'npm-dev' else 'build'}\n",
                    )
                    self.assertEqual(
                        (self.app / "package-lock.json").read_bytes(), lockfile
                    )

    def test_stale_lockfile_triggers_locked_install(self):
        modules = self.app / "node_modules"
        timestamp = modules.stat().st_mtime_ns - 1_000_000_000
        os.utime(modules, ns=(timestamp, timestamp))

        self.make("npm-build")

        self.assertEqual(
            (self.app / "npm.log").read_text(), "ci\nrun build\n"
        )

    def test_missing_lockfile_fails_with_update_instruction(self):
        (self.app / "package-lock.json").unlink()

        result = self.make("npm-build", success=False)

        self.assertIn("run 'make update-package-lock'", result.stderr)
        self.assertFalse((self.app / "npm.log").exists())

    def test_incompatible_lockfile_install_failure_stops_build(self):
        shutil.rmtree(self.app / "node_modules")

        self.make("npm-build", success=False, env={**os.environ, "FAIL_CI": "1"})

        self.assertEqual((self.app / "npm.log").read_text(), "ci\n")

    def test_build_configuration_change_does_not_update_dependencies(self):
        self.write("vite.config.ts", "changed\n")

        self.make("npm-build")

        self.assertEqual((self.app / "npm.log").read_text(), "run build\n")

    def test_update_target_is_explicit_and_does_not_run_during_build(self):
        self.make("npm-build")
        self.assertEqual((self.app / "npm.log").read_text(), "run build\n")

        (self.app / "npm.log").unlink()
        self.make("update-package-lock")

        self.assertEqual(
            (self.app / "npm.log").read_text(), "update --package-lock-only\n"
        )

    def test_parallel_update_finishes_before_install_and_bundle(self):
        shutil.rmtree(self.app / "node_modules")

        self.make("-j4", "update-package-lock", "npm-build")

        self.assertEqual(
            (self.app / "npm.log").read_text(),
            "update --package-lock-only\nci\nrun build\n",
        )

    def test_commit_package_lock_is_noop_without_updating_lockfile(self):
        self.make_git("init", "-q")
        self.make_git("config", "user.email", "test@example.com")
        self.make_git("config", "user.name", "Test")
        self.make_git("add", "package-lock.json")
        self.make_git("commit", "-qm", "initial")
        before = self.make_git("rev-list", "--count", "HEAD").stdout

        self.make("commit-package-lock")

        self.assertEqual(self.make_git("rev-list", "--count", "HEAD").stdout, before)
        self.assertFalse((self.app / "npm.log").exists())

    def make_git(self, *arguments):
        return subprocess.run(
            ["git", *arguments], cwd=self.app, text=True, capture_output=True,
            check=True,
        )

    def test_legacy_and_neutral_dependencies_are_combined(self):
        self.configure("BUNDLER_DEPS = source.js\nWEBPACK_DEPS = legacy.js\n")
        lines = self.make("print-deps").stdout.splitlines()
        self.assertEqual(lines[0], lines[1])
        self.assertIn("source.js", lines[0].split())
        self.assertIn("legacy.js", lines[0].split())

    def test_custom_targets_are_exposed_under_legacy_name(self):
        self.configure("BUNDLER_TARGETS = $(ABSSRCDIR)/js/custom.json\n")
        lines = self.make("print-targets").stdout.splitlines()
        self.assertEqual(lines, [str(self.app / "js/custom.json")] * 2)
        env = {**os.environ, "OUTPUT": "js/custom.json"}
        self.make("npm-build", env=env)
        self.assertEqual((self.app / "js/custom.json").read_text(), "built\n")
        self.make("npm-build", env=env)
        self.assertEqual((self.app / "npm.log").read_text(), "run build\n")
        self.make("bundler-clean")
        self.make("npm-build", success=False, env={**env, "FAIL_BUILD": "1"})
        self.assertFalse((self.app / "js/custom.json").exists())

    def test_clean_aliases(self):
        for target in ("bundler-clean", "webpack-clean"):
            with self.subTest(target=target):
                self.write("js/app.js", "")
                self.write("css/app.css", "")
                self.make(target)
                self.assertEqual(list((self.app / "js").iterdir()), [])
                self.assertEqual(list((self.app / "css").iterdir()), [])
                self.assertTrue((self.app / "source.js").exists())

    def test_development_build_switches_flavour(self):
        self.make("npm-dev")
        self.assertEqual((self.app / "build-flavour").read_text(), "dev\n")
        self.assertEqual((self.app / "npm.log").read_text(), "run dev\n")
        self.assertFalse((self.app / "clean.log").exists())

    def test_flavour_switch_cleans_only_bundler_outputs(self):
        self.write("build-flavour", "dev\n")
        for name in (
            "build/vendor-wrapped/.composer-ready",
            "build/ts-types/php-types.d.ts",
            "build/scss-variables/app.scss",
            "vendor-wrapped/.scoper-ready",
            "js/stale.js",
            "css/stale.css",
        ):
            self.write(name, "")

        self.make("npm-build")

        self.assertEqual((self.app / "build-flavour").read_text(), "build\n")
        self.assertTrue((self.app / "build/vendor-wrapped/.composer-ready").exists())
        self.assertTrue((self.app / "build/ts-types/php-types.d.ts").exists())
        self.assertTrue((self.app / "build/scss-variables/app.scss").exists())
        self.assertTrue((self.app / "vendor-wrapped/.scoper-ready").exists())
        self.assertFalse((self.app / "js/stale.js").exists())
        self.assertFalse((self.app / "css/stale.css").exists())
        self.assertFalse((self.app / "clean.log").exists())
        self.assertTrue((self.app / "js/asset-meta.json").exists())

    def test_failed_build_removes_asset_metadata(self):
        self.make("npm-build", success=False, env={**os.environ, "FAIL_BUILD": "1"})
        self.assertFalse((self.app / "js/asset-meta.json").exists())

    def test_legacy_config_default_is_preserved(self):
        self.write("webpack.config.js", "")
        self.configure(config="")
        output = self.make("print-deps").stdout
        self.assertIn("webpack.config.js", output)


if __name__ == "__main__":
    unittest.main()
