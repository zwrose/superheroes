"""C4 layer 2: the round-1 repository sweep.

The invariant: in round 1 of a non-returning session, each verifier-confirmed Important or Critical finding gets exactly
one repository-wide search, using only the search description its independent raising reviewer wrote (stamped by the
driver, its author family outside every maker family at sweep time); each hit on a line the PR touched becomes its own
finding that the verifier must grade before any fix can select it; each other hit is listed on `outsideThisPR` under that
sweep's own `kind: "sweep"` entry with file, line and the mistake; and no finding staged in round 1 is lost across the
extra verifier pass.

S1 who qualifies (edges 1-3, 17, 18) · S2 not-run reasons (4-7, 20) · S3 the file parts (8) · S4 the fold of the hits
(9-14) · S5 the sweep pass through the verifiers (15, 16) · S6 resume (19) · S7 the shared helpers, contract and
disclosure · S8 driven end to end through next/submit, and the record.

Bite-proof record: c4_wo2a_sweep
"""
import copy
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import decision_kinds  # noqa: E402
import model_registry  # noqa: E402
import payload_contracts as PC  # noqa: E402
import pr_body_stage  # noqa: E402
import receipt_disclosures  # noqa: E402
import review_record as rr  # noqa: E402
import review_record_session as rs  # noqa: E402
import round_adapters as RA  # noqa: E402
import round_driver as RD  # noqa: E402
import round_phases as RP  # noqa: E402
import session_contract as SC  # noqa: E402
import test_break_it_loop as BL  # noqa: E402
import test_round_driver as TRD  # noqa: E402
import test_synthesis_seat_1858 as S1858  # noqa: E402
import verification  # noqa: E402
from session_checkout import enter_checkout  # noqa: E402
from test_review_record_session import Fake, Session, put_extras  # noqa: E402
import test_review_record_session as TRS  # noqa: E402

CONSEQUENCE = "a defect stays in the change"
KIND = "unchecked retry"
# the host the searchers run on is claude (family anthropic), whose mechanical cell is haiku; the verifier cells are live
HOST = dict(TRD._nonpanel_cell_proof(["claude", "codex"]), hostFamily="anthropic")
INDEPENDENT = "codex"  # the reviewer that wrote the description: a family outside the makers
CONFIRMED = {"verdict": "CONFIRMED", "reason": "reproduced", "evidence": "ran: 1 failed"}
PLAUSIBLE = {"verdict": "PLAUSIBLE", "reason": "could not run it"}
REFUTED = {"verdict": "REFUTED", "reason": "the guard holds"}
MISSED_PATH = {"verdict": "PLAUSIBLE", "reason": "the first test never calls the retry path", "pathReached": False}

# src/a.py touched head lines: 2, 3 (next to a deleted run) and 19 (added); 1, 4 and 20 are context. src/b.py is new:
# its lines 1-6 are touched.
DIFF = (
    "diff --git a/src/a.py b/src/a.py\n"
    "index 1111111..2222222 100644\n"
    "--- a/src/a.py\n"
    "+++ b/src/a.py\n"
    "@@ -1,7 +1,5 @@\n"
    " l1\n l2\n-d3\n-d4\n l5\n l6\n l7\n"
    "@@ -20,3 +18,4 @@\n"
    " c18\n+add19\n c20\n c21\n"
    "diff --git a/src/b.py b/src/b.py\n"
    "new file mode 100644\n"
    "index 0000000..3333333\n"
    "--- /dev/null\n"
    "+++ b/src/b.py\n"
    "@@ -0,0 +1,6 @@\n"
    "+b1\n+b2\n+b3\n+b4\n+b5\n+b6\n")


def _description(**over):
    return dict({"kind": KIND, "looksLike": "a retry with no cap", "examples": ["while True: retry()"]}, **over)


def _finding(title="Retry without a cap", line=2, file="src/a.py", severity="Important", **extra):
    out = {"title": title, "file": file, "line": line, "severity": severity, "consequence": CONSEQUENCE,
           "body": "the body", "confidence": "High", "searchDescription": _description()}
    out.update(extra)
    return out


def _hit(line, file="src/a.py", what="retries with no cap"):
    return {"file": file, "line": line, "what": what}


def _seat(sweep_id="S-1", part=1):
    return RA.sweep_seat_key(sweep_id, part)


def _both(*hits, sweep_id="S-1"):
    """Both parts of a two-file head answering: part 1 returns `hits`, part 2 nothing."""
    return {_seat(sweep_id, 1): list(hits), _seat(sweep_id, 2): []}


@pytest.fixture
def world(tmp_path, monkeypatch):
    for module in (RD, TRD.RD):  # the verifiers seat on the host's own claude, outside the makers' families
        monkeypatch.setattr(module, "_reviewer_engine_vendor", lambda root: ("claude", RD.VENDOR_SOURCE_CONFIGURED))
    w = BL.World(tmp_path)
    w.state["reviewedDiff"] = DIFF
    w.state["config"]["fixerVendor"] = "cursor"  # the host (claude) and codex are then outside the makers' families
    w.state["config"]["seatMap"] = copy.deepcopy(HOST)
    w.staged = []  # the titles every verifier fold was asked about
    return w


def _fold(world, phase, artifact):
    RD._fold(world.state, world.state["config"], phase, artifact, session_dir=str(world.session))
    return world.state


def _panel(world, ran=None, round_no=None, **by_seat):
    """Fold one panel round whose seats return the given findings (`code_reviewer=[...]` -> seat `code-reviewer`)."""
    if round_no is not None:
        world.state["round"] = round_no
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    for name, found in by_seat.items():
        seats[name.replace("_", "-")] = {"findings": list(found)}
    artifact = {"seats": seats, "ranManifest": {"code-reviewer": INDEPENDENT} if ran is None else ran}
    return _fold(world, RD.P_PANEL, artifact)


def _verify(world, table=None, silent=()):
    """One verifier fold over the staged `_toVerify`; `table` is {title: verdict}, CONFIRMED when a title is not in it,
    and a title in `silent` gets no verdict at all."""
    state = world.state
    verdicts = []
    for staged in verification.stage_ids(state["_toVerify"]):
        world.staged.append(staged["title"])
        if staged["title"] not in silent:
            verdicts.append(dict((table or {}).get(staged["title"], CONFIRMED), id=staged["id"]))
    vendor = RD._nonpanel_selection(state, str(world.session), RD.P_VERIFIERS)[0]
    return _fold(world, RD.P_VERIFIERS, {"verdicts": verdicts, "verifierVendor": vendor})


