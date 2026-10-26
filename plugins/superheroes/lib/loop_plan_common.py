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
code vs `--compiled`/`--skipped-blocking` for spec). What survives here is the reviewer
re-dispatch budget the round driver reads, the blocking vocabulary, and the findings-file
reader. This module owns NO policy: the run/skip/tier schedule still comes from
`review_round_policy.plan_round`, the continue/exit action from `loop_state.decide`, and the
confirmation follow-up from the `review_round_policy` twins. stdlib only.
"""
import json

import circuit_breaker

CHEAP = "reviewer"
# BLOCKING is the drift-guarded canonical blocking vocabulary (SSOT §11), re-exported into
# spec_loop_plan / code_loop_plan namespaces. The blocking/critical PARTITION routes through
# circuit_breaker.is_blocking / is_critical (#276/#291) — case-normalized + fail-closed.
BLOCKING = ("Critical", "Important")
# The single home of the reviewer re-dispatch budget (#350/#525 lineage): a reviewer whose
# result is missing/malformed is re-dispatched at most this many times before it is recorded
# `missing` — "re-dispatch … once … never asks twice". Both Python schedulers and the JS shell
# hold this ONE value; test_retry_budget_parity pins them together so the count can't drift from
# the constant that names it.
REDISPATCH_BUDGET = 1


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
