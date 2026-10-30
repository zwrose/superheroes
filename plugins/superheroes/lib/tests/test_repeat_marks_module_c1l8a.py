"""The repeat-marks module on its own (C1-L8a).

`repeat_marks` is imported directly; nothing here reaches it through the round driver. Edges: M-D1..M-D7 the seven
rows of the decision table (`decide`) · outcome_of and disposition_of · M-C `code_changed` reads the tree and
fails closed · M-S a session ledger row's outcome follows the record writer's three readings of a refuted row ·
M-R a record finding is pooled, an undecided one with outcome None, a malformed one never · the file readings ·
pool order, refs and the no-double-listing rule · exact identity (session raw key, record stored key) over the
judge's name · the judge's refs · the grouping faults (unknown ref, a refuted id twice, refuted ids set aside
before survivor coverage, a refuted-only group, an omitted survivor) · strip_groups · kept_reason.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/c1l8a_repeat_marks_module.md
"""
import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import repeat_marks as RM  # noqa: E402
import session_contract as SC  # noqa: E402

_CONSEQUENCE = "a reviewer-found defect stays in the change"
_WRONG = {"verdict": "wrong", "reason": "the guard at line 40 returns early"}


# ---- fixtures and helpers ---------------------------------------------------------------------

def _git(root, *args):
    """git in the fixture repo: no user or system config, an inline identity, no signing."""
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    return subprocess.run(
        ["git", "-c", "user.name=superheroes-test", "-c", "user.email=superheroes-test@example.invalid",
         "-c", "commit.gpgsign=false", "-C", root, *args],
        check=True, capture_output=True, text=True, env=env).stdout.strip()


def _write_tree(root, text):
    with open(os.path.join(root, "f.txt"), "w", encoding="utf-8") as fh:
        fh.write(text)


@pytest.fixture
def repo(tmp_path):
    """A real repo with three heads: `first`, `changed` (a different tree) and `same` (changed's tree)."""
    root = str(tmp_path / "repo")
    os.makedirs(root)
    _git(root, "init", "-q")
    _write_tree(root, "one\n")
    _git(root, "add", "f.txt")
    _git(root, "commit", "-q", "-m", "first")
    first = _git(root, "rev-parse", "HEAD")
    _write_tree(root, "two\n")
    _git(root, "commit", "-a", "-q", "-m", "change the tree")
    changed = _git(root, "rev-parse", "HEAD")
    _git(root, "commit", "-q", "--allow-empty", "-m", "same tree")
    return SimpleNamespace(root=root, first=first, changed=changed, same=_git(root, "rev-parse", "HEAD"))


def _raw(title, line=1, **extra):
    return dict({"severity": "Important", "file": "f.py", "consequence": _CONSEQUENCE},
                title=title, line=line, **extra)


def _key(raw):
    return SC.finding_identity_key(raw)


def _row(raw, disposition, decided=1, **extra):
    """A ledger row of ``raw`` decided in round ``decided``."""
    return dict(raw, disposition=disposition, dispositionRound=decided, raisedSeq=1, dispositionSeq=2, **extra)


def _stored(raw, outcome, **extra):
    """A finding as the review record holds it: an opaque stored key and an outcome."""
    return dict(raw, findingKey=RM.opaque_key(raw), outcome=outcome, **extra)


def _record_payload(findings, sha="a" * 40):
    return {"ok": True, "findings": findings, "finalCommit": {"sha": sha}}


def _group(*ids, ref=None, group_id="g"):
    return {"group_id": group_id, "member_ids": list(ids), "repeatOf": ref}


def _pool(*rows):
    """A pool of one session entry per ``(raw, disposition)`` pair, refs from e1."""
    return RM.build_pool([_row(raw, disposition) for raw, disposition in rows], 2, [])


# ---- the decision table (one test per row) ----------------------------------------------------

