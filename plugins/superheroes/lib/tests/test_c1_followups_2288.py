"""#2288: three returning-review gaps in the round driver.

Pins, each at the place the rule is enforced:

F1  a returning review falls back to a full panel only for a diff section that changed: a file whose section is the
    same in the earlier review's diff and the round-1 diff (an unchanged binary, an unchanged rename) never reaches
    a diff parser, while the audit's own fixer delta still diffs the unfiltered pair;
F2  an audit-spawned child stays linked to its parent on the full returning path (`_after_audits`' audit-first branch)
    and across the key change a `_with_carried` merge makes;
F3  a round record's `fixGroups` lists every fix group that governed that round's fixes: a second synthesis wave of
    the round appends, a re-stamp of the same group adds nothing.

Edges: E1 a non-text diff into `_changed_sections_only` · E2 a section only one diff holds · E3 two identical
sections in one diff and one in the other · E4 no `auditSpawned` dict · E5 two parents at one merged key · E6 a
`fixGroups` that is not a list.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/c1_followups_2288.md
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import countable_lines  # noqa: E402
import delta_surface  # noqa: E402
import returning_review as R  # noqa: E402
import session_contract as SC  # noqa: E402
import test_break_it_loop as BL  # noqa: E402
import test_c1l11b_carried_findings as TC  # noqa: E402
import test_c1l11b_returning_session as TS  # noqa: E402
import test_fix_groups_c1l11c as TFG  # noqa: E402
import test_repeat_marks_c1l8 as TRM  # noqa: E402
import test_returning_review_c1l11 as TR  # noqa: E402
import test_round_driver as TRD  # noqa: E402
from test_c1l11b_returning_session import _isolated_git  # noqa: E402,F401  (autouse: no global git config)
from test_fix_scope_c7 import _ledger  # noqa: E402

RD = TRD.RD

# a binary file as git reads one: it has NUL bytes. Every character is ASCII, so the text-mode fixture writer
# puts down exactly these bytes.
BLOB = "vendor/blob.bin"
BIN_A = "".join(chr(i % 128) for i in range(1024))
BIN_B = BIN_A[::-1]


def _first_with(**extra):
    return dict(TS._first_leg(), **extra)


def _one_line_change(repo):
    repo.write("src/app.py", repo.read("src/app.py") + "extra = 1\n")
    repo.commit("a one-line change")


def _change_binary_and_a_line(repo):
    repo.write(BLOB, BIN_B)
    _one_line_change(repo)


def _baseline(s):
    """The earlier review's diff (``base...lastReviewed``), as the driver reads it."""
    baseline = RD._returning_baseline_diff(s.repo.root, s.base, s.reviewed)
    assert isinstance(baseline, str)
    return baseline


def _sections(diff, file):
    return [sec["text"] for sec in countable_lines.parse_sections(diff) if sec["file"] == file]


def _premise_unparseable(s):
    """The test's premise: neither the round-1 diff nor the earlier review's diff reads in a hunk parser as it stands."""
    assert delta_surface.parse_hunks(s.cfg["diff"]) is None
    assert delta_surface.parse_hunks(_baseline(s)) is None


def _returning_why(state):
    return state["rounds"]["1"]["returning"]["why"]


# --- T1 (F1): an unchanged section never reaches a parser ----------------------------------------------------------

def test_t1a_an_unchanged_binary_beside_a_one_line_change_gets_the_scoped_review_not_the_panel(tmp_path, monkeypatch):
    s = TS.Session(tmp_path, monkeypatch, first=_first_with(**{BLOB: BIN_A}), change=_one_line_change)
    assert "Binary files" in s.cfg["diff"] and "Binary files" in _baseline(s)  # premise: the binary is in both diffs
    _premise_unparseable(s)
    assert _sections(s.cfg["diff"], BLOB) == _sections(_baseline(s), BLOB) != []  # premise: and it did not change
    answer = s.next()
    state = s.state()
    assert (answer["action"], answer["round"]) == (RD.P_SCOPED, 1), answer
    assert state["fullPanelRan"] is False and state["rounds"]["1"]["roundKind"] == RD.RETURNING_KIND
    assert state["rounds"]["1"]["returning"]["read"] == "changed"
    assert not any(w.startswith(RD.RETURNING_SURFACE_UNKNOWN) for w in _returning_why(state)), _returning_why(state)
    assert list(answer["payload"]["hunks"]) == ["src/app.py"]
    assert "blob.bin" not in state["_fixDeltaDiff"] and "blob.bin" not in str(state["_newSurface"])


