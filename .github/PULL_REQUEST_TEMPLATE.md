<!--
Thanks for submitting a DJ! Please read CONTRIBUTING.md before filling this out — it explains
every item below in full. Fill in every blank; don't delete a section because it feels
redundant with CI. Both CI and this checklist need to pass before a maintainer will review.
-->

## Persona

**Slug:** `<your-slug>`

**Distinctness statement (required):** what makes this DJ distinct from every other entry on
the shelf, in one line.

> _(fill in here)_

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
      persona entry, and by submitting this PR I am dedicating it to the public domain under
      **CC0 1.0 Universal**, irrevocably — anyone may copy, modify, remix, or redistribute it,
      including for commercial use, with no attribution required and no way for me to revoke
      this later.

## 🇬🇧 English-first (required)

- [ ] This entry (`soul`, `lore`, `quirks`, `samplePatter`, `description`) is written in
      English, per the v1 English-first policy.

## 🚫 Hard bans attestation (required)

- [ ] This entry contains none of the following, regardless of its `audience` rating:
      hate/harassment content, sexualized minors, real-person impersonation, or
      trademarks/branding.
