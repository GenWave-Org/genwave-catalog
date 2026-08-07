# 🤝 Contributing to genwave-catalog

Thanks for wanting to add to the shelf. This is a community catalog for
[GenWave](https://github.com/GenWave-Org/genwave), carrying three kinds of entry: DJ **personas**
and **themes** (both open to community submission) and **font packs** (Dean-curated only — see
[Font packs](#font-packs-kind-font) below). Every entry here is something someone else's radio
station can drop straight in. That's a gift to strangers, so we ask a bit of care in return. This
doc is the full bar: what CI checks mechanically, and what a human reviews.

This walkthrough below is the **persona** path. Submitting a **theme** instead? Read this section
for the shared mechanics (prerequisites, validate/lint/index/selftest, the PR template), then
jump to [🎨 Theme submission](#-theme-submission) for what's different. Font packs don't follow
this path at all — see [Font packs](#font-packs-kind-font).

## 🚀 Start to finish

1. **Prerequisites** — Python 3.12 and `pip install jsonschema==4.19.2` (the exact pin
   `.github/workflows/ci.yml` installs). A different `jsonschema` version can validate
   differently than CI does, so match the pin, not just "some jsonschema".
2. **Fork and clone** this repo.
3. **Copy `entries/example-dj/`** to `entries/<your-slug>/`, then rename both files to
   `<your-slug>.persona.json` and `<your-slug>.meta.json`. `<your-slug>` must match
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
   persona, run the submission-length lint too, before you open a PR:
   ```
   python3 tools/lint.py
   ```
   `tools/lint.py` covers **persona cards only** today — it has nothing to say about a theme entry
   one way or the other, so a clean run here is not itself a theme quality signal. Warnings alone
   won't block a PR, but read them — see the "Keep the card tight" section below for why they're
   there. Red always needs fixing.
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
   only its own `entries/<slug>/` directory plus the regenerated `index.json` — never a
   second entry, and never `schemas/`, `tools/`, `fixtures/`, `.github/`, `README.md`,
   `CONTRIBUTING.md`, `LICENSE`, or `.gitattributes`. Infra changes go in their own PR
   (with no `entries/` edits), where they get reviewed as infra.

**Hard bans, regardless of rating, no exceptions:** hate/harassment content, sexualized minors,
real-person impersonation, trademarks/branding.

**Per kind:** items 1, 2, 4, 5, and 8 above apply to a theme exactly as written — schema-valid,
required fields present (against the theme schemas, not the persona ones), `audience`
self-rating, CC0 checkbox, scoped diff. Items 3 and 6 have a theme equivalent, not a persona-only
meaning: a theme still needs its own one-line distinctness statement (what makes this *look*
distinct, not this DJ), and English-first still applies to whatever prose a theme entry carries
(`description` — a theme has no `soul`/`lore`/`quirks`/`samplePatter` to translate). Item 7
(`tools/lint.py`'s prompt-weight budget) is **persona-only** and does not apply to a theme — a
theme carries no field that rides into a runtime model prompt. A theme submission adds two gates
of its own with no persona equivalent (AA contrast, vendored-five faces) — see
[🎨 Theme submission](#-theme-submission) below. Font packs don't clear this bar at all —
curated only, see [Font packs](#font-packs-kind-font).

The rest of this doc walks through items 3–7 one at a time, for a persona; theme specifics are
their own section below.

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

1. **Copy an existing theme entry** — e.g. `entries/graveyard-shift/` — to `entries/<your-slug>/`,
   then rename both files to `<your-slug>.theme.json` and `<your-slug>.meta.json`. Same slug rule
   as personas: `^[a-z0-9]+(-[a-z0-9]+)*$` (README.md's
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
which of the 8 items carry over as-is, which have a theme equivalent, and which are persona-only.

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
`entries/<slug>/` holding `<slug>.font.json`, `<slug>.meta.json`, the woff2 face(s), and the
upstream's own `OFL.txt` byte-identical. CI enforces the schemas, the 200 KiB pack ceiling,
licence allowlist, and stowaway/orphan/duplicate checks (`tools/validate.py`).
