"""C1-L10b: a break-it test the fix auditor lists in `testMismatch` is put back, and the test reviewer gets one correction.

The invariant: after any audit fold that lists a target in `testMismatch`, no path of the review loop, terminal or not,
leaves the round with a committed break-it test at that target's path that is not the test reviewer's version (the
original, or the one correction); and the test reviewer is offered at most one correction per finding over the whole
session.

Pins, each at the place the rule is enforced:

T1  an auditor-flagged weakened test: the next step is a restore-only `apply-fixes` step carrying the reviewer's bytes,
    and the committed test at head is the reviewer's once the step folds (git read, a real temp repository);
T2  the restore runs before every terminal path: the round at the cap, the extra audit round, and a correction seat that
    fails authentication or is never answered (the library path, `run_loop`);
T3  the test reviewer is offered exactly one correction per finding over the session;
T4  a landed correction: its bytes are committed, become `reviewerTest` and the carried block on every row that holds the
    finding, and a later audit reads `same` against them;
T5  the restore check at both entry points, `submit` and `run_loop`, and the shared function itself;
T6  a finding still open at the cap is handed back like any other;
T7  the correction order and the sidecar that carries its inputs;
T8  no mismatch, no restore step;
T9  the break-it kept check after a restore or a landed correction expects the restored bytes, from the finding's
    carried block, and is unchanged for a finding with no restore or a later run.

Bite-proof record: c1l10b_wo2_test_restore
"""
import copy
import hashlib
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

import break_it  # noqa: E402
import decision_kinds  # noqa: E402
import round_phases as RP  # noqa: E402
import test_apply_fixes_c1l9a as H  # noqa: E402
import test_break_it_loop as BL  # noqa: E402
import test_c1l10_audit_checks as C1  # noqa: E402
import test_round_driver as TRD  # noqa: E402
import test_round_driver_advance as TA  # noqa: E402
from test_round_driver_advance import adapters  # noqa: E402,F401  (a fixture)

RD = TRD.RD

TEST_PATH = C1.TEST_PATH
ROLE_TEST = C1.ROLE_TEST
FIXED_TEST = C1.FIXED_TEST
WEAKER_TEST = C1.WEAKER_TEST
WHY = C1.WHY
CORRECTED_TEST = "def test_charge():\n    import charge_mod\n    assert charge(2) == 2\n    assert charge(3) == 3\n"
SECOND_CHANGE = "def test_charge():\n    import charge_mod\n    assert charge(2) >= 0\n"
_ID = C1._ID


@pytest.fixture(autouse=True)
def _pinned_git_config(monkeypatch, tmp_path):
    for name in ("home", "xdg-config"):
        (tmp_path / name).mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout


def _commit(repo, message):
    _git(repo, "add", "-A")
    _git(repo, *_ID, "commit", "-q", "--allow-empty", "-m", message)
    return _git(repo, "rev-parse", "HEAD").strip()


def _decisions(state):
    return [d["kind"] for d in state["decisions"]]


class World:
    """A repository whose head carries the build session's explained change of a break-it test, and a round-N
    state whose fix batch holds the finding with the test reviewer's version kept as `reviewerTest`."""

    def __init__(self, tmp_path, cap=None, committed=FIXED_TEST, round_no=2, seat_map=True):
        self.root = tmp_path / "repo"
        self.root.mkdir(parents=True)
        _git(self.root, "init", "-q")
        (self.root / "README.md").write_text("fixture\n")
        self.base = _commit(self.root, "base")
        self.write(TEST_PATH, committed)
        self.fix_head = _commit(self.root, "fix")
        self.cfg = {"repoRoot": str(self.root), "baseRef": self.base, "fixerVendor": "claude",
                    "vendors": ["claude", "codex"]}
        if seat_map:  # the seat map proves a live reviewer cell outside the makers' families
            self.cfg["seatMap"] = TRD._assertable_seat_map(["claude", "codex"], "claude")
        if cap:
            self.cfg["maxRounds"] = cap
        self.finding = C1._finding(content=FIXED_TEST, reviewer_test=ROLE_TEST, changed_why=WHY)
        self.key = RD._finding_key_of(self.finding)
        self.state = RD.new_state(self.cfg)
        self.state["round"] = round_no
        self.state["rounds"] = {str(round_no - 1): {"fixFoldHead": self.fix_head}}
        self.state["fixBatch"] = [self.finding]
        self.state["findings"] = [copy.deepcopy(self.finding)]
        self.state["_auditTargets"] = RD._audit_targets(self.state, self.cfg, {})
        # a real delta round carries its fixes' own diff (set by the post-fix fold); empty here, so the scoped finder is skipped
        self.state["_newSurface"] = {}
        self.state["_fixDeltaDiff"] = ""
        self.state["_verifyThen"] = RD.VERIFY_THEN_POST_AUDITS
        self.state["step"] = RD.P_AUDITS

    def write(self, rel, text):
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if text is None:
            if target.exists():
                target.unlink()
        else:
            target.write_text(text)

    def head(self):
        return _git(self.root, "rev-parse", "HEAD").strip()

    def committed(self):
        done = subprocess.run(["git", "-C", str(self.root), "show", "HEAD:" + TEST_PATH],
                              capture_output=True, text=True)
        return done.stdout if done.returncode == 0 else None

    def audit_artifact(self, answer="weakened"):
        targets = self.state["_auditTargets"]
        results = [dict({"id": t["id"], "ruling": "discharged", "reason": "the fix resolves it",
                         "checks": TRD.audit_checks(), "auditorVendor": t.get("auditorVendor")},
                        **TRD.audit_test_match(t, answer)) for t in targets]
        return {"results": results,
                "collectionManifest": {t["id"]: t.get("auditorVendor") for t in targets}}

    def fold(self, phase, artifact, **kw):
        RD._fold(self.state, self.cfg, phase, artifact, **kw)

    def audit(self, answer="weakened"):
        self.fold(RD.P_AUDITS, self.audit_artifact(answer))

    def step(self):
        return RD._advance(self.state, self.cfg)

    def restore(self, content=ROLE_TEST, message="restore the test"):
        self.write(TEST_PATH, content)
        _commit(self.root, message)
        self.fold(RD.P_APPLY_FIXES, {"fixes": []})

    def verify(self, head=None):
        artifact = {"result": "pass"}
        if head is not None:
            artifact["headSha"] = head
        self.fold(RD.P_VERIFY, artifact, verified_head_resolution=(None, None))

    def correct(self, content):
        """The test reviewer's correction: a result for the item, then the second restore-only step."""
        step = self.step()
        assert step["action"] == RD.P_SECOND_TEST and step["payload"]["correction"] is True, step
        self.fold(RD.P_SECOND_TEST, {"findings": [{"id": self.key, "suggestion": C1._block_text(content)}]})
        assert self.state["step"] == RD.P_APPLY_FIXES
        self.restore(content, "commit the corrected test")

    def next_round(self, content, change=True):
        """The settle copies the open target rows into the next fix batch (`_settle_delta`); the build session
        then commits ``content`` as its fix, and the next round's audit targets are built over it."""
        outcome = self.state["_auditOutcome"]
        copies = [dict(t) for t in self.state["_auditTargets"] if t["id"] in outcome["notDischarged"]]
        batch = RD._union_open_blockers([], copies)
        if change:  # `break-it-change` rewrote the block once more
            for row in batch:
                RD._rewrite_break_it_copy(row, C1._block_text(content), C1._record(), "a second change")
        else:
            content = break_it.carried_block(batch[0])[0]["content"]
        self.write(TEST_PATH, content)
        head = _commit(self.root, "fix again")
        self.state["rounds"][str(self.state["round"])]["fixFoldHead"] = head
        self.state["round"] += 1
        self.state["fixBatch"] = batch
        self.state["_auditTargets"] = RD._audit_targets(self.state, self.cfg, {})
        self.state["_verifyThen"] = RD.VERIFY_THEN_POST_AUDITS
        self.state["step"] = RD.P_AUDITS
        return batch

    def run_loop(self, seams):
        """`run_loop` over this state: the library layer's whole loop from the audits on."""
        original = RD.new_state
        RD.new_state = lambda config=None: self.state
        try:
            return TRD._run_loop_capturing_state(seams, self.cfg)
        finally:
            RD.new_state = original


# --- T1 ------------------------------------------------------------------------------------------------------------

