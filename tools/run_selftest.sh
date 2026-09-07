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
#  12. kind-aware show-entry validation (schemas/show-manifest.schema.json +
#      schemas/show-meta.schema.json, SPEC F118.1/F118.4, T253): a green
#      valid-show fixture end to end, red schema-shape gates (missing
#      flavor, missing audience), fixtures/golden.show.json against the
#      show-manifest schema, build_index.py's show-kind projection (kind +
#      manifest only, no card/assets/family/preview), tools/lint.py's
#      show budget lint (WARN>1x on every field, HARD>=2x on flavor at
#      exactly the 2x boundary), and tools/lint.py's HARD-only
#      show-rotation-bounds rule (schema 1.1's optional envelope.rotation,
#      SPEC F152.1/F152.3/F152.6, PLAN T364): red variants for "neither
#      bound set", "notAiredWithinDays out of range", and "maxPlays past
#      Int32.MaxValue" (the last one also red at the schema level, its own
#      "maximum" keyword); green fixtures with maxPlays: 0, with SPEC
#      F152.3's own documented null-bound payload, and with an explicit
#      envelope.rotation: null, all validating and linting clean
#  13. per-kind entries/ folder layout invariants (gh-33): a manifest whose
#      kind folder disagrees with its own manifest-filename suffix
#      (kind-folder-mismatch), and the same slug held by two different kind
#      folders at once (duplicate-slug) are each rejected, naming the
#      offending entry
#  14. kind-aware avatar-entry validation (schemas/avatar-manifest.schema.json
#      + schemas/avatar-meta.schema.json, SPEC F128.1, T309): a green
#      valid-avatar fixture end to end, the deep PNG gates ported from the
#      app's own PngImageHeader (magic bytes, IHDR 512x512, acTL/APNG
#      reject), the per-item (512 KiB) and per-pack (6 MiB) byte ceilings
#      (generated at test time, not committed — the oversize-card/
#      font-over-ceiling precedent), item-name uniqueness, and orphan/
#      stowaway asset accounting; a persona entry's own optional
#      <slug>.avatar.png sidecar face rides the identical PNG gates (SPEC
#      F128.2); build_index.py projects an avatar entry's assets[] (no
#      family) and a persona's own single-element assets[] only when the
#      sidecar is actually on disk
#  15. kind-aware icon-entry validation (schemas/icon-manifest.schema.json +
#      schemas/icon-meta.schema.json, SPEC F130.1/F130.6, T309): a green
#      valid-icon fixture exercising every whitelisted primitive tag, the
#      closed seven-tag whitelist + per-tag closed attribute sets + d/points
#      character grammars (all pinned in the JSON Schema itself, ported from
#      GenWave.Host.Icons.IconPackDefinitionParser), the icon-name map-KEY
#      pattern/length gate, the 512-icon/64-element-per-icon bounds, the
#      256 KiB definition-size cap (generated at test time), the
#      finite-numeric-attribute walk (a `1e400` JSON literal overflows to a
#      non-finite float — no JSON Schema keyword can catch this), and the F1
#      ruling (a `license`/`licence` member inside the manifest is a HARD
#      reject; the companion meta.json REQUIRES `license`+`sourceUrl`);
#      build_index.py projects an icon entry's kind+manifest only, the same
#      minimal shape a show entry gets
#
#  16. kind-aware ad-pack-entry validation (schemas/ad-pack-manifest.schema.json
#      + schemas/ad-pack-meta.schema.json, SPEC F162.2, app PLAN T405/T407): a
#      green valid-ad-pack fixture end to end (every-hint, null-hint, and
#      brand-only briefs), the app-mirrored caps as red schema gates (empty
#      briefs[], blank brand, 501-char hint, 101 briefs, an unknown member),
#      validate.py's own cross-item brand-uniqueness gate
#      (ad-pack-duplicate-brand — case/whitespace-folded), the closed folder
#      set (a stowaway file), the 256 KiB manifest cap (generated at test
#      time: a schema-valid manifest padded with whitespace, the ONLY way a
#      valid document reaches it), build_index.py's ad-pack projection (kind +
#      manifest only, no card/assets/family/preview), and the index-entry
#      schema's own ad-pack branch (manifest-only accepted, a card-carrying or
#      assets-carrying ad-pack entry rejected)
#
#  17. kind-aware voice-pack-entry validation (schemas/voice-pack-manifest.schema.json
#      + schemas/voice-pack-meta.schema.json, SPEC F164, app PLAN T410/T412/T413): a
#      green valid-voice-pack fixture end to end (a plain voice plus a blended one,
#      sourceRef: null) and a valid-voice-pack-no-sourceref sibling (the key absent
#      entirely), the closed engine/synthetic/sourceRef shape as red schema gates
#      (a non-kokoro engine — mirrored generically as synthetic-false's own const
#      failure — synthetic: false, a non-null sourceRef, an uppercase/traversal/too-
#      long voiceId, 17 voices past maxItems 16), validate.py's own cross-item gates
#      (voice-pack-file-mismatch, voice-pack-duplicate-voice), the deep asset gates
#      ported from the app's own weight/preview handling (real zip/torch magic on
#      every .pt, real MP3 magic on the preview, the 1 MiB per-weight and 150 KiB
#      preview byte ceilings generated at test time, the 8 MiB per-pack ceiling —
#      9 weights generated at test time), the preview's own filename==slug rule
#      (voice-pack-preview-name), and the same orphan/stowaway "a pack IS its
#      files" posture as font/avatar (voice-pack-orphan-file; the T411 brief's own
#      wording reserves "orphan" for an unclaimed disk file here — a manifest
#      reference to a MISSING file is an ordinary missing-file finding instead,
#      the opposite of font-pack's own "orphan" direction); build_index.py's
#      voice-pack projection (kind + manifest + assets[], no card/family/preview)
#      and the index-entry schema's own voice-pack branch (manifest+assets
#      required, a card/preview-carrying voice-pack entry rejected).
#
#  18. kind-aware jingle-pack-entry validation (schemas/jingle-pack-manifest.schema.json
#      + schemas/jingle-pack-meta.schema.json, SPEC F165, app PLAN T410/T412,
#      STORY-400): a green valid-jingle-pack fixture end to end (a CC0 bed/wav, a
#      CC-BY sting/mp3 with full attribution, a CC0 station_id/flac), the closed
#      license/role shape as red schema gates (CC-BY-SA refused by the enum itself,
#      an unknown role, CC-BY missing attribution/creator/sourceUrl, CC0 carrying an
#      attribution object anyway, a top-level attribution array — STORY-400 AC6),
#      validate.py's own cross-item and per-asset gates (jingle-pack-sha256-mismatch
#      against the real bytes on disk, jingle-pack-audio-magic per extension via
#      JINGLE_AUDIO_MAGIC_CHECKS, the 5 MiB per-asset ceiling generated at test time
#      alongside its own manifest so the sha256 stays self-consistent,
#      jingle-pack-duplicate-asset on both file and case/whitespace-folded title),
#      the reverse orphan check (jingle-pack-orphan-audio), build_index.py's
#      jingle-pack projection (kind + manifest + assets[], no card/family/preview),
#      the index-entry schema's own jingle-pack branch, and
#      validate_index_asset_integrity (T411, new at this task): every index.json
#      entry's own declared sha256/bytes actually matches the real file on disk —
#      a stale claim neither validate_index_slug_ownership nor
#      validate_index_duplicate_asset_paths ever opens the file to catch.

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
OVERSIZE_CARD="$RED_DIR/oversize-card/entries/personas/oversize-card/oversize-card.persona.json"

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

FONT_GREEN_FIXTURE="tools/testdata/green/valid-font"
FONT_OVER_CEILING_ASSET="$RED_DIR/font-over-ceiling/entries/fonts/font-over-ceiling/font-over-ceiling-variable-latin.woff2"

SHOW_GREEN_FIXTURE="tools/testdata/green/valid-show"
HEAVY_SHOW_DIR="tools/testdata/warn/heavy-show"
SHOW_ROTATION_GREEN_FIXTURE="tools/testdata/green/valid-show-with-rotation"
SHOW_ROTATION_NULL_BOUND_GREEN_FIXTURE="tools/testdata/green/valid-show-with-null-bound"
SHOW_ROTATION_NULL_ROTATION_GREEN_FIXTURE="tools/testdata/green/valid-show-with-null-rotation"

AVATAR_GREEN_FIXTURE="tools/testdata/green/valid-avatar"
PERSONA_AVATAR_GREEN_FIXTURE="tools/testdata/green/valid-dj-with-avatar"
ICON_GREEN_FIXTURE="tools/testdata/green/valid-icon"
AVATAR_ITEM_OVERSIZE_PNG="$RED_DIR/avatar-item-oversize/entries/avatars/avatar-item-oversize/too-heavy.png"
ICON_OVER_CEILING_DIR="$RED_DIR/icon-over-ceiling/entries/icons/icon-over-ceiling"
AD_PACK_GREEN_FIXTURE="tools/testdata/green/valid-ad-pack"
AD_PACK_OVER_CEILING_DIR="$RED_DIR/ad-pack-over-ceiling/entries/ad-packs/ad-pack-over-ceiling"

VOICE_PACK_GREEN_FIXTURE="tools/testdata/green/valid-voice-pack"
VOICE_PACK_NO_SOURCEREF_GREEN_FIXTURE="tools/testdata/green/valid-voice-pack-no-sourceref"
VOICE_PACK_PREVIEW_OVER_MAX="$RED_DIR/preview-over-max/entries/voice-packs/preview-over-max/preview-over-max.preview.mp3"
VOICE_PACK_PT_OVER_MAX="$RED_DIR/pt-over-max/entries/voice-packs/pt-over-max/river.pt"
VOICE_PACK_OVER_CEILING_DIR="$RED_DIR/over-ceiling/entries/voice-packs/over-ceiling"

JINGLE_PACK_GREEN_FIXTURE="tools/testdata/green/valid-jingle-pack"
JINGLE_PACK_ASSET_OVER_MAX_DIR="$RED_DIR/asset-over-max/entries/jingle-packs/asset-over-max"
JINGLE_PACK_OVER_CEILING_DIR="$RED_DIR/jingle-pack-over-ceiling/entries/jingle-packs/jingle-pack-over-ceiling"

TMP_GREEN_TREE=""
TMP_PRON_TREE=""
TMP_SYMLINK_TREE=""
TMP_KIND_TREE=""
TMP_THEME_TREE=""
TMP_FONT_TREE=""
TMP_FONT_INDEX_TREE=""
TMP_HOSTILE_BYTES_TREE=""
TMP_SCHEMA_HELPERS_DIR=""
TMP_SHOW_TREE=""
TMP_SHOW_INDEX_TREE=""
TMP_AVATAR_TREE=""
TMP_PERSONA_AVATAR_TREE=""
TMP_PERSONA_AVATAR_INDEX_TREE=""
TMP_ICON_TREE=""
TMP_ICON_INDEX_TREE=""
TMP_AVATAR_INDEX_TREE=""
TMP_AD_PACK_TREE=""
TMP_AD_PACK_INDEX_TREE=""
TMP_VOICE_PACK_TREE=""
TMP_VOICE_PACK_INDEX_TREE=""
TMP_JINGLE_PACK_TREE=""
TMP_JINGLE_PACK_INDEX_TREE=""
TMP_SHOW_ROTATION_TREE=""
TMP_SHOW_ROTATION_NULL_BOUND_TREE=""
TMP_SHOW_ROTATION_NULL_ROTATION_TREE=""
cleanup() {
    rm -f "$OVERSIZE_CARD"
    rm -f "$FONT_OVER_CEILING_ASSET"
    rm -f "$AVATAR_ITEM_OVERSIZE_PNG"
    rm -f "$RED_DIR"/avatar-pack-ceiling/entries/avatars/avatar-pack-ceiling/face-*.png
    rm -f "$ICON_OVER_CEILING_DIR"/icon-over-ceiling.icon.json "$ICON_OVER_CEILING_DIR"/icon-over-ceiling.meta.json
    rm -f "$AD_PACK_OVER_CEILING_DIR"/ad-pack-over-ceiling.ad-pack.json "$AD_PACK_OVER_CEILING_DIR"/ad-pack-over-ceiling.meta.json
    rm -f "$VOICE_PACK_PREVIEW_OVER_MAX" "$VOICE_PACK_PT_OVER_MAX"
    rm -f "$VOICE_PACK_OVER_CEILING_DIR"/voice*.pt
    rm -f "$JINGLE_PACK_ASSET_OVER_MAX_DIR"/bed.wav "$JINGLE_PACK_ASSET_OVER_MAX_DIR"/asset-over-max.jingle-pack.json "$JINGLE_PACK_ASSET_OVER_MAX_DIR"/asset-over-max.meta.json
    rm -f "$JINGLE_PACK_OVER_CEILING_DIR"/asset*.wav "$JINGLE_PACK_OVER_CEILING_DIR"/jingle-pack-over-ceiling.jingle-pack.json "$JINGLE_PACK_OVER_CEILING_DIR"/jingle-pack-over-ceiling.meta.json
    [[ -n "$TMP_GREEN_TREE" ]] && rm -rf "$TMP_GREEN_TREE"
    [[ -n "$TMP_PRON_TREE" ]] && rm -rf "$TMP_PRON_TREE"
    [[ -n "$TMP_SYMLINK_TREE" ]] && rm -rf "$TMP_SYMLINK_TREE"
    [[ -n "$TMP_KIND_TREE" ]] && rm -rf "$TMP_KIND_TREE"
    [[ -n "$TMP_THEME_TREE" ]] && rm -rf "$TMP_THEME_TREE"
    [[ -n "$TMP_FONT_TREE" ]] && rm -rf "$TMP_FONT_TREE"
    [[ -n "$TMP_FONT_INDEX_TREE" ]] && rm -rf "$TMP_FONT_INDEX_TREE"
    [[ -n "$TMP_HOSTILE_BYTES_TREE" ]] && rm -rf "$TMP_HOSTILE_BYTES_TREE"
    [[ -n "$TMP_SCHEMA_HELPERS_DIR" ]] && rm -rf "$TMP_SCHEMA_HELPERS_DIR"
    [[ -n "$TMP_SHOW_TREE" ]] && rm -rf "$TMP_SHOW_TREE"
    [[ -n "$TMP_SHOW_INDEX_TREE" ]] && rm -rf "$TMP_SHOW_INDEX_TREE"
    [[ -n "$TMP_AVATAR_TREE" ]] && rm -rf "$TMP_AVATAR_TREE"
    [[ -n "$TMP_PERSONA_AVATAR_TREE" ]] && rm -rf "$TMP_PERSONA_AVATAR_TREE"
    [[ -n "$TMP_PERSONA_AVATAR_INDEX_TREE" ]] && rm -rf "$TMP_PERSONA_AVATAR_INDEX_TREE"
    [[ -n "$TMP_ICON_TREE" ]] && rm -rf "$TMP_ICON_TREE"
    [[ -n "$TMP_ICON_INDEX_TREE" ]] && rm -rf "$TMP_ICON_INDEX_TREE"
    [[ -n "$TMP_AVATAR_INDEX_TREE" ]] && rm -rf "$TMP_AVATAR_INDEX_TREE"
    [[ -n "$TMP_AD_PACK_TREE" ]] && rm -rf "$TMP_AD_PACK_TREE"
    [[ -n "$TMP_AD_PACK_INDEX_TREE" ]] && rm -rf "$TMP_AD_PACK_INDEX_TREE"
    [[ -n "$TMP_VOICE_PACK_TREE" ]] && rm -rf "$TMP_VOICE_PACK_TREE"
    [[ -n "$TMP_VOICE_PACK_INDEX_TREE" ]] && rm -rf "$TMP_VOICE_PACK_INDEX_TREE"
    [[ -n "$TMP_JINGLE_PACK_TREE" ]] && rm -rf "$TMP_JINGLE_PACK_TREE"
    [[ -n "$TMP_JINGLE_PACK_INDEX_TREE" ]] && rm -rf "$TMP_JINGLE_PACK_INDEX_TREE"
    [[ -n "$TMP_SHOW_ROTATION_TREE" ]] && rm -rf "$TMP_SHOW_ROTATION_TREE"
    [[ -n "$TMP_SHOW_ROTATION_NULL_BOUND_TREE" ]] && rm -rf "$TMP_SHOW_ROTATION_NULL_BOUND_TREE"
    [[ -n "$TMP_SHOW_ROTATION_NULL_ROTATION_TREE" ]] && rm -rf "$TMP_SHOW_ROTATION_NULL_ROTATION_TREE"
}
trap cleanup EXIT

