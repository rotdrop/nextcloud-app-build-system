# Scope Composer dependencies after including setup.mk and composer.mk.
ifndef _APP_BUILD_NAMESPACE_WRAPPER_INCLUDED
_APP_BUILD_NAMESPACE_WRAPPER_INCLUDED := 1

_NAMESPACE_WRAPPER_MAKEFILE := $(lastword $(MAKEFILE_LIST))
include $(dir $(lastword $(MAKEFILE_LIST)))scoped-vendor.mk
_NAMESPACE_WRAPPER_DEFAULT_GOAL := $(.DEFAULT_GOAL)

PHP_SCOPER ?= $(ABSSRCDIR)/vendor-bin/php-scoper/vendor/bin/php-scoper
MAKEFILE_DEP ?= Makefile
SCOPED_VENDOR_DIR = vendor-$(SCOPED_VENDOR_SUFFIX)
SCOPED_COMPOSER_JSON = composer-$(SCOPED_VENDOR_SUFFIX).json
SCOPED_COMPOSER_LOCK = composer-$(SCOPED_VENDOR_SUFFIX).lock
SCOPED_VENDOR_LINK_DIRS ?= vendor
SCOPED_COMPOSER_UPDATE_OPTIONS ?=
_SCOPED_COMPOSER_READY = $(BUILDDIR)/$(SCOPED_VENDOR_DIR)/.composer-ready
_SCOPED_VENDOR_READY = $(SCOPED_VENDOR_DIR)/.scoper-ready

php-scoper-install: $(PHP_SCOPER)
.PHONY: php-scoper-install

$(PHP_SCOPER): composer.lock
	if ! [ -x "$@" ]; then $(COMPOSER) bin php-scoper install; else touch "$@"; fi

ifneq ($(strip $(WRAPPER_GIT_DEPENDENCIES)),)
WRAPPER_PREV_BUILD_HASH := $(if $(wildcard $(ABSSRCDIR)/wrapper-build-hash),$(shell cat "$(ABSSRCDIR)/wrapper-build-hash"))
WRAPPER_GIT_BUILD_HASH := $(shell set -e; $(foreach dir,$(WRAPPER_GIT_DEPENDENCIES),echo "$(dir)"; git -C "$(dir)" rev-parse HEAD;))
ifneq ($(.SHELLSTATUS),0)
$(error Cannot read Git dependencies of PHP-Scoper)
endif

ifneq ($(WRAPPER_PREV_BUILD_HASH),$(WRAPPER_GIT_BUILD_HASH))
.PHONY: wrapper-build-hash
endif
wrapper-build-hash:
	@echo "GIT dependencies of PHP-Scoper have changed, need to rebuild the wrapper"
	@echo "OLD HASH $(WRAPPER_PREV_BUILD_HASH)"
	@echo "NEW HASH $(WRAPPER_GIT_BUILD_HASH)"
	printf '%s\n' "$(WRAPPER_GIT_BUILD_HASH)" > "$@"

$(_SCOPED_COMPOSER_READY): wrapper-build-hash
endif

$(SCOPED_COMPOSER_LOCK): $(SCOPED_COMPOSER_JSON) $(MAKEFILE_DEP) $(_NAMESPACE_WRAPPER_MAKEFILE)
	rm -f "$@"

# Success stamps keep partially generated directories from satisfying a retry.
$(BUILDDIR)/$(SCOPED_VENDOR_DIR): $(_SCOPED_COMPOSER_READY)

$(_SCOPED_COMPOSER_READY): $(SCOPED_COMPOSER_LOCK)
	mkdir -p "$(BUILDDIR)"
	$(if $(strip $(SCOPED_VENDOR_LINK_DIRS)),set -e; $(foreach dir,$(SCOPED_VENDOR_LINK_DIRS),ln -sfn "$(ABSSRCDIR)/$(dir)" "$(BUILDDIR)/$(dir)";))
	rm -rf "$(BUILDDIR)/$(SCOPED_VENDOR_DIR)"
	ln -sfn "$(DEV_LIB_DIR)/patches" "$(BUILDDIR)/composer-patches"
	env COMPOSER="$(ABSSRCDIR)/$(SCOPED_COMPOSER_JSON)" $(COMPOSER) -d$(BUILDDIR) install $(COMPOSER_OPTIONS)
	env COMPOSER="$(ABSSRCDIR)/$(SCOPED_COMPOSER_JSON)" $(COMPOSER) -d$(BUILDDIR) update $(COMPOSER_OPTIONS) $(SCOPED_COMPOSER_UPDATE_OPTIONS)
	touch "$@"

$(BUILDDIR)/$(SCOPED_VENDOR_DIR)/autoload.php: $(BUILDDIR)/$(SCOPED_VENDOR_DIR) $(SCOPED_COMPOSER_JSON) $(MAKEFILE_DEP)
	env COMPOSER="$(ABSSRCDIR)/$(SCOPED_COMPOSER_JSON)" $(COMPOSER) -d$(BUILDDIR) dump-autoload

composer-$(SCOPED_VENDOR_SUFFIX)-suggest:
	@printf '\n*** Scoped Composer Suggestions ***\n\n'
	env COMPOSER="$(ABSSRCDIR)/$(SCOPED_COMPOSER_JSON)" $(COMPOSER) -d$(BUILDDIR) suggest --all
.PHONY: composer-$(SCOPED_VENDOR_SUFFIX)-suggest

composer-suggest: composer-$(SCOPED_VENDOR_SUFFIX)-suggest

$(SCOPED_VENDOR_DIR): $(_SCOPED_VENDOR_READY)

$(_SCOPED_VENDOR_READY): $(MAKEFILE_DEP) $(_NAMESPACE_WRAPPER_MAKEFILE) $(PHP_SCOPER) scoper.inc.php $(_SCOPED_COMPOSER_READY)
	rm -f "$@"
	$(PHP_SCOPER) add-prefix -d$(BUILDDIR) --config=$(ABSSRCDIR)/scoper.inc.php --output-dir=$(ABSSRCDIR)/$(SCOPED_VENDOR_DIR) --force
# scoper does not handle symlinks
	if [ -d "$(BUILDDIR)/$(SCOPED_VENDOR_DIR)/bin" ]; then cp -a "$(BUILDDIR)/$(SCOPED_VENDOR_DIR)/bin" "$(ABSSRCDIR)/$(SCOPED_VENDOR_DIR)/"; fi
# scoper does not preserve executable bits
	find "$(ABSSRCDIR)/$(SCOPED_VENDOR_DIR)" -name bin -a -type d -exec chmod -R gu+x {} \;
# scoper does not rewrite the composer autoload maps, regenerate them
	env COMPOSER="$(ABSSRCDIR)/$(SCOPED_COMPOSER_JSON)" $(COMPOSER) dump-autoload
	test -r "$(SCOPED_VENDOR_DIR)/composer/autoload_real.php"
	if grep -q filesToLoad "$(SCOPED_VENDOR_DIR)/composer/autoload_real.php"; then $(call apply-scoped-autoload-patch,$(SCOPED_VENDOR_DIR)); fi
	touch "$@"

$(SCOPED_VENDOR_DIR)/autoload.php: $(SCOPED_VENDOR_DIR)

namespace-wrapper: php-scoper-install $(SCOPED_VENDOR_DIR)/autoload.php
.PHONY: namespace-wrapper

.DEFAULT_GOAL := $(_NAMESPACE_WRAPPER_DEFAULT_GOAL)
endif
