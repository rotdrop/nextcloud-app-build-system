# Makefile fragment setting the common build variables, e.g. app-name
# and namespaces parsed from info.xml. Needs the variables ABSSRCDIR
# (absolute path of the source directory) set by the including
# Makefile.

include $(dir $(lastword $(MAKEFILE_LIST)))scoped-vendor.mk
# evaluate the (expensive) xpath look-ups only once
APP_NAME := $(shell $(XPATH) -q -e '/info/id/text()' $(APP_INFO))
APP_VERSION := $(shell $(XPATH) -q -e '/info/version/text()' $(APP_INFO))
APP_NAMESPACE := $(shell $(XPATH) -q -e '/info/namespace/text()' $(APP_INFO))
CLOUD_MAX_VERSION := $(shell $(XPATH) -q -e 'string(/info/dependencies/nextcloud/@max-version)' $(APP_INFO))

BUILDDIR ?= ./build
ABSBUILDDIR ?= $(ABSSRCDIR)/build
BUILD_TOOLS_DIR ?= $(BUILDDIR)/tools
DOWNLOADS_DIR ?= ./downloads
CONFIG_DIR ?= ./config
TYPESCRIPT_CONVERTER ?= $(ABSSRCDIR)/dev-scripts/php-to-typescript.php
TS_TYPES_DIR ?= $(ABSBUILDDIR)/ts-types
TS_PHP_SOURCE_DIRS ?= lib vendor-$(SCOPED_VENDOR_SUFFIX)/rotdrop/nextcloud-app-toolkit/src
WRAPPER_NAMESPACE_POSTFIX ?= $(SCOPED_NAMESPACE_POSTFIX)

# Composer identifies "files" autoloads by a hash of package and file
# name. Namespaced copies of a package in different apps would thus
# suppress each other. The patch prefixes the identifiers with an app
# specific string. Usage, after "composer dump-autoload" of the
# namespaced vendor tree:
#   $(call apply-scoped-autoload-patch,vendor-$(SCOPED_VENDOR_SUFFIX))
SCOPED_AUTOLOAD_PATCH = $(DEV_LIB_DIR)/patches/composer/scoped_autoload_real.patch
apply-scoped-autoload-patch = cd $(1) && sed -e 's/@FILE_IDENTIFIER_PREFIX@/OCA_$(APP_NAMESPACE)_$(SCOPED_NAMESPACE_POSTFIX)/g' $(SCOPED_AUTOLOAD_PATCH) | patch -p1 -N

# manually invoked helper target; keep it from becoming the default goal
include $(DEV_LIB_DIR)/makefile/dev-lib-sync.mk
.DEFAULT_GOAL :=
