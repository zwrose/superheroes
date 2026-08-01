#!/usr/bin/env python3
"""v2 run preflight (#472, WO-3): the interactive-approval probe lib + the FAIL-LOUD go/no-go
aggregator + the dispatch-calibration observability readout.

The subprocess-able probes (`gh auth`, the cross-vendor CLI no-op) live here — pure decision
logic plus an INJECTABLE command runner, so the whole lib is unit-testable with fakes; a Python
subprocess CANNOT drive the browser MCP. The browser live-exercise (connect -> navigate ->
snapshot) is a HOST-TOOL action the orchestrator performs per
`skills/configure/reference/preflight.md` and feeds in as an outcome via `browser_probe_result`.
This lib owns two things downstream of every probe: the FAIL-LOUD go/no-go aggregator
(`aggregate`) and the dispatch-calibration readout (`dispatch_calibration`) — the effective
engine + model per v2 dispatch role, for the build brief + PR provenance.

stdlib only. A probe never raises out of itself (FAIL-LOUD: a broken/absent tool reports
ok=False with a detail string, never an uncaught exception)."""
import argparse
import json
import os
import subprocess
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import core_md                 # noqa: E402
import engine_adapter          # noqa: E402
import engine_dispatch         # noqa: E402
import engine_pref            # noqa: E402
import liveness_cache          # noqa: E402
import model_registry          # noqa: E402
import model_tier_overrides    # noqa: E402

DEFAULT_GH_ARGV = ("gh", "auth", "status")

PROBE_ASK = "Reply with the single word READY and nothing else.\n"


def probe_prompt():
    """The hardened probe prompt: the SAME anti-hijack preamble a real review seat carries."""
    return engine_dispatch.ANTIHIJACK_PREAMBLE + PROBE_ASK


_PROBE_TIERS = ("reviewer-deep", "reviewer")


def _probe_effort(engine, model, effort):
    """An omitted codex effort resolves to the effort the registry matrix actually pairs with
    this model; cursor tolerates None and is left alone."""
    if effort is not None:
        return effort
    if engine != "codex":
        return None
    for tier in _PROBE_TIERS:
        cell = model_registry.matrix_config(tier, "codex")
        if cell is not None and cell[0] == model:
            return cell[1] or "high"
    return "high"


def cross_vendor_no_op_argv(engine):
    """The harmless authenticated no-op argv for `engine` (a DEFAULT — the caller may override
    it with an explicit `argv`)."""
    if engine == "codex":
        return ("codex", "exec", "--sandbox", "read-only", "-")
    if engine == "cursor":
        # The cursor probe must dispatch the project's configured cursor model (the SSOT default
        # in engine_adapter), not a hard-coded id — `cursor-small` was observed unavailable in a
        # live run, which would fail the probe for a project that never dispatches it.
        return ("cursor-agent", "--model", engine_adapter._CURSOR_MODEL, "-p", "--trust",
                "--mode", "plan")
    return (engine, "--version")


def probe_command(tool, argv, run=None, *, stdin_text=None):
    """Run `argv` via `run` (default: `subprocess.run`, capturing stdout+stderr as text with a
    120s timeout) and return `{"tool", "ok", "exit", "detail"}`. `ok` is exactly (exit code ==
    0). ANY exception from `run` (OSError, TimeoutExpired, anything at all) is caught here —
    ok=False, exit=None, detail=the exception string. Never raises."""
    if run is None:
        run = subprocess.run
    try:
        proc = run(list(argv), capture_output=True, text=True, timeout=120,
                   input=stdin_text or "")
        exit_code = getattr(proc, "returncode", None)
        stdout = getattr(proc, "stdout", "") or ""
        stderr = getattr(proc, "stderr", "") or ""
        return {"tool": tool, "ok": (exit_code == 0), "exit": exit_code,
                "detail": (stdout + stderr).strip()}
    except Exception as exc:
        return {"tool": tool, "ok": False, "exit": None, "detail": str(exc)}


def gh_auth_probe(run=None):
    """The `gh` sign-in check — one probe, no side effects."""
    return probe_command("gh auth", list(DEFAULT_GH_ARGV), run)