def test_t1_a_weakened_test_is_restored_by_a_restore_only_step_before_anything_else(tmp_path):
    # axis: E1 — the audit fold that lists a mismatch enters the restore instead of its continuation
    w = World(tmp_path)
    assert w.committed() == FIXED_TEST
    w.audit()
    assert w.state["rounds"]["2"]["testMismatch"] == [w.key]
    step = w.step()
    assert step["action"] == step["phase"] == RD.P_APPLY_FIXES
    assert step["payload"]["restoreOnly"] is True and "batch" not in step["payload"]
    assert step["payload"]["restores"] == [{"findingKey": w.key, "path": TEST_PATH, "content": ROLE_TEST,
                                            "sha256": _sha(ROLE_TEST)}]
    assert step["payload"]["startHead"] == w.fix_head
    assert w.committed() == FIXED_TEST  # nothing is restored until the build session commits
    w.restore()
    assert w.committed() == ROLE_TEST
    rec = w.state["rounds"]["2"]
    assert rec["testRestore"] == [{"findingKey": w.key, "path": TEST_PATH, "source": "reviewer",
                                   "restoredHead": w.head()}]
    assert "break-it-test-mismatch" in _decisions(w.state) and "break-it-test-restored" in _decisions(w.state)
    # a restore is no fix: not recorded as one, not in the fix batch, not credited
    assert "fix" not in rec and "fixBatches" not in rec
    assert w.state["fixBatch"] == [w.finding]
    assert RD.TEST_RESTORE_FIELD not in w.state and "_fixStepHead" not in w.state


def test_t1_the_finding_stays_not_discharged_and_the_restore_is_not_a_discharge(tmp_path):
    w = World(tmp_path)
    w.audit()
    w.restore()
    outcome = w.state["_auditOutcome"]
    assert outcome["notDischarged"] == [w.key] and outcome["discharged"] == []
    assert w.state["rounds"]["2"]["audits"][0]["ruling"] == "not-discharged"


def test_t1_the_restore_step_re_emits_from_driver_state_after_a_resume(tmp_path):
    # edge 13: the pending restore lives in driver state, not in the report or the pending step
    w = World(tmp_path)
    w.audit()
    first = w.step()
    resumed = json.loads(json.dumps(w.state))
    assert RD._advance(resumed, w.cfg) == first
    session = tmp_path / "saved"
    session.mkdir()
    RD.save_state(str(session), w.state)
    ok, loaded = RD.load_state(str(session))
    assert ok and RD._advance(loaded, w.cfg) == first


# --- T2 ------------------------------------------------------------------------------------------------------------

def test_t2_the_extra_audit_round_restores_then_verifies_then_hands_back_open(tmp_path):
    # edge 12: restore, correction, verify, then the extra round's own settle
    w = World(tmp_path, cap=2, round_no=3)
    w.state["extraAudit"] = {"round": 3}
    w.audit()
    assert w.state["step"] == RD.P_APPLY_FIXES
    w.restore()
    assert w.committed() == ROLE_TEST and w.state["step"] == RD.P_SECOND_TEST
    w.fold(RD.P_SECOND_TEST, {"findings": []})
    assert w.state["step"] == RD.P_VERIFY and w.state["_verifyThen"] == RD.VERIFY_THEN_POST_AUDITS
    assert w.step()["payload"]["restoredHead"] == w.head()
    w.verify(head=w.head())
    assert w.state["terminal"] == "handed-back" and w.state["decisions"][-1]["kind"] == "extra-audit-open"
    assert w.committed() == ROLE_TEST
    kinds = _decisions(w.state)
    assert kinds.index("break-it-test-restored") < kinds.index("extra-audit-open")


def test_t2_a_correction_seat_that_fails_authentication_parks_with_the_reviewers_test_already_committed(tmp_path):
    # the library path: `run_loop` parks the unauthenticated seat; the restore had landed before the seat was offered
    w = World(tmp_path)
    seen = []

    def fix_step(batch, rnd, payload):
        assert payload["restoreOnly"] is True
        seen.append(payload["restores"][0]["content"])
        w.write(TEST_PATH, payload["restores"][0]["content"])
        _commit(w.root, "restore")
        return {"fixes": []}

    def reviewer(dim, tier, rnd, ctx):
        assert dim == "second-test" and ctx["correction"] is True
        assert w.committed() == ROLE_TEST  # the offer is made after the restore
        return {"findings": [], "vendor": "claude"}  # not the vendor the seat was ordered on

    def auditor(targets, rnd):
        return w.audit_artifact()["results"]

    _receipt, state = w.run_loop(TRD._seams(auditor=auditor, fix_step=fix_step, reviewer=reviewer))
    assert seen == [ROLE_TEST]
    assert state["terminal"] == "cannot-certify"
    assert state["certification"]["reason"].startswith("nonpanel-finder-unauthenticated:%s" % RD.P_SECOND_TEST)
    assert w.committed() == ROLE_TEST
    assert "testCorrection" not in state["fixBatch"][0] or state["fixBatch"][0]["testCorrection"]["used"] is False


def test_t2_a_correction_never_answered_still_leaves_the_reviewers_test_committed(tmp_path):
    # durable path and hand path both stop at the pending correction step; the restore is already committed
    w = World(tmp_path)
    w.audit()
    w.restore()
    step = w.step()
    assert step["action"] == RD.P_SECOND_TEST and step["payload"]["correction"] is True
    assert w.committed() == ROLE_TEST
    again = w.step()
    assert again == step  # the same step until a result folds
    assert RD.TEST_CORRECTION_FIELD not in w.state["fixBatch"][0]  # offered but not yet used


def test_t2_a_round_at_the_cap_restores_then_hands_back_the_open_finding(tmp_path):
    # edge 11 / T6: the settle hands it back like any other open finding
    w = World(tmp_path, cap=2)
    order = []

    def fix_step(batch, rnd, payload):
        if payload.get("restoreOnly"):
            order.append("restore")
            w.write(TEST_PATH, payload["restores"][0]["content"])
            _commit(w.root, "restore")
            return {"fixes": []}
        order.append("fix")
        block = break_it.carried_block(batch[0])[0]
        order.append(block["content"])
        w.write(TEST_PATH, block["content"])
        w.write("src/charge.py", "def charge(n):\n    return n\n")
        sha = _commit(w.root, "fix")
        return {"fixes": [{"finding": w.key, "commit": sha}]}

    def reviewer(dim, tier, rnd, ctx):
        return {"findings": [], "vendor": "codex"}

    def verify(command, rnd):
        order.append("verify")
        # axis: the in-process verify seam reports the head the run ran at, which the restore gate counts — see bite-proof record c1l11f_wo_e_verify_after_restore
        return {"result": "pass", "headSha": _git(w.root, "rev-parse", "HEAD").strip()}

    seams = TRD._seams(auditor=lambda targets, rnd: w.audit_artifact()["results"], fix_step=fix_step,
                       reviewer=reviewer, verify_runner=verify)
    seams["panel_diff"] = lambda config, head: (TRD.DIFF, None)
    _receipt, state = w.run_loop(seams)
    assert state["terminal"] == "handed-back", (state["terminal"], state.get("certification"))
    assert state["decisions"][-1]["kind"] == "round-cap"
    # the restore ran before the settle's fix, and the fix recommits the test reviewer's version
    assert order[0] == "restore" and order[1] == "verify"
    assert order[2:4] == ["fix", ROLE_TEST] or order[2:4] == ["fix", CORRECTED_TEST]
    # T6: the finding is still open in the record
    assert state["rounds"]["2"]["audits"][0]["ruling"] == "not-discharged"
    ledger, _fault = RD._disposition_ledger_by_key(state)
    assert (ledger.get(w.key) or {}).get("disposition") != "fixed"


def test_t2_a_round_at_the_cap_restores_then_a_bare_pass_with_no_head_halts_with_certification_withheld(tmp_path):
    # the in-process leg passes no head: a pass with no run head and no fold head after a restore never advances
    w = World(tmp_path, cap=2)

    def fix_step(batch, rnd, payload):
        assert payload.get("restoreOnly"), "the run must halt at the verify gate, before any settle fix"
        w.write(TEST_PATH, payload["restores"][0]["content"])
        _commit(w.root, "restore")
        return {"fixes": []}

    def reviewer(dim, tier, rnd, ctx):
        return {"findings": [], "vendor": "codex"}

    # axis: a bare "pass" from the in-process verify seam carries no head, so the gate after a restore halts — see bite-proof record c1l11f_wo_e_verify_after_restore
    seams = TRD._seams(auditor=lambda targets, rnd: w.audit_artifact()["results"], fix_step=fix_step,
                       reviewer=reviewer, verify_runner=lambda command, rnd: "pass")
    seams["panel_diff"] = lambda config, head: (TRD.DIFF, None)
    _receipt, state = w.run_loop(seams)
    assert state["terminal"] == "halted", (state["terminal"], state.get("certification"))
    assert state["certification"]["shape"] is None and "unknown" in state["certification"]["reason"]
    assert state["decisions"][-1]["kind"] == "verify-unresolved"
    assert "round-cap" not in _decisions(state)


