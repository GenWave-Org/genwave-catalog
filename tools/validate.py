#!/usr/bin/env python3
"""Validate genwave-catalog entries against the repo's schemas and format rules.

Rules enforced (all documented as LAW in README.md / SPEC F89.2, kind-aware
per SPEC F103.2 / T179):

  - An entry's `kind` is read off which manifest filename its directory
    carries — <slug>.persona.json means a persona entry, <slug>.theme.json
    means a theme entry, <slug>.font.json means a font entry (SPEC F104.1 /
    T195) — persona wins if, bizarrely, more than one manifest file is
    present, then theme, then font (resolve_kind's own precedence). This is
    NOT the same convention tools/build_index.py's resolve_manifest derives
    `kind` from today: that function mirrors only the persona/theme half —
    it does not yet resolve a `.font.json` manifest at all (a T196
    obligation; see resolve_manifest's own comment) — so a directory this
    module classifies kind:"font" still validates here, but build_index.py
    silently skips it (never emits an index entry for it) until T196 lands.
    An entry with none of the three manifest filenames is reported as a
    missing persona card, the pre-T179 default.
  - <slug>.persona.json (or <slug>.theme.json) and <slug>.meta.json are each
    valid JSON.
  - A persona's card validates against schemas/persona-card.schema.json; a
    theme's manifest validates against schemas/theme-manifest.schema.json.
  - A persona's meta file validates against schemas/persona-meta.schema.json;
    a theme's meta file validates against schemas/theme-meta.schema.json —
    this is where required fields (`audience`, persona's >=2 `samplePatter`,
    theme's `preview` swatches) are enforced; the schema violation always
    names the offending file.
  - A theme's manifest clears the WCAG AA contrast gate (SPEC F102.8 / T158,
    ported to the catalog at T180): the 11 token pairs
    `admin-ui/__specs__/theme-shelf-contrast.spec.ts` asserts against every
    shipped theme (ink on each ground, accent-ink on accent, danger-ink on
    danger, mute/accent-2 on each ground) each measure >= 4.5:1 in both
    `light` and `dark` modes (tools/contrast.py). This is a HARD gate, same
    as the schema check above it — a failing pair, or a pair missing either
    of its two tokens, rejects the entry before it ever reaches
    tools/build_index.py.
  - A font pack (kind:\"font\", <slug>.font.json) is gated per SPEC F104.2,
    on top of its own schema check (schemas/font-manifest.schema.json /
    schemas/font-meta.schema.json): the entry's actual asset files (every
    sibling file in its directory other than the manifest/meta, matching the
    app's own closed woff2|txt extension set) must sum to <= 204,800 bytes
    (200 KiB, the per-pack ceiling), must include an `OFL.txt` licence file,
    the manifest's `license` field must be one of this repo's permitted SPDX
    identifiers, every face the manifest's `files[]` names must correspond to
    an asset the entry actually ships (an "orphan" reference is malformed),
    `files[]` must never declare the same asset filename twice, and — the
    reverse of the orphan check — every physical asset file the entry ships
    must itself be named in `files[]` or be `OFL.txt` (a "stowaway" asset
    nothing references is just as malformed). All six are HARD gates
    (tools/validate.py's `validate_font_pack`).
  - `added` is a real calendar date, not just YYYY-MM-DD shaped (the schema
    pattern lets '9999-99-99' through; datetime.date.fromisoformat doesn't).
  - slug == entry directory name == both filenames' stems.
  - The directory name itself matches ^[a-z0-9]+(-[a-z0-9]+)*$, anchored to
    the absolute end of the string — a trailing newline in the name fails
    this, unlike a bare `$` in Python's re would let through.
  - entries/ contains only <slug>/ directories — no loose files.
  - An entry directory contains only its manifest file (<slug>.persona.json,
    <slug>.theme.json, or <slug>.font.json) and <slug>.meta.json — plus,
    ONLY for a font entry, its own asset files (woff2 faces + OFL.txt) — any
    other file is a violation.
  - Nothing under entries/ is a symlink, at any depth (checked before any
    file is read).
  - <slug>.persona.json is <= 256 KiB and <slug>.meta.json is <= 64 KiB. No
    size cap is enforced on <slug>.theme.json or <slug>.font.json — SPEC
    F103.2/F104.2 don't define one on the manifest text itself and the app
    imposes none on a loaded manifest (a font pack's own per-pack asset
    ceiling is a separate, asset-summed rule — see above).
  - fixtures/golden.persona.json (the app-serializer parity artifact) still
    validates against the card schema, fixtures/golden.theme.json still
    validates against the theme-manifest schema, and fixtures/golden.font.json
    still validates against the font-manifest schema, so none of the three
    can silently rot.
  - index.json exists at the repo root and validates against
    schemas/index.schema.json — this and the fixtures/ check above only ever
    run against the real repo (see --root below), never a testdata root.

Prints one line per violation, each naming the offending file (or directory)
and the rule it broke. Exits 0 with no output beyond a summary when the tree
is clean, non-zero otherwise.

Usage:
    tools/validate.py [--root PATH]

--root overrides where entries/ is read from, while schemas/ is always read
from this script's own repo — this is what lets tools/run_selftest.sh point
at tools/testdata/red/<variant>/ without needing its own copy of the schemas.
The fixtures/golden.persona.json and index.json checks are gated on `--root`
resolving to this repo's own root (not merely on the directory/file existing)
so that deleting either from the real repo fails CI, while a testdata root —
which never carries either — is never held to that bar.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

import jsonschema

from catalog_lib import REPO_ROOT, SCHEMAS_DIR, discover_entry_dirs, find_symlinks, rel
from contrast import check_theme_aa

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*\Z")  # \Z, not $: $ matches before a trailing \n
CARD_SIZE_CAP = 256 * 1024  # bytes; mirrors the app's own import cap (SPEC F79.6)
META_SIZE_CAP = 64 * 1024  # bytes

# A font pack's own asset files (SPEC F104.1) — closed extension set (woff2
# faces + the pack's OFL licence text), bare filename only (mirrors the app's
# GenWave.Host.Catalog.CatalogIndexValidator.AssetFileNameText exactly).
FONT_ASSET_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.(?:woff2|txt)\Z")
FONT_LICENSE_ASSET_NAME = "OFL.txt"
FONT_PACK_BYTE_CEILING = 200 * 1024  # 204,800 bytes; SPEC F104.2's per-pack ceiling
# FONTS.md step 1: "confirm the upstream family carries a permissive licence —
# the SIL Open Font License (OFL) or an equivalent (e.g. Apache 2.0)". The
# catalog's own permitted set starts with exactly the two SPDX identifiers
# that wording names; widen this set (and this comment) if/when a future pack
# needs a third.
FONT_PERMITTED_LICENSES = {"OFL-1.1", "Apache-2.0"}


def load_schema(name: str) -> dict:
    return json.loads((SCHEMAS_DIR / name).read_text(encoding="utf-8"))


def parse_json(path: Path) -> tuple[object | None, list[str]]:
    """Returns (instance, violations). instance is None if parsing failed."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, [f"{rel(REPO_ROOT, path)}: missing-file: {exc.strerror}"]
    try:
        return json.loads(raw), []
    except json.JSONDecodeError as exc:
        return None, [
            f"{rel(REPO_ROOT, path)}: json-parse: {exc.msg} (line {exc.lineno}, column {exc.colno})"
        ]


