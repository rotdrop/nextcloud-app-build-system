#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Generic release script run by "make release": tag the version found in
# appinfo/info.xml as v<version> and push the tag, which triggers the release
# workflow. An optional argument must equal the version in info.xml.
#
# Environment: RELEASE_BRANCH (default: the default branch of origin),
# RELEASE_REMOTE (default: origin).
set -euo pipefail

if [[ $# -gt 1 ]]; then
  echo "Usage: $0 [VERSION] (for example: 1.2.2 or 1.2.2-rc1)" >&2
  exit 2
fi

remote=${RELEASE_REMOTE:-origin}
cd "$(git rev-parse --show-toplevel)"

version=$(sed -n 's:.*<version>\(.*\)</version>.*:\1:p' appinfo/info.xml | head -n 1)
if [[ -z $version ]]; then
  echo "No <version> found in appinfo/info.xml." >&2
  exit 1
fi
if [[ $# -eq 1 && ${1#v} != "$version" ]]; then
  echo "Requested version ${1#v} differs from appinfo/info.xml version $version." >&2
  exit 1
fi
tag="v$version"

branch=${RELEASE_BRANCH:-}
if [[ -z $branch ]]; then
  branch=$(git symbolic-ref --quiet --short "refs/remotes/$remote/HEAD" 2>/dev/null || true)
  branch=${branch#"$remote"/}
  [[ -n $branch ]] || branch=$(LC_ALL=C git remote show "$remote" | sed -n 's/^ *HEAD branch: //p')
fi
if [[ $(git branch --show-current) != "$branch" ]]; then
  echo "Release must be run from the $branch branch." >&2
  exit 1
fi
if [[ -n $(git status --porcelain) ]]; then
  echo "Working tree must be clean before releasing." >&2
  exit 1
fi
if git show-ref --verify --quiet "refs/tags/$tag"; then
  echo "Tag $tag already exists locally; the version is already tagged." >&2
  exit 1
fi
if [[ -n $(git ls-remote --tags "$remote" "refs/tags/$tag") ]]; then
  echo "Tag $tag already exists on $remote; the version is already published." >&2
  exit 1
fi
remote_head=$(git ls-remote --heads "$remote" "refs/heads/$branch")
if [[ -z $remote_head || ${remote_head%%$'\t'*} != "$(git rev-parse HEAD)" ]]; then
  echo "HEAD must match $remote/$branch. Synchronize and push reviewed commits before releasing." >&2
  exit 1
fi

git tag -a "$tag" -m "Release $tag"
if ! git push "$remote" "refs/tags/$tag:refs/tags/$tag"; then
  echo "Push failed. Local tag $tag has been retained; inspect $remote before retrying." >&2
  exit 1
fi
echo "Pushed $tag. Approve the release environment deployments in GitHub Actions."