def test_t2_a_retry_pass_whose_head_moved_while_running_halts_through_the_run_loop_callback(tmp_path):
    # axis: the seam's after-head reaches the fold, so a passing retry that straddled a head change is not called unchanged code — see bite-proof record c1l11f_wo_e_verify_after_restore
    w = World(tmp_path, cap=2)
    moved_to = "f" * 40
    runs = []

    def fix_step(batch, rnd, payload):
        assert payload.get("restoreOnly"), "the run must halt at the verify gate, before any settle fix"
        w.write(TEST_PATH, payload["restores"][0]["content"])
        _commit(w.root, "restore")
        return {"fixes": []}

    def verify(command, rnd):
        head = _git(w.root, "rev-parse", "HEAD").strip()
        runs.append(head)
        if len(runs) == 1:
            return {"result": "fail", "headSha": head}
        return {"result": "pass", "headSha": head, "headShaAfter": moved_to}

    seams = TRD._seams(auditor=lambda targets, rnd: w.audit_artifact()["results"], fix_step=fix_step,
                       reviewer=lambda dim, tier, rnd, ctx: {"findings": [], "vendor": "codex"},
                       verify_runner=verify)
    seams["panel_diff"] = lambda config, head: (TRD.DIFF, None)
    _receipt, state = w.run_loop(seams)
    assert len(runs) == 2
    assert state["terminal"] == "halted", (state["terminal"], state.get("certification"))
    assert state["decisions"][-1]["kind"] == "verify-rerun-head-moved"
    (entry,) = [e for e in state["rounds"]["2"].get("rerunChecks", []) if e.get("check") == "verify"]
    assert entry["decision"] == "head-moved" and entry["heads"] == [runs[1], moved_to]


def test_t2_a_first_pass_whose_head_moved_while_running_halts_through_the_run_loop_callback(tmp_path):
    # axis: the seam's after-head reaches the fold, so a first passing run after a restore that straddled a head change never advances — see bite-proof record c1l11f_wo_e_verify_after_restore
    w = World(tmp_path, cap=2)
    moved_to = "f" * 40
    runs = []

    def fix_step(batch, rnd, payload):
        assert payload.get("restoreOnly"), "the run must halt at the verify gate, before any settle fix"
        w.write(TEST_PATH, payload["restores"][0]["content"])
        _commit(w.root, "restore")
        return {"fixes": []}

    def verify(command, rnd):
        head = _git(w.root, "rev-parse", "HEAD").strip()
        runs.append(head)
        return {"result": "pass", "headSha": head, "headShaAfter": moved_to}

    seams = TRD._seams(auditor=lambda targets, rnd: w.audit_artifact()["results"], fix_step=fix_step,
                       reviewer=lambda dim, tier, rnd, ctx: {"findings": [], "vendor": "codex"},
                       verify_runner=verify)
    seams["panel_diff"] = lambda config, head: (TRD.DIFF, None)
    _receipt, state = w.run_loop(seams)
    assert len(runs) == 1
    assert state["terminal"] == "halted", (state["terminal"], state.get("certification"))
    assert state["certification"]["shape"] is None
    assert state["decisions"][-1]["kind"] == "verify-unresolved"
    assert runs[0] in state["decisions"][-1]["detail"] and moved_to in state["decisions"][-1]["detail"]
    assert "round-cap" not in _decisions(state)


# --- T3 ------------------------------------------------------------------------------------------------------------

def test_t3_the_test_reviewer_gets_exactly_one_correction_over_the_session(tmp_path):
    # axis: E3 — the once-only guard reads `testCorrection.used` off the finding
    w = World(tmp_path)
    w.audit()
    w.restore()
    assert w.state["step"] == RD.P_SECOND_TEST
    w.correct(CORRECTED_TEST)
    assert w.committed() == CORRECTED_TEST
    assert w.state["step"] == RD.P_VERIFY
    # a later round: the build session changed the test again and the auditor judged it weakened again
    w.next_round(SECOND_CHANGE)
    (target,) = w.state["_auditTargets"]
    assert target["breakIt"]["match"] == "changed-explained" and target["breakIt"]["reviewerTest"] == CORRECTED_TEST
    assert target["testCorrection"] == {"round": 2, "used": True, "outcome": "corrected"}
    w.audit()
    step = w.step()
    assert step["payload"]["restoreOnly"] is True
    assert step["payload"]["restores"][0]["content"] == CORRECTED_TEST
    w.restore(CORRECTED_TEST, "restore the corrected test")
    assert w.committed() == CORRECTED_TEST
    assert w.state["step"] == RD.P_VERIFY, "a second correction was offered"
    kinds = _decisions(w.state)
    assert kinds.count("break-it-correction-offered") == 1 and kinds.count("break-it-test-restored") == 2


def test_t3_a_correction_that_returned_nothing_is_used_all_the_same(tmp_path):
    w = World(tmp_path)
    w.audit()
    w.restore()
    w.fold(RD.P_SECOND_TEST, {"findings": []})
    assert w.state["fixBatch"][0]["testCorrection"] == {"round": 2, "used": True, "outcome": "none"}
    assert w.state["step"] == RD.P_VERIFY and "break-it-correction-none" in _decisions(w.state)
    assert w.state["rounds"]["2"]["testCorrection"] == [
        {"findingKey": w.key, "outcome": "none", "reason": "no-result"}]
    w.next_round(SECOND_CHANGE)
    w.audit()
    w.restore()
    assert w.state["step"] == RD.P_VERIFY


def test_t3_a_seat_that_cannot_be_seated_offers_nothing_and_uses_nothing(tmp_path):
    # edge 7: the correction is not offered, so it is not used; a later round may offer it
    w = World(tmp_path, seat_map=False)  # no seat map proves a live cell outside the makers' families
    w.audit()
    w.restore()
    assert w.state["step"] == RD.P_VERIFY
    assert "break-it-correction-unseatable" in _decisions(w.state)
    assert w.state["rounds"]["2"]["testCorrection"] == [{"findingKey": w.key, "outcome": "unseatable"}]
    assert RD.TEST_CORRECTION_FIELD not in w.state["fixBatch"][0]
    assert RD.TEST_CORRECTION_FIELD not in w.state["findings"][0]
    assert w.committed() == ROLE_TEST


@pytest.mark.parametrize("result,reason", [
    pytest.param(lambda w: {"findings": [{"id": w.key, "suggestion": "no block here"}]}, "no-block", id="no-block"),
    pytest.param(lambda w: {"findings": [{"id": w.key, "suggestion": C1._block_text(CORRECTED_TEST).replace(
        TEST_PATH, "tests/elsewhere.py")}]}, "other-path", id="another-path"),
    pytest.param(lambda w: {"findings": [{"id": w.key, "suggestion": C1._block_text(CORRECTED_TEST),
                                          break_it.REDACTED_FIELD: True}]}, "redacted", id="redacted"),
    pytest.param(lambda w: {"findings": [{"id": w.key, "suggestion": C1._block_text(CORRECTED_TEST)}] * 2},
                 "duplicate-id", id="duplicate-id"),
    pytest.param(lambda w: {"findings": [{"id": w.key, "suggestion": C1._block_text(ROLE_TEST)}]}, "unchanged",
                 id="unchanged"),
])
def test_t3_a_result_that_is_not_a_usable_block_is_no_correction(tmp_path, result, reason):
    # edge 8
    w = World(tmp_path)
    w.audit()
    w.restore()
    w.fold(RD.P_SECOND_TEST, result(w))
    assert w.state["rounds"]["2"]["testCorrection"] == [{"findingKey": w.key, "outcome": "none", "reason": reason}]
    assert w.state["step"] == RD.P_VERIFY and w.committed() == ROLE_TEST


def test_t3_a_missing_test_is_restored_and_no_correction_is_offered(tmp_path):
    # edge 4: weakened is judged only on a changed, explained test; a test git cannot read is restored like the rest
    w = World(tmp_path, committed=None)
    w.audit()
    assert w.state["_auditTargets"][0]["breakIt"]["match"] == "missing"
    assert w.step()["payload"]["restores"][0]["content"] == ROLE_TEST
    w.restore()
    assert w.committed() == ROLE_TEST
    assert w.state["step"] == RD.P_VERIFY and "break-it-correction-offered" not in _decisions(w.state)


# --- T4 ------------------------------------------------------------------------------------------------------------

def test_t4_a_landed_correction_is_committed_and_becomes_the_reviewers_version_everywhere(tmp_path):
    # axis: E4 — the carried-block sync rewrites `suggestion` on every row that holds the finding
    w = World(tmp_path)
    w.audit()
    w.restore()
    w.correct(CORRECTED_TEST)
    assert w.committed() == CORRECTED_TEST
    rec = w.state["rounds"]["2"]
    assert [e["source"] for e in rec["testRestore"]] == ["reviewer", "corrected"]
    assert rec["testRestore"][1]["restoredHead"] == w.head()
    assert rec["testCorrection"] == [{"findingKey": w.key, "outcome": "corrected"}]
    assert "break-it-correction-landed" in _decisions(w.state)
    for row in (w.state["fixBatch"][0], w.state["findings"][0], w.state["_auditTargets"][0]):
        assert row[RD.REVIEWER_TEST_FIELD] == CORRECTED_TEST
        block = break_it.carried_block(row)[0]
        assert block["content"] == CORRECTED_TEST and block["path"] == TEST_PATH and block["run"] == C1.RUN
        assert row[RD.TEST_CORRECTION_FIELD] == {"round": 2, "used": True, "outcome": "corrected"}
    # the next fix commits the block's bytes, and the next audit reads them as the test reviewer's own
    w.next_round(None, change=False)
    (target,) = w.state["_auditTargets"]
    assert target["breakIt"]["match"] == "same", target["breakIt"]
    assert target["breakIt"]["reviewerTest"] == CORRECTED_TEST == target["breakIt"]["committedTest"]