def test_t1b_an_unchanged_rename_beside_a_one_line_change_gets_the_scoped_review_not_the_panel(tmp_path, monkeypatch):
    real = TR.returning

    def renaming_first_leg(repo, **kwargs):  # the earlier review's commit renames a file the base holds
        repo.git("mv", "src/shared.py", "src/moved.py")
        return real(repo, **kwargs)

    monkeypatch.setattr(TR, "returning", renaming_first_leg)
    s = TS.Session(tmp_path, monkeypatch, first=TS._first_leg(), change=_one_line_change)
    # the driver's diff runs with rename detection on (`-M`), so a pure rename is a header-only section that names two paths
    header = "diff --git a/src/shared.py b/src/moved.py\nsimilarity index 100%\nrename from src/shared.py\nrename to src/moved.py\n"
    assert header in s.cfg["diff"] and header in _baseline(s)
    _premise_unparseable(s)
    assert _sections(s.cfg["diff"], "src/moved.py") == _sections(_baseline(s), "src/moved.py") != []
    answer = s.next()
    state = s.state()
    assert (answer["action"], answer["round"]) == (RD.P_SCOPED, 1), answer
    assert state["fullPanelRan"] is False and state["rounds"]["1"]["returning"]["read"] == "changed"
    assert not any(w.startswith(RD.RETURNING_SURFACE_UNKNOWN) for w in _returning_why(state)), _returning_why(state)
    assert list(answer["payload"]["hunks"]) == ["src/app.py"]


def test_t1c_a_changed_binary_still_forces_the_full_panel(tmp_path, monkeypatch):
    s = TS.Session(tmp_path, monkeypatch, first=_first_with(**{BLOB: BIN_A}), change=_change_binary_and_a_line)
    _premise_unparseable(s)
    [before], [after] = _sections(_baseline(s), BLOB), _sections(s.cfg["diff"], BLOB)
    assert before != after  # premise: the binary's bytes differ between the reviewed commit and the head
    answer = s.next()
    state = s.state()
    assert (answer["action"], answer["round"]) == (RD.P_PANEL, 1), answer
    # the decider itself reads a changed binary as `full` (its lines cannot be counted)
    assert _returning_why(state)[0].startswith(R.WHY_DIFF_UNREADABLE), _returning_why(state)
    assert state["config"]["returning"]["read"] == "full"
    # and the driver's own surface, asked for the same two diffs, is still unknown: the filter keeps a changed section
    surface, why = RD._returning_surface(state, dict(state["config"], returningBaselineDiff=_baseline(s)))
    assert surface is None and "could not be worked out for every file" in why, (surface, why)


@pytest.mark.parametrize("record,read", [(None, "changed"), (TC.ABANDONED, "full")], ids=["changed", "full"])
def test_t1d_the_carried_audit_target_shows_no_section_of_a_file_unchanged_between_the_two_diffs(tmp_path, monkeypatch, record, read):
    first = dict(TC.FIRST, **{"src/other.py": TR.numbered("other", 12), BLOB: BIN_A})
    finding = TC._finding(27)
    s = TC._session(tmp_path, monkeypatch, [finding], first=first, change=TC.FIXES_LINE_27, record=record)
    _premise_unparseable(s)
    for file in ("src/other.py", BLOB):  # premise: both unchanged files are in both diffs, the same
        assert _sections(s.cfg["diff"], file) == _sections(_baseline(s), file) != []
    answer = s.next()
    assert answer["action"] == RD.P_AUDITS and s.state()["config"]["returning"]["read"] == read, answer
    [target] = answer["payload"]["targets"]
    assert target["id"] == finding[SC.FINDING_KEY_FIELD]
    delta = target["fixerDelta"]
    assert "-+edited_b = 1" in delta and "++edited_b = 2" in delta, delta  # positive control: the fix is there
    assert not [ln for ln in delta if "other.py" in ln or "blob.bin" in ln or "value_other_" in ln or "Binary files" in ln], delta


# --- the helper's fail-closed edges --------------------------------------------------------------------------------

def _sec(name, tag="x"):
    return ("diff --git a/%s b/%s\nindex 1111111..2222222 100644\n--- a/%s\n+++ b/%s\n@@ -1 +1 @@\n-old %s\n+new %s\n"
            % (name, name, name, name, tag, tag))


def test_e1_a_diff_that_is_not_text_comes_back_unchanged():
    text = _sec("a.py")
    for pair in ((None, text), (text, None), (None, None), (3, text), (text, ["x"]), (b"x", text)):
        assert RD._changed_sections_only(*pair) == pair