def _sweep(world, hits_by_seat):
    return _fold(world, RD.P_SWEEP, {"seats": {seat: {"hits": list(hits)} for seat, hits in hits_by_seat.items()}})


def _to_sweep(world, *findings, table=None, **panel_kw):
    """Raise `findings`, confirm them by `table` and return the state at the sweep step."""
    _panel(world, code_reviewer=list(findings or [_finding()]), **panel_kw)
    state = _verify(world, table)
    assert state["step"] == RD.P_SWEEP, (state["step"], _rows(state))
    return state


def _rows(state):
    return state["rounds"]["1"].get("sweeps") or []


def _sweep_entries(state):
    return [e for e in state.get("outsideThisPR") or [] if e["source"]["kind"] == "sweep"]


def _not_sweeping(state, reason=None, reached=True):
    """The round went past the sweep trigger without a sweep step; `reason` is the one every recorded sweep carries.
    `reached` is False for a round that never reaches the trigger's sweep step (a returning session)."""
    assert state["step"] != RD.P_SWEEP and "_sweepPending" not in state
    assert state.get("_sweepDone") is (True if reached else None)
    if reason is None:
        assert not _rows(state)
    else:
        assert [r.get("notRun") for r in _rows(state)] == [reason]
        assert any(d["kind"] == "sweep-not-run" for d in state["decisions"])
        assert not any(d["kind"] == "sweep-dispatched" for d in state["decisions"])


@pytest.fixture
def routed(monkeypatch):
    """The `(verified titles, refuted titles)` each verifier fold carried to the route toward synthesis."""
    seen = []
    original = RD._route_to_synthesis

    def spy(state, config, session_dir):
        seen.append(([f["title"] for f in state["_verified"]], [f["title"] for f in state["_refuted"]]))
        return original(state, config, session_dir)

    monkeypatch.setattr(RD, "_route_to_synthesis", spy)
    return seen


# ---- S1 who qualifies -----------------------------------------------------------------------------------------


def test_s1_a_confirmed_important_finding_is_swept_once_with_the_reviewers_description_and_no_author(world):
    # axis: the one sweep a qualifying finding gets reads the description its reviewer wrote and nothing else
    state = _to_sweep(world)
    (row,) = _rows(state)
    assert (row["sweepId"], row["title"], row["file"], row["line"], row["parts"]) == (
        "S-1", "Retry without a cap", "src/a.py", 2, 2)
    assert row["findingKey"] == SC.finding_identity_key(_finding())
    assert (row["missing"], row["inside"], row["outside"], row["covered"], row["dropped"], row["ungraded"]) == (
        [], 0, 0, 0, 0, 0)
    payload = RD._sweep_payload(state)
    (sweep,) = payload["sweeps"]
    assert sweep["searchDescription"] == _description()  # the reviewer's, with no `author`
    assert payload["searcher"] == {"vendor": "claude", "model": "haiku-4.5", "effort": "medium"}
    assert state["_swept"] == [row["findingKey"]] and state["_sweepSeq"] == 1
    assert any(d["kind"] == "sweep-dispatched" for d in state["decisions"])


@pytest.mark.parametrize("severity", ["Critical", "Important"])
def test_s1_critical_and_important_qualify(world, severity):
    # axis: qualification reads the severity after the verifier's own call
    _to_sweep(world, _finding(severity=severity))


def test_s1_a_minor_finding_is_not_swept_and_synthesis_goes_on_as_before(world):
    # axis: only a Critical or Important finding is searched for — see bite-proof record c4_wo2a_sweep
    _panel(world, code_reviewer=[_finding(severity="Minor")])
    _not_sweeping(_verify(world))


def test_s1_a_minor_finding_the_verifier_promotes_to_important_is_swept(world):
    _panel(world, code_reviewer=[_finding(severity="Minor")])
    state = _verify(world, {"Retry without a cap": dict(CONFIRMED, severity="Important")})
    assert state["step"] == RD.P_SWEEP and [r["title"] for r in _rows(state)] == ["Retry without a cap"]


def test_s1_an_important_finding_the_verifier_downgrades_to_minor_is_not_swept(world):
    _panel(world, code_reviewer=[_finding()])
    _not_sweeping(_verify(world, {"Retry without a cap": dict(CONFIRMED, severity="Minor")}))


def test_s1_a_plausible_important_finding_is_not_swept(world):
    # axis: only a CONFIRMED finding is searched for — see bite-proof record c4_wo2a_sweep
    _panel(world, code_reviewer=[_finding()])
    _not_sweeping(_verify(world, {"Retry without a cap": PLAUSIBLE}))


def test_s1_a_refuted_important_finding_is_not_swept(world):
    _panel(world, code_reviewer=[_finding()])
    _not_sweeping(_verify(world, {"Retry without a cap": REFUTED}))


def test_s1_only_the_qualifying_finding_of_several_is_swept_and_ids_follow_the_verified_order(world):
    _panel(world, code_reviewer=[_finding("Alpha", line=2), _finding("Beta", line=3, severity="Minor"),
                                 _finding("Gamma", line=19)])
    state = _verify(world)
    assert [(r["sweepId"], r["title"]) for r in _rows(state)] == [("S-1", "Alpha"), ("S-2", "Gamma")]
    assert [s["sweepId"] for s in RD._sweep_payload(state)["sweeps"]] == ["S-1", "S-2"]


def test_s1_a_returning_session_never_sweeps(world):
    # axis: the sweep belongs to round 1 of a session that is not a returning review — see bite-proof record c4_wo2a_sweep
    _panel(world, code_reviewer=[_finding()])
    RD._record_round(world.state, "roundKind", RD.RETURNING_KIND)
    _not_sweeping(_verify(world), reached=False)