def test_d1_a_fixed_finding_raised_again_and_found_wrong_is_kept_and_the_fix_holds():
    assert RM.decide("fixed", "wrong", False) == (True, True)
    assert RM.decide("fixed", "wrong", True) == (True, True)


@pytest.mark.parametrize("grade", ["confirmed", "plausible", None])
def test_d2_a_fixed_finding_raised_again_with_any_other_grade_is_a_new_finding(grade):
    assert RM.decide("fixed", grade, False) == (False, False)
    assert RM.decide("fixed", grade, True) == (False, False)


def test_d3_a_shown_wrong_finding_after_a_code_change_and_found_wrong_again_is_kept():
    assert RM.decide("shown-wrong", "wrong", True) == (True, None)


@pytest.mark.parametrize("grade", ["confirmed", "plausible", None])
def test_d4_a_shown_wrong_finding_after_a_code_change_with_any_other_grade_is_new(grade):
    assert RM.decide("shown-wrong", grade, True) == (False, None)


@pytest.mark.parametrize("grade", ["wrong", "confirmed", "plausible", None])
def test_d5_a_shown_wrong_finding_on_unchanged_code_is_kept_whatever_the_grade(grade):
    assert RM.decide("shown-wrong", grade, False) == (True, None)


def test_d5_the_change_is_read_only_for_a_shown_wrong_outcome():
    reads = []

    def changed():
        reads.append(1)
        return True

    for outcome in ("fixed", "craft", "left-for-owner", "ruling", None):
        RM.decide(outcome, "confirmed", changed)
    assert reads == []
    assert RM.decide("shown-wrong", "confirmed", changed) == (False, None)
    assert reads == [1]


@pytest.mark.parametrize("outcome", ["craft", "left-for-owner", "ruling"])
@pytest.mark.parametrize("grade", ["wrong", "confirmed", None])
def test_d6_a_settled_outcome_is_kept_whatever_the_grade_and_the_code(outcome, grade):
    assert RM.decide(outcome, grade, True) == (True, None)
    assert RM.decide(outcome, grade, False) == (True, None)


@pytest.mark.parametrize("grade", ["wrong", "confirmed", None])
def test_d7_an_undecided_earlier_finding_is_a_new_finding(grade):
    assert RM.decide(None, grade, False) == (False, None)
    assert RM.decide(None, grade, True) == (False, None)
    assert RM.decide("open", grade, True) == (False, None)


# ---- outcome_of, disposition_of ---------------------------------------------------------------

def test_outcome_of_maps_a_ledger_disposition_and_an_out_of_scope_row_counts_as_a_ruling():
    assert RM.outcome_of("out-of-scope") == "ruling"
    assert RM.outcome_of("fixed") == "fixed"
    for token in ("craft", "left-for-owner", "ruling"):
        assert RM.outcome_of(token) == token
    assert RM.outcome_of("shown-wrong") is None and RM.outcome_of(None) is None and RM.outcome_of("open") is None


def test_outcome_of_reads_a_refuted_row_as_the_record_writer_does():
    assert RM.outcome_of("refuted", {"grade": _WRONG}) == "shown-wrong"
    assert RM.outcome_of("refuted", {"refutedReason": "author-justified: the owner chose this"}) == "left-for-owner"
    assert RM.outcome_of("refuted", {"grade": {"verdict": "confirmed"}, "refutedReason": "guard holds"}) is None
    assert RM.outcome_of("refuted", {}) is None and RM.outcome_of("refuted") is None


def test_disposition_of_writes_shown_wrong_as_refuted_and_every_other_outcome_as_itself():
    assert RM.disposition_of("shown-wrong") == "refuted"
    for outcome in ("fixed", "craft", "left-for-owner", "ruling"):
        assert RM.disposition_of(outcome) == outcome


# ---- the code-changed read --------------------------------------------------------------------

def test_code_changed_is_false_for_the_same_tree_at_two_heads(repo):
    assert RM.code_changed(repo.root, repo.changed, repo.same) is False
    assert RM.code_changed(repo.root, repo.same, repo.same) is False


