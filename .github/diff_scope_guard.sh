#!/usr/bin/env bash
# Diff-scope guard (issue #8): entry PRs may touch only entries/<slug>/ + index.json.
#
# Input: $1 = file containing the PR's changed paths, one per line
#        (produced in CI by: git diff --name-only "$(git merge-base origin/$BASE_REF HEAD)" HEAD).
# Exit 0: in scope. Exit 1: violation, one line per offending file on stdout.
# Fail-closed: missing/unreadable input is an error, not a pass.
#
# Rules:
#   - A PR touching entries/ must not also touch any of: schemas/, tools/,
#     fixtures/, .github/, README.md, CONTRIBUTING.md, LICENSE, .gitattributes.
#   - A PR touching entries/ must stay inside ONE entries/<slug>/ directory.
#   - index.json is always allowed (entry PRs must regenerate it).
#   - Infra-only PRs (no entries/ changes) always pass.
set -euo pipefail

if [ "$#" -ne 1 ] || [ ! -r "$1" ]; then
  echo "diff-scope guard: changed-paths file missing or unreadable: ${1:-<none>}" >&2
  exit 1
fi

changed_file="$1"
entry_touched=false
declare -A entry_dirs=()
fail=false

while IFS= read -r path; do
  [ -n "$path" ] || continue
  case "$path" in
    entries/*)
      entry_touched=true
      slug="${path#entries/}"
      slug="${slug%%/*}"
      entry_dirs["$slug"]=1
      ;;
  esac
done < "$changed_file"

if [ "$entry_touched" = true ]; then
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    case "$path" in
      schemas/*|tools/*|fixtures/*|.github/*|README.md|CONTRIBUTING.md|LICENSE|.gitattributes)
        echo "FAIL: entry PR touches out-of-scope file: $path (entry PRs may touch only entries/<slug>/ + index.json)"
        fail=true
        ;;
    esac
  done < "$changed_file"

  if [ "${#entry_dirs[@]}" -gt 1 ]; then
    echo "FAIL: PR touches more than one entry directory (one entry per PR): ${!entry_dirs[*]}"
    fail=true
  fi
fi

if [ "$fail" = true ]; then
  exit 1
fi

echo "diff-scope guard: OK"
