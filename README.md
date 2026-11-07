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
npm scripts. Switching build flavour clears only these bundler outputs, leaving
other generated build inputs intact. Set `BUNDLER_CONFIG` to the actual
configuration file; its legacy default remains `webpack.config.js` for apps
that do not override it.

`make commit-package-lock` commits a modified `package-lock.json` (only that
file) with the message `chore(deps): update package-lock.json` and pushes it;
it does nothing if the file is unchanged.

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

## Shared app Makefile: `makefile/app.mk`

`makefile/app.mk` contains everything the app Makefiles used to duplicate:
tool detection and guards, the `APPSTORE_*` variables, appstore packaging
and signing, `clean`/`distclean`/`mostlyclean`/`realclean`, tests,
`phpcs`/`phpmd` (with auto-install rules), `tide` and `release`. An app
Makefile shrinks to its hooks plus the include:

```make
SRCDIR = .
ABSSRCDIR = $(CURDIR)
DEV_LIB_DIR = $(ABSSRCDIR)/dev-scripts/lib

APP_BUILD_FLAVOUR_FIRST = 1
APP_NOTIFICATION_API = 1
APPSTORE_FILES_EXTRA = contrib

include $(DEV_LIB_DIR)/makefile/app.mk
```

Hooks must be set before the include. The complete list is documented in the
header of `app.mk`: `APP_DEV_SETUP_DEPS`, `APP_REQUIRED_TOOLS`,
`APP_BUILD_FLAVOUR_FIRST`, `APP_NOTIFICATION_API`, `APP_PHP_DIRS`,
`APP_MOSTLYCLEAN_DEPS`/`APP_MOSTLYCLEAN_FILES`, `APPSTORE_FILES`,
`APPSTORE_FILES_EXTRA`, `APPSTORE_COPY_HOOK`, `APPSTORE_COMPOSER_ARGS`,
`JS_FILES_EXTRA`, `TS_PHP_SOURCE_DIRS`, `L10N_VITE_CONFIG`, `RELEASE_SCRIPT`.

`wget` is not required by default; apps needing it set
`APP_REQUIRED_TOOLS = WGET` before the include.

### Example: app-specific build steps via hooks

App-specific pipelines stay in the app. This is the pdf_downloader
DejaVu/TCPDF font pipeline (tidied up) as it can be written in the app's own
Makefile fragment using the generic hooks `APP_REQUIRED_TOOLS`,
`dev-setup` prerequisites, `APP_MOSTLYCLEAN_FILES` and `APPSTORE_COPY_HOOK`.
The hook variables are set before the include of `app.mk`, the rules follow it:

