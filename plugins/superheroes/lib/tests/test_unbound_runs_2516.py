"""#2516: the review record names every reviewer run the session cost counts that carries a runner nonce no single run
folder among the extras' `runDirs` claims, as `unboundRuns` (`{seat, nonce, case}`), and the write succeeds either way.
`sessionCost` is computed in the same pass and is unchanged.

Bite-proof record: i2516_unbound_runs
"""
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
import test_review_record as trr  # noqa: E402
from test_c1l11b_returning_session import _isolated_git  # noqa: E402,F401  (autouse: no global git config)
from test_review_record_session import Fake, Session, send, extras, GOOD_RUN  # noqa: E402
from test_review_record_session_cost_2307 import run, written  # noqa: E402

N2 = {"seat": "security-reviewer", "nonce": "n2", "case": "not-in-extras"}
N2_UNMATCHED = dict(N2, case="unmatched")


def two_seats(tmp_path):
    return Session(tmp_path).seat("code-reviewer", nonce="n1").seat("security-reviewer", nonce="n2")


class Raising(Fake):
    """A Fake whose engine reader raises for the folder `/run/boom`."""

    def readers(self):
        base = super().readers()
        inner = base["engine_run"]

        def engine_run(d):
            if d == "/run/boom":
                raise OSError("unreadable")
            return inner(d)
        return {**base, "engine_run": engine_run}


def test_t1_a_run_whose_folder_the_extras_leave_out_is_named_not_in_extras(tmp_path):
    # axis: a nonce no listed folder claims, with every listed folder naming a run of this session, is `not-in-extras`
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2516_unbound_runs.md
    rec = written(tmp_path, two_seats(tmp_path).save(), {"n1": run("n1")})
    assert rec["unboundRuns"] == [N2]
    assert rec["sessionCost"]["runsWithoutFigure"] == 1 and rec["sessionCost"]["runs"] == 2


def test_t1b_a_found_folder_with_no_figure_is_neither_foreign_nor_unbound(tmp_path):
    # axis: a folder whose nonce belongs to a run is never foreign and never lists its run, whatever its `attemptsCost`
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2516_unbound_runs.md
    figureless = (dict(GOOD_RUN, runnerNonce="n1"), None)  # GOOD_RUN carries an observation and no attemptsCost
    rec = written(tmp_path, two_seats(tmp_path).save(), {"n1": figureless})
    assert rec["unboundRuns"] == [N2]
    assert rec["sessionCost"]["runsWithoutFigure"] == 2


@pytest.mark.parametrize("shape", ["other-nonce", "error-record", "no-nonce", "raises", "blank-nonce"])
def test_t2_a_nonce_no_folder_claims_beside_a_foreign_folder_is_unmatched(tmp_path, shape):
    # axis: a folder that raised, is no dict, carries no nonce or one no run has makes an unclaimed nonce `unmatched`
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2516_unbound_runs.md
    dirs = ["/run/n1", "/run/x"]
    runs = {"/run/n1": run("n1")}
    if shape == "other-nonce":
        runs["/run/x"] = run("n9")
    elif shape == "error-record":
        runs["/run/x"] = (None, "error")
    elif shape == "no-nonce":
        runs["/run/x"] = (dict(GOOD_RUN), None)
    elif shape == "blank-nonce":
        runs["/run/x"] = (dict(GOOD_RUN, runnerNonce=""), None)
    else:
        dirs = ["/run/n1", "/run/boom"]
    fake = Raising(runs=runs)
    out = send(tmp_path, two_seats(tmp_path).save(), fake, ci="green", runDirs=dirs)
    assert out["ok"], out
    assert rr.read(7, readers=fake.readers())["unboundRuns"] == [N2_UNMATCHED]


