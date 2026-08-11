#!/usr/bin/env python3
"""The deterministic engine argv/parse/commit core (kept out of the effectful dispatch layer so
it is unit-testable). Named engine_adapter (NOT engine_cli — that is test-pilot's). Every
external free-text surface is scrubbed at THIS trust boundary (parse_result). The library path
strips echoed prompts when given prompt text; the ``parse-result`` CLI subcommand never sees the
dispatched prompt and cannot strip echoes — empty-findings from that path are unverified. Flags
verified live 2026-07-12 against codex 0.144.1 (GPT-5.6; 0.141.0 is rejected by the API as too
old) and cursor-agent 2026.06.26 (--model / -p / --trust; -m is gone)."""
import argparse
import hashlib
import json
import os
import re
import stat as _stat
import subprocess
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import readout  # noqa: E402  (the band's single scrub seam; same-tree sibling)
import model_registry  # noqa: E402  (band-wide model taxonomy; same-tree sibling)

# The SINGLE-SOURCED commit trailer. The committer (commit_result, Task 7) and the
# build_state_cli git-log parser both reference this so the convention cannot fork.
TASK_ID_TRAILER = "Task-Id"

# Re-export vacuous forfeit reason from dispatch_outcome (CONVENTIONS §11 Pattern 1). The
# dispatch runner produces it; round_driver and seat_canary compare against it — consumers
# import this name, never restate the literal.
import dispatch_outcome  # noqa: E402  (stdlib-only chokepoint; must not import engine_adapter)

REVIEW_FORFEIT_VACUOUS = dispatch_outcome.REASON_VACUOUS

# Bounds for the payload-shape diagnostic. These strings come from ENGINE-CONTROLLED JSON and
# cross the same trust boundary as any other external free text.
PAYLOAD_SHAPE_MAX_KEYS = 12
PAYLOAD_SHAPE_MAX_KEY_LEN = 60

SHAPE_OBJECT_WITHOUT_FINDINGS = "object-without-findings"
SHAPE_OBJECT_FINDINGS_NOT_A_LIST = "object-findings-not-a-list"
SHAPE_ARRAY_NOT_ALL_OBJECTS = "array-not-all-objects"
SHAPE_NO_PARSEABLE_JSON = "no-parseable-json"
SHAPE_EMPTY_STDOUT = "empty-stdout"
SHAPE_PROMPT_ECHO_ONLY = "prompt-echo-only"

REVIEW_PAYLOAD_SHAPES = (
    SHAPE_OBJECT_WITHOUT_FINDINGS,      # a JSON object parsed, but it carries no `findings` key
    SHAPE_OBJECT_FINDINGS_NOT_A_LIST,   # a JSON object parsed with a `findings` key that is not a list
    SHAPE_ARRAY_NOT_ALL_OBJECTS,        # a bare top-level array parsed, but not every element is an object
    SHAPE_NO_PARSEABLE_JSON,            # stdout was non-empty but held no parseable top-level JSON value
    SHAPE_EMPTY_STDOUT,                 # stdout was empty or whitespace only
    SHAPE_PROMPT_ECHO_ONLY,             # the seat emitted only an echo of its prompt — graded text empty after strip
)

# #392: the distinct, honest outcome for a fix whose SUBSTANCE is the history shape (squash to N
# commits, reword, drop a commit) rather than content. Such a fix produces a tree content-identical
# to pre_sha, so the fold-only invariant (commit_result never discards commits below pre_sha) folds
# it to a no-op — the engine did exactly what was asked, but the adapter structurally cannot LAND a
# pure history rewrite. Reporting THIS token (not a bare/blank commit-failed) lets the caller fall
# open to the native fixer — which CAN rewrite history — deliberately, and the journal names WHY.
# The write-path dispatch caller reads this `reason` off the adapter's JSON result DYNAMICALLY (it does not
# hardcode the literal), passing it through verbatim as both the fall-open reason and the journal
# outcome. Downstream acceptance_verdict.tally_external_dispatches counts it as a genuine (non-"ok")
# dispatch FAILURE — the deliberate, conservative choice (#392): the engine authentically ran, but the
# dispatch did NOT land a commit, so it fails SAFE (never inflates a run's success tally) exactly like
# commit-failed. It is NOT modeled as a new acceptance outcome class.
HISTORY_SHAPE_UNREPRESENTABLE = "history-shape-fix-unrepresentable"

# Cursor dispatches a single composer model; codex model selection is resolved inline via model_registry.
_CURSOR_MODEL = model_registry.dispatch_token("cursor", "composer-2.5")

# #563 DoD5: a large engine stdout must not WEDGE the parse (the field incident: a >10-min scan on
# ~1 MB of stdout). The plausible-start scan (see `_last_top_level_json`) is the real fix. This
# bounded tail is a fast PATH for the common small case: read only the last MAX_STDOUT_TAIL_BYTES and
# parse that. A read that had to truncate is NEVER trusted (see the parse-result branch): it is
# re-read in FULL, so the bound never changes the result — it only avoids loading a small file's
# worth extra in the common case. 512 KB comfortably exceeds any real findings payload.
MAX_STDOUT_TAIL_BYTES = 512 * 1024

# #668: runner stdout capture keeps only the tail (MAX_STDOUT_CAPTURE in engine_dispatch); a large
# echoed prompt can arrive truncated while the trailing shape-contract example survives.
ECHO_TAIL_CHARS = 2000

WRITE_REPORT_SENTINEL = "<<<SUPERHEROES-WRITE-REPORT>>>"

