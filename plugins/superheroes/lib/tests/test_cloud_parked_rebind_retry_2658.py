from pathlib import Path

from test_cloud_parked import (  # noqa: F401 (w is a fixture)
    RELAUNCHED,
    _entries,
    _lane,
    _lapsed_comment,
    _notice,
    _park,
    _supersede,
    ll,
    w,
)


def test_a_newer_park_retries_rebind_after_the_ledger_recovers(w):
    # axis: an unreadable rebind keeps the previous park and launch so the same new park can be retried
    _lane(w, "l-old", 101, "old-session", "a", finished=True)
    _park(w, 10, issue=101)
    _supersede(w, "l-old")
    _lane(w, "l-new", 101, "new-session", "a2", ts=RELAUNCHED)
    w.gh.comments[10].append(_lapsed_comment(10, created_at="2026-10-11T10:00:00Z", cid=1010))
    w.gh.closing[10] = None
    before = _entries(w)
    ledger = Path(ll.ledger_path(w.repo, w.env)["path"])
    clean = ledger.read_bytes()
    ledger.write_bytes(clean + b"not JSON\n")

    try:
        refused = _notice(w, 10)
        after = _entries(w)
    finally:
        ledger.write_bytes(clean)

    assert refused == {"ok": False, "reason": "launch-ledger-unreadable"}
    assert after == before
    assert _notice(w, 10)["ok"] is True
    assert (_entries(w)[0]["launchId"], _entries(w)[0]["parkId"]) == ("l-new", 1010)
