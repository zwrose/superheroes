#!/usr/bin/env python3
# plugins/superheroes/lib/configure_view.py
"""The FR-4 combined profile view for superheroes:configure: one plain-text screen of the
project's core facts + every hero layer + the pinned patterns, plus the single coalesced FR-7
drift notice on every run. Strictly READ-ONLY — viewing never writes, so it can never silently
confirm provisional calibration (FR-18). Terminal-first; no graphical rendering.

v2: the old config-file `## Permission posture` section is retired — v2 owner-authority is
config-free (#482), so `permission_rules` is dead and there is nothing to render. In its place
this screen carries the v2 dispatch-calibration observability surface: the EFFECTIVE engine +
model for each v2 dispatch role (`## Dispatch calibration`), and the Codex model-pin detail
(`## Engine model pins (Codex)`)."""
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import core_md         # noqa: E402
import engine_pref     # noqa: E402
import guardian_ledger  # noqa: E402
import guardian_store  # noqa: E402
import guardian_sweep  # noqa: E402
import guardian_vitals  # noqa: E402
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


def _cadence_view(config):
    """Cadence display from read_config output only (CONVENTIONS §11 — no second parser)."""
    cadence = config.get("cadence")
    if not isinstance(cadence, dict):
        cadence = {}
    cadence_tuned = config.get("cadenceTuned")
    if not isinstance(cadence_tuned, dict):
        cadence_tuned = {}
    return cadence, cadence_tuned


def _collect_guardian(cwd, root):
    config = guardian_sweep.read_config(cwd, root)
    cadence, cadence_tuned = _cadence_view(config)
    ledger = guardian_store.read_ledger(cwd, root)
    report_card_notes = []
    card = guardian_ledger.report_card(
        ledger.get("records"), config.get("reportCard"), notes_out=report_card_notes)
    if ledger.get("status") not in ("ok", "absent") and ledger.get("note"):
        report_card_notes.append(ledger["note"])
    snapshot = guardian_store.read_snapshot(cwd, root)
    trend = guardian_vitals.read_trend(cwd, root=root, limit=1)
    last_date = None
    if trend.get("records"):
        last_date = trend["records"][-1].get("date")
    return {
        "cadence": cadence,
        "cadenceTuned": cadence_tuned,
        "coverage": config.get("coverage") or [],
        "card": card,
        "reportCardNotes": report_card_notes,
        "ledgerStatus": ledger.get("status"),
        "ledgerNote": ledger.get("note"),
        "lastSweptSha": snapshot.get("sweptSha") if snapshot else None,
        "lastSweepDate": last_date,
    }


def _guardian_lines(guardian):
    """Plain-text guardian observability rows for the one-screen view."""
    if guardian is None:
        return ["(not available)"]
    lines = []
    cadence = guardian.get("cadence") or {}
    min_merges = cadence.get("minMerges")
    min_days = cadence.get("minDays")
    if isinstance(min_merges, int) and isinstance(min_days, int):
        note = "tuned" if guardian.get("cadenceTuned") else "defaults"
        lines.append("cadence: ≥%d merges or ≥%d days (%s)" % (min_merges, min_days, note))
    else:
        lines.append("cadence: (not available)")

    coverage = guardian.get("coverage") or []
    if not coverage:
        lines.append("coverage: none recorded")
    else:
        parts = []
        for entry in coverage:
            if not isinstance(entry, dict):
                continue
            path = entry.get("path")
            tool = entry.get("tool")
            if isinstance(path, str) and path.strip():
                label = path.strip()
                if isinstance(tool, str) and tool.strip():
                    label = "%s (%s)" % (label, tool.strip())
                parts.append(label)
        lines.append("coverage: " + (", ".join(parts) if parts else "none recorded"))

    card = guardian.get("card") or {}
    benched = sorted(lens for lens, entry in card.items() if entry.get("benched"))
    below_floor = []
    for lens, entry in sorted(card.items()):
        if entry.get("benched"):
            continue
        if not entry.get("adjudicated"):
            continue
        reason = entry.get("reason") or ""
        if "is active:" in reason:
            continue
        below_floor.append(lens)

    ledger_status = guardian.get("ledgerStatus")
    bench_authoritative = ledger_status in ("ok", "absent")

    if not bench_authoritative:
        if ledger_status == "partial":
            note = guardian.get("ledgerNote") or "ledger partially parsed"
            lines.append("benched lenses: uncertain — ledger is partial (%s)" % note)
        elif ledger_status in ("malformed", "newer", "unreadable"):
            note = guardian.get("ledgerNote") or ledger_status
            if not card:
                lines.append("benched lenses: unknown — ledger unreadable (%s)" % note)
            else:
                lines.append("benched lenses: uncertain — ledger unreadable (%s)" % note)
        else:
            note = guardian.get("ledgerNote") or (ledger_status or "unknown")
            lines.append("benched lenses: uncertain — ledger status %s (%s)"
                         % (ledger_status, note))
    elif ledger_status == "absent" and not card:
        lines.append("benched lenses: no sweep history yet")
    elif benched:
        lines.append("benched lenses:")
        for lens in benched:
            lines.append("  %s — %s" % (lens, card[lens].get("reason") or "(no reason)"))
    else:
        lines.append("benched lenses: none")

    for note in guardian.get("reportCardNotes") or []:
        lines.append("report-card note: %s" % note)

    for lens in below_floor:
        lines.append("%s — floor not met" % lens)

    sha = guardian.get("lastSweptSha")
    if sha:
        date = guardian.get("lastSweepDate")
        if date:
            lines.append("last sweep: %s (%s)" % (sha, date))
        else:
            lines.append("last sweep: %s" % sha)
    return lines


