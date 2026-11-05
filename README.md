# nextcloud-app-build-system
Kind of library of Makefile fragments and such. Intended as git sub-repo.

## Tests

Run the Makefile integration tests from the repository root using Python's
standard-library `unittest` runner:

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
```

The tests require Python 3, GNU Make, PHP, Node.js 16.9 or newer, and `patch`.
They create temporary app fixtures and provide stand-ins for `xpath`, the
toolkit, and the Vue extractor; no Nextcloud installation, Composer/npm
dependency installation, or additional Python packages are needed.

The GitHub Actions workflow in `.github/workflows/tests.yml` runs the same
command on pushes to `main` and on pull requests, and can also be started manually.
It uses the tools preinstalled on the Ubuntu 24.04 hosted runner.

## JavaScript bundler targets

`makefile/npm.mk` uses `BUNDLER_DEPS` for application-specific build
prerequisites, `BUNDLER_TARGETS` for generated assets (default:
`$(ABSSRCDIR)/js/asset-meta.json`), and `make bundler-clean` to remove generated
files from `js/` and `css/`. Set variables before including the fragment.
`npm-dev` and `npm-build` still run the application's `dev` and `build`
npm scripts. Set `BUNDLER_CONFIG` to the actual configuration file; its
legacy default remains `webpack.config.js` for apps that do not override it.

Existing apps can update the shared library without changing their Makefiles:
`WEBPACK_DEPS` is still accepted and exposes the resolved `BUNDLER_DEPS`,
`WEBPACK_TARGETS` exposes `BUNDLER_TARGETS`, and `webpack-clean` remains a
compatibility alias for `bundler-clean`. New code should use the neutral names.

The default-branch Makefiles of all eight consuming apps were checked.
All already set `BUNDLER_CONFIG = vite.config.ts`; no config rename is needed.
To migrate their remaining names:

| App | Makefile changes |
| --- | --- |
| bav | Rename `WEBPACK_DEPS` to `BUNDLER_DEPS`; use `bundler-clean` in `mostlyclean`. |
| cafevdb | Rename `WEBPACK_DEPS` to `BUNDLER_DEPS`, including the JSDoc and TypeDoc prerequisites. |
| cafevdbmembers | Rename `WEBPACK_DEPS` to `BUNDLER_DEPS`; use `bundler-clean` in `mostlyclean`. |
| dokuwiki | Rename `WEBPACK_DEPS` to `BUNDLER_DEPS`; use `bundler-clean` in `mostlyclean`. |
| files_archive | Rename `WEBPACK_DEPS` to `BUNDLER_DEPS`; use `bundler-clean` in `mostlyclean`. |
| mail_roundcube | Rename `WEBPACK_DEPS` to `BUNDLER_DEPS`; use `bundler-clean` in `mostlyclean`. |
| pdf_downloader | Rename `WEBPACK_DEPS` to `BUNDLER_DEPS`; use `bundler-clean` in `mostlyclean`. |
| redaxo | Rename `WEBPACK_DEPS` to `BUNDLER_DEPS`; use `bundler-clean` in `mostlyclean`. |

## Consuming app repositories

The consuming app names used in this documentation map to these GitHub
repositories:

| App | GitHub repository |
| --- | --- |
| bav | [rotdrop/nextcloud-app-bav](https://github.com/rotdrop/nextcloud-app-bav) |
| cafevdb | [rotdrop/cafevdb](https://github.com/rotdrop/cafevdb) |
| cafevdbmembers | [rotdrop/cafevdb-members](https://github.com/rotdrop/cafevdb-members) |
| dokuwiki | [rotdrop/nextcloud-app-dokuwiki](https://github.com/rotdrop/nextcloud-app-dokuwiki) |
| files_archive | [rotdrop/nextcloud-app-files-archive](https://github.com/rotdrop/nextcloud-app-files-archive) |
| mail_roundcube | [rotdrop/nextcloud-roundcube](https://github.com/rotdrop/nextcloud-roundcube) |
| pdf_downloader | [rotdrop/nextcloud-app-pdf-downloader](https://github.com/rotdrop/nextcloud-app-pdf-downloader) |
| redaxo | [rotdrop/nextcloud-app-redaxo](https://github.com/rotdrop/nextcloud-app-redaxo) |

## Scoped Composer configuration

Configure `<scopednamespace>` in the application's `appinfo/info.xml`, for
example `<scopednamespace>Wrapped</scopednamespace>`. The setup and translation
fragments derive `SCOPED_NAMESPACE_POSTFIX` from this value and
`SCOPED_VENDOR_SUFFIX` from its lowercase form. Provide the corresponding
`composer-wrapped.json` and install its dependencies into `vendor-wrapped`.
No namespace or suffix variables need to be set in the consuming Makefile.
Missing or empty XML configuration and a missing matching Composer manifest
are errors; a `.json.in` template alone does not satisfy this requirement.
The fragments require the `xpath` binary.

### Building the scoped vendor tree

After `setup.mk` and `composer.mk`, include the shared build rules:

```makefile
include $(DEV_LIB_DIR)/makefile/composer.mk
include $(DEV_LIB_DIR)/makefile/namespace-wrapper.mk

