"""Fake-based units for stack_merge.py. No real gh or network — every gh call is faked.

The 200/202 merge-async body shapes used here are derived from GitHub's REST docs
(docs.github.com/en/rest/pulls/pulls), NOT recorded from a live call. The one recorded
fixture is the poll GET for an unknown uuid
(fixtures/stack_rest/merge_async_get_unknown_uuid.stdout / .stderr: gh exit 1, a 404 body
on stdout, "gh: Not Found (HTTP 404)" on stderr)."""
import json
import os
import subprocess
from types import SimpleNamespace

import pytest

import stack_merge as sm

REPO = "owner/example"
TOP = 105
SHA = "0123456789abcdef0123456789abcdef01234567"
OTHER_SHA = "fedcba9876543210fedcba9876543210fedcba98"
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
HEAD_ARGV = ["gh", "api", "repos/owner/example/pulls/105"]


@pytest.fixture(autouse=True)
def _gh_on_path(monkeypatch):
    monkeypatch.setattr(sm.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)


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


def _pending(uuid=UUID, expected=SHA):
    return _body("pending", message="queued", uuid=uuid, merge_method="squash",
                 merge_action="merge", expected_head_sha=expected, bypass_rules=False)


def _merged(**extra):
    details = {"message": "merged", "sha": MERGE_SHA}
    details.update(extra)
    return _body("merged", **details)


def _head(sha=SHA):
    return _proc(json.dumps({"number": TOP, "head": {"sha": sha}}))


def _recorded_404():
    with open(os.path.join(FIXTURES, "merge_async_get_unknown_uuid.stdout")) as fh:
        out = fh.read()
    with open(os.path.join(FIXTURES, "merge_async_get_unknown_uuid.stderr")) as fh:
        err = fh.read()
    return _proc(out, returncode=1, stderr=err)


def _do_merge(handlers, **kwargs):
    run, calls = _make_run(handlers)
    clock = _Clock()
    kwargs.setdefault("poll_timeout", 30)
    kwargs.setdefault("poll_interval", 5)
    result = sm.merge(repo=REPO, top=TOP, sha=SHA, run=run, sleep=clock.sleep,
                      monotonic=clock.monotonic, **kwargs)
    return result, calls, run


def _do_poll(handlers, **kwargs):
    run, calls = _make_run(handlers)
    clock = _Clock()
    kwargs.setdefault("poll_timeout", 30)
    kwargs.setdefault("poll_interval", 5)
    result = sm.poll(repo=REPO, top=TOP, uuid=UUID, sha=SHA, run=run, sleep=clock.sleep,
                     monotonic=clock.monotonic, **kwargs)
    return result, calls, run


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


# M1 — the PUT request shape

def test_m1_put_argv_pins_top_pr_squash_and_sha():
    result, calls, run = _do_merge({tuple(PUT_ARGV): _merged(), tuple(HEAD_ARGV): _head()})
    _assert_merged(result)
    assert calls == [PUT_ARGV, HEAD_ARGV]
    assert calls[0][:4] == ["gh", "api", "-X", "PUT"]
    assert "repos/owner/example/pulls/105/merge-async" in calls[0]
    assert "merge_method=squash" in calls[0]
    assert "sha=" + SHA in calls[0]
    assert not any("merge_action" in arg for arg in calls[0])
    assert run.kw_calls[0]["timeout"] == 30  # min(GH_TIMEOUT, the 30-second budget)
    _result, _calls, run = _do_merge(
        {tuple(PUT_ARGV): _merged(), tuple(HEAD_ARGV): _head()}, poll_timeout=500)
    assert run.kw_calls[0]["timeout"] == sm.GH_TIMEOUT


# M2 — merged straight away

def test_m2_put_merged_is_ok_with_merge_commit():
    result, _calls, _run = _do_merge({tuple(PUT_ARGV): _merged(), tuple(HEAD_ARGV): _head()})
    _assert_merged(result)
    assert result["mergeCommitSha"] == MERGE_SHA
    assert (result["repo"], result["top"], result["sha"]) == (REPO, TOP, SHA)


