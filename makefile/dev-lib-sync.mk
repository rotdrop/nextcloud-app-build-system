# Makefile fragment providing the manually invoked target dev-lib-sync
# which updates the git submodule DEV_LIB_DIR (this package) to the
# current origin/main, commits the changed submodule pointer and pushes
# it to the currently checked-out branch of the application. The target
# dev-lib-sync-release does the same for the tag DEV_LIB_SYNC_TAG. It is not a
# prerequisite of any other target. Needs ABSSRCDIR and DEV_LIB_DIR set
# by the including Makefile.

DEV_LIB_SYNC_SCRIPT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))../scripts/dev-lib-sync.sh)
DEV_LIB_SYNC_REMOTE = origin
DEV_LIB_SYNC_BRANCH = main
DEV_LIB_SYNC_TAG = v1
DEV_LIB_SYNC_TRAILER = Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>

# Commits only the submodule update and pushes it to the current branch (never
# force-pushes, never pushes other refs). Intended for local development only.
dev-lib-sync: ## Update the dev-scripts/lib submodule to origin/main, commit and push
	@'$(DEV_LIB_SYNC_SCRIPT)' dev-lib-sync '$(ABSSRCDIR)' '$(DEV_LIB_DIR)' \
	  '$(DEV_LIB_SYNC_REMOTE)' branch '$(DEV_LIB_SYNC_BRANCH)' '$(DEV_LIB_SYNC_TRAILER)'

# DEV_LIB_SYNC_TAG defaults to v1, the release line the reusable workflows are
# pinned to.
dev-lib-sync-release: ## Like dev-lib-sync, but update to the commit of the tag DEV_LIB_SYNC_TAG
	@'$(DEV_LIB_SYNC_SCRIPT)' dev-lib-sync-release '$(ABSSRCDIR)' '$(DEV_LIB_DIR)' \
	  '$(DEV_LIB_SYNC_REMOTE)' tag '$(DEV_LIB_SYNC_TAG)' '$(DEV_LIB_SYNC_TRAILER)'
.PHONY: dev-lib-sync dev-lib-sync-release
