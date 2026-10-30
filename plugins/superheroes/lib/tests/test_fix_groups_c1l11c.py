"""C1-L11c: findings that share a root cause and carry break-it tests are separate findings in one fix group.

FR-18 ("Grouped findings get one fix"): `merge_and_rank` keeps every test-carrying member as its own finding
(its own `suggestion`, its own runs) and returns `fixGroups` tying the group's resulting findings; the round
driver mints one `fixGroup` id from the member keys and stamps it on the live rows; the apply-fixes check wants
one commit that holds every member's test and a change beside all of them; each member is still audited, kept
and recorded on its own.

Edges: E-a invalid grouping · E-b all-test group · E-c lone test carrier · E-d author-justified drop · E-e
unkeyed member · E-f member queued past the cap · E-g split group · E-h different commits · E-i tests-only
commit · E-j unreadable git facts · E-k a finding in no group · E-l malformed record `fixGroup`.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/c1l11c_wo1_fix_groups.md
Bite-proof record (DoD row 2, the restore of a weakened member test): plugins/superheroes/lib/tests/bite_proofs/c1l11c_wo3_group_restore.md
"""
import hashlib
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

import audits as AU  # noqa: E402
import break_it  # noqa: E402
import review_record as REC  # noqa: E402
import review_record_session as RS  # noqa: E402
import round_driver as RD  # noqa: E402
import session_contract as SC  # noqa: E402
import test_break_it_loop as BL  # noqa: E402
import test_round_driver as TRD  # noqa: E402
import verification as V  # noqa: E402
from test_review_record import Fake as RecFake, account, finding as rec_finding, put, send  # noqa: E402

A_PATH = BL.TEST_PATH
B_PATH = "tests/test_charge_amount.py"
A_TEST = BL._TEST_FAILING
B_TEST = BL._TEST_FAILING.replace("100", "250")
A_WEAKENED = BL._TEST_WEAKENED
A_TITLE = "Break-it: a retried charge runs twice"
B_TITLE = "Break-it: a retried 250 charge runs twice"
GROUP = [{"group_id": "g0", "member_ids": ["v0", "v1"]}]


@pytest.fixture(autouse=True)
def _pinned_git(monkeypatch, tmp_path):
    """The fixture repo's commits read no user or system git configuration."""
    for name in ("home", "xdg-config"):
        (tmp_path / name).mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _group_id(*keys):
    return "fg-" + hashlib.sha256("\n".join(sorted(keys)).encode("utf-8")).hexdigest()[:12]


# ---- the end-to-end fixture: two same-root-cause break-it findings, run, grouped, fixed by one commit ----

class Grouped:
    """Two break-it findings at their own test paths, folded through the panel (both run), the verifiers and a
    native-shaped synthesis grouping (no `group_id`) that puts them in one group."""

    def __init__(self, tmp_path):
        self.world = world = BL.World(tmp_path)
        self.state = state = world.state
        state["config"]["seatMap"] = {"hostFamily": "anthropic"}
        world.fold_panel(
            BL._break_it_finding(A_TEST),
            BL._break_it_finding(B_TEST, file=B_PATH, title=B_TITLE, suggestion=BL._block(B_PATH, B_TEST)))
        verdicts = [{"id": s["id"], "verdict": "CONFIRMED", "reason": "checked", "evidence": "ran"}
                    for s in V.stage_ids(state["_toVerify"])]
        RD._fold_verifiers(state, state["config"], {
            "verdicts": verdicts, "verifierVendor": RD._nonpanel_selection(state, None, RD.P_VERIFIERS)[0]})
        ids = {f["title"]: f["id"] for f in state["_verified"]}
        grouping = [{"member_ids": [ids[A_TITLE], ids[B_TITLE]], "repeatOf": None}]
        RD._fold_synthesis(state, state["config"], {"grouping": grouping})
        rows = {f["title"]: f for f in state["findings"]}
        self.key_a, self.key_b = (SC.finding_identity_key(rows[t]) for t in (A_TITLE, B_TITLE))

    def batch_row(self, key):
        return next(r for r in self.state["_fixBatch"] if SC.finding_identity_key(r) == key)

    def commit_shared(self, a=A_TEST, b=B_TEST, code=BL._CHARGE_IDEMPOTENT):
        """One commit holding both tests and the code fix; it becomes the fix-fold head."""
        repo = self.world.repo
        BL._write(repo, BL.CHARGE_PATH, code)
        BL._write(repo, A_PATH, a)
        BL._write(repo, B_PATH, b)
        sha = BL._commit(repo, "fix the retry for both findings")
        self.state["config"][RD.FIX_FOLD_HEAD_KEY] = sha
        return sha

    def bind(self, sha, *keys):
        return {"fixes": [{"finding": k, "commit": sha} for k in keys]}

    def fold(self, artifact):
        """The apply-fixes check, then the fold with the bindings it verified."""
        state, cfg = self.state, self.state["config"]
        detail, commits = RD._apply_fixes_commit_fault(state, cfg, artifact)
        assert detail is None, detail
        RD._fold_apply_fixes(state, cfg, artifact, changed_subjects_seam=lambda *args: [],
                             panel_diff_seam=lambda config, head: (self.world.diff, None), fix_commits=commits)
        return commits

    def kept_rows(self):
        assert RD._break_it_kept_step(self.state, self.state["config"]) is False
        return {r["findingKey"]: r for rec in self.state["rounds"].values() for r in rec.get("breakItKept") or []}