# Shared home for the schemas/index.schema.json `entry` subschema + its own
# sha256/assetRef/swatchSet/hexColor definitions embedding, so its own
# "#/definitions/..." $refs self-resolve without needing a resolver rooted at
# the full document — one Python module, written once, rather than a
# duplicated `entry_schema["definitions"] = {...}` heredoc in each of
# check_kind_entry_red/check_kind_entry_green below (N4 review finding).
TMP_SCHEMA_HELPERS_DIR="$(mktemp -d)"
cat >"$TMP_SCHEMA_HELPERS_DIR/index_entry_schema.py" <<'PY'
"""Shared helper for tools/run_selftest.sh's inline Python checks against
schemas/index.schema.json's `entry` subschema (N4 review finding: one
definitions source instead of a copy per caller)."""
import json
from pathlib import Path

import jsonschema


def load_entry_validator(schema_path: Path = Path("schemas/index.schema.json")):
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    entry_schema = dict(schema["definitions"]["entry"])
    entry_schema["definitions"] = {
        "sha256": schema["definitions"]["sha256"],
        "assetRef": schema["definitions"]["assetRef"],
        "swatchSet": schema["definitions"]["swatchSet"],
        "hexColor": schema["definitions"]["hexColor"],
    }
    return jsonschema.validators.validator_for(entry_schema)(entry_schema)
PY

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
mkdir -p "$TMP_PRON_TREE/entries/personas/valid-dj"
cp "$GREEN_FIXTURE/valid-dj.persona.json" "$TMP_PRON_TREE/entries/personas/valid-dj/valid-dj.persona.json"
cp "$GREEN_FIXTURE/valid-dj.meta.json" "$TMP_PRON_TREE/entries/personas/valid-dj/valid-dj.meta.json"
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

echo "== validate.py: per-kind entries/ folder layout invariants (gh-33) =="

echo "-- red kind-folder-mismatch: a .persona.json manifest sitting under entries/shows/ (the wrong kind folder) is rejected, naming both the implied and actual folder --"
check_red_variant kind-folder-mismatch "kind-folder-mismatch"

echo "-- red duplicate-slug-across-kinds: the SAME slug held by two different kind folders (entries/personas/shared-slug/ and entries/themes/shared-slug/) is rejected — index.json and the app key an entry on slug alone --"
check_red_variant duplicate-slug-across-kinds "duplicate-slug"

echo "== validate.py: kind-aware theme-entry validation (schemas/theme-manifest.schema.json + schemas/theme-meta.schema.json, SPEC F103.2 / T179) =="

echo "-- green valid-theme fixture validates clean end-to-end as a kind:\"theme\" entry --"
TMP_THEME_TREE="$(mktemp -d)"
mkdir -p "$TMP_THEME_TREE/entries/themes/valid-theme"
cp "$KIND_GREEN_FIXTURE/valid-theme.theme.json" "$TMP_THEME_TREE/entries/themes/valid-theme/valid-theme.theme.json"
cp "$KIND_GREEN_FIXTURE/valid-theme.meta.json" "$TMP_THEME_TREE/entries/themes/valid-theme/valid-theme.meta.json"
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
check_red_variant theme-unvendored-font "theme-unvendored-font: theme 'theme-unvendored-font' fonts.sans references font src '/fonts/space-grotesk-variable-latin.woff2'"

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

# Shared by every "does this golden parity fixture still validate against
# its schema" check below (theme, font, and any future kind) — a THIRD
# near-verbatim copy of this inline-Python block (font, added at T195) is
# what made the duplication worth collapsing into one function (N4 review
# finding).
check_golden_fixture() {
    local fixture_path="$1" schema_path="$2"
    local output status
    output=$(python3 - "$fixture_path" "$schema_path" <<'PY'
import json
import sys
from pathlib import Path

import jsonschema

fixture_path, schema_path = sys.argv[1], sys.argv[2]
schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
golden = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
validator = jsonschema.validators.validator_for(schema)(schema)
errors = [e.message for e in validator.iter_errors(golden)]
if errors:
    for message in errors:
        print(f"{fixture_path}: schema: {message}")
    sys.exit(1)
print(f"{fixture_path} validates against {schema_path}")
PY
    )
    status=$?
    echo "$output"
    if [[ $status -eq 0 ]]; then
        pass "$fixture_path validates against $schema_path"
    else
        fail "$fixture_path does not validate against $schema_path"
    fi
    echo
}

echo "-- fixtures/golden.theme.json (the app-manifest-serializer parity fixture) validates against schemas/theme-manifest.schema.json --"
check_golden_fixture "fixtures/golden.theme.json" "schemas/theme-manifest.schema.json"

echo "== validate.py: kind-aware font-entry validation (schemas/font-manifest.schema.json + schemas/font-meta.schema.json, SPEC F104.1/F104.2 / T195) =="

echo "-- green valid-font fixture validates clean end-to-end as a kind:\"font\" entry --"
TMP_FONT_TREE="$(mktemp -d)"
mkdir -p "$TMP_FONT_TREE/entries/fonts/valid-font"
cp "$FONT_GREEN_FIXTURE/valid-font.font.json" "$TMP_FONT_TREE/entries/fonts/valid-font/valid-font.font.json"
cp "$FONT_GREEN_FIXTURE/valid-font.meta.json" "$TMP_FONT_TREE/entries/fonts/valid-font/valid-font.meta.json"
cp "$FONT_GREEN_FIXTURE/valid-font-variable-latin.woff2" "$TMP_FONT_TREE/entries/fonts/valid-font/valid-font-variable-latin.woff2"
cp "$FONT_GREEN_FIXTURE/OFL.txt" "$TMP_FONT_TREE/entries/fonts/valid-font/OFL.txt"
output=$(python3 tools/validate.py --root "$TMP_FONT_TREE" 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "green valid-font fixture validates clean as a kind:\"font\" entry"
else
    fail "green valid-font fixture did not validate clean as a kind:\"font\" entry (expected exit 0, got $status)"
fi
echo

echo "-- red font-manifest schema-shape gates: schemas/font-manifest.schema.json's own required-field and pattern checks (SPEC F104.1, T195 review finding — these previously had zero red coverage; mirrors bad-theme-mode/missing-theme-preview's role for the theme kind above) --"
check_red_variant font-manifest-missing-weight-bytes "'weight' is a required property"
check_red_variant font-manifest-bad-family "does not match '^[A-Za-z0-9][A-Za-z0-9 -]*"
check_red_variant font-manifest-bad-sourceurl "does not match '^https://'"

check_red_variant font-missing-ofl "font-missing-ofl"
check_red_variant font-bad-license "font-bad-license"
check_red_variant font-orphan-manifest "font-orphan-manifest-file"
check_red_variant font-duplicate-asset "font-duplicate-asset"
check_red_variant font-stowaway-asset "font-stowaway-asset"

echo "-- red font-over-ceiling: per-pack byte ceiling rejects a font pack whose summed asset bytes exceed 204,800 (SPEC F104.2) --"
if python3 - "$FONT_OVER_CEILING_ASSET" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
# 205 KiB alone already exceeds the 200 KiB (204,800-byte) per-pack ceiling —
# generated here at test time, not committed (see .gitignore), the same
# oversize-card precedent immediately above.
path.write_bytes(b"x" * (205 * 1024))
print(f"generated {path} ({path.stat().st_size} bytes)")
PY
then
    check_red_variant font-over-ceiling "font-pack-ceiling"
else
    fail "failed to generate the font-over-ceiling fixture asset"
fi
rm -f "$FONT_OVER_CEILING_ASSET"

echo "-- fixtures/golden.font.json (the app font-manifest-serializer parity fixture) validates against schemas/font-manifest.schema.json --"
check_golden_fixture "fixtures/golden.font.json" "schemas/font-manifest.schema.json"

echo "== validate.py: kind-aware show-entry validation (schemas/show-manifest.schema.json + schemas/show-meta.schema.json, SPEC F118.1/F118.4, T253) =="

echo "-- green valid-show fixture validates clean end-to-end as a kind:\"show\" entry --"
TMP_SHOW_TREE="$(mktemp -d)"
mkdir -p "$TMP_SHOW_TREE/entries/shows/valid-show"
cp "$SHOW_GREEN_FIXTURE/valid-show.show.json" "$TMP_SHOW_TREE/entries/shows/valid-show/valid-show.show.json"
cp "$SHOW_GREEN_FIXTURE/valid-show.meta.json" "$TMP_SHOW_TREE/entries/shows/valid-show/valid-show.meta.json"
output=$(python3 tools/validate.py --root "$TMP_SHOW_TREE" 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "green valid-show fixture validates clean as a kind:\"show\" entry"
else
    fail "green valid-show fixture did not validate clean as a kind:\"show\" entry (expected exit 0, got $status)"
fi
echo

echo "-- red show-manifest schema-shape gate: a manifest missing the required 'flavor' field is rejected (SPEC F118.1) --"
check_red_variant show-manifest-missing-flavor "'flavor' is a required property"

echo "-- red show-missing-audience: audience is required for a show entry same as every other kind (SPEC F118.4 AC2) --"
check_red_variant show-missing-audience "'audience' is a required property"

echo "-- red show-meta-bad-suggested-persona: suggestedPersona is untrusted input, not free text — a path-traversal string is rejected by the slug pattern/maxLength gate, not merely non-empty (security review MUST-FIX 1) --"
check_red_variant show-meta-bad-suggested-persona "suggestedPersona: '../../etc/passwd' does not match"

echo "-- red show-meta-suggested-persona-too-long: a shape-valid slug at 65 chars (one over the 64-char cap) is rejected by maxLength alone, not the pattern — kills a mutant that widens or drops the cap (security review nit) --"
check_red_variant show-meta-suggested-persona-too-long "suggestedPersona: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' is too long"

echo "-- red show-stowaway-asset: a stray .woff2 in a show entry directory is rejected — show's KindSpec.allows_extra is always False (unlike font's own asset allowance), so ANY sibling file beyond the manifest/meta is unexpected (security review NOTE 4) --"
check_red_variant show-stowaway-asset "unexpected-file"

echo "-- fixtures/golden.show.json (the cross-repo show-manifest parity fixture, PLAN T254) validates against schemas/show-manifest.schema.json --"
check_golden_fixture "fixtures/golden.show.json" "schemas/show-manifest.schema.json"

echo "== validate.py: kind-aware avatar-entry validation (schemas/avatar-manifest.schema.json + schemas/avatar-meta.schema.json, SPEC F128.1, T309) =="

echo "-- green valid-avatar fixture validates clean end-to-end as a kind:\"avatar\" entry --"
TMP_AVATAR_TREE="$(mktemp -d)"
mkdir -p "$TMP_AVATAR_TREE/entries/avatars/valid-avatar"
cp "$AVATAR_GREEN_FIXTURE/valid-avatar.avatar.json" "$TMP_AVATAR_TREE/entries/avatars/valid-avatar/valid-avatar.avatar.json"
cp "$AVATAR_GREEN_FIXTURE/valid-avatar.meta.json" "$TMP_AVATAR_TREE/entries/avatars/valid-avatar/valid-avatar.meta.json"
cp "$AVATAR_GREEN_FIXTURE/warm-grin.png" "$TMP_AVATAR_TREE/entries/avatars/valid-avatar/warm-grin.png"
cp "$AVATAR_GREEN_FIXTURE/cool-smirk.png" "$TMP_AVATAR_TREE/entries/avatars/valid-avatar/cool-smirk.png"
output=$(python3 tools/validate.py --root "$TMP_AVATAR_TREE" 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "green valid-avatar fixture validates clean as a kind:\"avatar\" entry"
else
    fail "green valid-avatar fixture did not validate clean as a kind:\"avatar\" entry (expected exit 0, got $status)"
fi
echo

echo "-- red avatar-manifest-missing-file: schema-shape gate, an items[] element missing the required 'file' field --"
check_red_variant avatar-manifest-missing-file "'file' is a required property"

echo "-- red avatar-too-many-items: schema-shape gate, 65 items[] elements is one over GenWave.Host.Api.AvatarPackController.MaxPackItems (F1, T309) — the app 400s the whole pack at 65, a catalog-green/app-red divergence this maxItems closes --"
check_red_variant avatar-too-many-items "is too long"

echo "-- red avatar-item-name-too-long: schema-shape gate, a 65-character item name is one over AvatarPackController.MaxItemNameLength (F2, T309) --"
check_red_variant avatar-item-name-too-long "is too long"

echo "-- red avatar-item-name-control-char: schema-shape gate, an item name carrying a control character fails the pattern mirroring AvatarPackController.IsValidItemName's char.IsControl gate (F2, T309) --"
check_red_variant avatar-item-name-control-char "does not match"

echo "-- red avatar-bad-magic: a .png-named file that isn't PNG bytes at all — extension is never trusted --"
check_red_variant avatar-bad-magic "avatar-png-magic"

echo "-- red avatar-bad-dimensions: a 256x256 PNG is rejected — the item must be exactly 512x512 --"
check_red_variant avatar-bad-dimensions "avatar-png-dimensions: 'too-small.png' is 256x256, not exactly 512x512"

echo "-- red avatar-actl-reject: an animated PNG (acTL chunk before the first IDAT) is rejected (APNG) --"
check_red_variant avatar-actl-reject "avatar-png-actl"

echo "-- red avatar-duplicate-name: two items declaring the same display 'name' --"
check_red_variant avatar-duplicate-name "avatar-duplicate-name: manifest declares item name 'Same Name' more than once"

echo "-- red avatar-orphan-item-file: items[] names a PNG the entry never ships --"
check_red_variant avatar-orphan-item-file "avatar-orphan-item-file"

echo "-- red avatar-stowaway-asset: a shipped PNG no item references — the reverse of the orphan check --"
check_red_variant avatar-stowaway-asset "avatar-stowaway-asset"

echo "-- red avatar-item-oversize: a single PNG item over the 512 KiB per-item ceiling (SPEC F128.1) --"
if python3 - "$AVATAR_ITEM_OVERSIZE_PNG" <<'PY'
import struct
import sys
import zlib
from pathlib import Path


def chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


path = Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
signature = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 512, 512, 8, 2, 0, 0, 0))
# Junk IDAT payload well past the 524,288-byte (512 KiB) per-item cap — this
# validator never decodes pixel data (mirrors the app's own PngImageHeader),
# so the bytes need not be real deflate data, only chunk-shaped.
idat = chunk(b"IDAT", b"\x00" * 530000)
iend = chunk(b"IEND", b"")
path.write_bytes(signature + ihdr + idat + iend)
print(f"generated {path} ({path.stat().st_size} bytes)")
PY
then
    check_red_variant avatar-item-oversize "avatar-png-oversize"
else
    fail "failed to generate the avatar-item-oversize fixture asset"
fi
rm -f "$AVATAR_ITEM_OVERSIZE_PNG"

echo "-- red avatar-pack-ceiling: 13 PNGs, each under the per-item cap, summing past the 6 MiB per-pack ceiling (SPEC F128.1) --"
if python3 - "$RED_DIR/avatar-pack-ceiling/entries/avatars/avatar-pack-ceiling" <<'PY'
import struct
import sys
import zlib
from pathlib import Path


def chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


directory = Path(sys.argv[1])
directory.mkdir(parents=True, exist_ok=True)
signature = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 512, 512, 8, 2, 0, 0, 0))
iend = chunk(b"IEND", b"")
# 13 faces at ~510 KiB each (under the 524,288-byte per-item cap alone) sum
# to ~6.63 MiB, past the 6,291,456-byte (6 MiB) per-pack ceiling — proves
# the PACK ceiling fires independently of the per-item one.
idat = chunk(b"IDAT", b"\x00" * 510000)
total = 0
for i in range(13):
    data = signature + ihdr + idat + iend
    (directory / f"face-{i:02d}.png").write_bytes(data)
    total += len(data)
print(f"generated 13 faces under {directory} (summed {total} bytes)")
PY
then
    check_red_variant avatar-pack-ceiling "avatar-pack-ceiling"
else
    fail "failed to generate the avatar-pack-ceiling fixture assets"
fi
rm -f "$RED_DIR"/avatar-pack-ceiling/entries/avatars/avatar-pack-ceiling/face-*.png

echo "== validate.py: a persona entry's own optional avatar sidecar face (SPEC F128.2, T309) =="