WRITE_REPORT_CONTRACT = (
    "Write-report contract (your graded tail is separate from prose receipts):\n"
    "Emit the full prose report the order already asks for, first and in full.\n"
    "The JSON object below is in addition to those receipts, never a replacement.\n"
    "As the very last thing in your output: a line containing only:\n"
    + WRITE_REPORT_SENTINEL + "\n"
    "then a single JSON object on the following line, then nothing at all.\n"
    "Field semantics:\n"
    "  ok — true means you ran the order to completion as specified; it is not an acceptance "
    "verdict — you never judge whether the work is good enough and you never mark your own work done.\n"
    "  ok: false — you stopped or refused; set signal to \"plan_wrong\" when the order's premise "
    "is wrong, otherwise \"needs_context\" (only those two values).\n"
    "  evidence.testFailed / evidence.testPassed — booleans for whether you observed a test "
    "failing / passing during this attempt; false when not observed.\n"
    "Example final two lines:\n"
    + WRITE_REPORT_SENTINEL + "\n"
    '{"ok": true, "signal": "ok", "evidence": {"testFailed": false, "testPassed": true}}'
)

# #747 WO-4a: pure engaged-artifact detector thresholds. Measured 2026-07-31 on the preserved
# dispatch corpus (harness 2.1.219, plugin 0.23.0): all seven prose specimens score ≥2 signals
# under the two-of-three rule; the preserved cursor stream log (66,821 B raw) scores 1 signal and
# is correctly rejected. Smallest genuine prose specimen is 661 B; the floor rejects one-line errors.
ARTIFACT_MIN_RESIDUE_BYTES = 200
ARTIFACT_EXCERPT_BYTES = 2000
ARTIFACT_MIN_SIGNALS = 2  # of citations / enumerations / sections — never one signal alone (BC-5)
ARTIFACT_SECTION_NAMES = (
    "findings",
    "investigation record",
    "verdict",
    "no blocking findings",
    "blocking",
    "summary",
)
_ARTIFACT_CITATION_RE = re.compile(r"[\w./\\-]+\.[\w]+:\d+")
_ARTIFACT_ENUM_LINE_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+", re.MULTILINE)
_ARTIFACT_TRACEBACK_FIRST_LINE_RE = re.compile(
    r"^(?:Traceback \(most recent call last\)|panic:|error\[E\d+\])",
    re.IGNORECASE,
)


# Named refusal tokens from build_argv_result (issue #636). The dispatch runner surfaces them as
# detail=engine-config:<token>; the build-argv CLI prints detail=<token> directly.
_BUILD_ARGV_REFUSAL_TOKENS = frozenset({
    "unknown-engine",
    "unknown-claude-tier",
    "fable-unrunnable",
    "unregistered-engine-model",
    "engine-model-effort-conflict",
    "invalid-model-effort",
    "untokenizable",
})


def _refuse(reason):
    assert reason in _BUILD_ARGV_REFUSAL_TOKENS
    return {"argv": [], "reason": reason}


def _ok(argv):
    return {"argv": argv, "reason": None}


def build_argv_result(engine, role_kind, effort, opts):
    """Like build_argv but returns {argv, reason} with a named refusal token when unrunnable."""
    opts = opts or {}
    cwd = opts.get("cwd")
    schema_path = opts.get("schema_path")
    is_read = role_kind == "review"
    claude_tier = opts.get("model")
    if claude_tier is not None:
        if not isinstance(claude_tier, str) or claude_tier not in model_registry.known_claude_models():
            return _refuse("unknown-claude-tier")
        if claude_tier == "fable":
            # Config-time gate configured_dispatch_violations is primary; depth for bypass callers.
            return _refuse("fable-unrunnable")
    if engine == "codex":
        engine_model = opts.get("engine_model")
        if isinstance(engine_model, str) and engine_model:
            if model_registry.is_registered("codex", engine_model):
                pass
            else:
                parsed = model_registry.parse_dispatch_token("codex", engine_model)
                if parsed is None:
                    return _refuse("unregistered-engine-model")
                engine_model, _tok_effort = parsed
        else:
            try:
                engine_model = model_registry.codex_peer_for_claude_tier(claude_tier)
            except ValueError:
                # Config-time gate configured_dispatch_violations is primary; depth for bypass callers.
                return _refuse("fable-unrunnable")
        ok, _reason = model_registry.validate_config(
            "codex", engine_model, effort, allow_override_only=True)
        if not ok:
            return _refuse("invalid-model-effort")
        sandbox = "read-only" if is_read else "workspace-write"
        argv = ["codex", "exec", "--sandbox", sandbox,
                "-m", engine_model,
                "-c", "model_reasoning_effort=%s" % effort]
        if cwd:
            argv += ["-C", cwd]           # write: confine writes to the managed worktree.
                                          # read (#665): pin the seat to the repo so it can trace
                                          # into files instead of inheriting the dispatcher's cwd.
        if is_read and schema_path:
            argv += ["--output-schema", schema_path]  # enforced structured review output
        # trailing `-`: read the prompt from stdin. The dispatch runner redirects the staged
        # prompt file into stdin (`<argv> < promptPath`) — the prompt is ALWAYS fed here.
        argv += ["-"]
        return _ok(argv)
    if engine == "cursor":
        engine_model = opts.get("engine_model")
        if isinstance(engine_model, str) and engine_model:
            if model_registry.is_registered("cursor", engine_model):
                model_id = engine_model
            else:
                parsed = model_registry.parse_dispatch_token("cursor", engine_model)
                if parsed is None:
                    return _refuse("unregistered-engine-model")
                model_id, tok_effort = parsed
                if tok_effort is not None and effort is not None and tok_effort != effort:
                    return _refuse("engine-model-effort-conflict")
                if effort is None and tok_effort is not None:
                    effort = tok_effort
            ok, _reason = model_registry.validate_config("cursor", model_id, effort)
            if not ok:
                return _refuse("invalid-model-effort")
            tok = model_registry.dispatch_token("cursor", model_id, effort)
            if not tok:
                # defensive: unreachable once validate_config passes for cursor models
                return _refuse("untokenizable")
            model = tok
        else:
            model = _CURSOR_MODEL
        # cursor-agent has no cwd flag; a cursor read dispatch is pinned by the runner's subprocess
        # cwd (#665), not by argv.
        # cursor-agent 2026.06.26: model flag is --model (not -m); -p/--print is REQUIRED for a
        # headless run (without it it goes interactive and --output-format is a no-op); --trust
        # clears the workspace-trust gate that otherwise HANGS a headless run (needed for the
        # read/--mode-plan role — the write role's -f also trusts, but --trust covers both).
        argv = ["cursor-agent", "--model", model, "-p", "--trust"]
        if is_read:
            argv += ["--mode", "plan"]
        else:
            argv += ["-f"]
        argv += ["--output-format", "stream-json"]
        return _ok(argv)
    return _refuse("unknown-engine")


