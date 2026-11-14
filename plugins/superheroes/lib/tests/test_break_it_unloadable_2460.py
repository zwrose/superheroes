"""#2460: an attached break-it test that does not load because of an indentation error is malformed seat output.

The invariant: a Python break-it test a seat returns whose content does not load because of an indentation error
(``compile(content, path, "exec", dont_inherit=True)`` raises ``IndentationError``, ``TabError`` included) is never run,
never put on a finding, never owed as a commit and never restored. The finding it rode on stands without it, and the
round records the seat, the finding's file and line, the test path and the compile error (``breakItMalformed``, the
decision ``break-it-test-malformed``, one ``checked`` line in the review record). An attached test that loads keeps
every rule it has today.

Pins, each at the place the rule is enforced:

T1  end to end: the unloadable test is dropped at the panel fold, so the fix batch owes no test binding for it, its
    audit target carries no ``breakIt`` facts, no restore step is entered and the loop goes on (before the fix it ended
    ``handed-back`` with ``break-it-restore-failed``: the restore demanded bytes the session could not commit);
T2  the round's row and decision; no run is recorded for the dropped test (E7);
T3  a healthy sibling is run, carried and restored exactly as before;
T4  the edges: E1 not a block, E2 per-area, E3 another syntax error, E4 another language, E5 a null byte, E6 a
    stamped block, E8 two test-role seats;
T5  the second-test fold and the correction fold;
T6  the review record's ``checked`` line;
U   ``break_it.load_error`` branch by branch, and the one-chokepoint census.

Bite-proof record: wo_a_2460_break_it_unloadable
"""
import ast
import copy
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import break_it  # noqa: E402
import decision_kinds  # noqa: E402
import receipt_disclosures  # noqa: E402
import review_record_session as rs  # noqa: E402
import test_break_it_attached_2210 as AT  # noqa: E402
import test_c1l10_audit_checks as C1  # noqa: E402
import test_c1l10b_test_restore as TR  # noqa: E402
import test_round_driver as TRD  # noqa: E402
from test_break_it_attached_2210 import fx, spy  # noqa: E402,F401  (fixtures)
from test_review_record_session import Fake, Session, extras  # noqa: E402

RD = TR.RD

HTML_TEST_PATH = "tests/test_html_comment_is_not_a_fence.py"
HTML_TITLE = "An HTML comment's contents are read as a fence"
# The attached block's content: line 8 is indented at module level, so it does not load.
UNLOADABLE = (
    '"""Regression: mention_guard must not read an HTML comment\'s contents as a fence."""\n'
    "from types import SimpleNamespace\n"
    "\n"
    "import cloud_builder\n"
    "import mention_guard\n"
    "\n"
    "\n"
    " def_placeholder = None\n")
# The same finding's test re-indented into a real test: it loads.
LOADABLE = UNLOADABLE.replace(" def_placeholder = None\n",
                              "def test_html_comment_is_not_a_fence():\n    assert SimpleNamespace(a=1).a == 1\n")
# A regression the build session commits instead: it loads, and its bytes are not the seat's.
OWN_REGRESSION = "def test_html_comment_is_not_a_fence():\n    assert True\n"
UNLOADABLE_ERROR = "IndentationError: unexpected indent (line 8)"
# A correction that does not load: the second line is indented deeper than the line after it.
UNLOADABLE_CORRECTION = "def test_charge():\n        import charge_mod\n    assert charge(2) == 2\n"


@pytest.fixture(autouse=True)
def _pinned_git(monkeypatch, tmp_path):
    """Every git command a fixture here runs reads no user or system git config. Autouse fixtures do not carry
    across an import, so the pin is defined again for this file."""
    for name in ("home", "xdg-config"):
        (tmp_path / name).mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _finding(content=UNLOADABLE, path=HTML_TEST_PATH, **extra):
    """An attached finding (taxonomy ``claim/test mismatch``, severity ``Important``) of the test role's seat."""
    fields = {"taxonomy": "claim/test mismatch", "title": HTML_TITLE, "suggestion": AT._block(path, content)}
    fields.update(extra)
    return AT._attached(content, **fields)