def test_m2_immediate_merged_with_other_head_is_head_mismatch():
    result, calls, _run = _do_merge(
        {tuple(PUT_ARGV): _merged(), tuple(HEAD_ARGV): _head(OTHER_SHA)})
    _assert_refusal(result, "head-mismatch")
    assert result["status"] == "merged"
    assert calls == [PUT_ARGV, HEAD_ARGV]


@pytest.mark.parametrize("readback", [
    OSError("network down"),
    subprocess.TimeoutExpired(["gh"], 5),
    _proc("", returncode=1, stderr="gh: Not Found (HTTP 404)"),
    _proc("not json"),
    _proc(json.dumps({"head": {}})),
    _proc(json.dumps({"head": {"sha": "not-a-sha"}})),
])
def test_m2_immediate_merged_with_unreadable_head_is_unreadable(readback):
    result, _calls, _run = _do_merge({tuple(PUT_ARGV): _merged(), tuple(HEAD_ARGV): readback})
    _assert_refusal(result, "merge-response-unreadable")


def test_m2_immediate_merged_naming_the_pin_skips_the_read_back():
    result, calls, _run = _do_merge({tuple(PUT_ARGV): _merged(expected_head_sha=SHA)})
    _assert_merged(result)
    assert calls == [PUT_ARGV]


def test_m2_read_back_gets_only_the_time_left_in_the_one_budget():
    clock = _Clock()
    seen = []

    def _run(argv, **kwargs):
        if list(argv) == PUT_ARGV:
            clock.now += 8
            return _merged()
        assert list(argv) == HEAD_ARGV
        seen.append(kwargs["timeout"])
        return _head()

    result = sm.merge(repo=REPO, top=TOP, sha=SHA, poll_timeout=10, poll_interval=5,
                      timeout=120, run=_run, sleep=clock.sleep, monotonic=clock.monotonic)
    _assert_merged(result)
    assert seen == [2]


def test_m2_put_that_uses_up_the_budget_refuses_without_a_read_back():
    clock = _Clock()
    calls = []

    def _run(argv, **kwargs):
        calls.append(list(argv))
        if list(argv) == PUT_ARGV:
            clock.now += 10
            return _merged()
        raise AssertionError("no read-back may start with no time left")

    result = sm.merge(repo=REPO, top=TOP, sha=SHA, poll_timeout=10, poll_interval=5,
                      timeout=120, run=_run, sleep=clock.sleep, monotonic=clock.monotonic)
    _assert_refusal(result, "merge-response-unreadable")
    assert result["status"] == "merged"
    assert "budget" in result["detail"]
    assert calls == [PUT_ARGV]


def test_m2_main_merged_exits_zero(capsys):
    run, _calls = _make_run({tuple(PUT_ARGV): _merged(), tuple(HEAD_ARGV): _head()})
    clock = _Clock()
    code = sm.main(["merge", "--repo", REPO, "--top", str(TOP), "--sha", SHA],
                   run=run, sleep=clock.sleep, monotonic=clock.monotonic)
    out = capsys.readouterr().out
    assert code == 0
    assert out.count("\n") == 1
    parsed = json.loads(out)
    _assert_merged(parsed)
    assert parsed["mergeCommitSha"] == MERGE_SHA


def test_m2_merged_without_a_commit_sha_has_null_merge_commit():
    result, _calls, _run = _do_merge(
        {tuple(PUT_ARGV): _body("merged", message="merged"), tuple(HEAD_ARGV): _head()})
    _assert_merged(result)
    assert result["mergeCommitSha"] is None


def test_m2_merged_with_non_hex_commit_sha_has_null_merge_commit():
    result, _calls, _run = _do_merge(
        {tuple(PUT_ARGV): _body("merged", sha="not-a-sha"), tuple(HEAD_ARGV): _head()})
    _assert_merged(result)
    assert result["mergeCommitSha"] is None


# M3 — pending, then polled to merged

