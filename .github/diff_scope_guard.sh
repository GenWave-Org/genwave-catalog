#!/usr/bin/env bash
# Diff-scope guard (issue #8): entry PRs may touch only
# entries/<kind-folder>/<slug>/ + index.json (kind-folder nesting: gh-33).
#
# Input: $1 = file containing the PR's changed paths, one per line
#        (produced in CI by: git diff --name-only "$(git merge-base origin/$BASE_REF HEAD)" HEAD).
# Exit 0: in scope. Exit 1: violation, one line per offending file on stdout.
# Fail-closed: missing/unreadable input is an error, not a pass.
#
# Rules:
#   - A PR touching entries/ must not also touch any of: schemas/, tools/,
#     fixtures/, .github/, README.md, CONTRIBUTING.md, LICENSE, .gitattributes.
#   - A PR touching entries/ must stay inside ONE
#     entries/<kind-folder>/<slug>/ directory — a path under entries/ with
#     fewer than 4 segments (entries/<kind-folder>/<file>, no slug segment
#     at all), or whose kind-folder segment isn't one of the four known
#     names, is its own violation, named with a clear error rather than
#     silently mis-parsed into a bogus "slug".
#   - index.json is always allowed (entry PRs must regenerate it).
#   - Infra-only PRs (no entries/ changes) always pass.
set -euo pipefail

if [ "$#" -ne 1 ] || [ ! -r "$1" ]; then
  echo "diff-scope guard: changed-paths file missing or unreadable: ${1:-<none>}" >&2
  exit 1
fi

changed_file="$1"
KNOWN_KIND_FOLDERS="personas themes fonts shows"
entry_touched=false
declare -A entry_dirs=()
fail=false

is_known_kind_folder() {
  local candidate="$1" kind
  for kind in $KNOWN_KIND_FOLDERS; do
    [ "$candidate" = "$kind" ] && return 0
  done
  return 1
}

while IFS= read -r path; do
  [ -n "$path" ] || continue
  case "$path" in
    entries/*)
      entry_touched=true
      # path = entries/<kind-folder>/<slug>/... — need at least 4 segments
      # (entries, kind-folder, slug, and something inside the entry).
      IFS='/' read -r -a segments <<<"$path"
      if [ "${#segments[@]}" -lt 4 ]; then
        echo "FAIL: entries/ path has no slug segment: $path (expected entries/<kind-folder>/<slug>/...)"
        fail=true
        continue
      fi
      kind_folder="${segments[1]}"
      if ! is_known_kind_folder "$kind_folder"; then
        echo "FAIL: entries/ path's kind-folder segment is not one of the four known kind folders" \
          "($KNOWN_KIND_FOLDERS): $path"
        fail=true
        continue
      fi
      slug="${segments[2]}"
      entry_dirs["$kind_folder/$slug"]=1
      ;;
  esac
done < "$changed_file"

if [ "$entry_touched" = true ]; then
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    case "$path" in
      schemas/*|tools/*|fixtures/*|.github/*|README.md|CONTRIBUTING.md|LICENSE|.gitattributes)
        echo "FAIL: entry PR touches out-of-scope file: $path (entry PRs may touch only entries/<kind-folder>/<slug>/ + index.json)"
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
