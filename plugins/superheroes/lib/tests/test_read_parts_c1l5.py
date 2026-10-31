"""A panel reviewer's read list travels from its output to its row in the review record.

Schema: the strict result schema a codex review runs under asks for `readParts` on the findings branch and nulls it on
every other branch. Parser: a findings object's list `readParts` rides on the parse result. Runner: grading, the
running projection, the final result and the replay of a native result each carry it when the source has one. Record:
a panel reviewer that ran and reported no well-formed list shows `readParts: []`; a seat that did not run shows none.
Order: both channels of the round-1 panel order name `readParts`, the gap-sweep order does not.
"""
import copy
import json
import os

import jsonschema
import pytest

import engine_result_channel as erc
import review_record as rr
import review_record_session as rs
import round_orders as ro
import round_phases as rp

import test_engine_dispatch as ted
from test_engine_dispatch import _pin_temp_base_to_tmp_path  # noqa: F401  autouse: keeps views and journals under tmp_path
from test_review_record_session import CODEX, Fake, Session, extras, put_envelope, put_extras
from test_round_orders import _base_context, _gapsweep_placeholders, _panel_placeholders

PARTS = [{"file": "src/a.py", "lines": [[3, 9], [20, 24]]}, {"file": "src/b.py", "lines": [[1, 4]]}]
RESULT_BRANCH_KEY = "readParts"


def _branch(**over):
    return ted._native_review_branch("findings", **over)


def _kinds():
    return [None, *erc.REVIEW_RESULT_KINDS]


# --- schema -------------------------------------------------------------------


def test_the_codex_findings_schema_takes_a_populated_read_list_and_null_and_needs_the_key():
    # axis: readParts is a required slot on the findings branch, an array of file/lines objects or null
    schema = erc.declared_schema("codex", erc.RUN_KIND_REVIEW, "findings")
    jsonschema.validate({"result": _branch(readParts=PARTS)}, schema)
    jsonschema.validate({"result": _branch(readParts=[])}, schema)
    jsonschema.validate({"result": _branch(readParts=None)}, schema)
    omitted = _branch()
    del omitted[RESULT_BRANCH_KEY]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"result": omitted}, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"result": _branch(readParts=[{"file": "a.py"}])}, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"result": _branch(readParts=[{"file": "a.py", "lines": [[1, 2]], "extra": 1}])}, schema)


def test_the_runner_validator_takes_the_same_envelopes_as_jsonschema():
    # axis: the runner's own validator and jsonschema agree on the read list slot
    schema = erc.declared_schema("codex", erc.RUN_KIND_REVIEW, "findings")
    assert erc.validate(schema, {"result": _branch(readParts=PARTS)}) == (True, "")
    assert erc.validate(schema, {"result": _branch(readParts=None)}) == (True, "")
    omitted = _branch()
    del omitted[RESULT_BRANCH_KEY]
    assert erc.validate(schema, {"result": omitted})[0] is False


@pytest.mark.parametrize("kind", [k for k in erc.REVIEW_RESULT_KINDS if k != "findings"])
def test_every_other_branch_carries_the_read_list_as_null_only(kind):
    # axis: only the findings branch can hold a read list, the verdicts, grouping and ruling branches null it
    schema = erc.declared_schema("codex", erc.RUN_KIND_REVIEW, kind)
    branch = ted._native_review_branch(kind)
    jsonschema.validate({"result": branch}, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"result": dict(branch, readParts=PARTS)}, schema)


@pytest.mark.parametrize("kind", _kinds())
def test_strict_mode_holds_for_every_declared_review_schema(kind):
    # axis: the declared review schemas stay inside the strict mode the engine runs them under
    for engine in ("codex", "cursor"):
        schema = erc.declared_schema(engine, erc.RUN_KIND_REVIEW, kind)
        if schema is not None:
            erc.assert_strict_mode_valid(schema)


def test_the_result_contract_prose_names_the_read_list_without_listing_it_as_a_payload():
    # axis: the rendered contract says what readParts is, and the per-kind populate line does not count it as a payload
    text = erc.review_result_contract_from_schema(erc.declared_schema("codex", erc.RUN_KIND_REVIEW, "findings"))
    assert "`readParts`" in text
    populate = [line for line in text.splitlines() if line.lstrip().startswith("- `findings`")]
    assert populate and "readParts" not in populate[0]


