"""#2307: every review record the session writer writes carries `sessionCost`, the cost of the reviewer runs
that session's journal shows it dispatched, each run once, across every round and attempt.

Bite-proof record: i2307_session_cost
"""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import review_record as rr  # noqa: E402
import review_record_session as rs  # noqa: E402
import test_c1l11d_carried_review as carried  # noqa: E402
import test_review_record as trr  # noqa: E402
from test_c1l11b_returning_session import _isolated_git  # noqa: E402,F401  (autouse: no global git config)
from test_review_record_session import Fake, Session, send, extras, put_extras, GOOD_RUN, HEAD, EARLIER, KEY, fix_session  # noqa: E402

NONE = {"tokens": 0, "minutes": 0.0, "runs": 0, "runsWithoutFigure": 0, "complete": True, "bySeat": {}}


def run(nonce, tokens=100, wall=120, obs=None):
    """An engine record for the run dir `/run/<nonce>`: the record the reader returns for it."""
    return dict(GOOD_RUN, runnerNonce=nonce, observation=obs if obs is not None else {"tokens": tokens, "wallSeconds": wall}), None


def written(tmp_path, session, runs, dirs=None, **over):
    """Write the session with the given engine records and read the posted record back."""
    fake = Fake(runs={f"/run/{n}": r for n, r in runs.items()})
    out = send(tmp_path, session, fake, ci="green", runDirs=dirs if dirs is not None else sorted(fake.runs), **over)
    assert out["ok"], out
    return rr.read(7, readers=fake.readers())


def test_t1_a_two_round_session_sums_exactly_its_three_runs(tmp_path):
    # axis: the record carries the session's whole reviewer cost
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2307_session_cost.md
    session, _, _ = fix_session(tmp_path)  # two panel seats in round 1 at EARLIER, an audit in round 2 at HEAD
    rec = written(tmp_path, session, {"n1": run("n1", 100, 60), "n2": run("n2", 200, 120), "n3": run("n3", 300, 30)})
    assert rec["sessionCost"] == {
        "tokens": 600, "minutes": 3.5, "runs": 3, "runsWithoutFigure": 0, "complete": True,
        "bySeat": {"code-reviewer": {"tokens": 100, "minutes": 1.0, "runs": 1},
                   "security-reviewer": {"tokens": 200, "minutes": 2.0, "runs": 1},
                   f"audits {KEY}": {"tokens": 300, "minutes": 0.5, "runs": 1}}}
    assert rec["sessionCost"]["complete"] is True


def test_t2_a_carried_reviewer_is_listed_but_never_counted(tmp_path, monkeypatch):
    s = carried._empty_session(tmp_path, monkeypatch)
    fake = Fake(head=s.head)
    def with_cost(rec):  # the earlier review's reviewer carries cost figures of its own
        rec["reviewers"][0]["observation"] = {"tokens": 100, "wallSeconds": 120}
        rec["cost"] = dict(rec["cost"], tokens=100, minutes=2.0)
    earlier = carried._post_earlier(fake, s, edit=with_cost)
    assert earlier["reviewers"][0]["observation"]["tokens"] == 100 and earlier["cost"]["tokens"] == 100
    out = carried._send(tmp_path, s, fake)
    assert out["ok"], out
    rec = carried._latest(fake)
    # bites on: a carried reviewer row's cost counted into this session's cost
    assert [(v["name"], "carried" in v) for v in rec["reviewers"]] == [("code-reviewer", True)]
    assert rec["sessionCost"] == NONE
    assert rec["sessionCost"]["runs"] == 0 and rec["sessionCost"]["complete"] is True


