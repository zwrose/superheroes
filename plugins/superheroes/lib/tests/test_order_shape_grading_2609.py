"""Issue 2609: every order shape the review round driver can emit, graded by the real gate.

The escape class (#2475, #2527): a fix landed for one order shape (a synthesis grouping in a PR-body run;
an empty grouping on a repeat-only order) while the same class of shape elsewhere stayed unchecked, so the
next shape to meet the grader forfeited. `round_orders.ORDER_SHAPES` now declares every payload shape
`round_driver._advance` emits, in one table; this file holds that table to the code and to the gates:

  * every shape `_advance` can emit is a row, and every key it can write is declared (source census);
  * every seat-answered row's minimal correct answer grades ok at its real gate;
  * its empty answer is graded exactly as the row's `emptyAnswerValid` says;
  * one clearly vacuous answer is refused.

Runner rows are graded by the real grader `ED._grade_review_attempt` over a real opened review run (the
#2527 path: `_build_resolved_inputs` plus `_open_review_run`, with the row's pin and flag on BOTH calls), in
two modes: PR body staged and not staged. Host-reply rows are graded by `payload_contracts.payload_fault`.

Guarded elements (the test function proving each):
  A1  a seat row with no fixture, or a fixture with no row, and a row with no census state   test_a_fixtures_are_exactly_the_seat_rows, test_a_census_states_are_exactly_the_rows
  A2  a malformed row (unknown channel or kind, a pin that is not the row's kind, a missing or surplus emptiness field)   test_a_rows_are_well_formed
  A3  two rows that can both match one payload   test_classifier_matches_exactly_one_row
  B1  an emitted order that classifies to no row or the wrong row, a wrong phase, a wrong `nothingToGroup`   test_b_advance_emits_the_row_it_is_declared_as
  B2  a `step ==` branch of `_advance` with no row, or a row with no branch   test_b_every_branch_of_advance_has_a_row
  C1  a key `_advance` can write that no row declares, or a declared key it never writes   test_c_source_keys_match_the_declared_keys
  C2  a payload construct the census cannot read is a loud failure, never a skip   test_c_unreadable_constructs_fail_loudly
  D1  a minimal correct answer a real grade refuses, in either mode   test_d_minimal_answer_grades_ok
  D2  a vacuous answer a real grade accepts, in either mode   test_d_vacuous_answer_is_refused
  D3  a wrong `emptyAnswerValid` (either way) or a wrong `emptyRefusedBy`   test_d_empty_answer_is_graded_as_the_row_declares
  D4  a wrong `expectedResultKind` or `nothingToGroup` on the opened run   test_d_opened_run_journals_the_row_pin_and_flag
  E   the sweep reply's gate   test_e_host_reply_rows_are_graded_by_payload_fault
  F   a minimal answer the payload contract refuses   test_f_minimal_answers_pass_the_payload_contract

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/order_shape_grading_2609.md
"""
import ast
import copy
import inspect
import json
import os
import sys
import textwrap
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from bite_support import _stamp_ended_from_native_result  # noqa: E402
import payload_contracts as PC  # noqa: E402
import repeat_marks as RM  # noqa: E402
import round_driver as RD  # noqa: E402
import round_orders as RO  # noqa: E402
import round_phases as RP  # noqa: E402
import test_synthesis_nothing_to_group_2527 as G2527  # noqa: E402
import test_synthesis_seat_1858 as S1858  # noqa: E402
from test_engine_dispatch import (  # noqa: E402
    ED,
    _SV_MOD,
    _codex_event_stream,
    _codex_seat,
    _fake_build_view,
    _fed_prompt,
    _repo,
    _sync_native_review_result_from_stdout,
    _valid_prompt,
)
from test_engine_dispatch import _pin_temp_base_to_tmp_path  # noqa: E402,F401  autouse: keeps views and journals under tmp_path

ROWS = RO.ORDER_SHAPES
ALL_IDS = {row["id"] for row in ROWS}
SEAT_ROWS = [row for row in ROWS if row["channel"] != RO.CHANNEL_ORCHESTRATOR]
RUNNER_ROWS = [row for row in ROWS if row["channel"] == RO.CHANNEL_RUNNER]
HOST_ROWS = [row for row in ROWS if row["channel"] == RO.CHANNEL_HOST_REPLY]
ROW_PHASES = {row["phase"] for row in ROWS}
VACUOUS = ED.engine_adapter.REVIEW_FORFEIT_VACUOUS