def test_m3_pending_then_polled_to_merged():
    result, calls, run = _do_merge({
        tuple(PUT_ARGV): _pending(),
        tuple(POLL_ARGV): [_pending(), _merged()],
    })
    _assert_merged(result)
    assert result["uuid"] == UUID
    assert result["mergeCommitSha"] == MERGE_SHA
    assert calls == [PUT_ARGV, POLL_ARGV, POLL_ARGV]
    assert UUID in calls[1][-1]
    assert run.kw_calls[1]["timeout"] <= sm.GH_TIMEOUT


def test_m3_poll_sleeps_the_interval_between_reads():
    run, _calls = _make_run({
        tuple(PUT_ARGV): _pending(),
        tuple(POLL_ARGV): [_pending(), _pending(), _merged()],
    })
    clock = _Clock()
    result = sm.merge(repo=REPO, top=TOP, sha=SHA, poll_timeout=60, poll_interval=7,
                      run=run, sleep=clock.sleep, monotonic=clock.monotonic)
    _assert_merged(result)
    assert clock.sleeps == [7, 7, 7]


# M4 — failed

def test_m4_put_failed_is_merge_failed_with_message():
    result, calls, _run = _do_merge({
        tuple(PUT_ARGV): _body("failed", message="required check failed"),
    })
    _assert_refusal(result, sm.REASON_MERGE_FAILED)
    assert result["status"] == "failed"
    assert "required check failed" in result["detail"]
    assert calls == [PUT_ARGV]


def test_m4_poll_failed_is_merge_failed_with_message():
    result, _calls, _run = _do_merge({
        tuple(PUT_ARGV): _pending(),
        tuple(POLL_ARGV): [_pending(), _body("failed", message="conflict in base")],
    })
    _assert_refusal(result, sm.REASON_MERGE_FAILED)
    assert "conflict in base" in result["detail"]
    assert result["uuid"] == UUID


def test_m4_failed_without_a_message_still_refuses():
    result, _calls, _run = _do_merge({tuple(PUT_ARGV): _body("failed")})
    _assert_refusal(result, sm.REASON_MERGE_FAILED)
    assert result["detail"]


# M5 — enqueued

def test_m5_put_enqueued_is_not_merged():
    result, calls, _run = _do_merge({tuple(PUT_ARGV): _body("enqueued", message="in the queue")})
    _assert_refusal(result, sm.REASON_MERGE_ENQUEUED)
    assert result["status"] == "enqueued"
    assert calls == [PUT_ARGV]


def test_m5_poll_enqueued_is_not_merged():
    result, _calls, _run = _do_merge({
        tuple(PUT_ARGV): _pending(),
        tuple(POLL_ARGV): _body("enqueued"),
    })
    _assert_refusal(result, sm.REASON_MERGE_ENQUEUED)
    assert result["uuid"] == UUID


# M6 — pending until the budget ends

def test_m6_pending_until_budget_ends_is_poll_timeout():
    result, calls, _run = _do_merge({
        tuple(PUT_ARGV): _pending(),
        tuple(POLL_ARGV): _pending(),
    }, poll_timeout=20, poll_interval=5)
    _assert_refusal(result, sm.REASON_POLL_TIMEOUT)
    assert result["status"] == "pending"
    assert result["uuid"] == UUID
    assert calls.count(POLL_ARGV) == 3


def test_m6_poll_call_timeout_is_capped_by_the_time_left():
    run, _calls = _make_run({tuple(PUT_ARGV): _pending(), tuple(POLL_ARGV): _pending()})
    clock = _Clock()
    result = sm.merge(repo=REPO, top=TOP, sha=SHA, poll_timeout=12, poll_interval=5,
                      run=run, sleep=clock.sleep, monotonic=clock.monotonic)
    _assert_refusal(result, sm.REASON_POLL_TIMEOUT)
    assert [kw["timeout"] for kw in run.kw_calls[1:]] == [7, 2]
    assert clock.now <= 12


def test_m6_default_budget_ends_below_the_host_command_cap():
    assert sm.DEFAULT_POLL_TIMEOUT == 420


