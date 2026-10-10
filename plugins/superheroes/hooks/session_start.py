#!/usr/bin/env python3
"""SessionStart hook (best-effort, non-fatal). Two responsibilities, both delivered via
`additionalContext`. The second is cloud-only: place the reviewer pass (`cloud_pass.place`) so
review seats can run, and append a short `### Reviewer pass` section saying whether it is in
place. The first:

**Bootstrap (ALWAYS — all four sources `startup|resume|clear|compact`).** Inject
the two records only this bootstrap uniquely supplies — the resolved ABSOLUTE
plugin + host-tool-map roots (so a skill's
`${CLAUDE_PLUGIN_ROOT}/hosts/<host>-tools.md` Read lands on the
real file) and the distilled covenant — plus nothing the harness already loads.
Current Claude Code natively supplies project/user CLAUDE.md, the env block, and
the MEMORY.md head on all spawn paths (probe-verified #627 F1, Claude Code
2.1.219). Assembled by `session_context` — best-effort, never raises. This runs
FIRST and UNCONDITIONALLY; it must NOT be gated behind a work-item lookup, or it
would be suppressed on exactly the compacted-discovery path it exists for.

When `CLAUDE_ENV_FILE` is set, appends `SUPERHEROES_HOST_MODEL` from the payload
(best-effort, never raises). Always exits 0.
"""
import argparse
import json
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))

_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SOURCES = {"startup", "resume", "clear", "compact"}
_HOST_MODEL_RE = re.compile(r"^[A-Za-z0-9._:/\[\]-]{1,128}$")


def _host_model(payload):
    """Shape-checked host model from the SessionStart payload, or empty."""
    model = payload.get("model")
    if isinstance(model, str):
        value = model.strip()
    elif isinstance(model, dict):
        mid = model.get("id")
        value = mid.strip() if isinstance(mid, str) else ""
    else:
        value = ""
    if not _HOST_MODEL_RE.match(value):
        return ""
    return value


def _write_host_model_env(value):
    env_file = os.environ.get("CLAUDE_ENV_FILE")
    if not env_file:
        return
    try:
        with open(env_file, "a", encoding="utf-8") as fh:
            fh.write("export SUPERHEROES_HOST_MODEL=%s\n" % shlex.quote(value))
    except OSError as exc:
        sys.stderr.write(
            "superheroes session_start: could not write host model env (%s)\n"
            % type(exc).__name__)


def _scrub_pass_env(result):
    """After any placement outcome, drop the pass from later shells; export its SHA-256 marker only
    when placed. Best-effort, never raises."""
    try:
        import cloud_pass
        env_file = os.environ.get("CLAUDE_ENV_FILE")
        marker = cloud_pass.pass_marker() if result.get("action") == "placed" else None
        if not env_file or result.get("reason") == "not-a-cloud-session":
            return
        with open(env_file, "a", encoding="utf-8") as fh:
            fh.write("unset %s\n" % cloud_pass.PASS_ENV)
            if marker:
                fh.write("export %s=%s\n" % (cloud_pass.PASS_MARKER_ENV, shlex.quote(marker)))
    except Exception as exc:
        sys.stderr.write("superheroes session_start: could not scrub pass env (%s)\n"
                         % type(exc).__name__)


def _append_host_model_section(boot, value):
    if not boot:
        return boot
    if value:
        line = "Host model (read from the session-start hook payload): %s" % value
    else:
        line = (
            "Host model: unknown — the session-start hook payload carried no readable model; "
            "seat composition falls back to the claude host's family for the families it cannot "
            "read and discloses it on the seat map as host-model-unknown."
        )
    return boot + "\n\n### Host model\n" + line


def _append_reviewer_pass_section(boot, result, raised):
    """Name the reviewer pass's state in the bootstrap — only in a cloud session. Never carries
    the pass itself, only the reason token (or the exception's type name) and the lapse date."""
    if not boot:
        return boot
    if raised is not None:
        # The call raised, so there is no result to read; CLAUDE_CODE_REMOTE is cloud_pass.CLOUD_ENV.
        if os.environ.get("CLAUDE_CODE_REMOTE") != "true":
            return boot
        reason = raised
    elif result.get("reason") == "not-a-cloud-session":
        return boot
    elif result.get("action") == "placed":
        lapses = result.get("passLapses")
        line = ("The reviewer pass is in place; it lapses %s." % lapses if lapses
                else "The reviewer pass is in place; its lapse date could not be read.")
        return boot + "\n\n### Reviewer pass\n" + line
    elif result.get("action") == "skipped":
        line = ("No reviewer pass is set in this cloud environment, so review seats cannot run "
                "here until one is pasted into the environment's variables.")
        return boot + "\n\n### Reviewer pass\n" + line
    else:
        reason = result.get("reason")
    line = ("The reviewer pass could not be placed (%s), so review seats cannot run here until a "
            "fresh pass is pasted into the environment's variables." % reason)
    return boot + "\n\n### Reviewer pass\n" + line


def _bootstrap(cwd, transcript_path, host, source=None):
    """The always-on project-context block. On a TOTAL failure (assemble unimportable/raised),
    return a minimal in-context breadcrumb (B6, #315) rather than '' — so a fully-failed bootstrap
    still leaves the running agent something to read back, not silence (stderr is invisible to it)."""
    try:
        import session_context
        block = session_context.assemble(
            cwd, transcript_path, _PLUGIN_ROOT, host, source=source)
        return block if (block and block.strip()) else ""
    except Exception as exc:
        sys.stderr.write("superheroes session_start: bootstrap skipped (%s)\n" % type(exc).__name__)
        return ("## Superheroes session bootstrap\n\n### Bootstrap diagnostics\n"
                "Session bootstrap failed to assemble (%s) — project-context layer not injected."
                % type(exc).__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="claude")   # only hooks.json (Claude) wires this hook
    args, _ = parser.parse_known_args()

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    if not isinstance(payload, dict):
        return 0
    source = payload.get("source")
    if source not in _SOURCES:
        return 0
    cwd = payload.get("cwd") or os.getcwd()
    transcript_path = payload.get("transcript_path")

    host_model = _host_model(payload)
    _write_host_model_env(host_model)

    pass_result, pass_raised = None, None
    try:
        import cloud_pass
        pass_result = cloud_pass.place()
        _scrub_pass_env(pass_result)
    except Exception as exc:
        pass_raised = type(exc).__name__
        _scrub_pass_env({})

    boot = _bootstrap(cwd, transcript_path, args.host, source=source)   # always-on, gated by nothing
    boot = _append_host_model_section(boot, host_model)
    boot = _append_reviewer_pass_section(boot, pass_result, pass_raised)
    if boot:
        sys.stdout.write(json.dumps({
            "hookSpecificOutput": {"hookEventName": "SessionStart",
                                   "additionalContext": boot}}) + "\n")
    try:
        import cache_markers
        swept = cache_markers.sweep_stale(_PLUGIN_ROOT)
        if swept:
            sys.stderr.write(
                "superheroes: swept %d stale .in_use marker(s)\n" % swept)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
