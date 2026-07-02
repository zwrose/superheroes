#!/usr/bin/env python3
# plugins/superheroes/lib/configure_view.py
"""The FR-4 combined profile view for superheroes:configure: one plain-text screen of the
project's core facts + every hero layer + the pinned patterns, plus the single coalesced FR-7
drift notice on every run. Strictly READ-ONLY — viewing never writes, so it can never silently
confirm provisional calibration (FR-18). Terminal-first; no graphical rendering."""
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import core_md         # noqa: E402
import mode_reconcile  # noqa: E402
import mode_registry   # noqa: E402
import model_tier_overrides  # noqa: E402
import store_sweep     # noqa: E402

_NON_LAYER = ("core.md", "patterns.md")


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def collect(cwd, root=None):
    """Gather everything the view renders (read-only): the core facts, each hero layer's text,
    the pinned patterns, the resolved storage mode, and the coalesced drift notice."""
    core = core_md.read(cwd, root)
    cal_dir = os.path.dirname(core_md.core_path(cwd, root))
    layers = []
    if os.path.isdir(cal_dir):
        for name in sorted(os.listdir(cal_dir)):
            if name.endswith(".md") and name not in _NON_LAYER:
                layers.append((name[:-3], _read(os.path.join(cal_dir, name)) or ""))
    patterns = _read(os.path.join(cal_dir, "patterns.md"))
    if patterns is None and core is not None:
        patterns = core.get("patterns")
    try:
        mode = mode_registry.resolve(cwd, root)["mode"]
    except Exception:
        mode = None
    try:
        drift = mode_reconcile.coalesce(cwd, root)
    except Exception:
        drift = None
    try:
        health = store_sweep.report(root=root)["counts"]  # read-only scan
    except Exception:
        health = None
    try:
        profile = model_tier_overrides.resolve_profile_path(cwd)
        tiers = model_tier_overrides.effective_tiers(profile)
        overrides = model_tier_overrides.load_overrides(profile)
    except Exception:
        profile, tiers, overrides = None, None, {}
    return {"core": core, "layers": layers, "patterns": patterns, "mode": mode,
            "drift": drift, "storeHealth": health,
            "modelTiers": tiers, "modelTierOverrides": overrides, "modelTierProfile": profile}


def _health_line(counts):
    total = sum(counts.values())
    stale = counts["orphan"] + counts["unknown"]
    if not stale:
        return f"storage health: ok ({total} per-project store{'s' if total != 1 else ''})"
    return (f"storage health: {total} per-project stores — {counts['orphan']} orphaned, "
            f"{counts['unknown']} unknown provenance (sweep available from the tune menu)")


def render(cwd, *, root=None):
    """One plain-text screen — 'here is everything superheroes knows about this project'.
    Read-only; the FR-7 drift notice (if any) trails the profile, re-shown on every run."""
    data = collect(cwd, root)
    out = ["# superheroes — project calibration", ""]
    out.append(f"storage mode: {data['mode'] or 'not set'}")
    if data["storeHealth"]:
        out.append(_health_line(data["storeHealth"]))
    core = data["core"]
    out.append("")
    out.append("## Core")
    if core is None:
        out.append("(no core calibration yet)")
    else:
        out.append(f"status: {core.get('status')}")
        out.append(f"verify command: {core.get('verifyCommand') or '(none)'}")
        out.append(f"stack: {', '.join(core.get('stackTags') or []) or '(none)'}")
        out.append("")
        out.append("### Threat model")
        out.append((core.get("threatModel") or "(none)").strip())
    for hero, text in data["layers"]:
        out.append("")
        out.append(f"## Layer: {hero}")
        out.append((text or "").strip())
    out.append("")
    out.append("## Model tiers")
    tiers = data.get("modelTiers")
    if not tiers:
        out.append("(using built-in defaults; review-crew profile not resolved)")
    else:
        for role in model_tier_overrides.KNOWN_ROLES:
            model = tiers.get(role)
            out.append(f"{role}: {model if model is not None else '(session, orchestrator only)'}")
    out.append("")
    out.append("## Pinned patterns")
    out.append((data["patterns"] or "(none)").strip())
    if data["drift"]:
        out.append("")
        out.append("---")
        out.append(f"⚠ {data['drift']['message']}")
    return "\n".join(out) + "\n"
