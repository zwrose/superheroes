"""#2011 WO-2: every write-result channel accepts, validates and carries a `refusals` list.

The entry shape and its validator live in `command_refusals`; each test reaches the shape through
that module's constants and `refusals_fault`, never a pasted copy. The channels:

- the native write schema (`engine_result_channel`) and the report grader (`_grade_build_report_obj`),
- native write admission and the terminal `dispatch-write` result (`engine_dispatch`),
- the foreground `parse_result(<engine>, "fix", ...)` path,
- the native implementer result (`native_engine._read_result` and the close).
"""
import json
import os

import pytest

import command_refusals as CR
import engine_adapter as EA
import engine_result_channel as ERC
import native_engine as NE
from test_engine_dispatch_write import (  # noqa: F401  (the autouse pin is a fixture)
    ED, _dispatch_write, _linked_worktree, _native_write_grade_state, _pin_temp_base_to_tmp_path,
    _valid_native_write_obj, _write_native_obj_at_argv,
)
from test_native_engine_1947 import (  # noqa: F401  (the autouse pin is a fixture)
    _assert_untouched, _close, _forfeited, _kinds, _make_repo, _open, _pin_env, _ready, _records,
    _routed, _transcript, _write,
)

# a secret-shaped key=value assignment that `pr_comment.scrub` rewrites to `token=[REDACTED]`
# (its pattern 3, pinned by test_readout.test_build_readout_scrubs_pr_url_secret)
_SECRET = "supersecretvalue123"
_SECRET_COMMAND = "curl --fail https://example.test/x?token=" + _SECRET


def _entry(**over):
    # the schema channels always emit `hook` and `route` (null when unused), so the default carries both
    entry = {"command": "git push", "refusedBy": "hook", "hook": "no-push", "route": None, "next": "stopped"}
    entry.update(over)
    return entry


def _without(key):
    entry = _entry()
    del entry[key]
    return entry


# a hook-named route the implementer took under the stop rule's one exception
_ROUTE_ENTRY = {"command": "git checkout --theirs f.txt", "refusedBy": "hook", "hook": "worktree-guard",
                "route": "git checkout --theirs f.txt", "next": "took the route the guard named"}

# the weekly-eats PR 3356 shape (#2167): the cloud sandbox's own refusal message named its step
_SANDBOX_ROUTE_ENTRY = {"command": "cd app && npm test", "refusedBy": "sandbox", "hook": None,
                        "route": "split into plain commands", "next": "ran cd and npm test as plain commands"}

VALID_LISTS = [
    [],
    [_entry()],
    [_without("hook")],
    [_without("route")],
    [_entry(hook=None)],
    [_entry(refusedBy="permission", hook=None), _entry(refusedBy="sandbox")],
    [_entry(route="git checkout --theirs f.txt")],
    [_ROUTE_ENTRY],
    [_SANDBOX_ROUTE_ENTRY],
]

# the valid lists the strict write schema accepts: it needs `hook` and `route` on every entry, null when unused
SCHEMA_VALID_LISTS = [v for v in VALID_LISTS if all("hook" in e and "route" in e for e in v)]

# every malformed case `refusals_fault` refuses: not a list, a non-dict element, an unknown key, a
# refusedBy outside the enum, a missing key, a blank command / next / hook / route, a route that is not
# a string, a route on a permission refusal
MALFORMED_LISTS = [
    "not-a-list",
    {"command": "x"},
    None,
    ["x"],
    [_entry(extra="y")],
    [_entry(refusedBy="other")],
    [_without("command")],
    [_without("next")],
    [_without("refusedBy")],
    [_entry(command="")],
    [_entry(command="   ")],
    [_entry(next="  ")],
    [_entry(hook="  ")],
    [_entry(route="")],
    [_entry(route="  ")],
    [_entry(route=5)],
    [_entry(refusedBy="permission", hook=None, route="git status")],
    [dict(_SANDBOX_ROUTE_ENTRY, route="  ")],
]

