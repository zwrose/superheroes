"""A repeat outcome after a fix order is recorded, so it closes the lane's reopening (#2159).

`record_outcome` on an already-terminal lane records a `reoutcome` amendment, deduped against an identical one
already in the ledger. A `vet not-ready` amendment is a fix order that reopens the lane for the wave watch, and
a `reoutcome` is what closes it; so an identical `reoutcome` from before the fix order must not swallow the
repeat outcome that answers it. The dedupe therefore only counts amendments at or after the lane's newest
fix order (a `vet not-ready` with a finite ts), and the new record is stamped no earlier than it. A lane with no
such fix order dedupes against its whole history, and every other amendment kind is unchanged.

Bite-proof record: bite_proofs/wo_2159_reoutcome_dedupe.md.
"""
import time

import launch_ledger as ll
import wave_watch as ww
from test_wave_watch_builder_note import _cloud_lane  # noqa: F401
from test_wave_watch_cloud import repo  # noqa: F401

_LAUNCH = "cloud-a"
_EVIDENCE = "re-handed back after the narrow fix"
_FIRST_EVIDENCE = "built and gated"


class _SteppedTime:
    """A stand-in for the `time` module whose `time()` reads a chosen value and whose rest is the real module."""

    def __init__(self, now):
        self._now = now

    def time(self):
        return self._now

    def __getattr__(self, name):
        return getattr(time, name)


def _handed_back(repo_root, launch_id=_LAUNCH, issue=101):
    _cloud_lane(repo_root, launch_id, issue)
    assert ll.record_outcome(repo_root, launch_id, "handback", _FIRST_EVIDENCE)["ok"] is True


def _fix_order(repo_root, launch_id=_LAUNCH):
    assert ll.amend(repo_root, launch_id, "vet", "not-ready", "needs the narrow fix")["ok"] is True


def _amend_at(repo_root, launch_id, kind, value, ts, note="n"):
    """An amendment laid at an explicit `ts`, as the ledger would hold it from another time."""
    assert ll.append(repo_root, {
        "event": ll.AMENDMENT_EVENT, "launchId": launch_id, "ts": ts,
        "schema": ll.SCHEMA, "kind": kind, "value": value, "note": note,
    })


def _info(repo_root, launch_id=_LAUNCH):
    return ll.fold(ll.read(repo_root)["records"])["launches"][launch_id]


def _reoutcomes(repo_root, launch_id=_LAUNCH):
    return [a for a in _info(repo_root, launch_id)["amendments"] if a["kind"] == "reoutcome"]


def _record(repo_root, launch_id=_LAUNCH, evidence=_EVIDENCE):
    result = ll.record_outcome(repo_root, launch_id, "handback", evidence)
    assert result["ok"] is True, result
    return result["recorded"]


def _record_count(repo_root):
    return len(ll.read(repo_root)["records"])


# axis: E1 scope boundary — the end-to-end second cycle: an identical reoutcome from before the fix order
# does not swallow the repeat outcome that answers it
def test_t1_second_cycle_repeat_outcome_after_a_fix_order_is_recorded_and_closes_the_reopening(repo):
    _handed_back(repo)
    assert _record(repo) == "amendment"
    _fix_order(repo)
    assert _record(repo) == "amendment"
    assert len(_reoutcomes(repo)) == 2
    assert ww._reopen_candidate(_info(repo), []) is None


# axis: E1 scope boundary — the issue's literal row: outcome, fix order, then the same outcome and evidence
def test_t2_the_issues_row_outcome_then_fix_order_then_repeat_outcome_closes_the_reopening(repo):
    _handed_back(repo)
    _fix_order(repo)
    assert ww._reopen_candidate(_info(repo), []) is not None
    assert _record(repo, evidence=_FIRST_EVIDENCE) == "amendment"
    assert ww._reopen_candidate(_info(repo), []) is None


# axis: E5 no fix order — a lane never sent a fix order dedupes against its whole history, as before
def test_t3_without_a_fix_order_an_identical_repeat_outcome_is_deduped(repo):
    _handed_back(repo)
    assert _record(repo) == "amendment"
    count = _record_count(repo)
    assert _record(repo) == "amendment-existing"
    assert len(_reoutcomes(repo)) == 1
    assert _record_count(repo) == count