# --- parser -------------------------------------------------------------------


def test_the_parser_keeps_a_list_read_list_unchanged():
    # axis: a findings object's list readParts rides on the parse result as it came, its shape is not judged here
    for parts in (PARTS, [], [{"file": "", "lines": "x"}]):
        parsed = ted.EA._parse_review_findings_object({"findings": [], "investigated": ["a.py"], "readParts": parts}, None)
        assert parsed["ok"] is True and parsed["readParts"] == parts


@pytest.mark.parametrize("value", [None, "src/a.py", {"file": "a.py"}, 3])
def test_the_parser_leaves_the_key_off_for_null_or_a_non_list(value):
    # axis: a null or non-list readParts leaves the key off the parse result
    parsed = ted.EA._parse_review_findings_object({"findings": [], "investigated": ["a.py"], "readParts": value}, None)
    assert parsed["ok"] is True and "readParts" not in parsed


def test_the_parser_leaves_the_key_off_when_the_object_has_none():
    # axis: an object without the key gives a result without it, never an invented list
    parsed = ted.EA._parse_review_findings_object({"findings": [], "investigated": ["a.py"]}, None)
    assert parsed["ok"] is True and "readParts" not in parsed


def test_the_investigated_only_near_miss_branch_is_unchanged():
    # axis: an object holding only investigated is read as before, and a readParts beside it is still a near miss
    only = ted.EA._parse_review_findings_object({"investigated": ["a.py"]}, None)
    assert only["ok"] is True and only["findings"] == [] and "readParts" not in only
    beside = ted.EA._parse_review_findings_object({"investigated": ["a.py"], "readParts": PARTS}, None)
    assert beside == {"ok": False, "reason": "unreadable"}


# --- runner -------------------------------------------------------------------


def _repo_with_source(tmp_path):
    repo = ted._repo(tmp_path)
    src = os.path.join(repo, "src", "main.py")
    os.makedirs(os.path.dirname(src), exist_ok=True)
    with open(src, "w", encoding="utf-8") as fh:
        fh.write("# main\n")
    return repo


@pytest.mark.parametrize("branch_over", [
    {"readParts": PARTS},
    {"readParts": PARTS, "findings": [], "investigated": ["src/main.py"]},
])
def test_grading_carries_a_read_list_the_result_has(tmp_path, branch_over):
    # axis: _finish_review_grade_from_parse puts readParts on the graded result, with findings and with the accepted-investigated clean review
    _repo_with_source(tmp_path)
    run_dir, state = ted._native_review_grade_state(tmp_path, _branch(**branch_over))
    grade = ted.ED._grade_review_attempt(run_dir, state, 1)
    assert grade["ok"] is True and grade["readParts"] == PARTS


@pytest.mark.parametrize("branch_over", [
    {},
    {"readParts": None},
    {"findings": [], "investigated": ["src/main.py"]},
])
def test_grading_adds_no_read_list_the_result_lacks(tmp_path, branch_over):
    # axis: a result without a list (null or none) comes out of grading without the key
    _repo_with_source(tmp_path)
    run_dir, state = ted._native_review_grade_state(tmp_path, _branch(**branch_over))
    grade = ted.ED._grade_review_attempt(run_dir, state, 1)
    assert grade["ok"] is True and "readParts" not in grade


def test_the_running_projection_carries_the_read_list(tmp_path):
    # axis: the graded entry of a non-terminal running projection carries the read list of its attempt
    run_dir, state = ted._native_review_grade_state(tmp_path, _branch(readParts=PARTS))
    state["opened"]["runKind"] = ted.ED.RUN_KIND_REVIEW
    (entry,) = ted.ED._build_running_graded(run_dir, state)
    assert entry["readParts"] == PARTS
    run_dir2, state2 = ted._native_review_grade_state(tmp_path, _branch(), run_name="run2")
    state2["opened"]["runKind"] = ted.ED.RUN_KIND_REVIEW
    (entry2,) = ted.ED._build_running_graded(run_dir2, state2)
    assert "readParts" not in entry2


