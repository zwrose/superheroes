#!/usr/bin/env python3
"""Deterministic, additive-only doc focus flags for review-spec (#515).

A small stdlib-only helper the review-spec skill runs over the spec text to compute
**additive emphasis** for the reviewer dispatch prompt. It is deterministic (the same
spec text always yields the same output) and **never narrows the dispatch**: the flags
add focus notes the dispatching skill folds into the per-agent prompt's `Focus:` line;
they do not drop, skip, or re-tier any script-owned dimension. No match → no note.

CLI:

    python3 doc_focus_flags.py --spec <path>

prints a JSON object `{"flags": [...], "focusNote": "<joined text or empty>"}`.

Triggers (case-insensitive, word-boundary-ish over the spec text):
  - **migration** — a spec touching a migration/backfill/schema change.
  - **external-service** — a spec naming an external/third-party service, API, or webhook.
"""
import argparse
import json
import re
import sys

# Each trigger: (flag, note, [keyword patterns]). Patterns are matched case-insensitively
# with word boundaries so a keyword embedded in an unrelated word does not false-trigger.
_TRIGGERS = [
    ("migration",
     "This spec touches a migration — emphasize rollback / back-out and data-safety "
     "unhappy paths.",
     # stems catch inflections/plurals: migrate/migration/migrating/migrations,
     # backfill/backfills/backfilling.
     [r"migrat\w*", r"backfill\w*", r"schema change"]),
    ("external-service",
     "This spec names external services — emphasize dependency-failure, timeout, and "
     "degraded-mode paths.",
     # APIs / webhooks / integrations catch the plural/inflected forms too.
     [r"external service", r"third-party", r"3rd-party", r"APIs?", r"webhooks?",
      r"upstream service", r"integrations?", r"remote service"]),
]

_COMPILED = [
    (flag, note, [re.compile(r"\b%s\b" % p, re.IGNORECASE) for p in patterns])
    for flag, note, patterns in _TRIGGERS
]


def compute_flags(text):
    """Return (flags, focusNote) for the given spec text. Deterministic and additive-only:
    flags are emitted in a fixed order; focusNote joins the matched notes (empty on no match)."""
    text = text or ""
    flags, notes = [], []
    for flag, note, regexes in _COMPILED:
        if any(rx.search(text) for rx in regexes):
            flags.append(flag)
            notes.append(note)
    return flags, " ".join(notes)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="deterministic additive-only doc focus flags for review-spec")
    parser.add_argument("--spec", required=True, help="path to the spec text to scan")
    args = parser.parse_args(argv)
    try:
        with open(args.spec, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        text = ""
    flags, focus_note = compute_flags(text)
    sys.stdout.write(json.dumps({"flags": flags, "focusNote": focus_note}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
