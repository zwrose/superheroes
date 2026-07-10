#!/usr/bin/env python3
"""The deterministic engine argv/parse/commit core (kept out of the model-driven JS layer so
it is unit-testable). Named engine_adapter (NOT engine_cli — that is test-pilot's). Every
external free-text surface is scrubbed at THIS trust boundary (parse_result). Flags verified
live 2026-07-01 against codex 0.141.0 (model gpt-5.5 — gpt-5.5-codex/gpt-5-codex are rejected
under ChatGPT-account auth) and cursor-agent 2026.06.26 (--model / -p / --trust; -m is gone)."""
import argparse
import json
import os
import subprocess
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import readout  # noqa: E402  (the band's single scrub seam; same-tree sibling)

# The SINGLE-SOURCED commit trailer. The committer (commit_result, Task 7) and the
# build_state_cli git-log parser both reference this so the convention cannot fork.
TASK_ID_TRAILER = "Task-Id"

# Explicit model per engine (Config-determinism NFR — never the developer's ambient default).
# codex: gpt-5.5 (there is NO gpt-5.5-codex variant; gpt-5-codex is rejected under ChatGPT-account
# auth). cursor: the current composer model id. Both verified live 2026-07-01.
_CODEX_MODEL = "gpt-5.5"
_CURSOR_MODEL = "composer-2.5-fast"

# Native model-tier short-name -> cursor model id — the OWNER POLICY map (ratified 2026-07-09).
# Cursor is the TOKEN-EFFICIENCY engine: its whole point is the highly token-efficient composer-2.5,
# so ALL work roles (build/fix/review/reviewer-deep) dispatch the pinned _CURSOR_MODEL composer
# default, and premium Claude models are NEVER routed through cursor by default. The ONE deliberate
# exception is plan authoring: `author-plan: fable` (model tier) + `planAuthor: cursor` (engine pref)
# dispatches Fable via cursor — hence `fable` is the map's ONLY entry (id verified live against
# `cursor-agent models` 2026-07-03). Every other tier (opus/sonnet/haiku, or any owner override)
# DELIBERATELY falls through build_argv's `.get(..., _CURSOR_MODEL)` to composer — that fall-through
# IS the policy, not a gap; do not "complete" this map with premium ids. EVERY cursor dispatch
# threads its role's resolved tier (#308) through this map, and display_model resolves through this
# SAME map (SSOT), so the preflight readout row shows the composer truth and can never disagree with
# the dispatched argv by construction (#308 / #162).
_CURSOR_MODEL_BY_TIER = {
    "fable": "claude-fable-5-thinking-xhigh",
}


def build_argv(engine, role_kind, effort, opts):
    """Return the argv list to dispatch `engine` for `role_kind` at `effort`. READ (review) →
    read-only sandbox; WRITE (build|fix|author-plan) → workspace-write. Always explicit
    model+effort. opts keys: cwd, schema_path, model (native tier short name — cursor maps it via
    _CURSOR_MODEL_BY_TIER; codex ignores it, staying on its pinned model). The PROMPT is NOT
    encoded here — codex reads it from stdin (trailing `-`) and cursor-agent reads it from stdin
    when given no positional prompt; the JS runner (Task 10) feeds the staged prompt file to the
    process stdin. Deterministic; fully unit-testable."""
    opts = opts or {}
    cwd = opts.get("cwd")
    schema_path = opts.get("schema_path")
    is_read = role_kind == "review"
    if engine == "codex":
        sandbox = "read-only" if is_read else "workspace-write"
        argv = ["codex", "exec", "--sandbox", sandbox,
                "-m", _CODEX_MODEL,
                "-c", "model_reasoning_effort=%s" % effort]
        if not is_read and cwd:
            argv += ["-C", cwd]           # confine writes to the managed worktree
        if is_read and schema_path:
            argv += ["--output-schema", schema_path]  # enforced structured review output
        # trailing `-`: read the prompt from stdin. The Task-10 JS runner redirects the staged
        # prompt file into stdin (`<argv> < promptPath`) — the prompt is ALWAYS fed here.
        argv += ["-"]
        return argv
    if engine == "cursor":
        # No positional prompt argument: cursor-agent reads the prompt from stdin, which the
        # Task-10 JS runner redirects from the staged prompt file (`<argv> < promptPath`).
        # cursor-agent 2026.06.26: model flag is --model (not -m); -p/--print is REQUIRED for a
        # headless run (without it it goes interactive and --output-format is a no-op); --trust
        # clears the workspace-trust gate that otherwise HANGS a headless run (needed for the
        # read/--mode-plan role — the write role's -f also trusts, but --trust covers both).
        model = _CURSOR_MODEL_BY_TIER.get(opts.get("model"), _CURSOR_MODEL)
        argv = ["cursor-agent", "--model", model, "-p", "--trust"]
        if is_read:
            argv += ["--mode", "plan"]     # read-only planning mode
        else:
            argv += ["-f"]                 # force / workspace-write
        argv += ["--output-format", "stream-json"]
        return argv
    # Unknown engine: return an empty argv; the JS caller treats an empty argv as unrunnable
    # → fall open to claude (never raises here).
    return []


