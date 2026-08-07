#!/usr/bin/env python3
"""Validate genwave-catalog entries against the repo's schemas and format rules.

Rules enforced (all documented as LAW in README.md / SPEC F89.2, kind-aware
per SPEC F103.2 / T179):

  - An entry's `kind` is read off which manifest filename its directory
    carries — <slug>.persona.json means a persona entry, <slug>.theme.json
    means a theme entry, <slug>.font.json means a font entry (SPEC F104.1 /
    T195) — persona wins if, bizarrely, more than one manifest file is
    present, then theme, then font (resolve_kind's own precedence, driven by
    the `kind_specs` dict build_kind_specs() assembles — N5, T196; the
    kind/suffix/precedence triple itself now lives in tools/catalog_lib.py's
    KIND_SUFFIXES, T196 review M3). This is now the SAME convention
    tools/build_index.py's own resolve_manifest derives `kind` from: until
    T196, that function mirrored only the persona/theme half —
    it did not resolve a `.font.json` manifest at all — so a directory this
    module classified kind:"font" validated here but build_index.py silently
    skipped it (never emitted an index entry for it). T196 closed that gap
    (resolve_manifest's own comment in tools/build_index.py records the
    history). An entry with none of the three manifest filenames is reported
    as a missing persona card, the pre-T179 default.
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
  - A theme's manifest stays curated-only (SPEC F104.9's unbreakable-themes
    invariant, PLAN T205, Dean's ruling 2026-08-05: "themes never reference
    font packs in the catalog"): every `fonts.display`/`fonts.sans` asset
    `src` must be one of GenWave's five vendored `/fonts/*.woff2` faces
    (VENDORED_FONT_SRCS, mirroring the app's own fonts-provenance.json) —
    never a font-pack face. A HARD gate (tools/validate.py's
    `validate_theme_font_provenance`); the app's own widened, per-station
    vendored-union-installed law (SPEC F104.9/F104.10) governs a station's
    own theme IMPORT, not what the shared catalog shelf may publish, so a
    catalog theme keeps rendering with zero network on every station
    regardless of which packs, if any, that station has installed.
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
  - Every index.json entry's `card`/`manifest`/`meta`/`assets[]` path
    resolves under `entries/<that entry's own slug>/` — nothing dangling,
    nothing borrowed from a sibling entry's directory (T196, SPEC F104.1 —
    draft-07 JSON Schema has no way to express a cross-sibling-property
    constraint like this, so validate_index_slug_ownership is the actual
    gate; schemas/index.schema.json's own patterns can only pin path SHAPE).
  - No two assets within one index.json entry's `assets[]` share the same
    `path` (T196 review M2): schemas/index.schema.json's `uniqueItems` on
    `assets` is FULL-OBJECT uniqueness — it only rejects a duplicate when
    `path`/`sha256`/`bytes` all match — so two assets sharing a `path` with
    different `sha256`/`bytes` pass that schema gate untouched even though
    the app dedupes an entry's assets on `path` ALONE
    (GenWave.Host.Catalog.CatalogIndexValidator.TryValidateAssets), silently
    dropping one of the two the moment it's parsed. Another cross-property
    constraint draft-07 can't express, so validate_index_duplicate_asset_paths
    is the actual gate, same posture as slug-ownership above.

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
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import jsonschema

from catalog_lib import (
    FONT_ASSET_NAME_PATTERN,
    KIND_SUFFIXES,
    REPO_ROOT,
    SCHEMAS_DIR,
    discover_entry_dirs,
    find_symlinks,
    font_asset_paths,
    rel,
)
from contrast import check_theme_aa

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*\Z")  # \Z, not $: $ matches before a trailing \n
CARD_SIZE_CAP = 256 * 1024  # bytes; mirrors the app's own import cap (SPEC F79.6)
META_SIZE_CAP = 64 * 1024  # bytes

# FONT_ASSET_NAME_PATTERN (closed woff2|txt extension set, bare filename
# only) now lives in tools/catalog_lib.py, shared with tools/build_index.py's
# assets[] index projection (T196) — imported above rather than redefined
# here.
FONT_LICENSE_ASSET_NAME = "OFL.txt"
FONT_PACK_BYTE_CEILING = 200 * 1024  # 204,800 bytes; SPEC F104.2's per-pack ceiling
# FONTS.md step 1: "confirm the upstream family carries a permissive licence —
# the SIL Open Font License (OFL) or an equivalent (e.g. Apache 2.0)". The
# catalog's own permitted set starts with exactly the two SPDX identifiers
# that wording names; widen this set (and this comment) if/when a future pack
# needs a third.
FONT_PERMITTED_LICENSES = {"OFL-1.1", "Apache-2.0"}

# SPEC F104.9's "unbreakable themes" invariant (Dean's ruling 2026-08-05, PLAN T205: "themes never
# reference font packs in the catalog") — mirrors the app's own GenWave.Host/wwwroot/fonts/fonts-
# provenance.json (FONTS.md's curated set) exactly. The app's ThemeFontProvenanceValidator widens to
# vendored UNION installed for a station's own IMPORT (SPEC F104.9/F104.10) — but that union is
# per-station, depending on which packs THAT station happened to install. A theme entry accepted onto
# the PUBLIC catalog must reference ONLY this fixed set: it renders identically, with zero network, on
# EVERY station regardless of what that station has installed — the guarantee validate_theme_font_
# provenance below exists to hold. Keep this set and that JSON file in sync by hand if GenWave ever
# vendors a new base face (the same cross-repo "authored in one repo, mirrored in the other" discipline
# fixtures/golden.theme.json already carries, T177).
VENDORED_FONT_SRCS = {
    "/fonts/fraunces-variable-latin.woff2",
    "/fonts/fraunces-italic-variable-latin.woff2",
    "/fonts/source-sans-3-variable-latin.woff2",
    "/fonts/jetbrains-mono-variable-latin.woff2",
    "/fonts/grenze-gotisch-variable-latin.woff2",
}


def load_schema(name: str) -> dict:
    return json.loads((SCHEMAS_DIR / name).read_text(encoding="utf-8"))


@dataclass(frozen=True)
class KindSpec:
    """Everything that varies by entry kind (SPEC F103.2 persona/theme,
    F104.1 font): the manifest filename suffix, a human-readable label for
    error messages, the manifest/meta schema pair, the manifest's own size
    cap (persona only — see CARD_SIZE_CAP), a predicate for which EXTRA
    sibling files an entry directory of this kind may carry beyond its own
    manifest/meta (font only: its own asset files), and the exact wording
    used when a file fails that allowance.

    ONE dict of these (see build_kind_specs) replaces what used to be three
    separate per-kind ladders (N5, T196 review finding): resolve_kind's own
    glob chain, the if/elif/else inside validate_entry that picked out
    manifest_suffix/manifest_schema/meta_schema/size_cap by hand, and the
    allowed-names if/else next to it that special-cased font's extra asset
    files. Each of the three now reads off this one structure instead of
    re-enumerating persona/theme/font independently — a new kind is one new
    dict entry, not three new branches."""

    suffix: str
    label: str
    manifest_schema: dict
    meta_schema: dict
    size_cap: int | None
    allows_extra: Callable[[Path], bool]
    unexpected_file_hint: str


def build_kind_specs() -> dict[str, KindSpec]:
    """Loads every kind's schemas exactly once and assembles the single
    `kind_specs` dict every per-kind decision in this module reads from
    (N5, T196). Insertion order IS precedence order: resolve_kind returns the
    first kind whose glob matches when walking this dict — persona, then
    theme, then font — the exact precedence this module has always
    documented (persona wins if, bizarrely, more than one manifest file is
    present in an entry directory). Each entry's `suffix` is read off
    tools/catalog_lib.py's KIND_SUFFIXES — the same ordered mapping
    tools/build_index.py's resolve_manifest walks — rather than being
    hand-spelled here a second time (T196 review M3)."""
    specs = {
        "persona": KindSpec(
            suffix=KIND_SUFFIXES["persona"],
            label="card",
            manifest_schema=load_schema("persona-card.schema.json"),
            meta_schema=load_schema("persona-meta.schema.json"),
            size_cap=CARD_SIZE_CAP,
            allows_extra=lambda path: False,
            unexpected_file_hint="only <slug>.persona.json and <slug>.meta.json are allowed in an entry directory",
        ),
        "theme": KindSpec(
            suffix=KIND_SUFFIXES["theme"],
            label="theme manifest",
            manifest_schema=load_schema("theme-manifest.schema.json"),
            meta_schema=load_schema("theme-meta.schema.json"),
            size_cap=None,  # SPEC F103.2 defines none; the app imposes none on a loaded manifest
            allows_extra=lambda path: False,
            unexpected_file_hint="only <slug>.theme.json and <slug>.meta.json are allowed in an entry directory",
        ),
        "font": KindSpec(
            suffix=KIND_SUFFIXES["font"],
            label="font manifest",
            manifest_schema=load_schema("font-manifest.schema.json"),
            meta_schema=load_schema("font-meta.schema.json"),
            size_cap=None,  # SPEC F104.2 defines none on the manifest text itself; see validate_font_pack
            allows_extra=lambda path: path.is_file() and bool(FONT_ASSET_NAME_PATTERN.match(path.name)),
            unexpected_file_hint=(
                "only <slug>.font.json, <slug>.meta.json, and asset files matching "
                "[A-Za-z0-9][A-Za-z0-9._-]*.(woff2|txt) are allowed in a font entry directory"
            ),
        ),
    }
    # Order pin (T196 review note): precedence order must BE KIND_SUFFIXES' order —
    # a reorder of either side without the other fails here at startup, loudly,
    # instead of letting resolve_kind and build_index silently disagree.
    assert list(specs) == list(KIND_SUFFIXES), (
        f"kind_specs order {list(specs)} != KIND_SUFFIXES order {list(KIND_SUFFIXES)}")
    return specs


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


def validate_theme_font_provenance(manifest_path: Path, slug: str, manifest: object) -> list[str]:
    """SPEC F104.9's unbreakable-themes invariant, catalog-CI half (PLAN T205) — a theme entry
    accepted onto the PUBLIC catalog may reference ONLY VENDORED_FONT_SRCS, never a font-pack face.
    See that constant's own remarks for why: the app's widened, per-station vendored-union-installed
    law (SPEC F104.9/F104.10) governs a station's own theme IMPORT, not what the shared, catalog-wide
    shelf may publish — a catalog theme referencing a pack face would render only on stations that
    happened to install that exact pack, silently 404ing its font everywhere else.

    A HARD gate, same posture as validate_theme_aa next to it: every `fonts.display`/`fonts.sans`
    face's every asset `src` is checked; a single unvendored src rejects the whole entry, naming the
    offending src (never silently accepted, never merely warned about). Defensive against a manifest
    that failed its own schema shape check (missing/malformed `fonts`, a role, or `assets`) — those
    shapes are silently skipped here, not reported as a second violation; the schema check next to
    this call already names that failure once."""
    if not isinstance(manifest, dict):
        return []
    fonts = manifest.get("fonts")
    if not isinstance(fonts, dict):
        return []

    violations: list[str] = []
    for role in ("display", "sans"):
        face = fonts.get(role)
        if not isinstance(face, dict):
            continue
        assets = face.get("assets")
        if not isinstance(assets, list):
            continue
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            src = asset.get("src")
            if isinstance(src, str) and src not in VENDORED_FONT_SRCS:
                violations.append(
                    f"{rel(REPO_ROOT, manifest_path)}: theme-unvendored-font: theme '{slug}' "
                    f"fonts.{role} references font src '{src}', outside GenWave's vendored curated "
                    "set — a catalog theme may never reference a font-pack face (SPEC F104.9's "
                    "unbreakable-themes invariant)"
                )

    return violations


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


def resolve_kind(entry_dir: Path, kind_specs: dict[str, KindSpec]) -> str:
    """"persona", "theme", or "font" — which manifest filename this entry
    directory carries, resolved by walking `kind_specs` in ITS OWN insertion
    order (persona wins if, bizarrely, more than one manifest file is
    present, then theme, then font — SPEC F104.1 / T195) and returning the
    first kind whose `*{suffix}` glob actually matches; none present
    defaults to "persona" (the pre-T179 shape, so the caller reports a
    familiar missing-card violation rather than a new missing-kind one).
    Glob-matched rather than an exact <slug>.* filename so a
    slug-mismatched manifest file is still classified — and then reported
    as a slug-mismatch below, not silently treated as missing.

    AS OF T196, this precedence exactly mirrors tools/build_index.py's own
    resolve_manifest — both derive kind from the identical
    persona-then-theme-then-font manifest-filename convention the app
    itself gates entry file-refs on (GenWave.Host, T176/T195). Before T196,
    that function mirrored only the persona/theme two-thirds of this
    precedence, so a directory this function classified kind:"font"
    validated here but build_index.py silently never emitted an index entry
    for it; resolve_manifest's own comment in tools/build_index.py records
    that history. "This module accepts a font pack" and "build_index.py
    will actually ship it" are the same claim again."""
    for kind, spec in kind_specs.items():
        if any(entry_dir.glob(f"*{spec.suffix}")):
            return kind
    return "persona"