def _row_id(row):
    return row["id"]


# ---------------------------------------------------------------------------------------------
# the answers: per seat row, the minimal correct answer, the empty answer and one vacuous answer
# ---------------------------------------------------------------------------------------------

# A real file the run's view holds, so an `investigated` entry survives the grader's spot check.
VIEW_FILE = "module_under_review.py"
INV = [VIEW_FILE]
FINDING = {"id": "f1", "message": "issue found"}
RULING = {"id": "f1", "ruling": "discharged", "reason": "resolved in diff",
          "checks": {name: {"answer": "yes", "why": "checked"}
                     for name in ("right", "brokeNothing", "testWouldFail")}}
A_GROUP = {"grouping": [{"member_ids": ["f1", "f2"], "repeatOf": None}]}


def _finding_answers():
    # the order asks for the read list always, so an empty list of findings carries `investigated`
    return {"minimal": {"findings": [dict(FINDING)], "investigated": list(INV)},
            "empty": {"findings": [], "investigated": list(INV)},
            "vacuous": {"findings": []}}


def _held_item_answers():
    # the order asks for each given item once; the empty answer returns none but keeps the read list, so its
    # grade is the empty collection's own, never the investigation floor's (the vacuous answer is that case)
    return {"minimal": {"findings": [dict(FINDING)], "investigated": list(INV)},
            "empty": {"findings": [], "investigated": list(INV)},
            "vacuous": {"findings": []}}


def _survivor_synthesis_answers():
    return {"minimal": copy.deepcopy(A_GROUP), "empty": {"grouping": []}, "vacuous": {"grouping": None}}


def _repeat_only_synthesis_answers():
    return {"minimal": {"grouping": []}, "empty": {"grouping": []}, "vacuous": {"grouping": None}}


FIXTURES = {
    "panel": _finding_answers(),
    "verifiers": {
        "minimal": {"verdicts": [{"id": "v1", "verdict": "CONFIRMED", "reason": "reproduced in test"}],
                    "investigated": list(INV)},
        "empty": {"verdicts": [], "investigated": list(INV)},
        "vacuous": {"verdicts": []},
    },
    "synthesis-survivors-earlier": _survivor_synthesis_answers(),
    "synthesis-survivors": _survivor_synthesis_answers(),
    "synthesis-repeat-only": _repeat_only_synthesis_answers(),
    "synthesis-repeat-none": _repeat_only_synthesis_answers(),
    "seams": _finding_answers(),
    "second-test": _held_item_answers(),
    "second-test-correction": _held_item_answers(),
    "audits": {"minimal": dict(RULING, investigated=list(INV)), "empty": {"id": "f1", "ruling": None},
               "vacuous": {"ruling": None}},
    "audits-verify": {"minimal": dict(RULING, investigated=list(INV)), "empty": {"id": "f1", "ruling": None},
                      "vacuous": {"ruling": None}},
    "scoped-finder": _finding_answers(),
    "sweep": {"minimal": {"hits": [{"file": "a.py", "line": 3, "what": "the described mistake"}]},
              "empty": {"hits": []}, "vacuous": {}},
}


# ---------------------------------------------------------------------------------------------
# the states: the smallest state and config that reach each row's branch in `_advance`
# ---------------------------------------------------------------------------------------------

def _earlier_pool(state):
    return {"entries": RM.build_pool(state, 1, G2527._earlier_entries())}


def _state(step, config=None, **fields):
    state = RD.new_state(S1858._cfg())
    state["step"] = step
    state["round"] = 1
    state.update(fields)
    return state, dict(state["config"], **(config or {}))


def _synthesis(*, survivors, earlier):
    state, config = _state(RP.P_SYNTHESIS)
    state["_verified"] = [dict(S1858._A_FINDING[0], id="f1", verdict="CONFIRMED")] if survivors else []
    state["_refuted"] = [dict(S1858._A_FINDING[0], id="f2", verdict="REFUTED")]
    if earlier:
        state["_earlierPool"] = _earlier_pool(state)
    return state, config


