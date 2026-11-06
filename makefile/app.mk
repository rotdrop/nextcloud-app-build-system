# Common build rules shared by the Nextcloud apps using this library.
#
# Usage in the application's Makefile (see README.md for the full contract):
#
#   SRCDIR = .
#   ABSSRCDIR = $(CURDIR)
#   DEV_LIB_DIR = $(ABSSRCDIR)/dev-scripts/lib
#   # ... optional app configuration variables, see README.md ...
#   include $(DEV_LIB_DIR)/makefile/app.mk
#   # ... app-specific targets, optional fragments ...
#
# All configuration variables are optional and are set *before* the include.
# Defaults use "?=", so command-line and environment values win as well.
# App-specific rules and extensions are added *after* the include, using the
# documented hook targets and "+=" extension variables.

ifndef _APP_BUILD_APP_INCLUDED
_APP_BUILD_APP_INCLUDED := 1

SRCDIR ?= .
ABSSRCDIR ?= $(CURDIR)
DEV_LIB_DIR ?= $(ABSSRCDIR)/dev-scripts/lib
MAKEFILE_DEP ?= Makefile
_APP_MK_DIR := $(dir $(lastword $(MAKEFILE_LIST)))

include $(_APP_MK_DIR)setup.mk

SILENT ?= @

# Tools; all can be overridden on the command-line.
RSYNC ?= $(shell which rsync 2> /dev/null)
PHP ?= $(shell which php 2> /dev/null)
NPM ?= $(shell which npm 2> /dev/null)
OPENSSL ?= $(shell which openssl 2> /dev/null)
EMACS ?= $(shell which emacs 2> /dev/null)
WGET ?= $(shell which wget 2> /dev/null)
PHPUNIT ?= $(ABSSRCDIR)/vendor-bin/phpunit/vendor/bin/phpunit
PHPCS ?= $(ABSSRCDIR)/vendor-bin/phpcs/vendor/bin/phpcs
PHPMD ?= $(ABSSRCDIR)/vendor-bin/phpmd/vendor/bin/phpmd
PHP_SCOPER ?= $(ABSSRCDIR)/vendor-bin/php-scoper/vendor/bin/php-scoper
BUNDLER_CONFIG ?= vite.config.ts

ifeq ($(origin COMPOSER),undefined)
COMPOSER_SYSTEM := $(shell which composer 2> /dev/null)
ifeq (, $(COMPOSER_SYSTEM))
COMPOSER = $(PHP) $(BUILD_TOOLS_DIR)/composer.phar
else
COMPOSER = $(COMPOSER_SYSTEM)
endif
endif
COMPOSER_OPTIONS ?= --prefer-dist

ifeq ($(PHP),)
$(error PHP binary is needed, but could not be found and was not specified on the command-line)
endif
ifeq ($(NPM),)
$(error NPM binary is needed, but could not be found and was not specified on the command-line)
endif
ifeq ($(COMPOSER),)
$(error COMPOSER binary is needed, but could not be found and was not specified on the command-line)
endif
ifneq ($(strip $(APP_REQUIRE_WGET)),)
ifeq ($(WGET),)
$(error WGET binary is needed, but could not be found and was not specified on the command-line)
endif
endif

MAKE_HELP_DIR ?= $(SRCDIR)/dev-scripts/MakeHelp
include $(MAKE_HELP_DIR)/MakeHelp.mk

# App-store packaging configuration.
APPSTORE_BUILD_DIR ?= $(BUILDDIR)/artifacts/appstore
APPSTORE_COMPRESSION ?= z
# VERSION is accepted for apps which historically passed it on the command-line.
APPSTORE_VERSION ?= $(or $(VERSION),$(APP_VERSION))
APPSTORE_PACKAGE_FILE := $(APPSTORE_BUILD_DIR)/$(APP_NAME)-$(APPSTORE_VERSION).tar
ifeq ($(APPSTORE_COMPRESSION),z)
  APPSTORE_PACKAGE_FILE := $(APPSTORE_PACKAGE_FILE).gz
