#!/usr/bin/env python3
"""review_setup_gather.py — the review loop's pre-round SETUP gather (fold 2, #141).

The shared review shell entered each round by firing four decision-free seam calls one courier leaf
apiece: the run-dir mkdir, the deferred-set seed read, review_memory load-summary, and
coverage_decisions load. Nothing decides between them (the reviewers have not dispatched yet), so by
the #118 stretch definition they are ONE stretch and should be ONE leaf. This gather runs the entry stretch in a single Python process and answers a combined, BOUNDED blob
of DECISIONS (#211 — decisions ride up, records stay on disk):

  { "ok": true,
    "resume":      <review_loop_plan entry-bootstrap DECISION — {round, contentHash, extras,
                    confirmationPending, markedRound, roundCount}, never records or findings>,
    "plan":        <review_loop_plan plan-round DECISION for the resume round — schedule + carried
                    + latestCoverageDecisionIds (folded so the entry read stays one leaf)>,
    "deferredSet": <parsed deferred-set.json, or {} when absent>,
    "coverage":    <coverage_decisions load result — decisions + the fence hash of the on-disk bytes> }

Everything is computed Python-side (no courier prose ever enters an integrity field — the live
2026-07-02 poison class), so `resume` / `plan` / `coverage` are byte-parity with the separate deciders
and the shell drops them straight into its resume/plan/coverage/deferred state. NO finding — not even a
blocking skeleton — rides back (#211 retires the #193 stub that still crossed up), so the entry read is
a small direct answer that never scales with run size (the #141 + #211 constraint).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import review_memory  # noqa: E402
import coverage_decisions  # noqa: E402
import review_loop_plan  # noqa: E402


def _load_deferred_set(path):
    """The deferred-set seed: the durable set the doc leg seeds runtimeDeferred from and the
    round-1 tally reuses. Missing/odd file -> {} (the normal first-round case), exactly the old
    io.readJson(deferred-set.json, {}) default."""
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def gather(run_dir, records_path, dimensions, extras_path, deferred_path,
           coverage_path, coverage_mode, doc_mode=False):
    # (1) the run-dir mkdir fold — the shell no longer mkdirs separately.
    if run_dir:
        os.makedirs(run_dir, exist_ok=True)
    # (2) #211: the entry read now rides DECISIONS, not records. Sweep a dead run's stale staging,
    # then compute the resume DECISION (review_loop_plan.entry_bootstrap): {round, contentHash,
    # extras, confirmationPending, markedRound, roundCount} — never stub records or findings (the
    # #193 stub that still rode up is retired). The fail-closed states of load_records_state
    # (missing/unreadable/corrupt) ride through UNCHANGED so an unverifiable seed still parks
    # round-memory-unreadable instead of a silent partial seed.
    review_memory.sweep_stale_staging(os.path.dirname(os.path.abspath(records_path)))
    resume = review_loop_plan.entry_bootstrap(records_path, dimensions, extras_path=extras_path)
    # (3) the deferred-set seed.
    deferred_set = _load_deferred_set(deferred_path)
    # (4) the coverage read — decisions + the fence hash over the exact on-disk bytes, Python-side.
    coverage = coverage_decisions.load_decisions(coverage_path, coverage_mode)
    # (5) the ROUND-1 plan DECISION (schedule + carried + latestCoverageDecisionIds), folded so the
    # entry read stays ONE leaf (#118). It reads the same disk; its changedSubjects come from the
    # folded extras. On an unreadable seed there is nothing to schedule — the shell parks on `resume`.
    plan = None
    if resume.get("ok"):
        extras = resume.get("extras")
        changed = extras.get("changedSubjects") if isinstance(extras, dict) else None
        plan = review_loop_plan.plan_round_decider(records_path, resume.get("round"), dimensions,
                                                   changed, just_marked=False, doc_mode=doc_mode)
    return {"ok": True, "resume": resume, "plan": plan,
            "deferredSet": deferred_set, "coverage": coverage}


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gather")
    g.add_argument("--run-dir", required=True)
    g.add_argument("--records-path", required=True)
    g.add_argument("--dimensions", required=True)
    g.add_argument("--extras-path")
    g.add_argument("--deferred-path")
    g.add_argument("--coverage-path", required=True)
    g.add_argument("--coverage-mode", choices=["doc", "code"], default="code")
    g.add_argument("--doc-mode", action="store_true")
    g.add_argument("--out-path",
                   help="when the gathered blob is larger than --receipt-threshold, write it here "
                        "and answer a small receipt for verified chunk reads")
    g.add_argument("--receipt-threshold", type=int, default=0)
    args = parser.parse_args(argv)
    if args.cmd == "gather":
        result = gather(args.run_dir, args.records_path, json.loads(args.dimensions),
                        args.extras_path, args.deferred_path, args.coverage_path,
                        args.coverage_mode, doc_mode=args.doc_mode)
        ok = review_memory._print_receipted_or_direct("review-setup-gather", result,
                                                      out_path=args.out_path,
                                                      threshold=args.receipt_threshold)
        return 0 if ok else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