def test_code_changed_is_true_when_the_tree_differs(repo):
    assert RM.code_changed(repo.root, repo.first, repo.changed) is True
    assert RM.code_changed(repo.root, repo.first, repo.same) is True


def test_code_changed_counts_an_unreadable_head_as_changed(repo):
    assert RM.code_changed(repo.root, None, repo.same) is True
    assert RM.code_changed(repo.root, repo.changed, "") is True
    assert RM.code_changed(repo.root, repo.changed, 7) is True
    assert RM.code_changed(repo.root, "0" * 40, repo.same) is True
    assert RM.code_changed(None, repo.changed, repo.same) is True


def test_code_changed_counts_a_head_starting_with_a_dash_as_changed(repo):
    assert RM.code_changed(repo.root, "-oops", repo.same) is True
    assert RM.code_changed(repo.root, repo.changed, "--help") is True


def test_code_changed_counts_a_failed_git_run_as_changed(repo, monkeypatch):
    assert RM.code_changed(repo.root + "-absent", repo.changed, repo.same) is True  # git exits non-zero
    for failure in (OSError("no git"), subprocess.TimeoutExpired("git", 30)):
        def refuse(*args, **kwargs):
            raise failure
        monkeypatch.setattr(RM.subprocess, "run", refuse)
        assert RM.code_changed(repo.root, repo.changed, repo.same) is True


# ---- the pool entries of a session ledger row (the record writer's three readings) -----------------

def test_s1_a_refuted_row_with_the_verifiers_wrong_grade_is_pooled_as_shown_wrong():
    entry = RM.session_entry(_row(_raw("a"), "refuted", grade=dict(_WRONG), refutedReason="guard holds"), 2)
    assert (entry["source"], entry["outcome"], entry["grade"]) == ("session", "shown-wrong", _WRONG)
    assert entry["key"] == _key(_raw("a")) and entry["round"] == 1
    assert entry["family"]["disposition"] == "refuted"


def test_s2_a_refuted_row_with_an_author_justified_reason_is_pooled_as_left_for_owner():
    entry = RM.session_entry(_row(_raw("a"), "refuted", refutedReason="author-justified: the owner chose this"), 2)
    assert entry["outcome"] == "left-for-owner"


def test_s3_a_refuted_row_with_neither_reading_is_undecided_and_not_pooled():
    assert RM.session_entry(_row(_raw("a"), "refuted", refutedReason="guard holds"), 2) is None
    assert RM.session_entry(_row(_raw("a"), "refuted", grade={"verdict": "confirmed", "reason": "r"}), 2) is None
    assert RM.session_entry(_row(_raw("a"), "refuted"), 2) is None


def test_a_session_row_is_pooled_only_when_decided_in_an_earlier_round_and_after_it_was_raised():
    assert RM.session_entry(_row(_raw("a"), "craft"), 2)["outcome"] == "craft"
    assert RM.session_entry(_row(_raw("a"), "out-of-scope"), 2)["outcome"] == "ruling"
    assert RM.session_entry(_row(_raw("a"), "craft", decided=2), 2) is None      # this round's decision
    assert RM.session_entry(_row(_raw("a"), "craft", decided=True), 2) is None   # not a plain int
    assert RM.session_entry(dict(_row(_raw("a"), "craft"), dispositionSeq=1), 2) is None  # stale disposition
    assert RM.session_entry(dict(_row(_raw("a"), "craft"), raisedSeq=None), 2) is None
    assert RM.session_entry(dict(_raw("a"), raisedSeq=1, dispositionSeq=2), 2) is None    # never decided
    assert RM.session_entry("not a dict", 2) is None and RM.session_entry(None, 2) is None


# ---- the pool entries of a record finding -----------------------------------------------------------