def validate_schema(path: Path, instance: object, schema: dict) -> list[str]:
    validator_cls = jsonschema.validators.validator_for(schema)
    validator = validator_cls(schema)
    violations = []
    for error in sorted(validator.iter_errors(instance), key=lambda e: list(map(str, e.path))):
        pointer = "/".join(str(p) for p in error.path) or "(root)"
        violations.append(f"{rel(REPO_ROOT, path)}: schema: {pointer}: {error.message}")
    return violations


def check_size_cap(path: Path, cap: int, kind: str) -> list[str]:
    size = path.stat().st_size
    if size > cap:
        return [f"{rel(REPO_ROOT, path)}: size-cap: {size} bytes exceeds the {cap}-byte cap for {kind} files"]
    return []


def validate_json_against(path: Path, schema: dict) -> list[str]:
    """Parse + schema-validate a JSON file, in isolation (no size check)."""
    instance, violations = parse_json(path)
    if instance is None:
        return violations
    return violations + validate_schema(path, instance, schema)


def validate_theme_aa(manifest_path: Path, slug: str, manifest: object) -> list[str]:
    """AA contrast gate (SPEC F102.8 / T158, ported to the catalog at T180):
    checks a theme manifest's `modes` against tools/contrast.py's 11 asserted
    pairs in both light and dark. A HARD gate, same posture as the schema
    check next to it — a failing (or token-missing) pair rejects the entry,
    it does not merely warn. Only ever called for kind:"theme" entries;
    personas have no `modes` to check and are unaffected."""
    if not isinstance(manifest, dict):
        return []
    return [
        f"{rel(REPO_ROOT, manifest_path)}: aa-contrast: theme '{slug}': {finding}"
        for finding in check_theme_aa(manifest.get("modes"))
    ]