def test_m6_one_budget_bounds_the_put_and_the_polling():
    clock = _Clock()
    put = _pending()

    def _run(argv, **kwargs):
        if list(argv) == PUT_ARGV:
            assert kwargs["timeout"] == 10
            clock.now += 8
            return put
        return _pending()

    result = sm.merge(repo=REPO, top=TOP, sha=SHA, poll_timeout=10, poll_interval=5,
                      timeout=120, run=_run, sleep=clock.sleep, monotonic=clock.monotonic)
    _assert_refusal(result, sm.REASON_POLL_TIMEOUT)
    assert result["uuid"] == UUID
    assert clock.now <= 10


def test_m6_interval_longer_than_the_budget_makes_no_poll_get():
    run, calls = _make_run({tuple(POLL_ARGV): _pending()})
    clock = _Clock()
    result = sm.poll(repo=REPO, top=TOP, uuid=UUID, sha=SHA, poll_timeout=1, poll_interval=600,
                     run=run, sleep=clock.sleep, monotonic=clock.monotonic)
    _assert_refusal(result, sm.REASON_POLL_TIMEOUT)
    assert result["uuid"] == UUID
    assert calls == []
    assert clock.now <= 1


def test_m6_deadline_crossed_before_the_sleep_makes_no_sleep_and_no_get():
    run, calls = _make_run({tuple(POLL_ARGV): _pending()})
    readings = iter([0, 11])
    sleeps = []

    def _monotonic():
        return next(readings, 11)

    def _sleep(seconds):
        if seconds < 0:
            raise ValueError("sleep length must be non-negative")
        sleeps.append(seconds)

    result = sm.poll(repo=REPO, top=TOP, uuid=UUID, sha=SHA, poll_timeout=10, poll_interval=5,
                     run=run, sleep=_sleep, monotonic=_monotonic)
    _assert_refusal(result, sm.REASON_POLL_TIMEOUT)
    assert result["uuid"] == UUID
    assert sleeps == []
    assert calls == []


def test_m6_main_poll_timeout_exits_one(capsys):
    run, _calls = _make_run({tuple(PUT_ARGV): _pending(), tuple(POLL_ARGV): _pending()})
    clock = _Clock()
    code = sm.main(["merge", "--repo", REPO, "--top", str(TOP), "--sha", SHA,
                    "--poll-timeout", "10", "--poll-interval", "5"],
                   run=run, sleep=clock.sleep, monotonic=clock.monotonic)
    parsed = json.loads(capsys.readouterr().out)
    assert code == 1
    _assert_refusal(parsed, sm.REASON_POLL_TIMEOUT)
    assert parsed["uuid"] == UUID


# M7 / M8 — a refused PUT

def test_m7_put_409_with_existing_request_is_refused_and_never_polled():
    body = json.dumps({"status": "pending", "details": {"uuid": UUID, "expected_head_sha": SHA}})
    result, calls, _run = _do_merge({
        tuple(PUT_ARGV): _proc(body, returncode=1, stderr="gh: Conflict (HTTP 409)"),
        tuple(POLL_ARGV): _merged(),
    })
    _assert_refusal(result, sm.REASON_MERGE_REQUEST_REFUSED)
    assert result["uuid"] == UUID
    assert calls == [PUT_ARGV]
    assert POLL_ARGV not in calls


def test_m7_put_409_with_unusable_uuid_does_not_carry_it():
    body = json.dumps({"status": "pending", "details": {"uuid": "../x"}})
    result, calls, _run = _do_merge({tuple(PUT_ARGV): _proc(body, returncode=1)})
    _assert_refusal(result, sm.REASON_MERGE_REQUEST_REFUSED)
    assert result["uuid"] is None
    assert calls == [PUT_ARGV]


def test_m8_put_400_with_message_is_refused_with_the_message():
    body = json.dumps({"message": "Pull Request is not mergeable"})
    result, calls, _run = _do_merge({
        tuple(PUT_ARGV): _proc(body, returncode=1, stderr="gh: Pull Request is not mergeable (HTTP 400)"),
    })
    _assert_refusal(result, sm.REASON_MERGE_REQUEST_REFUSED)
    assert "Pull Request is not mergeable" in result["detail"]
    assert result["uuid"] is None
    assert calls == [PUT_ARGV]


