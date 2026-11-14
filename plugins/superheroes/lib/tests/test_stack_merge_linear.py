"""The linearity gate of stack_merge.merge (#2459): a stack on a merge-queue base that carries a
merge commit is refused before any merge request is sent.

Unit tests fake the three readers the gate calls (stack_check.read_membership,
merge_queue.read, stack_linear.check_rest) and the gh `run`; the one end-to-end test fakes only
`run` and reads the recorded REST fixtures of fixtures/stack_rest/. The merge-async body shapes
are derived from GitHub's REST docs, not recorded (as in test_stack_merge.py)."""
import json
import os
from types import SimpleNamespace

import pytest

import merge_queue
import stack_check
import stack_linear
import stack_merge as sm

REPO = "owner/example"
TOP = 105
SHA = "0123456789abcdef0123456789abcdef01234567"
MERGE_SHA = "89abcdef0123456789abcdef0123456789abcdef"
UUID = "3f2b8c1e-5a6d-4e7f-9a0b-1c2d3e4f5a6b"

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "stack_rest")

TOTAL_KEYS = {
    "ok", "merged", "status", "reason", "detail", "repo", "top", "sha", "uuid", "mergeCommitSha",
}

PUT_ARGV = [
    "gh", "api", "-X", "PUT", "repos/owner/example/pulls/105/merge-async",
    "-f", "merge_method=squash", "-f", "sha=" + SHA,
]
POLL_ARGV = ["gh", "api", "repos/owner/example/pulls/105/merge-async/" + UUID]


@pytest.fixture(autouse=True)
def _gh_on_path(monkeypatch):
    monkeypatch.setattr(sm.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)


# --- small helpers, copied from test_stack_merge.py ---------------------------------------------

def _make_run(handlers):
    """Fake run keyed by argv. A list is consumed in order; its last entry then repeats."""
    calls = []
    kw_calls = []
    queues = {}
    for key, value in handlers.items():
        queues[key] = list(value) if isinstance(value, list) else [value]

    def _run(argv, **kwargs):
        calls.append(list(argv))
        kw_calls.append(dict(kwargs))
        assert kwargs.get("capture_output") is True
        assert kwargs.get("text") is True
        key = tuple(argv)
        if key not in queues:
            raise AssertionError("unexpected gh argv: %r" % (argv,))
        queue = queues[key]
        handler = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(handler, Exception):
            raise handler
        return handler

    _run.kw_calls = kw_calls
    return _run, calls


class _Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class _StepClock:
    """A clock that moves `step` seconds forward on every read."""

    def __init__(self, step):
        self.now = 0.0
        self.step = step

    def monotonic(self):
        value = self.now
        self.now += self.step
        return value

    def sleep(self, seconds):
        raise AssertionError("no sleep expected")


