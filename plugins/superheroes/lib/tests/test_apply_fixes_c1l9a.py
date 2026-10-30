"""The build session applies the fixes itself: the `apply-fixes` step, and a fix that carries a break-it test
lands with its test.

E1 a bound commit that carries the fix and the test folds, and the round records it.
E2 no binding for a test-carrying finding refuses with `no-binding`, the step still pending.
E3 a commit without the test refuses `test-missing`; E4 a commit with other bytes `test-bytes-differ`.
E5 a commit that changes only the test refuses `no-fix-change`.
E6 a commit outside HEAD refuses `commit-unknown`; one reachable from the step's start head `commit-not-in-step`, even
   when that commit carries both the fix and the test (the start-head range alone refuses it).
E7 a repair round: the test already at the start head with the block's bytes, a source-only commit folds.
E8 a finding listed `unfixed` owes no test and is not credited.
E9 a binding or an `unfixed` entry naming a finding outside the slice refuses.
E10 a slice with no commit and no test-carrying finding folds, and a changed staged PR body is recorded.
E11 a run with no repository owes the commit facts to the `fix_commits` seam.
E13 a ruling while the step is pending rewrites its batch and guidance files.
E14 `next --fixer-vendor` is no flag. E15 the fixer's vendor is the build session's family's.
"""
import hashlib
import json
import os
import shlex
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _path in (_HERE, _LIB):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import break_it  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD

PY = shlex.quote(sys.executable)
_ID = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]

CHARGE_PATH = "src/payments/charge.py"
TEST_PATH = "tests/test_charge_once.py"
VENDORS = ["claude", "codex"]
REFUSED = "fold-refused"
NO_TEST = "fix-without-break-it-test"

_CHARGE_RETRYING = (
    "def charge_with_retry(ledger, amount, timeouts=1):\n"
    "    for _ in range(timeouts + 1):\n"
    "        ledger.append(amount)\n"
    "    return ledger\n")
_CHARGE_FIXED = (
    "def charge_with_retry(ledger, amount, timeouts=1):\n"
    "    if not ledger:\n"
    "        ledger.append(amount)\n"
    "    return ledger\n")
_TEST_FAILING = (
    "import os, sys\n"
    "sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'payments'))\n"
    "import charge\n"
    "ledger = charge.charge_with_retry([], 100, timeouts=1)\n"
    "assert len(ledger) == 1, 'charged %d times' % len(ledger)\n")
_TEST_OTHER_BYTES = _TEST_FAILING.replace("== 1", ">= 1")