def font_asset_paths(entry_dir: Path) -> list[Path]:
    """Every one of a font entry's OWN asset files — every sibling file in
    its directory matching FONT_ASSET_NAME_PATTERN (the same closed
    woff2|txt extension set the app enforces). These are the entry's
    `assets[]`-to-be (tools/build_index.py's later projection, T196); this
    module treats "what's actually on disk" as the source of truth, the same
    posture it already takes for a manifest/meta file's own presence."""
    return sorted(p for p in entry_dir.iterdir() if p.is_file() and FONT_ASSET_NAME_PATTERN.match(p.name))


def validate_font_pack(entry_dir: Path, slug: str, manifest: object) -> list[str]:
    """Font pack gates (SPEC F104.2), on top of the schema check next to this
    call — six HARD gates, same posture as validate_theme_aa above:

      - the pack's own asset files (font_asset_paths) sum to <= the 200 KiB
        per-pack ceiling (FONT_PACK_BYTE_CEILING);
      - an `OFL.txt` licence file is among those assets;
      - the manifest's `license` field is one of FONT_PERMITTED_LICENSES;
      - every face `files[]` names actually exists as one of those assets
        (an "orphan" reference — a manifest naming a face the entry doesn't
        ship — is malformed, mirroring the app's own reject-vs-degrade
        posture for a font entry's assets: a pack IS its files);
      - `files[]` never declares the same asset filename twice (mirrors
        GenWave.Host.Catalog.CatalogIndexValidator.TryValidateAssets' own
        seen-paths dedupe, ported here to the manifest's own declared list
        since tools/build_index.py's assets[] projection is a later task,
        T196 — this module has only the manifest's own `files[]` to check
        today);
      - the REVERSE of the orphan-reference check above: every physical
        asset file the entry ships (font_asset_paths again) is accounted for
        by either `files[]` or being the OFL.txt licence file itself — a
        stowaway woff2 sitting in the directory that no face references is
        just as malformed as a face referencing an asset that isn't there.
        "a pack IS its files" cuts both ways.

    A missing OFL.txt / zero assets is reported even when the manifest
    itself failed to parse as an object (`manifest` is checked defensively
    below); the license/orphan/duplicate/stowaway checks all need a parsed
    dict (the stowaway check needs `files[]`, even an absent/empty one, to
    know what's declared) and are skipped, not reported as new violations,
    when it isn't one — the schema check next to this call already names
    that shape failure once.
    """
    label = rel(REPO_ROOT, entry_dir)
    violations: list[str] = []

    assets = font_asset_paths(entry_dir)
    asset_names = {p.name for p in assets}

    if not assets:
        violations.append(
            f"{label}: font-no-assets: font pack ships zero assets — needs at least "
            f"{FONT_LICENSE_ASSET_NAME} and one woff2 face"
        )

    if FONT_LICENSE_ASSET_NAME not in asset_names:
        violations.append(f"{label}: font-missing-ofl: font pack does not ship {FONT_LICENSE_ASSET_NAME} among its assets")

    total_bytes = sum(p.stat().st_size for p in assets)
    if total_bytes > FONT_PACK_BYTE_CEILING:
        violations.append(
            f"{label}: font-pack-ceiling: summed asset bytes {total_bytes} exceeds the "
            f"{FONT_PACK_BYTE_CEILING}-byte per-pack ceiling (SPEC F104.2)"
        )

    if not isinstance(manifest, dict):
        return violations

    license_value = manifest.get("license")
    if isinstance(license_value, str) and license_value not in FONT_PERMITTED_LICENSES:
        permitted = ", ".join(sorted(FONT_PERMITTED_LICENSES))
        violations.append(
            f"{label}: font-bad-license: license '{license_value}' is not in the permitted set ({permitted})"
        )

    files = manifest.get("files")
    declared_files: list[str] = []
    if isinstance(files, list):
        declared_files = [f["file"] for f in files if isinstance(f, dict) and isinstance(f.get("file"), str)]

        seen: set[str] = set()
        duplicated: set[str] = set()
        for file_name in declared_files:
            if file_name in seen:
                duplicated.add(file_name)
            seen.add(file_name)
        for file_name in sorted(duplicated):
            violations.append(
                f"{label}: font-duplicate-asset: manifest declares '{file_name}' more than once in files[]"
            )

        for file_name in sorted(set(declared_files)):
            if file_name not in asset_names:
                violations.append(
                    f"{label}: font-orphan-manifest-file: manifest names '{file_name}' in files[] but the "
                    "entry does not ship that asset"
                )

    # Reverse orphan (the flip side of font-orphan-manifest-file above): a
    # physical asset file the entry ships that neither files[] declares nor
    # is the OFL.txt licence file itself is a stowaway — "a pack IS its
    # files" means an unreferenced, unaccounted-for file is malformed too,
    # not just a face reference pointing at nothing.
    accounted_for = set(declared_files) | {FONT_LICENSE_ASSET_NAME}
    for asset_name in sorted(asset_names - accounted_for):
        violations.append(
            f"{label}: font-stowaway-asset: entry ships '{asset_name}' but it is named neither in "
            f"files[] nor is it {FONT_LICENSE_ASSET_NAME} — every shipped asset must be accounted for"
        )

    return violations


