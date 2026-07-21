#!/usr/bin/env python3
# plugins/superheroes/lib/guardian_report.py
"""Deterministic markdown renderer for Guardian sweep reports. Stdlib-only."""
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

HEADER_TITLE = "# Guardian sweep report"
HEADER_STANDING_INSTRUCTIONS = "## Standing instructions"
HEADER_VALIDATED = "## Validated findings"
HEADER_TRACKED = "## Tracked / filed"
HEADER_VITALS = "## Vitals delta"
HEADER_REPORT_CARD = "## Report card"
HEADER_FUNNEL = "## Candidate funnel"

_STANDING_BODY = """\
- Verify each finding against its receipt before acting.
- Triage against the board; consult the owner before filing.
- Record dispositions in the ledger; carry verified-closure forward.
"""

FUNNEL_RAISED = "raised"
FUNNEL_MALFORMED = "malformed"
FUNNEL_KILLED_DRIFT = "killed-by-drift"
FUNNEL_KILLED_LEDGER = "killed-by-ledger"
FUNNEL_KILLED_BENCH = "benched-suppressed"
FUNNEL_MATCH_NOTES = "matcher-notes"
FUNNEL_TRACKED_FILED = "tracked-filed"
FUNNEL_DEGRADED = "degraded-lenses"
FUNNEL_REJECTED = "model-rejected"
FUNNEL_VALIDATED = "surfaced-and-validated"


def _storage_header(bundle):
    """One actionable line for storage mode + durability consequence."""
    mode = bundle.get("storageMode") or "in-repo"
    committed = bundle.get("committed", "uncommitted")
    if mode == "global":
        return ("storage: global — history is machine-local to this project store "
                "(not shared via the repo)")
    if committed == "committed":
        return ("storage: in-repo — guardian artifacts are committed with the repo")
    return ("storage: in-repo — guardian artifacts are generated uncommitted; "
            "durability requires a PR")


def _fmt_delta_entry(name, move):
    if not isinstance(move, dict):
        return "%s: %s" % (name, move)
    prev, cur = move.get("prev"), move.get("cur")
    change = move.get("change")
    return "%s: %s → %s (%s)" % (name, prev, cur, change)


def _render_vitals(lines, vd):
    lines.append(HEADER_VITALS)
    lines.append("")
    if not vd:
        lines.append(
            "_Vitals collection is turned off for this project — no trend this sweep._")
        lines.append("")
        return

    crossings = vd.get("crossings") if isinstance(vd, dict) else None
    delta = vd.get("delta") if isinstance(vd, dict) else None
    if crossings is None and delta is None and isinstance(vd, dict):
        # Legacy flat map shape.
        for k in sorted(vd):
            lines.append("- %s: %s" % (k, vd[k]))
        lines.append("")
        return

    not_collected = vd.get("notCollected") if isinstance(vd, dict) else None
    if not isinstance(not_collected, dict):
        not_collected = {}

    crossing_vitals = set()
    if crossings:
        for c in crossings:
            if not isinstance(c, dict):
                continue
            crossing_vitals.add(c.get("vital"))
            sentence = c.get("sentence") or _fmt_delta_entry(
                c.get("vital"), c)
            lines.append("- %s" % sentence)
    non_crossing = []
    if delta:
        for name in sorted(delta):
            if name in crossing_vitals:
                continue
            non_crossing.append(_fmt_delta_entry(name, delta[name]))
        if non_crossing:
            if crossings:
                lines.append("")
                lines.append("Other movement:")
            for item in non_crossing:
                lines.append("- %s" % item)

    measured_movement = bool(crossings) or bool(non_crossing)
    if not_collected:
        if measured_movement:
            lines.append("")
        lines.append("Not collected:")
        for name in sorted(not_collected):
            reason = not_collected[name]
            lines.append("- %s: %s" % (name, reason))

    if not measured_movement:
        if not_collected:
            lines.append(
                "_No vitals movement — nothing was collected this sweep._")
        else:
            lines.append("_No vitals movement._")
    lines.append("")


def _percent(actionability):
    return "n/a" if actionability is None else "%.0f%%" % (actionability * 100)


def _render_report_card(lines, card):
    lines.append(HEADER_REPORT_CARD)
    lines.append("")
    if not card:
        lines.append("_No lenses graded yet._")
        lines.append("")
        return
    for lens in sorted(card):
        entry = card[lens]
        if not isinstance(entry, dict):
            continue
        lines.append("- %s: %d for / %d against (%s actionability, sweeps=%s)" % (
            lens,
            entry.get("for", 0),
            entry.get("against", 0),
            _percent(entry.get("actionability")),
            "unknown" if entry.get("sweeps") is None else entry.get("sweeps"),
        ))
        if entry.get("benched"):
            lines.append("  - %s" % (entry.get("reason") or ("%s is benched" % lens)))
        elif entry.get("adjudicated", 0) == 0 or entry.get("sweeps") is None \
                or not entry.get("reason", "").startswith(lens + " is active"):
            # Below the small-N floor — must not read as passing.
            reason = entry.get("reason")
            if reason:
                lines.append("  - %s" % reason)
    lines.append("")