def test_m8_put_nonzero_without_a_body_is_refused_with_stderr():
    result, _calls, _run = _do_merge({
        tuple(PUT_ARGV): _proc("", returncode=1, stderr="gh: Forbidden (HTTP 403)"),
    })
    _assert_refusal(result, sm.REASON_MERGE_REQUEST_REFUSED)
    assert "HTTP 403" in result["detail"]


def test_m8_put_nonzero_with_a_merged_looking_body_is_still_refused():
    body = json.dumps({"status": "merged", "details": {"sha": MERGE_SHA, "expected_head_sha": SHA}})
    result, _calls, _run = _do_merge({tuple(PUT_ARGV): _proc(body, returncode=1)})
    _assert_refusal(result, sm.REASON_MERGE_REQUEST_REFUSED)
    assert result["status"] is None


# M9 / M10 — head mismatch

def test_m9_pending_with_other_expected_head_is_head_mismatch_and_never_polled():
    result, calls, _run = _do_merge({
        tuple(PUT_ARGV): _pending(expected=OTHER_SHA),
        tuple(POLL_ARGV): _merged(),
    })
    _assert_refusal(result, sm.REASON_HEAD_MISMATCH)
    assert calls == [PUT_ARGV]


def test_m10_merged_with_other_expected_head_is_head_mismatch():
    result, _calls, _run = _do_merge({
        tuple(PUT_ARGV): _merged(expected_head_sha=OTHER_SHA),
    })
    _assert_refusal(result, sm.REASON_HEAD_MISMATCH)


def test_m10_expected_head_matches_case_insensitively():
    result, _calls, _run = _do_merge({
        tuple(PUT_ARGV): _merged(expected_head_sha=SHA.upper()),
    })
    _assert_merged(result)


def test_m10_poll_with_other_expected_head_ends_the_loop_as_head_mismatch():
    result, calls, _run = _do_merge({
        tuple(PUT_ARGV): _pending(),
        tuple(POLL_ARGV): [_pending(), _merged(expected_head_sha=OTHER_SHA), _merged()],
    })
    _assert_refusal(result, sm.REASON_HEAD_MISMATCH)
    assert calls.count(POLL_ARGV) == 2


# M11 — unreadable PUT bodies

@pytest.mark.parametrize("stdout", [
    "not json at all",
    "",
    json.dumps([{"status": "merged"}]),
    json.dumps({"status": "done", "details": {}}),
    json.dumps({"status": 7, "details": {}}),
    json.dumps({"status": "merged"}),
    json.dumps({"status": "merged", "details": "ok"}),
    json.dumps({"status": "pending", "details": {"expected_head_sha": SHA}}),
    json.dumps({"status": "pending", "details": {"uuid": "../etc", "expected_head_sha": SHA}}),
    json.dumps({"status": "pending", "details": {"uuid": UUID}}),
    json.dumps({"status": "merged", "details": {"expected_head_sha": 123}}),
    json.dumps({"status": "merged", "details": {"expected_head_sha": None}}),
], ids=["not-json", "empty", "array", "unknown-status", "status-not-string", "details-missing",
        "details-not-object", "pending-no-uuid", "pending-bad-uuid", "pending-no-expected",
        "expected-not-string", "expected-null"])
def test_m11_unreadable_put_body_is_never_merged(stdout):
    result, calls, _run = _do_merge({
        tuple(PUT_ARGV): _proc(stdout),
        tuple(POLL_ARGV): _merged(),
    })
    _assert_refusal(result, sm.REASON_MERGE_RESPONSE_UNREADABLE)
    assert calls == [PUT_ARGV]


@pytest.mark.parametrize("status", ["done", 7])
def test_m11_unknown_status_is_refused_at_the_read_and_not_echoed(status):
    result, _calls, _run = _do_merge({
        tuple(PUT_ARGV): _proc(json.dumps({"status": status, "details": {}})),
    })
    _assert_refusal(result, sm.REASON_MERGE_RESPONSE_UNREADABLE)
    assert result["status"] is None
    assert "known status" in result["detail"]


