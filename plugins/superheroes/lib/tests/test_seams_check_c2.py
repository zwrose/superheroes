"""A sliced change gets one seams check in round 1, and nothing else splits or sweeps a change.

The panel's findings and the seams check's findings are staged together for the verifiers. The seams check runs
once, in round 1 only, and only when the round's slice plan says the change was sliced. The panel payload carries no
per-lens split of the diff. A saved session standing at the retired extra pass continues past it. No shipped library
module, order template or review-code doc names the retired pass or the folder split.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/c2_wo3_seams_check.md
"""
import copy
import glob
import json
import os
import re
import sys
from unittest import mock

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import decision_kinds  # noqa: E402
import round_driver as RD  # noqa: E402
import round_phases as RP  # noqa: E402
import test_round_driver as TRD  # noqa: E402

_PLUGIN_ROOT = os.path.dirname(_LIB)

DIFF = ("diff --git a/a.py b/a.py\nindex 1..2 100644\n--- a/a.py\n+++ b/a.py\n"
        "@@ -1 +1,2 @@\n-old\n+new\n+more\n"
        "diff --git a/b.py b/b.py\nindex 1..2 100644\n--- a/b.py\n+++ b/b.py\n"
        "@@ -1 +1,2 @@\n-old\n+new\n+more\n")
CFG = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF, "fixerVendor": "claude"}
CONSEQUENCE = "a reviewer-found defect stays in the change"

SLICE_PLAN = {
    "sliced": True, "weight": 3000, "countable": 3000, "bar": 1500,
    "slices": [
        {"id": "s1", "weight": 1500, "diff": "",
         "parts": [{"file": "b.py", "lines": []}, {"file": "a.py", "lines": [[1, 2]]}, {"file": "a.py", "lines": []}]},
        {"id": "s2", "weight": 1500, "diff": "", "parts": [{"file": "c.py", "lines": []}]},
    ],
}
RETIRED_STEP = "dispatch-gap-sweep"


def _finding(title, file, line=1):
    return {"title": title, "severity": "Important", "consequence": CONSEQUENCE, "file": file, "line": line}


def _panel_artifact(*findings):
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["code-reviewer"] = {"findings": list(findings)}
    return {"seats": seats}


def _round_one_state(plan=None):
    state = RD.new_state(dict(CFG))
    state["reviewedDiff"] = DIFF
    if plan is not None:
        state["slicePlan"] = copy.deepcopy(plan)
    return state


def _fold_panel_with(state, *findings):
    """Fold a panel artifact holding ``findings``. On a sliced round 1 the panel seats are the roster's (whole-change seats and
    ``<lens>:<id>`` slice seats), so the findings are keyed under the first ``code-reviewer:<id>`` slice seat; an unsliced round
    keeps the plain ``code-reviewer`` key."""
    roster = RP.panel_roster(state, state["config"])
    slice_seat = next((s for s in roster if s.startswith("code-reviewer:")), None)
    if slice_seat is None:
        artifact = _panel_artifact(*findings)
    else:
        artifact = {"seats": {s: {"findings": []} for s in roster}}
        artifact["seats"][slice_seat]["findings"] = list(findings)
    RD._fold(state, state["config"], RD.P_PANEL, artifact)
    return state


# --- a sliced round 1 goes panel -> seams check -> verifiers --------------------------------------------------------

def test_a_sliced_round_one_goes_panel_then_seams_check_then_verifiers_with_both_findings_staged_once():
    state = _round_one_state(SLICE_PLAN)
    _fold_panel_with(state, _finding("panel bug", "a.py"))
    assert state["step"] == RD.P_SEAMS == "dispatch-seams-check"
    assert state["_seamsChecked"] is True
    assert [f["title"] for f in state["_panelStaged"]] == ["panel bug"]
    assert not state.get("_toVerify"), "nothing is staged for the verifiers until the seams check has folded"
    assert RD._advance(state, state["config"])["action"] == RD.P_SEAMS

    RD._fold(state, state["config"], RD.P_SEAMS, {"findings": [_finding("seam bug", "b.py")]})
    assert state["step"] == RD.P_VERIFIERS
    assert "_panelStaged" not in state
    assert sorted(f["title"] for f in state["_toVerify"]) == ["panel bug", "seam bug"]


def test_a_seams_check_with_no_findings_stages_the_panels_alone():
    state = _round_one_state(SLICE_PLAN)
    _fold_panel_with(state, _finding("panel bug", "a.py"))
    RD._fold(state, state["config"], RD.P_SEAMS, {"findings": []})
    assert state["step"] == RD.P_VERIFIERS
    assert [f["title"] for f in state["_toVerify"]] == ["panel bug"]


