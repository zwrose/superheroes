"""C1-L4b: a session saved inside an ordered extra audit round finishes that round, and its record says so.

The round audits only the cap round's fixes. It dispatches no panel, scoped finder, seams check, fixer or verify
run, it is labelled in the record, and it is never counted in the cap. The `extra-audit` verb that ordered it is
retired (it refuses `extra-audit-retired`; see `test_extra_audit_retired_2553.py`), so these tests build the state an
ordered round leaves without the verb: a session handed back at its cap with the bounded pass switched off, then the
writes the verb made (`_legacy_extra_round`).

Drives the real round driver through the CLI functions (`cmd_next`, `cmd_submit`) on a session directory built
the way production builds one, and the review record writer through its injected readers.

Bite-proof records: c1l4b_wo_a, c1l4b_wo_g
"""
import hashlib
import os
import sys
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import review_record as RR  # noqa: E402
import review_record_session as RS  # noqa: E402
import test_outcome_settle_c7 as TOC  # noqa: E402
import test_review_record as TRR  # noqa: E402
import test_review_record_session as TRRS  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD  # the driver module these sessions run on is test_round_driver's own load of it

CAP = 2
PR = 2239
WHY = "the advisor wants the cap round's fixes audited once"
VENDORS = ["claude", "codex"]
SUPERSEDED = "round-receipt.superseded-1.json"


# --- a session driven through the CLI functions ----------------------------------------------------

def _finding(title, severity="Important", file="newsurf.py"):
    return {"title": title, "severity": severity, "consequence": TRD._CONSEQUENCE, "file": file, "line": 1}


def _audit_artifact(payload, extra_round, extra, fail_titles):
    results = []
    for t in payload.get("targets", []):
        failing = extra == "not-discharged" if extra_round else t.get("title") in fail_titles
        row = {"id": t["id"], "auditorVendor": t.get("auditorVendor"), "checks": TRD.audit_checks()}
        if failing:
            row.update(ruling="not-discharged", reason="still broken")
        elif extra_round and extra == "new-issue":
            row.update(ruling="discharged-but-new-issue", reason="fix resolves it", evidence="tests pass",
                       newIssues=[_finding("raised-by-the-audit")])
        else:
            row.update(ruling="discharged", reason="fix resolves it", evidence="tests pass")
        results.append(row)
    return {"results": results,
            "collectionManifest": {t["id"]: t.get("auditorVendor") for t in payload.get("targets", [])}}


def _respond(cap=CAP, scoped=None, fail_titles=(), extra="discharged", findings=True):
    """Scripted answers: the panel raises one blocker, the scoped finder raises a new one in `scoped`'s rounds
    (by default the cap round), every audit discharges except `fail_titles`, and the extra round (any round past
    the cap) answers `extra`: discharged, not-discharged or new-issue."""
    scoped = {cap: [_finding("open-important")]} if scoped is None else scoped
    base = TRD._responder(round1_findings=list(TRD._A_FINDING) if findings else None, vendors=VENDORS)
    fixes = {"n": 0}

    def respond(phase, payload, rnd):
        if phase == RD.P_SCOPED:
            return {"findings": [dict(f) for f in scoped.get(rnd, [])]}
        if phase == RD.P_APPLY_FIXES:
            fixes["n"] += 1
            return {"fixes": [], "headDiff": TRD._headf_ns(fixes["n"]), "changedSubjects": ["Code"]}
        if phase == RD.P_AUDITS:
            return _audit_artifact(payload, rnd > cap, extra, fail_titles)
        return base(phase, payload, rnd)

    return respond


def _start(tmp_path, cap=CAP):
    """A fresh session directory inside its own real checkout, seeded as review setup seeds one."""
    d = str(tmp_path / "session")
    os.makedirs(d)
    checkout = str(tmp_path / "checkout")
    TRD.enter_checkout(checkout)
    TRD._seed_repo_root_if_missing(d, checkout)
    return d, TRD._cfg(maxRounds=cap)


