"""#2463: a kept break-it test found in a higher layer of the stack counts as kept.

The kept check (`round_driver._break_it_kept_step`) reads a fixed break-it test missing from the reviewed
layer's head as `missing` / `not-in-head`. When the reviewed PR is a layer of a stack, the layers above it
are searched, in order, each checked out clean; the first one that holds the test unchanged and passing makes
the row `kept`. Every other case keeps today's row, and a failed stack read credits nothing.
"""
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import break_it  # noqa: E402
import break_it_layers  # noqa: E402
import dependency_links  # noqa: E402
import review_record_session as rs  # noqa: E402
import round_driver as RD  # noqa: E402
import stack_check  # noqa: E402
from test_break_it_js_dependencies_2034 import (  # noqa: E402
    NPM_RUN as JS_NPM_RUN, PACKAGE as JS_PACKAGE, PASSING as JS_PASSING, TEST_PATH as JS_TEST_PATH, _install_fake)
from test_review_record_session import Fake, Session, extras  # noqa: E402

PY = shlex.quote(sys.executable)
# pinned condition: every fixture git call ignores the user's and the system's git config and passes its
# commit identity inline; production timing or environment shape the pin makes unobservable: a host whose
# global config rewrites hooks, signing or default branches (the code under test reads the repo with the
# caller's own environment, so this pin covers only the fixture's own commits).
# inherited GIT_* routing (GIT_INDEX_FILE, GIT_DIR, GIT_WORK_TREE...) captured at collection would send a
# fixture's git call to the caller's repository, so none of it is kept; the two pins are the only GIT_* kept
_GIT_ENV = {**{k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
_ID = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]

TEST_PATH = "tests/test_charge_once.py"
CHARGE_PATH = "src/payments/charge.py"
_PASSING = "assert 1 + 1 == 2\n"
_OTHER = "assert 2 + 2 == 4\n"
GHOST = "a" * 40


def _git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, text=True, env=_GIT_ENV)
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


def _record(body=_PASSING):
    return {"path": TEST_PATH, "command": "%s %s" % (PY, TEST_PATH),
            "sha256": hashlib.sha256(body.encode()).hexdigest(), "content": body}


def _worktrees(repo):
    return [line for line in _git(repo, "worktree", "list", "--porcelain").splitlines()
            if line.startswith("worktree ")]


class Stack:
    """base <- layer-2 (reviewed, checked out) <- layer-3 (no test) <- layer-4 (the test, `layer4_body`)."""

    def __init__(self, tmp_path, layer4_body=_PASSING, base_files=None, layer4_files=None):
        tmp_path.mkdir(parents=True, exist_ok=True)
        self.tmp = tmp_path
        self.repo = tmp_path / "repo"
        self.repo.mkdir()
        _git(self.repo, "init", "-q")
        _git(self.repo, "symbolic-ref", "HEAD", "refs/heads/layer-2")
        _write(self.repo, "README.md", "fixture\n")
        _write(self.repo, ".gitignore", ".venv/\n")
        for rel, text in (base_files or {}).items():
            _write(self.repo, rel, text)
        self.base = _commit(self.repo, "base")
        _write(self.repo, "src/lower.py", "LOWER = 1\n")
        self.layer2 = _commit(self.repo, "layer 2")
        self.origin = tmp_path / "origin.git"
        _git(tmp_path, "clone", "-q", "--bare", str(self.repo), str(self.origin))
        _git(self.repo, "remote", "add", "origin", str(self.origin))
        _git(self.repo, "checkout", "-q", "-b", "layer-3")
        _write(self.repo, "src/three.py", "THREE = 3\n")
        self.layer3 = _commit(self.repo, "layer 3")
        _git(self.repo, "checkout", "-q", "-b", "layer-4")
        if layer4_body is None:
            _write(self.repo, "src/four.py", "FOUR = 4\n")
        else:
            _write(self.repo, TEST_PATH, layer4_body)
        for rel, text in (layer4_files or {}).items():
            _write(self.repo, rel, text)
        self.layer4 = _commit(self.repo, "layer 4")
        _git(self.repo, "checkout", "-q", "layer-2")
        self.scratch = tmp_path / "scratch"
        self.scratch.mkdir()

    @property
    def layers(self):
        return [{"position": 3, "number": 103, "headRefName": "layer-3", "headRefOid": self.layer3},
                {"position": 4, "number": 104, "headRefName": "layer-4", "headRefOid": self.layer4}]

    def search(self, layers=GHOST, record=None, interpreter=GHOST):
        return break_it_layers.check_kept_in_layers(
            str(self.repo), self.base, self.layers if layers is GHOST else layers,
            _record() if record is None else record,
            interpreter=(break_it.resolve_interpreter({"verifyCommand": "%s -c pass" % PY})
                         if interpreter is GHOST else interpreter),
            scratch=str(self.scratch))


@pytest.fixture
def stack(tmp_path):
    return Stack(tmp_path)


