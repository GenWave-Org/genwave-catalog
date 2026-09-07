# 📻 genwave-catalog

A community shelf for [GenWave](https://github.com/GenWave-Org/genwave) — a self-hosted internet
radio control plane. The shelf carries nine kinds of entry: **12 DJ personas** (portable,
byte-valid exports of a GenWave DJ's personality — name, voice, lore, taste rules, pronunciation
corrections; a persona may also wear one optional sidecar face), **4 themes** (station-wide
look-and-feel manifests), **1 font pack** (vendored webfont faces for the Wardrobe), **show cards**
(portable named-show identity packages — name, tagline, and prompt-only flavor), **avatar packs**
(curated sets of 512×512 DJ faces for the Wardrobe's Avatars tab), **icon packs** (curated sets of
vector chrome icons for the admin UI's third swappable layer), **ad packs** (brand briefs — the
fictional sponsors a station's own LLM writes parody ad spots from; data only, no audio), **voice
packs** (Kokoro voice weights plus a required preview clip), and **jingle packs** (background
music (beds), stings, and station IDs, licence-verified) — each byte-valid and ready for a
station to drop straight in. Personas, themes, shows, avatar packs, and ad packs are open to
community submission; font packs and icon packs are Dean-curated only; voice packs and jingle
packs are first-party packs this cycle, with community submissions not yet open (see
[Contributing](#-contributing)).

This repo holds content — data files, schemas, and docs — plus the small set of Python tools under
`tools/` (and the CI that runs them) that keep it valid. There is no build and no runtime service;
the code here only validates and indexes the data files that live alongside it.

Catalog metadata and infrastructure — schemas, tools, docs, the index — are dedicated to the
public domain under **CC0 1.0 Universal** unless otherwise noted — see [`LICENSE`](./LICENSE);
by contributing, you agree your submission is released the same way. Individual packs may carry
their own licenses — check each entry before assuming CC0.

## 🗂️ Layout

```
entries/
  personas/
    <slug>/                         # a persona entry
      <slug>.persona.json              # the persona card (GenWave app repo SPEC F79.1/F79.2 format)
      <slug>.meta.json                  # catalog-only metadata (SPEC F89.1)
  themes/
    <slug>/                         # a theme entry
      <slug>.theme.json                # the theme manifest (app repo SPEC F103.2)
      <slug>.meta.json                  # catalog-only metadata, incl. preview swatches
  fonts/
    space-grotesk/                  # a font pack entry — e.g. entries/fonts/space-grotesk/
      space-grotesk.font.json          # the font manifest (app repo SPEC F104.1)
      space-grotesk.meta.json           # catalog-only metadata
      space-grotesk-variable-latin.woff2 # the vendored, latin-subsetted webfont face(s)
      OFL.txt                           # the upstream's own licence text, byte-identical
  shows/
    <slug>/                         # a show entry
      <slug>.show.json                 # the show manifest (app repo SPEC F118.1)
      <slug>.meta.json                  # catalog-only metadata, incl. optional suggestedPersona
  avatars/
    <slug>/                         # an avatar pack entry
      <slug>.avatar.json               # the avatar manifest (app repo SPEC F128.1): packName + items[]
      <slug>.meta.json                  # catalog-only metadata
      warm-grin.png                      # one 512x512 PNG per item, free-named, sitting alongside
  icons/
    <slug>/                         # an icon pack entry
      <slug>.icon.json                 # the gw-icon-pack definition (app repo SPEC F130.1) — no binary assets
      <slug>.meta.json                  # catalog-only metadata, incl. required license/sourceUrl (SPEC F130.6)
  ad-packs/
    <slug>/                         # an ad pack entry
      <slug>.ad-pack.json              # the ad-pack manifest (app repo SPEC F162.2): packName + briefs[] — data only
      <slug>.meta.json                  # catalog-only metadata
  voice-packs/
    <slug>/                         # a voice pack entry
      <slug>.voice-pack.json           # the voice-pack manifest (app repo SPEC F164): packName + engine + voices[]
      <slug>.meta.json                  # catalog-only metadata
      <slug>.preview.mp3                # required preview clip, played before install (SPEC F164.4)
      river.pt                           # one Kokoro voice weight per voices[] entry, named <voiceId>.pt
  jingle-packs/
    <slug>/                         # a jingle pack entry
      <slug>.jingle-pack.json          # the jingle-pack manifest (app repo SPEC F165): packName + assets[]
      <slug>.meta.json                  # catalog-only metadata, incl. optional tags[]
      bed.wav                            # one audio file per assets[] entry (.wav/.mp3/.flac)
schemas/
  persona-card.schema.json  # validates <slug>.persona.json
  persona-meta.schema.json  # validates a persona's <slug>.meta.json
  theme-manifest.schema.json # validates <slug>.theme.json
  theme-meta.schema.json    # validates a theme's <slug>.meta.json
  font-manifest.schema.json # validates <slug>.font.json
  font-meta.schema.json     # validates a font pack's <slug>.meta.json
  show-manifest.schema.json # validates <slug>.show.json
  show-meta.schema.json     # validates a show's <slug>.meta.json
  avatar-manifest.schema.json # validates <slug>.avatar.json
  avatar-meta.schema.json    # validates an avatar pack's <slug>.meta.json
  icon-manifest.schema.json   # validates <slug>.icon.json — the one manifest schema pinning full shape, not just types
  icon-meta.schema.json        # validates an icon pack's <slug>.meta.json (requires license/sourceUrl)
  ad-pack-manifest.schema.json # validates <slug>.ad-pack.json — the app's own brief caps, mirrored
  ad-pack-meta.schema.json     # validates an ad pack's <slug>.meta.json
  voice-pack-manifest.schema.json # validates <slug>.voice-pack.json (SPEC F164.1–F164.4)
  voice-pack-meta.schema.json     # validates a voice pack's <slug>.meta.json
  jingle-pack-manifest.schema.json # validates <slug>.jingle-pack.json (SPEC F165.1–F165.4)
  jingle-pack-meta.schema.json     # validates a jingle pack's <slug>.meta.json
  index.schema.json         # validates the committed index.json
fixtures/
  golden.persona.json       # real bytes from the app's PersonaCardSerializer, pinned for parity
  golden.theme.json          # real bytes from the app's theme manifest shape, pinned for parity
  golden.font.json            # real bytes from the app's font manifest shape, pinned for parity
  golden.show.json             # a show manifest shape, pinned ahead of the app side (PLAN T254)
tools/
  validate.py                # CI + local: schema/slug/size/contrast/provenance checks over entries/ and index.json
  lint.py                      # CI + local: persona/show submission-length budgets + dead pronunciation rules
  contrast.py                   # WCAG AA contrast math, the theme shelf's HARD gate
  png_image.py                   # byte-level PNG parsing (magic/IHDR/acTL) for the avatar kind's image gates
  build_index.py                 # builds index.json from entries/
  catalog_lib.py                   # shared helpers: repo root, relative paths, entry discovery, symlink checks
  run_selftest.sh                   # local CI mirror: good entries green, each red variant red
  testdata/red/                       # one minimal broken entry (or index.json) per validate.py/lint.py rule
  testdata/green/                      # a schema-valid entry pair per kind, exercising build_index.py's output shape
  testdata/warn/                        # a card that trips every WARN-tier lint.py rule, exit 0
index.json                    # built by tools/build_index.py, verified (rebuilt + diffed + schema-checked) by CI
LICENSE                      # CC0 1.0 Universal
README.md
```

An entry's kind is read off which manifest filename its directory carries — `<slug>.persona.json`,
`<slug>.theme.json`, `<slug>.font.json`, `<slug>.show.json`, `<slug>.avatar.json`, or
`<slug>.icon.json` (`tools/catalog_lib.py`'s `KIND_SUFFIXES`); persona wins if, bizarrely, more
than one is present, then theme, then font, then show, then avatar, then icon. An entry's kind
FOLDER — which of `entries/personas/`, `entries/themes/`, `entries/fonts/`, `entries/shows/`,
`entries/avatars/`, or `entries/icons/` it lives under (`tools/catalog_lib.py`'s `KIND_FOLDERS`) —
must agree with what its manifest filename implies; a mismatch (say, a `.persona.json` manifest
sitting under `entries/shows/`) is a hard `tools/validate.py` violation even though the manifest
itself is otherwise valid. A font pack's `OFL.txt` is tracked `-text` in
[`.gitattributes`](./.gitattributes) — licence text is byte-hashed into `index.json`, so
its line endings are never normalized on checkout, keeping that hash stable across platforms.

`fixtures/` holds four golden parity fixtures, one per kind (persona/theme/font/show), none of
them hand-written and none of them a submission or shelf content — each exists only to catch drift
between this catalog's schemas and the app's own formats, and `tools/validate.py`'s
`validate_golden_fixture` re-checks all four against their schema on every run against the real
repo. There is deliberately no `golden.avatar.json`/`golden.icon.json`: the app never WRITES an
avatar manifest (`CatalogAvatarPackManifestSerializer`'s own remarks — this app only ever reads
one through the guarded proxy door) or a catalog-shaped icon definition (the app's own
`IconPackDefinitionSerializer` writes the INSTALLED, already-validated form to `station.icon_pack`,
not a catalog submission shape) — a golden round-trip fixture needs a real writer on the other
end to pin against, and neither kind has one yet.

`fixtures/golden.persona.json` is generated by the app's real serializer
(`GenWave.Core.Domain.PersonaCardSerializer.Serialize`, `GenWave.Abstractions`), byte-for-byte —
including an empty `tagline`, exactly as a real card written by `LegacyPersonaCardMapper.BuildCard`
carries — so this fixture proves the schema tolerates what the app actually exports, not an
idealized version of it. `fixtures/golden.theme.json` and `fixtures/golden.font.json` are the same
idea for the theme and font kinds, pinned against the app's own
`tests/GenWave.Host.Tests/Fixtures/golden.theme.json` / `golden.font.json`. `fixtures/golden.show.json`
is the same idea for the show kind, but pinned ahead of the app side for now: the app's own
`ShowManifest` parser and its matching `tests/GenWave.Host.Tests/Fixtures/golden.show.json` land at
PLAN T254, which is what will prove the round-trip both ways — until then this fixture only proves
this repo's own manifest stays schema-valid.

`entries/personas/example-dj/` is a working example — a real, schema-valid entry pair, clearly marked in
its `meta.json` as the format reference rather than a genuine submission — and is deliberately a
*different* card from the golden fixture (different name/tagline/content) so the two are never
mistaken for the same artifact. Copy that directory as your starting point.

### The persona card (`<slug>.persona.json`)

Format is owned by the [GenWave app repo](https://github.com/GenWave-Org/genwave) (SPEC F79.1),
**unchanged** here — a card that validates against `schemas/persona-card.schema.json` imports
through the app's own import path with no transformation. The schema tolerates unknown fields
(`additionalProperties: true`) so a newer card that adds a field the catalog hasn't caught up to
yet still passes.

Required shape: `schemaVersion`, `name`, `tagline`, `soul`, `quirks[]`, `voice`
(`engine`/`voiceId`/`pace`/`language`), `energyDisposition`, `lore[]` (authored memory only),
`corrections[]` (`from`/`to` pronunciation fixes). Optional `taste[]`: authored taste rules only,
each `{ predicate: { artist, genre, tag }, context: { daysOfWeek, startHour, endHour }, weight }`.

### The catalog metadata (`<slug>.meta.json`)

Owned by this repo (SPEC F89.1), and stricter — `additionalProperties: false`, so an unrecognized
field fails CI rather than silently passing through.

| Field | Required | Notes |
|---|---|---|
| `author` | ✅ | who submitted this persona |
| `description` | ✅ | short blurb for the catalog shelf |
| `samplePatter` | ✅ | array of illustrative on-air lines, **2 minimum** |
| `audience` | ✅ | `"everyone"` \| `"mature"` — no other values |
| `added` | ✅ | ISO date (`YYYY-MM-DD`) |
| `bestFor` | optional | genre-affinity hints, e.g. `"late-night"`, `"ambient"` |
| `tags` | optional | free-form tags |

`samplePatter` (≥2 lines) is a persona-meta field only — themes have no on-air voice. A theme's
`<slug>.meta.json` swaps it for a required `preview` object instead: `light`/`dark` swatch sets
(`bg`/`surface`/`ink`/`accent`/`accent-2` hex values) the shelf card paints without fetching and
parsing the full `<slug>.theme.json` manifest. A font pack's `<slug>.meta.json` has neither —
its shelf card renders from `author`/`description`/`audience`/`added`/`bestFor` plus the family
name and byte total already projected onto `index.json` (see "How `index.json` is built" below),
so nothing sample-patter- or preview-shaped is required of it. A show's `<slug>.meta.json` has
neither either — its shelf card renders from `author`/`description`/`audience`/`added`/`bestFor`;
it additionally carries an optional `suggestedPersona` (an on-shelf persona slug the import modal
may offer to also hire, SPEC F118.3 — soft, never required, never projected onto `index.json` since
it's only consulted once, at import time). An avatar pack's `<slug>.meta.json` has neither either —
its shelf card renders from the manifest's own `packName` plus `author`/`description`/`audience`/
`added`/`bestFor`. An icon pack's `<slug>.meta.json` is the one exception with EXTRA required
fields: `license` and `sourceUrl` (plus optional `version`) — the icon manifest is deliberately
closed to style+icons only (SPEC F130.1), so licence/provenance live here instead (SPEC F130.6's F1
ruling; see [Icon packs](./CONTRIBUTING.md#icon-packs-kind-icon) in CONTRIBUTING.md). An ad pack's
`<slug>.meta.json` has neither either — its shelf card renders from the manifest's own `packName`
plus `author`/`description`/`audience`/`added`/`bestFor`, and carries no licence field: a pack is
original prose, CC0 like a persona card. A voice pack's `<slug>.meta.json` follows the same
ad-pack-meta shape (no licence — a pack ships opaque synthetic weights, not attributable source
audio). A jingle pack's `<slug>.meta.json` is the ad-pack-meta shape plus an optional `tags[]`
(1–8 short lowercase tokens for the shelf card); no licence field here either — a jingle pack's
licence lives per-asset, inside the manifest, not the meta sidecar. All nine kinds
share `author`/`description`/`audience`/`added`, and all nine schemas are
`additionalProperties: false`.

### The avatar manifest (`<slug>.avatar.json`) and a persona's own sidecar face

Format is owned by the [GenWave app repo](https://github.com/GenWave-Org/genwave) (SPEC F128.1):
`packName` plus `items[]`, each `{ name, file, suggestedPersona? }` — `file` names a sibling PNG
under the same `entries/avatars/<slug>/` directory. A PERSONA entry may separately carry its own
single optional `<slug>.avatar.png` sidecar face directly inside `entries/personas/<slug>/`
(SPEC F128.2) — not a pack, no manifest of its own, just one PNG riding alongside the persona card.
Every PNG this catalog carries (a pack item, or a persona's sidecar) is held to the identical
image bar: real PNG bytes verified by **magic bytes** (never file extension), an IHDR declaring
**exactly 512×512**, **≤ 512 KiB** per item, and **never animated** (an `acTL` chunk before the
first `IDAT` — an APNG — is rejected). An avatar pack's items, summed, additionally stay
**≤ 6 MiB** per pack.

### The icon pack definition (`<slug>.icon.json`)

Format is owned by the [GenWave app repo](https://github.com/GenWave-Org/genwave) (SPEC F130.1,
`GenWave.Host.Icons.IconPackDefinitionParser` — the canonical source `schemas/icon-manifest.schema.json`
is ported from): a pack-level `style` (`strokeWidth` in `[0.5, 3]`, `fill`: `none`|`currentColor`)
and an `icons` map of name → element list, where an element is one of the seven whitelisted SVG
primitives (`path`/`rect`/`circle`/`ellipse`/`line`/`polyline`/`polygon`), each with its own closed
attribute set. See [Icon packs](./CONTRIBUTING.md#icon-packs-kind-icon) in CONTRIBUTING.md for the
full shape, the house icon-name contract (the 24 names an installed pack's `icons` map can usefully
cover), and the licence/provenance split (SPEC F130.6's F1 ruling: `license`/`sourceUrl` live in
`<slug>.meta.json` only — a `license` member found inside `<slug>.icon.json` itself is a HARD
`tools/validate.py` rejection).

### The ad-pack manifest (`<slug>.ad-pack.json`)

Format is owned by the [GenWave app repo](https://github.com/GenWave-Org/genwave) (SPEC F162.2,
`GenWave.Host.Catalog.CatalogAdPackManifestSerializer` — the reader `schemas/ad-pack-manifest.schema.json`
mirrors): an optional `packName` plus 1–100 `briefs[]`, each `{ brand, premise?, tone?, structure? }`
— the fictional sponsors a station's own LLM writes parody spots from. **Data only**: no script, no
audio, no code. A station installs a pack as rows in its own briefs table, and every brief still
faces the app's script validator (blocklisted real brands, 555 phone shape, audience posture) at
generation time. Caps mirror the app's constants: `brand` 1–200 non-blank chars, each hint ≤ 500
chars, 100 briefs per pack, ≤ 256 KiB of manifest. `tools/validate.py` adds the one cross-item rule
JSON Schema cannot express — no two briefs may share a brand after case/whitespace folding
(`ad-pack-duplicate-brand`). See [📣 Ad pack submission](./CONTRIBUTING.md#-ad-pack-submission) in
CONTRIBUTING.md for the review bar (every brand invented — the trademark hard ban is the whole game).

### The voice-pack manifest (`<slug>.voice-pack.json`)

Format is owned by the [GenWave app repo](https://github.com/GenWave-Org/genwave) (SPEC
F164.1–F164.4): `packName`, `engine` (closed to `"kokoro"` this cycle), `synthetic: true` +
`sourceRef: null`/absent (a hard consent attestation — **no soft-cloning of a real voice via this
shelf, by construction**), and 1–16 `voices[]`, each `{ voiceId, file, gender?, age?, blend? }`
where `file` must equal `<voiceId>.pt` and a required top-level `preview` must equal
`<slug>.preview.mp3` (F164.4 — played in the shelf detail modal before install). `tools/validate.py`
adds what JSON Schema cannot express: every `.pt` is a real zip/torch archive (magic bytes only,
**never unpickled**) ≤ 1 MiB each and ≤ 8 MiB summed, the preview is a real MP3 ≤ 150 KiB, and no
orphaned or stowaway files. See [Voice packs](./CONTRIBUTING.md#voice-packs-kind-voice-pack) in
CONTRIBUTING.md — first-party packs this cycle, community submissions not yet open: this catalog
has no way to verify a submitter's consent claim about whose voice a `.pt` file carries.

### The jingle-pack manifest (`<slug>.jingle-pack.json`)

Format is owned by the [GenWave app repo](https://github.com/GenWave-Org/genwave) (SPEC
F165.1–F165.4): `packName` plus 1–32 `assets[]`, each `{ file, sha256, role, title, license,
attribution? }` — `role` closed to `bed`/`sting`/`station_id` (no auto-classification), `license`
closed to `CC0`/`CC-BY` (**CC-BY-SA rejected** — share-alike is viral on a derivative ad spot), and
a structured per-asset `attribution` (`{creator, sourceUrl, license}`) required iff `license ==
"CC-BY"`, forbidden otherwise — the manifest's own top level is closed against a pack-level
`attribution` field (STORY-400 AC6). `tools/validate.py` adds what JSON Schema cannot express: each
asset's declared `sha256` matches the real bytes on disk, the bytes match the extension's own magic
(RIFF/WAVE, ID3/MPEG-sync, or `fLaC`), ≤ 5 MiB per asset and ≤ 40 MiB summed, no duplicate `file`
or case/whitespace-folded `title`, and no orphaned or stowaway files. See
[Jingle packs](./CONTRIBUTING.md#jingle-packs-kind-jingle-pack) in CONTRIBUTING.md — first-party
packs this cycle, community submissions not yet open: every asset's licence and any CC-BY
attribution is verified against its source before it ships.

### Slug format

A `<slug>` must match `^[a-z0-9]+(-[a-z0-9]+)*$` — lowercase letters and digits, single hyphens
between groups, no leading/trailing/doubled hyphens — matched to the absolute end of the string, so
a trailing newline in the name is also rejected, not just characters outside the pattern. This is
the verbatim rule the app repo's `PersonaController.SlugFormat` checks on import (and the shape
`LegacyPersonaCardMapper.Slugify` ever produces) — the same one canonical rule this catalog and the
app both enforce.

### Size caps

- `<slug>.persona.json` ≤ **256 KB** (matches the app's own import cap, SPEC F79.6)
- `<slug>.meta.json` ≤ **64 KB** — same cap for all nine kinds
- `<slug>.icon.json` ≤ **256 KiB** (SPEC F130.1's own definition-size cap)
- `<slug>.ad-pack.json` ≤ **256 KiB** (the app's manifest fetch cap, `CatalogProxyService.MaxCardBytes`)
- No size cap is enforced on `<slug>.theme.json`, `<slug>.font.json`, `<slug>.show.json`,
  `<slug>.avatar.json`, `<slug>.voice-pack.json`, or `<slug>.jingle-pack.json` text itself —
  deliberate; neither SPEC F103.2 nor F104.2 nor F118.1 nor F128.1 nor F164 nor F165 defines one on
  the manifest, and the app imposes none on a loaded manifest either
- A font pack's own asset files (its woff2 face(s) + `OFL.txt`), summed, must stay **≤ 200 KiB**
  (204,800 bytes) — the per-pack ceiling, separate from and on top of the meta cap above
- A PNG this catalog carries (an avatar pack item, or a persona's own sidecar face) must stay
  **≤ 512 KiB** per item (SPEC F128.1); an avatar pack's items, summed, must stay **≤ 6 MiB**
- A voice pack's `<voiceId>.pt` file must stay **≤ 1 MiB** each, **≤ 8 MiB** summed per pack; its
  `<slug>.preview.mp3` must stay **≤ 150 KiB** (`Packs:PreviewMaxBytes`)
- A jingle pack's audio asset must stay **≤ 5 MiB** each (`Packs:JingleAssetMaxBytes`), **≤ 40 MiB**
  summed per pack (a catalog ruling — SPEC F165 sets no pack ceiling itself)

## 🔨 How `index.json` is built

A GenWave station never crawls `entries/` directly — it fetches a single `index.json` from the
repo root, listing every entry's file paths (relative), each file's `sha256`, and its `audience`.
`index.json` is **committed at the repo root**, not built by CI — a contributor adding or changing
an entry runs `tools/build_index.py` locally and commits the regenerated file as part of the PR.
CI checks it on **every PR and every push to `main`**, not just after merge: it re-runs
`tools/build_index.py` and byte-diffs the result against the committed `index.json`, and separately
schema-validates the committed file against `schemas/index.schema.json` — so a PR that edits
`entries/` without regenerating the index, or that deletes `index.json` outright, fails CI before
it can land, and the index can never silently drift from `entries/`.

Each entry also projects `kind` — `"persona"`, `"theme"`, `"font"`, `"show"`, `"avatar"`, or
`"icon"` — absent on a persona entry by design (a missing `kind` means persona, matching every
pre-F103.2 entry). A theme, font, show, avatar, or icon entry carries `manifest` (its
`<slug>.theme.json`, `<slug>.font.json`, `<slug>.show.json`, `<slug>.avatar.json`, or
`<slug>.icon.json` path + sha256) where a persona entry carries `card`; a theme entry additionally
carries `preview` (its meta's swatch sets, projected so the shelf can paint without fetching the
manifest); a font or avatar entry additionally carries `assets[]` (a font pack's woff2 face(s) +
`OFL.txt`, or an avatar pack's PNG items, each with `path`/`sha256`/`bytes`) — a font entry alone
additionally carries, optionally, `family` (copied from the manifest so a zero-fetch shelf listing
can show it; an avatar pack has no `family` equivalent, its card renders from the manifest's own
`packName` instead). A show or icon entry carries neither — each is the minimal `{manifest, meta}`
shape with nothing further projected (a show's optional `suggestedPersona`, and an icon pack's
`license`/`sourceUrl`, both live only in `<slug>.meta.json`, read directly at import/curation time,
not needed for a zero-fetch shelf listing). SEPARATELY (SPEC F128.2), a PERSONA entry may carry its
own OPTIONAL single-element `assets[]` — its `<slug>.avatar.png` sidecar face — present only when
that file is actually on disk, never an empty array. Every `assets[]` `bytes` value is the asset's
**real on-disk size**, never a manifest-declared one, and every `sha256` is likewise recomputed
from the file on disk — `tools/build_index.py` never trusts a manifest's own claims about its own
assets.

The index build excludes the `example-dj` entry: that slug is documentation, not shelf stock, so
it is never counted, imported, or listed no matter what its own files contain.
`generatedAt` is derived entirely from the tree being indexed (the newest `added` date among
included entries), never from git history or wall-clock time, so building the same tree twice
always produces byte-identical output.

CI (`tools/validate.py`) validates every PR before merge:

- every JSON Schema above, kind-aware (persona card/meta, theme manifest/meta, font manifest/meta,
  show manifest/meta, avatar manifest/meta, icon manifest/meta, plus `schemas/index.schema.json`
  for the committed `index.json`)
- `slug` matching the directory name and both filenames
- `samplePatter` having at least 2 entries (personas)
- both size caps, the font pack's 200 KiB summed-asset ceiling, and the icon pack's 256 KiB
  definition-size cap
- a theme manifest's WCAG AA contrast (`tools/contrast.py`): 11 token pairs, ≥4.5:1, in both
  `light` and `dark` modes
- the curated-only theme-font-provenance gate: a theme's `fonts.display`/`fonts.sans` asset `src`
  must be one of GenWave's five vendored faces — `fraunces`, `fraunces-italic`, `source-sans-3`,
  `jetbrains-mono`, `grenze-gotisch`, each `-variable-latin.woff2` — never a font-pack face, even
  one shipped by this same catalog
- font-pack gates: `OFL.txt` present, `license` in the permitted SPDX set (`OFL-1.1`,
  `Apache-2.0`), and no orphan/duplicate/stowaway asset references
- avatar-pack gates: every PNG verified by magic bytes, IHDR exactly 512×512, ≤512 KiB per item,
  no `acTL` (APNG), ≤6 MiB per pack, item names unique, and no orphan/stowaway asset references —
  the identical four PNG gates additionally apply to a persona's own optional sidecar face
- icon-pack gates: the closed seven-primitive whitelist + per-tag attribute sets + `d`/`points`
  grammars (pinned in `schemas/icon-manifest.schema.json` itself), every numeric geometry attribute
  finite, and the F1 ruling — a `license`/`licence` member inside `<slug>.icon.json` is a HARD
  reject; the companion meta.json REQUIRES `license`/`sourceUrl`
- ad-pack gates: the app's own caps pinned in `schemas/ad-pack-manifest.schema.json` (1–100 briefs,
  non-blank `brand` ≤ 200 chars, hints ≤ 500 chars, closed member sets), brand uniqueness after
  case/whitespace folding (`ad-pack-duplicate-brand`), and the ≤ 256 KiB manifest cap
- voice-pack gates: `engine`/`synthetic`/`sourceRef` pinned (SPEC F164.2/F164.3), every `.pt` a
  real zip/torch archive (magic bytes, ≤ 1 MiB each, ≤ 8 MiB summed), no duplicate `voiceId`, the
  required preview a real MP3 ≤ 150 KiB matching the pack's own slug, and no orphan/stowaway
  asset references
- jingle-pack gates: every asset's `sha256` matching the real bytes on disk, the bytes matching
  the extension's own magic (RIFF/WAVE, ID3/MPEG-sync, `fLaC`), the closed CC0/CC-BY licence enum
  with structured per-asset attribution required iff CC-BY (STORY-400), ≤ 5 MiB per asset and
  ≤ 40 MiB summed, no duplicate `file`/`title`, and no orphan/stowaway asset references
- `index.json` slug-ownership (every entry's paths resolve under its own
  `entries/<kind-folder>/<slug>/`, never a sibling's), duplicate-asset-path checks, and
  asset-integrity checks (every declared `sha256`/`bytes` matches the real file on disk)
- entries/ is nested by kind: only the nine known kind folders directly under `entries/`, only
  `<slug>/` directories inside each; a slug used by more than one kind folder, or a kind folder
  that disagrees with what an entry's own manifest filename implies, is a violation
- no unexpected files in an entry directory, and no symlinks anywhere under `entries/`

`tools/lint.py` additionally checks every persona card's submission-length budgets and
pronunciation-rule sanity, and every show manifest's `name`/`tagline`/`flavor` budgets
(60/120/400 chars at 1x, SPEC F115.1) — warn-first past 1x, red only at or past 2x (SPEC F118.4).
The diff-scope guard (`.github/diff_scope_guard.sh`) separately enforces one
`entries/<kind-folder>/<slug>/` + `index.json` per PR.
`tools/run_selftest.sh` mirrors this whole set locally, including a red-variant fixture per rule
(some are whole `index.json` fixtures, for the two index-level cross-checks above), so you can
confirm your PR is clean before pushing.

## 🤝 Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for the full 9-item quality bar (schema-valid,
required fields, a distinctness statement, `audience` self-rating, CC0 checkbox, English-first,
submission-length lint, scoped diff, and the likeness/CC0 image attestation for image-carrying
entries) and the PR template. **Personas, themes, shows, avatar packs, and ad packs are open to
community submission; font packs and icon packs are Dean-curated only; voice packs and jingle
packs are first-party packs this cycle, with community submissions not yet open** — see
CONTRIBUTING's [Font packs](./CONTRIBUTING.md#font-packs-kind-font),
[Icon packs](./CONTRIBUTING.md#icon-packs-kind-icon),
[Voice packs](./CONTRIBUTING.md#voice-packs-kind-voice-pack), and
[Jingle packs](./CONTRIBUTING.md#jingle-packs-kind-jingle-pack) sections.

Short version, personas: copy `entries/personas/example-dj/` to `entries/personas/<your-slug>/`,
rename both files to match your slug, write your card and metadata, and open a PR. Themes follow
the same shape under `entries/themes/<your-slug>/` with a `<slug>.theme.json` manifest in place of
the persona card; shows follow the same shape under `entries/shows/<your-slug>/` with a
`<slug>.show.json` manifest; avatar packs follow the same shape under
`entries/avatars/<your-slug>/` with a `<slug>.avatar.json` manifest plus one 512×512 PNG per item.
CI validates the shape; a maintainer reviews the content (and, for an avatar pack, the image
itself, per the likeness/CC0 attestation).

## 📥 Using an entry

Every kind here is byte-importable into a GenWave station, with no conversion step — the file you
see in `entries/` is exactly the file the station uses:

1. **Personas** — from the catalog shelf in the Admin UI, once the station points at this
   catalog's index, or by **file import**: download `<slug>.persona.json` and upload it directly
   via the Admin UI's persona import panel.
2. **Themes** — installed into the app's theme system from the catalog shelf, then worn
   station-wide.
3. **Font packs** — installed via the Wardrobe; the app fetches each of the pack's `assets[]`
   hash-verified against `index.json`'s own `sha256`/`bytes` for that asset, never trusting a
   fetched byte count it wasn't told to expect.
4. **Shows** — imported from the catalog shelf via `POST /api/shows/{slug}/import?catalogSlug=…`
   (SPEC F118.2), the same size-capped, schema-major-checked, transactional shell every kind's
   import rides. `name`/`tagline` are public and air on the station; `flavor` is prompt-only and
   never leaves it (SPEC F115.3) — the full-card import confirm shows it to the owner adopting it,
   since they're the one deciding to run with it as prompt config.
5. **Avatar packs** — installed via the Wardrobe's Avatars tab (`POST /api/avatar-packs/{slug}/install`,
   SPEC F128.3); the app fetches each item's PNG through the guarded proxy door and
   **re-validates it server-side** (magic bytes/IHDR/size/acTL — this catalog's CI is never
   trusted at install time), hash-verified against `index.json`'s own `sha256`/`bytes`. A face is
   then assigned to a persona (`POST /api/personas/{id}/avatar/from-pack`), copying its bytes —
   uninstalling the pack later never removes a worn face.
6. **Icon packs** — installed via `POST /api/icon-packs/{slug}/install` (SPEC F130.5; schema +
   whitelist re-validated server-side, this catalog's CI is never trusted at install time), then
   activated station-wide via the `Station:IconPack` setting. Uninstalling the active pack is
   legal — the renderer fails open to the house icons.
7. **Ad packs** — installed via `POST /api/ad-packs/{slug}/install` (SPEC F162.2): each brief
   upserts into the station's own `ad_brief` table keyed `(pack_slug, brand)` — reinstalling
   updates a brief's hints and never duplicates it or resets the owner's enabled/disabled choice.
   The station's ad-spot worker then writes, validates, and renders spots from them off the air
   clock; nothing airs until the owner approves each one (or turns on `Station:Ads:AutoApprove`).
8. **Voice packs** — installed via `POST /api/voice-packs/{slug}/install` (SPEC F164.5): the
   `.pt` weights and preview clip are copied in flat, keyed by their `voiceId`; an engine mismatch
   against the station's configured TTS engine, or a `voiceId` collision with an already-installed
   voice, refuses the whole install rather than partially landing it. Uninstalling refuses if any
   persona, ad-cast slot, or announcer setting still references one of the pack's voices (SPEC
   F164.6) — a voice in use is never pulled out from under something using it.
9. **Jingle packs** — installed via `POST /api/jingle-packs/{slug}/install` (SPEC F165.5): each
   asset is hash-verified against `index.json`'s own `sha256`/`bytes`, then run through the same
   loudness/cue-point enrichment pipeline as scanned media and written into `library.media` —
   background music (beds), stings, and station IDs join the mix like any other track. Uninstalling
   refuses while any of the pack's rows are still referenced by a schedule or in-flight render
   (SPEC F165.6).