def test_t4_the_sync_writes_the_ledger_row_and_the_live_finding_and_leaves_other_findings_alone():
    state = RD.new_state({})
    mine = C1._finding(content=FIXED_TEST, reviewer_test=ROLE_TEST, changed_why=WHY)
    other = dict(C1._finding(), title="Another defect")
    key = RD._finding_key_of(mine)
    ledger = RD._ensure_disposition_ledger_for_write(state)
    ledger.extend([copy.deepcopy(mine), copy.deepcopy(other)])
    state["findings"] = [copy.deepcopy(mine), copy.deepcopy(other)]
    RD._sync_reviewer_test(state, key, CORRECTED_TEST, correction={"round": 2, "used": True, "outcome": "corrected"})
    for row in (ledger[0], state["findings"][0]):
        assert row[RD.REVIEWER_TEST_FIELD] == CORRECTED_TEST
        assert break_it.carried_block(row)[0]["content"] == CORRECTED_TEST
        assert row[RD.TEST_CORRECTION_FIELD]["used"] is True
    for row in (ledger[1], state["findings"][1]):
        assert break_it.carried_block(row)[0]["content"] == ROLE_TEST
        assert RD.REVIEWER_TEST_FIELD not in row and RD.TEST_CORRECTION_FIELD not in row
    # no ledger row for the key: the ledger is left as it was
    bare = RD.new_state({})
    RD._sync_reviewer_test(bare, key, CORRECTED_TEST)
    assert RD.new_state({}).get(RD.session_contract.DISPOSITION_LEDGER_KEY) == bare.get(
        RD.session_contract.DISPOSITION_LEDGER_KEY)


def test_t4_equal_fix_batch_and_audit_target_rows_are_both_rewritten():
    state = RD.new_state({})
    mine = C1._finding(content=FIXED_TEST, reviewer_test=ROLE_TEST, changed_why=WHY)
    key = RD._finding_key_of(mine)
    batch_row, target_row = copy.deepcopy(mine), copy.deepcopy(mine)
    assert batch_row == target_row and batch_row is not target_row
    state["fixBatch"] = [batch_row]
    state["_auditTargets"] = [target_row]
    RD._sync_reviewer_test(state, key, CORRECTED_TEST, correction={"round": 2, "used": True, "outcome": "corrected"})
    for row in (batch_row, target_row):
        assert row[RD.REVIEWER_TEST_FIELD] == CORRECTED_TEST
        assert break_it.carried_block(row)[0]["content"] == CORRECTED_TEST
        assert row[RD.TEST_CORRECTION_FIELD]["used"] is True


def test_t4_an_audit_target_row_carries_the_reviewers_version_and_the_correction(tmp_path):
    w = World(tmp_path)
    w.finding[RD.TEST_CORRECTION_FIELD] = {"round": 1, "used": True, "outcome": "none"}
    (target,) = RD._audit_targets(w.state, w.cfg, {})
    assert target[RD.REVIEWER_TEST_FIELD] == ROLE_TEST
    assert target[RD.TEST_CORRECTION_FIELD] == {"round": 1, "used": True, "outcome": "none"}
    assert break_it.carried_block(target)[0]["content"] == FIXED_TEST


# --- T5 ------------------------------------------------------------------------------------------------------------

def _restore_state(path=TEST_PATH, content=ROLE_TEST, step_head="a" * 40):
    return {RD.TEST_RESTORE_FIELD: {"stage": "restore", "items": [
        {"findingKey": "k", "path": path, "content": content, "sha256": _sha(content)}]},
        "_fixStepHead": step_head}


def _facts(files=None, **entry):
    body = {"sha": "b" * 40, "reachable": True, "inStep": False, "paths": [TEST_PATH],
            "files": {TEST_PATH: ROLE_TEST.encode("utf-8")} if files is None else files}
    body.update(entry)
    return lambda commits, paths: {RD.RESTORE_COMMIT: body}


def test_t5_the_shared_check_accepts_a_test_only_commit_with_the_reviewers_bytes():
    state = _restore_state()
    assert RD._restore_commit_fault(state, {}, {"fixes": []}, commit_seam=_facts()) == (None, "b" * 40)


@pytest.mark.parametrize("seam,fault", [
    pytest.param(_facts(files={TEST_PATH: WEAKER_TEST.encode()}), "%s:test-bytes-differ" % TEST_PATH,
                 id="wrong-bytes"),
    pytest.param(_facts(files={TEST_PATH: None}), "%s:test-missing" % TEST_PATH, id="missing-path"),
    pytest.param(_facts(files={}), "%s:test-missing" % TEST_PATH, id="path-not-read"),
    pytest.param(_facts(inStep=True), "commit-not-in-step", id="no-new-commit"),
    pytest.param(_facts(inStep=None), "commit-not-in-step", id="in-step-unknown"),
    pytest.param(_facts(reachable=False), "commit-unknown", id="unreachable"),
    pytest.param(lambda commits, paths: None, "unverifiable", id="git-unreadable"),
    pytest.param(lambda commits, paths: {}, "unverifiable", id="head-unknown"),
])
def test_t5_the_shared_check_refuses_every_way_a_restore_can_fail(seam, fault):
    # axis: E2 — the byte comparison is the restore's own check
    detail, sha = RD._restore_commit_fault(_restore_state(), {}, {"fixes": []}, commit_seam=seam)
    assert (detail, sha) == (fault, None)


@pytest.mark.parametrize("report", [
    pytest.param({"fixes": [], "unfixed": [{"finding": "k", "why": "x"}]}, id="unfixed"),
    pytest.param({"fixes": [{"finding": "k", "commit": "abc"}]}, id="binding"),
    pytest.param({"fixes": [{"finding": "k"}]}, id="malformed-binding"),
])
def test_t5_a_restore_report_takes_no_unfixed_and_no_fix_binding(report):
    detail, sha = RD._restore_commit_fault(_restore_state(), {}, report, commit_seam=_facts())
    assert detail.startswith(RD.RESTORE_REPORT_SHAPE) and sha is None


def test_t5_with_no_restore_pending_the_check_has_nothing_to_judge():
    assert RD._restore_commit_fault({}, {}, {"fixes": []}) == (RD.RESTORE_NOT_PENDING, None)


