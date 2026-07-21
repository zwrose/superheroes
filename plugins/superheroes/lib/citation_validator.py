#!/usr/bin/env python3
"""Deterministic dangling-citation validator for the `spec` definition-doc (#517, D3).

The provenance pincer's review-side deterministic leg. The-architect's authoring rule
(CONVENTIONS §3.2) requires load-bearing **mirror-facts** — spec statements the repo could
contradict — to carry an inline **citation** naming the repo source. This module is the
review-spec compile step's check that every such citation **resolves**: the cited path
exists, and (when an anchor is given) the anchor text occurs in that file. A citation that
points at nothing — a fabricated or superseded source — is the #205 fabricated-fact class
made mechanically catchable, so this check **fails closed**: a dangling citation, an
unreadable spec, or a citation the parser cannot resolve all yield a blocking finding, never
a silent clean.

An emitted finding is a **blocking-class** (Important) finding surfaced to the
**owner-gated** review-spec loop — not a mechanical gate (review-spec never auto-writes
`passed`). This reconciles the "blocking" wording here with CONVENTIONS/LEDGERS' "never
blocks": the finding is blocking-class in the rubric, but only the owner-gated loop, not
this check, decides the verdict.

This is the deterministic half only. **Content-match — does the cited source actually SAY
what the spec claims — stays verifier judgment** (the Grounding seat,
`skills/review-spec/reference/provenance.md`); this module never reads intent, only existence.

Citation grammar (the §11 cross-boundary fact — this module's `CITATION_RE` is its one
authoritative home; the template/skill examples are drift-tested against it):

    [cite: <repo-relative-path>]
    [cite: <repo-relative-path> § <anchor>]

`<path>` is resolved against the repo root; `<anchor>` (optional, after ` § `) is a literal
substring the reader can find in the file (a symbol, heading, or quoted phrase). The
`<anchor>` must be a simple substring that does NOT contain `]` or a newline — the grammar
truncates the anchor at the first `]` / end of line.

Consumer: the review-spec compile step (SKILL §4). Ledger: LEDGERS.md §1. stdlib only.
"""
import argparse
import json
import os
import re
import sys

# --- the citation grammar: ONE authoritative home (CONVENTIONS §11) ------------
# `[cite: <path>]` or `[cite: <path> § <anchor>]`. The path is every char up to a
# ` § ` anchor separator or the closing `]`; the anchor is the remainder before `]`.
CITATION_RE = re.compile(r"\[cite:\s*(?P<path>[^\]\n]+?)(?:\s*§\s*(?P<anchor>[^\]\n]+?))?\s*\]")


def parse_citations(text):
    """Yield (path, anchor_or_None, line_number) for every citation in `text`.
    line_number is 1-indexed. The single public parse entrypoint over CITATION_RE."""
    out = []
    for i, line in enumerate(text.splitlines(), start=1):
        for m in CITATION_RE.finditer(line):
            path = m.group("path").strip()
            anchor = m.group("anchor")
            out.append((path, anchor.strip() if anchor else None, i))
    return out


def _finding(idx, line, title, body, suggestion, evidence, taxonomy="dangling-citation"):
    """A base-rubric findings-schema entry. Important + Grounding, High confidence (the
    check is deterministic — an unresolved citation is certain). `evidence` is the concise
    trigger+impact string (review-base's definition), distinct from the fuller `body`."""
    return {
        "id": "citation-%03d" % idx,
        "severity": "Important",
        "dimension": "Grounding",
        "taxonomy": taxonomy,
        "title": title,
        "file": None,  # set by check() to the spec path
        "line": line,
        "body": body,
        "suggestion": suggestion,
        "evidence": evidence,
        "confidence": "High",
    }