def test_r1_an_undecided_earlier_finding_is_pooled_with_outcome_none_and_reads_as_new():
    open_finding = dict(_raw("still open", id="R-9"), findingKey=RM.opaque_key(_raw("still open")), outcome=None)
    entry = RM.record_entry(open_finding, "b" * 40)
    assert entry is not None
    assert (entry["source"], entry["key"], entry["id"], entry["outcome"], entry["head"]) == (
        "record", open_finding["findingKey"], "R-9", None, "b" * 40)
    assert RM.decide(entry["outcome"], "wrong", False) == (False, None)
    assert RM.record_entry(_raw("no outcome field", line=2), None)["outcome"] is None
    odd = RM.record_entry(dict(_raw("odd outcome", line=4), findingKey="rr1:x", outcome="open"), None)
    assert odd["outcome"] is None
    entries, reason = RM.read_earlier_findings(_record_payload([open_finding]))
    assert reason is None and [e["outcome"] for e in entries] == [None]


def test_r2_a_decided_record_finding_reads_into_a_pool_entry_with_its_judged_head():
    keep = _stored(_raw("kept", id="R-1"), "craft")
    entries, reason = RM.read_earlier_findings(_record_payload([keep], sha="b" * 40))
    assert reason is None
    assert [(e["source"], e["key"], e["id"], e["outcome"], e["head"]) for e in entries] == [
        ("record", keep["findingKey"], "R-1", "craft", "b" * 40)]


def test_r3_a_record_finding_with_no_key_and_no_file_and_title_is_never_pooled():
    rows = [
        _stored(_raw("good"), "ruling"),
        {"outcome": "craft", "title": "titled only"},     # no stored key, no file
        {"outcome": "craft", "file": "f.py"},              # no stored key, no title
        {"findingKey": "", "outcome": "craft"},            # empty key, nothing to mint
        "not a dict", None, 7,
    ]
    entries, reason = RM.read_earlier_findings(_record_payload(rows))
    assert reason is None
    assert [e["title"] for e in entries] == ["good"]
    minted = {"outcome": "craft", "file": "f.py", "title": "no stored key", "line": 9}
    entries, _ = RM.read_earlier_findings(_record_payload([minted]))
    assert entries[0]["key"] == RM.opaque_key(minted)
    assert RM.record_entry("not a dict", None) is None


def test_the_record_readings_name_a_reason_unless_the_record_is_missing():
    assert RM.read_earlier_findings({"ok": False, "reason": "review-record-missing"}) == ([], None)
    assert RM.read_earlier_findings({"ok": False, "reason": "review-record-unreadable"}) == (
        [], "review-record-unreadable")
    assert RM.read_earlier_findings({"ok": False}) == ([], "refused")
    assert RM.read_earlier_findings({"ok": False, "reason": "  "}) == ([], "refused")
    for malformed in ([], "x", None, {"findings": []}, {"ok": True, "findings": "x"}, {"ok": "yes", "findings": []}):
        assert RM.read_earlier_findings(malformed) == ([], "malformed"), malformed
    entries, reason = RM.read_earlier_findings({"ok": True, "findings": [_stored(_raw("a"), "craft")]})
    assert reason is None and entries[0]["head"] is None  # no finalCommit: no judged head


# ---- the earlier-findings file ------------------------------------------------------------------------

def test_read_file_names_a_missing_unreadable_or_not_json_file(tmp_path):
    assert RM.read_file(str(tmp_path / "absent.json")) == (None, [], "file-missing")
    assert RM.read_file(str(tmp_path)) == (None, [], "unreadable")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert RM.read_file(str(bad)) == (None, [], "not-json")


def test_read_file_reads_the_ok_true_the_missing_record_and_the_other_refusal_readings(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(_record_payload([_stored(_raw("a"), "craft")])), encoding="utf-8")
    payload, entries, reason = RM.read_file(str(good))
    assert payload["ok"] is True and len(entries) == 1 and reason is None

    missing = tmp_path / "missing.json"
    missing.write_text(json.dumps({"ok": False, "reason": "review-record-missing"}), encoding="utf-8")
    assert RM.read_file(str(missing)) == ({"ok": False, "reason": "review-record-missing"}, [], None)

    refused = tmp_path / "refused.json"
    refused.write_text(json.dumps({"ok": False, "reason": "review-record-unreadable"}), encoding="utf-8")
    assert RM.read_file(str(refused)) == ({"ok": False, "reason": "review-record-unreadable"}, [],
                                          "review-record-unreadable")

    listed = tmp_path / "list.json"
    listed.write_text("[]", encoding="utf-8")
    assert RM.read_file(str(listed)) == (None, [], "malformed")