def test_t3_a_run_listed_twice_counts_once_with_its_figures(tmp_path):
    # axis: a run is one nonce, however many slots journal it and however many times its dir is listed
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2307_session_cost.md
    s = Session(tmp_path).seat("code-reviewer", nonce="n1").seat("security-reviewer", nonce="n1")
    rec = written(tmp_path, s.save(), {"n1": run("n1", 100, 120)}, dirs=["/run/n1", "/run/n1"])
    assert rec["sessionCost"] == {"tokens": 100, "minutes": 2.0, "runs": 1, "runsWithoutFigure": 0, "complete": True,
                                  "bySeat": {"code-reviewer": {"tokens": 100, "minutes": 2.0, "runs": 1}}}


@pytest.mark.parametrize("obs", [
    {"wallSeconds": 60},                       # no tokens
    {"tokens": 5},                             # no wall time
    {"tokens": True, "wallSeconds": 60},       # a bool is no count
    {"tokens": 5, "wallSeconds": True},
    {"tokens": -1, "wallSeconds": 60},         # negative
    {"tokens": 5, "wallSeconds": -1},
    "not-a-dict",
], ids=["no-tokens", "no-wall", "bool-tokens", "bool-wall", "neg-tokens", "neg-wall", "no-observation"])
def test_t4_a_run_without_a_figure_is_counted_and_adds_nothing(tmp_path, obs):
    # axis: a run lacking tokens or wall time counts as a run, adds no figure, and makes the cost incomplete
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2307_session_cost.md
    s = Session(tmp_path).seat("code-reviewer", nonce="n1").seat("security-reviewer", nonce="n2")
    rec = written(tmp_path, s.save(), {"n1": run("n1", 100, 120), "n2": run("n2", obs=obs)})
    assert rec["sessionCost"] == {
        "tokens": 100, "minutes": 2.0, "runs": 2, "runsWithoutFigure": 1, "complete": False,
        "bySeat": {"code-reviewer": {"tokens": 100, "minutes": 2.0, "runs": 1},
                   "security-reviewer": {"tokens": 0, "minutes": 0.0, "runs": 1}}}


def test_t4b_an_unreadable_or_ambiguous_engine_record_gives_no_figure():
    # axis: an engine record that raises, is no dict, or whose nonce two different dirs claim gives no figure
    rows = [{"outcome": "recorded", "cmd": "record-result", "phase": "dispatch-panel", "round": 1, "seat": seat, "attempt": 0,
             "executionEvidence": {"runnerNonce": n}} for seat, n in (("a", "n1"), ("b", "n2"), ("c", "n3"), ("d", "n4"))]
    engine = {"/r/boom": None, "/r/str": ("text", None), "/r/x1": run("n3"), "/r/x2": run("n3"), "/r/ok": run("n4", 7, 60)}

    def engine_run(d):
        if d == "/r/boom":
            raise OSError("unreadable")
        return engine[d]
    cost = rs._session_cost(rows, list(engine), engine_run)
    assert (cost["runs"], cost["runsWithoutFigure"], cost["tokens"], cost["minutes"]) == (4, 3, 7, 1.0)
    assert cost["bySeat"]["d"] == {"tokens": 7, "minutes": 1.0, "runs": 1}


def test_t5_per_seat_sums_add_up_to_the_totals(tmp_path):
    # axis: the per-seat figures sum to the totals
    s = Session(tmp_path, rounds={"1": {}, "2": {}})
    s.seat("code-reviewer", nonce="n1").seat("security-reviewer", nonce="n2")
    s.seat("code-reviewer", rnd=2, head=HEAD, nonce="n3").seat("security-reviewer", rnd=2, head=HEAD, nonce="n4")
    rec = written(tmp_path, s.save(), {"n1": run("n1", 10, 36), "n2": run("n2", 20, 42), "n3": run("n3", 30, 48), "n4": run("n4", 40, 54)})
    cost = rec["sessionCost"]
    assert cost["bySeat"] == {"code-reviewer": {"tokens": 40, "minutes": 1.4, "runs": 2},
                              "security-reviewer": {"tokens": 60, "minutes": 1.6, "runs": 2}}
    assert (cost["tokens"], cost["minutes"], cost["runs"], cost["complete"]) == (100, 3.0, 4, True)
    seats = cost["bySeat"].values()
    assert sum(v["tokens"] for v in seats) == cost["tokens"] and sum(v["runs"] for v in seats) == cost["runs"]
    assert round(sum(v["minutes"] for v in seats), 1) == cost["minutes"]