else ifeq ($(APPSTORE_COMPRESSION),J)
  APPSTORE_PACKAGE_FILE := $(APPSTORE_PACKAGE_FILE).xz
endif
APPSTORE_SIGN_DIR ?= $(APPSTORE_BUILD_DIR)/sign
BUILD_CERT_DIR ?= $(BUILD_TOOLS_DIR)/certificates
CERT_DIR ?= $(HOME)/.nextcloud/certificates
OCC ?= $(CURDIR)/../../occ

# Entries which do not exist are skipped when the archive is staged.
APPSTORE_FILES ?=\
 appinfo\
 css\
 js\
 img\
 l10n\
 lib\
 templates\
 composer\
 vendor\
 $(SCOPED_VENDOR_DIR)\
 CHANGELOG.md\
 COPYING\
 README.md
APPSTORE_FILES += $(APPSTORE_FILES_EXTRA)

# .htaccess is blacklisted by the app-store installer, so we have to remove it
APPSTORE_BLACKLISTED ?= foobar .htaccess .git* .*keep *~

# Command run after the build and before staging in order to strip development dependencies.
APPSTORE_COMPOSER_COMMAND ?= $(COMPOSER) update --no-dev
APPSTORE_BUILD_TARGETS ?= build

# Static analysis configuration.
PHP_QA_DIRS ?= lib appinfo templates
_EMPTY :=
_SPACE := $(_EMPTY) $(_EMPTY)
_COMMA := ,
PHPCS_ARGS ?= -s --report=emacs --standard=$(SRCDIR)/.phpcs.xml $(PHP_QA_DIRS)
PHPMD_ARGS ?= $(subst $(_SPACE),$(_COMMA),$(strip $(PHP_QA_DIRS))) text $(SRCDIR)/.phpmd.xml

# Source and generated inputs of the bundler build.
APP_TS_NOTIFICATION_API ?=
L10N_VITE_CONFIG ?= vite.l10n.config.ts
# Extra prerequisites of the Vite l10n analysis, e.g. generated TypeScript sources.
L10N_IGNORE_DEPS ?=
TIDE_ENTRY ?= $(SRCDIR)/src/vue-app.ts

#@@ The default rule.
all: help
.PHONY: all

#@@ Build the distribution assets (minified, without debugging info)
build:
	$(MAKE) build-flavour-build
	$(MAKE) dev-setup
	$(MAKE) npm-build
.PHONY: build

#@@ Build the development assets (include debugging information)
dev:
	$(MAKE) build-flavour-dev
	$(MAKE) dev-setup
	$(MAKE) npm-dev
.PHONY: dev

#@@ Build the distribution assets without Composer development dependencies
build-no-dev:
	$(MAKE) COMPOSER_OPTIONS="$(COMPOSER_OPTIONS) --no-dev" build
.PHONY: build-no-dev

# Apps add prerequisites with "dev-setup: foo" or by setting DEV_SETUP_DEPS before the include.
#@private
dev-setup: composer namespace-wrapper $(DEV_SETUP_DEPS)
.PHONY: dev-setup

include $(_APP_MK_DIR)composer.mk
include $(_APP_MK_DIR)namespace-wrapper.mk

app-toolkit: $(SCOPED_VENDOR_DIR)/autoload.php
.PHONY: app-toolkit

include $(_APP_MK_DIR)l10n.mk

toolkit-l10n: app-toolkit
vue-components-l10n: node_modules

#@@ Regenerate the translation sources and the l10n exclusion lists
l10n: l10n-sources l10n-ignore toolkit-l10n-ignore-candidates
.PHONY: l10n

ifneq ($(strip $(L10N_IGNORE_DEPS)),)
vue-components-l10n-ignore: $(L10N_IGNORE_DEPS)
endif

include $(_APP_MK_DIR)ts-app-config.mk
include $(_APP_MK_DIR)ts-types-files.mk
ifneq ($(strip $(APP_TS_NOTIFICATION_API)),)
include $(_APP_MK_DIR)ts-notification-api.mk
endif

