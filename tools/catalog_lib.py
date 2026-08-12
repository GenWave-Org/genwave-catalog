"""Shared helpers for genwave-catalog's tools/ scripts.

The ONE mechanism `tools/validate.py`, `tools/build_index.py`, and
`tools/lint.py` all use for:

  - locating the repo root (`REPO_ROOT`, `SCHEMAS_DIR`)
  - repo/tree-relative POSIX paths (`rel`)
  - discovering entries/<kind-folder>/<slug>/ directories under an arbitrary
    root (`discover_entry_dirs`) — nested per-kind since gh-33 (previously a
    flat entries/<slug>/)
  - refusing to trust symlinks under entries/ (`find_symlinks`)
  - which sibling files inside a kind:"font" entry directory count as its
    OWN asset files (`FONT_ASSET_NAME_PATTERN`, `font_asset_paths`)
  - the kind -> manifest-filename-suffix mapping, in precedence order
    (`KIND_SUFFIXES`)
  - the kind -> entries/ subfolder name mapping (`KIND_FOLDERS`), the
    physical-layout counterpart to `KIND_SUFFIXES` — a kind's manifest
    filename suffix says what file identifies it; `KIND_FOLDERS` says which
    directory it lives under (gh-33)

Keeping these in one file means a rule like "entries/ is discovered this way" or
"symlinks are never trusted" is defined exactly once, not once per tool and
liable to drift between the two.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "schemas"

# A font pack's own asset files (SPEC F104.1) — closed extension set (woff2
# faces + the pack's OFL licence text), bare filename only (mirrors the app's
# GenWave.Host.Catalog.CatalogIndexValidator.AssetFileNameText exactly).
# Shared by tools/validate.py (validate_font_pack's own asset-set gates) and
# tools/build_index.py (assets[] index projection, T196) so "what counts as a
# font pack's own asset file" is defined exactly once (moved here at T196;
# validate.py carried its own copy from T195 until then).
FONT_ASSET_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.(?:woff2|txt)\Z")

# Kind -> manifest filename suffix, in PRECEDENCE order: persona wins if,
# bizarrely, more than one manifest file is present in an entry directory,
# then theme, then font, then show (SPEC F103.2 / F104.1 / F118.1).
# tools/build_index.py's resolve_manifest and tools/validate.py's
# build_kind_specs both walk THIS one ordered mapping to derive kind from the
# filename actually on disk (T196 review M3) — before this, each tool spelled
# the same kind/suffix/precedence triple out by hand with prose merely
# claiming the two stayed in sync, which is exactly the drift shape this
# epic already paid for once (resolve_manifest's own HISTORY note in
# tools/build_index.py).
KIND_SUFFIXES: dict[str, str] = {
    "persona": ".persona.json",
    "theme": ".theme.json",
    "font": ".font.json",
    "show": ".show.json",
}

# Kind -> entries/ subfolder name (gh-33: entries/<slug>/ moved to
# entries/<kind-folder>/<slug>/, one folder per kind, nested-only — no more
# flat entries/<slug>/). This is the SINGLE SOURCE OF TRUTH for that
# mapping: tools/validate.py reads it to check a physical kind folder agrees
# with the kind its manifest filename suffix implies (KIND_SUFFIXES, above)
# and to compute an index entry's `owned_prefix` for the slug-ownership
# cross-check; tools/build_index.py and tools/lint.py never need the folder
# name itself (they walk whatever discover_entry_dirs hands them, and derive
# `kind` purely from the manifest filename, same as always), but read it
# from here rather than a private copy so a future kind is one dict entry,
# not a dict entry plus N hand-spelled string literals scattered across the
# module. Same key set, same order as KIND_SUFFIXES by construction (no
# runtime assert like KindSpec's own order pin in tools/validate.py — the
# literal dict below is trivially eyeballed against KIND_SUFFIXES two lines
# up).
KIND_FOLDERS: dict[str, str] = {
    "persona": "personas",
    "theme": "themes",
    "font": "fonts",
    "show": "shows",
}


def rel(root: Path, path: Path) -> str:
    """`path` as a POSIX string relative to `root`, falling back to the plain
    string form when `path` isn't actually under `root` (e.g. a diagnostic
    for a file outside the tree being checked)."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def discover_entry_dirs(entries_dir: Path) -> list[tuple[str, Path]]:
    """Every entry directory two levels under entries_dir —
    entries/<kind-folder>/<slug>/ (gh-33; before it, a flat entries/<slug>/,
    one level) — as (kind_folder, entry_dir) pairs, sorted by (kind folder
    name, slug name). Empty list when entries_dir doesn't exist.

    Walks whatever directories are really there at both levels; it does NOT
    filter to KIND_FOLDERS' four known names. That allowlist is
    tools/validate.py's validate_entries_top_level's job, run as a separate
    check — tools/build_index.py and tools/lint.py never call it, and still
    need to see (and, for build_index.py, still index) every entry
    regardless of what its kind folder happens to be named: kind has always
    been derived from the manifest FILENAME inside an entry directory
    (KIND_SUFFIXES), never from the folder it sits in. Keeping this function
    a dumb, symmetric two-level walk — rather than baking KIND_FOLDERS'
    allowlist into it — means those two callers keep behaving exactly as
    they did on the old flat tree: they see every entry, and leave
    "is this directory name actually legal" to validate.py, which is the
    only caller that has ever owned that judgment."""
    if not entries_dir.is_dir():
        return []
    pairs: list[tuple[str, Path]] = []
    for kind_dir in sorted(p for p in entries_dir.iterdir() if p.is_dir()):
        pairs.extend(
            (kind_dir.name, entry_dir) for entry_dir in sorted(p for p in kind_dir.iterdir() if p.is_dir())
        )
    return pairs


def find_symlinks(path: Path) -> list[Path]:
    """`path` itself, or everything under it, restricted to symlinks.

    A directory that is itself a symlink is reported but never descended
    into — no following a symlink outside the repo, no cycles. Callers must
    check this (and act on any hit) BEFORE reading file contents from the
    tree; a symlinked card/meta file could otherwise be used to make the
    tools hash or parse bytes from outside the tree being checked.
    """
    if path.is_symlink():
        return [path]
    if not path.is_dir():
        return []
    hits: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
        base = Path(dirpath)
        for name in list(dirnames) + list(filenames):
            candidate = base / name
            if candidate.is_symlink():
                hits.append(candidate)
    return sorted(hits)


def font_asset_paths(entry_dir: Path) -> list[Path]:
    """Every one of a font entry's OWN asset files — every sibling file in
    its directory matching FONT_ASSET_NAME_PATTERN (the closed woff2|txt
    extension set the app enforces). Sorted for determinism. Both
    tools/validate.py (validate_font_pack's own asset-set gates: ceiling,
    OFL presence, orphan/stowaway) and tools/build_index.py (the assets[]
    index projection, T196) treat "what's actually on disk" as the source
    of truth for a font pack's asset list — never a manifest-declared
    `files[]` value — so they share this one selection here rather than
    each keeping (and risking drifting) their own copy."""
    return sorted(p for p in entry_dir.iterdir() if p.is_file() and FONT_ASSET_NAME_PATTERN.match(p.name))