_HELD = {"finding": dict(S1858._A_FINDING[0], id="f1"), "note": "the test never reached the path"}
_CORRECTION = {"restoredHead": "abc123", "items": [{
    "findingKey": "k1", "path": "tests/test_x.py", "reviewerTest": "a", "committedTest": "b",
    "changedWhy": "a missing import", "why": "the change lets it pass"}]}
_RESTORE = {"stage": "restore", "then": "after-audits", "items": [{
    "findingKey": "k1", "path": "tests/test_x.py", "content": "a", "sha256": "0" * 64}]}
_SWEEP = {"_sweepParts": [{"part": 1, "files": ["a.py"]}], "_sweepSearcher": {"vendor": "claude"},
          "_sweepPending": [{"sweepId": "s1", "findingKey": "k1", "title": "t", "file": "a.py", "line": 1,
                             "searchDescription": {"kind": "k", "looksLike": "l"}}]}

CENSUS_STATES = {
    "panel": _state(RP.P_PANEL),
    "verifiers": _state(RP.P_VERIFIERS, _toVerify=[dict(S1858._A_FINDING[0])]),
    "synthesis-survivors-earlier": _synthesis(survivors=True, earlier=True),
    "synthesis-survivors": _synthesis(survivors=True, earlier=False),
    "synthesis-repeat-only": _synthesis(survivors=False, earlier=True),
    "synthesis-repeat-none": _synthesis(survivors=False, earlier=False),
    "seams": _state(RP.P_SEAMS, slicePlan={"sliced": True, "slices": [{"id": "s1", "parts": [{"file": "a.py"}]}]}),
    "second-test": _state(RP.P_SECOND_TEST, _secondTestHeld=[_HELD]),
    "second-test-correction": _state(RP.P_SECOND_TEST, **{RD.TEST_CORRECTION_PENDING_FIELD: _CORRECTION}),
    "audits": _state(RP.P_AUDITS, _auditTargets=[{"id": "t1"}]),
    "audits-verify": _state(RP.P_AUDITS, {"verifyCommand": "run the checks"}, _auditTargets=[{"id": "t1"}],
                            _verifyThen=RD.VERIFY_THEN_POST_AUDITS),
    "scoped-finder": _state(RP.P_SCOPED, _newSurface={"a.py": [[1, 3]]}),
    "sweep": _state(RP.P_SWEEP, **_SWEEP),
    "run-verify": _state(RP.P_VERIFY, {"verifyCommand": "run the checks"}),
    "run-verify-restored": _state(RP.P_VERIFY, {"verifyCommand": "run the checks"}, _restoredHead="abc123"),
    "apply-fixes-batch": _state(RP.P_APPLY_FIXES, _fixBatch=[{"id": "f1"}], _fixStepHead="abc123"),
    "apply-fixes-restore": _state(RP.P_APPLY_FIXES, _fixStepHead="abc123", **{RD.TEST_RESTORE_FIELD: _RESTORE}),
}


def _emit(shape_id):
    state, config = copy.deepcopy(CENSUS_STATES[shape_id])
    return RD._advance(state, config)


# ---------------------------------------------------------------------------------------------
# A. the table is complete and well formed
# ---------------------------------------------------------------------------------------------

def test_a_fixtures_are_exactly_the_seat_rows():
    # axis: a row with no fixture, or a fixture for no row, fails and names the id (A1)
    seat_ids = {row["id"] for row in SEAT_ROWS}
    assert set(FIXTURES) == seat_ids, "no fixture for %s; no row for fixture %s" % (
        sorted(seat_ids - set(FIXTURES)), sorted(set(FIXTURES) - seat_ids))
    for shape_id, answers in FIXTURES.items():
        assert set(answers) == {"minimal", "empty", "vacuous"}, shape_id


def test_a_census_states_are_exactly_the_rows():
    # axis: a row with no census state, or a state for no row, fails and names the id (A1)
    assert set(CENSUS_STATES) == ALL_IDS, "no census state for %s; no row for state %s" % (
        sorted(ALL_IDS - set(CENSUS_STATES)), sorted(set(CENSUS_STATES) - ALL_IDS))