def collect(cwd, root=None):
    """Gather everything the view renders (read-only): the core facts, each hero layer's text,
    the pinned patterns, the resolved storage mode, the coalesced drift notice, the effective
    model tiers, and the validated engine preferences."""
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
        profile = model_tier_overrides.resolve_profile_path(cwd, root)
        tiers = model_tier_overrides.effective_tiers(profile)
        overrides = model_tier_overrides.load_overrides(profile)
    except Exception:
        profile, tiers, overrides = None, None, {}
    try:
        # #409: the validated engine-preference view — carries the accepted codexModels pins AND the
        # rejected `invalidCodexModels` sub-map, so a hand-edited bad pin surfaces instead of showing
        # raw core.md text as if active. Read-only.
        engine_prefs = engine_pref.load_engine_prefs(cwd, root)
    except Exception:
        engine_prefs = {}
    try:
        guardian = _collect_guardian(cwd, root)
    except Exception:
        guardian = None
    return {"core": core, "layers": layers, "patterns": patterns, "mode": mode,
            "drift": drift, "storeHealth": health,
            "modelTiers": tiers, "modelTierOverrides": overrides, "modelTierProfile": profile,
            "enginePrefs": engine_prefs, "guardian": guardian}


def _health_line(counts):
    total = sum(counts.values())
    stale = counts["orphan"] + counts["unknown"]
    if not stale:
        return f"storage health: ok ({total} per-project store{'s' if total != 1 else ''})"
    return (f"storage health: {total} per-project stores — {counts['orphan']} orphaned, "
            f"{counts['unknown']} unknown provenance (sweep available from the tune menu)")


_ROLE_LABEL = {"implementer": "implementer", "brief-check": "brief-check reviewer",
               "review-code": "review-code seats", "pilot": "pilot"}


def _dispatch_rows(prefs, tiers):
    """The v2 dispatch-calibration rows: (label, engine, model) for every dispatch role, computed
    by the shared `engine_pref.dispatch_calibration_rows` (the ONE source both this view and the
    preflight readout format) and mapped to this view's display labels. `orchestrator` has neither
    a config key nor a model tier of its own — it always inherits the session model — so its row is
    a fixed, non-configurable line appended here rather than a resolver call."""
    rows = [(_ROLE_LABEL[r["role"]], r["engine"], r["model"])
            for r in engine_pref.dispatch_calibration_rows(prefs, tiers)]
    rows.append(("orchestrator (session)", "(session — this session's model)", "not configurable"))
    return rows


def render(cwd, *, root=None):
    """One plain-text screen — 'here is everything superheroes knows about this project'.
    Read-only; the FR-7 drift notice (if any) trails the profile, re-shown on every run."""
    data = collect(cwd, root)
    out = ["# superheroes — project calibration", ""]
    out.append(f"storage mode: {data['mode'] or 'not set'}")
    if data["storeHealth"]:
        out.append(_health_line(data["storeHealth"]))
    core = data["core"]
    tiers = data.get("modelTiers") or {}
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
        out.append("## Dispatch calibration (engine + model per role)")
        for label, engine, model in _dispatch_rows(prefs, tiers):
            out.append(f"{label} — {engine} — {model}")
        out.append("")
        out.append("## Engine model pins (Codex)")
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
    if not tiers:
        out.append("(using built-in defaults; review-crew profile not resolved)")
    else:
        for role in model_tier_overrides.KNOWN_ROLES:
            out.append(f"{role}: {tiers.get(role)}")
    out.append("orchestrator: (session model — not owner-configurable)")
    out.append("")
    out.append("## Guardian")
    for line in _guardian_lines(data.get("guardian")):
        out.append(line)
    out.append("")
    out.append("## Pinned patterns")
    out.append((data["patterns"] or "(none)").strip())
    if data["drift"]:
        out.append("")
        out.append("---")
        out.append(f"⚠ {data['drift']['message']}")
    return "\n".join(out) + "\n"