echo "-- green valid-dj-with-avatar fixture validates clean — the sidecar face rides the same PNG rules as a pack item --"
TMP_PERSONA_AVATAR_TREE="$(mktemp -d)"
mkdir -p "$TMP_PERSONA_AVATAR_TREE/entries/personas/valid-dj-with-avatar"
cp "$PERSONA_AVATAR_GREEN_FIXTURE"/*.persona.json "$TMP_PERSONA_AVATAR_TREE/entries/personas/valid-dj-with-avatar/"
cp "$PERSONA_AVATAR_GREEN_FIXTURE"/*.meta.json "$TMP_PERSONA_AVATAR_TREE/entries/personas/valid-dj-with-avatar/"
cp "$PERSONA_AVATAR_GREEN_FIXTURE"/*.avatar.png "$TMP_PERSONA_AVATAR_TREE/entries/personas/valid-dj-with-avatar/"
output=$(python3 tools/validate.py --root "$TMP_PERSONA_AVATAR_TREE" 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "green valid-dj-with-avatar fixture validates clean with its sidecar face"
else
    fail "green valid-dj-with-avatar fixture did not validate clean (expected exit 0, got $status)"
fi
echo

echo "-- red persona-avatar-bad-dimensions: a persona's own sidecar face is held to the SAME 512x512 rule as a pack item --"
check_red_variant persona-avatar-bad-dimensions "persona-avatar-png-dimensions"

echo "== validate.py: kind-aware icon-entry validation (schemas/icon-manifest.schema.json + schemas/icon-meta.schema.json, SPEC F130.1/F130.6, T309) =="

echo "-- green valid-icon fixture (every whitelisted primitive tag) validates clean end-to-end as a kind:\"icon\" entry --"
TMP_ICON_TREE="$(mktemp -d)"
mkdir -p "$TMP_ICON_TREE/entries/icons/valid-icon"
cp "$ICON_GREEN_FIXTURE/valid-icon.icon.json" "$TMP_ICON_TREE/entries/icons/valid-icon/valid-icon.icon.json"
cp "$ICON_GREEN_FIXTURE/valid-icon.meta.json" "$TMP_ICON_TREE/entries/icons/valid-icon/valid-icon.meta.json"
output=$(python3 tools/validate.py --root "$TMP_ICON_TREE" 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "green valid-icon fixture validates clean as a kind:\"icon\" entry"
else
    fail "green valid-icon fixture did not validate clean as a kind:\"icon\" entry (expected exit 0, got $status)"
fi
echo

echo "-- red icon-bad-tag: an element tag outside the closed seven-primitive whitelist --"
check_red_variant icon-bad-tag "is not one of ['path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon']"

echo "-- red icon-bad-d-grammar: a path 'd' attribute outside PathDataText's character grammar --"
check_red_variant icon-bad-d-grammar "does not match"

echo "-- red icon-bad-points-grammar: a polyline 'points' attribute outside PointsText's character grammar --"
check_red_variant icon-bad-points-grammar "does not match"

echo "-- red icon-bad-fill: a literal colour ('red') where only none|currentColor is expressible --"
check_red_variant icon-bad-fill "'red' is not one of ['none', 'currentColor']"

echo "-- red icon-strokewidth-out-of-range: style.strokeWidth outside the [0.5, 3] SPEC F130.1 range --"
check_red_variant icon-strokewidth-out-of-range "is greater than the maximum of 3"

echo "-- red icon-name-bad-pattern: an icon-map key outside ^[a-z][a-z0-9-]*\$ (the map-KEY gate, not just element values) --"
check_red_variant icon-name-bad-pattern "does not match"

echo "-- red icon-name-too-long: an icon-map key at 65 chars, one over the 64-char cap --"
check_red_variant icon-name-too-long "is too long"

echo "-- red icon-attr-not-finite: a JSON-legal '1e400' geometry literal overflows to a non-finite float once parsed — no JSON Schema keyword can catch this, so tools/validate.py's own numeric walk is the actual gate --"
check_red_variant icon-attr-not-finite "icon-attr-not-finite"

echo "-- red icon-licence-in-manifest: the F1 ruling — a 'license' member inside <slug>.icon.json is a HARD reject (the app's own serializer would silently drop it), licence/provenance belongs in meta.json only (SPEC F130.6) --"
check_red_variant icon-licence-in-manifest "icon-licence-in-manifest"

echo "-- red icon-meta-missing-license: the F1 ruling's other half — an icon entry's meta.json REQUIRES 'license' (and 'sourceUrl') --"
check_red_variant icon-meta-missing-license "'license' is a required property"

echo "-- red icon-elements-per-icon-over-cap: 65 elements on one icon, over the 64-element-per-icon cap (SPEC F130.1) --"
check_red_variant icon-elements-per-icon-over-cap "is too long"

echo "-- red icon-too-many-icons: 513 icons in one pack, over the 512-icon-per-pack cap (SPEC F130.1) --"
check_red_variant icon-too-many-icons "has too many properties"

echo "-- red icon-over-ceiling: the definition exceeds the 256 KiB SPEC F130.1 size cap --"
if python3 - "$ICON_OVER_CEILING_DIR" <<'PY'
import json
import sys
from pathlib import Path

directory = Path(sys.argv[1])
directory.mkdir(parents=True, exist_ok=True)
slug = directory.name

# 300 icons x 20 circle elements each (well under the 512-icon/64-element
# caps individually) comfortably clears the 262,144-byte definition cap on
# its own — an otherwise fully schema-valid document, so ONLY the size-cap
# rule fires, not the icon-count or elements-per-icon ones.
icons = {
    f"icon-{i:03d}": [{"tag": "circle", "cx": j % 16, "cy": j % 16, "r": 1} for j in range(20)]
    for i in range(300)
}
manifest = {"style": {"strokeWidth": 1, "fill": "none"}, "icons": icons}
(directory / f"{slug}.icon.json").write_text(json.dumps(manifest))

meta = {
    "author": "GenWave",
    "description": "Red-variant fixture.",
    "audience": "everyone",
    "added": "2026-08-16",
    "license": "MIT",
    "sourceUrl": "https://example.com/upstream",
    "version": None,
}
(directory / f"{slug}.meta.json").write_text(json.dumps(meta))
size = (directory / f"{slug}.icon.json").stat().st_size
print(f"generated {directory}/{slug}.icon.json ({size} bytes)")
PY
then
    check_red_variant icon-over-ceiling "size-cap"
else
    fail "failed to generate the icon-over-ceiling fixture"
fi
rm -f "$ICON_OVER_CEILING_DIR"/icon-over-ceiling.icon.json "$ICON_OVER_CEILING_DIR"/icon-over-ceiling.meta.json

echo "== validate.py: kind-aware ad-pack-entry validation (schemas/ad-pack-manifest.schema.json + schemas/ad-pack-meta.schema.json, SPEC F162.2, app PLAN T405/T407) =="

echo "-- green valid-ad-pack fixture (every-hint, null-hint, and brand-only briefs) validates clean end-to-end as a kind:\"ad-pack\" entry --"
TMP_AD_PACK_TREE="$(mktemp -d)"
mkdir -p "$TMP_AD_PACK_TREE/entries/ad-packs/valid-ad-pack"
cp "$AD_PACK_GREEN_FIXTURE/valid-ad-pack.ad-pack.json" "$TMP_AD_PACK_TREE/entries/ad-packs/valid-ad-pack/valid-ad-pack.ad-pack.json"
cp "$AD_PACK_GREEN_FIXTURE/valid-ad-pack.meta.json" "$TMP_AD_PACK_TREE/entries/ad-packs/valid-ad-pack/valid-ad-pack.meta.json"
output=$(python3 tools/validate.py --root "$TMP_AD_PACK_TREE" 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "green valid-ad-pack fixture validates clean as a kind:\"ad-pack\" entry"
else
    fail "green valid-ad-pack fixture did not validate clean as a kind:\"ad-pack\" entry (expected exit 0, got $status)"
fi
echo

echo "-- red ad-pack-no-briefs: an empty briefs[] is no pack at all (minItems 1 — CatalogAdPackManifestSerializer's own 'no briefs, no manifest') --"
check_red_variant ad-pack-no-briefs "is too short"

echo "-- red ad-pack-blank-brand: a whitespace-only brand fails the \\S pattern (the serializer's own non-blank rule — minLength alone admitted it) --"
check_red_variant ad-pack-blank-brand "briefs/0/brand"

echo "-- red ad-pack-hint-too-long: a 501-char premise, one over MaxHintLength (500) --"
check_red_variant ad-pack-hint-too-long "is too long"

echo "-- red ad-pack-too-many-briefs: 101 briefs, one over MaxBriefsPerPack (100) --"
check_red_variant ad-pack-too-many-briefs "is too long"

echo "-- red ad-pack-unknown-field: a misspelled hint member ('premis') fails CI rather than installing as a brief with no premise (the app's reader ignores unknown members silently) --"
check_red_variant ad-pack-unknown-field "Additional properties are not allowed"

echo "-- red ad-pack-duplicate-brand: two briefs sharing a brand after case/whitespace folding — the one cross-item rule JSON Schema cannot express --"
check_red_variant ad-pack-duplicate-brand "ad-pack-duplicate-brand"

echo "-- red ad-pack-stowaway-file: the closed folder set — only <slug>.ad-pack.json and <slug>.meta.json (an ad pack carries no assets of any kind) --"
check_red_variant ad-pack-stowaway-file "unexpected-file"

echo "-- red ad-pack-over-ceiling: a schema-valid manifest padded past the 256 KiB manifest fetch cap (CatalogProxyService.MaxCardBytes) --"
if python3 - "$AD_PACK_OVER_CEILING_DIR" <<'PY'
import json
import sys
from pathlib import Path

directory = Path(sys.argv[1])
directory.mkdir(parents=True, exist_ok=True)
slug = directory.name

# One schema-valid brief, then 300 KB of JSON whitespace inside the array —
# the schema's own caps (100 briefs x (200 + 3 x 500) chars) keep every REAL
# pack far below 256 KiB, so padding is the only way a valid document reaches
# the cap, and ONLY the size-cap rule fires.
padded = '{"briefs": [' + " " * 300_000 + '{"brand": "Padded Brand"}]}'
(directory / f"{slug}.ad-pack.json").write_text(padded)
meta = {"author": "GenWave", "description": "Red-variant fixture.", "audience": "everyone", "added": "2026-09-05"}
(directory / f"{slug}.meta.json").write_text(json.dumps(meta))
size = (directory / f"{slug}.ad-pack.json").stat().st_size
print(f"generated {directory}/{slug}.ad-pack.json ({size} bytes)")
PY
then
    check_red_variant ad-pack-over-ceiling "size-cap"
else
    fail "failed to generate the ad-pack-over-ceiling fixture"
fi
rm -f "$AD_PACK_OVER_CEILING_DIR"/ad-pack-over-ceiling.ad-pack.json "$AD_PACK_OVER_CEILING_DIR"/ad-pack-over-ceiling.meta.json

echo "== build_index.py + schemas/index.schema.json: ad-pack kind projects manifest only — no card/assets/family/preview (SPEC F162.2) =="
TMP_AD_PACK_INDEX_TREE="$(mktemp -d)"
mkdir -p "$TMP_AD_PACK_INDEX_TREE/entries/ad-packs/valid-ad-pack"
cp "$AD_PACK_GREEN_FIXTURE/valid-ad-pack.ad-pack.json" "$TMP_AD_PACK_INDEX_TREE/entries/ad-packs/valid-ad-pack/valid-ad-pack.ad-pack.json"
cp "$AD_PACK_GREEN_FIXTURE/valid-ad-pack.meta.json" "$TMP_AD_PACK_INDEX_TREE/entries/ad-packs/valid-ad-pack/valid-ad-pack.meta.json"

tmp_ad_pack_index="$(mktemp)"
ad_pack_index_build_ok=1
if ! python3 tools/build_index.py --root "$TMP_AD_PACK_INDEX_TREE" --out "$tmp_ad_pack_index"; then
    fail "build_index.py exited non-zero building the ad-pack-kind fixture tree"
    ad_pack_index_build_ok=0
fi

if [[ $ad_pack_index_build_ok -eq 1 ]]; then
    tmp_ad_pack_index_check="$(mktemp)"
    cat >"$tmp_ad_pack_index_check" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[4])
from index_entry_schema import load_entry_validator

index_path, tree_root, schema_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
data = json.loads(index_path.read_text())
by_slug = {e["slug"]: e for e in data["entries"]}
validator = load_entry_validator(schema_path)

errors = []

pack = by_slug.get("valid-ad-pack")
if pack is None:
    errors.append("valid-ad-pack entry missing from built index")
else:
    if pack.get("kind") != "ad-pack":
        errors.append(f"valid-ad-pack: expected kind 'ad-pack', got {pack.get('kind')!r}")
    for absent_key in ("card", "assets", "family", "preview"):
        if absent_key in pack:
            errors.append(f"valid-ad-pack: unexpected '{absent_key}' key on an ad-pack entry")
    manifest = pack.get("manifest")
    if not isinstance(manifest, dict):
        errors.append("valid-ad-pack: missing 'manifest' key")
    else:
        path = manifest.get("path")
        if not isinstance(path, str) or not path.endswith("valid-ad-pack.ad-pack.json"):
            errors.append(f"valid-ad-pack.manifest.path unexpected: {path!r}")
        else:
            want = hashlib.sha256((tree_root / path).read_bytes()).hexdigest()
            got = manifest.get("sha256")
            if want != got:
                errors.append(f"valid-ad-pack.manifest.sha256 mismatch: recomputed {want}, index has {got}")
    pack_errors = [e.message for e in validator.iter_errors(pack)]
    if pack_errors:
        errors.append(f"valid-ad-pack entry does not validate against schemas/index.schema.json: {pack_errors}")

if errors:
    for line in errors:
        print(line)
    sys.exit(1)
print(
    "ad-pack-kind index shape OK: kind/manifest projected (sha256 verified), no card/assets/family/preview, "
    "entry validates against schemas/index.schema.json"
)
PY
    if python3 "$tmp_ad_pack_index_check" "$tmp_ad_pack_index" "$TMP_AD_PACK_INDEX_TREE" "schemas/index.schema.json" "$TMP_SCHEMA_HELPERS_DIR"; then
        pass "build_index.py projects an ad-pack entry's kind+manifest only (no card/assets/family/preview); entry schema-valid"
    else
        fail "build_index.py ad-pack-kind projection assertions failed"
    fi
    rm -f "$tmp_ad_pack_index_check"
else
    fail "skipped ad-pack-kind projection assertions because build_index.py failed above"
fi
rm -f "$tmp_ad_pack_index"
echo

echo "== validate.py: kind-aware voice-pack-entry validation (schemas/voice-pack-manifest.schema.json + schemas/voice-pack-meta.schema.json, SPEC F164, app PLAN T410/T412/T413) =="

echo "-- green valid-voice-pack fixture (a plain voice plus a blended one, sourceRef: null) validates clean end-to-end as a kind:\"voice-pack\" entry --"
TMP_VOICE_PACK_TREE="$(mktemp -d)"
mkdir -p "$TMP_VOICE_PACK_TREE/entries/voice-packs/valid-voice-pack"
cp "$VOICE_PACK_GREEN_FIXTURE"/* "$TMP_VOICE_PACK_TREE/entries/voice-packs/valid-voice-pack/"
output=$(python3 tools/validate.py --root "$TMP_VOICE_PACK_TREE" 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "green valid-voice-pack fixture validates clean as a kind:\"voice-pack\" entry"
else
    fail "green valid-voice-pack fixture did not validate clean as a kind:\"voice-pack\" entry (expected exit 0, got $status)"
fi
echo

echo "-- green valid-voice-pack-no-sourceref fixture (sourceRef key absent entirely, not merely null) validates clean --"
tmp_voice_pack_no_sourceref_tree="$(mktemp -d)"
mkdir -p "$tmp_voice_pack_no_sourceref_tree/entries/voice-packs/valid-voice-pack-no-sourceref"
cp "$VOICE_PACK_NO_SOURCEREF_GREEN_FIXTURE"/* "$tmp_voice_pack_no_sourceref_tree/entries/voice-packs/valid-voice-pack-no-sourceref/"
output=$(python3 tools/validate.py --root "$tmp_voice_pack_no_sourceref_tree" 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "green valid-voice-pack-no-sourceref fixture validates clean (sourceRef absent is legal, SPEC F164.3)"
else
    fail "green valid-voice-pack-no-sourceref fixture did not validate clean (expected exit 0, got $status)"
fi
rm -rf "$tmp_voice_pack_no_sourceref_tree"
echo

echo "-- red missing-preview: schema-shape gate, 'preview' is a required manifest member --"
check_red_variant missing-preview "'preview' is a required property"

echo "-- red preview-over-max: a real MP3 (ID3 magic) padded past the 150 KiB preview cap (SPEC F164) --"
if python3 - "$VOICE_PACK_PREVIEW_OVER_MAX" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
# A real ID3-tagged MP3 header (has_mp3_magic checks only the first bytes),
# padded well past the 153,600-byte (150 KiB) preview cap — same "real
# magic, junk payload" posture as avatar-item-oversize's PNG chunk.
path.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 160_000)
print(f"generated {path} ({path.stat().st_size} bytes)")
PY
then
    check_red_variant preview-over-max "voice-pack-preview-over-max"
else
    fail "failed to generate the preview-over-max fixture asset"
fi
rm -f "$VOICE_PACK_PREVIEW_OVER_MAX"

echo "-- red preview-bad-magic: a preview file, correctly named, that isn't an MP3 at all — extension is never trusted --"
check_red_variant preview-bad-magic "voice-pack-preview-magic"

echo "-- red preview-wrong-name: the preview's own stem does not equal THIS entry's slug (voice-pack-preview-name; the schema only pins the SHAPE of preview) --"
check_red_variant preview-wrong-name "voice-pack-preview-name"

echo "-- red synthetic-false: schema-shape gate, 'synthetic' is pinned const true (SPEC F164.3) --"
check_red_variant synthetic-false "True was expected"

echo "-- red sourceref-non-null: schema-shape gate, sourceRef must be null when present (SPEC F164.3) --"
check_red_variant sourceref-non-null "is not of type 'null'"

echo "-- red voiceid-uppercase: schema-shape gate, voiceId must match the lowercase SettingValidator.VoiceIdFormat() class --"
check_red_variant voiceid-uppercase "does not match"

echo "-- red voiceid-traversal: schema-shape gate, a '../x' voiceId fails the same lowercase pattern --"
check_red_variant voiceid-traversal "does not match"

echo "-- red voiceid-too-long: schema-shape gate, a 65-character voiceId is one over maxLength 64 --"
check_red_variant voiceid-too-long "is too long"

echo "-- red file-mismatch: voices[].file does not equal '<voiceId>.pt' for that item's own voiceId (voice-pack-file-mismatch — the schema only pins file's SHAPE, never this cross-property equality) --"
check_red_variant file-mismatch "voice-pack-file-mismatch"

echo "-- red duplicate-voice: the same voiceId declared twice with different gender/age (voice-pack-duplicate-voice — schema uniqueItems alone only forbids two IDENTICAL objects) --"
check_red_variant duplicate-voice "voice-pack-duplicate-voice"

echo "-- red too-many-voices: schema-shape gate, 17 voices[] elements is one over maxItems 16 --"
check_red_variant too-many-voices "is too long"

echo "-- red pt-bad-magic: a .pt-named file that isn't zip/torch bytes at all — extension is never trusted --"
check_red_variant pt-bad-magic "voice-pack-pt-magic"

echo "-- red pt-over-max: a real zip/torch archive padded past the 1 MiB per-weight cap (SPEC F164) --"
if python3 - "$VOICE_PACK_PT_OVER_MAX" <<'PY'
import sys
import zipfile
from pathlib import Path

path = Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as zf:
    # Padded well past the 1,048,576-byte (1 MiB) per-weight cap — a real
    # zip/torch archive (has_zip_magic checks the local-file-header magic
    # only), same "real container, junk payload" posture as
    # avatar-item-oversize's PNG chunk.
    zf.writestr("data.bin", b"\x00" * 1_100_000)
print(f"generated {path} ({path.stat().st_size} bytes)")
PY
then
    check_red_variant pt-over-max "voice-pack-pt-over-max"
else
    fail "failed to generate the pt-over-max fixture asset"
fi
rm -f "$VOICE_PACK_PT_OVER_MAX"

echo "-- red over-ceiling: 9 weights, each under the per-weight cap, summing past the 8 MiB per-pack ceiling (SPEC F164) --"
if python3 - "$VOICE_PACK_OVER_CEILING_DIR" <<'PY'
import sys
import zipfile
from pathlib import Path

directory = Path(sys.argv[1])
directory.mkdir(parents=True, exist_ok=True)
# 9 weights at ~950 KiB each (under the 1,048,576-byte per-weight cap alone)
# sum to ~8.35 MiB, past the 8,388,608-byte (8 MiB) per-pack ceiling —
# proves the PACK ceiling fires independently of the per-weight one, same
# posture as avatar-pack-ceiling's 13 faces.
total = 0
for i in range(9):
    weight_path = directory / f"voice{i}.pt"
    with zipfile.ZipFile(weight_path, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("data.bin", b"\x00" * 950_000)
    total += weight_path.stat().st_size
print(f"generated 9 weights under {directory} (summed {total} bytes)")
PY
then
    check_red_variant over-ceiling "voice-pack-over-ceiling"
else
    fail "failed to generate the over-ceiling fixture assets"
fi
rm -f "$VOICE_PACK_OVER_CEILING_DIR"/voice*.pt

echo "-- red orphan-pt: the entry ships an extra .pt file no voices[] entry names (voice-pack-orphan-file — T411 brief wording, the OPPOSITE of font-pack's own \"orphan\" direction) --"
check_red_variant orphan-pt "voice-pack-orphan-file"

echo "-- red stowaway-file: a file that doesn't even match VOICE_ASSET_NAME_PATTERN (the KindSpec-level unexpected-file gate, before validate_voice_pack ever runs) --"
check_red_variant stowaway-file "unexpected-file"

echo "-- red voice-pack-unknown-field: an unrecognized top-level manifest member fails CI rather than installing silently --"
check_red_variant voice-pack-unknown-field "Additional properties are not allowed"

echo "== build_index.py + schemas/index.schema.json: voice-pack kind projects manifest + assets[] (weights and preview), no card/family (SPEC F164) =="
TMP_VOICE_PACK_INDEX_TREE="$(mktemp -d)"
mkdir -p "$TMP_VOICE_PACK_INDEX_TREE/entries/voice-packs/valid-voice-pack"
cp "$VOICE_PACK_GREEN_FIXTURE"/* "$TMP_VOICE_PACK_INDEX_TREE/entries/voice-packs/valid-voice-pack/"

tmp_voice_pack_index="$(mktemp)"
voice_pack_index_build_ok=1
if ! python3 tools/build_index.py --root "$TMP_VOICE_PACK_INDEX_TREE" --out "$tmp_voice_pack_index"; then
    fail "build_index.py exited non-zero building the voice-pack-kind fixture tree"
    voice_pack_index_build_ok=0
fi

if [[ $voice_pack_index_build_ok -eq 1 ]]; then
    tmp_voice_pack_index_check="$(mktemp)"
    cat >"$tmp_voice_pack_index_check" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[4])
from index_entry_schema import load_entry_validator

index_path, tree_root, schema_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
data = json.loads(index_path.read_text())
by_slug = {e["slug"]: e for e in data["entries"]}
validator = load_entry_validator(schema_path)

errors = []

pack = by_slug.get("valid-voice-pack")
if pack is None:
    errors.append("valid-voice-pack entry missing from built index")
else:
    if pack.get("kind") != "voice-pack":
        errors.append(f"valid-voice-pack: expected kind 'voice-pack', got {pack.get('kind')!r}")
    for absent_key in ("card", "family"):
        if absent_key in pack:
            errors.append(f"valid-voice-pack: unexpected '{absent_key}' key on a voice-pack entry")
    entry_dir = tree_root / "entries/voice-packs/valid-voice-pack"
    on_disk = sorted(
        p for p in entry_dir.iterdir()
        if p.is_file() and p.name not in ("valid-voice-pack.voice-pack.json", "valid-voice-pack.meta.json")
    )
    assets = pack.get("assets")
    if not isinstance(assets, list) or not assets:
        errors.append("valid-voice-pack: missing non-empty 'assets' key")
    else:
        got_paths = sorted(a.get("path") for a in assets)
        want_paths = sorted(f"entries/voice-packs/valid-voice-pack/{p.name}" for p in on_disk)
        if got_paths != want_paths:
            errors.append(f"valid-voice-pack.assets paths mismatch: got {got_paths}, want {want_paths}")
        if len(assets) != len(on_disk):
            errors.append(f"valid-voice-pack.assets count {len(assets)} != on-disk file count {len(on_disk)}")
        for asset in assets:
            asset_path = tree_root / asset["path"]
            want_sha256 = hashlib.sha256(asset_path.read_bytes()).hexdigest()
            if asset.get("sha256") != want_sha256:
                errors.append(f"{asset['path']}: sha256 mismatch: recomputed {want_sha256}, index has {asset.get('sha256')}")
            want_bytes = asset_path.stat().st_size
            if asset.get("bytes") != want_bytes:
                errors.append(f"{asset['path']}: bytes mismatch: recomputed {want_bytes}, index has {asset.get('bytes')}")
    manifest = pack.get("manifest")
    if not isinstance(manifest, dict):
        errors.append("valid-voice-pack: missing 'manifest' key")
    else:
        path = manifest.get("path")
        if not isinstance(path, str) or not path.endswith("valid-voice-pack.voice-pack.json"):
            errors.append(f"valid-voice-pack.manifest.path unexpected: {path!r}")
    pack_errors = [e.message for e in validator.iter_errors(pack)]
    if pack_errors:
        errors.append(f"valid-voice-pack entry does not validate against schemas/index.schema.json: {pack_errors}")

if errors:
    for line in errors:
        print(line)
    sys.exit(1)
print(
    "voice-pack-kind index shape OK: kind/manifest/assets[] projected (sha256+bytes verified, sorted, "
    "count matches on-disk files), no card/family, entry validates against schemas/index.schema.json"
)
PY
    if python3 "$tmp_voice_pack_index_check" "$tmp_voice_pack_index" "$TMP_VOICE_PACK_INDEX_TREE" "schemas/index.schema.json" "$TMP_SCHEMA_HELPERS_DIR"; then
        pass "build_index.py projects a voice-pack entry's kind+manifest+assets[] (weights+preview, no card/family); entry schema-valid"
    else
        fail "build_index.py voice-pack-kind projection assertions failed"
    fi
    rm -f "$tmp_voice_pack_index_check"
else
    fail "skipped voice-pack-kind projection assertions because build_index.py failed above"
fi
rm -f "$tmp_voice_pack_index"
echo

echo "== validate.py: kind-aware jingle-pack-entry validation (schemas/jingle-pack-manifest.schema.json + schemas/jingle-pack-meta.schema.json, SPEC F165, app PLAN T410/T412, STORY-400) =="

echo "-- green valid-jingle-pack fixture (CC0 bed/wav, CC-BY sting/mp3 with full attribution, CC0 station_id/flac) validates clean end-to-end as a kind:\"jingle-pack\" entry --"
TMP_JINGLE_PACK_TREE="$(mktemp -d)"
mkdir -p "$TMP_JINGLE_PACK_TREE/entries/jingle-packs/valid-jingle-pack"
cp "$JINGLE_PACK_GREEN_FIXTURE"/* "$TMP_JINGLE_PACK_TREE/entries/jingle-packs/valid-jingle-pack/"
output=$(python3 tools/validate.py --root "$TMP_JINGLE_PACK_TREE" 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "green valid-jingle-pack fixture validates clean as a kind:\"jingle-pack\" entry"
else
    fail "green valid-jingle-pack fixture did not validate clean as a kind:\"jingle-pack\" entry (expected exit 0, got $status)"
fi
echo

echo "-- red cc-by-sa: CC-BY-SA's share-alike obligation is refused by the closed license enum itself (SPEC F165.4) --"
check_red_variant cc-by-sa "is not one of"

echo "-- red cc-by-missing-attribution: license CC-BY with no attribution object at all (schema if/then, STORY-400 AC1) --"
check_red_variant cc-by-missing-attribution "'attribution' is a required property"

echo "-- red cc-by-missing-creator: attribution present but missing 'creator' --"
check_red_variant cc-by-missing-creator "'creator' is a required property"

echo "-- red cc-by-missing-sourceurl: attribution present but missing 'sourceUrl' --"
check_red_variant cc-by-missing-sourceurl "'sourceUrl' is a required property"

echo "-- red cc-by-bad-source-url: sourceUrl carries whitespace and an angle bracket after the scheme — the OLD prefix-only pattern let this through since it had no end anchor (T411 review round 1 finding 3) --"
check_red_variant cc-by-bad-source-url "does not match"

echo "-- red cc0-with-attribution: a CC0 asset has nothing to attribute — carrying an attribution object anyway is refused (schema if/then/else, STORY-400 AC1) --"
check_red_variant cc0-with-attribution "should not be valid under"

echo "-- red top-level-attribution: a pack-level attribution array is refused — attribution belongs to the ASSET, never the pack as a whole (STORY-400 AC6) --"
check_red_variant top-level-attribution "Additional properties are not allowed"

echo "-- red unknown-role: a role outside the closed bed/sting/station_id enum (SPEC F165.3) --"
check_red_variant unknown-role "is not one of"

echo "-- red sha256-mismatch: the declared sha256 does not match the real bytes on disk (jingle-pack-sha256-mismatch — the schema only pins sha256's SHAPE) --"
check_red_variant sha256-mismatch "jingle-pack-sha256-mismatch"

echo "-- red audio-bad-magic: a .wav-named file that isn't RIFF/WAVE bytes at all — extension is never trusted (jingle-pack-audio-magic) --"
check_red_variant audio-bad-magic "jingle-pack-audio-magic"

echo "-- red asset-over-max: a real RIFF/WAVE file padded past the 5 MiB per-asset cap, generated alongside its own manifest so sha256 stays self-consistent (SPEC F165) --"
if python3 - "$JINGLE_PACK_ASSET_OVER_MAX_DIR" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

directory = Path(sys.argv[1])
directory.mkdir(parents=True, exist_ok=True)
slug = directory.name

# A real RIFF/WAVE header, then padded well past the 5,242,880-byte (5 MiB)
# per-asset cap. The manifest is generated alongside it (not committed) so
# its own sha256 always matches these exact bytes — jingle-pack's sha256 is
# a REQUIRED, checked field, unlike voice-pack/avatar/font's asset refs, so
# committing a manifest separately from a regenerated oversized file would
# risk exactly the staleness this fixture is meant to avoid.
data = b"RIFF" + (5_300_000).to_bytes(4, "little") + b"WAVE" + b"\x00" * 5_300_000
audio_path = directory / "bed.wav"
audio_path.write_bytes(data)

manifest = {
    "packName": "Asset Over Max",
    "assets": [{
        "file": "bed.wav",
        "sha256": hashlib.sha256(data).hexdigest(),
        "role": "bed",
        "title": "Bed",
        "license": "CC0",
    }],
}
meta = {"author": "GenWave", "description": "Red-variant fixture.", "audience": "everyone", "added": "2026-09-05"}
(directory / f"{slug}.jingle-pack.json").write_text(json.dumps(manifest, indent=2) + "\n")
(directory / f"{slug}.meta.json").write_text(json.dumps(meta, indent=2) + "\n")
print(f"generated {audio_path} ({audio_path.stat().st_size} bytes)")
PY
then
    check_red_variant asset-over-max "jingle-pack-asset-over-max"
else
    fail "failed to generate the asset-over-max fixture"
fi
rm -f "$JINGLE_PACK_ASSET_OVER_MAX_DIR"/bed.wav "$JINGLE_PACK_ASSET_OVER_MAX_DIR"/asset-over-max.jingle-pack.json "$JINGLE_PACK_ASSET_OVER_MAX_DIR"/asset-over-max.meta.json

echo "-- red jingle-pack-over-ceiling: 9 RIFF/WAVE assets, each under the 5 MiB per-asset cap, summing past the 40 MiB per-pack ceiling (T411 review round 1 finding 5 — this rule shipped with zero red coverage; mirrors voice-pack's own over-ceiling fixture) --"
if python3 - "$JINGLE_PACK_OVER_CEILING_DIR" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

directory = Path(sys.argv[1])
directory.mkdir(parents=True, exist_ok=True)
slug = directory.name

# 9 assets at 4,700,012 bytes each (well under the 5,242,880-byte per-asset
# cap alone) sum to 42,300,108 bytes, past the 41,943,040-byte (40 MiB)
# per-pack ceiling — proves the PACK ceiling fires independently of the
# per-asset one, same posture as voice-pack's over-ceiling fixture. The
# whole entry (manifest + meta + audio) is generated together so every
# asset's required sha256 stays self-consistent, same posture as
# asset-over-max above.
assets = []
total = 0
for i in range(9):
    data = b"RIFF" + (4_700_000).to_bytes(4, "little") + b"WAVE" + b"\x00" * 4_700_000
    file_name = f"asset{i}.wav"
    (directory / file_name).write_bytes(data)
    total += len(data)
    assets.append({
        "file": file_name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "role": "bed",
        "title": f"Bed {i}",
        "license": "CC0",
    })

manifest = {"packName": "Jingle Pack Over Ceiling", "assets": assets}
meta = {"author": "GenWave", "description": "Red-variant fixture.", "audience": "everyone", "added": "2026-09-06"}
(directory / f"{slug}.jingle-pack.json").write_text(json.dumps(manifest, indent=2) + "\n")
(directory / f"{slug}.meta.json").write_text(json.dumps(meta, indent=2) + "\n")
print(f"generated 9 assets under {directory} (summed {total} bytes)")
PY
then
    check_red_variant jingle-pack-over-ceiling "jingle-pack-over-ceiling"
else
    fail "failed to generate the jingle-pack-over-ceiling fixture"
fi
rm -f "$JINGLE_PACK_OVER_CEILING_DIR"/asset*.wav "$JINGLE_PACK_OVER_CEILING_DIR"/jingle-pack-over-ceiling.jingle-pack.json "$JINGLE_PACK_OVER_CEILING_DIR"/jingle-pack-over-ceiling.meta.json

echo "-- red duplicate-title: two different assets sharing a title under fold_brand's own case/whitespace fold (jingle-pack-duplicate-asset) --"
check_red_variant duplicate-title "jingle-pack-duplicate-asset"

echo "-- red orphan-audio: the entry ships an audio file no assets[] entry names — the reverse of the missing-file check (jingle-pack-orphan-audio) --"
check_red_variant orphan-audio "jingle-pack-orphan-audio"

echo "-- red jingle-pack-unknown-field: an unrecognized member inside one asset item fails CI rather than being silently ignored --"
check_red_variant jingle-pack-unknown-field "Additional properties are not allowed"

echo "== build_index.py + schemas/index.schema.json: jingle-pack kind projects manifest + assets[], no card/family (SPEC F165) =="
TMP_JINGLE_PACK_INDEX_TREE="$(mktemp -d)"
mkdir -p "$TMP_JINGLE_PACK_INDEX_TREE/entries/jingle-packs/valid-jingle-pack"
cp "$JINGLE_PACK_GREEN_FIXTURE"/* "$TMP_JINGLE_PACK_INDEX_TREE/entries/jingle-packs/valid-jingle-pack/"

tmp_jingle_pack_index="$(mktemp)"
jingle_pack_index_build_ok=1
if ! python3 tools/build_index.py --root "$TMP_JINGLE_PACK_INDEX_TREE" --out "$tmp_jingle_pack_index"; then
    fail "build_index.py exited non-zero building the jingle-pack-kind fixture tree"
    jingle_pack_index_build_ok=0
fi

if [[ $jingle_pack_index_build_ok -eq 1 ]]; then
    tmp_jingle_pack_index_check="$(mktemp)"
    cat >"$tmp_jingle_pack_index_check" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[4])
from index_entry_schema import load_entry_validator

index_path, tree_root, schema_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
data = json.loads(index_path.read_text())
by_slug = {e["slug"]: e for e in data["entries"]}
validator = load_entry_validator(schema_path)

errors = []

pack = by_slug.get("valid-jingle-pack")
if pack is None:
    errors.append("valid-jingle-pack entry missing from built index")
else:
    if pack.get("kind") != "jingle-pack":
        errors.append(f"valid-jingle-pack: expected kind 'jingle-pack', got {pack.get('kind')!r}")
    for absent_key in ("card", "family"):
        if absent_key in pack:
            errors.append(f"valid-jingle-pack: unexpected '{absent_key}' key on a jingle-pack entry")
    entry_dir = tree_root / "entries/jingle-packs/valid-jingle-pack"
    on_disk = sorted(
        p for p in entry_dir.iterdir()
        if p.is_file() and p.name not in ("valid-jingle-pack.jingle-pack.json", "valid-jingle-pack.meta.json")
    )
    assets = pack.get("assets")
    if not isinstance(assets, list) or not assets:
        errors.append("valid-jingle-pack: missing non-empty 'assets' key")
    else:
        got_paths = sorted(a.get("path") for a in assets)
        want_paths = sorted(f"entries/jingle-packs/valid-jingle-pack/{p.name}" for p in on_disk)
        if got_paths != want_paths:
            errors.append(f"valid-jingle-pack.assets paths mismatch: got {got_paths}, want {want_paths}")
        if len(assets) != len(on_disk):
            errors.append(f"valid-jingle-pack.assets count {len(assets)} != on-disk file count {len(on_disk)}")
        for asset in assets:
            asset_path = tree_root / asset["path"]
            want_sha256 = hashlib.sha256(asset_path.read_bytes()).hexdigest()
            if asset.get("sha256") != want_sha256:
                errors.append(f"{asset['path']}: sha256 mismatch: recomputed {want_sha256}, index has {asset.get('sha256')}")
            want_bytes = asset_path.stat().st_size
            if asset.get("bytes") != want_bytes:
                errors.append(f"{asset['path']}: bytes mismatch: recomputed {want_bytes}, index has {asset.get('bytes')}")
    manifest = pack.get("manifest")
    if not isinstance(manifest, dict):
        errors.append("valid-jingle-pack: missing 'manifest' key")
    else:
        path = manifest.get("path")
        if not isinstance(path, str) or not path.endswith("valid-jingle-pack.jingle-pack.json"):
            errors.append(f"valid-jingle-pack.manifest.path unexpected: {path!r}")
    pack_errors = [e.message for e in validator.iter_errors(pack)]
    if pack_errors:
        errors.append(f"valid-jingle-pack entry does not validate against schemas/index.schema.json: {pack_errors}")

if errors:
    for line in errors:
        print(line)
    sys.exit(1)
print(
    "jingle-pack-kind index shape OK: kind/manifest/assets[] projected (sha256+bytes verified, sorted, "
    "count matches on-disk files), no card/family, entry validates against schemas/index.schema.json"
)
PY
    if python3 "$tmp_jingle_pack_index_check" "$tmp_jingle_pack_index" "$TMP_JINGLE_PACK_INDEX_TREE" "schemas/index.schema.json" "$TMP_SCHEMA_HELPERS_DIR"; then
        pass "build_index.py projects a jingle-pack entry's kind+manifest+assets[] (no card/family); entry schema-valid"
    else
        fail "build_index.py jingle-pack-kind projection assertions failed"
    fi
    rm -f "$tmp_jingle_pack_index_check"
else
    fail "skipped jingle-pack-kind projection assertions because build_index.py failed above"
fi
rm -f "$tmp_jingle_pack_index"
echo

echo "== build_index.py + schemas/index.schema.json: show kind projects manifest only — no card/assets/family/preview (SPEC F118.1, T253) =="
TMP_SHOW_INDEX_TREE="$(mktemp -d)"
mkdir -p "$TMP_SHOW_INDEX_TREE/entries/shows/valid-show"
cp "$SHOW_GREEN_FIXTURE/valid-show.show.json" "$TMP_SHOW_INDEX_TREE/entries/shows/valid-show/valid-show.show.json"
cp "$SHOW_GREEN_FIXTURE/valid-show.meta.json" "$TMP_SHOW_INDEX_TREE/entries/shows/valid-show/valid-show.meta.json"

tmp_show_index="$(mktemp)"
show_index_build_ok=1
if ! python3 tools/build_index.py --root "$TMP_SHOW_INDEX_TREE" --out "$tmp_show_index"; then
    fail "build_index.py exited non-zero building the show-kind fixture tree"
    show_index_build_ok=0
fi

if [[ $show_index_build_ok -eq 1 ]]; then
    tmp_show_index_check="$(mktemp)"
    cat >"$tmp_show_index_check" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[4])
from index_entry_schema import load_entry_validator

index_path, tree_root, schema_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
data = json.loads(index_path.read_text())
by_slug = {e["slug"]: e for e in data["entries"]}
validator = load_entry_validator(schema_path)

errors = []

show = by_slug.get("valid-show")
if show is None:
    errors.append("valid-show entry missing from built index")
else:
    if show.get("kind") != "show":
        errors.append(f"valid-show: expected kind 'show', got {show.get('kind')!r}")
    for absent_key in ("card", "assets", "family", "preview"):
        if absent_key in show:
            errors.append(f"valid-show: unexpected '{absent_key}' key on a show entry")
    manifest = show.get("manifest")
    if not isinstance(manifest, dict):
        errors.append("valid-show: missing 'manifest' key")
    else:
        path = manifest.get("path")
        if not isinstance(path, str) or not path.endswith("valid-show.show.json"):
            errors.append(f"valid-show.manifest.path unexpected: {path!r}")
        else:
            want = hashlib.sha256((tree_root / path).read_bytes()).hexdigest()
            got = manifest.get("sha256")
            if want != got:
                errors.append(f"valid-show.manifest.sha256 mismatch: recomputed {want}, index has {got}")
    show_errors = [e.message for e in validator.iter_errors(show)]
    if show_errors:
        errors.append(f"valid-show entry does not validate against schemas/index.schema.json: {show_errors}")

if errors:
    for line in errors:
        print(line)
    sys.exit(1)
print(
    "show-kind index shape OK: kind/manifest projected (sha256 verified), no card/assets/family/"
    "preview, entry validates against schemas/index.schema.json"
)
PY
    if python3 "$tmp_show_index_check" "$tmp_show_index" "$TMP_SHOW_INDEX_TREE" "schemas/index.schema.json" "$TMP_SCHEMA_HELPERS_DIR"; then
        pass "build_index.py projects a show entry's kind+manifest only (no card/assets/family/preview); entry schema-valid"
    else
        fail "build_index.py show-kind projection assertions failed"
    fi
    rm -f "$tmp_show_index_check"
else
    fail "skipped show-kind projection assertions because build_index.py failed above"
fi
rm -f "$tmp_show_index"
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

card = json.loads((Path(sys.argv[1]) / "entries/personas/heavy-card/heavy-card.persona.json").read_text(encoding="utf-8"))
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

echo "== lint.py: show budget lint (SPEC F115.1/F118.4 · T253) =="

echo "-- red oversize-show-flavor: flavor at EXACTLY 2x its SPEC F115.1 budget (800 chars) HARD-fails; name/tagline stay within budget (F118.4's WARN>1x/HARD>=2x posture, inclusive at the 2x boundary) --"
check_red_lint oversize-show-flavor "show-flavor-budget"

echo "-- warn heavy-show: name/tagline/flavor each land in the 1x..2x band -> WARN once each, exit 0, never HARD (SPEC F118.4 · T253) --"
output=$(python3 tools/lint.py --root "$HEAVY_SHOW_DIR" 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "heavy-show lint.py exits 0"
else
    fail "heavy-show lint.py exited $status, expected 0"
fi
for expect in "show-name-budget" "show-tagline-budget" "show-flavor-budget"; do
    if grep -qF "$expect" <<<"$output"; then
        pass "heavy-show lint.py warns naming '$expect'"
    else
        fail "heavy-show lint.py did not warn naming '$expect'"
    fi
done
# Mirrors the heavy-card "(7 warnings)" total-count precedent above: pinning
# the summary line's total to exactly 3 — combined with the 3 distinct rule
# ids each already confirmed present — is what actually proves each fires
# exactly once.
if grep -qF "(3 warnings)" <<<"$output"; then
    pass "heavy-show lint.py reports exactly 3 warnings total (each show budget rule fires exactly once)"
else
    fail "heavy-show lint.py did not report exactly 3 total warnings"
fi
echo

echo "== lint.py: show-rotation-bounds (SPEC F152.1/F152.6, PLAN T364) =="

echo "-- red show-rotation-no-bound: envelope.rotation present but sets neither maxPlays nor notAiredWithinDays --"
check_red_lint show-rotation-no-bound "show-rotation-bounds: envelope.rotation sets neither maxPlays nor notAiredWithinDays"

echo "-- red show-rotation-bad-days: notAiredWithinDays is 0, one below the inclusive 1..3650 range --"
check_red_lint show-rotation-bad-days "show-rotation-bounds: envelope.rotation.notAiredWithinDays is 0, must be between 1 and 3650"

echo "-- green valid-show-with-rotation: a schema-valid manifest carrying envelope.rotation.maxPlays=0 validates clean and lints clean (schema 1.1) --"
TMP_SHOW_ROTATION_TREE="$(mktemp -d)"
mkdir -p "$TMP_SHOW_ROTATION_TREE/entries/shows/valid-show-with-rotation"
cp "$SHOW_ROTATION_GREEN_FIXTURE/valid-show-with-rotation.show.json" \
    "$TMP_SHOW_ROTATION_TREE/entries/shows/valid-show-with-rotation/valid-show-with-rotation.show.json"
cp "$SHOW_ROTATION_GREEN_FIXTURE/valid-show-with-rotation.meta.json" \
    "$TMP_SHOW_ROTATION_TREE/entries/shows/valid-show-with-rotation/valid-show-with-rotation.meta.json"
output=$(python3 tools/validate.py --root "$TMP_SHOW_ROTATION_TREE" 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "green valid-show-with-rotation fixture validates clean (schemas/show-manifest.schema.json envelope.rotation shape)"
else
    fail "green valid-show-with-rotation fixture did not validate clean (expected exit 0, got $status)"
fi
output=$(python3 tools/lint.py --root "$TMP_SHOW_ROTATION_TREE" 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "green valid-show-with-rotation fixture lints clean"
else
    fail "green valid-show-with-rotation fixture did not lint clean (expected exit 0, got $status)"
fi
if grep -qF "show-rotation-bounds" <<<"$output"; then
    fail "green valid-show-with-rotation fixture unexpectedly triggered show-rotation-bounds"
else
    pass "green valid-show-with-rotation fixture triggers no show-rotation-bounds finding"
fi
echo

echo "== validate.py + lint.py: envelope.rotation JSON null tolerance (SPEC F152.1/F152.3/F152.6, PLAN T364 review MED-1) =="

echo "-- green valid-show-with-null-bound: SPEC F152.3's own documented payload (maxPlays set, notAiredWithinDays explicit null) validates and lints clean --"
TMP_SHOW_ROTATION_NULL_BOUND_TREE="$(mktemp -d)"
mkdir -p "$TMP_SHOW_ROTATION_NULL_BOUND_TREE/entries/shows/valid-show-with-null-bound"
cp "$SHOW_ROTATION_NULL_BOUND_GREEN_FIXTURE/valid-show-with-null-bound.show.json" \
    "$TMP_SHOW_ROTATION_NULL_BOUND_TREE/entries/shows/valid-show-with-null-bound/valid-show-with-null-bound.show.json"
cp "$SHOW_ROTATION_NULL_BOUND_GREEN_FIXTURE/valid-show-with-null-bound.meta.json" \
    "$TMP_SHOW_ROTATION_NULL_BOUND_TREE/entries/shows/valid-show-with-null-bound/valid-show-with-null-bound.meta.json"
output=$(python3 tools/validate.py --root "$TMP_SHOW_ROTATION_NULL_BOUND_TREE" 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "green valid-show-with-null-bound fixture validates clean (SPEC F152.3 payload)"
else
    fail "green valid-show-with-null-bound fixture did not validate clean (expected exit 0, got $status)"
fi
output=$(python3 tools/lint.py --root "$TMP_SHOW_ROTATION_NULL_BOUND_TREE" 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "green valid-show-with-null-bound fixture lints clean"
else
    fail "green valid-show-with-null-bound fixture did not lint clean (expected exit 0, got $status)"
fi
echo

echo "-- green valid-show-with-null-rotation: an explicit envelope.rotation: null validates and lints clean — exercises load_show_rotation's ROTATION_ABSENT-on-explicit-null branch, not just the missing-key case --"
TMP_SHOW_ROTATION_NULL_ROTATION_TREE="$(mktemp -d)"
mkdir -p "$TMP_SHOW_ROTATION_NULL_ROTATION_TREE/entries/shows/valid-show-with-null-rotation"
cp "$SHOW_ROTATION_NULL_ROTATION_GREEN_FIXTURE/valid-show-with-null-rotation.show.json" \
    "$TMP_SHOW_ROTATION_NULL_ROTATION_TREE/entries/shows/valid-show-with-null-rotation/valid-show-with-null-rotation.show.json"
cp "$SHOW_ROTATION_NULL_ROTATION_GREEN_FIXTURE/valid-show-with-null-rotation.meta.json" \
    "$TMP_SHOW_ROTATION_NULL_ROTATION_TREE/entries/shows/valid-show-with-null-rotation/valid-show-with-null-rotation.meta.json"
output=$(python3 tools/validate.py --root "$TMP_SHOW_ROTATION_NULL_ROTATION_TREE" 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "green valid-show-with-null-rotation fixture validates clean (rotation: [\"object\",\"null\"])"
else
    fail "green valid-show-with-null-rotation fixture did not validate clean (expected exit 0, got $status)"
fi
output=$(python3 tools/lint.py --root "$TMP_SHOW_ROTATION_NULL_ROTATION_TREE" 2>&1)
status=$?
echo "$output"
if [[ $status -eq 0 ]]; then
    pass "green valid-show-with-null-rotation fixture lints clean"
else
    fail "green valid-show-with-null-rotation fixture did not lint clean (expected exit 0, got $status)"
fi
if grep -qF "show-rotation-bounds" <<<"$output"; then
    fail "green valid-show-with-null-rotation fixture unexpectedly triggered show-rotation-bounds (ROTATION_ABSENT branch not reached for explicit null)"
else
    pass "green valid-show-with-null-rotation fixture triggers no show-rotation-bounds finding (ROTATION_ABSENT reached for explicit null)"
fi
echo

echo "-- red show-rotation-maxplays-overflow: maxPlays one past Int32.MaxValue (2147483648) fails BOTH the schema's own maximum and lint's show-rotation-bounds (PLAN T364 review MED-2) --"
check_red_variant show-rotation-maxplays-overflow "2147483648 is greater than the maximum of 2147483647"
check_red_lint show-rotation-maxplays-overflow "show-rotation-bounds: envelope.rotation.maxPlays is 2147483648, must be between 0 and 2147483647"

echo "== lint.py: symlinked entries are never read, even when their target would otherwise warn (SPEC F89.6 guard · mutant M15) =="
TMP_SYMLINK_TREE="$(mktemp -d)"
mkdir -p "$TMP_SYMLINK_TREE/entries/personas/good-entry" "$TMP_SYMLINK_TREE/real/symlinked-heavy"
cp "$GREEN_FIXTURE/valid-dj.persona.json" "$TMP_SYMLINK_TREE/entries/personas/good-entry/good-entry.persona.json"
cp "$GREEN_FIXTURE/valid-dj.meta.json" "$TMP_SYMLINK_TREE/entries/personas/good-entry/good-entry.meta.json"
# The symlink target is a COPY of heavy-card's entry (not valid-dj) — a
# guard-less lint would emit warnings naming this slug, so a missing guard
# is actually observable here rather than indistinguishable from a clean run.
cp "$HEAVY_CARD_DIR/entries/personas/heavy-card/heavy-card.persona.json" "$TMP_SYMLINK_TREE/real/symlinked-heavy/symlinked-heavy.persona.json"
cp "$HEAVY_CARD_DIR/entries/personas/heavy-card/heavy-card.meta.json" "$TMP_SYMLINK_TREE/real/symlinked-heavy/symlinked-heavy.meta.json"
ln -s "$TMP_SYMLINK_TREE/real/symlinked-heavy" "$TMP_SYMLINK_TREE/entries/personas/symlinked-heavy"

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
mkdir -p "$TMP_GREEN_TREE/entries/personas/valid-dj" "$TMP_GREEN_TREE/entries/personas/aardvark-dj" "$TMP_GREEN_TREE/entries/personas/example-dj"
cp "$GREEN_FIXTURE/valid-dj.persona.json" "$TMP_GREEN_TREE/entries/personas/valid-dj/valid-dj.persona.json"
cp "$GREEN_FIXTURE/valid-dj.meta.json" "$TMP_GREEN_TREE/entries/personas/valid-dj/valid-dj.meta.json"
# A second copy under a slug that sorts before valid-dj, so the sorted-slugs
# assertion below exercises a real reorder rather than a single-item no-op.
cp "$GREEN_FIXTURE/valid-dj.persona.json" "$TMP_GREEN_TREE/entries/personas/aardvark-dj/aardvark-dj.persona.json"
cp "$GREEN_FIXTURE/valid-dj.meta.json" "$TMP_GREEN_TREE/entries/personas/aardvark-dj/aardvark-dj.meta.json"
cp entries/personas/example-dj/example-dj.persona.json "$TMP_GREEN_TREE/entries/personas/example-dj/example-dj.persona.json"
cp entries/personas/example-dj/example-dj.meta.json "$TMP_GREEN_TREE/entries/personas/example-dj/example-dj.meta.json"

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
# entries/<kind-folder>/<slug>/*.meta.json — so unlike the red/green fixtures
# above (which are entries/ trees fed through validate.py or build_index.py),
# the checks below either (a) build a small mixed persona+theme entries/ tree
# and inspect build_index.py's output shape, or (b) hand-author a bare index
# entry object (tools/testdata/red/bad-kind-*/index-entry.json — deliberately
# NOT an entries/ tree, since build_index.py itself can only ever emit
# kind "persona" or "theme": it derives kind from which manifest filename is
# present, so a bogus kind value can only arise from a hand-crafted
# index.json, never from a real build) and schema-validate it directly
# against schemas/index.schema.json's entry definition via the jsonschema
# library, the same way the pronunciations[] schema check above does.
TMP_KIND_TREE="$(mktemp -d)"
mkdir -p "$TMP_KIND_TREE/entries/personas/valid-dj" "$TMP_KIND_TREE/entries/themes/valid-theme"
cp "$GREEN_FIXTURE/valid-dj.persona.json" "$TMP_KIND_TREE/entries/personas/valid-dj/valid-dj.persona.json"
cp "$GREEN_FIXTURE/valid-dj.meta.json" "$TMP_KIND_TREE/entries/personas/valid-dj/valid-dj.meta.json"
cp "$KIND_GREEN_FIXTURE/valid-theme.theme.json" "$TMP_KIND_TREE/entries/themes/valid-theme/valid-theme.theme.json"
cp "$KIND_GREEN_FIXTURE/valid-theme.meta.json" "$TMP_KIND_TREE/entries/themes/valid-theme/valid-theme.meta.json"

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
# Embed the sha256/swatchSet/hexColor definitions directly into the entry
# subschema so its "#/definitions/..." $refs self-resolve without needing a
# resolver rooted at the full document. swatchSet/hexColor back the T191
# "preview" property added to the entry schema (mirrors theme-meta.schema.json's
# own swatchSet contract) — omitting them here would make this embedded
# subschema (not the real one tools/validate.py loads whole) throw
# PointerToNowhere the moment a theme entry carrying "preview" is validated.
entry_schema = dict(schema["definitions"]["entry"])
entry_schema["definitions"] = {
    "sha256": schema["definitions"]["sha256"],
    "swatchSet": schema["definitions"]["swatchSet"],
    "hexColor": schema["definitions"]["hexColor"],
}
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
    if "preview" in persona:
        errors.append("valid-dj: unexpected 'preview' key on a persona entry (T191 projection is theme-only)")
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
    # T191 scope note: build_index.py must project meta.json's "preview" into
    # the index entry (the "bestFor" precedent) — without it every real theme
    # card renders zero shelf chips (T185's contract). Compared against the
    # SAME meta.json build_index.py itself just read, not a hardcoded literal,
    # so a future edit to the fixture can't silently desync this assertion.
    meta_path = tree_root / "entries" / "themes" / "valid-theme" / "valid-theme.meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if theme.get("preview") != meta.get("preview"):
        errors.append(
            f"valid-theme: index 'preview' {theme.get('preview')!r} does not match "
            f"{meta_path}'s own 'preview' {meta.get('preview')!r} — build_index.py did not project it"
        )
    theme_errors = [e.message for e in validator.iter_errors(theme)]
    if theme_errors:
        errors.append(f"valid-theme entry does not validate against schemas/index.schema.json: {theme_errors}")