def test_t6_a_session_that_ran_no_reviewer_carries_a_zero_cost(tmp_path):
    # axis: no reviewer ran, so the cost is the empty one and complete
    s = Session(tmp_path, terminal=None)
    session = s.save()
    account = rs.account_from_session(session, extras(), Fake().readers(), abandoned="stopped before any seat ran")
    assert account["sessionCost"] == NONE and isinstance(account["sessionCost"]["minutes"], float)
    fake = Fake()
    out = rs.write_from_session(session, put_extras(tmp_path, extras(ci="green")), str(tmp_path), fake.readers(),
                                abandoned="stopped before any seat ran")
    assert out["ok"], out
    assert rr.read(7, readers=fake.readers())["sessionCost"] == NONE


def test_t6b_a_hand_submit_session_counts_each_seat_its_rounds_say_ran_without_a_figure(tmp_path):
    # axis: a hand submit journals no seat, so each seat that ran is a run with no figure
    s = Session(tmp_path, rounds={"1": {"seatStatus": {"code-reviewer": "run", "security-reviewer": "missing"}}})
    account = rs.account_from_session(s.save(), extras(), Fake().readers())
    assert account["sessionCost"] == {"tokens": 0, "minutes": 0.0, "runs": 1, "runsWithoutFigure": 1, "complete": False,
                                      "bySeat": {"code-reviewer": {"tokens": 0, "minutes": 0.0, "runs": 1}}}


def test_t6c_a_hand_submitted_synthesis_counts_as_a_run_without_a_figure(tmp_path):
    # axis: a hand-accepted synthesis step is a run without a figure under `synthesis synthesis`, once per (round, attempt)
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2307_session_cost.md
    s = Session(tmp_path, rounds={"1": {"seatStatus": {"code-reviewer": "run", "security-reviewer": "missing"}}})
    synthesis = {"outcome": "accepted", "cmd": "submit", "phase": "dispatch-synthesis", "round": 1, "attempt": 0}
    s.rows.append(dict(synthesis))
    cost = rs.account_from_session(s.save(), extras(), Fake().readers())["sessionCost"]
    assert (cost["runs"], cost["runsWithoutFigure"], cost["complete"]) == (2, 2, False)
    assert cost["bySeat"]["synthesis synthesis"] == {"tokens": 0, "minutes": 0.0, "runs": 1}
    s.rows.append(dict(synthesis))  # the same (round, attempt) again: still one run
    cost = rs.account_from_session(s.save(), extras(), Fake().readers())["sessionCost"]
    assert (cost["runs"], cost["runsWithoutFigure"]) == (2, 2)
    assert cost["bySeat"]["synthesis synthesis"] == {"tokens": 0, "minutes": 0.0, "runs": 1}


def test_t7_the_size_trim_leaves_the_session_cost_alone(tmp_path, monkeypatch):
    session, _, _ = fix_session(tmp_path)
    runs = {"n1": run("n1", 100, 60), "n2": run("n2", 200, 120), "n3": run("n3", 300, 30)}
    plain = Fake(runs={f"/run/{n}": r for n, r in runs.items()})
    assert send(tmp_path, session, plain, ci="green", runDirs=sorted(plain.runs))["ok"]
    whole = rr.read(7, readers=plain.readers())
    assert "reviewerShed" not in whole
    for cap in range(len(plain.marked()[0]["body"]) - 10, 2000, -100):  # the first cap at which the reviewer steps of the trim run
        monkeypatch.setattr(rr, "MAX_BODY_CHARS", cap)
        rec = written(tmp_path, session, runs)
        if rec.get("reviewerShed"):
            break
    else:
        pytest.fail("no cap made the reviewer steps of the trim run")
    # bites on: the size trim shedding or altering the cost; the trim must have run for this to mean anything
    assert rec["reviewerShed"], rec.get("reviewerShed")
    assert rec["sessionCost"] == whole["sessionCost"]
    assert rec["sessionCost"]["tokens"] == 600 and rec["sessionCost"]["runs"] == 3