```make
CONFIG_DIR = ./config
FONTS_LIST_FILE = $(CONFIG_DIR)/fonts-list.json

APP_REQUIRED_TOOLS = WGET
APP_MOSTLYCLEAN_FILES = stamp.tcpdf-fonts stamp.tcpdf-dejavu-fonts $(FONTS_LIST_FILE)
APPSTORE_COPY_HOOK = appstore-copy-fonts

include $(DEV_LIB_DIR)/makefile/app.mk

DEJAVU_ARCHIVE_BASE ?= dejavu-fonts-ttf
DEJAVU_ARCHIVE_FORMAT ?= tar.bz2
DEJAVU_VERSION ?= 2.37
DEJAVU_BASEURL ?= https://sourceforge.net/projects/dejavu/files/dejavu
DEJAVU_ARCHIVE ?= $(DEJAVU_ARCHIVE_BASE)-$(DEJAVU_VERSION).$(DEJAVU_ARCHIVE_FORMAT)
DEJAVU_DOWNLOAD_URL ?= $(DEJAVU_BASEURL)/$(DEJAVU_VERSION)/$(DEJAVU_ARCHIVE)

FONTS_SRC_DIR ?= $(BUILDDIR)/fonts
DEJAVU_SRC_DIR ?= $(FONTS_SRC_DIR)/$(DEJAVU_ARCHIVE_BASE)-$(DEJAVU_VERSION)/ttf
FONTS_DST_DIR ?= vendor/tecnickcom/tcpdf/fonts
TCPDF_ADDFONT ?= $(ABSSRCDIR)/$(SCOPED_VENDOR_DIR)/tecnickcom/tcpdf/tools/tcpdf_addfont.php

dev-setup: build-fonts $(FONTS_LIST_FILE)

# rebuild some fonts which seemingly are shipped in a broken or too
# old version by tcpdf
#@private
build-fonts: stamp.tcpdf-fonts
.PHONY: build-fonts

#@private
stamp.tcpdf-fonts: stamp.tcpdf-dejavu-fonts
	date > $@

#@private
build-fonts-dejavu: stamp.tcpdf-dejavu-fonts
.PHONY: build-fonts-dejavu

#@private
stamp.tcpdf-dejavu-fonts: $(SCOPED_VENDOR_DIR)/autoload.php composer.lock $(MAKEFILE_DEP) $(DEJAVU_SRC_DIR)
	rm -f $(FONTS_DST_DIR)/dejavu*.php
	rm -f $(FONTS_DST_DIR)/dejavu*.z
	cd $(DEJAVU_SRC_DIR); $(PHP) $(TCPDF_ADDFONT) -b -t TrueTypeUnicode -f 32 -i DejaVuSans.ttf,DejaVuSans-Bold.ttf,DejaVuSansCondensed.ttf,DejaVuSansCondensed-Bold.ttf,DejaVuSans-ExtraLight.ttf,DejaVuSerif.ttf,DejaVuSerif-Bold.ttf,DejaVuSerifCondensed.ttf,DejaVuSerifCondensed-Bold.ttf
	cd $(DEJAVU_SRC_DIR); $(PHP) $(TCPDF_ADDFONT) -b -t TrueTypeUnicode -f 33 -i DejaVuSansMono.ttf,DejaVuSansMono-Bold.ttf
	cd $(DEJAVU_SRC_DIR); $(PHP) $(TCPDF_ADDFONT) -b -t TrueTypeUnicode -f 96 -i DejaVuSans-BoldOblique.ttf,DejaVuSansCondensed-BoldOblique.ttf,DejaVuSansCondensed-Oblique.ttf,DejaVuSerifCondensed-BoldItalic.ttf,DejaVuSerifCondensed-Italic.ttf,DejaVuSerif-Italic.ttf,DejaVuSerif-BoldItalic.ttf,DejaVuSans-Oblique.ttf
	cd $(DEJAVU_SRC_DIR); $(PHP) $(TCPDF_ADDFONT) -b -t TrueTypeUnicode -f 97 -i DejaVuSansMono-BoldOblique.ttf,DejaVuSansMono-Oblique.ttf
	date > $@

#@private
$(DEJAVU_SRC_DIR): $(DOWNLOADS_DIR)/$(DEJAVU_ARCHIVE)
	mkdir -p $(FONTS_SRC_DIR)
	tar -C $(FONTS_SRC_DIR) -x -f $(ABSSRCDIR)/$(DOWNLOADS_DIR)/$(DEJAVU_ARCHIVE)
	touch $@

#@private
$(DOWNLOADS_DIR)/$(DEJAVU_ARCHIVE):
	mkdir -p $(DOWNLOADS_DIR)
	cd $(DOWNLOADS_DIR); $(WGET) $(DEJAVU_DOWNLOAD_URL)

#@private
$(FONTS_LIST_FILE): stamp.tcpdf-fonts $(wildcard $(FONTS_DST_DIR)/*.php)
	mkdir -p $(dir $@)
	( echo '{';\
FONTS_LIST="$$(ls -C1 $(FONTS_DST_DIR)/*.php)";\
FONTS_COUNT=$$(echo -n "$$FONTS_LIST"|wc -l);\
INDEX=0;\
for FONT_FILE in $$( echo -n "$$FONTS_LIST"); do\
  MD5=$$(md5sum "$$FONT_FILE"|awk '{ print $$1; }');\
  BASENAME=$$(basename $$FONT_FILE .php);\
  echo -n "  \"$$BASENAME\": \"$$MD5\"";\
  if [ "$$INDEX" -lt "$$FONTS_COUNT" ]; then\
    echo ',';\
  else\
    echo;\
  fi;\
  INDEX=$$(( $$INDEX + 1 ));\
done;\
echo '}'; ) > $(FONTS_LIST_FILE)

# The archive additionally ships the toolkit configuration and the fonts list.
#@private
appstore-copy-fonts:
	mkdir -p $(APPSTORE_SIGN_DIR)/$(APP_NAME)/config
	$(RSYNC) -a -L $(APPSTORE_BLACKLISTED:%=--exclude '%') $(SCOPED_VENDOR_DIR)/rotdrop/nextcloud-app-toolkit/config/ $(FONTS_LIST_FILE) $(APPSTORE_SIGN_DIR)/$(APP_NAME)/config/
.PHONY: appstore-copy-fonts
```