def _decision_kinds(state):
    return [d["kind"] for d in state["decisions"]]


def _malformed_decisions(state):
    return [d for d in state["decisions"] if d["kind"] == "break-it-test-malformed"]


# ---- the audit world ----------------------------------------------------------------------------------------

def _audit_world(tmp_path, staged, committed=OWN_REGRESSION):
    """The 10b audit world (``TR.World``) carrying ``staged`` (a finding the panel fold staged) as its fix batch, over
    a repository whose head is the build session's fix: it commits ``committed`` at the block's own path."""
    w = TR.World(tmp_path)
    block = break_it.carried_block(staged)[0]
    path = block["path"] if block is not None else HTML_TEST_PATH
    w.write(path, committed)
    w.fix_head = TR._commit(w.root, "fix with its own regression")
    w.state["rounds"]["1"]["fixFoldHead"] = w.fix_head
    w.finding = copy.deepcopy(staged)
    w.key = RD._finding_key_of(w.finding)
    w.state["fixBatch"] = [w.finding]
    w.state["_fixBatch"] = [w.finding]
    w.state["findings"] = [copy.deepcopy(staged)]
    w.state["_auditTargets"] = RD._audit_targets(w.state, w.cfg, {})
    return w


def _loop(w, restore_with):
    """``run_loop`` over ``w`` from the audits on. ``restore_with(item)`` is the text the build session commits when
    it is handed a restore-only step. Returns ``(state, restores_asked)``."""
    asked = []

    def fix_step(batch, rnd, payload):
        if payload.get("restoreOnly"):
            item = payload["restores"][0]
            asked.append(item)
            w.write(item["path"], restore_with(item))
            TR._commit(w.root, "restore")
        return {"fixes": []}

    seams = TRD._seams(auditor=lambda targets, rnd: w.audit_artifact()["results"], fix_step=fix_step,
                       reviewer=lambda dim, tier, rnd, ctx: {"findings": [], "vendor": "codex"})
    _receipt, state = w.run_loop(seams)
    return state, asked


# ---- T1 ----------------------------------------------------------------------------------------------------

def test_t1_an_unloadable_attached_test_is_dropped_so_no_restore_is_demanded_and_the_loop_goes_on(fx, tmp_path):
    # axis: the whole path — the panel fold drops the test, the fix batch owes no binding, the audit has no test facts, the restore is never entered
    state = fx.fold_panel(test_role=[_finding()])
    staged = fx.staged(HTML_TITLE)

    # the loop: before the drop, the audit flagged the test, the restore demanded the unloadable bytes and the
    # session committed other bytes, so the PR was handed back with `break-it-restore-failed`
    final, asked = _loop(_audit_world(tmp_path / "loop", staged), restore_with=lambda item: OWN_REGRESSION)
    kinds = _decision_kinds(final)
    assert "break-it-restore-failed" not in kinds, final["decisions"][-1]
    assert asked == [] and final.get("terminal") != "handed-back", (final.get("terminal"), asked)
    assert "testMismatch" not in final["rounds"].get("2", {}) and "testRestore" not in final["rounds"].get("2", {})
    assert RD.TEST_RESTORE_FIELD not in final

    # the fix batch carries no block, so the fix report owes no test binding for the finding
    w = _audit_world(tmp_path / "facts", staged)
    assert break_it.carried_block(staged) == (None, None)
    assert RD._apply_fixes_commit_fault(w.state, w.cfg, {"fixes": []}) == (None, [])
    # its audit target carries no break-it facts
    (target,) = w.state["_auditTargets"]
    assert "breakIt" not in target
    # the panel itself recorded the drop and nothing was run
    assert [r["path"] for r in state["rounds"]["1"]["breakItMalformed"]] == [HTML_TEST_PATH]