def test_m11_details_missing_is_unreadable_even_for_merged():
    result, _calls, _run = _do_merge({tuple(PUT_ARGV): _proc(json.dumps({"status": "merged"}))})
    _assert_refusal(result, sm.REASON_MERGE_RESPONSE_UNREADABLE)
    assert result["status"] == "merged"


# M12 — poll GET failures inside the budget

def test_m12_recorded_404_then_merged_keeps_polling_and_is_ok():
    result, calls, _run = _do_merge({
        tuple(PUT_ARGV): _pending(),
        tuple(POLL_ARGV): [_recorded_404(), _merged()],
    })
    _assert_merged(result)
    assert calls == [PUT_ARGV, POLL_ARGV, POLL_ARGV]


def test_m12_recorded_404_every_poll_is_poll_timeout_with_the_404_text():
    result, calls, _run = _do_merge({
        tuple(PUT_ARGV): _pending(),
        tuple(POLL_ARGV): _recorded_404(),
    }, poll_timeout=20, poll_interval=5)
    _assert_refusal(result, sm.REASON_POLL_TIMEOUT)
    assert result["uuid"] == UUID
    assert "HTTP 404" in result["detail"]
    assert "Not Found" in result["detail"]
    assert calls.count(POLL_ARGV) == 3


def test_m12_poll_get_exiting_nonzero_with_a_merged_body_is_never_merged():
    body = json.dumps({"status": "merged", "details": {"sha": MERGE_SHA, "expected_head_sha": SHA}})
    result, calls, _run = _do_merge({
        tuple(PUT_ARGV): _pending(),
        tuple(POLL_ARGV): _proc(body, returncode=1, stderr="gh: Bad Gateway (HTTP 502)"),
    }, poll_timeout=10, poll_interval=5)
    _assert_refusal(result, sm.REASON_POLL_TIMEOUT)
    assert "HTTP 502" in result["detail"]
    assert calls.count(POLL_ARGV) == 1


def test_m12_poll_call_that_raises_then_merged_is_ok():
    result, _calls, _run = _do_merge({
        tuple(PUT_ARGV): _pending(),
        tuple(POLL_ARGV): [OSError("network down"), subprocess.TimeoutExpired(["gh"], 5), _merged()],
    })
    _assert_merged(result)


def test_m12_poll_call_that_always_raises_is_poll_timeout_with_the_error():
    result, _calls, _run = _do_merge({
        tuple(PUT_ARGV): _pending(),
        tuple(POLL_ARGV): OSError("network down"),
    }, poll_timeout=10, poll_interval=5)
    _assert_refusal(result, sm.REASON_POLL_TIMEOUT)
    assert "network down" in result["detail"]


def test_m12_unreadable_poll_body_then_merged_is_ok():
    result, _calls, _run = _do_merge({
        tuple(PUT_ARGV): _pending(),
        tuple(POLL_ARGV): [_proc("<html>"), _proc(json.dumps({"status": "done", "details": {}})),
                           _proc(json.dumps({"status": "merged"})), _merged()],
    })
    _assert_merged(result)


def test_m12_unreadable_poll_body_every_time_is_poll_timeout_with_the_error():
    result, _calls, _run = _do_merge({
        tuple(PUT_ARGV): _pending(),
        tuple(POLL_ARGV): _proc("<html>"),
    }, poll_timeout=10, poll_interval=5)
    _assert_refusal(result, sm.REASON_POLL_TIMEOUT)
    assert "unreadable" in result["detail"]


def test_m12_a_pending_read_clears_the_remembered_poll_error():
    result, _calls, _run = _do_merge({
        tuple(PUT_ARGV): _pending(),
        tuple(POLL_ARGV): [_recorded_404(), _pending()],
    }, poll_timeout=15, poll_interval=5)
    _assert_refusal(result, sm.REASON_POLL_TIMEOUT)
    assert "404" not in result["detail"]


