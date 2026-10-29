"""Attached break-it tests (#2210, C1-L6 WO-B): a break-it test rides on any finding of the test role's seat, and the
run step judges nothing.

D1 a full panel runs an attached and a per-area test once each, before compile, and stages both stamped.
D3 the record writer's account carries the stamped runs in a shape the review record accepts.
D4 `_fill` appends a run in its scrubbed form.
D2 a per-area test with a syntax error is changed in place at the verifier step: both runs are recorded, the verifiers
   are re-ordered from the changed copies, and the fixer's commit of the changed test is the one the kept check holds.
F4 `break-it-change` at any step but the verifiers' is refused, the state untouched.
F5 each other refusal (unknown finding, no test, no reason, unreadable content, unchanged content) leaves the state alone.
F6 a verifier result for the superseded attempt is refused.
F1 a seat-supplied `breakItRun` / `breakItRuns` never survives compile.
F2 an attached block on a seat other than the test role's is never run.
F3 a passed run keeps its finding, stamped.
F7 a same-anchor merge an ordinary finding wins keeps the attached test, its stamp and its runs.
"""
import hashlib
import json
import os
import shlex
import subprocess
import sys
import types

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _path in (_HERE, _LIB):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import break_it  # noqa: E402
import engine_adapter  # noqa: E402
import review_record  # noqa: E402
import review_record_session as rs  # noqa: E402
import verification  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD
SC = RD.session_contract

PY = shlex.quote(sys.executable)
_ID = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]

CHARGE_PATH = "src/payments/charge.py"
ATTACHED_TEST = "tests/test_charge_once.py"
PER_AREA_TEST = "tests/test_charge_idempotent.py"
ATTACHED_TITLE = "A retried charge is posted twice"
CONSEQUENCE = "the customer is charged twice"

_CHARGE_RETRYING = (
    "def charge_with_retry(ledger, amount, timeouts=1):\n"
    "    for _ in range(timeouts + 1):\n"
    "        ledger.append(amount)\n"
    "    return ledger\n")
_TEST_FAILING = (
    "import os, sys\n"
    "sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'payments'))\n"
    "import charge\n"
    "ledger = charge.charge_with_retry([], 100, timeouts=1)\n"
    "assert len(ledger) == 1, 'charged %d times' % len(ledger)\n")
_TEST_PASSING = _TEST_FAILING.replace("== 1", ">= 1")