### Decisions on drift between the app Makefiles

- `APP_VERSION` is the single version variable (from `appinfo/info.xml`).
  `VERSION=...` on the command line is accepted as an alias (bav used it);
  an environment `VERSION` is deliberately ignored.
- Tool paths use `$(ABSSRCDIR)/vendor-bin/...` (bav used `./vendor/bin/phpunit`).
- `phpcs`/`phpmd` follow the redaxo/dokuwiki variant, `phpcs-errors` comes from roundcube.
- App-specific file lists moved to `APPSTORE_FILES_EXTRA` (`config`, `contrib`)
  and `JS_FILES_EXTRA`. The `mostlyclean` list is the union of all apps.
- Package signing now uses the key actually in use (`APP_PRIVATE_KEY` or the
  certificate directory) and writes `<archive>.sig`; before, the key from
  `$(HOME)` was hard-coded and signing failed in CI.
- The font pipeline example fixes the `FONTS_DEST_DIR` typo, a double slash in
  the download URL and a missing dependency of the font list on the font stamp.
- `make release` uses the generic `scripts/release.sh` unless the app has its
  own `dev-scripts/release.sh`; it tags the `info.xml` version, see below.
- Not moved here: `validate-release.py` and roundcube/bav
  specifics (`toolkit-l10n`, php-scoper rule, custom `l10n` rule).

## Reusable workflows

`.github/workflows/{build-appstore,ci,release}.yml` are `workflow_call`
workflows. The app id and version are read from `appinfo/info.xml`.

```yaml
# .github/workflows/ci.yml in the app
on: [push, pull_request]
jobs:
  ci:
    uses: rotdrop/nextcloud-app-build-system/.github/workflows/ci.yml@v1
    with:
      apt-packages: wget   # only if needed
```

```yaml
# .github/workflows/release.yml in the app
on:
  push:
    tags: ['v*']
jobs:
  release:
    uses: rotdrop/nextcloud-app-build-system/.github/workflows/release.yml@v1
    secrets: inherit       # APP_PRIVATE_KEY, APP_PUBLIC_CRT, optional APPSTORE_TOKEN
    permissions:
      contents: write
```

Common inputs: `php-version`, `node-version`, `apt-packages`, `make-args`
and `verify-script` (a script relative to the app root, run after the build
with `APP_ID`, `APP_VERSION` and `ARCHIVE` set). `build-appstore.yml` has
further inputs for the PHP extensions, `release`, `environment` and the
signing server.

### Opting out of signing and app store upload

Apps not (yet) in the Nextcloud app store can opt out in `release.yml`:

```yaml
    with:
      sign: false                # unsigned tarball, no server checkout, no keys
      upload-to-appstore: false  # never push to the app store
```

- `sign` (default `true`): with `false` the archive is built unsigned and still
  attached to the GitHub release (tag pattern rules for pre-releases stay), and
  nothing is uploaded. With `true` the secrets `APP_PRIVATE_KEY` and
  `APP_PUBLIC_CRT` are required and the release fails if they are missing.
- `upload-to-appstore` (default `true`): uploads the signed archive to the
  app store. Pre-releases (version contains `-`) are uploaded with
  `nightly: true`, i.e. to the nightly channel, stable releases with
  `nightly: false`. Nothing is uploaded for unsigned builds (silently, as with
  `upload-to-appstore: false`). If the `APPSTORE_TOKEN` secret is absent, a
  stable release **fails** the upload job with an error naming the environment;
  a pre-release only gets a warning and is skipped. The upload job runs in the
  same `environment` as the build, so an environment secret works. It checks
  that the download URL is public, then logs the HTTP status and response body
  (`--fail-with-body`; 201 = created, 200 = existing release updated). This replaces the former
  opt-in `publish-to-appstore` input.
- `build-appstore.yml` has the same `sign` input, effective with `release: true`.
  Without `release`, archives are always unsigned.
- Locally: `make appstore APPSTORE_SIGN=0` builds an unsigned archive and
  ignores keys in `~/.nextcloud/certificates`; it needs no `occ`. Without keys
  signing is skipped with a message anyway.

Versioning: reference the workflows by the floating major tag `@v1` (or an
exact tag). The nested calls (`ci` and `release` call `build-appstore`) use
`@v1` too, because `uses:` cannot be computed and `./` would resolve in the
app's repository. When cutting a new major version, update these two
references in the same commit, and move the `v1` tag with each compatible
release.

### `make release`

