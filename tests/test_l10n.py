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
        self.configure_scope("Scoped")
        self.write(
            "xpath",
            "#!/usr/bin/env python3\n"
            "import sys, xml.etree.ElementTree as ET\n"
            "print(ET.parse(sys.argv[-1]).getroot().findtext('scopednamespace', ''))\n",
        )
        (self.app / "xpath").chmod(0o755)
        self.write("Makefile", f"include {FRAGMENT}\nall:\n\t@echo app-default\n")
        # Stand-ins make inclusion and invocation observable without installing packages.
        self.install_toolkit("vendor")
        self.write(
            "npx",
            "#!/usr/bin/env python3\n"
            "import os, pathlib, sys\n"
            f"assert sys.argv[1:4] == ['--no-install', '{VUE_COMPONENTS}', "
            "'extract-l10n-strings']\n"
            "assert len(sys.argv) in (5, 6)\n"
            "assert pathlib.Path.cwd() == pathlib.Path(__file__).parent\n"
            "if len(sys.argv) == 6:\n"
            "    pathlib.Path('received-ignore').write_text(sys.argv[5])\n"
            "sys.exit(23) if os.environ.get('FAIL_EXTRACTOR') else None\n"
            "pathlib.Path(sys.argv[4]).write_text('vue-components')\n",
        )
        (self.app / "npx").chmod(0o755)

    def install_toolkit(self, vendor):
        self.write(
            f"{vendor}/{TOOLKIT}/tools/l10n.mk",
            'toolkit-l10n:\n'
            '\t@mkdir -p "$(dir $(APP_TOOLKIT_L10N_DEST))"\n'
            '\t@printf toolkit > "$(APP_TOOLKIT_L10N_DEST)"\n'
            '.PHONY: toolkit-l10n\n',
        )

    def configure_scope(self, namespace):
        self.write("appinfo/info.xml",
                   f"<info><scopednamespace>{namespace}</scopednamespace></info>")
        self.manifest(f"composer-{namespace.lower()}.json", {})

    def write(self, name, content):
        path = self.app / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def manifest(self, name, content):
        self.write(name, json.dumps(content))

    def make(self, *arguments, success=True, env=None):
        result = subprocess.run(
            ["make", "--no-print-directory", "-C", str(self.app),
             f"NPX={self.app / 'npx'}", f"XPATH={self.app / 'xpath'}", *arguments],
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

    def test_suffixed_composer_manifests_and_vendor_trees(self):
        (self.app / f"vendor/{TOOLKIT}/tools/l10n.mk").unlink()
        self.manifest("composer.json", {})
        for suffix in ("scoped", "wrapped", "custom"):
            self.configure_scope(suffix.title())
            self.install_toolkit(f"vendor-{suffix}")
            for template in ("", ".in"):
                for section in ("require", "require-dev"):
                    with self.subTest(suffix=suffix, template=template, section=section):
                        name = f"composer-{suffix}.json{template}"
                        self.manifest(name, {section: {TOOLKIT: "*"}})
                        self.make("l10n-sources")
                        destination = self.output / "toolkit-strings.php"
                        self.assertEqual(destination.read_text(), "toolkit")
                        destination.unlink()
                        (self.app / name).unlink()
                        self.manifest(f"composer-{suffix}.json", {})
            (self.app / f"vendor-{suffix}/{TOOLKIT}/tools/l10n.mk").unlink()

    def test_root_toolkit_takes_precedence_over_suffixed_manifests(self):
        self.manifest("composer.json", {"require": {TOOLKIT: "*"}})
        self.manifest("composer-scoped.json", {"require": {TOOLKIT: "*"}})
        self.manifest("composer-wrapped.json", {"require-dev": {TOOLKIT: "*"}})
        self.make("l10n-sources")
        self.assertEqual((self.output / "toolkit-strings.php").read_text(), "toolkit")

    def test_suffixed_manifests_without_dependency_do_not_enable_extraction(self):
        for suffix in ("scoped", "wrapped"):
            self.install_toolkit(f"vendor-{suffix}")
            self.manifest(f"composer-{suffix}.json", {"repositories": [{"url": TOOLKIT}]})
        self.make("l10n-sources")
        self.assertFalse(self.output.exists())

    def test_toolkit_directory_override(self):
        self.configure_scope("Wrapped")
        self.manifest("composer-wrapped.json", {"require": {TOOLKIT: "*"}})
        self.install_toolkit("custom-vendor")
        self.make("l10n-sources",
                  f"APP_TOOLKIT_DIR={self.app / 'custom-vendor' / TOOLKIT}")
        self.assertEqual((self.output / "toolkit-strings.php").read_text(), "toolkit")

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

    def test_vue_ignore_file_is_passed_when_present(self):
        self.manifest("package.json", {"dependencies": {VUE_COMPONENTS: "*"}})
        self.write(".l10nignore", "# exclusions\n")
        self.make("vue-components-l10n")
        self.assertEqual((self.app / "received-ignore").read_text(),
                         str(self.app / ".l10nignore"))

    def test_vue_ignore_override_and_disable(self):
        self.manifest("package.json", {"dependencies": {VUE_COMPONENTS: "*"}})
        self.write(".l10nignore", "# exclusions\n")
        custom = self.app / "ignore list"
        self.write("ignore list", "")
        self.make("vue-components-l10n", f"VUE_COMPONENTS_L10N_IGNORE={custom}")
        received = self.app / "received-ignore"
        self.assertEqual(received.read_text(), str(custom))
        received.unlink()
        self.make("vue-components-l10n", "VUE_COMPONENTS_L10N_IGNORE=")
        self.assertFalse(received.exists())

    def test_exclusion_targets_skip_undeclared_packages(self):
        self.make("l10n-ignore", "toolkit-l10n-ignore-candidates")
        self.assertFalse((self.app / ".l10nignore").exists())

    def test_vue_ignore_target_arguments_and_overrides(self):
        self.manifest("package.json", {"dependencies": {VUE_COMPONENTS: "*"}})
        self.write("node", "#!/usr/bin/env python3\n"
                   "import json, pathlib, sys\n"
                   "if sys.argv[1] == '-e': print('yes')\n"
                   "else: pathlib.Path('ignore-args').write_text(json.dumps(sys.argv[1:]))\n")
        (self.app / "node").chmod(0o755)
        self.make("l10n-ignore", f"NODE={self.app / 'node'}",
                  "L10N_VITE_CONFIG=custom config.ts",
                  f"L10N_IGNORE={self.app / 'custom ignore'}",
                  f"L10N_VUE_KEEP={self.app / 'keep list'}",
                  "L10N_VITE_MODES=production")
        arguments = json.loads((self.app / "ignore-args").read_text())
        self.assertEqual(Path(arguments[0]).name, "l10n-ignore.mjs")
        self.assertEqual(arguments[1:], [
            "vue", str(self.app), "custom config.ts", str(self.app / "custom ignore"),
            str(self.app / "keep list"), "production",
        ])

    def test_php_candidate_target_does_not_extract_or_write(self):
        self.manifest("composer.json", {"require": {TOOLKIT: "*"}})
        self.write(f"vendor/{TOOLKIT}/src/Unused.php", "<?php class Unused {}")
        result = self.make("toolkit-l10n-ignore-candidates")
        self.assertIn(f"{TOOLKIT}/src/Unused.php", result.stdout)
        self.assertFalse((self.app / ".l10nignore").exists())
        self.assertFalse(self.output.exists())

    def test_php_candidate_diff_uses_ignore_override(self):
        self.manifest("composer.json", {"require": {TOOLKIT: "*"}})
        self.write(f"vendor/{TOOLKIT}/src/Unused.php", "<?php class Unused {}")
        self.write(".l10nignore", f"vendor/{TOOLKIT}/src/Unused.php\n")
        custom = self.app / "custom ignore"
        contents = f"vendor-scoped/{TOOLKIT}/src/Removed.php\n"
        self.write("custom ignore", contents)
        result = self.make("toolkit-l10n-ignore-candidates", f"L10N_IGNORE={custom}")
        self.assertIn(f"# - {TOOLKIT}/src/Removed.php", result.stdout)
        self.assertIn(f"# + {TOOLKIT}/src/Unused.php", result.stdout)
        self.assertEqual(custom.read_text(), contents)

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
        for name in ("composer.json", "composer.json.in", "composer-scoped.json",
                     "composer-scoped.json.in", "package.json"):
            with self.subTest(name=name):
                self.write(name, "{")
                result = self.make("l10n-sources", success=False)
                self.assertIn("Cannot read", result.stderr)
                (self.app / name).unlink()
                self.manifest("composer-scoped.json", {})

    def test_unrelated_suffixed_manifest_is_ignored(self):
        self.write("composer-wrapped.json", "{")
        self.make("l10n-sources")
        self.assertFalse(self.output.exists())

    def test_scope_configuration_is_required(self):
        for contents in ("<info/>", "<info><scopednamespace/></info>", "<info>"):
            with self.subTest(contents=contents):
                self.write("appinfo/info.xml", contents)
                result = self.make("l10n-sources", success=False)
                self.assertIn("scopednamespace", result.stderr)
        (self.app / "appinfo/info.xml").unlink()
        self.assertIn("Cannot read scopednamespace",
                      self.make("l10n-sources", success=False).stderr)

    def test_matching_manifest_is_required_even_with_template(self):
        self.configure_scope("Wrapped")
        (self.app / "composer-wrapped.json").unlink()
        self.manifest("composer-wrapped.json.in", {})
        result = self.make("l10n-sources", success=False)
        self.assertIn("composer-wrapped.json is missing", result.stderr)

    def test_malformed_scoped_manifest_fails_even_with_root_toolkit(self):
        self.manifest("composer.json", {"require": {TOOLKIT: "*"}})
        self.write("composer-scoped.json", "{")
        result = self.make("l10n-sources", success=False)
        self.assertIn("Cannot read Composer manifests", result.stderr)

    def test_missing_toolkit_fragment_fails(self):
        self.manifest("composer.json", {"require": {TOOLKIT: "*"}})
        (self.app / f"vendor/{TOOLKIT}/tools/l10n.mk").unlink()
        for target in ("l10n-sources", "toolkit-l10n"):
            with self.subTest(target=target):
                result = self.make(target, success=False)
                self.assertIn("l10n.mk", result.stderr)
                self.assertFalse(self.output.exists())

    def test_missing_toolkit_does_not_block_unrelated_targets(self):
        for suffix in ("", "-wrapped"):
            with self.subTest(suffix=suffix):
                self.configure_scope("Wrapped")
                name = f"composer{suffix}.json"
                self.manifest(name, {"require": {TOOLKIT: "*"}})
                toolkit = self.app / f"vendor{suffix}/{TOOLKIT}/tools/l10n.mk"
                if toolkit.exists():
                    toolkit.unlink()
                self.write(
                    "Makefile",
                    f"include {FRAGMENT}\n"
                    "dev:\n\t@echo app-dev\n"
                    "realclean:\n\t@echo app-realclean\n",
                )
                self.assertIn("app-dev", self.make().stdout)
                self.assertIn("app-dev", self.make("dev").stdout)
                self.assertIn("app-realclean", self.make("realclean").stdout)
                self.make("-n", "dev")
                self.assertFalse(self.output.exists())
                (self.app / name).unlink()

    def test_toolkit_installed_during_same_make_invocation(self):
        self.configure_scope("Wrapped")
        self.manifest("composer-wrapped.json", {"require": {TOOLKIT: "*"}})
        source = self.app / f"vendor/{TOOLKIT}/tools/l10n.mk"
        destination = self.app / f"vendor-wrapped/{TOOLKIT}/tools/l10n.mk"
        self.write(
            "Makefile",
            f"include {FRAGMENT}\n"
            "toolkit-l10n: install-toolkit\n"
            "install-toolkit:\n"
            f'\t@mkdir -p "{destination.parent}"\n'
            f'\t@cp "{source}" "{destination}"\n',
        )
        self.make("-j2", "l10n-sources")
        self.assertEqual((self.output / "toolkit-strings.php").read_text(), "toolkit")

    def test_toolkit_submake_receives_makefile_overrides(self):
        self.manifest("composer.json", {"require": {TOOLKIT: "*"}})
        self.install_toolkit("custom-vendor")
        self.write(
            "Makefile",
            f"APP_TOOLKIT_DIR := {self.app / 'custom-vendor' / TOOLKIT}\n"
            f"L10N_SOURCES_DIR := {self.app / 'custom-catalogues'}\n"
            f"L10N_IGNORE := {self.app / 'custom ignore'}\n"
            "PHP := php -d memory_limit=128M\n"
            f"include {FRAGMENT}\n",
        )
        self.write(
            f"custom-vendor/{TOOLKIT}/tools/l10n.mk",
            "toolkit-l10n:\n"
            '\t@test "$(ABSSRCDIR)" = "$(CURDIR)"\n'
            '\t@test "$(APP_TOOLKIT_DIR)" = "$(CURDIR)/custom-vendor/'
            f'{TOOLKIT}"\n'
            '\t@test "$(PHP)" = "php -d memory_limit=128M"\n'
            f'\t@test "$(APP_TOOLKIT_L10N_IGNORE)" = "{self.app}/custom ignore"\n'
            '\t@mkdir -p "$(dir $(APP_TOOLKIT_L10N_DEST))"\n'
            '\t@printf toolkit > "$(APP_TOOLKIT_L10N_DEST)"\n',
        )
        self.make("l10n-sources")
        self.assertEqual(
            (self.app / "custom-catalogues/toolkit-strings.php").read_text(),
            "toolkit",
        )

    def test_toolkit_extractor_failure_propagates(self):
        self.manifest("composer.json", {"require": {TOOLKIT: "*"}})
        self.write(f"vendor/{TOOLKIT}/tools/l10n.mk", "toolkit-l10n:\n\t@exit 23\n")
        result = self.make("l10n-sources", success=False)
        self.assertIn("23", result.stderr)
        self.assertFalse(self.output.exists())

    def test_extractor_failure_propagates(self):
        self.manifest("package.json", {"dependencies": {VUE_COMPONENTS: "*"}})
        result = self.make("l10n-sources", success=False,
                           env={**os.environ, "FAIL_EXTRACTOR": "1"})
        self.assertIn("23", result.stderr)
        self.assertFalse((self.output / "vue-components-strings.js").exists())


if __name__ == "__main__":
    unittest.main()
