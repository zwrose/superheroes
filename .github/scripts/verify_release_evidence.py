#!/usr/bin/env python3
"""Release-evidence check (stdlib only) — the #189 per-PR evidence pattern lifted to release level.

Runs in GitHub Actions on the release-please PR. It NEVER calls a live model — it verifies that
the *evidence* owed by this release exists, is a pass, and is bound to the released SHA. The
binding is what stops stale or copied evidence from passing (best-effort per #56, not
cryptographic).

Flow (the CLI wires the I/O; the functions below are pure and unit-tested):

  1. Classify the release range (via `classify_release`) → the owed instruments. This module is
     the ONLY consumer of the classifier at runtime; the owed-summary it emits is the single
     authority on what a release owes (#231) — the `release-eval` skill reads that summary and
     never re-derives it.
  2. Parse the LAST valid fenced `release-eval-evidence` JSON block across the PR's comments
     (a corrected re-post supersedes an earlier one).
  3. For each owed instrument, require a `verdict: pass` entry bound to the release head SHA:
       - acceptance → the evidence's `bundleSha256` equals the SHA-256 of `showrunner.bundle.js`
         at the release head (content binding — the #235 spine-provenance hash), AND the
         evidence's `releaseSha` equals the head SHA.
       - benchmark  → the evidence's `releaseSha` equals the head SHA (release-ref binding).
  4. Green iff every owed instrument is satisfied; a `neither` release owes nothing → trivially
     green. Otherwise red, naming what is missing.
"""
import argparse
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import classify_release  # noqa: E402

EVIDENCE_FENCE = "release-eval-evidence"
OWED_MARKER = "<!-- release-evidence-owed -->"
STATUS_CONTEXT = "release-evidence"

_FENCE_RE = re.compile(
    r"```" + re.escape(EVIDENCE_FENCE) + r"\s*\n(.*?)\n```",
    re.DOTALL,
)


def collect_entries(comment_bodies):
    """Return a flat list of instrument entries pooled across EVERY parseable
    `release-eval-evidence` block in every comment. Each entry inherits its block's top-level
    `releaseSha` when it lacks its own, so downstream binding sees the effective release SHA.

    Pooling (not last-block-wins) lets evidence be posted incrementally — acceptance in one
    comment, the benchmark in another — and still count. Staleness is not a risk: SHA-binding
    (below) rejects any entry not bound to the current release head, so an old block's entries
    can never satisfy a new release. A malformed block is skipped, never fatal."""
    entries = []
    for body in comment_bodies or []:
        if not isinstance(body, str):
            continue
        for m in _FENCE_RE.finditer(body):
            try:
                obj = json.loads(m.group(1))
            except ValueError:
                continue
            if not isinstance(obj, dict):
                continue
            block_sha = obj.get("releaseSha")
            for e in obj.get("instruments") or []:
                if not isinstance(e, dict):
                    continue
                entry = dict(e)
                entry.setdefault("releaseSha", block_sha)
                entries.append(entry)
    return entries


def verify_instrument(instrument, entries, head_sha, head_bundle_sha256):
    """(ok, reason) for one owed instrument, searched across the pooled entries. Fail-closed:
    any missing / mismatched fact fails and names the first offending fact — never a false
    pass. A single valid, SHA-bound `pass` entry satisfies the instrument."""
    mine = [e for e in (entries or []) if e.get("instrument") == instrument]
    if not mine:
        return False, f"no {instrument} evidence found in a release-eval-evidence block"

    reasons = []
    for entry in mine:
        if entry.get("verdict") != "pass":
            reasons.append(f"{instrument} verdict is {entry.get('verdict')!r}, not \"pass\"")
            continue
        bound = entry.get("releaseSha")
        if bound != head_sha:
            reasons.append(
                f"{instrument} evidence is bound to {bound!r}, not the release head {head_sha!r}")
            continue
        if instrument == classify_release.SPINE_INSTRUMENT:
            claimed = entry.get("bundleSha256")
            if not head_bundle_sha256:
                reasons.append("could not read showrunner.bundle.js at the release head to bind "
                               "the acceptance evidence")
                continue
            if claimed != head_bundle_sha256:
                reasons.append(
                    f"acceptance bundleSha256 {claimed!r} does not match the released bundle "
                    f"{head_bundle_sha256!r} (evidence is for a different spine)")
                continue
        return True, f"{instrument}: pass bound to {head_sha}"
    return False, "; ".join(reasons) or f"{instrument} evidence did not verify"