def validate_added_date(meta_path: Path, meta: object) -> list[str]:
    """`added` passing the meta schema's pattern only proves it's shaped like
    YYYY-MM-DD — '9999-99-99' matches that pattern but isn't a real calendar
    date. Catch that here since it flows straight into index.json's
    generatedAt (tools/build_index.py: max `added` across included entries)."""
    if not isinstance(meta, dict):
        return []
    added = meta.get("added")
    if not isinstance(added, str):
        return []  # missing/wrong-type is already reported by the schema check
    try:
        datetime.date.fromisoformat(added)
    except ValueError:
        return [f"{rel(REPO_ROOT, meta_path)}: bad-date: 'added' value '{added}' is not a real calendar date"]
    return []


def resolve_kind(entry_dir: Path) -> str:
    """"persona", "theme", or "font" — which manifest filename this entry
    directory carries: a *.persona.json file means "persona" (persona wins
    if, bizarrely, more than one manifest file is present), else a
    *.theme.json file means "theme", else a *.font.json file means "font"
    (SPEC F104.1 / T195), and none present defaults to "persona" (the
    pre-T179 shape, so the caller reports a familiar missing-card violation
    rather than a new missing-kind one). Glob-matched rather than an exact
    <slug>.* filename so a slug-mismatched manifest file is still classified
    — and then reported as a slug-mismatch below, not silently treated as
    missing.

    DIVERGES from tools/build_index.py's own resolve_manifest as of T195:
    that function mirrors only the persona/theme two-thirds of this
    precedence — it has no *.font.json branch at all, so it silently skips
    every kind:"font" directory this function correctly resolves (no error,
    no index entry, the pack just never reaches index.json). Closing that
    gap — teaching resolve_manifest to recognise *.font.json, project
    assets[]/family, and generally build a real font index entry — is T196's
    job, not this module's; resolve_manifest carries its own comment marking
    the obligation. Until T196 lands, "this module accepts a font pack" and
    "build_index.py will actually ship it" are two different claims."""
    if any(entry_dir.glob("*.persona.json")):
        return "persona"
    if any(entry_dir.glob("*.theme.json")):
        return "theme"
    if any(entry_dir.glob("*.font.json")):
        return "font"
    return "persona"


