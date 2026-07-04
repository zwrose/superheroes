#!/usr/bin/env python3
"""#130 token telemetry — the cross-run efficiency trend over the control-plane store.

Reads each work-item's `events.jsonl` under a checkout's `issues/*/`, rolls each run's cost up via
`cost_report.summarize`, classifies it (completed / parked / other from its terminal event), and
reports **tokens-per-completed-work-item** and **tokens-per-park** across runs — so the efficiency
trend #125/#118 cut is one command away. Output tokens are measured-only and approximate (budget
deltas); an unmeasured run still contributes exact dispatch counts. stdlib only; fail-soft.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import control_plane
import cost_report
import journal


def classify(events):
    """completed / parked / other, from the LAST terminal marker (run_completed wins over parked)."""
    state = "other"
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        etype = ev.get("type")
        if etype == "run_completed":
            state = "completed"
        elif etype == "parked":
            state = "parked"
    return state


def run_cost(events):
    """One run's trend row (state + exact dispatches + measured output tokens)."""
    summary = cost_report.summarize(events)
    return {
        "state": classify(events),
        "dispatches": summary["totalDispatches"],
        "outputTokens": summary["outputTokens"],
        "measured": summary["measured"],
    }


def collect_runs(checkout_dir):
    """Every work-item run under <checkout_dir>/issues/*/events.jsonl. Missing dir -> []."""
    issues = os.path.join(checkout_dir, "issues")
    try:
        names = sorted(os.listdir(issues))
    except OSError:
        return []
    runs = []
    for work_item in names:
        ev_path = os.path.join(issues, work_item, "events.jsonl")
        if not os.path.isfile(ev_path):
            continue
        events = [e for e in journal.read_events(ev_path) if isinstance(e, dict)]
        row = run_cost(events)
        row["workItem"] = work_item
        runs.append(row)
    return runs


def collect_for_cwd(cwd, store_root=None):
    return collect_runs(control_plane.checkout_dir(cwd, store_root))


def _avg(total, n):
    return round(total / n, 1) if n else None


def _bucket(rows):
    count = len(rows)
    dispatches = sum(r["dispatches"] for r in rows)
    measured = [r for r in rows if r["measured"] and r["outputTokens"] is not None]
    tokens = sum(r["outputTokens"] for r in measured)
    return {
        "count": count,
        "dispatches": dispatches,
        "outputTokens": tokens if measured else None,
        "tokenItems": len(measured),
        "dispatchesPerItem": _avg(dispatches, count),
        "tokensPerItem": _avg(tokens, len(measured)),
        # park-flavoured aliases (same numbers) so the report reads naturally for either bucket
        "dispatchesPerPark": _avg(dispatches, count),
        "tokensPerPark": _avg(tokens, len(measured)),
    }


def build_trend(runs):
    runs = list(runs or [])
    return {
        "runs": runs,
        "completed": _bucket([r for r in runs if r["state"] == "completed"]),
        "parked": _bucket([r for r in runs if r["state"] == "parked"]),
        "other": {"count": sum(1 for r in runs if r["state"] == "other")},
    }


def _fmt(n):
    if n is None:
        return "—"
    return "{:,}".format(int(n)) if float(n).is_integer() else "{:,.1f}".format(n)


def _tok(n):
    return "—" if n is None else "≈%s" % _fmt(n)


def render_trend(trend):
    trend = trend or {}
    runs = trend.get("runs") or []
    lines = ["# Token trend", ""]
    if not runs:
        lines.append("_No recorded runs found in the store for this checkout._")
        return "\n".join(lines) + "\n"
    lines += ["| work-item | state | dispatches | output tokens |",
              "| --- | --- | ---: | ---: |"]
    for r in runs:
        lines.append("| %s | %s | %s | %s |"
                     % (r["workItem"], r["state"], _fmt(r["dispatches"]),
                        _tok(r["outputTokens"]) if r["measured"] else "not measured"))
    comp, park = trend["completed"], trend["parked"]
    lines += [
        "",
        "**Per completed work-item** (%d): %s output tokens · %s dispatches%s"
        % (comp["count"], _tok(comp["tokensPerItem"]), _fmt(comp["dispatchesPerItem"]),
           "" if comp["tokenItems"] == comp["count"] else " · tokens over %d measured of %d" % (comp["tokenItems"], comp["count"])),
        "**Per park** (%d): %s output tokens · %s dispatches"
        % (park["count"], _tok(park["tokensPerPark"]), _fmt(park["dispatchesPerPark"])),
    ]
    if trend.get("other", {}).get("count"):
        lines.append("_(%d in-progress/other run(s) excluded from the averages.)_" % trend["other"]["count"])
    lines += ["", "_Output tokens are approximate (budget-derived, output-only); dispatch counts are exact._"]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="tokens-per-work-item trend over the control-plane store")
    ap.add_argument("--root", default=None, help="repo cwd used to resolve the checkout store (default: cwd)")
    ap.add_argument("--store-root", default=None, help="override the store root")
    ap.add_argument("--json", action="store_true", help="emit the trend as JSON instead of a table")
    args = ap.parse_args(argv)
    runs = collect_for_cwd(args.root or os.getcwd(), store_root=args.store_root)
    trend = build_trend(runs)
    if args.json:
        print(json.dumps(trend, indent=2))
    else:
        sys.stdout.write(render_trend(trend))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