dev-setup: namespace-wrapper
```

`make namespace-wrapper` installs PHP-Scoper via the Composer bin plugin,
installs and updates `composer-$(SCOPED_VENDOR_SUFFIX).json` in `$(BUILDDIR)`,
and scopes its vendor tree into the application directory. Keep the app's
`scoper.inc.php` and matching Composer manifest; its `config.vendor-dir` and
the scoper Finder must use `vendor-$(SCOPED_VENDOR_SUFFIX)`.
The fragment requires the existing `COMPOSER`, `COMPOSER_OPTIONS`, `BUILDDIR`,
`ABSSRCDIR`, and `DEV_LIB_DIR` settings. `PHP_SCOPER` and `MAKEFILE_DEP` default
to the bin-plugin executable and `Makefile`, respectively.

The final scoping rule preserves cafevdb's workarounds: copy `bin` (including
symlinks) from the build tree when present, restore executable permissions,
regenerate Composer's autoload maps, and patch file identifiers when the
generated autoloader contains `filesToLoad`. Apps without Composer binaries
or file autoloads are supported. The include preserves the app's default goal.
It also provides `php-scoper-install`, the suffixed vendor/autoload targets,
and `composer-$(SCOPED_VENDOR_SUFFIX)-suggest`, attached to `composer-suggest`.

For **cafevdb on nextcloud35**, retain its `WRAPPER_GIT_DEPENDENCIES` list
and set this before the include:

```makefile
SCOPED_VENDOR_LINK_DIRS = 3rdparty vendor
include $(DEV_LIB_DIR)/makefile/namespace-wrapper.mk
```

The fragment then maintains `wrapper-build-hash` and rebuilds when a listed
repository's HEAD changes. Keep the app-specific `namespace-wrapper-patch`
and `namespace-wrapper-unpatch` rules and their namespace/file lists.

For **nextcloud-app-dokuwiki**, preserve its production-only update:

```makefile
SCOPED_COMPOSER_UPDATE_OPTIONS = --no-dev
include $(DEV_LIB_DIR)/makefile/namespace-wrapper.mk
```

In either app, replace the local PHP-Scoper installation, scoped Composer
lock/build/autoload, scoped vendor/autoload, and `namespace-wrapper` rules
with the include. For cafevdb also remove the local hash and
`composer-wrapped-suggest` rules; the fragment supplies them.
Keep app-specific translation extraction separate (or use `l10n.mk` below).
`SCOPED_VENDOR_LINK_DIRS` defaults to `vendor`; its entries are app-relative
directories symlinked into the build directory for Composer path repositories.
`SCOPED_COMPOSER_UPDATE_OPTIONS` defaults to empty and augments
`COMPOSER_OPTIONS` only for the scoped update command.

## Package translations

Include `makefile/l10n.mk` in the application's Makefile:

```makefile
ABSSRCDIR = $(CURDIR)
DEV_LIB_DIR = $(ABSSRCDIR)/dev-scripts/lib
include $(DEV_LIB_DIR)/makefile/l10n.mk
```

Run `make l10n-sources` before creating POT files, or add `l10n-sources` as
a prerequisite of the application's POT target. It generates
`l10n-sources/toolkit-strings.php` and
`l10n-sources/vue-components-strings.js`. Set `L10N_SOURCES_DIR` before the
include to put both files in another directory. Individual destinations can
be overridden with `APP_TOOLKIT_L10N_DEST` and `VUE_COMPONENTS_L10N_DEST`.
Use absolute paths for destination overrides when invoking make outside
the app directory.

The fragment invokes the installed toolkit's `tools/l10n.mk` only when
`composer.json` or `composer-$(SCOPED_VENDOR_SUFFIX).json`
(or either of their `.in` templates) declares
`rotdrop/nextcloud-app-toolkit` in `require` or `require-dev`.
Toolkit paths default to the matching vendor tree (`vendor` or
`vendor-$(SCOPED_VENDOR_SUFFIX)`). If multiple manifests declare the toolkit,
the root manifest/template takes precedence. Unrelated suffixed manifests
are not scanned.
It runs the Vue extractor only when `package.json` declares
`@rotdrop/nextcloud-vue-components` in `dependencies`, `devDependencies`,
`optionalDependencies`, or `peerDependencies`. Repository URLs and stale
installed packages do not enable extraction. Undeclared packages make
the corresponding targets no-ops; malformed manifests are errors.

Install the declared packages before running translation extraction.
The toolkit fragment is loaded by a sub-make only when `toolkit-l10n` runs,
so unrelated targets such as `dev` and `realclean` work without an installed
toolkit. Extraction still fails if the toolkit is missing; a build that
installs dependencies and extracts translations in one invocation must order
installation before extraction using prerequisites. Override `APP_TOOLKIT_DIR`
for a nonstandard Composer vendor directory. The Vue command runs from the
app directory using `npx --no-install` to avoid implicit package downloads.
`PHP`, `NODE`, and `NPX` can be overridden. The individual targets `toolkit-l10n` and
`vue-components-l10n` are also available. Including the fragment does not
change the application's default goal.

### Excluding unused package files

For Vite apps, run `make l10n-ignore` (also named
`vue-components-l10n-ignore`) explicitly before `make l10n-sources`. It
builds the app's Vite configuration in both development and production modes,
without emitting build assets or emptying output directories, and updates
only a marked generated section in `.l10nignore`. Existing handwritten entries
are preserved. The app must have Vite installed; its plugins still run,
including any plugin-specific side effects. Vite loads its configuration
normally, including TypeScript configs and async config factories.

Set `L10N_VITE_CONFIG` for another config file (the default is Vite's normal
auto-discovery) and `L10N_VITE_MODES`
for another space-separated list of modes. The config must cover **all**
runtime entry points and feature variants used by the app. Apps needing custom
environment switches should provide a wrapper config covering all relevant
entries or modes. This integration uses Vite's build API, not an import scanner,
and supports Vite's Rollup and Rolldown backends.

Only library source files absent from every analyzed module graph are excluded.
Lazy chunks, transitive imports, and even parsed
but tree-shaken modules are retained deliberately; barrel imports can therefore
keep more translations than strictly necessary. Compilation errors, warnings,
unresolved runtime dynamic imports (including `@vite-ignore` imports), and
directly externalized library modules abort generation without changing the
ignore file. This is static
build analysis, not proof of runtime non-use: custom loaders, external mappings,
or runtime discovery that bypass Vite's dependency tracking require review.
Watched loader inputs are also retained when exposed by Rollup; Rolldown does
not currently expose those inputs, so files read only by plugins need keep
entries.

For files used outside those graphs, add exact paths such as
`node_modules/@rotdrop/nextcloud-vue-components/lib/components/FilePrefixPicker.vue`
to `.l10nkeep` (override with `L10N_VUE_KEEP`). Blank lines and `#` comments are
allowed; globs are not. Keep entries prevent generated exclusions but do not
override handwritten `.l10nignore` exclusions.