# ---- T2 ----------------------------------------------------------------------------------------------------

def test_t2_the_round_records_the_seat_the_finding_the_path_and_the_error_and_no_run_is_recorded(fx, spy):
    state = fx.fold_panel(test_role=[_finding()])
    (row,) = fx.round_record["breakItMalformed"]
    assert row == {"seat": "test-role", "title": HTML_TITLE, "file": AT.CHARGE_PATH, "line": 2,
                   "path": HTML_TEST_PATH, "error": UNLOADABLE_ERROR}
    (decision,) = _malformed_decisions(state)
    assert decision["detail"].startswith("1 break-it test(s)") and HTML_TEST_PATH in decision["detail"]
    # E7: the finding stands without the test, carrying no run, and the round holds no run for it
    staged = fx.staged(HTML_TITLE)
    assert break_it.carried_block(staged) == (None, None) and staged["suggestion"] is None
    assert break_it.RUN_FIELD not in staged and break_it.RUNS_FIELD not in staged
    assert "breakItRuns" not in fx.round_record and "break-it-run" not in _decision_kinds(state)
    assert not RD._carried_test_unrecoverable(staged)
    assert spy.calls == []
    ledger = [e for e in state[AT.SC.DISPOSITION_LEDGER_KEY] if e["title"] == HTML_TITLE]
    assert ledger and all(break_it.RUNS_FIELD not in e and break_it.RUN_FIELD not in e for e in ledger)


def test_t2_the_panel_row_is_kept_by_a_resume_and_the_decision_kind_is_registered():
    assert "break-it-test-malformed" in decision_kinds.DECISION_KINDS
    shape_ok = receipt_disclosures.CARRIED_DISCLOSURE_CHANNELS["breakItMalformed"]
    assert shape_ok([{"seat": "test-role", "path": "tests/t.py"}]) and not shape_ok("tests/t.py")


# ---- T3 ----------------------------------------------------------------------------------------------------

def test_t3_a_healthy_sibling_is_run_carried_and_restored_as_before(fx, spy, tmp_path):
    state = fx.fold_panel(test_role=[_finding(LOADABLE)])
    assert [c["path"] for c in spy.calls] == [HTML_TEST_PATH]
    staged = fx.staged(HTML_TITLE)
    block = break_it.carried_block(staged)[0]
    assert block["path"] == HTML_TEST_PATH and block["content"] == LOADABLE
    assert staged[break_it.RUN_FIELD]["path"] == HTML_TEST_PATH and len(staged[break_it.RUNS_FIELD]) == 1
    assert "breakItMalformed" not in fx.round_record and _malformed_decisions(state) == []
    (run,) = fx.round_record["breakItRuns"]
    assert run["path"] == HTML_TEST_PATH and run["kind"] == break_it.KIND_ATTACHED

    # the restore rule, through the 10b restore path: the audit flags the committed regression, the restore step
    # carries the seat's bytes, and a session that commits them goes on
    w = _audit_world(tmp_path / "audit", staged)
    w.audit()
    assert w.state["rounds"]["2"]["testMismatch"] == [w.key]
    step = w.step()
    assert step["payload"]["restoreOnly"] is True
    assert step["payload"]["restores"][0]["content"] == LOADABLE and step["payload"]["restores"][0]["path"] == HTML_TEST_PATH
    kept_state, asked = _loop(_audit_world(tmp_path / "loop", staged), restore_with=lambda item: item["content"])
    assert [item["content"] for item in asked] == [LOADABLE]
    assert "break-it-test-restored" in _decision_kinds(kept_state) and "break-it-restore-failed" not in _decision_kinds(kept_state)
    # and the same restore with other bytes still hands the PR back
    failed_state, _asked = _loop(_audit_world(tmp_path / "bad", staged), restore_with=lambda item: OWN_REGRESSION)
    assert failed_state["terminal"] == "handed-back" and failed_state["decisions"][-1]["kind"] == "break-it-restore-failed"