@pytest.fixture(autouse=True)
def _pinned_git(monkeypatch, tmp_path):
    """The fixture repo's commits read no user or system git configuration."""
    for name in ("home", "xdg-config"):
        (tmp_path / name).mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def git(repo, *args):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    done = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, text=True, env=env)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def commit(repo, message):
    git(repo, "add", "-A")
    git(repo, *_ID, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def write(repo, rel, text):
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def block(path, content):
    return "break-it-test v1\npath: %s\nrun: %s %s\n---\n%s" % (path, PY, shlex.quote(path), content)


def attached(title="A retried charge is posted twice", **extra):
    """An ordinary finding of the test role's seat with a break-it test attached; it keeps its own file:line."""
    out = {"title": title, "file": CHARGE_PATH, "line": 2, "severity": "Important",
           "taxonomy": "test-quality", "body": "the retry resends the charge",
           "consequence": "the customer is charged twice", "confidence": "High",
           "suggestion": block(TEST_PATH, _TEST_FAILING)}
    out.update(extra)
    return out


def ordinary(**extra):
    out = {"title": "The PR body names the wrong retry count", "file": CHARGE_PATH, "line": 3,
           "severity": "Important", "consequence": "a reader is misled", "confidence": "High",
           "body": "the description says one retry"}
    out.update(extra)
    return out


def responder(findings=(), apply_fixes=None, verify="pass"):
    """Answer every phase of a full review: the test role's seat returns ``findings`` in round 1, every
    verifier confirms, every audit discharges, and ``apply_fixes`` (given the step's payload) is the build
    session's report."""
    def respond(phase, payload, rnd):
        if phase == RD.P_PANEL:
            seats = {d: {"findings": []} for d in RD.DIMENSIONS}
            if rnd == 1 and findings:
                seats["test-role"] = {"findings": list(findings)}
            return {"seats": seats, "seatMap": TRD._assertable_seat_map(VENDORS, "claude")}
        if phase == RD.P_VERIFIERS:
            return {"verdicts": [{"id": i, "verdict": "CONFIRMED", "reason": "checked", "evidence": "ran"}
                                 for c in payload.get("clusters", []) for i in c.get("ids", [])]}
        if phase == RD.P_SYNTHESIS:
            return {"grouping": None}
        if phase in (RD.P_GAPSWEEP, RD.P_SCOPED):
            return {"findings": []}
        if phase == RD.P_AUDITS:
            return {"results": [{"id": t["id"], "ruling": "discharged", "reason": "r", "evidence": "e",
                                 "auditorVendor": t.get("auditorVendor")} for t in payload.get("targets", [])],
                    "collectionManifest": {t["id"]: t.get("auditorVendor") for t in payload.get("targets", [])}}
        if phase == RD.P_APPLY_FIXES:
            return apply_fixes(payload)
        if phase == RD.P_VERIFY:
            return {"result": verify}
        return {}

    return respond


class Fixture:
    """A throwaway repo whose change adds src/payments/charge.py, a session folder over it, and a review
    driven by `next` / `submit` to the pending `apply-fixes` step."""

    def __init__(self, root, findings=None, staged_pr_body=None):
        root.mkdir(parents=True, exist_ok=True)
        self.repo = root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        write(self.repo, "README.md", "fixture\n")
        self.base = commit(self.repo, "base")
        write(self.repo, CHARGE_PATH, _CHARGE_RETRYING)
        self.head = commit(self.repo, "retry the charge")
        self.diff = git(self.repo, "diff", self.base, self.head) + "\n"
        self.session = root / "session"
        self.session.mkdir()
        (self.session / RD.round_records.META_FILE).write_text(
            '{"repoRoot": "%s", "headSha": "%s"}' % (self.repo, self.head))
        if staged_pr_body is not None:
            (self.session / "pr-body").mkdir()
            (self.session / "pr-body" / "staged.md").write_text(staged_pr_body)
        self.config = TRD._cfg(diff=self.diff, repoRoot=str(self.repo), baseRef=self.base, headSha=self.head,
                               verifyCommand="%s -c pass" % PY)
        self.findings = [attached()] if findings is None else findings
        self.respond = responder(self.findings, lambda payload: {"fixes": ["fixed"]})
        self.pending = None

    def reach(self):
        """Drive to the pending `apply-fixes` step; return its `next`."""
        self.pending = TRD._drive_to_phase(str(self.session), self.config, self.respond, RD.P_APPLY_FIXES)
        return self.pending

    def state(self):
        ok, state = RD.load_state(str(self.session))
        assert ok
        return state

    def keys(self):
        return [RD._finding_identity_key(row) for row in self.state()["_fixBatch"]]

    def key_of(self, title):
        (key,) = [RD._finding_identity_key(r) for r in self.state()["_fixBatch"] if r["title"] == title]
        return key

    def commit_fix(self, test_content=_TEST_FAILING, code=_CHARGE_FIXED, message="fix the retry"):
        """Commit a fix: the charge code and the test file, each unless it is None."""
        if code is not None:
            write(self.repo, CHARGE_PATH, code)
        if test_content is not None:
            write(self.repo, TEST_PATH, test_content)
        return commit(self.repo, message)

    def submit(self, artifact, pending=None):
        n = pending or self.pending
        return RD.cmd_submit(str(self.session), n["phase"], n["attempt"], n["expectedStateHash"], artifact)

    def assert_refused_pending(self, artifact, detail):
        """The report refuses as `fold-refused` naming ``detail``, and the state file, the pending step and its
        attempt are exactly as they were."""
        before = TRD._state_bytes(str(self.session))
        out = self.submit(artifact)
        assert out == {"ok": False, "reason": REFUSED, "detail": detail}, out
        assert TRD._state_bytes(str(self.session)) == before
        again = RD.cmd_next(str(self.session))
        assert (again["phase"], again["attempt"]) == (self.pending["phase"], self.pending["attempt"])
        assert again["payload"] == self.pending["payload"]


def _bound(key, sha):
    return {"fixes": [{"finding": key, "commit": sha}]}


# ---- the step and what `next` hands the session --------------------------------------------------------------

def test_next_hands_the_session_its_batch_files_and_landing_and_makes_no_order(tmp_path):
    fx = Fixture(tmp_path, staged_pr_body="the body\n")
    n = fx.reach()
    payload = n["payload"]
    assert n["action"] == n["phase"] == RD.P_APPLY_FIXES
    assert payload["startHead"] == fx.head == git(fx.repo, "rev-parse", "HEAD")
    assert [RD._finding_identity_key(r) for r in payload["batch"]] == fx.keys()
    assert json.load(open(payload["fixBatchPath"])) and payload["guidancePath"] is None
    assert payload["landingPath"] == RD.round_records.bare_payload_path(
        str(fx.session), 1, RD.P_APPLY_FIXES, RD.round_records.storage_key("apply-fixes"), n["attempt"])
    assert os.path.isdir(os.path.dirname(payload["landingPath"]))
    assert payload["prBodyPath"] == os.path.join(str(fx.session), "pr-body", "staged.md")
    assert not os.path.exists(os.path.join(str(fx.session), "round-1", "orders", RD.P_APPLY_FIXES))
    assert not [e for e in RD.read_journal(str(fx.session)) if e.get("outcome") == "orders-emitted"
                and e.get("phase") == RD.P_APPLY_FIXES]


# ---- E1 ------------------------------------------------------------------------------------------------------

def test_e1_a_bound_commit_that_carries_the_fix_and_the_test_folds(tmp_path):
    fx = Fixture(tmp_path)
    fx.reach()
    key = fx.keys()[0]
    sha = fx.commit_fix()
    out = fx.submit(_bound(key, sha))
    assert out["ok"] is True and out["nextStep"] != RD.P_APPLY_FIXES, out
    fix = fx.state()["rounds"]["1"]["fix"]
    assert fix["commits"] == [{"finding": key, "commit": sha}]
    assert fix["fixes"] == [{"finding": key, "commit": sha}] and "unfixed" not in fix
    assert key in fx.state()["rounds"]["1"]["fixReportedKeys"]


def test_e1_a_staged_id_names_the_finding_as_its_key_does(tmp_path):
    fx = Fixture(tmp_path)
    n = fx.reach()
    row = n["payload"]["batch"][0]
    sha = fx.commit_fix()
    out = fx.submit(_bound(row["id"], sha))
    assert out["ok"] is True, out
    assert fx.state()["rounds"]["1"]["fix"]["commits"] == [
        {"finding": RD._finding_identity_key(row), "commit": sha}]


# ---- E2 – E6 -------------------------------------------------------------------------------------------------

def test_e2_a_test_carrying_finding_with_no_binding_refuses_and_the_step_stays_pending(tmp_path):
    fx = Fixture(tmp_path)
    fx.reach()
    key = fx.keys()[0]
    fx.commit_fix()
    fx.assert_refused_pending({"fixes": ["fixed it"]}, "%s:%s:no-binding" % (NO_TEST, key))
    # a corrected resubmit on the same attempt and hash folds
    sha = git(fx.repo, "rev-parse", "HEAD")
    assert fx.submit(_bound(key, sha))["ok"] is True


def test_e3_a_commit_that_lacks_the_test_refuses(tmp_path):
    fx = Fixture(tmp_path)
    fx.reach()
    key = fx.keys()[0]
    sha = fx.commit_fix(test_content=None)
    fx.assert_refused_pending(_bound(key, sha), "%s:%s:test-missing" % (NO_TEST, key))


def test_e4_a_commit_whose_test_bytes_differ_from_the_block_refuses(tmp_path):
    fx = Fixture(tmp_path)
    fx.reach()
    key = fx.keys()[0]
    sha = fx.commit_fix(test_content=_TEST_OTHER_BYTES)
    fx.assert_refused_pending(_bound(key, sha), "%s:%s:test-bytes-differ" % (NO_TEST, key))


def test_e5_a_commit_that_changes_only_the_test_refuses(tmp_path):
    fx = Fixture(tmp_path)
    fx.reach()
    key = fx.keys()[0]
    sha = fx.commit_fix(code=None)
    fx.assert_refused_pending(_bound(key, sha), "%s:%s:no-fix-change" % (NO_TEST, key))


def test_e6_a_commit_outside_head_refuses_commit_unknown(tmp_path):
    fx = Fixture(tmp_path)
    fx.reach()
    key = fx.keys()[0]
    git(fx.repo, "checkout", "-q", "-b", "side")
    side = fx.commit_fix()
    git(fx.repo, "checkout", "-q", "-")
    fx.assert_refused_pending(_bound(key, side), "%s:%s:commit-unknown" % (NO_TEST, key))
    fx.assert_refused_pending(_bound(key, "0" * 40), "%s:%s:commit-unknown" % (NO_TEST, key))


def test_e6_a_commit_reachable_from_the_start_head_refuses_commit_not_in_step(tmp_path):
    fx = Fixture(tmp_path)
    n = fx.reach()
    key = fx.keys()[0]
    fx.commit_fix()
    fx.assert_refused_pending(_bound(key, n["payload"]["startHead"]),
                              "%s:%s:commit-not-in-step" % (NO_TEST, key))


def test_e6_a_complete_commit_reachable_from_the_start_head_refuses_commit_not_in_step(tmp_path):
    # axis: the start-head range refuses a commit that is otherwise complete — see bite-proof record c1l9a_wo4a_migration
    fx = Fixture(tmp_path)
    fx.reach()
    key = fx.keys()[0]
    sha = fx.commit_fix()
    assert sorted(git(fx.repo, "show", "--name-only", "--format=", sha).split()) == [CHARGE_PATH, TEST_PATH]
    # the step began at a head that already holds the commit, which carries the fix and the test
    state = fx.state()
    state["_fixStepHead"] = sha
    RD.save_state(str(fx.session), state)
    fx.pending = RD.cmd_next(str(fx.session))
    fx.assert_refused_pending(_bound(key, sha), "%s:%s:commit-not-in-step" % (NO_TEST, key))


# ---- E7 ------------------------------------------------------------------------------------------------------

def test_e7_a_repair_round_with_the_test_already_at_the_start_head_folds_a_source_only_commit(tmp_path):
    fx = Fixture(tmp_path)
    fx.reach()
    key = fx.keys()[0]
    # the test was committed before the step began: the step starts at a head that already holds it
    start = fx.commit_fix(code=None, message="keep the test")
    state = fx.state()
    state["_fixStepHead"] = start
    RD.save_state(str(fx.session), state)
    n = RD.cmd_next(str(fx.session))
    sha = fx.commit_fix(test_content=None)
    assert git(fx.repo, "show", "--name-only", "--format=", sha) == CHARGE_PATH
    out = fx.submit(_bound(key, sha), pending=n)
    assert out["ok"] is True, out
    assert fx.state()["rounds"]["1"]["fix"]["commits"] == [{"finding": key, "commit": sha}]


# ---- E8 / E9 -------------------------------------------------------------------------------------------------

def test_e8_a_finding_listed_unfixed_owes_no_test_and_is_not_credited(tmp_path):
    fx = Fixture(tmp_path)
    fx.reach()
    key = fx.keys()[0]
    out = fx.submit({"fixes": ["fixed what I could"],
                     "unfixed": [{"finding": key, "why": "the retry is the owner's call"}]})
    assert out["ok"] is True, out
    rec = fx.state()["rounds"]["1"]
    assert rec["fix"]["unfixed"] == [{"finding": key, "why": "the retry is the owner's call"}]
    assert rec["fix"]["commits"] == [] and rec["fixReportedKeys"] == []


@pytest.mark.parametrize("artifact_for, token", [
    (lambda key: {"fixes": [{"finding": "no-such-finding", "commit": "a" * 40}]},
     "fix-finding-unknown:no-such-finding"),
    (lambda key: {"fixes": ["x"], "unfixed": [{"finding": "no-such-finding", "why": "w"}]},
     "unfixed-finding-unknown:no-such-finding"),
])
def test_e9_a_finding_outside_the_slice_refuses(tmp_path, artifact_for, token):
    fx = Fixture(tmp_path)
    fx.reach()
    fx.assert_refused_pending(artifact_for(fx.keys()[0]), token)


# ---- E10 -----------------------------------------------------------------------------------------------------

def test_e10_a_pr_body_only_slice_folds_with_no_commit_and_records_the_changed_body(tmp_path):
    fx = Fixture(tmp_path, findings=[], staged_pr_body="the body, as staged\n")
    # a finding about the PR body: ordinary, carries no test
    fx.respond = responder([ordinary()], lambda payload: {"fixes": ["fixed the PR body"]})
    fx.findings = [ordinary()]
    fx.config["leg"] = "code"
    n = TRD._drive_to_phase(str(fx.session), fx.config, fx.respond, RD.P_APPLY_FIXES)
    staged = os.path.join(str(fx.session), "pr-body", "staged.md")
    before = hashlib.sha256(open(staged, "rb").read()).hexdigest()
    assert fx.state()["_prBodyAtStep"] == before
    open(staged, "w").write("the body, as fixed\n")
    after = hashlib.sha256(open(staged, "rb").read()).hexdigest()
    out = fx.submit({"fixes": ["fixed the PR body"]}, pending=n)
    assert out["ok"] is True, out
    rec = fx.state()["rounds"]["1"]
    assert rec["prBodyFix"] == {"before": before, "after": after}
    assert rec["fix"]["commits"] == []


def test_e10_an_unchanged_staged_body_records_no_pr_body_fix(tmp_path):
    fx = Fixture(tmp_path, findings=[], staged_pr_body="the body, as staged\n")
    fx.respond = responder([ordinary()], lambda payload: {"fixes": ["looked, nothing to change"]})
    n = TRD._drive_to_phase(str(fx.session), fx.config, fx.respond, RD.P_APPLY_FIXES)
    assert fx.submit({"fixes": ["looked, nothing to change"]}, pending=n)["ok"] is True
    assert "prBodyFix" not in fx.state()["rounds"]["1"]


# ---- E11: a run with no repository ---------------------------------------------------------------------------

def _loop_seams(key_box, report, **extra):
    """In-process seams: the code reviewer raises one finding carrying a test block; the fix step reports."""
    def reviewer(dim, tier, rnd, ctx):
        if dim == "code-reviewer" and rnd == 1:
            return [attached(file="f.py", line=1)]  # a line the scripted diff (TRD.DIFF) adds
        return []

    def fix_step(batch, rnd, payload):
        key_box["key"] = RD._finding_identity_key(batch[0])
        return report(key_box["key"])

    return dict(TRD._seams(reviewer=reviewer, fix_step=fix_step), **extra)


def test_e11_without_a_repository_or_the_seam_a_bound_test_finding_is_unverifiable():
    box = {}
    seams = _loop_seams(box, lambda key: {"fixes": [{"finding": key, "commit": "abc1234"}]})
    _receipt, state = TRD._run_loop_capturing_state(seams, TRD._cfg())
    assert state["terminal"] == "cannot-certify", state.get("certification")
    assert state["certification"]["reason"] == "%s: %s:%s:unverifiable" % (REFUSED, NO_TEST, box["key"])


def test_e11_without_a_repository_the_seam_supplies_the_commit_facts():
    box = {}

    def facts(commits, test_paths):
        assert commits == ["abc1234"] and test_paths == [TEST_PATH]
        return {"abc1234": {"reachable": True, "inStep": False, "paths": [CHARGE_PATH, TEST_PATH],
                            "files": {TEST_PATH: _TEST_FAILING.encode("utf-8")}}}

    seams = _loop_seams(box, lambda key: {"fixes": [{"finding": key, "commit": "abc1234"}]}, fix_commits=facts)
    _receipt, state = TRD._run_loop_capturing_state(seams, TRD._cfg())
    assert state["rounds"]["1"]["fix"]["commits"] == [{"finding": box["key"], "commit": "abc1234"}]


def test_e11_without_a_repository_the_seam_can_refuse_the_commit():
    box = {}
    seams = _loop_seams(
        box, lambda key: {"fixes": [{"finding": key, "commit": "abc1234"}]},
        fix_commits=lambda commits, paths: {"abc1234": {"reachable": True, "inStep": False,
                                                       "paths": [TEST_PATH], "files": {TEST_PATH: _TEST_FAILING.encode()}}})
    _receipt, state = TRD._run_loop_capturing_state(seams, TRD._cfg())
    assert state["terminal"] == "cannot-certify"
    assert "%s:%s:no-fix-change" % (NO_TEST, box["key"]) in state["certification"]["reason"]


# ---- E13: a ruling while the step is pending -----------------------------------------------------------------

def test_e13_a_ruling_while_the_step_is_pending_rewrites_the_batch_and_guidance_files(tmp_path):
    fx = Fixture(tmp_path, findings=[attached(), ordinary()])
    n = fx.reach()
    assert len(n["payload"]["batch"]) == 2 and n["payload"]["guidancePath"] is None
    test_key, other_key = fx.key_of("A retried charge is posted twice"), fx.key_of(
        "The PR body names the wrong retry count")
    prov = {"ruledBy": "owner", "ruledAt": "2026-08-26T00:00:00Z", "records": ["rulings.json"]}
    ruling = tmp_path / "ruling.json"
    ruling.write_text(json.dumps({"_provenance": prov, "rulings": [
        {"id": test_key, "ruling": "guidance", "reason": "owner direction",
         "guidance": "Keep the retry; make the charge idempotent instead."},
        {"id": other_key, "ruling": "out-of-scope", "reason": "defer",
         "followUp": {"item": "backlog item", "revisitTrigger": "next milestone",
                      "classClosure": "owner backlog"}}]}))
    out = RD.cmd_rule(str(fx.session), str(ruling), "owner")
    assert out["ok"] is True, out
    again = RD.cmd_next(str(fx.session))
    assert (again["phase"], again["attempt"]) == (RD.P_APPLY_FIXES, n["attempt"])
    assert [RD._finding_identity_key(r) for r in again["payload"]["batch"]] == [test_key]
    assert [RD._finding_identity_key(r) for r in json.load(open(again["payload"]["fixBatchPath"]))] == [test_key]
    guidance = open(again["payload"]["guidancePath"]).read()
    assert "make the charge idempotent" in guidance and again["payload"]["guidancePath"].endswith("fix-guidance.md")
    assert again["payload"]["startHead"] == n["payload"]["startHead"]
    # the fix then lands as in E1, against the rewritten step
    assert fx.submit(_bound(test_key, fx.commit_fix()), pending=again)["ok"] is True


# ---- E14 / E15 -----------------------------------------------------------------------------------------------

def test_e14_next_no_longer_takes_a_fixer_vendor(tmp_path):
    with pytest.raises(SystemExit) as exit_info:
        RD.main(["next", "--session-dir", str(tmp_path), "--fixer-vendor", "claude"])
    assert exit_info.value.code != 0


def _seat_map(**extra):
    return dict(TRD._assertable_seat_map(VENDORS, "claude"), **extra)


def _fixer_vendor_of(tmp_path, overrides):
    session = tmp_path / "s"
    session.mkdir()
    out = RD.cmd_next(str(session), dict({"leg": "code", "vendors": VENDORS, "diff": TRD.DIFF}, **overrides))
    assert out["ok"], out
    ok, state = RD.load_state(str(session))
    assert ok
    return state["config"].get("fixerVendor")


@pytest.mark.parametrize("map_extra, want", [
    ({"hostFamily": "anthropic"}, "claude"),
    ({"hostFamily": "openai"}, "codex"),
    ({"hostFamily": "xai"}, "cursor"),
    ({"hostFamily": None, "authorFamily": "openai"}, "codex"),
    ({"hostFamily": "martian", "authorFamily": "anthropic"}, None),
])
def test_e15_the_fixer_vendor_is_the_build_sessions_familys_vendor(tmp_path, map_extra, want):
    overrides = {"seatMap": _seat_map(**map_extra)}
    if map_extra.get("hostFamily") is None:
        overrides["seatMap"].pop("hostFamily", None)
    assert _fixer_vendor_of(tmp_path, overrides) == want


def test_e15_no_seat_map_leaves_the_fixer_unknown_and_a_given_vendor_is_kept(tmp_path):
    assert _fixer_vendor_of(tmp_path, {}) is None
    other = tmp_path / "other"
    other.mkdir()
    assert _fixer_vendor_of(other, {"seatMap": _seat_map(hostFamily="anthropic"), "fixerVendor": "codex"}) == "codex"