def test_a_rows_are_well_formed():
    # axis: every row declares its channel, kind, pin, flag and emptiness in the table's own vocabulary (A2)
    assert len(ALL_IDS) == len(ROWS), "a row id is repeated"
    for row in ROWS:
        shape_id = row["id"]
        assert row["phase"] in RP.ALL_PHASES and row["phase"] != RP.P_TERMINAL, shape_id
        assert row["channel"] in RO.ORDER_SHAPE_CHANNELS, shape_id
        assert isinstance(row["payloadKeys"], frozenset) and row["payloadKeys"], shape_id
        assert isinstance(row["nothingToGroup"], bool), shape_id
        assert ("nothingToGroup" in row["payloadKeys"]) == row["nothingToGroup"], shape_id
        if row["channel"] == RO.CHANNEL_RUNNER:
            assert row["resultKind"] in ED.engine_adapter.REVIEW_RESULT_KINDS, shape_id
            assert row["expectedResultKind"] in (None, row["resultKind"]), shape_id
        else:
            assert row["resultKind"] is None and row["expectedResultKind"] is None, shape_id
        if row["nothingToGroup"]:
            assert row["phase"] == RP.P_SYNTHESIS and row["resultKind"] == "grouping", shape_id
        if row["channel"] == RO.CHANNEL_ORCHESTRATOR:
            assert "emptyAnswerValid" not in row and "emptyRefusedBy" not in row, shape_id
            continue
        assert isinstance(row["emptyAnswerValid"], bool), shape_id
        assert isinstance(row["orderAllowsEmpty"], bool), shape_id
        # a gate that refuses what the order allows is a defect, never a declaration
        assert row["emptyAnswerValid"] or not row["orderAllowsEmpty"], shape_id
        if row["emptyAnswerValid"]:
            assert "emptyRefusedBy" not in row, shape_id
        else:
            assert row["emptyRefusedBy"] in RO.EMPTY_REFUSED_BY, shape_id


def _canonical_payload(row):
    conditions = dict(row["when"])
    payload = {}
    for key in row["payloadKeys"]:
        payload[key] = [] if conditions.get(key) == "empty" else (["x"] if key in conditions else True)
    return payload


def test_classifier_matches_exactly_one_row():
    # axis: no payload can match two rows; a payload with an extra or a missing key, or the wrong phase, matches none (A3)
    for row in ROWS:
        payload = _canonical_payload(row)
        assert RO.matching_order_shapes(row["phase"], payload) == [row["id"]], row["id"]
        assert RO.order_shape(row["phase"], dict(payload, surplus=True)) is None, row["id"]
        other = next(p for p in ROW_PHASES if p != row["phase"])
        assert RO.matching_order_shapes(other, payload) != [row["id"]], row["id"]
    for phase in ROW_PHASES:
        assert RO.order_shape(phase, {}) is None, phase
    assert RO.order_shape(RP.P_PANEL, None) is None
    assert RO.order_shape("not-a-phase", {}) is None


# ---------------------------------------------------------------------------------------------
# B. the real `_advance` emits each row
# ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("row", ROWS, ids=_row_id)
def test_b_advance_emits_the_row_it_is_declared_as(row):
    # axis: the order `_advance` emits for the row's state is classified as that row, in that phase, with the row's flag (B1)
    out = _emit(row["id"])
    assert out["phase"] == row["phase"] and out["action"] == row["phase"], out
    payload = out["payload"]
    assert RO.matching_order_shapes(out["phase"], payload) == [row["id"]], (sorted(payload), out["phase"])
    assert RO.order_shape(out["phase"], payload) == row["id"]
    assert row["nothingToGroup"] == (payload.get("nothingToGroup") is True), payload


# ---------------------------------------------------------------------------------------------
# C. the source census of `_advance`
# ---------------------------------------------------------------------------------------------

class UnreadableCensus(Exception):
    """A payload construct in `_advance` or a helper that the census cannot read."""


def _helper_source(name):
    return textwrap.dedent(inspect.getsource(getattr(RD, name)))