def test_1_a_test_held_by_a_higher_layer_is_found_with_the_real_runner_and_nothing_is_left_behind(stack):
    own = break_it.check_kept(str(stack.repo), stack.base, stack.layer2, _record(), scratch=str(stack.scratch))
    assert (own["outcome"], own["reason"]) == (break_it.KEPT_MISSING, "not-in-head"), own
    got = stack.search()
    assert got["read"] == "ok" and got["reason"] is None, got
    assert got["foundIn"] == {"position": 4, "pr": 104, "branch": "layer-4", "commit": stack.layer4}, got
    assert got["result"]["outcome"] == break_it.KEPT, got
    assert [s["position"] for s in got["searched"]] == [3, 4]
    assert [s["outcome"] for s in got["searched"]] == [break_it.KEPT_MISSING, break_it.KEPT]
    assert _git(stack.repo, "rev-parse", "HEAD") == stack.layer2
    assert _git(stack.repo, "status", "--porcelain") == ""
    assert len(_worktrees(stack.repo)) == 1, _worktrees(stack.repo)


def test_2_no_layer_holding_the_test_reads_ok_and_not_found(tmp_path):
    s = Stack(tmp_path, layer4_body=None)
    got = s.search()
    assert got["read"] == "ok" and got["foundIn"] is None and got["result"] is None, got
    assert len(got["searched"]) == 2
    assert len(_worktrees(s.repo)) == 1


def test_3_a_higher_layer_file_whose_body_differs_is_not_credited(tmp_path):
    s = Stack(tmp_path, layer4_body=_OTHER)
    got = s.search()
    assert got["read"] == "ok" and got["foundIn"] is None, got
    assert break_it.KEPT not in [row["outcome"] for row in got["searched"]], got


def test_4_e2_a_layer_head_that_exists_nowhere_fails_the_read(stack):
    layers = [{"position": 3, "number": 103, "headRefName": "no-such-branch", "headRefOid": GHOST}]
    got = stack.search(layers)
    assert got["read"] == "failed" and got["reason"] == "layer-head-unreadable", got
    assert got["foundIn"] is None


def test_5_e5_an_unresolved_layer_ends_the_search_though_a_later_layer_holds_a_passing_copy(stack, monkeypatch):
    real, calls = break_it.check_kept, []

    def flaky(*args, **kwargs):
        calls.append(args[2])
        if len(calls) == 1:
            return {"path": TEST_PATH, "outcome": break_it.KEPT_UNRESOLVED, "reason": "ls-tree-failed", "run": None}
        return real(*args, **kwargs)

    monkeypatch.setattr(break_it, "check_kept", flaky)
    got = stack.search()
    assert got["read"] == "failed" and got["reason"].startswith("layer-read-failed:"), got
    assert got["reason"] == "layer-read-failed:ls-tree-failed"
    assert got["foundIn"] is None and calls == [stack.layer3], (got, calls)
    assert len(_worktrees(stack.repo)) == 1


@pytest.mark.parametrize("layers", [
    "not-a-list", None, ["x"], [None],
    [{"position": 3, "number": 103, "headRefName": "layer-3", "headRefOid": "abc"}],
    [{"position": 3, "number": 103, "headRefName": "-layer-3", "headRefOid": "a" * 40}],
    [{"position": 3, "number": 103, "headRefName": "", "headRefOid": "a" * 40}],
    [{"position": True, "number": 103, "headRefName": "layer-3", "headRefOid": "a" * 40}],
    [{"position": 3, "number": "103", "headRefName": "layer-3", "headRefOid": "a" * 40}],
    [{"position": 3, "number": 103, "headRefName": "layer-3", "headRefOid": 7}],
])
def test_6_e1_e7_malformed_layers_fail_the_read(stack, layers):
    got = stack.search(layers)
    assert got["read"] == "failed" and got["reason"] == "layer-malformed", got


def test_6_e6_an_exception_inside_the_search_is_a_failed_read_and_nothing_is_raised(stack, monkeypatch):
    def boom(*args, **kwargs):
        raise subprocess.TimeoutExpired("git", 1)

    monkeypatch.setattr(break_it, "_git", boom)
    got = stack.search()
    assert got["read"] == "failed" and got["reason"] == "layer-search-error", got
    assert got["foundIn"] is None


def test_6_e3_e4_an_unresolved_scratch_and_a_failed_checkout_fail_the_read(stack, monkeypatch):
    monkeypatch.setattr(break_it, "_scratch_folder", lambda root, scratch: (None, "scratch-unresolved"))
    got = stack.search()
    assert got["read"] == "failed" and got["reason"] == "scratch-unresolved", got
    monkeypatch.undo()
    real = break_it._git

    def no_worktree(repo, *args):
        if args[:2] == ("worktree", "add"):
            return subprocess.CompletedProcess(args, 1, b"", b"refused")
        return real(repo, *args)

    monkeypatch.setattr(break_it, "_git", no_worktree)
    got = stack.search()
    assert got["read"] == "failed" and got["reason"] == "layer-checkout-failed", got


def test_7_a_layer_commit_absent_locally_but_on_origin_is_fetched_and_found(stack, tmp_path):
    other = tmp_path / "other"
    _git(tmp_path, "clone", "-q", str(stack.origin), str(other))
    _git(other, "checkout", "-q", "-b", "layer-5")
    _write(other, TEST_PATH, _PASSING)
    oid = _commit(other, "layer 5")
    _git(other, "push", "-q", "origin", "layer-5")
    assert subprocess.run(["git", "-C", str(stack.repo), "cat-file", "-e", oid + "^{commit}"],
                          env=_GIT_ENV, capture_output=True).returncode != 0
    got = stack.search([{"position": 5, "number": 105, "headRefName": "layer-5", "headRefOid": oid}])
    assert got["read"] == "ok", got
    assert got["foundIn"] == {"position": 5, "pr": 105, "branch": "layer-5", "commit": oid}, got