def validate_entry(
    entry_dir: Path,
    card_schema: dict,
    persona_meta_schema: dict,
    theme_manifest_schema: dict,
    theme_meta_schema: dict,
    font_manifest_schema: dict,
    font_meta_schema: dict,
) -> list[str]:
    slug = entry_dir.name
    label = rel(REPO_ROOT, entry_dir)

    # Symlinks are never trusted — checked, and bailed out on, before any
    # file in this entry is opened (tools/catalog_lib.py: find_symlinks).
    symlinks = find_symlinks(entry_dir)
    if symlinks:
        return [f"{rel(REPO_ROOT, p)}: symlink: symlinks are not allowed under entries/" for p in symlinks]

    violations: list[str] = []

    if not SLUG_PATTERN.match(slug):
        violations.append(
            f"{label}: slug-format: directory name '{slug}' does not match "
            "^[a-z0-9]+(-[a-z0-9]+)*$ (matched to the absolute end of the name — a trailing "
            "newline fails this too)"
        )

    kind = resolve_kind(entry_dir)
    if kind == "theme":
        manifest_suffix = ".theme.json"
        manifest_schema = theme_manifest_schema
        manifest_kind_label = "theme manifest"
        meta_schema = theme_meta_schema
        manifest_size_cap = None  # SPEC F103.2 defines none; the app imposes none on a loaded manifest
    elif kind == "font":
        manifest_suffix = ".font.json"
        manifest_schema = font_manifest_schema
        manifest_kind_label = "font manifest"
        meta_schema = font_meta_schema
        manifest_size_cap = None  # SPEC F104.2 defines none on the manifest text itself; see validate_font_pack
    else:
        manifest_suffix = ".persona.json"
        manifest_schema = card_schema
        manifest_kind_label = "card"
        meta_schema = persona_meta_schema
        manifest_size_cap = CARD_SIZE_CAP

    allowed_names = {f"{slug}{manifest_suffix}", f"{slug}.meta.json"}
    if kind == "font":
        # A font entry ALSO ships its own asset files (SPEC F104.1) —
        # 1-2 woff2 faces plus OFL.txt — sitting alongside the manifest/meta
        # named above, unlike a persona/theme entry's fixed two-file shape.
        unexpected = sorted(
            p.name
            for p in entry_dir.iterdir()
            if p.name not in allowed_names and not (p.is_file() and FONT_ASSET_NAME_PATTERN.match(p.name))
        )
        for name in unexpected:
            violations.append(
                f"{rel(REPO_ROOT, entry_dir / name)}: unexpected-file: only <slug>{manifest_suffix}, "
                "<slug>.meta.json, and asset files matching "
                "[A-Za-z0-9][A-Za-z0-9._-]*.(woff2|txt) are allowed in a font entry directory"
            )
    else:
        unexpected = sorted(p.name for p in entry_dir.iterdir() if p.name not in allowed_names)
        for name in unexpected:
            violations.append(
                f"{rel(REPO_ROOT, entry_dir / name)}: unexpected-file: only <slug>{manifest_suffix} and "
                "<slug>.meta.json are allowed in an entry directory"
            )

    manifest_candidates = sorted(entry_dir.glob(f"*{manifest_suffix}"))
    meta_candidates = sorted(entry_dir.glob("*.meta.json"))

    if len(manifest_candidates) != 1:
        violations.append(
            f"{label}: missing-file: expected exactly one <slug>{manifest_suffix}, found {len(manifest_candidates)}"
        )
    if len(meta_candidates) != 1:
        violations.append(
            f"{label}: missing-file: expected exactly one <slug>.meta.json, found {len(meta_candidates)}"
        )

    if len(manifest_candidates) == 1:
        manifest_path = manifest_candidates[0]
        manifest_stem = manifest_path.name[: -len(manifest_suffix)]
        if manifest_stem != slug:
            violations.append(
                f"{rel(REPO_ROOT, manifest_path)}: slug-mismatch: filename slug '{manifest_stem}' does not match directory '{slug}'"
            )
        if manifest_size_cap is not None:
            violations.extend(check_size_cap(manifest_path, manifest_size_cap, manifest_kind_label))
        manifest_instance, manifest_parse_violations = parse_json(manifest_path)
        violations.extend(manifest_parse_violations)
        if manifest_instance is not None:
            violations.extend(validate_schema(manifest_path, manifest_instance, manifest_schema))
            if kind == "theme":
                violations.extend(validate_theme_aa(manifest_path, slug, manifest_instance))
            elif kind == "font":
                violations.extend(validate_font_pack(entry_dir, slug, manifest_instance))

    if len(meta_candidates) == 1:
        meta_path = meta_candidates[0]
        meta_stem = meta_path.name[: -len(".meta.json")]
        if meta_stem != slug:
            violations.append(
                f"{rel(REPO_ROOT, meta_path)}: slug-mismatch: filename slug '{meta_stem}' does not match directory '{slug}'"
            )
        violations.extend(check_size_cap(meta_path, META_SIZE_CAP, "meta"))
        meta_instance, meta_parse_violations = parse_json(meta_path)
        violations.extend(meta_parse_violations)
        if meta_instance is not None:
            violations.extend(validate_schema(meta_path, meta_instance, meta_schema))
            violations.extend(validate_added_date(meta_path, meta_instance))

    return violations