# ---- T4: the edges -----------------------------------------------------------------------------------------

def test_t4_e1_a_suggestion_that_is_no_block_is_untouched(fx, spy):
    fx.fold_panel(test_role=[AT._attached(suggestion="rename the helper", taxonomy="claim/test mismatch")])
    assert "breakItMalformed" not in fx.round_record and spy.calls == []
    assert fx.staged(AT.ATTACHED_TITLE)["suggestion"] == "rename the helper"


def test_t4_e2_a_per_area_finding_whose_block_does_not_load_is_untouched(fx, spy):
    content = AT._TEST_FAILING + " stray = 1\n"
    assert break_it.load_error({"path": AT.PER_AREA_TEST, "content": content}) is not None  # the premise
    fx.fold_panel(test_role=[AT._per_area(content, suggestion=AT._block(AT.PER_AREA_TEST, content))])
    assert [c["path"] for c in spy.calls] == [AT.PER_AREA_TEST]
    assert "breakItMalformed" not in fx.round_record
    staged = fx.staged("Break-it: an idempotent charge")
    assert break_it.carried_block(staged)[0]["content"] == content and staged[break_it.RUN_FIELD]["path"] == AT.PER_AREA_TEST


def test_t4_e3_a_syntax_error_that_is_not_an_indentation_error_is_run_as_before(fx, spy):
    content = "def test_it(:\n    pass\n"
    fx.fold_panel(test_role=[_finding(content)])
    assert [c["path"] for c in spy.calls] == [HTML_TEST_PATH]
    assert "breakItMalformed" not in fx.round_record
    assert break_it.carried_block(fx.staged(HTML_TITLE))[0]["content"] == content


def test_t4_e4_a_block_of_another_language_is_never_compile_checked(fx, spy):
    path = "tests/html_comment.test.ts"
    content = "  const x = 1;\n    expect(x).toBe(1);\n"
    fx.fold_panel(test_role=[_finding(content, path=path)])
    assert [c["path"] for c in spy.calls] == [path]
    assert "breakItMalformed" not in fx.round_record
    assert break_it.carried_block(fx.staged(HTML_TITLE))[0]["content"] == content


@pytest.mark.parametrize("stamp,reason", [(break_it.TRANSIT_FIELD, "transit-redacted"),
                                          (break_it.REDACTED_FIELD, "suggestion-redacted")])
def test_t4_e6_a_stamped_block_is_never_dropped_for_load_reasons(fx, spy, stamp, reason):
    fx.fold_panel(test_role=[_finding(**{stamp: True})])
    assert spy.calls == []
    assert "breakItMalformed" not in fx.round_record
    staged = fx.staged(HTML_TITLE)
    assert break_it.carried_block(staged)[0]["content"] == UNLOADABLE
    assert (staged[break_it.RUN_FIELD]["outcome"], staged[break_it.RUN_FIELD]["reason"]) == ("not-run", reason)


def test_t4_e8_two_test_role_seats_each_name_their_own_seat(fx, spy):
    fx.state["slicePlan"] = {"sliced": True, "slices": [{"id": "s1"}, {"id": "s2"}]}
    other = "tests/test_second_seat.py"
    seats = AT._seats()
    seats["test-role:s1"] = {"findings": [_finding(title="First seat's finding")]}
    seats["test-role:s2"] = {"findings": [_finding(UNLOADABLE.replace("mention_guard", "other_guard"), path=other,
                                                   title="Second seat's finding")]}
    RD._fold(fx.state, fx.state["config"], RD.P_PANEL, {"seats": seats}, session_dir=str(fx.session))
    rows = fx.round_record["breakItMalformed"]
    assert sorted((r["seat"], r["title"], r["path"]) for r in rows) == [
        ("test-role:s1", "First seat's finding", HTML_TEST_PATH),
        ("test-role:s2", "Second seat's finding", other)]
    (decision,) = _malformed_decisions(fx.state)
    assert decision["detail"].startswith("2 break-it test(s)")
    assert spy.calls == []