def _membership(position=2):
    def member(pos):
        return {"position": pos, "number": 100 + pos, "headRefName": "layer-%d" % pos,
                "headRefOid": "%x" % pos * 40, "state": "OPEN"}

    return {"ok": True, "reason": None, "detail": None, "repo": "owner/name", "pr": 100 + position,
            "stack": {"number": 9}, "queried": {"number": 100 + position, "position": position},
            "members": [member(4), member(1), member(2), member(3)], "pages": 1}


def _refusal(reason):
    return {"ok": False, "reason": reason, "detail": "d", "repo": "owner/name", "pr": 102, "stack": None,
            "queried": None, "members": [], "pages": 0}


def _session(tmp_path, **meta):
    d = tmp_path / "sess"
    d.mkdir(exist_ok=True)
    (d / RD.round_records.META_FILE).write_text(json.dumps(meta))
    return str(d)


PR_META = {"mode": "pr", "pr": 102, "repo": "owner/name"}


def test_8_stack_layers_above_reads_only_a_linked_pr_sessions_higher_members(tmp_path, monkeypatch):
    calls = []

    def seam(pr, repo):
        calls.append((pr, repo))
        return seam.answer

    monkeypatch.setattr(RD, "_read_stack_membership", seam)
    seam.answer = _membership()
    assert RD._stack_layers_above(None) == (None, None)
    assert RD._stack_layers_above(_session(tmp_path, mode="branch", pr=102, repo="owner/name")) == (None, None)
    assert RD._stack_layers_above(_session(tmp_path, mode="pr", repo="owner/name")) == (None, None)
    assert RD._stack_layers_above(_session(tmp_path, mode="pr", pr=True, repo="owner/name")) == (None, None)
    assert RD._stack_layers_above(_session(tmp_path, mode="pr", pr=102, repo="not a repo")) == (None, None)
    assert calls == []
    layers, failure = RD._stack_layers_above(_session(tmp_path, **PR_META))
    assert failure is None and calls == [(102, "owner/name")]
    assert [layer["position"] for layer in layers] == [3, 4], layers
    assert layers[0] == {"position": 3, "number": 103, "headRefName": "layer-3", "headRefOid": "3" * 40}
    seam.answer = _refusal(stack_check.REASON_NOT_LINKED)
    assert RD._stack_layers_above(_session(tmp_path, **PR_META)) == (None, None)
    seam.answer = _refusal(stack_check.REASON_STACK_UNREADABLE)
    assert RD._stack_layers_above(_session(tmp_path, **PR_META)) == (None, "stack-unreadable")
    seam.answer = "garbage"
    assert RD._stack_layers_above(_session(tmp_path, **PR_META)) == (None, "stack-unreadable")
    seam.answer = dict(_membership(), members="x")
    assert RD._stack_layers_above(_session(tmp_path, **PR_META)) == (None, "stack-unreadable")
    seam.answer = dict(_membership(), queried={"position": "2"})
    assert RD._stack_layers_above(_session(tmp_path, **PR_META)) == (None, "stack-unreadable")
    seam.answer = dict(_membership(position=4))
    assert RD._stack_layers_above(_session(tmp_path, **PR_META)) == ([], None)

    def raises(pr, repo):
        raise OSError("gh missing")

    monkeypatch.setattr(RD, "_read_stack_membership", raises)
    assert RD._stack_layers_above(_session(tmp_path, **PR_META)) == (None, "stack-read-error")


def test_8b_a_session_whose_mode_the_resolver_cannot_resolve_is_not_a_stack_layer(tmp_path, monkeypatch):
    # e1/e2: an absent or invalid mode resolves to the fail-closed default "pr" but unresolved — it must not search
    calls = []

    def seam(pr, repo):
        calls.append((pr, repo))
        return _membership()

    monkeypatch.setattr(RD, "_read_stack_membership", seam)
    assert RD._stack_layers_above(_session(tmp_path, mode="bogus", pr=102, repo="owner/name")) == (None, None)
    assert RD._stack_layers_above(_session(tmp_path, pr=102, repo="owner/name")) == (None, None)
    assert calls == []
    layers, failure = RD._stack_layers_above(_session(tmp_path, **PR_META))
    assert failure is None and calls == [(102, "owner/name")] and [layer["position"] for layer in layers] == [3, 4]


# --- end to end through the kept step -----------------------------------------------------------------

_CHARGE_RETRYING = (
    "def charge_with_retry(ledger, amount, timeouts=1):\n"
    "    for _ in range(timeouts + 1):\n"
    "        ledger.append(amount)\n"
    "    return ledger\n")
