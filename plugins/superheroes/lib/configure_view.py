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
import engine_pref     # noqa: E402
import mode_reconcile  # noqa: E402
import mode_registry   # noqa: E402
import model_tier_overrides  # noqa: E402
import permission_rules  # noqa: E402
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
    try:
        permission = permission_rules.rules(cwd, root=root)  # read-only, provenance-valid only
    except Exception:
        permission = []
    try:
        permission_audit = permission_rules.audit(cwd, root=root)  # read-only FR-7 record
    except Exception:
        permission_audit = []
    try:
        # #409: the validated engine-preference view — carries the accepted codexModels pins AND the
        # rejected `invalidCodexModels` sub-map, so a hand-edited bad pin surfaces instead of showing
        # raw core.md text as if active. Read-only.
        engine_prefs = engine_pref.load_engine_prefs(cwd, root)
    except Exception:
        engine_prefs = {}
    return {"core": core, "layers": layers, "patterns": patterns, "mode": mode,
            "drift": drift, "storeHealth": health,
            "modelTiers": tiers, "modelTierOverrides": overrides, "modelTierProfile": profile,
            "permissionRules": permission, "permissionAudit": permission_audit,
            "enginePrefs": engine_prefs}


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
        prefs = core.get("enginePreferences")
        prefs = prefs if isinstance(prefs, dict) else {}
        out.append("")
        out.append("## Engine preferences")
        out.append(f"reviewer: {prefs.get('reviewer') or 'claude'}")
        out.append(f"implementation: {prefs.get('implementation') or 'claude'}")
        out.append(f"planAuthor: {prefs.get('planAuthor') or 'claude'}")
        effort = prefs.get("effort") if isinstance(prefs.get("effort"), dict) else {}
        out.append("effort overrides: " + (", ".join(f"{k}={v}" for k, v in sorted(effort.items()))
                                           or "(none)"))
        # #409: render the VALIDATED pins (load_engine_prefs output), not the raw core.md map — so an
        # accepted pin shows as active and a rejected one is surfaced below rather than displayed as if
        # in force. Mirrors the preflight readout line.
        eng = data.get("enginePrefs") or {}
        codex_models = eng.get("codexModels") if isinstance(eng.get("codexModels"), dict) else {}
        out.append("Codex model pins:")
        if codex_models:
            for role, model in sorted(codex_models.items()):
                out.append(f"  {role}: {model}")
        else:
            out.append("  (none; GPT-5.6 models derive from shared tiers)")
        rejected = eng.get("invalidCodexModels") if isinstance(eng.get("invalidCodexModels"), dict) else {}
        if rejected:
            out.append("Rejected Codex model pins (not applied — dispatch falls to the tier default):")
            for role, reason in sorted(rejected.items()):
                out.append(f"  {role}: {reason} ⚠")
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
    out.append("## Permission posture")
    perm = data.get("permissionRules") or []
    if not perm:
        out.append("(no auto-allow rules — every would-be prompt still prompts)")
    else:
        out.append("auto-allowed routine families (owner-curated, below the owner-role floor):")
        for rule in perm:
            out.append(f"- {rule.get('family') or '(unnamed)'}: {rule.get('pattern') or '(no pattern)'}")
    audit = data.get("permissionAudit") or []
    if audit:
        out.append(f"Audit record: {len(audit)} observed command{'s' if len(audit) != 1 else ''}")
    else:
        out.append("Audit record: none (seed the routine families to write it)")
    out.append("")
    out.append("## Pinned patterns")
    out.append((data["patterns"] or "(none)").strip())
    if data["drift"]:
        out.append("")
        out.append("---")
        out.append(f"⚠ {data['drift']['message']}")
    return "\n".join(out) + "\n"