@pytest.fixture
def grouped(tmp_path):
    return Grouped(tmp_path)


def test_fr18_two_break_it_findings_sharing_a_root_cause_get_one_fix_and_both_runs_are_recorded(grouped):
    state, ka, kb = grouped.state, grouped.key_a, grouped.key_b
    # both members were run at the panel: two run rows, one per finding
    assert sorted(r["findingKey"] for r in state["rounds"]["1"]["breakItRuns"]) == sorted([ka, kb])
    # after the synthesis fold: two separate findings, one fix group, its id the driver's hash of the member keys
    assert len(state["findings"]) == 2 and state["rounds"]["1"]["merges"] == []
    gid = _group_id(ka, kb)
    stamped = {SC.finding_identity_key(f): f["fixGroup"] for f in state["findings"]}
    assert stamped == {ka: {"id": gid, "members": [ka, kb]}, kb: {"id": gid, "members": [ka, kb]}}
    assert state["rounds"]["1"]["fixGroups"] == [{"id": gid, "members": [ka, kb]}]
    # the fix batch rows are copies of the live rows: both carry the group, and each its own test
    assert sorted(SC.finding_identity_key(r) for r in state["_fixBatch"]) == sorted([ka, kb])
    assert all(r["fixGroup"] == {"id": gid, "members": [ka, kb]} for r in state["_fixBatch"])
    assert {break_it.carried_block(r)[0]["path"] for r in state["_fixBatch"]} == {A_PATH, B_PATH}
    # ONE commit holds both tests and the code change; both members are bound to it and it folds
    sha = grouped.commit_shared()
    commits = grouped.fold(grouped.bind(sha, ka, kb))
    assert sorted(commits, key=lambda c: c["finding"]) == sorted(
        [{"finding": ka, "commit": sha}, {"finding": kb, "commit": sha}], key=lambda c: c["finding"])
    assert state["rounds"]["1"]["fix"]["commits"] == commits
    # the kept step checks each member's own test, at the final head
    RD._record_disposition(state, ka, "fixed", 1)
    RD._record_disposition(state, kb, "fixed", 1)
    kept = grouped.kept_rows()
    assert {k: (r["outcome"], r["path"]) for k, r in kept.items()} == {ka: ("kept", A_PATH), kb: ("kept", B_PATH)}
    # the record lists both findings, each with its own runs and the one group, bound to the shared commit
    listed = {f["title"]: f for f in RS._findings_and_merges(state)[0]}
    assert sorted(listed) == sorted([A_TITLE, B_TITLE])
    for title, path in ((A_TITLE, A_PATH), (B_TITLE, B_PATH)):
        (run,) = listed[title]["breakItRuns"]
        assert run["test"] == path
        group = listed[title]["fixGroup"]
        assert (group["id"], group["commit"]) == (gid, sha) and len(group["members"]) == 2
        assert REC._fix_group_fault(group) is None
        assert "one fix shared with 1 other finding(s) (group %s)" % gid in REC._finding_bullet(listed[title])
    # a record round-trip: every stored member reference resolves to a listed finding's stored key
    stored = {REC._key(f) for f in listed.values()}
    assert all(set(f["fixGroup"]["members"]) == stored for f in listed.values())


def test_fr18_a_weakened_member_test_charges_only_that_member(grouped):
    state, ka, kb = grouped.state, grouped.key_a, grouped.key_b
    # member A's test was changed with a reason (what the break-it-change fold writes): its block is the changed
    # test, the test role's original rides `reviewerTest`, the reason rides its run list. B is untouched.
    row = grouped.batch_row(ka)
    row["suggestion"] = BL._block(A_PATH, A_WEAKENED)
    row[RD.REVIEWER_TEST_FIELD] = A_TEST
    row[break_it.RUNS_FIELD] = list(row[break_it.RUNS_FIELD]) + [{"test": A_PATH, "changedWhy": "the cents are rounded"}]
    sha = grouped.commit_shared(a=A_WEAKENED)
    grouped.fold(grouped.bind(sha, ka, kb))
    targets = {t["id"]: t for t in RD._audit_targets(state, state["config"], {})}
    assert targets[ka]["breakIt"]["match"] == "changed-explained" and targets[ka]["breakIt"]["path"] == A_PATH
    assert targets[kb]["breakIt"]["match"] == "same" and targets[kb]["breakIt"]["path"] == B_PATH
    checks = {name: {"answer": "yes", "why": "checked"} for name in AU.CHECK_NAMES}
    results = [
        dict(id=ka, ruling="discharged", reason="the fix resolves it", checks=checks,
             testMatch={"answer": "weakened", "why": "the assertion no longer checks the charge"}),
        dict(id=kb, ruling="discharged", reason="the fix resolves it", checks=checks)]
    audited = [targets[ka], targets[kb]]
    manifest = {t["id"]: t["auditorVendor"] for t in audited if t.get("auditorVendor")}
    outcome = AU.apply_audit_results(audited, results, collection_manifest=manifest)
    assert outcome["notDischarged"] == [ka] and outcome["discharged"] == [kb]
    assert outcome["testMismatch"] == [ka]