def _proc(stdout="", returncode=0, stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def _body(status, **details):
    return _proc(json.dumps({"status": status, "details": details}))


def _pending(uuid=UUID, expected=SHA):
    return _body("pending", message="queued", uuid=uuid, merge_method="squash",
                 merge_action="merge", expected_head_sha=expected, bypass_rules=False)


def _merged(**extra):
    details = {"message": "merged", "sha": MERGE_SHA, "expected_head_sha": SHA}
    details.update(extra)
    return _body("merged", **details)


def _assert_refusal(result, reason):
    assert set(result) == TOTAL_KEYS
    assert result["ok"] is False
    assert result["merged"] is False
    assert result["reason"] == reason
    assert result["mergeCommitSha"] is None


def _assert_merged(result):
    assert set(result) == TOTAL_KEYS
    assert result["ok"] is True
    assert result["merged"] is True
    assert result["status"] == "merged"
    assert result["reason"] is None


def _sent_put(calls):
    return [c for c in calls if c[:4] == ["gh", "api", "-X", "PUT"]]


# --- the three readers' answers ------------------------------------------------------------------

def _membership(numbers=(103, 104, 105), top_position=None, base="main"):
    """An ok read_membership answer: `numbers` bottom to top, the queried pull request at
    `top_position` (the last member when None)."""
    position = len(numbers) if top_position is None else top_position
    members = [{"position": index + 1, "number": number} for index, number in enumerate(numbers)]
    return {
        "ok": True, "reason": None, "detail": None, "repo": REPO, "pr": numbers[position - 1],
        "stack": {"number": 9, "size": len(numbers), "baseRefName": base},
        "queried": {"number": numbers[position - 1], "position": position,
                    "headRefName": "h", "headRefOid": SHA, "baseRefName": "b"},
        "members": members, "pages": 1,
    }


def _membership_refusal(reason, detail):
    return {"ok": False, "reason": reason, "detail": detail, "repo": REPO, "pr": TOP,
            "stack": None, "queried": None, "members": [], "pages": 0}


def _queue_answer(queue=True, source="rules"):
    return {"ok": True, "queue": queue, "source": source, "method": None, "reads": None,
            "reason": None, "detail": None, "repo": REPO, "branch": "main"}


def _queue_refusal():
    return {"ok": False, "queue": None, "source": None, "method": None, "reads": None,
            "reason": "bad-argument", "detail": "branch must be a non-empty string",
            "repo": REPO, "branch": None}


def _linear_ok():
    return {"ok": True, "linear": True, "reason": None, "detail": None, "layers": []}


def _not_linear(detail="merge commits: layer 104: abc"):
    return {"ok": False, "linear": False, "reason": "stack-not-linear", "detail": detail,
            "layers": []}


def _unreadable(reason="linearity-unreadable", detail="layer 104: commit list unreadable"):
    return {"ok": False, "linear": None, "reason": reason, "detail": detail, "layers": []}


class _Env:
    """Fakes for the three readers. Each answer is a value or a callable of the call's kwargs;
    `on_call[name]` runs on every call (a test uses it to move the clock)."""

    def __init__(self, monkeypatch):
        self.read_membership = _membership()
        self.merge_queue = _queue_answer(True)
        self.check_rest = _linear_ok()
        self.calls = {"read_membership": [], "merge_queue": [], "check_rest": []}
        self.on_call = {}
        monkeypatch.setattr(stack_check, "read_membership", self._fake("read_membership"))
        monkeypatch.setattr(merge_queue, "read", self._fake("merge_queue"))
        monkeypatch.setattr(stack_linear, "check_rest", self._fake("check_rest"))

    def _fake(self, name):
        def _answer(**kwargs):
            self.calls[name].append(kwargs)
            hook = self.on_call.get(name)
            if hook is not None:
                hook()
            value = getattr(self, name)
            return value(**kwargs) if callable(value) else value
        return _answer


@pytest.fixture
def env(monkeypatch):
    return _Env(monkeypatch)


def _go(handlers=None, clock=None, **kwargs):
    """Run sm.merge against a fake gh. By default the PUT answers merged."""
    run, calls = _make_run({tuple(PUT_ARGV): _merged()} if handlers is None else handlers)
    clock = _Clock() if clock is None else clock
    kwargs.setdefault("poll_timeout", 30)
    kwargs.setdefault("poll_interval", 5)
    result = sm.merge(repo=REPO, top=TOP, sha=SHA, run=run, sleep=clock.sleep,
                      monotonic=clock.monotonic, **kwargs)
    return result, calls, run


def _run_dod(module, monkeypatch):
    """The definition-of-done scenario on `module` (a stack_merge): a queue base and a layer
    carrying a merge commit. Returns (result, the gh argvs the fake run saw). Written so a probe
    can run it against another version of stack_merge."""
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(stack_check, "read_membership", lambda **kw: _membership())
    monkeypatch.setattr(merge_queue, "read", lambda **kw: _queue_answer(True))
    monkeypatch.setattr(stack_linear, "check_rest", lambda **kw: _not_linear())
    run, calls = _make_run({tuple(PUT_ARGV): _merged()})
    clock = _Clock()
    result = module.merge(repo=REPO, top=TOP, sha=SHA, run=run, sleep=clock.sleep,
                          monotonic=clock.monotonic, poll_timeout=30, poll_interval=5)
    return result, calls


# --- the definition of done ----------------------------------------------------------------------

def test_dod_queue_base_with_a_merge_commit_is_refused_and_no_request_is_sent(monkeypatch):
    result, calls = _run_dod(sm, monkeypatch)
    _assert_refusal(result, "stack-not-linear")
    assert result["detail"] == "merge commits: layer 104: abc"
    assert _sent_put(calls) == []
    assert calls == []


def test_queue_base_with_linear_layers_sends_the_put_and_merges(env):
    result, calls, run = _go()
    _assert_merged(result)
    assert calls == [PUT_ARGV]
    assert [c["prs"] for c in env.calls["check_rest"]] == [[103, 104, 105]]


def test_no_queue_base_merges_as_before_and_never_reads_commits(env):
    env.merge_queue = _queue_answer(False, source="none")
    env.check_rest = _not_linear()
    result, calls, run = _go()
    _assert_merged(result)
    assert calls == [PUT_ARGV]
    assert env.calls["check_rest"] == []


def test_the_queue_is_read_for_the_stack_base_not_the_pull_requests_base(env):
    env.read_membership = _membership(base="release/1")
    _go()
    assert [c["branch"] for c in env.calls["merge_queue"]] == ["release/1"]


# --- fail-closed edges ---------------------------------------------------------------------------

def test_g1_budget_already_spent_before_the_gate_reads_nothing_and_sends_nothing(env):
    clock = _StepClock(100)
    result, calls, run = _go(clock=clock)
    _assert_refusal(result, "linearity-unreadable")
    assert "budget" in result["detail"]
    assert calls == []
    assert env.calls["read_membership"] == []
    assert env.calls["merge_queue"] == []
    assert env.calls["check_rest"] == []


@pytest.mark.parametrize("reason,detail", [
    ("not-linked", "pull request 105 is not in a native stack"),
    ("stack-unreadable", "graphql refused; rest: gh api exited 1"),
])
def test_g2_membership_refusal_is_linearity_unreadable_and_names_the_reason(env, reason, detail):
    env.read_membership = _membership_refusal(reason, detail)
    result, calls, run = _go()
    _assert_refusal(result, "linearity-unreadable")
    assert result["detail"] == "stack membership: %s: %s" % (reason, detail)
    assert calls == []
    assert env.calls["merge_queue"] == []
    assert env.calls["check_rest"] == []


def _above_top():
    answer = _membership(numbers=(103, 104, 105))
    answer["queried"]["position"] = 0
    return answer


def _bad_member_number():
    answer = _membership()
    answer["members"][1]["number"] = "104"
    return answer


def _no_stack():
    answer = _membership()
    answer["stack"] = None
    return answer


def _no_base():
    answer = _membership()
    answer["stack"]["baseRefName"] = None
    return answer


@pytest.mark.parametrize("answer", [
    pytest.param(dict(_membership(), members=[]), id="no-members"),
    pytest.param(_above_top(), id="every-member-above-the-top"),
    pytest.param(_bad_member_number(), id="member-number-not-an-int"),
    pytest.param(_no_stack(), id="stack-missing"),
    pytest.param(_no_base(), id="base-missing"),
], )
def test_g3_membership_ok_but_no_layer_at_or_below_the_top_is_unreadable(env, answer):
    env.read_membership = answer
    result, calls, run = _go()
    _assert_refusal(result, "linearity-unreadable")
    assert "no layer" in result["detail"]
    assert calls == []
    assert env.calls["merge_queue"] == []
    assert env.calls["check_rest"] == []


def test_g4_queue_read_not_ok_is_linearity_unreadable_and_never_passes(env):
    env.merge_queue = _queue_refusal()
    result, calls, run = _go()
    _assert_refusal(result, "linearity-unreadable")
    assert result["detail"].startswith("merge queue: bad-argument: ")
    assert calls == []
    assert env.calls["check_rest"] == []


def test_g5_queue_true_from_a_failed_read_still_checks_the_commits(env):
    env.merge_queue = _queue_answer(True, source="read-failed")
    env.check_rest = _not_linear()
    result, calls, run = _go()
    _assert_refusal(result, "stack-not-linear")
    assert len(env.calls["check_rest"]) == 1
    assert calls == []


def test_g5_queue_true_from_a_failed_read_with_linear_layers_merges(env):
    env.merge_queue = _queue_answer(True, source="read-failed")
    result, calls, run = _go()
    _assert_merged(result)
    assert len(env.calls["check_rest"]) == 1


@pytest.mark.parametrize("queue", [None, 0, "false", ""])
def test_g5_only_an_exact_false_queue_answer_passes_unchecked(env, queue):
    env.merge_queue = _queue_answer(queue, source="none")
    env.check_rest = _not_linear()
    result, calls, run = _go()
    _assert_refusal(result, "stack-not-linear")
    assert len(env.calls["check_rest"]) == 1
    assert calls == []


def test_g6_a_merge_commit_on_a_queue_base_is_stack_not_linear_with_the_readers_detail(env):
    env.check_rest = _not_linear("merge commits: layer 103: aaa; layer 105: bbb")
    result, calls, run = _go()
    _assert_refusal(result, "stack-not-linear")
    assert result["detail"] == "merge commits: layer 103: aaa; layer 105: bbb"
    assert calls == []


@pytest.mark.parametrize("reason", ["linearity-unreadable", "bad-argument"])
def test_g7_a_commit_read_that_is_not_ok_and_not_a_merge_commit_is_unreadable(env, reason):
    env.check_rest = _unreadable(reason=reason, detail="layer 104: commit list unreadable")
    result, calls, run = _go()
    _assert_refusal(result, "linearity-unreadable")
    assert result["detail"] == "%s: layer 104: commit list unreadable" % reason
    assert calls == []


def test_g8_budget_spent_between_the_gate_and_the_put_sends_nothing(env):
    clock = _Clock()
    env.merge_queue = _queue_answer(False, source="none")
    env.on_call["merge_queue"] = lambda: setattr(clock, "now", 30.0)
    result, calls, run = _go(clock=clock)
    _assert_refusal(result, "linearity-unreadable")
    assert "budget" in result["detail"]
    assert _sent_put(calls) == []
    assert calls == []


def test_g8_a_slow_gate_leaves_the_put_only_the_time_left(env):
    clock = _Clock()
    env.merge_queue = _queue_answer(False, source="none")
    env.on_call["merge_queue"] = lambda: setattr(clock, "now", 25.0)
    result, calls, run = _go(clock=clock, timeout=120)
    _assert_merged(result)
    assert calls == [PUT_ARGV]
    assert run.kw_calls[0]["timeout"] == 5.0


def test_g9_a_layer_above_the_top_carrying_a_merge_commit_is_ignored(env):
    env.read_membership = _membership(numbers=(104, 105, 106), top_position=2)

    def _check(**kwargs):
        return _not_linear() if 106 in kwargs["prs"] else _linear_ok()

    env.check_rest = _check
    result, calls, run = _go()
    _assert_merged(result)
    assert [c["prs"] for c in env.calls["check_rest"]] == [[104, 105]]


# --- the one budget ------------------------------------------------------------------------------

def test_every_read_of_the_gate_shares_the_one_deadline_and_the_one_run(env):
    clock = _Clock()
    result, calls, run = _go(clock=clock, poll_timeout=30, timeout=10)
    _assert_merged(result)
    membership_kw = env.calls["read_membership"][0]
    assert membership_kw["pr"] == TOP
    assert membership_kw["repo"] == REPO
    assert membership_kw["deadline"] == 30
    assert membership_kw["timeout"] == 10
    assert membership_kw["run"] is run
    queue_kw = env.calls["merge_queue"][0]
    assert queue_kw["repo"] == REPO
    assert queue_kw["deadline_at"] == 30
    assert queue_kw["timeout"] == 10
    assert queue_kw["run"] is run
    assert queue_kw["monotonic"] == clock.monotonic
    linear_kw = env.calls["check_rest"][0]
    assert linear_kw["repo"] == REPO
    assert linear_kw["deadline_at"] == 30
    assert linear_kw["timeout"] == 10
    assert linear_kw["run"] is run
    assert linear_kw["monotonic"] == clock.monotonic


def test_the_membership_read_is_capped_by_the_time_left(env):
    _go(poll_timeout=30, timeout=120)
    assert env.calls["read_membership"][0]["timeout"] == 30


def test_a_slow_gate_shortens_the_polling_budget_too(env):
    clock = _Clock()
    env.merge_queue = _queue_answer(False, source="none")
    env.on_call["merge_queue"] = lambda: setattr(clock, "now", 20.0)
    result, calls, run = _go({tuple(PUT_ARGV): _pending(), tuple(POLL_ARGV): _pending()},
                             clock=clock, poll_timeout=30, poll_interval=5)
    _assert_refusal(result, "poll-timeout")
    assert clock.sleeps == [5, 5]
    assert clock.now == 30.0


# --- end to end: only `run` is faked -------------------------------------------------------------

E2E_REPO = "zwrose/superheroes"
E2E_TOP = 2077
E2E_LOWER = 2065


def _fixture_text(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return fh.read()


def _commit_row(sha_char, parents):
    return {"sha": sha_char * 40, "parents": [{"sha": p * 40} for p in parents]}


def _e2e_run(commits):
    """A fake gh for the whole gate: GraphQL refused with the cloud proxy's 403 (membership falls
    back to REST, the queue read fails closed), the recorded REST pull and stack, a rules list
    with no merge_queue row, and `commits` (pull request number -> rows) for the commit pages."""
    calls = []
    pull = _fixture_text("pulls_2077.json")
    stack = _fixture_text("stacks_2078.json")
    refused = _proc(_fixture_text("graphql_refused.stdout"), returncode=1,
                    stderr=_fixture_text("graphql_refused.stderr"))
    pages = {
        "repos/zwrose/superheroes/pulls/2077": pull,
        "repos/zwrose/superheroes/stacks/2078": stack,
        "repos/zwrose/superheroes/rules/branches/main?per_page=100&page=1":
            json.dumps([{"type": "pull_request", "parameters": {}}]),
    }
    for number, rows in commits.items():
        pages["repos/zwrose/superheroes/pulls/%d/commits?per_page=100&page=1" % number] = (
            json.dumps(rows))

    def _run(argv, **kwargs):
        calls.append(list(argv))
        assert kwargs.get("capture_output") is True
        assert kwargs.get("text") is True
        if argv[:4] == ["gh", "api", "-X", "PUT"]:
            return _merged(expected_head_sha=SHA)
        if argv[:3] == ["gh", "api", "graphql"]:
            return refused
        if argv[:2] == ["gh", "api"] and len(argv) == 3 and argv[2] in pages:
            return _proc(pages[argv[2]])
        raise AssertionError("unexpected gh argv: %r" % (argv,))

    return _run, calls


LINEAR_ROWS = [_commit_row("a", ["0"]), _commit_row("b", ["a"])]
MERGE_ROWS = [_commit_row("c", ["0"]), _commit_row("d", ["c", "e"])]


@pytest.mark.parametrize("commits", [
    pytest.param({E2E_LOWER: LINEAR_ROWS, E2E_TOP: MERGE_ROWS}, id="merge-commit-in-the-top"),
    pytest.param({E2E_LOWER: MERGE_ROWS, E2E_TOP: LINEAR_ROWS}, id="merge-commit-in-the-lower"),
])
def test_end_to_end_a_merge_commit_on_an_assumed_queue_base_sends_no_put(commits):
    run, calls = _e2e_run(commits)
    result = sm.merge(repo=E2E_REPO, top=E2E_TOP, sha=SHA, run=run, poll_timeout=60)
    _assert_refusal(result, "stack-not-linear")
    assert "merge commits:" in result["detail"]
    assert _sent_put(calls) == []
    assert ["gh", "api", "repos/zwrose/superheroes/pulls/2065/commits?per_page=100&page=1"] in calls
    assert ["gh", "api", "repos/zwrose/superheroes/pulls/2077/commits?per_page=100&page=1"] in calls


def test_end_to_end_linear_layers_on_an_assumed_queue_base_send_the_put_and_merge():
    run, calls = _e2e_run({E2E_LOWER: LINEAR_ROWS, E2E_TOP: LINEAR_ROWS})
    result = sm.merge(repo=E2E_REPO, top=E2E_TOP, sha=SHA, run=run, poll_timeout=60)
    _assert_merged(result)
    assert len(_sent_put(calls)) == 1
    assert calls[-1][:4] == ["gh", "api", "-X", "PUT"]