`make release [VERSION=x.y.z]` runs `scripts/release.sh`, or the app's own
`dev-scripts/release.sh` if it exists (`RELEASE_SCRIPT` overrides both). The
script reads the version from `appinfo/info.xml`, requires a clean tree on the
default branch (`RELEASE_BRANCH` overrides) matching the remote, and pushes
the annotated tag `v<version>`, which triggers the release workflow.

### Is a Nextcloud server tree needed in CI?

Normally no. The workflows build the app in its own checkout. The
pdf_downloader CI built inside a server tree; the PHP-to-TypeScript generation
(`dev-scripts/php-to-typescript.php`) runs there without a server
(`libxml-xpath-perl`, and `memory_limit=1G` for php-scoper suffice) and
produces `php-types.d.ts` and the module files. Signing needs a server for
`occ integrity:sign-app` and `integrity:check-app`; `build-appstore.yml`
installs a stock server only if `release` is true and passes it as `OCC=`.
files_archive and bav already build without a server. This was verified for
pdf_downloader only; dokuwiki, redaxo and roundcube have to be confirmed when
they are migrated.

#### Opt-in: `build-server`

Some apps (cafevdb, cafevdbmembers) have a `dev-scripts/php-to-typescript.php`
that bootstraps Nextcloud through `lib/scripts/console-setup.php`, which
requires `<app>/../../lib/versioncheck.php`: the app must live at
`<server>/apps/<app id>`. For these, pass to `ci`, `build-appstore` or
`release`:

```yaml
    with:
      build-server: true
      signing-server-ref: stable35   # branch or tag of nextcloud/server
```

`signing-server-repository` (default `nextcloud/server`) and
`signing-server-ref` (default `master`) select the server. The composite
action `.github/actions/nextcloud-server` clones it shallowly into
`$RUNNER_TEMP`, runs `composer install` and `occ maintenance:install`, and
bind-mounts the app checkout at `<server>/apps/<app id>` (a symlink does not
work because the script resolves it with `realpath()`). `make appstore`, and
in `ci` also the `realclean` job (whose `make build` generates the types too),
run in that directory. The app is not enabled in that server, so
`scripts/console-setup.php` registers it like a lazily loaded app, through
the server's bootstrap `Coordinator::runLazyRegistration()`: this sets up the
autoloading and runs the app's `register()` (service aliases such as
interface bindings), which `php-to-typescript` needs to resolve the app's
classes and dependency injection. The app info is read through the app manager
because Nextcloud's libxml entity loader makes `simplexml_load_file()` fail.
Without a Coordinator it falls back to the autoloader registration. This is a
no-op for enabled apps. Verified with a real server and the real cafevdb-members
tree; `occ app:enable` is not needed (it would require installation, the app's
vendor directory and a database migration).
Apps must therefore update their `dev-scripts/lib` submodule.
The artifacts are written to the app checkout as usual.
Signing reuses the same server. The default is `false` and then nothing
changes. The action needs the `v1` tag to contain it, so it is not usable
from a branch before the tag is moved.

#### Composer and the GitHub API

`ci`, `build-appstore` and `release` export `COMPOSER_AUTH` with the workflow
token as a job-level environment variable, so every make step (and the
`nextcloud-server` action) is authenticated. Apps with many `github.com` VCS
repositories in their `composer.json` (a cold run of cafevdb-members needs
about 500 API requests) can still exhaust the hourly API limit of the token,
which Composer reports as "Could not authenticate against github.com". Such
apps should pass `composer-use-github-api: false`: Composer then clones with
git and makes no API requests (about 11 s instead of 2 min in a local test).
The default is `true`, i.e. unchanged behaviour.

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

### Following the release tag: `dev-lib-sync-release`

`make dev-lib-sync-release` behaves exactly like `dev-lib-sync` but moves the
submodule to the commit of the tag `$(DEV_LIB_SYNC_TAG)` (default `v1`, the
floating release line the apps' reusable workflows are pinned to) instead of
`origin/main`. Set e.g. `make dev-lib-sync-release DEV_LIB_SYNC_TAG=v2` for
another major version. Because the floating tag is force-moved, it fetches
with `git fetch --tags --force`, and it resolves `refs/tags/<tag>^{commit}`,
which also works for annotated tags. The commit message is
`Update dev-scripts/lib to v1 (<sha>)`. The same refusals apply
(detached application HEAD, dirty submodule, submodule commits not contained
in the tag); it never force-pushes. The shared logic lives in
`scripts/dev-lib-sync.sh`.