def test_t8_a_rewrite_at_a_new_head_keeps_the_earlier_heads_runs(tmp_path):
    s = Session(tmp_path)
    s.seat("code-reviewer", nonce="n1")
    runs = {"n1": run("n1", 100, 60), "n2": run("n2", 50, 30)}
    fake = Fake(runs={f"/run/{n}": r for n, r in runs.items()})
    assert send(tmp_path, s.save(), fake, ci="green", runDirs=sorted(fake.runs))["ok"]
    assert rr.read(7, readers=fake.readers())["sessionCost"]["runs"] == 1
    s.state["rounds"] = {"1": {}, "2": {}}
    s.seat("code-reviewer", rnd=2, head=HEAD, nonce="n2")
    assert send(tmp_path, s.save(), fake, ci="green", runDirs=sorted(fake.runs))["ok"]
    cost = rr.read(7, readers=fake.readers())["sessionCost"]
    # bites on: a rewrite counting only the runs of the newest head
    assert cost["runs"] == 2 and cost["tokens"] == 150 and cost["minutes"] == 1.5
    assert cost["bySeat"] == {"code-reviewer": {"tokens": 150, "minutes": 1.5, "runs": 2}}


def test_t9_a_superseded_attempt_still_counts(tmp_path):
    # axis: every attempt of a slot is a run the session dispatched
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2307_session_cost.md
    s = Session(tmp_path).seat("code-reviewer", attempt=0, nonce="n1").seat("code-reviewer", attempt=1, nonce="n2")
    rec = written(tmp_path, s.save(), {"n1": run("n1", 100, 60), "n2": run("n2", 200, 120)})
    assert rec["sessionCost"] == {"tokens": 300, "minutes": 3.0, "runs": 2, "runsWithoutFigure": 0, "complete": True,
                                  "bySeat": {"code-reviewer": {"tokens": 300, "minutes": 3.0, "runs": 2}}}


def test_t10_a_synthesis_run_counts_under_its_own_name(tmp_path):
    # axis: the synthesis seat is a reviewer run and costs like one
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2307_session_cost.md
    s = Session(tmp_path).seat("code-reviewer", nonce="n1").seat("grouper", phase="dispatch-synthesis", nonce="n2")
    rec = written(tmp_path, s.save(), {"n1": run("n1", 100, 60), "n2": run("n2", 40, 30)})
    assert rec["sessionCost"]["bySeat"] == {"code-reviewer": {"tokens": 100, "minutes": 1.0, "runs": 1},
                                            "synthesis grouper": {"tokens": 40, "minutes": 0.5, "runs": 1}}
    assert rec["sessionCost"]["runs"] == 2 and rec["sessionCost"]["tokens"] == 140


def test_t11_a_missing_or_advanced_slot_is_a_run_only_with_a_nonce(tmp_path):
    # axis: a slot with no nonce that was not a recorded result never ran; a forfeit with a nonce still cost
    s = Session(tmp_path).seat("code-reviewer", nonce="n1").seat("security-reviewer", cmd="record-missing")
    s.seat("performance-reviewer", cmd="advance", envelope=False)
    rec = written(tmp_path, s.save(), {"n1": run("n1", 100, 60)})
    assert rec["sessionCost"]["runs"] == 1 and set(rec["sessionCost"]["bySeat"]) == {"code-reviewer"}
    again = tmp_path / "again"
    again.mkdir()
    s2 = Session(again)
    s2.seat("code-reviewer", nonce="n1").seat("security-reviewer", cmd="record-missing", nonce="n2")
    rec2 = written(tmp_path, s2.save(), {"n1": run("n1", 100, 60), "n2": run("n2", 40, 30)})
    assert rec2["sessionCost"]["runs"] == 2 and rec2["sessionCost"]["tokens"] == 140
    assert rec2["sessionCost"]["bySeat"]["security-reviewer"] == {"tokens": 40, "minutes": 0.5, "runs": 1}