def _helper_keys(name, resolve_helper):
    fn = ast.parse(resolve_helper(name)).body[0]
    returned = [node.value for node in ast.walk(fn) if isinstance(node, ast.Return) and node.value is not None]
    if not returned:
        raise UnreadableCensus("helper %s returns no value the census can read" % name)
    keys = set()
    for value in returned:
        keys |= _value_keys(value, resolve_helper, in_helper=True)
    return keys


def _value_keys(value, resolve_helper, in_helper=False):
    """The string keys of a payload-valued expression: a dict literal, `dict(...)`, or (one level) a helper call."""
    if isinstance(value, ast.Dict):
        keys = set()
        for key in value.keys:
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                raise UnreadableCensus("a dict key that is not a string literal (a computed key or a ** spread), line %d" % value.lineno)
            keys.add(key.value)
        return keys
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
        if value.func.id == "dict":
            keys = set()
            for arg in value.args:
                keys |= _value_keys(arg, resolve_helper, in_helper)
            for kw in value.keywords:
                if kw.arg is None:
                    raise UnreadableCensus("dict(**spread), line %d" % value.lineno)
                keys.add(kw.arg)
            return keys
        if not in_helper:
            return _helper_keys(value.func.id, resolve_helper)
    raise UnreadableCensus("a payload value the census cannot read: %s" % ast.dump(value)[:90])


def _is_payload(node):
    return isinstance(node, ast.Name) and node.id == "payload"


def _branch_keys(body, resolve_helper):
    keys = set()
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if _is_payload(target):
                        keys |= _value_keys(node.value, resolve_helper)
                    elif isinstance(target, ast.Subscript) and _is_payload(target.value):
                        if not (isinstance(target.slice, ast.Constant) and isinstance(target.slice.value, str)):
                            raise UnreadableCensus("payload[...] with a key that is not a string literal, line %d" % node.lineno)
                        keys.add(target.slice.value)
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                if _is_payload(node.target) or (isinstance(node.target, ast.Subscript) and _is_payload(node.target.value)):
                    raise UnreadableCensus("an augmented or annotated write to payload, line %d" % node.lineno)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and _is_payload(node.func.value):
                    raise UnreadableCensus("payload.%s(...), line %d" % (node.func.attr, node.lineno))
                # a call handed `payload` itself can add keys the census never sees (a helper that mutates it)
                if any(_is_payload(arg) or (isinstance(arg, ast.Starred) and _is_payload(arg.value))
                       for arg in node.args) or any(_is_payload(kw.value) for kw in node.keywords):
                    raise UnreadableCensus("a call that receives payload, line %d" % node.lineno)
    return keys


def _step_phase(test, resolve_phase):
    """The phase of a `step == <PHASE>` test, else None."""
    if (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name) and test.left.id == "step"
            and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq)
            and isinstance(test.comparators[0], ast.Name)):
        return resolve_phase(test.comparators[0].id)
    return None


def _census(source, resolve_phase, resolve_helper):
    """{phase: every string key the phase's `step ==` branch can put into `payload`}."""
    fn = ast.parse(textwrap.dedent(source)).body[0]
    found = {}

    def walk(node):
        phase = _step_phase(node.test, resolve_phase)
        if phase is not None:
            found.setdefault(phase, set()).update(_branch_keys(node.body, resolve_helper))
        for sub in node.orelse:
            if isinstance(sub, ast.If):
                walk(sub)

    for stmt in fn.body:
        if isinstance(stmt, ast.If):
            walk(stmt)
    return found


def _advance_census():
    return _census(inspect.getsource(RD._advance), lambda name: getattr(RD, name), _helper_source)


def test_b_every_branch_of_advance_has_a_row():
    # axis: the `step ==` phases `_advance` branches on (read by `ast`, never typed) are exactly the rows' phases (B2)
    branches = set(_advance_census()) - {RP.P_TERMINAL}
    assert branches == ROW_PHASES, "branch with no row: %s; row with no branch: %s" % (
        sorted(branches - ROW_PHASES), sorted(ROW_PHASES - branches))