def test_replay_of_a_native_result_carries_the_read_list(tmp_path):
    # axis: the replay of an ended native attempt keeps the read list it was graded with
    run_dir, state = ted._native_review_grade_state(tmp_path, _branch(readParts=PARTS))
    assert ted.ED._parse_review_attempt(run_dir, state, 1)["readParts"] == PARTS
    run_dir2, state2 = ted._native_review_grade_state(tmp_path, _branch(readParts=None), run_name="run2")
    assert "readParts" not in ted.ED._parse_review_attempt(run_dir2, state2, 1)


def test_replay_admits_a_run_saved_before_the_read_list_and_reads_it_as_unreported(tmp_path):
    # axis: a native review run whose saved schema lacks readParts still replays; the list is unreported
    old = erc.prechange_review_schema("codex", erc.RUN_KIND_REVIEW)
    assert "readParts" not in json.dumps(old)
    branch = _branch()
    branch.pop("readParts", None)
    run_dir, state = ted._native_review_grade_state(tmp_path, branch, schema=old)
    parsed = ted.ED._parse_review_attempt(run_dir, state, 1)
    assert parsed is not None
    assert "readParts" not in parsed


def test_replay_still_refuses_a_saved_schema_that_is_neither_current_nor_prechange(tmp_path):
    # axis: the prechange equality in _verify_native_schema; the branch has no readParts, so it would validate against the prechange schema if the saved one were wrongly taken for it
    branch = _branch()
    branch.pop("readParts", None)
    run_dir, state = ted._native_review_grade_state(tmp_path, branch, schema={})
    assert ted.ED._parse_review_attempt(run_dir, state, 1) is None
    # replay returns None without a reason; the grade of the same attempt records it as the forfeit's detail
    grade = ted.ED._grade_review_attempt(run_dir, state, 1)
    assert grade.get("forfeit") is True
    assert grade.get("detail") == "native-schema-unreadable"


def _dispatch(tmp_path, branch):
    def runner(argv, prompt_bytes, timeout, progress_cb, cwd):
        path = ted._resolve_native_result_path(argv, prompt_bytes)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(ted._wrap_native_review_result(branch), fh, separators=(",", ":"))
            fh.write("\n")
        return "", False, 0, ""

    return ted.ED.dispatch_review(
        seat=ted._codex_seat(), prompt_path=ted._valid_prompt(tmp_path), repo_root=_repo_with_source(tmp_path),
        run_engine=ted.FakeRunner([runner]), build_view=ted._fake_build_view(tmp_path))


def test_dispatch_review_returns_the_read_list_the_reviewer_reported(tmp_path):
    # axis: the final dispatch-review result carries the reviewer's readParts beside its findings
    res = _dispatch(tmp_path, _branch(readParts=PARTS))
    assert res["ok"] is True and res["findings"] and res["readParts"] == PARTS


def test_dispatch_review_returns_a_clean_review_with_its_read_list(tmp_path):
    # axis: a clean review (no findings, accepted investigated path) still returns the list it read
    res = _dispatch(tmp_path, _branch(readParts=PARTS, findings=[], investigated=["src/main.py"]))
    assert res["ok"] is True and res["findings"] == [] and res["readParts"] == PARTS


def test_dispatch_review_without_a_read_list_returns_none(tmp_path):
    # axis: a reviewer that gave none (null) comes out without the key, never an invented list
    res = _dispatch(tmp_path, _branch(readParts=None))
    assert res["ok"] is True and "readParts" not in res


# --- the record, from a fixture round 1 ----------------------------------------


GOOD = [{"file": "a.py", "lines": [[1, 10], [20, 24]]}]
MALFORMED = [{"file": "a.py", "lines": [[5, 2]]}]


def _round_one(tmp_path):
    """Three panel seats that ran: a well-formed list, no readParts key, a malformed list; a fourth that did not run."""
    s = Session(tmp_path).seat("code-reviewer").seat("security-reviewer").seat("test-role")
    s.seat("premortem-reviewer", cmd="record-missing", envelope=False)
    session = s.save()
    put_envelope(session, "code-reviewer", {"vendor": "codex", "model": CODEX, "payload": {"findings": [], "readParts": GOOD}})
    put_envelope(session, "security-reviewer", {"vendor": "codex", "model": CODEX, "payload": {"findings": []}})
    put_envelope(session, "test-role", {"vendor": "codex", "model": CODEX, "payload": {"findings": [], "readParts": MALFORMED}})
    # a seat that did not run holds no list, even when its stored envelope carries one
    put_envelope(session, "premortem-reviewer", {"vendor": "codex", "model": CODEX, "payload": {
        "findings": [], "vacuous": True, "reason": "never-ran", "readParts": GOOD}})
    return session


