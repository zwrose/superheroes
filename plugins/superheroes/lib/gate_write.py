#!/usr/bin/env python3
"""The trio's gate-write handshake — ONE tested place (was inlined bash in 3 skills).

review-crew's review-plan / review-tasks (mode **certify**) and review-spec (mode
**reset**) record a definition-doc's review gate via the definition-doc lib. This helper
performs the whole guarded handshake so a fix lives in one place — the previous
near-verbatim duplication across the three SKILL.md files let a fix miss one copy and
resurface as a bug a review round later.

In the consolidated one-plugin tree `definition_doc.py` is a same-tree sibling, so this
wrapper imports it directly (no cross-plugin resolution, no subprocess).

The handshake:

  **canonical-path guard** (`samefile`): refuse to stamp a doc other than the one
    reviewed, because definition_doc's `set-gate` reconstructs the canonical
    `docs/superheroes/<work-item>/<doc>.md` from `--work-item`
  → **certify**: parent-gate precondition (downgrade `passed`→`changes-requested` when the
    parent doc isn't approved), then `set-gate <review>`
  → **reset** (spec only): revoke a *stale* owner approval — read the gate; if it is
    `passed`, `set-gate pending`; otherwise no-op. It **never** writes `passed` (the
    advisory invariant: review-spec revokes, the owner grants).

It **degrades, it does not crash**: every path prints a clear message to stderr and a short
outcome token on stdout (the calling skill surfaces it in its terminal summary). It never
hand-edits YAML — definition_doc is the single frontmatter writer.

**Exit codes carry gate-integrity intent, not just crashed-or-not.** A `certify` that produced a
verdict but could NOT record it (`skipped:noncanonical`, `failed:set-gate`) exits **non-zero
(3)**: it leaves the gate at `pending`, which is indistinguishable from "no review ran" — and
definition_doc's self-certify branch would otherwise upgrade that `pending` to `passed`, a
green gate with no real review. `recorded:*` exits 0. `reset` mode always exits 0: it is
advisory revoke-only and never grants `passed`, so a skipped reset is a warning, not a
gate-integrity failure.

stdlib only (the band convention). Outcome tokens (stdout): `recorded:passed`,
`recorded:changes-requested`, `reset:pending`, `noop:not-approved`,
`skipped:noncanonical`, `skipped:unreadable`, `failed:set-gate`.
"""
import argparse
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
import definition_doc  # noqa: E402  (same-tree sibling; the single frontmatter writer)


def _say(detail):
    sys.stderr.write(detail + "\n")


def _emit(token):
    sys.stdout.write(token + "\n")


def _doc(work_item, doc, root):
    """The doc's real path for the gate handshake: mode-aware (cwd defaults to the repo
    root). If the mode is undeterminable (a newer registry schema → UnknownSchemaVersion),
    fall back to the pure in-repo default so the gate guard degrades rather than crashes;
    UFR-7's halt-with-notice belongs to the the-architect WRITE path (Task 6), not the gate
    read/write. Only that specific exception is caught — any other error propagates."""
    import mode_registry
    try:
        d = definition_doc.resolve_work_item_dir(work_item, root=root, cwd=root)
    except mode_registry.UnknownSchemaVersion:
        return definition_doc.doc_path(work_item, doc, root)
    return os.path.join(d, doc + ".md")


def _canonical(root, work_item, doc):
    # The guard compares the reviewed doc against the resolved canonical path with samefile.
    return _doc(work_item, doc, root)


def _same_file(a, b):
    """`-ef` equivalent: True iff a and b are the same file; False if either is absent."""
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def _read_gate(doc, work_item, root):
    """Return (ok, value). On failure ok=False and value holds the error text."""
    try:
        return True, definition_doc.read_gate(_doc(work_item, doc, root))
    except (ValueError, OSError) as exc:
        return False, str(exc)


def _set_gate(doc, work_item, review, root):
    """Return (ok, err). definition_doc is the sole frontmatter writer.

    Kept as a module-level helper (was a subprocess to definition_doc.py set-gate; now a
    direct call) so test seams that monkeypatch `gate_write._set_gate` survive the collapse."""
    try:
        definition_doc.set_gate(_doc(work_item, doc, root), review)
        return True, ""
    except (ValueError, OSError) as exc:
        return False, str(exc)