def render(bundle, dispositions, ledger):
    """Deterministic markdown report from a collect bundle + model dispositions."""
    lines = [HEADER_TITLE, ""]
    lines.append(_storage_header(bundle))
    lines.append("")
    lines.append(HEADER_STANDING_INSTRUCTIONS)
    lines.append("")
    lines.extend(_STANDING_BODY.splitlines())
    lines.append("")

    # Validated findings
    lines.append(HEADER_VALIDATED)
    lines.append("")
    disp_by_id = {d["id"]: d for d in (dispositions or []) if isinstance(d, dict)}
    validated_any = False
    for sid in sorted(disp_by_id):
        d = disp_by_id[sid]
        if d.get("verdict") != "validated":
            continue
        validated_any = True
        lines.append("### %s" % sid)
        lines.append("")
        lines.append("**Consequence:** %s" % d.get("consequence", ""))
        lines.append("")
        lines.append("**Receipt:** %s" % d.get("receipt", ""))
        lines.append("")
        lines.append("**Effort:** %s" % d.get("effort", ""))
        join = d.get("ledgerJoin")
        if join and join in ledger.get("byId", {}):
            hist = ledger["byId"][join]
            lines.append("")
            lines.append("**Ledger history:** disposition=%s issue=%s"
                         % (hist.get("disposition"), hist.get("issue")))
        lines.append("")
    if not validated_any:
        lines.append("_None._")
        lines.append("")

    # Tracked / filed
    lines.append(HEADER_TRACKED)
    lines.append("")
    status_lines = bundle.get("ledgerStatus") or []
    if status_lines:
        for st in status_lines:
            lines.append("- %s (%s): %s" % (st.get("id"), st.get("lens"), st.get("line")))
    else:
        lines.append("_None._")
    lines.append("")

    # Vitals delta
    _render_vitals(lines, bundle.get("vitalsDelta") or {})

    # Report card
    _render_report_card(lines, bundle.get("reportCard") or {})
    notes = bundle.get("reportCardNotes") or []
    if notes:
        lines.append("### Report-card configuration")
        lines.append("")
        for note in notes:
            lines.append("- %s" % note)
        lines.append("")

    # Candidate funnel
    lines.append(HEADER_FUNNEL)
    lines.append("")
    funnel = bundle.get("funnel") or {}
    raised = funnel.get("raised") or {}
    lines.append("### %s" % FUNNEL_RAISED)
    if raised:
        for lens in sorted(raised):
            lines.append("- %s: %d" % (lens, raised[lens]))
    else:
        lines.append("_None._")
    lines.append("")

    malformed = funnel.get("malformed") or []
    lines.append("### %s" % FUNNEL_MALFORMED)
    if malformed:
        for item in malformed:
            lines.append("- %s[%s]: %s" % (
                item.get("lens"), item.get("index"), item.get("repr")))
    else:
        lines.append("_None._")
    lines.append("")

    drift = funnel.get("killedByDrift") or []
    lines.append("### %s" % FUNNEL_KILLED_DRIFT)
    if drift:
        for item in drift:
            lines.append("- %s (%s): %s" % (
                item.get("id"), item.get("lens"), item.get("reason")))
    else:
        lines.append("_None._")
    lines.append("")

    ledger_killed = funnel.get("killedByLedger") or []
    lines.append("### %s" % FUNNEL_KILLED_LEDGER)
    if ledger_killed:
        for item in ledger_killed:
            lines.append("- %s (%s): %s" % (
                item.get("id"), item.get("lens"), item.get("disposition")))
    else:
        lines.append("_None._")
    lines.append("")

    benched = funnel.get("killedByBench") or []
    lines.append("### %s" % FUNNEL_KILLED_BENCH)
    if benched:
        for item in benched:
            lines.append("- %s (%s): %s" % (
                item.get("id"), item.get("lens"), item.get("reason")))
    else:
        lines.append("_None._")
    lines.append("")

    match_notes = funnel.get("matchNotes") or []
    lines.append("### %s" % FUNNEL_MATCH_NOTES)
    if match_notes:
        for item in match_notes:
            lines.append("- %s (%s): %s" % (
                item.get("id"), item.get("lens"), item.get("note")))
    else:
        lines.append("_None._")
    lines.append("")

    tracked_filed = funnel.get("trackedFiled") or []
    lines.append("### %s" % FUNNEL_TRACKED_FILED)
    if tracked_filed:
        for item in tracked_filed:
            lines.append("- %s (%s)" % (item.get("id"), item.get("lens")))
    else:
        lines.append("_None._")
    lines.append("")

    degraded = funnel.get("degradedLenses") or []
    lines.append("### %s" % FUNNEL_DEGRADED)
    if degraded:
        for item in degraded:
            lines.append("- %s: %s" % (item.get("lens"), item.get("reason")))
    else:
        lines.append("_None._")
    lines.append("")

    rejected = [d for d in (dispositions or [])
                if isinstance(d, dict) and d.get("verdict") == "rejected"]
    lines.append("### %s" % FUNNEL_REJECTED)
    if rejected:
        for d in rejected:
            lines.append("- %s" % d.get("id"))
    else:
        lines.append("_None._")
    lines.append("")

    validated_ids = {d["id"] for d in (dispositions or [])
                     if isinstance(d, dict) and d.get("verdict") == "validated"}
    lines.append("### %s" % FUNNEL_VALIDATED)
    if validated_ids:
        for vid in sorted(validated_ids):
            lines.append("- %s" % vid)
    else:
        lines.append("_None._")
    lines.append("")

    return "\n".join(lines)
