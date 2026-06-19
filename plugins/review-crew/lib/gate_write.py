#!/usr/bin/env python3
"""The trio's gate-write handshake — ONE tested place (was inlined bash in 3 skills).

review-crew's review-plan / review-tasks (mode **certify**) and review-spec (mode
**reset**) record a definition-doc's review gate via the-architect's lib. This helper
performs the whole guarded handshake so a fix lives in one place — the previous
near-verbatim duplication across the three SKILL.md files let a fix miss one copy and
resurface as a bug a review round later.

The handshake:

  resolve the-architect's lib (via `architect_lib`) → **fail closed** if absent
  → **canonical-path guard** (`samefile`): refuse to stamp a doc other than the one
    reviewed, because the-architect's `set-gate` reconstructs the canonical
    `docs/superheroes/<work-item>/<doc>.md` from `--work-item`
  → **certify**: parent-gate precondition (downgrade `passed`→`changes-requested` when the
    parent doc isn't approved), then `set-gate <review>`
  → **reset** (spec only): revoke a *stale* owner approval — read the gate; if it is
    `passed`, `set-gate pending`; otherwise no-op. It **never** writes `passed` (the
    advisory invariant: review-spec revokes, the owner grants).

It **degrades, it does not crash**: every path prints a clear message to stderr and a short
outcome token on stdout (the calling skill surfaces it in its terminal summary). It never
hand-edits YAML — the-architect's CLI is the single frontmatter writer.

**Exit codes carry gate-integrity intent, not just crashed-or-not.** A `certify` that produced a
verdict but could NOT record it (`skipped:lib-absent`, `skipped:noncanonical`, `failed:set-gate`)
exits **non-zero (3)**: it leaves the gate at `pending`, which is indistinguishable from "no
review ran" — and the-architect's self-certify branch would otherwise upgrade that `pending` to
`passed`, a green gate with no real review. `recorded:*` exits 0. `reset` mode always exits 0: it
is advisory revoke-only and never grants `passed`, so a skipped reset is a warning, not a
gate-integrity failure.

stdlib only (the band convention). Outcome tokens (stdout): `recorded:passed`,
`recorded:changes-requested`, `reset:pending`, `noop:not-approved`, `skipped:lib-absent`,
`skipped:noncanonical`, `skipped:unreadable`, `failed:set-gate`.
"""
import argparse
import os
import subprocess
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
import architect_lib  # noqa: E402  (sibling resolver in the same lib dir)

# review-crew's own plugin root (lib/..) — used to find the-architect as an installed
# marketplace sibling; computed from __file__ so we don't depend on $CLAUDE_PLUGIN_ROOT
# being exported into this subprocess's environment.
_PLUGIN_ROOT = os.path.dirname(_LIB_DIR)


def _say(detail):
    sys.stderr.write(detail + "\n")


def _emit(token):
    sys.stdout.write(token + "\n")


def _canonical(root, work_item, doc):
    # the-architect OWNS this layout — its doc_path() and set-gate/read-gate derive the same
    # docs/superheroes/<work-item>/<doc>.md. We re-encode it here only so the samefile guard can
    # run without a subprocess round-trip. test_gate_write.py::test_canonical_path_matches_the_architect
    # PINS this equal to the-architect's doc_path(), so the two copies cannot drift undetected —
    # a layout change there (e.g. a versioned subdir) fails CI instead of silently re-opening the
    # wrong-file hole this guard exists to close (arch-r3-001).
    return os.path.join(root, "docs", "superheroes", work_item, doc + ".md")


def _same_file(a, b):
    """`-ef` equivalent: True iff a and b are the same file; False if either is absent."""
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def _read_gate(lib, doc, work_item, root):
    """Return (ok, value). On failure ok=False and value holds the error text."""
    p = subprocess.run([sys.executable, lib, "read-gate", "--doc", doc,
                        "--work-item", work_item, "--root", root],
                       capture_output=True, text=True)
    if p.returncode == 0:
        return True, p.stdout.strip()
    return False, (p.stderr.strip() or "read-gate failed")


