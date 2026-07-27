#!/usr/bin/env python3
"""Validate genwave-catalog entries against the repo's schemas and format rules.

Rules enforced (all documented as LAW in README.md / SPEC F89.2):

  - <slug>.persona.json and <slug>.meta.json are each valid JSON.
  - The card validates against schemas/persona-card.schema.json.
  - The meta file validates against schemas/persona-meta.schema.json — this is
    where the required `audience` field and the >=2 `samplePatter` minimum are
    enforced; the schema violation always names the offending file.
  - `added` is a real calendar date, not just YYYY-MM-DD shaped (the schema
    pattern lets '9999-99-99' through; datetime.date.fromisoformat doesn't).
  - slug == entry directory name == both filenames' stems.
  - The directory name itself matches ^[a-z0-9]+(-[a-z0-9]+)*$, anchored to
    the absolute end of the string — a trailing newline in the name fails
    this, unlike a bare `$` in Python's re would let through.
  - entries/ contains only <slug>/ directories — no loose files.
  - An entry directory contains only <slug>.persona.json and <slug>.meta.json
    — any other file is a violation.
  - Nothing under entries/ is a symlink, at any depth (checked before any
    file is read).
  - <slug>.persona.json is <= 256 KiB and <slug>.meta.json is <= 64 KiB.
  - fixtures/golden.persona.json (the app-serializer parity artifact) still
    validates against the card schema, so it can never silently rot.
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


def validate_entry(entry_dir: Path, card_schema: dict, meta_schema: dict) -> list[str]:
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

    allowed_names = {f"{slug}.persona.json", f"{slug}.meta.json"}
    unexpected = sorted(p.name for p in entry_dir.iterdir() if p.name not in allowed_names)
    for name in unexpected:
        violations.append(
            f"{rel(REPO_ROOT, entry_dir / name)}: unexpected-file: only <slug>.persona.json and "
            "<slug>.meta.json are allowed in an entry directory"
        )

    card_candidates = sorted(entry_dir.glob("*.persona.json"))
    meta_candidates = sorted(entry_dir.glob("*.meta.json"))

    if len(card_candidates) != 1:
        violations.append(
            f"{label}: missing-file: expected exactly one <slug>.persona.json, found {len(card_candidates)}"
        )
    if len(meta_candidates) != 1:
        violations.append(
            f"{label}: missing-file: expected exactly one <slug>.meta.json, found {len(meta_candidates)}"
        )

    if len(card_candidates) == 1:
        card_path = card_candidates[0]
        card_stem = card_path.name[: -len(".persona.json")]
        if card_stem != slug:
            violations.append(
                f"{rel(REPO_ROOT, card_path)}: slug-mismatch: filename slug '{card_stem}' does not match directory '{slug}'"
            )
        violations.extend(check_size_cap(card_path, CARD_SIZE_CAP, "card"))
        violations.extend(validate_json_against(card_path, card_schema))

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


def validate_entries(entries_dir: Path, card_schema: dict, meta_schema: dict) -> list[str]:
    if not entries_dir.is_dir():
        return [f"{rel(REPO_ROOT, entries_dir)}: missing-file: entries/ directory not found"]
    violations: list[str] = validate_entries_top_level(entries_dir)
    for entry_dir in discover_entry_dirs(entries_dir):
        violations.extend(validate_entry(entry_dir, card_schema, meta_schema))
    return violations


def validate_golden_fixture(fixtures_dir: Path, card_schema: dict) -> list[str]:
    """Only called for the real repo (see main()) — fixtures/ must exist
    there; a testdata root never carries a copy and is never routed here."""
    if not fixtures_dir.is_dir():
        return [f"{rel(REPO_ROOT, fixtures_dir)}: missing-file: fixtures/ directory not found"]
    golden_path = fixtures_dir / "golden.persona.json"
    if not golden_path.is_file():
        return [f"{rel(REPO_ROOT, golden_path)}: missing-file: golden fixture not found"]
    return validate_json_against(golden_path, card_schema)


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
    meta_schema = load_schema("persona-meta.schema.json")

    violations = validate_entries(root / "entries", card_schema, meta_schema)

    if root == REPO_ROOT:
        violations.extend(validate_golden_fixture(root / "fixtures", card_schema))
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
