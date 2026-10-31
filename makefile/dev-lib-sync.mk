# Makefile fragment providing the manually invoked target dev-lib-sync
# which updates the git submodule DEV_LIB_DIR (this package) to the
# current origin/main, commits the changed submodule pointer and pushes
# it to the currently checked-out branch of the application. It is not a
# prerequisite of any other target. Needs ABSSRCDIR and DEV_LIB_DIR set
# by the including Makefile.

DEV_LIB_SYNC_REMOTE = origin
DEV_LIB_SYNC_BRANCH = main
DEV_LIB_SYNC_TRAILER = Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>

#@@ Update the dev-scripts/lib submodule to origin/main if necessary, commit only
#@@ the submodule update and push it to the current branch (never force-pushes,
#@@ never pushes other refs). Intended for local development only.
dev-lib-sync:
	@set -e; \
	app_dir='$(ABSSRCDIR)'; lib_dir='$(DEV_LIB_DIR)'; \
	remote='$(DEV_LIB_SYNC_REMOTE)'; upstream='$(DEV_LIB_SYNC_REMOTE)/$(DEV_LIB_SYNC_BRANCH)'; \
	lib_path=$$(realpath --relative-to="$$app_dir" "$$lib_dir"); \
	branch=$$(git -C "$$app_dir" symbolic-ref --quiet --short HEAD || true); \
	if [ -z "$$branch" ]; then \
	  echo "dev-lib-sync: $$app_dir is on a detached HEAD, refusing to push." >&2; exit 1; \
	fi; \
	if [ -n "$$(git -C "$$lib_dir" status --porcelain)" ]; then \
	  echo "dev-lib-sync: $$lib_path has uncommitted changes, refusing." >&2; exit 1; \
	fi; \
	git -C "$$lib_dir" fetch "$$remote"; \
	if [ -n "$$(git -C "$$lib_dir" rev-list -n 1 HEAD "^$$upstream")" ]; then \
	  echo "dev-lib-sync: $$lib_path has local commits not in $$upstream, refusing." >&2; exit 1; \
	fi; \
	git -C "$$lib_dir" checkout --quiet --detach "$$upstream"; \
	short=$$(git -C "$$lib_dir" rev-parse --short "$$upstream"); \
	if git -C "$$app_dir" diff --quiet -- "$$lib_path" \
	   && git -C "$$app_dir" diff --cached --quiet -- "$$lib_path"; then \
	  echo "dev-lib-sync: $$lib_path is already at $$upstream ($$short), nothing to do."; exit 0; \
	else \
	  git -C "$$app_dir" add -- "$$lib_path"; \
	  git -C "$$app_dir" commit -m "Update $$lib_path to $$short" -m '$(DEV_LIB_SYNC_TRAILER)' -- "$$lib_path"; \
	fi; \
	git -C "$$app_dir" push "$$remote" "HEAD:refs/heads/$$branch"
.PHONY: dev-lib-sync