if errors:
    for line in errors:
        print(line)
    sys.exit(1)
print(
    "kind-aware index shape OK: persona entry unchanged (card, no kind/manifest/preview key), "
    "theme entry carries kind:\"theme\" + manifest + preview (sha256 verified, preview matches "
    "meta.json), both entries validate against schemas/index.schema.json"
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

echo "== build_index.py + schemas/index.schema.json: font kind projects assets[]/family (SPEC F104.1, T196) =="
# Mirrors the persona+theme kind-discriminator check above, font-shaped: a
# small entries/ tree (the FONT_GREEN_FIXTURE's own font/meta/asset files)
# fed through build_index.py, then the built entry's assets[]/family/byte
# totals are checked against the SAME on-disk files build_index.py itself
# just read — not hardcoded numbers — plus a schema-validity check against
# schemas/index.schema.json's font branch (T196 obligation 6).
TMP_FONT_INDEX_TREE="$(mktemp -d)"
mkdir -p "$TMP_FONT_INDEX_TREE/entries/fonts/valid-font"
cp "$FONT_GREEN_FIXTURE/valid-font.font.json" "$TMP_FONT_INDEX_TREE/entries/fonts/valid-font/valid-font.font.json"
cp "$FONT_GREEN_FIXTURE/valid-font.meta.json" "$TMP_FONT_INDEX_TREE/entries/fonts/valid-font/valid-font.meta.json"
cp "$FONT_GREEN_FIXTURE/valid-font-variable-latin.woff2" "$TMP_FONT_INDEX_TREE/entries/fonts/valid-font/valid-font-variable-latin.woff2"
cp "$FONT_GREEN_FIXTURE/OFL.txt" "$TMP_FONT_INDEX_TREE/entries/fonts/valid-font/OFL.txt"

tmp_font_index="$(mktemp)"
font_index_build_ok=1
if ! python3 tools/build_index.py --root "$TMP_FONT_INDEX_TREE" --out "$tmp_font_index"; then
    fail "build_index.py exited non-zero building the font-kind fixture tree"
    font_index_build_ok=0
fi

if [[ $font_index_build_ok -eq 1 ]]; then
    tmp_font_index_check="$(mktemp)"
    cat >"$tmp_font_index_check" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[4])
