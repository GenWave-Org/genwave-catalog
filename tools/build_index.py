#!/usr/bin/env python3
"""Build index.json at the repo root from entries/ (SPEC F89.2, kind-aware
per SPEC F103.2 / T178, widened to the font kind by F104.1 / T196, widened
to the show kind by F118.1 / T253, widened to the avatar and icon kinds
(plus a persona's own optional avatar sidecar) by F128.1/F128.2/F130.6 / T309).

    { "generatedAt": <ISO date>, "entries": [
        { "slug", "audience", "bestFor" (when present),
          "card": {"path", "sha256"}, "meta": {"path", "sha256"},
          "assets" (when present, SPEC F128.2 — a SINGLE-element array
          carrying the persona's own optional <slug>.avatar.png sidecar
          face, same {path, sha256, bytes} shape every other kind's own
          assets[] uses; absent means no face, no key at all — never an
          empty array) },
        { "slug", "audience", "kind": "theme", "bestFor" (when present),
          "preview" (when present, T191 — mirrors "bestFor"; a theme's meta.json
          always carries it, theme-meta.schema.json requires it, but the
          projection stays a plain presence check rather than an assumption),
          "manifest": {"path", "sha256"}, "meta": {"path", "sha256"} },
        { "slug", "audience", "kind": "font", "bestFor" (when present),
          "manifest": {"path", "sha256"}, "meta": {"path", "sha256"},
          "assets": [{"path", "sha256", "bytes"}, ...] (sorted, real on-disk
          bytes — never the manifest's own declared `files[].bytes`),
          "family" (copied straight off the manifest's own `family` field,
          T196 — STORY-281 AC1) },
        { "slug", "audience", "kind": "show", "bestFor" (when present),
          "manifest": {"path", "sha256"}, "meta": {"path", "sha256"} }
          (SPEC F118.1, T253 — no `assets`/`family`/`preview`: a show entry
          is the minimal `{manifest, meta}` shape, nothing to project beyond
          it; `suggestedPersona`, when present in meta.json, is deliberately
          NOT projected here — it's read directly off the meta file at
          import time, PLAN T254, not needed for a zero-fetch shelf listing),
        { "slug", "audience", "kind": "avatar", "bestFor" (when present),
          "manifest": {"path", "sha256"}, "meta": {"path", "sha256"},
          "assets": [{"path", "sha256", "bytes"}, ...] }
          (sorted, real on-disk bytes — the pack's own PNG items; SPEC
          F128.1 — no `family` equivalent: the shelf card renders from the
          manifest's own `packName` instead, never a projected index field),
        { "slug", "audience", "kind": "icon", "bestFor" (when present),
          "manifest": {"path", "sha256"}, "meta": {"path", "sha256"} }
          (SPEC F130.6 — no `assets`/`family`/`preview`, the same minimal
          shape a show entry gets: licence/provenance live only in
          meta.json, read directly at install time),
        ...
    ] }

`kind` is derived from which manifest filename an entry directory actually
carries — <slug>.persona.json means kind="persona", <slug>.theme.json means
kind="theme", <slug>.font.json means kind="font", <slug>.show.json means
kind="show", <slug>.avatar.json means kind="avatar", <slug>.icon.json means
kind="icon" (resolve_manifest below, walking tools/catalog_lib.py's own
KIND_SUFFIXES) — never from a field inside meta.json, so it can't drift from
the file that's really on disk, and never from the entry's kind FOLDER
either (entries/<kind-folder>/<slug>/, gh-33) — the folder is where the
entry lives, not what it is; tools/validate.py is what gates the two
agreeing (`kind-folder-mismatch`), this module doesn't repeat that check, it
just keeps reading kind off the manifest filename same as always. A persona
entry gets no `kind` key at all (rather than an explicit "persona"): the app
already defaults a missing `kind` to persona (GenWave.Host, T176), so every
entry that existed before T178 keeps its exact pre-existing shape and
rebuilds byte-identical; only a theme, font, show, avatar, or icon entry
gains the new `kind` and `manifest` keys (a font or avatar entry
additionally gains `assets`; a font entry alone additionally gains `family`
when present in its manifest).

Deterministic by construction: entries are sorted by slug, sha256 is computed
over each file's raw bytes, paths are repo-root-relative (never absolute —
F90.2 consumers reject an absolute path), and JSON is serialized with sorted
keys and fixed separators plus a trailing newline. A font or avatar entry's
own `assets[]` is itself sorted (font_asset_paths/avatar_asset_paths,
tools/catalog_lib.py) so this determinism holds for it too. `example-dj` is
excluded (README.md: it's documentation, never shelf stock). Symlinks
anywhere under entries/ abort the build rather than being trusted
(tools/catalog_lib.py).

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

from catalog_lib import (
    KIND_SUFFIXES,
    REPO_ROOT,
    avatar_asset_paths,
    discover_entry_dirs,
    find_symlinks,
    font_asset_paths,
    rel,
)

EXCLUDED_SLUGS = {"example-dj"}  # documentation entry, never shelf stock (README.md)
EMPTY_GENERATED_AT = "1970-01-01"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def asset_ref(root: Path, path: Path) -> dict:
    """The one {path, sha256, bytes} shape every kind's assets[] entry uses
    (font, avatar, and now a persona's own optional sidecar face) — sha256
    and bytes are ALWAYS recomputed from the file on disk, never trusted
    from a manifest's own declared claims (the same "a pack IS its files"
    posture font's own assets[] projection has always held). Factored out
    once three call sites needed the identical three-line dict literal."""
    return {"path": rel(root, path), "sha256": sha256_of(path), "bytes": path.stat().st_size}


def resolve_manifest(entry_dir: Path, slug: str) -> tuple[Path | None, str]:
    """Which manifest file this entry carries, and the `kind` that implies.

    `kind` is read off the filesystem, not off a field inside meta.json:
    which of `tools/catalog_lib.py`'s own `KIND_SUFFIXES` filename suffixes
    is present decides it (the single source of truth for the kind set
    itself — read it there rather than trusting a kind list hand-copied
    into this prose, the exact staleness T196 review M3 already paid for
    once) — walked in `KIND_SUFFIXES`' OWN insertion order (persona wins if,
    bizarrely, more than one manifest file is present, then every other
    kind in that mapping's own order — SPEC F104.1/F118.1/F128.1/F130.6,
    T196/T253/T309), the same ordered mapping tools/validate.py's own
    resolve_kind walks, so the two can no longer drift apart on either the
    suffix spelling or the precedence order (T196 review M3). This is the
    single source of truth for kind — the same filename-per-kind convention
    the app itself gates entry file-refs on (GenWave.Host, T176 — a suffix
    like `.font.json` means kind="font", each inside its own kind-folder
    entry directory, `entries/<KIND_FOLDERS[kind]>/<slug>/` since gh-33's
    per-kind folder nesting) — rather than a second, parallel `kind` value
    recorded in meta.json that could drift from the manifest file actually
    on disk.

    Returns (None, "persona") when none of the six files are present; the
    caller skips the directory in that case (tools/validate.py is the
    source of truth for that shape error, not this function).

    HISTORY: until T196, this function stopped at persona/theme — a
    directory carrying only a *.font.json manifest fell through to
    `return None, "persona"`, so discover_entries' caller saw
    `manifest_path is None` and silently `continue`d past it: a
    schema-valid, tools/validate.py-clean font pack was simply never
    emitted into index.json (no error, no log line), even though
    tools/validate.py's own resolve_kind already classified it kind:"font".
    T196 added the branch below, closing that gap; the OBLIGATIONS block
    ahead of main() records the full six-piece contract T196 delivered
    against.
    """
    for kind, suffix in KIND_SUFFIXES.items():
        candidate = entry_dir / f"{slug}{suffix}"
        if candidate.is_file():
            return candidate, kind
    return None, "persona"


# ============================================================================
# T196 OBLIGATIONS — font-kind index projection (SPEC F104.1). Recorded here
# verbatim at T195 as the contract for T196 to act on directly rather than
# rediscover; kept here UNCHANGED IN SUBSTANCE as the historical record of
# that contract now that T196 has implemented all six pieces — each marked
# DONE below with where it landed:
#
#   1. DONE (T196) — resolve_manifest gains a third branch — a *.font.json
#      file present means kind="font" (mirrors tools/validate.py's
#      resolve_kind, which already had this branch as of T195) — checked
#      after persona/theme, same precedence order. See resolve_manifest
#      above.
#   2. DONE (T196) — discover_entries projects a font entry's `assets[]`
#      from REAL on-disk bytes, not the manifest's own (untrusted,
#      merely-typed) `files[]` — every sibling asset file in the entry
#      directory (font_asset_paths, moved to tools/catalog_lib.py at T196 so
#      both this module and tools/validate.py share one definition of "what
#      counts as a font pack's own asset file"), sorted for determinism,
#      each carrying its own recomputed sha256 (sha256_of, already defined
#      above) and real stat().st_size — never a manifest-declared `bytes`
#      value. See discover_entries below.
#   3. DONE (T196) — tools/validate.py's validate_index gained a
#      slug-ownership cross-check (validate_index_slug_ownership): every
#      `card`, `manifest`, `meta`, AND `assets[]` path an index entry
#      carries must resolve under `entries/<that-entry's-own-slug>/` —
#      nothing dangling, nothing borrowed from a sibling entry's directory.
#   4. DONE (T196) — schemas/index.schema.json's `assets` property gained
#      `uniqueItems: true` (full-object uniqueness, not just distinct
#      paths) — the same posture `files[]`'s duplicate-asset gate already
#      takes one layer down in the pack's own manifest.
#   5. DONE (T196) — discover_entries projects `family` onto a font entry's
#      index record straight off the pack's own manifest `family` field
#      (STORY-281 AC1 reconciliation, T194 review finding — recorded in
#      CatalogFontManifestSerializer's own remarks) — the same `bestFor`/
#      `preview` precedent already used for theme entries above. See
#      discover_entries below.
#   6. DONE (T196) — tools/run_selftest.sh gained an assertion that a built
#      font entry's `assets[]` byte total (summed) matches
#      independently-recomputed on-disk byte totals for the SAME fixture
#      tree — not a hardcoded number — plus a schema-validity check of the
#      freshly built entry against schemas/index.schema.json's
#      `if`/`then`/`else` font branch, the same "green fixture exercises
#      index shape" posture the existing persona/theme selftest sections
#      already have.
# ============================================================================


def discover_entries(root: Path) -> tuple[list[dict], list[str]]:
    """Every entries/<kind-folder>/<slug>/ under root (gh-33) except
    EXCLUDED_SLUGS, sorted by slug, plus the `added` date of each included
    entry's meta.json (the source for generatedAt). The kind folder itself
    is never consulted here — `kind` is (and always has been) read off which
    manifest filename is actually present (resolve_manifest, below), not off
    which directory an entry happens to sit under; tools/validate.py is what
    gates a mismatch between the two, this module just indexes whatever
    validated clean."""
    entries_dir = root / "entries"

    symlinks = find_symlinks(entries_dir)
    if symlinks:
        listing = ", ".join(rel(root, p) for p in symlinks)
        raise SystemExit(f"build_index: refusing to build — symlink(s) found under entries/: {listing}")

    records: list[dict] = []
    added_dates: list[str] = []

    for _kind_folder, entry_dir in discover_entry_dirs(entries_dir):
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
            # SPEC F128.2: a persona entry MAY carry exactly one
            # <slug>.avatar.png sidecar face — projected as a single-element
            # assets[] (the same {path, sha256, bytes} shape font/avatar
            # packs use) ONLY when tools/validate.py's own KindSpec.allows_extra
            # for the persona kind found it on disk; absent means no key at
            # all, the ordinary pre-F128 shape, same "only stamp what's
            # really there" posture `bestFor`/`preview` already follow below.
            sidecar_path = entry_dir / f"{slug}.avatar.png"
            if sidecar_path.is_file():
                record["assets"] = [asset_ref(root, sidecar_path)]
        else:
            record["kind"] = kind
            record["manifest"] = manifest_ref
            if kind == "font":
                # assets[] is projected from what's REALLY on disk (T196
                # obligation 2) — never the manifest's own (untrusted,
                # merely-typed) files[].bytes — sorted for determinism
                # (font_asset_paths, tools/catalog_lib.py, shared with
                # tools/validate.py's validate_font_pack gates).
                record["assets"] = [asset_ref(root, asset_path) for asset_path in font_asset_paths(entry_dir)]
                # `family` is copied straight off the manifest (STORY-281
                # AC1, T196 obligation 5) — required by
                # schemas/font-manifest.schema.json, so, like `audience`
                # above, this is a plain dict access: tools/validate.py is
                # the source of truth for that shape guarantee, the same
                # posture this module already takes throughout.
                manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
                record["family"] = manifest_data["family"]
            elif kind == "avatar":
                # Same "real on-disk bytes, never the manifest's own
                # declared claims" posture as font's own assets[] above —
                # avatar_asset_paths (tools/catalog_lib.py) is the same
                # "what's really on disk is the source of truth" selection
                # tools/validate.py's validate_avatar_pack already uses. No
                # `family` equivalent (SPEC F128.1 has none) — an avatar
                # pack's shelf card renders from `packName` in the manifest
                # itself plus author/description/byte total, never a
                # projected field.
                record["assets"] = [asset_ref(root, asset_path) for asset_path in avatar_asset_paths(entry_dir)]
            # kind == "icon" projects nothing further — the same minimal
            # {kind, manifest, meta} shape a show entry gets (SPEC F130.6):
            # licence/provenance live only in meta.json, read directly at
            # install time, never needed for a zero-fetch shelf listing.
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
