"""The queue-slots gate of stack_merge.merge (#2480): a stack on a merge-queue base is held until
merge_queue.slots answers that the queue has a free build slot for every layer, and no merge
request is sent otherwise.

Unit tests fake the four readers the gate calls (stack_check.read_membership, merge_queue.read,
stack_linear.check_rest, merge_queue.slots) and the gh `run`. The fakes and helpers are copied
from test_stack_merge_linear.py, not imported. The merge-async body shapes are derived from
GitHub's REST docs, not recorded (as in test_stack_merge.py)."""
import json
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

TOTAL_KEYS = {
    "ok", "merged", "status", "reason", "detail", "repo", "top", "sha", "uuid", "mergeCommitSha",
}

PUT_ARGV = [
    "gh", "api", "-X", "PUT", "repos/owner/example/pulls/105/merge-async",
    "-f", "merge_method=squash", "-f", "sha=" + SHA,
]


@pytest.fixture(autouse=True)
def _gh_on_path(monkeypatch):
    monkeypatch.setattr(sm.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)


# --- small helpers, copied from test_stack_merge_linear.py ---------------------------------------

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


def _proc(stdout="", returncode=0, stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def _body(status, **details):
    return _proc(json.dumps({"status": status, "details": details}))


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


# --- the readers' answers ------------------------------------------------------------------------

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


def _slots_answer(*, ok=True, fits=False, reason=None, detail=None, layers=3, free=None,
                  limit=None, queued=None):
    """A merge_queue.slots answer with the twelve keys the module always returns."""
    return {"ok": ok, "fits": fits, "queue": True, "limit": limit, "queued": queued,
            "free": free, "layers": layers, "reads": {"rules": "ok", "graphql": "ok"},
            "reason": reason, "detail": detail, "repo": REPO, "branch": "main"}


def _slots_fits():
    return _slots_answer(fits=True, limit=5, queued=0, free=5)


SHORT_DETAIL = ("the queue builds up to 5 entries at a time and holds 4 already, leaving "
                "1 free for 3 layers")


def _slots_short(detail=SHORT_DETAIL):
    return _slots_answer(fits=False, reason="slots-short", detail=detail, limit=5, queued=4,
                         free=1)


def _slots_unreadable(detail="graphql read failed: gh exited 1: HTTP 403"):
    return _slots_answer(fits=False, reason="slots-unreadable", detail=detail)


def _slots_bad_argument():
    return _slots_answer(ok=False, fits=False, reason="bad-argument",
                         detail="layers must be an integer of at least 1")


class _Env:
    """Fakes for the readers and the slots read. Each answer is a value or a callable of the
    call's kwargs; `on_call[name]` runs on every call (a test uses it to move the clock). `order`
    records the names of the calls in the order they were made."""

    def __init__(self, monkeypatch):
        self.read_membership = _membership()
        self.merge_queue = _queue_answer(True)
        self.check_rest = _linear_ok()
        self.slots = _slots_fits()
        self.calls = {"read_membership": [], "merge_queue": [], "check_rest": [], "slots": []}
        self.order = []
        self.on_call = {}
        monkeypatch.setattr(stack_check, "read_membership", self._fake("read_membership"))
        monkeypatch.setattr(merge_queue, "read", self._fake("merge_queue"))
        monkeypatch.setattr(stack_linear, "check_rest", self._fake("check_rest"))
        monkeypatch.setattr(merge_queue, "slots", self._fake("slots"))

    def _fake(self, name):
        def _answer(**kwargs):
            self.calls[name].append(kwargs)
            self.order.append(name)
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


# --- E1: fits true sends the PUT -----------------------------------------------------------------

def test_e1_slots_fit_sends_the_put_and_merges_after_the_linear_check(env):
    result, calls, run = _go()
    _assert_merged(result)
    assert calls == [PUT_ARGV]
    assert env.order == ["read_membership", "merge_queue", "check_rest", "slots"]
    assert len(env.calls["slots"]) == 1


# --- E2: slots-short ------------------------------------------------------------------------------

def test_e2_slots_short_is_queue_slots_short_with_the_slots_detail_and_no_request(env):
    env.slots = _slots_short()
    result, calls, run = _go()
    _assert_refusal(result, "queue-slots-short")
    assert result["detail"] == SHORT_DETAIL
    assert _sent_put(calls) == []
    assert calls == []
    assert len(env.calls["slots"]) == 1


# --- E3: slots-unreadable -------------------------------------------------------------------------

def test_e3_slots_unreadable_is_queue_slots_unreadable_naming_the_reason_and_detail(env):
    env.slots = _slots_unreadable("graphql read failed: gh exited 1: HTTP 403")
    result, calls, run = _go()
    _assert_refusal(result, "queue-slots-unreadable")
    assert result["detail"] == (
        "merge queue slots: slots-unreadable: graphql read failed: gh exited 1: HTTP 403")
    assert _sent_put(calls) == []
    assert calls == []


# --- E4: bad-argument, a non-dict, a dict with no fits, and only `fits is True` passes -----------

def _no_fits_key():
    answer = _slots_fits()
    del answer["fits"]
    return answer


@pytest.mark.parametrize("answer", [
    pytest.param(_slots_bad_argument(), id="bad-argument"),
    pytest.param(None, id="none"),
    pytest.param("fits", id="string"),
    pytest.param(["fits"], id="list"),
    pytest.param(True, id="bool"),
    pytest.param({}, id="empty-dict"),
    pytest.param(_no_fits_key(), id="dict-without-a-fits-key"),
])
def test_e4_a_bad_argument_or_an_answer_that_is_not_a_fits_object_is_queue_slots_unreadable(
        env, answer):
    env.slots = answer
    result, calls, run = _go()
    _assert_refusal(result, "queue-slots-unreadable")
    assert result["detail"].startswith("merge queue slots: ")
    assert _sent_put(calls) == []
    assert calls == []


@pytest.mark.parametrize("answer", [
    pytest.param({}, id="empty-dict"),
    pytest.param(_no_fits_key(), id="dict-without-a-fits-key"),
])
def test_e4_a_dict_with_no_fits_key_says_so(env, answer):
    env.slots = answer
    result, calls, run = _go()
    _assert_refusal(result, "queue-slots-unreadable")
    assert result["detail"] == "merge queue slots: the answer is not an object with a fits key"
    assert calls == []


def test_e4_bad_argument_names_its_reason_and_detail(env):
    env.slots = _slots_bad_argument()
    result, calls, run = _go()
    _assert_refusal(result, "queue-slots-unreadable")
    assert result["detail"] == (
        "merge queue slots: bad-argument: layers must be an integer of at least 1")


@pytest.mark.parametrize("fits", [1, "yes", "true", [True], {"a": 1}, 1.0, None, 0, "", "no"])
def test_e4_only_an_exact_true_fits_passes(env, fits):
    env.slots = dict(_slots_fits(), fits=fits)
    result, calls, run = _go()
    _assert_refusal(result, "queue-slots-unreadable")
    assert _sent_put(calls) == []
    assert calls == []


@pytest.mark.parametrize("fits", [0, "no", None, ""])
def test_e4_slots_short_with_a_fits_that_is_not_exactly_false_is_unreadable(env, fits):
    env.slots = dict(_slots_short(), fits=fits)
    result, calls, run = _go()
    _assert_refusal(result, "queue-slots-unreadable")
    assert _sent_put(calls) == []


@pytest.mark.parametrize("reason", [None, "slots-unreadable", "something-else"])
def test_e4_fits_false_without_the_slots_short_reason_is_unreadable(env, reason):
    env.slots = _slots_answer(fits=False, reason=reason, detail="d")
    result, calls, run = _go()
    _assert_refusal(result, "queue-slots-unreadable")
    assert result["detail"] == "merge queue slots: %s: d" % reason
    assert _sent_put(calls) == []


# --- E5: the one budget --------------------------------------------------------------------------

def test_e5_the_slot_read_shares_the_one_deadline_and_the_one_run(env):
    clock = _Clock()
    result, calls, run = _go(clock=clock, poll_timeout=30, timeout=10)
    _assert_merged(result)
    slots_kw = env.calls["slots"][0]
    assert slots_kw["repo"] == REPO
    assert slots_kw["deadline_at"] == 30
    assert slots_kw["timeout"] == 10
    assert slots_kw["run"] is run
    assert slots_kw["monotonic"] == clock.monotonic
    queue_kw = env.calls["merge_queue"][0]
    assert slots_kw["deadline_at"] == queue_kw["deadline_at"]
    assert slots_kw["timeout"] == queue_kw["timeout"]
    assert slots_kw["run"] is queue_kw["run"]
    assert slots_kw["monotonic"] == queue_kw["monotonic"]


def test_e5_a_slot_read_that_spends_the_budget_leaves_the_put_unsent(env):
    clock = _Clock()
    env.on_call["slots"] = lambda: setattr(clock, "now", 30.0)
    result, calls, run = _go(clock=clock)
    _assert_refusal(result, "linearity-unreadable")
    assert "budget" in result["detail"]
    assert _sent_put(calls) == []
    assert calls == []


# --- E6: layers is the count at or below the top -------------------------------------------------

def test_e6_layers_is_the_count_of_members_at_or_below_the_top(env):
    env.read_membership = _membership(numbers=(104, 105, 106), top_position=2)
    result, calls, run = _go()
    _assert_merged(result)
    assert [c["layers"] for c in env.calls["slots"]] == [2]
    assert [c["prs"] for c in env.calls["check_rest"]] == [[104, 105]]


def test_e6_layers_counts_every_member_when_the_top_is_the_last(env):
    _go()
    assert [c["layers"] for c in env.calls["slots"]] == [3]


# --- E7: the branch is the stack's base ----------------------------------------------------------

def test_e7_slots_is_read_for_the_stack_base_branch(env):
    env.read_membership = _membership(base="release/1")
    _go()
    assert [c["branch"] for c in env.calls["slots"]] == ["release/1"]


# --- E8: a base with no queue never reads slots --------------------------------------------------

def test_e8_a_base_read_as_queue_false_never_reads_slots_and_merges(env):
    env.merge_queue = _queue_answer(False, source="none")
    env.slots = _slots_short()
    result, calls, run = _go()
    _assert_merged(result)
    assert calls == [PUT_ARGV]
    assert env.calls["slots"] == []
    assert env.calls["check_rest"] == []


# --- E9, E10: linearity is decided before slots --------------------------------------------------

def test_e9_a_stack_that_is_not_linear_on_a_queue_base_never_reads_slots(env):
    env.check_rest = _not_linear()
    env.slots = _slots_fits()
    result, calls, run = _go()
    _assert_refusal(result, "stack-not-linear")
    assert result["detail"] == "merge commits: layer 104: abc"
    assert env.calls["slots"] == []
    assert calls == []


@pytest.mark.parametrize("reason", ["linearity-unreadable", "bad-argument"])
def test_e10_a_commit_read_that_is_unreadable_never_reads_slots(env, reason):
    env.check_rest = _unreadable(reason=reason)
    result, calls, run = _go()
    _assert_refusal(result, "linearity-unreadable")
    assert result["detail"] == "%s: layer 104: commit list unreadable" % reason
    assert env.calls["slots"] == []
    assert calls == []


def test_a_membership_or_queue_refusal_never_reads_slots(env):
    env.read_membership = _membership_refusal("not-linked", "pull request 105 is not in a stack")
    result, calls, run = _go()
    _assert_refusal(result, "linearity-unreadable")
    assert env.calls["slots"] == []
    env.read_membership = _membership()
    env.merge_queue = _queue_refusal()
    result, calls, run = _go()
    _assert_refusal(result, "linearity-unreadable")
    assert env.calls["slots"] == []
    assert calls == []


# --- review round 1: merged layers, an all-merged stack, and a stack that can never fit -----------

def _membership_with_states(states, numbers=(103, 104, 105)):
    """The default membership with each member's `state` set, bottom to top."""
    answer = _membership(numbers=numbers)
    for member, state in zip(answer["members"], states):
        member["state"] = state
    return answer


def test_a_merged_layer_needs_no_build_slot(env):
    env.read_membership = _membership_with_states(("MERGED", "OPEN", "OPEN"))
    result, calls, run = _go()
    _assert_merged(result)
    assert [c["layers"] for c in env.calls["slots"]] == [2]
    assert [c["prs"] for c in env.calls["check_rest"]] == [[103, 104, 105]]


def test_a_layer_whose_state_is_not_merged_or_unreadable_still_needs_a_slot(env):
    env.read_membership = _membership_with_states(("CLOSED", None, "OPEN"))
    _go()
    assert [c["layers"] for c in env.calls["slots"]] == [3]


def test_a_stack_with_every_layer_merged_needs_no_slot_and_reads_none(env):
    env.read_membership = _membership_with_states(("MERGED", "MERGED", "MERGED"))
    result, calls, run = _go()
    _assert_merged(result)
    assert env.calls["slots"] == []
    assert calls == [PUT_ARGV]


NEVER_FITS_DETAIL = ("the stack has 6 layers and the queue builds at most 5 entries at a time, "
                     "so it can never fit the queue as it stands; it needs the owner: split the "
                     "stack, or the owner's word for another way through")


def test_slots_never_fits_is_queue_slots_never_fits_with_its_detail_and_no_request(env):
    env.slots = _slots_answer(fits=False, reason="slots-never-fits", detail=NEVER_FITS_DETAIL,
                              layers=6, limit=5, queued=0, free=5)
    result, calls, run = _go()
    _assert_refusal(result, "queue-slots-never-fits")
    assert result["detail"] == NEVER_FITS_DETAIL
    assert calls == []


@pytest.mark.parametrize("fits", [True, None, 0, "false"])
def test_slots_never_fits_with_a_fits_that_is_not_exactly_false_is_not_never_fits(env, fits):
    env.slots = _slots_answer(fits=fits, reason="slots-never-fits", detail=NEVER_FITS_DETAIL)
    result, calls, run = _go()
    assert result["reason"] != "queue-slots-never-fits"
