#!/usr/bin/env python3
"""Build index.json at the repo root from entries/ (SPEC F89.2).

    { "generatedAt": <ISO date>, "entries": [
        { "slug", "audience", "bestFor" (when present),
          "card": {"path", "sha256"}, "meta": {"path", "sha256"} },
        ...
    ] }

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
        card_path = entry_dir / f"{slug}.persona.json"
        meta_path = entry_dir / f"{slug}.meta.json"
        if not card_path.is_file() or not meta_path.is_file():
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
            "card": {"path": rel(root, card_path), "sha256": sha256_of(card_path)},
            "meta": {"path": rel(root, meta_path), "sha256": sha256_of(meta_path)},
        }
        if "bestFor" in meta:
            record["bestFor"] = meta["bestFor"]
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