# M13 — arguments and the PUT call itself

def _bad(**overrides):
    args = dict(repo=REPO, top=TOP, sha=SHA, poll_timeout=30, poll_interval=5, timeout=120)
    args.update(overrides)
    run, calls = _make_run({})
    clock = _Clock()
    result = sm.merge(run=run, sleep=clock.sleep, monotonic=clock.monotonic, **args)
    assert calls == []
    assert all(result[key] is None for key in ("repo", "top", "sha", "uuid", "status"))
    _assert_refusal(result, sm.REASON_BAD_ARGUMENT)


@pytest.mark.parametrize("value", [None, 5, "owner", "owner/", "/name", "o/n/x", "own er/name", "o/n\n"])
def test_m13_bad_repo(value):
    _bad(repo=value)


@pytest.mark.parametrize("value", [0, -1, True, "5", 5.0, None])
def test_m13_bad_top(value):
    _bad(top=value)


@pytest.mark.parametrize("value", [None, SHA[:39], SHA + "0", "g" * 40, 123, SHA + "\n"])
def test_m13_bad_sha(value):
    _bad(sha=value)


@pytest.mark.parametrize("value", [None, "", "a" * 65, "abc/def", "../x", "a b", 5])
def test_m13_bad_uuid_for_poll(value):
    run, calls = _make_run({})
    clock = _Clock()
    result = sm.poll(repo=REPO, top=TOP, uuid=value, sha=SHA, run=run, sleep=clock.sleep,
                     monotonic=clock.monotonic)
    _assert_refusal(result, sm.REASON_BAD_ARGUMENT)
    assert calls == []


@pytest.mark.parametrize("value", [0, -3, True, "5", None, float("nan"), float("inf")])
def test_m13_bad_poll_timeout(value):
    _bad(poll_timeout=value)


@pytest.mark.parametrize("value", [0, -3, True, "5", None, float("nan"), float("inf")])
def test_m13_bad_poll_interval(value):
    _bad(poll_interval=value)


@pytest.mark.parametrize("value", [0, -3, True, "5", None, float("nan"), float("inf")])
def test_m13_bad_timeout(value):
    _bad(timeout=value)


def test_m13_gh_not_on_path_is_gh_unavailable(monkeypatch):
    monkeypatch.setattr(sm.shutil, "which", lambda name: None)
    run, calls = _make_run({})
    result = sm.merge(repo=REPO, top=TOP, sha=SHA, run=run)
    _assert_refusal(result, sm.REASON_GH_UNAVAILABLE)
    assert calls == []


def test_m13_gh_not_on_path_blocks_poll_too(monkeypatch):
    monkeypatch.setattr(sm.shutil, "which", lambda name: None)
    run, calls = _make_run({})
    result = sm.poll(repo=REPO, top=TOP, uuid=UUID, sha=SHA, run=run)
    _assert_refusal(result, sm.REASON_GH_UNAVAILABLE)
    assert calls == []


@pytest.mark.parametrize("exc", [OSError("exec failed"), FileNotFoundError("gh"),
                                 subprocess.TimeoutExpired(["gh"], 120)],
                         ids=["oserror", "filenotfound", "timeout"])
def test_m13_put_run_raising_is_merge_request_refused(exc):
    result, calls, _run = _do_merge({tuple(PUT_ARGV): exc})
    _assert_refusal(result, sm.REASON_MERGE_REQUEST_REFUSED)
    assert calls == [PUT_ARGV]


# M14 — the poll verb

def test_m14_poll_verb_merged_is_ok():
    result, calls, _run = _do_poll({tuple(POLL_ARGV): _merged()})
    _assert_merged(result)
    assert result["uuid"] == UUID
    assert calls == [POLL_ARGV]


def test_m14_poll_verb_pending_then_merged_is_ok():
    result, calls, _run = _do_poll({tuple(POLL_ARGV): [_pending(), _merged()]})
    _assert_merged(result)
    assert calls == [POLL_ARGV, POLL_ARGV]