def test_t2c_a_nonce_two_different_folders_claim_is_unmatched(tmp_path):
    # axis: two different folders claiming one nonce leave that run unbound, `unmatched`, though both folders are listed
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2516_unbound_runs.md
    rec = written(tmp_path, two_seats(tmp_path).save(), {"n1": run("n1"), "n2a": run("n2"), "n2b": run("n2")})
    assert rec["unboundRuns"] == [N2_UNMATCHED]
    assert rec["sessionCost"]["runsWithoutFigure"] == 1


def test_t3_a_run_whose_folder_is_listed_is_never_named(tmp_path):
    # axis: a nonce exactly one folder claims is bound and never listed, in the record or the account
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2516_unbound_runs.md
    session = two_seats(tmp_path).save()
    runs = {"n1": run("n1"), "n2": run("n2")}
    assert "unboundRuns" not in written(tmp_path, session, runs)
    fake = Fake(runs={f"/run/{n}": r for n, r in runs.items()})
    account = rs.account_from_session(session, extras(runDirs=sorted(fake.runs)), fake.readers())
    assert "unboundRuns" not in account


@pytest.mark.parametrize("dirs", [["/run/n1"], ["/run/n1", "/run/n1"]], ids=["listed-once", "listed-twice"])
def test_t3b_two_slots_sharing_one_nonce_with_its_one_folder_listed_are_never_named(tmp_path, dirs):
    # axis: one nonce, however many slots journal it and however many times its folder is listed, is one bound run
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2516_unbound_runs.md
    s = Session(tmp_path).seat("code-reviewer", nonce="n1").seat("security-reviewer", nonce="n1")
    assert "unboundRuns" not in written(tmp_path, s.save(), {"n1": run("n1")}, dirs=dirs)


def test_t4_a_run_with_no_nonce_and_a_hand_run_are_never_named():
    # axis: only a run that carries a runner nonce can be unbound; a nonce-less run and a hand run are never listed
    rows = [{"outcome": "recorded", "cmd": "record-result", "phase": "dispatch-panel", "round": 1, "seat": seat, "attempt": 0,
             "executionEvidence": ev} for seat, ev in (("bare", None), ("blank", {"runnerNonce": " "}), ("named", {"runnerNonce": "n9"}))]
    cost, unbound = rs._cost_and_unbound(rows, [], lambda d: run("n9"), hand=("by-hand",))
    assert cost["runs"] == 4 and cost["runsWithoutFigure"] == 4
    assert unbound == [{"seat": "named", "nonce": "n9", "case": "not-in-extras"}]


def test_t5_nothing_unbound_writes_no_key_at_all(tmp_path):
    # axis: an empty unbound list is no key, never `[]`, in the account
    session = Session(tmp_path, terminal=None).save()
    account = rs.account_from_session(session, extras(), Fake().readers(), abandoned="stopped before any seat ran")
    assert "unboundRuns" not in account and account["sessionCost"]["runs"] == 0


GOOD_UNBOUND = [{"seat": "code-reviewer", "nonce": "n1", "case": "not-in-extras"},
                {"seat": "security-reviewer", "nonce": "n2", "case": "unmatched"}]


@pytest.mark.parametrize("bad", [
    [dict(N2, case="elsewhere")],
    [dict(N2, case="")],
    [dict(N2, extra=1)],
    [{"seat": "s", "nonce": "n"}],
    [dict(N2, nonce="")],
    [dict(N2, nonce="  ")],
    [dict(N2, nonce=5)],
    [dict(N2, seat="")],
    [dict(N2, seat=None)],
    [N2, "not an entry"],
    dict(N2),
    "unbound",
], ids=["unknown-case", "empty-case", "extra-key", "missing-key", "blank-nonce", "space-nonce", "int-nonce", "blank-seat",
        "none-seat", "non-dict-entry", "dict-not-list", "string-not-list"])
