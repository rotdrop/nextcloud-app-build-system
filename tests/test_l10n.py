import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


FRAGMENT = Path(__file__).resolve().parents[1] / "makefile" / "l10n.mk"
TOOLKIT = "rotdrop/nextcloud-app-toolkit"
VUE_COMPONENTS = "@rotdrop/nextcloud-vue-components"


class L10nMakefileTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.app = Path(self.temporary.name)
        self.output = self.app / "l10n-sources"
        self.write("Makefile", f"include {FRAGMENT}\nall:\n\t@echo app-default\n")
        # Stand-ins make inclusion and invocation observable without installing packages.
        self.write(
            f"vendor/{TOOLKIT}/tools/l10n.mk",
            'toolkit-l10n:\n'
            '\t@mkdir -p "$(dir $(APP_TOOLKIT_L10N_DEST))"\n'
            '\t@printf toolkit > "$(APP_TOOLKIT_L10N_DEST)"\n'
            '.PHONY: toolkit-l10n\n',
        )
        self.write(
            "npx",
            "#!/usr/bin/env python3\n"
            "import os, pathlib, sys\n"
            f"assert sys.argv[1:4] == ['--no-install', '{VUE_COMPONENTS}', "
            "'extract-l10n-strings']\n"
            "assert len(sys.argv) == 5\n"
            "assert pathlib.Path.cwd() == pathlib.Path(__file__).parent\n"
            "sys.exit(23) if os.environ.get('FAIL_EXTRACTOR') else None\n"
            "pathlib.Path(sys.argv[4]).write_text('vue-components')\n",
        )
        (self.app / "npx").chmod(0o755)

    def write(self, name, content):
        path = self.app / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def manifest(self, name, content):
        self.write(name, json.dumps(content))

    def make(self, *arguments, success=True, env=None):
        result = subprocess.run(
            ["make", "--no-print-directory", "-C", str(self.app),
             f"NPX={self.app / 'npx'}", *arguments],
            text=True, capture_output=True, env=env,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_absent_dependencies_skip_even_with_installed_toolkit(self):
        self.make("l10n-sources", "toolkit-l10n", "vue-components-l10n")
        self.assertFalse(self.output.exists())

    def test_repository_urls_do_not_enable_extraction(self):
        self.manifest("composer.json", {"repositories": [{"url": TOOLKIT}]})
        self.manifest("package.json", {"description": VUE_COMPONENTS})
        self.make("l10n-sources")
        self.assertFalse(self.output.exists())

    def test_composer_dependency_sections_and_template(self):
        for name in ("composer.json", "composer.json.in"):
            for section in ("require", "require-dev"):
                with self.subTest(name=name, section=section):
                    self.manifest(name, {section: {TOOLKIT: "*"}})
                    self.make("l10n-sources")
                    destination = self.output / "toolkit-strings.php"
                    self.assertEqual(destination.read_text(), "toolkit")
                    self.assertFalse((self.output / "vue-components-strings.js").exists())
                    destination.unlink()
                    (self.app / name).unlink()

    def test_template_dependency_is_used_with_existing_composer_json(self):
        self.manifest("composer.json", {})
        self.manifest("composer.json.in", {"require": {TOOLKIT: "*"}})
        self.make("l10n-sources")
        self.assertTrue((self.output / "toolkit-strings.php").is_file())

    def test_npm_dependency_sections(self):
        for section in ("dependencies", "devDependencies", "optionalDependencies",
                        "peerDependencies"):
            with self.subTest(section=section):
                self.manifest("package.json", {section: {VUE_COMPONENTS: "*"}})
                self.make("l10n-sources")
                destination = self.output / "vue-components-strings.js"
                self.assertEqual(destination.read_text(), "vue-components")
                self.assertFalse((self.output / "toolkit-strings.php").exists())
                destination.unlink()

    def test_shared_directory_override_and_parallel_extraction(self):
        self.manifest("composer.json", {"require": {TOOLKIT: "*"}})
        self.manifest("package.json", {"dependencies": {VUE_COMPONENTS: "*"}})
        destination = self.app / "custom-catalogues"
        self.make("-j2", "l10n-sources", f"L10N_SOURCES_DIR={destination}")
        self.assertEqual((destination / "toolkit-strings.php").read_text(), "toolkit")
        self.assertEqual((destination / "vue-components-strings.js").read_text(),
                         "vue-components")

    def test_individual_destination_overrides(self):
        self.manifest("composer.json", {"require": {TOOLKIT: "*"}})
        self.manifest("package.json", {"dependencies": {VUE_COMPONENTS: "*"}})
        toolkit = self.app / "php" / "strings.php"
        vue = self.app / "js" / "strings.js"
        self.make("l10n-sources", f"APP_TOOLKIT_L10N_DEST={toolkit}",
                  f"VUE_COMPONENTS_L10N_DEST={vue}")
        self.assertTrue(toolkit.is_file())
        self.assertTrue(vue.is_file())

    def test_default_goal_is_preserved_before_and_after_include(self):
        self.manifest("composer.json", {"require": {TOOLKIT: "*"}})
        self.manifest("package.json", {"dependencies": {VUE_COMPONENTS: "*"}})
        for contents in (
            f"include {FRAGMENT}\nall:\n\t@echo app-default\n",
            f"all:\n\t@echo app-default\ninclude {FRAGMENT}\n",
        ):
            with self.subTest(contents=contents):
                self.write("Makefile", contents)
                self.assertIn("app-default", self.make().stdout)
                self.assertFalse(self.output.exists())

    def test_malformed_manifests_fail_explicitly(self):
        for name in ("composer.json", "composer.json.in", "package.json"):
            with self.subTest(name=name):
                self.write(name, "{")
                result = self.make("l10n-sources", success=False)
                self.assertIn("Cannot read", result.stderr)
                (self.app / name).unlink()

    def test_missing_toolkit_fragment_fails(self):
        self.manifest("composer.json", {"require": {TOOLKIT: "*"}})
        (self.app / f"vendor/{TOOLKIT}/tools/l10n.mk").unlink()
        self.assertIn("l10n.mk", self.make("l10n-sources", success=False).stderr)

    def test_extractor_failure_propagates(self):
        self.manifest("package.json", {"dependencies": {VUE_COMPONENTS: "*"}})
        result = self.make("l10n-sources", success=False,
                           env={**os.environ, "FAIL_EXTRACTOR": "1"})
        self.assertIn("23", result.stderr)
        self.assertFalse((self.output / "vue-components-strings.js").exists())


if __name__ == "__main__":
    unittest.main()
