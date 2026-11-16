#!/usr/bin/env bash
# Tags a HaltOS release. GitHub Actions then publishes it, and servers pick it up with `sudo haltos update`.
# Usage: tools/release.sh 1.1.0   (VERSION and CHANGELOG.md must already say 1.1.0 on main)
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."

v=${1:-}
die() {
    echo "release: $*" >&2
    exit 1
}
[[ $v =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "give a version like 1.1.0"
[ "$(git branch --show-current)" = main ] || die "switch to main first"
[ -z "$(git status --porcelain)" ] || die "commit or stash your changes first"
git pull -q --ff-only
[ "$(cat VERSION)" = "$v" ] || die "VERSION says $(cat VERSION), bump it to $v in a PR first"
grep -q "^## $v" CHANGELOG.md || die "CHANGELOG.md has no '## $v' section"
! git rev-parse -q --verify "refs/tags/v$v" >/dev/null || die "v$v already exists"

git tag -a "v$v" -m "HaltOS $v"
git push -q origin "v$v"
echo "tagged v$v, GitHub Actions publishes the release: https://github.com/halitsever/haltos/actions"
