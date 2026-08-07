<!--
Thanks for submitting to the shelf! The catalog carries three kinds of entry — persona, theme,
and font pack. Please read CONTRIBUTING.md before filling this out — it explains every item below
in full. Fill in the section for YOUR kind (Persona or Theme) below and delete the other one; the
checklists further down apply to either kind. Both CI and this checklist need to pass before a
maintainer will review.

Font packs are Dean-curated only — no community PRs; by arrangement only. See CONTRIBUTING.md's
"Font packs" section.
-->

## Persona

**Slug:** `<your-slug>`

**Distinctness statement (required):** what makes this DJ distinct from every other entry on
the shelf, in one line.

> _(fill in here)_

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

## 🇬🇧 English-first (required)

- [ ] This entry's prose is written in English, per the v1 English-first policy — persona:
      `soul`, `lore`, `quirks`, `samplePatter`, `description`; theme: `description`.

## 🚫 Hard bans attestation (required)

- [ ] This entry contains none of the following, regardless of its `audience` rating:
      hate/harassment content, sexualized minors, real-person impersonation, or
      trademarks/branding.