@pytest.mark.parametrize("round_no", [2, 3, 4])
def test_s1_a_later_round_never_sweeps_and_leaves_the_session_unswept(world, round_no):
    # axis: the sweep belongs to round 1 of a session that is not a returning review — see bite-proof record c4_wo2a_sweep
    _panel(world, round_no=round_no, code_reviewer=[_finding()])
    state = _verify(world)
    assert state["step"] != RD.P_SWEEP and "_sweepDone" not in state and "sweeps" not in state["rounds"][str(round_no)]


def test_s1_a_sweep_hit_the_verifier_confirms_important_never_starts_a_sweep_of_its_own(world):
    # axis: a session sweeps once, and a hit is never searched for — see bite-proof record c4_wo2a_sweep
    _to_sweep(world)
    state = _sweep(world, _both(_hit(19)))
    assert state["step"] == RD.P_VERIFIERS and state["_sweepPass"] is True
    state = _verify(world)
    assert state["step"] != RD.P_SWEEP and "_sweepPending" not in state
    assert [r["sweepId"] for r in _rows(state)] == ["S-1"] and state["_sweepSeq"] == 1
    assert state["_swept"] == [SC.finding_identity_key(_finding())]


def test_s1_a_finding_with_nothing_qualifying_marks_the_session_swept_so_a_later_pass_does_not_sweep(world):
    # axis: a session sweeps once; a later pass through this point never sweeps again — see bite-proof record c4_wo2a_sweep
    _panel(world, code_reviewer=[_finding(severity="Minor")])
    state = _verify(world)
    assert state["_sweepDone"] is True
    state["_verified"] = [dict(_finding(), verdict="CONFIRMED", id="v9")]
    assert RD._begin_sweep(state, state["config"], str(world.session)) is False
    assert "_sweepPending" not in state and not _rows(state)


def test_s1_a_finding_already_swept_is_not_swept_again_even_when_the_session_is_not_marked_done(world):
    # axis: a session sweeps once; a finding already swept is not searched for again — see bite-proof record c4_wo2a_sweep
    state = _to_sweep(world)
    key = state["_swept"][0]
    for name in RD._SWEEP_PASS_KEYS + ("_sweepDone",):
        state.pop(name, None)
    state["_verified"] = [dict(_finding(), verdict="CONFIRMED", id="v0", findingKey=key)]
    state["step"] = RD.P_VERIFIERS
    assert RD._begin_sweep(state, state["config"], str(world.session)) is False
    assert state["_swept"] == [key] and state["_sweepSeq"] == 1


# ---- S2 the reasons a sweep does not run ----------------------------------------------------------------------


@pytest.mark.parametrize("description", [
    None,
    _description(kind="  "),
    _description(looksLike=""),
    _description(kind=None),
], ids=["null", "blank-kind", "blank-looks-like", "null-kind"])
def test_s2_no_usable_description_means_no_sweep_and_nothing_stands_in(world, description):
    # axis: a description without a kind or looksLike is not run, and the build session writes none — see bite-proof record c4_wo2a_sweep
    _panel(world, code_reviewer=[_finding(searchDescription=description)])
    state = _verify(world)
    _not_sweeping(state, "no-search-description")
    assert "searchDescription" not in state["rounds"]["1"]["sweeps"][0]


def test_s2_a_description_with_no_author_stamp_is_not_run(world):
    # the provenance names no executed vendor, so the driver stamped nothing
    _panel(world, ran={}, code_reviewer=[_finding()])
    _not_sweeping(_verify(world), "no-search-description")


def test_s2_an_author_family_that_became_a_maker_family_before_the_sweep_is_not_run(world):
    # axis: the description's author must still be outside every maker family when the sweep is due — see bite-proof record c4_wo2a_sweep
    _panel(world, code_reviewer=[_finding()])
    assert world.state["_toVerify"][0]["searchDescription"]["author"]["family"] == "openai"
    world.state["formerFixerFamilies"] = ["openai"]  # codex became a maker after the description was stamped
    _not_sweeping(_verify(world), "search-description-author-ineligible")


def test_s2_the_not_run_sweep_still_consumes_its_id_and_its_finding_is_marked_swept(world):
    _panel(world, code_reviewer=[_finding(searchDescription=None), _finding("Beta", line=3)])
    state = _verify(world)
    assert [(r["sweepId"], r.get("notRun")) for r in _rows(state)] == [
        ("S-1", "no-search-description"), ("S-2", None)]
    assert state["step"] == RD.P_SWEEP and [s["sweepId"] for s in state["_sweepPending"]] == ["S-2"]
    assert len(state["_swept"]) == 2


def test_s2_a_host_with_no_searcher_cell_runs_no_sweep_and_emits_no_order(world):
    # axis: a host with no searcher cell runs no sweep and emits no order — see bite-proof record c4_wo2a_sweep
    world.state["config"]["seatMap"]["hostFamily"] = "openai"  # codex's family has no native vendor with a mechanical cell
    _panel(world, code_reviewer=[_finding()])
    _not_sweeping(_verify(world), "no-searcher-cell")


def test_s2_a_registry_with_a_null_mechanical_cell_runs_no_sweep(world, monkeypatch):
    # axis: a host with no searcher cell runs no sweep and emits no order — see bite-proof record c4_wo2a_sweep
    real = model_registry.matrix_config
    monkeypatch.setattr(model_registry, "matrix_config",
                        lambda role, vendor: None if role == "mechanical" else real(role, vendor))
    _panel(world, code_reviewer=[_finding()])
    _not_sweeping(_verify(world), "no-searcher-cell")


def test_s2_an_unknown_host_has_no_searcher_cell(world):
    world.state["config"]["seatMap"].pop("hostFamily")
    assert RD._sweep_searcher(world.state) is None
    world.state["config"]["seatMap"]["hostFamily"] = "anthropic"
    assert RD._sweep_searcher(world.state) == {"vendor": "claude", "model": "haiku-4.5", "effort": "medium"}


def test_s2_a_registry_that_raises_leaves_the_sweep_without_a_cell(world, monkeypatch):
    def boom(role, vendor):
        raise RuntimeError("registry unreadable")

    monkeypatch.setattr(model_registry, "matrix_config", boom)
    assert RD._sweep_searcher(world.state) is None


def _corrupt_meta(world, **fields):
    path = world.session / RD.round_records.META_FILE
    meta = json.loads(path.read_text())
    meta.update(fields)
    path.write_text(json.dumps({k: v for k, v in meta.items() if v is not None}))