def test_e2_a_section_only_one_diff_holds_is_never_dropped_and_order_and_preamble_are_kept():
    a, b, c, d = _sec("a.py"), _sec("b.py"), _sec("c.py"), _sec("d.py")
    base, head = "pre one\n" + a + b + c, "pre two\n" + a + d + c
    assert RD._changed_sections_only(base, head) == ("pre one\n" + b, "pre two\n" + d)
    # a file added since the last review, and one removed since: both stay, in their diff
    assert RD._changed_sections_only(a, a + b) == ("", b)
    assert RD._changed_sections_only(a + b, a) == (b, "")
    # nothing in common: both come back byte for byte
    assert RD._changed_sections_only(a, b) == (a, b)
    # the same file with different bytes is a changed section, kept in both
    assert RD._changed_sections_only(_sec("a.py", "1"), _sec("a.py", "2")) == (_sec("a.py", "1"), _sec("a.py", "2"))


def test_e3_two_identical_sections_in_one_diff_and_one_in_the_other_drop_one_pair_only():
    a, b = _sec("a.py"), _sec("b.py")
    assert RD._changed_sections_only(a + b + a, a) == (b + a, "")
    assert RD._changed_sections_only(a, a + b + a) == ("", b + a)
    assert RD._changed_sections_only(a + a, a + a) == ("", "")


def test_a_diff_with_no_section_has_nothing_to_drop():
    assert RD._changed_sections_only("", "") == ("", "")
    assert RD._changed_sections_only("only a preamble\n", _sec("a.py")) == ("only a preamble\n", _sec("a.py"))


# --- T2 (F2): an audit-spawned child stays linked to its parent ---------------------------------------------------

CHILD = {"title": "the first edited value is stale", "severity": "Minor", "file": TC.SHARED, "line": 3,
         "consequence": TRD._CONSEQUENCE, "consequenceKind": "real", "body": "the value no longer matches line 27",
         "suggestion": "reword it"}


def _spawning_responder(parent_key):
    """Round 1's audit keeps the carried parent (not discharged) and raises CHILD; every later ruling discharges."""
    first = TC._respond(audit="not-discharged", verdict="CONFIRMED")
    later = TC._respond(audit="discharged", verdict="CONFIRMED")

    def respond(phase, payload, rnd):
        art = (first if rnd == 1 else later)(phase, payload, rnd)
        if phase == RD.P_AUDITS and rnd == 1:
            for result in art["results"]:
                if result["id"] == parent_key:
                    result["newIssues"] = [dict(CHILD)]
        return art

    return respond


def test_t2a_a_child_the_full_returning_audit_raised_is_linked_rides_the_parents_next_audit_and_is_not_left_unfixed(tmp_path, monkeypatch):
    parent = TC._finding(27, tradeoff=False)
    pk = parent[SC.FINDING_KEY_FIELD]
    s = TC._session(tmp_path, monkeypatch, [parent], change=TC.TOUCHES_NEAR_27, record=TC.ABANDONED)
    respond = _spawning_responder(pk)
    # round 1, the full read: the carried parent is audited first, then the panel runs
    n, seen = TC._run(s, respond, stop_at=RD.P_VERIFIERS)
    assert n["action"] == RD.P_VERIFIERS and seen[:2] == [(RD.P_AUDITS, 1), (RD.P_PANEL, 1)], seen
    state = s.state()
    assert state["config"]["returning"]["read"] == "full"
    [ck] = [SC.finding_identity_key(f) for f in state["_toVerify"] if f.get("title") == CHILD["title"]]
    assert ck != pk
    assert state["auditSpawned"] == {ck: pk}  # the link is bound where the audit's new issues are compiled
    # the parent is sent back for a fix; the Minor child is no fix of this batch
    n, seen = TC._run(s, respond, stop_at=RD.P_APPLY_FIXES)
    assert n["action"] == RD.P_APPLY_FIXES, seen
    assert [SC.finding_identity_key(f) for f in n["payload"]["batch"]] == [pk]
    state = s.state()
    assert state["auditSpawned"] == {ck: pk}
    # the next audit carries the child as a rider on the parent's
    state["round"] = 2
    state["fixBatch"] = list(state["_fixBatch"])
    targets = RD._audit_targets(state, state["config"], {})
    assert [t["id"] for t in targets] == [pk, ck], targets
    assert [t.get("spawnedFrom") for t in targets] == [None, pk]
    # the parent's fix resolves both: the child is recorded fixed, never left unfixed for the owner
    monkeypatch.setattr(RD, "_after_audits", lambda st, config: None)
    state["_auditTargets"] = targets
    results = [{"id": t["id"], "ruling": "discharged", "reason": "the fix resolves it", "checks": TRD.audit_checks(),
                "auditorVendor": t.get("auditorVendor")} for t in targets]
    RD._fold_audits(state, state["config"], {"results": results,
                                             "collectionManifest": {t["id"]: t.get("auditorVendor") for t in targets}})
    state["terminal"] = "converged"
    RD._settle_open_findings(state)
    ledger = _ledger(state)
    assert ledger[ck]["disposition"] == "fixed" and ledger[pk]["disposition"] == "fixed", (ledger[ck], ledger[pk])
    assert not [r for r in ledger.values() if r.get("disposition") == "left-for-owner"]
    assert "settledReason" not in ledger[ck]