from index_entry_schema import load_entry_validator

index_path, tree_root, schema_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
data = json.loads(index_path.read_text())
by_slug = {e["slug"]: e for e in data["entries"]}
validator = load_entry_validator(schema_path)

errors = []

font = by_slug.get("valid-font")
if font is None:
    errors.append("valid-font entry missing from built index")
else:
    if font.get("kind") != "font":
        errors.append(f"valid-font: expected kind 'font', got {font.get('kind')!r}")
    manifest = font.get("manifest")
    if not isinstance(manifest, dict) or not str(manifest.get("path", "")).endswith("valid-font.font.json"):
        errors.append(f"valid-font: manifest missing/unexpected: {manifest!r}")

    # family: projected straight off the manifest build_index.py itself just
    # read, not a hardcoded literal (mirrors the theme "preview" precedent
    # above) — so a future edit to the fixture can't silently desync this.
    manifest_data = json.loads((tree_root / "entries/fonts/valid-font/valid-font.font.json").read_text(encoding="utf-8"))
    if font.get("family") != manifest_data.get("family"):
        errors.append(
            f"valid-font: index 'family' {font.get('family')!r} does not match the manifest's own "
            f"'family' {manifest_data.get('family')!r} — build_index.py did not project it"
        )

    # assets[]: every sibling file in the entry directory other than the
    # manifest/meta themselves — the same font_asset_paths selection
    # build_index.py itself uses (tools/catalog_lib.py) — recomputed here
    # independently rather than assumed.
    entry_dir = tree_root / "entries" / "fonts" / "valid-font"
    on_disk = sorted(
        p for p in entry_dir.iterdir()
        if p.is_file() and p.name not in ("valid-font.font.json", "valid-font.meta.json")
    )
    assets = font.get("assets")
    if not isinstance(assets, list) or len(assets) != len(on_disk):
        got_len = len(assets) if isinstance(assets, list) else "n/a"
        errors.append(f"valid-font: assets[] length {got_len} does not match on-disk asset count {len(on_disk)}")
    else:
        asset_paths = [a.get("path") for a in assets]
        if asset_paths != sorted(asset_paths):
            errors.append(f"valid-font: assets[] paths not sorted: {asset_paths}")

        recomputed_total = 0
        declared_total = 0
        for asset, disk_path in zip(assets, on_disk):
            want_sha = hashlib.sha256(disk_path.read_bytes()).hexdigest()
            want_bytes = disk_path.stat().st_size
            got_sha = asset.get("sha256")
            got_bytes = asset.get("bytes")
            if want_sha != got_sha:
                errors.append(f"valid-font: {disk_path.name} sha256 mismatch: recomputed {want_sha}, index has {got_sha}")
            if want_bytes != got_bytes:
                errors.append(f"valid-font: {disk_path.name} bytes mismatch: recomputed {want_bytes}, index has {got_bytes}")
            recomputed_total += want_bytes
            declared_total += got_bytes if isinstance(got_bytes, int) else 0
        # T196 obligation 6: the SUMMED assets[] byte total must match an
        # independently-recomputed on-disk byte total for the same tree —
        # not merely each individual asset matching its own on-disk file.
        if recomputed_total != declared_total:
            errors.append(
                f"valid-font: assets[] byte total {declared_total} does not match independently "
                f"recomputed on-disk byte total {recomputed_total}"
            )

    font_errors = [e.message for e in validator.iter_errors(font)]
    if font_errors:
        errors.append(f"valid-font entry does not validate against schemas/index.schema.json: {font_errors}")

