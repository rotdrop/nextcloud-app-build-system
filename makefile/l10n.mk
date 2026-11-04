# Generate committed translation inputs for packages used by the app.
# Include after setting ABSSRCDIR and any destination overrides.

ABSSRCDIR ?= $(CURDIR)
PHP ?= php
NODE ?= node
NPX ?= npx
L10N_SOURCES_DIR ?= $(ABSSRCDIR)/l10n-sources
APP_TOOLKIT_DIR ?= $(ABSSRCDIR)/vendor/rotdrop/nextcloud-app-toolkit
APP_TOOLKIT_L10N_DEST ?= $(L10N_SOURCES_DIR)/toolkit-strings.php
VUE_COMPONENTS_L10N_DEST ?= $(L10N_SOURCES_DIR)/vue-components-strings.js

_L10N_DEFAULT_GOAL := $(.DEFAULT_GOAL)
_L10N_COMPOSER_MANIFESTS := $(wildcard $(ABSSRCDIR)/composer.json $(ABSSRCDIR)/composer.json.in)
_L10N_HAS_TOOLKIT :=
_L10N_HAS_VUE_COMPONENTS :=

ifneq ($(_L10N_COMPOSER_MANIFESTS),)
_L10N_HAS_TOOLKIT := $(shell $(PHP) -r 'foreach (array_slice($$argv, 1) as $$file) { $$json = json_decode(file_get_contents($$file), true, 512, JSON_THROW_ON_ERROR); if (isset($$json["require"]["rotdrop/nextcloud-app-toolkit"]) || isset($$json["require-dev"]["rotdrop/nextcloud-app-toolkit"])) { echo "yes"; } }' $(_L10N_COMPOSER_MANIFESTS))
ifneq ($(.SHELLSTATUS),0)
$(error Cannot read Composer manifests for translation extraction)
endif
endif

ifneq ($(wildcard $(ABSSRCDIR)/package.json),)
_L10N_HAS_VUE_COMPONENTS := $(shell $(NODE) -e 'const fs = require("node:fs"); const manifest = JSON.parse(fs.readFileSync(process.argv[1], "utf8")); if (["dependencies", "devDependencies", "optionalDependencies", "peerDependencies"].some(section => Object.hasOwn(manifest[section] || {}, "@rotdrop/nextcloud-vue-components"))) console.log("yes");' "$(ABSSRCDIR)/package.json")
ifneq ($(.SHELLSTATUS),0)
$(error Cannot read package.json for translation extraction)
endif
endif

ifneq ($(_L10N_HAS_TOOLKIT),)
include $(APP_TOOLKIT_DIR)/tools/l10n.mk
else
toolkit-l10n:
.PHONY: toolkit-l10n
endif

#@@ Generate package string catalogues before creating the app's POT files.
l10n-sources: toolkit-l10n vue-components-l10n
.PHONY: l10n-sources

#@@ Generate the Vue components' string catalogue, commit the result.
vue-components-l10n:
ifneq ($(_L10N_HAS_VUE_COMPONENTS),)
	mkdir -p "$(dir $(VUE_COMPONENTS_L10N_DEST))"
	cd "$(ABSSRCDIR)" && $(NPX) --no-install @rotdrop/nextcloud-vue-components extract-l10n-strings "$(VUE_COMPONENTS_L10N_DEST)"
endif
.PHONY: vue-components-l10n

.DEFAULT_GOAL := $(_L10N_DEFAULT_GOAL)