_CHARGE_IDEMPOTENT = (
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


def _block(path, content):
    return "break-it-test v1\npath: %s\nrun: %s %s\n---\n%s" % (path, PY, shlex.quote(path), content)


def _finding():
    return {"title": "Break-it: a retried charge runs twice", "file": TEST_PATH, "line": 1,
            "severity": "Important", "dimension": "Test", "taxonomy": break_it.TAXONOMY,
            "body": "payments risk area: the retry resends the charge",
            "consequence": "the customer is charged twice", "confidence": "High",
            "suggestion": _block(TEST_PATH, _TEST_FAILING)}


class World:
    """The reviewed layer (HEAD, detached) holds no test; the fix and its test sit on branch `layer-3`."""

    def __init__(self, tmp_path, fixed=True):
        self.repo = tmp_path / "repo"
        self.repo.mkdir()
        _git(self.repo, "init", "-q")
        _write(self.repo, "README.md", "fixture\n")
        self.base = _commit(self.repo, "base")
        _write(self.repo, CHARGE_PATH, _CHARGE_RETRYING)
        self.head = _commit(self.repo, "retry the charge")
        diff = _git(self.repo, "diff", self.base, self.head) + "\n"
        self.session = tmp_path / "session"
        self.session.mkdir()
        self.config = {"leg": "code", "vendors": ["claude", "codex"], "diff": diff, "fixerVendor": "claude",
                       "repoRoot": str(self.repo), "baseRef": self.base, "verifyCommand": "%s -c pass" % PY}
        self.state = RD.new_state(self.config)
        self.state["reviewedDiff"] = diff
        seats = {d: {"findings": []} for d in RD.DIMENSIONS}
        seats["test-role"] = {"findings": [_finding()]}
        RD._fold(self.state, self.state["config"], RD.P_PANEL, {"seats": seats}, session_dir=self.session_dir)
        (run,) = self.round_record["breakItRuns"]
        RD._record_disposition(self.state, run["findingKey"], "fixed", 1)
        _git(self.repo, "checkout", "-q", "-b", "layer-3")
        if fixed:
            _write(self.repo, CHARGE_PATH, _CHARGE_IDEMPOTENT)
        _write(self.repo, TEST_PATH, _TEST_FAILING)
        self.layer3 = _commit(self.repo, "fix the retry" if fixed else "add the test, leave the retry")
        _git(self.repo, "checkout", "-q", "--detach", self.head)
        meta = {"repoRoot": str(self.repo), "headSha": self.head}
        meta.update(PR_META)
        (self.session / RD.round_records.META_FILE).write_text(json.dumps(meta))

    @property
    def session_dir(self):
        return str(self.session)

    @property
    def round_record(self):
        return self.state["rounds"][str(self.state["round"])]

    def membership(self):
        out = _membership()
        out["members"] = [m for m in out["members"] if m["position"] != 4]
        for m in out["members"]:
            if m["position"] == 3:
                m["headRefOid"] = self.layer3

        return out

    def step(self):
        return RD._break_it_kept_step(self.state, self.state["config"], session_dir=self.session_dir)


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def test_9a_the_step_credits_a_copy_held_by_a_higher_layer_and_does_not_park(world, monkeypatch):
    monkeypatch.setattr(RD, "_read_stack_membership", lambda pr, repo: world.membership())
    assert world.step() is False, world.state.get("certification")
    (row,) = world.round_record["breakItKept"]
    assert (row["outcome"], row["reason"]) == (break_it.KEPT, "in-higher-layer"), row
    assert row["path"] == TEST_PATH and row["run"]["outcome"] == "passed", row
    assert row["stack"]["read"] == "ok"
    assert row["stack"]["foundIn"] == {"position": 3, "pr": 103, "branch": "layer-3", "commit": world.layer3}
    assert _git(world.repo, "rev-parse", "HEAD") == world.head
    assert len(_worktrees(world.repo)) == 1


def test_9b_a_pr_that_is_not_in_a_stack_parks_with_todays_row_and_no_stack_key(world, monkeypatch):
    monkeypatch.setattr(RD, "_read_stack_membership", lambda pr, repo: _refusal(stack_check.REASON_NOT_LINKED))
    assert world.step() is True
    (row,) = world.round_record["breakItKept"]
    assert (row["outcome"], row["reason"]) == (break_it.KEPT_MISSING, "not-in-head"), row
    assert "stack" not in row
    reason = world.state["certification"]["reason"]
    assert "not-in-head" in reason and "stack" not in reason, reason


def test_9c_a_stack_that_cannot_be_read_parks_names_why_and_credits_nothing(world, monkeypatch):
    monkeypatch.setattr(RD, "_read_stack_membership",
                        lambda pr, repo: _refusal(stack_check.REASON_STACK_UNREADABLE))
    assert world.step() is True
    (row,) = world.round_record["breakItKept"]
    assert (row["outcome"], row["reason"]) == (break_it.KEPT_MISSING, "not-in-head"), row
    assert row["stack"] == {"read": "failed", "reason": "stack-unreadable"}, row
    assert "the stack could not be read: stack-unreadable" in world.state["certification"]["reason"]


def test_12_a_changed_test_on_the_reviewed_head_never_reaches_the_stack_search(world, monkeypatch):
    # the reviewed head holds a file at the recorded path whose body differs (changed / sha256-differs) while a
    # higher layer (layer-3) still holds the original passing test: only missing / not-in-head may search the stack
    assert hashlib.sha256(_OTHER.encode()).hexdigest() != hashlib.sha256(_TEST_FAILING.encode()).hexdigest()
    _write(world.repo, TEST_PATH, _OTHER)
    changed_head = _commit(world.repo, "reviewed head with a different test body")
    assert changed_head != world.head
    meta = {"repoRoot": str(world.repo), "headSha": changed_head}
    meta.update(PR_META)
    (world.session / RD.round_records.META_FILE).write_text(json.dumps(meta))
    calls = []

    def seam(pr, repo):
        calls.append((pr, repo))
        return world.membership()

    monkeypatch.setattr(RD, "_read_stack_membership", seam)
    assert world.step() is True, world.state.get("certification")
    (row,) = world.round_record["breakItKept"]
    assert (row["outcome"], row["reason"]) == (break_it.KEPT_CHANGED, "sha256-differs"), row
    assert row["path"] == TEST_PATH, row
    assert "stack" not in row, row
    assert calls == [], calls


# --- the three negative cases, at the step level: identical on the base code and the head code --------------
# Each patches the seam with raising=False so the same test runs where the seam does not exist (the base code,
# which has no stack search) and reads the same park there as here.

def _layer_commit(world, files):
    """A real, locally present commit on top of the reviewed head, left as a loose commit (HEAD back on the head)."""
    for rel, text in files.items():
        _write(world.repo, rel, text)
    oid = _commit(world.repo, "layer above")
    _git(world.repo, "checkout", "-q", "--detach", world.head)
    return oid


def _members_above(world, oids):
    out = _membership()
    out["members"] = [m for m in out["members"] if m["position"] not in (3, 4)]
    for position, oid in zip((3, 4), oids):
        out["members"].append({"position": position, "number": 100 + position, "headRefName": "layer-%d" % position,
                               "headRefOid": oid, "state": "OPEN"})

    return out


def _assert_parks_not_in_head(world):
    assert world.step() is True
    (row,) = world.round_record["breakItKept"]
    assert (row["outcome"], row["reason"]) == ("missing", "not-in-head"), row
    assert "(missing: not-in-head)" in world.state["certification"]["reason"], world.state["certification"]
    assert "break-it test not kept: %s (missing: not-in-head)" % TEST_PATH in world.state["certification"]["reason"]


def test_11_n1_a_pr_that_is_not_a_stack_layer_parks_not_in_head(world, monkeypatch):
    monkeypatch.setattr(RD, "_read_stack_membership",
                        lambda pr, repo: _refusal(stack_check.REASON_NOT_LINKED), raising=False)
    _assert_parks_not_in_head(world)


def test_11_n2_a_stack_layer_with_no_layer_above_holding_the_test_parks_not_in_head(world, monkeypatch):
    # layer 3 and layer 4 are real local commits above the reviewed head; neither holds the test path
    layer3 = _layer_commit(world, {"src/three.py": "THREE = 3\n"})
    layer4 = _layer_commit(world, {"src/four.py": "FOUR = 4\n"})
    monkeypatch.setattr(RD, "_read_stack_membership",
                        lambda pr, repo: _members_above(world, [layer3, layer4]), raising=False)
    _assert_parks_not_in_head(world)


def test_11_n3_a_layer_above_holding_a_non_matching_body_parks_not_in_head(world, monkeypatch):
    # layer 3 holds no test; layer 4 (the top) holds a file at the test's path with a different body (other sha256)
    layer3 = _layer_commit(world, {"src/three.py": "THREE = 3\n"})
    layer4 = _layer_commit(world, {TEST_PATH: _OTHER})
    assert hashlib.sha256(_OTHER.encode()).hexdigest() != hashlib.sha256(_TEST_FAILING.encode()).hexdigest()
    monkeypatch.setattr(RD, "_read_stack_membership",
                        lambda pr, repo: _members_above(world, [layer3, layer4]), raising=False)
    _assert_parks_not_in_head(world)


# --- the review record --------------------------------------------------------------------------------

_FOUND = {"path": TEST_PATH, "outcome": "kept", "reason": "in-higher-layer", "run": None,
          "stack": {"read": "ok", "searched": [],
                    "foundIn": {"position": 4, "pr": 104, "branch": "layer-4", "commit": "c" * 40}}}
_FAILED = {"path": "tests/test_b.py", "outcome": "missing", "reason": "not-in-head", "run": None,
           "stack": {"read": "failed", "reason": "stack-unreadable"}}
_PLAIN = {"path": "tests/test_c.py", "outcome": "missing", "reason": "not-in-head", "run": None}


def test_10_the_record_names_the_layer_pr_branch_and_commit_or_the_failed_read(tmp_path):
    rounds = {"1": {"breakItKept": [_FOUND, _FAILED, _PLAIN, "junk"]}, "2": {}, "x": {"breakItKept": [_FOUND]}}
    assert rs._break_it_stack_checked(rounds) == [
        "Break-it test %s (round 1): kept in stack layer 4 (PR 104, branch layer-4) at ccccccc, "
        "not in the reviewed layer's head" % TEST_PATH,
        "Break-it test tests/test_b.py (round 1): the stack could not be read (stack-unreadable); "
        "the test reads not-in-head"]
    assert rs._break_it_stack_checked({"1": {"breakItKept": [_PLAIN]}}) == []
    # and the session assembly carries them
    s = Session(tmp_path, rounds={"1": {"breakItKept": [_FOUND, _FAILED, _PLAIN]}, "2": {}})
    s.seat("code-reviewer")
    account = rs.account_from_session(s.save(), extras(checked=["ran the suite"]), Fake().readers())
    lines = [c for c in account["checked"] if c.startswith("Break-it test")]
    assert len(lines) == 2 and "kept in stack layer 4 (PR 104, branch layer-4) at ccccccc" in lines[0], lines
    assert "the stack could not be read (stack-unreadable)" in lines[1], lines
    assert "ran the suite" in account["checked"]


# --- a layer checkout gets the reviewed checkout's installed dependencies (code-001) -------------------------
# bite-proof record wo_e_2463_layer_dependencies

_GATE_TEST = (
    "import os, sys\n"
    "sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))\n"
    "import charge_gate\n"
    "assert charge_gate.OPEN, 'the gate is closed'\n")
VENV = [".venv/bin/python"]


def _venv(repo):
    """An untracked, git-ignored .venv/bin/python that runs the current interpreter."""
    target = repo / ".venv" / "bin" / "python"
    target.parent.mkdir(parents=True)
    target.write_text("#!/bin/sh\nexec %s \"$@\"\n" % PY)
    target.chmod(0o755)


def _spy_check_kept(monkeypatch):
    calls, real = [], break_it.check_kept

    def spy(root, base, head, record, **kwargs):
        calls.append((root, head))
        return real(root, base, head, record, **kwargs)

    monkeypatch.setattr(break_it, "check_kept", spy)
    return calls


def _record_rows(searched, read="ok", reason=None):
    stack = {"read": read, "foundIn": None, "searched": searched}
    if reason:
        stack["reason"] = reason
    return {"1": {"breakItKept": [{"path": TEST_PATH, "outcome": "missing", "reason": "not-in-head", "run": None,
                                   "stack": stack}]}}


def test_t1_a_higher_layer_with_the_identical_test_that_fails_there_is_not_credited(tmp_path):
    # axis: only a kept result credits a layer (G13): the identical bytes failing at the layer read failing, not found
    s = Stack(tmp_path, layer4_body=_GATE_TEST, layer4_files={"src/charge_gate.py": "OPEN = False\n"})
    held = _git(s.repo, "show", "%s:%s" % (s.layer4, TEST_PATH))
    assert hashlib.sha256((held + "\n").encode()).hexdigest() == _record(_GATE_TEST)["sha256"]
    got = s.search(record=_record(_GATE_TEST))
    assert got["read"] == "ok" and got["foundIn"] is None and got["result"] is None, got
    last = got["searched"][-1]
    assert (last["position"], last["outcome"], last["runOutcome"]) == (4, break_it.KEPT_FAILING, "failed"), got
    assert len(_worktrees(s.repo)) == 1


def test_t2_a_relative_venv_interpreter_runs_in_the_layer_checkout_through_the_linked_folder(stack):
    # axis: the reviewed checkout's interpreter folder is linked into the layer checkout (G14)
    _venv(stack.repo)
    assert _git(stack.repo, "status", "--porcelain") == ""
    got = stack.search(interpreter=VENV)
    assert got["read"] == "ok" and got["foundIn"]["position"] == 4, got
    assert got["result"]["outcome"] == break_it.KEPT and got["searched"][-1]["runOutcome"] == "passed", got
    assert len(_worktrees(stack.repo)) == 1 and list(stack.scratch.iterdir()) == []
    assert (stack.repo / ".venv" / "bin" / "python").is_file()


def test_t2_without_the_link_the_same_layer_is_not_found(stack, monkeypatch):
    _venv(stack.repo)
    monkeypatch.setattr(dependency_links, "_link_dependencies", lambda *a, **k: None)
    got = stack.search(interpreter=VENV)
    assert got["read"] == "ok" and got["foundIn"] is None, got
    last = got["searched"][-1]
    assert (last["outcome"], last["reason"], last["runOutcome"]) == (
        break_it.KEPT_FAILING, "interpreter-unavailable", "not-run"), got


@pytest.mark.skipif(shutil.which("node") is None or shutil.which("npm") is None,
                    reason="node and npm are required to run a JavaScript break-it test")
def test_t3_a_javascript_layer_runs_with_the_reviewed_checkouts_installed_node_modules(tmp_path, monkeypatch):
    # axis: the reviewed checkout's node_modules is linked into the layer checkout (G14)
    for key, value in (("npm_config_cache", str(tmp_path / "npm-cache")), ("npm_config_offline", "true"),
                       ("npm_config_update_notifier", "false"), ("npm_config_fund", "false"),
                       ("npm_config_audit", "false")):
        monkeypatch.setenv(key, value)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "symbolic-ref", "HEAD", "refs/heads/layer-2")
    _write(repo, "package.json", json.dumps(JS_PACKAGE))
    _write(repo, ".gitignore", "node_modules/\n")
    _write(repo, "vitest.config.mjs",
           'import { defineConfig } from "vitest/config"; export default defineConfig({});\n')
    _write(repo, "README.md", "fixture\n")
    base = _commit(repo, "base")
    _write(repo, "src/lower.js", "module.exports = 1;\n")
    _commit(repo, "layer 2")
    _git(repo, "checkout", "-q", "-b", "layer-3")
    _write(repo, JS_TEST_PATH, JS_PASSING)
    layer3 = _commit(repo, "layer 3")
    _git(repo, "checkout", "-q", "layer-2")
    _install_fake(repo / "node_modules")
    assert _git(repo, "status", "--porcelain") == ""
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    record = {"path": JS_TEST_PATH, "command": JS_NPM_RUN, "content": JS_PASSING,
              "sha256": hashlib.sha256(JS_PASSING.encode()).hexdigest()}
    layers = [{"position": 3, "number": 103, "headRefName": "layer-3", "headRefOid": layer3}]
    got = break_it_layers.check_kept_in_layers(str(repo), base, layers, record, scratch=str(scratch))
    assert got["read"] == "ok" and got["foundIn"]["position"] == 3, got
    assert got["searched"][0]["runOutcome"] == "passed", got
    assert len(_worktrees(repo)) == 1 and list(scratch.iterdir()) == []
    monkeypatch.setattr(dependency_links, "_link_dependencies", lambda *a, **k: None)
    got = break_it_layers.check_kept_in_layers(str(repo), base, layers, record, scratch=str(scratch))
    assert got["read"] == "ok" and got["foundIn"] is None, got
    assert got["searched"][0]["outcome"] == break_it.KEPT_FAILING, got