# ---- T5: the second-test fold and the correction fold --------------------------------------------------------

def _second_test(fx_, held, result):
    fx_.state["_secondTestHeld"] = [{"finding": held, "note": "the test missed the path"}]
    RD._fold_second_test(fx_.state, fx_.state["config"], {"findings": [result]}, session_dir=str(fx_.session))
    (staged,) = fx_.state["_toVerify"]
    return staged


def test_t5_a_second_test_that_does_not_load_is_no_new_test_and_the_held_test_stays(fx, spy):
    # axis: the second-test fold keeps the held finding's own test and says why
    held = AT._attached(id="F1")
    result = dict(_finding(), id="F1")
    staged = _second_test(fx, held, result)
    key = RD._finding_identity_key(held)
    assert staged["suggestion"] == held["suggestion"] and staged[RD.SECOND_TEST_FIELD] is True
    assert break_it.RUN_FIELD not in staged and break_it.RUNS_FIELD not in staged
    assert spy.calls == []
    rec = fx.round_record
    assert rec["secondTest"]["noTest"] == [{"findingKey": key, "reason": "not-loadable"}]
    assert rec["secondTest"]["ran"] == [] and "breakItRuns" not in rec
    assert rec["breakItMalformed"] == [{"seat": "test-role", "title": AT.ATTACHED_TITLE, "file": AT.CHARGE_PATH,
                                        "line": 2, "path": HTML_TEST_PATH, "error": UNLOADABLE_ERROR,
                                        "findingKey": key}]
    assert len(_malformed_decisions(fx.state)) == 1


@pytest.mark.parametrize("stamp,reason", [(break_it.TRANSIT_FIELD, "transit-redacted"),
                                          (break_it.REDACTED_FIELD, "suggestion-redacted")])
def test_t5_e6_a_stamped_second_test_keeps_its_carry_and_not_run_handling(fx, spy, stamp, reason):
    held = AT._attached(id="F1")
    staged = _second_test(fx, held, dict(_finding(**{stamp: True}), id="F1"))
    assert spy.calls == [] and "breakItMalformed" not in fx.round_record
    assert fx.round_record["secondTest"]["noTest"] == []
    assert (staged[break_it.RUN_FIELD]["outcome"], staged[break_it.RUN_FIELD]["reason"]) == ("not-run", reason)


def test_t5_a_second_test_that_loads_is_still_run(fx, spy):
    staged = _second_test(fx, AT._attached(id="F1"), dict(_finding(LOADABLE), id="F1"))
    assert [c["path"] for c in spy.calls] == [HTML_TEST_PATH]
    assert break_it.carried_block(staged)[0]["content"] == LOADABLE
    assert "breakItMalformed" not in fx.round_record


def _corrected_world(tmp_path):
    w = TR.World(tmp_path)
    w.audit()
    w.restore()
    return w


def test_t5_a_correction_that_does_not_load_is_no_correction_and_the_restored_test_stands(tmp_path):
    # axis: the correction fold names `not-loadable` and leaves the restored test in place
    w = _corrected_world(tmp_path)
    assert w.state["step"] == RD.P_SECOND_TEST
    w.fold(RD.P_SECOND_TEST, {"findings": [{"id": w.key, "suggestion": C1._block_text(UNLOADABLE_CORRECTION)}]})
    assert w.state["rounds"]["2"]["testCorrection"] == [{"findingKey": w.key, "outcome": "none", "reason": "not-loadable"}]
    assert w.state["step"] == RD.P_VERIFY and w.committed() == TR.ROLE_TEST
    (row,) = w.state["rounds"]["2"]["breakItMalformed"]
    assert row["seat"] == "test-role" and row["findingKey"] == w.key and row["path"] == TR.TEST_PATH
    assert (row["title"], row["file"], row["line"]) == ("Retry charges twice", TR.TEST_PATH, 1)
    assert row["error"].startswith("IndentationError: unindent does not match any outer indentation level")
    assert len(_malformed_decisions(w.state)) == 1 and "break-it-correction-none" in _decision_kinds(w.state)
    # the correction is used all the same
    assert RD._correction_used(w.state, w.key)


