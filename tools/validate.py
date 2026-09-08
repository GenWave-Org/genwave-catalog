#!/usr/bin/env python3
"""Validate genwave-catalog entries against the repo's schemas and format rules.

Rules enforced (all documented as LAW in README.md / SPEC F89.2, kind-aware
per SPEC F103.2 / T179):

  - An entry's `kind` is read off which manifest filename its directory
    carries — <slug>.persona.json means a persona entry, <slug>.theme.json
    means a theme entry, <slug>.font.json means a font entry (SPEC F104.1 /
    T195), <slug>.show.json means a show entry (SPEC F118.1 / T253) —
    persona wins if, bizarrely, more than one manifest file is present, then
    theme, then font, then show (resolve_kind's own precedence, driven by
    the `kind_specs` dict build_kind_specs() assembles — N5, T196; the
    kind/suffix/precedence triple itself now lives in tools/catalog_lib.py's
    KIND_SUFFIXES, T196 review M3). This is now the SAME convention
    tools/build_index.py's own resolve_manifest derives `kind` from: until
    T196, that function mirrored only the persona/theme half —
    it did not resolve a `.font.json` manifest at all — so a directory this
    module classified kind:"font" validated here but build_index.py silently
    skipped it (never emitted an index entry for it). T196 closed that gap
    (resolve_manifest's own comment in tools/build_index.py records the
    history). An entry with none of the six manifest filenames is reported
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
  - An avatar pack (kind:\"avatar\", <slug>.avatar.json, SPEC F128.1), on top
    of its own schema check: every shipped PNG (every sibling file matching
    the app's own bare-filename `.png` extension set) is verified by MAGIC
    BYTES (never extension), must have an IHDR declaring exactly 512x512,
    must be <= 512 KiB, and must not be an animated PNG (an `acTL` chunk
    before the first `IDAT` is rejected); the pack's PNG assets, summed,
    must be <= 6 MiB; every `items[]` element's `name` must be unique within
    the pack; every `file` an item names must correspond to a PNG the entry
    actually ships (orphan), and — the reverse — every shipped PNG must be
    named by some item's `file` (stowaway). All HARD gates
    (tools/validate.py's `validate_avatar_pack`/`validate_png_asset`).
  - A PERSONA entry (SPEC F128.2) may additionally carry exactly one
    `<slug>.avatar.png` sidecar face, held to the identical per-item PNG
    rules an avatar pack's own items get (`validate_persona_avatar_sidecar`).
  - An icon pack (kind:\"icon\", <slug>.icon.json, SPEC F130.1/F130.6) is the
    one manifest in this repo whose full closed shape lives in JSON Schema
    itself (schemas/icon-manifest.schema.json), ported from the app's own
    GenWave.Host.Icons.IconPackDefinitionParser: a closed seven-tag SVG
    primitive whitelist, each tag's own closed (additionalProperties:false)
    attribute set, the `d`/`points` character grammars, `fill`/`stroke`
    restricted to `none`|`currentColor`, the icon-name character/length gate,
    and the 512-icon/64-element-per-icon bounds. tools/validate.py adds what
    JSON Schema structurally cannot express: every numeric geometry
    attribute must be FINITE (a JSON literal like `1e400` is schema-valid
    but overflows to a non-finite float once parsed,
    `validate_icon_numeric_finite`), the <= 256 KiB definition-size cap
    (wired through the same `KindSpec.size_cap` mechanism the persona card
    uses), and the F1 ruling: a `license`/`licence` member found inside the
    manifest itself is a HARD reject — licence/provenance belongs in the
    companion `<slug>.meta.json` ONLY (`validate_icon_licence_not_in_manifest`;
    schemas/icon-meta.schema.json requires `license`+`sourceUrl` there).
  - An ad pack (kind:\"ad-pack\", <slug>.ad-pack.json, SPEC F162.2) is DATA
    ONLY — `packName` plus `briefs[]` of fictional-brand briefs the station's
    own LLM writes parody spots from. schemas/ad-pack-manifest.schema.json
    mirrors the app's CatalogAdPackManifestSerializer caps (1-100 briefs,
    brand 1-200 non-blank chars, each hint <= 500 chars, closed member sets).
    tools/validate.py adds the one cross-item rule JSON Schema cannot
    express: no two briefs in a pack may share a brand after case/whitespace
    folding (`validate_ad_pack` — the app upserts keyed (pack_slug, brand),
    so an exact duplicate silently overwrites, and a case-only variant would
    list as two brands), plus the <= 256 KiB manifest-size cap (the app's
    own manifest fetch cap, CatalogProxyService.MaxCardBytes — reachable by
    a schema-valid document only through whitespace padding, but reachable).
  - A voice pack (kind:\"voice-pack\", <slug>.voice-pack.json, SPEC F164) ships
    kokoro voice weights (`<voiceId>.pt`, a torch zip archive this module NEVER
    unpickles — only its magic bytes and size are ever read) plus one
    `<slug>.preview.mp3` clip. schemas/voice-pack-manifest.schema.json pins the
    closed shape (engine locked to \"kokoro\", `synthetic` pinned true,
    `sourceRef` null-or-absent only); tools/validate.py adds what JSON Schema
    cannot express: every `voices[].file` exists, is a real zip archive, <=
    1 MiB (`voice-pack-pt-over-max`), summed <= 8 MiB (`voice-pack-over-ceiling`);
    no duplicate `voiceId` (`voice-pack-duplicate-voice`); `file` equals
    `<voiceId>.pt` exactly (`voice-pack-file-mismatch`); the preview exists, is a
    real MP3, <= 150 KiB (`voice-pack-preview-over-max`), and its name equals
    `<slug>.preview.mp3` (`voice-pack-preview-name`); and the same orphan/stowaway
    "a pack IS its files" posture validate_font_pack/validate_avatar_pack already
    take (`voice-pack-orphan-file`; a wrongly-named stowaway is the ordinary
    unexpected-file gate). All HARD gates (`validate_voice_pack`).
  - A jingle pack (kind:\"jingle-pack\", <slug>.jingle-pack.json, SPEC F165) ships
    background music beds, stings, and station IDs (`role`) as wav/mp3/flac
    assets. schemas/jingle-pack-manifest.schema.json pins the closed shape
    (license closed to CC0/CC-BY, a per-item `if`/`then` requiring `attribution`
    iff `license == \"CC-BY\"` and forbidding it for CC0 — STORY-400 AC1);
    tools/validate.py adds what JSON Schema cannot express: every asset's
    declared `sha256` matches the file on disk (`jingle-pack-sha256-mismatch`),
    the bytes match the extension's own magic (`jingle-pack-audio-magic`), <=
    5 MiB per asset (`jingle-pack-asset-over-max`), summed <= 40 MiB (a ruling,
    `jingle-pack-over-ceiling` — no ceiling is specified by SPEC F165 itself, so
    this mirrors the font/avatar/voice-pack precedent of a summed-pack bound
    rather than leaving one kind alone unbounded), no duplicate `file` or
    case/whitespace-folded `title` (`jingle-pack-duplicate-asset`, the same fold
    `fold_brand` already applies for ad-pack brands), and the same orphan/
    stowaway posture as every other pack kind (`jingle-pack-orphan-audio`). All
    HARD gates (`validate_jingle_pack`).
  - `added` is a real calendar date, not just YYYY-MM-DD shaped (the schema
    pattern lets '9999-99-99' through; datetime.date.fromisoformat doesn't).
  - slug == entry directory name == both filenames' stems.
  - The directory name itself matches ^[a-z0-9]+(-[a-z0-9]+)*$, anchored to
    the absolute end of the string — a trailing newline in the name fails
    this, unlike a bare `$` in Python's re would let through.
  - entries/ is nested by kind (gh-33): it may only contain the kind folders
    named in `tools/catalog_lib.py`'s own `KIND_FOLDERS` mapping (the single
    source of truth for that set — read it there rather than trusting a
    count hand-copied into this prose, the exact staleness gh-33/T196 review
    M3 already paid for once), as directories, nothing else; each kind
    folder may in turn only contain <slug>/ directories, no loose files. A
    missing or empty kind folder is not itself a violation.
  - An entry's kind FOLDER agrees with the kind its manifest filename suffix
    implies — a `.persona.json` manifest sitting under `entries/shows/`
    (say) is a `kind-folder-mismatch` violation, even though the manifest
    itself is otherwise perfectly valid. The manifest filename suffix stays
    kind's actual source of truth (unchanged by gh-33); the folder is
    metadata ABOUT that truth, and the two must agree.
  - A slug is unique across every kind folder — two kind folders each
    holding a `<the-same-slug>/` directory is a hard violation, since
    `index.json`'s entries (and the app importing them) key an entry on its
    slug alone, never on slug+kind.
  - An entry directory contains only its manifest file (<slug>.persona.json,
    <slug>.theme.json, <slug>.font.json, or <slug>.show.json) and
    <slug>.meta.json — plus, ONLY for a font entry, its own asset files
    (woff2 faces + OFL.txt) — any other file is a violation.
  - Nothing under entries/ is a symlink, at any depth (checked before any
    file is read) — including a kind folder itself, one level above where a
    <slug> entry directory sits since gh-33's nesting.
  - <slug>.persona.json is <= 256 KiB and <slug>.meta.json is <= 64 KiB. No
    size cap is enforced on <slug>.theme.json, <slug>.font.json, or
    <slug>.show.json — SPEC F103.2/F104.2/F118.1 don't define one on the
    manifest text itself and the app imposes none on a loaded manifest (a
    font pack's own per-pack asset ceiling is a separate, asset-summed rule
    — see above).
  - fixtures/golden.persona.json (the app-serializer parity artifact) still
    validates against the card schema, fixtures/golden.theme.json still
    validates against the theme-manifest schema, fixtures/golden.font.json
    still validates against the font-manifest schema, and
    fixtures/golden.show.json still validates against the show-manifest
    schema, so none of the four can silently rot.
  - index.json exists at the repo root and validates against
    schemas/index.schema.json — this and the fixtures/ check above only ever
    run against the real repo (see --root below), never a testdata root.
  - Every index.json entry's `card`/`manifest`/`meta`/`assets[]` path
    resolves under `entries/<that entry's own kind folder>/<that entry's own
    slug>/` — nothing dangling, nothing borrowed from a sibling entry's
    directory (T196, SPEC F104.1, folder segment added gh-33 — draft-07 JSON
    Schema has no way to express a cross-sibling-property constraint like
    this, so validate_index_slug_ownership is the actual gate;
    schemas/index.schema.json's own patterns can only pin path SHAPE).
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
  - Every index.json entry's `card`/`manifest`/`meta`/`assets[]` own declared
    `sha256` (and `bytes`, for `assets[]`) matches the REAL file sitting on disk
    at that path (T411): neither cross-check above ever opens the file a path
    names, so a stale or hand-edited claim would otherwise sail through both
    untouched. validate_index_asset_integrity is the actual gate — added at
    T411 alongside the voice-pack/jingle-pack kinds, since it is not specific to
    either and closes a gap that predates both.

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
import hashlib
import json
import math
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import jsonschema

from catalog_lib import (
    AVATAR_ASSET_NAME_PATTERN,
    FONT_ASSET_NAME_PATTERN,
    JINGLE_ASSET_NAME_PATTERN,
    KIND_FOLDERS,
    KIND_SUFFIXES,
    REPO_ROOT,
    SCHEMAS_DIR,
    VOICE_ASSET_NAME_PATTERN,
    avatar_asset_paths,
    discover_entry_dirs,
    find_symlinks,
    font_asset_paths,
    jingle_asset_paths,
    rel,
    voice_asset_paths,
)
from contrast import check_theme_aa
from png_image import has_animation_chunk, has_signature, try_read_dimensions

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

# SPEC F128.1's avatar-pack byte ceilings — per-item (an avatar pack's own PNG,
# OR a persona entry's own sidecar face, SPEC F128.2's "same per-item
# validation") and per-pack (summed across every item an avatar pack ships;
# a persona's own single sidecar face is never summed against this — it has
# no siblings to sum with).
AVATAR_ITEM_BYTE_CEILING = 512 * 1024  # 524,288 bytes
AVATAR_PACK_BYTE_CEILING = 6 * 1024 * 1024  # 6,291,456 bytes

# The <slug>.avatar.json manifest TEXT itself (as opposed to the PNG items it
# names, bounded above) is fetched through the SAME app-side path every other
# kind's own card/manifest text is: GenWave.Host.Catalog.CatalogProxyService.
# FetchAndVerifyEntryAsync bounds EVERY entry's manifest fetch to MaxCardBytes
# (256 KiB) regardless of kind — the identical magnitude CARD_SIZE_CAP already
# mirrors for the persona kind, though that constant's own comment cites a
# DIFFERENT app-side cap (the persona IMPORT flow's own bound, SPEC F79.6) —
# so this gets its own named constant rather than reusing CARD_SIZE_CAP under
# a citation that wouldn't actually describe it. Rider fold 4 (T309 review):
# F1's own maxItems:64 on avatar-manifest.schema.json's `items[]` already
# bounds a real-world manifest's text size practically (64 items' worth of
# name/file/suggestedPersona strings falls far short of 256 KiB long before
# this cap would ever bind) — this is defense in depth against a
# pathologically verbose manifest, not the primary gate.
AVATAR_MANIFEST_SIZE_CAP = 256 * 1024  # bytes; mirrors CatalogProxyService.MaxCardBytes

# SPEC F130.1's icon pack definition-size cap (GenWave.Host.Icons.
# IconPackDefinitionParser.MaxDefinitionBytes) — wired through KindSpec.size_cap
# below, the same mechanism CARD_SIZE_CAP already uses for the persona kind.
ICON_DEFINITION_SIZE_CAP = 256 * 1024  # 262,144 bytes

# SPEC F130.6's F1 ruling (amended 2026-08-16 at the T305 review): an icon
# pack's licence/provenance belongs ONLY in the companion <slug>.meta.json.
# Both spellings are gated — this codebase's own prose favours "licence"
# (British) while every OTHER kind's actual schema field is spelled
# "license" (American, e.g. schemas/font-manifest.schema.json) — a
# contributor copying either convention into <slug>.icon.json is caught.
ICON_LICENCE_KEYS = ("license", "licence")

# SPEC F162.2's ad-pack manifest rides the app's ordinary manifest fetch cap
# (GenWave.Host.Catalog.CatalogProxyService.MaxCardBytes, 256 KiB — the SAME
# number every non-persona manifest is fetched under) — wired through
# KindSpec.size_cap like the icon definition cap above. The schema's own
# caps (100 briefs x (200 + 3 x 500) chars) keep any REAL pack far below it;
# only whitespace padding can reach it, which is exactly why the cap stays a
# validate.py gate rather than being left to the schema.
AD_PACK_MANIFEST_SIZE_CAP = 256 * 1024  # 262,144 bytes

# SPEC F164's voice-pack byte ceilings (T411): per-.pt-weight, summed pack,
# and preview clip. The preview number mirrors the app's own
# Packs:PreviewMaxBytes default; there is no app-side per-weight or
# per-pack config to mirror (kokoro's own export size sets the practical
# floor), so those two are catalog-only ceilings, same posture as
# FONT_PACK_BYTE_CEILING/AVATAR_PACK_BYTE_CEILING before them.
VOICE_PACK_PT_BYTE_CEILING = 1024 * 1024  # 1,048,576 bytes per .pt weight
VOICE_PACK_PACK_BYTE_CEILING = 8 * 1024 * 1024  # 8,388,608 bytes summed
VOICE_PACK_PREVIEW_BYTE_CEILING = 150 * 1024  # 153,600 bytes; = Packs:PreviewMaxBytes

# SPEC F165's jingle-pack byte ceilings (T411): per-asset mirrors the app's
# own Packs:JingleAssetMaxBytes default; the summed-pack ceiling is a
# catalog ruling (SPEC F165 itself sets none) mirroring the font/avatar/
# voice-pack precedent of bounding a pack's total footprint, not just its
# individual items — see validate_jingle_pack's own docstring.
JINGLE_PACK_ASSET_BYTE_CEILING = 5 * 1024 * 1024  # 5,242,880 bytes
JINGLE_PACK_PACK_BYTE_CEILING = 40 * 1024 * 1024  # 41,943,040 bytes summed


def has_zip_magic(data: bytes) -> bool:
    """A kokoro voice weight (`.pt`) is a torch archive, which is a ZIP
    container under the hood — checked by its local-file-header magic ONLY
    (`PK\x03\x04`), never by unzipping or unpickling it: the file is
    untrusted pickle end to end, so this module treats it as opaque bytes,
    exactly like PngImageHeader treats a PNG's own signature as the whole
    story for "is this the format it claims to be"."""
    return data[:4] == b"PK\x03\x04"


def has_mp3_magic(data: bytes) -> bool:
    """An MP3's bytes either open with an `ID3` tag or, tag-less, the first
    frame's own 11-bit sync word (the top byte 0xFF followed by a second
    byte whose top three bits are all set, `& 0xE0 == 0xE0`) — the same two
    shapes ffmpeg itself emits depending on whether it writes an ID3v2
    header, and the only two this module bothers to recognise."""
    if data[:3] == b"ID3":
        return True
    return len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0


def has_wav_magic(data: bytes) -> bool:
    """A WAV file's own RIFF/WAVE container header: `RIFF` at offset 0, a
    4-byte little-endian chunk size (not itself checked — ffmpeg's own
    output is trusted to be internally consistent; this module only ever
    asks "is this a WAV", never "is this a WELL-FORMED WAV"), then `WAVE`
    at offset 8."""
    return data[:4] == b"RIFF" and data[8:12] == b"WAVE"


def has_flac_magic(data: bytes) -> bool:
    """A FLAC stream's fixed 4-byte marker."""
    return data[:4] == b"fLaC"