@pytest.mark.parametrize("meta", [{"headSha": "0" * 40}, {"headSha": None}, {"repoRoot": None, "headSha": None}],
                         ids=["git-fails", "no-head", "no-repo-root"])
def test_s2_no_file_list_means_no_sweep(world, meta):
    # no repository root, no head, or a git failure leaves nothing to list
    world.state["config"].pop("repoRoot", None)
    world.state["config"].pop("headSha", None)
    _corrupt_meta(world, **meta)
    _panel(world, code_reviewer=[_finding()])
    _not_sweeping(_verify(world), "no-file-list")


def test_s2_a_head_with_no_tracked_file_has_no_file_list(world, tmp_path):
    empty = tmp_path / "empty"
    head = enter_checkout(str(empty))
    _corrupt_meta(world, repoRoot=str(empty), headSha=head)
    world.state["config"]["repoRoot"] = str(empty)
    world.state["config"]["headSha"] = head
    _panel(world, code_reviewer=[_finding()])
    _not_sweeping(_verify(world), "no-file-list")


def test_s2_no_reviewed_diff_means_no_sweep(world):
    # without a diff every hit would read as inside, so no search runs
    _panel(world, code_reviewer=[_finding()])
    world.state["reviewedDiff"] = None
    _not_sweeping(_verify(world), "no-reviewed-diff")


# ---- S3 the parts ---------------------------------------------------------------------------------------------


def _tracked(world):
    out = subprocess.run(["git", "-C", str(world.repo), "ls-files"], capture_output=True, text=True, check=True)
    return sorted(out.stdout.split())


def _commit_files(world, count):
    for index in range(count):
        BL._write(world.repo, "docs/note%d.md" % index, "n" * (10 * (index + 1)) + "\n")
    head = BL._commit(world.repo, "more files")
    _corrupt_meta(world, headSha=head)
    world.state["config"]["headSha"] = head


def test_s3_fewer_than_four_tracked_files_make_fewer_parts_and_never_an_empty_one(world):
    state = _to_sweep(world)
    parts = RD._sweep_payload(state)["sweeps"][0]["parts"]
    assert [p["part"] for p in parts] == [1, 2]  # the two tracked files of the head
    assert all(p["files"] for p in parts)
    assert sorted(f for p in parts for f in p["files"]) == _tracked(world)
    assert RD._sweep_split_files([("only.py", 5)]) == [{"part": 1, "files": ["only.py"]}]
    assert RD._sweep_split_files([]) == []


def test_s3_many_files_make_four_size_balanced_parts_that_cover_every_tracked_file_exactly_once(world):
    _commit_files(world, 9)
    state = _to_sweep(world)
    parts = RD._sweep_payload(state)["sweeps"][0]["parts"]
    assert [p["part"] for p in parts] == [1, 2, 3, 4] and RP.SWEEP_PARTS == 4
    assert sorted(f for p in parts for f in p["files"]) == _tracked(world)  # every file, once
    assert _rows(state)[0]["parts"] == 4


def test_s3_the_split_is_deterministic_and_balances_by_size():
    entries = [("a", 100), ("b", 90), ("c", 10), ("d", 10), ("e", 5), ("f", 5)]
    first = RD._sweep_split_files(entries)
    assert first == RD._sweep_split_files(list(reversed(entries)))
    loads = [sum(dict(entries)[f] for f in p["files"]) for p in first]
    assert len(first) == 4 and max(loads) == 100 and sorted(loads) == [15, 15, 90, 100]


# ---- S4 the fold of the hits ----------------------------------------------------------------------------------


def test_s4_a_missing_searcher_seat_folds_with_a_gap_and_is_recorded_and_disclosed(world):
    # axis: a part whose searcher returned no usable result is recorded missing, never as a part that found nothing — see bite-proof record c4_wo2a_sweep
    _to_sweep(world)
    state = _sweep(world, {_seat("S-1", 1): [_hit(19)]})  # part 2 answered nothing
    (row,) = _rows(state)
    assert row["missing"] == [2] and row["inside"] == 1
    assert state["step"] == RD.P_VERIFIERS  # the hit found by part 1 still goes on
    assert any(d["kind"] == "sweep-incomplete" for d in state["decisions"])
    assert any("sweep-incomplete (round 1): S-1 — searcher part(s) 2 returned nothing" in line
               for line in RD.build_receipt(state)["degraded"])


def test_s4_every_seat_missing_records_every_part_and_the_round_goes_on_to_synthesis(world):
    _to_sweep(world)
    state = _sweep(world, {})
    assert _rows(state)[0]["missing"] == [1, 2]
    assert state["step"] != RD.P_SWEEP and state["_sweepDone"] is True and "_sweepPending" not in state


@pytest.mark.parametrize("result", [{"hits": "not a list"}, {"hits": [7]}, {"hits": [{"file": "x"}, "y"]}, {"nope": []}])
def test_s4_a_result_that_breaks_the_contract_is_a_missing_part_not_a_crash(world, result):
    _to_sweep(world)
    state = _fold(world, RD.P_SWEEP, {"seats": {_seat("S-1", 1): result, _seat("S-1", 2): {"hits": []}}})
    assert _rows(state)[0]["missing"] == [1]


def test_s4_malformed_hits_and_a_pr_body_citation_are_dropped_and_counted(world):
    # axis: a hit citing the PR body is dropped and counted, never staged — see bite-proof record c4_wo2a_sweep
    _to_sweep(world)
    bad = [{"file": pr_body_stage.CITATION, "line": 3, "what": "in the PR body"},
           {"file": "", "line": 3}, {"file": "  ", "line": 3}, {"file": None, "line": 3}, {"line": 3},
           {"file": "src/b.py", "line": "3"}, {"file": "src/b.py", "line": True}, {"file": "src/b.py", "line": None},
           {"file": "src/b.py", "line": 2.5}, {"file": 7, "line": 3}]
    state = _sweep(world, _both(*bad))
    (row,) = _rows(state)
    assert (row["dropped"], row["inside"], row["outside"], row["covered"]) == (10, 0, 0, 0)
    assert state["step"] != RD.P_SWEEP and not state.get("outsideThisPR")


