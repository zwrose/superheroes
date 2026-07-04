#!/usr/bin/env python3
"""review_setup_gather.py — the review loop's pre-round SETUP gather (fold 2, #141).

The shared review shell entered each round by firing four decision-free seam calls one courier leaf
apiece: the run-dir mkdir, the deferred-set seed read, review_memory load-summary, and
coverage_decisions load. Nothing decides between them (the reviewers have not dispatched yet), so by
the #118 stretch definition they are ONE stretch and should be ONE leaf. This gather runs all four
in a single Python process and answers a combined, BOUNDED blob:

  { "ok": true,
    "memory":      <review_memory entry-bootstrap result — records are STUBS (decision scalars +
                    blocking-only finding skeletons), contentHash + resumeRound + extras folded>,
    "deferredSet": <parsed deferred-set.json, or {} when absent>,
    "coverage":    <coverage_decisions load result — decisions + the fence hash of the on-disk bytes> }

Everything is computed Python-side (no courier prose ever enters an integrity field — the live
2026-07-02 poison class), so `memory` / `coverage` are byte-parity with the separate helpers and the
shell drops them straight into memoryState / coverageState / the deferred seed. The evidence bodies
never ride back (the entry-bootstrap stub contract is reused verbatim), and #193 further collapses the
resume seed to one direct payload-tier answer, so the fold reintroduces no mega-JSON through the
courier (the #141 constraint).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import review_memory  # noqa: E402
import coverage_decisions  # noqa: E402


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
           coverage_path, coverage_mode):
    # (1) the run-dir mkdir fold — the shell no longer mkdirs separately.
    if run_dir:
        os.makedirs(run_dir, exist_ok=True)
    # (2) entry-bootstrap (#193): sweep a dead run's stale staging, then compute the resume
    # bootstrap — the contentHash + resume round + per-round STUBS (decision scalars + blocking-only
    # finding skeletons) + the folded last-extras.json. Byte-identical to `review_memory.py
    # entry-bootstrap --sweep-stale-staging --extras-path`. The stub replaces the full summarize
    # skeleton so entry seeding fits ONE direct payload-tier answer instead of a receipt + N chunk
    # leaves; the durable evidence bodies (and now non-blocking prior-round findings) never ride back.
    memory = review_memory.entry_bootstrap(records_path, dimensions,
                                           extras_path=extras_path, sweep_stale=True)
    # (3) the deferred-set seed.
    deferred_set = _load_deferred_set(deferred_path)
    # (4) the coverage read — decisions + the fence hash over the exact on-disk bytes, Python-side.
    coverage = coverage_decisions.load_decisions(coverage_path, coverage_mode)
    return {"ok": True, "memory": memory, "deferredSet": deferred_set, "coverage": coverage}


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
    g.add_argument("--out-path",
                   help="when the gathered blob is larger than --receipt-threshold, write it here "
                        "and answer a small receipt for verified chunk reads")
    g.add_argument("--receipt-threshold", type=int, default=0)
    args = parser.parse_args(argv)
    if args.cmd == "gather":
        result = gather(args.run_dir, args.records_path, json.loads(args.dimensions),
                        args.extras_path, args.deferred_path, args.coverage_path,
                        args.coverage_mode)
        ok = review_memory._print_receipted_or_direct("review-setup-gather", result,
                                                      out_path=args.out_path,
                                                      threshold=args.receipt_threshold)
        return 0 if ok else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