def test_fr18_a_weakened_member_is_restored_by_the_restore_alone_and_the_other_member_is_untouched(grouped):
    # axis: DoD row 2 — the restore of a weakened test is per fix-group member — see bite-proof record c1l11c_wo3_group_restore
    state, cfg, ka, kb = grouped.state, grouped.state["config"], grouped.key_a, grouped.key_b
    row = grouped.batch_row(ka)
    row["suggestion"] = BL._block(A_PATH, A_WEAKENED)
    row[RD.REVIEWER_TEST_FIELD] = A_TEST
    row[break_it.RUNS_FIELD] = list(row[break_it.RUNS_FIELD]) + [{"test": A_PATH, "changedWhy": "the cents are rounded"}]
    sha = grouped.commit_shared(a=A_WEAKENED)
    grouped.fold(grouped.bind(sha, ka, kb))
    repo, gid = grouped.world.repo, _group_id(ka, kb)

    def committed(path):
        done = subprocess.run(["git", "-C", str(repo), "show", "HEAD:" + path], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return done.stdout

    def held_by_b():
        return RD._reviewer_test_rows(state, kb)

    # the audit of the shared fix: A's test is judged weakened, B's is unchanged
    state["_auditTargets"] = targets = RD._audit_targets(state, cfg, {})
    state["_verifyThen"], state["step"] = RD.VERIFY_THEN_POST_AUDITS, RD.P_AUDITS
    by_id = {t["id"]: t for t in targets}
    assert by_id[ka]["breakIt"]["match"] == "changed-explained" and by_id[kb]["breakIt"]["match"] == "same"
    assert all(t.get("auditorVendor") for t in targets)
    b_before = {"reviewerTest": [r.get(RD.REVIEWER_TEST_FIELD) for r in held_by_b()],
                "blocks": [break_it.carried_block(r)[0]["content"] for r in held_by_b()]}
    assert b_before["blocks"] and set(b_before["blocks"]) == {B_TEST}
    results = [dict({"id": t["id"], "ruling": "discharged", "reason": "the fix resolves it",
                     "checks": TRD.audit_checks(), "auditorVendor": t.get("auditorVendor")},
                    **TRD.audit_test_match(t, "weakened" if t["id"] == ka else "matches")) for t in targets]
    RD._fold(state, cfg, RD.P_AUDITS, {
        "results": results, "collectionManifest": {t["id"]: t.get("auditorVendor") for t in targets}})
    rnd = state["rounds"][str(state["round"])]
    assert rnd["testMismatch"] == [ka]
    # member B is discharged; only A is not
    outcome = state["_auditOutcome"]
    assert outcome["notDischarged"] == [ka] and outcome["discharged"] == [kb]

    # the restore-only step lists A alone, with the test role's bytes
    step = RD._advance(state, cfg)
    assert step["action"] == step["phase"] == RD.P_APPLY_FIXES
    assert step["payload"]["restoreOnly"] is True
    assert step["payload"]["restores"] == [
        {"findingKey": ka, "path": A_PATH, "content": A_TEST, "sha256": hashlib.sha256(A_TEST.encode("utf-8")).hexdigest()}]
    assert committed(A_PATH) == A_WEAKENED and committed(B_PATH) == B_TEST  # nothing is restored until it is committed

    # the build session writes A's restore and commits; the empty restore report folds
    BL._write(repo, A_PATH, A_TEST)
    BL._commit(repo, "restore member A's test")
    RD._fold(state, cfg, RD.P_APPLY_FIXES, {"fixes": []})
    assert committed(A_PATH) == A_TEST and committed(B_PATH) == B_TEST
    (restored,) = rnd["testRestore"]
    assert (restored["findingKey"], restored["path"], restored["source"]) == (ka, A_PATH, "reviewer")

    # B: no correction, the same reviewer test, the same carried block, on every row that holds it; still discharged
    assert state["_auditOutcome"]["discharged"] == [kb] and state["_auditOutcome"]["notDischarged"] == [ka]
    assert held_by_b()
    for held in held_by_b():
        assert RD.TEST_CORRECTION_FIELD not in held
    assert [r.get(RD.REVIEWER_TEST_FIELD) for r in held_by_b()][:len(b_before["reviewerTest"])] == b_before["reviewerTest"]
    assert {break_it.carried_block(r)[0]["content"] for r in held_by_b()} == {B_TEST}
    # A carries the test role's bytes now, and both live rows keep the one fix group
    assert {break_it.carried_block(r)[0]["content"] for r in RD._reviewer_test_rows(state, ka)} == {A_TEST}
    live = {SC.finding_identity_key(f): f for f in state["findings"]}
    assert live[ka]["fixGroup"] == live[kb]["fixGroup"] == {"id": gid, "members": [ka, kb]}


def test_a_shared_fix_discharges_one_member_the_other_is_repaired_alone_and_the_kept_step_checks_both(grouped):
    state, ka, kb = grouped.state, grouped.key_a, grouped.key_b
    sha = grouped.commit_shared()
    grouped.fold(grouped.bind(sha, ka, kb))
    # the audit discharged A and rejected B: A is recorded fixed, B is requeued beside A's row
    RD._record_disposition(state, ka, "fixed", 1)
    requeued = [dict(r) for r in state["fixBatch"]]
    assert RD._queue_fix_batch(state, state["config"], requeued) == "queued"
    assert [SC.finding_identity_key(r) for r in state["_fixBatch"]] == [kb]  # A is excluded as discharged
    assert state["_fixBatch"][0]["fixGroup"]["members"] == [ka, kb]
    # B's lone repair: a source-only commit, no split, no shared-commit demand
    BL._write(grouped.world.repo, BL.CHARGE_PATH, BL._CHARGE_IDEMPOTENT + "# idempotent\n")
    repair = BL._commit(grouped.world.repo, "repair the retry for B")
    state["config"][RD.FIX_FOLD_HEAD_KEY] = repair
    commits = grouped.fold(grouped.bind(repair, kb))
    assert commits == [{"finding": kb, "commit": repair}]
    RD._record_disposition(state, kb, "fixed", 2)
    kept = grouped.kept_rows()
    assert {k: (r["outcome"], r["path"]) for k, r in kept.items()} == {ka: ("kept", A_PATH), kb: ("kept", B_PATH)}


# ---- unit fixtures: group members in a bare state --------------------------------------------------------

def _member(i, severity="Important", with_test=True, title=None):
    path, content = ((A_PATH, A_TEST), (B_PATH, B_TEST))[i]
    title = title or "member %d" % i
    if with_test:
        row = BL._break_it_finding(content, file=path, title=title, severity=severity,
                                   suggestion=BL._block(path, content))
    else:
        row = {"title": title, "file": path, "line": 1, "severity": severity, "consequence": "c", "body": "b"}
    return dict(row, id="v%d" % i)


def _unit(severities=("Important", "Important"), tests=(True, True), titles=(None, None), stamp=True):
    state = RD.new_state({"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "claude"})
    RD._set_findings(state, [_member(i, s, t, titles[i]) for i, (s, t) in enumerate(zip(severities, tests))])
    keys = [RD._finding_identity_key(r) for r in state["findings"]]
    if stamp:
        RD._stamp_fix_groups(state, GROUP, state["findings"])
    state["_fixBatch"] = [dict(r) for r in state["findings"]]
    return SimpleNamespace(state=state, ka=keys[0], kb=keys[1], gid=_group_id(*keys), rows=state["findings"])


def _facts(paths, a=A_TEST, b=B_TEST, **over):
    return dict({"reachable": True, "inStep": False, "paths": list(paths),
                 "files": {A_PATH: a.encode() if a is not None else None,
                           B_PATH: b.encode() if b is not None else None}}, **over)


def _check(u, bindings, commits, unfixed=()):
    """`_apply_fixes_commit_fault` over the slice with `bindings` ``[(finding key, commit)]`` and git facts
    `commits` ``{commit: facts}``."""
    artifact = {"fixes": [{"finding": k, "commit": c} for k, c in bindings]}
    if unfixed:
        artifact["unfixed"] = [{"finding": k, "reason": "left"} for k in unfixed]
    return RD._apply_fixes_commit_fault(
        u.state, u.state["config"], artifact,
        commit_seam=lambda named, paths: {c: f for c, f in commits.items() if c in named})


BOTH_TESTS_AND_CODE = [BL.CHARGE_PATH, A_PATH, B_PATH]


# ---- item 1: merge_and_rank ----------------------------------------------------------------------------------

def test_merge_and_rank_ties_only_groups_with_a_test_carrier_and_two_results():
    def plain(fid):
        return {"id": fid, "file": "f%s.py" % fid, "line": 1, "title": "t%s" % fid, "severity": "Important"}

    carrier = dict(plain("v0"), taxonomy=break_it.TAXONOMY, suggestion=BL._block(A_PATH, A_TEST))
    out = V.merge_and_rank([plain("v1"), plain("v2"), carrier], [{"member_ids": ["v1", "v2", "v0"]}])
    assert out["fixGroups"] == [{"group_id": "g0", "member_ids": ["v0", "v2"]}] and len(out["merges"]) == 1
    # a group of plain findings merges into one fix and ties nothing; a lone carrier ties nothing
    assert V.merge_and_rank([plain("v1"), plain("v2")], [{"member_ids": ["v1", "v2"]}])["fixGroups"] == []
    assert V.merge_and_rank([carrier, plain("v1")], [{"member_ids": ["v0"]}, {"member_ids": ["v1"]}])["fixGroups"] == []
    # a given group id is kept; an invalid grouping (a group omitting a survivor) ties nothing
    given = V.merge_and_rank([carrier, plain("v1")], [{"group_id": "root", "member_ids": ["v0", "v1"]}])
    assert given["fixGroups"] == [{"group_id": "root", "member_ids": ["v0", "v1"]}]
    assert V.merge_and_rank([carrier, plain("v1")], [{"member_ids": ["v0"]}])["fixGroups"] == []


# ---- item 2: the driver stamps the group with its own id --------------------------------------------------------

def test_the_fix_group_id_is_the_drivers_hash_of_the_member_keys_whatever_the_grouping_names():
    u = _unit()
    assert u.state["rounds"]["1"]["fixGroups"] == [{"id": u.gid, "members": [u.ka, u.kb]}]
    assert u.gid.startswith("fg-") and len(u.gid) == len("fg-") + 12
    assert all(r["fixGroup"]["id"] == u.gid for r in u.rows)
    # the same members give the same id; other members give another
    assert _unit().gid == u.gid
    other = _unit(titles=("member 0", "another member"))
    assert other.gid != u.gid
    # a grouping that names its own group id changes nothing
    named = _unit(stamp=False)
    RD._stamp_fix_groups(named.state, [{"group_id": "mine", "member_ids": ["v0", "v1"]}], named.state["findings"])
    assert named.state["findings"][0]["fixGroup"]["id"] == u.gid


def test_a_member_the_author_filter_dropped_or_a_group_with_no_test_carrier_stamps_nothing():
    u = _unit(stamp=False)
    RD._stamp_fix_groups(u.state, GROUP, u.state["findings"][:1])  # the drop left one member
    assert not any("fixGroup" in r for r in u.rows) and u.state["rounds"]["1"]["fixGroups"] == []
    plain = _unit(tests=(False, False), stamp=False)
    RD._stamp_fix_groups(plain.state, GROUP, plain.state["findings"])
    assert not any("fixGroup" in r for r in plain.rows) and plain.state["rounds"]["1"]["fixGroups"] == []


def test_a_member_with_no_key_leaves_its_group_to_per_member_fixes_and_records_the_decision(monkeypatch):
    u = _unit(stamp=False)
    real = RD._finding_identity_key
    monkeypatch.setattr(RD, "_finding_identity_key",
                        lambda f: None if isinstance(f, dict) and f.get("id") == "v1" else real(f))
    RD._stamp_fix_groups(u.state, GROUP, u.state["findings"])
    assert not any("fixGroup" in r for r in u.rows) and u.state["rounds"]["1"]["fixGroups"] == []
    assert [d["kind"] for d in u.state["decisions"] if d["kind"] == "fix-group-unkeyed"] == ["fix-group-unkeyed"]


def test_a_stamp_from_an_earlier_round_is_removed_from_a_row_in_no_group_now():
    u = _unit()
    assert all("fixGroup" in r for r in u.rows)
    RD._stamp_fix_groups(u.state, [], u.state["findings"])
    assert not any("fixGroup" in r for r in u.rows) and u.state["rounds"]["1"]["fixGroups"] == []


# ---- item 3a: the batch is closed over fix groups ----------------------------------------------------------------

def test_an_important_and_a_minor_member_both_reach_the_apply_fixes_check_and_both_get_audit_targets():
    u = _unit(severities=("Important", "Minor"))
    state = u.state
    RD._after_findings_settled(state, state["config"])
    assert state["step"] == RD.P_APPLY_FIXES
    assert sorted(RD._finding_identity_key(r) for r in state["_fixBatch"]) == sorted([u.ka, u.kb])
    assert all(r["fixGroup"]["id"] == u.gid for r in state["_fixBatch"])  # the fix-batch rows carry the group
    detail, commits = _check(u, [(u.ka, "c1"), (u.kb, "c1")], {"c1": _facts(BOTH_TESTS_AND_CODE)})
    assert detail is None and [c["finding"] for c in commits] == [u.ka, u.kb]
    state["fixBatch"] = list(state["_fixBatch"])
    assert sorted(t["id"] for t in RD._audit_targets(state, state["config"], {})) == sorted([u.ka, u.kb])


def test_a_member_the_owner_choice_hold_took_out_of_the_batch_is_not_pulled_back():
    u = _unit()
    u.rows[1]["tradeoff"] = True  # a product-choice blocker: held for the owner, not fixed
    RD._after_findings_settled(u.state, u.state["config"])
    assert u.state["ownerChoiceHeld"] == [u.kb]
    assert [RD._finding_identity_key(r) for r in u.state["_fixBatch"]] == [u.ka]


# ---- item 3: a slice keeps a fix group whole -----------------------------------------------------------------------

def test_a_fix_group_member_queued_past_the_cap_is_pulled_into_the_slice():
    u = _unit()
    other = {"id": "x", "title": "other", "file": "x.py", "line": 1, "severity": "Important"}
    RD._set_findings(u.state, list(u.state["findings"]) + [other])
    live = {f["title"]: dict(f) for f in u.state["findings"]}
    u.state["config"]["fixBatchCap"] = 1
    rows = [live["member 0"], live["other"], live["member 1"]]
    assert RD._queue_fix_batch(u.state, u.state["config"], rows) == "queued"
    assert [r["title"] for r in u.state["_fixBatch"]] == ["member 0", "member 1"]
    assert [r["title"] for r in u.state["_fixQueue"]] == ["other"]


# ---- item 4: the apply-fixes check -------------------------------------------------------------------------------

def test_one_commit_bound_to_every_member_with_every_test_and_a_change_beside_them_folds():
    u = _unit()
    detail, commits = _check(u, [(u.ka, "c1"), (u.kb, "c1")], {"c1": _facts(BOTH_TESTS_AND_CODE)})
    assert detail is None
    assert commits == [{"finding": u.ka, "commit": "c1"}, {"finding": u.kb, "commit": "c1"}]


def test_members_bound_to_different_commits_or_a_commit_that_fails_one_member_refuse_no_shared_commit():
    u = _unit()
    token = "fix-group-no-shared-commit:%s" % u.gid
    passing = _facts(BOTH_TESTS_AND_CODE)
    # each commit passes both members' checks, but no one commit is bound to both
    assert _check(u, [(u.ka, "c1"), (u.kb, "c2")], {"c1": passing, "c2": passing}) == (token, [])
    # one commit bound to both passes A's check but not B's (B's bytes differ)
    assert _check(u, [(u.ka, "c1"), (u.kb, "c1")], {"c1": _facts(BOTH_TESTS_AND_CODE, b="other\n")}) == (token, [])


@pytest.mark.parametrize("tests", [(True, True), (True, False), (False, True)])
def test_members_bound_to_different_commits_refuse_whether_or_not_each_carries_a_test(tests):
    u = _unit(tests=tests)
    passing = _facts(BOTH_TESTS_AND_CODE)
    assert _check(u, [(u.ka, "c1"), (u.kb, "c2")], {"c1": passing, "c2": passing}) == (
        "fix-group-no-shared-commit:%s" % u.gid, [])


@pytest.mark.parametrize("tests", [(True, False), (False, True)])
def test_a_plain_member_bound_to_head_naming_the_shared_commit_folds(tests):
    u = _unit(tests=tests)
    s = "a" * 40
    carrier, plain = (u.ka, u.kb) if tests[0] else (u.kb, u.ka)
    facts = dict(_facts(BOTH_TESTS_AND_CODE), sha=s)
    detail, commits = _check(u, [(carrier, s), (plain, "HEAD")], {s: facts, "HEAD": facts})
    assert detail is None
    assert {c["finding"] for c in commits} == {carrier}
    assert all(c["commit"] == s for c in commits)


def test_a_commit_that_holds_every_members_test_and_nothing_else_refuses_no_shared_commit():
    u = _unit()
    tests_only = _facts([A_PATH, B_PATH])
    assert _check(u, [(u.ka, "c1"), (u.kb, "c1")], {"c1": tests_only}) == (
        "fix-group-no-shared-commit:%s" % u.gid, [])


def test_the_exempt_paths_widen_only_the_changes_beside_the_test_check():
    u = _unit()
    block, _kind = break_it.carried_block(u.state["_fixBatch"][0])
    facts = _facts([A_PATH, B_PATH])
    assert RD._fix_commit_test_fault(facts, block) is None  # today: the other test file counts as a change
    assert RD._fix_commit_test_fault(facts, block, exempt_paths=(B_PATH,)) == RD.FIX_NO_FIX_CHANGE
    assert RD._fix_commit_test_fault(facts, block, exempt_paths=(B_PATH, "x.py")) == RD.FIX_NO_FIX_CHANGE
    assert RD._fix_commit_test_fault(_facts(BOTH_TESTS_AND_CODE), block, exempt_paths=(B_PATH,)) is None


def test_members_listed_partly_unfixed_refuse_a_split_group_and_all_unfixed_owes_nothing():
    u = _unit()
    passing = _facts(BOTH_TESTS_AND_CODE)
    assert _check(u, [(u.ka, "c1")], {"c1": passing}, unfixed=[u.kb]) == ("fix-group-split:%s" % u.gid, [])
    assert _check(u, [(u.kb, "c1")], {"c1": passing}, unfixed=[u.ka]) == ("fix-group-split:%s" % u.gid, [])
    assert _check(u, [], {}, unfixed=[u.ka, u.kb]) == (None, [])


def test_a_group_member_with_no_binding_still_owes_one_and_unreadable_git_facts_refuse_first():
    u = _unit()
    assert _check(u, [(u.ka, "c1")], {"c1": _facts(BOTH_TESTS_AND_CODE)}) == (
        "%s:%s:%s" % (RD.FIX_WITHOUT_TEST, u.kb, RD.FIX_NO_BINDING), [])
    detail, commits = RD._apply_fixes_commit_fault(
        u.state, u.state["config"], {"fixes": [{"finding": u.ka, "commit": "c1"}, {"finding": u.kb, "commit": "c1"}]},
        commit_seam=lambda named, paths: None)
    assert (detail, commits) == ("%s:%s:%s" % (RD.FIX_WITHOUT_TEST, u.ka, RD.FIX_UNVERIFIABLE), [])


def test_a_finding_in_no_group_takes_the_single_finding_path_unchanged():
    u = _unit(stamp=False)
    u.state["_fixBatch"] = [dict(r) for r in u.rows]  # no `fixGroup` on any row
    # each member's own commit passes its own check: no common commit is asked for
    detail, commits = _check(u, [(u.ka, "c1"), (u.kb, "c2")],
                             {"c1": _facts([BL.CHARGE_PATH, A_PATH]), "c2": _facts([BL.CHARGE_PATH, B_PATH])})
    assert detail is None and commits == [{"finding": u.ka, "commit": "c1"}, {"finding": u.kb, "commit": "c2"}]
    # and a tests-only commit is a no-fix-change refusal naming the finding, not a group token
    assert _check(u, [(u.ka, "c1"), (u.kb, "c1")], {"c1": _facts([A_PATH])})[0] == (
        "%s:%s:%s" % (RD.FIX_WITHOUT_TEST, u.ka, RD.FIX_NO_FIX_CHANGE))


# ---- item 4c: the test role's original test rides a requeue --------------------------------------------------------

def test_a_requeued_member_judged_weakened_is_compared_on_its_next_audit_to_the_test_roles_original(tmp_path):
    world = BL.World(tmp_path)
    world.fix(test_content=A_WEAKENED)
    member = BL._break_it_finding(A_WEAKENED)  # its block is the build session's changed test
    member[RD.REVIEWER_TEST_FIELD] = A_TEST
    member[break_it.RUNS_FIELD] = [{"test": A_PATH, "changedWhy": "the cents are rounded"}]
    (first,) = RD._audit_targets({"fixBatch": [member]}, world.config, {})
    assert first["breakIt"]["match"] == "changed-explained" and first[RD.REVIEWER_TEST_FIELD] == A_TEST
    # the audit judged it weakened: the target row is what is queued again
    (again,) = RD._audit_targets({"fixBatch": [first]}, world.config, {})
    assert again["breakIt"]["match"] != "same"
    assert (again["breakIt"]["reviewerTest"], again["breakIt"]["committedTest"]) == (A_TEST, A_WEAKENED)


# ---- item 5: audit targets name the group -------------------------------------------------------------------------

def test_each_audit_target_and_batch_sibling_of_a_member_names_the_other_members():
    u = _unit()
    plain = {"id": "x", "title": "other", "file": "x.py", "line": 1, "severity": "Important"}
    RD._set_findings(u.state, list(u.state["findings"]) + [plain])
    u.state["fixBatch"] = [dict(f) for f in u.state["findings"]]
    targets = {t["id"]: t for t in RD._audit_targets(u.state, u.state["config"], {})}
    assert targets[u.ka]["fixGroup"] == {"id": u.gid, "members": [u.kb]}
    assert targets[u.kb]["fixGroup"] == {"id": u.gid, "members": [u.ka]}
    siblings = {s["id"]: s for s in targets[u.ka]["batchFindings"]}
    assert siblings[u.kb]["fixGroup"] == {"id": u.gid, "members": [u.ka]}
    other = next(k for k in targets if k not in (u.ka, u.kb))
    assert "fixGroup" not in targets[other] and "fixGroup" not in siblings.get(other, {})
    # each member keeps its own breakIt block
    assert targets[u.ka]["breakIt"]["path"] == A_PATH and targets[u.kb]["breakIt"]["path"] == B_PATH


# ---- item 6: the review record -----------------------------------------------------------------------------------

BAD_GROUPS = [
    ("", "not a group"),
    (".id", {"members": ["a", "b"]}),
    (".id", {"id": " ", "members": ["a", "b"]}),
    (".members", {"id": "g", "members": ["a"]}),
    (".members", {"id": "g", "members": "ab"}),
    (".members", {"id": "g", "members": ["a", " "]}),
    (".commit", {"id": "g", "members": ["a", "b"], "commit": ""}),
    (".commit", {"id": "g", "members": ["a", "b"], "commit": 7}),
]


def test_the_record_writer_refuses_a_malformed_fix_group_naming_the_finding_and_the_part(tmp_path):
    for suffix, bad in BAD_GROUPS:
        fake = RecFake()
        out = REC.write(put(tmp_path, account(findings=[rec_finding(fixGroup=bad)])), str(tmp_path), fake.readers())
        assert (out["ok"], out.get("reason")) == (False, "review-account-invalid"), (suffix, out)
        assert out["detail"].startswith("findings[0].fixGroup" + suffix), (suffix, out)
        assert fake.comments == []


def test_the_record_writer_takes_a_fix_group_with_or_without_a_commit_and_the_bullet_names_the_group(tmp_path):
    for group in ({"id": "fg-1", "members": ["a", "b"]}, {"id": "fg-1", "members": ["a", "b", "c"], "commit": "abc1234"}):
        assert REC._fix_group_fault(group) is None
        send(tmp_path, RecFake(), findings=[rec_finding(fixGroup=group)])
    bullet = REC._finding_bullet(rec_finding(fixGroup={"id": "fg-1", "members": ["a", "b", "c"]}))
    assert bullet.endswith(" · one fix shared with 2 other finding(s) (group fg-1)")
    assert "one fix shared" not in REC._finding_bullet(rec_finding())


# ---- item 3c: every path that composes a batch closes it over fix groups --------------------------------------

def _rule_guidance(state, key):
    """An owner `guidance` decision on `key`, written the way the `rule` verb writes one."""
    state["rulingSeqCounter"] = state.get("rulingSeqCounter", 0) + 1
    state.setdefault("rulingsLog", []).append({
        "seq": state["rulingSeqCounter"], "round": state.get("round", 1), "phase": "dispatch-fixer",
        "attempt": None, "id": key, "findingKey": key, "ruling": "guidance", "reason": "owner call",
        "by": "owner", "guidance": "keep the retry behaviour"})


def test_an_owner_ruling_that_adds_a_group_member_brings_its_sibling_into_the_batch():
    u = _unit(severities=("Minor", "Minor"))  # neither is blocking: only the ruling queues the first
    _rule_guidance(u.state, u.ka)
    RD._after_findings_settled(u.state, u.state["config"])
    assert u.state["step"] == RD.P_APPLY_FIXES
    assert sorted(RD._finding_identity_key(r) for r in u.state["_fixBatch"]) == sorted([u.ka, u.kb])


def test_a_guidance_restored_member_offered_beside_no_sibling_brings_its_sibling_into_the_batch():
    u = _unit(severities=("Minor", "Minor"))
    _rule_guidance(u.state, u.ka)
    live = {RD._finding_identity_key(r): dict(r) for r in u.state["findings"]}
    # the restored member is already offered (the ruling is satisfied by that row), so the resolver adds nothing
    assert RD._queue_fix_batch(u.state, u.state["config"], [live[u.ka]]) == "queued"
    assert sorted(RD._finding_identity_key(r) for r in u.state["_fixBatch"]) == sorted([u.ka, u.kb])


def test_a_delta_settle_offering_the_important_member_brings_its_minor_sibling_into_the_batch():
    u = _unit(severities=("Important", "Minor"))
    state = u.state
    state["_settleDelta"] = True
    RD._after_findings_settled(state, state["config"])
    assert state["step"] == RD.P_APPLY_FIXES
    assert sorted(RD._finding_identity_key(r) for r in state["_fixBatch"]) == sorted([u.ka, u.kb])


def test_the_delta_settle_closure_still_leaves_an_owner_held_sibling_out():
    u = _unit(severities=("Important", "Minor"))
    u.rows[1]["tradeoff"] = True
    u.state["ownerChoiceHeld"] = [u.kb]
    u.state["_settleDelta"] = True
    RD._after_findings_settled(u.state, u.state["config"])
    assert [RD._finding_identity_key(r) for r in u.state["_fixBatch"]] == [u.ka]


def test_a_tradeoff_minor_sibling_pulled_by_the_closure_is_held_for_the_owner_not_admitted():
    u = _unit(severities=("Important", "Minor"))
    u.rows[1]["tradeoff"] = True  # a product choice that rides only as a group sibling, never as a blocker
    RD._after_findings_settled(u.state, u.state["config"])
    assert u.state["ownerChoiceHeld"] == [u.kb]
    assert [RD._finding_identity_key(r) for r in u.state["_fixBatch"]] == [u.ka]


def test_a_tradeoff_sibling_pulled_by_the_queue_closure_is_held_for_the_owner_not_admitted():
    u = _unit(severities=("Important", "Minor"))
    u.rows[1]["tradeoff"] = True
    live = {RD._finding_identity_key(r): dict(r) for r in u.state["findings"]}
    assert RD._queue_fix_batch(u.state, u.state["config"], [live[u.ka]]) == "queued"
    assert u.state["ownerChoiceHeld"] == [u.kb]
    assert [RD._finding_identity_key(r) for r in u.state["_fixBatch"]] == [u.ka]