def test_a_seams_check_finding_outside_the_diff_is_dropped_at_compile_like_any_other():
    state = _round_one_state(SLICE_PLAN)
    _fold_panel_with(state, _finding("panel bug", "a.py"))
    RD._fold(state, state["config"], RD.P_SEAMS, {"findings": [_finding("elsewhere", "z.py")]})
    assert [f["title"] for f in state["_toVerify"]] == ["panel bug"]
    assert [d["reason"] for d in state["rounds"]["1"]["compileDrops"]] == ["outside the round diff scope"]


# --- the seams check runs once, in round 1 only ---------------------------------------------------------------------

def test_after_the_seams_check_re_entering_round_one_goes_straight_to_the_verifiers():
    state = _round_one_state(SLICE_PLAN)
    _fold_panel_with(state, _finding("panel bug", "a.py"))
    RD._fold(state, state["config"], RD.P_SEAMS, {"findings": []})
    staged, _drops = RD.mechanical_compile([_finding("another", "b.py")], DIFF)
    state["step"] = RD.P_PANEL
    RD._after_panel_findings(state, state["config"], staged)
    assert state["step"] == RD.P_VERIFIERS
    assert "another" in [f["title"] for f in state["_toVerify"]]


def test_a_later_round_of_a_sliced_change_never_enters_the_seams_check():
    state = _round_one_state(SLICE_PLAN)
    state["round"] = 2
    staged, _drops = RD.mechanical_compile([_finding("later", "a.py")], DIFF)
    RD._after_panel_findings(state, state["config"], staged)
    assert state["step"] == RD.P_VERIFIERS
    assert not state.get("_seamsChecked") and "_panelStaged" not in state
    assert [f["title"] for f in state["_toVerify"]] == ["later"]


def test_a_sliced_run_through_its_fix_rounds_runs_the_seams_check_once():
    calls = {"seams": 0}
    seams = TRD._rearm_until_converge_seams(3)
    inner = seams["reviewer"]

    def counting(dim, tier, rnd, ctx):
        if dim == "seams-check":
            calls["seams"] += 1
        return inner(dim, tier, rnd, ctx)

    seams["reviewer"] = counting
    with mock.patch.object(TRD.RD, "_round_is_sliced", lambda state: True):
        receipt = TRD.RD.run_loop(seams, TRD._cfg_cert(maxRounds=4))
    assert max(r["round"] for r in receipt["rounds"]) == 3
    assert calls["seams"] == 1


# --- an unsliced change never enters the seams check; the panel payload is not split --------------------------------

@pytest.mark.parametrize("plan", [None, {"sliced": False, "slices": []}, {"sliced": "yes", "slices": []}, "junk"],
                         ids=["no-plan", "not-sliced", "sliced-not-true", "not-a-dict"])
def test_an_unsliced_round_one_never_enters_the_seams_check(plan):
    state = _round_one_state()
    if plan is not None:
        state["slicePlan"] = plan
    assert RD._round_is_sliced(state) is False
    _fold_panel_with(state, _finding("panel bug", "a.py"))
    assert state["step"] == RD.P_VERIFIERS
    assert "_seamsChecked" not in state and "_panelStaged" not in state
    assert [f["title"] for f in state["_toVerify"]] == ["panel bug"]


def test_an_unsliced_big_run_never_dispatches_the_seams_check():
    calls = {"seams": 0}

    def reviewer(dim, tier, rnd, ctx):
        if dim == "seams-check":
            calls["seams"] += 1
        return []

    TRD.RD.run_loop(TRD._seams(reviewer=reviewer), TRD._cfg(diff=TRD._big_diff(25)))
    assert calls["seams"] == 0


def test_a_three_thousand_line_diff_has_no_shards_in_the_panel_payload():
    body = "".join("+line %d\n" % i for i in range(3000))
    big = ("diff --git a/big.py b/big.py\nnew file mode 100644\nindex 0000000..1111111\n--- /dev/null\n"
           "+++ b/big.py\n@@ -0,0 +1,3000 @@\n" + body)
    state = RD.new_state(dict(CFG, diff=big))
    state["reviewedDiff"] = big
    payload = RD._advance(state, state["config"])["payload"]
    assert "shards" not in payload
    assert set(payload) == {"dimensions", "tier", "slices"}
    assert payload["dimensions"] == RP.panel_roster(state, state["config"])
    assert isinstance(payload["slices"], list) and payload["slices"]
    assert [s["id"] for s in payload["slices"]] == [s["id"] for s in state["slicePlan"]["slices"]]
    assert payload["tier"] == RD.DEEP
    for gone in ("shard_plan", "_shard_payload", "CROSS_CUTTING_LENSES", "DEFAULT_SHARD_MAX_LINES"):
        assert not hasattr(RD, gone) and not hasattr(RD.delta_surface, gone), gone