def test_t11b_an_advance_ingested_host_seat_with_a_stored_result_is_a_run_without_a_figure(tmp_path):
    # axis: a nonce-less advance row counts by slot, without a figure, only when its stored envelope is a real result
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2307_session_cost.md
    s = Session(tmp_path).seat("code-reviewer", cmd="advance").seat("security-reviewer", cmd="advance", envelope=False)
    s.seat("performance-reviewer", cmd="advance")
    path = rs.record_paths.store_path(s.dir, 1, "dispatch-panel", rs.record_paths.storage_key("performance-reviewer", 0), 0)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"payload": {"vacuous": True}}, fh)  # a stored result that says its reviewer did not run
    cost = written(tmp_path, s.save(), {})["sessionCost"]
    assert cost["bySeat"] == {"code-reviewer": {"tokens": 0, "minutes": 0.0, "runs": 1}}
    assert (cost["runs"], cost["runsWithoutFigure"], cost["complete"]) == (1, 1, False)


def test_t11c_two_hand_submitted_audit_targets_of_one_vendor_are_two_runs(tmp_path):
    # axis: a hand-submitted audit is one run per non-silent audit target under `audits <target id>`, never one per vendor
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2307_session_cost.md
    audits = [{"id": "a.py::x@L1", "auditor": "codex"}, {"id": "b.py::y@L2", "auditor": "codex"},
              {"id": "c.py::z@L3", "reason": rs.audits_mod.NO_AUDIT_RESULT_REASON}]
    s = Session(tmp_path, rounds={"1": {"seatStatus": {"code-reviewer": "run"}, "audits": audits}})
    cost = rs.account_from_session(s.save(), extras(), Fake().readers())["sessionCost"]
    assert cost["bySeat"] == {"code-reviewer": {"tokens": 0, "minutes": 0.0, "runs": 1},
                              "audits a.py::x@L1": {"tokens": 0, "minutes": 0.0, "runs": 1},
                              "audits b.py::y@L2": {"tokens": 0, "minutes": 0.0, "runs": 1}}
    assert (cost["runs"], cost["runsWithoutFigure"]) == (3, 3)


def test_t12_a_secret_shaped_seat_key_is_shown_redacted_with_its_figures(tmp_path):
    # axis: a seat key the scrubber would hide is shown neutrally and keeps its figures
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2307_session_cost.md
    secret_seat = "to" + "ken.py::t@L3"
    s = Session(tmp_path, rounds={"1": {}, "2": {}})
    s.seat("code-reviewer", nonce="n1").seat(secret_seat, phase="dispatch-audits", rnd=2, head=HEAD, nonce="n2")
    rec = written(tmp_path, s.save(), {"n1": run("n1", 100, 60), "n2": run("n2", 300, 30)})
    assert rec["sessionCost"]["bySeat"] == {"code-reviewer": {"tokens": 100, "minutes": 1.0, "runs": 1},
                                            "[REDACTED SEAT]": {"tokens": 300, "minutes": 0.5, "runs": 1}}
    assert (rec["sessionCost"]["tokens"], rec["sessionCost"]["minutes"], rec["sessionCost"]["runs"]) == (400, 1.5, 2)