def validate_entries_top_level(entries_dir: Path) -> list[str]:
    """entries/ itself may only contain <slug>/ directories — a loose file
    directly under entries/ (entries/README.md, a stray entries/loose-link
    symlink) is invisible to validate_entry, which only ever sees what
    discover_entry_dirs hands it (directories only). Non-recursive by design:
    a directory that's itself a symlink is deliberately left to
    validate_entry's own find_symlinks(entry_dir) call, so it's reported
    exactly once, not twice."""
    violations: list[str] = []
    for path in sorted(p for p in entries_dir.iterdir() if not p.is_dir()):
        if path.is_symlink():
            violations.append(f"{rel(REPO_ROOT, path)}: symlink: symlinks are not allowed under entries/")
        else:
            violations.append(
                f"{rel(REPO_ROOT, path)}: unexpected-file: entries/ may only contain <slug>/ directories"
            )
    return violations


def validate_entries(
    entries_dir: Path,
    card_schema: dict,
    persona_meta_schema: dict,
    theme_manifest_schema: dict,
    theme_meta_schema: dict,
    font_manifest_schema: dict,
    font_meta_schema: dict,
) -> list[str]:
    if not entries_dir.is_dir():
        return [f"{rel(REPO_ROOT, entries_dir)}: missing-file: entries/ directory not found"]
    violations: list[str] = validate_entries_top_level(entries_dir)
    for entry_dir in discover_entry_dirs(entries_dir):
        violations.extend(
            validate_entry(
                entry_dir,
                card_schema,
                persona_meta_schema,
                theme_manifest_schema,
                theme_meta_schema,
                font_manifest_schema,
                font_meta_schema,
            )
        )
    return violations


