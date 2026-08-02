#!/usr/bin/env python3
"""Lint genwave-catalog persona cards against submission length budgets
(SPEC F89.6).

Rules enforced, each a two-tier check (WARN, then HARD if far enough over):

  - soul-budget: len(soul) — warn > 600 chars, hard > 1200 chars.
  - quirk-budget: len(each quirks[i]) — warn > 120 chars, hard > 240 chars.
  - quirk-count: len(quirks) outside 2..6 — WARN ONLY, no hard tier.
  - lore-budget: len(each lore[i]) — warn > 200 chars, hard > 400 chars.
  - prompt-weight: worst-case prompt weight — warn > 900 chars, hard > 1800
    chars. Weight = len(soul) + sum of the 3 LONGEST quirks + len(name); the
    app samples 2-3 quirks per break (genwave SPEC F71.3), so the 3 longest
    bound what can actually reach the model in one prompt.
  - verbosity-phrase: WARN ONLY. Case-insensitive substring match, over soul
    and each quirk, for a fixed phrase list ("ramble", "at length", "in
    great detail", "always describe", "go on about") — text that instructs
    the model to run long defeats the length budgets above from the inside.
  - dead-rule: for each well-typed rule in pronunciations[], mirrors the
    app's GenWave.Tts.PronunciationRuleSet.Create drop predicate EXACTLY
    (genwave src/GenWave.Tts/PronunciationRuleSet.cs) so a card author is
    told at submission time which rules the render path will silently drop
    (SPEC F89.7). A rule is dead if ANY of: pattern blank; effective word
    (word if non-blank, else pattern — mirrors PronunciationRule.Parse's
    default; a missing or null word is blank the same as an empty string)
    blank; ipa blank; ipa contains ')', '[', or ']'; effective word not
    contained in pattern case-insensitively. HARD ONLY — one line per dead
    rule naming every failed condition, so an author fixes all of them in
    one round.
  - word-repeat: WARN ONLY, for rules that are NOT already dead. Effective
    word occurs more than once in pattern (case-insensitive) — only the
    first occurrence binds (same rule the app's Create documents), later
    occurrences are unreachable.

A hard finding implies its warn threshold was also crossed; only the HARD
line is printed for that field+check, never both.

Every message states the measured value against its budget, e.g.
"soul is 1301 chars (warn 600, hard 1200)".

Scope: every entries/<slug>/<slug>.persona.json under --root, INCLUDING
example-dj (it's the template people copy, and must stay within budget too).
A card that fails to parse as JSON, or whose soul/name/quirks/lore fields are
missing or not the expected type, is SKIPPED SILENTLY — malformed JSON/shape
is tools/validate.py's law, not this lint's, and this tool must never crash
on garbage input (every field is read with .get() plus a type check). The
same silent-skip contract applies to pronunciations independently of the
rest of the card: missing, null, or not a list skips dead-rule/word-repeat
entirely; a non-dict list item, or a rule whose pattern/ipa/word is present
but wrong-typed, skips that one rule — wrong types are schema law
(tools/validate.py + the bad-pronunciations-type red fixture), not this
lint's. An entries/<slug> directory that is itself a symlink (or a symlink
anywhere under it) is SKIPPED SILENTLY too, before any file inside it is
opened (tools/catalog_lib.py: find_symlinks) — trusting a symlinked entry
could make this lint read bytes from outside the tree being checked, and
validate.py already owns the loud violation for that case.

Output: WARN findings print as `::warning file=<repo-relative
path>::<rule>: <message>` when the GITHUB_ACTIONS environment variable is
set (GitHub Actions log annotation syntax), else as
`WARN <repo-relative path>: <rule>: <message>`. Warnings alone never fail
the run (exit 0). HARD findings always print as
`<repo-relative path>: <rule>: <message>` (validate.py's own style,
regardless of GITHUB_ACTIONS) and any HARD finding makes the run fail
(exit 1).

Stdlib only — no jsonschema. This lint reads JSON with the `json` module and
never touches schemas/, so a jsonschema version drift can't affect it (that
dependency, and the shape law it enforces, stay with tools/validate.py).

Usage:
    tools/lint.py [--root PATH]

--root overrides where entries/ is read from (default: repo root) — this is
what lets tools/run_selftest.sh point at tools/testdata/red/<variant>/ and
tools/testdata/warn/<variant>/ without a copy of the real catalog. Findings
are always reported with paths relative to this script's own repo (matching
tools/validate.py), not relative to --root.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from catalog_lib import REPO_ROOT, discover_entry_dirs, find_symlinks, rel

# SPEC F89.6 submission-length budgets. These numbers are REASONED, NOT
# FITTED: they encode a judgment call about what a break-length TTS prompt
# should carry, not a curve fit to catalog data. Revisit once genwave T143
# field data (measured render time / listener drop-off vs. prompt length)
# exists. Real catalog maxima measured 2026-08-02: soul 413, quirk 85,
# lore 128, worst-case weight 622, quirk counts 2..3 — all well inside these
# budgets, so grandfather-clean holds today with zero warnings.
SOUL_WARN = 600
SOUL_HARD = 1200
QUIRK_WARN = 120
QUIRK_HARD = 240
QUIRK_COUNT_MIN = 2
QUIRK_COUNT_MAX = 6
LORE_WARN = 200
LORE_HARD = 400
WEIGHT_WARN = 900
WEIGHT_HARD = 1800
PROMPT_WEIGHT_SAMPLE_SIZE = 3  # genwave SPEC F71.3: 2-3 quirks sampled per break

VERBOSITY_PHRASES = (
    "ramble",
    "at length",
    "in great detail",
    "always describe",
    "go on about",
)

WARN = "WARN"
HARD = "HARD"

# One finding: (tier, rule id, message). Path is attached by the caller once
# the card's fields are known to be well-shaped.
Finding = tuple[str, str, str]


def load_card_fields(card_path: Path) -> tuple[str, list[str], list[str], str, object] | None:
    """Read and shape-check a persona card. Returns (soul, quirks, lore,
    name, pronunciations) when soul/name/quirks/lore are present and
    correctly typed, else None — a silent skip, per this tool's contract
    (shape law belongs to validate.py, not here). pronunciations is handed
    back RAW and unchecked — unlike the other four fields it is optional on
    a card (SPEC F89.5), so its own shape law (missing/null/not-a-list, or a
    malformed item within it) is check_pronunciation_rules' silent-skip
    contract to enforce, not a reason to drop the rest of the card's
    findings."""
    try:
        raw = card_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        card = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(card, dict):
        return None

    soul = card.get("soul")
    name = card.get("name")
    quirks = card.get("quirks")
    lore = card.get("lore")
    pronunciations = card.get("pronunciations")

    if not isinstance(soul, str) or not isinstance(name, str):
        return None
    if not isinstance(quirks, list) or not all(isinstance(q, str) for q in quirks):
        return None
    if not isinstance(lore, list) or not all(isinstance(entry, str) for entry in lore):
        return None

    return soul, quirks, lore, name, pronunciations


def check_soul_budget(soul: str) -> list[Finding]:
    length = len(soul)
    message = f"soul is {length} chars (warn {SOUL_WARN}, hard {SOUL_HARD})"
    if length > SOUL_HARD:
        return [(HARD, "soul-budget", message)]
    if length > SOUL_WARN:
        return [(WARN, "soul-budget", message)]
    return []


def check_quirk_budget(quirks: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for i, quirk in enumerate(quirks):
        length = len(quirk)
        message = f"quirks[{i}] is {length} chars (warn {QUIRK_WARN}, hard {QUIRK_HARD})"
        if length > QUIRK_HARD:
            findings.append((HARD, "quirk-budget", message))
        elif length > QUIRK_WARN:
            findings.append((WARN, "quirk-budget", message))
    return findings


def check_quirk_count(quirks: list[str]) -> list[Finding]:
    count = len(quirks)
    if count < QUIRK_COUNT_MIN or count > QUIRK_COUNT_MAX:
        message = f"quirks has {count} entries (want {QUIRK_COUNT_MIN}..{QUIRK_COUNT_MAX})"
        return [(WARN, "quirk-count", message)]
    return []


def check_lore_budget(lore: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for i, entry in enumerate(lore):
        length = len(entry)
        message = f"lore[{i}] is {length} chars (warn {LORE_WARN}, hard {LORE_HARD})"
        if length > LORE_HARD:
            findings.append((HARD, "lore-budget", message))
        elif length > LORE_WARN:
            findings.append((WARN, "lore-budget", message))
    return findings


def check_prompt_weight(soul: str, quirks: list[str], name: str) -> list[Finding]:
    longest = sorted((len(q) for q in quirks), reverse=True)[:PROMPT_WEIGHT_SAMPLE_SIZE]
    weight = len(soul) + sum(longest) + len(name)
    message = f"worst-case prompt weight is {weight} chars (warn {WEIGHT_WARN}, hard {WEIGHT_HARD})"
    if weight > WEIGHT_HARD:
        return [(HARD, "prompt-weight", message)]
    if weight > WEIGHT_WARN:
        return [(WARN, "prompt-weight", message)]
    return []


def check_verbosity_phrases(soul: str, quirks: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    lowered_soul = soul.lower()
    for phrase in VERBOSITY_PHRASES:
        if phrase in lowered_soul:
            findings.append((WARN, "verbosity-phrase", f"soul contains verbosity-instructing phrase '{phrase}'"))
    for i, quirk in enumerate(quirks):
        lowered_quirk = quirk.lower()
        for phrase in VERBOSITY_PHRASES:
            if phrase in lowered_quirk:
                findings.append(
                    (WARN, "verbosity-phrase", f"quirks[{i}] contains verbosity-instructing phrase '{phrase}'")
                )
    return findings


def check_pronunciation_rules(pronunciations: object) -> list[Finding]:
    """dead-rule (HARD) + word-repeat (WARN) — SPEC F89.7. Mirrors the app's
    GenWave.Tts.PronunciationRuleSet.Create drop predicate EXACTLY (genwave
    src/GenWave.Tts/PronunciationRuleSet.cs, Create method) so a card author
    is told at submission time which rules the render path will silently
    drop, instead of finding out only when a pronunciation never takes
    effect on air.

    Silent-skip lane (this lint's standing contract, not validate.py's):
    pronunciations missing, null, or not a list skips this check entirely;
    a list item that isn't a dict, or a well-formed dict whose pattern/ipa/
    word is present but wrong-typed, skips that one rule — wrong types are
    schema law (tools/validate.py + the bad-pronunciations-type red
    fixture), not this lint's. Only well-typed rules (pattern: str, ipa:
    str, word: str or None) reach the dead-rule/word-repeat analysis below.
    """
    findings: list[Finding] = []
    if not isinstance(pronunciations, list):
        return findings

    for i, rule in enumerate(pronunciations):
        if not isinstance(rule, dict):
            continue
        pattern = rule.get("pattern")
        ipa = rule.get("ipa")
        word = rule.get("word")
        if not isinstance(pattern, str) or not isinstance(ipa, str):
            continue
        if word is not None and not isinstance(word, str):
            continue

        # A missing/null/whitespace-only word defaults to pattern, mirroring
        # PronunciationRule.Parse's IsNullOrWhiteSpace default.
        effective_word = word if isinstance(word, str) and word.strip() else pattern

        conditions: list[str] = []
        if not pattern.strip():
            conditions.append("pattern is blank")
        if not effective_word.strip():
            conditions.append("word is blank")
        if not ipa.strip():
            conditions.append("ipa is blank")
        for bad_char in (")", "[", "]"):
            if bad_char in ipa:
                conditions.append(f"ipa contains '{bad_char}' (breaks [word](ipa)/[pause] markup)")
        # .lower() on both sides is the closest Python analog of the app's
        # StringComparison.OrdinalIgnoreCase Contains check (parity target).
        # Known exotic gap: a handful of compatibility codepoints (the
        # Kelvin sign, long s "ſ", micro sign "µ") case-fold differently
        # under .NET's OrdinalIgnoreCase than under Python's str.lower() —
        # no realistic card's pattern/word touches these, so it's accepted
        # rather than chased with a custom fold table.
        if effective_word.lower() not in pattern.lower():
            conditions.append(f"word '{effective_word}' does not occur in pattern '{pattern}'")

        if conditions:
            findings.append((HARD, "dead-rule", f"pronunciations[{i}]: " + "; ".join(conditions)))
            continue

        occurrences = pattern.lower().count(effective_word.lower())
        if occurrences > 1:
            findings.append(
                (
                    WARN,
                    "word-repeat",
                    f"pronunciations[{i}]: word '{effective_word}' occurs {occurrences} times in pattern "
                    f"'{pattern}' — only the first occurrence binds, later ones are unreachable",
                )
            )

    return findings


def lint_card(soul: str, quirks: list[str], lore: list[str], name: str, pronunciations: object) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(check_soul_budget(soul))
    findings.extend(check_quirk_budget(quirks))
    findings.extend(check_quirk_count(quirks))
    findings.extend(check_lore_budget(lore))
    findings.extend(check_prompt_weight(soul, quirks, name))
    findings.extend(check_verbosity_phrases(soul, quirks))
    findings.extend(check_pronunciation_rules(pronunciations))
    return findings


def format_finding(tier: str, label: str, rule: str, message: str, github_actions: bool) -> str:
    if tier == HARD:
        return f"{label}: {rule}: {message}"
    if github_actions:
        return f"::warning file={label}::{rule}: {message}"
    return f"WARN {label}: {rule}: {message}"


def lint_entries(entries_dir: Path) -> list[tuple[str, str, str, str]]:
    """Every finding across every entry under entries_dir, as
    (tier, repo-relative label, rule, message) tuples."""
    results: list[tuple[str, str, str, str]] = []
    for entry_dir in discover_entry_dirs(entries_dir):
        # Symlinks are never trusted (tools/catalog_lib.py: find_symlinks) —
        # checked before any file in this entry is opened. A symlinked entry
        # dir or persona card could otherwise make this lint read bytes from
        # outside the tree being checked. validate.py owns the loud
        # violation for this; the lint's contract is silent-skip, matching
        # how a malformed card is already handled below.
        if find_symlinks(entry_dir):
            continue
        slug = entry_dir.name
        card_path = entry_dir / f"{slug}.persona.json"
        fields = load_card_fields(card_path)
        if fields is None:
            continue
        soul, quirks, lore, name, pronunciations = fields
        label = rel(REPO_ROOT, card_path)
        for tier, rule, message in lint_card(soul, quirks, lore, name, pronunciations):
            results.append((tier, label, rule, message))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="directory containing entries/ to lint (default: repo root)",
    )
    args = parser.parse_args()
    root = args.root.resolve()

    github_actions = bool(os.environ.get("GITHUB_ACTIONS"))

    findings = lint_entries(root / "entries")

    for tier, label, rule, message in findings:
        print(format_finding(tier, label, rule, message, github_actions))

    hard_count = sum(1 for tier, *_ in findings if tier == HARD)
    warn_count = sum(1 for tier, *_ in findings if tier == WARN)

    if hard_count:
        print(f"FAIL: {hard_count} violation(s)")
        return 1

    if warn_count:
        print(f"PASS: catalog within submission budgets ({warn_count} warning{'s' if warn_count != 1 else ''})")
    else:
        print("PASS: catalog within submission budgets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
