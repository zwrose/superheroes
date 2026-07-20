#!/usr/bin/env python3
"""The deterministic engine argv/parse/commit core (kept out of the model-driven JS layer so
it is unit-testable). Named engine_adapter (NOT engine_cli — that is test-pilot's). Every
external free-text surface is scrubbed at THIS trust boundary (parse_result). Flags verified
live 2026-07-12 against codex 0.144.1 (GPT-5.6; 0.141.0 is rejected by the API as too old)
and cursor-agent 2026.06.26 (--model / -p / --trust; -m is gone)."""
import argparse
import hashlib
import json
import os
import subprocess
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import readout  # noqa: E402  (the band's single scrub seam; same-tree sibling)
import engine_pref  # noqa: E402  (provider-specific model policy; same-tree sibling)
import model_registry  # noqa: E402  (band-wide model taxonomy; same-tree sibling)

# The SINGLE-SOURCED commit trailer. The committer (commit_result, Task 7) and the
# build_state_cli git-log parser both reference this so the convention cannot fork.
TASK_ID_TRAILER = "Task-Id"

# #392: the distinct, honest outcome for a fix whose SUBSTANCE is the history shape (squash to N
# commits, reword, drop a commit) rather than content. Such a fix produces a tree content-identical
# to pre_sha, so the fold-only invariant (commit_result never discards commits below pre_sha) folds
# it to a no-op — the engine did exactly what was asked, but the adapter structurally cannot LAND a
# pure history rewrite. Reporting THIS token (not a bare/blank commit-failed) lets the caller fall
# open to the native fixer — which CAN rewrite history — deliberately, and the journal names WHY.
# engine_dispatch.js reads this `reason` off the adapter's JSON result DYNAMICALLY (it does not
# hardcode the literal), passing it through verbatim as both the fall-open reason and the journal
# outcome. Downstream acceptance_verdict.tally_external_dispatches counts it as a genuine (non-"ok")
# dispatch FAILURE — the deliberate, conservative choice (#392): the engine authentically ran, but the
# dispatch did NOT land a commit, so it fails SAFE (never inflates a run's success tally) exactly like
# commit-failed. It is NOT modeled as a new acceptance outcome class.
HISTORY_SHAPE_UNREPRESENTABLE = "history-shape-fix-unrepresentable"

# Explicit model per engine (Config-determinism NFR — never the developer's ambient default).
# Codex maps the shared tier through engine_pref and accepts a separate concrete engine-model pin;
# this compatibility alias remains the capable no-tier default used by display/readout callers.
_CODEX_MODEL_BY_TIER = dict(engine_pref.CODEX_MODEL_BY_TIER)
_CODEX_MODEL = model_registry.codex_peer_for_claude_tier("opus")
_CODEX_MODELS = model_registry.codex_models()
_CURSOR_MODEL = model_registry.dispatch_token("cursor", "composer-2.5")


