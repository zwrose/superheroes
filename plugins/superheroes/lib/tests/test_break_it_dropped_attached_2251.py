"""A dropped finding with an attached test is handled as a dropped finding is today (#2251, C1-L6b).

K1 `break_it.intercept` stamps `kind` on each round-level run entry: `per-area` for a per-area finding, `attached` for any other.
K2 `_break_it_kept_step` parks a dropped-at-compile run that did not pass unless its `kind` is `attached`; a per-area run and a run with no or an unknown `kind` park.
K3 end to end: a session whose only finding is an attached failing test outside the change converges, and its run is kept, marked `droppedAtCompile`.
B1 `_break_it_run_keys` never hashes a `file` that is not a string, on either side of the binding.
B2 a numeric-string `line` on a run binds to the compiled finding at that line.
A1 archiving an older live row keeps the ledger's test text with the run stamp it keeps.
"""
import copy
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _path in (_HERE, _LIB):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import break_it  # noqa: E402
import session_contract  # noqa: E402
import test_break_it as TB  # noqa: E402
import test_break_it_attached_2210 as A  # noqa: E402
import test_break_it_review_round2_2210 as R2  # noqa: E402
from test_break_it_attached_2210 import _pinned_git, fx  # noqa: E402,F401  (fixtures, re-exported for pytest)

RD = A.RD

BLOCK = "break-it-test v1\npath: a.py\nrun: python a.py\n---\npass\n"


# ---- K1: intercept stamps the kind on the round-level run entry ---------------------------------------------


def test_k1_intercept_stamps_kind_per_area_and_attached_on_the_run_entries(tmp_path):
    per_area = TB._finding("t/a.py")
    attached = TB._finding("t/b.py", taxonomy="test-quality")
    kept, runs, _exempt, _stamped = break_it.intercept(
        [per_area, attached], str(tmp_path), "H", runner=TB._fake("failed"))
    assert [(r["file"], r["kind"]) for r in runs] == [
        ("t/a.py", break_it.KIND_PER_AREA), ("t/b.py", break_it.KIND_ATTACHED)]
    assert break_it.KIND_PER_AREA == "per-area" and break_it.KIND_ATTACHED == "attached"
    # the kind rides on the round-level entry only: neither the finding's run stamp nor its record-shaped run carries it
    for finding in kept:
        assert "kind" not in finding[break_it.RUN_FIELD]
        assert all("kind" not in run for run in finding[break_it.RUNS_FIELD])


def test_k1_a_malformed_per_area_block_is_still_stamped_per_area(tmp_path):
    malformed = TB._finding("t/a.py", suggestion="not a block")
    _kept, runs, _exempt, _stamped = break_it.intercept([malformed], str(tmp_path), "H", runner=TB._fake("passed"))
    assert [r["kind"] for r in runs] == [break_it.KIND_PER_AREA]


# ---- K2: the dropped-at-compile park --------------------------------------------------------------------------


def _dropped(outcome, **extra):
    return dict(R2._run_record(outcome), findingKey=None, droppedAtCompile=True, **extra)


@pytest.mark.parametrize("extra, parks", [
    ({"kind": break_it.KIND_ATTACHED}, False),
    ({"kind": break_it.KIND_PER_AREA}, True),
    ({}, True),
    ({"kind": "something-else"}, True),
    ({"kind": None}, True),
], ids=["attached", "per-area", "no kind", "unknown kind", "null kind"])
def test_k2_a_dropped_failed_run_parks_unless_it_is_an_attached_test(extra, parks):
    state = R2._kept_state({1: [_dropped("failed", **extra)]})
    assert RD._break_it_kept_step(state, state["config"]) is parks
    assert (state.get("terminal") == "cannot-certify") is parks
    if parks:
        assert "dropped at compile" in state["certification"]["reason"]


@pytest.mark.parametrize("kind", [break_it.KIND_ATTACHED, break_it.KIND_PER_AREA, None])
def test_k2_a_dropped_not_run_parks_unless_it_is_an_attached_test(kind):
    run = _dropped("not-run", reason="run-error", **({} if kind is None else {"kind": kind}))
    state = R2._kept_state({1: [run]})
    assert RD._break_it_kept_step(state, state["config"]) is (kind != break_it.KIND_ATTACHED)


def test_k2_a_dropped_attached_run_still_parks_when_its_working_copy_was_not_restored():
    run = _dropped("not-run", reason="working-copy-restore-failed", kind=break_it.KIND_ATTACHED)
    state = R2._kept_state({1: [run]})
    assert RD._break_it_kept_step(state, state["config"]) is True
    assert "working copy not restored" in state["certification"]["reason"]


# ---- K3: end to end ---------------------------------------------------------------------------------------------


def test_k3_a_session_whose_only_finding_is_a_dropped_attached_failing_test_converges(fx):
    session = str(fx.session)
    off_diff = A._attached(file="elsewhere/x.py", line=9, title="An attached test on a file outside the change")
    payload = A.TRD._drive_cli(session, fx.config, A._respond(A._seats(test_role=[off_diff])))
    ok, state = RD.load_state(session)
    assert ok
    assert payload["verdict"] == "converged", payload
    assert not [d for d in state["decisions"] if d["kind"] == "cannot-certify"]
    assert state.get("terminal") != "cannot-certify"
    (run,) = state["rounds"]["1"]["breakItRuns"]
    assert run["droppedAtCompile"] is True and run["findingKey"] is None
    assert (run["outcome"], run["kind"], run["file"]) == ("failed", break_it.KIND_ATTACHED, "elsewhere/x.py")
    assert [d["reason"] for d in state["rounds"]["1"]["compileDrops"]] == ["outside the round diff scope"]


