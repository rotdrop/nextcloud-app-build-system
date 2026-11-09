"""Tests for the shared application Makefile makefile/app.mk and its opt-in
fragments, using a fixture app which mirrors the layout of a consuming app.

The "make -n" snapshots live in tests/snapshots. Regenerate them after an
intended change with:

    UPDATE_SNAPSHOTS=1 python3 -B -m unittest tests.test_app
"""
import json
import os

# Tools parsed or asserted on by the tests must not emit localized output.
os.environ["LC_ALL"] = "C"
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = Path(__file__).resolve().parent / "snapshots"

XPATH_STUB = """#!/usr/bin/env python3
import sys, xml.etree.ElementTree as ET
root = ET.parse(sys.argv[-1]).getroot()
query = sys.argv[-2]
texts = {
    '/info/id/text()': 'id',
    '/info/version/text()': 'version',
    '/info/namespace/text()': 'namespace',
    '/info/scopednamespace/text()': 'scopednamespace',
}
if query in texts:
    print(root.findtext(texts[query]))
elif 'max-version' in query:
    print(root.find('dependencies/nextcloud').get('max-version'))
"""

INFO_XML = (
    "<info><id>fixtureapp</id><version>1.2.3</version>"
    "<namespace>FixtureApp</namespace>"
    "<scopednamespace>Scoped</scopednamespace>"
    '<dependencies><nextcloud min-version="33" max-version="35"/></dependencies>'
    "</info>"
)

DEFAULT_MAKEFILE = (
    "SRCDIR = .\n"
    "ABSSRCDIR = $(CURDIR)\n"
    "DEV_LIB_DIR = $(ABSSRCDIR)/dev-scripts/lib\n"
    "{hooks}"
    "include $(DEV_LIB_DIR)/makefile/app.mk\n"
    "{rules}"
)


class AppMakefileTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.app = Path(self.temporary.name).resolve()
        for name in ("composer.json.in", "package.json", "vite.config.ts",
                     "eslint.config.mjs", "scoper.inc.php", "composer-scoped.json"):
            self.write(name, "{}\n")
        self.write("appinfo/info.xml", INFO_XML)
        self.write("src/main.ts", "")
        self.write("img/icon.svg", "")
        self.write("l10n/de.js", "")
        self.write("dev-scripts/php-to-typescript.php", "")
        (self.app / "dev-scripts/lib").symlink_to(ROOT)
        self.write("xpath", XPATH_STUB)
        (self.app / "xpath").chmod(0o755)
        self.configure()
        self.env = {**os.environ, "XDEBUG_MODE": "off", "HOME": str(self.app / "home")}
        self.env.pop("VERSION", None)
        self.env.pop("APP_VERSION", None)

    def write(self, name, content):
        path = self.app / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def configure(self, hooks="", rules=""):
        self.write("Makefile", DEFAULT_MAKEFILE.format(hooks=hooks, rules=rules))

    @property
    def tools(self):
        # Fixed tool names keep the output independent of the host.
        return [
            f"XPATH={self.app / 'xpath'}", "PHP=php", "NPM=npm", "RSYNC=rsync",
            "OPENSSL=openssl", "EMACS=emacs", "COMPOSER=composer",
        ]

    def make(self, *arguments, success=True, with_tools=True, env=None):
        command = ["make", "--no-print-directory", "-C", str(self.app)]
        if with_tools:
            command += self.tools
        result = subprocess.run(
            [*command, *arguments], text=True, capture_output=True,
            env=env or self.env,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def ready_composer(self):
        """Pretend composer ran, so that -n does not plan the dependency installation."""
        self.write("composer.json", "{}\n")
        self.write("composer.lock", "{}\n")
        for tool in ("phpcs", "phpmd"):
            path = self.app / f"vendor-bin/{tool}/vendor/bin/{tool}"
            self.write(f"vendor-bin/{tool}/vendor/bin/{tool}", "")
            path.chmod(0o755)
        now = time.time_ns()
        for name, age in (("composer.json.in", 100), ("composer.json", 50),
                          ("composer.lock", 40), ("vendor-bin/phpcs/vendor/bin/phpcs", 30),
                          ("vendor-bin/phpmd/vendor/bin/phpmd", 30)):
            os.utime(self.app / name, ns=(now - age * 10**9,) * 2)

    def normalize(self, text):
        return text.replace(str(self.app), "@APP@").replace(str(ROOT), "@LIB@")

    def assert_snapshot(self, name, text):
        text = self.normalize(text)
        path = SNAPSHOTS / f"{name}.txt"
        if os.environ.get("UPDATE_SNAPSHOTS"):
            SNAPSHOTS.mkdir(exist_ok=True)
            path.write_text(text)
        self.assertTrue(path.exists(), f"missing snapshot {path}")
        self.assertEqual(path.read_text(), text, f"snapshot {name} differs")

    def variable(self, name, hooks="", extra=()):
        self.configure(
            hooks=hooks,
            rules=f"print-var:\n\t@echo '$({name})'\n",
        )
        return self.make("print-var", *extra).stdout.strip()


class TestSuitesTest(AppMakefileTestCase):
    def setUp(self):
        super().setUp()
        self.write(
            "phpunit",
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" >> phpunit.log\n"
            "exit \"${PHPUNIT_STATUS:-0}\"\n",
        )
        self.write(
            "npm",
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" >> npm.log\n"
            "case \"$1\" in\n"
            "  ci) test -z \"$FAIL_CI\" || exit 24; mkdir -p node_modules ;;\n"
            "  run) test -d node_modules || exit 98; exit \"${TEST_STATUS:-0}\" ;;\n"
            "  *) exit 99 ;;\n"
            "esac\n",
        )
        for name in ("phpunit", "npm"):
            (self.app / name).chmod(0o755)
        self.configure(
            hooks="PHPUNIT = $(ABSSRCDIR)/phpunit\nNPM = $(ABSSRCDIR)/npm\n"
        )

    def suite_make(self, *arguments, **kwargs):
        return self.make(*arguments, f"NPM={self.app / 'npm'}", **kwargs)

    def frontend_suite(self, script="vitest run", name="test"):
        self.write("package.json", json.dumps({"scripts": {name: script}}))
        self.write("package-lock.json", "{}\n")

    def test_absent_suites_warn_without_invoking_runners(self):
        result = self.suite_make("test")
        for warning in (
            "phpunit.xml not found", "phpunit.integration.xml not found",
            "npm script 'test' not found",
        ):
            self.assertIn(warning, result.stderr)
        self.assertFalse((self.app / "phpunit.log").exists())
        self.assertFalse((self.app / "npm.log").exists())
        self.assertFalse((self.app / "node_modules").exists())

    def test_php_suites_run_only_with_their_configuration(self):
        for config, target in (
            ("phpunit.xml", "unit-tests"),
            ("phpunit.integration.xml", "integration-tests"),
        ):
            with self.subTest(target=target):
                self.suite_make(target)
                self.assertFalse((self.app / "phpunit.log").exists())
                self.write(config, "<phpunit/>\n")
                self.suite_make(target)
                self.assertEqual(
                    (self.app / "phpunit.log").read_text(), f"-c {config}\n"
                )
                (self.app / "phpunit.log").unlink()

    def test_php_failures_are_not_skipped(self):
        for target, config in (
            ("unit-tests", "phpunit.xml"),
            ("integration-tests", "phpunit.integration.xml"),
        ):
            with self.subTest(target=target):
                self.write(config, "<phpunit/>\n")
                result = self.suite_make(
                    target, success=False,
                    env={**self.env, "PHPUNIT_STATUS": "23"},
                )
                self.assertIn("Error 23", result.stderr)
                self.assertNotIn("skipping", result.stderr)

    def test_missing_php_runner_is_an_error(self):
        self.write("phpunit.xml", "<phpunit/>\n")
        (self.app / "phpunit").unlink()
        self.suite_make("unit-tests", success=False)

    def test_php_only_runs_without_npm_dependencies(self):
        self.write("phpunit.xml", "<phpunit/>\n")
        self.suite_make("test")
        self.assertEqual((self.app / "phpunit.log").read_text(), "-c phpunit.xml\n")
        self.assertFalse((self.app / "npm.log").exists())

    def test_frontend_only_installs_then_runs_once(self):
        self.frontend_suite("vitest")
        self.write("js/existing.js", "keep\n")
        self.suite_make("test")
        self.assertEqual((self.app / "npm.log").read_text(), "ci\nrun test -- --run\n")
        self.suite_make("test")
        self.assertEqual(
            (self.app / "npm.log").read_text(),
            "ci\nrun test -- --run\nrun test -- --run\n",
        )
        self.assertEqual((self.app / "js/existing.js").read_text(), "keep\n")
        self.assertFalse((self.app / "build-flavour").exists())

    def test_mixed_suites_run_in_parallel(self):
        self.frontend_suite()
        self.write("phpunit.xml", "<phpunit/>\n")
        self.write("phpunit.integration.xml", "<phpunit/>\n")
        self.suite_make("-j4", "test")
        self.assertCountEqual(
            (self.app / "phpunit.log").read_text().splitlines(),
            ["-c phpunit.xml", "-c phpunit.integration.xml"],
        )
        self.assertEqual((self.app / "npm.log").read_text(), "ci\nrun test -- --run\n")

    def test_missing_manifest_warns_without_node_or_npm(self):
        (self.app / "package.json").unlink()
        result = self.suite_make("frontend-tests", "NODE=/nonexistent/node")
        self.assertIn("package.json not found", result.stderr)
        self.assertFalse((self.app / "npm.log").exists())

    def test_empty_script_is_absent(self):
        self.frontend_suite("  ")
        result = self.suite_make("frontend-tests")
        self.assertIn("npm script 'test' not found", result.stderr)
        self.assertFalse((self.app / "npm.log").exists())

    def test_invalid_manifest_and_missing_node_are_errors(self):
        self.write("package.json", "{invalid")
        self.suite_make("frontend-tests", success=False)
        self.frontend_suite(script=42)
        result = self.suite_make("frontend-tests", success=False)
        self.assertIn("npm test script must be a string", result.stderr)
        self.write("package.json", "{}")
        self.suite_make("frontend-tests", "NODE=/nonexistent/node", success=False)
        self.assertFalse((self.app / "npm.log").exists())

    def test_frontend_script_and_arguments_can_be_overridden(self):
        self.frontend_suite("vitest run", name="test:unit")
        self.suite_make(
            "frontend-tests", "FRONTEND_TEST_SCRIPT=test:unit",
            "FRONTEND_TEST_ARGS=--run --reporter=verbose",
        )
        self.assertEqual(
            (self.app / "npm.log").read_text(),
            "ci\nrun test:unit -- --run --reporter=verbose\n",
        )
        self.suite_make(
            "frontend-tests", "FRONTEND_TEST_SCRIPT=test:unit",
            "FRONTEND_TEST_ARGS=",
        )
        self.assertTrue((self.app / "npm.log").read_text().endswith("run test:unit --\n"))

    def test_frontend_failure_is_fatal(self):
        self.frontend_suite()
        # Vitest uses status 1 for failed tests and for an empty configured suite.
        for status in ("1", "23", "127"):
            with self.subTest(status=status):
                result = self.suite_make(
                    "test", success=False, env={**self.env, "TEST_STATUS": status},
                )
                self.assertIn(f"Error {status}", result.stderr)
        self.assertEqual(
            (self.app / "npm.log").read_text(),
            "ci\n" + "run test -- --run\n" * 3,
        )

    def test_missing_lockfile_or_failed_install_stops_frontend_tests(self):
        self.frontend_suite()
        (self.app / "package-lock.json").unlink()
        result = self.suite_make("frontend-tests", success=False)
        self.assertIn("run 'make update-package-lock'", result.stderr)
        self.assertFalse((self.app / "npm.log").exists())
        self.write("package-lock.json", "{}")
        self.suite_make(
            "frontend-tests", success=False, env={**self.env, "FAIL_CI": "1"},
        )
        self.assertEqual((self.app / "npm.log").read_text(), "ci\n")


@unittest.skipUnless(
    Path("/usr/share/bash-completion/bash_completion").is_file()
    and Path("/usr/share/bash-completion/completions/make").is_file(),
    "requires bash-completion and its make completion",
)
class BashCompletionTest(AppMakefileTestCase):
    def test_appstore_completion(self):
        self.configure(
            hooks="APP_NOTIFICATION_API = 1\n" + "\n".join(self.tools) + "\n"
        )
        for prefix in ("apps", "appstore"):
            with self.subTest(prefix=prefix):
                result = subprocess.run(
                    ["bash", "-c", r"""
source /usr/share/bash-completion/bash_completion || exit
source /usr/share/bash-completion/completions/make || exit
cd "$1" || exit
completion=$(complete -p make) || exit
completion=${completion#* -F }
completion=${completion%% *}
COMP_WORDS=(make "$2")
COMP_CWORD=$((${#COMP_WORDS[@]} - 1))
COMP_LINE="${COMP_WORDS[*]}"
COMP_POINT=${#COMP_LINE}
COMP_TYPE=9
"$completion" make "$2" make
printf '%s\n' "${COMPREPLY[@]}"
""", "bash", str(self.app), prefix],
                    text=True, capture_output=True,
                    env={**self.env, "PATH": f"{self.app}:{self.env['PATH']}"},
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines(), ["appstore"])
        self.assertFalse((self.app / "build").exists())


class SnapshotTest(AppMakefileTestCase):
    def test_appstore(self):
        # Recursive make calls are replaced by "true" to snapshot only the recipe itself.
        self.assert_snapshot("appstore", self.make("-n", "appstore", "MAKE=true").stdout)

    def test_mostlyclean(self):
        self.assert_snapshot("mostlyclean", self.make("-n", "mostlyclean").stdout)

    def test_php_checks_and_tests(self):
        self.write("lib/.keep", "")
        self.write("appinfo/.keep", "")
        self.ready_composer()
        out = "".join(
            self.make("-n", target).stdout
            for target in ("phpcs", "phpcs-errors", "phpmd", "test", "run-tide")
        )
        self.assert_snapshot("php-checks", out)

    def rsync_line(self):
        out = self.make("-n", "appstore", "MAKE=true").stdout
        return next(line for line in out.splitlines() if line.startswith("rsync"))

    def test_appstore_without_templates_directory(self):
        self.assertNotIn("templates", self.rsync_line().replace("./build", ""))

    def test_appstore_with_templates_directory(self):
        self.write("templates/page.php", "")
        self.assertIn(" templates ", self.rsync_line())

    def test_appstore_files_override_without_templates(self):
        self.configure(hooks="APPSTORE_FILES = appinfo lib\n")
        self.assertIn(" appinfo lib ", self.rsync_line())
        self.assertNotIn("templates", self.rsync_line().replace("./build", ""))

    def test_flavour_first_build(self):
        self.configure(hooks="APP_BUILD_FLAVOUR_FIRST = 1\n")
        self.assert_snapshot("build-flavour-first", self.make("-n", "build", "MAKE=true").stdout)

    def test_generic_hooks(self):
        self.configure(
            hooks="APP_REQUIRED_TOOLS = WGET\nAPPSTORE_FILES_EXTRA = contrib\n"
                  "APP_MOSTLYCLEAN_FILES = stamp.extra\nAPPSTORE_COPY_HOOK = copy-extra\n",
            rules="dev-setup: extra-setup\nextra-setup:\n\t@echo extra-setup\n"
                  "copy-extra:\n\t@echo copy-extra\n.PHONY: extra-setup copy-extra\n",
        )
        out = self.make("-n", "extra-setup", "copy-extra", "WGET=wget").stdout
        self.assert_snapshot("generic-hooks", out)


class SigningTest(AppMakefileTestCase):
    def appstore(self, *arguments):
        env = {**self.env, "APP_PRIVATE_KEY": "key", "APP_PUBLIC_CRT": "crt"}
        # Fake tools: the recorded php/openssl calls show whether signing ran.
        return self.make("appstore", "MAKE=true", "COMPOSER=true", "RSYNC=true",
                         "PHP=echo", "OPENSSL=echo", *arguments, env=env)

    def test_signing_is_the_default(self):
        out = self.appstore().stdout
        self.assertIn("integrity:sign-app", out)
        self.assertTrue((self.app / "build/tools/certificates/fixtureapp.key").exists())

    def test_unsigned_build_ignores_keys(self):
        out = self.appstore("APPSTORE_SIGN=0").stdout
        self.assertNotIn("integrity:sign-app", out)
        self.assertNotIn("Signing", out)
        self.assertFalse((self.app / "build/tools/certificates").exists() and
                         any((self.app / "build/tools/certificates").iterdir()))
        self.assertTrue(list((self.app / "build/artifacts/appstore").glob("*.tar.gz")))


class VariableTest(AppMakefileTestCase):
    def test_default_goal_is_help(self):
        out = self.make().stdout
        self.assertIn("Targets:", out)
        self.assertRegex(out, r"(?m)^  build\s+Build the distribution assets")

    def test_help_lists_only_documented_rules(self):
        out = self.make("help").stdout
        self.assertNotIn("dev-setup", out)
        self.assertNotIn("DRY", out)
        self.assertNotRegex(out, r"(?m)^  [A-Za-z_]+\s*:?=")

    def test_version_is_read_from_info_xml(self):
        self.assertEqual(self.variable("APP_VERSION"), "1.2.3")
        self.assertIn("fixtureapp-1.2.3.tar.gz", self.variable("APPSTORE_PACKAGE_FILE"))

    def test_version_alias_and_precedence(self):
        self.assertEqual(self.variable("APP_VERSION", extra=["VERSION=4.5.6"]), "4.5.6")
        package = self.variable("APPSTORE_PACKAGE_FILE", extra=["VERSION=4.5.6"])
        self.assertTrue(package.endswith("fixtureapp-4.5.6.tar.gz"), package)
        self.assertEqual(
            self.variable("APP_VERSION", extra=["VERSION=4.5.6", "APP_VERSION=7.8.9"]),
            "7.8.9",
        )

    def test_version_from_environment_is_ignored(self):
        env = {**self.env, "VERSION": "9.9.9"}
        self.configure(rules="print-var:\n\t@echo '$(APP_VERSION)'\n")
        self.assertEqual(self.make("print-var", env=env).stdout.strip(), "1.2.3")

    def test_compression(self):
        package = self.variable("APPSTORE_PACKAGE_FILE", extra=["APPSTORE_COMPRESSION=J"])
        self.assertTrue(package.endswith("fixtureapp-1.2.3.tar.xz"), package)

    def test_hooks_have_defaults(self):
        self.assertEqual(self.variable("APP_DEV_SETUP_DEPS"), "ts-app-config")
        self.assertEqual(self.variable("BUNDLER_CONFIG"), "vite.config.ts")
        self.assertEqual(self.variable("L10N_VITE_CONFIG"), "vite.l10n.config.ts")
        self.assertEqual(self.variable("TS_PHP_SOURCE_DIRS"),
                         "lib vendor-scoped/rotdrop/nextcloud-app-toolkit/src")

    def test_hooks_can_be_overridden(self):
        self.assertEqual(
            self.variable("TS_PHP_SOURCE_DIRS", hooks="TS_PHP_SOURCE_DIRS = lib\n"), "lib")
        self.assertEqual(
            self.variable("L10N_VITE_CONFIG", hooks="L10N_VITE_CONFIG = other.ts\n"),
            "other.ts")
        deps = self.variable(
            "BUNDLER_DEPS", hooks="JS_FILES_EXTRA = extra/file.vue\nBUNDLER_DEPS = mine.js\n")
        self.assertIn("extra/file.vue", deps.split())
        self.assertIn("mine.js", deps.split())
        self.assertIn(str(self.app / "src/main.ts"), deps.split())

    def test_notification_api_is_opt_in(self):
        self.assertNotIn("notification-api", self.variable("BUNDLER_DEPS"))
        deps = self.variable("BUNDLER_DEPS", hooks="APP_NOTIFICATION_API = 1\n")
        self.assertTrue(any(d.endswith("notification-api.d.ts") for d in deps.split()), deps)
        self.configure(hooks="APP_NOTIFICATION_API = 1\n")
        out = self.make("-n", "ts-notification-api").stdout
        self.assertIn("stable35/openapi.json", out)

    def test_appstore_files_and_hook(self):
        files = self.variable("APPSTORE_FILES", hooks="APPSTORE_FILES_EXTRA = contrib\n")
        self.assertIn("vendor-scoped", files.split())
        self.assertEqual(
            self.variable("APPSTORE_FILES_EXTRA", hooks="APPSTORE_FILES_EXTRA = contrib\n"),
            "contrib")
        self.configure(
            hooks="APPSTORE_COPY_HOOK = my-hook\n",
            rules="my-hook:\n\t@echo hook-ran\n.PHONY: my-hook\n",
        )
        self.assertIn("true my-hook", self.make("-n", "appstore", "MAKE=true").stdout)


class ToolTest(AppMakefileTestCase):
    def test_missing_required_tool_is_an_error(self):
        for tool in ("PHP", "NPM"):
            with self.subTest(tool=tool):
                result = self.make(f"{tool}=", success=False)
                self.assertIn(f"{tool} binary is needed", result.stderr)

    def test_wget_is_not_required_by_default(self):
        self.make("all", "WGET=")

    def test_optional_required_tools(self):
        self.configure(hooks="APP_REQUIRED_TOOLS = WGET\n")
        result = self.make("all", "WGET=", success=False)
        self.assertIn("WGET binary is needed", result.stderr)
        self.make("all", "WGET=wget")

    def test_hooks_extend_dev_setup_mostlyclean_and_appstore(self):
        self.configure(
            hooks="APP_MOSTLYCLEAN_FILES = stamp.extra\nAPPSTORE_COPY_HOOK = copy-extra\n",
            rules="dev-setup: extra-setup\nextra-setup:\n\t@echo extra-setup\n"
                  "print-var:\n\t@echo '$(APP_MOSTLYCLEAN_FILES)|$(APPSTORE_COPY_HOOK)'\n"
                  "print-deps:\n\t@echo '$^'\n",
        )
        self.assertEqual(self.make("print-var").stdout.strip(), "stamp.extra|copy-extra")
        self.assertIn("echo extra-setup", self.make("-n", "dev-setup", "MAKE=true").stdout)


class ReleaseTest(AppMakefileTestCase):
    def setUp(self):
        super().setUp()
        self.write("dev-scripts/release.sh", '#!/bin/sh\necho "release[$*]"\n')

    def test_release_runs_the_script(self):
        self.assertEqual(self.make("release").stdout.strip().splitlines()[-1], "release[]")
        out = self.make("release", "VERSION=2.0.0").stdout.strip().splitlines()[-1]
        self.assertEqual(out, "release[2.0.0]")

    def test_release_does_not_need_the_build_environment(self):
        self.make("release", "XPATH=", "PHP=", "NPM=", with_tools=False)
        result = self.make("build", "XPATH=", "PHP=", with_tools=False, success=False)
        self.assertIn("xpath", result.stderr)

    def test_missing_release_script(self):
        result = self.make("release", "RELEASE_SCRIPT=/nonexistent", success=False)
        self.assertIn("Release script", result.stderr)


class GenericReleaseTest(AppMakefileTestCase):
    def setUp(self):
        super().setUp()
        self.origin = self.app.parent / (self.app.name + "-origin.git")
        self.addCleanup(shutil.rmtree, self.origin, True)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.org")
        self.git("config", "user.name", "T")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)], check=True)
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "-q", "-u", "origin", "main")

    def git(self, *arguments):
        return subprocess.run(["git", "-C", str(self.app), *arguments], check=True,
                              capture_output=True, text=True).stdout

    def tags(self):
        return subprocess.run(["git", "--git-dir", str(self.origin), "tag"], check=True,
                              capture_output=True, text=True).stdout.split()

    def test_default_script_tags_info_xml_version(self):
        self.make("release")
        self.assertEqual(self.tags(), ["v1.2.3"])

    def test_version_argument_must_match(self):
        self.make("release", "VERSION=1.2.3")
        self.assertEqual(self.tags(), ["v1.2.3"])
        self.assertIn("differs", self.make("release", "VERSION=9.9.9", success=False).stderr)

    def test_refuses_existing_tag(self):
        self.make("release")
        self.assertIn("already", self.make("release", success=False).stderr)

    def test_refuses_dirty_tree_and_other_branch(self):
        self.write("dirty", "x")
        self.assertIn("clean", self.make("release", success=False).stderr)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "more")
        self.assertIn("match", self.make("release", success=False).stderr)
        self.git("checkout", "-q", "-b", "topic")
        self.assertIn("main branch", self.make("release", success=False).stderr)
        self.assertEqual(self.tags(), [])

    def test_app_local_script_overrides_default(self):
        self.write("dev-scripts/release.sh", '#!/bin/sh\necho "local[$*]"\n')
        self.assertEqual(self.make("release").stdout.strip().splitlines()[-1], "local[]")
        self.assertEqual(self.tags(), [])