def _merge_state(spawned):
    """A state whose carried child (a held row under its stored key) is about to meet the fresh report of the same finding
    (a different key), with ``spawned`` as its spawn map (None leaves it without one)."""
    parent = TC._finding(27)
    held = TC._finding(3, title="the first edit is stale", severity="Minor", consequenceKind="code-quality")
    fresh = TC._compiled(held, consequenceKind="real")
    fresh_key = RD._finding_identity_key(fresh)
    assert fresh_key != held[SC.FINDING_KEY_FIELD]
    state = RD.new_state(TRD._cfg())
    state["_carriedToVerify"] = [held]
    if spawned is not None:
        state["auditSpawned"] = spawned
    return state, parent, held, fresh, fresh_key


def test_t2b_a_compiled_child_bound_to_a_parent_keeps_its_link_under_the_key_the_merge_keeps_and_still_rides():
    state, parent, held, fresh, fresh_key = _merge_state(None)
    pk, hk = parent[SC.FINDING_KEY_FIELD], held[SC.FINDING_KEY_FIELD]
    new_issue = dict(fresh, originAuditId=pk)  # an audit of the parent raised it
    compiled = RD.mechanical_compile([dict(new_issue)], None)[0]
    RD._bind_audit_spawned(state, [new_issue], compiled)
    assert state["auditSpawned"] == {fresh_key: pk}  # premise: bound under the fresh report's key
    merged = RD._with_carried(state, compiled)
    [row] = merged
    assert RD._finding_identity_key(row) == hk  # the merged row keeps the held row's stored key
    assert state["auditSpawned"] == {hk: pk}
    # the child rides the parent's next audit under the key it now has
    RD._stage_findings(state, [dict(parent), row])
    RD._set_findings(state, state["_toVerify"])
    state["round"] = 2
    state["fixBatch"] = [r for r in state["findings"] if RD._finding_identity_key(r) == pk]
    targets = RD._audit_targets(state, state["config"], {})
    assert [t["id"] for t in targets] == [pk, hk], targets
    assert [t.get("spawnedFrom") for t in targets] == [None, pk]


def test_t2b_two_different_parents_converging_on_one_merged_key_leave_no_link():
    # a link under the fresh report's key and a link under the held row's own key, to different parents
    state, parent, held, fresh, fresh_key = _merge_state(None)
    hk = held[SC.FINDING_KEY_FIELD]
    state["auditSpawned"] = {fresh_key: "f.py::parent a@L1", hk: "f.py::parent b@L2", "f.py::other@L9": "f.py::parent c@L3"}
    RD._with_carried(state, [fresh])
    assert state["auditSpawned"] == {"f.py::other@L9": "f.py::parent c@L3"}
    # the same parent behind both keys is one link, at the merged key
    state, parent, held, fresh, fresh_key = _merge_state(None)
    state["auditSpawned"] = {fresh_key: "f.py::parent a@L1", held[SC.FINDING_KEY_FIELD]: "f.py::parent a@L1"}
    RD._with_carried(state, [fresh])
    assert state["auditSpawned"] == {held[SC.FINDING_KEY_FIELD]: "f.py::parent a@L1"}


def test_e4_a_state_with_no_usable_spawn_map_is_left_without_one_by_a_merge():
    state, parent, held, fresh, fresh_key = _merge_state(None)
    RD._with_carried(state, [fresh])
    assert "auditSpawned" not in state
    for junk in (["not", "a", "dict"], "x", 7):
        state, parent, held, fresh, fresh_key = _merge_state(junk)
        RD._with_carried(state, [fresh])
        assert state["auditSpawned"] == junk
    # a spawn map with no entry for either key is left as it was
    state, parent, held, fresh, fresh_key = _merge_state({"f.py::other@L9": "f.py::parent c@L3"})
    RD._with_carried(state, [fresh])
    assert state["auditSpawned"] == {"f.py::other@L9": "f.py::parent c@L3"}


