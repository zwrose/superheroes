#!/usr/bin/env python3
"""Leg-agnostic plumbing shared by the script-owned review-loop schedulers.

`spec_loop_plan.py` (#164/#167) was the first script-owned round scheduler: it took the
per-round dispatch decision out of the orchestrator's hands and delegated all POLICY to the
parity-locked twins (`review_round_policy.plan_round` + `loop_state.decide` +
`confirmation_followup`/`is_cross_cutting`). `code_loop_plan.py` (#174 PR 2) is the second —
the same shape for review-code's auto-fix loop.

The two legs differ only in evidence PLUMBING: where the findings files live
(`round-<N>/findings-<agent>.json` for code vs flat `findings-<agent>.json` for spec), how
the changed surface is derived (a git file-path diff for code vs a section-heading diff for
spec), and which artifacts feed the continuation gate (`--fix-batch`/`--resolutions` for
code vs `--compiled`/`--skipped-blocking` for spec). Everything ELSE — the scheduler state
file, the confirmation-panel economics bookkeeping, carry-forward, and plan rendering — is
identical between the legs, so it lives here once rather than being duplicated. This module
owns NO policy: the run/skip/tier schedule still comes from `review_round_policy.plan_round`,
the continue/exit action from `loop_state.decide`, and the confirmation follow-up from the
`review_round_policy` twins. It only reads/writes the scheduler state and derives the
evidence those twins consume. stdlib only.
"""
import json
import os
import tempfile

import circuit_breaker
import review_round_policy

DEEP = "reviewer-deep"
CHEAP = "reviewer"
# BLOCKING is the drift-guarded canonical blocking vocabulary (SSOT §11), re-exported into
# spec_loop_plan / code_loop_plan namespaces. The blocking/critical PARTITION routes through
# circuit_breaker.is_blocking / is_critical (#276/#291) — case-normalized + fail-closed.
BLOCKING = ("Critical", "Important")
STATE_FILE = "loop-state.json"
# The single home of the reviewer re-dispatch budget (#350/#525 lineage): a reviewer whose
# result is missing/malformed is re-dispatched at most this many times before it is recorded
# `missing` — "re-dispatch … once … never asks twice". Both Python schedulers and the JS shell
# hold this ONE value; test_retry_budget_parity pins them together so the count can't drift from
# the constant that names it.
REDISPATCH_BUDGET = 1


# --- scheduler-state I/O ------------------------------------------------------

def _state_path(session_dir):
    return os.path.join(session_dir, STATE_FILE)


def load_state(session_dir):
    """(ok, state). Missing file is ok (fresh); unreadable/corrupt is NOT ok — the caller
    fails toward run-all and rebuilds. Prior records are never clobbered by a failed read:
    only an explicit save writes."""
    path = _state_path(session_dir)
    if not os.path.exists(path):
        return True, {"schemaVersion": 1, "rounds": {}}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return False, {"schemaVersion": 1, "rounds": {}}
    if not isinstance(data, dict) or not isinstance(data.get("rounds"), dict):
        return False, {"schemaVersion": 1, "rounds": {}}
    for entry in data["rounds"].values():
        if not isinstance(entry, dict):
            return False, {"schemaVersion": 1, "rounds": {}}
    return True, data


def save_state(session_dir, state):
    """Atomic replace so a crash mid-write cannot corrupt prior round records."""
    path = _state_path(session_dir)
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".loop-state-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
        return True
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return False


def _round_entry(state, round_no):
    return state["rounds"].setdefault(str(round_no), {})


# --- findings-file evidence ---------------------------------------------------

def read_findings_file(path, tier):
    """Derive a dimension result from its findings JSON at *path*. A valid file — array or
    object with a findings list — is always high-confidence; wrapper confidence is ignored.
    Invalid/missing files fail loud as transport errors."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {"valid": False, "why": "missing"}
    except (OSError, ValueError):
        return {"valid": False, "why": "malformed"}
    if isinstance(data, list):
        if any(not isinstance(f, dict) for f in data):
            return {"valid": False, "why": "malformed"}
        findings = data
        confidence = "high"
    elif isinstance(data, dict) and isinstance(data.get("findings"), list):
        if any(not isinstance(f, dict) for f in data["findings"]):
            return {"valid": False, "why": "malformed"}
        findings = data["findings"]
        confidence = "high"
    else:
        return {"valid": False, "why": "malformed"}
    return {
        "valid": True,
        "findings": findings,
        "confidence": confidence,
        "hasFindings": len(findings) > 0,
        # #276/#291: case-normalized, fail-closed partition. `blocking` feeds the surfaced-severity /
        # confirmation path (code_loop_plan / spec_loop_plan); `critical` drives the confirmation
        # re-arm/park gate. Was case-sensitive `in {Critical,Important}` / `== "Critical"`, which
        # silently mis-counted a mis-cased or foreign severity.
        "blocking": sum(1 for f in findings if circuit_breaker.is_blocking(f.get("severity"))),
        "critical": sum(1 for f in findings if circuit_breaker.is_critical(f.get("severity"))),
    }


# --- plans --------------------------------------------------------------------

# --- per-dimension records ----------------------------------------------------

def _subjects(dimension, findings):
    subjects = {f.get("dimension") for f in findings
                if isinstance(f.get("dimension"), str) and f.get("dimension")}
    fallback = review_round_policy.SUBJECT_FALLBACK.get(
        str(dimension or "").split("-")[0].lower())
    if fallback:
        subjects.add(fallback)
    return sorted(subjects)


def _previous_dims(state, upto_round):
    """The latest recorded state per dimension across rounds ≤ upto_round — the twin of the
    shell's buildPreviousDimensionState (later rounds overwrite earlier ones)."""
    previous = {}
    for key in sorted(state.get("rounds") or {}, key=lambda k: int(k) if str(k).isdigit() else 0):
        if not str(key).isdigit() or int(key) > upto_round:
            continue
        dims = (state["rounds"][key] or {}).get("dims") or {}
        for name, rec in dims.items():
            if isinstance(rec, dict):
                previous[name] = rec
    return previous


def _carry_forward(state, dimension, round_no, sched):
    """The prose twin of the shell's carryForwardDimension: a skipped dimension keeps its
    latest recorded state; with nothing to carry it is low-confidence (never skip-eligible
    again until it actually runs)."""
    previous = _previous_dims(state, round_no - 1)
    prior = previous.get(dimension)
    if isinstance(prior, dict):
        rec = dict(prior)
    else:
        rec = {"confidence": "low", "hasFindings": False, "blockingCount": 0,
               "subjects": _subjects(dimension, [])}
    rec.update({"dimension": dimension, "status": "skipped", "round": round_no,
                "carriedFromRound": sched.get("carriedFromRound") or rec.get("round")})
    return rec