@pytest.fixture(autouse=True)
def _pinned_git(monkeypatch, tmp_path):
    """The fixture repo's commits read no user or system git config. The runner drops GIT_CONFIG_GLOBAL from the
    environment it gives git, so its own git calls are kept off the developer's configuration by an empty per-test
    HOME and XDG_CONFIG_HOME."""
    for name in ("home", "xdg-config"):
        (tmp_path / name).mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _git(repo, *args):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    done = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, text=True, env=env)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def _commit(repo, message):
    _git(repo, "add", "-A")
    _git(repo, *_ID, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _write(repo, rel, text):
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def _status(repo):
    return _git(repo, "status", "--porcelain", "--untracked-files=all")


def _block(path, content):
    return "break-it-test v1\npath: %s\nrun: %s %s\n---\n%s" % (path, PY, shlex.quote(path), content)


def _attached(content=_TEST_FAILING, **extra):
    """An ordinary finding of the test role's seat with a break-it block attached; it keeps its own file:line."""
    out = {"title": ATTACHED_TITLE, "file": CHARGE_PATH, "line": 2, "severity": "Important",
           "taxonomy": "test-quality", "body": "the retry resends the charge", "consequence": CONSEQUENCE,
           "confidence": "High", "suggestion": _block(ATTACHED_TEST, content)}
    out.update(extra)
    return out


def _per_area(content=_TEST_PASSING, **extra):
    out = {"title": "Break-it: an idempotent charge", "file": PER_AREA_TEST, "line": 1, "severity": "Important",
           "taxonomy": break_it.TAXONOMY, "body": "payments risk area", "consequence": CONSEQUENCE,
           "confidence": "High", "suggestion": _block(PER_AREA_TEST, content)}
    out.update(extra)
    return out


def _ordinary(**extra):
    out = {"title": ATTACHED_TITLE, "file": CHARGE_PATH, "line": 2, "severity": "Critical",
           "consequence": CONSEQUENCE, "confidence": "High", "body": "the same defect, found by a code read"}
    out.update(extra)
    return out


def _seats(**by_seat):
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    for seat, findings in by_seat.items():
        seats[seat.replace("_", "-")] = {"findings": list(findings)}
    return seats


class Fixture:
    """A throwaway repo whose change adds src/payments/charge.py, a session folder over it, and a fresh loop state."""

    def __init__(self, root):
        root.mkdir(parents=True, exist_ok=True)
        self.repo = root / "repo"
        self.repo.mkdir()
        _git(self.repo, "init", "-q")
        _write(self.repo, "README.md", "fixture\n")
        self.base = _commit(self.repo, "base")
        _write(self.repo, CHARGE_PATH, _CHARGE_RETRYING)
        self.head = _commit(self.repo, "retry the charge")
        self.diff = _git(self.repo, "diff", self.base, self.head) + "\n"
        self.session = root / "session"
        self.session.mkdir()
        (self.session / RD.round_records.META_FILE).write_text(
            '{"repoRoot": "%s", "headSha": "%s"}' % (self.repo, self.head))
        self.config = TRD._cfg(diff=self.diff, repoRoot=str(self.repo), baseRef=self.base, headSha=self.head,
                               verifyCommand="%s -c pass" % PY)
        self.state = RD.new_state(self.config)
        self.state["reviewedDiff"] = self.diff

    def fold_panel(self, **by_seat):
        RD._fold(self.state, self.state["config"], RD.P_PANEL, {"seats": _seats(**by_seat)},
                 session_dir=str(self.session))
        return self.state

    @property
    def round_record(self):
        return self.state["rounds"][str(self.state["round"])]

    def staged(self, title):
        (found,) = [f for f in self.state["_toVerify"] if f["title"] == title]
        return found

    def fix(self, test_path=None, test_content=None):
        """Commit a fix; the test file goes in with it unless ``test_path`` is None."""
        _write(self.repo, CHARGE_PATH, _CHARGE_RETRYING + "# fixed\n")
        if test_path is not None:
            _write(self.repo, test_path, test_content)
        self.state["config"][RD.FIX_FOLD_HEAD_KEY] = _commit(self.repo, "fix the retry")


@pytest.fixture
def fx(tmp_path):
    return Fixture(tmp_path)


@pytest.fixture
def spy(monkeypatch):
    """Wrap the intercept's runner: ``calls`` is one entry per test actually run, ``offered`` the titles each
    intercept call was handed."""
    seen = types.SimpleNamespace(calls=[], offered=[])
    real = break_it.intercept

    def runner(repo_root, head, block, **kwargs):
        seen.calls.append({"path": block["path"], "head": head, "repo_root": repo_root})
        return break_it.run_one(repo_root, head, block, **kwargs)

    def spying(findings, repo_root, head, **kwargs):
        seen.offered.append([f.get("title") for f in findings])
        return real(findings, repo_root, head, **dict(kwargs, runner=runner))

    monkeypatch.setattr(break_it, "intercept", spying)
    return seen


def _drive_to_verifiers(fx_, seats, respond=None):
    """Drive a real session (`next` / `submit`) through the panel, whose test-role seat returns ``seats``'s findings,
    and stop at the pending verifier step. Returns that `next`. ``respond`` answers every phase when given."""
    base = TRD._responder()

    def panel_only(phase, payload, rnd):
        if phase == RD.P_PANEL:
            return {"seats": seats}
        return base(phase, payload, rnd)

    return TRD._drive_to_phase(str(fx_.session), fx_.config, respond or panel_only, RD.P_VERIFIERS)


# ---- D1 / D3 ------------------------------------------------------------------------------------------------

def test_d1_a_full_panel_runs_an_attached_and_a_per_area_test_once_and_stages_both_stamped(fx, spy):
    before = _status(fx.repo)
    nxt = _drive_to_verifiers(fx, _seats(test_role=[_attached(), _per_area()]))
    # each carried test ran exactly once, at the fixture's head, in the fixture repo
    assert sorted(c["path"] for c in spy.calls) == sorted([ATTACHED_TEST, PER_AREA_TEST])
    assert {c["head"] for c in spy.calls} == {fx.head}
    assert {os.path.realpath(c["repo_root"]) for c in spy.calls} == {os.path.realpath(str(fx.repo))}
    assert _status(fx.repo) == before == ""
    ok, state = RD.load_state(str(fx.session))
    assert ok and state["step"] == RD.P_VERIFIERS
    assert nxt["action"] == "dispatch-verifiers"
    expected = {ATTACHED_TITLE: ("failed", 1, ATTACHED_TEST), "Break-it: an idempotent charge": ("passed", 0, PER_AREA_TEST)}
    ledger = {e["title"]: e for e in state[SC.DISPOSITION_LEDGER_KEY]}
    staged = {f["title"]: f for f in state["_toVerify"]}
    emitted = {f["title"]: f for c in nxt["payload"]["clusters"] for f in c["findings"]}
    assert sorted(staged) == sorted(ledger) == sorted(emitted) == sorted(expected)
    for title, (outcome, code, path) in expected.items():
        for where in (staged[title], ledger[title], emitted[title]):
            assert where[break_it.RUN_FIELD]["outcome"] == outcome
            assert where[break_it.RUN_FIELD]["path"] == path
            (run,) = where[break_it.RUNS_FIELD]
            assert (run["status"], run["exitCode"], run["test"], run["commit"]) == ("ran", code, path, fx.head)
        assert "charged 2 times" in staged[title][break_it.RUN_FIELD]["output"] or outcome == "passed"
    # the passing test's finding is still staged: the run judged nothing
    assert "Break-it: an idempotent charge" in staged
    runs = state["rounds"]["1"]["breakItRuns"]
    assert sorted(r["outcome"] for r in runs) == ["failed", "passed"] and all(r["findingKey"] for r in runs)
    (decision,) = [d for d in state["decisions"] if d["kind"] == "break-it-run"]
    assert decision["detail"] == "2 run: 1 exited 0, 1 exited non-zero, 0 not run"


def test_d3_the_record_writers_account_carries_the_stamped_runs_in_the_record_shape(fx):
    _drive_to_verifiers(fx, _seats(test_role=[_attached(), _per_area()]))
    ok, state = RD.load_state(str(fx.session))
    assert ok
    rows = {f["title"]: f for f in rs._findings(state)}
    assert sorted(rows) == sorted([ATTACHED_TITLE, "Break-it: an idempotent charge"])
    for title, (status, code, path) in {ATTACHED_TITLE: ("ran", 1, ATTACHED_TEST),
                                        "Break-it: an idempotent charge": ("ran", 0, PER_AREA_TEST)}.items():
        runs = rows[title]["breakItRuns"]
        assert review_record._items_fault(runs, review_record._break_it_fault) is None
        (run,) = runs
        assert (run["status"], run["exitCode"], run["test"], run["commit"]) == (status, code, path, fx.head)
        assert run["changedWhy"] is None


# ---- D4 -----------------------------------------------------------------------------------------------------

def test_d4_fill_appends_a_run_the_scrub_changes_once_in_its_scrubbed_form():
    raw = {"test": "tests/test_a.py", "commit": "abc1234", "status": "ran", "exitCode": 1,
           "output": "token " + "sk-" + "a" * 48, "reason": None, "changedWhy": None}
    scrubbed = review_record._scrubbed(raw)
    assert scrubbed != raw  # the premise: the writer's scrub changes this run
    row = {"title": "t", "file": "a.py", "line": 3, "severity": "Important"}
    account = {"findings": [dict(row, breakItRuns=[raw, raw])]}
    rs._fill(account, [dict(row, breakItRuns=[])])
    assert account["findings"][0]["breakItRuns"] == [scrubbed]


# ---- F1 -----------------------------------------------------------------------------------------------------

FORGED = {"outcome": "failed", "output": "forged", "path": CHARGE_PATH}
FORGED_RUNS = [{"test": "forged.py", "commit": "x", "status": "ran", "exitCode": 1, "output": "forged",
                "reason": None, "changedWhy": None}]


def _forged(finding):
    return dict(finding, **{break_it.RUN_FIELD: dict(FORGED), break_it.RUNS_FIELD: list(FORGED_RUNS)})


def test_f1_compile_strips_a_seat_supplied_stamp_unless_the_driver_stamped_the_finding(fx):
    diff = fx.diff
    finding = _forged(_ordinary())
    (compiled,), _ = RD.mechanical_compile([finding], diff)
    assert break_it.RUN_FIELD not in compiled and break_it.RUNS_FIELD not in compiled
    # being scope-exempt is no stamp
    (compiled,), _ = RD.mechanical_compile([finding], diff, scope_exempt={id(finding)})
    assert break_it.RUN_FIELD not in compiled and break_it.RUNS_FIELD not in compiled
    # the driver's own stamped copy keeps both (the positive control)
    (compiled,), _ = RD.mechanical_compile([finding], diff, stamped={id(finding)})
    assert compiled[break_it.RUN_FIELD] == FORGED and compiled[break_it.RUNS_FIELD] == FORGED_RUNS


def test_f1_a_forged_stamp_on_any_seat_never_reaches_staging(fx, spy):
    plain = _forged(_ordinary(title="A forged stamp on a code reviewer's finding"))
    no_block = _forged(_ordinary(title="A forged stamp on the test role's blockless finding", line=3))
    attached = _forged(_attached())
    fx.fold_panel(code_reviewer=[plain], test_role=[no_block, attached])
    assert "breakItRun" not in fx.staged(plain["title"]) and "breakItRuns" not in fx.staged(plain["title"])
    assert break_it.RUN_FIELD not in fx.staged(no_block["title"])
    assert break_it.RUNS_FIELD not in fx.staged(no_block["title"])
    # the test role's attached finding carries the driver's own stamp, not the forged one
    stamp = fx.staged(ATTACHED_TITLE)[break_it.RUN_FIELD]
    assert stamp["path"] == ATTACHED_TEST and stamp["output"] != "forged" and stamp["head"] == fx.head
    (run,) = fx.staged(ATTACHED_TITLE)[break_it.RUNS_FIELD]
    assert run["test"] == ATTACHED_TEST and run["output"] != "forged"


# ---- F2 -----------------------------------------------------------------------------------------------------

def test_f2_an_attached_block_on_another_seat_is_never_run(fx, spy):
    fx.fold_panel(code_reviewer=[_attached()])
    assert spy.calls == []
    assert all(ATTACHED_TITLE not in offered for offered in spy.offered)
    assert "breakItRuns" not in fx.round_record
    staged = fx.staged(ATTACHED_TITLE)
    assert break_it.RUN_FIELD not in staged and break_it.RUNS_FIELD not in staged


# ---- F3 -----------------------------------------------------------------------------------------------------

def test_f3_a_passed_run_keeps_its_finding_stamped(fx, spy):
    fx.fold_panel(test_role=[_attached(_TEST_PASSING), _per_area()])
    assert len(spy.calls) == 2
    for title in (ATTACHED_TITLE, "Break-it: an idempotent charge"):
        staged = fx.staged(title)
        assert staged[break_it.RUN_FIELD]["outcome"] == "passed"
        (run,) = staged[break_it.RUNS_FIELD]
        assert (run["status"], run["exitCode"]) == ("ran", 0)
    runs = fx.round_record["breakItRuns"]
    assert [r["outcome"] for r in runs] == ["passed", "passed"]
    assert [r["findingKey"] for r in runs] == [fx.staged(r["title"])[SC.FINDING_KEY_FIELD] for r in runs]
    assert not fx.round_record.get("compileDrops")


# ---- F7 -----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("ordinary_seat", ["code_reviewer", "test_role_plain"])
def test_f7_a_same_anchor_merge_an_ordinary_finding_wins_keeps_the_attached_test(fx, ordinary_seat):
    ordinary = _ordinary()
    if ordinary_seat == "code_reviewer":
        fx.fold_panel(code_reviewer=[ordinary], test_role=[_attached()])
    else:
        fx.fold_panel(test_role=[ordinary, _attached()])
    (staged,) = [f for f in fx.state["_toVerify"] if f["title"] == ATTACHED_TITLE]
    assert staged["severity"] == "Critical"  # the ordinary finding won the base
    assert staged["suggestion"] == _block(ATTACHED_TEST, _TEST_FAILING)
    assert staged[break_it.RUN_FIELD]["outcome"] == "failed"
    assert staged[break_it.RUN_FIELD]["path"] == ATTACHED_TEST
    (run,) = staged[break_it.RUNS_FIELD]
    assert (run["status"], run["exitCode"], run["test"]) == ("ran", 1, ATTACHED_TEST)
    (entry,) = fx.round_record["breakItRuns"]
    assert entry["findingKey"] == staged[SC.FINDING_KEY_FIELD]
    assert "supersededAtCompile" not in entry and "droppedAtCompile" not in entry


# ---- the rest of the contract -------------------------------------------------------------------------------

def test_carried_block_reads_both_kinds_and_carries_test_follows_it():
    attached, per_area = _attached(), _per_area()
    block, kind = break_it.carried_block(attached)
    assert kind == "attached" and block["path"] == ATTACHED_TEST
    assert block["sha256"] == hashlib.sha256(_TEST_FAILING.encode()).hexdigest()
    assert break_it.carried_block(per_area)[1] == "per-area"
    for other in (_ordinary(), _attached(suggestion="not a block"), "not a dict", None,
                  _per_area(suggestion="not a block")):
        assert break_it.carried_block(other) == (None, None)
    assert break_it.carries_test(attached) and break_it.carries_test(per_area)
    assert break_it.carries_test(_per_area(suggestion="not a block"))  # a per-area finding, malformed block and all
    assert not break_it.carries_test(_ordinary()) and not break_it.carries_test(_attached(suggestion="x"))


def test_record_run_maps_a_run_record_to_the_review_records_shape():
    def run(outcome, reason=None, code=None):
        return {"outcome": outcome, "reason": reason, "exitCode": code, "output": "out", "head": "h1",
                "path": "t/a.py"}

    mapped = break_it.record_run(run("passed", code=0))
    assert mapped == {"test": "t/a.py", "commit": "h1", "status": "ran", "exitCode": 0, "output": "out",
                      "reason": None, "changedWhy": None}
    assert break_it.record_run(run("failed", code=3), "fixed a typo")["changedWhy"] == "fixed a typo"
    timed = break_it.record_run(run("not-run", "timeout"))
    assert (timed["status"], timed["exitCode"], timed["reason"]) == ("timed-out", None, "timeout")
    setup = break_it.record_run(run("not-run", "module-not-found", 1))
    assert (setup["status"], setup["exitCode"], setup["reason"]) == ("ran", 1, "module-not-found")
    never = break_it.record_run(run("not-run", "path-mismatch"))
    assert (never["status"], never["exitCode"], never["reason"]) == ("not-started", None, "path-mismatch")
    # a run with no parsed block names the finding's file
    assert break_it.record_run(dict(run("not-run", "block-header-missing"), path=None, file="src/x.py"))["test"] == "src/x.py"
    for record in (run("passed", code=0), run("failed", code=3), run("not-run", "timeout"),
                   run("not-run", "module-not-found", 1), run("not-run", "path-mismatch")):
        assert review_record._break_it_fault(break_it.record_run(record)) is None


def test_an_attached_test_keeps_ordinary_scope_checking_and_has_no_path_rule(fx, spy):
    off_diff = _attached(file="elsewhere/x.py", line=9, title="An attached test on a file outside the change")
    fx.fold_panel(test_role=[off_diff, _attached()])
    # both ran (the path of the block is not the file), only the in-diff one reaches staging
    assert sorted(c["path"] for c in spy.calls) == [ATTACHED_TEST, ATTACHED_TEST]
    assert [f["title"] for f in fx.state["_toVerify"]] == [ATTACHED_TITLE]
    assert [d["reason"] for d in fx.round_record["compileDrops"]] == ["outside the round diff scope"]
    dropped = [r for r in fx.round_record["breakItRuns"] if r["title"] == off_diff["title"]]
    assert dropped[0]["droppedAtCompile"] is True and dropped[0]["findingKey"] is None


def test_a_scrub_altered_attached_block_is_stamped_not_run(fx, spy):
    content = "request = {'token': '" + "sk-" + "a" * 48 + "'}\nassert False\n"
    accepted, _ = engine_adapter._scrub_findings([_attached(content)])
    assert accepted[0]["suggestion"] != _attached(content)["suggestion"]
    assert accepted[0][break_it.REDACTED_FIELD] is True
    fx.fold_panel(test_role=[accepted[0]])
    assert spy.calls == []
    stamp = fx.staged(ATTACHED_TITLE)[break_it.RUN_FIELD]
    assert (stamp["outcome"], stamp["reason"]) == ("not-run", "suggestion-redacted")
    (run,) = fx.staged(ATTACHED_TITLE)[break_it.RUNS_FIELD]
    assert (run["status"], run["exitCode"]) == ("not-started", None)
    clean, _ = engine_adapter._scrub_findings([_attached()])
    assert break_it.REDACTED_FIELD not in clean[0]


def test_a_finding_that_carries_a_test_leaves_a_group_unmerged():
    def finding(fid, **extra):
        return dict({"id": fid, "file": "f%s.py" % fid, "line": 1, "title": "t%s" % fid,
                     "severity": "Important", "suggestion": "s-%s" % fid}, **extra)

    attached = finding("v0", suggestion=_block(ATTACHED_TEST, _TEST_FAILING), **{break_it.RUN_FIELD: {"outcome": "failed"}})
    out = verification.merge_and_rank([attached, finding("v1"), finding("v2")],
                                      [{"group_id": "g0", "member_ids": ["v0", "v1", "v2"]}])
    # v1 and v2 merge into one finding (the later of two equal severities represents them); v0 stays as it is
    assert sorted(f["id"] for f in out["findings"]) == ["v0", "v2"]
    assert [m["member_ids"] for m in out["merges"]] == [["v1", "v2"]]
    kept ={f["id"]: f for f in out["findings"]}
    assert kept["v0"]["suggestion"] == attached["suggestion"] and kept["v0"][break_it.RUN_FIELD] == {"outcome": "failed"}


def test_the_fixer_lint_exempts_an_attached_test_path_only_for_the_drivers_own_stamp():
    stamped = _attached(**{break_it.RUN_FIELD: {"outcome": "failed", "path": ATTACHED_TEST}})
    elsewhere = _attached(**{break_it.RUN_FIELD: {"outcome": "failed", "path": "tests/other.py"}})
    unstamped = _attached()
    per_area = _per_area(**{break_it.RUN_FIELD: {"outcome": "passed", "path": PER_AREA_TEST}})
    assert RD._fixer_create_items([stamped, elsewhere, unstamped, per_area, "x"]) == [ATTACHED_TEST, PER_AREA_TEST]


def test_a_requeued_attached_target_keeps_its_test_block_and_both_stamps():
    f = _attached(**{break_it.RUN_FIELD: {"outcome": "failed", "sha256": "x"}, break_it.RUNS_FIELD: list(FORGED_RUNS)})
    (row,) = RD._audit_targets({"fixBatch": [f]}, {}, {})
    assert row["suggestion"] == f["suggestion"] and row["body"] == f["body"]
    assert row[break_it.RUN_FIELD] == f[break_it.RUN_FIELD] and row[break_it.RUNS_FIELD] == f[break_it.RUNS_FIELD]


def test_a_fixed_attached_test_is_checked_kept_whether_its_run_passed_or_failed(fx):
    fx.fold_panel(test_role=[_attached(_TEST_PASSING)])
    key = fx.staged(ATTACHED_TITLE)[SC.FINDING_KEY_FIELD]
    RD._record_disposition(fx.state, key, "fixed", 1)
    fx.fix(ATTACHED_TEST, _TEST_PASSING)
    assert RD._break_it_kept_step(fx.state, fx.state["config"]) is False
    (row,) = fx.round_record["breakItKept"]
    assert (row["findingKey"], row["outcome"]) == (key, "kept")
    # the same finding fixed with its test left out of the change parks
    left_out = Fixture(fx.session.parent / "left-out")
    left_out.fold_panel(test_role=[_attached(_TEST_PASSING)])
    RD._record_disposition(left_out.state, left_out.staged(ATTACHED_TITLE)[SC.FINDING_KEY_FIELD], "fixed", 1)
    left_out.fix()
    assert RD._break_it_kept_step(left_out.state, left_out.state["config"]) is True
    assert "missing" in left_out.state["certification"]["reason"]


def test_a_changed_tests_later_run_is_the_one_the_kept_check_holds_the_commit_to(fx):
    fx.fold_panel(test_role=[_attached()])
    key = fx.staged(ATTACHED_TITLE)[SC.FINDING_KEY_FIELD]
    changed = _TEST_PASSING + "# a small change\n"
    first = fx.round_record["breakItRuns"][0]
    later = dict(first, sha256=hashlib.sha256(changed.encode()).hexdigest(), content=changed, outcome="passed",
                 exitCode=0)
    fx.round_record["breakItRuns"].append(later)
    RD._record_disposition(fx.state, key, "fixed", 1)
    fx.fix(ATTACHED_TEST, changed)
    assert RD._break_it_kept_step(fx.state, fx.state["config"]) is False
    (row,) = fx.round_record["breakItKept"]
    assert (row["findingKey"], row["outcome"]) == (key, "kept")


# ---- break-it-change ----------------------------------------------------------------------------------------

_SYNTAX_ERROR = "def test_idempotent_charge(:\n    pass\n"
_CHARGE_FIXED = (
    "def charge_with_retry(ledger, amount, timeouts=1):\n"
    "    if not ledger:\n"
    "        ledger.append(amount)\n"
    "    return ledger\n")
WHY = "the first draft had a syntax error"
VENDORS = ["claude", "codex"]
NOT_AT_VERIFIERS = "break-it-change-not-at-verifiers"


def _respond(seats, fixer=None):
    """Answer every phase of a full review: the test role's seat returns ``seats`` in round 1, every verifier confirms,
    every audit discharges, and ``fixer`` (given the fixer order's payload) makes the fix."""
    base = TRD._responder(vendors=VENDORS)

    def respond(phase, payload, rnd):
        if phase == RD.P_PANEL and rnd == 1:
            return dict(base(phase, payload, rnd), seats=seats)
        if phase == RD.P_FIXER and fixer is not None:
            return fixer(payload)
        return base(phase, payload, rnd)

    return respond


def _fixer(fx_):
    """The fixer: writes each test block its batch carries byte for byte, fixes the code, and commits both."""
    def fix(payload):
        for row in payload["batch"]:
            block, _ = break_it.carried_block(row)
            if block is not None:
                _write(fx_.repo, block["path"], block["content"])
        _write(fx_.repo, CHARGE_PATH, _CHARGE_FIXED)
        _commit(fx_.repo, "fix the retry and keep the test")
        return {"fixes": [], "changedSubjects": ["Code"]}

    return fix


def _content_file(tmp_path, content, name="changed.py"):
    path = tmp_path / name
    path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
    return str(path)


def _verdicts(nxt):
    return {"verdicts": [{"id": i, "verdict": "CONFIRMED", "evidence": "ran", "reason": "ran"}
                         for c in nxt["payload"]["clusters"] for i in c["ids"]]}


def _assert_stale_verifier_result_refused(session, old, fresh):
    """A verifier result for the superseded attempt is refused whichever state hash it carries, and neither refusal
    moves the state."""
    before = TRD._state_bytes(session)
    with_fresh_hash = RD.cmd_submit(session, old["phase"], old["attempt"], fresh["expectedStateHash"], _verdicts(old))
    assert with_fresh_hash["ok"] is False and "echo does not match" in with_fresh_hash["reason"], with_fresh_hash
    with_old_hash = RD.cmd_submit(session, old["phase"], old["attempt"], old["expectedStateHash"], _verdicts(old))
    assert with_old_hash["ok"] is False, with_old_hash
    assert TRD._state_bytes(session) == before


def _assert_refused(session, token, ref, content_file, why):
    """The verb refuses with ``token`` alone in its answer, journals the refusal, and leaves the state file as it was."""
    before = TRD._state_bytes(session)
    assert RD.cmd_break_it_change(session, ref, content_file, why) == {"ok": False, "reason": token}
    assert TRD._state_bytes(session) == before
    row = RD.read_journal(session)[-1]
    assert (row["cmd"], row["outcome"], row["reason"]) == ("break-it-change", "refused", token)


def test_d2_a_syntax_error_in_a_per_area_test_is_changed_in_place_and_the_verifiers_are_re_ordered(fx, tmp_path, capsys):
    session = str(fx.session)
    old = _drive_to_verifiers(fx, _seats(test_role=[_per_area(_SYNTAX_ERROR)]))
    ok, state = RD.load_state(session)
    assert ok
    (staged,) = state["_toVerify"]
    key = staged[SC.FINDING_KEY_FIELD]
    assert staged[break_it.RUN_FIELD]["outcome"] == "failed" and "SyntaxError" in staged[break_it.RUN_FIELD]["output"]
    (first,) = staged[break_it.RUNS_FIELD]
    assert (first["status"], first["exitCode"], first["changedWhy"]) == ("ran", 1, None)
    assert state["pending"]["attempt"] == old["attempt"]
    corrected = _content_file(tmp_path, _TEST_FAILING)
    argv = ["break-it-change", "--session-dir", session, "--finding", "v0", "--content-file", corrected, "--why", WHY]
    assert RD.main(argv) == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["ok"] is True and out["finding"] == "v0"
    assert out["run"]["outcome"] == "failed" and "charged 2 times" in out["run"]["output"]
    assert out["run"]["sha256"] == hashlib.sha256(_TEST_FAILING.encode()).hexdigest()
    ok, state = RD.load_state(session)
    assert ok
    (staged,) = state["_toVerify"]
    (entry,) = state[SC.DISPOSITION_LEDGER_KEY]
    want = _block(PER_AREA_TEST, _TEST_FAILING)
    for where in (staged, entry):
        assert where["suggestion"] == want
        assert break_it.carried_block(where)[0]["content"] == _TEST_FAILING
        assert where[break_it.RUN_FIELD] == out["run"]
        before_change, after_change = where[break_it.RUNS_FIELD]
        assert (before_change["exitCode"], before_change["changedWhy"]) == (1, None)
        assert "SyntaxError" in before_change["output"]
        assert (after_change["status"], after_change["exitCode"], after_change["changedWhy"],
                after_change["test"]) == ("ran", 1, WHY, PER_AREA_TEST)
        assert "charged 2 times" in after_change["output"]
    first_entry, second_entry = state["rounds"]["1"]["breakItRuns"]
    assert first_entry.get("changedWhy") is None and first_entry["sha256"] == hashlib.sha256(_SYNTAX_ERROR.encode()).hexdigest()
    assert (second_entry["changedWhy"], second_entry["findingKey"], second_entry["title"], second_entry["file"],
            second_entry["outcome"]) == (WHY, key, staged["title"], PER_AREA_TEST, "failed")
    assert second_entry["sha256"] == hashlib.sha256(_TEST_FAILING.encode()).hexdigest()
    (decision,) = [d for d in state["decisions"] if d["kind"] == "break-it-change"]
    assert key in decision["detail"] and "failed" in decision["detail"]
    row = RD.read_journal(session)[-1]
    assert (row["cmd"], row["outcome"], row["supersededAttempt"]) == ("break-it-change", "changed", old["attempt"])
    assert state["pending"] is None
    # the next `next` orders the verifiers again, from the changed copies, at an attempt of its own
    fresh = RD.cmd_next(session)
    assert fresh["ok"] and fresh["action"] == RD.P_VERIFIERS
    (carried,) = [f for c in fresh["payload"]["clusters"] for f in c["findings"]]
    assert carried["suggestion"] == want
    assert [r["changedWhy"] for r in carried[break_it.RUNS_FIELD]] == [None, WHY]
    _assert_stale_verifier_result_refused(session, old, fresh)
    assert fresh["attempt"] > old["attempt"]
    assert RD.cmd_submit(session, fresh["phase"], fresh["attempt"], fresh["expectedStateHash"], _verdicts(fresh))["ok"]


def test_d2_the_changed_test_is_the_one_the_fixer_commits_and_the_kept_check_holds(fx, tmp_path):
    session = str(fx.session)
    respond = _respond(_seats(test_role=[_per_area(_SYNTAX_ERROR)]), _fixer(fx))
    _drive_to_verifiers(fx, None, respond)
    assert RD.cmd_break_it_change(session, "v0", _content_file(tmp_path, _TEST_FAILING), WHY)["ok"] is True
    payload = TRD._drive_cli(session, fx.config, respond)
    ok, state = RD.load_state(session)
    assert ok
    key = state["rounds"]["1"]["breakItRuns"][-1]["findingKey"]
    (kept,) = [r for rec in state["rounds"].values() for r in rec.get("breakItKept") or []]
    assert (kept["findingKey"], kept["path"], kept["outcome"]) == (key, PER_AREA_TEST, break_it.KEPT)
    assert _git(fx.repo, "show", "HEAD:" + PER_AREA_TEST) == _TEST_FAILING.strip()
    assert payload["verdict"] == "converged", payload
    assert not [d for d in state["decisions"] if d["kind"] == "cannot-certify"]


def test_f6_a_verifier_result_for_the_superseded_attempt_is_refused(fx, tmp_path):
    session = str(fx.session)
    old = _drive_to_verifiers(fx, _seats(test_role=[_attached()]))
    assert RD.cmd_break_it_change(session, "v0", _content_file(tmp_path, _TEST_PASSING), WHY)["ok"] is True
    fresh = RD.cmd_next(session)
    assert fresh["ok"] and fresh["action"] == RD.P_VERIFIERS
    _assert_stale_verifier_result_refused(session, old, fresh)
    assert fresh["attempt"] != old["attempt"]


@pytest.mark.parametrize("step", [RD.P_PANEL, RD.P_FIXER])
def test_f4_the_verb_at_any_other_step_is_refused_and_leaves_the_state_alone(fx, tmp_path, step):
    session = str(fx.session)
    TRD._drive_to_phase(session, fx.config, _respond(_seats(test_role=[_attached()]), _fixer(fx)), step)
    ok, state = RD.load_state(session)
    assert ok and state["step"] == step != RD.P_VERIFIERS
    _assert_refused(session, NOT_AT_VERIFIERS, "v0", _content_file(tmp_path, _TEST_PASSING), WHY)


@pytest.fixture
def at_verifiers(fx):
    """A session at the verifiers' step with an attached failing test staged as `v0`; returns its folder."""
    _drive_to_verifiers(fx, _seats(test_role=[_attached()]))
    return str(fx.session)


@pytest.mark.parametrize("ref", ["v9", "not-a-finding-key", ""])
def test_f5_a_finding_the_staged_set_does_not_hold_is_refused(at_verifiers, tmp_path, ref):
    _assert_refused(at_verifiers, "break-it-change-finding-unknown", ref, _content_file(tmp_path, _TEST_PASSING), WHY)


@pytest.mark.parametrize("finding", [_attached, _ordinary], ids=["an attached block no run stamped", "an ordinary finding"])
def test_f5_a_finding_with_no_driver_run_of_a_test_is_refused(fx, tmp_path, finding):
    _drive_to_verifiers(fx, _seats(code_reviewer=[finding()]))
    _assert_refused(str(fx.session), "break-it-change-no-test", "v0", _content_file(tmp_path, _TEST_PASSING), WHY)


@pytest.mark.parametrize("why", ["", "   \n\t"])
def test_f5_an_absent_or_blank_reason_is_refused(at_verifiers, tmp_path, why):
    _assert_refused(at_verifiers, "break-it-change-why-missing", "v0", _content_file(tmp_path, _TEST_PASSING), why)


@pytest.mark.parametrize("content", [None, b"\xff\xfe not utf-8"], ids=["absent file", "not UTF-8"])
def test_f5_content_that_cannot_be_read_as_utf8_text_is_refused(at_verifiers, tmp_path, content):
    path = str(tmp_path / "absent.py") if content is None else _content_file(tmp_path, content)
    _assert_refused(at_verifiers, "break-it-change-content-unreadable", "v0", path, WHY)


def test_f5_content_equal_to_the_carried_block_is_refused(at_verifiers, tmp_path):
    _assert_refused(at_verifiers, "break-it-change-content-unchanged", "v0", _content_file(tmp_path, _TEST_FAILING), WHY)
