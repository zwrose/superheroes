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
from collections import namedtuple

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
import audits  # noqa: E402  (AUDIT_RULINGS + usability predicates; stdlib-only sibling)
import dispatch_outcome  # noqa: E402  (stdlib-only chokepoint; must not import engine_adapter)
import payload_contracts  # noqa: E402  (single contract home below this layer; no upward import)
import review_findings_schema  # noqa: E402  (findings-member schema home; #1145)
import round_phases  # noqa: E402  (verifier-verdict enum home; verification.VERDICTS re-exports same tuple)

REVIEW_FORFEIT_VACUOUS = dispatch_outcome.REASON_VACUOUS

# Re-export result-kind enum for consumers (CONVENTIONS §11 Pattern 1). Producers emit these
# literals; engine_dispatch and drift tests import this name, never restate the tuple.
REVIEW_RESULT_KINDS = ("findings", "verdicts", "grouping", "ruling")

# Rubric severity tiers — re-export from review_findings_schema (single home; #1145).
REVIEW_SEVERITY_TIERS = review_findings_schema.SEVERITY_TIERS

# Bounds for the payload-shape diagnostic. These strings come from ENGINE-CONTROLLED JSON and
# cross the same trust boundary as any other external free text.
PAYLOAD_SHAPE_MAX_KEYS = 12
PAYLOAD_SHAPE_MAX_KEY_LEN = 60

SHAPE_OBJECT_WITHOUT_FINDINGS = "object-without-findings"
SHAPE_OBJECT_BOTH_PAYLOAD_KEYS = "object-both-payload-keys"
SHAPE_OBJECT_FINDINGS_NOT_A_LIST = "object-findings-not-a-list"
SHAPE_OBJECT_VERDICTS_NOT_A_LIST = "object-verdicts-not-a-list"
SHAPE_ARRAY_NOT_ALL_OBJECTS = "array-not-all-objects"
SHAPE_FINDINGS_HOLLOW_MEMBER = "findings-hollow-member"
SHAPE_VERDICTS_HOLLOW_MEMBER = "verdicts-hollow-member"
SHAPE_PLACEHOLDER_LITERAL_REFUSAL = "placeholder-literal-refusal"
SHAPE_NO_PARSEABLE_JSON = "no-parseable-json"
SHAPE_EMPTY_STDOUT = "empty-stdout"
SHAPE_PROMPT_ECHO_ONLY = "prompt-echo-only"

REVIEW_PAYLOAD_SHAPES = (
    SHAPE_OBJECT_WITHOUT_FINDINGS,      # a JSON object parsed, but it carries no recognized payload key
    SHAPE_OBJECT_BOTH_PAYLOAD_KEYS,     # a JSON object parsed with both `findings` and `verdicts` keys
    SHAPE_OBJECT_FINDINGS_NOT_A_LIST,   # a JSON object parsed with a `findings` key that is not a list
    SHAPE_OBJECT_VERDICTS_NOT_A_LIST,   # a JSON object parsed with a `verdicts` key that is not a list
    SHAPE_ARRAY_NOT_ALL_OBJECTS,        # a bare top-level array parsed, but not every element is an object
    SHAPE_FINDINGS_HOLLOW_MEMBER,       # a findings array parsed with at least one hollow object member
    SHAPE_VERDICTS_HOLLOW_MEMBER,       # a verdicts array parsed with at least one hollow object member
    SHAPE_PLACEHOLDER_LITERAL_REFUSAL,  # an item carries a review-base template literal in id or severity
    SHAPE_NO_PARSEABLE_JSON,            # stdout was non-empty but held no parseable top-level JSON value
    SHAPE_EMPTY_STDOUT,                 # stdout was empty or whitespace only
    SHAPE_PROMPT_ECHO_ONLY,             # the seat emitted only an echo of its prompt — graded text empty after strip
)

# Single home is round_phases.VERDICTS; verification.VERDICTS re-exports the same tuple.
VERDICTS = round_phases.VERDICTS

# review-base.md findings JSON template literals — field-exact placeholder refusal (#763).
REVIEW_BASE_TEMPLATE_ID = "<agent-name>-001"
REVIEW_BASE_TEMPLATE_SEVERITY = "Critical | Important | Minor | Nit"

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
    "Example final two lines (placeholders — compose real JSON literals yourself):\n"
    + WRITE_REPORT_SENTINEL + "\n"
    '{"ok": <true or false>, "signal": "<ok | plan_wrong | needs_context>", '
    '"evidence": {"testFailed": <true or false>, "testPassed": <true or false>}}'
)

_REVIEW_RESULT_KIND_DESCRIPTIONS = {
    "findings": (
        "a single JSON object whose payload key is `findings` (a list of finding objects; "
        "include `investigated` when you read repo paths to ground the review)"
    ),
    "verdicts": (
        "a single JSON object whose payload key is `verdicts` (a list of verdict objects)"
    ),
    "grouping": (
        "a single JSON object whose payload key is `grouping` (the synthesis grouping payload)"
    ),
    "ruling": (
        "a single JSON object with top-level `id`, `ruling`, and `reason` keys (an audit ruling)"
    ),
}
if set(_REVIEW_RESULT_KIND_DESCRIPTIONS) != set(REVIEW_RESULT_KINDS):
    raise AssertionError("REVIEW_RESULT_KIND_DESCRIPTIONS must cover REVIEW_RESULT_KINDS exactly")