# ---- B1: a non-string file is never hashed -----------------------------------------------------------------------

BAD_FILES = [["a.py"], {"f": "a.py"}, None, 7]


@pytest.mark.parametrize("file", BAD_FILES, ids=["list", "dict", "none", "number"])
@pytest.mark.parametrize("with_line", [True, False], ids=["with line", "no line"])
def test_b1_a_run_whose_file_is_not_a_string_is_unmatched_and_dropped_at_compile(file, with_line):
    run = {"file": file, "title": "x"}
    if with_line:
        run["line"] = 291
    out = RD._break_it_run_keys([run], [])
    assert len(out) == 1
    assert out[0]["droppedAtCompile"] is True and out[0]["findingKey"] is None


@pytest.mark.parametrize("file", BAD_FILES, ids=["list", "dict", "none", "number"])
@pytest.mark.parametrize("with_line", [True, False], ids=["with line", "no line"])
def test_b1_a_compiled_finding_whose_file_is_not_a_string_is_not_indexed_and_does_not_crash(file, with_line):
    compiled = [{"file": file, "title": "x", "line": 291, "findingKey": "k", "taxonomy": break_it.TAXONOMY,
                 "suggestion": BLOCK}]
    run = {"file": "a.py", "title": "x"}
    if with_line:
        run["line"] = 291
    out = RD._break_it_run_keys([run], compiled)
    assert len(out) == 1
    assert out[0]["droppedAtCompile"] is True and out[0]["findingKey"] is None


def test_b1_a_string_file_still_binds_next_to_a_finding_whose_file_is_a_list():
    good = {"file": "a.py", "title": "x", "line": 291, "findingKey": "good", "taxonomy": break_it.TAXONOMY,
            "suggestion": BLOCK}
    bad = dict(good, file=["a.py"], findingKey="bad")
    out = RD._break_it_run_keys([{"file": "a.py", "title": "x", "line": 291}], [bad, good])
    assert out[0]["findingKey"] == "good" and not out[0].get("droppedAtCompile")


# ---- B2: a numeric-string line binds -----------------------------------------------------------------------------


def test_b2_a_numeric_string_line_on_a_run_binds_to_the_finding_at_that_line():
    assert session_contract.coerce_line("2") == (True, 2)
    compiled = [{"file": "a.py", "title": "x", "line": 2, "findingKey": "k", "taxonomy": break_it.TAXONOMY,
                 "suggestion": BLOCK}]
    (entry,) = RD._break_it_run_keys([{"file": "a.py", "title": "x", "line": "2"}], compiled)
    assert entry["findingKey"] == "k"
    assert not entry.get("droppedAtCompile")


# ---- A1: the archive keeps the test text that matches the run stamp it keeps ---------------------------------


def test_a1_archiving_an_older_live_row_keeps_the_ledgers_corrected_test_with_its_run():
    key_field = session_contract.FINDING_KEY_FIELD
    first = {"outcome": "failed", "path": "a.py", "sha256": "old", "changedWhy": None}
    corrected = {"outcome": "failed", "path": "a.py", "sha256": "new", "changedWhy": "fixed the syntax"}
    old_text, new_text = BLOCK, BLOCK.replace("pass", "assert True")
    live = {key_field: "k1", "file": "a.py", "title": "t", "suggestion": old_text,
            break_it.RUN_FIELD: first, break_it.RUNS_FIELD: [first]}
    state = {session_contract.DISPOSITION_LEDGER_KEY: [
        {key_field: "k1", "file": "a.py", "title": "t", "suggestion": new_text,
         break_it.RUN_FIELD: corrected, break_it.RUNS_FIELD: [first, corrected]}],
        "dispositionLedgerOwner": session_contract.DISPOSITION_LEDGER_OWNER_VALUE}
    RD._archive_departures(state, [live])
    (row,) = state[session_contract.DISPOSITION_LEDGER_KEY]
    assert row["suggestion"] == new_text
    assert row[break_it.RUN_FIELD] == corrected and row[break_it.RUNS_FIELD] == [first, corrected]


def test_a1_a_live_row_that_is_not_older_keeps_its_own_test_and_stamp():
    key_field = session_contract.FINDING_KEY_FIELD
    first = {"outcome": "failed", "path": "a.py", "sha256": "old"}
    live = {key_field: "k1", "file": "a.py", "title": "t", "suggestion": BLOCK,
            break_it.RUN_FIELD: first, break_it.RUNS_FIELD: [first]}
    state = {session_contract.DISPOSITION_LEDGER_KEY: [
        {key_field: "k1", "file": "a.py", "title": "t", "suggestion": "ledger text",
         break_it.RUN_FIELD: {"outcome": "failed", "path": "a.py", "sha256": "ledger"}, break_it.RUNS_FIELD: [first]}],
        "dispositionLedgerOwner": session_contract.DISPOSITION_LEDGER_OWNER_VALUE}
    before = copy.deepcopy(live)
    RD._archive_departures(state, [live])
    (row,) = state[session_contract.DISPOSITION_LEDGER_KEY]
    assert row["suggestion"] == before["suggestion"] and row[break_it.RUN_FIELD] == first
