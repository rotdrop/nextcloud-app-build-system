import json
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "l10n-ignore.mjs"
PACKAGE = "@rotdrop/nextcloud-vue-components"
BEGIN = "# BEGIN generated nextcloud-vue-components exclusions"
END = "# END generated nextcloud-vue-components exclusions"

# A small Vite API double keeps the repository's tests dependency-free.
VITE = r"""
import fs from 'node:fs'
import assert from 'node:assert/strict'
import { pathToFileURL } from 'node:url'
export const createLogger = () => ({ error() {} })
export async function build(options) {
  assert.equal(options.build.write, false)
  assert.equal(options.build.emptyOutDir, false)
  assert.equal(options.build.watch, null)
  const loaded = await import(pathToFileURL(options.configFile || 'vite.config.cjs').href)
  const config = await (typeof loaded.default === 'function'
    ? loaded.default({ mode: options.mode, command: 'build' }) : loaded.default)
  const context = {
    getModuleIds: () => (config.modules || []).map(m => m.id),
    getModuleInfo: id => config.modules.find(m => m.id === id),
    getWatchFiles: () => config.dependencies || [],
    parse: code => JSON.parse(code),
  }
  for (const plugin of options.plugins) {
    plugin.configResolved({ build: { ...options.build, ...(config.build || {}) } })
    for (const id of config.transformed || []) plugin.transform('', id)
    if (config.warnings) {
      plugin.onLog.handler('warn', { message: 'Compilation diagnostics' })
    }
    if (config.loggerWarning) options.customLogger.warn('Logger warning')
    if (config.failure || config.errors) throw new Error('Build failed')
    plugin.buildEnd.call(context)
  }
  fs.appendFileSync('builds.jsonl', JSON.stringify({ mode: options.mode }) + '\n')
}
"""