@pytest.mark.parametrize("stamp,reason", [(break_it.TRANSIT_FIELD, "transit-redacted"), (break_it.REDACTED_FIELD, "redacted")])
def test_t5_e6_a_stamped_correction_keeps_its_existing_reason(tmp_path, stamp, reason):
    w = _corrected_world(tmp_path)
    w.fold(RD.P_SECOND_TEST, {"findings": [{"id": w.key, "suggestion": C1._block_text(UNLOADABLE_CORRECTION), stamp: True}]})
    assert w.state["rounds"]["2"]["testCorrection"] == [{"findingKey": w.key, "outcome": "none", "reason": reason}]
    assert "breakItMalformed" not in w.state["rounds"]["2"]


def test_t5_a_correction_that_loads_and_changes_the_test_still_lands(tmp_path):
    w = _corrected_world(tmp_path)
    w.fold(RD.P_SECOND_TEST, {"findings": [{"id": w.key, "suggestion": C1._block_text(TR.CORRECTED_TEST)}]})
    assert w.state["rounds"]["2"]["testCorrection"] == [{"findingKey": w.key, "outcome": "corrected"}]
    assert "breakItMalformed" not in w.state["rounds"]["2"] and w.state["step"] == RD.P_APPLY_FIXES


# ---- T6: the review record -----------------------------------------------------------------------------------

def test_t6_the_review_record_names_each_dropped_test_in_round_order(tmp_path):
    first = {"seat": "test-role:s1", "title": HTML_TITLE, "file": "src/a.py", "line": 3, "path": HTML_TEST_PATH,
             "error": UNLOADABLE_ERROR}
    second = {"seat": "test-role", "title": "t", "file": "src/b.py", "line": 9, "path": "tests/test_b.py",
              "error": "TabError: inconsistent use of tabs and spaces in indentation (line 3)", "findingKey": "k"}
    third = dict(first, seat="test-role:s2", path="tests/test_c.py")
    s = Session(tmp_path, rounds={"1": {"breakItMalformed": [first]}, "2": {"breakItMalformed": [second, "junk", third]},
                                  "3": {}})
    s.seat("code-reviewer")
    account = rs.account_from_session(s.save(), extras(checked=["ran the suite"]), Fake().readers())
    lines = [c for c in account["checked"] if c.startswith("Break-it test dropped")]
    assert lines == [
        "Break-it test dropped as malformed seat output (round 1): test-role:s1 returned %s for src/a.py:3; it does "
        "not load (%s), so the finding stands without it and no commit or restore of it was asked."
        % (HTML_TEST_PATH, UNLOADABLE_ERROR),
        "Break-it test dropped as malformed seat output (round 2): test-role returned tests/test_b.py for "
        "src/b.py:9; it does not load (TabError: inconsistent use of tabs and spaces in indentation (line 3)), "
        "so the finding stands without it and no commit or restore of it was asked.",
        "Break-it test dropped as malformed seat output (round 2): test-role:s2 returned tests/test_c.py for "
        "src/a.py:3; it does not load (%s), so the finding stands without it and no commit or restore of it "
        "was asked." % UNLOADABLE_ERROR]
    assert "ran the suite" in account["checked"]


def test_t6_a_round_with_no_dropped_test_adds_no_line(tmp_path):
    s = Session(tmp_path, rounds={"1": {}, "2": {"breakItMalformed": []}})
    s.seat("code-reviewer")
    account = rs.account_from_session(s.save(), extras(checked=["ran the suite"]), Fake().readers())
    assert [c for c in account["checked"] if c.startswith("Break-it test dropped")] == []


# ---- U: load_error --------------------------------------------------------------------------------------------