def test_s4_the_same_place_found_by_two_parts_is_one_hit_and_the_first_what_wins(world):
    _to_sweep(world)
    state = _sweep(world, {_seat("S-1", 1): [_hit(1, "README.md", "first words")],
                           _seat("S-1", 2): [_hit(1, "README.md", "other words")]})
    (entry,) = _sweep_entries(state)
    assert [h["title"] for h in entry["hits"]] == ["first words"] and _rows(state)[0]["outside"] == 1


def test_s4_the_same_inside_place_found_by_two_parts_is_one_finding(world):
    _to_sweep(world)
    state = _sweep(world, {_seat("S-1", 1): [_hit(19, what="first inside")],
                           _seat("S-1", 2): [_hit(19, what="second inside")]})
    assert [f["title"] for f in state["_toVerify"]] == ["first inside"] and _rows(state)[0]["inside"] == 1


def test_s4_a_hit_at_the_parents_own_place_or_one_of_its_places_is_covered_not_found_again(world):
    # axis: a hit at the parent's own place or one of its places is already known — see bite-proof record c4_wo2a_sweep
    _to_sweep(world, _finding(kindOfMistake={"kind": KIND, "places": [{"file": "src/a.py", "line": 3}]}))
    state = _sweep(world, _both(_hit(2), _hit(3), _hit(2, what="again")))
    (row,) = _rows(state)
    assert (row["covered"], row["inside"], row["outside"], row["dropped"]) == (2, 0, 0, 0)
    assert state["step"] != RD.P_SWEEP and not state.get("outsideThisPR")


def test_s4_a_hit_on_a_context_line_or_in_an_untouched_file_is_outside_under_the_sweeps_own_entry(world):
    # axis: an outside hit lands under its sweep's own entry, never a reviewer's — see bite-proof record c4_wo2a_sweep
    _to_sweep(world)
    state = _sweep(world, _both(_hit(1, what="retry on a context line"), _hit(4, "README.md", "retry in the readme")))
    (entry,) = state["outsideThisPR"]
    assert entry["source"] == {"kind": "sweep", "name": "searchers", "sweepId": "S-1"}
    assert [(h["id"], h["file"], h["line"], h["title"]) for h in entry["hits"]] == [
        ("O-1", "src/a.py", 1, "retry on a context line"), ("O-2", "README.md", 4, "retry in the readme")]
    row = _rows(state)[0]
    assert (row["outside"], row["inside"]) == (2, 0)
    assert state["step"] != RD.P_SWEEP  # nothing inside: the verifiers are skipped
    assert [d for d in state["decisions"] if d["kind"] == "sweep-folded"]
    assert state["_outsideRounds"]  # noted for the round, as a reviewer's outside hit is


def test_s4_the_sweeps_outside_ids_follow_every_hit_already_listed_including_a_reviewers(world):
    # axis: an outside hit's id counts every hit already listed on every entry — see bite-proof record c4_wo2a_sweep
    _to_sweep(world, _finding(kindOfMistake={"kind": KIND, "places": [{"file": "src/a.py", "line": 1}]}))
    reviewer = world.state["outsideThisPR"]
    assert [e["source"]["kind"] for e in reviewer] == ["reviewer"] and len(reviewer[0]["hits"]) == 1
    state = _sweep(world, _both(_hit(20, what="a"), _hit(21, what="b")))
    assert [e["source"]["kind"] for e in state["outsideThisPR"]] == ["reviewer", "sweep"]
    assert [h["id"] for h in state["outsideThisPR"][1]["hits"]] == ["O-2", "O-3"]
    assert [h["id"] for h in state["outsideThisPR"][0]["hits"]] == ["O-1"]


@pytest.mark.parametrize("held", [None, "garbage", {"x": 1}])
def test_s4_an_outside_list_that_is_absent_or_not_a_list_is_made_or_replaced_never_a_lost_hit(world, held):
    _to_sweep(world)
    if held is None:
        world.state.pop("outsideThisPR", None)
    else:
        world.state["outsideThisPR"] = held
    state = _sweep(world, _both(_hit(20)))
    assert [h["file"] for e in state["outsideThisPR"] for h in e["hits"]] == ["src/a.py"]


def test_s4_an_inside_hit_becomes_a_finding_of_its_own_with_the_parents_severity_and_a_sweep_mark(world):
    _to_sweep(world, _finding(severity="Critical"))
    state = _sweep(world, _both(_hit(19, what="  retries forever here  ")))
    (hit,) = state["_toVerify"]
    parent = _finding(severity="Critical")
    assert (hit["title"], hit["file"], hit["line"], hit["severity"]) == ("retries forever here", "src/a.py", 19, "Critical")
    assert hit["consequence"] == CONSEQUENCE
    assert hit["kindOfMistake"] == {"kind": KIND, "places": []} and not hit.get("searchDescription")
    assert hit["sweepOf"] == {"sweepId": "S-1", "findingKey": SC.finding_identity_key(parent)}
    assert hit["body"] == ('Found by repository sweep S-1 for the confirmed finding "Retry without a cap" '
                           "(src/a.py:2): retries forever here")
    minted = SC.finding_identity_key(SC.sweep_hit_finding(  # the one identity the writer's recovery mints too
        _hit(19, what="retries forever here"), {"sweepId": "S-1"}, dict(parent, searchDescription=_description())))
    assert minted == SC.finding_identity_key(hit) == "src/a.py::retries forever here@L19"
    assert minted in [SC.finding_identity_key(e) for e in state[SC.DISPOSITION_LEDGER_KEY]]  # and its ledger row has it
    assert state["step"] == RD.P_VERIFIERS and state["_sweepPass"] is True
    assert _rows(state)[0]["inside"] == 1


def test_s4_a_blank_what_titles_the_hit_by_the_descriptions_kind(world):
    _to_sweep(world)
    state = _sweep(world, _both({"file": "src/a.py", "line": 19, "what": "  "}, {"file": "README.md", "line": 3}))
    assert [f["title"] for f in state["_toVerify"]] == [KIND]
    assert [h["title"] for e in state["outsideThisPR"] for h in e["hits"]] == [KIND]


# ---- S5 the sweep pass through the verifiers ------------------------------------------------------------------


