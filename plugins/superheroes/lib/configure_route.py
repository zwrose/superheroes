#!/usr/bin/env python3
# plugins/superheroes/lib/configure_route.py
"""The FR-1 state-sense brain for superheroes:configure. Pure (no writes): senses a project's
calibration state and returns the path the conductor should run — set-up / fix / view — plus
plain-language reasons and the raw reconcile signals. "Healthy but drifted" stays in `view`
(the drift renders as the FR-7 notice, not a separate fix path); a still-provisional
calibration routes to `fix` (FR-18); an incomplete set-up routes to `fix` (UFR-7)."""
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import control_plane   # noqa: E402
import core_md         # noqa: E402
import mode_reconcile  # noqa: E402
import mode_registry   # noqa: E402

# Reconcile signal types that mean "a structural fix is pending" (route to fix, not view).
_STRUCTURAL = (
    "migration-pending", "disagreement", "doc-policy-provisional", "migration-incomplete",
    "legacy-migration-ambiguous", "core-md-unreadable", "calibration-not-saved",
)


def _review_layer_missing(cwd, root):
    """The review-crew threat-model layer is the .md light layer the set-up pass seeds; a
    missing one means an incomplete set-up. (The-architect doc-policy is the OTHER light layer
    but is not a .md file — its absence surfaces through the doc-policy-provisional signal.)"""
    layer = os.path.join(os.path.dirname(core_md.core_path(cwd, root)), "review-crew.md")
    return not os.path.isfile(layer)


def route(cwd, *, interactive, root=None):
    """Sense the calibration state → {"path": "set-up"|"fix"|"view", "reasons": [...],
    "signals": [...]}. Pure; never writes."""
    try:
        signals = mode_reconcile.gather_signals(cwd, root) or []
    except Exception:
        signals = []
    r = mode_registry.resolve(cwd, root)
    core = core_md.read(cwd, root)
    recorded = r["source"] in ("registry", "backfilled")

    # 1. Fresh — nothing configured yet.
    if not recorded and core is None:
        return {"path": "set-up", "reasons": ["no storage mode or calibration yet"],
                "signals": signals}

    # 2. Incomplete set-up (UFR-7) — a recorded mode but the core or a light layer is missing.
    if recorded and (core is None or _review_layer_missing(cwd, root)):
        return {"path": "fix",
                "reasons": ["incomplete set-up — calibration is missing pieces"],
                "signals": signals}

    # 3. Provisional calibration (FR-18) — surface for the owner to confirm (interactive only).
    if interactive and core is not None and core.get("status") == "provisional":
        return {"path": "fix",
                "reasons": ["calibration is still provisional — review and confirm it"],
                "signals": signals}

    # 4. A structural fix is pending (legacy / pending migration / unconfirmed doc-policy).
    structural = [s for s in signals if s.get("type") in _STRUCTURAL]
    if structural:
        kinds = ", ".join(sorted({s["type"] for s in structural}))
        return {"path": "fix", "reasons": [f"a structural fix is pending: {kinds}"],
                "signals": signals}

    # 5. Configured and healthy — any routine drift renders as the FR-7 notice in the view.
    return {"path": "view", "reasons": ["configured and healthy"], "signals": signals}


def _current_work(cwd, root):
    """The current control-plane work-item dict, or None. Fail-open."""
    try:
        return control_plane.get_current(cwd, root)
    except Exception:
        return None


def work_in_flight(cwd, *, root=None):
    """UFR-3: True when a piece of work is mid-flight (its documents would move under a switch),
    so the conductor can warn before a storage-mode switch. A tested condition, not prose."""
    return bool(_current_work(cwd, root))