def test_m14_poll_verb_budget_end_is_poll_timeout():
    result, _calls, _run = _do_poll({tuple(POLL_ARGV): _pending()}, poll_timeout=10)
    _assert_refusal(result, sm.REASON_POLL_TIMEOUT)
    assert result["uuid"] == UUID


def test_m14_poll_verb_never_sends_a_put():
    _result, calls, _run = _do_poll({tuple(POLL_ARGV): _merged()})
    assert all("PUT" not in call for call in calls)


def test_m14_main_poll_merged_exits_zero(capsys):
    run, _calls = _make_run({tuple(POLL_ARGV): _merged()})
    clock = _Clock()
    code = sm.main(["poll", "--repo", REPO, "--top", str(TOP), "--uuid", UUID, "--sha", SHA],
                   run=run, sleep=clock.sleep, monotonic=clock.monotonic)
    parsed = json.loads(capsys.readouterr().out)
    assert code == 0
    _assert_merged(parsed)


# M15 — only merged is ok

@pytest.mark.parametrize("handlers_for", [
    lambda: {tuple(PUT_ARGV): _pending(), tuple(POLL_ARGV): _pending()},
    lambda: {tuple(PUT_ARGV): _body("enqueued")},
    lambda: {tuple(PUT_ARGV): _body("failed", message="no")},
    lambda: {tuple(PUT_ARGV): _pending(), tuple(POLL_ARGV): _recorded_404()},
], ids=["pending", "enqueued", "failed", "poll-timeout"])
def test_m15_no_non_merged_outcome_reads_as_ok_or_merged(handlers_for):
    result, _calls, _run = _do_merge(handlers_for(), poll_timeout=10, poll_interval=5)
    assert result["ok"] is False
    assert result["merged"] is False
    assert result["reason"] is not None


@pytest.mark.parametrize("status", ["pending", "enqueued", "failed", "done", "MERGED", "", None])
def test_m15_settle_reads_only_the_merged_status_as_merged(status):
    read = {"status": status, "uuid": None, "commit": None, "message": None}
    settled = sm._settle(REPO, TOP, SHA, read, None)
    assert settled is None or (settled["ok"] is False and settled["merged"] is False)


def test_m15_settle_pending_is_not_final():
    read = {"status": "pending", "uuid": UUID, "commit": None, "message": None}
    assert sm._settle(REPO, TOP, SHA, read, None) is None


def test_m15_settle_unnamed_status_is_unreadable_not_merged():
    read = {"status": "done", "uuid": None, "commit": None, "message": None}
    settled = sm._settle(REPO, TOP, SHA, read, None)
    _assert_refusal(settled, sm.REASON_MERGE_RESPONSE_UNREADABLE)


def test_m15_settle_merged_is_ok():
    read = {"status": "merged", "uuid": None, "commit": MERGE_SHA, "message": None}
    _assert_merged(sm._settle(REPO, TOP, SHA, read, None))


# CLI

@pytest.mark.parametrize("argv", [
    [],
    ["bogus"],
    ["merge"],
    ["merge", "--repo", REPO, "--top", "x", "--sha", SHA],
    ["merge", "--repo", REPO, "--top", "5"],
    ["poll", "--repo", REPO, "--top", "5", "--sha", SHA],
    ["merge", "--repo", REPO, "--top", "5", "--sha", SHA, "--unknown", "1"],
    ["-h"],
])
def test_cli_malformed_is_bad_argument_json_exit_one(argv, capsys):
    code = sm.main(argv)
    out = capsys.readouterr().out
    assert code == 1
    assert out.count("\n") == 1
    _assert_refusal(json.loads(out), sm.REASON_BAD_ARGUMENT)


def test_cli_bad_value_reaches_validation_and_exits_one(capsys):
    run, calls = _make_run({})
    code = sm.main(["merge", "--repo", REPO, "--top", "0", "--sha", SHA], run=run)
    parsed = json.loads(capsys.readouterr().out)
    assert code == 1
    _assert_refusal(parsed, sm.REASON_BAD_ARGUMENT)
    assert calls == []