def build_argv(engine, role_kind, effort, opts):
    """Return the argv list to dispatch `engine` for `role_kind` at `effort`. READ (review) →
    read-only sandbox; WRITE (build|fix) → workspace-write. Always explicit
    model+effort. opts keys: cwd, schema_path, model (native Claude tier short name from
    model_registry.known_claude_models()), engine_model (registry id or composed dispatch token).
    Cursor uses composer by default or an explicit engine_model pin; a non-tier `model` value is
    refused (never silently substituted). Codex uses a valid engine_model pin or maps the shared
    tier. The PROMPT is NOT encoded here — codex reads it from stdin (trailing `-`) and
    cursor-agent reads it from stdin when given no positional prompt; the dispatch runner feeds
    the staged prompt file to the process stdin. Deterministic; fully unit-testable."""
    return build_argv_result(engine, role_kind, effort, opts)["argv"]


def _top_level_json_matches(stdout, want_type=None):
    """Return top-level JSON (value, start, end) matches in a streamed blob.

    `want_type` limits returned container types when supplied. The scan attempts decoding only
    at plausible object/array starts, avoiding raw_decode exceptions for ordinary stream noise.
    """
    s = (stdout or "").strip()
    if not s:
        return []
    try:
        val = json.loads(s)
        if want_type is None or isinstance(val, want_type):
            return [(val, 0, len(s))]
        return []
    except ValueError:
        pass
    # A top-level JSON object starts with '{' and an array with '['. Attempt a decode ONLY at one of
    # those two container-start chars — a cheap char test in place of the old raw_decode-per-char
    # exception storm (#563: the old scan threw one ValueError per stream-noise char and wedged on
    # large stdout). Record only the wanted type, but ALWAYS advance past a successfully decoded value
    # (i = end) so a whole value — including a top-level array — is consumed as a unit and its inner
    # objects are NOT re-seen as top-level (a top-level array is thereby consumed whole and its inner
    # objects are NOT re-seen as top-level, so the #196 bare-array rescue still holds: a bare
    # `[{...}]` leaves `_last_json_object` == None). This matches the pre-#563 result for every real
    # engine payload; the one accepted divergence is a top-level *scalar/string* whose text embeds an
    # empty-object array like `[{},{}]` — near-nil in practice, and restoring strict scalar-
    # consumption parity would reopen the per-char exception storm this scan exists to close).
    dec = json.JSONDecoder()
    matches = []
    i, n = 0, len(s)
    while i < n:
        if s[i] != "{" and s[i] != "[":
            i += 1
            continue
        try:
            val, end = dec.raw_decode(s, i)
            if want_type is None or isinstance(val, want_type):
                matches.append((val, i, end))
            i = end
        except ValueError:
            i += 1
    return matches


def _last_top_level_json(stdout, want_type):
    """Return the LAST top-level JSON value of `want_type` (dict or list) in a (possibly
    line-delimited / streamed) blob, or None. Shared by _last_json_object (dict) and
    _last_json_array (list) so the plausible-start scan logic lives once."""
    matches = _top_level_json_matches(stdout, want_type)
    return matches[-1][0] if matches else None


def _last_json_object(stdout):
    """Return the LAST top-level JSON object in a (possibly line-delimited / streamed) blob,
    or None."""
    return _last_top_level_json(stdout, dict)


def _last_json_array(stdout):
    """Return the LAST top-level JSON array in a (possibly line-delimited / streamed) blob,
    or None — the tolerated bare-array reviewer shape (an engine emits `[...]` directly
    instead of `{"findings": [...]}`, #196)."""
    return _last_top_level_json(stdout, list)


def write_prompt_is_contracted(fed_prompt):
    """True when the fed write prompt carries the write-report contract block."""
    if not isinstance(fed_prompt, str) or not fed_prompt:
        return False
    return WRITE_REPORT_CONTRACT in fed_prompt


def extract_write_report(text):
    """Strict tail grammar: sentinel line + one JSON object + trailing whitespace only.

    Input must already be envelope-unwrapped and echo-stripped. Returns the decoded object
    or None. Never raises."""
    try:
        if not isinstance(text, str) or not text:
            return None
        lines = text.split("\n")
        last_idx = None
        for i, line in enumerate(lines):
            if line.strip() == WRITE_REPORT_SENTINEL:
                last_idx = i
        if last_idx is None:
            return None
        after = "\n".join(lines[last_idx + 1:])
        if not after:
            return None
        dec = json.JSONDecoder()
        obj, end = dec.raw_decode(after.lstrip())
        if not isinstance(obj, dict):
            return None
        tail = after.lstrip()[end:]
        if tail.strip():
            return None
        return obj
    except Exception:
        return None