def test_t4_a_missing_interpreter_folder_means_not_run_and_not_credited(stack, monkeypatch):
    # axis: a needed interpreter folder present nowhere is a not-run layer, never a run (G15)
    calls = _spy_check_kept(monkeypatch)
    got = stack.search(interpreter=VENV)
    assert got["read"] == "ok" and got["foundIn"] is None and got["result"] is None, got
    assert calls == [], calls
    assert [(s["position"], s["outcome"], s["reason"], s["held"], s["runOutcome"]) for s in got["searched"]] == [
        (3, "not-run", "dependency-missing:.venv", False, None),
        (4, "not-run", "dependency-missing:.venv", True, None)], got
    assert len(_worktrees(stack.repo)) == 1 and list(stack.scratch.iterdir()) == []
    lines = rs._break_it_stack_checked(_record_rows(got["searched"]))
    assert lines == [
        "Break-it test %s (round 1): stack layer 3 (PR 103) at %s could not be checked (dependency-missing:.venv)"
        % (TEST_PATH, stack.layer3[:7]),
        "Break-it test %s (round 1): found in stack layer 4 (PR 104) at %s but it could not run there "
        "(dependency-missing:.venv); the test reads not-in-head" % (TEST_PATH, stack.layer4[:7])], lines
    assert not any("did not pass" in line for line in lines)


