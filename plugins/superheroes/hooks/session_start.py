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

When `CLAUDE_ENV_FILE` is set, appends three exports on every start (best-effort, never raises):
`SUPERHEROES_HOST_MODEL` from the payload (empty when it names none), and the session transcript's
path and its byte size at this start (`SUPERHEROES_SESSION_TRANSCRIPT`,
`SUPERHEROES_SESSION_TRANSCRIPT_FROM`), from which seat composition reads the model when the start
event named none (#2110). The hook never reads the transcript for a model itself. Always exits 0.

**Start copy record (cloud only, #2612).** Run as a script in a cloud session
(`CLAUDE_CODE_REMOTE=true`), the hook installs an audit hook before its first plugin import. It notes
each plugin file it opens, the moment it opens it, with the real folder the plugin link points to
then, and ends by appending one `SUPERHEROES_START_COPY` export to `CLAUDE_ENV_FILE`: a JSON record
bound to the payload's session id. The cloud check reads it back, so it can fail a start part that
was loaded from an older plugin copy than the release it expects. The hook's own part is credited only
when its running code equals the file at the folder the link pointed to at the start. It opens nothing
outside `cloud_setup_text.START_HOOK_READS`, and it never raises.
"""
import argparse
import json
import os
import shlex
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))

# The plugin folder as the host's link names it; `_PLUGIN_ROOT` below is the same expression.
_LINK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OWN_PART = "hooks/session_start.py"
_PYC_DIR = "__pycache__"


def _plugin_part(path, link_root, roots, current):
    """(plugin-relative part, the real folder it was opened from) for an opened `path`, or None
    when the path is outside the plugin. The part comes from the path under the link, else from its
    real path under a folder already seen or under the current real folder."""
    abspath = os.path.abspath(path)
    link_prefix = link_root.rstrip(os.sep) + os.sep
    if abspath.startswith(link_prefix):
        rel, root = abspath[len(link_prefix):], current
    else:
        real = os.path.realpath(path)
        rel, root = None, None
        for candidate in list(roots) + [current]:
            prefix = candidate.rstrip(os.sep) + os.sep
            if real.startswith(prefix):
                rel, root = real[len(prefix):], candidate
                break
        if rel is None:
            return None
    pieces = [piece for piece in rel.split(os.sep) if piece]
    if not pieces or ".." in pieces:
        return None
    if len(pieces) >= 2 and pieces[-2] == _PYC_DIR and pieces[-1].endswith(".pyc"):
        pieces = pieces[:-2] + [pieces[-1].split(".")[0] + ".py"]
    return "/".join(pieces), root


def _start_recorder(link_root):
    """(audit function, state). `state["roots"]` lists the real folders the plugin link resolved to
    when a file was opened, and `state["parts"]` maps each plugin-relative part (forward slashes) to
    the set of indexes into `roots` it was opened from. The audit function notes only `open` events
    on a path (never a file descriptor), maps a bytecode file to its source, skips directories and
    anything outside the plugin, stops once `state["stopped"]` is set, and never raises: an audit
    hook that raises aborts the open it watches."""
    state = {"roots": [], "parts": {}, "stopped": False}

    def audit(event, args):
        try:
            if state["stopped"] or event != "open":
                return
            target = args[0]
            if not isinstance(target, (str, bytes, os.PathLike)):
                return
            path = os.fsdecode(target)
            current = os.path.realpath(link_root)
            found = _plugin_part(path, link_root, state["roots"], current)
            if found is None or os.path.isdir(path):
                return
            part, root = found
            if root not in state["roots"]:
                state["roots"].append(root)
            state["parts"].setdefault(part, set()).add(state["roots"].index(root))
        except Exception:
            pass

    return audit, state


def _own_copy_matches(code, root):
    """True when `code` equals the hook file at `<root>/hooks/session_start.py`, compiled with no
    inherited flags. A code object does not compare its file name, so a copy of the same bytes under
    another folder is equal. Any failure is False."""
    try:
        path = os.path.join(root, "hooks", "session_start.py")
        with open(path, "rb") as fh:
            source = fh.read()
        return compile(source, path, "exec", dont_inherit=True) == code
    except Exception:
        return False


_START_ROOT = None
_OWN_CODE = None
_RECORDER = None
if __name__ == "__main__" and os.environ.get("CLAUDE_CODE_REMOTE") == "true":
    _START_ROOT = os.path.realpath(_LINK_ROOT)
    _OWN_CODE = sys._getframe(0).f_code
    _audit, _RECORDER = _start_recorder(_LINK_ROOT)
    sys.addaudithook(_audit)

import host_model  # noqa: E402

_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SOURCES = {"startup", "resume", "clear", "compact"}


def _write_start_copy(session_id):
    """Append the start copy record to `CLAUDE_ENV_FILE`. Best-effort, never raises. It acts only
    when the recorder is installed, the env file is set and the session id is a non-empty string.
    Recording stops first, so the check's own read of the hook file credits nothing; the hook's own
    part is then set from the comparison of its running code alone."""
    try:
        state = _RECORDER
        env_file = os.environ.get("CLAUDE_ENV_FILE")
        if state is None or not env_file or not isinstance(session_id, str) or not session_id:
            return
        state["stopped"] = True
        import cloud_pass
        if _own_copy_matches(_OWN_CODE, _START_ROOT):
            if _START_ROOT not in state["roots"]:
                state["roots"].append(_START_ROOT)
            state["parts"][_OWN_PART] = {state["roots"].index(_START_ROOT)}
        else:
            state["parts"].pop(_OWN_PART, None)
        record = {"schema": cloud_pass.START_COPY_SCHEMA, "session": session_id,
                  "roots": list(state["roots"]),
                  "parts": {part: sorted(indexes) for part, indexes in state["parts"].items()}}
        line = json.dumps(record, sort_keys=True, separators=(",", ":"))
        with open(env_file, "a", encoding="utf-8") as fh:
            fh.write("export %s=%s\n" % (cloud_pass.START_COPY_ENV, shlex.quote(line)))
    except Exception:
        pass


def _write_host_model_env(value, transcript, transcript_from):
    env_file = os.environ.get("CLAUDE_ENV_FILE")
    if not env_file:
        return
    try:
        with open(env_file, "a", encoding="utf-8") as fh:
            for name, val in ((host_model.HOST_MODEL_ENV, value),
                              (host_model.TRANSCRIPT_ENV, transcript),
                              (host_model.TRANSCRIPT_FROM_ENV, transcript_from)):
                fh.write("export %s=%s\n" % (name, shlex.quote(val)))
    except (OSError, UnicodeEncodeError) as exc:
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
            return False
        with open(env_file, "a", encoding="utf-8") as fh:
            fh.write("unset %s\n" % cloud_pass.PASS_ENV)
            if marker:
                fh.write("export %s=%s\n" % (cloud_pass.PASS_MARKER_ENV, shlex.quote(marker)))
        return True
    except Exception as exc:
        sys.stderr.write("superheroes session_start: could not scrub pass env (%s)\n"
                         % type(exc).__name__)
        return False


def _append_host_model_section(boot, value):
    if not boot:
        return boot
    if value:
        line = "Host model (read from the session-start hook payload): %s" % value
    else:
        line = (
            "Host model: unknown — the session-start hook payload carried no readable model; "
            "seat composition reads the model from this session's own transcript (turns since "
            "this start) and discloses it on the seat map as host-model-unknown only when that "
            "names none either, falling back to the claude host's family for the families it "
            "cannot read."
        )
    return boot + "\n\n### Host model\n" + line


def _placed_by_parent(result):
    """True when this session holds only the marker and the file at the sign-in path hashes to it:
    a parent session placed the pass and scrubbed the variable. Never raises."""
    if result.get("reason") != "no-pass-in-environment":
        return False
    try:
        import cloud_pass
        return cloud_pass.placed_matches_marker(os.environ)
    except Exception:
        return False


def _parent_placed_line():
    """The section line for a pass a parent session placed, from the placed file's own expiry."""
    import cloud_pass
    try:
        placed = cloud_pass.placed_pass_state(os.environ)
    except Exception:
        placed = {}
    state, lapses = placed.get("state"), placed.get("passLapses")
    if state == "valid":
        return "The reviewer pass is in place; it lapses %s." % lapses
    if state == "lapsed":
        return ("The reviewer pass in place has lapsed (%s), so review seats cannot run here "
                "until a fresh pass is pasted into the environment's variables." % lapses)
    return ("The reviewer pass could not be placed (pass-expiry-unreadable), so review seats "
            "cannot run here until a fresh pass is pasted into the environment's variables.")


def _append_reviewer_pass_section(boot, result, raised, scrubbed=True):
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
        if not scrubbed:
            line += " The pass is still visible to processes in this session (its variable stayed set)."
        return boot + "\n\n### Reviewer pass\n" + line
    elif result.get("action") == "skipped" and _placed_by_parent(result):
        return boot + "\n\n### Reviewer pass\n" + _parent_placed_line()
    elif result.get("action") == "skipped":
        line = ("No reviewer pass is set in this cloud environment, so review seats cannot run "
                "here until one is pasted into the environment's variables.")
        return boot + "\n\n### Reviewer pass\n" + line
    else:
        reason = result.get("reason")
    line = ("The reviewer pass could not be placed (%s), so review seats cannot run here until a "
            "fresh pass is pasted into the environment's variables." % reason)
    return boot + "\n\n### Reviewer pass\n" + line


def _bootstrap(cwd, transcript_path, host, source=None, session_id=None):
    """The always-on project-context block. On a TOTAL failure (assemble unimportable/raised),
    return a minimal in-context breadcrumb (B6, #315) rather than '' — so a fully-failed bootstrap
    still leaves the running agent something to read back, not silence (stderr is invisible to it)."""
    try:
        import session_context
        block = session_context.assemble(
            cwd, transcript_path, _PLUGIN_ROOT, host, source=source, session_id=session_id)
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

    model = host_model.from_payload(payload)
    session_transcript, session_transcript_from = host_model.transcript_from_payload(payload)
    _write_host_model_env(model, session_transcript, session_transcript_from)

    pass_result, pass_raised, scrubbed = None, None, True
    try:
        import cloud_pass
        pass_result = cloud_pass.place()
        scrubbed = _scrub_pass_env(pass_result)
    except Exception as exc:
        pass_raised = type(exc).__name__
        _scrub_pass_env({})

    boot = _bootstrap(cwd, transcript_path, args.host, source=source,
                      session_id=payload.get("session_id"))   # always-on, gated by nothing
    boot = _append_host_model_section(boot, model)
    boot = _append_reviewer_pass_section(boot, pass_result, pass_raised, scrubbed)
    if boot:
        sys.stdout.write(json.dumps({
            "hookSpecificOutput": {"hookEventName": "SessionStart",
                                   "additionalContext": boot}}) + "\n")
    try:
        import compaction_directive
        compaction_directive.reap(payload.get("session_id"), cwd=cwd)
    except Exception:
        pass
    try:
        import cache_markers
        swept = cache_markers.sweep_stale(_PLUGIN_ROOT)
        if swept:
            sys.stderr.write(
                "superheroes: swept %d stale .in_use marker(s)\n" % swept)
    except Exception:
        pass
    _write_start_copy(payload.get("session_id"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