def _last_top_level_json(stdout, want_type):
    """Return the LAST top-level JSON value of `want_type` (dict or list) in a (possibly
    line-delimited / streamed) blob, or None. Tries a whole-blob parse first, then a
    raw_decode scan that skips non-JSON stream noise a char at a time. Shared by
    _last_json_object (dict) and _last_json_array (list) so the scan logic lives once."""
    s = (stdout or "").strip()
    if not s:
        return None
    try:
        val = json.loads(s)
        if isinstance(val, want_type):
            return val
    except ValueError:
        pass
    dec = json.JSONDecoder()
    last = None
    i, n = 0, len(s)
    while i < n:
        while i < n and s[i] in " \t\r\n":
            i += 1
        if i >= n:
            break
        try:
            val, end = dec.raw_decode(s, i)
            if isinstance(val, want_type):
                last = val
            i = end
        except ValueError:
            i += 1  # skip a non-JSON char (stream noise) and keep scanning
    return last


def _last_json_object(stdout):
    """Return the LAST top-level JSON object in a (possibly line-delimited / streamed) blob,
    or None."""
    return _last_top_level_json(stdout, dict)


def _last_json_array(stdout):
    """Return the LAST top-level JSON array in a (possibly line-delimited / streamed) blob,
    or None — the tolerated bare-array reviewer shape (an engine emits `[...]` directly
    instead of `{"findings": [...]}`, #196)."""
    return _last_top_level_json(stdout, list)


def _unwrap_stream_envelope(stdout):
    """Unwrap a stream-json RESULT ENVELOPE before the role parsers scan for the leaf's
    payload (#347). cursor-agent `--output-format stream-json` (the format the byte-activity
    stall monitor NEEDS — a buffering format would run monitor-inert) wraps ALL leaf text in
    line-delimited events; the final event is `{"type":"result","result":"<all leaf text as
    ONE escaped string>",...}`. The leaf's real verdict/findings JSON therefore sits
    JSON-escaped INSIDE that string — invisible to a top-level scan, which sees only the
    envelope (no `ok` key -> build/fix coerced to a refusal; live: every in-child cursor
    dispatch ever recorded, issue #347). When — and only when — the LAST top-level object is
    such an envelope (`type=="result"`, a string `result`, and NOT itself a leaf verdict: no
    `ok` key), return the inner text for re-scanning; otherwise return stdout unchanged
    (codex output and native shapes are byte-identical through here). An error envelope whose
    inner text carries no JSON still ends `unreadable` downstream — the honest fail
    direction."""
    obj = _last_json_object(stdout)
    if (isinstance(obj, dict) and obj.get("type") == "result"
            and isinstance(obj.get("result"), str) and "ok" not in obj):
        return obj["result"]
    return stdout


def _scrub(text):
    if not isinstance(text, str) or not text:
        return text
    scrubbed, _ok = readout.scrub(text)
    return scrubbed


# Structural keys are NEVER free text (file paths, line numbers, severity/id/dimension enums,
# confidence scores) — every OTHER string value in a finding dict is untrusted external free text
# (body/suggestion/evidence/title/description/message/etc.) and is scrubbed unconditionally so no
# new field name can silently reopen the leak this boundary exists to close.
_FINDING_STRUCTURAL_KEYS = {"file", "line", "severity", "id", "dimension", "confidence"}


def _scrub_findings(findings):
    out = []
    for f in findings if isinstance(findings, list) else []:
        if not isinstance(f, dict):
            continue
        g = dict(f)
        for key, val in g.items():
            if key in _FINDING_STRUCTURAL_KEYS:
                continue
            if isinstance(val, str):
                g[key] = _scrub(val)
        out.append(g)
    return out