def cross_vendor_cli_probe(engine, run=None, argv=None):
    """One harmless authenticated no-op for the cross-vendor CLI `engine` will dispatch (the
    brief-check reviewer, or any external-engine implementer). `argv` overrides the default
    no-op from `cross_vendor_no_op_argv`. `engine` is coerced to str up front so a bad caller
    value (None, a non-str) can never TypeError the label/argv build before reaching the
    guarded `probe_command` — the fail-loud contract holds even for a malformed argument."""
    engine = str(engine)
    argv = list(argv or cross_vendor_no_op_argv(engine))
    stdin_text = probe_prompt() if engine in ("codex", "cursor") else None
    return probe_command("cross-vendor-cli:" + engine, argv, run, stdin_text=stdin_text)


def browser_probe_result(ok, detail=""):
    """Wrap the orchestrator's host-tool browser live-exercise (connect -> navigate ->
    snapshot) outcome in the same probe shape the other probes use, so it folds into
    `aggregate` alongside them. This lib never performs the browser action itself."""
    return {"tool": "browser", "ok": bool(ok), "detail": detail}


def aggregate(results):
    """The FAIL-LOUD go/no-go over a list of probe dicts. Each result may carry `required`
    (default True) and `applicable` (default True). A probe that is applicable AND required
    AND not ok is BLOCKING; `go` is True iff there are no blocking probes. A non-applicable
    probe is listed in `na` and never blocks, regardless of its `ok`/`required` value.

    FAIL-LOUD on the malformed/empty cases too — you cannot "go" on evidence you cannot read:
    - `results` empty (no probes ran at all) -> go=False, blocking=["<no-probes>"].
    - a record that is not a dict, or a dict missing `tool` or missing `ok`, is itself a BLOCKING
      failure (its index is recorded in `blocking`) — it is never silently skipped/ignored.
    Well-formed records keep exactly today's applicable/required/na semantics. Pure."""
    results = list(results or [])
    if not results:
        return {"go": False, "blocking": ["<no-probes>"], "checked": [], "na": []}
    go = True
    blocking = []
    checked = []
    na = []
    for i, r in enumerate(results):
        if not isinstance(r, dict) or "tool" not in r or "ok" not in r:
            go = False
            blocking.append("<malformed:%d>" % i)
            continue
        tool = r.get("tool")
        if not r.get("applicable", True):
            na.append(tool)
            continue
        checked.append(tool)
        if r.get("required", True) and not r.get("ok", False):
            go = False
            blocking.append(tool)
    return {"go": go, "blocking": blocking, "checked": checked, "na": na}


def _dispatch_calibration_read_error_marker(reason, detail):
    return [{"role": "*", "engine": None, "model": None,
             "readError": core_md.gate_refusal_line(
                 core_md.gate_refusal(reason, detail))}]


def _dispatch_calibration_read_error_marker_from_line(read_error_line):
    return [{"role": "*", "engine": None, "model": None, "readError": read_error_line}]


def _eval_failed_line(exc):
    return core_md.gate_refusal_line(
        core_md.gate_refusal(
            core_md.GATE_REASON_EVALUATION_FAILED,
            core_md.gate_refusal_detail(exc)))


# Single home for the CLI-visible `configRead` field set; `skills/configure/reference/preflight.md`
# §B restates it under a drift guard.
CONFIG_READ_FIELDS = ("status", "reason", "readError")


def config_read_payload(snapshot):
    """The CLI-visible `configRead` projection of a `readout_config` snapshot."""
    return {field: snapshot[field] for field in CONFIG_READ_FIELDS}