def test_t5_the_validator_refuses_a_malformed_part_by_name_and_posts_nothing(tmp_path, bad):
    # axis: the writer's validation of the part: exactly the keys seat, nonce, case; non-blank seat and nonce; a known case; a list
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2516_unbound_runs.md
    fake = trr.Fake()
    out = rr.write(trr.put(tmp_path, trr.account(unboundRuns=bad)), str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"], out["detail"]) == (False, "review-account-invalid", "unboundRuns"), out
    assert fake.comments == []


def test_t5b_a_well_formed_part_and_an_absent_one_are_both_accepted(tmp_path):
    # axis: a valid part is written as given and an account with none is accepted and gains no key
    fake = trr.Fake()
    assert rr.write(trr.put(tmp_path, trr.account(unboundRuns=GOOD_UNBOUND)), str(tmp_path), fake.readers())["ok"]
    assert rr.read(7, readers=fake.readers())["unboundRuns"] == GOOD_UNBOUND
    plain = trr.Fake()
    assert rr.write(trr.put(tmp_path, trr.account()), str(tmp_path), plain.readers())["ok"]
    assert "unboundRuns" not in rr.read(7, readers=plain.readers())
    assert "unboundRuns" not in trr.build(trr.account(unboundRuns=[]))


def unbound_lines(rec, level):
    return [l for l in rr._summary(rec, level).split("\n") if l.startswith("Unbound runs:")]


def test_t6_level_zero_names_each_run_and_the_compact_levels_give_the_count():
    rec = trr.build(trr.account(unboundRuns=[N2]))
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2516_unbound_runs.md
    # axis: level 0 names every run (seat, nonce, case) and the compact levels give only the count
    assert unbound_lines(rec, 0) == ["Unbound runs: security-reviewer nonce n2 (not-in-extras)."]
    assert unbound_lines(rec, 1) == [f"Unbound runs: 1 run {rr.LISTED}."]
    assert unbound_lines(rec, 2) == [f"Unbound runs: 1 run {rr.LISTED}."]
    two = trr.build(trr.account(unboundRuns=GOOD_UNBOUND))
    assert unbound_lines(two, 0) == [
        "Unbound runs: code-reviewer nonce n1 (not-in-extras); security-reviewer nonce n2 (unmatched)."]
    assert unbound_lines(two, 1) == [f"Unbound runs: 2 runs {rr.LISTED}."]
    assert not unbound_lines(trr.build(trr.account()), 0)


def test_t6b_a_seat_or_nonce_the_scrubber_would_hide_reads_redacted_and_a_bug_free_seat_name_does_not_refuse():
    # axis: the record shows a hidden seat as `[REDACTED SEAT]` and a hidden nonce as `[REDACTED NONCE]`; the line is left out of the claim check
    secret = "pass" + "word=hunter2"
    rec = trr.build(trr.account(unboundRuns=[dict(N2, seat=secret, nonce=secret), dict(N2, seat="no bugs reviewer")]))
    assert [(e["seat"], e["nonce"]) for e in rec["unboundRuns"]] == [("[REDACTED SEAT]", "[REDACTED NONCE]"), ("no bugs reviewer", "n2")]
    assert "hunter2" not in rr._summary(rec, 0)
    assert "[REDACTED SEAT] nonce [REDACTED NONCE] (not-in-extras)" in rr._summary(rec, 0)


def _engine(runs):
    return lambda d: runs.get(d, (dict(GOOD_RUN), None))


def test_t7_the_session_cost_is_the_first_part_of_the_same_pass(tmp_path):
    # axis: `_session_cost` is exactly the cost `_cost_and_unbound` returns, for the not-in-extras and the clash sessions
    # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2516_unbound_runs.md
    s = two_seats(tmp_path)
    for runs, dirs in (({"/run/n1": run("n1")}, ["/run/n1"]),
                       ({"/run/n1": run("n1"), "/run/n2a": run("n2"), "/run/n2b": run("n2")}, ["/run/n1", "/run/n2a", "/run/n2b"])):
        engine = _engine(runs)
        cost, unbound = rs._cost_and_unbound(s.rows, dirs, engine)
        assert rs._session_cost(s.rows, dirs, engine) == cost
        assert unbound and cost["runsWithoutFigure"] == 1