def certify(doc, work_item, reviewed_path, review, parent_doc, root):
    """review-plan / review-tasks: record `review` on `doc`, downgrading to
    changes-requested if the parent isn't approved. Canonical-path guarded.

    Returns an exit code: 0 only when the verdict was RECORDED (`recorded:*`); 3 when a
    verdict was produced but could not be recorded (`skipped:noncanonical`, `failed:set-gate`)
    — see the module docstring's gate-integrity note."""
    if not _same_file(reviewed_path, _canonical(root, work_item, doc)):
        _say("reviewed doc (%s) is outside the canonical docs/superheroes/%s/ layout — gate "
             "NOT recorded (refusing to stamp a different file). The %s was still reviewed/"
             "revised." % (reviewed_path, work_item, doc))
        _emit("skipped:noncanonical")
        return 3
    # Parent precondition: never certify <doc> as passed if its parent isn't approved.
    if parent_doc and review == "passed":
        ok, parent = _read_gate(parent_doc, work_item, root)
        if not ok:
            _say("could not read parent %s gate: %s" % (parent_doc, parent))
            parent = "unreadable"
        if parent != "passed":
            _say("parent %s gate is '%s' (not 'passed') — recording changes-requested, not "
                 "passed; the %s must be approved first." % (parent_doc, parent, parent_doc))
            review = "changes-requested"
    ok, err = _set_gate(doc, work_item, review, root)
    if ok:
        _emit("recorded:" + review)
        return 0
    _say("set-gate failed — gate NOT recorded (the %s doc may be missing/malformed despite "
         "reaching this step): %s" % (doc, err))
    _emit("failed:set-gate")
    return 3


def reset(doc, work_item, reviewed_path, root):
    """review-spec stale-approval reset: if the spec is currently `passed`, revoke it to
    `pending` (the owner must re-approve the changed content). Never grants `passed`."""
    if not _same_file(reviewed_path, _canonical(root, work_item, doc)):
        _say("⚠ spec was revised but the gate could not be reset (the doc is outside the "
             "canonical layout) — if it was approved, warn the owner: the 'passed' gate may "
             "be STALE; the spec needs re-approval.")
        return _emit("skipped:noncanonical")
    ok, current = _read_gate(doc, work_item, root)
    if not ok:
        _say("could not read the spec gate (%s) — if it was approved, warn the owner the "
             "approval may be stale." % current)
        return _emit("skipped:unreadable")
    if current != "passed":
        return _emit("noop:not-approved")
    ok, err = _set_gate(doc, work_item, "pending", root)
    if ok:
        _say("spec was already approved and has now been revised — gate reset to 'pending'; "
             "the owner must re-approve before it advances.")
        return _emit("reset:pending")
    _say("⚠ could not reset the stale-approval gate (set-gate failed) — warn the owner: the "
         "'passed' gate is STALE and the spec needs re-approval: %s" % err)
    return _emit("failed:set-gate")


def main(argv):
    ap = argparse.ArgumentParser(description="the trio's gate-write handshake (superheroes)")
    ap.add_argument("--mode", required=True, choices=["certify", "reset"])
    ap.add_argument("--doc", required=True, choices=["spec", "plan", "tasks"])
    ap.add_argument("--work-item", required=True)
    ap.add_argument("--reviewed-path", required=True,
                    help="the file actually reviewed (the canonical-path guard compares against it)")
    ap.add_argument("--review", choices=["passed", "changes-requested"],
                    help="certify mode: the verdict to record")
    ap.add_argument("--parent-doc", choices=["spec", "plan"],
                    help="certify mode: the parent doc-type whose gate must be approved")
    ap.add_argument("--root", required=True)
    args = ap.parse_args(argv[1:])

    if args.mode == "certify":
        if not args.review:
            _say("certify mode requires --review")
            _emit("error:bad-args")
            return 2
        return certify(args.doc, args.work_item, args.reviewed_path, args.review,
                       args.parent_doc, args.root)
    reset(args.doc, args.work_item, args.reviewed_path, args.root)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