`L10N_IGNORE` overrides the ignore file path. The Vue extractor automatically
receives it when it exists; set `VUE_COMPONENTS_L10N_IGNORE` to override or to
empty to disable filtering. Regenerate exclusions after changing application
imports, build configurations, or package versions, then regenerate and commit
the catalogues. Generation is intentionally not an automatic prerequisite of
translation extraction; run the two commands sequentially, not as parallel make
goals. Review generated exclusions before committing.

For PHP, `make toolkit-l10n-ignore-candidates` prints a review-only list of
toolkit files whose basenames are not mentioned in app PHP/XML/JSON/template
sources or other toolkit PHP files. Vendor trees and generated catalogue
directories are skipped. This is a deliberately simple heuristic, not PHP
reachability analysis: aliases, dynamic references, service discovery, and files
declaring functions or multiple classes need manual inspection. After the list,
it prints a commented set diff against toolkit PHP entries in `.l10nignore`
(or `L10N_IGNORE`): `# +` marks new candidates, and `# -` marks existing
exclusions no longer suggested, including paths to removed files. Entries are
compared without leading directories such as `vendor/` or `vendor-scoped/`;
duplicates, blank lines, comments, and unrelated entries do not affect the diff.
A missing ignore file is treated as an empty list; other read errors fail.
The diff is advisory, not a recommendation to undo deliberate manual choices.
It never writes
the ignore file and never changes toolkit extraction. Developers must hand-tune
any PHP exclusions and configure the toolkit's own ignore support separately.
At present, the upstream toolkit extractor incorrectly recognizes
`rotdrop/nextcloud-vue-components/src/` rather than its own package prefix; that
needs fixing upstream before the toolkit paths printed here can be used.

`makefile/setup.mk` also uses the XML-derived suffix for the toolkit's
PHP-to-TypeScript source directory. Its
`apply-scoped-autoload-patch` helper accepts the vendor directory as its
argument; the Composer patch uses relative paths and works with any suffix.