def validate_entry(entry_dir: Path, kind_specs: dict[str, KindSpec]) -> list[str]:
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

    kind = resolve_kind(entry_dir, kind_specs)
    spec = kind_specs[kind]

    allowed_names = {f"{slug}{spec.suffix}", f"{slug}.meta.json"}
    unexpected = sorted(
        p.name for p in entry_dir.iterdir() if p.name not in allowed_names and not spec.allows_extra(p)
    )
    for name in unexpected:
        violations.append(f"{rel(REPO_ROOT, entry_dir / name)}: unexpected-file: {spec.unexpected_file_hint}")

    manifest_candidates = sorted(entry_dir.glob(f"*{spec.suffix}"))
    meta_candidates = sorted(entry_dir.glob("*.meta.json"))

    if len(manifest_candidates) != 1:
        violations.append(
            f"{label}: missing-file: expected exactly one <slug>{spec.suffix}, found {len(manifest_candidates)}"
        )
    if len(meta_candidates) != 1:
        violations.append(
            f"{label}: missing-file: expected exactly one <slug>.meta.json, found {len(meta_candidates)}"
        )

    if len(manifest_candidates) == 1:
        manifest_path = manifest_candidates[0]
        manifest_stem = manifest_path.name[: -len(spec.suffix)]
        if manifest_stem != slug:
            violations.append(
                f"{rel(REPO_ROOT, manifest_path)}: slug-mismatch: filename slug '{manifest_stem}' does not match directory '{slug}'"
            )
        if spec.size_cap is not None:
            violations.extend(check_size_cap(manifest_path, spec.size_cap, spec.label))
        manifest_instance, manifest_parse_violations = parse_json(manifest_path)
        violations.extend(manifest_parse_violations)
        if manifest_instance is not None:
            violations.extend(validate_schema(manifest_path, manifest_instance, spec.manifest_schema))
            if kind == "theme":
                violations.extend(validate_theme_aa(manifest_path, slug, manifest_instance))
                violations.extend(validate_theme_font_provenance(manifest_path, slug, manifest_instance))
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
            violations.extend(validate_schema(meta_path, meta_instance, spec.meta_schema))
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