def validate_golden_fixture(
    fixtures_dir: Path, card_schema: dict, theme_manifest_schema: dict, font_manifest_schema: dict
) -> list[str]:
    """Only called for the real repo (see main()) — fixtures/ must exist
    there; a testdata root never carries a copy and is never routed here.
    Checks all three parity artifacts: golden.persona.json (the app card
    serializer) against the card schema, golden.theme.json (the app manifest
    serializer) against the theme-manifest schema, and golden.font.json (the
    app CatalogFontManifestSerializer) against the font-manifest schema —
    any one silently drifting from what it's supposed to validate against
    would mean this repo's copy of the app's format has rotted out from
    under it.

    Deliberately shape-only, not AA-checked (T180 scoping decision):
    golden.theme.json is a byte-for-byte round-trip parity fixture pinned
    against the app's own tests/GenWave.Host.Tests/Fixtures/golden.theme.json
    (Story269_CatalogKindSeam.cs) — its job is proving the manifest SHAPE
    serializes/deserializes without loss, not modelling a shelf-quality
    palette, and it is in fact not AA-clean as authored (three light-mode
    pairs measure below 4.5:1). Making it AA-clean would mean re-picking its
    colours, which would change its bytes and require a synced edit on the
    app side purely to satisfy a gate this fixture was never meant to
    exercise. The AA gate itself (validate_theme_aa) is scoped to actual
    catalog theme ENTRIES under entries/, where T180's task is aimed.
    golden.font.json is the same idea for the font kind (T193/T195): a
    round-trip parity fixture pinned against the app's own
    tests/GenWave.Host.Tests/Fixtures/golden.font.json, shape-only and not
    subject to validate_font_pack's own asset/ceiling/license gates — it
    carries no sibling asset files of its own (this is a manifest-shape
    parity artifact, not a real catalog entry), so those gates are scoped to
    actual font ENTRIES under entries/, same split as the theme AA gate."""
    if not fixtures_dir.is_dir():
        return [f"{rel(REPO_ROOT, fixtures_dir)}: missing-file: fixtures/ directory not found"]

    violations: list[str] = []

    golden_persona_path = fixtures_dir / "golden.persona.json"
    if not golden_persona_path.is_file():
        violations.append(f"{rel(REPO_ROOT, golden_persona_path)}: missing-file: golden fixture not found")
    else:
        violations.extend(validate_json_against(golden_persona_path, card_schema))

    golden_theme_path = fixtures_dir / "golden.theme.json"
    if not golden_theme_path.is_file():
        violations.append(f"{rel(REPO_ROOT, golden_theme_path)}: missing-file: golden theme fixture not found")
    else:
        violations.extend(validate_json_against(golden_theme_path, theme_manifest_schema))

    golden_font_path = fixtures_dir / "golden.font.json"
    if not golden_font_path.is_file():
        violations.append(f"{rel(REPO_ROOT, golden_font_path)}: missing-file: golden font fixture not found")
    else:
        violations.extend(validate_json_against(golden_font_path, font_manifest_schema))

    return violations


def validate_index(index_path: Path) -> list[str]:
    """Only called for the real repo (see main()) — index.json must exist at
    the repo root and validate against schemas/index.schema.json."""
    if not index_path.is_file():
        return [f"{rel(REPO_ROOT, index_path)}: missing-file: index.json not found at repo root"]
    return validate_json_against(index_path, load_schema("index.schema.json"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="directory containing entries/ to validate (default: repo root)",
    )
    args = parser.parse_args()
    root = args.root.resolve()

    card_schema = load_schema("persona-card.schema.json")
    persona_meta_schema = load_schema("persona-meta.schema.json")
    theme_manifest_schema = load_schema("theme-manifest.schema.json")
    theme_meta_schema = load_schema("theme-meta.schema.json")
    font_manifest_schema = load_schema("font-manifest.schema.json")
    font_meta_schema = load_schema("font-meta.schema.json")

    violations = validate_entries(
        root / "entries",
        card_schema,
        persona_meta_schema,
        theme_manifest_schema,
        theme_meta_schema,
        font_manifest_schema,
        font_meta_schema,
    )

    if root == REPO_ROOT:
        violations.extend(
            validate_golden_fixture(root / "fixtures", card_schema, theme_manifest_schema, font_manifest_schema)
        )
        violations.extend(validate_index(root / "index.json"))

    for line in violations:
        print(line)

    if violations:
        print(f"FAIL: {len(violations)} violation(s)")
        return 1

    print("PASS: all catalog entries valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
