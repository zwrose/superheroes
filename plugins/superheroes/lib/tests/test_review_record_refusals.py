"""#2011 WO-3: the review record carries the refusals a review round's fix recorded.

A refusal stored at `rounds[n]["fix"]["refusals"]` (the apply-fixes fold writes none; a session of
an earlier version holds them) is collected by `account_from_session` as `commandRefusals` (tagged
with its round), validated by the record writer, and rendered as one "Refusals met" summary line. A
session whose fixes met none yields a record with no `commandRefusals` key and no such line.

Bite-proof record: wo3_2011_record
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
import test_review_record as TRR  # noqa: E402
import test_review_record_session as TRS  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD

REFUSAL = {"command": "git push --force origin main", "refusedBy": "hook", "hook": "no-force-push",
           "next": "left the branch unpushed"}
OTHER = {"command": "rm -rf build", "refusedBy": "permission", "next": "removed the files one by one"}


def _fold(state, artifact, index=0):
    state["round"] = 1
    state["_fixBatchIndex"] = index
    RD._fold_apply_fixes(state, state["config"], artifact, changed_subjects_seam=lambda *args: [],
                   panel_diff_seam=lambda config, head: ("", None))


def _state():
    return RD.new_state(TRD._cfg())


@pytest.mark.parametrize("artifact", [{"fixes": []}, {"fixes": [], "refusals": []}, {"fixes": [], "refusals": "x"}])
def test_a_payload_with_no_refusals_leaves_no_key(artifact):
    state = _state()
    _fold(state, artifact)
    assert "refusals" not in state["rounds"]["1"]["fix"]
    _fold(state, artifact, index=1)
    assert "refusals" not in state["rounds"]["1"]["fix"]


def _session(tmp_path, rounds):
    """A terminal session with one fixed finding; `rounds` is the stored rounds map."""
    s = TRS.Session(tmp_path, dispositionLedger=[TRS.ledger_row()], config={"maxRounds": 7, "fixerVendor": "claude"},
                    rounds=rounds, seatMapReceipts=[{"round": "1", "map": {"seats": {}, "makerFamilies": ["xai"]}}])
    s.seat("code-reviewer", nonce="n1")
    s.seat("security-reviewer", nonce="n2")
    s.seat(TRS.KEY, phase="dispatch-audits", rnd=2, head=TRS.HEAD, nonce="n3")
    runs = {f"/run/{n}": (dict(TRS.GOOD_RUN, runnerNonce=n, viewHeadSha=head), None)
            for n, head in (("n1", TRS.EARLIER), ("n2", TRS.EARLIER), ("n3", TRS.HEAD))}
    return s.save(), runs, {"runDirs": sorted(runs)}


def _fix(**over):
    return {"fix": {"fixes": [{"title": "t", "file": "a.py"}], **over}}


def test_the_account_carries_each_refusal_tagged_with_its_round(tmp_path):
    # axis: the collect reads every numbered round's fix refusals, in round order — see bite-proof record wo3_2011_record
    session, runs, ex = _session(tmp_path, {"1": _fix(refusals=[REFUSAL]), "2": _fix(refusals=[OTHER, REFUSAL])})
    acct = rs.account_from_session(session, TRS.extras(**ex), TRS.Fake(runs=runs).readers())
    assert acct["commandRefusals"] == [dict(REFUSAL, round=1), dict(OTHER, round=2), dict(REFUSAL, round=2)]
    assert all(type(e["round"]) is int for e in acct["commandRefusals"])
    assert acct["refused"] == []  # the compile drops are a different list


def test_the_written_record_carries_the_refusal_in_json_and_summary(tmp_path):
    # axis: the record build keeps the account's refusals, and the summary names the command — see bite-proof record wo3_2011_record
    session, runs, ex = _session(tmp_path, {"1": _fix(refusals=[REFUSAL])})
    fake = TRS.Fake(runs=runs)
    out = TRS.send(tmp_path, session, fake, **ex)
    assert out["ok"], out
    rec = rr.read(7, readers=fake.readers())
    assert rec["commandRefusals"] == [dict(REFUSAL, round=1)]
    body = fake.marked()[0]["body"]
    assert ("Refusals met: 1 — round 1: `git push --force origin main` (hook: no-force-push) "
            "→ left the branch unpushed.") in body


def test_a_session_with_no_refusals_has_no_key_and_no_line(tmp_path):
    for rounds in ({"1": _fix()}, {"1": _fix(refusals=[])}, {"1": {"fix": "not-a-dict"}}, {"1": _fix(refusals="x")}):
        sub = tmp_path / str(len(list(tmp_path.iterdir())))
        sub.mkdir()
        session, runs, ex = _session(sub, rounds)
        fake = TRS.Fake(runs=runs)
        out = TRS.send(sub, session, fake, **ex)
        assert out["ok"], out
        rec = rr.read(7, readers=fake.readers())
        assert "commandRefusals" not in rec
        assert "Refusals met" not in fake.marked()[0]["body"]


def test_the_account_collect_skips_what_is_not_a_list_and_never_raises():
    rounds = {"1": {"fix": {"fixes": []}}, "2": {"fix": 3}, "3": "x", "4": {"fix": {"refusals": "x"}},
              "n": {"fix": {"refusals": [REFUSAL]}}, "5": {"fix": {"refusals": [REFUSAL]}}}
    assert rs._command_refusals(rounds) == [dict(REFUSAL, round=5)]


def test_command_refusals_collect_in_numeric_round_order():
    # axis: the collect sorts the round keys numerically, not by insertion or lexical order — see bite-proof record wo5_2011_review_fixes
    rounds = {"10": _fix(refusals=[REFUSAL]), "2": _fix(refusals=[OTHER]), "1": _fix(refusals=[REFUSAL])}
    assert rs._command_refusals(rounds) == [dict(REFUSAL, round=1), dict(OTHER, round=2), dict(REFUSAL, round=10)]


def _validated(entries):
    return rr._validate(TRR.account(commandRefusals=entries))


def test_validate_accepts_a_valid_entry_and_defaults_to_none():
    assert _validated([dict(REFUSAL, round=2), dict(OTHER, round=1)])["commandRefusals"][0]["round"] == 2
    assert rr._validate(TRR.account())["commandRefusals"] == []


@pytest.mark.parametrize("bad", [
    dict(REFUSAL, round=1, command="  "),
    dict(REFUSAL, round=1, refusedBy="other"),
    dict(REFUSAL, round=0),
    dict(REFUSAL, round=True),
    dict(REFUSAL, round="1"),
    {k: v for k, v in dict(REFUSAL, round=1).items() if k != "next"},
    dict(REFUSAL, round=1, extra="x"),
    REFUSAL,
    "not-a-dict",
])
def test_validate_refuses_a_malformed_entry(bad):
    # axis: each entry is a refusal the contract accepts, tagged with a real round — see bite-proof record wo3_2011_record
    with pytest.raises(rr.Refusal) as e:
        _validated([bad])
    assert e.value.reason == "review-account-invalid" and e.value.detail.startswith("commandRefusals[0]")


def test_validate_refuses_a_commandrefusals_that_is_not_a_list():
    with pytest.raises(rr.Refusal) as e:
        _validated({"command": "x"})
    assert (e.value.reason, e.value.detail) == ("review-account-invalid", "commandRefusals")


def test_a_refusal_whose_text_holds_a_forbidden_claim_does_not_refuse_the_record(tmp_path):
    # axis: the refusals line is left out of the claim check; the agent's literal command is data — see bite-proof record wo3_2011_record
    said = dict(REFUSAL, command="echo 'this change is bug-free' > NOTES", next="wrote it to a file instead: no bugs")
    fake = TRR.Fake()
    out = rr.write(TRR.put(tmp_path, TRR.account(commandRefusals=[dict(said, round=1)])), str(tmp_path),
                   fake.readers())
    assert out["ok"], out
    assert "bug-free" in fake.marked()[0]["body"]
    # the check still bites on every other line
    with pytest.raises(rr.Refusal) as e:
        rr._assert_no_bug_free_claim("This change is bug-free.")
    assert e.value.reason == "review-record-forbidden-claim"


def test_a_forbidden_claim_elsewhere_still_refuses_the_record_when_a_refusal_is_present(tmp_path):
    # axis: the summary's claim check still runs over every other line when the refusals line is present — see bite-proof record wo5_2011_review_fixes
    fake = TRR.Fake()
    account = TRR.account(commandRefusals=[dict(REFUSAL, round=1)], reviewers=[TRR.reviewer("bug free")])
    out = rr.write(TRR.put(tmp_path, account), str(tmp_path), fake.readers())
    assert (out["ok"], out.get("reason")) == (False, "review-record-forbidden-claim")
    assert fake.comments == [] and fake.writes == []


def test_the_command_is_fenced_longer_than_any_backtick_run_inside_it():
    line = rr._command_refusals_line([dict(REFUSAL, round=1, command="echo ``x`` y")], False)
    assert "```echo ``x`` y```" in line
    assert rr._inline_code("a`b") == "``a`b``"
    assert rr._inline_code("`a") == "`` `a ``"


def test_the_fence_is_longer_than_the_longest_of_several_backtick_runs():
    # axis: the fence is one longer than the longest backtick run, not the shortest — see bite-proof record wo6_2011_sendback
    assert rr._inline_code("echo ``x`` `y` z") == "```echo ``x`` `y` z```"


ROUTED = dict(REFUSAL, hook="worktree-guard", route="git checkout --theirs f.txt",
              next="took the route the guard named")


def test_the_refusals_line_shows_a_taken_route():
    # axis: the refusals line lists a taken route beside its refusal — see bite-proof record wo_a_2054_route
    line = rr._command_refusals_line([dict(ROUTED, round=3)], False)
    assert ("round 3: `git push --force origin main` (hook: worktree-guard, took `git checkout --theirs f.txt`)"
            " → took the route the guard named") in line


@pytest.mark.parametrize("route", [None, ""])
def test_the_refusals_line_shows_no_route_when_none_was_taken(route):
    line = rr._command_refusals_line([dict(REFUSAL, round=1, route=route)], False)
    assert ", took" not in line
    assert line == rr._command_refusals_line([dict(REFUSAL, round=1)], False)


def test_validate_accepts_a_taken_route_and_refuses_one_on_a_permission_refusal():
    assert _validated([dict(ROUTED, round=1)])["commandRefusals"][0]["route"] == "git checkout --theirs f.txt"
    with pytest.raises(rr.Refusal) as e:
        _validated([dict(OTHER, round=1, route="git status")])
    assert e.value.reason == "review-account-invalid" and e.value.detail.startswith("commandRefusals[0]")


def test_the_compact_level_renders_the_count_form():
    refusals = [dict(REFUSAL, round=1), dict(OTHER, round=2)]
    assert rr._command_refusals_line(refusals, True) == f"Refusals met: 2 refused or denied commands {rr.LISTED}."
    assert rr._command_refusals_line(refusals[:1], True) == f"Refusals met: 1 refused or denied command {rr.LISTED}."


def test_long_command_and_next_text_is_clipped():
    long = "x" * (rr.BASIS_TEXT_MAX + 50)
    line = rr._command_refusals_line([dict(REFUSAL, round=1, command=long, next=long)], False)
    assert long not in line and line.count("…") == 2
