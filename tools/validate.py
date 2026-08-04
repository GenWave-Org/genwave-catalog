#!/usr/bin/env python3
"""Validate genwave-catalog entries against the repo's schemas and format rules.

Rules enforced (all documented as LAW in README.md / SPEC F89.2, kind-aware
per SPEC F103.2 / T179):

  - An entry's `kind` is read off which manifest filename its directory
    carries — <slug>.persona.json means a persona entry, <slug>.theme.json
    means a theme entry — the same filename-per-kind convention
    tools/build_index.py derives `kind` from (persona wins if, bizarrely,
    both are present). An entry with neither is reported as a missing
    persona card, the pre-T179 default.
  - <slug>.persona.json (or <slug>.theme.json) and <slug>.meta.json are each
    valid JSON.
  - A persona's card validates against schemas/persona-card.schema.json; a
    theme's manifest validates against schemas/theme-manifest.schema.json.
  - A persona's meta file validates against schemas/persona-meta.schema.json;
    a theme's meta file validates against schemas/theme-meta.schema.json —
    this is where required fields (`audience`, persona's >=2 `samplePatter`,
    theme's `preview` swatches) are enforced; the schema violation always
    names the offending file.
  - `added` is a real calendar date, not just YYYY-MM-DD shaped (the schema
    pattern lets '9999-99-99' through; datetime.date.fromisoformat doesn't).
  - slug == entry directory name == both filenames' stems.
  - The directory name itself matches ^[a-z0-9]+(-[a-z0-9]+)*$, anchored to
    the absolute end of the string — a trailing newline in the name fails
    this, unlike a bare `$` in Python's re would let through.
  - entries/ contains only <slug>/ directories — no loose files.
  - An entry directory contains only its manifest file (<slug>.persona.json
    or <slug>.theme.json) and <slug>.meta.json — any other file is a
    violation.
  - Nothing under entries/ is a symlink, at any depth (checked before any
    file is read).
  - <slug>.persona.json is <= 256 KiB and <slug>.meta.json is <= 64 KiB. No
    size cap is enforced on <slug>.theme.json — SPEC F103.2 doesn't define
    one and the app itself imposes none on a loaded manifest.
  - fixtures/golden.persona.json (the app-serializer parity artifact) still
    validates against the card schema, and fixtures/golden.theme.json still
    validates against the theme-manifest schema, so neither can silently rot.
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

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*\Z")  # \Z, not $: $ matches before a trailing \n
CARD_SIZE_CAP = 256 * 1024  # bytes; mirrors the app's own import cap (SPEC F79.6)
META_SIZE_CAP = 64 * 1024  # bytes


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
    """"persona" or "theme" — which manifest filename this entry directory
    carries. Mirrors tools/build_index.py's own resolve_manifest precedence:
    a *.persona.json file means "persona" (persona wins if, bizarrely, both
    are present), a *.theme.json file with no *.persona.json means "theme",
    and neither present defaults to "persona" (the pre-T179 shape, so the
    caller reports a familiar missing-card violation rather than a new
    missing-kind one). Glob-matched rather than an exact <slug>.* filename so
    a slug-mismatched manifest file is still classified — and then reported
    as a slug-mismatch below, not silently treated as missing."""
    if any(entry_dir.glob("*.persona.json")):
        return "persona"
    if any(entry_dir.glob("*.theme.json")):
        return "theme"
    return "persona"


def validate_entry(
    entry_dir: Path,
    card_schema: dict,
    persona_meta_schema: dict,
    theme_manifest_schema: dict,
    theme_meta_schema: dict,
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
    else:
        manifest_suffix = ".persona.json"
        manifest_schema = card_schema
        manifest_kind_label = "card"
        meta_schema = persona_meta_schema
        manifest_size_cap = CARD_SIZE_CAP

    allowed_names = {f"{slug}{manifest_suffix}", f"{slug}.meta.json"}
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
        violations.extend(validate_json_against(manifest_path, manifest_schema))

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
) -> list[str]:
    if not entries_dir.is_dir():
        return [f"{rel(REPO_ROOT, entries_dir)}: missing-file: entries/ directory not found"]
    violations: list[str] = validate_entries_top_level(entries_dir)
    for entry_dir in discover_entry_dirs(entries_dir):
        violations.extend(
            validate_entry(entry_dir, card_schema, persona_meta_schema, theme_manifest_schema, theme_meta_schema)
        )
    return violations


def validate_golden_fixture(fixtures_dir: Path, card_schema: dict, theme_manifest_schema: dict) -> list[str]:
    """Only called for the real repo (see main()) — fixtures/ must exist
    there; a testdata root never carries a copy and is never routed here.
    Checks both parity artifacts: golden.persona.json (the app card
    serializer) against the card schema, and golden.theme.json (the app
    manifest serializer) against the theme-manifest schema — either one
    silently drifting from what it's supposed to validate against would mean
    this repo's copy of the app's format has rotted out from under it."""
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

    violations = validate_entries(
        root / "entries", card_schema, persona_meta_schema, theme_manifest_schema, theme_meta_schema
    )

    if root == REPO_ROOT:
        violations.extend(validate_golden_fixture(root / "fixtures", card_schema, theme_manifest_schema))
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