def build_argv(engine, role_kind, effort, opts):
    """Return the argv list to dispatch `engine` for `role_kind` at `effort`. READ (review) →
    read-only sandbox; WRITE (build|fix) → workspace-write. Always explicit
    model+effort. opts keys: cwd, schema_path, model (native tier short name), engine_model
    (provider-specific concrete model pin). Cursor dispatches the composer default (`_CURSOR_MODEL`);
    a `fable` tier is anthropic-only and unrunnable on cursor. Codex uses a valid engine_model pin
    or maps the shared tier. The PROMPT is NOT
    encoded here — codex reads it from stdin (trailing `-`) and cursor-agent reads it from stdin
    when given no positional prompt; the JS runner (Task 10) feeds the staged prompt file to the
    process stdin. Deterministic; fully unit-testable."""
    opts = opts or {}
    cwd = opts.get("cwd")
    schema_path = opts.get("schema_path")
    is_read = role_kind == "review"
    if engine == "codex":
        engine_model = opts.get("engine_model")
        if not isinstance(engine_model, str) or not model_registry.is_registered("codex", engine_model):
            try:
                engine_model = model_registry.codex_peer_for_claude_tier(opts.get("model"))
            except ValueError:
                return []  # fable/anthropic-only on codex — unrunnable → JS falls open to claude
        ok, _reason = model_registry.validate_config(
            "codex", engine_model, effort, allow_override_only=True)
        if not ok:
            return []  # invalid (model,effort) — fail loud: do not dispatch a silently-misconfigured codex
        sandbox = "read-only" if is_read else "workspace-write"
        argv = ["codex", "exec", "--sandbox", sandbox,
                "-m", engine_model,
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
        if opts.get("model") == "fable":
            return []  # fable is anthropic-only; the cursor fable channel is retired — fall open to claude
        model = _CURSOR_MODEL  # composer-2.5 (per-role grok selection is issue #510's composition layer)
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


def parse_result(engine, role_kind, stdout):
    """Parse an external engine's stdout into the native result shape. review → scrubbed
    findings (from the canonical {"findings": [...]} object OR, tolerated, a bare top-level
    array of finding objects — #196); build|fix → {ok,signal,evidence{testFailed,testPassed}}
    honoring the leaf's OWN ok/signal (an honest {"ok":false,"signal":"plan_wrong"} refusal stays
    ok:false so it parks — never coerced to ok:true and committed, #288).
    Unparseable/empty → {ok:false, reason:'unreadable'}. External free-text is
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


# The canned message used when the engine committed nothing (edits only) OR left a commit whose
# captured message is empty/unusable. When the engine DID leave a usable message, that message is
# preserved (see _capture_engine_message + commit_result) so spec-prescribed commit messages
# survive an external build (#386).
_CANNED_COMMIT_SUBJECT = "build: apply external-engine change"


def _capture_engine_message(worktree):
    """Capture the message of the TIP of the engine's own commits (`git log -1 --format=%B HEAD`)
    for reuse as the folded commit's message. The TIP is chosen deliberately: it is the engine's
    final word on what the change is — a multi-commit engine output folds to one commit, and its
    last message is the authoritative summary of the whole (a WIP first commit is exactly the
    message we do NOT want). Returns the sanitized message body, or "" when unusable so the caller
    falls back to the canned subject:
      - trailing whitespace stripped (empty/whitespace-only → "" → canned fallback);
      - any pre-existing Task-Id trailer line removed, so composing our own never doubles it (#386).

    Scrubbed via the same readout.scrub seam as parse_result: every external free-text surface
    at this trust boundary is scrubbed before persistence. Commit messages reach public PR
    history via ship_phase pushes, so an engine tip message is in scope."""
    log = _git(worktree, "log", "-1", "--format=%B", "HEAD")
    if log.returncode != 0:
        return ""
    # Drop any pre-existing Task-Id trailer line(s) (exact "Task-Id:" prefix — the format we emit)
    # so the trailer we append is never doubled.
    kept = [ln for ln in log.stdout.split("\n")
            if not ln.strip().startswith(TASK_ID_TRAILER + ":")]
    scrubbed = _scrub("\n".join(kept))
    return scrubbed.strip() if isinstance(scrubbed, str) else ""


def commit_result(worktree, task_id, pre_sha):
    """The SOLE committer for external writes. HEAD==pre_sha (engine only edited) → make the
    single Task-Id-trailered commit with the canned subject. HEAD!=pre_sha (engine left its own
    commit(s)) → capture the engine's tip commit message BEFORE the soft-reset, soft-reset to
    pre_sha (folds ONLY this dispatch's commits — pre_sha is per-dispatch), then the single
    trailered commit REUSING the engine's message (falling back to the canned subject when the
    engine left no usable message, #386). Never a hard reset; discards no prior work. Never raises."""
    try:
        head = _git(worktree, "rev-parse", "HEAD")
        if head.returncode != 0:
            return {"ok": False, "error": "cannot resolve HEAD: %s" % head.stderr.strip()}
        subject = _CANNED_COMMIT_SUBJECT
        engine_self_committed = head.stdout.strip() != pre_sha
        if engine_self_committed:
            # Capture the engine's own commit message BEFORE folding — after the soft-reset the
            # engine's commits (and their messages) are gone from HEAD. A usable message is reused
            # so spec-prescribed commit messages survive; empty/unusable → canned fallback.
            captured = _capture_engine_message(worktree)
            if captured:
                subject = captured
            # fold ONLY this dispatch's commits back into the index (prior work is below pre_sha)
            r = _git(worktree, "reset", "--soft", pre_sha)
            if r.returncode != 0:
                return {"ok": False, "error": "soft-reset failed: %s" % r.stderr.strip()}
        msg = "%s\n\n%s: %s" % (subject, TASK_ID_TRAILER, task_id)
        add = _git(worktree, "add", "-A")
        if add.returncode != 0:
            return {"ok": False, "error": "git add failed: %s" % add.stderr.strip()}
        commit = _git(worktree, "commit", "-m", msg)
        if commit.returncode != 0:
            # #392: when the engine self-committed and the fold leaves the index identical to HEAD
            # (`git diff --cached --quiet` → 0, i.e. nothing to commit), the engine's work was a PURE
            # history-shape change (squash/reword/drop-commit) whose tree already equals pre_sha's.
            # The fold-only invariant cannot land it; report it as a DISTINCT, honest outcome so the
            # caller falls open to the native fixer deliberately and the journal names WHY — never a
            # blank commit-failed and never a silently-swallowed empty diff.
            if engine_self_committed and \
                    _git(worktree, "diff", "--cached", "--quiet").returncode == 0:
                return {"ok": False, "reason": HISTORY_SHAPE_UNREPRESENTABLE}
            # #392 sub-defect 1: "nothing to commit" (and other benign git refusals) print to STDOUT,
            # not stderr — a stderr-only read left the reason blank. Prefer stderr, fall back to stdout.
            detail = commit.stderr.strip() or commit.stdout.strip()
            return {"ok": False, "error": "git commit failed: %s" % detail}
        new_head = _git(worktree, "rev-parse", "HEAD")
        return {"ok": True, "sha": new_head.stdout.strip()}
    except Exception as exc:
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}


def _cmd_build_argv(args):
    # #395: deterministic staged-input verify — the caller passes PATH:SHA256 for each file the
    # staging courier claimed to have written. The courier's self-reported ok is fabricatable
    # (live wf_28e14382-82e); this re-hash from disk is the authoritative signal. Any mismatch or
    # unreadable file fails the WHOLE build-argv closed — the external CLI must never run on
    # unverified inputs.
    for spec in (args.verify or []):
        path, _, want = spec.rpartition(":")
        try:
            with open(path, "rb") as fh:
                got = hashlib.sha256(fh.read()).hexdigest()
        except OSError:
            got = None
        if got != want:
            sys.stdout.write(json.dumps(
                {"ok": False, "reason": "staged-input-mismatch", "path": path}) + "\n")
            return 0

    opts = {"cwd": args.cwd, "schema_path": args.schema_path, "model": args.model,
            "engine_model": args.engine_model}
    sys.stdout.write(json.dumps(build_argv(args.engine, args.role, args.effort, opts)) + "\n")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(prog="engine_adapter")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build-argv")
    b.add_argument("--engine", required=True, choices=("codex", "cursor"))
    b.add_argument("--role", required=True, choices=("review", "build", "fix"))
    b.add_argument("--effort", required=True)
    b.add_argument("--cwd", default=None)
    b.add_argument("--schema-path", default=None)
    b.add_argument("--model", default=None,
                   help="native tier short name; cursor dispatches composer (fable is anthropic-only, unrunnable on cursor)")
    b.add_argument("--engine-model", default=None,
                   help="provider-specific concrete model id; currently used by codex pins")
    b.add_argument("--verify", action="append", default=None,
                   help="PATH:SHA256 staged-input check; any mismatch/unreadable file fails build-argv closed")
    pr = sub.add_parser("parse-result")
    pr.add_argument("--engine", required=True, choices=("codex", "cursor"))
    pr.add_argument("--role", required=True, choices=("review", "build", "fix"))
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
