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
FUNNEL_TRACKED_FILED = "tracked-filed"
FUNNEL_DEGRADED = "degraded-lenses"
FUNNEL_REJECTED = "model-rejected"
FUNNEL_VALIDATED = "surfaced-and-validated"


def render(bundle, dispositions, ledger):
    """Deterministic markdown report from a collect bundle + model dispositions."""
    lines = [HEADER_TITLE, ""]
    committed = bundle.get("committed", "uncommitted")
    lines.append("committed: %s" % committed)
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
    lines.append(HEADER_VITALS)
    lines.append("")
    vd = bundle.get("vitalsDelta") or {}
    if vd:
        for k in sorted(vd):
            lines.append("- %s: %s" % (k, vd[k]))
    else:
        lines.append("_No vitals movement._")
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