def REVIEW_RESULT_CONTRACT(expected_result_kind=None):
    """Kind-aware review stdout contract — pinned seats get one kind; unpinned get all four."""
    if expected_result_kind in REVIEW_RESULT_KINDS:
        kind = expected_result_kind
        return (
            "Review result contract (your graded stdout must match this shape):\n"
            "Emit %s as your final stdout with nothing after it.\n"
            % _REVIEW_RESULT_KIND_DESCRIPTIONS[kind]
        )
    kinds_enumerated = ", ".join("`%s`" % k for k in REVIEW_RESULT_KINDS)
    lines = [
        "Review result contract (your graded stdout must match exactly one of these shapes):",
        "The runner accepts these result kinds (%d): %s." % (len(REVIEW_RESULT_KINDS), kinds_enumerated),
        "Emit exactly one matching JSON object as your final stdout with nothing after it.",
    ]
    for kind in REVIEW_RESULT_KINDS:
        lines.append("  - `%s`: %s" % (kind, _REVIEW_RESULT_KIND_DESCRIPTIONS[kind]))
    return "\n".join(lines) + "\n"


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
        # non-interactive CLI invocation (without it it goes interactive and --output-format is a no-op); --trust
        # clears the workspace-trust gate that otherwise HANGS a non-interactive CLI invocation (needed for the
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
    model+effort. opts keys: cwd, model (native Claude tier short name from
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
    """True when the fed write prompt carries the write-report contract.

    Keyed on WRITE_REPORT_SENTINEL (stable) rather than WRITE_REPORT_CONTRACT prose
    (expected to be edited). Fail-closed: a prompt that merely mentions the sentinel
    is treated as contracted and routes to strict tail grading."""
    if not isinstance(fed_prompt, str) or not fed_prompt:
        return False
    return WRITE_REPORT_SENTINEL in fed_prompt


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
        stripped = stripped.replace(WRITE_REPORT_CONTRACT, "")
        if write_prompt_is_contracted(prompt):
            obj = extract_write_report(stripped)
            # Prompt-example guard applies only to the extracted tail object, not prose
            # elsewhere in the output. Safe because the contract's example is non-decodable
            # (test_write_report_contract_has_no_extractable_report), and the tail must
            # carry the sentinel and satisfy strict grammar.
            if obj is None or any(obj == prompt_object[0]
                                  for prompt_object in _top_level_json_matches(prompt, dict)):
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


def _is_stream_result_envelope(obj):
    """True when obj is a cursor stream-json RESULT envelope (not a leaf verdict)."""
    return (isinstance(obj, dict) and obj.get("type") == "result"
            and isinstance(obj.get("result"), str) and "ok" not in obj)


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
    if _is_stream_result_envelope(obj):
        return obj["result"]
    return stdout


def _scrub(text):
    if not isinstance(text, str) or not text:
        return text
    scrubbed, _ok = readout.scrub(text)
    return scrubbed


# Structural keys are NEVER free text (file paths, line numbers, severity/dimension enums,
# confidence scores) — every OTHER string value in a finding dict is untrusted external free text
# (body/suggestion/evidence/title/description/message/id/etc.) and is scrubbed unconditionally so no
# new field name can silently reopen the leak this boundary exists to close.
_FINDING_STRUCTURAL_KEYS = {"file", "line", "severity", "dimension", "confidence"}
# Re-export substance censuses from review_findings_schema — legacy names kept for tests/consumers.
_FINDING_SUBSTANCE_KEYS_CANONICAL = review_findings_schema.SUBSTANCE_KEYS_CANONICAL
_FINDING_SUBSTANCE_KEYS_TOLERATED = review_findings_schema.SUBSTANCE_KEYS_LEGACY
FINDING_REJECT_NO_SUBSTANCE = "no-substantive-fields"


def _finding_is_substantive(obj, *, echo_nonce=None):
    """True when a finding dict carries substantive review content per the schema home."""
    if not isinstance(obj, dict):
        return False
    if review_findings_schema.member_carries_sentinel(obj, nonce=echo_nonce):
        return False
    return review_findings_schema.member_is_engaged(obj)


def _findings_list_has_hollow_member(findings, *, echo_nonce=None):
    """True when a findings array contains at least one hollow object member."""
    if not isinstance(findings, list):
        return False
    return any(
        isinstance(x, dict) and not _finding_is_substantive(x, echo_nonce=echo_nonce)
        for x in findings
    )


def _verdict_is_valid(obj):
    """True when a verdict dict carries id, enum verdict, and non-empty reason."""
    if not isinstance(obj, dict):
        return False
    vid = obj.get("id")
    if not isinstance(vid, str) or not vid.strip():
        return False
    verdict = obj.get("verdict")
    if not isinstance(verdict, str) or not verdict.strip():
        return False
    if verdict not in VERDICTS:
        return False
    reason = obj.get("reason")
    return isinstance(reason, str) and bool(reason.strip())


def _verdicts_list_has_hollow_member(verdicts):
    """True when a verdicts array contains at least one invalid member."""
    if not isinstance(verdicts, list):
        return False
    return any(not _verdict_is_valid(x) for x in verdicts)


def _item_has_placeholder_literal(item):
    """True when an item carries a review-base template literal in id or severity."""
    if not isinstance(item, dict):
        return False
    if item.get("id") == REVIEW_BASE_TEMPLATE_ID:
        return True
    if item.get("severity") == REVIEW_BASE_TEMPLATE_SEVERITY:
        return True
    return False


def _review_items_have_placeholder_literal(items):
    """True when any list member carries a placeholder literal in id or severity."""
    if not isinstance(items, list):
        return False
    return any(_item_has_placeholder_literal(x) for x in items)


_VERDICT_STRUCTURAL_KEYS = {"verdict"}


def _scrub_verdicts(verdicts):
    """Return scrubbed verdict dicts. Caller must reject hollow members first. Never raises."""
    if not isinstance(verdicts, list):
        return []
    accepted = []
    for v in verdicts:
        if not isinstance(v, dict):
            continue
        g = dict(v)
        for key, val in g.items():
            if key in _VERDICT_STRUCTURAL_KEYS:
                continue
            if key == "severity" and val in REVIEW_SEVERITY_TIERS:
                continue
            g[key] = _scrub_finding_value(val)
        accepted.append(g)
    return accepted


def normalize_review_stdout(stdout, fed_prompt=None):
    """Unwrap stream envelope and optionally strip echoed prompt once for review consumers.

    Returns {text, rawEnvelopeError, echoOnly}. Never raises."""
    raw = stdout if isinstance(stdout, str) else ""
    raw_has_content = bool(raw.strip())
    raw_envelope_error = _raw_stream_envelope_has_error_control(raw)
    text = _unwrap_stream_envelope(raw)
    if not isinstance(text, str):
        text = ""
    if fed_prompt is not None:
        prompt = fed_prompt if isinstance(fed_prompt, str) else ""
        text = strip_echoed_prompt(text, prompt)
        if not isinstance(text, str):
            text = ""
    echo_only = raw_has_content and not text.strip()
    return {
        "text": text,
        "rawEnvelopeError": raw_envelope_error,
        "echoOnly": echo_only,
    }


def _review_payload_is_usable(payload):
    """True when a parsed review payload carries substantive content past the #949 gate."""
    if payload is None:
        return False
    if isinstance(payload, (list, dict)):
        return bool(payload)
    return bool(payload)


def _outer_envelope_error_makes_unreadable(outer_envelope_error, payload):
    """Single gate for #949: outer error/control envelope + no usable payload → unreadable."""
    return outer_envelope_error and not _review_payload_is_usable(payload)


def _findings_reply_has_hollow_member(rejected):
    """True when any scrub rejection was for a hollow finding member."""
    return any(r.get("reason") == FINDING_REJECT_NO_SUBSTANCE for r in rejected)


def _scrub_finding_value(val):
    """Recursively scrub every string in a finding field value."""
    if isinstance(val, str):
        return _scrub(val)
    if isinstance(val, dict):
        return {k: _scrub_finding_value(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_scrub_finding_value(x) for x in val]
    return val


def _render_rejection_entry(entry):
    """Render an engine-controlled value safely for rejection records. Never raises."""
    if isinstance(entry, str):
        return _scrub(entry)
    if isinstance(entry, dict):
        return _scrub_mapping(entry)
    try:
        return _scrub(json.dumps(entry))
    except Exception:
        return _scrub(str(entry))


def _scrub_findings(findings, *, echo_nonce=None):
    """Return (accepted, rejected) — reject non-dicts with a named reason, never skip. Never raises."""
    if not isinstance(findings, list):
        return [], []
    accepted = []
    rejected = []
    for f in findings:
        if not isinstance(f, dict):
            rejected.append({"entry": _render_rejection_entry(f), "reason": "not-a-dict"})
            continue
        if not _finding_is_substantive(f, echo_nonce=echo_nonce):
            rejected.append({"entry": _render_rejection_entry(f), "reason": FINDING_REJECT_NO_SUBSTANCE})
            continue
        pre_scrubbed = dict(f)
        for key, val in pre_scrubbed.items():
            if key in _FINDING_STRUCTURAL_KEYS:
                continue
            pre_scrubbed[key] = _scrub_finding_value(val)
        f = review_findings_schema.normalize_member(pre_scrubbed)
        g = dict(f)
        for key, val in g.items():
            if key in _FINDING_STRUCTURAL_KEYS:
                continue
            g[key] = _scrub_finding_value(val)
        accepted.append(g)
    return accepted, rejected


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


_INVESTIGATED_LOCATOR_SUFFIX_RE = re.compile(r":(\d+)(?::(\d+))?$")


def _normalize_investigated_path_string(path_val):
    """Strip surrounding whitespace and wrapping backticks. Never raises."""
    if not isinstance(path_val, str):
        return path_val
    path_val = path_val.strip()
    if len(path_val) >= 2 and path_val[0] == "`" and path_val[-1] == "`":
        path_val = path_val[1:-1].strip()
    return path_val


def _strip_investigated_locator_suffix(path_val, repo_root):
    """Strip a trailing :line or :line:col only when the remainder is an existing regular file."""
    if not repo_root or not isinstance(path_val, str) or not path_val:
        return path_val
    match = _INVESTIGATED_LOCATOR_SUFFIX_RE.search(path_val)
    if not match:
        return path_val
    candidate = path_val[:match.start()]
    if not candidate:
        return path_val
    try:
        root_real = os.path.realpath(repo_root)
        root_prefix = root_real + os.sep
        real = os.path.realpath(os.path.join(repo_root, candidate))
        if real != root_real and not real.startswith(root_prefix):
            return path_val
        if os.path.isfile(real):
            return candidate
    except (OSError, ValueError):
        pass
    return path_val


def _scrub_investigated(investigated):
    """Return (accepted, rejected) — normalize or reject, never drop. Never raises."""
    rejected = []

    def _reject(entry, reason):
        rejected.append({"path": _render_rejection_entry(entry), "reason": reason})

    if not isinstance(investigated, list):
        _reject(investigated, "not-a-list")
        return [], rejected
    accepted = []
    for entry in investigated:
        path_val = None
        if isinstance(entry, str):
            path_val = entry
        elif isinstance(entry, dict):
            raw = entry.get("path")
            if raw is None:
                raw = entry.get("file")
            if raw is None:
                _reject(entry, "object-without-path")
                continue
            if not isinstance(raw, str):
                _reject(entry, "invalid-path")
                continue
            path_val = raw
        else:
            _reject(entry, "not-a-string")
            continue
        path_val = _normalize_investigated_path_string(path_val)
        if not isinstance(path_val, str) or not path_val:
            _reject(entry, "empty-path")
            continue
        accepted.append(_scrub(path_val))
    return accepted, rejected


def _investigated_path_is_placeholder_echo(path_val, *, echo_nonce=None):
    """True when a whole investigated path string is a verbatim/near-copy example placeholder."""
    if not isinstance(path_val, str):
        return False
    placeholders = review_findings_schema.example_member_values(None)
    effective = review_findings_schema.effective_nonce(echo_nonce)
    if effective is not None:
        placeholders = placeholders | review_findings_schema.example_member_values(effective)
    normalized_placeholders = review_findings_schema._normalized_placeholder_set(placeholders)
    normalized = review_findings_schema._near_copy_normalize(path_val)
    return bool(normalized) and normalized in normalized_placeholders


def _investigated_list_all_placeholder_echo(paths, *, echo_nonce=None):
    """True when every accepted investigated path is an example placeholder echo."""
    if not paths:
        return False
    return all(
        _investigated_path_is_placeholder_echo(p, echo_nonce=echo_nonce) for p in paths
    )


# Whitelist for the findings-less near-miss: only objects whose keys are exactly this set
# may be certified clean without a `findings` key. Error/control envelopes are rejected
# before this check; unknown keys fail closed rather than blacklisting every crash shape.
_REVIEW_NEAR_MISS_ALLOWED_KEYS = frozenset({"investigated"})


def _review_object_has_error_control_markers(obj):
    """Shared error/control marker vocabulary for review dicts and stream envelopes."""
    if not isinstance(obj, dict):
        return True
    if "error" in obj or obj.get("is_error"):
        return True
    status = obj.get("status")
    if isinstance(status, str) and status.lower() in ("error", "failed", "failure"):
        return True
    subtype = obj.get("subtype")
    if isinstance(subtype, str) and subtype.lower() in ("error", "failed", "failure"):
        return True
    return False


def _raw_stream_envelope_has_error_control(stdout):
    """True when the LAST top-level object is a stream envelope carrying error/control markers.

    Inspected on raw stdout before _unwrap_stream_envelope discards outer metadata (#949)."""
    obj = _last_json_object(stdout)
    if not _is_stream_result_envelope(obj):
        return False
    return _review_object_has_error_control_markers(obj)


def _parse_review_verdicts_object(obj, outer_envelope_error):
    """Parse a review object carrying a `verdicts` key. Never raises."""
    verdicts = obj.get("verdicts")
    if not isinstance(verdicts, list):
        return {"ok": False, "reason": "unreadable"}
    if _review_items_have_placeholder_literal(verdicts):
        return {"ok": False, "reason": "unreadable"}
    if _verdicts_list_has_hollow_member(verdicts):
        return {"ok": False, "reason": "unreadable"}
    verdicts_list = _scrub_verdicts(verdicts)
    if _outer_envelope_error_makes_unreadable(outer_envelope_error, verdicts_list):
        return {"ok": False, "reason": "unreadable"}
    investigated = []
    inv_rejected = []
    if "investigated" in obj:
        investigated, inv_rejected = _scrub_investigated(obj.get("investigated"))
    result = {"ok": True, "resultKind": "verdicts",
              "verdicts": verdicts_list, "investigated": investigated}
    return _attach_investigated_parse_rejections(result, inv_rejected)


def _matches_review_findings(obj):
    if "findings" in obj:
        return True
    return "investigated" in obj and set(obj.keys()) == _REVIEW_NEAR_MISS_ALLOWED_KEYS


def _matches_review_verdicts(obj):
    return "verdicts" in obj


def _matches_review_grouping(obj):
    return "grouping" in obj


def _audit_ruling_payload_valid(obj):
    """Validate ruling per payload_contracts P_AUDITS contract. Never raises."""
    audit_id = obj.get("id")
    if isinstance(audit_id, str) and not audit_id.strip():
        return False
    return payload_contracts.payload_fault(payload_contracts.P_AUDITS, obj, "") is None


def _matches_review_ruling(obj):
    if not all(key in obj for key in ("id", "ruling", "reason")):
        return False
    ruling = obj.get("ruling")
    if not isinstance(ruling, str) or ruling not in audits.AUDIT_RULINGS:
        return False
    return _audit_ruling_payload_valid(obj)


_REVIEW_CONTRACT_MATCHERS = (
    ("findings", _matches_review_findings),
    ("verdicts", _matches_review_verdicts),
    ("grouping", _matches_review_grouping),
    ("ruling", _matches_review_ruling),
)


def _recognised_review_kinds(obj):
    """Return the registered review result kinds that structurally match `obj`. Never raises."""
    matched = []
    for kind, matcher in _REVIEW_CONTRACT_MATCHERS:
        try:
            if matcher(obj):
                matched.append(kind)
        except Exception:
            pass
    return matched


def _grouping_payload_valid(grouping):
    """Validate synthesis grouping per payload_contracts P_SYNTHESIS contract. Never raises."""
    return payload_contracts.payload_fault(
        payload_contracts.P_SYNTHESIS,
        {"grouping": grouping},
        payload_contracts.SEAT_SYNTHESIS,
    ) is None


def _scrub_grouping(grouping):
    """Scrub synthesis grouping free-text fields. Never raises."""
    if grouping is None:
        return None
    return _scrub_mapping(grouping)


def _parse_review_grouping_object(obj, outer_envelope_error):
    """Parse a review object carrying a `grouping` key. Never raises."""
    grouping = obj.get("grouping")
    if not _grouping_payload_valid(grouping):
        return {"ok": False, "reason": "unreadable"}
    if _outer_envelope_error_makes_unreadable(outer_envelope_error, grouping):
        return {"ok": False, "reason": "unreadable"}
    grouping_scrubbed = _scrub_grouping(grouping)
    investigated = []
    inv_rejected = []
    if "investigated" in obj:
        investigated, inv_rejected = _scrub_investigated(obj.get("investigated"))
    result = {"ok": True, "resultKind": "grouping",
              "grouping": grouping_scrubbed, "investigated": investigated}
    return _attach_investigated_parse_rejections(result, inv_rejected)


def _scrub_ruling_object(obj):
    """Scrub a ruling payload's free-text fields. Never raises."""
    out = {
        "id": _scrub(obj["id"]) if isinstance(obj.get("id"), str) else obj.get("id"),
        "ruling": obj.get("ruling"),
        "reason": _scrub(obj["reason"]) if isinstance(obj.get("reason"), str) else obj.get("reason"),
    }
    for opt in ("newIssues", "evidence", "auditorVendor"):
        if opt in obj:
            val = obj.get(opt)
            if opt == "newIssues" and isinstance(val, list):
                out[opt] = [_scrub_mapping(x) if isinstance(x, dict) else _scrub_finding_value(x)
                            for x in val]
            elif isinstance(val, str):
                out[opt] = _scrub(val)
            else:
                out[opt] = val
    return out


def _parse_review_ruling_object(obj, outer_envelope_error):
    """Parse a review object recognised as an audit ruling. Never raises."""
    if not _audit_ruling_payload_valid(obj):
        return {"ok": False, "reason": "unreadable"}
    if _outer_envelope_error_makes_unreadable(outer_envelope_error, obj):
        return {"ok": False, "reason": "unreadable"}
    ruling_record = _scrub_ruling_object(obj)
    investigated = []
    inv_rejected = []
    if "investigated" in obj:
        investigated, inv_rejected = _scrub_investigated(obj.get("investigated"))
    result = {
        "ok": True,
        "resultKind": "ruling",
        "ruling": ruling_record,
        "investigated": investigated,
    }
    return _attach_investigated_parse_rejections(result, inv_rejected)


def _parse_review_findings_object(obj, outer_envelope_error, *, echo_nonce=None):
    """Parse a review object recognised as findings. Never raises."""
    if "findings" not in obj and "investigated" in obj:
        if (_outer_envelope_error_makes_unreadable(outer_envelope_error, [])
                or set(obj.keys()) != _REVIEW_NEAR_MISS_ALLOWED_KEYS):
            return {"ok": False, "reason": "unreadable"}
        investigated, inv_rejected = _scrub_investigated(obj.get("investigated"))
        if not investigated:
            return {"ok": False, "reason": "unreadable"}
        if _investigated_list_all_placeholder_echo(investigated, echo_nonce=echo_nonce):
            return {"ok": False, "reason": "unreadable"}
        result = {"ok": True, "resultKind": "findings",
                  "findings": [], "investigated": investigated}
        return _attach_investigated_parse_rejections(result, inv_rejected)
    findings = obj.get("findings")
    if findings is None:
        return {"ok": False, "reason": "unreadable"}
    if not isinstance(findings, list):
        return {"ok": False, "reason": "unreadable"}
    if _review_items_have_placeholder_literal(findings):
        return {"ok": False, "reason": "unreadable"}
    findings_list, findings_rejected = _scrub_findings(findings, echo_nonce=echo_nonce)
    if _findings_reply_has_hollow_member(findings_rejected):
        return {"ok": False, "reason": "unreadable"}
    if _outer_envelope_error_makes_unreadable(outer_envelope_error, findings_list):
        return {"ok": False, "reason": "unreadable"}
    if findings and not findings_list:
        return {"ok": False, "reason": "unreadable"}
    investigated = []
    inv_rejected = []
    if "investigated" in obj:
        investigated, inv_rejected = _scrub_investigated(obj.get("investigated"))
        if _investigated_list_all_placeholder_echo(investigated, echo_nonce=echo_nonce):
            return {"ok": False, "reason": "unreadable"}
    result = {"ok": True, "resultKind": "findings",
              "findings": findings_list, "investigated": investigated}
    result = _attach_findings_parse_rejections(result, findings_rejected)
    return _attach_investigated_parse_rejections(result, inv_rejected)


_REVIEW_CONTRACT_PARSERS = {
    "findings": _parse_review_findings_object,
    "verdicts": _parse_review_verdicts_object,
    "grouping": _parse_review_grouping_object,
    "ruling": _parse_review_ruling_object,
}


def _carries_findings(result):
    value = result.get("findings")
    if isinstance(value, list):
        return True, value
    return False, None


def _nonempty_findings(value):
    return bool(value)


def _engaged_findings(value):
    return isinstance(value, list) and bool(value)


def _carries_verdicts(result):
    value = result.get("verdicts")
    if isinstance(value, list):
        return True, value
    return False, None


def _nonempty_verdicts(value):
    return bool(value)


def _engaged_verdicts(value):
    return isinstance(value, list) and bool(value)


def _carries_grouping(result):
    if "grouping" not in result:
        return False, None
    value = result.get("grouping")
    return True, value


def _nonempty_grouping(value):
    return bool(value)


def _engaged_grouping(value):
    return isinstance(value, list) and bool(value)


def _carries_ruling(result):
    value = result.get("ruling")
    if isinstance(value, dict) and value.get("ruling"):
        return True, value
    return False, None


def _nonempty_ruling(value):
    return True


def _engaged_ruling(value):
    if not isinstance(value, dict):
        return False
    return bool(isinstance(value.get("id"), str) and value.get("id")
                and isinstance(value.get("ruling"), str) and value.get("ruling")
                and isinstance(value.get("reason"), str) and value.get("reason"))


_ReviewPayloadSemantics = namedtuple(
    "_ReviewPayloadSemantics", ("key", "carries", "nonempty", "engaged"))

# Third registry beside recognition (_REVIEW_CONTRACT_MATCHERS) and parsing
# (_REVIEW_CONTRACT_PARSERS). A kind registered in either of those without an entry here is
# caught by the exhaustiveness census, not by a runtime branch; runtime behaviour for an
# unregistered kind is fail-closed, and that is deliberate — the loud failure belongs in the
# test, not in production.
_REVIEW_PAYLOAD_SEMANTICS = {
    "findings": _ReviewPayloadSemantics("findings", _carries_findings,
                                         _nonempty_findings, _engaged_findings),
    "verdicts": _ReviewPayloadSemantics("verdicts", _carries_verdicts,
                                        _nonempty_verdicts, _engaged_verdicts),
    "grouping": _ReviewPayloadSemantics("grouping", _carries_grouping,
                                          _nonempty_grouping, _engaged_grouping),
    "ruling": _ReviewPayloadSemantics("ruling", _carries_ruling,
                                      _nonempty_ruling, _engaged_ruling),
}


def review_payload_carried(result, kind):
    """Whether a review result carries a payload for kind, and the value. Never raises."""
    try:
        if not isinstance(result, dict):
            return False, None
        record = _REVIEW_PAYLOAD_SEMANTICS.get(kind)
        if record is None:
            return False, None
        return record.carries(result)
    except Exception:
        return False, None


def review_payload_nonempty(kind, value):
    """Whether a carried payload counts as non-empty for kind. Never raises."""
    try:
        record = _REVIEW_PAYLOAD_SEMANTICS.get(kind)
        if record is None:
            return False
        return record.nonempty(value)
    except Exception:
        return False


def review_payload_engaged(result, kind):
    """Whether a result carries positive-engagement evidence for kind. Never raises."""
    try:
        if not isinstance(result, dict):
            return False
        record = _REVIEW_PAYLOAD_SEMANTICS.get(kind)
        if record is None:
            return False
        carried, value = record.carries(result)
        if not carried:
            return False
        return record.engaged(value)
    except Exception:
        return False


def _attach_investigated_parse_rejections(result, rejected):
    if rejected:
        result["investigatedRejectedRecords"] = rejected
        result["investigatedRejected"] = [r["reason"] for r in rejected]
    return result


def _attach_findings_parse_rejections(result, rejected):
    if rejected:
        result["findingsRejectedRecords"] = rejected
        result["findingsRejected"] = [r["reason"] for r in rejected]
    return result


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


def _review_payload_shape_findings_obj(obj, *, echo_nonce=None):
    """Findings-kind shape diagnostic for a recognised review object. Never raises."""
    if "findings" not in obj:
        investigated = obj.get("investigated")
        if isinstance(investigated, list) and investigated:
            accepted, _ = _scrub_investigated(investigated)
            if accepted:
                if _investigated_list_all_placeholder_echo(accepted, echo_nonce=echo_nonce):
                    return {"parsed": SHAPE_FINDINGS_HOLLOW_MEMBER,
                            "topLevelKeys": [], "keysTruncated": False}
                return None
        top_keys, keys_truncated = _bound_top_level_keys(obj)
        return {"parsed": SHAPE_OBJECT_WITHOUT_FINDINGS,
                "topLevelKeys": top_keys, "keysTruncated": keys_truncated}
    findings = obj.get("findings")
    if not isinstance(findings, list):
        return {"parsed": SHAPE_OBJECT_FINDINGS_NOT_A_LIST,
                "topLevelKeys": [], "keysTruncated": False}
    if _review_items_have_placeholder_literal(findings):
        return {"parsed": SHAPE_PLACEHOLDER_LITERAL_REFUSAL,
                "topLevelKeys": [], "keysTruncated": False}
    if _findings_list_has_hollow_member(findings, echo_nonce=echo_nonce):
        return {"parsed": SHAPE_FINDINGS_HOLLOW_MEMBER,
                "topLevelKeys": [], "keysTruncated": False}
    investigated = obj.get("investigated")
    if isinstance(investigated, list) and investigated:
        accepted, _ = _scrub_investigated(investigated)
        if accepted and _investigated_list_all_placeholder_echo(
                accepted, echo_nonce=echo_nonce):
            return {"parsed": SHAPE_FINDINGS_HOLLOW_MEMBER,
                    "topLevelKeys": [], "keysTruncated": False}
    return None


def _review_payload_shape_verdicts_obj(obj):
    """Verdicts-kind shape diagnostic for a recognised review object. Never raises."""
    verdicts = obj.get("verdicts")
    if not isinstance(verdicts, list):
        return {"parsed": SHAPE_OBJECT_VERDICTS_NOT_A_LIST,
                "topLevelKeys": [], "keysTruncated": False}
    if _review_items_have_placeholder_literal(verdicts):
        return {"parsed": SHAPE_PLACEHOLDER_LITERAL_REFUSAL,
                "topLevelKeys": [], "keysTruncated": False}
    if _verdicts_list_has_hollow_member(verdicts):
        return {"parsed": SHAPE_VERDICTS_HOLLOW_MEMBER,
                "topLevelKeys": [], "keysTruncated": False}
    return None


def _review_payload_shape_grouping_obj(obj):
    """Grouping-kind shape diagnostic for a recognised review object. Never raises."""
    if _grouping_payload_valid(obj.get("grouping")):
        return None
    top_keys, keys_truncated = _bound_top_level_keys(obj)
    return {"parsed": SHAPE_OBJECT_WITHOUT_FINDINGS,
            "topLevelKeys": top_keys, "keysTruncated": keys_truncated}


def _review_payload_shape_ruling_obj(obj):
    """Ruling-kind shape diagnostic for a recognised review object. Never raises."""
    if _matches_review_ruling(obj) and _audit_ruling_payload_valid(obj):
        return None
    top_keys, keys_truncated = _bound_top_level_keys(obj)
    return {"parsed": SHAPE_OBJECT_WITHOUT_FINDINGS,
            "topLevelKeys": top_keys, "keysTruncated": keys_truncated}


_REVIEW_PAYLOAD_SHAPE_DIAGNOSTICS = {
    "findings": _review_payload_shape_findings_obj,
    "verdicts": _review_payload_shape_verdicts_obj,
    "grouping": _review_payload_shape_grouping_obj,
    "ruling": _review_payload_shape_ruling_obj,
}


def review_payload_shape(stdout, fed_prompt=None, *, echo_nonce=None):
    """Diagnose WHY a review stdout failed the findings parse.

    Returns {"parsed": <one of REVIEW_PAYLOAD_SHAPES>,
             "topLevelKeys": [str, ...],      # [] unless `parsed` is object-without-findings
                                               # or object-both-payload-keys
             "keysTruncated": bool}
    Returns None when `stdout` DOES parse as a valid review payload — there is nothing to diagnose.
    Never raises."""
    try:
        norm = normalize_review_stdout(stdout, fed_prompt)
        if norm["echoOnly"]:
            return {"parsed": SHAPE_PROMPT_ECHO_ONLY, "topLevelKeys": [], "keysTruncated": False}
        stdout = norm["text"]
        if not isinstance(stdout, str) or not stdout.strip():
            return {"parsed": SHAPE_EMPTY_STDOUT, "topLevelKeys": [], "keysTruncated": False}
        obj = _last_json_object(stdout)
        if isinstance(obj, dict):
            matched = _recognised_review_kinds(obj)
            if len(matched) > 1:
                top_keys, keys_truncated = _bound_top_level_keys(obj)
                return {"parsed": SHAPE_OBJECT_BOTH_PAYLOAD_KEYS,
                        "topLevelKeys": top_keys, "keysTruncated": keys_truncated}
            if len(matched) == 1:
                if matched[0] == "findings":
                    diag = _review_payload_shape_findings_obj(obj, echo_nonce=echo_nonce)
                else:
                    diag = _REVIEW_PAYLOAD_SHAPE_DIAGNOSTICS[matched[0]](obj)
                if diag is not None:
                    return diag
                return None
            top_keys, keys_truncated = _bound_top_level_keys(obj)
            return {"parsed": SHAPE_OBJECT_WITHOUT_FINDINGS,
                    "topLevelKeys": top_keys, "keysTruncated": keys_truncated}
        if obj is None:
            arr = _last_json_array(stdout)
            if isinstance(arr, list):
                if all(isinstance(x, dict) for x in arr):
                    if _review_items_have_placeholder_literal(arr):
                        return {"parsed": SHAPE_PLACEHOLDER_LITERAL_REFUSAL,
                                "topLevelKeys": [], "keysTruncated": False}
                    if _findings_list_has_hollow_member(arr, echo_nonce=echo_nonce):
                        return {"parsed": SHAPE_FINDINGS_HOLLOW_MEMBER,
                                "topLevelKeys": [], "keysTruncated": False}
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
        norm = normalize_review_stdout(stdout, fed_prompt)
        return norm["text"] if norm["text"].strip() else ""
    except Exception:
        return ""


def salvage_write_report(engine, role_kind, stdout, fed_prompt):
    """Recover a build/fix implementer's report from raw engine stdout. Never raises.

    In the prose tier, `truncated` means the manual-read excerpt was capped by byte length
    on the scrubbed residue (the excerpt carries the tail of the scrubbed text, where the
    report usually lives). `excerptBytes` counts bytes from that scrubbed tail slice.
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
        residue = residue.replace(WRITE_REPORT_CONTRACT, "")

        # A partial prompt echo can retain its example verdict even when the wider prompt was not
        # removable verbatim. Do not turn that template object into an implementer claim.
        # Salvage is deliberately stricter than grading — the broad guard was kept while grading
        # was narrowed (PR #969); the divergence is accepted, and the fail direction is a lost
        # recovery aid on an already-forfeited path, never a false success.
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
            return scrub_salvage_block({
                "report": report,
                "structured": True,
                "requiresManualRead": False,
                "salvaged": True,
            })

        residue_bytes = len(residue.encode("utf-8"))
        if (residue_bytes < ARTIFACT_MIN_RESIDUE_BYTES or
                _artifact_is_prompt_echo_residue(residue, prompt) or
                _artifact_is_traceback_residue(residue)):
            return None
        residue_scrubbed = _scrub(residue)
        residue_scrubbed_encoded = residue_scrubbed.encode("utf-8")
        truncated = len(residue_scrubbed_encoded) > ARTIFACT_EXCERPT_BYTES
        if truncated:
            excerpt_raw = residue_scrubbed_encoded[-ARTIFACT_EXCERPT_BYTES:]
        else:
            excerpt_raw = residue_scrubbed_encoded
        return {
            "report": None,
            "structured": False,
            "requiresManualRead": True,
            "excerpt": excerpt_raw.decode("utf-8", errors="ignore"),
            "excerptBytes": len(excerpt_raw),
            "salvaged": True,
            "truncated": truncated,
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


def salvage_from_artifact(stdout, fed_prompt, *, echo_nonce=None):
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
        parsed = parse_result("codex", "review", residue, echo_nonce=echo_nonce)
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
      - a non-empty payload of any registered review result kind, OR
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
        for kind in REVIEW_RESULT_KINDS:
            if review_payload_engaged(result, kind):
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
        raw_entry = entry
        if not isinstance(entry, str):
            _reject(raw_entry, "not-a-path")
            continue
        entry = _normalize_investigated_path_string(entry)
        if not entry:
            _reject(raw_entry, "not-a-path")
            continue
        entry = _strip_investigated_locator_suffix(entry, repo_root)
        if "\x00" in entry:
            _reject(entry, "invalid-path")
            continue
        if os.path.isabs(entry):
            _reject(entry, "absolute")
            continue
        try:
            real = os.path.realpath(os.path.join(repo_root, entry))
        except (OSError, ValueError):
            _reject(entry, "invalid-path")
            continue
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


def parse_result(engine, role_kind, stdout, *, raw_envelope_error=None, echo_nonce=None):
    """Parse an external engine's stdout into the native result shape. review → scrubbed
    findings (from the canonical {"findings": [...]} object OR, tolerated, a bare top-level
    array of finding objects — #196); build|fix → {ok,signal,evidence{testFailed,testPassed}}
    honoring the leaf's OWN ok/signal (an honest {"ok":false,"signal":"plan_wrong"} refusal stays
    ok:false so it parks — never coerced to ok:true and committed, #288).
    Unparseable/empty → {ok:false, reason:'unreadable'}. External free-text is
    scrubbed HERE (Secret-hygiene). When `raw_envelope_error` is supplied it is used verbatim
    for the #949 gate — never re-derived from already-normalized text. Never raises."""
    try:
        if role_kind == "review":
            norm = normalize_review_stdout(stdout)
            outer_envelope_error = (
                norm["rawEnvelopeError"] if raw_envelope_error is None else raw_envelope_error
            )
            stdout = norm["text"]
            obj = _last_json_object(stdout)
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
                    if _review_items_have_placeholder_literal(arr):
                        return {"ok": False, "reason": "unreadable"}
                    findings_list, findings_rejected = _scrub_findings(arr, echo_nonce=echo_nonce)
                    if _findings_reply_has_hollow_member(findings_rejected):
                        return {"ok": False, "reason": "unreadable"}
                    if _outer_envelope_error_makes_unreadable(outer_envelope_error, findings_list):
                        return {"ok": False, "reason": "unreadable"}
                    if arr and not findings_list:
                        return {"ok": False, "reason": "unreadable"}
                    result = {"ok": True, "resultKind": "findings",
                              "findings": findings_list, "investigated": []}
                    return _attach_findings_parse_rejections(result, findings_rejected)
                return {"ok": False, "reason": "unreadable"}
            if not isinstance(obj, dict):
                return {"ok": False, "reason": "unreadable"}
            matched = _recognised_review_kinds(obj)
            if len(matched) > 1:
                return {"ok": False, "reason": "unreadable"}
            if len(matched) == 1:
                if matched[0] == "findings":
                    return _parse_review_findings_object(
                        obj, outer_envelope_error, echo_nonce=echo_nonce)
                return _REVIEW_CONTRACT_PARSERS[matched[0]](obj, outer_envelope_error)
            return {"ok": False, "reason": "unreadable"}
        outer_envelope_error = _raw_stream_envelope_has_error_control(stdout)
        stdout = _unwrap_stream_envelope(stdout)   # #347: see the unwrap's docstring
        obj = _last_json_object(stdout)
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
    opts = {"cwd": args.cwd, "model": args.model,
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