def _drive(d, respond, cfg=None, max_steps=200):
    """next/submit until `next` emits the terminal; return that `next` answer and every action emitted."""
    emitted = []
    for step in range(max_steps):
        n = RD.cmd_next(d, cfg if step == 0 else None)
        assert n["ok"], n
        emitted.append(n["action"])
        if n["action"] == RD.P_TERMINAL:
            return n, emitted
        art = TRD._claim_reviewer(d, n["phase"], respond(n["phase"], n["payload"], n["round"]))
        s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert s["ok"], s
    raise AssertionError("the session did not reach a terminal in %d steps" % max_steps)


def _hand_back_at_cap(state, config, trigger):
    """What a session did at its cap when no bounded pass ran: hand back `round-cap` with the cap round's
    fix never audited. The state a legacy extra round starts from."""
    RD._cap_blocks(state, config, state["round"] + 1, "post-verify-advance")


def _capped(tmp_path, cap=CAP, **script):
    """A finalized session handed back at its cap with the cap round's fix never audited: the bounded pass
    is switched off while the session runs, so it ends the way a session with no pass ends."""
    d, cfg = _start(tmp_path, cap)
    with pytest.MonkeyPatch.context() as off:
        off.setattr(RD, "_begin_bounded_pass", _hand_back_at_cap)
        terminal, _emitted = _drive(d, _respond(cap=cap, **script), cfg)
    assert terminal["payload"]["verdict"] == "handed-back", terminal
    state = _state(d)
    assert state["decisions"][-1]["kind"] == "round-cap" and state["round"] == cap, state["decisions"][-3:]
    assert state["_receiptFinalized"] is True
    return d


def _state(d):
    ok, state = RD.load_state(d)
    assert ok and state is not None
    return state