@pytest.mark.parametrize("phase", sorted(ROW_PHASES))
def test_c_source_keys_match_the_declared_keys(phase):
    # axis: every key `_advance` can write for a phase is declared by one of its rows, and every declared key is written (C1)
    written = _advance_census()[phase]
    declared = set().union(*(row["payloadKeys"] for row in ROWS if row["phase"] == phase))
    assert written <= declared, "keys `_advance` writes that no %s row declares: %s" % (phase, sorted(written - declared))
    assert declared <= written, "keys %s rows declare that `_advance` never writes: %s" % (phase, sorted(declared - written))


_BRANCH = """
def _advance(state, config):
    if step == P_A:
        {write}
    return {{}}
"""


@pytest.mark.parametrize("write", [
    pytest.param('payload = {"a": 1, **extra}', id="dict-spread"),
    pytest.param('payload = {key: 1}', id="computed-key"),
    pytest.param('payload = dict(**extra)', id="dict-call-spread"),
    pytest.param('payload = {"a": 1}\n        payload.update(extra)', id="update-call"),
    pytest.param('payload = {"a": 1}\n        payload[key] = 2', id="computed-subscript"),
    pytest.param('payload = build()', id="unresolved-helper"),
    pytest.param('payload = {"a": 1}\n        extend(payload)', id="call-receives-payload"),
    pytest.param('payload = {"a": 1}\n        extend(target=payload)', id="call-receives-payload-by-name"),
])
def test_c_unreadable_constructs_fail_loudly(write):
    # axis: a branch the census cannot read raises with the construct named; it is never skipped (C2)
    helpers = {"build": "def build():\n    return other()\n"}
    with pytest.raises(UnreadableCensus):
        _census(_BRANCH.format(write=write), lambda name: name, lambda name: helpers[name])


def test_c_readable_constructs_are_read():
    # axis: the census reads a dict literal, a subscript write, dict(helper(), k=v) and a helper's returned dict
    helpers = {"build": "def build():\n    return {'h': 1}\n"}
    source = _BRANCH.format(write='payload = dict(build(), k=1)\n        payload["s"] = 2')
    assert _census(source, lambda name: name, lambda name: helpers[name]) == {"P_A": {"h", "k", "s"}}


# ---------------------------------------------------------------------------------------------
# D. runner rows: a real opened review run, graded by the real grader
# ---------------------------------------------------------------------------------------------

def _open_run(tmp_path, run_dir, *, expected_result_kind, nothing_to_group, pr_body_staged):
    """Open a real review run (no process spawned): `_manual_open_review_run` with the row's pin and flag
    threaded through BOTH the real `_build_resolved_inputs` and the real `_open_review_run`, a real file
    in the view for `investigated`, and (when staged) the PR body on `viewMeta` and `run-opened`."""
    repo_root = _repo(tmp_path)
    with open(os.path.join(repo_root, VIEW_FILE), "w", encoding="utf-8") as fh:
        fh.write("VALUE = 1\n")
    view = _fake_build_view(tmp_path)(os.path.realpath(repo_root))
    pr_body_source = None
    if pr_body_staged:
        view["prBodyPath"] = _SV_MOD.PR_BODY_FILE_NAME
        view["prBodyBytes"] = 12
        pr_body_source = os.path.join(str(tmp_path), "session", "pr-body.md")
    cwd = os.path.realpath(view["path"])
    seat = _codex_seat()
    built = ED.engine_adapter.build_argv_result(seat, "review", {"model": "sonnet", "cwd": cwd})
    prompt_path = _valid_prompt(tmp_path)
    with open(prompt_path, encoding="utf-8") as fh:
        base = fh.read()
    os.makedirs(run_dir, exist_ok=True)
    progress_path = os.path.join(run_dir, "progress.jsonl")
    resolved_inputs = ED._build_resolved_inputs(
        seat=seat, role_kind="review", repo_root=os.path.realpath(repo_root), run_dir_real=run_dir,
        run_dir_source="caller", staged_prompt_path=os.path.join(run_dir, ED.PROMPT_NAME),
        timeout=ED.RETRY_MIN_TIMEOUT, timeout_source="default",
        retry_timeout=ED.RETRY_MIN_TIMEOUT, retry_timeout_source="default",
        max_wait=None, max_wait_source="default", preflight_timeout=None,
        preflight_timeout_source="declared-none", mode="review", mode_source="default",
        expected_result_kind=expected_result_kind,
        expected_result_kind_source="caller" if expected_result_kind else "declared-none",
        base_sha=None, base_sha_source="declared-none", diff_base=view.get("diffBase"),
        diff_base_source="resolved" if view.get("diffBase") is not None else "declared-none",
        progress_path=progress_path, progress_path_source="resolved",
        engine_model_opts={"cwd": cwd}, nothing_to_group=nothing_to_group,
    )
    ok, detail = ED._open_review_run(
        run_dir, engine="codex", argv=built["argv"], cwd=cwd,
        timeout=ED.RETRY_MIN_TIMEOUT, retry_timeout=ED.RETRY_MIN_TIMEOUT,
        prompt_path=prompt_path, view_path=view["path"], view_meta=view,
        fed_prompt=_fed_prompt(base, view_meta=view), order_id="test-order",
        progress_path=progress_path, repo_root=os.path.realpath(repo_root),
        resolved_inputs=resolved_inputs, expected_result_kind=expected_result_kind,
        pr_body_source_path=pr_body_source, nothing_to_group=nothing_to_group,
        echo_nonce="nonce-2609",
    )
    assert ok, detail
    return view