def readout_config(cwd=None, root=None):
    """Single snapshot of the core.md engine-preference read for this module's CLI readouts.

    Returns ``{"prefs", "status", "reason", "readError"}`` — one snapshot of the project's
    core.md read only. Model tiers are read separately by each consumer and are not part of
    this snapshot. Callers thread this snapshot to every consumer in a single ``main()``
    invocation so two readouts of the same run can never disagree about whether core.md was
    readable.

    This is the one door for readouts **in this module** (`run`, ``compose-liveness``). Other
    snippets (e.g. ``skills/configure/reference/preflight.md`` §B and ``review-code``) still read
    prefs through ``core_md.read()`` — a known gap outside this module. Never raises."""
    cwd = cwd or os.getcwd()
    try:
        cfg = core_md.engine_preferences_for_gate(cwd=cwd, root=root)
        if core_md.gate_config_is_absent(cfg):
            return {
                "prefs": {},
                "status": core_md.CONFIG_ABSENT,
                "reason": None,
                "readError": None,
            }
        elif not core_md.gate_config_is_refusal(cfg):
            prefs = core_md.gate_config_usable_prefs(cfg)
            return {
                "prefs": prefs,
                "status": core_md.CONFIG_OK,
                "reason": None,
                "readError": None,
            }
        else:
            refusal = core_md.gate_config_refusal(cfg)
            read_error = core_md.gate_refusal_line(refusal)
            return {
                "prefs": {},
                "status": cfg.status,
                "reason": refusal["reason"],
                "readError": read_error,
            }
    except Exception as exc:
        return {
            "prefs": {},
            "status": core_md.CONFIG_UNREADABLE,
            "reason": core_md.GATE_REASON_EVALUATION_FAILED,
            "readError": _eval_failed_line(exc),
        }


def dispatch_calibration(cwd=None, root=None, prefs=None, tiers=None, snapshot=None):
    """The OBSERVABILITY readout: the effective engine + model per v2 dispatch role, for the
    build brief + PR provenance. `prefs`/`tiers` are a unit-test seam (no disk); when either is
    omitted this reads the real project calibration via ``core_md.engine_preferences_for_gate``
    (absent/ok/unreadable). On ``CONFIG_OK`` the RAW ``enginePreferences`` from the accessor are
    used (NOT ``engine_pref.load_engine_prefs``'s normalized output: an absent ``briefCheck`` must
    stay ABSENT so ``resolve_engine`` applies the codex default, whereas the normalized 'claude'
    would suppress it). On ``CONFIG_UNREADABLE`` a single marker row carries ``readError`` instead
    of defaulted rows. Model tiers are read here, not supplied by the snapshot; a snapshot's
    ``readError`` takes precedence over any explicitly passed ``prefs``. Never raises — any read
    failure returns that marker, not an empty list."""
    try:
        if snapshot is not None and snapshot.get("readError") is not None:
            return _dispatch_calibration_read_error_marker_from_line(snapshot["readError"])
        if prefs is None:
            if snapshot is not None:
                prefs = snapshot.get("prefs")
                prefs = prefs if isinstance(prefs, dict) else {}
            else:
                cfg = core_md.engine_preferences_for_gate(cwd=cwd, root=root)
                refusal = core_md.gate_config_refusal(cfg)
                if refusal is not None:
                    return _dispatch_calibration_read_error_marker(
                        refusal["reason"], refusal["detail"])
                prefs = core_md.gate_config_usable_prefs(cfg)
                prefs = prefs if isinstance(prefs, dict) else {}
        if tiers is None:
            tiers = model_tier_overrides.effective_tiers(
                model_tier_overrides.resolve_profile_path(cwd, root))
        return engine_pref.dispatch_calibration_rows(prefs, tiers)
    except Exception as exc:
        return _dispatch_calibration_read_error_marker(
            core_md.GATE_REASON_EVALUATION_FAILED, core_md.gate_refusal_detail(exc))


