# plugins/superheroes/lib/tests/test_acceptance_ceiling.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_ceiling as c

C = {"elapsed_sec": 1800.0, "spend": 5.0}
EXPECTED_DEFAULT_SPEND = 5_000_000.0
BASE = dict(ceilings=C, attempt=1, budget_consumed={"elapsed_sec": 0.0, "spend": 0.0})


def test_defaults_exist():
    assert c.DEFAULT_CEILINGS["elapsed_sec"] > 0
    assert c.DEFAULT_CEILINGS["spend"] > 0


def test_under_both_ceilings_continues():
    r = c.decide(dict(BASE, elapsed_sec=10.0, spend_sampled=0.5, spend_readable=True))
    assert r["action"] == "continue"


def test_elapsed_breach_kills_naming_elapsed():
    r = c.decide(dict(BASE, elapsed_sec=1801.0, spend_sampled=0.5, spend_readable=True))
    assert r["action"] == "kill" and r["ceiling"] == "elapsed"


def test_spend_breach_kills_naming_spend():
    r = c.decide(dict(BASE, elapsed_sec=10.0, spend_sampled=5.5, spend_readable=True))
    assert r["action"] == "kill" and r["ceiling"] == "spend"


def test_unreadable_spend_governs_on_elapsed_only():
    # spend unreadable -> never kill on spend; only elapsed can trip (fail-closed on readable).
    under = c.decide(dict(BASE, elapsed_sec=10.0, spend_sampled=None, spend_readable=False))
    assert under["action"] == "continue"
    over = c.decide(dict(BASE, elapsed_sec=1801.0, spend_sampled=None, spend_readable=False))
    assert over["action"] == "kill" and over["ceiling"] == "elapsed"


def test_remaining_budget_is_invocation_scoped_for_retry():
    r = c.decide(dict(ceilings=C, attempt=2, elapsed_sec=10.0, spend_sampled=1.0,
                      spend_readable=True, budget_consumed={"elapsed_sec": 600.0, "spend": 2.0}))
    assert r["remaining"]["elapsed_sec"] == 1200.0   # 1800 - 600
    assert r["remaining"]["spend"] == 3.0            # 5 - 2


def test_retry_breach_is_invocation_scoped_not_fresh_ceiling():
    # attempt 2 with 1700s already consumed: a 200s elapsed (1700+200 > 1800) MUST kill,
    # even though 200s alone is far under the 1800s ceiling. Same for spend.
    r = c.decide(dict(ceilings=C, attempt=2, elapsed_sec=200.0, spend_sampled=0.5,
                      spend_readable=True, budget_consumed={"elapsed_sec": 1700.0, "spend": 0.0}))
    assert r["action"] == "kill" and r["ceiling"] == "elapsed"
    s = c.decide(dict(ceilings=C, attempt=2, elapsed_sec=10.0, spend_sampled=1.0,
                      spend_readable=True, budget_consumed={"elapsed_sec": 0.0, "spend": 4.5}))
    assert s["action"] == "kill" and s["ceiling"] == "spend"   # 4.5+1.0 > 5.0


def test_partial_owner_ceilings_merge_with_defaults_and_never_raise():
    assert c.DEFAULT_CEILINGS["spend"] == EXPECTED_DEFAULT_SPEND
    r = c.decide({
        "ceilings": {"elapsed_sec": 10.0},
        "elapsed_sec": 1.0,
        "spend_sampled": 0.5,
        "spend_readable": True,
        "budget_consumed": {"elapsed_sec": 0.0, "spend": 0.0},
    })
    assert r["action"] == "continue"
    assert r["remaining"]["elapsed_sec"] == 10.0
    assert r["remaining"]["spend"] == EXPECTED_DEFAULT_SPEND