Commit the generated catalogues on each translated branch so the translation
service can scan them; do not import or execute them, or exclude them via
`.l10nignore`. Nextcloud's current Transifex bot uses shallow Git clones and
runs `translationtool.phar create-pot-files` on the checked-out files
(see its [app translation script](https://github.com/nextcloud/docker-ci/blob/cb72dcd957314fc59eca1a9890dafbe971db1e37/translations-app/handleAppTranslations.sh#L109-L139)).
It does not run this fragment, so regenerate and commit the catalogues when
updating the packages.

The output directory can be marked `export-ignore` in the application's
`.gitattributes` to omit it from Git-generated release archives: this does
not affect the bot's clones. Do not use that exclusion if another translation
pipeline extracts strings from `git archive` output or GitHub source archives
rather than a checkout.

## PHP to TypeScript

The converter is now provided by the Composer library
`rotdrop/php-to-typescript`. Applications using `makefile/ts-types-files.mk`
must install it in their own `vendor-bin/php-to-typescript/` environment,
managed by `bamarni/composer-bin-plugin`. The updated Makefile fragment uses
the Composer package.

### Application setup

Enable `bamarni/composer-bin-plugin` in the application's root Composer
manifest and install the development dependencies:

```sh
composer config allow-plugins.bamarni/composer-bin-plugin true
composer require --dev bamarni/composer-bin-plugin:^1.8
```

In `vendor-bin/php-to-typescript/composer.json`, declare the converter
dependency and, until it is available on Packagist, its VCS repository:

```json
{
  "require-dev": {
    "rotdrop/php-to-typescript": "*@dev"
  },
  "repositories": [
    {
      "type": "vcs",
      "url": "https://github.com/rotdrop/php-to-typescript-"
    }
  ]
}
```

The repository name currently has a trailing hyphen; the Composer package
name does not. Replace `*@dev` with a release constraint when available.
Run `composer bin php-to-typescript install` from the application root.
Commit the bin environment's manifest and lock file, not its `vendor/` tree.
The Makefile installs this environment if its autoloader is missing or its
manifest/lock file changes. It also tracks the installed package's manifest
and all nested PHP sources as generation dependencies.

### Application launcher migration

The package is a library, not a standalone executable. Keep
`TYPESCRIPT_CONVERTER` pointing at the application's existing PHP launcher
and retain its constructor options, exclusions, collector choices, and
Nextcloud/toolkit bootstrap. Update the launcher as follows:

- Load `$appDir . '/vendor-bin/php-to-typescript/vendor/autoload.php'`
  instead of the old `vendor-bin/typescript-transformer/` autoloader.
- Remove the manual `addPsr4()` mapping of
  `OCA\RotDrop\DevScripts\PhpToTypeScript` to the bundled
  `lib/scripts/php-to-typescript/` directory. Composer now supplies it.
- Retain application and toolkit autoloaders and namespace mappings.
  Imports remain unchanged, including the `Collectors` and `Attributes`
  subnamespaces (for example,
  `OCA\RotDrop\DevScripts\PhpToTypeScript\Collectors\DTOCollector`).
- Pass the application's development-scripts directory as
  `devScriptsFolder`, not the installed package's directory.

The shared `scripts/vendor/autoload.php` bootstrap remains supported: the
Makefile still installs `scripts/composer.json`, including its Nextcloud OCP
dependency. It no longer deletes that environment or its lock files before
every generation.

Once the launcher has migrated, remove the old
`vendor-bin/typescript-transformer/` environment if nothing else uses it.
Spatie's transformer and Symfony Finder are dependencies of the new package.
Compare generated declarations and modules in the consuming application,
especially when replacing a fork of Spatie's transformer. Database metadata
generation still requires the existing Nextcloud/CAFEVDB integration; apps
without it should retain their explicit non-database collectors.

## Syncing the submodule: `dev-lib-sync`

`makefile/dev-lib-sync.mk` (included by `makefile/setup.mk`) provides the
manually invoked target `make dev-lib-sync` for local development. It is not
a prerequisite of any other target and does not become the default goal.

It fetches `origin` in `$(DEV_LIB_DIR)` and moves the submodule to
`origin/main`. If the submodule pointer changed, only that path is committed
(`Update dev-scripts/lib to <sha>`, other staged or unstaged work is left
alone) and pushed to the *currently checked-out branch* of the application
(`git push origin HEAD:refs/heads/<branch>`, never forced, no other refs).
It does nothing if already up to date, and refuses on a detached application
HEAD, uncommitted changes in the submodule, or submodule commits not in
`origin/main`.