def _grade_build_report_obj(obj):
    """Single home for build|fix report-object grading (CONVENTIONS §11). Never raises."""
    if not isinstance(obj, dict):
        return {"ok": False, "reason": "unreadable"}
    ev = obj.get("evidence") if isinstance(obj.get("evidence"), dict) else {}
    evidence = {"testFailed": bool(ev.get("testFailed")),
                "testPassed": bool(ev.get("testPassed"))}
    if obj.get("ok") is not True:
        sig = "plan_wrong" if obj.get("signal") == "plan_wrong" else "needs_context"
        return {"ok": False, "signal": sig, "reason": sig, "evidence": evidence}
    return {"ok": True, "signal": "ok", "evidence": evidence}


def grade_write_report(engine, role_kind, stdout, fed_prompt):
    """Grade a write dispatch stdout. Contracted prompts require the strict tail report;
    uncontracted prompts delegate to parse_result (byte-identical legacy). Never raises."""
    try:
        text = stdout if isinstance(stdout, str) else ""
        text = _unwrap_stream_envelope(text)
        if not isinstance(text, str):
            text = ""
        prompt = fed_prompt if isinstance(fed_prompt, str) else ""
        stripped = strip_echoed_prompt(text, prompt)
        if not isinstance(stripped, str):
            stripped = ""
        if write_prompt_is_contracted(prompt):
            obj = extract_write_report(stripped)
            if obj is None:
                return {"ok": False, "reason": "unreadable"}
            return _grade_build_report_obj(obj)
        return parse_result(engine, role_kind, stdout)
    except Exception:
        return {"ok": False, "reason": "unreadable"}


def strip_echoed_prompt(stdout, prompt_text):
    """Remove verbatim echoes of the dispatched prompt from engine stdout before parse.

    Strips the full prompt (raw and JSON-escaped), then the last ECHO_TAIL_CHARS of the prompt
    (raw and JSON-escaped) for capture-truncated echoes. Never raises."""
    if not isinstance(stdout, str) or not stdout:
        return stdout
    if not isinstance(prompt_text, str) or not prompt_text:
        return stdout
    out = stdout
    escaped_full = json.dumps(prompt_text)[1:-1]
    tail = prompt_text[-ECHO_TAIL_CHARS:]
    tail_escaped = json.dumps(tail)[1:-1]
    for fragment in (prompt_text, escaped_full, tail, tail_escaped):
        out = out.replace(fragment, "")
    if out and tail.endswith(out):
        out = ""
    return out


def codex_tokens_used(stderr_tail):
    """Parse codex stderr tail for the last 'tokens used' block; return int or None. Never raises."""
    try:
        if not isinstance(stderr_tail, str) or not stderr_tail:
            return None
        lines = stderr_tail.splitlines()
        last_idx = None
        for i, line in enumerate(lines):
            if line.strip() == "tokens used":
                last_idx = i
        if last_idx is None or last_idx + 1 >= len(lines):
            return None
        count_line = lines[last_idx + 1].strip()
        if not count_line:
            return None
        return int(count_line.replace(",", "").strip())
    except Exception:
        return None


def cursor_tool_calls(stdout):
    """Count distinct tool_call call_ids in a cursor stream-json stdout; int or None. Never raises."""
    try:
        if not isinstance(stdout, str) or not stdout:
            return None
        call_ids = set()
        object_count = 0
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if not isinstance(obj, dict) or obj.get("type") != "tool_call":
                continue
            object_count += 1
            cid = obj.get("call_id")
            if isinstance(cid, str) and cid:
                call_ids.add(cid)
        if object_count == 0:
            return 0
        if call_ids:
            return len(call_ids)
        return object_count
    except Exception:
        return None


def _read_stdout_tail(path, max_bytes):
    """Return (text, truncated). Read the last <=max_bytes of `path` as BINARY and decode utf-8 with
    errors='ignore' so a partial leading multibyte char at the window edge is dropped harmlessly (the
    trailing result JSON is intact). `truncated` is True iff the file was larger than the window."""
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        if size <= max_bytes:
            fh.seek(0)
            return fh.read().decode("utf-8", errors="ignore"), False
        fh.seek(size - max_bytes)
        return fh.read().decode("utf-8", errors="ignore"), True


def prompt_path_ok(path):
    """(ok, reason). A dispatch prompt must be a readable REGULAR file with non-whitespace content.
    Everything else fails closed so an empty/absent prompt never reaches an engine that then blocks
    reading stdin (#563 stdin-hang repro: codex `exec` told to read stdin + an open/empty stdin =
    hang). We stat BEFORE reading so a FIFO/device/dir never blocks or is read."""
    try:
        st = os.stat(path)
    except OSError:
        return False, "missing"
    if not _stat.S_ISREG(st.st_mode):
        return False, "not-regular-file"
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            content = fh.read()
    except OSError:
        return False, "unreadable"
    if not content.strip():
        return False, "empty"
    return True, ""


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


