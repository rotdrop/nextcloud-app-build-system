# nextcloud-app-build-system
Kind of library of Makefile fragments and such. Intended as git sub-repo.

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

The fragment includes the installed toolkit's `tools/l10n.mk` only when
`composer.json` or `composer.json.in` declares
`rotdrop/nextcloud-app-toolkit` in `require` or `require-dev`.
It runs the Vue extractor only when `package.json` declares
`@rotdrop/nextcloud-vue-components` in `dependencies`, `devDependencies`,
`optionalDependencies`, or `peerDependencies`. Repository URLs and stale
installed packages do not enable extraction. Undeclared packages make
the corresponding targets no-ops; malformed manifests are errors.

Install the declared packages before including/running the fragment. The
toolkit fragment must exist at parse time (override `APP_TOOLKIT_DIR` for
a nonstandard Composer vendor directory). The Vue command runs from the
app directory using `npx --no-install` to avoid implicit package downloads.
`PHP`, `NODE`, and `NPX` can be overridden. The individual targets `toolkit-l10n` and
`vue-components-l10n` are also available. Including the fragment does not
change the application's default goal.

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