if errors:
    for line in errors:
        print(line)
    sys.exit(1)
print(
    "font-kind index shape OK: kind/manifest/family projected, assets[] sorted with real sha256+bytes "
    "matching on-disk files, summed byte total matches independently-recomputed on-disk total, entry "
    "validates against schemas/index.schema.json"
)
PY
    if python3 "$tmp_font_index_check" "$tmp_font_index" "$TMP_FONT_INDEX_TREE" "schemas/index.schema.json" "$TMP_SCHEMA_HELPERS_DIR"; then
        pass "build_index.py projects a font entry's assets[]/family; summed byte total matches on-disk; entry schema-valid"
    else
        fail "build_index.py font-kind projection assertions failed"
    fi
    rm -f "$tmp_font_index_check"
else
    fail "skipped font-kind projection assertions because build_index.py failed above"
fi
rm -f "$tmp_font_index"
echo

echo "== build_index.py: a font manifest's declared files[].bytes never reaches assets[] (B1 review mutation probe) =="
# The check above (T196 obligation 6) recomputes its expectation from the
# SAME on-disk file the fixture's manifest happens to declare the identical
# byte count for — it alone can't distinguish "build_index.py projected
# stat().st_size" from "build_index.py projected the manifest's own
# files[].bytes" when the two numbers match by construction. This probes
# that gap directly: a synthetic pack whose manifest declares an
# app-rejecting 999999 bytes (comfortably over
# schemas/index.schema.json's own 262144-byte assetRef ceiling) for its one
# face, asserting the emitted index carries the REAL on-disk stat() size,
# never the manifest's hostile claim.
TMP_HOSTILE_BYTES_TREE="$(mktemp -d)"
mkdir -p "$TMP_HOSTILE_BYTES_TREE/entries/fonts/valid-font"
python3 - "$FONT_GREEN_FIXTURE/valid-font.font.json" "$TMP_HOSTILE_BYTES_TREE/entries/fonts/valid-font/valid-font.font.json" <<'PY'
import json
import sys
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
manifest = json.loads(src.read_text(encoding="utf-8"))
manifest["files"][0]["bytes"] = 999999  # app-rejecting: over the 262144-byte fetch-transport ceiling
dst.write_text(json.dumps(manifest), encoding="utf-8")
PY
cp "$FONT_GREEN_FIXTURE/valid-font.meta.json" "$TMP_HOSTILE_BYTES_TREE/entries/fonts/valid-font/valid-font.meta.json"
cp "$FONT_GREEN_FIXTURE/valid-font-variable-latin.woff2" "$TMP_HOSTILE_BYTES_TREE/entries/fonts/valid-font/valid-font-variable-latin.woff2"
cp "$FONT_GREEN_FIXTURE/OFL.txt" "$TMP_HOSTILE_BYTES_TREE/entries/fonts/valid-font/OFL.txt"

tmp_hostile_bytes_index="$(mktemp)"
if python3 tools/build_index.py --root "$TMP_HOSTILE_BYTES_TREE" --out "$tmp_hostile_bytes_index"; then
    tmp_hostile_bytes_check="$(mktemp)"
    cat >"$tmp_hostile_bytes_check" <<'PY'
import json
import sys
from pathlib import Path

index_path, tree_root = Path(sys.argv[1]), Path(sys.argv[2])
data = json.loads(index_path.read_text())
by_slug = {e["slug"]: e for e in data["entries"]}

errors = []
font = by_slug.get("valid-font")
if font is None:
    errors.append("valid-font entry missing from built index")
else:
    woff2_path = tree_root / "entries/fonts/valid-font/valid-font-variable-latin.woff2"
    real_bytes = woff2_path.stat().st_size
    declared_bytes = 999999

    asset = next(
        (a for a in font.get("assets", []) if str(a.get("path", "")).endswith("valid-font-variable-latin.woff2")),
        None,
    )
    if asset is None:
        errors.append("valid-font: woff2 asset missing from built assets[]")
    else:
        got = asset.get("bytes")
        if got == declared_bytes:
            errors.append(
                f"valid-font: assets[].bytes {got!r} came straight from the manifest's own hostile "
                "declared 999999, not stat()"
            )
        elif got != real_bytes:
            errors.append(f"valid-font: assets[].bytes {got!r} does not match on-disk stat() {real_bytes}")

if errors:
    for line in errors:
        print(line)
    sys.exit(1)
print("valid-font: assets[].bytes carries the on-disk truth, ignoring the manifest's hostile declared 999999")
PY
    if python3 "$tmp_hostile_bytes_check" "$tmp_hostile_bytes_index" "$TMP_HOSTILE_BYTES_TREE"; then
        pass "build_index.py's assets[] bytes carry on-disk truth, never a font manifest's hostile declared value"
    else
        fail "build_index.py's assets[] bytes did not carry on-disk truth against a hostile declared manifest value"
    fi
    rm -f "$tmp_hostile_bytes_check"
