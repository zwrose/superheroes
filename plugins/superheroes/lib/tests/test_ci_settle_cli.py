"""ci_settle_cli.settle — the #120-deferred bounded settle-poll (0.10.0 qualification)."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import ci_settle_cli


def _seq_reader(seq):
    it = iter(seq)
    last = seq[-1]
    def _read():
        return next(it, last)
    return _read


def _fake_clock(step=10.0):
    t = {"now": 0.0}
    def _clock():
        return t["now"]
    def _sleep(s):
        t["now"] += s
    return _clock, _sleep


def test_settles_when_pending_resolves():
    clock, sleep = _fake_clock()
    out = ci_settle_cli.settle("wi", None, 900, 20,
                               _read=_seq_reader([[{"name": "v", "bucket": "pending"}],
                                                  [{"name": "v", "bucket": "pass"}]]),
                               _sleep=sleep, _clock=clock)
    assert out["settled"] is True
    assert out["checks"] == [{"name": "v", "bucket": "pass"}]


def test_budget_exhaustion_returns_unsettled_with_last_checks():
    clock, sleep = _fake_clock()
    out = ci_settle_cli.settle("wi", None, 60, 20,
                               _read=_seq_reader([[{"name": "v", "bucket": "pending"}]]),
                               _sleep=sleep, _clock=clock)
    assert out["settled"] is False
    assert out["checks"] == [{"name": "v", "bucket": "pending"}]
    assert out["waited_sec"] <= 60


def test_error_and_stale_payloads_stop_the_poll_immediately():
    clock, sleep = _fake_clock()
    for payload in ({"error": "CI status could not be read"}, {"stale": True}):
        out = ci_settle_cli.settle("wi", None, 900, 20,
                                   _read=_seq_reader([payload]), _sleep=sleep, _clock=clock)
        assert out["settled"] is False and out["checks"] == payload
        assert out["waited_sec"] == 0.0   # no blind waiting on an unreadable/stale head


def test_settled_red_is_settled_not_waited_out():
    clock, sleep = _fake_clock()
    out = ci_settle_cli.settle("wi", None, 900, 20,
                               _read=_seq_reader([[{"name": "v", "bucket": "fail"}]]),
                               _sleep=sleep, _clock=clock)
    assert out["settled"] is True   # red IS a settled state — the ship loop's fixer owns it