def test_s5_an_inside_hit_reaches_the_next_verifier_pass_and_once_confirmed_is_verified_beside_its_parent(world, routed):
    # axis: an inside hit goes to the verifiers, never straight to the verified list — see bite-proof record c4_wo2a_sweep
    _to_sweep(world)
    state = _sweep(world, _both(_hit(19, what="second site")))
    assert state["_verified"] == [] and [f["title"] for f in state["_toVerify"]] == ["second site"]
    assert not any(f["title"] == "second site" for f in state.get("_verified") or [])
    state = _verify(world)
    assert routed[-1] == (["Retry without a cap", "second site"], [])
    assert "_sweepCarry" not in state and "_sweepRefutedCarry" not in state and "_sweepPass" not in state
    assert state["_sweepDone"] is True
    assert [p["CONFIRMED"] for p in state["rounds"]["1"]["verifyPasses"]] == [1, 1]  # both passes are kept


def test_s5_a_refuted_hit_is_closed_wrong_and_never_verified(world, routed):
    _to_sweep(world)
    _sweep(world, _both(_hit(19, what="not really")))
    state = _verify(world, {"not really": REFUTED})
    assert routed[-1] == (["Retry without a cap"], ["not really"])


def test_s5_an_inside_hit_with_no_verifier_grade_is_open_and_never_reaches_a_fix(world, routed):
    # axis: a sweep hit with no verifier grade is removed from the survivors — see bite-proof record c4_wo2a_sweep
    _to_sweep(world)
    _sweep(world, _both(_hit(19, what="ungraded site"), _hit(20)))
    state = _verify(world, silent=("ungraded site",))
    assert routed[-1] == (["Retry without a cap"], [])
    assert _rows(state)[0]["ungraded"] == 1
    assert [d["detail"] for d in state["decisions"] if d["kind"] == "sweep-hit-ungraded"] == [
        "ungraded site (src/a.py:19): a repository-sweep hit the verifier did not grade"]
    (ledger,) = [e for e in state[SC.DISPOSITION_LEDGER_KEY] if e.get("title") == "ungraded site"]
    assert "disposition" not in ledger  # the row stays open
    assert not any(f["title"] == "ungraded site" for f in state.get("findings") or [])


def test_s5_an_ungraded_hit_is_disclosed_as_a_degradation(world):
    _to_sweep(world)
    _sweep(world, _both(_hit(19, what="ungraded site")))
    state = _verify(world, silent=("ungraded site",))
    assert any("sweep-hit-ungraded (round 1): 1 sweep hit(s) left open without a verifier grade" in line
               for line in RD.build_receipt(state)["degraded"])


def test_s5_the_census_every_finding_staged_in_round_1_ends_verified_refuted_or_a_recorded_drop(world, routed):
    # axis: the carry is restaged with the sweep pass's survivors, so no finding staged in round 1 is lost — see bite-proof record c4_wo2a_sweep
    _panel(world, code_reviewer=[_finding("Plain", line=2), _finding("Held", line=3),
                                 _finding("Gone", line=5, file="src/b.py")])
    for staged in world.state["_toVerify"]:
        if staged["title"] == "Held":
            staged["breakItRun"] = {"outcome": "passed"}
    state = _verify(world, {"Held": MISSED_PATH, "Gone": REFUTED})
    if state["step"] == RD.P_SECOND_TEST:
        RD._fold_second_test(state, state["config"], {"findings": []}, session_dir=str(world.session))
    assert state["step"] == RD.P_VERIFIERS and state["_secondTestPass"] is True
    state = _verify(world)  # the second test pass: the held finding is confirmed
    assert state["step"] == RD.P_SWEEP, state["step"]
    assert sorted(r["title"] for r in _rows(state)) == ["Held", "Plain"]
    hits = {_seat("S-1", 1): [_hit(19, what="site one"), _hit(1, "src/b.py", "site two"),
                              _hit(2, "src/b.py", "site three"), _hit(3, "src/b.py", "site four"),
                              _hit(1, "README.md", "outside five"), {"file": "", "line": 1}],
            _seat("S-2", 2): [_hit(4, "src/b.py", "site six")]}
    state = _sweep(world, hits)
    state = _verify(world, {"site two": REFUTED, "site three": REFUTED}, silent=("site four",))
    verified, refuted = routed[-1]
    assert sorted(verified) == ["Held", "Plain", "site one", "site six"]
    assert sorted(refuted) == ["Gone", "site three", "site two"]
    staged = set(world.staged)
    ungraded = {"site four"}
    assert staged == set(verified) | set(refuted) | ungraded  # nothing staged in round 1 went missing
    assert sum(r["ungraded"] for r in _rows(state)) == 1 and sum(r["dropped"] for r in _rows(state)) == 1
    assert sum(r["outside"] for r in _rows(state)) == 1
    assert state["rounds"]["1"]["verify"]["held"] != [] and len(state["rounds"]["1"]["verifyPasses"]) == 3
    assert len({f["id"] for f in state["_verified"] + state["_refuted"]}) == 7  # restaged with pairwise unique ids


def test_s5_a_hit_two_sweeps_both_found_is_one_finding(world):
    _to_sweep(world, _finding("Alpha", line=2), _finding("Beta", line=3))
    state = _sweep(world, {_seat("S-1", 1): [_hit(19)], _seat("S-1", 2): [], _seat("S-2", 1): [_hit(19)],
                           _seat("S-2", 2): []})
    assert len(state["_toVerify"]) == 1 and [r["inside"] for r in _rows(state)] == [1, 0]
    assert [r["covered"] for r in _rows(state)] == [0, 1]


# ---- S6 a session resumed between steps -----------------------------------------------------------------------


def _reload(world):
    world.state = json.loads(json.dumps(world.state))


def test_s6_a_state_saved_and_reloaded_between_every_step_behaves_the_same(world, routed):
    _panel(world, code_reviewer=[_finding()])
    _reload(world)
    _verify(world)
    _reload(world)
    state = world.state
    assert state["step"] == RD.P_SWEEP and state["_sweepDone"] and state["_swept"] and state["_sweepPending"]
    _sweep(world, _both(_hit(19, what="second site"), _hit(20)))
    _reload(world)
    assert world.state["_sweepPass"] is True
    state = _verify(world)
    _reload(world)
    assert routed[-1] == (["Retry without a cap", "second site"], [])
    assert world.state["_sweepDone"] is True and len(_rows(world.state)) == 1
    assert [d["kind"] for d in world.state["decisions"]].count("sweep-dispatched") == 1


