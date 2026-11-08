import json
import os

os.environ["LC_ALL"] = "C"
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
AUTOLOAD = "\n" * 46 + (
    "            }\n"
    "        }, null, null);\n"
    "        foreach ($filesToLoad as $fileIdentifier => $file) {\n"
    "            $requireFile($fileIdentifier, $file);\n"
    "        }\n"
    "\n"
    "        return $loader;\n"
)


class NamespaceWrapperTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.app = Path(self.temporary.name)
        self.write("composer.lock", "{}")
        self.write("scoper.inc.php", "<?php")
        self.write("vendor/installed", "")
        self.executable(
            "xpath",
            "#!/usr/bin/env python3\n"
            "import sys, xml.etree.ElementTree as ET\n"
            "root = ET.parse(sys.argv[-1]).getroot()\n"
            "print(root.findtext('scopednamespace') "
            "if sys.argv[-2] == '/info/scopednamespace/text()' else 'Test')\n",
        )
        # Stand-ins simulate Composer's tree and Scoper's binary/permission losses.
        self.executable(
            "composer",
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib, shutil, sys\n"
            "app = pathlib.Path(__file__).parent\n"
            "args = sys.argv[1:]\n"
            "with (app / 'commands').open('a') as log:\n"
            "    log.write(json.dumps(['composer', os.environ.get('COMPOSER'), args]) + '\\n')\n"
            "if args[:2] == ['bin', 'php-scoper']:\n"
            "    tool = app / 'vendor-bin/php-scoper/vendor/bin/php-scoper'\n"
            "    tool.parent.mkdir(parents=True, exist_ok=True)\n"
            "    shutil.copy2(app / 'scoper', tool)\n"
            "    sys.exit(0)\n"
            "cwd = app\n"
            "if args[0].startswith('-d'):\n"
            "    cwd = app / args.pop(0)[2:]\n"
            "command = args[0]\n"
            "if os.environ.get('FAIL_COMPOSER') == command:\n"
            "    sys.exit(17)\n"
            "manifest = pathlib.Path(os.environ['COMPOSER'])\n"
            "vendor = cwd / json.loads(manifest.read_text())['config']['vendor-dir']\n"
            "if command in ('install', 'update'):\n"
            "    manifest.with_suffix('.lock').write_text('{}')\n"
            "    vendor.mkdir(parents=True, exist_ok=True)\n"
            "    if os.environ.get('WITH_BIN'):\n"
            "        binary = vendor / 'package/bin/tool'\n"
            "        binary.parent.mkdir(parents=True, exist_ok=True)\n"
            "        binary.write_text('#!/usr/bin/env php\\n')\n"
            "        binary.chmod(0o644)\n"
            "        (vendor / 'bin').mkdir(exist_ok=True)\n"
            "        link = vendor / 'bin/tool'\n"
            "        if not link.is_symlink():\n"
            "            link.symlink_to('../package/bin/tool')\n"
            "if command in ('install', 'update', 'dump-autoload'):\n"
            "    (vendor / 'autoload.php').write_text('<?php')\n"
            "    (vendor / 'composer').mkdir(exist_ok=True)\n"
            f"    autoload = {AUTOLOAD!r}\n"
            "    if os.environ.get('NO_FILES'):\n"
            "        autoload = '<?php return $loader;'\n"
            "    if os.environ.get('BAD_PATCH'):\n"
            "        autoload = '<?php /* filesToLoad */'\n"
            "    (vendor / 'composer/autoload_real.php').write_text(autoload)\n",
        )
        self.executable(
            "scoper",
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib, shutil, sys\n"
            "args = sys.argv[1:]\n"
            "output = pathlib.Path(next(a.split('=', 1)[1] for a in args "
            "if a.startswith('--output-dir=')))\n"
            "app = output.parent\n"
            "with (app / 'commands').open('a') as log:\n"
            "    log.write(json.dumps(['scoper', args]) + '\\n')\n"
            "if os.environ.get('FAIL_SCOPER'):\n"
            "    sys.exit(19)\n"
            "build = next(a[2:] for a in args if a.startswith('-d'))\n"
            "shutil.copytree(app / build / output.name, output, dirs_exist_ok=True,\n"
            "                ignore=lambda directory, names: ['bin'] "
            "if pathlib.Path(directory).name == output.name else [])\n",
        )
        self.configure("Scoped")

    def write(self, name, content):
        path = self.app / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def executable(self, name, content):
        self.write(name, content).chmod(0o755)

    def configure(self, namespace, options=""):
        self.vendor = f"vendor-{namespace.lower()}"
        self.manifest = f"composer-{namespace.lower()}.json"
        self.write("appinfo/info.xml",
                   f"<info><scopednamespace>{namespace}</scopednamespace></info>")
        self.write(self.manifest, json.dumps({"config": {"vendor-dir": self.vendor}}))
        self.write(
            "Makefile",
            f"ABSSRCDIR := {self.app}\n"
            f"DEV_LIB_DIR := {ROOT}\n"
            f"COMPOSER := {self.app}/composer\n"
            "COMPOSER_OPTIONS := --prefer-dist\n"
            f"include {ROOT}/makefile/setup.mk\n"
            f"{options}\n"
            f"include {ROOT}/makefile/namespace-wrapper.mk\n"
            f"include {ROOT}/makefile/namespace-wrapper.mk\n"
            "all:\n\t@echo app-default\n",
        )

    def make(self, *arguments, success=True, **env):
        result = subprocess.run(
            ["make", "--no-print-directory", "-C", str(self.app),
             f"XPATH={self.app}/xpath", *arguments],
            text=True, capture_output=True, env={**os.environ, **env},
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def commands(self):
        log = self.app / "commands"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def test_default_goal_does_not_install_anything(self):
        result = self.make()
        self.assertIn("app-default", result.stdout)
        self.assertEqual(self.commands(), [])

    def test_cafevdb_binary_workarounds_and_incremental_build(self):
        self.configure("Wrapped", "SCOPED_VENDOR_LINK_DIRS = 3rdparty vendor")
        (self.app / "3rdparty").mkdir()
        self.make("-j4", "namespace-wrapper", WITH_BIN="1")
        output = self.app / self.vendor
        self.assertTrue((output / "bin/tool").is_symlink())
        self.assertTrue((output / "bin/tool").stat().st_mode & 0o110 == 0o110)
        self.assertIn("'OCA_Test_Wrapped' . $fileIdentifier",
                      (output / "composer/autoload_real.php").read_text())
        for directory in ("vendor", "3rdparty"):
            self.assertEqual((self.app / "build" / directory).resolve(), self.app / directory)
        self.assertEqual((self.app / "build/composer-patches").resolve(), ROOT / "patches")
        commands = self.commands()
        update = next(c for c in commands if c[0] == "composer" and "update" in c[2])
        self.assertEqual(update[1], str(self.app / self.manifest))
        self.assertEqual(update[2], ["-d./build", "update", "--prefer-dist"])
        self.assertEqual(sum(c[0] == "scoper" for c in commands), 1)
        self.make("namespace-wrapper", WITH_BIN="1")
        self.assertEqual(self.commands(), commands)
        (self.app / self.manifest).touch()
        self.make("namespace-wrapper", WITH_BIN="1")
        self.assertEqual(sum(c[0] == "scoper" for c in self.commands()), 2)

    def test_build_flavour_switches_preserve_scoped_vendor(self):
        self.configure("Wrapped")
        for name in ("package.json", "package-lock.json", "webpack.config.js",
                     "eslint.config.mjs"):
            self.write(name, "")
        (self.app / "node_modules").mkdir()
        self.executable(
            "npm",
            "#!/bin/sh\n"
            "if [ \"$1\" = run ]; then echo \"$2\" >> npm.log; fi\n"
            "mkdir -p js css\n"
            "echo built > js/asset-meta.json\n",
        )
        with (self.app / "Makefile").open("a") as makefile:
            makefile.write(
                f"NPM = {self.app}/npm\n"
                f"include {ROOT}/makefile/npm.mk\n"
                ".DEFAULT_GOAL := all\n"
            )

        self.make("namespace-wrapper")
        self.make("npm-build")
        self.make("namespace-wrapper")
        self.make("npm-build")
        self.make("npm-dev")
        self.make("namespace-wrapper")
        self.make("npm-build")
        self.make("namespace-wrapper")

        self.assertEqual(sum(c[0] == "scoper" for c in self.commands()), 1)
        self.assertEqual(
            (self.app / "npm.log").read_text().splitlines(),
            ["build", "dev", "build"],
        )

    def test_dokuwiki_without_binaries_or_file_autoloads(self):
        self.configure("Scoped", "SCOPED_COMPOSER_UPDATE_OPTIONS = --no-dev")
        self.make("namespace-wrapper", NO_FILES="1")
        self.assertFalse((self.app / self.vendor / "bin").exists())
        self.assertEqual(
            (self.app / self.vendor / "composer/autoload_real.php").read_text(),
            "<?php return $loader;",
        )
        update = next(c for c in self.commands() if c[0] == "composer" and "update" in c[2])
        self.assertEqual(update[2], ["-d./build", "update", "--prefer-dist", "--no-dev"])

    def test_build_autoload_and_suggestions_targets(self):
        self.configure("CuStOm")
        self.make(f"build/{self.vendor}/autoload.php", f"composer-custom-suggest")
        self.assertTrue((self.app / "build" / self.vendor / "autoload.php").is_file())
        self.assertFalse((self.app / self.vendor).exists())
        self.assertIn("suggest", self.commands()[-1][2])
        self.assertEqual(self.commands()[-2][2][-1], "dump-autoload")

    def git(self, *arguments):
        result = subprocess.run(
            ["git", "-C", str(self.app / "3rdparty/package"), *arguments],
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_git_dependency_changes_rebuild_only_when_needed(self):
        self.write("3rdparty/package/source", "one")
        self.git("init", "--quiet")
        self.git("add", "source")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.com",
                 "commit", "--quiet", "-m", "Initial")
        self.configure("Wrapped",
                       "WRAPPER_GIT_DEPENDENCIES = 3rdparty/package\n"
                       "SCOPED_VENDOR_LINK_DIRS = 3rdparty vendor")
        self.make("namespace-wrapper")
        first_hash = (self.app / "wrapper-build-hash").read_text()
        commands = self.commands()
        self.make("namespace-wrapper")
        self.assertEqual(self.commands(), commands)
        self.write("3rdparty/package/source", "two")
        self.git("add", "source")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.com",
                 "commit", "--quiet", "-m", "Changed")
        self.make("namespace-wrapper")
        self.assertNotEqual((self.app / "wrapper-build-hash").read_text(), first_hash)
        self.assertEqual(sum(c[0] == "scoper" for c in self.commands()), 2)

    def test_invalid_git_dependency_is_an_error(self):
        self.configure("Wrapped", "WRAPPER_GIT_DEPENDENCIES = missing")
        result = self.make("namespace-wrapper", success=False)
        self.assertIn("Cannot read Git dependencies", result.stderr)

    def test_composer_scoper_and_patch_errors_propagate(self):
        for env in ({"FAIL_COMPOSER": "update"}, {"FAIL_SCOPER": "1"}, {"BAD_PATCH": "1"}):
            with self.subTest(env=env):
                (self.app / self.manifest).touch()
                result = self.make("namespace-wrapper", success=False, **env)
                self.assertIn("Error", result.stderr)
                previous_scopes = sum(c[0] == "scoper" for c in self.commands())
                self.make("namespace-wrapper")
                self.assertEqual(
                    sum(c[0] == "scoper" for c in self.commands()), previous_scopes + 1,
                )
                self.assertIn(
                    "'OCA_Test_Scoped' . $fileIdentifier",
                    (self.app / self.vendor / "composer/autoload_real.php").read_text(),
                )


if __name__ == "__main__":
    unittest.main()