def validate_entries(entries_dir: Path, kind_specs: dict[str, KindSpec]) -> list[str]:
    if not entries_dir.is_dir():
        return [f"{rel(REPO_ROOT, entries_dir)}: missing-file: entries/ directory not found"]
    violations: list[str] = validate_entries_top_level(entries_dir)
    for entry_dir in discover_entry_dirs(entries_dir):
        violations.extend(validate_entry(entry_dir, kind_specs))
    return violations


def validate_golden_fixture(fixtures_dir: Path, kind_specs: dict[str, KindSpec]) -> list[str]:
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
        violations.extend(validate_json_against(golden_persona_path, kind_specs["persona"].manifest_schema))

    golden_theme_path = fixtures_dir / "golden.theme.json"
    if not golden_theme_path.is_file():
        violations.append(f"{rel(REPO_ROOT, golden_theme_path)}: missing-file: golden theme fixture not found")
    else:
        violations.extend(validate_json_against(golden_theme_path, kind_specs["theme"].manifest_schema))

    golden_font_path = fixtures_dir / "golden.font.json"
    if not golden_font_path.is_file():
        violations.append(f"{rel(REPO_ROOT, golden_font_path)}: missing-file: golden font fixture not found")
    else:
        violations.extend(validate_json_against(golden_font_path, kind_specs["font"].manifest_schema))

    return violations


