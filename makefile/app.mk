# Shared application Makefile. A consuming app only sets its hooks and
# overrides and then includes this file, see the README for a full example:
#
#   SRCDIR = .
#   ABSSRCDIR = $(CURDIR)
#   DEV_LIB_DIR = $(ABSSRCDIR)/dev-scripts/lib
#   include $(DEV_LIB_DIR)/makefile/app.mk
#
# All hooks are "?="-defaulted here, so the app has to set them BEFORE
# the include. Rules and prerequisites may be added after the include.
#
# Hooks and overrides:
#
#   APP_DEV_SETUP_DEPS      prerequisites of dev-setup (default: ts-app-config)
#   APP_REQUIRED_TOOLS      variable names of further tools which must exist,
#                           e.g. "WGET"; PHP and NPM are always required
#   APP_BUILD_FLAVOUR_FIRST non-empty: switch the build flavour before dev-setup
#   APP_NOTIFICATION_API    non-empty: generate the notification API types
#   APP_PHP_DIRS            directories for phpcs/phpmd (default: lib appinfo templates)
#   APP_MOSTLYCLEAN_DEPS    additional prerequisites of mostlyclean
#   APP_MOSTLYCLEAN_FILES   additional files removed by mostlyclean
#   APPSTORE_FILES          files copied to the archive (replaces the default list)
#   APPSTORE_FILES_EXTRA    further files copied to the archive
#   APPSTORE_COPY_HOOK      make target(s) run after copying and before signing,
#                           the signing directory is $(APPSTORE_SIGN_DIR)/$(APP_NAME)
#   APPSTORE_COMPOSER_ARGS  composer arguments run before packaging (default: update --no-dev)
#   JS_FILES_EXTRA          further files the bundler build depends on
#   TS_PHP_SOURCE_DIRS      PHP sources for the TypeScript type generation
#   L10N_VITE_CONFIG        Vite config used for the l10n ignore analysis
#   BUNDLER_CONFIG          bundler configuration file (default: vite.config.ts)
#   RELEASE_SCRIPT          script run by "make release"
#
# The version is APP_VERSION, taken from appinfo/info.xml and
# overridable on the command line. VERSION given on the command line is
# accepted as an alias.

SRCDIR ?= .
ABSSRCDIR ?= $(CURDIR)
DEV_LIB_DIR ?= $(ABSSRCDIR)/dev-scripts/lib

SILENT ?= @

# Tagging does not need the Nextcloud build environment, so this part
# is always available and the rest is skipped for "make release".
RELEASE_SCRIPT ?= $(ABSSRCDIR)/dev-scripts/release.sh

#@@ Validate the unpublished changelog version, tag it, and push the release tag.
release:
	$(SILENT)test -f "$(RELEASE_SCRIPT)" || { echo 'Release script "$(RELEASE_SCRIPT)" not found, set RELEASE_SCRIPT.' 1>&2; exit 1; }
	bash "$(RELEASE_SCRIPT)" $(if $(filter command line,$(origin VERSION)),"$(VERSION)")
.PHONY: release

ifneq ($(strip $(MAKECMDGOALS)),release)

include $(DEV_LIB_DIR)/makefile/setup.mk

# VERSION from the environment is ignored on purpose, it is too generic.
ifneq ($(filter command line,$(origin VERSION)),)
ifeq ($(filter command line,$(origin APP_VERSION)),)
override APP_VERSION := $(VERSION)
endif
endif

###############################################################################
#
# Tools. These may be overridden on the command line, e.g. make PHP=php8.4.

lowercase = $(shell printf '%s' '$(1)' | tr '[:upper:]' '[:lower:]')

define _app_detect_tool
ifeq ($$(origin $(1)),undefined)
$(1) := $$(shell command -v $(2) 2> /dev/null)
endif
endef