def _grade(tmp_path, payload, *, expected_result_kind, nothing_to_group, tool_calls, pr_body_staged,
           run_name="run"):
    """Open a real run, stage `payload` as attempt 1's result with `tool_calls` completed tool calls in the
    engine's event stream, grade it with the real grader."""
    run_dir = str(tmp_path / run_name)
    _open_run(tmp_path, run_dir, expected_result_kind=expected_result_kind,
              nothing_to_group=nothing_to_group, pr_body_staged=pr_body_staged)
    text = json.dumps(payload)
    stdout = _codex_event_stream(text, action_items=tool_calls)
    with open(os.path.join(run_dir, "attempt-1.stdout"), "w", encoding="utf-8") as fh:
        fh.write(stdout)
    with open(os.path.join(run_dir, "attempt-1.stderr"), "w", encoding="utf-8") as fh:
        fh.write("")
    _sync_native_review_result_from_stdout(run_dir, text)
    ED._journal_append(run_dir, {"kind": "attempt-started", "attempt": 1, "childPid": 1, "at": time.time()})
    ended = _stamp_ended_from_native_result(run_dir, {
        "exit": 0, "timedOut": False, "signal": None, "refusal": None, "at": time.time(),
        "wallSeconds": 1.0, "stdoutBytes": len(stdout),
    })
    ED._journal_append(run_dir, {"kind": "attempt-ended", "attempt": 1, **ended})
    records, _ = ED._journal_read(run_dir)
    return ED._grade_review_attempt(run_dir, ED._journal_state(records), 1)


def _grade_answer(tmp_path, row, which, *, tool_calls, pr_body_staged):
    return _grade(tmp_path, FIXTURES[row["id"]][which], expected_result_kind=row["expectedResultKind"],
                  nothing_to_group=row["nothingToGroup"], tool_calls=tool_calls, pr_body_staged=pr_body_staged,
                  run_name="%s-%s-%s" % (row["id"], which, "staged" if pr_body_staged else "plain"))


MODES = [pytest.param(True, id="pr-body-staged"), pytest.param(False, id="pr-body-not-staged")]


def _seat_key(row, answer):
    """The seat key `payload_fault` is asked about: an audit's own id, a searcher's key, else none."""
    if row["phase"] == RP.P_AUDITS:
        return answer.get("id")
    if row["phase"] == RP.P_SWEEP:
        return PC.SEAT_SEARCHER_PREFIX + "s1:1"
    return None


def _answer_without_runner_keys(answer):
    return {key: value for key, value in answer.items() if key != "investigated"}


def _fault(row, answer):
    return PC.payload_fault(row["phase"], _answer_without_runner_keys(answer), _seat_key(row, answer))