# the cases the native write schema refuses itself: shape and enum, never a blank string
SCHEMA_REFUSED_LISTS = [
    "not-a-list",
    {"command": "x"},
    ["x"],
    [_entry(extra="y")],
    [_entry(refusedBy="other")],
    [_without("command")],
    [_without("next")],
    [_without("refusedBy")],
    [_without("hook")],
    [_without("route")],
    [_entry(route=5)],
]

# the cases only the admission check refuses: well-shaped but blank strings, and a route on a
# permission refusal
BLANK_LISTS = [
    [_entry(command="")],
    [_entry(command="   ")],
    [_entry(next="  ")],
    [_entry(hook="  ")],
    [_entry(route="  ")],
    [_entry(refusedBy="permission", hook=None, route="git status")],
]


def test_the_case_tables_agree_with_refusals_fault():
    omitting = ([_without("hook")], [_without("route")])
    assert all(CR.refusals_fault(v) is None for v in VALID_LISTS)
    assert all(CR.refusals_fault(v) is not None for v in MALFORMED_LISTS)
    assert all(CR.refusals_fault(v) is not None for v in SCHEMA_REFUSED_LISTS if v not in omitting)
    assert all(CR.refusals_fault(v) is not None for v in BLANK_LISTS)


def _write_obj(**over):
    return _valid_native_write_obj(**over)


# --- the native write schema and the report grader -----------------------------------------


@pytest.mark.parametrize("refusals", SCHEMA_VALID_LISTS)
def test_write_schema_accepts_a_valid_refusals_list(refusals):
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_WRITE)
    ok, reason = ERC.validate(schema, _write_obj(refusals=refusals))
    assert ok, reason


# axis: the native write schema's refusals property refuses a shape or enum violation (refusedBy "other") — see bite-proof record wo2_2011_refusals
@pytest.mark.parametrize("refusals", SCHEMA_REFUSED_LISTS)
def test_write_schema_refuses_a_malformed_refusals_list(refusals):
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_WRITE)
    ok, _reason = ERC.validate(schema, _write_obj(refusals=refusals))
    assert not ok


@pytest.mark.parametrize("route", ["git checkout --theirs f.txt", None])
def test_write_schema_accepts_a_taken_route_and_a_null_route(route):
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_WRITE)
    ok, reason = ERC.validate(schema, _write_obj(refusals=[dict(_ROUTE_ENTRY, route=route)]))
    assert ok, reason


def test_write_contract_prose_names_route():
    assert "route" in EA.WRITE_REPORT_FIELD_SEMANTICS


def test_write_schema_requires_the_refusals_key():
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_WRITE)
    obj = _write_obj()
    del obj["refusals"]
    ok, _reason = ERC.validate(schema, obj)
    assert not ok


def test_write_schema_does_not_police_blank_strings():
    # the vendor-validated shape carries no minLength; the admission check refuses blanks (below)
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_WRITE)
    for refusals in BLANK_LISTS:
        ok, reason = ERC.validate(schema, _write_obj(refusals=refusals))
        assert ok, reason


def test_write_contract_prose_names_refusals():
    assert "refusals" in EA.WRITE_REPORT_FIELD_SEMANTICS
    assert '"refusals": []' in EA.WRITE_REPORT_CONTRACT
    contract = ERC.write_result_contract_from_schema(
        ERC.declared_schema("codex", ERC.RUN_KIND_WRITE))
    assert "`refusals`" in contract
    assert EA.WRITE_REPORT_FIELD_SEMANTICS.strip() in contract


def test_grade_build_report_carries_a_valid_refusals_list():
    refusals = [_entry()]
    ok_obj = {"ok": True, "signal": "ok", "evidence": {}, "refusals": refusals}
    bad_obj = {"ok": False, "signal": "plan_wrong", "evidence": {}, "refusals": refusals}
    assert EA._grade_build_report_obj(ok_obj)["refusals"] == refusals
    graded = EA._grade_build_report_obj(bad_obj)
    assert graded["refusals"] == refusals and graded["signal"] == "plan_wrong"


