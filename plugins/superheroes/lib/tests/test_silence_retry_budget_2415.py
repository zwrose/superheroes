"""A codex review retry that follows a silence-watchdog cut is itself watched, and its cut earns one last attempt (#2415).

`engine_dispatch._attempt_budget(opened, state)` is the run's attempt budget; `_silence_watchdog_threshold(opened, attempt,
state)` arms the watchdog on every attempt below it. The end-to-end second chance is pinned in `test_engine_dispatch_e2e.py`.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/i2415_test_role_ceiling.md
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import engine_dispatch as ED  # noqa: E402

_THRESHOLD = 390
_ABSENT = object()


def _opened(*, engine="codex", run_kind=None, watchdog=_THRESHOLD):
    rec = {"kind": "run-opened", "engine": engine,
           "runKind": ED.RUN_KIND_REVIEW if run_kind is None else run_kind}
    if watchdog is not _ABSENT:
        rec["silenceWatchdogSeconds"] = watchdog
    return rec


def _cut():
    return {"kind": "attempt-ended", "signalSource": "silence-watchdog", "timedOut": False, "exit": -15,
            "silenceWatchdog": {"thresholdSeconds": _THRESHOLD, "silentSeconds": 391.0}}


def _timed_out():
    return {"kind": "attempt-ended", "signalSource": "runner-timeout", "timedOut": True, "exit": None}


def _nonzero():
    return {"kind": "attempt-ended", "signalSource": "engine-exit", "timedOut": False, "exit": 3}


def _answered():
    return {"kind": "attempt-ended", "signalSource": "engine-exit", "timedOut": False, "exit": 0}


def _state(first=_ABSENT, second=_ABSENT, *, opened=None):
    """A state in the shape `_journal_state` returns; an attempt is absent, running (`None`) or ended (a record)."""
    attempts = {}
    for number, ended in ((1, first), (2, second)):
        if ended is not _ABSENT:
            attempts[number] = {"childPid": 1, "enginePgid": 1, "ended": ended}
    return {"opened": opened, "attempts": attempts}


# --- the budget ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("first,second,expected", [
    # attempt 1 has not ended (absent, or running)
    (_ABSENT, _ABSENT, 2),
    (None, _ABSENT, 2),
    # attempt 1 ended any way but the watchdog
    (_timed_out(), _ABSENT, 2),
    (_timed_out(), None, 2),
    (_nonzero(), None, 2),
    (_answered(), None, 2),
    # attempt 1 cut, attempt 2 not yet ended: the retry is running (and is armed)
    (_cut(), _ABSENT, 3),
    (_cut(), None, 3),
    # attempt 1 cut, attempt 2 cut too: the last attempt
    (_cut(), _cut(), 3),
    # attempt 1 cut, attempt 2 ended any other way: no third attempt
    (_cut(), _timed_out(), 2),
    (_cut(), _nonzero(), 2),
    (_cut(), _answered(), 2),
])
def test_the_budget_follows_how_the_attempts_ended(first, second, expected):
    # axis: G3 — a third attempt only when attempt 1 was cut and attempt 2 is running or was cut too
    assert ED._attempt_budget(_opened(), _state(first, second)) == expected


def test_the_budget_is_never_more_than_one_above_the_base():
    # axis: only attempt 1's cut earns the extra attempt, so a cut attempt 2 does not earn a fourth
    assert ED._attempt_budget(_opened(), _state(_cut(), _cut())) == ED.MAX_ATTEMPTS + 1
    assert ED._attempt_budget(_opened(), _state(_timed_out(), _cut())) == ED.MAX_ATTEMPTS


@pytest.mark.parametrize("opened", [
    _opened(run_kind=ED.RUN_KIND_WRITE),
    _opened(engine="claude"),
    _opened(engine="cursor"),
    _opened(watchdog=None),
    _opened(watchdog=0),
    _opened(watchdog=-1),
    _opened(watchdog=True),
    _opened(watchdog="390"),
    _opened(watchdog=float("inf")),
    _opened(watchdog=float("nan")),
    _opened(watchdog=_ABSENT),
    None,
    [],
    "opened",
])
def test_any_other_run_keeps_the_two_attempt_budget(opened):
    # axis: a write run, a non-codex run and a run with the watchdog off never earn a third attempt
    assert ED._attempt_budget(opened, _state(_cut(), _cut())) == ED.MAX_ATTEMPTS
    assert ED._attempt_budget(opened, _state(_cut(), None)) == ED.MAX_ATTEMPTS


@pytest.mark.parametrize("state", [
    None,
    [],
    "state",
    {},
    {"attempts": None},
    {"attempts": []},
    {"attempts": "x"},
    {"attempts": {1: None}},
    {"attempts": {1: "x", 2: "y"}},
    {"attempts": {1: {"ended": "x"}}},
    {"attempts": {1: {"ended": []}, 2: {"ended": []}}},
])
def test_a_malformed_or_absent_state_keeps_the_two_attempt_budget(state):
    # axis: E1 — a state that cannot be read fails closed to today's budget
    assert ED._attempt_budget(_opened(), state) == ED.MAX_ATTEMPTS


def test_a_budget_that_would_raise_reads_as_two(monkeypatch):
    # axis: E6 — an exception inside the budget reads as today's budget, never propagates
    def boom(_ended):
        raise RuntimeError("boom")

    monkeypatch.setattr(ED, "_silence_watchdog_end", boom)
    assert ED._attempt_budget(_opened(), _state(_cut(), _cut())) == ED.MAX_ATTEMPTS


def test_a_write_run_never_exceeds_two_attempts():
    # axis: E5 — a write run's attempt 3 is refused whatever the journal says
    state = _state(_cut(), _cut(), opened=_opened(run_kind=ED.RUN_KIND_WRITE))
    assert ED._spawn_attempt("/nonexistent", state, 3)[1] == "attempts-exhausted"


def test_attempt_four_is_never_spawned_even_for_a_codex_review_run():
    # axis: E4 — attempt 3 can never be followed by a fourth
    state = _state(_cut(), _cut(), opened=_opened())
    assert ED._spawn_attempt("/nonexistent", state, 4)[1] == "attempts-exhausted"


def test_attempt_three_is_refused_when_the_retry_was_not_cut():
    # axis: E2b — a retry that ended any other way earns no third attempt
    state = _state(_cut(), _timed_out(), opened=_opened())
    assert ED._spawn_attempt("/nonexistent", state, 3)[1] == "attempts-exhausted"


# --- the arming ---------------------------------------------------------------------------------------------------------


def test_the_watchdog_is_armed_on_attempt_one_before_it_ends():
    # axis: G4 — attempt 1 of a codex review run is armed with the threshold recorded at run open
    assert ED._silence_watchdog_threshold(_opened(), 1, _state()) == _THRESHOLD
    assert ED._silence_watchdog_threshold(_opened(), 1, _state(None)) == _THRESHOLD


def test_a_retry_after_a_watchdog_cut_is_armed():
    # axis: G4 — attempt 2 is armed when attempt 1 was cut by the watchdog
    assert ED._silence_watchdog_threshold(_opened(), 2, _state(_cut())) == _THRESHOLD
    assert ED._silence_watchdog_threshold(_opened(), 2, _state(_cut(), None)) == _THRESHOLD


@pytest.mark.parametrize("first", [_timed_out(), _nonzero(), _answered()])
def test_a_retry_after_any_other_end_is_not_armed(first):
    # axis: G4 — attempt 2 stays unarmed (today) when attempt 1 ended any way but the watchdog
    assert ED._silence_watchdog_threshold(_opened(), 2, _state(first)) is None
    assert ED._silence_watchdog_threshold(_opened(), 2, _state(first, None)) is None


@pytest.mark.parametrize("state", [
    _state(), _state(_cut()), _state(_cut(), _cut()), _state(_cut(), _timed_out()), _state(_timed_out())])
def test_attempt_three_is_never_armed(state):
    # axis: the last attempt is bounded by its ceiling alone
    assert ED._silence_watchdog_threshold(_opened(), 3, state) is None


def test_the_two_argument_form_keeps_today_s_arming():
    # axis: with no state the budget is MAX_ATTEMPTS, so attempt 2 is the unarmed last attempt
    assert ED._silence_watchdog_threshold(_opened(), 1) == _THRESHOLD
    assert ED._silence_watchdog_threshold(_opened(), 2) is None
    assert ED._silence_watchdog_threshold(_opened(), 2, None) is None


def test_a_run_that_is_not_a_codex_review_run_is_armed_on_attempt_one_only():
    # axis: a write run and a non-codex run keep today's arming whatever the journal says
    for opened in (_opened(run_kind=ED.RUN_KIND_WRITE), _opened(engine="cursor")):
        assert ED._silence_watchdog_threshold(opened, 1, _state(_cut())) is None
        assert ED._silence_watchdog_threshold(opened, 2, _state(_cut())) is None