# --- the seams payload and its sidecar list the slices --------------------------------------------------------------

def test_the_seams_payload_lists_each_slice_by_id_with_its_sorted_files():
    state = _round_one_state(SLICE_PLAN)
    state["step"] = RD.P_SEAMS
    payload = RD._advance(state, state["config"])["payload"]
    assert payload == {"fullDiff": True, "slices": [{"id": "s1", "files": ["a.py", "b.py"]},
                                                     {"id": "s2", "files": ["c.py"]}]}


def test_the_seams_payload_with_no_plan_lists_no_slices():
    state = _round_one_state()
    state["step"] = RD.P_SEAMS
    assert RD._advance(state, state["config"])["payload"] == {"fullDiff": True, "slices": []}


def test_the_seams_order_sidecar_carries_the_slice_list(tmp_path):
    state = _round_one_state(SLICE_PLAN)
    state["step"] = RD.P_SEAMS
    payload = RD._advance(state, state["config"])["payload"]
    ((path, content),) = RD._order_sidecar_writes(str(tmp_path), 1, RD.P_SEAMS, ["seams-check"], payload)
    assert os.path.basename(path) == "seams-slices.json"
    assert json.loads(content.decode("utf-8")) == {"slices": payload["slices"]}


# --- a saved session at the retired extra pass continues past it ----------------------------------------------------

def _saved_at_retired_step(tmp_path, where):
    session_dir = str(tmp_path / ("saved-" + where))
    os.makedirs(session_dir)
    state = RD.new_state(dict(CFG))
    state["reviewedDiff"] = DIFF
    state["findings"] = []
    state["fullPanelRan"] = True
    state["_gapSweptRound"] = 1
    state["_gapMerge"] = True
    state["_verifiedCarry"] = []
    pending = {"action": RETIRED_STEP, "phase": RETIRED_STEP, "round": 1, "attempt": 0, "payload": {}}
    if where == "step":
        state["step"] = RETIRED_STEP
        state["pending"] = None
    else:
        state["step"] = RD.P_VERIFIERS
        state["pending"] = pending
    RD.save_state(session_dir, state)
    return session_dir


@pytest.mark.parametrize("where", ["step", "pending"])
def test_a_current_generation_session_saved_at_the_retired_step_continues_past_it(tmp_path, where):
    session_dir = _saved_at_retired_step(tmp_path, where)
    assert RD._commit_recover_or_refuse(session_dir, "next") is None
    ok, state = RD.load_state(session_dir)
    assert ok, state
    pending = state.get("pending") if isinstance(state.get("pending"), dict) else {}
    assert RETIRED_STEP not in (state.get("step"), pending.get("action"), pending.get("phase"))
    assert state.get("terminal") or state["step"] in RP.ALL_PHASES
    for gone in ("_gapSweptRound", "_gapMerge", "_verifiedCarry"):
        assert gone not in state, gone
    assert [d["kind"] for d in state["decisions"]].count("retired-gap-sweep") == 1
    assert "retired-gap-sweep" in decision_kinds.DECISION_KINDS
    rows = [r for r in RD.read_journal(session_dir) if r.get("outcome") == "retired-step-dropped"]
    assert len(rows) == 1 and rows[0]["round"] == 1


def test_the_retired_step_handler_leaves_other_states_as_they_are():
    base = RD.new_state(dict(CFG))
    base["step"] = RETIRED_STEP
    earlier = dict(copy.deepcopy(base), sessionGeneration=6)
    finished = dict(copy.deepcopy(base), terminal="converged")
    at_panel = RD.new_state(dict(CFG))
    for state in (earlier, finished, at_panel):
        before = json.dumps(state, sort_keys=True)
        assert RD._finish_retired_extra_pass(state) is False
        assert json.dumps(state, sort_keys=True) == before