# ---- S7 the shared helpers, the contract and the disclosure ---------------------------------------------------


def test_s7_add_sweep_hit_opens_one_entry_per_sweep_numbers_after_every_listed_hit_and_never_adds_a_duplicate():
    # axis: a sweep entry numbers its hits after every hit on every entry and never takes a reviewer's entry — see bite-proof record c4_wo2a_sweep
    entries = [{"source": {"kind": "reviewer", "name": "searchers", "sweepId": None},
                "hits": [{"id": "O-1", "file": "a.py", "line": 1, "title": "t"}]}]
    assert SC.add_sweep_hit(entries, "S-1", "searchers", "b.py", 2, "u") is True
    assert SC.add_sweep_hit(entries, "S-2", "searchers", "c.py", 3, "v") is True
    assert SC.add_sweep_hit(entries, "S-1", "searchers", "d.py", 4, "w") is True
    assert SC.add_sweep_hit(entries, "S-1", "searchers", "b.py", 2, "u") is False
    assert [(e["source"]["kind"], e["source"].get("sweepId"), [h["id"] for h in e["hits"]]) for e in entries] == [
        ("reviewer", None, ["O-1"]), ("sweep", "S-1", ["O-2", "O-4"]), ("sweep", "S-2", ["O-3"])]
    broken = [{"source": {"kind": "sweep", "name": "searchers", "sweepId": "S-1"}, "hits": "x"}]
    assert SC.add_sweep_hit(broken, "S-1", "searchers", "b.py", 2, "u") is True and broken[0]["hits"][0]["id"] == "O-1"


def test_s7_the_run_kind_phase_and_decision_kinds_are_registered():
    assert SC.RUN_KIND_BY_PHASE[RP.P_SWEEP] == SC.RUN_KIND_SEARCH == "search" and SC.RUN_KIND_SEARCH in SC.RUN_KIND_VALUES
    assert SC.run_kind_value_ok("search") and SC.run_kind_for_phase(RP.P_SWEEP) == "search"
    assert RP.P_SWEEP in RP.ALL_PHASES and RP.P_SWEEP in PC.ADAPTER_PHASES
    assert RP.P_SWEEP not in RD._NONPANEL_REVIEWER_PHASES  # a searcher is not a reviewer
    for kind in ("sweep-not-run", "sweep-dispatched", "sweep-folded", "sweep-incomplete", "sweep-hit-ungraded"):
        assert kind in decision_kinds.DECISION_KINDS


def test_s7_the_roster_is_one_seat_per_sweep_and_part_and_each_key_has_a_storage_key(world):
    state = _to_sweep(world, _finding("Alpha", line=2), _finding("Beta", line=3))
    keys, fault = RA.roster_for(RP.P_SWEEP, state, state["config"])
    assert fault is None and keys == ["searcher:S-1:1", "searcher:S-1:2", "searcher:S-2:1", "searcher:S-2:2"]
    assert len({RD.round_records.storage_key(k, 0) for k in keys}) == 4
    assert RA.roster_for(RP.P_SWEEP, {"round": 1}, {})[0] == []


def test_s7_the_payload_contract_names_the_hits_field_and_a_missing_seat_never_refuses_the_fold():
    assert PC.payload_fault(RP.P_SWEEP, {"hits": []}, "searcher:S-1:1") is None
    assert "hits" in PC.payload_fault(RP.P_SWEEP, {"hits": "x"}, "searcher:S-1:1")
    assert "hits" in PC.payload_fault(RP.P_SWEEP, {"hits": [3]}, "searcher:S-1:1")
    assert "hits" in PC.payload_fault(RP.P_SWEEP, {}, "searcher:S-1:1")
    assert RA._MISSING_POLICY[RP.P_SWEEP] == RA.MISSING_FOLD_FAIL_CLOSED


def test_s7_a_not_run_sweep_and_an_incomplete_one_are_degradations_never_a_hidden_pass(world):
    # axis: a sweep that did not run is disclosed — see bite-proof record c4_wo2a_sweep
    _panel(world, code_reviewer=[_finding(searchDescription=None)])
    state = _verify(world)
    lines = RD.build_receipt(state)["degraded"]
    assert ('sweep-not-run (round 1): S-1 for "Retry without a cap" — no-search-description; '
            "no search ran and nothing stood in") in lines


def test_s7_the_sweep_rows_are_a_carried_disclosure_channel():
    assert "sweeps" in receipt_disclosures.CARRIED_DISCLOSURE_CHANNELS and "sweeps" in RD.VERIFIER_FOLD_DISCLOSURE_CHANNELS


# ---- S8 driven end to end through next/submit -----------------------------------------------------------------

_E2E_DIFF = DIFF


