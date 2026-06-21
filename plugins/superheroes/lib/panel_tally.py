#!/usr/bin/env python3
"""Deterministic per-round + loop-terminal tally for the review-panel Workflow pattern.

The single source of truth for the panel's per-round gate/confidence and the four loop
terminals. It layers the spec's normalized vocabulary (`clean` / `blocking` / `cannot-certify`;
loop terminals `continue` / `clean` / `clean-with-skips` / `cannot-certify` / `halted`) over the
REUSED libs: it imports `loop_state.decide` (the continue/clean/skip/halt accounting),
`circuit_breaker.finding_identity` (the `file::normalized_title` identity), and
`review_result.write_result` (the atomic durable record) UNCHANGED. Every terminal is decided
here, never in the JS shell; every read is fail-safe (a missing/malformed input biases to a
non-clean outcome, never a silent `clean`). stdlib only.
"""
import argparse
import json
import os
import sys

import circuit_breaker
import loop_state
import review_result

BLOCKING = ("Critical", "Important")
SEV_RANK = {"Critical": 0, "Important": 1, "Minor": 2, "Nit": 3}


# ── run-key dir layout (panel_tally owns these; no scattered literals) ──
def round_dir(run_dir, rnd):
    return os.path.join(run_dir, "round-%d" % rnd)


def findings_path(run_dir, rnd, reviewer):
    return os.path.join(round_dir(run_dir, rnd), "findings-%s.json" % reviewer)


def verdict_path(run_dir, rnd):
    return os.path.join(round_dir(run_dir, rnd), "verdict.json")


def deferred_set_path(run_dir):
    return os.path.join(run_dir, "deferred-set.json")


def result_path(run_dir):
    return os.path.join(run_dir, "result.json")


# ── compile / dedupe (FR-3) ──
def _identity(f):
    return circuit_breaker.finding_identity(f)


def _merge_dims(a, b):
    parts = []
    for src in (a.get("dimension"), b.get("dimension")):
        if not src:
            continue
        for p in str(src).split("+"):
            p = p.strip()
            if p and p not in parts:
                parts.append(p)
    return " + ".join(parts)


def compile_findings(findings, context_files=None):
    """Merge by identity (file::normalized_title): keep the higher severity, union dimensions.
    Drop uncited findings (file/line None) and, when context_files is given, any finding whose
    file is outside the reviewed material."""
    by_id = {}
    for f in findings:
        if f.get("file") is None or f.get("line") is None:
            continue
        if context_files is not None and f.get("file") not in context_files:
            continue
        fid = _identity(f)
        if fid in by_id:
            ex = by_id[fid]
            dims = _merge_dims(ex, f)
            if SEV_RANK.get(f.get("severity"), 99) < SEV_RANK.get(ex.get("severity"), 99):
                merged = dict(f)
            else:
                merged = dict(ex)
            merged["dimension"] = dims
            by_id[fid] = merged
        else:
            by_id[fid] = dict(f)
    out = list(by_id.values())
    for f in out:  # FR-4: deterministic mechanical/judgment classification (no action taken)
        f["classification"] = "judgment" if f.get("tradeoff") else "mechanical"
    return out


# ── per-round gate + confidence (FR-5/6/7) ──
def round_gate(compiled, expected_roster, completed_roster):
    """Deterministic per-round verdict from the compiled findings + completion state.
    Precedence: any reviewer that did not complete → `cannot-certify` (coverage gap). Returns
    the `missing` (incomplete) reviewers too, so the verdict can NAME the missing review angles
    (FR-5/UFR-2)."""
    incomplete = [r for r in expected_roster if r not in completed_roster]
    has_blocker = any(f.get("severity") in BLOCKING for f in compiled)
    if incomplete:
        gate = "cannot-certify"
    elif has_blocker:
        gate = "blocking"
    else:
        gate = "clean"
    all_verifiable = all(bool(f.get("evidence")) for f in compiled)
    confidence = "high" if (not incomplete and all_verifiable) else "low"
    return gate, confidence, incomplete


# ── deferral accounting (FR-10) ──
def present_deferred(compiled, deferred_set):
    """present-∩-deferred: count present BLOCKING findings whose identity was deferred and whose
    current severity is no GREATER than the severity it was deferred at (a higher-severity or
    different-substance re-flag is a new, non-deferred blocker). Mirrors loop_state's cumulative
    present-∩-skip contract: a deferral for a finding no longer re-flagged simply stops counting."""
    n = 0
    for f in compiled:
        if f.get("severity") not in BLOCKING:
            continue
        deferred_sev = deferred_set.get(_identity(f))
        if deferred_sev is None:
            continue
        if SEV_RANK.get(f.get("severity"), 99) >= SEV_RANK.get(deferred_sev, 99):
            n += 1
    return n