# axis: E5 dedupe resumes — after the fix order is answered, a further identical repeat outcome is deduped
def test_t3_dedupe_resumes_after_the_fix_order_is_answered(repo):
    _handed_back(repo)
    assert _record(repo) == "amendment"
    _fix_order(repo)
    assert _record(repo) == "amendment"
    count = _record_count(repo)
    assert _record(repo) == "amendment-existing"
    assert len(_reoutcomes(repo)) == 2
    assert _record_count(repo) == count


# axis: E2 tie — an identical reoutcome at exactly the fix order's ts counts as after it (the reader's tie
# closes the reopening), so it dedupes
def test_t4_an_identical_reoutcome_at_the_fix_orders_ts_dedupes(repo):
    _handed_back(repo)
    tie = time.time()
    _amend_at(repo, _LAUNCH, "reoutcome", "handback", tie, note=_EVIDENCE)
    _amend_at(repo, _LAUNCH, "vet", "not-ready", tie)
    assert ww._reopen_candidate(_info(repo), []) is None
    count = _record_count(repo)
    assert _record(repo) == "amendment-existing"
    assert _record_count(repo) == count


# axis: E3 non-finite candidate — an identical reoutcome whose ts is not finite is not after the fix order
# (the reader skips it), so it does not dedupe and a closer is written
def test_t5_an_identical_reoutcome_with_a_non_finite_ts_does_not_dedupe(repo):
    _handed_back(repo)
    _amend_at(repo, _LAUNCH, "vet", "not-ready", time.time())
    _amend_at(repo, _LAUNCH, "reoutcome", "handback", float("inf"), note=_EVIDENCE)
    assert ww._reopen_candidate(_info(repo), []) is not None
    assert _record(repo) == "amendment"
    assert ww._reopen_candidate(_info(repo), []) is None


# axis: E4 ts clamp — a clock stepped back behind the fix order cannot write a closer older than it
def test_t6_a_clock_stepped_back_still_writes_a_closer_no_older_than_the_fix_order(repo, monkeypatch):
    _handed_back(repo)
    assert _record(repo) == "amendment"
    now = time.time()
    fix_order_ts = now + 1000
    _amend_at(repo, _LAUNCH, "vet", "not-ready", fix_order_ts)
    assert ww._reopen_candidate(_info(repo), []) is not None
    monkeypatch.setattr(ll, "time", _SteppedTime(now))
    assert _record(repo) == "amendment"
    assert _reoutcomes(repo)[-1]["ts"] == fix_order_ts
    assert ww._reopen_candidate(_info(repo), []) is None
    assert _record(repo) == "amendment-existing"


# axis: edge (b) non-finite opener — a vet not-ready with a non-finite ts is no fix order here (the reader
# skips it), so the dedupe is the whole history's
def test_t8_a_vet_not_ready_with_a_non_finite_ts_is_ignored_as_a_fix_order(repo):
    _handed_back(repo)
    assert _record(repo) == "amendment"
    _amend_at(repo, _LAUNCH, "vet", "not-ready", float("nan"))
    count = _record_count(repo)
    assert _record(repo) == "amendment-existing"
    assert _record_count(repo) == count


# axis: E8 newest opener — with two finite fix orders and an identical reoutcome between them, the dedupe is
# scoped to the newer fix order, so the repeat is written and closes the reopening reported at its ts
def test_t9_the_newest_of_two_fix_orders_scopes_the_dedupe(repo):
    _handed_back(repo)
    now = time.time()
    _amend_at(repo, _LAUNCH, "vet", "not-ready", now - 300)
    _amend_at(repo, _LAUNCH, "reoutcome", "handback", now - 200, note=_EVIDENCE)
    _amend_at(repo, _LAUNCH, "vet", "not-ready", now - 100)
    assert ww._reopen_candidate(_info(repo), []) == (now - 100, "vet-not-ready")
    assert _record(repo) == "amendment"
    assert ww._reopen_candidate(_info(repo), []) is None


# axis: E6 other kinds — only a reoutcome is scoped to the fix order; an evidence amendment still dedupes
# against its whole history
def test_t7_other_amendment_kinds_still_dedupe_against_the_whole_history(repo):
    _handed_back(repo)
    first = ll.amend(repo, _LAUNCH, "evidence", "v", "n")
    assert first["ok"] is True and first["deduped"] is False
    _fix_order(repo)
    second = ll.amend(repo, _LAUNCH, "evidence", "v", "n", dedupe_identical=True)
    assert second["ok"] is True
    assert second["deduped"] is True
