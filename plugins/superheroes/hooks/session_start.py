#!/usr/bin/env python3
"""SessionStart hook (best-effort, non-fatal). Two responsibilities, both delivered
via `additionalContext`:

1. **Bootstrap (ALWAYS — all four sources `startup|resume|clear|compact`).** Inject
   the project-context layer a plain chat start auto-loads but a slash-command spawn
   drops: project/user CLAUDE.md, the env block, the MEMORY.md head, plus the
   resolved ABSOLUTE plugin + host-tool-map roots (so a skill's
   `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<host>-tools.md` Read lands on the
   real file). Assembled by `session_context` — best-effort, never raises. This runs
   FIRST and UNCONDITIONALLY; it must NOT be gated behind the work-item lookup, or it
   would be suppressed on exactly the compacted-discovery path it exists for.

2. **Resume brief (ADDITIVE — compact WITH a work-item only).** The workhorse
   post-compaction reconcile/re-arm instruction, appended into the SAME
   `additionalContext` only when `source=='compact'` and a current work-item exists.
   The work-item lookup gates ONLY this brief, never the bootstrap.

No env export (CLAUDE_ENV_FILE is not provisioned on SessionStart — spike-confirmed).
Always exits 0.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))

_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SOURCES = {"startup", "resume", "clear", "compact"}


def _bootstrap(cwd, transcript_path, host):
    """The always-on project-context block (or '' on any failure)."""
    try:
        import session_context
        block = session_context.assemble(cwd, transcript_path, _PLUGIN_ROOT, host)
        return block if (block and block.strip()) else ""
    except Exception as exc:
        sys.stderr.write("superheroes session_start: bootstrap skipped (%s)\n" % type(exc).__name__)
        return ""


def _resume_brief(cwd, source):
    """The additive workhorse resume-brief — only on compact WITH a work-item."""
    if source != "compact":
        return ""
    try:
        import control_plane
        wi = control_plane.get_current(cwd)
        if not wi:
            return ""
        brief = control_plane.paths(cwd, wi)["resume_brief"]
        return ("Workhorse resume: this session was compacted mid-run on work-item "
                "'%s'. Before continuing, RECONCILE against reality and RE-ARM the step 0 "
                "enforcer floor self-check (bounded retry → parked-GATE). Resume brief: %s"
                % (wi, brief))
    except Exception as exc:
        sys.stderr.write("superheroes session_start: resume-brief skipped (%s)\n" % type(exc).__name__)
        return ""


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

    blocks = []
    boot = _bootstrap(cwd, transcript_path, args.host)   # always-on, gated by nothing
    if boot:
        blocks.append(boot)
    brief = _resume_brief(cwd, source)                   # additive, compact-with-work-item only
    if brief:
        blocks.append(brief)

    if blocks:
        sys.stdout.write(json.dumps({
            "hookSpecificOutput": {"hookEventName": "SessionStart",
                                   "additionalContext": "\n\n".join(blocks)}}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
