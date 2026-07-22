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


def _fmt_delta_entry(name, move, *, completeness=None):
    if not isinstance(move, dict):
        return "%s: %s" % (name, move)
    prev, cur = move.get("prev"), move.get("cur")
    change = move.get("change")
    text = "%s: %s → %s (%s)" % (name, prev, cur, change)
    entry = (completeness or {}).get(name) if isinstance(completeness, dict) else None
    if isinstance(entry, dict) and entry.get("state") == "partial":
        reason = entry.get("reason") or "incomplete measurement"
        text = "%s (partial: %s)" % (text, reason)
    return text


def _render_vitals(lines, vd, snapshot=None):
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
    sources = vd.get("sources") if isinstance(vd, dict) else None
    if not isinstance(sources, dict):
        sources = {}
    completeness = vd.get("completeness") if isinstance(vd, dict) else None
    if not isinstance(completeness, dict):
        completeness = {}
    snapshot_vitals = {}
    if isinstance(snapshot, dict):
        raw = snapshot.get("vitals")
        if isinstance(raw, dict):
            snapshot_vitals = raw

    partial_vitals = {
        name for name, entry in completeness.items()
        if isinstance(entry, dict) and entry.get("state") == "partial"
    }

    not_comparable = {}
    if isinstance(delta, dict):
        raw_nc = delta.get("_notComparable")
        if isinstance(raw_nc, dict):
            not_comparable = raw_nc
    skipped_comparisons = bool(not_comparable)

    crossing_vitals = set()
    if crossings:
        for c in crossings:
            if not isinstance(c, dict):
                continue
            vital = c.get("vital")
            crossing_vitals.add(vital)
            sentence = c.get("sentence") or _fmt_delta_entry(
                vital, c, completeness=completeness)
            if vital in partial_vitals:
                reason = (completeness.get(vital) or {}).get("reason")
                if reason:
                    sentence = "%s (partial: %s)" % (sentence, reason)
            lines.append("- %s" % sentence)
    non_crossing = []
    if delta:
        for name in sorted(delta):
            if name in crossing_vitals or name == "_notComparable":
                continue
            non_crossing.append(
                _fmt_delta_entry(name, delta[name], completeness=completeness))
        if non_crossing:
            if crossings:
                lines.append("")
                lines.append("Other movement:")
            for item in non_crossing:
                lines.append("- %s" % item)

    measured_movement = bool(crossings) or bool(non_crossing)
    if not_comparable:
        if measured_movement:
            lines.append("")
        lines.append("Comparison skipped:")
        for name in sorted(not_comparable):
            lines.append("- %s: %s" % (name, not_comparable[name]))

    if not_collected:
        if measured_movement:
            lines.append("")
        lines.append("Not collected:")
        for name in sorted(not_collected):
            reason = not_collected[name]
            lines.append("- %s: %s" % (name, reason))

    shown_in_movement = crossing_vitals | {
        name for name in (delta or {}) if name != "_notComparable"
    }
    partial_only = partial_vitals - shown_in_movement - set(not_collected.keys())
    if partial_only:
        if measured_movement or not_collected or skipped_comparisons:
            lines.append("")
        lines.append("Partial measurements:")
        for name in sorted(partial_only):
            reason = (completeness.get(name) or {}).get("reason") or (
                "incomplete measurement")
            value = None
            move = (delta or {}).get(name)
            if isinstance(move, dict):
                value = move.get("cur")
            if value is None:
                value = snapshot_vitals.get(name)
            lines.append("- %s: %s (partial: %s)" % (name, value, reason))

    if not measured_movement and not skipped_comparisons:
        if not_collected and not sources:
            lines.append(
                "_No vitals movement — nothing was collected this sweep._")
        elif not_collected:
            lines.append(
                "_No vitals movement — %d value(s) collected; "
                "some vitals were unavailable._" % len(sources))
        elif sources:
            lines.append(
                "_No vitals movement — first sweep establishing baseline "
                "(%d value(s) collected)._"
                % len(sources))
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
    _render_vitals(lines, bundle.get("vitalsDelta") or {},
                   bundle.get("nextSnapshot"))

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