def build_summary(owed_result, entries, head_sha, head_bundle_sha256):
    """The authoritative owed-summary (dict). Records the release class, what is owed, what is
    satisfied vs missing, the per-instrument reason, and the SHA + bundle hash the skill must
    bind its evidence to. Also the pass/fail of the whole check."""
    owed = owed_result["owed"]
    satisfied, missing, reasons = [], [], {}
    for inst in owed:
        ok, reason = verify_instrument(inst, entries, head_sha, head_bundle_sha256)
        reasons[inst] = reason
        (satisfied if ok else missing).append(inst)

    commands = classify_release.instrument_commands()
    return {
        "schemaVersion": 1,
        "releaseSha": head_sha,
        "releaseClass": owed_result["class"],
        "owed": owed,
        "satisfied": satisfied,
        "missing": missing,
        "reasons": reasons,
        "bundleSha256": head_bundle_sha256,
        "commands": {k: commands[k] for k in owed},
        "ok": not missing,
    }


def sha256_file(path):
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None


def render_owed_comment(summary):
    """The sticky owed-summary comment body the check upserts on the release PR. Carries the
    marker (so the check can find/replace it and skip its own re-trigger) and the machine-readable
    block the `release-eval` skill reads."""
    status = "✓ satisfied" if summary["ok"] else "✗ evidence owed"
    lines = [
        OWED_MARKER,
        f"## Release evidence — {status}",
        "",
        f"Release class: **{summary['releaseClass']}** · head `{summary['releaseSha']}`",
        "",
    ]
    if not summary["owed"]:
        lines.append("This release owes no live instrument (docs-only / repo-plumbing). The "
                     "evidence check is green.")
    else:
        lines.append("Owed instruments and their status:")
        for inst in summary["owed"]:
            mark = "✓" if inst in summary["satisfied"] else "✗"
            lines.append(f"- {mark} **{inst}** — {summary['reasons'].get(inst, '')}")
        lines += [
            "",
            "Run the missing instrument(s), then post the evidence as a fenced "
            f"`{EVIDENCE_FENCE}` JSON block (the `release-eval` skill does this for you). "
            "The check re-verifies on each new comment.",
        ]
    lines += [
        "",
        "<details><summary>machine-readable owed summary</summary>",
        "",
        "```json",
        json.dumps(summary, indent=2, sort_keys=True),
        "```",
        "",
        "</details>",
    ]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="verify release evidence on the release PR")
    ap.add_argument("--head-sha", required=True, help="the release PR head SHA to bind to")
    ap.add_argument("--base", help="range base (default: last superheroes-v* tag)")
    ap.add_argument("--bundle", default="plugins/superheroes/lib/showrunner.bundle.js",
                    help="path to showrunner.bundle.js at the checked-out release head")
    ap.add_argument("--comments", help="path to a JSON file: array of comment bodies (strings) "
                    "or comment objects with a .body")
    ap.add_argument("--owed-comment-out", help="write the sticky owed-summary comment body here")
    args = ap.parse_args(argv)

    base = args.base if args.base else classify_release.last_release_tag(args.head_sha)
    paths = classify_release.changed_paths_in_range(base, args.head_sha)
    owed_result = classify_release.classify(paths)

    bodies = []
    if args.comments:
        with open(args.comments, encoding="utf-8") as fh:
            raw = json.load(fh)
        for item in raw or []:
            if isinstance(item, str):
                bodies.append(item)
            elif isinstance(item, dict):
                bodies.append(item.get("body") or "")
    entries = collect_entries(bodies)

    head_bundle = sha256_file(args.bundle)
    summary = build_summary(owed_result, entries, args.head_sha, head_bundle)

    if args.owed_comment_out:
        with open(args.owed_comment_out, "w", encoding="utf-8") as fh:
            fh.write(render_owed_comment(summary))

    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["ok"]:
        sys.stderr.write("✓ release evidence satisfied\n")
        return 0
    sys.stderr.write("✗ release evidence owed: %s\n" % ", ".join(summary["missing"]))
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