def _set_gate(lib, doc, work_item, review, root):
    """Return (ok, err). the-architect's CLI is the sole frontmatter writer."""
    p = subprocess.run([sys.executable, lib, "set-gate", "--doc", doc,
                        "--work-item", work_item, "--review", review, "--root", root],
                       capture_output=True, text=True)
    return p.returncode == 0, (p.stderr.strip() if p.returncode else "")


def certify(doc, work_item, reviewed_path, review, parent_doc, root, lib):
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
        ok, parent = _read_gate(lib, parent_doc, work_item, root)
        if not ok:
            _say("could not read parent %s gate: %s" % (parent_doc, parent))
            parent = "unreadable"
        if parent != "passed":
            _say("parent %s gate is '%s' (not 'passed') — recording changes-requested, not "
                 "passed; the %s must be approved first." % (parent_doc, parent, parent_doc))
            review = "changes-requested"
    ok, err = _set_gate(lib, doc, work_item, review, root)
    if ok:
        _emit("recorded:" + review)
        return 0
    _say("set-gate failed — gate NOT recorded (the %s doc may be missing/malformed despite "
         "reaching this step): %s" % (doc, err))
    _emit("failed:set-gate")
    return 3


def reset(doc, work_item, reviewed_path, root, lib):
    """review-spec stale-approval reset: if the spec is currently `passed`, revoke it to
    `pending` (the owner must re-approve the changed content). Never grants `passed`."""
    if not _same_file(reviewed_path, _canonical(root, work_item, doc)):
        _say("⚠ spec was revised but the gate could not be reset (the doc is outside the "
             "canonical layout) — if it was approved, warn the owner: the 'passed' gate may "
             "be STALE; the spec needs re-approval.")
        return _emit("skipped:noncanonical")
    ok, current = _read_gate(lib, doc, work_item, root)
    if not ok:
        _say("could not read the spec gate (%s) — if it was approved, warn the owner the "
             "approval may be stale." % current)
        return _emit("skipped:unreadable")
    if current != "passed":
        return _emit("noop:not-approved")
    ok, err = _set_gate(lib, doc, work_item, "pending", root)
    if ok:
        _say("spec was already approved and has now been revised — gate reset to 'pending'; "
             "the owner must re-approve before it advances.")
        return _emit("reset:pending")
    _say("⚠ could not reset the stale-approval gate (set-gate failed) — warn the owner: the "
         "'passed' gate is STALE and the spec needs re-approval: %s" % err)
    return _emit("failed:set-gate")


def main(argv):
    ap = argparse.ArgumentParser(description="the trio's gate-write handshake (review-crew)")
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

    lib = architect_lib.resolve(root=args.root, plugin_root=_PLUGIN_ROOT)
    if lib is None:
        if args.mode == "certify":
            _say("the-architect lib not resolvable (not in-repo, not an installed sibling) — "
                 "gate NOT recorded. ⚠ a verdict was produced but could not be recorded; this "
                 "exits non-zero so the-architect does NOT mistake the still-`pending` gate for "
                 "\"no review ran\" and self-certify it to passed. Resolve the-architect "
                 "alongside review-crew and re-run. The %s was still reviewed/revised."
                 % args.doc)
            _emit("skipped:lib-absent")
            return 3
        _say("⚠ spec was revised but the-architect lib is not resolvable to reset the gate "
             "— if it was approved, warn the owner: the 'passed' gate may be STALE; the "
             "spec needs re-approval.")
        _emit("skipped:lib-absent")
        return 0  # reset is advisory revoke-only — a skipped reset is a warning, never a passed grant

    if args.mode == "certify":
        if not args.review:
            _say("certify mode requires --review")
            _emit("error:bad-args")
            return 2
        return certify(args.doc, args.work_item, args.reviewed_path, args.review,
                       args.parent_doc, args.root, lib)
    reset(args.doc, args.work_item, args.reviewed_path, args.root, lib)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