def test_t12b_redacted_seat_keys_stay_distinct():
    # axis: redacting several seat keys keeps every cost bucket under its own distinct neutral key
    cost = {"tokens": 3, "minutes": 0.0, "runs": 3, "runsWithoutFigure": 3, "complete": False,
            "bySeat": {"to" + "ken.py::a": {"tokens": 1, "minutes": 0.0, "runs": 1}, "to" + "ken.py::b": {"tokens": 2, "minutes": 0.0, "runs": 1},
                       "[REDACTED SEAT]": {"tokens": 0, "minutes": 0.0, "runs": 1}}}
    shown = rr._shown_session_cost(cost)["bySeat"]
    assert sorted(shown) == ["[REDACTED SEAT]", "[REDACTED SEAT]-1", "[REDACTED SEAT]-2"]
    assert sorted(v["tokens"] for v in shown.values()) == [0, 1, 2]


GOOD = {"tokens": 10, "minutes": 1.0, "runs": 1, "runsWithoutFigure": 0, "complete": True,
        "bySeat": {"code-reviewer": {"tokens": 10, "minutes": 1.0, "runs": 1}}}
BAD = [
    ("complete-disagrees", dict(GOOD, complete=False), "sessionCost.complete"),
    ("complete-not-bool", dict(GOOD, complete=1), "sessionCost.complete"),
    ("by-seat-tokens-do-not-sum", dict(GOOD, bySeat={"code-reviewer": {"tokens": 9, "minutes": 1.0, "runs": 1}}), "sessionCost.bySeat"),
    ("by-seat-runs-do-not-sum", dict(GOOD, bySeat={"code-reviewer": {"tokens": 10, "minutes": 1.0, "runs": 2}}), "sessionCost.bySeat"),
    ("by-seat-minutes-do-not-sum", dict(GOOD, minutes=2.0), "sessionCost.bySeat"),
    ("unfigured-above-runs", dict(GOOD, runsWithoutFigure=2, complete=False), "sessionCost.runsWithoutFigure"),
    ("bool-tokens", dict(GOOD, tokens=True), "sessionCost"),
    ("negative-minutes", dict(GOOD, minutes=-1.0), "sessionCost"),
    ("extra-key", dict(GOOD, extra=1), "sessionCost"),
    ("missing-key", {k: v for k, v in GOOD.items() if k != "bySeat"}, "sessionCost"),
    ("not-a-dict", [GOOD], "sessionCost"),
    ("blank-seat-key", dict(GOOD, bySeat={" ": {"tokens": 10, "minutes": 1.0, "runs": 1}}), "sessionCost.bySeat"),
    ("seat-extra-key", dict(GOOD, bySeat={"code-reviewer": {"tokens": 10, "minutes": 1.0, "runs": 1, "x": 1}}), "sessionCost.bySeat"),
]


@pytest.mark.parametrize("cost,detail", [(c, d) for _, c, d in BAD], ids=[i for i, _, _ in BAD])
def test_t13_the_validator_refuses_a_malformed_session_cost_and_posts_nothing(tmp_path, cost, detail):
    # axis: a malformed sessionCost is review-account-invalid, naming the path, and nothing is posted
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2307_session_cost.md
    fake = trr.Fake()
    out = rr.write(trr.put(tmp_path, trr.account(sessionCost=cost)), str(tmp_path), fake.readers())
    assert out["ok"] is False and out["reason"] == "review-account-invalid" and out["detail"] == detail, out
    assert fake.comments == []


def test_t13b_a_well_formed_session_cost_and_an_absent_one_are_both_accepted(tmp_path):
    # axis: a valid sessionCost is written as given, and an account with none is accepted and gains no cost field
    fake = trr.Fake()
    assert rr.write(trr.put(tmp_path, trr.account(sessionCost=GOOD)), str(tmp_path), fake.readers())["ok"]
    assert rr.read(7, readers=fake.readers())["sessionCost"] == GOOD
    plain = trr.Fake()
    assert rr.write(trr.put(tmp_path, trr.account()), str(tmp_path), plain.readers())["ok"]
    assert "sessionCost" not in rr.read(7, readers=plain.readers())