# ---- the pool: order, refs, no double listing -------------------------------------------------------

def test_the_pool_lists_session_rows_then_record_findings_with_refs_from_e1():
    ledger = [_row(_raw("session one", line=1), "fixed"),
              _row(_raw("session two", line=2), "refuted", grade=dict(_WRONG)),
              dict(_raw("still open", line=3), raisedSeq=1)]
    record = [RM.record_entry(_stored(_raw("record one", line=4), "craft"), "c" * 40),
              RM.record_entry(_stored(_raw("record open", line=5), None), "c" * 40)]
    pool = RM.build_pool(ledger, 2, record)
    assert [(e["ref"], e["source"], e["title"], e["outcome"]) for e in pool] == [
        ("e1", "session", "session one", "fixed"), ("e2", "session", "session two", "shown-wrong"),
        ("e3", "record", "record one", "craft"), ("e4", "record", "record open", None)]
    assert RM.build_pool(ledger, 1, []) == []                      # nothing was decided before round 1
    assert RM.build_pool(None, 2, None) == []


def test_a_record_finding_the_session_already_holds_is_not_listed_twice():
    session_raw = _raw("session one", line=1)
    ledger = [_row(session_raw, "fixed")]
    by_stored_key = RM.record_entry(_stored(session_raw, "fixed"), "c" * 40)
    by_raw_key = dict(by_stored_key, key=_key(session_raw))
    other = RM.record_entry(_stored(_raw("other", line=2), "craft"), "c" * 40)
    for held in (by_stored_key, by_raw_key):
        pool = RM.build_pool(ledger, 2, [held, other])
        assert [(e["ref"], e["title"], e["source"]) for e in pool] == [
            ("e1", "session one", "session"), ("e2", "other", "record")]
    twice = RM.build_pool([], 2, [other, dict(other)])             # two record entries of one key: one listing
    assert [e["ref"] for e in twice] == ["e1"]


def test_order_list_carries_the_six_fields_the_order_names():
    pool = _pool((_raw("one", id="F-1"), "craft"), (_raw("two", line=2), "ruling"))
    assert RM.order_list(pool) == [
        {"ref": "e1", "id": "F-1", "file": "f.py", "line": 1, "title": "one", "outcome": "craft"},
        {"ref": "e2", "id": None, "file": "f.py", "line": 2, "title": "two", "outcome": "ruling"}]
    assert RM.order_list(None) == [] and RM.order_list([]) == []


# ---- exact identity and the judge's refs ---------------------------------------------------------------

def test_exact_match_reads_a_session_raw_key_and_a_record_stored_key():
    session_entry = dict(RM.session_entry(_row(_raw("s"), "craft"), 2), ref="e1")
    stored_entry = RM.record_entry(_stored(_raw("r", line=2), "ruling"), None)
    pool = RM.build_pool([], 2, [stored_entry])
    pool = [session_entry] + [dict(pool[0], ref="e2")]
    assert RM.exact_match(_raw("s"), pool) is pool[0]
    assert RM.exact_match(_raw("r", line=2), pool) is pool[1]
    assert RM.exact_match(_raw("other"), pool) is None
    assert RM.exact_match(_raw("s"), []) is None and RM.exact_match(_raw("s"), None) is None
    # a session entry is matched on its raw key only, a record entry on its stored key only
    assert RM.exact_match(_raw("r", line=2), pool[:1]) is None
    assert RM.exact_match(dict(_raw("r", line=2), findingKey=stored_entry["key"]), [pool[1]]) is pool[1]