def check(spec_path, root):
    """Validate every citation in the spec at `spec_path` against the repo at `root`.
    Returns a list of base-rubric findings (empty when every citation resolves).

    Fail-closed: an unreadable spec yields one finding (never an empty/clean result); a
    citation whose path is missing, or whose anchor is absent from the file, yields a
    finding. A cited path that exists (and whose anchor, if any, is present) yields none.
    """
    findings = []
    try:
        with open(spec_path, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        # line=1 (not None): review-spec §4 step 1 drops any finding with line == null,
        # so a null-line fail-closed finding would silently vanish. Anchor it at line 1.
        f = _finding(1, 1,
                     "Citation validator could not read the spec",
                     "The spec at %s could not be read (%s), so its citations are "
                     "UNVERIFIED. Failing closed: treat provenance as unconfirmed."
                     % (spec_path, exc),
                     "Re-run the review once the spec path is readable.",
                     "spec at %s could not be read (%s) — its citations are unverifiable, "
                     "so provenance is unconfirmed" % (spec_path, exc))
        f["file"] = spec_path
        return [f]

    idx = 0
    for line, text_line in enumerate(text.splitlines(), start=1):
        spans = []
        for m in CITATION_RE.finditer(text_line):
            spans.append((m.start(), m.end()))
            path = m.group("path").strip()
            anchor = m.group("anchor")
            anchor = anchor.strip() if anchor else None
            target = os.path.join(root, path)
            if not os.path.isfile(target):
                idx += 1
                findings.append(_finding(
                    idx, line,
                    "Dangling citation: %s" % path,
                    "The spec cites `%s`%s, but that path resolves to no file at the repo "
                    "root (missing, or the path is a directory). A citation that resolves to "
                    "nothing is a fabricated or superseded source (the #205 fabricated-fact "
                    "class). Failing closed → blocking." % (
                        path, (" § %s" % anchor) if anchor else ""),
                    "Fix the path to a real repo file, or remove the mirror-fact if it no longer "
                    "holds. If this is not a repo mirror-fact, it should not carry a `[cite: …]`.",
                    "cited path `%s` resolves to no repo file — the spec asserts a repo fact "
                    "with no real source" % path))
                continue
            if anchor:
                try:
                    with open(target, encoding="utf-8") as fh:
                        body = fh.read()
                except (OSError, UnicodeDecodeError):
                    # Fail CLOSED: the cited file exists but we cannot read it to confirm the
                    # anchor. Do NOT claim the anchor is stale/fabricated — we simply don't know.
                    idx += 1
                    findings.append(_finding(
                        idx, line,
                        "Unreadable cited file: %s § %s" % (path, anchor),
                        "The spec cites `%s § %s`, but the cited file `%s` could not be read "
                        "(e.g. binary / non-UTF-8) to confirm the anchor `%s` — failing "
                        "closed." % (path, anchor, path, anchor),
                        "Ensure the cited file is a readable UTF-8 text file, or drop the "
                        "anchor.",
                        "cited file `%s` could not be read (binary / non-UTF-8) — the anchor "
                        "`%s` cannot be confirmed" % (path, anchor)))
                    continue
                if anchor not in body:
                    idx += 1
                    findings.append(_finding(
                        idx, line,
                        "Dangling citation anchor: %s § %s" % (path, anchor),
                        "The spec cites `%s § %s`, but the anchor text `%s` does not occur in "
                        "that file. The path resolves but the anchor is stale or fabricated. "
                        "Failing closed → blocking." % (path, anchor, anchor),
                        "Update the anchor to a string that appears in `%s`, or drop the anchor. "
                        "(Content-match — whether the source SAYS what the spec claims — is the "
                        "Grounding verifier's judgment, not this check's.)" % path,
                        "anchor `%s` is absent from cited file `%s` — the spec's provenance "
                        "anchor points at text that is not there" % (anchor, path)))
        # A malformed `[cite:` marker (no closing `]`, or split across lines) is not matched
        # by CITATION_RE, so it would silently yield NO finding — fail-open. Emit one finding
        # per `[cite:` occurrence whose start is not inside a matched (valid-citation) span.
        for mm in re.finditer(r"\[cite:", text_line):
            if any(s <= mm.start() < e for (s, e) in spans):
                continue
            idx += 1
            findings.append(_finding(
                idx, line,
                "Malformed citation marker",
                "a `[cite:` marker here is malformed (missing closing `]`, or split across "
                "lines) — the parser cannot resolve it; fix the marker. Failing closed.",
                "Close the `[cite: …]` marker with a `]` on the same line.",
                "a `[cite:` marker on this line has no resolvable close — the parser cannot "
                "extract a path, so the provenance claim is unverifiable",
                taxonomy="malformed-citation"))
    for f in findings:
        f["file"] = spec_path
    return findings


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="validate a spec's citations; emit a JSON findings array")
    c.add_argument("--spec", required=True, help="path to the spec definition-doc")
    c.add_argument("--root", required=True, help="repo root the citations resolve against")
    args = p.parse_args(argv)
    findings = check(args.spec, args.root)
    sys.stdout.write(json.dumps(findings) + "\n")
    # Exit 0 always: the findings array is the product; a non-zero exit would let a caller
    # mistake "citations checked, some dangling" for "validator crashed". The compile step
    # reads the array, not the exit code.
    return 0


if __name__ == "__main__":
    sys.exit(main())