# Look up the binary $(2) (default: lowercased $(1)) unless $(1) is
# already set, and fail if it cannot be found.
app-require-tool = $(eval $(call _app_detect_tool,$(1),$(or $(2),$(call lowercase,$(1)))))$(if $($(1)),,$(error $(1) binary is needed, but could not be found and was not specified on the command-line))

$(eval $(call _app_detect_tool,RSYNC,rsync))
$(eval $(call _app_detect_tool,OPENSSL,openssl))
$(eval $(call _app_detect_tool,EMACS,emacs))

APP_REQUIRED_TOOLS ?=
$(foreach tool,PHP NPM $(APP_REQUIRED_TOOLS),$(call app-require-tool,$(tool)))

ifeq ($(origin COMPOSER),undefined)
COMPOSER_SYSTEM := $(shell command -v composer 2> /dev/null)
ifeq ($(COMPOSER_SYSTEM),)
COMPOSER = $(PHP) $(BUILD_TOOLS_DIR)/composer.phar
else
COMPOSER = $(COMPOSER_SYSTEM)
endif
endif
COMPOSER_OPTIONS ?= --prefer-dist

PHPUNIT ?= $(ABSSRCDIR)/vendor-bin/phpunit/vendor/bin/phpunit
PHPCS ?= $(ABSSRCDIR)/vendor-bin/phpcs/vendor/bin/phpcs
PHPMD ?= $(ABSSRCDIR)/vendor-bin/phpmd/vendor/bin/phpmd

BUNDLER_CONFIG ?= vite.config.ts

MAKE_HELP_DIR ?= $(SRCDIR)/dev-scripts/MakeHelp
include $(MAKE_HELP_DIR)/MakeHelp.mk

###############################################################################
#
# Appstore packaging variables

APPSTORE_BUILD_DIR ?= $(BUILDDIR)/artifacts/appstore
APPSTORE_COMPRESSION ?= z
ifeq ($(APPSTORE_COMPRESSION),z)
  APPSTORE_PACKAGE_SUFFIX ?= .gz
else ifeq ($(APPSTORE_COMPRESSION),J)
  APPSTORE_PACKAGE_SUFFIX ?= .xz
endif
APPSTORE_PACKAGE_FILE ?= $(APPSTORE_BUILD_DIR)/$(APP_NAME)-$(APP_VERSION).tar$(APPSTORE_PACKAGE_SUFFIX)
APPSTORE_SIGN_DIR ?= $(APPSTORE_BUILD_DIR)/sign
BUILD_CERT_DIR ?= $(BUILD_TOOLS_DIR)/certificates
CERT_DIR ?= $(HOME)/.nextcloud/certificates
# Only needed for signing, it is part of a Nextcloud server tree.
OCC ?= $(CURDIR)/../../occ

# what has to be copied to the appstore archive
APPSTORE_FILES ?=\
 appinfo\
 css\
 js\
 img\
 l10n\
 templates\
 lib\
 vendor\
 $(SCOPED_VENDOR_DIR)\
 composer\
 CHANGELOG.md\
 COPYING\
 README.md
APPSTORE_FILES_EXTRA ?=

# .htaccess is blacklisted by the app-store installer, so we have to remove it
APPSTORE_BLACKLISTED ?= .htaccess .git* .*keep *~

APPSTORE_COMPOSER_ARGS ?= update --no-dev
APPSTORE_COPY_HOOK ?=

###############################################################################
#
# Main targets

#@@ The default rule.
all: help
.PHONY: all
.DEFAULT_GOAL := all

APP_BUILD_FLAVOUR_FIRST ?=
ifneq ($(strip $(APP_BUILD_FLAVOUR_FIRST)),)

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

else

#@@ Build the distribution assets (minified, without debugging info)
build: dev-setup npm-build
.PHONY: build

#@@ Build the development assets (include debugging information)
dev: dev-setup npm-dev
.PHONY: dev

endif

#@@ Build the distribution assets with composer dependencies without dev-dependencies
build-no-dev:
	$(MAKE) COMPOSER_OPTIONS="$(COMPOSER_OPTIONS) --no-dev" build
