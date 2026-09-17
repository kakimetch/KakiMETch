#!/bin/sh
set -eu

range="$1"

bad="$(
  git log --format='%h %s' "$range" |
    grep -E -v '^[0-9a-f]+ (Merge |Revert |fixup! |squash! |(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)(\([a-z0-9._-]+\))?!?: .+)'
  true
)"

if [ -n "$bad" ]; then
  cat >&2 <<'EOF'
Commit messages must use Conventional Commits:

  type(scope): summary
  type: summary

Allowed types: build, chore, ci, docs, feat, fix, perf, refactor, revert, style, test.
EOF
  printf '%s\n' "$bad" >&2
  exit 1
fi