else
    fail "build_index.py exited non-zero building the hostile-declared-bytes fixture tree"
fi
rm -f "$tmp_hostile_bytes_index"
echo

echo "== build_index.py + schemas/index.schema.json: avatar kind projects assets[], no family (SPEC F128.1, T309) =="
TMP_AVATAR_INDEX_TREE="$(mktemp -d)"
mkdir -p "$TMP_AVATAR_INDEX_TREE/entries/avatars/valid-avatar"
cp "$AVATAR_GREEN_FIXTURE/valid-avatar.avatar.json" "$TMP_AVATAR_INDEX_TREE/entries/avatars/valid-avatar/valid-avatar.avatar.json"
cp "$AVATAR_GREEN_FIXTURE/valid-avatar.meta.json" "$TMP_AVATAR_INDEX_TREE/entries/avatars/valid-avatar/valid-avatar.meta.json"
cp "$AVATAR_GREEN_FIXTURE/warm-grin.png" "$TMP_AVATAR_INDEX_TREE/entries/avatars/valid-avatar/warm-grin.png"
cp "$AVATAR_GREEN_FIXTURE/cool-smirk.png" "$TMP_AVATAR_INDEX_TREE/entries/avatars/valid-avatar/cool-smirk.png"

tmp_avatar_index="$(mktemp)"
avatar_index_build_ok=1
if ! python3 tools/build_index.py --root "$TMP_AVATAR_INDEX_TREE" --out "$tmp_avatar_index"; then
    fail "build_index.py exited non-zero building the avatar-kind fixture tree"
    avatar_index_build_ok=0
fi

if [[ $avatar_index_build_ok -eq 1 ]]; then
    tmp_avatar_index_check="$(mktemp)"
    cat >"$tmp_avatar_index_check" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[4])
from index_entry_schema import load_entry_validator

index_path, tree_root, schema_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
data = json.loads(index_path.read_text())
by_slug = {e["slug"]: e for e in data["entries"]}
validator = load_entry_validator(schema_path)

errors = []

avatar = by_slug.get("valid-avatar")
if avatar is None:
    errors.append("valid-avatar entry missing from built index")
else:
    if avatar.get("kind") != "avatar":
        errors.append(f"valid-avatar: expected kind 'avatar', got {avatar.get('kind')!r}")
    if "family" in avatar:
        errors.append("valid-avatar: unexpected 'family' key on an avatar entry (no family equivalent, SPEC F128.1)")
    manifest = avatar.get("manifest")
    if not isinstance(manifest, dict) or not str(manifest.get("path", "")).endswith("valid-avatar.avatar.json"):
        errors.append(f"valid-avatar: manifest missing/unexpected: {manifest!r}")

    entry_dir = tree_root / "entries" / "avatars" / "valid-avatar"
    on_disk = sorted(
        p for p in entry_dir.iterdir()
        if p.is_file() and p.name not in ("valid-avatar.avatar.json", "valid-avatar.meta.json")
    )
    assets = avatar.get("assets")
    if not isinstance(assets, list) or len(assets) != len(on_disk):
        got_len = len(assets) if isinstance(assets, list) else "n/a"
        errors.append(f"valid-avatar: assets[] length {got_len} does not match on-disk PNG count {len(on_disk)}")
    else:
        asset_paths = [a.get("path") for a in assets]
        if asset_paths != sorted(asset_paths):
            errors.append(f"valid-avatar: assets[] paths not sorted: {asset_paths}")
        for asset, disk_path in zip(assets, on_disk):
            want_sha = hashlib.sha256(disk_path.read_bytes()).hexdigest()
            want_bytes = disk_path.stat().st_size
            if asset.get("sha256") != want_sha:
                errors.append(f"valid-avatar: {disk_path.name} sha256 mismatch: recomputed {want_sha}, index has {asset.get('sha256')}")
            if asset.get("bytes") != want_bytes:
                errors.append(f"valid-avatar: {disk_path.name} bytes mismatch: recomputed {want_bytes}, index has {asset.get('bytes')}")

    avatar_errors = [e.message for e in validator.iter_errors(avatar)]
    if avatar_errors:
        errors.append(f"valid-avatar entry does not validate against schemas/index.schema.json: {avatar_errors}")

if errors:
    for line in errors:
        print(line)
    sys.exit(1)
print(
    "avatar-kind index shape OK: kind/manifest/assets[] projected (sha256+bytes verified against on-disk "
    "PNGs, sorted), no family key, entry validates against schemas/index.schema.json"
)
PY
    if python3 "$tmp_avatar_index_check" "$tmp_avatar_index" "$TMP_AVATAR_INDEX_TREE" "schemas/index.schema.json" "$TMP_SCHEMA_HELPERS_DIR"; then
        pass "build_index.py projects an avatar entry's kind/manifest/assets[] (no family); entry schema-valid"
    else
        fail "build_index.py avatar-kind projection assertions failed"
    fi
    rm -f "$tmp_avatar_index_check"
else
    fail "skipped avatar-kind projection assertions because build_index.py failed above"
fi
rm -f "$tmp_avatar_index"
echo

echo "== build_index.py + schemas/index.schema.json: icon kind projects manifest only — no card/assets/family/preview (SPEC F130.6, T309) =="
TMP_ICON_INDEX_TREE="$(mktemp -d)"
mkdir -p "$TMP_ICON_INDEX_TREE/entries/icons/valid-icon"
cp "$ICON_GREEN_FIXTURE/valid-icon.icon.json" "$TMP_ICON_INDEX_TREE/entries/icons/valid-icon/valid-icon.icon.json"
cp "$ICON_GREEN_FIXTURE/valid-icon.meta.json" "$TMP_ICON_INDEX_TREE/entries/icons/valid-icon/valid-icon.meta.json"

tmp_icon_index="$(mktemp)"
icon_index_build_ok=1
if ! python3 tools/build_index.py --root "$TMP_ICON_INDEX_TREE" --out "$tmp_icon_index"; then
    fail "build_index.py exited non-zero building the icon-kind fixture tree"
    icon_index_build_ok=0
fi

if [[ $icon_index_build_ok -eq 1 ]]; then
    tmp_icon_index_check="$(mktemp)"
    cat >"$tmp_icon_index_check" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[4])
from index_entry_schema import load_entry_validator

index_path, tree_root, schema_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
data = json.loads(index_path.read_text())
by_slug = {e["slug"]: e for e in data["entries"]}
validator = load_entry_validator(schema_path)

errors = []

icon = by_slug.get("valid-icon")
if icon is None:
    errors.append("valid-icon entry missing from built index")
else:
    if icon.get("kind") != "icon":
        errors.append(f"valid-icon: expected kind 'icon', got {icon.get('kind')!r}")
    for absent_key in ("card", "assets", "family", "preview"):
        if absent_key in icon:
            errors.append(f"valid-icon: unexpected '{absent_key}' key on an icon entry")
    manifest = icon.get("manifest")
    if not isinstance(manifest, dict):
        errors.append("valid-icon: missing 'manifest' key")
    else:
        path = manifest.get("path")
        if not isinstance(path, str) or not path.endswith("valid-icon.icon.json"):
            errors.append(f"valid-icon.manifest.path unexpected: {path!r}")
        else:
            want = hashlib.sha256((tree_root / path).read_bytes()).hexdigest()
            got = manifest.get("sha256")
            if want != got:
                errors.append(f"valid-icon.manifest.sha256 mismatch: recomputed {want}, index has {got}")
    icon_errors = [e.message for e in validator.iter_errors(icon)]
    if icon_errors:
        errors.append(f"valid-icon entry does not validate against schemas/index.schema.json: {icon_errors}")

if errors:
    for line in errors:
        print(line)
    sys.exit(1)
print(
    "icon-kind index shape OK: kind/manifest projected (sha256 verified), no card/assets/family/preview, "
    "entry validates against schemas/index.schema.json"
)
PY
    if python3 "$tmp_icon_index_check" "$tmp_icon_index" "$TMP_ICON_INDEX_TREE" "schemas/index.schema.json" "$TMP_SCHEMA_HELPERS_DIR"; then
        pass "build_index.py projects an icon entry's kind+manifest only (no card/assets/family/preview); entry schema-valid"
    else
        fail "build_index.py icon-kind projection assertions failed"
    fi
    rm -f "$tmp_icon_index_check"
else
    fail "skipped icon-kind projection assertions because build_index.py failed above"
fi
rm -f "$tmp_icon_index"
echo