def _dispatch_selftest_config(cwd=None, root=None, snapshot=None):
    """prefs/tiers bundle for dispatch_selftest leg 5.

    No return path exists that neither carries a ``read_error`` nor completed a tier read."""
    cwd = cwd or os.getcwd()
    try:
        if snapshot is not None:
            read_error = snapshot.get("readError")
            prefs = snapshot.get("prefs")
        else:
            cfg = core_md.engine_preferences_for_gate(cwd=cwd, root=root)
            refusal = core_md.gate_config_refusal(cfg)
            read_error = core_md.gate_refusal_line(refusal) if refusal is not None else None
            prefs = {} if core_md.gate_config_is_absent(cfg) else cfg.prefs
        if read_error is not None:
            return {"prefs": {}, "tiers": {}, "read_error": read_error}
        prefs = prefs if isinstance(prefs, dict) else {}
        tiers = model_tier_overrides.effective_tiers(
            model_tier_overrides.resolve_profile_path(cwd, root))
        return {"prefs": prefs, "tiers": tiers}
    except Exception as exc:
        return {
            "prefs": {},
            "tiers": {},
            "read_error": core_md.gate_refusal_line(
                core_md.gate_refusal(
                    core_md.GATE_REASON_EVALUATION_FAILED, core_md.gate_refusal_detail(exc))),
        }


_BROWSER_NOTE = ("browser live-exercise is a host action — run it per reference/preflight.md "
                  "and fold the result in with browser_probe_result()")


def model_no_op_argv(engine, model, effort=None):
    """Per-model harmless no-op argv for composition preflight. Returns None when the model is
    unknown/unroutable (caller marks unavailable — never calls run)."""
    if engine in ("codex", "cursor"):
        effort = _probe_effort(engine, model, effort)
        result = engine_adapter.build_argv_result(
            engine, "review", effort, {"engine_model": model})
        if result.get("reason") or not result.get("argv"):
            return None
        return tuple(result["argv"])
    return (engine, "--version")


def needed_configs_for(tiers, vendors):
    """Distinct matrix configs per external vendor for the given tiers. Skips claude (always live)."""
    out = {}
    for vendor in vendors:
        if vendor == "claude":
            continue
        configs = []
        seen = set()
        for tier in tiers:
            cell = model_registry.matrix_config(tier, vendor)
            if cell is None:
                continue
            if cell not in seen:
                seen.add(cell)
                configs.append(cell)
        out[vendor] = configs
    return out


def composition_liveness(needed_configs, run=None):
    """Per-vendor composition liveness: auth is all-or-nothing per vendor, layered with per-model
    adequacy. Returns {vendor: {"live": bool, "models": {model: {"ok", "detail"}}}}."""
    if not isinstance(needed_configs, dict):
        return {}
    result = {}
    for vendor, configs in needed_configs.items():
        if vendor == "claude":
            result[vendor] = {"live": True, "models": {}}
            continue
        models = {}
        for model, effort in configs:
            argv = model_no_op_argv(vendor, model, effort)
            if argv is None:
                models[model] = {"ok": False, "detail": "unknown/unroutable model"}
            else:
                r = probe_command("composition:%s:%s" % (vendor, model), argv, run,
                                  stdin_text=probe_prompt())
                r_ok = r["ok"]
                r_detail = r["detail"]
                entry = {"ok": r_ok, "detail": r_detail}
                existing = models.get(model)
                if existing is not None and not existing["ok"]:
                    entry = existing
                elif existing is not None and not r_ok:
                    entry = {"ok": False, "detail": r_detail}
                elif existing is not None:
                    entry = existing
                models[model] = entry
        live = bool(configs) and all(m["ok"] for m in models.values())
        result[vendor] = {"live": live, "models": models}
    return result


def live_vendors_for_composition(
    configured_vendors,
    tiers=("reviewer-deep", "reviewer"),
    run=None,
    *,
    needed_override=None,
    probe_mode="probe",
    cache_path=None,
    now=None,
):
    """Derive live vendors for seat_map.build from composition preflight. Claude is always live."""
    needed = needed_override if needed_override is not None else needed_configs_for(tiers, configured_vendors)
    notes = []

    if cache_path is not None and now is not None:
        rec = liveness_cache.read(cache_path, now=now)
        if rec is not None and liveness_cache.covers(rec.get("needed", {}), needed):
            live, dead_notes = liveness_cache.live_vendors_from(rec["liveness"], needed)
            notes.append({
                "constraint": "preflight-cache",
                "reason": "reused liveness receipt (age %ds)" % int(now - rec["probedAt"]),
            })
            notes.extend(dead_notes)
            return (live, rec["liveness"], notes)

    if probe_mode == "cache-only":
        notes.append({
            "constraint": "preflight-cache-only",
            "reason": (
                "receipt-only path (e.g. --post): no fresh liveness cache within TTL — "
                "vendors not probed; panel falls open to Claude"
            ),
        })
        return (["claude"], {"claude": {"live": True, "models": {}}}, notes)

    liveness = composition_liveness({**needed, "claude": []}, run)
    if cache_path is not None and now is not None:
        wrote = liveness_cache.write(liveness, needed, path=cache_path, now=now)
        if not wrote:
            notes.append({
                "constraint": "preflight-cache-write-failed",
                "reason": (
                    "liveness receipt could not be written — every compose will re-probe "
                    "until the store is writable"
                ),
            })
    live = sorted(v for v, info in liveness.items() if info.get("live"))
    return (live, liveness, notes)


