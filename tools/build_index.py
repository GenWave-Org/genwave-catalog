#!/usr/bin/env python3
"""Build index.json at the repo root from entries/ (SPEC F89.2, kind-aware
per SPEC F103.2 / T178).

    { "generatedAt": <ISO date>, "entries": [
        { "slug", "audience", "bestFor" (when present),
          "card": {"path", "sha256"}, "meta": {"path", "sha256"} },
        { "slug", "audience", "kind": "theme", "bestFor" (when present),
          "preview" (when present, T191 — mirrors "bestFor"; a theme's meta.json
          always carries it, theme-meta.schema.json requires it, but the
          projection stays a plain presence check rather than an assumption),
          "manifest": {"path", "sha256"}, "meta": {"path", "sha256"} },
        ...
    ] }

`kind` is derived from which manifest filename an entry directory actually
carries — <slug>.persona.json means kind="persona", <slug>.theme.json means
kind="theme" (resolve_manifest below) — never from a field inside
meta.json, so it can't drift from the file that's really on disk. A persona
entry gets no `kind` key at all (rather than an explicit "persona"): the app
already defaults a missing `kind` to persona (GenWave.Host, T176), so every
entry that existed before T178 keeps its exact pre-existing shape and
rebuilds byte-identical; only a theme entry gains both the new `kind` and
`manifest` keys.

Deterministic by construction: entries are sorted by slug, sha256 is computed
over each file's raw bytes, paths are repo-root-relative (never absolute —
F90.2 consumers reject an absolute path), and JSON is serialized with sorted
keys and fixed separators plus a trailing newline. `example-dj` is excluded
(README.md: it's documentation, never shelf stock). Symlinks anywhere under
entries/ abort the build rather than being trusted (tools/catalog_lib.py).

`generatedAt` is derived entirely from the tree being indexed: the max
`added` date across every INCLUDED entry's meta.json, or "1970-01-01" when
there are zero included entries. No git dependency, no wall-clock time — the
same tree in always produces byte-identical output out, no matter what
commit, squash, or rebase history led to it. Every `added` value is parsed
with datetime.date.fromisoformat before it can reach generatedAt — a
shape-valid-but-nonexistent date (e.g. "9999-99-99") aborts the build rather
than being trusted (defense in depth; tools/validate.py is the primary gate).

Usage:
    tools/build_index.py [--root PATH] [--out PATH]
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path

from catalog_lib import REPO_ROOT, discover_entry_dirs, find_symlinks, rel

EXCLUDED_SLUGS = {"example-dj"}  # documentation entry, never shelf stock (README.md)
EMPTY_GENERATED_AT = "1970-01-01"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_manifest(entry_dir: Path, slug: str) -> tuple[Path | None, str]:
    """Which manifest file this entry carries, and the `kind` that implies.

    `kind` is read off the filesystem, not off a field inside meta.json:
    <slug>.persona.json present means kind="persona" (the default,
    pre-F103.2 shape), <slug>.theme.json present means kind="theme". This
    is the single source of truth for kind — the same filename-per-kind
    convention the app itself gates entry file-refs on (GenWave.Host, T176:
    persona -> entries/<slug>/<slug>.persona.json, theme ->
    entries/<slug>/<slug>.theme.json) — rather than a second, parallel
    `kind` value recorded in meta.json that could drift from the manifest
    file actually on disk.

    Returns (None, "persona") when neither file is present; the caller
    skips the directory in that case (tools/validate.py is the source of
    truth for that shape error, not this function).

    *** T196 OBLIGATION — DOES NOT YET HANDLE kind:"font" ***
    Unlike tools/validate.py's own resolve_kind (which already has a third
    *.font.json branch, SPEC F104.1 / T195), THIS function stops at
    persona/theme. A directory carrying only a *.font.json manifest falls
    through to `return None, "persona"` below, so discover_entries' caller
    sees `manifest_path is None` and silently `continue`s past it — a
    schema-valid, tools/validate.py-clean font pack is simply never emitted
    into index.json, no error, no log line. T196 is what adds the
    `*.font.json` branch here (mirroring validate.py's resolve_kind), teaches
    discover_entries to build the `{manifest, assets, family}` record shape
    for it (see the OBLIGATIONS block ahead of main() below), and closes this
    gap. Until T196 ships, do not assume "validate.py accepted this font
    pack" implies "it's on the shelf" — check index.json.
    """
    persona_path = entry_dir / f"{slug}.persona.json"
    if persona_path.is_file():
        return persona_path, "persona"
    theme_path = entry_dir / f"{slug}.theme.json"
    if theme_path.is_file():
        return theme_path, "theme"
    return None, "persona"


# ============================================================================
# T196 OBLIGATIONS — font-kind index projection (SPEC F104.1, closes the gap
# resolve_manifest's own comment above marks). This is where T196's builder
# starts: `discover_entries` below (and resolve_manifest above it) are what a
# theme-kind entry already gets projected through; a font-kind entry needs
# the equivalent treatment, six pieces, recorded here verbatim so T196 can
# act on this list directly rather than rediscovering it:
#
#   1. resolve_manifest gains a third branch — a *.font.json file present
#      means kind="font" (mirrors tools/validate.py's resolve_kind, which
#      already has this branch as of T195) — checked after persona/theme,
#      same precedence order.
#   2. discover_entries projects a font entry's `assets[]` from REAL
#      on-disk bytes, not the manifest's own (untrusted, merely-typed)
#      `files[]` — every sibling asset file in the entry directory
#      (font_asset_paths' own selection logic in tools/validate.py is the
#      precedent: closed woff2|txt extension set), sorted for determinism,
#      each carrying its own recomputed sha256 (sha256_of, already defined
#      above) and real stat().st_size — never trust a manifest-declared
#      `bytes` value for what ships in the index.
#   3. tools/validate.py's validate_index (or an equivalent introduced
#      alongside it) gains a slug-ownership cross-check: every `manifest`,
#      `meta`, AND `assets[]` path an index entry carries must resolve
#      under `entries/<that-entry's-own-slug>/` — nothing dangling, nothing
#      borrowed from a sibling entry's directory.
#   4. schemas/index.schema.json's `assets` property gains `uniqueItems:
#      true` (full-object uniqueness, not just distinct paths) — a font
#      entry's own `assets[]` should never carry the same asset twice, the
#      same posture `files[]`'s duplicate-asset gate already takes one
#      layer down in the pack's own manifest.
#   5. discover_entries projects `family` onto a font entry's index record
#      by reading it straight off the pack's own manifest `family` field
#      (STORY-281 AC1 reconciliation, T194 review finding — recorded in
#      CatalogFontManifestSerializer's own remarks) — the same `bestFor`/
#      `preview` precedent already used for theme entries above.
#   6. tools/run_selftest.sh gains an assertion that a built font entry's
#      `assets[]` byte total (summed) matches independently-recomputed
#      on-disk byte totals for the SAME fixture tree — not a hardcoded
#      number — plus a schema-validity check of the freshly built entry
#      against schemas/index.schema.json's `if`/`then`/`else` font branch,
#      the same "green fixture exercises index shape" posture the existing
#      persona/theme selftest sections already have.
# ============================================================================


def discover_entries(root: Path) -> tuple[list[dict], list[str]]:
    """Every entries/<slug>/ under root except EXCLUDED_SLUGS, sorted by
    slug, plus the `added` date of each included entry's meta.json (the
    source for generatedAt)."""
    entries_dir = root / "entries"

    symlinks = find_symlinks(entries_dir)
    if symlinks:
        listing = ", ".join(rel(root, p) for p in symlinks)
        raise SystemExit(f"build_index: refusing to build — symlink(s) found under entries/: {listing}")

    records: list[dict] = []
    added_dates: list[str] = []

    for entry_dir in discover_entry_dirs(entries_dir):
        slug = entry_dir.name
        if slug in EXCLUDED_SLUGS:
            continue
        manifest_path, kind = resolve_manifest(entry_dir, slug)
        meta_path = entry_dir / f"{slug}.meta.json"
        if manifest_path is None or not meta_path.is_file():
            # tools/validate.py is the source of truth for shape errors; the
            # index build only ever runs on a tree that already passed it.
            continue

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        added = meta["added"]
        try:
            datetime.date.fromisoformat(added)
        except ValueError as exc:
            # Defense in depth: tools/validate.py is the source of truth for
            # this check, but build_index.py is run directly by contributors
            # too, and a shape-valid-but-nonexistent date (e.g. "9999-99-99")
            # would otherwise flow straight into index.json's generatedAt.
            raise SystemExit(
                f"build_index: {rel(root, meta_path)} has an invalid 'added' date {added!r}: {exc}"
            ) from exc

        record = {
            "slug": slug,
            "audience": meta["audience"],
            "meta": {"path": rel(root, meta_path), "sha256": sha256_of(meta_path)},
        }
        manifest_ref = {"path": rel(root, manifest_path), "sha256": sha256_of(manifest_path)}
        if kind == "persona":
            # No `kind` key on a persona entry — the app already defaults a
            # missing `kind` to persona, so this keeps every pre-T178 entry
            # byte-identical rather than gratuitously stamping "persona"
            # onto all of them.
            record["card"] = manifest_ref
        else:
            record["kind"] = kind
            record["manifest"] = manifest_ref
        if "bestFor" in meta:
            record["bestFor"] = meta["bestFor"]
        if "preview" in meta:
            record["preview"] = meta["preview"]
        records.append(record)
        added_dates.append(added)

    records.sort(key=lambda r: r["slug"])
    return records, added_dates


def build_index(root: Path) -> dict:
    records, added_dates = discover_entries(root)
    generated_at = max(added_dates) if added_dates else EMPTY_GENERATED_AT
    return {"generatedAt": generated_at, "entries": records}


def write_index(index: dict, out_path: Path) -> None:
    text = json.dumps(index, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    out_path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="directory containing entries/ to index (default: repo root)",
    )
    parser.add_argument("--out", type=Path, default=None, help="output path (default: <root>/index.json)")
    args = parser.parse_args()

    root = args.root.resolve()
    out_path = args.out if args.out is not None else root / "index.json"

    index = build_index(root)
    write_index(index, out_path)
    count = len(index["entries"])
    print(f"wrote {out_path} ({count} entr{'y' if count == 1 else 'ies'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
