from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AppMakefileTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.app = Path(self.temporary.name)
        self.write("appinfo/info.xml", "<info><id>demo</id></info>")
        self.write("composer-scoped.json", "{}")
        self.write("dev-scripts/MakeHelp/MakeHelp.mk", "help:\n\t@echo help\n.PHONY: help\n")
        self.write("package.json", "{}")
        self.write("scoper.inc.php", "<?php\n")
        self.write("composer.json.in", "{}")
        self.write("composer.json", "{}")
        self.write("composer.lock", "{}")
        self.write("stamp.composer-core-versions", "")
        self.write(
            "xpath",
            "#!/usr/bin/env python3\n"
            "import sys, xml.etree.ElementTree as ET\n"
            "root = ET.parse(sys.argv[-1]).getroot()\n"
            "path = sys.argv[-2]\n"
            "if path == '/info/scopednamespace/text()': print('Scoped')\n"
            "elif path == '/info/id/text()': print('demo')\n"
            "elif path == '/info/version/text()': print('1.2.3')\n"
            "elif path == '/info/namespace/text()': print('Demo')\n",
        )
        (self.app / "xpath").chmod(0o755)

    def write(self, name, content):
        path = self.app / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def makefile(self, before="", after=""):
        self.write(
            "Makefile",
            "SRCDIR = .\n"
            f"ABSSRCDIR = {self.app}\n"
            f"DEV_LIB_DIR = {ROOT}\n"
            f"{before}"
            f"include {ROOT}/makefile/app.mk\n"
            f"{after}"
            "print-%:\n\t@echo '$($*)'\n",
        )

    def make(self, *args, check=True):
        result = subprocess.run(
            ["make", "--no-print-directory", "-C", str(self.app),
             f"XPATH={self.app / 'xpath'}", "PHP=php", "NPM=npm",
             "COMPOSER=composer", *args],
            text=True, capture_output=True,
        )
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_default_goal_and_app_configuration(self):
        self.makefile(before="TS_PHP_SOURCE_DIRS = lib\nAPPSTORE_COMPOSER_COMMAND = true\n")
        # MakeHelp.mk's first target is help, which is the default goal
        self.assertEqual(self.make("print-.DEFAULT_GOAL").stdout, "help\n")
        self.assertIn("all: help", self.make("-pq", check=False).stdout)
        self.assertEqual(self.make("print-TS_PHP_SOURCE_DIRS").stdout, "lib\n")
        self.assertEqual(self.make("print-APP_NAME").stdout, "demo\n")
        self.assertEqual(self.make("print-APPSTORE_VERSION").stdout, "1.2.3\n")
        self.assertEqual(self.make("print-APPSTORE_VERSION", "VERSION=9").stdout, "9\n")

    def test_build_targets_and_dev_setup_extension(self):
        self.makefile(after="DEV_SETUP_DEPS_TEST = 1\ndev-setup: app-step\napp-step:\n\t@true\n")
        database = self.make("-pq", "build", check=False).stdout
        recipe = database.split("\nbuild:", 1)[1].split("\n\n", 1)[0]
        self.assertEqual(
            [line.strip() for line in recipe.splitlines() if line.startswith("\t")],
            ["$(MAKE) build-flavour-build", "$(MAKE) dev-setup", "$(MAKE) npm-build"],
        )
        rules = self.make("-pq", "dev-setup", check=False).stdout
        self.assertIn("composer namespace-wrapper", rules)
        self.assertIn("app-step", rules)

    def test_notification_api_is_opt_in(self):
        self.makefile()
        self.assertEqual(self.make("print-TS_NOTIFICATION_API").stdout, "\n")
        self.makefile(before="APP_TS_NOTIFICATION_API = 1\n")
        self.assertTrue(
            self.make("print-TS_NOTIFICATION_API").stdout.endswith("notification-api.d.ts\n"))
        self.assertIn("notification-api.d.ts", self.make("print-BUNDLER_DEPS").stdout)

    def test_appstore_package_skips_missing_files_and_runs_stage_hook(self):
        for name in ("lib/a.php", "COPYING"):
            self.write(name, "x")
        self.makefile(
            before="APPSTORE_FILES_EXTRA = extra\n",
            after="appstore-stage::\n\t@echo STAGE-HOOK\n",
        )
        self.write("extra/file", "x")
        dry = self.make("-n", "appstore-package", "RSYNC=rsync").stdout
        rsync = [line for line in dry.splitlines() if line.startswith("rsync")][0]
        for present in ("appinfo", "lib", "COPYING", "extra"):
            self.assertIn(f" {present} ", rsync + " ")
        for missing in ("templates", "vendor-scoped", "config"):
            self.assertNotIn(f" {missing} ", rsync + " ")
        self.assertEqual(self.make("appstore-stage").stdout, "STAGE-HOOK\n")

    def test_clean_targets_use_extension_variables(self):
        self.makefile(after="MOSTLYCLEAN_EXTRA += custom.stamp\nDISTCLEAN_EXTRA += custom-dir\n")
        for name in ("custom.stamp", "composer.lock", "package-lock.json", "build/x",
                     "custom-dir/x", "node_modules/a/node_modules/b", "keep.txt"):
            self.write(name, "x")
        self.make("realclean")
        for name in ("custom.stamp", "composer.lock", "package-lock.json", "build",
                     "custom-dir", "node_modules"):
            self.assertFalse((self.app / name).exists(), name)
        self.assertTrue((self.app / "keep.txt").exists())

    def test_pdf_downloader_fonts_are_optional(self):
        self.makefile()
        missing = self.make("-n", "build-fonts", check=False)
        self.assertNotEqual(missing.returncode, 0)
        self.assertNotIn("dejavu", self.make("-pq", "dev-setup", check=False).stdout.lower())

        self.makefile(after=f"include {ROOT}/makefile/optional/pdf-downloader-fonts.mk\n")
        self.write("wget", "#!/bin/sh\n")
        (self.app / "wget").chmod(0o755)
        fonts = self.make("-n", "build-fonts", f"WGET={self.app / 'wget'}").stdout
        self.assertIn("dejavu-fonts-ttf-2.37.tar.bz2", fonts)
        rules = self.make("-pq", "dev-setup", f"WGET={self.app / 'wget'}", check=False).stdout
        self.assertIn("build-fonts", rules)
        self.assertIn("fonts-list.json", rules)


if __name__ == "__main__":
    unittest.main()
