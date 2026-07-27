# 🤝 Contributing to genwave-catalog

Thanks for wanting to add a DJ to the shelf. This is a community catalog of
[GenWave](https://github.com/GenWave-Org/genwave) persona cards — every entry here is a
character someone else's radio station can drop straight in. That's a gift to strangers, so
we ask a bit of care in return. This doc is the full bar: what CI checks mechanically, and
what a human reviews.

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
   Fix every violation it prints — each one names the offending file and rule.
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

**Hard bans, regardless of rating, no exceptions:** hate/harassment content, sexualized minors,
real-person impersonation, trademarks/branding.

The rest of this doc walks through items 3–6 one at a time.

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

Everything in this repo is released under **CC0 1.0 Universal** — see [`LICENSE`](./LICENSE).
By opening a PR here and checking the CC0 box in the template, you are dedicating your entry
to the public domain, irrevocably. That means anyone — including for-profit use — can copy,
modify, remix, or redistribute your persona with no attribution required and no way for you
to take it back later. Only submit a persona you actually own the rights to and are genuinely
willing to give away on those terms. If that gives you pause, that's worth listening to before
you open the PR, not after it's merged.

### 🇬🇧 English-first

For v1, entries must be written in English — `soul`, `lore`, `quirks`, `samplePatter`,
`description`, all of it. This isn't a judgment on other languages; it's a scope limit on what
a small volunteer review team (ie. just me right now) can evaluate for the other five bar items right now.

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
