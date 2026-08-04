#!/usr/bin/env bash
# Local CI mirror for genwave-catalog. Mirrors .github/workflows/ci.yml's
# checks on demand:
#   1. tools/validate.py against the real (good) entries/           -> green
#   2. tools/validate.py against each tools/testdata/red/<variant>/ -> the
#      specific failure line for that rule, and nothing else would suffice
#   3. tools/build_index.py determinism: run twice, diff, expect none
#   4. the built index excludes example-dj
#   5. the committed index.json matches a fresh rebuild — same drift check
#      ci.yml runs, so "added an entry, forgot to regenerate" fails locally
#   6. tools/build_index.py against a green fixture tree: per-file sha256
#      (recomputed and compared), the audience field, relative-only paths,
#      sorted slugs, and example-dj excluded when present
#   7. tools/lint.py against the real (good) entries/                -> exit 0
#      (hard-clean: no HARD violations on the shelf). WARN-tier findings on
#      real entries are allowed and never fail this check — warn-first is
#      the ratified posture (SPEC F89.6; CONTRIBUTING: "Warnings alone won't
#      block your PR") — the shelf also happens to be warning-free as of
#      2026-08-02, but that fact is not what the harness asserts
#   8. tools/lint.py against tools/testdata/red/<variant>/ (oversize-soul,
#      dead-pronunciation-rule) -> the specific HARD failure line(s), exact
#      dead-rule count, and no dead-rule/word-repeat stacking
#   9. tools/lint.py against tools/testdata/warn/heavy-card/          -> every
#      WARN-tier rule fires exactly once and exit stays 0; the prompt-weight
#      number is cross-checked against an independent soul+3-longest-quirks
#      computation; GITHUB_ACTIONS=1 emits ::warning annotations only, never
#      plain WARN lines
#  10. tools/lint.py's symlink guard: a symlinked entry directory is never
#      read, even when its target would otherwise produce warnings
#  11. .github/workflows/ci.yml wires tools/lint.py into the validate job —
#      same drift-check spirit as item 5, so a CI edit that drops the lint
#      step fails here too, not just after merge
#
# Every python3/build_index.py invocation below has its exit status checked
# explicitly (`set -uo pipefail`, not `set -e`, since several steps below —
# the red-variant checks — deliberately run a command expected to fail and
# must inspect its exit code rather than let it abort the script). A step
# whose command silently fails must never be scored as a pass just because a
# later comparison happened to also come back clean.
#
# The oversize-card fixture's persona.json is >256KB, so it is generated here
# at test time instead of being committed (see .gitignore) — kept out of the
# repo to keep it small; regenerate any time via this script.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

RED_DIR="tools/testdata/red"
GREEN_FIXTURE="tools/testdata/green/valid-dj"
HEAVY_CARD_DIR="tools/testdata/warn/heavy-card"
OVERSIZE_CARD="$RED_DIR/oversize-card/entries/oversize-card/oversize-card.persona.json"

FAILURES=0
pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; FAILURES=$((FAILURES + 1)); }

# Shared by check_red_variant (tools/validate.py reds) and check_red_lint
# (tools/lint.py reds): run `tool --root RED_DIR/variant`, expect a non-zero
# exit whose output names `expect`. validate.py has no WARN tier, so
# tier_aware=false there keeps the plain substring-match semantics it always
# had. lint.py's WARN/HARD split means a substring match alone would let a
# mutant that only crossed the WARN threshold satisfy a HARD-tier
# expectation, so tier_aware=true additionally requires the matching line
# not be WARN-prefixed — HARD lines never carry the "WARN " prefix in either
# of lint.py's output branches (see format_finding).
check_red() {
    local tool="$1" tier_aware="$2" msg_infix="$3" variant="$4" expect="$5"
    local output status
    output=$(python3 "$tool" --root "$RED_DIR/$variant" 2>&1)
    status=$?
    echo "$output"
    local matched=1
    if [[ "$tier_aware" == "true" ]]; then
        grep -F "$expect" <<<"$output" | grep -qv '^WARN ' && matched=0
    else
        grep -qF "$expect" <<<"$output" && matched=0
    fi
    if [[ $status -ne 0 && $matched -eq 0 ]]; then
        pass "$variant fails ${msg_infix}naming '$expect'"
    else
        fail "$variant did not fail ${msg_infix}naming '$expect' (exit=$status)"
    fi
    echo
}

KIND_GREEN_FIXTURE="tools/testdata/green/valid-theme"
KIND_RED_DIR="tools/testdata/red"