def _past_retired_pass(tmp_path, carry):
    session_dir = str(tmp_path / "past-retired")
    os.makedirs(session_dir)
    state = RD.new_state(dict(CFG))
    state["reviewedDiff"] = DIFF
    state["findings"] = []
    state["step"] = RD.P_VERIFIERS
    state["pending"] = {"action": RD.P_VERIFIERS, "phase": RD.P_VERIFIERS, "round": 1, "attempt": 0, "payload": {}}
    if carry is not None:
        blocker = _finding("verified blocker", "a.py")
        state["_verifiedCarry"] = [blocker]
        state["findings"] = [blocker]
    RD.save_state(session_dir, state)
    return session_dir


def test_a_session_already_past_the_retired_pass_with_verified_blockers_is_handed_back(tmp_path):
    session_dir = _past_retired_pass(tmp_path, carry=True)
    assert RD._commit_recover_or_refuse(session_dir, "next") is None
    ok, state = RD.load_state(session_dir)
    assert ok, state
    assert state["terminal"] == "handed-back"
    assert state["certification"]["shape"] is None
    assert state.get("pending") is None
    assert "_verifiedCarry" not in state
    assert [f["title"] for f in state["findings"]] == ["verified blocker"]


def test_a_session_past_the_retired_pass_without_a_verified_carry_is_unchanged(tmp_path):
    state = RD.load_state(_past_retired_pass(tmp_path, carry=None))[1]
    before = json.dumps(state, sort_keys=True)
    assert RD._finish_retired_extra_pass(state) is False
    assert json.dumps(state, sort_keys=True) == before


def test_a_finding_two_waves_both_report_reaches_the_verifiers_once():
    state = _round_one_state(SLICE_PLAN)
    twice = _finding("same bug", "a.py")
    state["_sliceCarry"] = [dict(twice)]
    roster = RP.panel_roster(state, state["config"])
    with mock.patch.object(RD, "_unread_of_wave", return_value=[]):
        RD._after_panel_wave(state, state["config"], roster, {}, {}, [dict(twice)])
    assert state["step"] == RD.P_SEAMS
    assert [f["title"] for f in state["_panelStaged"]] == ["same bug"]


def test_a_seams_candidate_at_a_panel_findings_place_is_merged_with_it():
    state = _round_one_state(SLICE_PLAN)
    _fold_panel_with(state, _finding("same bug", "a.py"))
    RD._fold(state, state["config"], RD.P_SEAMS, {"findings": [_finding("same bug", "a.py")]})
    assert [f["title"] for f in state["_toVerify"]] == ["same bug"]


def test_held_panel_findings_reach_the_receipt_when_the_seams_check_fails_authentication():
    state = _round_one_state(SLICE_PLAN)
    _fold_panel_with(state, _finding("panel bug", "a.py"))
    assert not state.get("findings")
    RD._retain_unauthenticated_finder_findings(state, {"findings": [_finding("seam bug", "b.py")]})
    assert sorted(f["title"] for f in state["findings"]) == ["panel bug", "seam bug"]


# --- the census: nothing shipped names the retired pass or the folder split -----------------------------------------

# the saved-state handler and its decision kind are the only places that name the retired pass
_NAMES_RETIRED_PASS = {"lib/round_driver.py", "lib/decision_kinds.py"}
_RETIRED_TOKENS = ("dispatch-gap-sweep", "retired-gap-sweep")
_CENSUS = re.compile(r"gap[- ]sweep|shard_plan|DEFAULT_SHARD", re.IGNORECASE)


def _shipped_files():
    patterns = ("lib/*.py", "eval/*.py", "rubric/orders/*.md", "skills/review-code/SKILL.md",
                "skills/review-code/reference/*.md")
    for pattern in patterns:
        for path in sorted(glob.glob(os.path.join(_PLUGIN_ROOT, pattern))):
            yield os.path.relpath(path, _PLUGIN_ROOT)


def test_no_shipped_library_module_order_template_or_review_code_doc_names_the_retired_pass_or_the_folder_split():
    found = []
    for rel in _shipped_files():
        with open(os.path.join(_PLUGIN_ROOT, rel), encoding="utf-8") as fh:
            text = fh.read()
        if rel in _NAMES_RETIRED_PASS:
            for token in _RETIRED_TOKENS:
                text = text.replace(token, "")
        found.extend("%s: %s" % (rel, m.group(0)) for m in _CENSUS.finditer(text))
    assert not found, "the retired names are still in shipped text:\n" + "\n".join(found)
    assert not os.path.exists(os.path.join(_PLUGIN_ROOT, "rubric", "orders", "dispatch-gap-sweep.md"))
