# 📻 genwave-catalog

A community shelf for [GenWave](https://github.com/GenWave-Org/genwave) — a self-hosted internet
radio control plane. The shelf carries four kinds of entry: **12 DJ personas** (portable,
byte-valid exports of a GenWave DJ's personality — name, voice, lore, taste rules, pronunciation
corrections), **4 themes** (station-wide look-and-feel manifests), **1 font pack** (vendored
webfont faces for the Wardrobe), and **show cards** (portable named-show identity packages — name,
tagline, and prompt-only flavor) — each byte-valid and ready for a station to drop straight in.
Personas, themes, and shows are open to community submission; font packs are Dean-curated only
(see [Contributing](#-contributing)).

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
schemas/
  persona-card.schema.json  # validates <slug>.persona.json
  persona-meta.schema.json  # validates a persona's <slug>.meta.json
  theme-manifest.schema.json # validates <slug>.theme.json
  theme-meta.schema.json    # validates a theme's <slug>.meta.json
  font-manifest.schema.json # validates <slug>.font.json
  font-meta.schema.json     # validates a font pack's <slug>.meta.json
  show-manifest.schema.json # validates <slug>.show.json
  show-meta.schema.json     # validates a show's <slug>.meta.json
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
`<slug>.theme.json`, `<slug>.font.json`, or `<slug>.show.json` (`tools/catalog_lib.py`'s
`KIND_SUFFIXES`); persona wins if, bizarrely, more than one is present, then theme, then font,
then show. An entry's kind FOLDER — which of `entries/personas/`, `entries/themes/`,
`entries/fonts/`, or `entries/shows/` it lives under (`tools/catalog_lib.py`'s `KIND_FOLDERS`) —
must agree with what its manifest filename implies; a mismatch (say, a `.persona.json` manifest
sitting under `entries/shows/`) is a hard `tools/validate.py` violation even though the manifest
itself is otherwise valid. A font pack's `OFL.txt` is tracked `-text` in
[`.gitattributes`](./.gitattributes) — licence text is byte-hashed into `index.json`, so
its line endings are never normalized on checkout, keeping that hash stable across platforms.

`fixtures/` holds four golden parity fixtures, one per kind, none of them hand-written and none
of them a submission or shelf content — each exists only to catch drift between this catalog's
schemas and the app's own formats, and `tools/validate.py`'s `validate_golden_fixture` re-checks
all four against their schema on every run against the real repo.

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
it's only consulted once, at import time). All four kinds share
`author`/`description`/`audience`/`added`, and all four schemas are `additionalProperties: false`.

### Slug format

A `<slug>` must match `^[a-z0-9]+(-[a-z0-9]+)*$` — lowercase letters and digits, single hyphens
between groups, no leading/trailing/doubled hyphens — matched to the absolute end of the string, so
a trailing newline in the name is also rejected, not just characters outside the pattern. This is
the verbatim rule the app repo's `PersonaController.SlugFormat` checks on import (and the shape
`LegacyPersonaCardMapper.Slugify` ever produces) — the same one canonical rule this catalog and the
app both enforce.

### Size caps

- `<slug>.persona.json` ≤ **256 KB** (matches the app's own import cap, SPEC F79.6)
- `<slug>.meta.json` ≤ **64 KB** — same cap for all four kinds
- No size cap is enforced on `<slug>.theme.json`, `<slug>.font.json`, or `<slug>.show.json` text
  itself — deliberate; neither SPEC F103.2 nor F104.2 nor F118.1 defines one on the manifest, and
  the app imposes none on a loaded manifest either
- A font pack's own asset files (its woff2 face(s) + `OFL.txt`), summed, must stay **≤ 200 KiB**
  (204,800 bytes) — the per-pack ceiling, separate from and on top of the meta cap above

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

Each entry also projects `kind` — `"persona"`, `"theme"`, `"font"`, or `"show"` — absent on a
persona entry by design (a missing `kind` means persona, matching every pre-F103.2 entry). A
theme, font, or show entry carries `manifest` (its `<slug>.theme.json`, `<slug>.font.json`, or
`<slug>.show.json` path + sha256) where a persona entry carries `card`; a theme entry additionally
carries `preview` (its meta's swatch sets, projected so the shelf can paint without fetching the
manifest); a font entry additionally carries `assets[]` (its woff2 face(s) + `OFL.txt`, each with
`path`/`sha256`/`bytes`) and, optionally, `family` (copied from the manifest so a zero-fetch shelf
listing can show it). A show entry carries neither — it's the minimal `{manifest, meta}` shape
with nothing further projected (its optional `suggestedPersona` lives only in `<slug>.meta.json`,
read directly at import time, not needed for a zero-fetch shelf listing). Every `assets[]` `bytes`
value is the asset's **real on-disk size**, never a manifest-declared one, and every `sha256` is
likewise recomputed from the file on disk — `tools/build_index.py` never trusts a manifest's own
claims about its own assets.

The index build excludes the `example-dj` entry: that slug is documentation, not shelf stock, so
it is never counted, imported, or listed no matter what its own files contain.
`generatedAt` is derived entirely from the tree being indexed (the newest `added` date among
included entries), never from git history or wall-clock time, so building the same tree twice
always produces byte-identical output.

CI (`tools/validate.py`) validates every PR before merge:

- every JSON Schema above, kind-aware (persona card/meta, theme manifest/meta, font manifest/meta,
  show manifest/meta, plus `schemas/index.schema.json` for the committed `index.json`)
- `slug` matching the directory name and both filenames
- `samplePatter` having at least 2 entries (personas)
- both size caps, plus the font pack's 200 KiB summed-asset ceiling
- a theme manifest's WCAG AA contrast (`tools/contrast.py`): 11 token pairs, ≥4.5:1, in both
  `light` and `dark` modes
- the curated-only theme-font-provenance gate: a theme's `fonts.display`/`fonts.sans` asset `src`
  must be one of GenWave's five vendored faces — `fraunces`, `fraunces-italic`, `source-sans-3`,
  `jetbrains-mono`, `grenze-gotisch`, each `-variable-latin.woff2` — never a font-pack face, even
  one shipped by this same catalog
- font-pack gates: `OFL.txt` present, `license` in the permitted SPDX set (`OFL-1.1`,
  `Apache-2.0`), and no orphan/duplicate/stowaway asset references
- `index.json` slug-ownership (every entry's paths resolve under its own
  `entries/<kind-folder>/<slug>/`, never a sibling's) and duplicate-asset-path checks
- entries/ is nested by kind: only the four known kind folders directly under `entries/`, only
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

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for the full 8-item quality bar (schema-valid,
required fields, a distinctness statement, `audience` self-rating, CC0 checkbox, English-first,
submission-length lint, scoped diff) and the PR template. **Personas, themes, and shows are open
to community submission; font packs are Dean-curated only** — see CONTRIBUTING's Font packs
section.

Short version, personas: copy `entries/personas/example-dj/` to `entries/personas/<your-slug>/`,
rename both files to match your slug, write your card and metadata, and open a PR. Themes follow
the same shape under `entries/themes/<your-slug>/` with a `<slug>.theme.json` manifest in place of
the persona card; shows follow the same shape under `entries/shows/<your-slug>/` with a
`<slug>.show.json` manifest. CI validates the shape; a maintainer reviews the content.

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