def _legacy_extra_round(d, why=WHY, by="advisor"):
    """The state an ordered extra audit round saved: a session handed back at its cap (the pass switched
    off) gets the writes the retired verb made, in its order, committed the way it committed them.

    The receipt is copied byte for byte to its superseded name (None for both when the session has no
    receipt), `extraAudit` is recorded, the terminal and the certification are cleared, the receipt marks
    are dropped, the order is a decision, and round `cap + 1` begins."""
    state = _state(d)
    config = state.get("config") or {}
    cap = RD._round_cap(config)
    receipt_path = os.path.join(d, RD.RECEIPT_FILE)
    superseded, sha = None, None
    if os.path.lexists(receipt_path):
        original = _read(d, RD.RECEIPT_FILE)
        sha = hashlib.sha256(original).hexdigest()
        RD.round_commit.atomic_write_bytes(os.path.join(d, SUPERSEDED), original)
        superseded = SUPERSEDED
    state["extraAudit"] = {"why": why, "by": by, "round": cap + 1,
                           "orderedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                           "supersededReceipt": superseded, "supersededReceiptSha256": sha}
    RD._set_terminal(state, None)
    state["certification"] = None
    state["pending"] = None
    for mark in RD._RECEIPT_FINALIZED_MARKS:
        state.pop(mark, None)
    RD._decision(state, "extra-audit-ordered", "extra audit round %d ordered by %s: %s" % (cap + 1, by, why))
    RD._begin_post_cap_round(state, config)
    entry = RD._journal_entry_for_commit(d, RD.EXTRA_AUDIT_CMD, "accepted", round=cap + 1, by=by, pr=PR,
                                         supersededReceiptSha256=sha)
    c = RD.round_commit.begin(d, "extra-audit-order")
    RD._stage_state(c, d, RD._canonical(state).encode("utf-8"))
    c.add_journal_append(os.path.join(d, RD.JOURNAL_FILE), entry)
    c.run()


def _files(d):
    """sha256 of every file in the session directory but the journal and the lock."""
    skip = (RD.JOURNAL_FILE, RD.round_records.LOCK_FILE)
    out = {}
    for root, _dirs, names in os.walk(d):
        for name in names:
            rel = os.path.relpath(os.path.join(root, name), d)
            if rel not in skip:
                with open(os.path.join(root, name), "rb") as fh:
                    out[rel] = hashlib.sha256(fh.read()).hexdigest()
    return out


def _read(d, name):
    with open(os.path.join(d, name), "rb") as fh:
        return fh.read()


def _ordered(tmp_path, **script):
    """A capped session holding a legacy extra audit round. Returns (session dir, the cap round's fix batch keys)."""
    d = _capped(tmp_path, **script)
    batch = RD._fix_batch_keys(_state(d))
    assert batch, "the cap round applied no fix batch"
    _legacy_extra_round(d)
    return d, batch


def _finish(d, respond):
    """next/submit from an ordered session to its terminal; the actions emitted on the way."""
    return _drive(d, respond)


def _rows(state, title):
    """The disposition-ledger rows titled `title`."""
    return [e for e in state.get(RD.session_contract.DISPOSITION_LEDGER_KEY) or [] if e.get("title") == title]


def _account(tmp_path, state):
    session = TRRS.Session(tmp_path / "rec", **state).seat("code-reviewer").save()
    return RS.account_from_session(session, TRRS.extras())


# --- T1: an ordered extra round audits the cap round's fixes and converges ---------------------------

def test_t1_an_ordered_extra_round_dispatches_only_the_audits_and_a_discharge_converges(tmp_path):
    # axis: the extra round's actions are the audits and the terminal, over exactly the cap round's fix batch;
    # the record counts the cap rounds and labels the extra one — see bite-proof record c1l4b_wo_a
    d, batch = _ordered(tmp_path)
    state = _state(d)
    assert state["round"] == CAP + 1 and not state.get("terminal") and state["step"] == RD.P_AUDITS
    assert state["extraAudit"]["round"] == CAP + 1 and state["extraAudit"]["why"] == WHY
    assert [dec["kind"] for dec in state["decisions"]][-1] == "extra-audit-ordered"
    n = RD.cmd_next(d)
    assert n["ok"] and n["action"] == RD.P_AUDITS and n["round"] == CAP + 1, n
    assert [t["id"] for t in n["payload"]["targets"]] == batch
    assert "verify" not in n["payload"]
    terminal, emitted = _finish(d, _respond())
    assert emitted == [RD.P_AUDITS, RD.P_TERMINAL], emitted
    assert terminal["payload"]["verdict"] == "converged"
    final = _state(d)
    assert final["terminal"] == "converged" and final["decisions"][-1]["kind"] == "converged"
    assert sorted(final["rounds"]) == ["1", "2", "3"] and final["round"] == CAP + 1
    rows = _rows(final, "open-important")
    assert len(rows) == 1 and rows[0]["disposition"] == "fixed", rows
    assert "settledReason" not in rows[0]
    account = _account(tmp_path, final)
    assert account["rounds"]["count"] == CAP
    assert account["rounds"]["extraAudit"] == {"why": WHY}
    assert account["rounds"]["stoppedAtCap"] is False
    RR._validate(account)


# --- T2: a non-discharging extra audit hands the PR back open ----------------------------------------

def test_t2_a_non_discharging_extra_audit_hands_back_open_with_no_further_round(tmp_path):
    # axis: the extra round runs no scoped finder, fixer or recovery after its audits, whatever they find
    # — see bite-proof record c1l4b_wo_a
    d, batch = _ordered(tmp_path, extra="not-discharged")
    terminal, emitted = _finish(d, _respond(extra="not-discharged"))
    assert emitted == [RD.P_AUDITS, RD.P_TERMINAL], emitted
    assert terminal["payload"]["verdict"] == "handed-back"
    final = _state(d)
    assert final["terminal"] == "handed-back" and final["decisions"][-1]["kind"] == "extra-audit-open"
    assert final["round"] == CAP + 1 and sorted(final["rounds"]) == ["1", "2", "3"]
    rows = _rows(final, "open-important")
    assert len(rows) == 1 and rows[0]["disposition"] == "left-for-owner" and rows[0]["settledReason"], rows
    account = _account(tmp_path, final)
    assert account["rounds"]["stoppedAtCap"] is True and account["rounds"]["count"] == CAP
    assert account["rounds"]["extraAudit"] == {"why": WHY}
    outcomes = [f["outcome"] for f in account["findings"] if f["title"] == "open-important"]
    assert outcomes == ["left-for-owner"], account["findings"]
    again = RD.cmd_next(d)
    assert again["ok"] and again["action"] == RD.P_TERMINAL
    assert _state(d)["round"] == CAP + 1


def test_t2b_a_new_issue_raised_by_the_extra_audit_is_settled_and_never_searched(tmp_path):
    # axis: an audit's new issue ends with an outcome at the extra round's terminal and opens no scoped round
    d, batch = _ordered(tmp_path)
    terminal, emitted = _finish(d, _respond(extra="new-issue"))
    assert emitted == [RD.P_AUDITS, RD.P_TERMINAL], emitted
    final = _state(d)
    assert final["terminal"] == "handed-back" and final["decisions"][-1]["kind"] == "extra-audit-open"
    assert [r["disposition"] for r in _rows(final, "open-important")] == ["fixed"]
    raised = _rows(final, "raised-by-the-audit")
    assert len(raised) == 1 and raised[0]["disposition"] == "left-for-owner", raised
    assert "_newIssues" not in final


# --- T2c: guidance no fixer ever received keeps the extra round from converging ------------------------

_RULED_KEY = "f.py::bug@L1"  # the panel's round-1 finding: fixed and audited long before the extra round


def _guided_extra_round(tmp_path, ruled):
    """An ordered extra round whose audits all discharge; with `ruled`, a guidance ruling on a session
    finding the extra round's audit targets do not carry is recorded after the order and before the audits."""
    d, batch = _ordered(tmp_path)
    assert _RULED_KEY not in batch, batch
    if ruled:
        path = TOC._write_rulings(tmp_path / "rulings.json", [
            {"id": _RULED_KEY, "ruling": "guidance", "reason": "the owner wants it handled this way",
             "guidance": "keep the public signature as it is"}])
        out = RD.cmd_rule(d, path, "owner")
        assert out.get("ok"), out
        assert [r["ruling"] for r in _state(d)["rulingsLog"]] == ["guidance"]
    terminal, emitted = _finish(d, _respond())
    assert emitted == [RD.P_AUDITS, RD.P_TERMINAL], emitted
    return terminal, _state(d)


def test_t2c_a_guidance_ruling_no_fixer_received_hands_the_extra_round_back_open(tmp_path):
    # axis: a guidance ruling no fixer ever received keeps the extra round from converging — see bite-proof record c1l4b_wo_g
    terminal, final = _guided_extra_round(tmp_path, ruled=True)
    assert terminal["payload"]["verdict"] == "handed-back"
    assert final["terminal"] == "handed-back" and final["decisions"][-1]["kind"] == "extra-audit-open"
    detail = final["decisions"][-1]["detail"]
    assert "guidance recorded but never sent to a fixer" in detail and "(guidance)" in detail, detail
    assert final["certification"]["shape"] is None and "(guidance)" in final["certification"]["reason"]


def test_t2c_the_same_extra_round_without_the_ruling_converges(tmp_path):
    # axis: A/B for the test above — with no ruling recorded the same discharged audits converge
    terminal, final = _guided_extra_round(tmp_path, ruled=False)
    assert terminal["payload"]["verdict"] == "converged"
    assert final["terminal"] == "converged" and final["decisions"][-1]["kind"] == "converged"
    assert not final.get("rulingsLog")


# --- T6: a legacy round resumed by a fresh `next` -----------------------------------------------------

def test_t6b_after_the_order_a_fresh_next_emits_the_audits_and_the_session_completes(tmp_path):
    # axis: the saved order is the whole reopen — nothing else is owed before the audits are dispatched
    d, batch = _ordered(tmp_path)
    first = RD.cmd_next(d)
    second = RD.cmd_next(d)
    assert first["action"] == RD.P_AUDITS and second["expectedStateHash"] == first["expectedStateHash"]
    assert [t["id"] for t in second["payload"]["targets"]] == batch
    terminal, _emitted = _finish(d, _respond())
    assert terminal["payload"]["verdict"] == "converged"
    assert RD._verify_terminal_receipt(d) is None


# --- T9: the loaded-state guard ----------------------------------------------------------------------

@pytest.mark.parametrize("extra,rnd", [(None, CAP + 1),
                                       ({"why": "x", "round": CAP + 2}, CAP + 1),
                                       ({"why": "x", "round": CAP + 2}, CAP + 2)],
                         ids=["no-order", "order-for-another-round", "two-past-the-cap"])
def test_t9_a_loaded_state_above_its_cap_without_its_order_still_hands_back(tmp_path, extra, rnd):
    # axis: a state above its cap without the matching order still hands back `round-cap` — see bite-proof record c1l4b_wo_a
    d = str(tmp_path)
    assert RD.cmd_next(d, TRD._cfg(maxRounds=CAP))["ok"]
    state = _state(d)
    assert not state.get("terminal")
    state["round"] = rnd
    # a later round has no panel to wait at (a saved one is retired on load), so the state waits at verify
    state["step"] = RD.P_VERIFY
    state["pending"] = None
    if extra is not None:
        state["extraAudit"] = extra
    RD.save_state(d, state)
    out = RD.cmd_next(d)
    assert out["ok"] and out["phase"] == RD.P_TERMINAL, out
    final = _state(d)
    assert final["terminal"] == "handed-back" and final["decisions"][-1]["kind"] == "round-cap"


def test_t9_a_state_ordered_its_extra_round_is_not_handed_back_on_load(tmp_path):
    d, _batch = _ordered(tmp_path)
    out = RD.cmd_next(d)
    assert out["ok"] and out["action"] == RD.P_AUDITS, out
    assert not _state(d).get("terminal")


# --- the extra round composes no panel ---------------------------------------------------------------

def test_t11_a_surface_the_extra_round_cannot_derive_hands_back_instead_of_scheduling_a_panel(tmp_path):
    d = _capped(tmp_path)
    state = _state(d)
    state["_headDiffUnknown"] = True  # the cap round's post-fix head diff could not be resolved
    RD.save_state(d, state)
    _legacy_extra_round(d)
    final = _state(d)
    assert final["terminal"] == "handed-back" and final["decisions"][-1]["kind"] == "extra-audit-open"
    assert final["round"] == CAP + 1 and final["step"] == RD.P_TERMINAL
    n = RD.cmd_next(d)
    assert n["ok"] and n["action"] == RD.P_TERMINAL, n
    assert _state(d)["decisions"][-1]["kind"] == "extra-audit-open"


def test_t12_a_lane_that_would_need_a_panel_hands_back_instead_of_halting_for_a_recompose(tmp_path, monkeypatch):
    import lane_call
    d = _capped(tmp_path)
    monkeypatch.setattr(lane_call, "call", lambda root, paths, proposed=None: {"floor": "full"})
    state = _state(d)
    state["config"]["seatMap"] = {"laneBasis": {"floor": None}}
    RD.save_state(d, state)
    _legacy_extra_round(d)
    final = _state(d)
    assert final["terminal"] == "handed-back" and final["decisions"][-1]["kind"] == "extra-audit-open"
    assert not any(dec["kind"] == RD.LANE_EXPANDED_RECOMPOSE for dec in final["decisions"])


# --- T10: the record writer's backstop ---------------------------------------------------------------

def _extra_account(session_id):
    return TRR.account(sessionId=session_id,
                       rounds={"count": 3, "cap": 4, "stoppedAtCap": False, "extraAudit": {"why": WHY}})


def test_t10_the_writer_refuses_a_second_sessions_record_that_shows_the_extra_round(tmp_path):
    # axis: another session's earlier record that shows the round refuses this one's — see bite-proof record c1l4b_wo_a
    fake = TRR.Fake()
    first = RR.write(TRR.put(tmp_path, _extra_account("s-A")), str(tmp_path), fake.readers())
    assert first["ok"], first
    posted = len(fake.comments)
    out = RR.write(TRR.put(tmp_path, _extra_account("s-B"), "second.json"), str(tmp_path), fake.readers())
    assert out["ok"] is False and out["reason"] == "review-record-extra-audit-repeated", out
    assert len(fake.comments) == posted


def test_t10_the_same_session_may_rewrite_its_own_record(tmp_path):
    fake = TRR.Fake()
    assert RR.write(TRR.put(tmp_path, _extra_account("s-A")), str(tmp_path), fake.readers())["ok"]
    again = RR.write(TRR.put(tmp_path, _extra_account("s-A"), "again.json"), str(tmp_path), fake.readers())
    assert again["ok"] is True, again


def test_t10_an_unreadable_earlier_record_never_blocks_a_write(tmp_path):
    fake = TRR.Fake()
    fake.comments.append({"id": 50, "author": "bot", "body": RR.MARKER + "\nnot a record", "url": "http://c/50"})
    out = RR.write(TRR.put(tmp_path, _extra_account("s-B")), str(tmp_path), fake.readers())
    assert out["ok"] is True, out
