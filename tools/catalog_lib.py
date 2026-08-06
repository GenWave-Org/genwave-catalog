"""Shared helpers for genwave-catalog's tools/ scripts.

The ONE mechanism `tools/validate.py` and `tools/build_index.py` both use for:

  - locating the repo root (`REPO_ROOT`, `SCHEMAS_DIR`)
  - repo/tree-relative POSIX paths (`rel`)
  - discovering entries/<slug>/ directories under an arbitrary root (`discover_entry_dirs`)
  - refusing to trust symlinks under entries/ (`find_symlinks`)
  - which sibling files inside a kind:"font" entry directory count as its
    OWN asset files (`FONT_ASSET_NAME_PATTERN`, `font_asset_paths`)
  - the kind -> manifest-filename-suffix mapping, in precedence order
    (`KIND_SUFFIXES`)

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
# then theme, then font (SPEC F103.2 / F104.1). tools/build_index.py's
# resolve_manifest and tools/validate.py's build_kind_specs both walk THIS
# one ordered mapping to derive kind from the filename actually on disk
# (T196 review M3) — before this, each tool spelled the same kind/suffix/
# precedence triple out by hand with prose merely claiming the two stayed in
# sync, which is exactly the drift shape this epic already paid for once
# (resolve_manifest's own HISTORY note in tools/build_index.py).
KIND_SUFFIXES: dict[str, str] = {
    "persona": ".persona.json",
    "theme": ".theme.json",
    "font": ".font.json",
}


def rel(root: Path, path: Path) -> str:
    """`path` as a POSIX string relative to `root`, falling back to the plain
    string form when `path` isn't actually under `root` (e.g. a diagnostic
    for a file outside the tree being checked)."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def discover_entry_dirs(entries_dir: Path) -> list[Path]:
    """Every immediate subdirectory of entries_dir, sorted by name. Empty
    list when entries_dir doesn't exist."""
    if not entries_dir.is_dir():
        return []
    return sorted(p for p in entries_dir.iterdir() if p.is_dir())


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