def validate_index_slug_ownership(index_path: Path, index: object) -> list[str]:
    """Every `card`, `manifest`, `meta`, and `assets[]` path an index entry
    carries must resolve under `entries/<that entry's own slug>/` — nothing
    dangling, nothing borrowed from a sibling entry's directory (T196
    obligation 3, SPEC F104.1). draft-07 JSON Schema has no way to express
    "this string must start with a value computed from a sibling property"
    — schemas/index.schema.json's own path patterns can only pin SHAPE
    (character set, extension), never cross-reference the entry's own
    `slug` — so this Python-side check is the actual home for it. The app's
    own CatalogIndexValidator rejects the WHOLE index the instant one
    entry's file-ref resolves outside its own directory, so CI must catch a
    mismatch here, before it ever reaches the app.

    Defensive throughout (isinstance-guarded at every level): a shape
    violation here is already reported once by the schema check next to
    this call in validate_index, so a malformed `index`/`entries`/entry
    shape is silently skipped rather than raising or double-reporting."""
    if not isinstance(index, dict):
        return []
    entries = index.get("entries")
    if not isinstance(entries, list):
        return []

    violations: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        slug = entry.get("slug")
        if not isinstance(slug, str):
            continue
        owned_prefix = f"entries/{slug}/"

        refs: list[tuple[str, str]] = []
        for field in ("card", "manifest", "meta"):
            ref = entry.get(field)
            if isinstance(ref, dict) and isinstance(ref.get("path"), str):
                refs.append((field, ref["path"]))
        assets = entry.get("assets")
        if isinstance(assets, list):
            for i, asset in enumerate(assets):
                if isinstance(asset, dict) and isinstance(asset.get("path"), str):
                    refs.append((f"assets[{i}]", asset["path"]))

        for field, path in refs:
            if not path.startswith(owned_prefix):
                violations.append(
                    f"{rel(REPO_ROOT, index_path)}: slug-ownership: entry '{slug}' {field} path "
                    f"'{path}' does not resolve under '{owned_prefix}'"
                )
    return violations


