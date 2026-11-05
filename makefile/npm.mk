# Make fragment for generic npm / bundler related targets

BUNDLER_TARGETS ?= $(ABSSRCDIR)/js/asset-meta.json

ifeq ($(BUNDLER_CONFIG),)
BUNDLER_CONFIG = webpack.config.js
endif

# Accept legacy dependency inputs and expose the resolved values to older apps.
BUNDLER_DEPS := $(sort $(BUNDLER_DEPS) $(WEBPACK_DEPS) $(MAKEFILE_DEP) node_modules package-lock.json package.json $(BUNDLER_CONFIG) eslint.config.mjs)
WEBPACK_DEPS = $(BUNDLER_DEPS)
WEBPACK_TARGETS = $(BUNDLER_TARGETS)

#@private
package-lock.json: package.json $(BUNDLER_CONFIG) $(MAKEFILE_DEP) $(THIRD_PARTY_NPM_DEPS)
	{ [ -d package-lock.json ] && [ test -d node_modules ]; } || $(NPM) install
	$(NPM) update
	touch package-lock.json

#@private
node_modules:
	$(NPM) install
	touch package-lock.json
	touch node_modules

BUILD_FLAVOUR_FILE = $(ABSSRCDIR)/build-flavour
PREV_BUILD_FLAVOUR = $(shell cat $(BUILD_FLAVOUR_FILE) 2> /dev/null || echo)

#@private
build-flavour-dev:
ifneq ($(PREV_BUILD_FLAVOUR), dev)
	$(MAKE) bundler-clean
	echo dev > $(BUILD_FLAVOUR_FILE)
endif
.PHONY: build-flavour-dev

#@private
build-flavour-build:
ifneq ($(PREV_BUILD_FLAVOUR), build)
	$(MAKE) bundler-clean
	echo build > $(BUILD_FLAVOUR_FILE)
endif
.PHONY: build-flavour-build

#@private
$(BUNDLER_TARGETS): $(BUILD_FLAVOUR_FILE) $(BUNDLER_DEPS)
	$(MAKE) bundler-clean
	@env LC_ALL=C $(MAKE) $(BUNDLER_DEPS)
	$(NPM) run $(shell cat $(BUILD_FLAVOUR_FILE)) || { status=$$?; rm -f $(BUNDLER_TARGETS); exit $$status; }

#@private
npm-dev: build-flavour-dev $(BUNDLER_TARGETS)
.PHONY: npm-dev

#@private
npm-build: build-flavour-build $(BUNDLER_TARGETS)
.PHONY: npm-build

#@@ Linting
lint:
	$(NPM) run lint
.PHONY: lint

#@@ Lint and fix (be careful!)
lint-fix:
	$(NPM) run lint:fix
.PHONY: lint-fix

#@@ Style linting
stylelint:
	$(NPM) run stylelint
.PHONY: stylelint

#@@ Style linting and apply fixes (be carful!)
stylelint-fix:
	$(NPM) run stylelint:fix
.PHONY: stylelint-

#@@ Removes bundler builds
bundler-clean:
	rm -rf ./js/*
	rm -rf ./css/*
.PHONY: bundler-clean

#@private
webpack-clean: bundler-clean
.PHONY: webpack-clean
