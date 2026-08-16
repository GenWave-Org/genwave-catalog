<!--
Thanks for submitting to the shelf! The catalog carries six kinds of entry — persona, theme,
font pack, show, avatar pack, and icon pack. Please read CONTRIBUTING.md before filling this out —
it explains every item below in full. Fill in the section for YOUR kind (Persona, Theme, Show, or
Avatar Pack) below and delete the others; the checklists further down apply to any kind. Both CI
and this checklist need to pass before a maintainer will review.

Font packs AND icon packs are Dean-curated only — no community PRs; by arrangement only. See
CONTRIBUTING.md's "Font packs" and "Icon packs" sections.
-->

## Persona

**Slug:** `<your-slug>`

**Distinctness statement (required):** what makes this DJ distinct from every other entry on
the shelf, in one line.

> _(fill in here)_

- [ ] If this PR adds an optional `<slug>.avatar.png` sidecar face (SPEC F128.2): it clears the
      same PNG bar as an avatar pack item (magic bytes, exactly 512×512, ≤512 KiB, never
      animated) and the [🖼️ Likeness/CC0 image attestation](#-likenesscc0-image-attestation-image-carrying-entries-only)
      below is filled in. N/A if this persona has no sidecar face.

## Theme

**Slug:** `<your-slug>`

**Distinct look statement (required):** what makes this theme's look distinct from every other
entry on the shelf, in one line.

> _(fill in here)_

- [ ] `preview` swatches (`light` and `dark`) are present in `<slug>.meta.json`.
- [ ] AA contrast pairs pass locally: `python3 tools/validate.py` reports no `aa-contrast`
      violation (11 token pairs, ≥4.5:1, both modes — `tools/contrast.py`).
- [ ] Every `fonts.display`/`fonts.sans` asset references one of GenWave's five vendored faces
      only (`fraunces`, `fraunces-italic`, `source-sans-3`, `jetbrains-mono`, `grenze-gotisch`) —
      never a font-pack face, including one from this catalog.

## Show

**Slug:** `<your-slug>`

**Distinct format statement (required):** what makes this show's format distinct from every other
entry on the shelf, in one line — the format/vibe, not a DJ's personality or a look.

> _(fill in here)_

- [ ] `name` (≤60 chars), `tagline` (≤120 chars), and `flavor` (≤400 chars) are each within their
      SPEC F115.1 1x budget locally: `python3 tools/lint.py` reports no `show-name-budget` /
      `show-tagline-budget` / `show-flavor-budget` violation (warnings are fine; red is not).
- [ ] `suggestedPersona`, if present in `<slug>.meta.json`, is a persona slug already **on this
      shelf** (`entries/personas/<slug>/`) — the import modal only offers "also hire" when it
      resolves to a real, on-shelf persona entry (SPEC F118.3; an unknown or already-hired slug is
      fine too, it just means no offer, never a rejected import).

## Avatar Pack

**Slug:** `<your-slug>`

**Distinctness statement (required):** what makes this pack's style distinct from every other
entry on the shelf, in one line — the art style/vibe, not a DJ's personality or a show's format.

> _(fill in here)_

- [ ] Every PNG item clears the image bar locally: `python3 tools/validate.py` reports no
      `avatar-png-magic` / `avatar-png-dimensions` / `avatar-png-oversize` / `avatar-png-actl`
      violation — real PNG bytes (verified by magic bytes, never extension), exactly 512×512,
      ≤512 KiB per item, never animated (no APNG).
- [ ] The pack's items, summed, stay ≤6 MiB (`avatar-pack-ceiling`); every item `name` is unique
      within the pack (`avatar-duplicate-name`); every `file` an item names is actually shipped,
      and every shipped PNG is named by some item (`avatar-orphan-item-file` /
      `avatar-stowaway-asset`).
- [ ] The [🖼️ Likeness/CC0 image attestation](#-likenesscc0-image-attestation-image-carrying-entries-only)
      below is filled in for every item.

## ✅ Mechanical checks

- [ ] Schema-valid: `python3 tools/validate.py` passes locally, including all required fields
      (see README.md's field tables — CI is the authority on the exact list).
- [ ] `python3 tools/build_index.py` was run and the regenerated `index.json` is included in
      this PR.
- [ ] `tools/run_selftest.sh` is green locally.

## 🔞 Audience self-rating (required)

Check exactly one — it must match the `audience` value in your `<slug>.meta.json`.

- [ ] **`everyone`** — safe for unannounced play around anyone, including kids.
- [ ] **`mature`** — leans into innuendo, crude humor, dark themes, or anything you wouldn't
      want playing unannounced around a kid.

**One sentence why:**

> _(fill in here)_

I understand this rating is verified at review, and mature-leaning content submitted under
`everyone` will come back as a revision request, not a judgment call.

## 📜 CC0 dedication (required)

- [ ] I am the owner (or authorized to act on behalf of the owner) of the rights in this
      entry, and by submitting this PR I am dedicating it to the public domain under
      **CC0 1.0 Universal**, irrevocably — anyone may copy, modify, remix, or redistribute it,
      including for commercial use, with no attribution required and no way for me to revoke
      this later.

## 🖼️ Likeness/CC0 image attestation (image-carrying entries only)

Required for an **Avatar Pack** PR, and for a **Persona** PR that adds an optional
`<slug>.avatar.png` sidecar face (SPEC F128.1). N/A for every other kind — leave unchecked and
say "N/A, no image" if this PR carries no PNG.

- [ ] I created or own every image in this PR. It depicts no real person's likeness and no
      trademarked character. (A maintainer reviews each image by eye, the same way `samplePatter`
      is reviewed for tone.)

## 🇬🇧 English-first (required)

- [ ] This entry's prose is written in English, per the v1 English-first policy — persona:
      `soul`, `lore`, `quirks`, `samplePatter`, `description`; theme: `description`; show:
      `tagline`, `flavor`, `description`; avatar pack: `description`.

## 🚫 Hard bans attestation (required)

- [ ] This entry contains none of the following, regardless of its `audience` rating:
      hate/harassment content, sexualized minors, real-person impersonation, or
      trademarks/branding.