def test_t5_a_dependency_folder_linking_into_a_tracked_part_of_the_checkout_is_not_linked(tmp_path, monkeypatch):
    s = Stack(tmp_path, base_files={"vendor/pkg/index.js": "module.exports = 1;\n"})
    os.symlink("vendor", s.repo / "node_modules")
    calls = _spy_check_kept(monkeypatch)
    got = s.search()
    assert got["read"] == "ok" and got["foundIn"] is None and calls == [], (got, calls)
    assert [(e["outcome"], e["reason"], e["held"]) for e in got["searched"]] == [
        ("not-run", "dependency-link-unsafe", False), ("not-run", "dependency-link-unsafe", True)], got
    assert len(_worktrees(s.repo)) == 1 and list(s.scratch.iterdir()) == []


def test_t6_a_held_layer_that_fails_parks_naming_the_layer_and_the_record_says_so(tmp_path, monkeypatch):
    # axis: the park names the first layer that held the test (G17) and the record line says it did not pass (G16)
    world = World(tmp_path, fixed=False)
    monkeypatch.setattr(RD, "_read_stack_membership", lambda pr, repo: world.membership())
    assert world.step() is True
    (row,) = world.round_record["breakItKept"]
    assert (row["outcome"], row["reason"]) == (break_it.KEPT_MISSING, "not-in-head"), row
    assert row["stack"]["read"] == "ok" and row["stack"]["foundIn"] is None, row
    (entry,) = row["stack"]["searched"]
    assert (entry["position"], entry["outcome"], entry["runOutcome"]) == (3, break_it.KEPT_FAILING, "failed"), entry
    reason = world.state["certification"]["reason"]
    assert "found in stack layer 3 (PR 103) but it did not pass there: failed" in reason, reason
    assert "the stack could not be read" not in reason, reason
    assert rs._break_it_stack_checked(world.state["rounds"]) == [
        "Break-it test %s (round 1): found in stack layer 3 (PR 103) at %s but it did not pass there (failed); "
        "the test reads not-in-head" % (TEST_PATH, world.layer3[:7])]
    assert len(_worktrees(world.repo)) == 1


