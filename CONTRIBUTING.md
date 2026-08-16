# 🤝 Contributing to genwave-catalog

Thanks for wanting to add to the shelf. This is a community catalog for
[GenWave](https://github.com/GenWave-Org/genwave), carrying six kinds of entry: DJ **personas**,
**themes**, **shows**, and **avatar packs** (all four open to community submission) and **font
packs** and **icon packs** (Dean-curated only — see [Font packs](#font-packs-kind-font) and
[Icon packs](#icon-packs-kind-icon) below). Every entry here is something someone else's radio
station can drop straight in. That's a gift to strangers, so we ask a bit of care in return. This
doc is the full bar: what CI checks mechanically, and what a human reviews.

This walkthrough below is the **persona** path. Submitting a **theme**, **show**, or **avatar
pack** instead? Read this section for the shared mechanics (prerequisites, validate/lint/index/
selftest, the PR template), then jump to [🎨 Theme submission](#-theme-submission),
[🎙 Show submission](#-show-submission), or [🖼 Avatar pack submission](#-avatar-pack-submission)
for what's different. Font packs and icon packs don't follow this path at all — see
[Font packs](#font-packs-kind-font) and [Icon packs](#icon-packs-kind-icon).

## 🚀 Start to finish

1. **Prerequisites** — Python 3.12 and `pip install jsonschema==4.19.2` (the exact pin
   `.github/workflows/ci.yml` installs). A different `jsonschema` version can validate
   differently than CI does, so match the pin, not just "some jsonschema".
2. **Fork and clone** this repo.
3. **Copy `entries/personas/example-dj/`** to `entries/personas/<your-slug>/`, then rename both
   files to `<your-slug>.persona.json` and `<your-slug>.meta.json`. `<your-slug>` must match
   `^[a-z0-9]+(-[a-z0-9]+)*$` — see README.md's [Slug format](./README.md#slug-format) for the
   exact rule.
4. **Author the card and metadata** — replace every placeholder field. README.md's
   [persona card](./README.md#the-persona-card-slugpersonajson) and
   [catalog metadata](./README.md#the-catalog-metadata-slugmetajson) sections have the full
   shape and field tables for both files; don't duplicate them here, just follow them.
5. **Validate locally**:
   ```
   python3 tools/validate.py
   ```
   Fix every violation it prints — each one names the offending file and rule; it's kind-aware, so
   a theme entry is checked against the theme schemas and gates, not the persona ones. Then, for a
   persona or a show, run the submission-length lint too, before you open a PR:
   ```
   python3 tools/lint.py
   ```
   `tools/lint.py` covers **persona cards and show manifests** today — it has nothing to say about
   a theme entry one way or the other, so a clean run here is not itself a theme quality signal.
   Warnings alone won't block a PR, but read them — see the "Keep the card tight" section below
   (personas) or [🎙 Show submission](#-show-submission) (shows) for why they're there. Red always
   needs fixing.
6. **Regenerate the index**:
   ```
   python3 tools/build_index.py
   ```
   Commit the resulting `index.json` change as part of your PR. CI rebuilds it and diffs
   against what you committed — a PR that edits `entries/` without this step fails CI.
7. **Run the local CI mirror**:
   ```
   tools/run_selftest.sh
   ```
   This mirrors the same checks CI runs, so a green run here means a green PR — provided your
   local Python and `jsonschema` match the pin from step 1; a version drift there can validate
   differently than CI does.
8. **Open a PR** using the pull request template — it walks you through attesting to
   everything below.

## ✅ The quality bar

CI enforces shape. A human enforces character. Both matter, and both are law here
(SPEC F89.3):

1. **Schema-valid** — enforced by CI (`tools/validate.py`), not negotiable.
2. **Required fields present** — also CI-enforced; see README.md's
   [persona card](./README.md#the-persona-card-slugpersonajson) and
   [catalog metadata](./README.md#the-catalog-metadata-slugmetajson) sections for the full
   field list.
3. **A one-line "what makes this DJ distinct" statement**, written in the PR itself.
4. **`audience` self-rating, verified at review** — mature-leaning content submitted under
   `everyone` is a revision request, not a judgment call.
5. **CC0 dedication checkbox**, checked.
6. **English-first for v1** — cards must be written in English.
7. **Keep the card's prompt weight tight** — CI-checked by `tools/lint.py`, warnings first, red
   only for the absurd.
8. **Scoped diff, one entry per PR** — CI-enforced (diff-scope guard): an entry PR touches
   only its own `entries/<kind-folder>/<slug>/` directory plus the regenerated `index.json` —
   never a second entry, and never `schemas/`, `tools/`, `fixtures/`, `.github/`, `README.md`,
   `CONTRIBUTING.md`, `LICENSE`, or `.gitattributes`. Infra changes go in their own PR
   (with no `entries/` edits), where they get reviewed as infra.
9. **Likeness/CC0 image attestation, image-carrying entries only** (SPEC F128.1) — an avatar
   pack item, or a persona's own optional `<slug>.avatar.png` sidecar face: "I created/own this
   image; no real person's likeness, no trademarked characters." CI can't check a drawing's
   provenance; the PR template's checkbox says so in as many words, and a reviewer eyeballs the
   image the same way they eyeball `samplePatter`.

**Hard bans, regardless of rating, no exceptions:** hate/harassment content, sexualized minors,
real-person impersonation, trademarks/branding.

**Per kind:** items 1, 2, 4, 5, and 8 above apply to a theme, a show, or an avatar pack exactly as
written — schema-valid, required fields present (against that kind's own schemas, not the persona
ones), `audience` self-rating, CC0 checkbox, scoped diff. Items 3 and 6 have a theme/show/avatar
equivalent, not a persona-only meaning: a theme still needs its own one-line distinctness statement
(what makes this *look* distinct, not this DJ), a show needs one too (what makes this *show's
format* distinct, not this DJ or this look), and an avatar pack needs one too (what makes this
*pack's style* distinct); English-first still applies to whatever prose a theme entry carries
(`description` — a theme has no `soul`/`lore`/`quirks`/`samplePatter` to translate), to a show's
`tagline`/`flavor`/`description`, and to an avatar pack's `description`. Item 7 (`tools/lint.py`'s
prompt-weight budget) is **persona-specific in its exact framing** and does not apply to a theme or
an avatar pack at all — neither carries a field that rides into a runtime model prompt — but a show
carries its own separate `tools/lint.py` budget gate on `name`/`tagline`/`flavor` (a different
formula, SPEC F115.1/F118.4, not the persona's soul-plus-quirks prompt-weight one) — see
[🎙 Show submission](#-show-submission) below for its numbers. Item 9 (the likeness/CC0 image
attestation) applies to an avatar pack and NOT to a theme or a show — neither carries an image. A
theme submission adds two gates of its own with no persona equivalent (AA contrast, vendored-five
faces) — see [🎨 Theme submission](#-theme-submission) below; a show submission adds one (the
`suggestedPersona` slug-shape/64-char cap) — see [🎙 Show submission](#-show-submission); an avatar
pack submission adds the PNG image bar itself (magic bytes, exact 512×512, size ceilings, no
animated PNGs) — see [🖼 Avatar pack submission](#-avatar-pack-submission). Font packs and icon
packs don't clear this bar at all — curated only, see [Font packs](#font-packs-kind-font) and
[Icon packs](#icon-packs-kind-icon).

The rest of this doc walks through items 3–7 one at a time, for a persona; theme and show
specifics are their own sections below.

### 🎭 The distinctness statement

In one line, in the PR description, tell us what makes this DJ different from every other
entry on the shelf. Not "a friendly DJ who plays music" — that's every DJ. What's the hook?
The voice, the obsession, the running bit, the thing listeners would recognize them by after
one segment. If you can't write that sentence, the character probably isn't finished yet.

### 🔞 The `audience` self-rating

`audience` is either `"everyone"` or `"mature"` — there's no third bucket, and no
partial credit for close-but-not-quite. Be honest about which one your persona is. As a rough
guide: if the card's `soul`, `lore`, `quirks`, or `samplePatter` lean into innuendo, crude
humor, dark themes, or anything you wouldn't want playing unannounced around a kid, that's
`mature`, not `everyone`. When in doubt, rate it `mature` — the catalog is fine with mature
entries; it is not fine with mismarked ones.

This is verified at review, not just taken on trust. If a reviewer reads `everyone` content
that reads mature to them, the response is a revision request asking you to relabel (or
rewrite) it — not a rejection, and not a debate about where the line is. The label just has
to match the content.

### 📜 CC0: what checking that box means

Catalog metadata and infrastructure are released under **CC0 1.0 Universal** unless otherwise
noted — see [`LICENSE`](./LICENSE); individual packs may carry their own licenses, so check each
entry. By opening a PR here and checking the CC0 box in the template, you are dedicating your entry
to the public domain, irrevocably. That means anyone — including for-profit use — can copy,
modify, remix, or redistribute your persona with no attribution required and no way for you
to take it back later. Only submit a persona you actually own the rights to and are genuinely
willing to give away on those terms. If that gives you pause, that's worth listening to before
you open the PR, not after it's merged.

### 🇬🇧 English-first

For v1, entries must be written in English — `soul`, `lore`, `quirks`, `samplePatter`,
`description`, all of it. This isn't a judgment on other languages; it's a scope limit on what
a small volunteer review team (ie. just me right now) can evaluate for the other seven bar items right now.

### 🎤 Keep the card tight

A persona's `soul`, a sampled handful of its `quirks`, and its name line don't just sit in the
JSON — at runtime they ride into the system prompt of a small local model (`llama3.2:3b` on the
reference station) that has to answer in a sentence or two. It doesn't see the whole card every
break, either: it gets `soul`, two or three quirks sampled from the list, and, on some breaks,
its name line. Load those fields up and you don't get a richer-sounding DJ — you get a model
that overshoots its own answer budget. When that happens, the app throws the generated line away
and airs template patter instead. Extra card weight doesn't buy depth; it buys silence-shaped
fallbacks.

Length isn't the only way to blow the budget. A quirk that *instructs* the model to run long
("go on about," "in great detail," that flavor of phrasing) costs more than the same amount of
plain descriptive text would, because it's telling the model to keep generating past where a
tighter card would already have stopped.

Run `python3 tools/lint.py` before you open a PR. Its warnings name every budget it checks,
measured value against allowed, for the field that's over. That output is the source of truth
for the exact numbers, not this doc — we don't restate them here so there's only one place for
them to be right. Warnings alone won't block your PR; only the absurd goes red.

One more thing the lint holds the line on: a pronunciation rule the app would silently drop —
one whose `word` never actually matches inside `pattern`, or that's otherwise dead on arrival —
fails CI outright, not just a warning. A rule like that would never fire at runtime anyway, so
there's no soft version of it: fix what the lint names rather than arguing with it.

## 🎨 Theme submission

Themes are open to community submission, same as personas — the mechanics above (prerequisites,
`tools/validate.py`, `tools/build_index.py`, `tools/run_selftest.sh`, the PR template) all apply.
Only the files and gates below are theme-specific.

1. **Copy an existing theme entry** — e.g. `entries/themes/graveyard-shift/` — to
   `entries/themes/<your-slug>/`, then rename both files to `<your-slug>.theme.json` and
   `<your-slug>.meta.json`. Same slug rule as personas: `^[a-z0-9]+(-[a-z0-9]+)*$` (README.md's
   [Slug format](./README.md#slug-format)).
2. **Author the manifest** (`<slug>.theme.json`) — validates against
   `schemas/theme-manifest.schema.json`. The shape is owned by the
   [GenWave app repo](https://github.com/GenWave-Org/genwave) (SPEC F103.2), same posture as the
   persona card: this catalog validates a copy of that schema but never changes it. Required:
   `slug`, `name`, `author`, `fonts` (`display` and `sans`, each `{ family, assets[] }`), `modes`
   (`light` and `dark` token maps).
3. **Author the metadata** (`<slug>.meta.json`) — validates against
   `schemas/theme-meta.schema.json`. Required: `author`, `description`, `audience`, `added`, and
   `preview` — a `light`/`dark` swatch set (`bg`/`surface`/`ink`/`accent`/`accent-2` hex values)
   the shelf card paints without fetching the full manifest. There is no `samplePatter` field; a
   theme has no on-air voice.
4. **Clear the AA contrast gate — HARD, not a warning.** `tools/contrast.py` checks the same 11
   token pairs the app's own `admin-ui/__specs__/theme-shelf-contrast.spec.ts` asserts against
   every shipped theme: `ink` on each of `bg`/`surface`/`surface-2`, `accent-ink` on `accent`,
   `danger-ink` on `danger`, and `mute`/`accent-2` on each of those same three grounds — every
   pair measuring **≥4.5:1** in BOTH `light` and `dark` modes (22 checks total). A failing pair,
   or a pair missing either of its two tokens, rejects the entry before it ever reaches
   `index.json` — same posture as a schema failure, not a lint warning. Run
   `python3 tools/validate.py` locally before you open a PR; the specific failing pair is named in
   the output.
5. **The vendored-five faces rule — HARD, no exceptions.** A theme's `fonts.display`/`fonts.sans`
   assets may reference ONLY GenWave's five vendored `/fonts/*.woff2` faces: **`fraunces`,
   `fraunces-italic`, `source-sans-3`, `jetbrains-mono`, `grenze-gotisch`** (each a
   `-variable-latin.woff2` file). This is a standing ruling (SPEC F104.9's unbreakable-themes
   invariant, PLAN T205, Dean's 2026-08-05 ruling: "themes never reference font packs in the
   catalog") — a theme referencing anything else, **including a font pack shipped by this very
   catalog**, is HARD-rejected by `tools/validate.py`'s curated-only theme-font-provenance gate.
   Why: a catalog theme has to keep rendering with zero network on every station regardless of
   which font packs, if any, that station has installed; a theme that could reference a pack face
   would silently 404 its font on any station that hadn't installed that exact pack.

The [quality bar](#-the-quality-bar) above still applies — see its "Per kind" note for exactly
which of the 9 items carry over as-is, which have a theme equivalent, and which are persona-only.

## 🎙 Show submission

Shows are open to community submission, same as personas and themes — the mechanics above
(prerequisites, `tools/validate.py`, `tools/build_index.py`, `tools/run_selftest.sh`, the PR
template) all apply. Only the files and gates below are show-specific.

1. **Create `entries/shows/<your-slug>/`** — there's no existing show entry to copy yet (the seed
   lineup ships separately, PLAN T256), so author `<slug>.show.json` and `<slug>.meta.json` from
   scratch, following the shapes below. Same slug rule as every other kind:
   `^[a-z0-9]+(-[a-z0-9]+)*$` (README.md's [Slug format](./README.md#slug-format)).
2. **Author the manifest** (`<slug>.show.json`) — validates against
   `schemas/show-manifest.schema.json`. The shape is owned by the
   [GenWave app repo](https://github.com/GenWave-Org/genwave) (SPEC F118.1), same posture as the
   persona card and theme manifest: this catalog validates a copy of that schema but never changes
   it. Required: `schemaVersion`, `name`, `tagline`, `flavor`.
3. **Author the metadata** (`<slug>.meta.json`) — validates against
   `schemas/show-meta.schema.json`. Required: `author`, `description`, `audience`, `added`.
   Optional: `bestFor`; and `suggestedPersona` — a persona slug the import modal may offer to also
   hire (SPEC F118.3). It's **soft**: a suggestion that's unknown or already hired just means no
   offer, never an import failure. Its *shape* is still enforced, though — it must match the
   catalog's own slug format (`^[a-z0-9]+(-[a-z0-9]+)*$`) and stay within 64 characters, the same
   cap the app's own `catalogSlug` route parameter enforces; free text does not pass here.
4. **Keep `name`/`tagline`/`flavor` within budget — CI-checked, warnings first, red only for the
   absurd.** Run `python3 tools/lint.py` before you open a PR; its warnings name the exact measured
   value against the budget for whichever field is over — that output is the source of truth for
   the numbers, not this doc, so there's only one place for them to be right (SPEC F115.1: warn
   past 1x, SPEC F118.4: red at or past 2x). `flavor` never leaves the station once imported — the
   same persona-`soul` precedent as the "Keep the card tight" section above — while `name`/`tagline`
   are public and air on the station (SPEC F115.3); the budget applies to all three regardless of
   which are public.

The [quality bar](#-the-quality-bar) above still applies — see its "Per kind" note for exactly
which of the 9 items carry over as-is, which have a show equivalent, and which are persona-only.

## 🖼 Avatar pack submission

Avatar packs are open to community submission, same as personas, themes, and shows — the
mechanics above (prerequisites, `tools/validate.py`, `tools/build_index.py`,
`tools/run_selftest.sh`, the PR template) all apply. Only the files and gates below are
avatar-pack-specific. (A persona's own optional `<slug>.avatar.png` sidecar face — a single face
riding inside an *existing* persona entry, not a standalone pack — follows the exact same PNG
rules described here; see step 3 below.)

1. **Create `entries/avatars/<your-slug>/`** — author `<slug>.avatar.json` and `<slug>.meta.json`
   from scratch. Same slug rule as every other kind: `^[a-z0-9]+(-[a-z0-9]+)*$` (README.md's
   [Slug format](./README.md#slug-format)).
2. **Author the manifest** (`<slug>.avatar.json`) — validates against
   `schemas/avatar-manifest.schema.json`. The shape is owned by the
   [GenWave app repo](https://github.com/GenWave-Org/genwave) (SPEC F128.1), same posture as every
   other kind's own manifest: this catalog validates a copy of that schema but never changes it.
   Required: `packName`, `items[]` (each `{ name, file, suggestedPersona? }` — `name` is the
   display name shown in the Wardrobe's item grid, `file` is the bare PNG filename sitting
   alongside the manifest, `suggestedPersona` is an OPTIONAL catalog persona slug this face pairs
   well with — a soft offer, same posture as a show's own `suggestedPersona`).
3. **Author each PNG item — HARD, no exceptions.** Every PNG this entry ships (a pack's own
   `items[]` face, or a persona's own `<slug>.avatar.png` sidecar) must clear all four, checked
   by `tools/validate.py` and re-checked server-side at install time (the catalog's CI is never
   trusted — SPEC F128.3):
   - **Real PNG bytes, verified by magic bytes** — never by file extension.
   - **Exactly 512×512** — read straight off the IHDR chunk; anything else is rejected.
   - **≤ 512 KiB per item.**
   - **Never animated (no APNG)** — an `acTL` chunk anywhere before the first `IDAT` is rejected.

   An avatar pack additionally holds two pack-level gates: every item's own PNG assets, summed,
   must stay **≤ 6 MiB**, and every item's `name` must be **unique within the pack**. Every `file`
   an item names must correspond to a PNG the entry actually ships (an "orphan" reference is
   malformed), and — the reverse — every PNG the entry ships must be named by some item's `file`
   (an unreferenced "stowaway" PNG is just as malformed).
4. **Author the metadata** (`<slug>.meta.json`) — validates against
   `schemas/avatar-meta.schema.json`. Required: `author`, `description`, `audience`, `added`.
   Optional: `bestFor`. No `preview`/`samplePatter` equivalent — the shelf card renders from the
   manifest's own `packName` plus `author`/`description`/byte total.

The [quality bar](#-the-quality-bar) above still applies — see its "Per kind" note for exactly
which of the 9 items carry over as-is, which have an avatar-pack equivalent, and which are
persona-only. Item 9 (the likeness/CC0 image attestation) is the one item with NO theme/show
equivalent — it exists only for image-carrying entries, and every avatar pack carries one.

## 🔍 What review looks like

A maintainer reads every PR by hand — there's no automated content approval, on purpose,
because the parts that matter (distinctness, tone, the audience rating, the hard bans) need a
human. That means review can be slow when the queue is long. That's a good problem to have; it
means people are writing DJs. Revision requests are the normal outcome of a first pass, not a
sign your persona was rejected — expect back-and-forth on wording, the audience label, or the
distinctness statement before merge.

CI passing gets you a shape-correct entry. Review gets you a shelf-worthy one.

## 🔗 About the card format

The `<slug>.persona.json` shape is not owned by this repo — it's the
[GenWave app repo](https://github.com/GenWave-Org/genwave)'s own byte-importable export format
(SPEC F79.1/F79.2). This catalog validates against a copy of that schema but never changes it;
a card that passes here imports straight into a GenWave station with no transformation. If
you're unsure what a field means or how it's used at runtime, the app repo is the source of
truth, not this one.


## Font packs (kind: font)

Font packs are **Dean-curated only** — no community pack submissions. Every pack clears the
GenWave app repo's `FONTS.md` process (OFL-confirm at the canonical upstream, provenance record,
latin subset, ceiling measure). For reproducibility, the exact subset invocation is:

```bash
pip install fonttools brotli   # fonttools 4.63.0 at the time of the first pack
pyftsubset UpstreamFont.ttf \
  --output-file=<family-kebab>-variable-latin.woff2 \
  --flavor=woff2 --layout-features='*' --name-IDs='*' \
  --unicodes="U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD"
```

`--name-IDs='*'` keeps the face's own OFL notice/URL name records (IDs 13/14) in the shipped
woff2 — attribution travels inside the binary, not only in the pack's `OFL.txt`. An entry is
`entries/fonts/<slug>/` holding `<slug>.font.json`, `<slug>.meta.json`, the woff2 face(s), and the
upstream's own `OFL.txt` byte-identical. CI enforces the schemas, the 200 KiB pack ceiling,
licence allowlist, and stowaway/orphan/duplicate checks (`tools/validate.py`).

## Icon packs (kind: icon)

Icon packs are **Dean-curated only** — no community pack submissions (SPEC F130.6, the FONTS.md
posture at a lighter weight). Every pack is produced by the offline authoring script in the
[GenWave app repo](https://github.com/GenWave-Org/genwave)'s `tools/IconPackAuthor/` (SVG source
set + a name mapping → a schema-valid `<slug>.icon.json` plus a draft `<slug>.meta.json`
skeleton), converted from an MIT (or equivalently permissive) icon set. An entry is
`entries/icons/<slug>/` holding exactly `<slug>.icon.json` and `<slug>.meta.json` — an icon pack
carries no binary assets of its own (its "artwork" is inline geometry, not a file).

**The manifest** (`<slug>.icon.json`) validates against `schemas/icon-manifest.schema.json` — the
`gw-icon-pack` schema-major-1 document (SPEC F130.1), owned by the
[GenWave app repo](https://github.com/GenWave-Org/genwave)'s
`GenWave.Host.Icons.IconPackDefinitionParser`, the single canonical source this catalog schema is
ported from. Unlike every other kind's manifest schema, this one pins the FULL closed shape, not
just types: a pack-level `style` (`strokeWidth` in `[0.5, 3]`, `fill` restricted to
`none`|`currentColor`) and an `icons` map (name → element list) whose elements are a closed
seven-primitive whitelist — `path`, `rect`, `circle`, `ellipse`, `line`, `polyline`, `polygon` —
each with its own closed attribute set (an attribute outside that tag's own set is rejected, e.g.
a `path` may never carry `x`/`y`). A `path`'s `d` and a `polyline`/`polygon`'s `points` are
restricted to a numeric-geometry character grammar (no letters beyond the SVG path commands, no
`<`/`>`/`;` — script, hrefs, and CSS are structurally inexpressible). `tools/validate.py` layers on
what JSON Schema itself cannot express: every numeric geometry attribute must be **finite** (a
JSON literal like `1e400` is schema-valid but overflows to a non-finite value once parsed), and
the definition text must stay **≤ 256 KiB**.

**The licence/provenance split — HARD, no exceptions (the F1 ruling, SPEC F130.6 amended
2026-08-16).** The manifest above is deliberately closed to style+icons only — it carries NO
licence or provenance field of its own. `license` and `sourceUrl` (plus optional `version`) are
instead **required in the companion `<slug>.meta.json`** (validates against
`schemas/icon-meta.schema.json`, alongside the usual `author`/`description`/`audience`/`added`). A
`license`/`licence` member found INSIDE `<slug>.icon.json` is a HARD `tools/validate.py` rejection
naming the offense — the app's own `IconPackDefinitionSerializer` re-serializes only what its
schema defines (`schemaVersion`/`style`/`icons`), so a licence string smuggled into the manifest
would be silently dropped the moment the pack installs, unattributed.

**Icon names — the house contract (SPEC F130.2).** A pack's `icons` map keys are gated to
`^[a-z][a-z0-9-]*$`, ≤ 64 characters (`tools/validate.py`, mirrored in the JSON Schema's own
`propertyNames`). A pack may cover any SUBSET of names — covering a name outside the list below is
not wrong, merely inert (the admin UI has no slot for it today; an install-time WARN names every
ignored one). This is the exact set the house admin chrome's
`admin-ui/app/(authed)/_components/icons.tsx` exports today — the kebab-cased, `Icon`-suffix-
stripped form of each export (e.g. `PersonaCatalogIcon` → `persona-catalog`), published here per
PLAN T309 so a pack author has one place to check coverage without cloning the app repo:

| | | | |
|---|---|---|---|
| `dashboard` | `live` | `catalog` | `safe-content` |
| `health` | `persona` | `persona-catalog` | `booth-log` |
| `settings` | `sign-out` | `sun` | `moon` |
| `menu` | `close` | `vote-up` | `vote-down` |
| `restore` | `taste-thumb-up` | `taste-thumb-down` | `schedule` |
| `shows` | `wardrobe` | `editor` | `exploration` |

This table is a mirror, not the source of truth — `GenWave.Host.Icons.IconNameContract.Names` (app
repo) and `icons.tsx` (its own parity fact, `Story337_IconPacksSwapTheChrome.cs`) are what actually
govern the admin UI's rendering; if this table and that constant ever disagree, the app repo wins
and this table is stale (file an issue).