def test_grade_build_report_carries_a_taken_route():
    obj = {"ok": True, "signal": "ok", "evidence": {}, "refusals": [_ROUTE_ENTRY]}
    assert EA._grade_build_report_obj(obj)["refusals"] == [_ROUTE_ENTRY]


def test_grade_build_report_adds_nothing_when_no_list_was_sent():
    assert "refusals" not in EA._grade_build_report_obj({"ok": True, "signal": "ok"})
    assert "refusals" not in EA._grade_build_report_obj({"ok": False, "signal": "plan_wrong"})


# axis: _grade_build_report_obj grades a malformed refusals list unreadable instead of carrying it — see bite-proof record wo2_2011_refusals
@pytest.mark.parametrize("refusals", MALFORMED_LISTS)
def test_grade_build_report_refuses_a_malformed_refusals_list(refusals):
    for ok in (True, False):
        graded = EA._grade_build_report_obj(
            {"ok": ok, "signal": "ok", "evidence": {}, "refusals": refusals})
        assert graded == {"ok": False, "reason": "unreadable"}


# axis: _grade_build_report_obj scrubs secret-shaped text in a carried refusal — see bite-proof record wo6_2011_sendback
def test_grade_build_report_scrubs_a_secret_in_a_refusal_command():
    obj = {"ok": True, "signal": "ok", "evidence": {},
           "refusals": [_entry(command=_SECRET_COMMAND)]}
    graded = EA._grade_build_report_obj(obj)
    command = graded["refusals"][0]["command"]
    assert _SECRET not in command
    assert command == "curl --fail https://example.test/x?token=[REDACTED]"


def test_grade_build_report_non_dict_is_unchanged():
    assert EA._grade_build_report_obj([]) == {"ok": False, "reason": "unreadable"}
    assert EA._grade_build_report_obj(None) == {"ok": False, "reason": "unreadable"}


# --- the foreground fix parse ---------------------------------------------------------------


def test_parse_result_fix_keeps_a_valid_refusals_list():
    refusals = [_entry()]
    stdout = json.dumps({"ok": True, "signal": "ok", "evidence": {}, "refusals": refusals})
    res = EA.parse_result("cursor", "fix", stdout)
    assert res["ok"] is True and res["refusals"] == refusals


def test_parse_result_fix_without_refusals_carries_no_key():
    res = EA.parse_result("cursor", "fix", json.dumps({"ok": True, "signal": "ok", "evidence": {}}))
    assert res["ok"] is True and "refusals" not in res


# axis: the foreground fix parse grades a malformed refusals list unreadable — see bite-proof record wo2_2011_refusals
@pytest.mark.parametrize("refusals", MALFORMED_LISTS)
def test_parse_result_fix_refuses_a_malformed_refusals_list(refusals):
    stdout = json.dumps({"ok": True, "signal": "ok", "evidence": {}, "refusals": refusals})
    assert EA.parse_result("cursor", "fix", stdout) == {"ok": False, "reason": "unreadable"}


# --- native write admission and the terminal dispatch-write result ---------------------------