class Driven:
    """A review session driven through `cmd_next` / `cmd_submit` in a real checkout with several tracked files. The
    code reviewer raises `findings`; each verifier title is answered from `verdicts` (CONFIRMED when absent, nothing
    when the title is in `silent`); a searcher part answers from `hits[(sweepId, part)]`."""

    def __init__(self, tmp_path, findings, hits=None, verdicts=None, silent=(), files=5):
        self.dir = str(tmp_path)
        self.checkout = os.path.join(self.dir, "checkout")
        os.makedirs(os.path.join(self.checkout, "src"))
        for index in range(files):
            with open(os.path.join(self.checkout, "src", "f%d.py" % index), "w") as fh:
                fh.write("x = %d\n" % index * (index + 1))
        head = enter_checkout(self.checkout)
        TRD._seed_repo_root_if_missing(self.dir, self.checkout)
        cfg = S1858._cfg()
        cfg.pop("repoRoot")
        self.cfg = TRD._cfg(diff=_E2E_DIFF, headSha=head, **cfg)
        self.findings, self.hits, self.verdicts, self.silent = list(findings), hits or {}, verdicts or {}, set(silent)
        self.seen, self.orders, self.verifier_payloads, self.fix_batches = [], [], [], []
        self.started = False

    def state(self):
        ok, state = RD.load_state(self.dir)
        assert ok, state
        return state

    def respond(self, n):
        phase, payload, rnd = n["phase"], n["payload"], n["round"]
        self.seen.append(phase)
        if phase == RD.P_PANEL:
            seats = {d: {"findings": []} for d in RD.DIMENSIONS}
            if rnd == 1:
                seats["code-reviewer"] = {"findings": [dict(f) for f in self.findings]}
            return {"seats": seats, "ranManifest": {"code-reviewer": INDEPENDENT}}
        if phase == RD.P_VERIFIERS:
            self.verifier_payloads.append(payload)
            verdicts = []
            for cluster in payload.get("clusters", []):
                for finding, fid in zip(cluster["findings"], cluster["ids"]):
                    if finding["title"] not in self.silent:
                        verdicts.append(dict(self.verdicts.get(finding["title"], CONFIRMED), id=fid))
            return {"verdicts": verdicts, "verifierVendor": RD._nonpanel_selection(self.state(), self.dir, phase)[0]}
        if phase == RD.P_SWEEP:
            self.orders.append(n)
            return {"seats": {RA.sweep_seat_key(s["sweepId"], p["part"]): {"hits": list(self.hits.get(
                (s["sweepId"], p["part"]), []))} for s in payload["sweeps"] for p in s["parts"]}}
        if phase == RD.P_APPLY_FIXES:
            self.fix_batches.append([row["title"] for row in payload["batch"]])
            return {"fixes": [], "unfixed": [{"finding": SC.finding_identity_key(row), "why": "the scaffold applies no fix"}
                                             for row in payload["batch"]]}
        return TRD._responder()(phase, payload, rnd)

    def drive(self):
        for _ in range(80):
            n = RD.cmd_next(self.dir, None if self.started else self.cfg)
            self.started = True
            assert n["ok"], n
            if n["action"] == RD.P_TERMINAL:
                return n
            art = TRD._claim_reviewer(self.dir, n["phase"], self.respond(n))
            s = RD.cmd_submit(self.dir, n["phase"], n["attempt"], n["expectedStateHash"], art)
            assert s["ok"], s
        raise AssertionError("no terminal within 80 steps; saw %s" % self.seen)


def _tracked_in(checkout):
    out = subprocess.run(["git", "-C", checkout, "ls-files"], capture_output=True, text=True, check=True)
    return sorted(out.stdout.split())


def test_s8_the_driven_sweep_order_carries_the_description_without_its_author_and_parts_covering_every_file(tmp_path):
    run = Driven(tmp_path, [_finding()])
    run.drive()
    (order,) = run.orders
    (sweep,) = order["payload"]["sweeps"]
    assert sweep["searchDescription"] == _description() and "author" not in json.dumps(order["payload"])
    assert sorted(f for p in sweep["parts"] for f in p["files"]) == _tracked_in(run.checkout)
    assert len(sweep["parts"]) == 4 and all(p["files"] for p in sweep["parts"])
    assert run.seen.count(RD.P_SWEEP) == 1  # one sweep step across the whole session


def test_s8_the_driven_session_sweeps_each_qualifying_finding_exactly_once_across_every_round(tmp_path):
    run = Driven(tmp_path, [_finding("Alpha", line=2), _finding("Beta", line=3), _finding("Minor one", line=19, severity="Minor")])
    run.drive()
    state = run.state()
    assert [(r["sweepId"], r["title"]) for r in _rows(state)] == [("S-1", "Alpha"), ("S-2", "Beta")]
    assert run.seen.count(RD.P_SWEEP) == 1 and sorted(state["_swept"]) == sorted(
        SC.finding_identity_key(_finding(t, line=ln)) for t, ln in (("Alpha", 2), ("Beta", 3)))
    assert [d["kind"] for d in state["decisions"]].count("sweep-dispatched") == 2


def test_s8_an_inside_hit_reaches_the_verifier_order_and_once_confirmed_the_fix_batch(tmp_path):
    run = Driven(tmp_path, [_finding()], hits={("S-1", 2): [_hit(19, what="second site")]})
    run.drive()
    verifier_titles = [[f["title"] for c in p["clusters"] for f in c["findings"]] for p in run.verifier_payloads]
    assert verifier_titles[0] == ["Retry without a cap"] and verifier_titles[1] == ["second site"]
    assert any("second site" in batch for batch in run.fix_batches)
    (row,) = _rows(run.state())
    assert row["inside"] == 1 and row["missing"] == []


def test_s8_an_ungraded_hit_never_reaches_a_fix_batch(tmp_path):
    run = Driven(tmp_path, [_finding()], hits={("S-1", 1): [_hit(19, what="ungraded site")]}, silent=("ungraded site",))
    run.drive()
    assert run.fix_batches and all("ungraded site" not in batch for batch in run.fix_batches)
    state = run.state()
    assert _rows(state)[0]["ungraded"] == 1
    assert any("sweep-hit-ungraded (round 1)" in line for line in RD.build_receipt(state)["degraded"])


def test_s8_an_outside_hit_lands_under_the_sweeps_entry_and_the_written_record_renders_it(tmp_path):
    # the record is the review record's own: its writer validates it and its reader renders the sweep source
    run = Driven(tmp_path, [_finding(kindOfMistake={"kind": KIND, "places": [{"file": "src/a.py", "line": 1}]})],
                 hits={("S-1", 1): [_hit(4, "src/f0.py", "retry in f0")]})
    run.drive()
    state = run.state()
    assert [e["source"]["kind"] for e in state["outsideThisPR"]] == ["reviewer", "sweep"]
    assert [h["id"] for e in state["outsideThisPR"] for h in e["hits"]] == ["O-1", "O-2"]
    session = Session(tmp_path / "acct", outsideThisPR=state["outsideThisPR"]).seat("code-reviewer").save()
    fake = Fake()
    out = rs.write_from_session(session, put_extras(tmp_path, TRS.extras()), str(tmp_path), fake.readers())
    assert out["ok"], out
    body = fake.marked()[-1]["body"]
    assert "O-2" in body and "from sweep S-1 by searchers" in body
    record = rr.read(7, readers=fake.readers())
    assert [e["source"]["kind"] for e in record["outsideThisPR"]] == ["reviewer", "sweep"]