.PHONY: build-no-dev

APP_DEV_SETUP_DEPS ?= ts-app-config

#@private
dev-setup: composer namespace-wrapper $(APP_DEV_SETUP_DEPS)
.PHONY: dev-setup

include $(DEV_LIB_DIR)/makefile/composer.mk

SCOPED_COMPOSER_UPDATE_OPTIONS ?= --no-dev
include $(DEV_LIB_DIR)/makefile/namespace-wrapper.mk

include $(DEV_LIB_DIR)/makefile/ts-app-config.mk
include $(DEV_LIB_DIR)/makefile/ts-types-files.mk

APP_NOTIFICATION_API ?=
ifneq ($(strip $(APP_NOTIFICATION_API)),)
include $(DEV_LIB_DIR)/makefile/ts-notification-api.mk
_APP_TS_NOTIFICATION_API = $(TS_NOTIFICATION_API)
endif

L10N_VITE_CONFIG ?= vite.l10n.config.ts
include $(DEV_LIB_DIR)/makefile/l10n.mk

l10n: l10n-sources l10n-ignore toolkit-l10n-ignore-candidates
.PHONY: l10n

# The Vite config imports generated TypeScript sources.
vue-components-l10n-ignore: $(TS_APP_CONFIG) ts-types-files $(_APP_TS_NOTIFICATION_API)

###############################################################################
#
# Bundler dependencies