def test_judge_refs_maps_each_member_of_a_naming_group_to_its_ref():
    grouping = [_group("v0", "v1", ref="e1", group_id="a"), _group("v2", ref=None, group_id="b"),
                {"group_id": "c", "member_ids": ["v3", 4, None], "repeatOf": "e2"},
                {"group_id": "d", "member_ids": "v5", "repeatOf": "e3"},
                {"group_id": "e", "member_ids": ["v6"]}, "not a group"]
    assert RM.judge_refs(grouping) == {"v0": "e1", "v1": "e1", "v3": "e2"}
    assert RM.judge_refs(None) == {} and RM.judge_refs("x") == {}


def test_m3_exact_identity_wins_over_the_judges_name():
    craft, fixed = _raw("craft A", line=1), _raw("fixed B", line=2)
    pool = _pool((craft, "craft"), (fixed, "fixed"))
    staged = [dict(craft, id="v0")]
    marks = RM.mark_repeats(staged, pool, {"v0": "e2"})            # the judge names the fixed finding
    assert marks == {"v0": (pool[0], "exact")}
    assert marks["v0"][0]["ref"] == "e1"


def test_mark_repeats_falls_back_to_the_judges_name_and_ignores_what_it_cannot_resolve():
    craft, fixed = _raw("craft A", line=1), _raw("fixed B", line=2)
    pool = _pool((craft, "craft"), (fixed, "fixed"))
    staged = [dict(_raw("reworded"), id="v0"), dict(_raw("unnamed", line=3), id="v1"),
              dict(_raw("bad ref", line=4), id="v2"), dict(_raw("no id", line=5)), "not a dict", {"id": 7}]
    marks = RM.mark_repeats(staged, pool, {"v0": "e2", "v2": "e9"})
    assert marks == {"v0": (pool[1], "judge")}
    assert RM.mark_repeats(staged, [], {"v0": "e2"}) == {}
    assert RM.mark_repeats([dict(craft, id="v0")], pool, {}) == {"v0": (pool[0], "exact")}


# ---- the grouping faults ---------------------------------------------------------------------------------

def _fault_pool():
    return _pool((_raw("earlier"), "craft"))


def test_m1_a_repeat_name_that_is_not_an_earlier_finding_ref_is_refused():
    pool = _fault_pool()
    assert RM.grouping_fault([{"id": "v0"}], [], [_group("v0", ref="e9")], pool) == {
        "kind": "repeat_ref", "member_id": "e9", "index": 0}
    assert RM.grouping_fault([{"id": "v0"}], [], [_group("v0"), _group("v1", ref="e2", group_id="b")], pool) == {
        "kind": "repeat_ref", "member_id": "e2", "index": 1}
    for bad in (5, "", ["e1"]):
        fault = RM.grouping_fault([{"id": "v0"}], [], [_group("v0", ref=bad)], pool)
        assert fault["kind"] == "repeat_ref" and fault["member_id"] == bad
    assert RM.grouping_fault([{"id": "v0"}], [], [_group("v0", ref="e1")], pool) is None
    assert RM.grouping_fault([{"id": "v0"}], [], [_group("v0", ref="e1")], []) == {
        "kind": "repeat_ref", "member_id": "e1", "index": 0}   # an empty pool has no ref to name


def test_m2_a_refuted_id_in_a_group_is_set_aside_before_survivor_coverage():
    survivors, refuted = [{"id": "v0"}], [{"id": "v1"}]
    assert RM.grouping_fault(survivors, refuted, [_group("v0", "v1")], []) is None
    assert RM.grouping_fault(survivors, refuted, [_group("v0"), _group("v1", ref=None, group_id="b")], []) is None
    # without the refuted set, the same id is an unknown member of the grouping
    assert RM.grouping_fault(survivors, [], [_group("v0", "v1")], [])["kind"] == "extra"


