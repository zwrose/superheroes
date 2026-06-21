#!/usr/bin/env python3
"""Self-healing reconcile engine + coalesced drift-nudge for the storage-mode registry
(CONVENTIONS §2.3/§2.4). Stdlib-only. The init skill drives reconcile(); tests drive it now.
Reconcile items are derived purely from current on-disk state; only dismissal (nudge-ack)
is durable."""
import argparse
import hashlib
import json
import os
import sys

import mode_registry as mr


def _sig_id(*parts):
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def gather_signals(cwd, root=None):
    """Pure function of on-disk state → the outstanding reconcile items."""
    locs = mr.hero_evidence(cwd, root)
    verdict = mr.evidence_verdict(locs)
    rec = mr.read_registry(cwd, root)
    sigs = []
    if rec is None:
        if verdict == "disagree":
            facts = sorted(f"{k}={v}" for k, v in locs.items())
            sigs.append({"type": "disagreement",
                         "identity": _sig_id("disagreement", *facts), "detail": locs})
        elif verdict == "none":
            sigs.append({"type": "provisional-mode",
                         "identity": _sig_id("provisional-mode"), "detail": {}})
    else:
        off = {k: v for k, v in locs.items()
               if v != "none" and v != rec["storageMode"]}
        if off:
            facts = sorted(f"{k}={v}" for k, v in off.items())
            sigs.append({"type": "migration-pending",
                         "identity": _sig_id("migration-pending", rec["storageMode"], *facts),
                         "detail": {"recorded": rec["storageMode"], "off": off}})
    return sigs


def _ack_path(cwd, root=None):
    return os.path.join(mr.project_store_dir(cwd, root), "nudge-ack.json")


def read_acks(cwd, root=None):
    try:
        with open(_ack_path(cwd, root), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def ack_signal(cwd, identity, root=None):
    if mr.ensure_project_store(cwd, root) is None:
        return
    acks = read_acks(cwd, root)
    acks[identity] = True
    mr.store_core.atomic_write(_ack_path(cwd, root), json.dumps(acks, indent=2))


def coalesce(cwd, root=None):
    """One combined reconcile prompt (FR-9) over the unacked signals (FR-10)."""
    acks = read_acks(cwd, root)
    items = [s for s in gather_signals(cwd, root) if s["identity"] not in acks]
    if not items:
        return None
    return {"count": len(items), "items": items,
            "message": f"this project has {len(items)} item(s) to reconcile — run init to settle it"}
