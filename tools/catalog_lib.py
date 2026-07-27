"""Shared helpers for genwave-catalog's tools/ scripts.

The ONE mechanism `tools/validate.py` and `tools/build_index.py` both use for:

  - locating the repo root (`REPO_ROOT`, `SCHEMAS_DIR`)
  - repo/tree-relative POSIX paths (`rel`)
  - discovering entries/<slug>/ directories under an arbitrary root (`discover_entry_dirs`)
  - refusing to trust symlinks under entries/ (`find_symlinks`)

Keeping these in one file means a rule like "entries/ is discovered this way" or
"symlinks are never trusted" is defined exactly once, not once per tool and
liable to drift between the two.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "schemas"


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