TMP_GREEN_TREE=""
TMP_PRON_TREE=""
TMP_SYMLINK_TREE=""
TMP_KIND_TREE=""
TMP_THEME_TREE=""
cleanup() {
    rm -f "$OVERSIZE_CARD"
    [[ -n "$TMP_GREEN_TREE" ]] && rm -rf "$TMP_GREEN_TREE"
    [[ -n "$TMP_PRON_TREE" ]] && rm -rf "$TMP_PRON_TREE"
    [[ -n "$TMP_SYMLINK_TREE" ]] && rm -rf "$TMP_SYMLINK_TREE"
    [[ -n "$TMP_KIND_TREE" ]] && rm -rf "$TMP_KIND_TREE"
    [[ -n "$TMP_THEME_TREE" ]] && rm -rf "$TMP_THEME_TREE"
}
trap cleanup EXIT

echo "== validate.py: good entries (expect green) =="
output=$(python3 tools/validate.py 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "good entries validate clean"
else
    fail "good entries validate clean (expected exit 0, got $status)"
fi
echo

echo "== schema + fixture: pronunciations[] is declared and the green fixture exercises its shapes (SPEC F89.5 / T151) =="
tmp_pron_check="$(mktemp)"
cat >"$tmp_pron_check" <<'PY'
import json
import sys
from pathlib import Path

SCHEMA_PATH = Path("schemas/persona-card.schema.json")
green_fixture = Path(sys.argv[1])
card_path = green_fixture / "valid-dj.persona.json"

schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
card = json.loads(card_path.read_text(encoding="utf-8"))

errors = []
if "pronunciations" not in schema.get("properties", {}):
    errors.append(f"{SCHEMA_PATH}: properties: 'pronunciations' is not declared — the schema does not know the field yet")

pronunciations = card.get("pronunciations")
if not isinstance(pronunciations, list) or not pronunciations:
    errors.append(f"{card_path}: pronunciations is missing or empty — the fixture no longer exercises the field")
else:
    has_nonblank_word = any(
        isinstance(r, dict) and isinstance(r.get("word"), str) and r.get("word") != "" for r in pronunciations
    )
    has_no_word_key = any(isinstance(r, dict) and "word" not in r for r in pronunciations)
    has_null_word = any(isinstance(r, dict) and "word" in r and r.get("word") is None for r in pronunciations)
    if not has_nonblank_word:
        errors.append(f"{card_path}: pronunciations is missing a rule with a non-empty string 'word'")
    if not has_no_word_key:
        errors.append(f"{card_path}: pronunciations is missing a rule with no 'word' key at all")
    if not has_null_word:
        errors.append(f"{card_path}: pronunciations is missing a rule with 'word' explicitly null")

if errors:
    for line in errors:
        print(line)
    sys.exit(1)
print("schema declares pronunciations and the green fixture exercises word/no-word/null-word shapes")
PY
if python3 "$tmp_pron_check" "$GREEN_FIXTURE"; then
    pass "schema declares pronunciations[] and the green fixture exercises word/no-word/null-word shapes"
else
    fail "schema declares pronunciations[] and the green fixture exercises word/no-word/null-word shapes"
fi
rm -f "$tmp_pron_check"
echo

echo "== validate.py: green fixture pronunciations[] validate against a schema that knows the field (SPEC F89.5 / T151) =="
TMP_PRON_TREE="$(mktemp -d)"
mkdir -p "$TMP_PRON_TREE/entries/valid-dj"
cp "$GREEN_FIXTURE/valid-dj.persona.json" "$TMP_PRON_TREE/entries/valid-dj/valid-dj.persona.json"
cp "$GREEN_FIXTURE/valid-dj.meta.json" "$TMP_PRON_TREE/entries/valid-dj/valid-dj.meta.json"
output=$(python3 tools/validate.py --root "$TMP_PRON_TREE" 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "green valid-dj pronunciations[] validate against a schema that knows the field"
else
    fail "green valid-dj pronunciations[] validate against a schema that knows the field (expected exit 0, got $status)"
fi
echo

echo "== validate.py: red variants (expect the specific failure line) =="

check_red_variant() {
    check_red tools/validate.py false "" "$1" "$2"
}

check_red_variant bad-slug-mismatch "slug-mismatch"
check_red_variant missing-audience "'audience' is a required property"
check_red_variant one-sample "samplePatter"
check_red_variant bad-json "json-parse"
check_red_variant bad-date "bad-date"
check_red_variant bad-pronunciations-type "schema: pronunciations/0/"

echo "== validate.py: kind-aware theme-entry validation (schemas/theme-manifest.schema.json + schemas/theme-meta.schema.json, SPEC F103.2 / T179) =="

echo "-- green valid-theme fixture validates clean end-to-end as a kind:\"theme\" entry --"
TMP_THEME_TREE="$(mktemp -d)"
mkdir -p "$TMP_THEME_TREE/entries/valid-theme"
cp "$KIND_GREEN_FIXTURE/valid-theme.theme.json" "$TMP_THEME_TREE/entries/valid-theme/valid-theme.theme.json"
cp "$KIND_GREEN_FIXTURE/valid-theme.meta.json" "$TMP_THEME_TREE/entries/valid-theme/valid-theme.meta.json"
output=$(python3 tools/validate.py --root "$TMP_THEME_TREE" 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "green valid-theme fixture validates clean as a kind:\"theme\" entry"
else
    fail "green valid-theme fixture did not validate clean as a kind:\"theme\" entry (expected exit 0, got $status)"
fi
echo

check_red_variant bad-theme-mode "'dark' is a required property"
check_red_variant missing-theme-preview "'preview' is a required property"

echo "-- red bad-theme-contrast: AA contrast gate rejects a theme entry with a sub-4.5:1 asserted pair (SPEC F102.8 / T158, ported to the catalog at T180) --"
output=$(python3 tools/validate.py --root "$KIND_RED_DIR/bad-theme-contrast" 2>&1)
status=$?
echo "$output"
if [[ $status -ne 0 ]]; then
    pass "bad-theme-contrast validate.py exits non-zero"
else
    fail "bad-theme-contrast validate.py exited 0, expected non-zero"
fi
for expect in "aa-contrast" "pair 'mute' on 'bg'" "measured 1.00:1"; do
    if grep -qF "$expect" <<<"$output"; then
        pass "bad-theme-contrast validate.py names '$expect'"
    else
        fail "bad-theme-contrast validate.py did not name '$expect'"
    fi
done
echo

echo "-- fixtures/golden.theme.json (the app-manifest-serializer parity fixture) validates against schemas/theme-manifest.schema.json --"
tmp_golden_theme_check="$(mktemp)"
cat >"$tmp_golden_theme_check" <<'PY'
import json
import sys
from pathlib import Path

import jsonschema

schema = json.loads(Path("schemas/theme-manifest.schema.json").read_text(encoding="utf-8"))
golden = json.loads(Path("fixtures/golden.theme.json").read_text(encoding="utf-8"))
validator = jsonschema.validators.validator_for(schema)(schema)
errors = [e.message for e in validator.iter_errors(golden)]
if errors:
    for message in errors:
        print(f"fixtures/golden.theme.json: schema: {message}")
    sys.exit(1)
print("fixtures/golden.theme.json validates against schemas/theme-manifest.schema.json")
PY
if python3 "$tmp_golden_theme_check"; then
    pass "fixtures/golden.theme.json validates against schemas/theme-manifest.schema.json"
else
    fail "fixtures/golden.theme.json does not validate against schemas/theme-manifest.schema.json"
fi
rm -f "$tmp_golden_theme_check"
echo

echo "-- generating oversize-card fixture (not committed; see .gitignore) --"
if python3 - "$OVERSIZE_CARD" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
card = {
    "schemaVersion": 1,
    "name": "Red Test DJ",
    "tagline": "",
    "soul": "x" * (260 * 1024),  # pushes the file past the 256 KiB card cap
    "quirks": [],
    "voice": {"engine": "kokoro", "voiceId": "af_heart", "pace": 1.0, "language": "en"},
    "energyDisposition": 0,
    "lore": [],
    "corrections": [],
}
path.write_text(json.dumps(card), encoding="utf-8")
print(f"generated {path} ({path.stat().st_size} bytes)")
PY
then
    check_red_variant oversize-card "size-cap"
else
    fail "failed to generate the oversize-card fixture"
fi
rm -f "$OVERSIZE_CARD"

echo "== ci.yml wires tools/lint.py into CI (drift check, same spirit as the index.json rebuild check) =="
# Anchored on an actual `run: python3 tools/lint.py` line (allowing leading
# whitespace and trailing whitespace only) — a bare substring match would
# also PASS on a commented-out step, or on the string appearing in a step
# name/echo anywhere in the file, neither of which means the lint runs.
if grep -qE '^[[:space:]]*run:[[:space:]]*python3 tools/lint\.py[[:space:]]*$' .github/workflows/ci.yml; then
    pass "ci.yml runs tools/lint.py (an uncommented 'run: python3 tools/lint.py' step exists)"
else
    fail "ci.yml has no uncommented 'run: python3 tools/lint.py' step — the lint step is missing, removed, or commented out"
fi
echo

echo "== lint.py: submission length budgets (SPEC F89.6 · T152) =="

check_red_lint() {
    check_red tools/lint.py true "tools/lint.py " "$1" "$2"
}

check_red_lint oversize-soul "soul-budget"

echo "-- red dead-pronunciation-rule: lint.py names every dropped rule (SPEC F89.7 · T154) --"
output=$(python3 tools/lint.py --root "$RED_DIR/dead-pronunciation-rule" 2>&1)
status=$?
echo "$output"
if [[ $status -ne 0 ]]; then
    pass "dead-pronunciation-rule lint.py exits non-zero"
else
    fail "dead-pronunciation-rule lint.py exited 0, expected non-zero"
fi
# HARD dead-rule lines never carry the "WARN " prefix (see format_finding).
# Capture first, THEN test/count — a prior review found the tier-aware grep
# above can false-FAIL via pipefail/SIGPIPE on huge outputs; irrelevant at 3
# lines, but capture-first avoids the pattern entirely for any new chain.
dead_rule_lines=$(grep -F 'dead-rule:' <<<"$output" | grep -v '^WARN ')
dead_rule_count=0
if [[ -n "$dead_rule_lines" ]]; then
    dead_rule_count=$(grep -c . <<<"$dead_rule_lines")
fi
if [[ "$dead_rule_count" -eq 4 ]]; then
    pass "dead-pronunciation-rule lint.py reports exactly 4 HARD dead-rule lines"
else
    fail "dead-pronunciation-rule lint.py reported $dead_rule_count HARD dead-rule lines, expected 4"
fi
for expect in "pronunciations[0]" "pronunciations[1]" "pronunciations[2]" "pronunciations[3]"; do
    matching=$(grep -F "$expect" <<<"$dead_rule_lines")
    if [[ -n "$matching" ]]; then
        pass "dead-pronunciation-rule lint.py names '$expect'"
    else
        fail "dead-pronunciation-rule lint.py did not name '$expect'"
    fi
done
# pronunciations[3] is dead (ipa contains '[') AND its pattern repeats the
# word ("the wind in the wind") — dead-rule and word-repeat must never
# stack (check_pronunciation_rules `continue`s past word-repeat once a rule
# is already dead).
if grep -F 'pronunciations[3]' <<<"$output" | grep -q 'word-repeat'; then
    fail "dead-pronunciation-rule lint.py stacked a word-repeat warn onto already-dead pronunciations[3]"
else
    pass "dead-pronunciation-rule lint.py did not stack word-repeat onto dead pronunciations[3]"
fi
# pronunciations[4] ('Wind down' / word 'wind') is alive only under
# case-insensitive containment — must never be named as dead (kills a
# mutant that drops the .lower() calls in the word-in-pattern check).
if grep -F 'pronunciations[4]' <<<"$dead_rule_lines" >/dev/null; then
    fail "dead-pronunciation-rule lint.py named pronunciations[4] as dead (case-insensitive containment mutant)"
else
    pass "dead-pronunciation-rule lint.py did not name pronunciations[4] as dead"
fi
echo

echo "-- warn heavy-card: lint.py warns exactly once each on soul-budget, quirk-budget, quirk-count, lore-budget, prompt-weight, verbosity-phrase, word-repeat, exits 0, never HARD on dead-rule (SPEC F89.6/F89.7 · T152/T154) --"
output=$(python3 tools/lint.py --root "$HEAVY_CARD_DIR" 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "heavy-card lint.py exits 0"
else
    fail "heavy-card lint.py exited $status, expected 0"
fi
for expect in "soul-budget" "quirk-count" "quirk-budget" "lore-budget" "verbosity-phrase" "word-repeat" "prompt-weight"; do
    if grep -qF "$expect" <<<"$output"; then
        pass "heavy-card lint.py warns naming '$expect'"
    else
        fail "heavy-card lint.py did not warn naming '$expect'"
    fi
done
# The 7 checks above only prove each rule id appears at least once. Pinning
# the summary line's total to exactly 7 — combined with 7 distinct ids each
# already confirmed present — is what actually proves each fires exactly
# once (a spurious 8th warning, e.g. a rule double-firing, would push the
# summary count past 7 without necessarily failing any single `grep -qF`
# above).
if grep -qF "(7 warnings)" <<<"$output"; then
    pass "heavy-card lint.py reports exactly 7 warnings total (each WARN-tier rule fires exactly once)"
else
    fail "heavy-card lint.py did not report exactly 7 total warnings (a rule fired more than once, or an unexpected extra warning appeared)"
fi
if grep -qF "dead-rule" <<<"$output"; then
    fail "heavy-card lint.py produced a dead-rule line (word-twice-in-pattern must only ever warn)"
else
    pass "heavy-card lint.py produced no dead-rule line"
fi
echo

echo "-- warn heavy-card: prompt-weight is measured from soul + the 3 LONGEST quirks + name, not sum-all or first-3 (SPEC F89.6 · T152) --"
# Computed independently from the fixture (not hard-coded) so a future edit
# to heavy-card.persona.json can't silently desync this assertion from the
# number lint.py actually reports.
measured_weight=$(grep -F 'prompt-weight:' <<<"$output" | grep -oE 'worst-case prompt weight is [0-9]+' | grep -oE '[0-9]+')
computed_weight=$(python3 - "$HEAVY_CARD_DIR" <<'PY'
import json
import sys
from pathlib import Path

card = json.loads((Path(sys.argv[1]) / "entries/heavy-card/heavy-card.persona.json").read_text(encoding="utf-8"))
longest3 = sorted((len(q) for q in card["quirks"]), reverse=True)[:3]
print(len(card["soul"]) + sum(longest3) + len(card["name"]))
PY
)
if [[ -n "$measured_weight" && "$measured_weight" == "$computed_weight" ]]; then
    pass "heavy-card prompt-weight ($measured_weight) matches soul + 3 longest quirks + name computed independently from the fixture"
else
    fail "heavy-card prompt-weight measured '$measured_weight' but soul + 3 longest quirks + name computed '$computed_weight' from the fixture"
fi
echo

echo "-- warn heavy-card: GITHUB_ACTIONS=1 emits ::warning annotations only, never mixed with plain WARN lines (SPEC F89.6) --"
ga_output=$(GITHUB_ACTIONS=1 python3 tools/lint.py --root "$HEAVY_CARD_DIR" 2>&1)
ga_status=$?
echo "$ga_output"
if [[ $ga_status -eq 0 ]]; then
    pass "heavy-card lint.py (GITHUB_ACTIONS=1) exits 0"
else
    fail "heavy-card lint.py (GITHUB_ACTIONS=1) exited $ga_status, expected 0"
fi
if grep -qE '^::warning file=.*::' <<<"$ga_output"; then
    pass "heavy-card lint.py (GITHUB_ACTIONS=1) emits ::warning annotation lines"
else
    fail "heavy-card lint.py (GITHUB_ACTIONS=1) did not emit any ::warning annotation line"
fi
if grep -qE '^WARN ' <<<"$ga_output"; then
    fail "heavy-card lint.py (GITHUB_ACTIONS=1) mixed a plain 'WARN ' line in with ::warning annotations"
else
    pass "heavy-card lint.py (GITHUB_ACTIONS=1) produced no plain 'WARN ' lines"
fi
echo

echo "== lint.py: symlinked entries are never read, even when their target would otherwise warn (SPEC F89.6 guard · mutant M15) =="
TMP_SYMLINK_TREE="$(mktemp -d)"
mkdir -p "$TMP_SYMLINK_TREE/entries/good-entry" "$TMP_SYMLINK_TREE/real/symlinked-heavy"
cp "$GREEN_FIXTURE/valid-dj.persona.json" "$TMP_SYMLINK_TREE/entries/good-entry/good-entry.persona.json"
cp "$GREEN_FIXTURE/valid-dj.meta.json" "$TMP_SYMLINK_TREE/entries/good-entry/good-entry.meta.json"
# The symlink target is a COPY of heavy-card's entry (not valid-dj) — a
# guard-less lint would emit warnings naming this slug, so a missing guard
# is actually observable here rather than indistinguishable from a clean run.
cp "$HEAVY_CARD_DIR/entries/heavy-card/heavy-card.persona.json" "$TMP_SYMLINK_TREE/real/symlinked-heavy/symlinked-heavy.persona.json"
cp "$HEAVY_CARD_DIR/entries/heavy-card/heavy-card.meta.json" "$TMP_SYMLINK_TREE/real/symlinked-heavy/symlinked-heavy.meta.json"
ln -s "$TMP_SYMLINK_TREE/real/symlinked-heavy" "$TMP_SYMLINK_TREE/entries/symlinked-heavy"

output=$(python3 tools/lint.py --root "$TMP_SYMLINK_TREE" 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "symlink-guard scratch tree lint.py exits 0"
else
    fail "symlink-guard scratch tree lint.py exited $status, expected 0"
fi
if grep -qF "symlinked-heavy" <<<"$output"; then
    fail "symlink-guard scratch tree lint.py output named the symlinked slug (guard not applied)"
else
    pass "symlink-guard scratch tree lint.py produced no output naming the symlinked slug"
fi
echo

echo "-- real entries/ come back from lint.py with no hard violations (shelf is hard-clean) --"
# WARN-tier findings are allowed here and must never fail this check — warn
# tolerance on real entries is the ratified posture (SPEC F89.6; CONTRIBUTING:
# "Warnings alone won't block your PR"). Only a HARD violation (exit != 0)
# fails the shelf.
output=$(python3 tools/lint.py 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "real entries/ lint.py exits 0 (no hard violations on the shelf)"
else
    fail "real entries/ lint.py exited $status, expected 0 (a hard violation landed on the shelf)"
fi
# Swallow-everything mutants (a broken discovery or symlink guard) can't hide
# here — a lint that reads nothing exits 0 silently. They are caught by the
# red/warn fixture checks above, which require specific findings from specific
# cards; the symlink-guard scratch tree proves symlinked entries are excluded
# for the right reason. This check owns one thing only: the shelf is hard-clean.
echo

echo "== build_index.py: determinism (same tree in -> byte-identical index out) =="
tmp1="$(mktemp)"
tmp2="$(mktemp)"
tmp_diff="$(mktemp)"
build_ok=1
if ! python3 tools/build_index.py --out "$tmp1"; then
    fail "build_index.py exited non-zero writing tmp1"
    build_ok=0
fi
if [[ $build_ok -eq 1 ]] && ! python3 tools/build_index.py --out "$tmp2"; then
    fail "build_index.py exited non-zero writing tmp2"
    build_ok=0
fi
if [[ $build_ok -eq 1 ]]; then
    if diff -u "$tmp1" "$tmp2" >"$tmp_diff" 2>&1; then
        pass "build_index.py output is byte-identical across repeated runs"
    else
        cat "$tmp_diff"
        fail "build_index.py produced different output on repeated runs"
    fi
fi
echo

echo "== build_index.py: excludes example-dj =="
if [[ $build_ok -eq 1 ]]; then
    tmp_slug_err="$(mktemp)"
    if slugs=$(python3 -c '
import json, sys
try:
    data = json.load(open(sys.argv[1]))
except json.JSONDecodeError as exc:
    print(f"JSONDecodeError: {exc}", file=sys.stderr)
    sys.exit(1)
print(",".join(e["slug"] for e in data["entries"]))
' "$tmp1" 2>"$tmp_slug_err"); then
        echo "index entries: [${slugs}]"
        if [[ ",${slugs}," != *",example-dj,"* ]]; then
            pass "index excludes example-dj"
        else
            fail "index.json includes example-dj"
        fi
    else
        cat "$tmp_slug_err"
        fail "could not read slugs from built index (build_index.py output was not valid JSON)"
    fi
    rm -f "$tmp_slug_err"
else
    fail "skipped example-dj exclusion check because build_index.py failed above"
fi
rm -f "$tmp1" "$tmp2" "$tmp_diff"
echo

echo "== build_index.py: committed index.json matches a fresh rebuild (drift check) =="
# Mirrors ci.yml's "Verify index.json matches entries/" step: a PR that edits
# entries/ without regenerating index.json must fail here too, not just in CI.
tmp_drift="$(mktemp)"
tmp_drift_diff="$(mktemp)"
if python3 tools/build_index.py --out "$tmp_drift"; then
    if diff -u index.json "$tmp_drift" >"$tmp_drift_diff" 2>&1; then
        pass "committed index.json matches a fresh rebuild (no drift)"
    else
        cat "$tmp_drift_diff"
        fail "committed index.json differs from a fresh rebuild — run tools/build_index.py and commit the result"
    fi
else
    fail "build_index.py exited non-zero rebuilding index.json for the drift check"
fi
rm -f "$tmp_drift" "$tmp_drift_diff"
echo

echo "== build_index.py: green fixture exercises index shape =="
TMP_GREEN_TREE="$(mktemp -d)"
mkdir -p "$TMP_GREEN_TREE/entries/valid-dj" "$TMP_GREEN_TREE/entries/aardvark-dj" "$TMP_GREEN_TREE/entries/example-dj"
cp "$GREEN_FIXTURE/valid-dj.persona.json" "$TMP_GREEN_TREE/entries/valid-dj/valid-dj.persona.json"
cp "$GREEN_FIXTURE/valid-dj.meta.json" "$TMP_GREEN_TREE/entries/valid-dj/valid-dj.meta.json"
# A second copy under a slug that sorts before valid-dj, so the sorted-slugs
# assertion below exercises a real reorder rather than a single-item no-op.
cp "$GREEN_FIXTURE/valid-dj.persona.json" "$TMP_GREEN_TREE/entries/aardvark-dj/aardvark-dj.persona.json"
cp "$GREEN_FIXTURE/valid-dj.meta.json" "$TMP_GREEN_TREE/entries/aardvark-dj/aardvark-dj.meta.json"
cp entries/example-dj/example-dj.persona.json "$TMP_GREEN_TREE/entries/example-dj/example-dj.persona.json"
cp entries/example-dj/example-dj.meta.json "$TMP_GREEN_TREE/entries/example-dj/example-dj.meta.json"

tmp_green_index="$(mktemp)"
green_build_ok=1
if ! python3 tools/build_index.py --root "$TMP_GREEN_TREE" --out "$tmp_green_index"; then
    fail "build_index.py exited non-zero building the green fixture tree"
    green_build_ok=0
fi

if [[ $green_build_ok -eq 1 ]]; then
    tmp_shape_check="$(mktemp)"
    cat >"$tmp_shape_check" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

index_path, tree_root = Path(sys.argv[1]), Path(sys.argv[2])
data = json.loads(index_path.read_text())
entries = data["entries"]

errors = []

slugs = [e["slug"] for e in entries]
if slugs != sorted(slugs):
    errors.append(f"slugs not sorted: {slugs}")
if slugs != ["aardvark-dj", "valid-dj"]:
    errors.append(f"unexpected slug set (example-dj should be excluded): {slugs}")

for e in entries:
    if e.get("audience") != "everyone":
        errors.append(f"{e['slug']}: audience field missing/wrong: {e.get('audience')!r}")
    for kind in ("card", "meta"):
        path = e[kind]["path"]
        if path.startswith("/"):
            errors.append(f"{e['slug']}.{kind}: path is absolute, expected relative: {path}")
        want = hashlib.sha256((tree_root / path).read_bytes()).hexdigest()
        got = e[kind]["sha256"]
        if want != got:
            errors.append(f"{e['slug']}.{kind}: sha256 mismatch: recomputed {want}, index has {got}")

if errors:
    for line in errors:
        print(line)
    sys.exit(1)
print("green fixture index shape OK: sha256, audience, relative paths, sorted slugs, example-dj excluded")
PY
    if python3 "$tmp_shape_check" "$tmp_green_index" "$TMP_GREEN_TREE"; then
        pass "built index shape (sha256, audience, relative paths, sorted slugs, example-dj excluded)"
    else
        fail "built index shape assertions failed against the green fixture tree"
    fi
    rm -f "$tmp_shape_check"
else
    fail "skipped green fixture shape assertions because build_index.py failed above"
fi
rm -f "$tmp_green_index"
echo

echo "== build_index.py + schemas/index.schema.json: kind discriminator (SPEC F103.2 / T178) =="
# kind is a property of the built INDEX entry, not of anything inside
# entries/<slug>/*.meta.json — so unlike the red/green fixtures above (which
# are entries/ trees fed through validate.py or build_index.py), the checks
# below either (a) build a small mixed persona+theme entries/ tree and
# inspect build_index.py's output shape, or (b) hand-author a bare index
# entry object (tools/testdata/red/bad-kind-*/index-entry.json — deliberately
# NOT an entries/ tree, since build_index.py itself can only ever emit
# kind "persona" or "theme": it derives kind from which manifest filename is
# present, so a bogus kind value can only arise from a hand-crafted
# index.json, never from a real build) and schema-validate it directly
# against schemas/index.schema.json's entry definition via the jsonschema
# library, the same way the pronunciations[] schema check above does.
TMP_KIND_TREE="$(mktemp -d)"
mkdir -p "$TMP_KIND_TREE/entries/valid-dj" "$TMP_KIND_TREE/entries/valid-theme"
cp "$GREEN_FIXTURE/valid-dj.persona.json" "$TMP_KIND_TREE/entries/valid-dj/valid-dj.persona.json"
cp "$GREEN_FIXTURE/valid-dj.meta.json" "$TMP_KIND_TREE/entries/valid-dj/valid-dj.meta.json"
cp "$KIND_GREEN_FIXTURE/valid-theme.theme.json" "$TMP_KIND_TREE/entries/valid-theme/valid-theme.theme.json"
cp "$KIND_GREEN_FIXTURE/valid-theme.meta.json" "$TMP_KIND_TREE/entries/valid-theme/valid-theme.meta.json"

tmp_kind_index="$(mktemp)"
kind_build_ok=1
if ! python3 tools/build_index.py --root "$TMP_KIND_TREE" --out "$tmp_kind_index"; then
    fail "build_index.py exited non-zero building the persona+theme kind fixture tree"
    kind_build_ok=0
fi

if [[ $kind_build_ok -eq 1 ]]; then
    tmp_kind_check="$(mktemp)"
    cat >"$tmp_kind_check" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

import jsonschema

index_path, tree_root, schema_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
data = json.loads(index_path.read_text())
by_slug = {e["slug"]: e for e in data["entries"]}

schema = json.loads(schema_path.read_text(encoding="utf-8"))
# Embed the sha256 definition directly into the entry subschema so its
# "#/definitions/sha256" $ref self-resolves without needing a resolver
# rooted at the full document.
entry_schema = dict(schema["definitions"]["entry"])
entry_schema["definitions"] = {"sha256": schema["definitions"]["sha256"]}
validator = jsonschema.validators.validator_for(entry_schema)(entry_schema)

errors = []

persona = by_slug.get("valid-dj")
if persona is None:
    errors.append("valid-dj entry missing from built index")
else:
    if "kind" in persona:
        errors.append(f"valid-dj: unexpected 'kind' key stamped onto a persona entry: {persona['kind']!r}")
    if "manifest" in persona:
        errors.append("valid-dj: unexpected 'manifest' key on a persona entry")
    if "card" not in persona:
        errors.append("valid-dj: missing 'card' key")
    persona_errors = [e.message for e in validator.iter_errors(persona)]
    if persona_errors:
        errors.append(f"valid-dj entry does not validate against schemas/index.schema.json: {persona_errors}")

theme = by_slug.get("valid-theme")
if theme is None:
    errors.append("valid-theme entry missing from built index")
else:
    if theme.get("kind") != "theme":
        errors.append(f"valid-theme: expected kind 'theme', got {theme.get('kind')!r}")
    if "card" in theme:
        errors.append("valid-theme: unexpected 'card' key on a theme entry")
    manifest = theme.get("manifest")
    if not isinstance(manifest, dict):
        errors.append("valid-theme: missing 'manifest' key")
    else:
        path = manifest.get("path")
        if not isinstance(path, str) or not path.endswith("valid-theme.theme.json"):
            errors.append(f"valid-theme.manifest.path unexpected: {path!r}")
        else:
            want = hashlib.sha256((tree_root / path).read_bytes()).hexdigest()
            got = manifest.get("sha256")
            if want != got:
                errors.append(f"valid-theme.manifest.sha256 mismatch: recomputed {want}, index has {got}")
    theme_errors = [e.message for e in validator.iter_errors(theme)]
    if theme_errors:
        errors.append(f"valid-theme entry does not validate against schemas/index.schema.json: {theme_errors}")

if errors:
    for line in errors:
        print(line)
    sys.exit(1)
print(
    "kind-aware index shape OK: persona entry unchanged (card, no kind/manifest key), "
    "theme entry carries kind:\"theme\" + manifest (sha256 verified), both entries "
    "validate against schemas/index.schema.json"
)
PY
    if python3 "$tmp_kind_check" "$tmp_kind_index" "$TMP_KIND_TREE" "schemas/index.schema.json"; then
        pass "build_index.py is kind-aware: persona entry unchanged, theme entry carries kind+manifest, both schema-valid"
    else
        fail "build_index.py kind-aware output shape assertions failed"
    fi
    rm -f "$tmp_kind_check"
else
    fail "skipped kind-aware shape assertions because build_index.py failed above"
fi
rm -f "$tmp_kind_index"
echo

check_kind_entry_red() {
    local variant="$1" expect="$2"
    local output status
    output=$(python3 - "$KIND_RED_DIR/$variant/index-entry.json" "$expect" <<'PY'
import json
import sys
from pathlib import Path

import jsonschema

schema = json.loads(Path("schemas/index.schema.json").read_text(encoding="utf-8"))
# Embed the sha256 definition directly into the entry subschema so its
# "#/definitions/sha256" $ref self-resolves without needing a resolver
# rooted at the full document.
entry_schema = dict(schema["definitions"]["entry"])
entry_schema["definitions"] = {"sha256": schema["definitions"]["sha256"]}
validator = jsonschema.validators.validator_for(entry_schema)(entry_schema)

fixture_path, expect_substring = Path(sys.argv[1]), sys.argv[2]
instance = json.loads(fixture_path.read_text(encoding="utf-8"))
errors = [e.message for e in validator.iter_errors(instance)]
if not errors:
    print(f"{fixture_path}: expected schema validation to fail, but it passed")
    sys.exit(1)
if not any(expect_substring in msg for msg in errors):
    print(f"{fixture_path}: none of the violation(s) name {expect_substring!r}: {errors}")
    sys.exit(1)
print(f"{fixture_path}: rejected as expected, naming {expect_substring!r}: {errors}")
PY
    )
    status=$?
    echo "$output"
    if [[ $status -eq 0 ]]; then
        pass "$variant: schemas/index.schema.json rejects it, naming '$expect'"
    else
        fail "$variant: schemas/index.schema.json did not reject it naming '$expect'"
    fi
    echo
}

echo "== schemas/index.schema.json: kind discriminator rejects bad entries (SPEC F103.2 / T178) =="
check_kind_entry_red bad-kind-value "'villain' is not one of"
check_kind_entry_red bad-kind-theme-no-manifest "'manifest' is a required property"

echo "=========================================="
if [[ $FAILURES -eq 0 ]]; then
    echo "SELFTEST PASS"
    exit 0
else
    echo "SELFTEST FAIL ($FAILURES check(s) failed)"
    exit 1
fi