echo "== build_index.py + schemas/index.schema.json: a persona entry's own optional avatar sidecar projects a single-element assets[] (SPEC F128.2, T309) =="
TMP_PERSONA_AVATAR_INDEX_TREE="$(mktemp -d)"
mkdir -p "$TMP_PERSONA_AVATAR_INDEX_TREE/entries/personas/valid-dj-with-avatar" "$TMP_PERSONA_AVATAR_INDEX_TREE/entries/personas/valid-dj"
cp "$PERSONA_AVATAR_GREEN_FIXTURE"/*.persona.json "$PERSONA_AVATAR_GREEN_FIXTURE"/*.meta.json "$PERSONA_AVATAR_GREEN_FIXTURE"/*.avatar.png "$TMP_PERSONA_AVATAR_INDEX_TREE/entries/personas/valid-dj-with-avatar/"
# A SECOND, faceless persona sits alongside it — proves the assets[] key is
# per-entry (only the one carrying a sidecar gets it), not a build-wide flag.
cp "$GREEN_FIXTURE/valid-dj.persona.json" "$GREEN_FIXTURE/valid-dj.meta.json" "$TMP_PERSONA_AVATAR_INDEX_TREE/entries/personas/valid-dj/"

tmp_persona_avatar_index="$(mktemp)"
persona_avatar_index_build_ok=1
if ! python3 tools/build_index.py --root "$TMP_PERSONA_AVATAR_INDEX_TREE" --out "$tmp_persona_avatar_index"; then
    fail "build_index.py exited non-zero building the persona-avatar-sidecar fixture tree"
    persona_avatar_index_build_ok=0
fi

if [[ $persona_avatar_index_build_ok -eq 1 ]]; then
    tmp_persona_avatar_index_check="$(mktemp)"
    cat >"$tmp_persona_avatar_index_check" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[4])
from index_entry_schema import load_entry_validator

index_path, tree_root, schema_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
data = json.loads(index_path.read_text())
by_slug = {e["slug"]: e for e in data["entries"]}
validator = load_entry_validator(schema_path)

errors = []

faced = by_slug.get("valid-dj-with-avatar")
if faced is None:
    errors.append("valid-dj-with-avatar entry missing from built index")
else:
    if "kind" in faced:
        errors.append(f"valid-dj-with-avatar: unexpected 'kind' key on a persona entry: {faced['kind']!r}")
    assets = faced.get("assets")
    if not isinstance(assets, list) or len(assets) != 1:
        errors.append(f"valid-dj-with-avatar: expected a single-element assets[], got {assets!r}")
    else:
        asset = assets[0]
        png_path = tree_root / "entries/personas/valid-dj-with-avatar/valid-dj-with-avatar.avatar.png"
        want_sha = hashlib.sha256(png_path.read_bytes()).hexdigest()
        want_bytes = png_path.stat().st_size
        if asset.get("sha256") != want_sha:
            errors.append(f"valid-dj-with-avatar: sha256 mismatch: recomputed {want_sha}, index has {asset.get('sha256')}")
        if asset.get("bytes") != want_bytes:
            errors.append(f"valid-dj-with-avatar: bytes mismatch: recomputed {want_bytes}, index has {asset.get('bytes')}")
        if asset.get("path") != "entries/personas/valid-dj-with-avatar/valid-dj-with-avatar.avatar.png":
            errors.append(f"valid-dj-with-avatar: unexpected asset path {asset.get('path')!r}")
    faced_errors = [e.message for e in validator.iter_errors(faced)]
    if faced_errors:
        errors.append(f"valid-dj-with-avatar entry does not validate against schemas/index.schema.json: {faced_errors}")

faceless = by_slug.get("valid-dj")
if faceless is None:
    errors.append("valid-dj (faceless) entry missing from built index")
elif "assets" in faceless:
    errors.append("valid-dj: unexpected 'assets' key on a persona entry with no sidecar face")

if errors:
    for line in errors:
        print(line)
    sys.exit(1)
print(
    "persona-avatar-sidecar index shape OK: the faced persona projects a single-element assets[] "
    "(sha256+bytes verified), the faceless one carries no assets key at all, both schema-valid"
)
PY
    if python3 "$tmp_persona_avatar_index_check" "$tmp_persona_avatar_index" "$TMP_PERSONA_AVATAR_INDEX_TREE" "schemas/index.schema.json" "$TMP_SCHEMA_HELPERS_DIR"; then
        pass "build_index.py projects a persona's own optional avatar-sidecar assets[]; faceless entries stay unchanged"
    else
        fail "build_index.py persona-avatar-sidecar projection assertions failed"
    fi
    rm -f "$tmp_persona_avatar_index_check"
else
    fail "skipped persona-avatar-sidecar projection assertions because build_index.py failed above"
fi
rm -f "$tmp_persona_avatar_index"
echo

echo "== validate.py: index.json slug-ownership cross-check (T196 obligation 3, SPEC F104.1 — reviewer probe 8) =="
echo "-- red font-asset-slug-mismatch: an asset path under ANOTHER entry's slug directory is rejected, naming the offense --"
# validate_index only ever runs against the real repo root (see validate.py's
# main(): gated on `root == REPO_ROOT`), so this calls validate_index
# directly rather than through the --root CLI flag — the same posture
# check_kind_entry_red/green already take for schema-only checks, just one
# layer up (the real Python function, not just the schema it also enforces).
tmp_slug_ownership_check="$(mktemp)"
cat >"$tmp_slug_ownership_check" <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, "tools")
import validate

index_path = Path(sys.argv[1])
violations = validate.validate_index(index_path)
if not violations:
    print(f"{index_path}: expected validate_index to reject it, but it passed")
    sys.exit(1)
if not any("slug-ownership" in v and "some-other-slug" in v for v in violations):
    print(f"{index_path}: violations did not name the slug-ownership offense: {violations}")
    sys.exit(1)
for v in violations:
    print(v)
print(f"{index_path}: validate_index correctly rejected the cross-slug asset path")
PY
if python3 "$tmp_slug_ownership_check" "tools/testdata/red/font-asset-slug-mismatch/index.json"; then
    pass "validate_index rejects an asset path under another entry's slug directory (slug-ownership)"
else
    fail "validate_index did not reject an asset path under another entry's slug directory (slug-ownership)"
fi
rm -f "$tmp_slug_ownership_check"
echo

echo "-- red persona-avatar-sibling-face: a persona's own avatar sidecar assets[0] resolves under ITS OWN directory prefix but names a SIBLING persona's face file — schemas/index.schema.json's own path pattern is shape-only (F3, T309), so only this Python-side filename==slug check catches it --"
# schemas/index.schema.json's assetRef.path pattern used to pin filename==
# directory-slug equality with a Python-only named-group backreference that
# failed to COMPILE under ECMA-262/.NET (F3) — removed in favour of a
# shape-only, portable pattern, with the equality check moved here. This
# fixture's own path resolves under its own owned_prefix (so the PREFIX
# check above would pass it clean) — proving the new filename==slug check,
# not the prefix check, is what actually rejects it.
tmp_slug_ownership_sidecar_check="$(mktemp)"
cat >"$tmp_slug_ownership_sidecar_check" <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, "tools")
import validate

index_path = Path(sys.argv[1])
violations = validate.validate_index(index_path)
if not violations:
    print(f"{index_path}: expected validate_index to reject it, but it passed")
    sys.exit(1)
if not any("slug-ownership" in v and "some-other-persona" in v for v in violations):
    print(f"{index_path}: violations did not name the sibling-face offense: {violations}")
    sys.exit(1)
for v in violations:
    print(v)
print(f"{index_path}: validate_index correctly rejected the sibling persona's avatar sidecar filename")
PY
if python3 "$tmp_slug_ownership_sidecar_check" "tools/testdata/red/persona-avatar-sibling-face/index.json"; then
    pass "validate_index rejects a persona avatar sidecar naming a sibling's face file (slug-ownership)"
else
    fail "validate_index did not reject a persona avatar sidecar naming a sibling's face file (slug-ownership)"
fi
rm -f "$tmp_slug_ownership_sidecar_check"
echo

echo "-- green: the real repo's own committed index.json passes the slug-ownership cross-check (every real entry is self-consistent) --"
tmp_slug_ownership_green_check="$(mktemp)"
cat >"$tmp_slug_ownership_green_check" <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, "tools")
import validate

index_path = Path("index.json")
violations = validate.validate_index_slug_ownership(index_path, __import__("json").loads(index_path.read_text()))
if violations:
    for v in violations:
        print(v)
    sys.exit(1)
print("index.json: every entry's card/manifest/meta/assets path resolves under its own slug")
PY
if python3 "$tmp_slug_ownership_green_check"; then
    pass "the real repo's committed index.json passes the slug-ownership cross-check"
else
    fail "the real repo's committed index.json failed the slug-ownership cross-check"
fi
rm -f "$tmp_slug_ownership_green_check"
echo

echo "== validate.py: index.json duplicate-asset-path cross-check (T196 review M2) =="
echo "-- red font-duplicate-asset-path: two assets sharing a path with DIFFERENT sha256/bytes pass the schema's uniqueItems (full-object only) but are rejected by validate_index --"
# schemas/index.schema.json's uniqueItems on assets[] is full-object
# uniqueness (path/sha256/bytes all equal) — a same-path/different-sha pair
# is schema-valid (confirmed: this fixture carries no other violation), so
# this proves validate_index itself (schema + both Python cross-checks) is
# what actually rejects it, not merely the standalone function.
tmp_dup_asset_path_check="$(mktemp)"
cat >"$tmp_dup_asset_path_check" <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, "tools")
import validate

index_path = Path(sys.argv[1])
violations = validate.validate_index(index_path)
if not violations:
    print(f"{index_path}: expected validate_index to reject it, but it passed")
    sys.exit(1)
if not any("duplicate-asset-path" in v for v in violations):
    print(f"{index_path}: violations did not name the duplicate-asset-path offense: {violations}")
    sys.exit(1)
for v in violations:
    print(v)
print(f"{index_path}: validate_index correctly rejected the same-path/different-sha256 asset pair")
PY
if python3 "$tmp_dup_asset_path_check" "tools/testdata/red/font-duplicate-asset-path/index.json"; then
    pass "validate_index rejects two assets sharing a path with different sha256/bytes (duplicate-asset-path)"
else
    fail "validate_index did not reject two assets sharing a path with different sha256/bytes (duplicate-asset-path)"
fi
rm -f "$tmp_dup_asset_path_check"
echo

echo "-- green: the real repo's own committed index.json carries no duplicate asset paths within any one entry --"
tmp_dup_asset_path_green_check="$(mktemp)"
cat >"$tmp_dup_asset_path_green_check" <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, "tools")
import validate

index_path = Path("index.json")
violations = validate.validate_index_duplicate_asset_paths(index_path, __import__("json").loads(index_path.read_text()))
if violations:
    for v in violations:
        print(v)
    sys.exit(1)
print("index.json: no entry's assets[] carries two assets with the same path")
PY
if python3 "$tmp_dup_asset_path_green_check"; then
    pass "the real repo's committed index.json carries no duplicate asset paths"
else
    fail "the real repo's committed index.json carries a duplicate asset path"
fi
rm -f "$tmp_dup_asset_path_green_check"
echo

echo "== validate.py: index.json asset-integrity cross-check (T411 — closes a gap that predates both new kinds) =="
echo "-- red preview-index-hash-mismatch: index.json declares a WRONG sha256 for a voice-pack preview asset — neither validate_index_slug_ownership nor validate_index_duplicate_asset_paths ever opens the file, so validate_index_asset_integrity is the actual gate --"
tmp_asset_integrity_check="$(mktemp)"
cat >"$tmp_asset_integrity_check" <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, "tools")
import validate

index_path = Path(sys.argv[1])
violations = validate.validate_index(index_path)
if not violations:
    print(f"{index_path}: expected validate_index to reject it, but it passed")
    sys.exit(1)
if not any("asset-hash-mismatch" in v for v in violations):
    print(f"{index_path}: violations did not name the asset-hash-mismatch offense: {violations}")
    sys.exit(1)
for v in violations:
    print(v)
print(f"{index_path}: validate_index correctly rejected the mismatched preview sha256")
PY
if python3 "$tmp_asset_integrity_check" "tools/testdata/red/preview-index-hash-mismatch/index.json"; then
    pass "validate_index rejects an index.json asset declaring a sha256 that doesn't match the real file (asset-hash-mismatch)"
else
    fail "validate_index did not reject an index.json asset declaring a mismatched sha256 (asset-hash-mismatch)"
fi
rm -f "$tmp_asset_integrity_check"
echo

echo "-- red asset-bytes-mismatch: index.json declares the CORRECT sha256 but a WRONG bytes count for a voice-pack preview asset (T411 review round 1 finding 5) — a bytes-only mutation of preview-index-hash-mismatch, proving validate_index_asset_integrity's bytes check fires independently of its sha256 check --"
tmp_asset_bytes_mismatch_check="$(mktemp)"
cat >"$tmp_asset_bytes_mismatch_check" <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, "tools")
import validate

index_path = Path(sys.argv[1])
violations = validate.validate_index(index_path)
if not violations:
    print(f"{index_path}: expected validate_index to reject it, but it passed")
    sys.exit(1)
if not any("asset-bytes-mismatch" in v for v in violations):
    print(f"{index_path}: violations did not name the asset-bytes-mismatch offense: {violations}")
    sys.exit(1)
for v in violations:
    print(v)
print(f"{index_path}: validate_index correctly rejected the mismatched preview bytes")
PY
if python3 "$tmp_asset_bytes_mismatch_check" "tools/testdata/red/asset-bytes-mismatch/index.json"; then
    pass "validate_index rejects an index.json asset declaring a bytes count that doesn't match the real file (asset-bytes-mismatch)"
else
    fail "validate_index did not reject an index.json asset declaring a mismatched bytes count (asset-bytes-mismatch)"
fi
rm -f "$tmp_asset_bytes_mismatch_check"
echo

echo "-- red index-asset-path-escape: an assets[] path with 20 ../ segments — deliberately more than any plausible checkout depth, since POSIX Path.resolve() clamps excess .. at the filesystem root rather than erroring, so this fixture reaches the real /etc/hostname on any machine or CI runner regardless of how deep the repo happens to be checked out (T411 review round 2 finding: a shallower 6-segment path used to resolve to a nonexistent file under the workspace, so the mutation below yielded no violation at all) (T411 review round 1 finding 2, security) — calls validate_index_asset_integrity DIRECTLY (not validate_index), bypassing failed_entry_indices entirely, so this fixture exercises the jail (asset_path.is_relative_to(root)) in isolation; a mutation that removes the jail line falls through to a real read of /etc/hostname and reports asset-hash-mismatch, naming that real file's leaked sha256 in the violation text, so this also proves the jail runs BEFORE any hash is disclosed --"
tmp_path_escape_check="$(mktemp)"
cat >"$tmp_path_escape_check" <<'PY'
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "tools")
import validate

index_path = Path(sys.argv[1])
index = json.loads(index_path.read_text())
violations = validate.validate_index_asset_integrity(index_path, index)
if not violations:
    print(f"{index_path}: expected validate_index_asset_integrity to reject it, but it passed")
    sys.exit(1)
if not any("asset-path-escapes-root" in v for v in violations):
    print(f"{index_path}: violations did not name the asset-path-escapes-root offense: {violations}")
    sys.exit(1)
if any(re.search(r"[0-9a-f]{64}", v) for v in violations):
    print(f"{index_path}: a violation disclosed a sha256-shaped hash — the read-oracle this fixture guards against: {violations}")
    sys.exit(1)
for v in violations:
    print(v)
print(f"{index_path}: validate_index_asset_integrity jailed the escaping path before reading or hashing it")
PY
if python3 "$tmp_path_escape_check" "tools/testdata/red/index-asset-path-escape/index.json"; then
    pass "validate_index_asset_integrity rejects a path that resolves outside the catalog root, discloses no hash (asset-path-escapes-root)"
else
    fail "validate_index_asset_integrity did not reject a path escaping the catalog root, or leaked a hash (asset-path-escapes-root)"
fi
rm -f "$tmp_path_escape_check"
echo

echo "-- green: the real repo's own committed index.json carries no stale sha256/bytes claims --"
tmp_asset_integrity_green_check="$(mktemp)"
cat >"$tmp_asset_integrity_green_check" <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, "tools")
import validate

index_path = Path("index.json")
violations = validate.validate_index_asset_integrity(index_path, __import__("json").loads(index_path.read_text()))
if violations:
    for v in violations:
        print(v)
    sys.exit(1)
print("index.json: every card/manifest/meta/assets[] sha256 and bytes claim matches the real file on disk")
PY
if python3 "$tmp_asset_integrity_green_check"; then
    pass "the real repo's committed index.json carries no stale sha256/bytes claims"
else
    fail "the real repo's committed index.json carries a stale sha256/bytes claim"
fi
rm -f "$tmp_asset_integrity_green_check"
echo

check_kind_entry_red() {
    local variant="$1" expect="$2"
    local output status
    output=$(python3 - "$TMP_SCHEMA_HELPERS_DIR" "$KIND_RED_DIR/$variant/index-entry.json" "$expect" <<'PY'
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from index_entry_schema import load_entry_validator

validator = load_entry_validator()

fixture_path, expect_substring = Path(sys.argv[2]), sys.argv[3]
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

check_kind_entry_green() {
    local variant="$1" fixture_dir="$2"
    local output status
    output=$(python3 - "$TMP_SCHEMA_HELPERS_DIR" "$fixture_dir/index-entry.json" <<'PY'
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from index_entry_schema import load_entry_validator

validator = load_entry_validator()

fixture_path = Path(sys.argv[2])
instance = json.loads(fixture_path.read_text(encoding="utf-8"))
errors = [e.message for e in validator.iter_errors(instance)]
if errors:
    print(f"{fixture_path}: expected schema validation to pass, but it did not: {errors}")
    sys.exit(1)
print(f"{fixture_path}: validates cleanly against schemas/index.schema.json")
PY
    )
    status=$?
    echo "$output"
    if [[ $status -eq 0 ]]; then
        pass "$variant: schemas/index.schema.json accepts it"
    else
        fail "$variant: schemas/index.schema.json did not accept it"
    fi
    echo
}

echo "== schemas/index.schema.json: kind discriminator rejects bad entries (SPEC F103.2 / T178) =="
check_kind_entry_red bad-kind-value "'villain' is not one of"
check_kind_entry_red bad-kind-theme-no-manifest "'manifest' is a required property"

echo "== schemas/index.schema.json: show kind admits manifest-only entries, rejects one missing it (SPEC F118.1, T253) =="
check_kind_entry_green valid-show-index-entry "tools/testdata/green/valid-show-index-entry"
check_kind_entry_red bad-kind-show-no-manifest "'manifest' is a required property"

echo "== schemas/index.schema.json: font kind admits assets[]/family, rejects malformed ones (SPEC F104.1, T195) =="
check_kind_entry_green valid-font-index-entry "tools/testdata/green/valid-font-index-entry"
check_kind_entry_red bad-kind-font-no-assets "'assets' is a required property"
check_kind_entry_red bad-font-family "'Bad<script>Family' does not match"

echo "== schemas/index.schema.json: numeric/length bounds actually reject over-bound values (SPEC F104.1, T195 review finding — these three bounds previously had zero red coverage) =="
check_kind_entry_red font-family-too-long "is too long"
check_kind_entry_red font-empty-assets "is too short"

echo "-- red font-asset-bytes-over-font-max: the font \`then\` branch's OWN narrower assets[].items.bytes ceiling (262144, GenWave.Host.Catalog.CatalogProxyService.MaxAssetBytes) rejects a value comfortably UNDER the shared assetRef's wider 524288 bound — proving the font-specific override, not the generic one, is what's catching it (rider fold 1, T309 review) --"
check_kind_entry_red font-asset-bytes-over-font-max "is greater than the maximum of 262144"

echo "== schemas/index.schema.json: kind/extension cross-dressing and kind-exclusive fields are rejected off their own kind (SPEC F103.2/F104.1, T195 review findings) =="

echo "-- kind/extension cross-dressing: a kind's manifest.path pattern rejects the OTHER kind's manifest extension --"
check_kind_entry_red theme-entry-font-manifest '\\.theme\\.json'
check_kind_entry_red font-entry-theme-manifest '\\.font\\.json'
check_kind_entry_red show-entry-theme-manifest '\\.show\\.json'

echo "-- kind-exclusive fields: a field scoped to one kind's then/else branch is rejected on any other kind (N7/N8, extended to show at T253) --"
check_kind_entry_red theme-entry-with-assets "should not be valid under {'required': ['assets']}"
check_kind_entry_red persona-entry-with-manifest "should not be valid under {'required': ['manifest']}"
check_kind_entry_red font-entry-with-preview "should not be valid under {'required': ['preview']}"
check_kind_entry_red show-entry-with-assets "should not be valid under {'required': ['assets']}"

echo "== schemas/index.schema.json: avatar kind admits assets[], rejects a malformed one; icon kind admits manifest-only entries (SPEC F128.1/F130.6, T309) =="
check_kind_entry_green valid-avatar-index-entry "tools/testdata/green/valid-avatar-index-entry"
check_kind_entry_red bad-kind-avatar-no-assets "'assets' is a required property"
check_kind_entry_green valid-icon-index-entry "tools/testdata/green/valid-icon-index-entry"
check_kind_entry_red bad-kind-icon-no-manifest "'manifest' is a required property"

echo "== schemas/index.schema.json: ad-pack kind admits manifest-only entries, rejects one missing it (SPEC F162.2) =="
check_kind_entry_green valid-ad-pack-index-entry "tools/testdata/green/valid-ad-pack-index-entry"
check_kind_entry_red bad-kind-ad-pack-no-manifest "'manifest' is a required property"

echo "== schemas/index.schema.json: voice-pack/jingle-pack kinds admit manifest+assets[], reject malformed ones (SPEC F164/F165, T411) =="
check_kind_entry_green valid-voice-pack-index-entry "tools/testdata/green/valid-voice-pack-index-entry"
check_kind_entry_red bad-kind-voice-pack-no-assets "'assets' is a required property"
check_kind_entry_green valid-jingle-pack-index-entry "tools/testdata/green/valid-jingle-pack-index-entry"
check_kind_entry_red bad-kind-jingle-pack-no-manifest "'manifest' is a required property"

echo "-- kind-exclusive fields, extended to voice-pack/jingle-pack: neither kind may carry 'card' or 'preview' (T411) --"
check_kind_entry_red voice-pack-entry-with-card "should not be valid under {'required': ['card']}"
check_kind_entry_red jingle-pack-entry-with-preview "should not be valid under {'required': ['preview']}"

echo "-- red avatar-asset-bytes-over-max: the avatar \`then\` branch's OWN narrower assets[].items.bytes ceiling (524288, GenWave.Host.Catalog.CatalogIndexValidator.MaxPngAssetBytes) — T411 review round 1 finding 6: before T411 widened the shared assetRef bound past 524288 for jingle-pack's sake, this fixture happened to also test the GENERIC bound (the two ceilings were numerically identical); now that the shared bound is 5242880, this fixture exercises ONLY the avatar-specific override (same posture as font-asset-bytes-over-font-max above) --"
check_kind_entry_red avatar-asset-bytes-over-max "is greater than the maximum of 524288"

echo "-- red persona-avatar-bytes-over-max: the persona \`else\` branch's OWN narrower assets[].items.bytes ceiling (524288, the same MaxPngAssetBytes cap as avatar's — T411 review round 1 finding 1) — the persona branch's avatar-sidecar override was the one kind this widening silently skipped; this fixture pins it can never regress silently again --"
check_kind_entry_red persona-avatar-bytes-over-max "is greater than the maximum of 524288"

echo "-- red jingle-asset-bytes-over-generic-max: the shared assetRef definition's own GENERIC 5242880-byte (5 MiB) ceiling — jingle-pack carries no per-kind override narrower than the shared bound (its own real cap IS the shared bound), so this is the only fixture that actually isolates the generic ceiling post-widening (T411 review round 1 finding 6) --"
check_kind_entry_red jingle-asset-bytes-over-generic-max "is greater than the maximum of 5242880"

echo "-- kind/extension cross-dressing, extended to avatar/icon --"
check_kind_entry_red avatar-entry-with-preview "should not be valid under {'required': ['preview']}"
check_kind_entry_red icon-entry-with-assets "should not be valid under {'required': ['assets']}"
check_kind_entry_red ad-pack-entry-with-assets "should not be valid under {'required': ['assets']}"

echo "== schemas/index.schema.json: a persona entry MAY carry assets[] (SPEC F128.2), capped to exactly one element (T309) =="
check_kind_entry_green valid-persona-with-avatar-index-entry "tools/testdata/green/valid-persona-with-avatar-index-entry"
check_kind_entry_red persona-entry-two-avatar-assets "is too long"

echo "=========================================="
if [[ $FAILURES -eq 0 ]]; then
    echo "SELFTEST PASS"
    exit 0
else
    echo "SELFTEST FAIL ($FAILURES check(s) failed)"
    exit 1
fi
