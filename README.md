# nextcloud-app-build-system
Makefile fragments and helper scripts for Nextcloud apps, installable as a
Composer package (previously used as git subrepo).

## Usage

    composer require --dev rotdrop/nextcloud-app-build-system

Until the package is on Packagist, add a `vcs` repository entry to the app's
`composer.json`. The tools' own dependencies are *not* installed privately
any more; the app must provide them in its `require-dev`:

- `cweagans/composer-patches` (^2.0) and `nextcloud/ocp` (`dev-stable35`)
- `spatie/typescript-transformer` (and what the app's PHP classes need)

To apply the OCP patch, add to the app's `composer.json`:

    "extra": { "patches": { "nextcloud/ocp": {
      "Fix server version at 35.0.0.0":
        "vendor/rotdrop/nextcloud-app-build-system/composer-patches/nextcloud/ocp/get-version.patch"
    } } }

In the app's `Makefile`:

    DEV_LIB_DIR = $(ABSSRCDIR)/vendor/rotdrop/nextcloud-app-build-system
    include $(DEV_LIB_DIR)/makefile/composer.mk

The PHP scripts are autoloadable (`OCA\RotDrop\DevScripts\PhpToTypeScript\`).
`scripts/console-setup.php` expects the constant `ROT_DROP_DEV_SCRIPTS_APP_DIR`
to be defined as the app's root directory.

Exclude `vendor/rotdrop/nextcloud-app-build-system` from release tarballs.
