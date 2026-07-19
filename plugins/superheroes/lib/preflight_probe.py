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
import engine_pref            # noqa: E402
import model_tier_overrides    # noqa: E402

DEFAULT_GH_ARGV = ("gh", "auth", "status")


def cross_vendor_no_op_argv(engine):
    """The harmless authenticated no-op argv for `engine` (a DEFAULT — the caller may override
    it with an explicit `argv`)."""
    if engine == "codex":
        return ("codex", "exec", "--sandbox", "read-only", "reply with the single word READY")
    if engine == "cursor":
        # The cursor probe must dispatch the project's configured cursor model (the SSOT default
        # in engine_adapter), not a hard-coded id — `cursor-small` was observed unavailable in a
        # live run, which would fail the probe for a project that never dispatches it.
        return ("cursor-agent", "--model", engine_adapter._CURSOR_MODEL, "-p", "--trust", "reply READY")
    return (engine, "--version")


def probe_command(tool, argv, run=None):
    """Run `argv` via `run` (default: `subprocess.run`, capturing stdout+stderr as text with a
    120s timeout) and return `{"tool", "ok", "exit", "detail"}`. `ok` is exactly (exit code ==
    0). ANY exception from `run` (OSError, TimeoutExpired, anything at all) is caught here —
    ok=False, exit=None, detail=the exception string. Never raises."""
    if run is None:
        run = subprocess.run
    try:
        proc = run(list(argv), capture_output=True, text=True, timeout=120)
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
    return probe_command("cross-vendor-cli:" + engine, list(argv or cross_vendor_no_op_argv(engine)), run)


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


def dispatch_calibration(cwd=None, root=None, prefs=None, tiers=None):
    """The OBSERVABILITY readout: the effective engine + model per v2 dispatch role, for the
    build brief + PR provenance. `prefs`/`tiers` are a unit-test seam (no disk); when either is
    omitted this reads the real project calibration — the RAW enginePreferences (via `core_md.read`,
    NOT `engine_pref.load_engine_prefs`'s normalized output: an absent `briefCheck` must stay ABSENT
    so `resolve_engine` applies the codex default, whereas the normalized 'claude' would suppress it)
    and `model_tier_overrides.effective_tiers`. Never raises — any read failure falls open to an
    empty readout, exactly like the resolvers it calls."""
    try:
        if prefs is None:
            raw = core_md.read(cwd, root)
            prefs = (raw or {}).get("enginePreferences")
            prefs = prefs if isinstance(prefs, dict) else {}
        if tiers is None:
            tiers = model_tier_overrides.effective_tiers(
                model_tier_overrides.resolve_profile_path(cwd, root))
        return engine_pref.dispatch_calibration_rows(prefs, tiers)
    except Exception:
        return []


_BROWSER_NOTE = ("browser live-exercise is a host action — run it per reference/preflight.md "
                  "and fold the result in with browser_probe_result()")


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
    args = ap.parse_args(argv[1:])

    if args.cmd == "run":
        probes = [gh_auth_probe()]
        if args.engine:
            cross_vendor_engines = [args.engine]
        else:
            raw = core_md.read(args.cwd)
            prefs = (raw or {}).get("enginePreferences")
            prefs = prefs if isinstance(prefs, dict) else {}
            cross_vendor_engines = configured_cross_vendor_engines(prefs)
        for engine in cross_vendor_engines:
            probes.append(cross_vendor_cli_probe(engine))
        out = {
            "probes": probes,
            "dispatchCalibration": dispatch_calibration(cwd=args.cwd),
            "aggregate": aggregate(probes),
            "browserNote": _BROWSER_NOTE,
            "crossVendorEngines": cross_vendor_engines,
        }
        sys.stdout.write(json.dumps(out) + "\n")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