# axis: the admitted refusals list is copied into the terminal dispatch-write success result — see bite-proof record wo2_2011_refusals
def test_dispatch_write_success_carries_refusals(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    refusals = [_entry(), _entry(refusedBy="sandbox", hook=None)]
    obj = _write_obj(refusals=refusals)

    def runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        _write_native_obj_at_argv(argv, obj)
        return "", False, 0, ""

    res = _dispatch_write(tmp_path, runner, cwd=wt)
    assert res["ok"] is True and res["terminal"] is True
    assert res["refusals"] == refusals


def test_dispatch_write_empty_list_is_carried_as_an_empty_list(tmp_path):
    wt, _main = _linked_worktree(tmp_path)

    def runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        _write_native_obj_at_argv(argv, _write_obj())
        return "", False, 0, ""

    res = _dispatch_write(tmp_path, runner, cwd=wt)
    assert res["ok"] is True
    assert res["refusals"] == []


def test_dispatch_write_terminal_refusal_carries_refusals(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    refusals = [_entry()]
    obj = _write_obj(ok=False, signal="plan_wrong", refusals=refusals)

    def runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        _write_native_obj_at_argv(argv, obj)
        return "", False, 0, ""

    res = _dispatch_write(tmp_path, runner, cwd=wt)
    assert res["ok"] is False and res["terminal"] is True and res["forfeited"] is False
    assert res["signal"] == "plan_wrong"
    assert res["refusals"] == refusals


def test_dispatch_write_undelivered_items_forfeit_carries_admitted_refusals(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    refusals = [_entry()]
    obj = _write_obj(refusals=refusals)

    def runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        _write_native_obj_at_argv(argv, obj)
        return "", False, 0, ""

    res = _dispatch_write(tmp_path, runner, cwd=wt, expected_items=["undelivered.txt"])
    assert res["forfeited"] is True
    assert res["detail"] == ED.ITEM_DETAIL_UNDELIVERED
    assert res["refusals"] == refusals


# axis: a native write result carrying the 3356 sandbox-route entry is admitted, not forfeited (#2167)
def test_native_write_admits_a_sandbox_named_route(tmp_path):
    run_dir, state = _native_write_grade_state(tmp_path, _write_obj(refusals=[_SANDBOX_ROUTE_ENTRY]))
    grade = ED._grade_write_attempt(run_dir, state, 1)
    assert grade.get("forfeit") is not True, grade
    assert grade.get("detail") != "native-result-refusals-invalid"


def test_write_result_digest_content_leaves_refusals_out():
    content = ED._write_result_digest_content({
        "ok": True, "signal": "ok", "evidence": {"testFailed": False, "testPassed": True},
        "report": "r", "refusals": [_entry()],
    })
    assert content is not None and "refusals" not in content


# axis: admission refuses a schema-valid refusals list that has a blank string (native-result-refusals-invalid) — see bite-proof record wo2_2011_refusals
@pytest.mark.parametrize("refusals", BLANK_LISTS)
def test_native_write_blank_refusals_forfeit_refusals_invalid(tmp_path, refusals):
    run_dir, state = _native_write_grade_state(tmp_path, _write_obj(refusals=refusals))
    grade = ED._grade_write_attempt(run_dir, state, 1)
    assert grade.get("forfeit") is True
    assert grade.get("detail") == "native-result-refusals-invalid"
    assert grade.get("ok") is not True


@pytest.mark.parametrize("refusals", SCHEMA_REFUSED_LISTS)
def test_native_write_malformed_refusals_forfeit_at_the_schema(tmp_path, refusals):
    run_dir, state = _native_write_grade_state(tmp_path, _write_obj(refusals=refusals))
    grade = ED._grade_write_attempt(run_dir, state, 1)
    assert grade.get("forfeit") is True
    assert grade.get("detail") == "native-result-schema-invalid"


def test_native_write_missing_refusals_forfeits_at_the_schema(tmp_path):
    obj = _write_obj()
    del obj["refusals"]
    run_dir, state = _native_write_grade_state(tmp_path, obj)
    grade = ED._grade_write_attempt(run_dir, state, 1)
    assert grade.get("forfeit") is True
    assert grade.get("detail") == "native-result-schema-invalid"


# --- the native implementer result ----------------------------------------------------------


def _result_file(tmp_path, body):
    run_dir = str(tmp_path / "result-run")
    os.makedirs(run_dir, exist_ok=True)
    with open(os.path.join(run_dir, "result.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(body))
    return run_dir


@pytest.mark.parametrize("refusals", VALID_LISTS)
def test_read_result_accepts_a_valid_refusals_list(tmp_path, refusals):
    body = {"status": "done", "summary": "s", "refusals": refusals}
    assert NE._read_result(_result_file(tmp_path, body)) == body


# axis: the native implementer result built from the 3356 shape reads valid, not native-result-invalid (#2167)
def test_read_result_accepts_the_sandbox_named_route(tmp_path):
    body = {"status": "done", "summary": "s", "refusals": [_SANDBOX_ROUTE_ENTRY]}
    assert NE._read_result(_result_file(tmp_path, body)) == body


def test_read_result_without_refusals_is_valid(tmp_path):
    body = {"status": "done", "summary": "s"}
    assert NE._read_result(_result_file(tmp_path, body)) == body


# axis: _read_result refuses a result whose refusals list is malformed (None → native-result-invalid) — see bite-proof record wo2_2011_refusals
@pytest.mark.parametrize("refusals", MALFORMED_LISTS)
def test_read_result_refuses_a_malformed_refusals_list(tmp_path, refusals):
    body = {"status": "done", "summary": "s", "refusals": refusals}
    assert NE._read_result(_result_file(tmp_path, body)) is None


def test_native_preamble_names_the_refusals_result_shape():
    assert '"refusals": [ ... ]' in NE.NATIVE_PREAMBLE
    assert "an empty list or no refusals key means you met none" in NE.NATIVE_PREAMBLE
    assert 'still write this result with status "blocked"' in NE.NATIVE_PREAMBLE


def _result_with(r, status="blocked", **extra):
    body = {"status": status, "summary": "stopped"}
    body.update(extra)
    _write(os.path.join(r.run, "result.json"), json.dumps(body))


def _unenrolled(capsys, monkeypatch, r):
    _routed(monkeypatch)
    code, opened = _open(capsys, r)
    assert code == 0, opened
    _transcript(r)


# axis: a forfeit path of the native close carries the valid refusals the agent wrote — see bite-proof record wo2_2011_refusals
def test_close_denied_enrollment_forfeit_carries_refusals(tmp_path, monkeypatch, capsys):
    r = _make_repo(tmp_path)
    _unenrolled(capsys, monkeypatch, r)
    refusals = [_entry(command="enroll", refusedBy="permission", hook=None, next="stopped")]
    _result_with(r, refusals=refusals)
    code, out = _close(capsys, r)
    _forfeited(code, out, "native-not-enrolled")
    assert out["refusals"] == refusals
    _assert_untouched(r)


def test_close_forfeit_without_refusals_carries_no_key(tmp_path, monkeypatch, capsys):
    r = _make_repo(tmp_path)
    _unenrolled(capsys, monkeypatch, r)
    _result_with(r)
    code, out = _close(capsys, r)
    _forfeited(code, out, "native-not-enrolled")
    assert "refusals" not in out


def test_close_forfeit_with_an_empty_refusals_list_carries_no_key(tmp_path, monkeypatch, capsys):
    r = _make_repo(tmp_path)
    _unenrolled(capsys, monkeypatch, r)
    _result_with(r, refusals=[])
    code, out = _close(capsys, r)
    _forfeited(code, out, "native-not-enrolled")
    assert "refusals" not in out


@pytest.mark.parametrize("refusals", MALFORMED_LISTS)
def test_close_forfeit_attaches_nothing_for_a_malformed_list(tmp_path, monkeypatch, capsys, refusals):
    r = _make_repo(tmp_path)
    _unenrolled(capsys, monkeypatch, r)
    _result_with(r, refusals=refusals)
    code, out = _close(capsys, r)
    _forfeited(code, out, "native-not-enrolled")
    assert "refusals" not in out


# axis: the native close scrubs secret-shaped text in a refusal, in its result and in the journal — see bite-proof record wo6_2011_sendback
def test_close_denied_enrollment_forfeit_scrubs_a_secret_in_a_refusal(tmp_path, monkeypatch, capsys):
    r = _make_repo(tmp_path)
    _unenrolled(capsys, monkeypatch, r)
    _result_with(r, refusals=[_entry(command=_SECRET_COMMAND, refusedBy="permission", hook=None)])
    code, out = _close(capsys, r)
    _forfeited(code, out, "native-not-enrolled")
    assert _SECRET not in json.dumps(out["refusals"])
    assert out["refusals"][0]["command"] == "curl --fail https://example.test/x?token=[REDACTED]"
    closed = [rec for rec in _records(r) if rec.get("kind") == "run-closed"]
    assert len(closed) == 1
    assert _SECRET not in json.dumps(closed[0])
    assert closed[0]["refusals"][0]["command"] == out["refusals"][0]["command"]


def test_close_forfeit_with_no_result_file_is_unchanged(tmp_path, monkeypatch, capsys):
    r = _make_repo(tmp_path)
    _unenrolled(capsys, monkeypatch, r)
    code, out = _close(capsys, r)
    _forfeited(code, out, "native-not-enrolled")
    assert "refusals" not in out


def test_close_forfeit_with_an_unparseable_result_is_unchanged(tmp_path, monkeypatch, capsys):
    r = _make_repo(tmp_path)
    _unenrolled(capsys, monkeypatch, r)
    _write(os.path.join(r.run, "result.json"), "{not json")
    code, out = _close(capsys, r)
    _forfeited(code, out, "native-not-enrolled")
    assert "refusals" not in out


def test_close_deadline_forfeit_carries_refusals(tmp_path, monkeypatch, capsys):
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r)
    refusals = [_entry()]
    _result_with(r, status="done", refusals=refusals)
    code, out = _close(capsys, r, forfeit=True)
    _forfeited(code, out, "native-deadline")
    assert out["refusals"] == refusals


def test_close_done_carries_refusals(tmp_path, monkeypatch, capsys):
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r)
    refusals = [_entry()]
    _result_with(r, status="done", refusals=refusals)
    code, out = _close(capsys, r)
    assert code == 0 and out["ok"] is True
    assert out["refusals"] == refusals


@pytest.mark.parametrize("status", ["needs_context", "blocked"])
def test_close_non_done_status_carries_refusals(tmp_path, monkeypatch, capsys, status):
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r)
    refusals = [_entry()]
    _result_with(r, status=status, refusals=refusals)
    code, out = _close(capsys, r)
    assert code == 0 and out["reason"] == status and out["forfeited"] is False
    assert out["refusals"] == refusals


def test_close_done_with_a_malformed_list_forfeits_result_invalid(tmp_path, monkeypatch, capsys):
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r)
    _result_with(r, status="done", refusals=[_entry(refusedBy="other")])
    code, out = _close(capsys, r)
    _forfeited(code, out, "native-result-invalid")
    assert "refusals" not in out
    _assert_untouched(r)


def test_close_second_close_returns_the_same_record_with_refusals(tmp_path, monkeypatch, capsys):
    r = _make_repo(tmp_path)
    _unenrolled(capsys, monkeypatch, r)
    _result_with(r, refusals=[_entry()])
    code, first = _close(capsys, r)
    _forfeited(code, first, "native-not-enrolled")
    kinds = _kinds(r)
    # axis: the replay returns the journaled record's refusals, never a fresh read of result.json — see bite-proof record wo5_2011_review_fixes
    _result_with(r, refusals=[_entry(command="different command")])
    code, second = _close(capsys, r)
    assert code == 1
    assert second == first and second["refusals"] == [_entry()]
    assert second["refusals"] == first["refusals"]
    assert _kinds(r) == kinds


def test_close_done_second_close_returns_the_same_record_with_refusals(tmp_path, monkeypatch, capsys):
    r = _make_repo(tmp_path)
    _ready(capsys, monkeypatch, r)
    _result_with(r, status="done", refusals=[_entry()])
    code, first = _close(capsys, r)
    assert code == 0 and first["ok"] is True
    # axis: the replay returns the journaled record's refusals, never a fresh read of result.json — see bite-proof record wo5_2011_review_fixes
    _result_with(r, status="done", refusals=[_entry(command="different command")])
    code, second = _close(capsys, r)
    assert code == 0
    assert second == first and second["refusals"] == [_entry()]
    assert second["refusals"] == first["refusals"]