def test_t6_a_failed_stack_read_keeps_only_its_own_park_suffix_but_the_record_keeps_the_held_layer(tmp_path, monkeypatch):
    world = World(tmp_path, fixed=False)
    monkeypatch.setattr(RD, "_read_stack_membership", lambda pr, repo: world.membership())
    searched = [{"position": 3, "pr": 103, "commit": world.layer3, "outcome": "failing", "reason": None,
                 "runOutcome": "failed"}]
    monkeypatch.setattr(break_it_layers, "check_kept_in_layers", lambda *a, **k: {
        "read": "failed", "reason": "layer-read-failed:ls-tree-failed", "foundIn": None, "result": None,
        "searched": searched})
    assert world.step() is True
    reason = world.state["certification"]["reason"]
    assert "the stack could not be read: layer-read-failed:ls-tree-failed" in reason, reason
    assert "found in stack layer" not in reason, reason
    lines = rs._break_it_stack_checked(world.state["rounds"])
    assert len(lines) == 2 and "the stack could not be read (layer-read-failed:ls-tree-failed)" in lines[0], lines
    assert "found in stack layer 3 (PR 103)" in lines[1] and "did not pass there" in lines[1], lines


def test_t6_the_record_lines_for_the_other_searched_outcomes(tmp_path):
    searched = [{"position": 3, "pr": 103, "commit": "d" * 40, "outcome": "missing", "reason": "not-in-head",
                 "runOutcome": None},
                {"position": 4, "pr": 104, "commit": "e" * 40, "outcome": "not-run",
                 "reason": "dependency-link-unsafe", "held": True, "runOutcome": None}]
    lines = rs._break_it_stack_checked(_record_rows(searched))
    assert lines == ["Break-it test %s (round 1): found in stack layer 4 (PR 104) at eeeeeee but it could not run "
                     "there (dependency-link-unsafe); the test reads not-in-head" % TEST_PATH], lines