def _scrub_finding_value(val):
    """Recursively scrub every string in a finding field value."""
    if isinstance(val, str):
        return _scrub(val)
    if isinstance(val, dict):
        return {k: _scrub_finding_value(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_scrub_finding_value(x) for x in val]
    return val


def _scrub_findings(findings):
    out = []
    for f in findings if isinstance(findings, list) else []:
        if not isinstance(f, dict):
            continue
        g = dict(f)
        for key, val in g.items():
            if key in _FINDING_STRUCTURAL_KEYS:
                continue
            g[key] = _scrub_finding_value(val)
        out.append(g)
    return out


def _scrub_mapping(obj):
    """Recursively scrub every string key and value in a mapping tree."""
    if isinstance(obj, str):
        return _scrub(obj)
    if isinstance(obj, dict):
        out = {}
        for idx, (k, v) in enumerate(obj.items()):
            new_k = _scrub(k) if isinstance(k, str) else k
            out_key = new_k
            if out_key in out:
                # axis: entry-preserving scrubbed-key collision disambiguation by position.
                out_key = f"{new_k}#{idx}"
                while out_key in out:
                    idx += 1
                    out_key = f"{new_k}#{idx}"
            out[out_key] = _scrub_mapping(v)
        return out
    if isinstance(obj, list):
        return [_scrub_mapping(x) for x in obj]
    return obj


def scrub_salvage_block(salvage):
    """Scrub every string in a salvage block for durable export. Never raises."""
    # axis: that every string leaving salvage is scrubbed — keys, structural values, all fields.
    if not isinstance(salvage, dict):
        return salvage
    return _scrub_mapping(salvage)


def _scrub_investigated(investigated):
    if not isinstance(investigated, list):
        return []
    out = []
    for entry in investigated:
        if not isinstance(entry, str) or not entry.strip():
            continue
        out.append(_scrub(entry))
    return out


def _bound_top_level_keys(obj):
    """Scrub and bound engine-controlled dict keys for the payload-shape diagnostic."""
    keys = []
    keys_truncated = False
    for i, k in enumerate(obj.keys()):
        if i >= PAYLOAD_SHAPE_MAX_KEYS:
            keys_truncated = True
            break
        key = _scrub(str(k))
        if len(key) > PAYLOAD_SHAPE_MAX_KEY_LEN:
            keys_truncated = True
            key = key[:PAYLOAD_SHAPE_MAX_KEY_LEN]
        keys.append(key)
    return keys, keys_truncated


def review_payload_shape(stdout):
    """Diagnose WHY a review stdout failed the findings parse.

    Returns {"parsed": <one of REVIEW_PAYLOAD_SHAPES>,
             "topLevelKeys": [str, ...],      # [] unless `parsed` == "object-without-findings"
             "keysTruncated": bool}
    Returns None when `stdout` DOES parse as a valid review payload — there is nothing to diagnose.
    Never raises."""
    try:
        stdout = _unwrap_stream_envelope(stdout)
        if not isinstance(stdout, str) or not stdout.strip():
            return {"parsed": SHAPE_EMPTY_STDOUT, "topLevelKeys": [], "keysTruncated": False}
        obj = _last_json_object(stdout)
        if isinstance(obj, dict):
            if "findings" not in obj:
                top_keys, keys_truncated = _bound_top_level_keys(obj)
                return {"parsed": SHAPE_OBJECT_WITHOUT_FINDINGS,
                        "topLevelKeys": top_keys, "keysTruncated": keys_truncated}
            findings = obj.get("findings")
            if not isinstance(findings, list):
                return {"parsed": SHAPE_OBJECT_FINDINGS_NOT_A_LIST,
                        "topLevelKeys": [], "keysTruncated": False}
            return None
        if obj is None:
            arr = _last_json_array(stdout)
            if isinstance(arr, list):
                if all(isinstance(x, dict) for x in arr):
                    return None
                return {"parsed": SHAPE_ARRAY_NOT_ALL_OBJECTS,
                        "topLevelKeys": [], "keysTruncated": False}
            return {"parsed": SHAPE_NO_PARSEABLE_JSON,
                    "topLevelKeys": [], "keysTruncated": False}
        return {"parsed": SHAPE_NO_PARSEABLE_JSON,
                "topLevelKeys": [], "keysTruncated": False}
    except Exception:
        # A diagnostic that cannot diagnose says nothing — never fabricate a parsed label from an
        # internal error (no-parseable-json is a finding about stdout, not a guess after failure).
        return None


def _review_residue(stdout, fed_prompt):
    """Unwrap stream-json envelope, strip echoed prompt, return graded residue. Never raises."""
    try:
        text = stdout if isinstance(stdout, str) else ""
        text = _unwrap_stream_envelope(text)
        if not isinstance(text, str):
            text = ""
        prompt = fed_prompt if isinstance(fed_prompt, str) else ""
        stripped = strip_echoed_prompt(text, prompt)
        if not isinstance(stripped, str) or not stripped.strip():
            return ""
        return stripped
    except Exception:
        return ""


def salvage_write_report(engine, role_kind, stdout, fed_prompt):
    """Recover a build/fix implementer's report from raw engine stdout. Never raises.

    In the structured tier, `truncated` means a partial JSON fragment followed a complete
    report. In the prose tier, it means the manual-read excerpt was capped by byte length.
    """
    try:
        if role_kind == "review" or not isinstance(stdout, str) or not stdout.strip():
            return None
        text = _unwrap_stream_envelope(stdout)
        if not isinstance(text, str):
            return None
        prompt = fed_prompt if isinstance(fed_prompt, str) else ""
        residue = strip_echoed_prompt(text, prompt)
        if not isinstance(residue, str) or not residue.strip():
            return None

        # A partial prompt echo can retain its example verdict even when the wider prompt was not
        # removable verbatim. Do not turn that template object into an implementer claim.
        residue_objects = _top_level_json_matches(residue, dict)
        prompt_objects = _top_level_json_matches(prompt, dict)
        if (_artifact_is_prompt_echo_residue(residue, prompt) or
                any(residue_object[0] == prompt_object[0]
                    for residue_object in residue_objects
                    for prompt_object in prompt_objects)):
            return None

        report_obj = extract_write_report(residue)
        if report_obj is not None:
            parsed = _grade_build_report_obj(report_obj)
            if parsed.get("reason") == "unreadable":
                return None
            report = {
                "ok": parsed.get("ok") is True,
                "signal": parsed.get("signal"),
                "evidence": {
                    "testFailed": bool(parsed.get("evidence", {}).get("testFailed")),
                    "testPassed": bool(parsed.get("evidence", {}).get("testPassed")),
                },
            }
            if not isinstance(report["signal"], str):
                return None
            lines = residue.split("\n")
            last_idx = None
            for i, line in enumerate(lines):
                if line.strip() == WRITE_REPORT_SENTINEL:
                    last_idx = i
            suffix = "\n".join(lines[last_idx:]) if last_idx is not None else residue
            complete_values = _top_level_json_matches(suffix)
            tail = suffix.strip()[complete_values[-1][2]:] if complete_values else suffix
            json_like_tail = bool(re.match(r'^\s*(?:\{\s*(?:"|\})|\[)', tail))
            truncated = json_like_tail and _last_json_object(tail) is None and \
                _last_json_array(tail) is None
            return scrub_salvage_block({
                "report": report,
                "structured": True,
                "requiresManualRead": False,
                "salvaged": True,
                "truncated": truncated,
            })

        residue_bytes = len(residue.encode("utf-8"))
        if (residue_bytes < ARTIFACT_MIN_RESIDUE_BYTES or
                _artifact_is_prompt_echo_residue(residue, prompt) or
                _artifact_is_traceback_residue(residue)):
            return None
        excerpt_raw = residue.encode("utf-8")[:ARTIFACT_EXCERPT_BYTES]
        return {
            "report": None,
            "structured": False,
            "requiresManualRead": True,
            "excerpt": _scrub(excerpt_raw.decode("utf-8", errors="ignore")),
            "excerptBytes": len(excerpt_raw),
            "salvaged": True,
            "truncated": residue_bytes > ARTIFACT_EXCERPT_BYTES,
        }
    except Exception:
        return None


def _artifact_residue_bytes(residue):
    if not isinstance(residue, str):
        return 0
    return len(residue.encode("utf-8"))


def _artifact_citations(residue):
    if not isinstance(residue, str) or not residue:
        return 0
    return len(set(_ARTIFACT_CITATION_RE.findall(residue)))


def _artifact_enumerations(residue):
    if not isinstance(residue, str) or not residue:
        return 0
    return len(_ARTIFACT_ENUM_LINE_RE.findall(residue))


def _artifact_sections(residue):
    """Recognised review section headings, lowercased, in document order. Never raises."""
    if not isinstance(residue, str) or not residue:
        return []
    found = []
    seen = set()
    for line in residue.splitlines():
        line_stripped = line.strip()
        if not line_stripped:
            continue
        line_lower = line_stripped.lower()
        for name in ARTIFACT_SECTION_NAMES:
            if name in seen:
                continue
            if re.match(r"#+\s*" + re.escape(name) + r"\s*:?\s*$", line_lower):
                found.append(name)
                seen.add(name)
            elif line_lower.rstrip(":") == name:
                found.append(name)
                seen.add(name)
    return found


def _artifact_is_prompt_echo_residue(residue, fed_prompt):
    """Reject residue that is an echoed fragment of the fed prompt (BC-5 partial-echo case)."""
    if not isinstance(residue, str) or not residue:
        return False
    if not isinstance(fed_prompt, str) or not fed_prompt:
        return False
    return residue in fed_prompt


def _artifact_is_traceback_residue(residue):
    if not isinstance(residue, str) or not residue:
        return False
    for line in residue.splitlines():
        if line.strip():
            return _ARTIFACT_TRACEBACK_FIRST_LINE_RE.match(line.strip()) is not None
    return False


def review_artifact_shape(stdout, fed_prompt):
    """Detect whether stdout holds a review-shaped artifact after prompt echo is stripped.

    Unwraps a cursor stream-json envelope first, then applies the same echo strip as
    ``engine_dispatch._grade_review_attempt`` (``strip_echoed_prompt`` on the unwrapped text).
    When the strip yields empty-or-whitespace, the residue is empty and the artifact is **not**
    engaged — never fall back to raw stdout.

    Citations match a ``path.ext:line`` shape anywhere in the residue, **including inside fenced
    code blocks** (a citation-shaped token in a fence is counted).

    Engaged when ``residueBytes >= ARTIFACT_MIN_RESIDUE_BYTES`` and at least two of: citations ≥ 1,
    enumerations ≥ 2, sections ≥ 1. ``basis`` names which signals held (sorted); otherwise
    ``engaged: False`` and ``basis: None``.

    Error direction (honest): a long engine error dump that happens to carry citations and bullets
    can read as engaged. That is bounded, not fixed, here — consumers keep the outcome a forfeit,
    never credit the seat, and verify any finding independently. This must **never** be read as
    evidence a seat was *inert* (``engagement_read`` already refuses ``inert``).

    Never raises."""
    try:
        residue = _review_residue(stdout, fed_prompt)
        residue_bytes = _artifact_residue_bytes(residue)
        citations = _artifact_citations(residue)
        enumerations = _artifact_enumerations(residue)
        sections = _artifact_sections(residue)
        shape = {
            "engaged": False,
            "residueBytes": residue_bytes,
            "citations": citations,
            "enumerations": enumerations,
            "sections": sections,
            "basis": None,
        }
        if not residue.strip():
            return shape
        if _artifact_is_prompt_echo_residue(residue, fed_prompt):
            return shape
        if _artifact_is_traceback_residue(residue):
            return shape
        if residue_bytes < ARTIFACT_MIN_RESIDUE_BYTES:
            return shape
        signals = []
        if citations >= 1:
            signals.append("citations")
        if enumerations >= 2:
            signals.append("enumerations")
        if len(sections) >= 1:
            signals.append("sections")
        if len(signals) >= ARTIFACT_MIN_SIGNALS:
            shape["engaged"] = True
            shape["basis"] = sorted(signals)
        return shape
    except Exception:
        return {
            "engaged": False,
            "residueBytes": 0,
            "citations": 0,
            "enumerations": 0,
            "sections": [],
            "basis": None,
        }


def salvage_from_artifact(stdout, fed_prompt):
    """Salvage structured findings or a scrubbed prose excerpt from review stdout.

    Uses the same residue path as ``review_artifact_shape``. When ``parse_result`` yields
    non-empty findings, returns them (``structured: True``). **Never** heuristically splits prose
    into findings — manufacturing claims from prose is worse than handing over the artifact.

    ``structured: True`` means findings were genuinely parsed — not merely that ``parse_result``
    returned ok. When ``parse_result`` returns ok with an **empty** findings list on residue that
    ``review_artifact_shape`` reports as **engaged**, that is a false clean (e.g. incidental bare
    ``[]`` in prose): return ``structured: False``, ``requiresManualRead: True``, and the excerpt.
    Genuinely structured empty JSON (non-engaged residue) may still report ``structured: True``
    with zero findings.

    When ``review_artifact_shape`` reports ``engaged: True`` but this returns ``structured: False``,
    callers must treat ``requiresManualRead: True`` and use ``excerpt`` as the human/orchestrator
    pointer — do not coerce prose into the findings transport.

    Every returned string (``excerpt`` and all free-text in structured ``findings``) passes through
    the module's existing scrub seam (``_scrub`` / ``_scrub_findings``). Never raises."""
    try:
        residue = _review_residue(stdout, fed_prompt)
        excerpt_raw = residue.encode("utf-8")[:ARTIFACT_EXCERPT_BYTES]
        excerpt = _scrub(excerpt_raw.decode("utf-8", errors="ignore"))
        excerpt_bytes = len(excerpt_raw)
        parsed = parse_result("codex", "review", residue)
        if parsed.get("ok") and isinstance(parsed.get("findings"), list):
            findings = parsed["findings"]
            if findings:
                return scrub_salvage_block({
                    "findings": findings,
                    "structured": True,
                    "requiresManualRead": False,
                    "excerptBytes": excerpt_bytes,
                    "excerpt": excerpt,
                })
            engaged = review_artifact_shape(stdout, fed_prompt).get("engaged")
            if engaged:
                return scrub_salvage_block({
                    "findings": [],
                    "structured": False,
                    "requiresManualRead": True,
                    "excerptBytes": excerpt_bytes,
                    "excerpt": excerpt,
                })
            return scrub_salvage_block({
                "findings": [],
                "structured": True,
                "requiresManualRead": False,
                "excerptBytes": excerpt_bytes,
                "excerpt": excerpt,
            })
        return {
            "findings": [],
            "structured": False,
            "requiresManualRead": bool(residue.strip()),
            "excerptBytes": excerpt_bytes,
            "excerpt": excerpt,
        }
    except Exception:
        return {
            "findings": [],
            "structured": False,
            "requiresManualRead": False,
            "excerptBytes": 0,
            "excerpt": "",
        }


def engagement_read(result):
    """The single home for "did this seat demonstrably act?".

    ACTION-BASED ONLY. Never tokens, never wall time, never stdout size.
    `result` is a dispatch-result-shaped mapping (it may carry "findings", "investigated",
    and an "engagement" mapping with "toolCalls").

    Returns "engaged" when there is POSITIVE evidence of action:
      - at least one finding returned, OR
      - at least one accepted `investigated` path, OR
      - engagement.toolCalls is not None and >= 1
    Otherwise returns "unknown".

    NEVER returns "inert". Absence of positive evidence is NOT proof of inaction — a correct
    payload the transport could not read (the #687 verdict-shape specimen) looks identical to a
    seat that never ran. Only `seat_canary probe` can justify asserting inertness.
    Does not look at `ok` — a forfeited seat that nevertheless returned findings is still
    "engaged". Never raises."""
    try:
        if not isinstance(result, dict):
            return "unknown"
        findings = result.get("findings")
        if isinstance(findings, list) and findings:
            return "engaged"
        investigated = result.get("investigated")
        if isinstance(investigated, list) and investigated:
            return "engaged"
        eng = result.get("engagement")
        if not isinstance(eng, dict):
            eng = {}
        # Token spend cannot separate engaged from vacuous, and an absolute floor would classify backwards.
        # Measured 2026-07-26 on codex 0.144.1 in this repo: a genuinely engaged clean review that read
        # repo files spent 2,460 tokens, while the field's vacuous seat (issue #666) spent ~23,000 — ten
        # times more — because prompt ingestion dominates. Engaged runs here ranged 2,460 → 34,857 tokens.
        # Wall time is equally unusable: an engaged dispatch returned a Critical finding in 8 seconds.
        # Only *actions* count — findings produced, files provably read, tools invoked.
        tool_calls = eng.get("toolCalls")
        if tool_calls is not None:
            try:
                if tool_calls >= 1:
                    return "engaged"
            except TypeError:
                pass
        return "unknown"
    except Exception:
        return "unknown"


def _resolve_generated_artifact_reals(generated_artifacts, repo_root):
    """Resolve existing generated-artifact paths once; never raises."""
    artifact_reals = []
    if generated_artifacts is None:
        return artifact_reals
    if isinstance(generated_artifacts, (str, bytes)):
        return artifact_reals
    try:
        entries = iter(generated_artifacts)
    except TypeError:
        return artifact_reals
    for entry in entries:
        if not isinstance(entry, str) or not entry.strip():
            continue
        try:
            real = os.path.realpath(os.path.join(repo_root, entry))
            if os.path.exists(real):
                artifact_reals.append(real)
        except Exception:
            pass
    return artifact_reals


def _matches_generated_artifact(real, artifact_reals):
    """Compare resolved identity, not spelling; never raises."""
    for art_real in artifact_reals:
        try:
            if os.path.samefile(real, art_real):
                return True
        except OSError:
            try:
                if os.path.realpath(real) == art_real:
                    return True
            except Exception:
                pass
    return False


def spot_check_investigated(investigated, repo_root, *, generated_artifacts=()):
    """(ok, accepted, rejected) — does this seat's investigation record survive a reality check?

    A spot check, not an audit: at least one claimed path must resolve inside the repo and exist.
    One verifiable path is enough to distinguish a seat that read the repo from one that read
    nothing; requiring every entry would fail an honest seat that cited a path deleted by the diff.
    Paths listed in `generated_artifacts` (repo-root-relative) are rejected — they do not count
    toward the floor. Never raises."""
    accepted = []
    rejected = []

    def _reject(entry, reason):
        rejected.append({"path": entry, "reason": reason})

    if not isinstance(investigated, list) or not investigated:
        return False, [], rejected
    if not repo_root or not isinstance(repo_root, str) or not os.path.isdir(repo_root):
        for entry in investigated:
            _reject(entry, "no-repo")
        return False, [], rejected

    root_real = os.path.realpath(repo_root)
    root_prefix = root_real + os.sep
    artifact_reals = _resolve_generated_artifact_reals(generated_artifacts, repo_root)

    for entry in investigated:
        if not isinstance(entry, str) or not entry.strip():
            _reject(entry, "not-a-path")
            continue
        if os.path.isabs(entry):
            _reject(entry, "absolute")
            continue
        real = os.path.realpath(os.path.join(repo_root, entry))
        if real != root_real and not real.startswith(root_prefix):
            _reject(entry, "escapes-repo")
            continue
        if not os.path.exists(real):
            _reject(entry, "missing")
            continue
        if not os.path.isfile(real):
            _reject(entry, "not-a-file")
            continue
        if artifact_reals and _matches_generated_artifact(real, artifact_reals):
            _reject(entry, "generated-artifact")
            continue
        accepted.append(entry)

    return len(accepted) >= 1, accepted, rejected


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
            investigated = []
            if isinstance(obj, dict):
                investigated = _scrub_investigated(obj.get("investigated"))
            return {"ok": True, "findings": _scrub_findings(findings),
                    "investigated": investigated}
        if obj is None:
            return {"ok": False, "reason": "unreadable"}
        return _grade_build_report_obj(obj)
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

    if args.prompt_path is not None:
        ok, why = prompt_path_ok(args.prompt_path)
        if not ok:
            sys.stdout.write(json.dumps(
                {"ok": False, "reason": "empty-prompt", "detail": why,
                 "path": args.prompt_path}) + "\n")
            return 0

    effort = args.effort
    if isinstance(effort, str) and not effort.strip():
        effort = None
    opts = {"cwd": args.cwd, "schema_path": args.schema_path, "model": args.model,
            "engine_model": args.engine_model}
    res = build_argv_result(args.engine, args.role, effort, opts)
    if res["reason"] is not None:
        sys.stdout.write(json.dumps(
            {"ok": False, "reason": "engine-config", "detail": res["reason"], "argv": []}) + "\n")
    else:
        sys.stdout.write(json.dumps(res["argv"]) + "\n")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(prog="engine_adapter")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build-argv")
    b.add_argument("--engine", required=True, choices=("codex", "cursor"))
    b.add_argument("--role", required=True, choices=("review", "build", "fix"))
    b.add_argument("--effort", default=None)
    b.add_argument("--cwd", default=None)
    b.add_argument("--schema-path", default=None)
    b.add_argument("--model", default=None,
                   help="native Claude tier short name (haiku/sonnet/opus/fable); non-tier values refuse")
    b.add_argument("--engine-model", default=None,
                   help="registry model id or composed dispatch token for the selected engine")
    b.add_argument("--verify", action="append", default=None,
                   help="PATH:SHA256 staged-input check; any mismatch/unreadable file fails build-argv closed")
    b.add_argument("--prompt-path", default=None,
                   help="if set, fail build-argv closed unless PATH is a readable regular file with "
                        "non-whitespace content (prevents dispatching an empty prompt that would hang "
                        "codex on stdin — #563)")
    _PARSE_RESULT_HELP = (
        "Parse engine stdout. This path never sees the dispatched prompt, so it cannot strip an "
        "echoed prompt; an empty-findings result here is unverified — apply the investigation floor "
        "manually. The library path (parse_result with prompt-stripped stdout) performs the strip."
    )
    pr = sub.add_parser(
        "parse-result",
        description=_PARSE_RESULT_HELP,
        help="parse stdout (no prompt → no echo strip; empty findings unverified)",
    )
    pr.add_argument("--engine", required=True, choices=("codex", "cursor"))
    pr.add_argument(
        "--role",
        required=True,
        choices=("review", "build", "fix"),
        help="dispatch role; for review, empty findings from this CLI are unverified (no echo strip)",
    )
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
            _raw, _truncated = _read_stdout_tail(args.stdout_path, MAX_STDOUT_TAIL_BYTES)
        else:
            _raw, _truncated = sys.stdin.read(), False
        res = parse_result(args.engine, args.role, _raw)
        # A truncated tail can only be TRUSTED when it is the whole stream; once the read was
        # truncated the bounded window may have cut off the true final value's start (or contain an
        # earlier ok-parsing object that is NOT the final leaf), so re-read the full file and use
        # that — a truncated tail is never authoritative. The bounded read stays a fast path for the
        # common (<= MAX_STDOUT_TAIL_BYTES) case; a larger stdout degrades to a full read (kept
        # affordable by the plausible-start scan), never a wedge (#563 DoD5).
        if _truncated:
            with open(args.stdout_path, encoding="utf-8", errors="ignore") as _fh:
                res = parse_result(args.engine, args.role, _fh.read())
        sys.stdout.write(json.dumps(res) + "\n")
        return 0
    if args.cmd == "commit":
        res = commit_result(args.worktree, args.task_id, args.pre_sha)
        sys.stdout.write(json.dumps(res) + "\n")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