class L10nIgnoreTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.app = Path(temporary.name)
        self.library = self.app / "node_modules" / PACKAGE / "lib"
        self.write("node_modules/vite/package.json",
                   '{"type":"module","exports":"./index.mjs"}')
        self.write("node_modules/vite/index.mjs", VITE)
        self.write("package.json", "{}")
        for name in ("Used.vue", "Unused.vue", "Lazy.ts", "Development.js",
                     "Production.js", "Watched.js", "Types.d.ts", "style.scss"):
            self.write(f"node_modules/{PACKAGE}/lib/{name}", "")
        self.write("vite.config.cjs", "module.exports = {}")

    def write(self, name, contents):
        path = self.app / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
        return path

    def run_script(self, command="vue", success=True, modes=None):
        arguments = (["vite.config.cjs", ".l10nignore", ".l10nkeep",
                      *(modes or ["development", "production"])]
                     if command == "vue" else ["vendor/rotdrop/nextcloud-app-toolkit"])
        result = subprocess.run(
            ["node", str(SCRIPT), command, str(self.app), *arguments],
            text=True, capture_output=True,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def config(self, expression):
        self.write("vite.config.cjs", f"module.exports = {expression}")

    def resource(self, name):
        return str(self.library / name)

    def exclusions(self):
        return (self.app / ".l10nignore").read_text()

    def test_graph_union_across_async_factories_modes_and_entries(self):
        paths = {name: self.resource(name) for name in (
            "Used.vue", "Lazy.ts", "Development.js", "Production.js", "Watched.js")}
        self.config(
            "async (env) => {"
            "require('node:assert').equal(env.command, 'build');"
            f"const paths = {json.dumps(paths)};"
            "return { modules: ["
            "{ id: paths['Used.vue'] + '?vue&type=script' },"
            "{ id: paths['Lazy.ts'] },"
            "{ id: paths[env.mode === 'development' ? 'Development.js' : 'Production.js'] }"
            "], dependencies: [paths['Watched.js']] }; }"
        )
        self.run_script()
        self.assertEqual(self.exclusions(),
                         f"{BEGIN}\nnode_modules/{PACKAGE}/lib/Unused.vue\n{END}\n")
        builds = [json.loads(line) for line in (self.app / "builds.jsonl").read_text().splitlines()]
        self.assertEqual([build["mode"] for build in builds],
                         ["development", "production"])

    def test_preserves_manual_entries_and_replaces_stale_exclusions(self):
        manual = "# handwritten\nsome/app/file.php\n"
        self.write(".l10nignore", f"{manual}{BEGIN}\nold-entry\n{END}\n# after\n")
        self.config(json.dumps({"modules": [{"id": self.resource("Used.vue")}]}))
        self.run_script()
        first = self.exclusions()
        self.assertTrue(first.startswith(manual + BEGIN))
        self.assertTrue(first.endswith(f"{END}\n# after\n"))
        self.assertNotIn("old-entry", first)
        self.assertNotIn("/Used.vue", first)
        self.run_script()
        self.assertEqual(self.exclusions(), first)

    def test_keep_entries_prevent_generated_exclusion_only(self):
        entry = f"node_modules/{PACKAGE}/lib/Unused.vue"
        self.write(".l10nignore", f"# manual override\n{entry}\n")
        self.write(".l10nkeep", f"# keep\n\n  {entry}  \n")
        self.run_script()
        self.assertEqual(self.exclusions().count(entry), 1)

    def test_diagnostics_and_externalization_leave_ignore_unchanged(self):
        for config in (
            {"failure": True}, {"errors": True}, {"warnings": True},
            {"loggerWarning": True},
            {"modules": [{"id": self.resource("Used.vue"),
                          "code": json.dumps({"import": {"type": "ImportExpression",
                                                         "source": {"type": "Identifier"}}})}]},
            {"modules": [{"isExternal": True, "id": PACKAGE}]},
            {"modules": [{"code": None, "id": PACKAGE}]},
            {"modules": [{"id": self.resource("Used.vue"), "importedIds": [PACKAGE]}]},
            {"modules": [{"isExternal": True, "id": self.resource("Used.vue")}]},
            {"build": {"write": True}},
        ):
            with self.subTest(config=config):
                self.config(json.dumps(config))
                self.write(".l10nignore", "manual\n")
                self.run_script(success=False)
                self.assertEqual(self.exclusions(), "manual\n")

    def test_failure_does_not_create_ignore_file(self):
        self.config("() => { throw new Error('Bad config') }")
        self.assertIn("Bad config", self.run_script(success=False).stderr)
        self.assertFalse((self.app / ".l10nignore").exists())

    def test_later_mode_failure_preserves_existing_exclusions(self):
        self.write(".l10nignore", "manual\n")
        self.config("({ mode }) => ({ warnings: mode === 'production' })")
        self.run_script(success=False)
        self.assertEqual(self.exclusions(), "manual\n")

    def test_build_modes_do_not_inherit_config_environment_mutations(self):
        self.config("() => { require('node:assert').equal(process.env.L10N_TEST_MODE_LEAK, undefined);"
                    "process.env.L10N_TEST_MODE_LEAK = 'previous mode'; return {}; }")
        self.run_script()

    def test_invalid_keep_entries_fail_without_overwrite(self):
        for entry in ("src/component.vue", f"{PACKAGE}/lib/Missing.vue",
                      f"{PACKAGE}/lib/../../vite/index.mjs"):
            with self.subTest(entry=entry):
                self.write(".l10nignore", "manual\n")
                self.write(".l10nkeep", entry)
                self.run_script(success=False)
                self.assertEqual(self.exclusions(), "manual\n")

    def test_malformed_markers_fail_before_building(self):
        for contents in (BEGIN, END, f"{END}\n{BEGIN}",
                         f"{BEGIN}\n{END}\n{BEGIN}\n{END}"):
            with self.subTest(contents=contents):
                self.write(".l10nignore", contents)
                self.run_script(success=False)
                self.assertEqual(self.exclusions(), contents)
                self.assertFalse((self.app / "builds.jsonl").exists())

    def test_symlink_sources_rejected(self):
        (self.library / "Linked.vue").symlink_to(self.library / "Used.vue")
        self.assertIn("symlink", self.run_script(success=False).stderr)
        self.assertFalse((self.app / ".l10nignore").exists())

    def test_esm_config_and_custom_mode(self):
        self.write("config.mjs", "export default Promise.resolve({})")
        self.write("vite.config.cjs", "module.exports = import('./config.mjs').then(m => m.default)")
        self.run_script(modes=["testing"])
        self.assertEqual(json.loads((self.app / "builds.jsonl").read_text()), {"mode": "testing"})

    def test_transform_inputs_and_virtual_modules(self):
        self.config(json.dumps({
            "transformed": [self.resource("Used.vue")],
            "modules": [{"id": "\0virtual-module"}],
        }))
        self.run_script()
        self.assertNotIn("/Used.vue", self.exclusions())

    def test_php_report_is_manual_and_conservative(self):
        root = "vendor/rotdrop/nextcloud-app-toolkit/src"
        self.write(f"{root}/Used.php", "<?php class Used {}")
        self.write(f"{root}/Transitive.php", "<?php class Transitive {}")
        self.write(f"{root}/Unused.php", "<?php class Unused {}")
        self.write(f"{root}/Referer.php", "<?php class Referer extends Transitive {}")
        self.write("lib/App.php", "<?php use OCA\\RotDrop\\Toolkit\\Used as Alias; new Alias();")
        self.write("node_modules/irrelevant/file.php", "<?php new Unused();")
        self.write("vendor-scoped/irrelevant/file.php", "<?php new Unused();")
        self.write(".l10nignore", "manual\n")
        result = self.run_script("php-candidates")
        entries = [line for line in result.stdout.splitlines() if not line.startswith("#")]
        self.assertEqual(entries, [
            "rotdrop/nextcloud-app-toolkit/src/Referer.php",
            "rotdrop/nextcloud-app-toolkit/src/Unused.php",
        ])
        self.assertEqual(self.exclusions(), "manual\n")

    def test_missing_php_package_fails(self):
        self.assertIn("ENOENT", self.run_script("php-candidates", success=False).stderr)

    def test_php_diff_normalizes_entries_and_reports_additions_and_removals(self):
        prefix = "rotdrop/nextcloud-app-toolkit/src"
        self.write(f"vendor/{prefix}/Existing.php", "<?php class Existing {}")
        self.write(f"vendor/{prefix}/New.php", "<?php class New {}")
        self.write(f"vendor/{prefix}/Used.php", "<?php class Used {}")
        self.write("lib/App.php", "<?php new Used();")
        contents = (
            f"# exclusions\r\n\r\n  vendor-scoped/{prefix}/Existing.php  \r\n"
            f"{prefix}/Existing.php\r\nvendor/{prefix}/Used.php\r\n"
            f"/old/vendor/{prefix}/Deleted.php\r\n"
            "node_modules/@rotdrop/nextcloud-vue-components/lib/Unused.vue\r\n"
            "src/Unrelated.php\r\n"
        ).encode()
        ignore = self.app / ".l10nignore"
        ignore.write_bytes(contents)
        result = self.run_script("php-candidates")
        diff = [line for line in result.stdout.splitlines()
                if line.startswith(("# + ", "# - "))]
        self.assertEqual(diff, [
            f"# - {prefix}/Deleted.php",
            f"# - {prefix}/Used.php",
            f"# + {prefix}/New.php",
        ])
        self.assertEqual(ignore.read_bytes(), contents)

    def test_php_diff_missing_ignore_and_no_differences(self):
        entry = "rotdrop/nextcloud-app-toolkit/src/Unused.php"
        self.write(f"vendor/{entry}", "<?php class Unused {}")
        result = self.run_script("php-candidates")
        self.assertIn(f"# + {entry}", result.stdout)
        self.assertFalse((self.app / ".l10nignore").exists())
        self.write(".l10nignore", f"vendor/{entry}\n")
        result = self.run_script("php-candidates")
        self.assertIn("# No differences.", result.stdout)
        self.assertNotIn(f"# + {entry}", result.stdout)

    def test_php_diff_unreadable_ignore_fails(self):
        self.write("vendor/rotdrop/nextcloud-app-toolkit/src/Unused.php", "<?php")
        (self.app / ".l10nignore").mkdir()
        result = self.run_script("php-candidates", success=False)
        self.assertIn("EISDIR", result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