def test_t7_e3_a_link_that_fails_is_not_run_and_not_credited(stack, monkeypatch):
    monkeypatch.setattr(dependency_links, "_link_dependencies",
                        lambda *a, **k: dependency_links.REASON_DEPENDENCY_LINK_FAILED)
    calls = _spy_check_kept(monkeypatch)
    got = stack.search()
    assert got["read"] == "ok" and got["foundIn"] is None and calls == [], (got, calls)
    assert [(e["outcome"], e["reason"], e["held"]) for e in got["searched"]] == [
        ("not-run", "dependency-link-failed", False), ("not-run", "dependency-link-failed", True)], got


@pytest.mark.parametrize("interpreter", [sys.executable, None, "python3", ["python3"], ["./python3"],
                                         ["../x/bin/python"], []])
def test_t7_e4_an_absolute_or_absent_interpreter_adds_no_extra_name(stack, monkeypatch, interpreter):
    seen, real = [], dependency_links._link_dependencies

    def spy(root, copy, names=dependency_links.DEPENDENCY_DIRS):
        seen.append(tuple(names))
        return real(root, copy, names=names)

    monkeypatch.setattr(dependency_links, "_link_dependencies", spy)
    stack.search(interpreter=interpreter)
    assert seen == [("node_modules",)] * 2, seen


def test_t7_e4_a_relative_interpreter_adds_its_first_component(stack, monkeypatch):
    _venv(stack.repo)
    seen, real = [], dependency_links._link_dependencies

    def spy(root, copy, names=dependency_links.DEPENDENCY_DIRS):
        seen.append(tuple(names))
        return real(root, copy, names=names)

    monkeypatch.setattr(dependency_links, "_link_dependencies", spy)
    stack.search(interpreter=VENV)
    assert seen == [("node_modules", ".venv")] * 2, seen


@pytest.mark.parametrize("interpreter", [["./.venv/bin/python"], "./.venv/bin/python", ["././.venv/bin/python"]])
def test_t7_e4_a_dot_slash_prefixed_interpreter_still_adds_its_folder(stack, monkeypatch, interpreter):
    # axis: a harmless leading ./ on a relative interpreter is stripped before its first folder is read, so the layer checkout still gets the reviewed checkout's .venv — see bite-proof record wo_e_2463_layer_dependencies
    _venv(stack.repo)
    seen, real = [], dependency_links._link_dependencies

    def spy(root, copy, names=dependency_links.DEPENDENCY_DIRS):
        seen.append(tuple(names))
        return real(root, copy, names=names)

    monkeypatch.setattr(dependency_links, "_link_dependencies", spy)
    stack.search(interpreter=interpreter)
    assert seen == [("node_modules", ".venv")] * 2, seen


def test_t7_e5_a_layer_head_that_tracks_node_modules_keeps_its_own(tmp_path, monkeypatch):
    s = Stack(tmp_path, layer4_files={"node_modules/pkg/index.js": "module.exports = 1;\n"})
    _write(s.repo, "node_modules/other/x.js", "1\n")  # installed in the reviewed checkout, untracked
    seen, real = [], break_it.check_kept

    def spy(root, base, head, record, **kwargs):
        seen.append((head, os.path.islink(os.path.join(root, "node_modules")),
                     os.path.isfile(os.path.join(root, "node_modules", "pkg", "index.js"))))
        return real(root, base, head, record, **kwargs)

    monkeypatch.setattr(break_it, "check_kept", spy)
    s.search()
    assert seen == [(s.layer3, True, False), (s.layer4, False, True)], seen
    assert (s.repo / "node_modules" / "other" / "x.js").is_file()


def test_t7_e6_a_raising_check_leaves_no_link_and_no_worktree_behind(stack, monkeypatch):
    _venv(stack.repo)
    seen = []

    def boom(root, *args, **kwargs):
        seen.append((os.path.islink(os.path.join(root, ".venv")), os.path.isdir(root)))
        raise RuntimeError("boom")

    monkeypatch.setattr(break_it, "check_kept", boom)
    got = stack.search(interpreter=VENV)
    assert got["read"] == "failed" and got["reason"] == "layer-search-error" and got["foundIn"] is None, got
    assert seen == [(True, True)], seen
    assert len(_worktrees(stack.repo)) == 1 and list(stack.scratch.iterdir()) == []
    assert (stack.repo / ".venv" / "bin" / "python").is_file()