@pytest.mark.parametrize("pr_body_staged", MODES)
@pytest.mark.parametrize("row", RUNNER_ROWS, ids=_row_id)
def test_d_minimal_answer_grades_ok(tmp_path, row, pr_body_staged):
    # axis: the row's minimal correct answer, from a seat the runner saw use tools, grades ok under the row's pin and flag (D1)
    grade = _grade_answer(tmp_path, row, "minimal", tool_calls=1, pr_body_staged=pr_body_staged)
    assert grade.get("ok") is True, grade
    assert grade.get("resultKind") == row["resultKind"], grade
    assert "forfeit" not in grade, grade


@pytest.mark.parametrize("pr_body_staged", MODES)
@pytest.mark.parametrize("row", RUNNER_ROWS, ids=_row_id)
def test_d_vacuous_answer_is_refused(tmp_path, row, pr_body_staged):
    # axis: an empty or absent payload with no accepted `investigated` and no observed tool call is refused (D2)
    grade = _grade_answer(tmp_path, row, "vacuous", tool_calls=0, pr_body_staged=pr_body_staged)
    assert grade.get("ok") is not True, grade
    assert grade.get("forfeit") is True, grade


@pytest.mark.parametrize("pr_body_staged", MODES)
@pytest.mark.parametrize("row", RUNNER_ROWS, ids=_row_id)
def test_d_empty_answer_is_graded_as_the_row_declares(tmp_path, row, pr_body_staged):
    # axis: `emptyAnswerValid` True grades ok at the runner and passes the payload contract; False is refused by the gate `emptyRefusedBy` names (D3)
    grade = _grade_answer(tmp_path, row, "empty", tool_calls=1, pr_body_staged=pr_body_staged)
    empty = FIXTURES[row["id"]]["empty"]
    if row["emptyAnswerValid"]:
        assert grade.get("ok") is True, grade
        assert _fault(row, empty) is None, _fault(row, empty)
    elif row["emptyRefusedBy"] == RO.REFUSED_BY_RUNNER:
        assert grade.get("ok") is not True and grade.get("forfeit") is True, grade
    else:
        assert row["emptyRefusedBy"] == RO.REFUSED_BY_PAYLOAD_FAULT
        assert _fault(row, empty) is not None, "payload_fault accepts the empty answer %r" % (empty,)


@pytest.mark.parametrize("row", RUNNER_ROWS, ids=_row_id)
def test_d_opened_run_journals_the_row_pin_and_flag(tmp_path, row):
    # axis: the run-opened record carries `nothingToGroup` and the pin exactly as the row declares (D4, edge 7)
    run_dir = str(tmp_path / "opened")
    _open_run(tmp_path, run_dir, expected_result_kind=row["expectedResultKind"],
              nothing_to_group=row["nothingToGroup"], pr_body_staged=False)
    records, _ = ED._journal_read(run_dir)
    opened = next(rec for rec in records if rec.get("kind") == "run-opened")
    if row["nothingToGroup"]:
        assert opened.get("nothingToGroup") is True, opened
        assert opened["resolvedInputs"]["nothingToGroup"] is True
    else:
        assert "nothingToGroup" not in opened and "nothingToGroup" not in opened["resolvedInputs"], opened
    assert opened.get("expectedResultKind") == row["expectedResultKind"], opened


# ---------------------------------------------------------------------------------------------
# E. host-reply rows: the payload contract is the gate
# ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("row", HOST_ROWS, ids=_row_id)
def test_e_host_reply_rows_are_graded_by_payload_fault(row):
    # axis: a searcher's reply passes `payload_fault` with hits or with none, and a reply with no `hits` is refused
    answers = FIXTURES[row["id"]]
    assert row["phase"] == RP.P_SWEEP
    assert _fault(row, answers["minimal"]) is None, _fault(row, answers["minimal"])
    assert (_fault(row, answers["empty"]) is None) == row["emptyAnswerValid"], _fault(row, answers["empty"])
    assert _fault(row, answers["vacuous"]) is not None


# ---------------------------------------------------------------------------------------------
# F. the minimal answers satisfy the payload contract
# ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("row", SEAT_ROWS, ids=_row_id)
def test_f_minimal_answers_pass_the_payload_contract(row):
    # axis: the answer a row's order asks for is one `payload_fault` accepts at record time (runner-only keys stripped)
    minimal = FIXTURES[row["id"]]["minimal"]
    assert _fault(row, minimal) is None, _fault(row, minimal)
