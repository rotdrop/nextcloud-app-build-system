# Make fragment for generic npm / bundler related targets

BUNDLER_TARGETS ?= $(ABSSRCDIR)/js/asset-meta.json

ifeq ($(BUNDLER_CONFIG),)
BUNDLER_CONFIG = webpack.config.js
endif

# Accept legacy dependency inputs and expose the resolved values to older apps.
BUNDLER_DEPS := $(sort $(BUNDLER_DEPS) $(WEBPACK_DEPS) $(MAKEFILE_DEP) node_modules package-lock.json package.json $(BUNDLER_CONFIG) eslint.config.mjs)
WEBPACK_DEPS = $(BUNDLER_DEPS)
WEBPACK_TARGETS = $(BUNDLER_TARGETS)

package-lock.json:
	@test -f "$@" || { echo "package-lock.json is required; run 'make update-package-lock' to create or update it." >&2; exit 1; }

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

build-flavour-dev:
ifneq ($(PREV_BUILD_FLAVOUR), dev)
	$(MAKE) bundler-clean
	echo dev > $(BUILD_FLAVOUR_FILE)
endif
.PHONY: build-flavour-dev

build-flavour-build:
ifneq ($(PREV_BUILD_FLAVOUR), build)
	$(MAKE) bundler-clean
	echo build > $(BUILD_FLAVOUR_FILE)
endif
.PHONY: build-flavour-build

$(BUNDLER_TARGETS): $(BUILD_FLAVOUR_FILE) $(BUNDLER_DEPS)
	$(MAKE) bundler-clean
	@env LC_ALL=C $(MAKE) $(BUNDLER_DEPS)
	$(NPM) run $(shell cat $(BUILD_FLAVOUR_FILE)) || { status=$$?; rm -f $(BUNDLER_TARGETS); exit $$status; }

npm-dev: build-flavour-dev
	$(MAKE) $(BUNDLER_TARGETS)
.PHONY: npm-dev

npm-build: build-flavour-build
	$(MAKE) $(BUNDLER_TARGETS)
.PHONY: npm-build

NODE ?= node
FRONTEND_TEST_SCRIPT ?= test
FRONTEND_TEST_ARGS ?= --run

frontend-tests: ## Run the configured frontend suite once, or warn if no test script exists
	$(SILENT)if [ ! -f package.json ]; then\
	  echo "Warning: package.json not found; skipping frontend tests." >&2;\
	elif $(NODE) -e 'const fs = require("node:fs"); const p = JSON.parse(fs.readFileSync("package.json", "utf8")); const s = p.scripts?.[process.argv[1]]; if (s !== undefined && typeof s !== "string") throw new TypeError("npm test script must be a string"); process.exit(s?.trim() ? 0 : 2)' "$(FRONTEND_TEST_SCRIPT)"; then\
	  $(MAKE) run-frontend-tests;\
	else\
	  status=$$?;\
	  if [ "$$status" -eq 2 ]; then\
	    echo "Warning: npm script '$(FRONTEND_TEST_SCRIPT)' not found; skipping frontend tests." >&2;\
	  else\
	    exit "$$status";\
	  fi;\
	fi
.PHONY: frontend-tests

run-frontend-tests: node_modules
	$(NPM) run $(FRONTEND_TEST_SCRIPT) -- $(FRONTEND_TEST_ARGS)
.PHONY: run-frontend-tests

lint: ## Linting
	$(NPM) run lint
.PHONY: lint

lint-fix: ## Lint and fix (be careful!)
	$(NPM) run lint:fix
.PHONY: lint-fix

stylelint: ## Style linting
	$(NPM) run stylelint
.PHONY: stylelint

stylelint-fix: ## Style linting and apply fixes (be careful!)
	$(NPM) run stylelint:fix
.PHONY: stylelint-

update-package-lock: ## Update dependencies in package-lock.json
	$(NPM) update --package-lock-only
.PHONY: update-package-lock

PACKAGE_LOCK_BRANCH ?= chore/update-package-lock

commit-package-lock: ## Open a pull request for a changed package-lock.json (no-op if unchanged)
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

bundler-clean: ## Removes bundler builds
	rm -rf ./js/*
	rm -rf ./css/*
.PHONY: bundler-clean

webpack-clean: bundler-clean
.PHONY: webpack-clean