def _block(path="tests/test_x.py", content="x = 1\n"):
    return {"path": path, "run": "python " + path, "content": content}


def test_u_an_unexpected_indent_names_the_class_the_message_and_the_line():
    assert break_it.load_error(_block(content=UNLOADABLE)) == UNLOADABLE_ERROR


def test_u_an_unindent_that_matches_no_level_is_an_indentation_error():
    error = break_it.load_error(_block(content=UNLOADABLE_CORRECTION))
    assert error.startswith("IndentationError: unindent does not match any outer indentation level (line ")


def test_u_a_missing_indented_block_is_an_indentation_error():
    assert break_it.load_error(_block(content="def f():\nx = 1\n")).startswith("IndentationError: expected an indented block")


def test_u_a_tab_error_is_an_indentation_error():
    error = break_it.load_error(_block(content="if True:\n        x = 1\n\ty = 2\n"))
    assert error is not None and error.startswith("TabError: ") and error.endswith("(line 3)")


@pytest.mark.parametrize("content", ["x = 1\n", "", UNLOADABLE.replace(" def_placeholder", "def_placeholder"), LOADABLE],
                         ids=["plain", "empty", "flush", "re-indented"])
def test_u_content_that_loads_is_none(content):
    assert break_it.load_error(_block(content=content)) is None


@pytest.mark.parametrize("content", ["def f(:\n    pass\n", "x = = 1\n", "print 'a'\n", "x = (\n"],
                         ids=["bad-signature", "double-equals", "py2-print", "unclosed-paren"])
def test_u_another_syntax_error_is_none(content):
    assert break_it.load_error(_block(content=content)) is None


@pytest.mark.parametrize("path", ["tests/a.ts", "tests/a.js", "tests/a.py.txt", "tests/a", "tests/a.PY", ""])
def test_u_a_path_that_is_not_python_is_never_compile_checked(path):
    assert break_it.load_error(_block(path=path, content=UNLOADABLE)) is None


@pytest.mark.parametrize("block", [None, "tests/a.py", [], 3, {}, {"path": "a.py"}, {"content": UNLOADABLE},
                                   {"path": 3, "content": UNLOADABLE}, {"path": "a.py", "content": None},
                                   {"path": "a.py", "content": UNLOADABLE.encode()}],
                         ids=["none", "str", "list", "int", "empty-dict", "no-content", "no-path", "path-not-str",
                              "content-none", "content-bytes"])
def test_u_a_malformed_block_is_none(block):
    assert break_it.load_error(block) is None


@pytest.mark.parametrize("content", ["x = 1\0\n", "\0", "(" * 100000],
                         ids=["null-byte", "only-null", "deeply-nested"])
def test_u_e5_nothing_else_is_raised(content):
    assert break_it.load_error(_block(content=content)) is None


def test_u_load_error_checks_the_content_and_not_the_run_line():
    block = _block(content="x = 1\n")
    block["run"] = " python tests/test_x.py"
    assert break_it.load_error(block) is None


# ---- the one chokepoint ---------------------------------------------------------------------------------------

def _function(tree, name):
    return next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name)


def test_u_the_three_seat_paths_call_the_one_predicate_and_none_re_implements_it():
    tree, _ast_module = TRD._round_driver_ast()
    for name in ("_fold_panel", "_fold_second_test", "_fold_test_correction"):
        calls = [n for n in ast.walk(_function(tree, name)) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and n.func.attr == "load_error"
                 and isinstance(n.func.value, ast.Name) and n.func.value.id == "break_it"]
        assert calls, "%s does not call break_it.load_error" % name
    # no site re-implements it: the driver names no IndentationError and calls no builtin `compile`
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id in ("IndentationError", "TabError")]
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "compile"]
    panel = _function(tree, "_fold_panel")
    keys = {n.args[1].value for n in ast.walk(panel) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "_record_round_wave" and isinstance(n.args[1], ast.Constant)}
    assert "breakItMalformed" in keys