def test_e5_a_child_already_linked_under_the_merged_key_to_another_parent_is_not_given_a_second_link():
    state, parent, held, fresh, fresh_key = _merge_state(None)
    hk = held[SC.FINDING_KEY_FIELD]
    state["auditSpawned"] = {fresh_key: "f.py::parent a@L1", hk: "f.py::parent a@L1"}
    RD._with_carried(state, [fresh])
    assert state["auditSpawned"] == {hk: "f.py::parent a@L1"}
    state, parent, held, fresh, fresh_key = _merge_state(None)
    state["auditSpawned"] = {fresh_key: "f.py::parent a@L1", held[SC.FINDING_KEY_FIELD]: "f.py::parent b@L2"}
    RD._with_carried(state, [fresh])
    assert state["auditSpawned"] == {}


# --- T3 (F3): a second synthesis wave appends its fix groups --------------------------------------------------------

def _wave(state, tag, a_path, b_path):
    """One verified-and-synthesized wave of two same-root-cause findings, each carrying a break-it test; returns their keys."""
    first = TRM._raw("%s one" % tag, line=1, suggestion=BL._block(a_path, TFG.A_TEST))
    second = TRM._raw("%s two" % tag, line=2, suggestion=BL._block(b_path, TFG.B_TEST))
    TRM._verify(state, [first, second], {first["title"]: "CONFIRMED", second["title"]: "CONFIRMED"})
    ids = TRM._ids(state)
    TRM._synth(state, [TRM._group(ids[first["title"]], ids[second["title"]])])
    return [TRM._key(first), TRM._key(second)]


def _groups(state, rnd):
    return [(g["id"], sorted(g["members"])) for g in state["rounds"][str(rnd)]["fixGroups"]]


def test_t3a_a_round_with_a_second_synthesis_wave_records_both_waves_groups_the_first_waves_first():
    state = TRM._state()
    wave_one = _wave(state, "wave one", TFG.A_PATH, TFG.B_PATH)
    assert _groups(state, 1) == [(TFG._group_id(*wave_one), sorted(wave_one))]
    wave_two = _wave(state, "wave two", "tests/test_wave_two_a.py", "tests/test_wave_two_b.py")
    assert state["round"] == 1
    assert _groups(state, 1) == [(TFG._group_id(*wave_one), sorted(wave_one)), (TFG._group_id(*wave_two), sorted(wave_two))]
    # the row stamps are the live rows' alone: the second wave's findings replaced the first wave's rows
    assert sorted(RD._finding_identity_key(r) for r in state["findings"] if "fixGroup" in r) == sorted(wave_two)


def test_t3b_stamping_the_same_groups_again_in_one_round_does_not_duplicate_them():
    u = TFG._unit()
    RD._stamp_fix_groups(u.state, TFG.GROUP, u.state["findings"])
    RD._stamp_fix_groups(u.state, TFG.GROUP, u.state["findings"])
    assert u.state["rounds"]["1"]["fixGroups"] == [{"id": u.gid, "members": [u.ka, u.kb]}]
    # a stamp that finds no group in a round that already has one keeps what is recorded
    RD._stamp_fix_groups(u.state, [], u.state["findings"])
    assert u.state["rounds"]["1"]["fixGroups"] == [{"id": u.gid, "members": [u.ka, u.kb]}]


def test_t3c_a_round_that_stamps_no_group_still_records_an_empty_list():
    u = TFG._unit(stamp=False)
    RD._stamp_fix_groups(u.state, [], u.state["findings"])
    assert u.state["rounds"]["1"]["fixGroups"] == []


@pytest.mark.parametrize("junk", ["not a list", {"id": "x"}, 7, None], ids=["str", "dict", "int", "none"])
def test_e6_a_fix_groups_that_is_not_a_list_is_treated_as_empty_and_replaced_by_a_list(junk):
    u = TFG._unit(stamp=False)
    u.state["rounds"].setdefault("1", {})["fixGroups"] = junk
    RD._stamp_fix_groups(u.state, TFG.GROUP, u.state["findings"])
    assert u.state["rounds"]["1"]["fixGroups"] == [{"id": u.gid, "members": [u.ka, u.kb]}]