def _scrub_notify(notify):
    """NOTIFY entries are author free-text end to end (identity AND message) — scrub both."""
    out = []
    for n in notify if isinstance(notify, list) else []:
        if not isinstance(n, dict):
            continue
        out.append({"identity": _scrub(n.get("identity")) if isinstance(n.get("identity"), str) else None,
                    "message": _scrub(n.get("message")) if isinstance(n.get("message"), str) else None})
    return out


def parse_result(engine, role_kind, stdout):
    """Parse an external engine's stdout into the native result shape. review → scrubbed
    findings (from the canonical {"findings": [...]} object OR, tolerated, a bare top-level
    array of finding objects — #196); build|fix → {ok,signal,evidence{testFailed,testPassed}}
    honoring the leaf's OWN ok/signal (an honest {"ok":false,"signal":"plan_wrong"} refusal stays
    ok:false so it parks — never coerced to ok:true and committed, #288);
    author-plan →
    {ok,notify[]} (the doc itself is verified downstream by the deterministic usableDraft
    post-check — this parse only confirms the engine ran to completion and surfaces NOTIFY
    defaults). Unparseable/empty → {ok:false, reason:'unreadable'}. External free-text is
    scrubbed HERE (Secret-hygiene). Never raises."""
    try:
        stdout = _unwrap_stream_envelope(stdout)   # #347: see the unwrap's docstring
        obj = _last_json_object(stdout)
        if role_kind == "review":
            findings = obj.get("findings") if isinstance(obj, dict) else None
            if obj is None:
                # Shape tolerance (#196): the engine emitted NO top-level object at all — the
                # genuine bare-array reviewer shape (`[...]` instead of {"findings": [...]}).
                # Adopt that array as the findings list, but only when every element is an object
                # (an empty array is a clean, zero-finding review; a bare array with any
                # non-object is noise → unreadable, the same fail direction as any other
                # unparseable stdout — never a silent empty pass). We gate on `obj is None`, NOT
                # merely on a missing `findings` key: a present-but-findings-less result object
                # (a crash/error object) must stay unreadable and fall open to a Claude re-run
                # (UFR-7) rather than have the stream hunted for some other array to reinterpret
                # as findings — that would fail OPEN, silently certifying a slot that never
                # reviewed. This keeps the object path byte-identical to before the tolerance.
                arr = _last_json_array(stdout)
                if isinstance(arr, list) and all(isinstance(x, dict) for x in arr):
                    findings = arr
            if not isinstance(findings, list):
                return {"ok": False, "reason": "unreadable"}
            return {"ok": True, "findings": _scrub_findings(findings)}
        if obj is None:
            return {"ok": False, "reason": "unreadable"}
        if role_kind == "author-plan":
            return {"ok": True, "notify": _scrub_notify(obj.get("notify"))}
        # build | fix
        ev = obj.get("evidence") if isinstance(obj.get("evidence"), dict) else {}
        evidence = {"testFailed": bool(ev.get("testFailed")),
                    "testPassed": bool(ev.get("testPassed"))}
        # HONOR the leaf's own ok/signal — a parseable stdout is NOT a build success (#288). An
        # external build|fix worker that honestly refuses ({"ok":false,"signal":"plan_wrong"}) with
        # partial edits must reach dispatch's write-failure path as a FALSE result: NO commit (the
        # adapter is the sole committer, and step-6 commit runs only on ok:true), its uncommitted
        # edits discarded by the caller (UFR-2), and it parks (UFR-3) instead of being coerced to
        # ok:true and recorded built:passed. The native build gate's #275 fix is native-leaf-only and
        # can never catch this — the refusal never survives THIS boundary as a falsy value unless we
        # preserve it here. Strict boolean identity mirrors that gate (`worker.ok === true`): a real
        # `false`, a truthy stringified "false", or a missing key all read as a refusal, never true.
        if obj.get("ok") is not True:
            # Normalize the refusal signal to the known worker-recovery vocabulary — NEVER pass the
            # engine's raw `signal` string through. This is a scrub boundary (Secret-hygiene): every
            # other branch scrubs external free-text, and `signal` here becomes `reason`, which flows
            # into the durable journal outcome AND owner-facing narrator logs (engine_dispatch.js).
            # `plan_wrong` is the ONLY value the native worker-recovery twin treats specially
            # (worker_recovery.decide); every other value — off-contract, empty, or non-string —
            # collapses to `needs_context`, exactly as native's `worker.signal || 'needs_context'` plus
            # the twin's non-plan_wrong bucket would. So this is behavior-identical to the native path
            # AND leak-proof: no engine-controlled free-text can escape as signal/reason (which also
            # keeps it disjoint from the #277 harness-dead tripwire's reserved reason tokens).
            sig = "plan_wrong" if obj.get("signal") == "plan_wrong" else "needs_context"
            return {"ok": False, "signal": sig, "reason": sig, "evidence": evidence}
        return {"ok": True, "signal": "ok", "evidence": evidence}
    except Exception:
        return {"ok": False, "reason": "unreadable"}


