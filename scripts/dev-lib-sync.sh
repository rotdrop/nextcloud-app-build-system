#!/bin/bash
# Shared implementation of the make targets dev-lib-sync and
# dev-lib-sync-release, see makefile/dev-lib-sync.mk.
#
# Usage: dev-lib-sync.sh TARGET_NAME APP_DIR LIB_DIR REMOTE branch|tag REF TRAILER
set -e

name=$1 app_dir=$2 lib_dir=$3 remote=$4 kind=$5 ref=$6 trailer=$7

lib_path=$(realpath --relative-to="$app_dir" "$lib_dir")
branch=$(git -C "$app_dir" symbolic-ref --quiet --short HEAD || true)
if [ -z "$branch" ]; then
  echo "$name: $app_dir is on a detached HEAD, refusing to push." >&2; exit 1
fi
if [ -n "$(git -C "$lib_dir" status --porcelain)" ]; then
  echo "$name: $lib_path has uncommitted changes, refusing." >&2; exit 1
fi

case "$kind" in
  branch)
    upstream="$remote/$ref"
    git -C "$lib_dir" fetch "$remote"
    target=$upstream
    ;;
  tag)
    # The floating tag is force-moved, so a plain fetch keeps a stale one.
    git -C "$lib_dir" fetch --tags --force "$remote"
    upstream="tag $ref"
    # ^{commit} peels annotated tags.
    target=$(git -C "$lib_dir" rev-parse --verify --quiet "refs/tags/$ref^{commit}") || {
      echo "$name: tag $ref not found in $lib_path." >&2; exit 1
    }
    ;;
  *) echo "$name: unknown kind $kind" >&2; exit 2 ;;
esac

if [ -n "$(git -C "$lib_dir" rev-list -n 1 HEAD "^$target")" ]; then
  echo "$name: $lib_path has local commits not in $upstream, refusing." >&2; exit 1
fi
git -C "$lib_dir" checkout --quiet --detach "$target"
short=$(git -C "$lib_dir" rev-parse --short "$target")
description=$short
[ "$kind" = tag ] && description="$ref ($short)"
if git -C "$app_dir" diff --quiet -- "$lib_path" \
   && git -C "$app_dir" diff --cached --quiet -- "$lib_path"; then
  echo "$name: $lib_path is already at $upstream ($short), nothing to do."; exit 0
fi
git -C "$app_dir" add -- "$lib_path"
git -C "$app_dir" commit -m "Update $lib_path to $description" -m "$trailer" -- "$lib_path"
git -C "$app_dir" push "$remote" "HEAD:refs/heads/$branch"