def _drive_to_restore(tmp_path):
    """The hand path (`next` / `submit`) to a pending restore: the fix commit is good, a later commit alters the test, so
    the audit at the fix-fold head reads a changed, unexplained test."""
    fx = H.Fixture(tmp_path)
    fx.reach()
    key = fx.keys()[0]
    good = fx.commit_fix()
    H.write(fx.repo, H.TEST_PATH, H._TEST_OTHER_BYTES)
    H.commit(fx.repo, "alter the test")
    assert fx.submit(H._bound(key, good))["ok"] is True
    for _ in range(20):
        n = RD.cmd_next(str(fx.session))
        assert n["ok"] and n["action"] != RD.P_TERMINAL, n
        if n["phase"] == RD.P_APPLY_FIXES:
            return fx, key, n
        art = fx.respond(n["phase"], n["payload"], n["round"])
        done = RD.cmd_submit(str(fx.session), n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert done["ok"], done
    raise AssertionError("never reached the restore step")


def _committed_at(repo, path):
    done = subprocess.run(["git", "-C", str(repo), "show", "HEAD:" + path], capture_output=True, text=True)
    return done.stdout if done.returncode == 0 else None


def test_t1_by_hand_the_next_step_after_a_flagged_test_is_the_restore_and_a_resume_re_emits_it(tmp_path):
    fx, key, n = _drive_to_restore(tmp_path)
    assert n["payload"]["restoreOnly"] is True and "batch" not in n["payload"]
    (restore,) = n["payload"]["restores"]
    assert restore == {"findingKey": key, "path": H.TEST_PATH, "content": H._TEST_FAILING,
                       "sha256": _sha(H._TEST_FAILING)}
    assert n["payload"]["landingPath"] and "fixBatchPath" not in n["payload"] and "guidancePath" not in n["payload"]
    assert _committed_at(fx.repo, H.TEST_PATH) == H._TEST_OTHER_BYTES
    # a session saved at the step and resumed: `next` re-emits the same step from driver state
    assert RD.cmd_next(str(fx.session))["payload"] == n["payload"]
    state = fx.state()
    state["pending"] = None
    RD.save_state(str(fx.session), state)
    again = RD.cmd_next(str(fx.session))
    assert again["phase"] == RD.P_APPLY_FIXES and again["payload"]["restores"] == n["payload"]["restores"]
    # the build session writes the file byte for byte and commits; the fold accepts a test-only commit
    H.write(fx.repo, H.TEST_PATH, H._TEST_FAILING)
    H.commit(fx.repo, "restore the test")
    out = RD.cmd_submit(str(fx.session), again["phase"], again["attempt"], again["expectedStateHash"],
                        {"fixes": []})
    assert out["ok"] is True and out["nextStep"] == RD.P_VERIFY, out
    assert _committed_at(fx.repo, H.TEST_PATH) == H._TEST_FAILING
    assert fx.state()["rounds"][str(fx.state()["round"])]["testRestore"][0]["source"] == "reviewer"


@pytest.mark.parametrize("make,fault", [
    pytest.param(lambda fx: H.write(fx.repo, H.TEST_PATH, H._TEST_OTHER_BYTES + "# not the reviewer's\n"),
                 "test-bytes-differ", id="wrong-bytes"),
    pytest.param(lambda fx: (fx.repo / H.TEST_PATH).unlink(), "test-missing", id="missing-path"),
    pytest.param(lambda fx: None, "commit-not-in-step", id="no-new-commit"),
])
def test_t5_through_submit_a_restore_that_failed_hands_the_pr_back(tmp_path, make, fault):
    fx, key, n = _drive_to_restore(tmp_path)
    make(fx)
    if fault != "commit-not-in-step":
        H.commit(fx.repo, "a restore that is not one")
    out = RD.cmd_submit(str(fx.session), n["phase"], n["attempt"], n["expectedStateHash"], {"fixes": []})
    assert out["ok"] is True and out["nextStep"] == RD.P_TERMINAL, out
    state = fx.state()
    assert state["terminal"] == "handed-back"
    last = state["decisions"][-1]
    assert last["kind"] == "break-it-restore-failed" and H.TEST_PATH in last["detail"] and fault in last["detail"]


@pytest.mark.parametrize("report", [
    pytest.param(lambda key: {"fixes": [], "unfixed": [{"finding": key, "why": "x"}]}, id="unfixed"),
    pytest.param(lambda key: {"fixes": [{"finding": key, "commit": "abc1234"}]}, id="binding"),
])
def test_t5_through_submit_a_report_that_carries_unfixed_or_a_binding_is_refused_and_the_step_stays_pending(
        tmp_path, report):
    fx, key, n = _drive_to_restore(tmp_path)
    before = TRD._state_bytes(str(fx.session))
    out = RD.cmd_submit(str(fx.session), n["phase"], n["attempt"], n["expectedStateHash"], report(key))
    assert out["ok"] is False and out["reason"] == "fold-refused" and out["detail"].startswith(RD.RESTORE_REPORT_SHAPE)
    assert TRD._state_bytes(str(fx.session)) == before
    assert RD.cmd_next(str(fx.session))["payload"] == n["payload"]


def test_t5_through_run_loop_a_restore_with_other_bytes_hands_the_pr_back_and_a_good_one_goes_on(tmp_path):
    for content, handed_back in ((WEAKER_TEST, True), (ROLE_TEST, False)):
        w = World(tmp_path / ("a" if handed_back else "b"))

        def fix_step(batch, rnd, payload, w=w, content=content):
            if payload.get("restoreOnly"):
                w.write(TEST_PATH, content)
                _commit(w.root, "restore")
                return {"fixes": []}
            return {"fixes": []}

        seams = TRD._seams(auditor=lambda targets, rnd, w=w: w.audit_artifact()["results"], fix_step=fix_step,
                           reviewer=lambda dim, tier, rnd, ctx: {"findings": [], "vendor": "codex"})
        _receipt, state = w.run_loop(seams)
        kinds = _decisions(state)
        if handed_back:
            assert state["terminal"] == "handed-back" and state["decisions"][-1]["kind"] == "break-it-restore-failed"
            assert "test-bytes-differ" in state["decisions"][-1]["detail"] and TEST_PATH in state["decisions"][-1]["detail"]
        else:
            assert "break-it-test-restored" in kinds and "break-it-restore-failed" not in kinds


def test_t5_a_mismatched_target_that_cannot_be_restored_hands_back_before_any_step(tmp_path):
    # edge 3: no parseable block, or a reviewer version that is not a string
    for breakage in ("no-block", "no-version"):
        w = World(tmp_path / breakage)
        target = w.state["_auditTargets"][0]
        if breakage == "no-block":
            target["breakIt"]["path"] = None
        else:
            target["breakIt"]["reviewerTest"] = None
        target["breakIt"]["match"] = "missing"
        w.audit()
        assert w.state["terminal"] == "handed-back"
        assert w.state["decisions"][-1]["kind"] == "break-it-restore-failed"
        assert w.key in w.state["decisions"][-1]["detail"]
        assert RD.TEST_RESTORE_FIELD not in w.state


def test_t5_several_mismatched_targets_share_one_restore_step_and_one_correction_step(tmp_path):
    # edge 2
    w = World(tmp_path)
    second = copy.deepcopy(w.finding)
    second["title"] = "Another retry bug"
    second["suggestion"] = C1._block_text(FIXED_TEST).replace(TEST_PATH, "tests/test_other.py")
    second[RD.REVIEWER_TEST_FIELD] = ROLE_TEST
    w.write("tests/test_other.py", FIXED_TEST)
    head = _commit(w.root, "second test")
    w.state["rounds"]["1"]["fixFoldHead"] = head
    w.state["fixBatch"] = [w.finding, second]
    w.state["_auditTargets"] = RD._audit_targets(w.state, w.cfg, {})
    w.audit()
    step = w.step()
    assert sorted(r["path"] for r in step["payload"]["restores"]) == ["tests/test_charge.py", "tests/test_other.py"]
    w.write(TEST_PATH, ROLE_TEST)
    w.write("tests/test_other.py", ROLE_TEST)
    _commit(w.root, "restore both")
    w.fold(RD.P_APPLY_FIXES, {"fixes": []})
    step = w.step()
    assert step["action"] == RD.P_SECOND_TEST and len(step["payload"]["findings"]) == 2


def test_t5_a_rider_is_no_part_of_the_restore(tmp_path):
    # edge 5: a rider carries no test of its own; `_fold_audits` excludes it from `notDischarged` and the restore alike
    w = World(tmp_path)
    w.state["_auditTargets"][0]["spawnedFrom"] = "some-parent"
    w.audit()
    assert RD.TEST_RESTORE_FIELD not in w.state and w.state["step"] != RD.P_APPLY_FIXES


# --- T6 / T8 -------------------------------------------------------------------------------------------------------

def test_t8_with_no_mismatch_the_audit_continues_exactly_as_before(tmp_path):
    # the committed test is the test role's own: nothing is listed and no restore step is made
    w = World(tmp_path, committed=ROLE_TEST)
    w.state["fixBatch"] = [C1._finding()]
    w.state["_auditTargets"] = RD._audit_targets(w.state, w.cfg, {})
    assert w.state["_auditTargets"][0]["breakIt"]["match"] == "same"
    w.audit()
    assert "testMismatch" not in w.state["rounds"]["2"]
    assert RD.TEST_RESTORE_FIELD not in w.state
    assert w.state["step"] == RD.P_VERIFY  # the post-audits gate, as the old continuation did
    assert "break-it-test-restored" not in _decisions(w.state)


def test_t6_the_decision_kinds_are_registered_and_the_restore_failure_is_a_handback_cause():
    for kind in ("break-it-test-restored", "break-it-correction-offered", "break-it-correction-none",
                 "break-it-correction-landed", "break-it-correction-unseatable", "break-it-restore-failed"):
        assert kind in decision_kinds.DECISION_KINDS, kind
    assert decision_kinds.map_terminal_cause("handed-back", "break-it-restore-failed") == {
        "kind": "non-loop", "reason": "open-findings"}
    assert decision_kinds.map_terminal_cause("handed-back", "break-it-restore-failed") == \
        decision_kinds.map_terminal_cause("handed-back", "fix-surface-unknown")


# --- T7 ------------------------------------------------------------------------------------------------------------

def test_t7_the_correction_payload_and_its_sidecar_carry_the_inputs(tmp_path):
    w = World(tmp_path)
    w.audit()
    w.restore()
    step = w.step()
    assert step["payload"]["correction"] is True
    (item,) = step["payload"]["findings"]
    assert item["id"] == w.key and item["path"] == TEST_PATH
    assert item["reviewerTest"] == ROLE_TEST and item["committedTest"] == FIXED_TEST
    assert item["changedWhy"] == WHY and item["why"] == "compared the committed test with the test role's"
    session = tmp_path / "sidecar"
    session.mkdir()
    writes = RD._order_sidecar_writes(str(session), 2, RD.P_SECOND_TEST, ["second-test"], step["payload"])
    ((path, content),) = writes
    assert os.path.basename(path) == RD.ORDER_SIDECAR_CORRECTION_FILE
    assert json.loads(content)["findings"][0]["reviewerTest"] == ROLE_TEST
    # the ordinary second-test payload still writes the held sidecar
    held = RD._order_sidecar_writes(str(session), 2, RD.P_SECOND_TEST, ["second-test"], {"findings": [{"id": "x"}]})
    assert os.path.basename(held[0][0]) == RD.ORDER_SIDECAR_HELD_FILE


def test_t7_the_correction_template_says_what_is_asked():
    path = os.path.join(_LIB, "..", "rubric", "orders", "dispatch-second-test-correction.md")
    text = open(path, encoding="utf-8").read()
    for clause in ("you wrote", "changed it and gave a reason", "judged that the change weakened",
                   "put back and committed again", "same `path`", "with no block in `suggestion`",
                   "{{CORRECTION_INPUTS_PATH}}", "{{BREAK_IT_GRAMMAR_BLOCK}}", "{{OUTPUT_CHANNEL_BLOCK}}"):
        assert " ".join(clause.split()) in " ".join(text.split()), clause
    assert "passed\non the unfixed code" not in text  # the ordinary order's premise is not this one's


def test_t7_the_rendered_correction_order_carries_the_correction_instructions():
    import round_orders as RO
    import test_round_orders as TRO
    ph = {k: v for k, v in TRO._second_test_placeholders().items() if k != "HELD_FINDINGS_PATH"}
    ph["CORRECTION_INPUTS_PATH"] = os.path.join(TRO._SESSION, "round-2", "second-test-correction.json")
    ctx = TRO._base_context(host_seat=True, landing_path=os.path.join(
        TRO._SESSION, "round-2", "landing", "dispatch-second-test", "second-test.a0.payload.json"),
        placeholders=ph, payload={"correction": True, "findings": []})
    text, reason = RO.render_order(RP.P_SECOND_TEST, "seat", ctx)
    assert reason is None, reason
    assert "judged that the change weakened" in text and ph["CORRECTION_INPUTS_PATH"] in text


@pytest.mark.parametrize("payload,phase,expected", [
    pytest.param({"correction": True}, RP.P_SECOND_TEST, "dispatch-second-test-correction", id="true"),
    pytest.param({"correction": "true"}, RP.P_SECOND_TEST, RP.P_SECOND_TEST, id="string-true"),
    pytest.param({"correction": 1}, RP.P_SECOND_TEST, RP.P_SECOND_TEST, id="one"),
    pytest.param({"correction": None}, RP.P_SECOND_TEST, RP.P_SECOND_TEST, id="none"),
    pytest.param({"correction": False}, RP.P_SECOND_TEST, RP.P_SECOND_TEST, id="false"),
    pytest.param({}, RP.P_SECOND_TEST, RP.P_SECOND_TEST, id="absent"),
    pytest.param("not a payload", RP.P_SECOND_TEST, RP.P_SECOND_TEST, id="payload-not-a-dict"),
    pytest.param({"correction": True}, RP.P_AUDITS, RP.P_AUDITS, id="another-phase"),
])
def test_t7_only_the_second_test_phase_with_a_correction_of_exactly_true_picks_the_correction_template(
        payload, phase, expected):
    # edge 1: a `correction` that is not exactly `true` is the ordinary template; no other phase has a second one
    import round_orders as RO
    assert RO._template_name(phase, {"payload": payload}) == expected


def test_t7_a_correction_that_is_not_exactly_true_renders_the_ordinary_order():
    import round_orders as RO
    import test_round_orders as TRO
    ctx = TRO._GOLDEN_CONTEXTS[RP.P_SECOND_TEST]()
    ctx["payload"] = dict(ctx.get("payload") or {}, correction="true")
    text, reason = RO.render_order(RP.P_SECOND_TEST, "seat", ctx)
    assert reason is None, reason
    assert "judged that the change weakened" not in text and "Write one more test for each finding" in text


def test_t7_a_missing_correction_template_refuses_and_never_falls_back_to_the_ordinary_one(monkeypatch):
    # edge 2
    import round_orders as RO
    import test_round_orders as TRO
    real = RO.order_template_path
    monkeypatch.setattr(RO, "order_template_path", lambda name, root=None: real(name + "-gone")
                        if name == RO.SECOND_TEST_CORRECTION_TEMPLATE else real(name, root))
    ph = {k: v for k, v in TRO._second_test_placeholders().items() if k != "HELD_FINDINGS_PATH"}
    ph["CORRECTION_INPUTS_PATH"] = os.path.join(TRO._SESSION, "round-2", "second-test-correction.json")
    ctx = TRO._base_context(host_seat=True, placeholders=ph, payload={"correction": True, "findings": []})
    text, reason = RO.render_order(RP.P_SECOND_TEST, "seat", ctx)
    assert text is None and reason == "template-missing:dispatch-second-test-correction"


def test_t7_the_correction_step_is_rendered_into_the_correction_order_on_the_cli_path(tmp_path):
    # the hand path: `next` emits the correction step's order; before the selection it refused `order-render-refused`
    w = World(tmp_path)
    w.audit()
    w.restore()
    session = tmp_path / "cli-session"
    session.mkdir()
    (session / RD.round_records.META_FILE).write_text(json.dumps({"repoRoot": str(w.root), "headSha": w.fix_head}))
    w.state["reviewedDiff"] = TRD.DIFF
    RD.save_state(str(session), w.state)
    n = RD.cmd_next(str(session))
    assert n["ok"] is True and n["phase"] == RD.P_SECOND_TEST and n["payload"]["correction"] is True, n
    (order,) = [os.path.join(d, f) for d, _dirs, files in os.walk(str(session)) for f in files
                if f.endswith(".md") and RD.P_SECOND_TEST in d]
    text = open(order, encoding="utf-8").read()
    assert "judged that the change weakened" in text and RD.ORDER_SIDECAR_CORRECTION_FILE in text


def test_t7_the_ordinary_second_test_order_is_unchanged():
    import test_round_orders as TRO
    rendered = TRO._render_golden(RP.P_SECOND_TEST)
    golden = os.path.join(TRO._GOLDEN_DIR, RP.P_SECOND_TEST + ".txt")
    expected = open(golden, encoding="utf-8").read()
    assert TRO._normalize_golden_machine_paths(rendered) == TRO._normalize_golden_machine_paths(expected)
    assert "judged that the change weakened" not in rendered


# --- T9 ------------------------------------------------------------------------------------------------------------

class KeptWorld:
    """`test_break_it_loop`'s world past a fix: the test role's failing test was run in round 1, the build session then
    changed it (`break-it-change`, run again) and fixed the code, and the finding is `fixed` on the ledger. The latest
    run record is the build session's version; a restore or a correction then puts other bytes at head."""

    def __init__(self, tmp_path):
        self.w = BL.World(tmp_path)
        self.state = self.w.state
        self.w.fold_panel(BL._break_it_finding(BL._TEST_FAILING))
        self.key = self.w.key_of_failed_run()
        self.w.disposition("fixed")
        self.runs = []
        self.change(BL._TEST_WEAKENED, "the first draft was too strict", rnd=1)
        self.w.fix(BL._TEST_WEAKENED)

    def row(self):
        return RD._fixed_ledger_rows(self.state)[1][self.key]

    def change(self, content, why, rnd):
        """What `break-it-change` records: the changed block on the ledger row and a new run record."""
        config = self.state["config"]
        self.state["round"] = rnd
        block = break_it.carried_block(self.row())[0]
        changed = {"path": block["path"], "run": block["run"], "content": content, "sha256": _sha(content)}
        record = break_it.run_one(self.w.repo, config["headSha"], changed, scratch=str(self.w.session),
                                  interpreter=break_it.resolve_interpreter(config))
        RD._carry_break_it_change_to_ledger(self.state, self.key, RD._break_it_block_text(changed, content),
                                            record, why)
        RD._record_round_append(self.state, "breakItRuns", dict(
            record, title=self.row().get("title"), file=self.row().get("file"), findingKey=self.key, changedWhy=why))

    def commit(self, content, message="commit the test"):
        BL._write(self.w.repo, BL.TEST_PATH, content)
        head = BL._commit(self.w.repo, message)
        self.state["config"][RD.FIX_FOLD_HEAD_KEY] = head
        return head

    def restore(self, content, stage="restore", rnd=2):
        """The restore-only step's fold (the one `_fold_test_restore` the driver runs) over a commit of ``content``."""
        self.state["round"] = rnd
        head = self.commit(content, "restore")
        self.state[RD.TEST_RESTORE_FIELD] = {"stage": stage, "then": RD.VERIFY_THEN_POST_AUDITS, "items": [
            {"findingKey": self.key, "path": BL.TEST_PATH, "content": content, "sha256": _sha(content),
             "weakened": False}]}
        RD._fold_test_restore(self.state, self.state["config"], {"fixes": []}, check=(None, head))

    def kept(self):
        """``(parked, outcome of the latest kept row)``."""
        parked = RD._break_it_kept_step(self.state, self.state["config"])
        return parked, self.state["rounds"][str(self.state["round"])]["breakItKept"][-1]["outcome"]

    def run_count(self):
        return sum(len(rec.get("breakItRuns") or []) for rec in self.state["rounds"].values())


def test_t9_a_session_that_converges_after_a_restore_keeps_the_restored_test(tmp_path):
    # axis: E5 — after a restore the kept check expects the carried block's bytes, not the latest run's
    k = KeptWorld(tmp_path)
    assert k.run_count() == 2
    k.restore(BL._TEST_FAILING)
    assert k.row()["suggestion"].endswith(BL._TEST_FAILING) and BL._TEST_FAILING != BL._TEST_WEAKENED
    k.state["round"] = 3  # the finding is fixed and discharged in a later round
    RD._terminal_converged(k.state, k.state["config"], full_panel=True)
    assert k.state["terminal"] == "converged", k.state.get("certification")
    assert k.state["rounds"]["3"]["breakItKept"][-1]["outcome"] == "kept"
    assert k.run_count() == 2, "a restore is no run: no run is recorded for it"


def test_t9_a_landed_correction_is_the_test_the_kept_check_expects(tmp_path):
    k = KeptWorld(tmp_path)
    k.restore(BL._TEST_FAILING)
    corrected = BL._TEST_FAILING + "assert ledger == [100]\n"
    k.restore(corrected, stage="corrected")
    assert [e["source"] for e in k.state["rounds"]["2"]["testRestore"]] == ["reviewer", "corrected"]
    assert k.kept() == (False, "kept")
    assert k.run_count() == 2
    # the expectation is the corrected bytes: the test role's first restore is no longer what must be there
    k.commit(BL._TEST_FAILING, "back to the first restore")
    parked, outcome = k.kept()
    assert parked is True and outcome == "changed" and k.state["terminal"] == "cannot-certify"


def test_t9_a_test_the_build_session_changes_again_after_the_restore_is_checked_as_that_later_run(tmp_path):
    k = KeptWorld(tmp_path)
    k.restore(BL._TEST_FAILING)
    again = BL._TEST_FAILING.replace("== 1", "<= 1")
    k.change(again, "the restored test needs one more change", rnd=3)
    assert k.run_count() == 3
    k.commit(again, "commit the later change")
    assert k.kept() == (False, "kept")
    # the restore is older than the run: the restored bytes are not what must be there
    k.commit(BL._TEST_FAILING, "the earlier restore again")
    parked, outcome = k.kept()
    assert parked is True and outcome == "changed"


def test_t9_a_later_run_wins_over_an_older_restore_whatever_the_ledger_block_holds(tmp_path):
    # edge 5: the ordering rule is the record's (round, then list order), not the ledger's; the ledger row here still
    # holds the restored block while the later run is of other bytes
    k = KeptWorld(tmp_path)
    k.restore(BL._TEST_FAILING)
    later = BL._TEST_FAILING.replace("== 1", "<= 1")
    k.state["round"] = 3
    RD._record_round_append(k.state, "breakItRuns", dict(
        k.state["rounds"]["1"]["breakItRuns"][-1], sha256=_sha(later), content=later))
    assert k.row()["suggestion"].endswith(BL._TEST_FAILING)
    k.commit(later, "the later change")
    assert k.kept() == (False, "kept")


def test_t9_a_finding_with_no_restore_is_checked_exactly_as_before(tmp_path):
    # edge 4 / 2d: no `testRestore` entry, no substitution; `test_break_it_loop.py::
    # test_l5_a_fixed_break_it_test_that_is_kept_certifies` is the unchanged case this one extends
    k = KeptWorld(tmp_path)
    assert "testRestore" not in k.state["rounds"].get("1", {})
    assert k.kept() == (False, "kept")
    k.commit(BL._TEST_FAILING, "another test at the path")
    parked, outcome = k.kept()
    assert parked is True and outcome == "changed"


def test_t9_a_carried_block_that_cannot_be_read_keeps_today_s_expectation_and_parks(tmp_path):
    # edge 3: fail closed, never pass on a guess
    k = KeptWorld(tmp_path)
    k.restore(BL._TEST_FAILING)
    ledger = k.state[RD.session_contract.DISPOSITION_LEDGER_KEY]
    ledger[RD._ledger_index_by_key(ledger)[k.key]]["suggestion"] = "no longer a block"
    assert break_it.carried_block(k.row())[0] is None
    parked, outcome = k.kept()
    assert parked is True and outcome == "changed"
    assert k.state["rounds"]["2"]["breakItKept"][-1]["reason"] == "sha256-differs"


# --- the durable paths: a verify result landed before the restore, and a finding raised again -----------------------

def test_the_gate_after_a_restore_runs_again_at_the_restored_head_and_never_reuses_the_landed_pass(
        tmp_path, monkeypatch, adapters):
    # axis: the post-restore verify takes a fresh slot — the concurrent slot's earlier pass is not the gate's result
    # No seat map: no reviewer outside the makers' families can be seated, so the correction is not offered and the
    # restore goes straight to the gate (asserted below through the `break-it-correction-unseatable` decision).
    w = World(tmp_path, seat_map=False)
    w.cfg["verifyCommand"] = "make test"
    d = TA._session(tmp_path, name="durable", verifyCommand="make test")
    state = TA._state(d)
    for field in ("round", "rounds", "fixBatch", "findings", "_auditTargets", "_newSurface", "_fixDeltaDiff",
                  "_verifyThen", "step"):
        state[field] = w.state[field]
    state["config"].update({k: v for k, v in w.cfg.items() if k != "verifyCommand"})
    state["pending"] = None
    RD.save_state(d, state)
    monkeypatch.chdir(w.root)
    out = RD.cmd_next(d)
    assert out["ok"] and out["phase"] == RD.P_AUDITS, out
    slot = out["payload"]["verify"]
    first = RD.cmd_run_verify(d, run=TA._verb_run(0))
    assert first["ok"] is True and first["result"] == "pass" and first["attempt"] == slot["attempt"], first
    assert first["landingPath"] == slot["landingPath"]
    # the audits report a weakened test while that pass is landed and unaccepted; the restore is committed
    w.state = TA._state(d)
    w.state["pending"] = None
    w.audit()
    w.restore()
    restored = w.head()
    assert "break-it-correction-unseatable" in _decisions(w.state), _decisions(w.state)
    assert "break-it-correction-offered" not in _decisions(w.state)
    assert w.state["step"] == RD.P_VERIFY and w.state["_restoredHead"] == restored
    RD.save_state(d, w.state)
    nxt = RD.cmd_next(d)
    assert nxt["ok"] and nxt["phase"] == RD.P_VERIFY, nxt
    assert nxt["attempt"] != slot["attempt"], "the restored head was given the slot the old pass landed in"
    assert nxt["payload"]["restoredHead"] == restored
    calls = []
    again = RD.cmd_run_verify(d, run=TA._verb_run(0, calls=calls))
    assert again["ok"] is True and len(calls) == 1, again
    landed, err = RD.round_records.read_json(again["landingPath"])
    assert err is None and landed["headSha"] == restored


def test_the_gate_after_a_restore_never_shares_a_slot_with_a_run_verify_still_in_progress(
        tmp_path, monkeypatch, adapters):
    # axis: the post-restore verify skips a slot an in-progress run-verify claims, and the old runner cannot publish into the new one
    w = World(tmp_path, seat_map=False)  # no correction is offered (see the test above), so the restore reaches the gate
    w.cfg["verifyCommand"] = "make test"
    d = TA._session(tmp_path, name="claimed", verifyCommand="make test")
    state = TA._state(d)
    for field in ("round", "rounds", "fixBatch", "findings", "_auditTargets", "_newSurface", "_fixDeltaDiff",
                  "_verifyThen", "step"):
        state[field] = w.state[field]
    state["config"].update({k: v for k, v in w.cfg.items() if k != "verifyCommand"})
    state["pending"] = None
    RD.save_state(d, state)
    monkeypatch.chdir(w.root)
    out = RD.cmd_next(d)
    assert out["ok"] and out["phase"] == RD.P_AUDITS, out
    slot = out["payload"]["verify"]
    rnd, old = slot["round"], slot["attempt"]
    # a concurrent run-verify holds the slot (a live claim, nothing landed): this process stands in for its runner
    landing_dir = RD.round_records.landing_dir(d, rnd, RD.P_VERIFY)
    os.makedirs(landing_dir, exist_ok=True)
    claim_path = os.path.join(landing_dir, RD.RUN_VERIFY_CLAIM_NAME % old)
    with open(claim_path, "w", encoding="utf-8") as fh:
        fh.write(RD.round_records.canonical({"pid": os.getpid(), "token": "t", "startedAt": "x"}))
    w.state = TA._state(d)
    w.state["pending"] = None
    w.audit()
    w.restore()
    restored = w.head()
    assert w.state["step"] == RD.P_VERIFY and w.state["_restoredHead"] == restored
    RD.save_state(d, w.state)
    nxt = RD.cmd_next(d)
    assert nxt["ok"] and nxt["phase"] == RD.P_VERIFY, nxt
    assert nxt["attempt"] != old, "the restored head was given the slot a live run-verify holds"
    calls = []
    again = RD.cmd_run_verify(d, run=TA._verb_run(0, calls=calls))
    assert again["ok"] is True and again["attempt"] == nxt["attempt"] and len(calls) == 1, again
    landed, err = RD.round_records.read_json(again["landingPath"])
    assert err is None and landed["headSha"] == restored
    # the old runner finishes after the restore: its slot is no longer the pending one, so nothing lands
    skey = RD.round_records.storage_key("verify")
    old_claim = {"slot": (rnd, old), "stale": False,
                 "landingPath": RD.round_records.bare_payload_path(d, rnd, RD.P_VERIFY, skey, old),
                 "recordPath": RD.round_records.store_path(d, rnd, RD.P_VERIFY, skey, old)}
    refused = RD._run_verify_publish(d, old_claim, {"result": "pass", "headSha": w.fix_head}, [])
    assert refused["ok"] is False and refused["reason"] == "run-verify-slot-moved", refused
    assert not os.path.exists(old_claim["landingPath"])


@pytest.mark.parametrize("head,halts", [pytest.param("0" * 40, True, id="another-head"),
                                        pytest.param(None, False, id="restored-head")])
def test_the_gate_after_a_restore_counts_only_a_run_at_the_restored_head(tmp_path, head, halts):
    w = World(tmp_path, seat_map=False)  # no correction is offered, so the restore goes straight to the gate
    w.audit()
    w.restore()
    restored = w.state["_restoredHead"]
    artifact = {"result": "pass", "headSha": head or restored}
    w.fold(RD.P_VERIFY, artifact, verified_head_resolution=(None, None))
    if halts:
        assert w.state["terminal"] == "halted" and w.state["step"] == RD.P_TERMINAL
        assert w.state["decisions"][-1]["kind"] == "verify-unresolved"
    else:
        assert not w.state.get("terminal") and "_restoredHead" not in w.state


@pytest.mark.parametrize("moves,halts", [pytest.param(True, True, id="head-moved-during-the-run"),
                                         pytest.param(False, False, id="head-held-still")])
def test_the_gate_after_a_restore_refuses_a_run_that_moved_head_during_the_run(tmp_path, moves, halts):
    # axis: the gate after a restore counts only a run that held still at the restored head — a pass that starts there and ends at another commit halts
    w = World(tmp_path, seat_map=False)  # no correction is offered, so the restore goes straight to the gate
    w.audit()
    w.restore()
    restored = w.state["_restoredHead"]
    later = _commit(w.root, "moved on during the run")
    assert later != restored
    artifact = {"result": "pass", "headSha": restored, "headShaAfter": later if moves else restored}
    w.fold(RD.P_VERIFY, artifact, verified_head_resolution=(None, None))
    if halts:
        assert w.state["terminal"] == "halted" and w.state["step"] == RD.P_TERMINAL
        assert w.state["decisions"][-1]["kind"] == "verify-unresolved"
        assert "moved during the run" in w.state["decisions"][-1]["detail"]
        assert w.state["certification"]["shape"] is None
        assert "moved during the run" in w.state["certification"]["reason"]
    else:
        assert not w.state.get("terminal") and "_restoredHead" not in w.state


def test_two_failing_runs_at_the_restored_head_halt_and_never_fall_back_to_an_earlier_pass(tmp_path):
    # axis: the post-restore gate is decided by its own runs — a first failure re-runs once, a second one halts
    w = World(tmp_path, seat_map=False)  # no correction is offered, so the restore goes straight to the gate
    w.audit()
    w.restore()
    restored = w.state["_restoredHead"]
    failing = {"result": "fail", "headSha": restored}
    w.fold(RD.P_VERIFY, failing, verified_head_resolution=(None, None))
    assert not w.state.get("terminal") and "verify-rerun" in _decisions(w.state)
    assert w.state["_restoredHead"] == restored
    w.fold(RD.P_VERIFY, failing, verified_head_resolution=(None, None))
    assert w.state["terminal"] == "halted" and w.state["step"] == RD.P_TERMINAL
    assert _decisions(w.state)[-1] == "verify-fail"


def test_two_failing_runs_after_a_restore_halt_through_run_verify_and_advance_never_counting_the_landed_pass(
        tmp_path, monkeypatch, adapters):
    # axis: the durable post-restore gate — two failing run-verify landings, each advanced, halt; the earlier landed pass is never the result
    w = World(tmp_path, seat_map=False)  # no correction is offered, so the restore reaches the gate
    w.cfg["verifyCommand"] = "make test"
    d = TA._session(tmp_path, name="durable-fail", verifyCommand="make test")
    state = TA._state(d)
    for field in ("round", "rounds", "fixBatch", "findings", "_auditTargets", "_newSurface", "_fixDeltaDiff",
                  "_verifyThen", "step"):
        state[field] = w.state[field]
    state["config"].update({k: v for k, v in w.cfg.items() if k != "verifyCommand"})
    state["pending"] = None
    RD.save_state(d, state)
    monkeypatch.chdir(w.root)
    out = RD.cmd_next(d)
    assert out["ok"] and out["phase"] == RD.P_AUDITS, out
    slot = out["payload"]["verify"]
    first = RD.cmd_run_verify(d, run=TA._verb_run(0))
    assert first["ok"] is True and first["result"] == "pass" and first["attempt"] == slot["attempt"], first
    # the audits report a weakened test while that pass is landed and unaccepted; the restore is committed
    w.state = TA._state(d)
    w.state["pending"] = None
    w.audit()
    w.restore()
    restored = w.head()
    assert w.state["step"] == RD.P_VERIFY and w.state["_restoredHead"] == restored
    RD.save_state(d, w.state)
    nxt = RD.cmd_next(d)
    assert nxt["ok"] and nxt["phase"] == RD.P_VERIFY and nxt["attempt"] != slot["attempt"], nxt
    # the first failing run at the restored head lands in its own slot and is recorded as a re-run, not a halt
    calls = []
    fail1 = RD.cmd_run_verify(d, run=TA._verb_run(1, calls=calls))
    assert fail1["ok"] is True and fail1["result"] == "fail" and len(calls) == 1, fail1
    assert fail1["attempt"] == nxt["attempt"], fail1
    landed1, err = RD.round_records.read_json(fail1["landingPath"])
    assert err is None and landed1["headSha"] == restored and landed1["result"] == "fail"
    out1 = TA._advance(d, tmp_path)
    assert out1["ok"] is True and out1.get("terminal") is None, out1
    mid = TA._state(d)
    assert not mid.get("terminal") and mid["step"] == RD.P_VERIFY and mid["_restoredHead"] == restored
    assert "verify-rerun" in _decisions(mid) and "verify-fail" not in _decisions(mid)
    assert mid["rounds"][str(mid["round"])]["verifyResult"] == "fail"
    # the re-run takes yet another slot, never the earlier landed pass's
    pend = mid["pending"]
    assert pend["phase"] == RD.P_VERIFY and pend["attempt"] not in (slot["attempt"], fail1["attempt"]), pend
    # the second failing run at the restored head halts the round
    fail2 = RD.cmd_run_verify(d, run=TA._verb_run(1))
    assert fail2["ok"] is True and fail2["result"] == "fail" and fail2["attempt"] == pend["attempt"], fail2
    out2 = TA._advance(d, tmp_path)
    assert out2["ok"] is True and out2.get("terminal") == "halted", out2
    end = TA._state(d)
    assert end["terminal"] == "halted" and end["step"] == RD.P_TERMINAL
    assert _decisions(end)[-1] == "verify-fail"
    assert end["rounds"][str(end["round"])]["verifyResult"] == "fail"


def test_a_used_correction_stays_used_when_the_finding_is_raised_again(tmp_path):
    # axis: the once-only guard also reads the round history, which a re-raised finding's fresh copies cannot reset
    w = World(tmp_path)
    w.audit()
    w.restore()
    w.correct(CORRECTED_TEST)
    assert RD._correction_used(w.state, w.key) is True
    # the live copies are replaced by fresh ones, as a scoped finder raising the same key again does
    fresh = C1._finding(content=FIXED_TEST, reviewer_test=ROLE_TEST, changed_why=WHY)
    w.state["findings"] = [fresh]
    w.state["fixBatch"] = [copy.deepcopy(fresh)]
    w.state["_auditTargets"] = RD._audit_targets(w.state, w.cfg, {})
    w.state.pop(RD.session_contract.DISPOSITION_LEDGER_KEY, None)
    assert all(RD.TEST_CORRECTION_FIELD not in row for row in w.state["findings"] + w.state["fixBatch"])
    assert RD._correction_used(w.state, w.key) is True
    assert RD._correction_used(w.state, "another-key") is False