L10N_FILES ?= $(wildcard l10n/*.js l10n/*.json)
JS_FILES ?= $(shell find $(ABSSRCDIR)/src \( -name "*.js" -o -name "*.vue" -o -name "*.ts" \) 2> /dev/null)
JS_FILES_EXTRA ?=
IMG_FILES ?= $(shell find $(ABSSRCDIR)/img -name "*.svg" 2> /dev/null)

NPM_INIT_DEPS ?=\
 Makefile package-lock.json package.json $(BUNDLER_CONFIG) eslint.config.mjs

BUNDLER_DEPS +=\
 $(NPM_INIT_DEPS)\
 $(JS_FILES)\
 $(JS_FILES_EXTRA)\
 $(IMG_FILES)\
 $(L10N_FILES)\
 $(TS_APP_CONFIG)\
 ts-types-files\
 $(_APP_TS_NOTIFICATION_API)

include $(DEV_LIB_DIR)/makefile/npm.mk

###############################################################################
#
# PHP code checks

APP_PHP_DIRS ?= lib appinfo templates

#@private
$(PHPCS): composer.lock
	if ! [ -x "$@" ]; then $(COMPOSER) bin phpcs install; else touch "$@"; fi

#@private
$(PHPMD): composer.lock
	if ! [ -x "$@" ]; then $(COMPOSER) bin phpmd install; else touch "$@"; fi

#@@ Run phpcs on the PHP code
phpcs: $(PHPCS)
	$(PHPCS) -s --runtime-set ignore_warnings_on_exit 1 --report=emacs --standard=$(SRCDIR)/.phpcs.xml $(wildcard $(APP_PHP_DIRS))
.PHONY: phpcs

#@@ Run phpcs on the PHP code, hiding mere warnings, and list the affected files
phpcs-errors: $(PHPCS)
	$(PHPCS) -n --standard=$(SRCDIR)/.phpcs.xml $(wildcard $(APP_PHP_DIRS)) | grep FILE: | awk '{ print $$2; }'
.PHONY: phpcs-errors

#@@ Run phpmd on the PHP code
phpmd: $(PHPMD)
	$(PHPMD) --format text --ruleset $(SRCDIR)/.phpmd.xml $(wildcard $(APP_PHP_DIRS))
.PHONY: phpmd

###############################################################################
#
# Appstore archive

#@@ Prepare appstore archive
appstore:
	$(MAKE) clean
	$(MAKE) build
	$(COMPOSER) $(APPSTORE_COMPOSER_ARGS)
	mkdir -p $(APPSTORE_SIGN_DIR)/$(APP_NAME)
	$(RSYNC) -a -L $(APPSTORE_BLACKLISTED:%=--exclude '%') $(APPSTORE_FILES) $(APPSTORE_FILES_EXTRA) $(APPSTORE_SIGN_DIR)/$(APP_NAME)
	$(if $(strip $(APPSTORE_COPY_HOOK)),$(MAKE) $(APPSTORE_COPY_HOOK))
	mkdir -p $(BUILD_CERT_DIR)
	$(SILENT)umask 077;\
if [ -n "$$APP_PRIVATE_KEY" ]; then\
  echo "$$APP_PRIVATE_KEY" > $(BUILD_CERT_DIR)/$(APP_NAME).key;\
elif [ -f "$(CERT_DIR)/$(APP_NAME).key" ]; then\
  cp $(CERT_DIR)/$(APP_NAME).key $(BUILD_CERT_DIR)/$(APP_NAME).key;\
fi;\
if [ -n "$$APP_PUBLIC_CRT" ]; then\
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
  $(OPENSSL) dgst -sha512 -sign $(BUILD_CERT_DIR)/$(APP_NAME).key -out $(APPSTORE_PACKAGE_FILE).sig $(APPSTORE_PACKAGE_FILE);\
  $(OPENSSL) base64 -in $(APPSTORE_PACKAGE_FILE).sig;\
else\
  echo 'Cannot sign app-store package, certificate "$(BUILD_CERT_DIR)/$(APP_NAME).crt" or private key "$(BUILD_CERT_DIR)/$(APP_NAME).key" not available.' 1>&2;\
fi
.PHONY: appstore

###############################################################################
#
# Cleaning

APP_MOSTLYCLEAN_DEPS ?=
APP_MOSTLYCLEAN_FILES ?=

#@@ Removes build files
clean: ## Tidy up local environment
	rm -rf $(BUILDDIR)
.PHONY: clean

#@@ Same as clean but also removes dependencies installed by composer, bower and npm
distclean: clean ## Clean even more, calls clean
	rm -rf vendor $(SCOPED_VENDOR_DIR)
	rm -rf vendor-bin/**/vendor
	find . -name node_modules -type d -prune -exec rm -rf {} + 2> /dev/null || true
.PHONY: distclean

#@@ Almost everything but downloads
mostlyclean: bundler-clean distclean $(APP_MOSTLYCLEAN_DEPS)
	rm -f composer*.lock
	rm -f composer.json
	rm -f patches.lock.json
	rm -f vendor-bin/**/composer.lock
	rm -f vendor-bin/**/patches.lock.json
	rm -f stamp.composer-core-versions
	rm -f $(BUILD_FLAVOUR_FILE)
	rm -rf .vite
	$(SILENT)git ls-files --error-unmatch package-lock.json > /dev/null 2>&1 || rm -f package-lock.json
	rm -f *.html
	rm -f stats.json
	rm -f $(APP_MOSTLYCLEAN_FILES)
.PHONY: mostlyclean

#@@ Really delete everything but the bare source files
realclean: mostlyclean downloadsclean
.PHONY: realclean

#@@ Remove non-npm non-composer downloads
downloadsclean:
	rm -rf $(DOWNLOADS_DIR)
.PHONY: downloadsclean

###############################################################################
#
# Tests and IDE support

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

TIDE_ENTRY ?= $(SRCDIR)/src/vue-app.ts

#@private
run-tide:
	$(EMACS) --batch --file $(TIDE_ENTRY) -l $(DEV_LIB_DIR)/scripts/tide-project-errors.el|tee tide-errors.log
.PHONY: run-tide

#@@ Runs the Emacs Tide IDE in batch mode and diagnoses TypeScript errors.
tide: dev-setup ts-app-config ts-types-files run-tide
.PHONY: tide

endif
