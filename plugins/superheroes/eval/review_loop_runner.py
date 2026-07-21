#!/usr/bin/env python3
"""Python convergence harness for the review-loop round driver (#507 WO-D).

Ports the retired JS convergence harness onto ``round_driver.run_loop``: loads a fixture, builds
scripted seams (reviewer / synthesis / verifier / auditor / fix_step / verify_runner),
runs the panel-leg library loop, and emits the same observational JSON shape the JS
runner printed:

  {terminal, roundCount, tokenTotal, benchmarkValid, telemetry,
   coverageDecisionIds, seen, fixContexts, fixResults}

Importable (``run_fixture``) for in-process tests, and runnable as a CLI:

  python3 review_loop_runner.py <fixture.json> [--fail-telemetry]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
LIB = EVAL_DIR.parent / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

import circuit_breaker as CB  # noqa: E402
import coverage_decisions as cov  # noqa: E402
import review_loop_plan as RLP  # noqa: E402
import review_memory as RM  # noqa: E402
import review_telemetry as RT  # noqa: E402
import round_driver as RD  # noqa: E402

# Synthetic citation surface so fixture findings (often file/line-less, written for the JS
# shell's graftSynthesizedFindings path) survive round_driver.mechanical_compile.
_EVAL_FILE = "eval-fixture.py"
_EVAL_DIFF = (
    "diff --git a/{f} b/{f}\n"
    "index 1..2 100644\n"
    "--- a/{f}\n"
    "+++ b/{f}\n"
    "@@ -1 +1,4 @@\n"
    "-old\n"
    "+line1\n"
    "+line2\n"
    "+line3\n"
    "+line4\n"
).format(f=_EVAL_FILE)
_EVAL_HEAD = (
    "diff --git a/{f} b/{f}\n"
    "index 2..3 100644\n"
    "--- a/{f}\n"
    "+++ b/{f}\n"
    "@@ -1 +1,5 @@\n"
    "-old\n"
    "+line1\n"
    "+line2\n"
    "+line3\n"
    "+line4\n"
    "+line5\n"
).format(f=_EVAL_FILE)
_EVAL_LINE = 2

_TERMINAL_MAP = {
    "converged": "clean",
    "halted": "halted",
    "held": "halted",
    "stalled": "halted",
    "capped-with-open-critical": "halted",
    "cannot-certify": "halted",
}


def _receipt(run_id, round_no, coverage_decisions=None):
    ids = [d.get("id") for d in (coverage_decisions or []) if isinstance(d, dict) and d.get("id")]
    return {
        "artifact": "%s:round-%d" % (run_id, round_no),
        "chain": [
            {"step": "citation", "evidence": "fixture cited changed artifact"},
            {"step": "reachability", "evidence": "fixture reached changed path"},
            {"step": "missing-check", "evidence": "fixture checked missing requirements"},
            {"step": "tooling", "evidence": "fixture harness completed"},
        ],
        "coverageDecisionIds": ids,
    }


def _cite(findings):
    out = []
    for f in findings or []:
        if not isinstance(f, dict):
            continue
        g = dict(f)
        if g.get("file") is None:
            g["file"] = _EVAL_FILE
        if g.get("line") is None:
            g["line"] = _EVAL_LINE
        out.append(g)
    return out


def _load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path, obj):
    path = str(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)
    os.replace(tmp, path)


def _persist_round_record(run_dir, round_no, kind, dim_results, changed_subjects, coverage, usage):
    records_path = os.path.join(run_dir, "round-records.json")
    state = RM.load_records_state(records_path, [])
    records = list(state.get("records") or []) if state.get("ok") else []
    record = RM.record_from_dimension_results(
        round_no, kind, dim_results, changed_subjects, coverage, usage or {})
    RM.persist_record(records_path, records, record, run_id="eval")


def _append_coverage(run_dir, decisions):
    if not decisions:
        return
    path = os.path.join(run_dir, "review-coverage-decisions.json")
    existing = []
    if os.path.exists(path):
        try:
            loaded = cov.load_decisions(path, "code")
            if loaded.get("ok"):
                existing = list(loaded.get("decisions") or [])
        except Exception:  # noqa: BLE001
            existing = []
    by_id = {d.get("id"): d for d in existing if isinstance(d, dict) and d.get("id")}
    for d in decisions:
        if isinstance(d, dict) and d.get("id"):
            by_id[d["id"]] = d
    _write_json(path, list(by_id.values()))


def _compose_worklist(run_dir, round_no, batch, roster):
    """Write the fixer worklist (compose_fix_context) and return its path + loaded content."""
    records_path = os.path.join(run_dir, "round-records.json")
    coverage_path = os.path.join(run_dir, "review-coverage-decisions.json")
    findings_path = os.path.join(run_dir, "current-findings-r%d.json" % round_no)
    worklist_path = os.path.join(run_dir, "fix-context-r%d.json" % round_no)
    _write_json(findings_path, list(batch or []))
    if not os.path.exists(records_path):
        _write_json(records_path, [])
    if not os.path.exists(coverage_path):
        _write_json(coverage_path, [])
    result = RLP.compose_fix_context(
        records_path, findings_path, coverage_path, "code",
        round_no, roster, worklist_path)
    if not result.get("ok"):
        # Fail-closed soft: still hand the fixer a minimal worklist so the seam can run.
        minimal = {
            "schemaVersion": 1,
            "round": round_no,
            "findings": list(batch or []),
            "classKeys": [
                f.get("classKey") or RM.class_key(f)
                for f in (batch or []) if isinstance(f, dict)
            ],
            "generalizeRequired": [],
            "changedSubjects": [],
            "coverageDecisions": [],
        }
        _write_json(worklist_path, minimal)
        return worklist_path, minimal
    with open(worklist_path, encoding="utf-8") as fh:
        return worklist_path, json.load(fh)


def run_fixture(fixture, fail_telemetry=False, run_dir=None, corrupt_records=False):
    """Drive ``round_driver.run_loop`` for one fixture; return the observational JSON dict.

    ``fixture`` may be a path (str/Path) or an already-loaded dict. ``corrupt_records`` writes a
    mangled round-records.json so the driver's fail-closed resume seam parks (cannot-certify).
    """
    if isinstance(fixture, (str, Path)):
        fixture_path = Path(fixture)
        fixture = _load_json(fixture_path)
    else:
        fixture_path = None

    name = fixture.get("name") or (fixture_path.stem if fixture_path else "fixture")
    reviewer_set = list(fixture.get("reviewerSet") or RD.DIMENSIONS)
    max_rounds = int(fixture.get("maxRounds") or 7)
    events = [dict(e) for e in (fixture.get("reviewerEvents") or [])]
    fix_events = list(fixture.get("fixEvents") or [])
    own_dir = run_dir is None
    if own_dir:
        run_dir = tempfile.mkdtemp(prefix="%s-" % name)

    records_path = os.path.join(run_dir, "round-records.json")
    coverage_path = os.path.join(run_dir, "review-coverage-decisions.json")
    if fixture.get("seedRoundRecords") is not None:
        _write_json(records_path, fixture["seedRoundRecords"])
    else:
        _write_json(records_path, [])
    if fixture.get("seedCoverageDecisions") is not None:
        _write_json(coverage_path, fixture["seedCoverageDecisions"])
    else:
        _write_json(coverage_path, [])
    if corrupt_records:
        with open(records_path, "w", encoding="utf-8") as fh:
            fh.write("{corrupt json — not a records array")

    # Post-round-1 event translation (#507 WO-D §B). The driver's schedule is delta rounds (a
    # scoped-finder re-scan) plus re-armed confirmation PANELS — it does NOT re-run every named
    # dimension each round the way the JS shell did. Map the fixture's post-round-1 events onto that
    # schedule WITHOUT editing the fixture JSON or the goldens: each delta scoped scan surfaces the
    # next fixture event-round that carried findings (empty rounds are the driver's own clean
    # deltas); a blocking finding whose (dim, title, severity) recurs across ≥2 fixture rounds is an
    # UNRESOLVED/recurring finding that ALSO re-surfaces on its dimension's re-armed confirmation
    # seat — so a recurring Critical re-arms confirmations to the cap and parks (skipped-dimension
    # regression), with a real security-reviewer seat running in the re-armed confirmation.
    def _sig(dim, f):
        return (dim, str(f.get("title")), str(f.get("severity")))

    _sig_rounds = {}
    for e in events:
        if not isinstance(e.get("round"), int) or e.get("round") <= 1:
            continue
        for f in e.get("findings") or []:
            if isinstance(f, dict) and CB.is_blocking(f.get("severity")):
                _sig_rounds.setdefault(_sig(e.get("reviewer"), f), set()).add(e.get("round"))
    recurring_sigs = {s for s, rs in _sig_rounds.items() if len(rs) >= 2}
    persistent = {}   # dim -> a recurring blocking finding to re-surface on confirmation seats
    fix_queue = list(fix_events)

    seen = []
    usage = {}
    coverage_decision_ids = []
    fix_contexts = []
    fix_results = []
    # Live coverage decisions accumulated during the run (plus seeds).
    live_coverage = []
    if fixture.get("seedCoverageDecisions"):
        live_coverage.extend(fixture["seedCoverageDecisions"])

    # Track last panel dim→findings for round-record persistence.
    last_panel = {"dims": {}, "round": None, "kind": "baseline"}
    head_n = {"n": 0}
    # The changed-subjects seam (#507 finding v2) replays THIS fix's fixture changedSubjects — the
    # same value fix_step returns — so the driver's git-derivation seam is exercised structurally
    # while fixture semantics + goldens stay unchanged. fix_step records it here; the driver calls
    # the seam right after folding the fixer artifact.
    last_fix = {"changedSubjects": None}

    def _head_diff():
        head_n["n"] += 1
        n = head_n["n"]
        return (
            "diff --git a/{f} b/{f}\n"
            "index 2..{n} 100644\n"
            "--- a/{f}\n"
            "+++ b/{f}\n"
            "@@ -1 +1,{lines} @@\n"
            "-old\n"
            "{adds}"
        ).format(
            f=_EVAL_FILE, n=n + 2, lines=4 + n,
            adds="".join("+line%d\n" % i for i in range(1, 5 + n)),
        )

    def _next_delta_round():
        cand = sorted({e.get("round") for e in events
                       if isinstance(e.get("round"), int) and e.get("round") > 1
                       and any(e.get("findings") or [])})
        return cand[0] if cand else None

    def reviewer(dim, tier, rnd, payload):
        # Scoped-finder / gap-sweep (a DELTA scan): surface the next fixture event-round that
        # carried findings, at this driver round. Empty fixture rounds are the driver's own clean
        # deltas (they trigger the converged-candidate / confirmation-rearm decision), so we skip
        # them rather than emit a dead seat.
        if dim in ("scoped-finder", "gap-sweep"):
            target = _next_delta_round()
            if target is None:
                seen.append({"reviewer": "scoped-finder", "round": rnd, "tier": tier,
                             "roundKind": "intermediate"})
                usage.setdefault("scoped-finder:r%d" % rnd, {"total": 1})
                return {"findings": [], "confidence": "high",
                        "verificationReceipt": _receipt(name, rnd, live_coverage),
                        "usage": {"total": 1}}
            evs = [e for e in events if e.get("round") == target]
            for e in list(evs):
                events.remove(e)
            merged = []
            usage_total = 0
            for e in evs:
                obs = e.get("reviewer") or "scoped-finder"
                etier = e.get("tier") or tier
                cited = _cite(e.get("findings") or [])
                merged.extend(cited)
                ut = int(e.get("usageTotal") or 1)
                usage_total += ut
                usage["%s:r%d" % (obs, rnd)] = {"total": ut}
                seen.append({"reviewer": obs, "round": rnd, "tier": etier,
                             "roundKind": "intermediate"})
                last_panel["dims"][obs] = {
                    "status": "run", "confidence": e.get("confidence") or "high",
                    "tier": etier, "findings": cited, "hasFindings": bool(cited)}
                for f in cited:
                    if CB.is_blocking(f.get("severity")) and _sig(obs, f) in recurring_sigs:
                        persistent[obs] = f
            last_panel["round"] = rnd
            last_panel["kind"] = "intermediate"
            return {"findings": merged, "confidence": "high",
                    "verificationReceipt": _receipt(name, rnd, live_coverage),
                    "usage": {"total": usage_total or 1}}

        # Named-dimension seat: a round-1 baseline panel, a resumed round, or a re-armed
        # confirmation panel. Match this round's event first (baseline / resume / seeded), else — on
        # a re-armed confirmation (round ≥ 2) — re-surface this dimension's recurring finding so the
        # security-reviewer confirmation seat keeps raising the unresolved Critical up to the cap.
        idx = next(
            (i for i, e in enumerate(events)
             if e.get("round") == rnd and e.get("reviewer") == dim
             and (not e.get("tier") or e.get("tier") == tier)),
            None,
        )
        if idx is not None:
            event = events.pop(idx)
        elif rnd > 1 and dim in persistent:
            event = {"findings": [persistent[dim]], "usageTotal": 1, "reviewer": dim,
                     "tier": RD.DEEP}
        else:
            event = {"findings": [], "usageTotal": 1, "reviewer": dim}

        kind = "baseline"
        if rnd > 1 and (tier == RD.DEEP or event.get("tier") == RD.DEEP) and dim in reviewer_set:
            kind = "confirmation"
        elif rnd > 1:
            kind = "intermediate"

        seen.append({
            "reviewer": dim,
            "round": rnd,
            "tier": event.get("tier") or tier,
            "roundKind": kind,
        })

        findings = _cite(event.get("findings") or [])
        usage_total = int(event.get("usageTotal") or 1)
        usage["%s:r%d" % (dim, rnd)] = {"total": usage_total}

        last_panel["dims"][dim] = {
            "status": "run",
            "confidence": event.get("confidence") or "high",
            "tier": event.get("tier") or tier,
            "findings": findings,
            "hasFindings": bool(findings),
        }
        last_panel["round"] = rnd
        last_panel["kind"] = kind

        return {
            "findings": findings,
            "confidence": event.get("confidence") or "high",
            "verificationReceipt": _receipt(name, rnd, live_coverage),
            "usage": {"total": usage_total},
        }

    def synthesis(findings, rnd):
        usage["synthesis:r%d" % rnd] = {"total": 1}
        return None  # empty grouping — round_driver merge_and_rank keeps findings

    def verifier(clusters, rnd):
        # Confirm every staged finding so blocking findings survive to the fix leg
        # (mirrors JS synthesisUnverified keep-on-empty-verdicts for gate purposes).
        out = []
        for c in clusters or []:
            for i in c.get("ids") or []:
                out.append({"id": i, "verdict": "CONFIRMED", "evidence": "fixture harness"})
        return out

    def auditor(targets, rnd):
        # Default: discharge — #507 scoped certification path. Fixtures that need a
        # not-discharged stall rely on scoped-finder re-raising blocking findings. Echo the
        # selected independent auditor vendor so the discharge clears the provenance gate.
        return [
            {"id": t["id"], "ruling": "discharged", "reason": "fixture discharge",
             "evidence": "fixture", "auditorVendor": t.get("auditorVendor")}
            for t in (targets or [])
        ]

    def _dims_for_batch(batch, rnd):
        dims = dict(last_panel["dims"]) if last_panel["round"] == rnd else {}
        if dims:
            return dims
        if not batch:
            return {}
        # Attribute the fix-batch findings to a reviewer dim for recurrence tracking.
        dim_name = reviewer_set[0] if reviewer_set else "test-reviewer"
        first = batch[0] if isinstance(batch[0], dict) else {}
        prefix = str(first.get("dimension") or "").split()[0].lower()
        for r in reviewer_set:
            if r.startswith(prefix):
                dim_name = r
                break
        return {
            dim_name: {
                "status": "run", "confidence": "high", "tier": RD.DEEP,
                "findings": list(batch), "hasFindings": True,
            }
        }

    def fix_step(batch, rnd, payload):
        # Persist this round's findings BEFORE composing the worklist so
        # recurrent_classes sees the current round (JS tally persists then composes).
        kind = last_panel.get("kind") if last_panel["round"] == rnd else "intermediate"
        if rnd <= 1:
            kind = last_panel.get("kind") or "baseline"
        dims = _dims_for_batch(batch, rnd)
        _persist_round_record(run_dir, rnd, kind or "intermediate", dims, [], live_coverage, {})

        worklist_path, context = _compose_worklist(run_dir, rnd, batch, reviewer_set)
        # Re-read from disk (JS runner contract: fixer receives the path).
        try:
            with open(worklist_path, encoding="utf-8") as fh:
                context = json.load(fh)
        except (OSError, ValueError):
            pass
        fix_contexts.append({"round": rnd, "context": context})
        usage["fix:r%d" % rnd] = {"total": 1}

        # Consume fixEvents in fixture ORDER (a queue), not by literal `afterRound` — the driver's
        # round numbering diverges from the JS scheduler's, so the Nth fix the driver runs takes the
        # Nth fixture fixEvent (its changedSubjects / coverageDecisions). This keeps the cross-cutting
        # rework subjects and the coverage-decision recording aligned with the driver's fix legs.
        fix = fix_queue.pop(0) if fix_queue else None
        if fix is None:
            fix = {"changedSubjects": [], "coverageDecisions": []}
        # Record for the changed-subjects seam the driver calls right after folding this artifact.
        last_fix["changedSubjects"] = list(fix.get("changedSubjects") or [])
        cds = list(fix.get("coverageDecisions") or [])
        ids = [d.get("id") for d in cds if isinstance(d, dict) and d.get("id")]
        fix_results.append({"round": rnd, "coverageDecisionIds": ids})
        for d in cds:
            if isinstance(d, dict) and d.get("id"):
                coverage_decision_ids.append(d["id"])
                live_coverage.append(d)
        _append_coverage(run_dir, cds)

        # Update the round record with changedSubjects now that the fix ran.
        _persist_round_record(
            run_dir, rnd, kind or "intermediate", dims,
            fix.get("changedSubjects") or [], live_coverage, {"available": True})

        return {
            "fixes": ["fixture"],
            "headDiff": _head_diff(),
            "changedSubjects": list(fix.get("changedSubjects") or []),
            "coverageDecisions": cds,
        }

    def verify_runner(command, rnd):
        return "pass"

    def changed_subjects(reviewed_diff_text, head_diff_text, accumulated_findings):
        # Scripted replay of the just-run fix's fixture changedSubjects — same pattern as the
        # scripted reviewers. The driver derives these from git on the live path; the harness's
        # synthetic single-file diffs cannot express the fixtures' explicit subjects, so the seam
        # replays them (fixture semantics + goldens unchanged, #507 finding v2).
        return last_fix["changedSubjects"]

    # After each full panel fold, persist round records (panel path may certify with no fix).
    _orig_fold_panel = RD._fold_panel

    def _fold_panel_persist(state, config, artifact):
        _orig_fold_panel(state, config, artifact)
        rnd = state["round"]
        kind = "baseline" if rnd <= 1 else (
            "confirmation" if (state.get("rounds") or {}).get(str(rnd), {}).get("roundKind")
            == "confirmation" or rnd > 1 else "intermediate")
        # Prefer confirmation label when this panel was a re-arm.
        rec = (state.get("rounds") or {}).get(str(rnd)) or {}
        if rec.get("roundKind") == "confirmation":
            kind = "confirmation"
        elif rnd > 1 and state.get("confirmations", 0) >= 0:
            # Round incremented on re-arm before panel; roundKind was stamped on this round.
            if any(d.get("kind") == "confirmation-rearm" and d.get("round") == rnd - 1
                   for d in state.get("decisions") or []):
                kind = "confirmation"
        seats = artifact.get("seats") if isinstance(artifact.get("seats"), dict) else artifact
        dims = {}
        for dim in reviewer_set:
            seat = seats.get(dim) if isinstance(seats, dict) else None
            findings = []
            if isinstance(seat, dict):
                findings = seat.get("findings") or []
            elif isinstance(seat, list):
                findings = seat
            dims[dim] = {
                "status": "run", "confidence": "high", "tier": RD.DEEP,
                "findings": findings, "hasFindings": bool(findings),
            }
        last_panel["dims"] = dims
        last_panel["round"] = rnd
        last_panel["kind"] = kind
        _persist_round_record(run_dir, rnd, kind, dims, [], live_coverage, {})

    RD._fold_panel = _fold_panel_persist
    try:
        seams = {
            "reviewer": reviewer,
            "synthesis": synthesis,
            "verifier": verifier,
            "auditor": auditor,
            "fix_step": fix_step,
            "verify_runner": verify_runner,
            "changed_subjects": changed_subjects,
            "io": {
                "stall_menu": lambda payload: "hold",
                "seatMap": {},
            },
        }
        config = {
            "leg": "panel",
            "dimensions": reviewer_set,
            "maxRounds": max_rounds,
            "diff": _EVAL_DIFF,
            "vendors": ["claude", "codex"],
            "fixerVendor": "claude",
            "verifyCommand": "none",
            # The driver reads these ONCE at new_state to resume from the durable seeds and to seed
            # the challenged-coverage breaker's accumulated decisions (#507 WO-D resume/records seam).
            "recordsPath": records_path,
            "coveragePath": coverage_path,
        }
        receipt = RD.run_loop(seams, config)
    finally:
        RD._fold_panel = _orig_fold_panel

    driver_terminal = receipt.get("verdict")
    terminal = _TERMINAL_MAP.get(driver_terminal, driver_terminal or "halted")

    round_count = max((c["round"] for c in seen), default=0)
    # Expected leaves: prefer the JS finalize schedule shape when every roster seat ran
    # each round; otherwise (delta rounds only dispatch scoped finders) derive leaves from
    # observed `seen` + synthesis + fix so benchmark completeness stays honest.
    rounds_seen = sorted({c["round"] for c in seen}) or [1]
    expected_leaves = []
    fix_rounds = {f["round"] for f in fix_contexts}
    for r in rounds_seen:
        ran = [c["reviewer"] for c in seen if c["round"] == r and c["reviewer"] in reviewer_set]
        # Full panel rounds: expect the whole roster (matches JS expectedUsageLeaves).
        if len(set(ran)) >= len(reviewer_set):
            for name_r in reviewer_set:
                expected_leaves.append("%s:r%d" % (name_r, r))
        else:
            for name_r in ran:
                leaf = "%s:r%d" % (name_r, r)
                if leaf not in expected_leaves:
                    expected_leaves.append(leaf)
        expected_leaves.append("synthesis:r%d" % r)
        usage.setdefault("synthesis:r%d" % r, {"total": 1})
        if r in fix_rounds:
            expected_leaves.append("fix:r%d" % r)

    telem_path = os.path.join(run_dir, "review-telemetry.json")
    telemetry = None
    if fail_telemetry:
        telemetry = {"benchmarkValid": False, "reason": "telemetry-write-failed"}
        benchmark_valid = False
    else:
        # Inject fix:rN usage defaults like the JS runner's runHelper shim.
        for leaf in expected_leaves:
            if leaf.startswith("fix:r") and leaf not in usage:
                usage[leaf] = {"total": 1}
        summary = RT.write_from_records(
            telem_path, records_path, expected_leaves, usage,
            terminal=terminal, benchmark=bool(fixture.get("benchmark")),
            run_id=name)
        if summary.get("ok"):
            # Prefer the on-disk record (includes runId stamp write_record adds).
            try:
                with open(telem_path, encoding="utf-8") as fh:
                    telemetry = json.load(fh)
            except (OSError, ValueError):
                telemetry = {k: v for k, v in summary.items() if k != "ok"}
            # Drop transport-only lease if present.
            telemetry.pop("lease", None)
            benchmark_valid = bool(telemetry.get("benchmarkValid"))
        else:
            telemetry = {"benchmarkValid": False,
                         "reason": summary.get("reason") or "telemetry-write-failed"}
            benchmark_valid = False

    fallback_total = sum(int((u or {}).get("total") or 0) for u in usage.values())
    if telemetry and isinstance(telemetry.get("tokenUsage"), dict):
        token_total = telemetry["tokenUsage"].get("total", fallback_total)
    else:
        token_total = fallback_total

    return {
        "terminal": terminal,
        "roundCount": round_count,
        "tokenTotal": token_total,
        "benchmarkValid": benchmark_valid,
        "telemetry": telemetry,
        "coverageDecisionIds": coverage_decision_ids,
        "seen": seen,
        "fixContexts": fix_contexts,
        "fixResults": fix_results,
        "_driverReceipt": receipt,
        "_runDir": run_dir if not own_dir else None,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", help="path to a review_loop fixture JSON")
    parser.add_argument("--fail-telemetry", action="store_true",
                        help="force telemetry write failure (benchmarkValid false)")
    args = parser.parse_args(argv)
    out = run_fixture(args.fixture, fail_telemetry=args.fail_telemetry)
    # Strip harness-only keys from CLI output (match JS runner shape).
    public = {k: v for k, v in out.items() if not k.startswith("_")}
    sys.stdout.write(json.dumps(public) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