def test_a_refuted_id_in_two_groups_is_refused():
    survivors, refuted = [{"id": "v0"}], [{"id": "v1"}]
    assert RM.grouping_fault(survivors, refuted, [_group("v0", "v1"), _group("v1", group_id="b")], []) == {
        "kind": "duplicate_member", "member_id": "v1", "index": 1}
    assert RM.grouping_fault(survivors, refuted, [_group("v0", "v1", "v1")], []) == {
        "kind": "duplicate_member", "member_id": "v1", "index": 0}


def test_a_group_of_refuted_ids_alone_is_accepted_beside_survivors_and_without_any():
    pool = _fault_pool()
    assert RM.grouping_fault([{"id": "v0"}], [{"id": "v1"}], [_group("v0"), _group("v1", ref="e1", group_id="b")],
                             pool) is None
    assert RM.grouping_fault([], [{"id": "v1"}], [_group("v1", ref="e1")], pool) is None


def test_an_omitted_survivor_is_refused():
    pool = _fault_pool()
    assert RM.grouping_fault([{"id": "v0"}, {"id": "v2"}], [{"id": "v1"}], [_group("v0", "v1")], pool) == {
        "kind": "omits", "member_id": "v2"}
    # every group is refuted-only: the survivors are all omitted
    assert RM.grouping_fault([{"id": "v0"}], [{"id": "v1"}], [_group("v1", ref="e1")], pool) == {
        "kind": "omits", "member_id": "v0"}
    assert RM.grouping_fault([{"id": "v0"}], [], [_group("v0"), _group("v0", group_id="b")], pool) == {
        "kind": "duplicate_member", "member_id": "v0", "index": 1}


def test_a_grouping_that_is_not_a_list_or_is_empty_carries_no_fault():
    assert RM.grouping_fault([{"id": "v0"}], [], None, []) is None
    assert RM.grouping_fault([{"id": "v0"}], [], "x", []) is None
    assert RM.grouping_fault([{"id": "v0"}], [], [], []) is None


# ---- strip_groups, kept_reason -----------------------------------------------------------------------------

def test_strip_groups_removes_the_ids_and_a_group_left_empty_and_loses_nothing_else():
    grouping = [_group("v0", "v1", ref="e1", group_id="a"), _group("v2", group_id="b"), _group("v3", "v4", group_id="c")]
    out = RM.strip_groups(grouping, {"v2", "v4"})
    assert out == [_group("v0", "v1", ref="e1", group_id="a"), _group("v3", group_id="c")]
    assert grouping[2]["member_ids"] == ["v3", "v4"]                # the input is not edited
    assert RM.strip_groups(grouping, set()) == grouping
    assert RM.strip_groups(grouping, {"v0", "v1", "v2", "v3", "v4"}) == []
    odd = [{"group_id": "x", "member_ids": "v9"}, "not a group"]
    assert RM.strip_groups(odd, {"v9"}) == odd
    assert RM.strip_groups(None, {"v0"}) is None


def test_kept_reason_names_the_earlier_finding_its_outcome_and_a_held_fix():
    named = {"id": "F-1", "key": "k", "outcome": "craft"}
    assert RM.kept_reason(named, None) == "repeat of F-1; keeps its earlier outcome (craft)"
    assert RM.kept_reason(dict(named, outcome="fixed"), True) == (
        "repeat of F-1; keeps its earlier outcome (fixed); the verifier found the fix still holds")
    assert RM.kept_reason(dict(named, outcome="fixed"), False) == "repeat of F-1; keeps its earlier outcome (fixed)"
    short = {"id": None, "key": "f.py@L1:title", "outcome": "ruling"}
    assert RM.kept_reason(short, None) == "repeat of f.py@L1:title; keeps its earlier outcome (ruling)"
    long_key = {"id": None, "key": "k" * 60, "outcome": "ruling"}
    assert RM.kept_reason(long_key, None) == "repeat of %s…; keeps its earlier outcome (ruling)" % ("k" * 40)