def configured_cross_vendor_engines(prefs):
    """The distinct NON-claude engines this project actually dispatches through, across the v2
    dispatch roles (review, build, brief-check, pilot). Empty when the project is all-Claude (the
    cross-vendor CLI probe is then N/A). Pure; tolerant of non-dict prefs."""
    prefs = prefs if isinstance(prefs, dict) else {}
    engines = {engine_pref.resolve_engine(rk, prefs) for rk in ("review", "build", "brief-check", "pilot")}
    return sorted(e for e in engines if e in ("codex", "cursor"))


def main(argv):
    ap = argparse.ArgumentParser(prog="preflight_probe")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run the subprocess-able preflight probes")
    r.add_argument("--cwd", default=".")
    r.add_argument("--engine", default=None,
                    help="probe exactly this engine (back-compat); omit to derive every "
                         "configured non-Claude engine from the project's enginePreferences")
    cl = sub.add_parser("compose-liveness", help="probe composition liveness and cache receipt")
    cl.add_argument("--cwd", default=".")
    cl.add_argument("--pins", default=None, help="JSON dict of seat pins for pin-reachability")
    args = ap.parse_args(argv[1:])

    if args.cmd == "compose-liveness":
        import time

        snap = readout_config(args.cwd)
        prefs = snap["prefs"]
        configured = configured_cross_vendor_engines(prefs)
        needed_override = None
        if args.pins:
            import seat_map  # noqa: E402 — lazy: breaks import cycle with seat_map

            try:
                pins = json.loads(args.pins)
            except json.JSONDecodeError as e:
                print(str(e), file=sys.stderr)
                return 1
            needed_override = seat_map.reachable_configs(configured, pins)
        now = time.time()
        cache_path = liveness_cache.receipt_path(args.cwd)
        live, liveness, notes = live_vendors_for_composition(
            configured,
            needed_override=needed_override,
            probe_mode="probe",
            cache_path=cache_path,
            now=now,
        )
        if snap["readError"] is not None:
            notes.append({
                "constraint": snap["reason"],
                "reason": snap["readError"],
            })
        sys.stdout.write(json.dumps({
            "live": live,
            "cachePath": cache_path,
            "crossVendorEngines": configured,
            "notes": notes,
            "configRead": config_read_payload(snap),
        }) + "\n")
        return 0

    if args.cmd == "run":
        import dispatch_selftest  # noqa: E402 — lazy: breaks seat_map → preflight_probe → dispatch_selftest → seat_map

        snap = readout_config(args.cwd)
        probes = [
            gh_auth_probe(),
            dispatch_selftest.probe_result(
                config=_dispatch_selftest_config(args.cwd, snapshot=snap)),
        ]
        if args.engine:
            cross_vendor_engines = [args.engine]
        else:
            cross_vendor_engines = configured_cross_vendor_engines(snap["prefs"])
        for engine in cross_vendor_engines:
            probes.append(cross_vendor_cli_probe(engine))
        out = {
            "probes": probes,
            "dispatchCalibration": dispatch_calibration(cwd=args.cwd, snapshot=snap),
            "aggregate": aggregate(probes),
            "browserNote": _BROWSER_NOTE,
            "crossVendorEngines": cross_vendor_engines,
            "configRead": config_read_payload(snap),
        }
        sys.stdout.write(json.dumps(out) + "\n")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