def _rows(session):
    return {v["name"]: v for v in rs.account_from_session(session, extras(), Fake().readers())["reviewers"]}


ABSENT = "<no readParts key>"


def test_a_ran_panel_reviewer_with_no_list_shows_nothing_read(tmp_path):
    # axis: E1 a panel reviewer that ran and reported no list shows readParts [], never an absent key
    rows = _rows(_round_one(tmp_path))
    assert rows["security-reviewer (round 1)"].get("readParts", ABSENT) == []


def test_a_ran_panel_reviewer_with_a_malformed_list_shows_nothing_read(tmp_path):
    # axis: E2 a panel reviewer that ran and reported a list the record would refuse shows readParts []
    rows = _rows(_round_one(tmp_path))
    assert rows["test-role (round 1)"].get("readParts", ABSENT) == []


def test_a_well_formed_list_reaches_its_row_unchanged(tmp_path):
    # axis: a list the record's own validator accepts is copied as it came
    rows = _rows(_round_one(tmp_path))
    assert rows["code-reviewer (round 1)"].get("readParts", ABSENT) == GOOD


def test_a_seat_that_did_not_run_gets_no_read_list(tmp_path):
    # axis: a seat that did not run has no readParts key, whatever its stored envelope holds
    rows = _rows(_round_one(tmp_path))
    (missing,) = [v for k, v in rows.items() if k.startswith("premortem-reviewer")]
    assert "readParts" not in missing


def test_the_written_record_and_summary_show_the_lists(tmp_path):
    # axis: the record writer takes the filled rows, and the summary reads files and lines for the list and nothing for the others
    session = _round_one(tmp_path)
    fake = Fake()
    out = rs.write_from_session(session, put_extras(tmp_path, extras()), str(tmp_path), fake.readers())
    assert out["ok"], out
    record = rr.read(7, readers=fake.readers())
    by_name = {v["name"]: v for v in record["reviewers"]}
    assert by_name["code-reviewer (round 1)"]["readParts"] == GOOD
    assert by_name["security-reviewer (round 1)"]["readParts"] == []
    assert by_name["test-role (round 1)"]["readParts"] == []
    body = "\n".join(c["body"] for c in fake.comments)
    assert body.count("; read 1 files, 15 lines") == 1
    assert body.count("; read nothing") == 2


def test_a_non_panel_row_gets_no_read_list(tmp_path):
    # axis: only panel rows are filled, a verifier row stays without the key
    s = Session(tmp_path).seat("code-reviewer").seat("verifier:0", phase="dispatch-verifiers")
    session = s.save()
    put_envelope(session, "verifier:0", {"vendor": "codex", "model": CODEX, "payload": {"verdicts": []}}, phase="dispatch-verifiers")
    rows = _rows(session)
    assert rows["code-reviewer (round 1)"].get("readParts", ABSENT) == []
    others = [v for k, v in rows.items() if k.startswith("verifier")]
    assert others and all("readParts" not in v for v in others)


# --- the order ----------------------------------------------------------------


@pytest.mark.parametrize("channel,host_seat", [("file", True), ("stdout", False)])
def test_the_round_one_panel_order_names_the_read_list_on_both_channels(channel, host_seat):
    # axis: the delivery text of the rendered panel order names readParts, on the file and the stdout channel
    ctx = _base_context(host_seat=host_seat, placeholders=_panel_placeholders(channel=channel))
    block = ro._panel_derived_placeholders(ctx)["OUTPUT_CHANNEL_BLOCK"]
    assert "readParts" in block
    text, reason = ro.render_order(rp.P_PANEL, "code-reviewer", ctx)
    assert reason is None and "readParts" in text


@pytest.mark.parametrize("channel", ["file", "stdout"])
def test_a_gap_sweep_order_does_not_name_the_read_list(channel):
    # axis: the gap sweep owes no read list, its order never asks for one
    ctx = _base_context(host_seat=(channel == "file"), placeholders=_gapsweep_placeholders(channel=channel))
    text, reason = ro.render_order(rp.P_GAPSWEEP, "gap-sweep", copy.deepcopy(ctx))
    assert reason is None and "readParts" not in text