def _git(worktree, *args):
    return subprocess.run(["git", "-C", worktree, *args],
                          capture_output=True, text=True)


def commit_result(worktree, task_id, pre_sha):
    """The SOLE committer for external writes. HEAD==pre_sha (engine only edited) → make the
    single Task-Id-trailered commit. HEAD!=pre_sha (engine left stray commits) → soft-reset to
    pre_sha (folds ONLY this dispatch's commits — pre_sha is per-dispatch), then the single
    trailered commit. Never a hard reset; discards no prior work. Never raises."""
    msg = "build: apply external-engine change\n\n%s: %s" % (TASK_ID_TRAILER, task_id)
    try:
        head = _git(worktree, "rev-parse", "HEAD")
        if head.returncode != 0:
            return {"ok": False, "error": "cannot resolve HEAD: %s" % head.stderr.strip()}
        if head.stdout.strip() != pre_sha:
            # fold ONLY this dispatch's commits back into the index (prior work is below pre_sha)
            r = _git(worktree, "reset", "--soft", pre_sha)
            if r.returncode != 0:
                return {"ok": False, "error": "soft-reset failed: %s" % r.stderr.strip()}
        add = _git(worktree, "add", "-A")
        if add.returncode != 0:
            return {"ok": False, "error": "git add failed: %s" % add.stderr.strip()}
        commit = _git(worktree, "commit", "-m", msg)
        if commit.returncode != 0:
            return {"ok": False, "error": "git commit failed: %s" % commit.stderr.strip()}
        new_head = _git(worktree, "rev-parse", "HEAD")
        return {"ok": True, "sha": new_head.stdout.strip()}
    except Exception as exc:
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}


def _cmd_build_argv(args):
    opts = {"cwd": args.cwd, "schema_path": args.schema_path, "model": args.model}
    sys.stdout.write(json.dumps(build_argv(args.engine, args.role, args.effort, opts)) + "\n")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(prog="engine_adapter")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build-argv")
    b.add_argument("--engine", required=True, choices=("codex", "cursor"))
    b.add_argument("--role", required=True, choices=("review", "build", "fix", "author-plan"))
    b.add_argument("--effort", required=True)
    b.add_argument("--cwd", default=None)
    b.add_argument("--schema-path", default=None)
    b.add_argument("--model", default=None,
                   help="native tier short name; cursor maps ONLY fable (owner policy), else composer")
    pr = sub.add_parser("parse-result")
    pr.add_argument("--engine", required=True, choices=("codex", "cursor"))
    pr.add_argument("--role", required=True, choices=("review", "build", "fix", "author-plan"))
    pr.add_argument("--stdout-path", default=None,
                     help="file holding the external engine's raw stdout; stdin if omitted")
    cm = sub.add_parser("commit")
    cm.add_argument("--worktree", required=True)
    cm.add_argument("--task-id", required=True)
    cm.add_argument("--pre-sha", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "build-argv":
        return _cmd_build_argv(args)
    if args.cmd == "parse-result":
        if args.stdout_path:
            with open(args.stdout_path, encoding="utf-8") as _fh:
                _raw = _fh.read()
        else:
            _raw = sys.stdin.read()
        res = parse_result(args.engine, args.role, _raw)
        sys.stdout.write(json.dumps(res) + "\n")
        return 0
    if args.cmd == "commit":
        res = commit_result(args.worktree, args.task_id, args.pre_sha)
        sys.stdout.write(json.dumps(res) + "\n")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