# extension -> (this file's audio-format check, the human name used in a
# jingle-pack-audio-magic violation) — one dict rather than an if/elif
# ladder inside validate_jingle_pack, mirroring KindSpec's own "one
# structure instead of a ladder" posture (T196 review N5). Keyed on the
# extension actually recovered from `file`, which schemas/jingle-pack-
# manifest.schema.json's own pattern already closed to exactly these three.
JINGLE_AUDIO_MAGIC_CHECKS: dict[str, tuple[Callable[[bytes], bool], str]] = {
    "wav": (has_wav_magic, "RIFF/WAVE"),
    "mp3": (has_mp3_magic, "ID3 or an MPEG sync word"),
    "flac": (has_flac_magic, "fLaC"),
}

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
    F104.1 font, F118.1 show): the manifest filename suffix, a
    human-readable label for error messages, the manifest/meta schema pair,
    the manifest's own size cap (persona only — see CARD_SIZE_CAP), a
    predicate for which EXTRA sibling files an entry directory of this kind
    may carry beyond its own manifest/meta (font only: its own asset files),
    and the exact wording used when a file fails that allowance.

    ONE dict of these (see build_kind_specs) replaces what used to be three
    separate per-kind ladders (N5, T196 review finding): resolve_kind's own
    glob chain, the if/elif/else inside validate_entry that picked out
    manifest_suffix/manifest_schema/meta_schema/size_cap by hand, and the
    allowed-names if/else next to it that special-cased font's extra asset
    files. Each of the three now reads off this one structure instead of
    re-enumerating persona/theme/font/show independently — a new kind is one
    new dict entry, not three new branches."""

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
    theme, then font, then show — the exact precedence this module has
    always documented (persona wins if, bizarrely, more than one manifest
    file is present in an entry directory). Each entry's `suffix` is read
    off tools/catalog_lib.py's KIND_SUFFIXES — the same ordered mapping
    tools/build_index.py's resolve_manifest walks — rather than being
    hand-spelled here a second time (T196 review M3)."""
    specs = {
        "persona": KindSpec(
            suffix=KIND_SUFFIXES["persona"],
            label="card",
            manifest_schema=load_schema("persona-card.schema.json"),
            meta_schema=load_schema("persona-meta.schema.json"),
            size_cap=CARD_SIZE_CAP,
            # SPEC F128.2: a persona entry MAY carry exactly one <slug>.avatar.png
            # sidecar face. allows_extra only ever admits THAT one exact filename
            # (path.parent.name is the entry directory's own name — the slug
            # every other check in validate_entry already keys off) — any other
            # extra file, including a differently-named PNG, still falls through
            # to the ordinary unexpected-file violation below.
            allows_extra=lambda path: path.is_file() and path.name == f"{path.parent.name}.avatar.png",
            unexpected_file_hint=(
                "only <slug>.persona.json, <slug>.meta.json, and an optional <slug>.avatar.png sidecar "
                "face are allowed in an entry directory"
            ),
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
        "show": KindSpec(
            suffix=KIND_SUFFIXES["show"],
            label="show manifest",
            manifest_schema=load_schema("show-manifest.schema.json"),
            meta_schema=load_schema("show-meta.schema.json"),
            size_cap=None,  # SPEC F118.1 defines none on the manifest text itself, same posture as theme/font
            allows_extra=lambda path: False,
            unexpected_file_hint="only <slug>.show.json and <slug>.meta.json are allowed in an entry directory",
        ),
        "avatar": KindSpec(
            suffix=KIND_SUFFIXES["avatar"],
            label="avatar manifest",
            manifest_schema=load_schema("avatar-manifest.schema.json"),
            meta_schema=load_schema("avatar-meta.schema.json"),
            size_cap=AVATAR_MANIFEST_SIZE_CAP,  # icon-style parity (rider fold 4, T309 review) — see that constant's own remarks
            allows_extra=lambda path: path.is_file() and bool(AVATAR_ASSET_NAME_PATTERN.match(path.name)),
            unexpected_file_hint=(
                "only <slug>.avatar.json, <slug>.meta.json, and asset files matching "
                "[A-Za-z0-9][A-Za-z0-9._-]*.png are allowed in an avatar entry directory"
            ),
        ),
        "icon": KindSpec(
            suffix=KIND_SUFFIXES["icon"],
            label="icon pack definition",
            manifest_schema=load_schema("icon-manifest.schema.json"),
            meta_schema=load_schema("icon-meta.schema.json"),
            size_cap=ICON_DEFINITION_SIZE_CAP,  # SPEC F130.1's own 256 KiB definition cap
            allows_extra=lambda path: False,
            unexpected_file_hint="only <slug>.icon.json and <slug>.meta.json are allowed in an entry directory",
        ),
        "ad-pack": KindSpec(
            suffix=KIND_SUFFIXES["ad-pack"],
            label="ad-pack manifest",
            manifest_schema=load_schema("ad-pack-manifest.schema.json"),
            meta_schema=load_schema("ad-pack-meta.schema.json"),
            size_cap=AD_PACK_MANIFEST_SIZE_CAP,  # the app's manifest fetch cap — see that constant's own remarks
            allows_extra=lambda path: False,
            unexpected_file_hint="only <slug>.ad-pack.json and <slug>.meta.json are allowed in an entry directory",
        ),
        "voice-pack": KindSpec(
            suffix=KIND_SUFFIXES["voice-pack"],
            label="voice-pack manifest",
            manifest_schema=load_schema("voice-pack-manifest.schema.json"),
            meta_schema=load_schema("voice-pack-meta.schema.json"),
            size_cap=None,  # SPEC F164 defines none on the manifest text itself; see validate_voice_pack
            allows_extra=lambda path: path.is_file() and bool(VOICE_ASSET_NAME_PATTERN.match(path.name)),
            unexpected_file_hint=(
                "only <slug>.voice-pack.json, <slug>.meta.json, and asset files matching "
                "[a-z0-9][a-z0-9_.-]*.(pt|mp3) are allowed in a voice-pack entry directory"
            ),
        ),
        "jingle-pack": KindSpec(
            suffix=KIND_SUFFIXES["jingle-pack"],
            label="jingle-pack manifest",
            manifest_schema=load_schema("jingle-pack-manifest.schema.json"),
            meta_schema=load_schema("jingle-pack-meta.schema.json"),
            size_cap=None,  # SPEC F165 defines none on the manifest text itself; see validate_jingle_pack
            allows_extra=lambda path: path.is_file() and bool(JINGLE_ASSET_NAME_PATTERN.match(path.name)),
            unexpected_file_hint=(
                "only <slug>.jingle-pack.json, <slug>.meta.json, and asset files matching "
                "[a-z0-9][a-z0-9._-]*.(wav|mp3|flac) are allowed in a jingle-pack entry directory"
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


def index_schema_failed_entry_indices(instance: object, schema: dict) -> frozenset[int]:
    """T411 review round 1, finding 2: the set of top-level `entries[]`
    indices with at least one schemas/index.schema.json violation, fed to
    validate_index_asset_integrity so it never resolves-and-hashes a `path`
    string belonging to an entry the schema already rejected (a schema-
    rejected `path` — e.g. one that never matched the closed per-kind
    pattern, such as a `..`-escaping string — is not a value this script
    should trust enough to join onto a filesystem root and read). A second,
    independent re-run of `iter_errors` rather than a shared call with
    validate_schema above: index.json is small (a build artifact, not
    user input at scale), and keeping this function free of validate_schema's
    own string-formatting keeps each function's one job legible."""
    validator_cls = jsonschema.validators.validator_for(schema)
    validator = validator_cls(schema)
    indices: set[int] = set()
    for error in validator.iter_errors(instance):
        if len(error.path) >= 2 and error.path[0] == "entries" and isinstance(error.path[1], int):
            indices.add(error.path[1])
    return frozenset(indices)


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


def validate_png_asset(path: Path, label: str, rule_prefix: str, max_bytes: int) -> list[str]:
    """Deep PNG validation (SPEC F128.1) shared by an avatar pack's own items
    (validate_avatar_pack) AND a persona entry's own optional sidecar face
    (validate_persona_avatar_sidecar, SPEC F128.2's "same per-item
    validation") — magic bytes (never extension), IHDR exactly 512x512,
    <= max_bytes, and acTL (APNG) reject. Ported from the app's own
    GenWave.Host.Images.PngImageHeader (tools/png_image.py is that port) so
    catalog CI holds the identical shape the app's own upload pipeline (SPEC
    F128.6) and avatar-pack install re-validation (SPEC F128.3) already do.
    `rule_prefix` distinguishes an avatar-pack-item finding from a
    persona-sidecar finding in the violation id, since the two share every
    other rule but the paragraph a reviewer reads should say which."""
    violations: list[str] = []
    data = path.read_bytes()

    if not has_signature(data):
        violations.append(
            f"{label}: {rule_prefix}-png-magic: '{path.name}' is not a PNG file (bad magic bytes) — "
            "the file extension is never trusted"
        )
        return violations  # further structural reads are meaningless on non-PNG bytes

    dims = try_read_dimensions(data)
    if dims is None:
        violations.append(f"{label}: {rule_prefix}-png-ihdr: '{path.name}' has no readable IHDR chunk")
    elif dims != (512, 512):
        width, height = dims
        violations.append(
            f"{label}: {rule_prefix}-png-dimensions: '{path.name}' is {width}x{height}, not exactly 512x512"
        )

    size = len(data)
    if size > max_bytes:
        violations.append(
            f"{label}: {rule_prefix}-png-oversize: '{path.name}' is {size} bytes, over the {max_bytes}-byte cap"
        )

    if has_animation_chunk(data):
        violations.append(
            f"{label}: {rule_prefix}-png-actl: '{path.name}' is an animated PNG (acTL chunk present before "
            "the first IDAT) — APNG faces are rejected"
        )

    return violations


def validate_binary_asset(
    data: bytes,
    file_name: str,
    label: str,
    magic_check: Callable[[bytes], bool],
    magic_rule: str,
    magic_human: str,
    over_max_rule: str,
    max_bytes: int,
    over_max_suffix: str = "cap",
) -> list[str]:
    """T411 review round 1 advisory: the non-PNG sibling of validate_png_asset
    just above — magic bytes (never the extension) plus a byte ceiling,
    the two checks voice-pack's own `.pt` weight and `.mp3` preview
    validation duplicated near-verbatim before this extraction. Takes
    already-read `data` rather than a `Path` (the caller already needed the
    bytes in hand for its own sha256/running-total bookkeeping in at least
    one call site — jingle-pack's own per-asset loop — so this avoids a
    second read there). `magic_rule`/`over_max_rule` are full violation ids,
    not a shared prefix + fixed suffix: voice-pack's own two call sites
    happen to share a stem (`voice-pack-pt-magic`/`voice-pack-pt-over-max`)
    but jingle-pack's own pair doesn't (`jingle-pack-audio-magic`/
    `jingle-pack-asset-over-max`), so a single `rule_prefix` can't name
    both correctly for every caller."""
    violations: list[str] = []
    if not magic_check(data):
        violations.append(
            f"{label}: {magic_rule}: '{file_name}' is not {magic_human} (bad magic bytes) — "
            "the file extension is never trusted"
        )
    size = len(data)
    if size > max_bytes:
        violations.append(
            f"{label}: {over_max_rule}: '{file_name}' is {size} bytes, over the {max_bytes}-byte {over_max_suffix}"
        )
    return violations


def validate_avatar_pack(entry_dir: Path, slug: str, manifest: object) -> list[str]:
    """Avatar pack gates (SPEC F128.1), on top of the schema check next to
    this call — mirrors validate_font_pack's own structure and "a pack IS
    its files" posture:

      - every shipped PNG (avatar_asset_paths) passes validate_png_asset's
        own four checks (magic bytes, IHDR 512x512, <= 512 KiB per item,
        acTL reject);
      - the pack's own PNG assets sum to <= the 6 MiB per-pack ceiling
        (AVATAR_PACK_BYTE_CEILING);
      - every item `name` is unique within the pack ("item names unique");
      - every item `file` names actually exists as one of those assets (an
        "orphan" reference — an item naming a PNG the entry doesn't ship —
        is malformed, mirroring validate_font_pack's own orphan gate);
      - the REVERSE of the orphan check: every physical PNG the entry ships
        is accounted for by some item's `file` — an unreferenced PNG is a
        stowaway, just as malformed as an item pointing at nothing.

    A missing/empty asset set is reported even when the manifest itself
    failed to parse as an object; the name-uniqueness/orphan/stowaway checks
    all need a parsed dict (`items`, even an absent/empty one, to know
    what's declared) and are skipped, not reported as new violations, when
    it isn't one — the schema check next to this call already names that
    shape failure once."""
    label = rel(REPO_ROOT, entry_dir)
    violations: list[str] = []

    assets = avatar_asset_paths(entry_dir)
    asset_names = {p.name for p in assets}

    if not assets:
        violations.append(f"{label}: avatar-no-assets: avatar pack ships zero PNG assets")

    for asset_path in assets:
        violations.extend(validate_png_asset(asset_path, label, "avatar", AVATAR_ITEM_BYTE_CEILING))

    total_bytes = sum(p.stat().st_size for p in assets)
    if total_bytes > AVATAR_PACK_BYTE_CEILING:
        violations.append(
            f"{label}: avatar-pack-ceiling: summed asset bytes {total_bytes} exceeds the "
            f"{AVATAR_PACK_BYTE_CEILING}-byte per-pack ceiling (SPEC F128.1)"
        )

    if not isinstance(manifest, dict):
        return violations

    items = manifest.get("items")
    declared_files: list[str] = []
    if isinstance(items, list):
        declared_names = [
            item["name"] for item in items if isinstance(item, dict) and isinstance(item.get("name"), str)
        ]
        declared_files = [
            item["file"] for item in items if isinstance(item, dict) and isinstance(item.get("file"), str)
        ]

        seen_names: set[str] = set()
        duplicated_names: set[str] = set()
        for name in declared_names:
            if name in seen_names:
                duplicated_names.add(name)
            seen_names.add(name)
        for name in sorted(duplicated_names):
            violations.append(
                f"{label}: avatar-duplicate-name: manifest declares item name '{name}' more than once in items[]"
            )

        for file_name in sorted(set(declared_files)):
            if file_name not in asset_names:
                violations.append(
                    f"{label}: avatar-orphan-item-file: manifest names '{file_name}' in items[] but the "
                    "entry does not ship that asset"
                )

    # Reverse orphan (the flip side of avatar-orphan-item-file above): a
    # physical PNG the entry ships that no item's `file` names is a
    # stowaway — "a pack IS its files" cuts both ways, same posture as
    # validate_font_pack's own font-stowaway-asset.
    accounted_for = set(declared_files)
    for asset_name in sorted(asset_names - accounted_for):
        violations.append(
            f"{label}: avatar-stowaway-asset: entry ships '{asset_name}' but no items[] entry names it — "
            "every shipped asset must be accounted for"
        )

    return violations


def validate_persona_avatar_sidecar(entry_dir: Path, slug: str) -> list[str]:
    """A persona entry MAY carry exactly one <slug>.avatar.png sidecar face
    (SPEC F128.2) — the same per-item PNG validation an avatar pack's own
    items get (validate_png_asset). Absent is fine (the ordinary, pre-F128
    case, and by far the common one today); any OTHER extra file in the
    entry directory is already rejected as unexpected-file by
    validate_entry's own allowed-names check (this kind's own
    KindSpec.allows_extra only ever admits the ONE exact filename
    `<slug>.avatar.png`), so "at most one" holds by construction on a real
    filesystem — unlike the app's own index.json-level ladder
    (GenWave.Host.Catalog.CatalogIndexValidator.TryValidatePersonaAvatarAsset),
    which additionally guards against a hand-crafted index.json declaring
    the SAME path twice in one entry's `assets[]`, a real directory can
    never hold two files sharing one name, so that particular cardinality
    violation cannot arise from a real entries/ tree; the belt-and-braces
    guard against a hand-crafted index.json borrowing a DIFFERENT entry's
    face is validate_index_slug_ownership's job, not this function's."""
    sidecar_path = entry_dir / f"{slug}.avatar.png"
    if not sidecar_path.is_file():
        return []
    label = rel(REPO_ROOT, entry_dir)
    return validate_png_asset(sidecar_path, label, "persona-avatar", AVATAR_ITEM_BYTE_CEILING)


def validate_icon_licence_not_in_manifest(manifest_path: Path, manifest: object) -> list[str]:
    """SPEC F130.6's F1 ruling (amended 2026-08-16 at the T305 review): an
    icon pack's licence/provenance fields live ONLY in the companion
    <slug>.meta.json, never inside <slug>.icon.json — F130.1's own
    gw-icon-pack document is deliberately closed (style + icons, nothing
    else), so a `license`/`licence` member here would be silently DROPPED
    the moment GenWave.Host.Icons.IconPackDefinitionSerializer re-serializes
    the validated model (that class only ever writes
    schemaVersion/style/icons — see its own remarks). A HARD gate, same
    posture as validate_theme_font_provenance next to it: better to catch a
    contributor's misplaced licence text at submission time than let it
    silently vanish the moment the pack installs."""
    if not isinstance(manifest, dict):
        return []
    present = [key for key in ICON_LICENCE_KEYS if key in manifest]
    if not present:
        return []
    keys = ", ".join(f"'{key}'" for key in present)
    return [
        f"{rel(REPO_ROOT, manifest_path)}: icon-licence-in-manifest: icon pack definition carries "
        f"{keys} at the top level — licence/provenance belongs in the companion <slug>.meta.json only "
        "(SPEC F130.6); the app's own IconPackDefinitionSerializer would silently drop it here"
    ]


def validate_icon_numeric_finite(manifest_path: Path, manifest: object) -> list[str]:
    """Every numeric geometry attribute across every icon's every element
    must be finite (mirrors GenWave.Host.Icons.IconPackDefinitionParser's
    own double.IsFinite gate on each numeric attribute it reads). JSON's own
    number grammar admits a syntactically valid literal like `1e400` that
    overflows to a non-finite float once parsed — no JSON Schema keyword can
    express "finite", so this Python-side walk is the actual gate here,
    mirroring the schema-pins-shape/Python-pins-the-numeric-rule split
    validate_theme_aa already draws for the theme kind's own contrast gate.
    Defensive throughout: only walks shapes the schema check next to this
    call has already confirmed are objects/arrays; anything else is
    silently skipped (already reported once by that schema check)."""
    if not isinstance(manifest, dict):
        return []
    icons = manifest.get("icons")
    if not isinstance(icons, dict):
        return []

    violations: list[str] = []
    for name, elements in icons.items():
        if not isinstance(elements, list):
            continue
        for index, element in enumerate(elements):
            if not isinstance(element, dict):
                continue
            for attr, value in element.items():
                if attr in ("tag", "d", "points", "fill", "stroke"):
                    continue
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                try:
                    finite = math.isfinite(float(value))
                except OverflowError:
                    finite = False
                if not finite:
                    violations.append(
                        f"{rel(REPO_ROOT, manifest_path)}: icon-attr-not-finite: icon '{name}' element "
                        f"#{index} attribute '{attr}' is not finite ({value!r})"
                    )

    return violations


def validate_icon_pack(manifest_path: Path, manifest: object) -> list[str]:
    """Icon pack gates (SPEC F130.1/F130.6) beyond the schema check next to
    this call: the F1 licence-in-manifest reject, and the finite-numeric
    walk neither JSON Schema nor that schema check can express."""
    return validate_icon_licence_not_in_manifest(manifest_path, manifest) + validate_icon_numeric_finite(
        manifest_path, manifest
    )


def fold_brand(brand: str) -> str:
    """The brand-identity fold validate_ad_pack compares under: case-folded,
    with every internal whitespace run collapsed to one space and the ends
    trimmed. Deliberately STRICTER than the app's own upsert key (raw text
    equality on `(pack_slug, brand)`): two briefs the app would happily store
    as separate rows ("Acme Widgets" / "acme   widgets") are one brand to any
    human reading the shelf, so they are a contributor mistake here."""
    return " ".join(brand.split()).casefold()


def validate_ad_pack(manifest_path: Path, manifest: object) -> list[str]:
    """Ad-pack gates (SPEC F162.2) beyond the schema check next to it:
    the one cross-item rule draft-07 cannot express. Every brief's `brand`
    must be unique within the pack under `fold_brand` — the app installs a
    pack as one transaction of per-brief upserts keyed `(pack_slug, brand)`
    (AdBriefRepository.UpsertAllAsync), so an exact duplicate would silently
    overwrite its earlier twin's premise/tone/structure, and a case- or
    spacing-only variant would land as two rows the shelf shows as two
    brands. Shape (types, caps, closed member sets, non-blank brand) is the
    schema's job; this function trusts it already ran and tolerates a
    malformed document by simply having nothing to say about it."""
    if not isinstance(manifest, dict):
        return []
    briefs = manifest.get("briefs")
    if not isinstance(briefs, list):
        return []
    violations: list[str] = []
    first_seen: dict[str, int] = {}
    for index, brief in enumerate(briefs):
        if not isinstance(brief, dict) or not isinstance(brief.get("brand"), str):
            continue
        folded = fold_brand(brief["brand"])
        if not folded:
            continue  # the schema's own \S pattern already names a blank brand
        if folded in first_seen:
            violations.append(
                f"{rel(REPO_ROOT, manifest_path)}: ad-pack-duplicate-brand: briefs/{index}/brand "
                f"{brief['brand']!r} repeats briefs/{first_seen[folded]}/brand after case/whitespace "
                "folding — the app upserts keyed (pack_slug, brand), so one would silently overwrite "
                "or shadow the other; merge them into one brief"
            )
        else:
            first_seen[folded] = index
    return violations


def validate_voice_pack(entry_dir: Path, slug: str, manifest: object) -> list[str]:
    """Voice pack gates (SPEC F164), on top of the schema check next to this
    call — mirrors validate_font_pack's own structure and "a pack IS its
    files" posture, adapted for two DIFFERENT asset roles (weights vs. the
    one preview) rather than one uniform asset set:

      - every `voices[].file` exists on disk, is a real ZIP/torch archive
        (has_zip_magic — `voice-pack-pt-magic`; NEVER unpickled), and is
        <= 1 MiB (`voice-pack-pt-over-max`);
      - the pack's own `.pt` weights sum to <= 8 MiB
        (`voice-pack-over-ceiling`);
      - no duplicate `voiceId` across `voices[]` (`voice-pack-duplicate-voice`
        — schemas/voice-pack-manifest.schema.json's own `uniqueItems` only
        forbids two IDENTICAL objects, not two voices sharing an id with
        different gender/age/blend);
      - `voices[].file` equals `<voiceId>.pt` for THAT item's own `voiceId`
        (`voice-pack-file-mismatch` — the schema only pins the shape of
        `file`, never the cross-property equality);
      - the preview exists, is a real MP3 (has_mp3_magic —
        `voice-pack-preview-magic`), and is <= 150 KiB
        (`voice-pack-preview-over-max`);
      - the preview's OWN filename equals `<slug>.preview.mp3` for the
        entry's actual slug (`voice-pack-preview-name` — the schema pins
        the shape of `preview`, never that its stem is THIS entry's slug);
      - the same orphan/stowaway "a pack IS its files" posture
        validate_font_pack/validate_avatar_pack already take, adapted to
        this kind's own vocabulary (T411 brief, deliberately the OPPOSITE
        of font-pack's own "orphan" direction): a real `.pt`/`.mp3` file the
        entry ships that the manifest does not name is `voice-pack-orphan-file`
        here (an unclaimed weight/preview sitting in the directory); a
        manifest `voices[].file`/`preview` naming a file the entry does NOT
        ship is reported as an ordinary missing-file finding inline, below,
        since font/avatar call that shape "orphan" too but this brief's own
        wording reserves "orphan" for the unclaimed-disk-file direction —
        the KindSpec-level `unexpected-file` gate (validate_entry) already
        catches a wrongly-NAMED stowaway (one that doesn't even match
        VOICE_ASSET_NAME_PATTERN) before this function ever runs.

    A missing `voices[]` (`voice-pack-no-voices`) is reported only when
    the manifest DID parse as an object but the field itself is absent —
    an empty `voices: []` does NOT fire this (the schema's own
    `minItems: 1` already backstops that shape); when the manifest fails
    to parse as an object at all, this function returns before
    `voices`/`preview` are ever inspected (T411 review round 1 advisory —
    this docstring previously claimed the opposite), same as the
    duplicate/mismatch/orphan checks below — the schema check next to
    this call already names that shape failure once."""
    label = rel(REPO_ROOT, entry_dir)
    violations: list[str] = []

    asset_paths = list(voice_asset_paths(entry_dir))
    pt_paths = {p.name: p for p in asset_paths if p.suffix == ".pt"}
    mp3_paths = {p.name: p for p in asset_paths if p.suffix == ".mp3"}

    if not isinstance(manifest, dict):
        return violations

    voices = manifest.get("voices")
    declared_pt_files: set[str] = set()
    if isinstance(voices, list):
        seen_voice_ids: set[str] = set()
        duplicated_voice_ids: set[str] = set()
        for voice in voices:
            if not isinstance(voice, dict):
                continue
            voice_id = voice.get("voiceId")
            if isinstance(voice_id, str):
                if voice_id in seen_voice_ids:
                    duplicated_voice_ids.add(voice_id)
                seen_voice_ids.add(voice_id)

            file_name = voice.get("file")
            if not isinstance(file_name, str):
                continue
            declared_pt_files.add(file_name)

            if isinstance(voice_id, str) and file_name != f"{voice_id}.pt":
                violations.append(
                    f"{label}: voice-pack-file-mismatch: voices[] entry '{voice_id}' declares file "
                    f"'{file_name}', expected '{voice_id}.pt'"
                )

            pt_path = pt_paths.get(file_name)
            if pt_path is None:
                violations.append(
                    f"{label}: missing-file: voices[] names '{file_name}' but the entry does not ship "
                    "that weight file"
                )
                continue

            violations.extend(
                validate_binary_asset(
                    pt_path.read_bytes(),
                    file_name,
                    label,
                    has_zip_magic,
                    "voice-pack-pt-magic",
                    "a zip/torch archive",
                    "voice-pack-pt-over-max",
                    VOICE_PACK_PT_BYTE_CEILING,
                    over_max_suffix="per-weight cap",
                )
            )

        for voice_id in sorted(duplicated_voice_ids):
            violations.append(
                f"{label}: voice-pack-duplicate-voice: manifest declares voiceId '{voice_id}' more than "
                "once in voices[]"
            )
    else:
        violations.append(f"{label}: voice-pack-no-voices: voice pack ships no readable voices[]")

    total_pt_bytes = sum(p.stat().st_size for p in pt_paths.values())
    if total_pt_bytes > VOICE_PACK_PACK_BYTE_CEILING:
        violations.append(
            f"{label}: voice-pack-over-ceiling: summed weight bytes {total_pt_bytes} exceeds the "
            f"{VOICE_PACK_PACK_BYTE_CEILING}-byte per-pack ceiling (SPEC F164)"
        )

    preview_name = manifest.get("preview")
    if isinstance(preview_name, str):
        expected_preview_name = f"{slug}.preview.mp3"
        if preview_name != expected_preview_name:
            violations.append(
                f"{label}: voice-pack-preview-name: manifest declares preview '{preview_name}', expected "
                f"'{expected_preview_name}' — a voice pack's preview filename must match its own slug"
            )
        preview_path = mp3_paths.get(preview_name)
        if preview_path is None:
            violations.append(
                f"{label}: missing-file: manifest names preview '{preview_name}' but the entry does not "
                "ship that file"
            )
        else:
            violations.extend(
                validate_binary_asset(
                    preview_path.read_bytes(),
                    preview_name,
                    label,
                    has_mp3_magic,
                    "voice-pack-preview-magic",
                    "an MP3 file",
                    "voice-pack-preview-over-max",
                    VOICE_PACK_PREVIEW_BYTE_CEILING,
                )
            )

    # Orphan (T411 brief wording, the OPPOSITE of font-pack's own "orphan"
    # direction): a real .pt/.mp3 file the entry ships that nothing in the
    # manifest claims — declared_pt_files above for weights, the preview
    # name itself for the one preview clip.
    accounted_for_pt = declared_pt_files
    for file_name in sorted(set(pt_paths) - accounted_for_pt):
        violations.append(
            f"{label}: voice-pack-orphan-file: entry ships '{file_name}' but no voices[] entry names it "
            "— every shipped weight must be accounted for"
        )
    accounted_for_mp3 = {preview_name} if isinstance(preview_name, str) else set()
    for file_name in sorted(set(mp3_paths) - accounted_for_mp3):
        violations.append(
            f"{label}: voice-pack-orphan-file: entry ships '{file_name}' but the manifest's preview does "
            "not name it — every shipped file must be accounted for"
        )

    return violations


def validate_jingle_pack(entry_dir: Path, slug: str, manifest: object) -> list[str]:
    """Jingle pack gates (SPEC F165), on top of the schema check next to
    this call — mirrors validate_font_pack's own structure and "a pack IS
    its files" posture:

      - every `assets[].file` exists on disk;
      - its declared `sha256` matches the REAL bytes on disk
        (`jingle-pack-sha256-mismatch` — the schema only pins the SHAPE of
        `sha256`, never that it's the truth);
      - the bytes actually match the extension's own audio-container magic
        (`jingle-pack-audio-magic`, via JINGLE_AUDIO_MAGIC_CHECKS — the file
        extension named in `file` is never trusted on its own);
      - <= 5 MiB per asset (`jingle-pack-asset-over-max`);
      - the pack's own assets sum to <= 40 MiB (`jingle-pack-over-ceiling` —
        a ruling: SPEC F165 sets no summed-pack ceiling itself, so this
        mirrors the font/avatar/voice-pack precedent of bounding a pack's
        total footprint rather than leaving one asset-carrying kind alone
        unbounded);
      - no duplicate `file`, and no duplicate `title` under the same
        case/whitespace fold `fold_brand` already applies to ad-pack's own
        `brand` (`jingle-pack-duplicate-asset` — two assets sharing a
        differently-cased title would show as the same clip twice on any
        shelf that lists titles);
      - the REVERSE of the missing-file check above: every physical audio
        file the entry ships is accounted for by some `assets[].file`
        (`jingle-pack-orphan-audio` — a stowaway clip that nothing in the
        manifest names is just as malformed as a manifest entry pointing at
        nothing).

    A missing `assets[]` (`jingle-pack-no-assets`) is reported only when
    the manifest DID parse as an object but the field itself is absent —
    an empty `assets: []` does NOT fire this (the schema's own
    `minItems: 1` already backstops that shape); when the manifest fails
    to parse as an object at all, this function returns before `assets`
    is ever inspected (T411 review round 1 advisory — this docstring
    previously claimed the opposite), same as the sha256/magic/duplicate/
    orphan checks below — the schema check next to this call already
    names that shape failure once."""
    label = rel(REPO_ROOT, entry_dir)
    violations: list[str] = []

    asset_paths = {p.name: p for p in jingle_asset_paths(entry_dir)}

    if not isinstance(manifest, dict):
        return violations

    assets = manifest.get("assets")
    declared_files: list[str] = []
    declared_titles: list[str] = []
    total_bytes = 0
    if isinstance(assets, list):
        for index, asset in enumerate(assets):
            if not isinstance(asset, dict):
                continue
            file_name = asset.get("file")
            title = asset.get("title")
            if isinstance(title, str):
                declared_titles.append(title)
            if not isinstance(file_name, str):
                continue
            declared_files.append(file_name)

            asset_path = asset_paths.get(file_name)
            if asset_path is None:
                violations.append(
                    f"{label}: missing-file: assets[{index}] names '{file_name}' but the entry does not "
                    "ship that file"
                )
                continue

            data = asset_path.read_bytes()
            total_bytes += len(data)

            declared_sha256 = asset.get("sha256")
            if isinstance(declared_sha256, str):
                actual_sha256 = hashlib.sha256(data).hexdigest()
                if declared_sha256 != actual_sha256:
                    violations.append(
                        f"{label}: jingle-pack-sha256-mismatch: assets[{index}] '{file_name}' declares "
                        f"sha256 '{declared_sha256}' but actually hashes to '{actual_sha256}'"
                    )

            # `file_name` is only reachable here once `asset_paths.get(file_name)`
            # above returned non-None, and asset_paths's keys are exactly the
            # names jingle_asset_paths(entry_dir) matched against
            # JINGLE_ASSET_NAME_PATTERN — closed to wav|mp3|flac — so this
            # extension always has an entry in JINGLE_AUDIO_MAGIC_CHECKS.
            extension = file_name.rsplit(".", 1)[-1] if "." in file_name else ""
            audio_magic = JINGLE_AUDIO_MAGIC_CHECKS[extension]
            magic_check = audio_magic[0]
            magic_human = f"{audio_magic[1]} bytes"
            violations.extend(
                validate_binary_asset(
                    data,
                    file_name,
                    label,
                    magic_check,
                    "jingle-pack-audio-magic",
                    magic_human,
                    "jingle-pack-asset-over-max",
                    JINGLE_PACK_ASSET_BYTE_CEILING,
                    over_max_suffix="per-asset cap",
                )
            )

        seen_files: set[str] = set()
        duplicated_files: set[str] = set()
        for file_name in declared_files:
            if file_name in seen_files:
                duplicated_files.add(file_name)
            seen_files.add(file_name)
        for file_name in sorted(duplicated_files):
            violations.append(
                f"{label}: jingle-pack-duplicate-asset: manifest declares file '{file_name}' more than "
                "once in assets[]"
            )

        seen_titles: dict[str, str] = {}
        duplicated_titles: set[str] = set()
        for title in declared_titles:
            folded = fold_brand(title)
            if not folded:
                continue
            if folded in seen_titles:
                duplicated_titles.add(folded)
            else:
                seen_titles[folded] = title
        for folded in sorted(duplicated_titles):
            violations.append(
                f"{label}: jingle-pack-duplicate-asset: manifest declares title {seen_titles[folded]!r} "
                "more than once in assets[] after case/whitespace folding"
            )
    else:
        violations.append(f"{label}: jingle-pack-no-assets: jingle pack ships no readable assets[]")

    if total_bytes > JINGLE_PACK_PACK_BYTE_CEILING:
        violations.append(
            f"{label}: jingle-pack-over-ceiling: summed asset bytes {total_bytes} exceeds the "
            f"{JINGLE_PACK_PACK_BYTE_CEILING}-byte per-pack ceiling (T411 ruling; SPEC F165 sets none "
            "itself)"
        )

    # Reverse (the flip side of the missing-file check above): a physical
    # audio file the entry ships that no assets[] entry names is a
    # stowaway — "a pack IS its files" cuts both ways, same posture as
    # validate_font_pack's own font-stowaway-asset.
    accounted_for = set(declared_files)
    for file_name in sorted(set(asset_paths) - accounted_for):
        violations.append(
            f"{label}: jingle-pack-orphan-audio: entry ships '{file_name}' but no assets[] entry names "
            "it — every shipped asset must be accounted for"
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
    """Which manifest filename this entry directory carries — one of
    `tools/catalog_lib.py`'s own `KIND_SUFFIXES` keys, the single source of
    truth for both the kind set and its precedence order (read it there
    rather than trusting a kind list hand-copied into this prose, the exact
    staleness T196 review M3 already paid for once) — resolved by walking
    `kind_specs` in ITS OWN insertion order (persona wins if, bizarrely,
    more than one manifest file is present in an entry directory, then every
    other kind in `KIND_SUFFIXES`' own order) and returning the first kind
    whose `*{suffix}` glob actually matches; none present defaults to
    "persona" (the pre-T179 shape, so the caller reports a familiar
    missing-card violation rather than a new missing-kind one). Glob-matched
    rather than an exact <slug>.* filename so a slug-mismatched manifest
    file is still classified — and then reported as a slug-mismatch below,
    not silently treated as missing.

    AS OF T196, this precedence exactly mirrors tools/build_index.py's own
    resolve_manifest — both derive kind from the identical, ordered
    manifest-filename convention the app itself gates entry file-refs on
    (GenWave.Host, T176/T195), by walking the SAME `KIND_SUFFIXES` mapping
    (T196 review M3) rather than each hand-spelling the kind/suffix/
    precedence triple independently. Before T196, that function mirrored
    only the persona/theme two-thirds of this precedence, so a directory
    this function classified kind:"font" validated here but build_index.py
    silently never emitted an index entry for it; resolve_manifest's own
    comment in tools/build_index.py records that history. "This module
    accepts a font pack" and "build_index.py will actually ship it" are the
    same claim again."""
    for kind, spec in kind_specs.items():
        if any(entry_dir.glob(f"*{spec.suffix}")):
            return kind
    return "persona"


def validate_entry(entry_dir: Path, kind_specs: dict[str, KindSpec], kind_folder: str) -> list[str]:
    slug = entry_dir.name
    label = rel(REPO_ROOT, entry_dir)

    # Symlinks are never trusted — checked, and bailed out on, before any
    # file in this entry is opened (tools/catalog_lib.py: find_symlinks).
    # entry_dir.parent (the kind folder, entries/<kind-folder>/) is checked
    # too, not just entry_dir itself — gh-33 nested entries/ one level
    # deeper, and discover_entry_dirs happily walks THROUGH a symlinked kind
    # folder (Path.iterdir() follows it), so without this a symlinked kind
    # folder would let a perfectly real-looking entry_dir sitting inside it
    # have its files opened and trusted.
    symlinks = find_symlinks(entry_dir)
    if entry_dir.parent.is_symlink():
        symlinks = [entry_dir.parent, *symlinks]
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

    # gh-33: the FOLDER this entry lives under (entries/<kind_folder>/<slug>/)
    # must agree with the kind its manifest filename suffix implies — the
    # manifest filename stays kind's actual source of truth (resolve_kind,
    # above, unchanged), the folder is metadata ABOUT that truth. Checked
    # even when the manifest itself is missing/malformed (resolve_kind's own
    # "none present -> persona" default still yields a real KIND_FOLDERS
    # entry to compare against), so a wrongly-shelved entry is named as such
    # rather than only ever surfacing as an unrelated missing-file violation.
    expected_folder = KIND_FOLDERS[kind]
    if kind_folder != expected_folder:
        violations.append(
            f"{label}: kind-folder-mismatch: entry's manifest implies kind '{kind}' (expected under "
            f"'entries/{expected_folder}/'), but it lives under 'entries/{kind_folder}/' — an entry's "
            "kind folder and its manifest filename suffix must agree"
        )

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
            elif kind == "avatar":
                violations.extend(validate_avatar_pack(entry_dir, slug, manifest_instance))
            elif kind == "icon":
                violations.extend(validate_icon_pack(manifest_path, manifest_instance))
            elif kind == "ad-pack":
                violations.extend(validate_ad_pack(manifest_path, manifest_instance))
            elif kind == "voice-pack":
                violations.extend(validate_voice_pack(entry_dir, slug, manifest_instance))
            elif kind == "jingle-pack":
                violations.extend(validate_jingle_pack(entry_dir, slug, manifest_instance))

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

    # A persona's own optional avatar sidecar (SPEC F128.2) lives alongside
    # the card/meta pair above but isn't itself a manifest or a meta file —
    # checked unconditionally for every persona-kind entry, independent of
    # whether the card/meta themselves parsed cleanly, since the sidecar PNG
    # is a wholly separate file or entry_dir.
    if kind == "persona":
        violations.extend(validate_persona_avatar_sidecar(entry_dir, slug))

    return violations


def validate_entries_top_level(entries_dir: Path) -> list[str]:
    """entries/ may only contain the kind folders named in `KIND_FOLDERS`'
    own values (gh-33 — read that mapping for the current set rather than
    trusting a name list hand-copied into this prose, the exact staleness
    T196 review M3 already paid for once), as directories, nothing else — a
    loose file directly under entries/ (entries/README.md), or a directory
    whose name isn't one of `KIND_FOLDERS`' values, is a violation (checked
    regardless of whether that directory happens to itself be a symlink: a
    name violation and a symlink violation are different problems, and an
    unknown-named symlinked directory is still unknown-named). A missing or
    empty kind folder is NOT itself a violation — discover_entry_dirs simply
    finds nothing under it.

    One level deeper, each correctly-named kind folder may in turn only
    contain <slug>/ directories — a loose file sitting directly inside e.g.
    entries/personas/ is invisible to validate_entry, which only ever sees
    what discover_entry_dirs hands it (directories only, from both levels).

    Non-recursive at both levels for the symlink-vs-directory question
    specifically, same posture this function has always taken: a directory
    that's itself a symlink (a kind folder, or a <slug> directory inside a
    legitimately-named one) is deliberately left to validate_entry's own
    guard (tools/catalog_lib.py: find_symlinks, extended by validate_entry to
    also check an entry directory's PARENT since gh-33's nesting) rather than
    reported here too."""
    violations: list[str] = []
    known_folders = set(KIND_FOLDERS.values())

    for path in sorted(entries_dir.iterdir()):
        if not path.is_dir():
            if path.is_symlink():
                violations.append(f"{rel(REPO_ROOT, path)}: symlink: symlinks are not allowed under entries/")
            else:
                violations.append(
                    f"{rel(REPO_ROOT, path)}: unexpected-file: entries/ may only contain the known "
                    f"kind folders ({', '.join(sorted(known_folders))})"
                )
        elif path.name not in known_folders:
            violations.append(
                f"{rel(REPO_ROOT, path)}: unexpected-file: entries/ may only contain the known kind "
                f"folders ({', '.join(sorted(known_folders))})"
            )

    for kind_dir in sorted(p for p in entries_dir.iterdir() if p.is_dir() and p.name in known_folders):
        for child in sorted(kind_dir.iterdir()):
            if not child.is_dir():
                if child.is_symlink():
                    violations.append(f"{rel(REPO_ROOT, child)}: symlink: symlinks are not allowed under entries/")
                else:
                    violations.append(
                        f"{rel(REPO_ROOT, child)}: unexpected-file: {kind_dir.name}/ may only contain "
                        "<slug>/ directories"
                    )

    return violations


def validate_slug_uniqueness(pairs: list[tuple[str, Path]]) -> list[str]:
    """Two kind folders each holding a directory for the SAME slug (e.g.
    both entries/personas/echo-ellis/ and entries/themes/echo-ellis/) is a
    hard violation (gh-33): index.json's entries[], and the app importing
    them, key an entry on its slug ALONE, never on slug+kind — two entries
    sharing a slug across kind folders would be indistinguishable once
    flattened into index.json, with tools/build_index.py silently keeping
    whichever one sorts last and dropping the other with no warning. Takes
    the (kind_folder, entry_dir) pairs discover_entry_dirs already found,
    rather than re-walking entries_dir itself."""
    violations: list[str] = []
    first_seen: dict[str, Path] = {}
    for _kind_folder, entry_dir in pairs:
        slug = entry_dir.name
        if slug in first_seen:
            violations.append(
                f"{rel(REPO_ROOT, entry_dir)}: duplicate-slug: slug '{slug}' is also used by "
                f"{rel(REPO_ROOT, first_seen[slug])} — a slug must be unique across every kind folder"
            )
        else:
            first_seen[slug] = entry_dir
    return violations


def validate_entries(entries_dir: Path, kind_specs: dict[str, KindSpec]) -> list[str]:
    if not entries_dir.is_dir():
        return [f"{rel(REPO_ROOT, entries_dir)}: missing-file: entries/ directory not found"]
    violations: list[str] = validate_entries_top_level(entries_dir)
    pairs = discover_entry_dirs(entries_dir)
    violations.extend(validate_slug_uniqueness(pairs))
    for kind_folder, entry_dir in pairs:
        violations.extend(validate_entry(entry_dir, kind_specs, kind_folder))
    return violations


def validate_golden_fixture(fixtures_dir: Path, kind_specs: dict[str, KindSpec]) -> list[str]:
    """Only called for the real repo (see main()) — fixtures/ must exist
    there; a testdata root never carries a copy and is never routed here.
    Checks all four parity artifacts: golden.persona.json (the app card
    serializer) against the card schema, golden.theme.json (the app manifest
    serializer) against the theme-manifest schema, golden.font.json (the
    app CatalogFontManifestSerializer) against the font-manifest schema, and
    golden.show.json (the app's future show-manifest serializer, PLAN T254)
    against the show-manifest schema — any one silently drifting from what
    it's supposed to validate against would mean this repo's copy of the
    app's format has rotted out from under it.

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
    actual font ENTRIES under entries/, same split as the theme AA gate.
    golden.show.json is the same idea for the show kind (SPEC F118.1, T253):
    a manifest-shape parity fixture this repo pins ahead of the app side —
    T254 is what will add the app's own copy under
    tests/GenWave.Host.Tests/Fixtures/golden.show.json and prove the
    round-trip; until then this check only proves this repo's own manifest
    stays schema-valid, the same starting posture golden.theme.json/
    golden.font.json had before their own app-side counterparts landed."""
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

    golden_show_path = fixtures_dir / "golden.show.json"
    if not golden_show_path.is_file():
        violations.append(f"{rel(REPO_ROOT, golden_show_path)}: missing-file: golden show fixture not found")
    else:
        violations.extend(validate_json_against(golden_show_path, kind_specs["show"].manifest_schema))

    return violations


def validate_index_slug_ownership(index_path: Path, index: object) -> list[str]:
    """Every `card`, `manifest`, `meta`, and `assets[]` path an index entry
    carries must resolve under `entries/<that entry's own kind folder>/<that
    entry's own slug>/` — nothing dangling, nothing borrowed from a sibling
    entry's directory (T196 obligation 3, SPEC F104.1; folder segment added
    gh-33). draft-07 JSON Schema has no way to express "this string must
    start with a value computed from a sibling property" — schemas/
    index.schema.json's own path patterns can only pin SHAPE (character set,
    extension), never cross-reference the entry's own `slug` — so this
    Python-side check is the actual home for it. The app's own
    CatalogIndexValidator rejects the WHOLE index the instant one entry's
    file-ref resolves outside its own directory, so CI must catch a mismatch
    here, before it ever reaches the app.

    Defensive throughout (isinstance-guarded at every level): a shape
    violation here is already reported once by the schema check next to
    this call in validate_index, so a malformed `index`/`entries`/entry
    shape is silently skipped rather than raising or double-reporting. An
    entry's `kind` (default "persona" when absent, matching every other
    kind-default posture in this module) resolving to something outside
    `KIND_FOLDERS` — only possible via a hand-crafted index.json, since
    schemas/index.schema.json's own `enum` already rejects it — is skipped
    the same way, rather than raising: the schema check next to this call
    already names that shape failure once.

    A PERSONA entry's own `assets[]` (its optional avatar sidecar, SPEC
    F128.2) is held to a SECOND, narrower check on top of the prefix check
    above (F3, T309 review): schemas/index.schema.json's own `assetRef.path`
    pattern is now shape-only for this branch (a portable, ECMA-262/.NET-
    compilable pattern cannot ALSO express "this filename segment equals the
    entry's own slug" the way a Python-only named-group backreference nearly
    did — see that pattern's own remarks for why it was removed), so the
    FILENAME must equal `<slug>.avatar.png` exactly, checked here rather
    than by pattern — this is what actually stops a persona entry's own
    sidecar `assets[0]` from naming a SIBLING persona's face file while
    still resolving under its own directory prefix (e.g.
    `entries/personas/persona-a/persona-b.avatar.png` passes the prefix
    check above but names the wrong face), mirroring
    GenWave.Host.Catalog.CatalogIndexValidator.PersonaAvatarAssetPathPattern's
    own same-slug rule at the app's own layer instead."""
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
        kind_value = entry.get("kind")
        kind = kind_value if isinstance(kind_value, str) else "persona"
        kind_folder = KIND_FOLDERS.get(kind)
        if kind_folder is None:
            continue
        owned_prefix = f"entries/{kind_folder}/{slug}/"

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

        expected_sidecar_path = f"{owned_prefix}{slug}.avatar.png"
        for field, path in refs:
            if not path.startswith(owned_prefix):
                violations.append(
                    f"{rel(REPO_ROOT, index_path)}: slug-ownership: entry '{slug}' {field} path "
                    f"'{path}' does not resolve under '{owned_prefix}'"
                )
            elif kind == "persona" and field.startswith("assets[") and path != expected_sidecar_path:
                violations.append(
                    f"{rel(REPO_ROOT, index_path)}: slug-ownership: persona entry '{slug}' {field} path "
                    f"'{path}' must be '{expected_sidecar_path}' — a persona's own avatar sidecar "
                    "filename must match its own slug, never a sibling's"
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


def validate_index_asset_integrity(
    index_path: Path, index: object, failed_entry_indices: frozenset[int] = frozenset()
) -> list[str]:
    """T411: every index.json entry's own declared `sha256` (`card`/
    `manifest`/`meta`/`assets[]`) — and `bytes`, for `assets[]` — must match
    the REAL file sitting on disk at that path, resolved relative to
    index_path's own parent directory (index.json's repo-root-relative path
    convention). Neither validate_index_slug_ownership nor
    validate_index_duplicate_asset_paths above ever opens the file a `path`
    names — both compare path STRINGS to each other only — so a stale or
    hand-edited sha256/bytes claim would otherwise sail through both
    untouched. Not specific to voice-pack/jingle-pack — the gap predates
    both — but added alongside them at T411, the kind that made someone go
    looking for it.

    The jail below (`asset_path.is_relative_to(root)`) runs for EVERY ref,
    regardless of `failed_entry_indices` — a schema-rejected `path` (e.g.
    one that never matched the closed per-kind pattern in the first place,
    such as `../../../../etc/hostname`) is exactly the shape of a
    path-traversal read oracle (existence + size + hash of any
    runner-readable file, disclosed in a public CI log) and gets caught
    HERE, unconditionally, before this function ever calls `is_file()` or
    `read_bytes()` on it.

    `failed_entry_indices` (T411 review round 1, finding 2) is the set of
    top-level `entries[]` indices `index_schema_failed_entry_indices` found
    a schema.json violation under — once a ref has passed the jail above,
    this function still skips its hash/bytes comparison (the `read_bytes()`
    below) when the ref's own entry already failed schema: don't spend a
    real disk read proving a claim about a shape the schema has already
    rejected wholesale, and don't let a coincidentally-valid `sha256`/`bytes`
    pair on an otherwise-malformed entry read as "this entry's assets are
    fine." The jail above and this skip are independent defenses, not an
    either/or — the jail alone is what a fixture calling this function
    directly (bypassing `failed_entry_indices` entirely) exercises.

    A path that doesn't resolve to a real file is DELIBERATELY skipped, not
    reported, by this function: tools/run_selftest.sh's own font-asset-
    slug-mismatch and persona-avatar-sibling-face red fixtures call
    validate_index directly against a bare, standalone index.json with no
    accompanying entries/ tree at all, specifically to exercise the
    string-only checks above in isolation. Flagging every referenced path
    in those fixtures as unreadable would be a false positive this function
    has nothing useful to say about — a dangling reference is a DIFFERENT
    failure mode, and one no existing fixture or gate names; out of scope
    here.

    Defensive throughout (isinstance-guarded at every level), same posture
    as the two checks above: a shape violation here is already reported
    once by the schema check next to this call in validate_index, so a
    malformed `index`/`entries`/ref shape is silently skipped rather than
    raising or double-reporting."""
    if not isinstance(index, dict):
        return []
    entries = index.get("entries")
    if not isinstance(entries, list):
        return []

    root = index_path.parent.resolve()
    violations: list[str] = []
    for entry_index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        slug = entry.get("slug")
        if not isinstance(slug, str):
            continue

        entry_schema_failed = entry_index in failed_entry_indices

        refs: list[tuple[str, dict]] = []
        for field in ("card", "manifest", "meta"):
            ref = entry.get(field)
            if isinstance(ref, dict) and isinstance(ref.get("path"), str):
                refs.append((field, ref))
        assets = entry.get("assets")
        if isinstance(assets, list):
            for i, asset in enumerate(assets):
                if isinstance(asset, dict) and isinstance(asset.get("path"), str):
                    refs.append((f"assets[{i}]", asset))

        for label, ref in refs:
            path_str = ref["path"]
            asset_path = (root / path_str).resolve()
            if not asset_path.is_relative_to(root):
                violations.append(
                    f"{rel(REPO_ROOT, index_path)}: asset-path-escapes-root: entry '{slug}' {label} "
                    f"path '{path_str}' resolves outside the catalog root"
                )
                continue
            if entry_schema_failed:
                continue  # the schema already rejected this entry; don't hash a path it flagged
            if not asset_path.is_file():
                continue  # dangling reference: a different failure mode, out of scope here
            data = asset_path.read_bytes()

            declared_sha256 = ref.get("sha256")
            if isinstance(declared_sha256, str):
                actual_sha256 = hashlib.sha256(data).hexdigest()
                if declared_sha256 != actual_sha256:
                    violations.append(
                        f"{rel(REPO_ROOT, index_path)}: asset-hash-mismatch: entry '{slug}' {label} "
                        f"declares sha256 '{declared_sha256}' but '{path_str}' actually hashes to "
                        f"'{actual_sha256}'"
                    )

            declared_bytes = ref.get("bytes")
            if isinstance(declared_bytes, int) and not isinstance(declared_bytes, bool):
                actual_bytes = len(data)
                if declared_bytes != actual_bytes:
                    violations.append(
                        f"{rel(REPO_ROOT, index_path)}: asset-bytes-mismatch: entry '{slug}' {label} "
                        f"declares bytes {declared_bytes} but '{path_str}' is actually {actual_bytes} "
                        "bytes"
                    )
    return violations


def validate_index(index_path: Path) -> list[str]:
    """Only called for the real repo (see main()) — index.json must exist at
    the repo root, validate against schemas/index.schema.json, AND pass both
    Python-side cross-property checks above: a schema-shape-clean `assets[]`/
    `manifest`/`meta`/`card` path borrowed from a SIBLING entry's directory
    (validate_index_slug_ownership), two assets within one entry sharing a
    `path` with different `sha256`/`bytes` (validate_index_duplicate_asset_paths),
    or a `sha256`/`bytes` claim that no longer matches the real file on disk
    (validate_index_asset_integrity, T411) would each pass every pattern in
    schemas/index.schema.json, since draft-07 can't express any of the three —
    these Python checks are what actually catch them. validate_index_asset_
    integrity additionally never hashes a path belonging to an entry the
    schema already rejected (index_schema_failed_entry_indices, T411 review
    round 1 finding 2), even though its own path-escape jail still runs for
    every ref regardless — a schema-flagged entry's `sha256`/`bytes` claims
    aren't worth a real disk read to disprove."""
    if not index_path.is_file():
        return [f"{rel(REPO_ROOT, index_path)}: missing-file: index.json not found at repo root"]
    instance, violations = parse_json(index_path)
    if instance is None:
        return violations
    index_schema = load_schema("index.schema.json")
    violations += validate_schema(index_path, instance, index_schema)
    violations += validate_index_slug_ownership(index_path, instance)
    violations += validate_index_duplicate_asset_paths(index_path, instance)
    failed_entry_indices = index_schema_failed_entry_indices(instance, index_schema)
    violations += validate_index_asset_integrity(index_path, instance, failed_entry_indices)
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