class CleanTest(AppMakefileTestCase):
    def populate(self):
        for name in ("build/x", "vendor/x", "vendor-scoped/x", "vendor-bin/a/vendor/x",
                     "node_modules/x", "sub/node_modules/x", "js/x.js", "css/x.css",
                     "composer.lock", "composer.json", "package-lock.json", "build-flavour",
                     ".vite/x", "stats.json", "report.html", "downloads/x"):
            self.write(name, "{}" if name.endswith(".json") else "x")

    def exists(self, name):
        return (self.app / name).exists()

    def test_clean_levels(self):
        self.populate()
        self.write("extra-generated", "x")
        self.configure(
            hooks="APP_MOSTLYCLEAN_FILES = extra-generated\n",
            rules="hook-ran:\n\t@touch hook-ran\n",
        )
        self.make("clean")
        self.assertFalse(self.exists("build"))
        self.assertTrue(self.exists("vendor"))
        self.make("distclean")
        for name in ("vendor", "vendor-scoped", "vendor-bin/a/vendor", "node_modules",
                     "sub/node_modules"):
            self.assertFalse(self.exists(name), name)
        self.assertTrue(self.exists("js/x.js"))
        self.assertTrue(self.exists("composer.lock"))
        self.make("mostlyclean")
        for name in ("js/x.js", "css/x.css", "composer.lock", "composer.json",
                     "build-flavour", ".vite", "stats.json",
                     "report.html", "extra-generated"):
            self.assertFalse(self.exists(name), name)
        self.assertTrue(self.exists("package-lock.json"))
        self.assertTrue(self.exists("downloads/x"))
        self.assertTrue(self.exists("src/main.ts"))
        self.make("realclean")
        self.assertFalse(self.exists("downloads"))
        self.assertFalse(self.exists("package-lock.json"))

    def git(self, *arguments):
        subprocess.run(["git", "-C", str(self.app), *arguments], check=True, capture_output=True)

    def test_mostlyclean_keeps_untracked_package_lock(self):
        self.git("init", "-q")
        self.write("package-lock.json", "{}")
        self.make("mostlyclean")
        self.assertTrue(self.exists("package-lock.json"))
        self.make("realclean")
        self.assertFalse(self.exists("package-lock.json"))

    def test_mostlyclean_keeps_tracked_package_lock(self):
        self.git("init", "-q")
        self.write("package-lock.json", "{}")
        self.git("add", "package-lock.json")
        self.make("mostlyclean")
        self.assertTrue(self.exists("package-lock.json"))
        self.make("realclean")
        self.assertFalse(self.exists("package-lock.json"))

    def test_cleanup_omits_empty_optional_file_removal(self):
        for target in ("mostlyclean", "realclean"):
            with self.subTest(target=target):
                result = self.make(target)
                self.assertNotIn("rm -f", [line.strip() for line in result.stdout.splitlines()])

    def test_mostlyclean_deps_hook(self):
        self.configure(
            hooks="APP_MOSTLYCLEAN_DEPS = hook-ran\n",
            rules="hook-ran:\n\t@touch hook-ran\n",
        )
        self.make("mostlyclean")
        self.assertTrue(self.exists("hook-ran"))

    def test_realclean_is_idempotent(self):
        self.make("realclean")
        self.make("realclean")


