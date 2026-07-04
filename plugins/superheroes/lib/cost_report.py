"""#130 token telemetry — the run-cost projection over `events.jsonl`.

`summarize` replays the additive `phase_cost` events (journal.py) into a per-run rollup:
total agent dispatches (always exact — the countable proxy), per-tier dispatch counts, and the
measured output-token total where the runtime surfaced it (budget.spent() phase-boundary deltas).
`render_cost_line` turns that rollup into the readout's cost line (total + top 1-2 phases). Tokens
are output-only and approximate (shared-pool budget deltas); they are shown ONLY when measured and
never fabricated — an unmeasured run reports honest dispatch counts and says tokens are unavailable.
stdlib only; never raises on a malformed event (telemetry is best-effort).
"""


def _int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def summarize(events):
    """events: the list from journal.read_events. Returns the run-cost rollup dict."""
    phases = []            # ordered, one entry per distinct phase (aggregated)
    by_phase = {}          # phase -> index into phases
    by_tier = {}
    total_dispatches = 0
    external = 0
    measured_tokens = 0
    any_measured = False
    any_unmeasured = False
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        etype = ev.get("type")
        if etype == "external_dispatch":
            external += 1
            continue
        if etype != "phase_cost":
            continue
        payload = ev.get("payload")
        if not isinstance(payload, dict):
            continue
        phase = payload.get("phase") or "unknown"
        disp = payload.get("dispatches")
        disp_total = _int(disp.get("total")) if isinstance(disp, dict) else None
        disp_total = disp_total or 0
        by_model = disp.get("byModel") if isinstance(disp, dict) else None
        tokens = payload.get("tokens") if isinstance(payload.get("tokens"), dict) else {}
        out = _int(tokens.get("output"))
        this_measured = bool(tokens.get("measured")) and out is not None
        if this_measured:
            any_measured = True
            measured_tokens += out
        else:
            any_unmeasured = True

        if phase in by_phase:
            row = phases[by_phase[phase]]
        else:
            by_phase[phase] = len(phases)
            row = {"phase": phase, "dispatches": 0, "outputTokens": None, "measured": False}
            phases.append(row)
        row["dispatches"] += disp_total
        if this_measured:
            row["outputTokens"] = (row["outputTokens"] or 0) + out
            row["measured"] = True

        total_dispatches += disp_total
        if isinstance(by_model, dict):
            for model, count in by_model.items():
                c = _int(count)
                if c:
                    by_tier[model] = by_tier.get(model, 0) + c

    # Rank the most expensive phases: by measured output tokens when any is measured, else by the
    # always-exact dispatch count. Top 2 per the issue ("top 1-2 most expensive phases").
    if any_measured:
        ranked = sorted(phases, key=lambda p: (p["outputTokens"] or 0, p["dispatches"]), reverse=True)
    else:
        ranked = sorted(phases, key=lambda p: p["dispatches"], reverse=True)
    top = [{"phase": p["phase"], "dispatches": p["dispatches"], "outputTokens": p["outputTokens"]}
           for p in ranked[:2] if p["dispatches"] > 0]

    return {
        "totalDispatches": total_dispatches,
        "byTier": by_tier,
        "outputTokens": measured_tokens if any_measured else None,
        "measured": any_measured,
        "partial": any_measured and any_unmeasured,
        "externalDispatches": external,
        "phases": phases,
        "topPhases": top,
    }


_SHORT = (("opus", "opus"), ("sonnet", "sonnet"), ("haiku", "haiku"), ("fable", "fable"))


def _short_model(model):
    m = str(model or "").lower()
    for needle, label in _SHORT:
        if needle in m:
            return label
    return str(model)


def _commas(n):
    return "{:,}".format(int(n))


def _tokens_phrase(tokens):
    return "≈%s output tokens" % _commas(tokens)


def render_cost_line(summary):
    """Render the readout's cost block as a list of markdown lines ([] when there is no cost data)."""
    summary = summary or {}
    total = summary.get("totalDispatches") or 0
    if total <= 0 and not summary.get("topPhases"):
        return []
    tiers = summary.get("byTier") or {}
    tier_bits = " · ".join("%s %s" % (_short_model(m), _commas(c))
                           for m, c in sorted(tiers.items(), key=lambda kv: (-kv[1], kv[0])))
    head = "- **Dispatches:** %s dispatches" % _commas(total)
    if tier_bits:
        head += " (%s)" % tier_bits
    if summary.get("externalDispatches"):
        head += " · %s external-engine" % _commas(summary["externalDispatches"])
    lines = ["### Run cost", head]

    if summary.get("measured"):
        tok = "- **Output tokens:** %s" % _tokens_phrase(summary.get("outputTokens") or 0)
        if summary.get("partial"):
            tok += " (partial — some phases unmeasured)"
        tok += " · _approximate; output-only, budget-derived_"
        lines.append(tok)
    else:
        lines.append("- **Output tokens:** not measured "
                     "(runtime token counts unavailable this run) — dispatch counts above are exact")

    top = summary.get("topPhases") or []
    if top:
        def _phase_bit(p):
            if p.get("outputTokens") is not None:
                return "%s (%s)" % (p["phase"], _tokens_phrase(p["outputTokens"]))
            return "%s (%s dispatches)" % (p["phase"], _commas(p["dispatches"]))
        label = "by tokens" if summary.get("measured") else "by dispatches"
        lines.append("- **Most expensive phases** (%s): %s"
                     % (label, ", ".join(_phase_bit(p) for p in top)))
    return lines
