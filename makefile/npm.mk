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
package-lock.json:
	@test -f "$@" || { echo "package-lock.json is required; run 'make update-package-lock' to create or update it." >&2; exit 1; }

#@private
node_modules: package.json package-lock.json
	$(NPM) ci
	touch node_modules

# A requested update must finish before npm ci reads the lockfile.
ifneq ($(filter update-package-lock,$(MAKECMDGOALS)),)
node_modules: update-package-lock
package-lock.json: update-package-lock
npm-dev npm-build: update-package-lock
endif

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
npm-dev: build-flavour-dev
	$(MAKE) $(BUNDLER_TARGETS)
.PHONY: npm-dev

#@private
npm-build: build-flavour-build
	$(MAKE) $(BUNDLER_TARGETS)
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

#@@ Update dependencies in package-lock.json
update-package-lock:
	$(NPM) update --package-lock-only
.PHONY: update-package-lock

PACKAGE_LOCK_BRANCH ?= chore/update-package-lock

#@@ Open a pull request for a changed package-lock.json (no-op if unchanged)
commit-package-lock:
	$(SILENT)if git diff --quiet HEAD -- package-lock.json; then\
	  echo "package-lock.json is unchanged, nothing to do.";\
	else\
	  base=$$(git rev-parse --abbrev-ref HEAD) && \
	  git checkout -B "$(PACKAGE_LOCK_BRANCH)" && \
	  git commit -m "chore(deps): update package-lock.json" -- package-lock.json && \
	  git push --force-with-lease -u origin "$(PACKAGE_LOCK_BRANCH)" && \
	  { gh pr create --base "$$base" --head "$(PACKAGE_LOCK_BRANCH)" \
	      --title "chore(deps): update package-lock.json" \
	      --body "Automated update of package-lock.json." \
	    || echo "A pull request for $(PACKAGE_LOCK_BRANCH) may already exist."; }; \
	  status=$$?; git checkout "$$base"; exit $$status;\
	fi
.PHONY: commit-package-lock

#@@ Removes bundler builds
bundler-clean:
	rm -rf ./js/*
	rm -rf ./css/*
.PHONY: bundler-clean

#@private
webpack-clean: bundler-clean
.PHONY: webpack-clean