class CiRealcleanTest(AppMakefileTestCase):
    def setUp(self):
        super().setUp()
        self.configure(
            hooks=f"XPATH = {self.app / 'xpath'}\n"
                  "override BUNDLER_DEPS = $(NPM_INIT_DEPS) node_modules\n",
        )
        self.write(
            "npm",
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" >> \"$NPM_LOG\"\n"
            "case \"$*\" in\n"
            "  ci) cmp package-lock.json \"$EXPECTED_LOCK\" || exit 1; "
            "mkdir -p node_modules ;;\n"
            "  'run build') mkdir -p js css; echo built > js/asset-meta.json ;;\n"
            "  *) exit 99 ;;\n"
            "esac\n",
        )
        (self.app / "npm").chmod(0o755)
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        match = re.search(
            r"- name: realclean leaves a pristine tree, also after a build\n"
            r".*?run: \|\n(.*?)\n\n", workflow, re.S,
        )
        self.assertIsNotNone(match)
        self.script = "\n".join(line[10:] for line in match.group(1).splitlines())
        # Exercise the npm build and cleanup without Composer or type generation.
        self.script = self.script.replace("make build", "make -o dev-setup build")

    def git(self, *arguments):
        subprocess.run(["git", "-C", str(self.app), *arguments], check=True, capture_output=True)

    def run_step(self, script=None):
        return subprocess.run(
            ["bash", "-e", "-o", "pipefail", "-c", script or self.script],
            cwd=self.app, env={**self.env, "PATH": f"{self.app}:{os.environ['PATH']}"},
            text=True, capture_output=True,
        )

    def test_tracked_lockfile_cleanup_and_locked_rebuild(self):
        self.write("package-lock.json", '{"lockfileVersion": 3}\n')
        lockfile = (self.app / "package-lock.json").read_bytes()
        self.git("add", "package-lock.json")
        self.git("commit", "-qm", "lock dependencies")
        for _ in range(2):
            self.make("realclean")
            self.assertFalse((self.app / "package-lock.json").exists())
            self.git("restore", "--", "package-lock.json")
            self.assertEqual((self.app / "package-lock.json").read_bytes(), lockfile)

        with tempfile.TemporaryDirectory() as tmp:
            expected = Path(tmp, "lock")
            expected.write_bytes(lockfile)
            log = Path(tmp, "npm.log")
            self.env.update(EXPECTED_LOCK=str(expected), NPM_LOG=str(log))
            result = self.run_step()
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(log.read_text(), "ci\nrun build\n")

        self.assertEqual((self.app / "package-lock.json").read_bytes(), lockfile)
        self.assertFalse((self.app / "node_modules").exists())
        self.assertFalse((self.app / "js/asset-meta.json").exists())
        status = subprocess.check_output(
            ["git", "status", "--porcelain", "--ignored"], cwd=self.app, text=True,
        )
        self.assertEqual(status, "")

    def test_untracked_lockfile_is_not_restored(self):
        self.write("package-lock.json", "{}\n")
        result = self.run_step(self.script.split("make -o dev-setup build")[0])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.app / "package-lock.json").exists())

    def test_ignored_artifacts_still_fail_cleanliness_check(self):
        self.write(".gitignore", "leftover\n")
        self.git("add", ".gitignore")
        self.git("commit", "-qm", "ignore fixture artifact")
        self.write("leftover", "artifact\n")
        result = self.run_step()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("!! leftover", result.stdout)
        self.assertIn("::error::realclean left files behind", result.stdout)


if __name__ == "__main__":
    unittest.main()
