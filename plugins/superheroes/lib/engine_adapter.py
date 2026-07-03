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

# Native tier short-name -> cursor model id, for roles that carry a model override (today only
# author-plan, the plan-author leaf: `author-plan: fable` + `planAuthor: cursor` = Fable via
# Cursor). Ids verified live 2026-07-03 against cursor-agent 2026.07.01 `models`. An unmapped or
# absent override keeps the pinned composer default — never the developer's ambient default.
_CURSOR_MODEL_BY_TIER = {
    "fable": "claude-fable-5-thinking-xhigh",
    "opus": "claude-opus-4-8-thinking-high",
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


def _last_json_object(stdout):
    """Return the LAST top-level JSON object in a (possibly line-delimited / streamed) blob,
    or None. Tries whole-blob parse first, then a raw_decode scan, then a per-line fallback."""
    s = (stdout or "").strip()
    if not s:
        return None
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
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
            obj, end = dec.raw_decode(s, i)
            if isinstance(obj, dict):
                last = obj
            i = end
        except ValueError:
            i += 1  # skip a non-JSON char (stream noise) and keep scanning
    return last


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
    findings; build|fix → {ok,signal,evidence{testFailed,testPassed}}; author-plan →
    {ok,notify[]} (the doc itself is verified downstream by the deterministic usableDraft
    post-check — this parse only confirms the engine ran to completion and surfaces NOTIFY
    defaults). Unparseable/empty → {ok:false, reason:'unreadable'}. External free-text is
    scrubbed HERE (Secret-hygiene). Never raises."""
    try:
        obj = _last_json_object(stdout)
        if obj is None:
            return {"ok": False, "reason": "unreadable"}
        if role_kind == "review":
            findings = obj.get("findings")
            if not isinstance(findings, list):
                return {"ok": False, "reason": "unreadable"}
            return {"ok": True, "findings": _scrub_findings(findings)}
        if role_kind == "author-plan":
            return {"ok": True, "notify": _scrub_notify(obj.get("notify"))}
        # build | fix
        ev = obj.get("evidence") if isinstance(obj.get("evidence"), dict) else {}
        evidence = {"testFailed": bool(ev.get("testFailed")),
                    "testPassed": bool(ev.get("testPassed"))}
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
                   help="native tier short name (fable/opus); cursor maps it to its model id")
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
