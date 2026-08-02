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

TMP_GREEN_TREE=""
cleanup() {
    rm -f "$OVERSIZE_CARD"
    [[ -n "$TMP_GREEN_TREE" ]] && rm -rf "$TMP_GREEN_TREE"
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
rm -rf "$TMP_PRON_TREE"
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

echo "== lint.py: submission length budgets (SPEC F89.6 · T152) =="

check_red_lint() {
    check_red tools/lint.py true "tools/lint.py " "$1" "$2"
}

check_red_lint oversize-soul "soul-budget"

echo "-- warn heavy-card: lint.py warns (soul, quirk band, verbosity phrase), exits 0 --"
output=$(python3 tools/lint.py --root "$HEAVY_CARD_DIR" 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "heavy-card lint.py exits 0"
else
    fail "heavy-card lint.py exited $status, expected 0"
fi
for expect in "soul-budget" "quirk-count" "verbosity-phrase"; do
    if grep -qF "$expect" <<<"$output"; then
        pass "heavy-card lint.py warns naming '$expect'"
    else
        fail "heavy-card lint.py did not warn naming '$expect'"
    fi
done
echo

echo "-- real entries/ come back from lint.py with zero warnings (grandfather clean) --"
output=$(python3 tools/lint.py 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "real entries/ lint.py exits 0"
else
    fail "real entries/ lint.py exited $status, expected 0"
fi
if grep -qE '^WARN |::warning' <<<"$output"; then
    fail "real entries/ lint.py produced warning output (grandfather clause broken)"
else
    pass "real entries/ lint.py produced zero warnings"
fi
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

echo "== pending: catalog submission lint (SPEC F89.6–F89.7 · genwave docs/PLAN.md T152–T155) =="
# House pending-spec idiom (the shell analog of genwave's [Fact(Skip = "Pending TNNN")]):
# each line below is a real check whose fixture data is ALREADY committed under
# tools/testdata/; the named task deletes its skip_pending line and wires the live check.
# SKIPs are deliberately not failures — the harness stays green until each task lands.
skip_pending() { printf 'SKIP  %s (pending %s)\n' "$1" "$2"; }
skip_pending "red dead-pronunciation-rule fails lint.py naming each dropped rule"              "T154"
skip_pending "warn heavy-card word-twice-in-pattern rule warns, never red"                     "T154"
skip_pending "ci.yml runs lint.py and this selftest carries zero SKIP lines"                   "T155"
echo

echo "=========================================="
if [[ $FAILURES -eq 0 ]]; then
    echo "SELFTEST PASS"
    exit 0
else
    echo "SELFTEST FAIL ($FAILURES check(s) failed)"
    exit 1
fi