L10N_FILES ?= $(wildcard $(ABSSRCDIR)/l10n/*.js $(ABSSRCDIR)/l10n/*.json)
JS_FILES ?= $(shell if [ -d "$(ABSSRCDIR)/src" ]; then find $(ABSSRCDIR)/src -name "*.js" -o -name "*.vue" -o -name "*.ts"; fi)
IMG_FILES ?= $(shell if [ -d "$(ABSSRCDIR)/img" ]; then find $(ABSSRCDIR)/img -name "*.svg"; fi)

# APP_BUNDLER_DEPS holds additional app-specific prerequisites of the bundler build.
BUNDLER_DEPS := $(BUNDLER_DEPS)\
 $(L10N_FILES)\
 $(JS_FILES)\
 $(IMG_FILES)\
 $(TS_APP_CONFIG)\
 ts-types-files\
 $(if $(strip $(APP_TS_NOTIFICATION_API)),$(TS_NOTIFICATION_API))\
 $(APP_BUNDLER_DEPS)

include $(_APP_MK_DIR)npm.mk

#@@ Run phpcs on the PHP code
phpcs: composer
	$(PHPCS) $(PHPCS_ARGS)
.PHONY: phpcs

#@@ Run phpmd on the PHP code
phpmd: composer
	$(PHPMD) $(PHPMD_ARGS)
.PHONY: phpmd

#@@ Build the app-store archive (and sign it if key and certificate are available)
appstore:
	$(MAKE) clean
	$(MAKE) $(APPSTORE_BUILD_TARGETS)
	$(APPSTORE_COMPOSER_COMMAND)
	$(MAKE) appstore-package
.PHONY: appstore

# Hook for app-specific staging: add recipes with "appstore-stage::".
# It runs after APPSTORE_FILES have been copied and before signing.
#@private
appstore-stage::
	@:
.PHONY: appstore-stage

# A separate make invocation is used by "appstore" so that the wildcard
# below sees the files produced by the build.
#@private
appstore-package:
	mkdir -p $(APPSTORE_SIGN_DIR)/$(APP_NAME)
	$(RSYNC) -a -L $(APPSTORE_BLACKLISTED:%=--exclude '%') $(wildcard $(APPSTORE_FILES)) $(APPSTORE_SIGN_DIR)/$(APP_NAME)
	$(MAKE) appstore-stage
	mkdir -p $(BUILD_CERT_DIR)
	$(SILENT)if [ -n "$$APP_PRIVATE_KEY" ]; then\
  echo "$$APP_PRIVATE_KEY" > $(BUILD_CERT_DIR)/$(APP_NAME).key;\
elif [ -f "$(CERT_DIR)/$(APP_NAME).key" ]; then\
  cp $(CERT_DIR)/$(APP_NAME).key $(BUILD_CERT_DIR)/$(APP_NAME).key;\
fi
	$(SILENT)if [ -n "$$APP_PUBLIC_CRT" ]; then\
  echo "$$APP_PUBLIC_CRT" > $(BUILD_CERT_DIR)/$(APP_NAME).crt;\
fi
	$(SILENT)if [ -f $(BUILD_CERT_DIR)/$(APP_NAME).key ] && [ ! -f $(BUILD_CERT_DIR)/$(APP_NAME).crt ]; then\
  curl -L -o $(BUILD_CERT_DIR)/$(APP_NAME).crt\
 "https://github.com/nextcloud/app-certificate-requests/raw/master/$(APP_NAME)/$(APP_NAME).crt";\
  $(OPENSSL) x509 -in $(BUILD_CERT_DIR)/$(APP_NAME).crt -noout -text > /dev/null 2>&1 || rm -f $(BUILD_CERT_DIR)/$(APP_NAME).crt;\
fi
	$(SILENT)if [ -f $(BUILD_CERT_DIR)/$(APP_NAME).key ] && [ -f $(BUILD_CERT_DIR)/$(APP_NAME).crt ]; then\
  echo "Signing app files ...";\
  $(PHP) $(OCC) integrity:sign-app\
 --privateKey=$(ABSSRCDIR)/$(BUILD_CERT_DIR)/$(APP_NAME).key\
 --certificate=$(ABSSRCDIR)/$(BUILD_CERT_DIR)/$(APP_NAME).crt\
 --path=$(ABSSRCDIR)/$(APPSTORE_SIGN_DIR)/$(APP_NAME);\
  echo "... signing app files done";\
else\
  echo 'Cannot sign app-files, certificate "$(BUILD_CERT_DIR)/$(APP_NAME).crt" or private key "$(BUILD_CERT_DIR)/$(APP_NAME).key" not available.' 1>&2;\
fi
	tar -c$(APPSTORE_COMPRESSION)f $(APPSTORE_PACKAGE_FILE) -C $(APPSTORE_SIGN_DIR) $(APP_NAME)
	$(SILENT)if [ -f $(BUILD_CERT_DIR)/$(APP_NAME).key ] && [ -f $(BUILD_CERT_DIR)/$(APP_NAME).crt ]; then\
  echo "Signing package ...";\
  $(OPENSSL) dgst -sha512 -sign $(BUILD_CERT_DIR)/$(APP_NAME).key $(APPSTORE_PACKAGE_FILE) | $(OPENSSL) base64; \
else\
  echo 'Cannot sign app-store package, certificate "$(BUILD_CERT_DIR)/$(APP_NAME).crt" or private key "$(BUILD_CERT_DIR)/$(APP_NAME).key" not available.' 1>&2;\
fi
.PHONY: appstore-package

# Clean-up. Apps extend the removal lists with "+=" after the include:
#   CLEAN_EXTRA, DISTCLEAN_EXTRA, MOSTLYCLEAN_EXTRA, REALCLEAN_EXTRA
# (space separated paths, removed with "rm -rf").

#@@ Removes build files
clean: ## Tidy up local environment
	rm -rf $(BUILDDIR) $(CLEAN_EXTRA)
.PHONY: clean

#@@ Same as clean but also removes dependencies installed by composer, bower and npm
distclean: clean ## Clean even more, calls clean
	rm -rf vendor
	rm -rf $(SCOPED_VENDOR_DIR)
	rm -rf vendor-bin/**/vendor
	find . -name node_modules -prune -exec rm -rf {} + 2> /dev/null || true
	rm -rf $(DISTCLEAN_EXTRA)
.PHONY: distclean

#@@ Almost everything but downloads
mostlyclean: bundler-clean distclean
	rm -f composer*.lock
	rm -f composer.json
	rm -f vendor-bin/**/composer.lock
	rm -f patches.lock.json vendor-bin/**/patches.lock.json
	rm -f stamp.composer-core-versions
	rm -f package-lock.json
	rm -f *.html
	rm -f stats.json
	rm -rf .vite
	rm -f $(BUILD_FLAVOUR_FILE)
	rm -rf $(MOSTLYCLEAN_EXTRA)
.PHONY: mostlyclean

#@@ Really delete everything but the bare source files
realclean: mostlyclean downloadsclean
	rm -rf $(REALCLEAN_EXTRA)
.PHONY: realclean

#@@ Remove non-npm non-composer downloads
downloadsclean:
	rm -rf $(DOWNLOADS_DIR)
.PHONY: downloadsclean

#@@ Run the test-suite
test: unit-tests integration-tests
.PHONY: test

#@@ Run the unit tests
unit-tests:
	$(PHPUNIT) -c phpunit.xml
.PHONY: unit-tests

#@@ Run the integration tests
integration-tests:
	$(PHPUNIT) -c phpunit.integration.xml
.PHONY: integration-tests

#@private
run-tide:
	$(EMACS) --batch --file $(TIDE_ENTRY) -l $(DEV_LIB_DIR)/scripts/tide-project-errors.el|tee tide-errors.log
.PHONY: run-tide

#@@ Runs the Emacs Tide IDE in batch mode and diagnoses TypeScript errors.
tide: dev-setup ts-app-config ts-types-files run-tide
.PHONY: tide

endif