def validate_index_duplicate_asset_paths(index_path: Path, index: object) -> list[str]:
    """No two assets within one entry's `assets[]` may share the same `path`
    (T196 review M2). schemas/index.schema.json's `uniqueItems: true` on
    `assets` is FULL-OBJECT uniqueness — draft-07 has no way to pin
    uniqueness on a single property alone — so it only rejects a duplicate
    when `path`/`sha256`/`bytes` all match; two assets sharing a `path` with
    a DIFFERENT `sha256`/`bytes` sail through that schema gate untouched.
    The app dedupes an entry's assets on `path` alone
    (GenWave.Host.Catalog.CatalogIndexValidator.TryValidateAssets' own
    seen-paths set), so that pair would silently lose one asset the instant
    it's parsed app-side — CI must catch it here, before it ever reaches the
    app, the same posture validate_index_slug_ownership takes for its own
    cross-sibling-property constraint (both express something draft-07
    JSON Schema structurally cannot).

    Defensive throughout (isinstance-guarded at every level), same posture
    as validate_index_slug_ownership above: a shape violation here is
    already reported once by the schema check next to this call in
    validate_index, so a malformed `index`/`entries`/`assets` shape is
    silently skipped rather than raising or double-reporting."""
    if not isinstance(index, dict):
        return []
    entries = index.get("entries")
    if not isinstance(entries, list):
        return []

    violations: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        slug = entry.get("slug")
        if not isinstance(slug, str):
            continue
        assets = entry.get("assets")
        if not isinstance(assets, list):
            continue

        first_index_by_path: dict[str, int] = {}
        for i, asset in enumerate(assets):
            if not isinstance(asset, dict):
                continue
            path = asset.get("path")
            if not isinstance(path, str):
                continue
            if path in first_index_by_path:
                violations.append(
                    f"{rel(REPO_ROOT, index_path)}: duplicate-asset-path: entry '{slug}' assets[{first_index_by_path[path]}] "
                    f"and assets[{i}] share path '{path}'"
                )
            else:
                first_index_by_path[path] = i
    return violations


def validate_index(index_path: Path) -> list[str]:
    """Only called for the real repo (see main()) — index.json must exist at
    the repo root, validate against schemas/index.schema.json, AND pass both
    Python-side cross-property checks above: a schema-shape-clean `assets[]`/
    `manifest`/`meta`/`card` path borrowed from a SIBLING entry's directory
    (validate_index_slug_ownership) or two assets within one entry sharing a
    `path` with different `sha256`/`bytes` (validate_index_duplicate_asset_paths)
    would each pass every pattern in schemas/index.schema.json, since
    draft-07 can't express either cross-property constraint — these two
    Python checks are what actually catch them."""
    if not index_path.is_file():
        return [f"{rel(REPO_ROOT, index_path)}: missing-file: index.json not found at repo root"]
    instance, violations = parse_json(index_path)
    if instance is None:
        return violations
    violations += validate_schema(index_path, instance, load_schema("index.schema.json"))
    violations += validate_index_slug_ownership(index_path, instance)
    violations += validate_index_duplicate_asset_paths(index_path, instance)
    return violations


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

    kind_specs = build_kind_specs()

    violations = validate_entries(root / "entries", kind_specs)

    if root == REPO_ROOT:
        violations.extend(validate_golden_fixture(root / "fixtures", kind_specs))
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
