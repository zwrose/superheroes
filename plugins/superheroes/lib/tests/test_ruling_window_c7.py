"""The simple ruling window (Canon 2026-10-15-dcc2b5e5-3): a ruling is accepted whenever it arrives
and binds the next fix of its finding; a fix already under way is never stopped; below-blocking
findings settle at convergence; which finding a ruling names is worked out once, when the next fixer
order's batch is finalized (`_resolve_ruled_batch`, reached through `_queue_fix_batch`).

Drives the CLI-level functions over the real adapters the way `test_rulings_channel_1445.py` does,
reusing its helpers (and, through it, the shared integration harness). Every "reaches the fixer"
assertion reads the fixer order the driver renders, not a helper's return value."""
import importlib.util
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_adapters  # noqa: E402
import round_driver as RD  # noqa: E402
import round_records as RR  # noqa: E402
import session_contract  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "test_rulings_channel_1445", os.path.join(_HERE, "test_rulings_channel_1445.py"))
_RC = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_RC)
_TRI = _RC._TRI

P_FIXER = RD.P_FIXER
_state = _RC._state
_state_bytes = _RC._state_bytes
_bootstrap = _RC._bootstrap
_drive_to_phase = _RC._drive_to_phase
_drive_one_phase = _RC._drive_one_phase
_write_ruling_file = _RC._write_ruling_file
_follow_up = _RC._follow_up
_rule = _RC._rule


# --- fixtures and helpers ------------------------------------------------------------------------

@pytest.fixture
def keep_severity(monkeypatch):
    """The shared harness's verifier verdicts all say `Important`; wrap them (in this file only) so a
    verified finding keeps the severity the panel gave it."""
    original = _TRI._payload_for

    def wrapped(session_dir, state, pend, seat, panel_findings, head_diff_path):
        payload = original(session_dir, state, pend, seat, panel_findings, head_diff_path)
        if pend["phase"] == RD.P_VERIFIERS:
            cluster = _TRI._cluster_for(pend, seat)
            severity_of = {f.get("id"): f.get("severity") for f in cluster.get("findings") or []}
            for verdict in payload["verdicts"]:
                if severity_of.get(verdict["id"]):
                    verdict["severity"] = severity_of[verdict["id"]]
        return payload

    monkeypatch.setattr(_TRI, "_payload_for", wrapped)


def _finding(title, line, severity="Important", kind="real"):
    finding = _RC._blocking_finding(title, line)
    finding["severity"] = severity
    finding["consequenceKind"] = kind
    return finding


def _session(tmp_path, findings, to_phase=P_FIXER, name="c7", **cfg):
    """A session driven to `to_phase` pending: (session_dir, gitdir, head_diff_path)."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name=name, **cfg)
    _drive_to_phase(session_dir, gitdir, findings, head_path, to_phase)
    return session_dir, gitdir, head_path


def _key(row):
    return RD._fix_batch_row_key(row)


def _batch_keys(state):
    return [_key(row) for row in state.get("_fixBatch") or []]


def _rows_by_title(state):
    rows = list(state.get("_fixBatch") or []) + list(state.get("_fixQueue") or [])
    return {row.get("title"): row for row in rows}


def _finding_key_by_title(state, title):
    for finding in state.get("findings") or []:
        if finding.get("title") == title:
            return _key(finding)
    for entry in state.get(session_contract.DISPOSITION_LEDGER_KEY) or []:
        if entry.get("title") == title:
            return RD._finding_identity_key(entry)
    raise AssertionError("no finding titled %r" % title)


def _guidance_file(tmp_path, name, key, text):
    return _write_ruling_file(tmp_path / name, [
        {"id": key, "ruling": "guidance", "reason": "owner call", "guidance": text}])


def _order_text(session_dir):
    """The fixer order the driver renders for the pending attempt."""
    return _RC._fixer_order_text(session_dir)


def _drive_until(session_dir, gitdir, head_path, phase, max_steps=12):
    """Drive pending phases (no new panel findings) until `phase` is pending."""
    for _ in range(max_steps):
        state = _state(session_dir)
        assert not state.get("terminal"), state.get("terminal")
        if state["pending"]["phase"] == phase:
            return state
        _p, out = _drive_one_phase(session_dir, gitdir, [], head_path)
        assert out.get("ok"), out
    raise AssertionError("never reached %s" % phase)


def _offered(state, session_dir, key):
    """True when the pending fixer order is offered the finding `key`: its batch holds the row AND
    the fixer-order file the driver materialized names it."""
    assert state["pending"]["phase"] == P_FIXER
    in_batch = key in _batch_keys(state)
    path = os.path.join(RR.round_dir(session_dir, state["round"]), "fix-batch.json")
    with open(path, encoding="utf-8") as fh:
        in_file = key in fh.read()
    return in_batch and in_file


def _two_important(tmp_path, name="c7-two", **cfg):
    """Fixer attempt emitted over a batch holding both findings F and G."""
    session_dir, gitdir, head_path = _session(
        tmp_path, [_finding("bounds F", 1), _finding("bounds G", 2)], name=name, **cfg)
    state = _state(session_dir)
    assert state["pending"]["phase"] == P_FIXER
    return (session_dir, gitdir, head_path,
            _finding_key_by_title(state, "bounds F"), _finding_key_by_title(state, "bounds G"))


# --- point 1: a ruling is always accepted and binds the next fix of its finding ------------------

def test_vet_442_ruling_on_an_emitted_order_is_accepted_and_reaches_the_next_order(
        tmp_path, keep_severity):
    """axis: REFUSAL — a `guidance` ruling on a finding in the batch of a fixer order that is already
    out is recorded (no `ruling-attempt-pending`), the attempt and its batch are left as they were,
    the fixer's result folds normally, and the next fixer order carries the finding with the guidance.
    """
    session_dir, gitdir, head_path, key_a, key_b = _two_important(tmp_path, "c7-442")
    emitted = _state(session_dir)
    assert RD._journal_has_orders_emitted(
        session_dir, emitted["round"], P_FIXER, emitted["pending"]["attempt"])
    assert "TAKE-THE-SECOND-OPTION" not in _order_text(session_dir)

    out = _rule(session_dir, _guidance_file(tmp_path, "r.json", key_a, "TAKE-THE-SECOND-OPTION"))
    assert out.get("ok") is True, out
    after = _state(session_dir)
    assert after["pending"] == emitted["pending"] and after["_fixBatch"] == emitted["_fixBatch"]
    assert after["rulingsLog"][-1]["ruling"] == "guidance"

    phase, folded = _drive_one_phase(session_dir, gitdir, [], head_path)
    assert phase == P_FIXER and folded.get("ok") and folded["folded"]["phase"] == P_FIXER, folded
    state = _drive_until(session_dir, gitdir, head_path, P_FIXER)
    assert state["round"] == 2
    assert _offered(state, session_dir, key_a)
    assert key_b not in _batch_keys(state), "B was fixed and carries no ruling: not sent again"
    assert "TAKE-THE-SECOND-OPTION" in _order_text(session_dir)


@pytest.mark.parametrize("phase", [RD.P_VERIFIERS, RD.P_GAPSWEEP, RD.P_AUDITS, RD.P_FIXER])
def test_rule_is_accepted_at_every_step_it_can_arrive(tmp_path, keep_severity, phase):
    """axis: REFUSAL — `rule` records `guidance` whichever step is pending (the verifiers, the
    gap-sweep, the audits, an emitted fixer attempt); none of them refuses on timing."""
    if phase == RD.P_AUDITS:
        session_dir, gitdir, head_path, key_a, _b = _two_important(tmp_path, "c7-step")
        _drive_one_phase(session_dir, gitdir, [], head_path)
        assert _state(session_dir)["pending"]["phase"] == RD.P_AUDITS
    else:
        session_dir, gitdir, head_path = _session(
            tmp_path, [_finding("bounds F", 1)], to_phase=phase, name="c7-step")
        key_a = _finding_key_by_title(_state(session_dir), "bounds F")
    before = len(_state(session_dir).get("rulingsLog") or [])
    out = _rule(session_dir, _guidance_file(tmp_path, "g.json", key_a, "GUIDED-%s" % phase))
    assert out.get("ok") is True, (phase, out)
    assert len(_state(session_dir)["rulingsLog"]) == before + 1


def test_vet_445_guidance_given_while_the_step_is_not_the_fixer_reaches_the_next_fixer(
        tmp_path, keep_severity):
    """axis: DELIVERY — guidance given during the audits (not the fixer step) is accepted and the
    next fixer order carries the finding with it."""
    session_dir, gitdir, head_path, key_a, _key_b = _two_important(tmp_path, "c7-445")
    _drive_one_phase(session_dir, gitdir, [], head_path)
    assert _state(session_dir)["pending"]["phase"] == RD.P_AUDITS
    out = _rule(session_dir, _guidance_file(tmp_path, "g.json", key_a, "GUIDED-DURING-AUDITS"))
    assert out.get("ok") is True, out
    state = _drive_until(session_dir, gitdir, head_path, P_FIXER)
    assert state["round"] == 2 and _offered(state, session_dir, key_a)
    assert "GUIDED-DURING-AUDITS" in _order_text(session_dir)


def test_1835_ruling_after_a_fixer_that_changed_nothing_rides_the_next_order(
        tmp_path, keep_severity, monkeypatch):
    """axis: DELIVERY — the fixer step folded having changed nothing and its audit left the finding
    open; a ruling recorded after that fold rides the next fixer order for the finding."""
    wrapped = _TRI._payload_for

    def idle(session_dir, state, pend, seat, panel_findings, head_diff_path):
        payload = wrapped(session_dir, state, pend, seat, panel_findings, head_diff_path)
        if pend["phase"] == P_FIXER:
            return {"fixes": [], "escalated": False, "headDiffPath": head_diff_path}
        if pend["phase"] == RD.P_AUDITS:
            return dict(payload, ruling="not-discharged", reason="the cited line is unchanged")
        return payload

    monkeypatch.setattr(_TRI, "_payload_for", idle)
    session_dir, gitdir, head_path = _session(
        tmp_path, [_finding("bounds F", 1)], name="c7-1835")
    key_f = _finding_key_by_title(_state(session_dir), "bounds F")
    _drive_one_phase(session_dir, gitdir, [], head_path)
    assert _state(session_dir)["pending"]["phase"] == RD.P_AUDITS
    _drive_one_phase(session_dir, gitdir, [], head_path)
    out = _rule(session_dir, _guidance_file(tmp_path, "g.json", key_f, "RULED-AFTER-IDLE-FIXER"))
    assert out.get("ok") is True, out
    state = _drive_until(session_dir, gitdir, head_path, P_FIXER)
    assert _offered(state, session_dir, key_f)
    assert "RULED-AFTER-IDLE-FIXER" in _order_text(session_dir)


def test_a_ruling_on_a_row_in_the_emitted_order_leaves_the_attempt_untouched(
        tmp_path, keep_severity):
    """axis: NON-INTERFERENCE — an `out-of-scope` ruling on a row of the emitted batch is recorded but
    the pending attempt, `_fixBatch`, `_fixQueue` and the emitted `fix-batch.json` stay byte-identical
    (a fix under way is never stopped or re-sliced)."""
    session_dir, _g, _h, key_a, _key_b = _two_important(tmp_path, "c7-untouched")
    before = _state(session_dir)
    path = os.path.join(RR.round_dir(session_dir, before["round"]), "fix-batch.json")
    with open(path, "rb") as fh:
        file_before = fh.read()
    out = _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
        {"id": key_a, "ruling": "out-of-scope", "reason": "later", "followUp": _follow_up()}]))
    assert out.get("ok") is True, out
    after = _state(session_dir)
    for field in ("pending", "_fixBatch", "_fixQueue", "_fixBatchIndex"):
        assert after.get(field) == before.get(field), field
    with open(path, "rb") as fh:
        assert fh.read() == file_before
    assert len(after["rulingsLog"]) == len(before.get("rulingsLog") or []) + 1


def _ledger_row(state, key):
    return {RD._finding_identity_key(e): e
            for e in state.get(session_contract.DISPOSITION_LEDGER_KEY) or []}[key]


def test_a_fix_that_went_against_the_ruling_is_sent_back_restaged(tmp_path, keep_severity):
    """axis: RESTAGE — A is in an emitted order, the ruling arrives, the fix lands and A is archived as
    fixed; the next round's fixer order still carries A with the ruling (the restage lives in driver
    state; the ledger keeps its fold-time record).

    bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1b_c7_ruling_window.md (element 5)
    """
    session_dir, gitdir, head_path, key_a, _key_b = _two_important(tmp_path, "c7-restage")
    assert _rule(session_dir, _guidance_file(tmp_path, "g.json", key_a, "DO-NOT-DELETE-IT"))["ok"]
    _drive_one_phase(session_dir, gitdir, [], head_path)  # the fixer folds
    _drive_one_phase(session_dir, gitdir, [], head_path)  # the audit discharges A
    state = _state(session_dir)
    assert _ledger_row(state, key_a)["disposition"] == "fixed"

    state = _drive_until(session_dir, gitdir, head_path, P_FIXER)
    assert state["round"] == 2 and _offered(state, session_dir, key_a)
    assert RD._live_finding_by_key(state, key_a) is None, "A is restaged from the ledger, not live"
    assert _ledger_row(state, key_a)["disposition"] == "fixed", "the ledger keeps its fold-time record"
    assert _offered(state, session_dir, key_a), "A is not excluded from round 2's batch as discharged"
    assert "DO-NOT-DELETE-IT" in _order_text(session_dir)
    assert any(d["kind"] == "fix-batch-ruled" and key_a in d["detail"] for d in state["decisions"])


# --- point 2: below-blocking findings settle at convergence --------------------------------------

def _run_recording_fixer_batches(session_dir, gitdir, head_path, max_steps=30):
    """Drive to the terminal; the titles of every fixer batch the driver sent, in order."""
    sent = []
    for _ in range(max_steps):
        state = _state(session_dir)
        if state.get("terminal"):
            return sent, state
        if state["pending"]["phase"] == P_FIXER:
            sent.append([r["title"] for r in state["_fixBatch"]])
            assert len(sent) <= 3, "a fixer was sent out again and again: %s" % sent
        _phase, out = _drive_one_phase(session_dir, gitdir, [], head_path)
        assert out.get("ok"), out
    raise AssertionError("no terminal in %d steps" % max_steps)


def test_a_converged_loop_settles_its_minors_and_never_puts_them_in_a_fix_batch(
        tmp_path, keep_severity):
    """axis: NO AUTONOMOUS LIFT — a real-consequence Minor and a code-quality Minor, neither ruled,
    ride no fixer batch; at convergence the first is left for the owner with its consequence and the
    second is craft, and the session's left-for-owner count (what the review record names) is 1.

    bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1b_c7_ruling_window.md (element 6)
    """
    import review_record_session
    session_dir, gitdir, head_path = _session(
        tmp_path, [_finding("blocker B", 1),
                   _finding("real minor", 2, "Minor", "real"),
                   _finding("quality minor", 3, "Minor", "code-quality")], name="c7-settle")
    sent, state = _run_recording_fixer_batches(session_dir, gitdir, head_path)
    assert state["terminal"] == "converged"
    assert sent and all(titles == ["blocker B"] for titles in sent), sent
    assert not any(d["kind"] == "fix-batch-ruled" for d in state["decisions"])
    real = _ledger_row(state, _finding_key_by_title(state, "real minor"))
    quality = _ledger_row(state, _finding_key_by_title(state, "quality minor"))
    assert real["disposition"] == "left-for-owner" and real["settledReason"]
    assert quality["disposition"] == "craft"
    left = [f for f in review_record_session._findings(state) if f["outcome"] == "left-for-owner"]
    assert [f["title"] for f in left] == ["real minor"]


def test_a_minor_named_by_guidance_reaches_the_next_fixer(tmp_path, keep_severity):
    """axis: OWNER-NAMED, WHATEVER THE SEVERITY — a code-quality Minor that was never in a fix batch,
    named by a `guidance` ruling while the blocker's fixer is out, rides the next fixer order with the
    guidance, and nothing else below blocking does.

    bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1b_c7_ruling_window.md (element 3)
    """
    session_dir, gitdir, head_path = _session(
        tmp_path, [_finding("blocker B", 1),
                   _finding("real minor", 2, "Minor", "real"),
                   _finding("quality minor", 3, "Minor", "code-quality")], name="c7-minor")
    state = _state(session_dir)
    assert [r["title"] for r in state["_fixBatch"]] == ["blocker B"]
    key_q = _finding_key_by_title(state, "quality minor")
    assert _rule(session_dir, _guidance_file(tmp_path, "g.json", key_q, "TIDY-THE-NAMES"))["ok"]
    _drive_one_phase(session_dir, gitdir, [], head_path)
    state = _drive_until(session_dir, gitdir, head_path, P_FIXER)
    assert state["round"] == 2
    assert [r["title"] for r in state["_fixBatch"]] == ["quality minor"]
    assert _offered(state, session_dir, key_q)
    assert "TIDY-THE-NAMES" in _order_text(session_dir)


# --- point 3: one resolution point --------------------------------------------------------------

def _unit_state(*findings):
    state = RD.new_state({"leg": "code", "vendors": ["claude"], "fixerVendor": "claude"})
    state["round"] = 2
    state["rounds"]["2"] = {}
    RD._set_findings(state, [dict(f, severity=f.get("severity", "Important"),
                                  consequenceKind=f.get("consequenceKind", "real"))
                             for f in findings])
    return state


def _log_ruling(state, key, ruling="guidance", guidance="G", seq=None):
    seq = seq or RD._next_ruling_seq(state)
    row = {"seq": seq, "round": state["round"], "findingKey": key, "ruling": ruling,
           "reason": "r", "id": key}
    if ruling == "guidance":
        row["guidance"] = guidance
    RD._writable_rulings_log(state).append(row)
    return seq


def test_a_ruling_on_a_reworded_finding_reaches_the_one_live_row():
    """axis: LINEAGE — guidance given on a finding's old wording binds the live row that rewords it:
    the row joins the batch and carries no second row for the old wording."""
    state = _unit_state({"file": "a.py", "line": 1, "title": "new wording"})
    live = RD._fix_batch_row_key(state["findings"][0])
    old = "a.py::old wording@L1"
    state["findingLineage"] = {live: old}
    _log_ruling(state, old)
    assert RD._queue_fix_batch(state, state["config"], []) == "queued"
    assert [RD._fix_batch_row_key(r) for r in state["_fixBatch"]] == [live]
    assert RD._gate_guidance_entries(state, 2)[0]["guidance"] == "G"


def _merged_into_session(tmp_path):
    """F1 and F2 reported together; the synthesis seat cannot be seated in this harness, so the merge
    it would record is made through the driver's own writers (`_record_merged_into`, `_set_findings`)
    at the gap-sweep step, before the fix batch is built. Returns
    (session_dir, gitdir, head_path, member_key, kept_key)."""
    session_dir, gitdir, head_path = _session(
        tmp_path, [_finding("bounds F1", 1), _finding("bounds F2", 2)],
        to_phase=RD.P_GAPSWEEP, name="c7-merge")
    state = _state(session_dir)
    kept = _finding_key_by_title(state, "bounds F1")
    member = _finding_key_by_title(state, "bounds F2")
    RD._record_merged_into(state, member, kept)
    RD._set_findings(state, [f for f in state["findings"] if _key(f) == kept])
    RD.save_state(session_dir, state)
    _drive_to_phase(session_dir, gitdir, [], head_path, P_FIXER)
    state = _state(session_dir)
    assert _batch_keys(state) == [kept]
    assert _ledger_row(state, member)[session_contract.MERGED_INTO_FIELD] == kept
    return session_dir, gitdir, head_path, member, kept


def test_a_ruling_on_a_member_merged_into_another_reaches_the_one_live_row(
        tmp_path, keep_severity):
    """axis: ATTACH — guidance given on a finding merged into another binds the representative: the
    representative is the row the next fixer order carries, with the member's guidance on it.

    bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1b_c7_ruling_window.md (element 2)
    """
    session_dir, gitdir, head_path, member, kept = _merged_into_session(tmp_path)
    assert _rule(session_dir, _guidance_file(tmp_path, "g.json", member, "FOR-THE-MERGED"))["ok"]
    _drive_one_phase(session_dir, gitdir, [], head_path)
    state = _drive_until(session_dir, gitdir, head_path, P_FIXER)
    assert state["round"] == 2
    assert _batch_keys(state) == [kept] and _offered(state, session_dir, kept)
    assert member not in _batch_keys(state)
    assert "FOR-THE-MERGED" in _order_text(session_dir)


def test_a_ruling_naming_no_live_finding_dispatches_nothing_and_is_recorded():
    """axis: NO LIVE FINDING — guidance on a finding that is neither live nor was in a fixer order and
    is settled (refuted) sends no fixer; one decision line records it, once, for the settle."""
    state = _unit_state()
    refuted = {"file": "a.py", "line": 1, "title": "gone", "severity": "Important",
               "consequenceKind": "real"}
    RD._set_findings(state, [refuted])
    key = RD._fix_batch_row_key(refuted)
    RD._record_disposition(state, key, "refuted", 1, refutedReason="not real")
    RD._set_findings(state, [])
    _log_ruling(state, key)
    for _ in range(2):
        assert RD._queue_fix_batch(state, state["config"], []) == "empty"
    assert not state.get("_fixBatch")
    lines = [d for d in state["decisions"] if d["kind"] == "ruling-no-live-finding"]
    assert len(lines) == 1 and key in lines[0]["detail"]


def test_a_decision_already_sent_is_not_sent_again(tmp_path, keep_severity):
    """axis: NO REPEAT — a finding sent to a fixer under a ruling is not sent again under that same
    ruling in any later round; a newer ruling on it is.

    bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1b_c7_ruling_window.md (element 4)
    """
    session_dir, gitdir, head_path, key_a, _key_b = _two_important(tmp_path, "c7-once")
    assert _rule(session_dir, _guidance_file(tmp_path, "g1.json", key_a, "FIRST"))["ok"]
    _drive_one_phase(session_dir, gitdir, [], head_path)
    state = _drive_until(session_dir, gitdir, head_path, P_FIXER)
    assert state["round"] == 2 and _offered(state, session_dir, key_a)
    # round 2's fixer folds and its audit discharges A again: with no newer ruling, the loop converges
    _sent, state = _run_recording_fixer_batches(session_dir, gitdir, head_path)
    assert state["terminal"] == "converged"
    assert _sent == [["bounds F"]], "only round 2's order (pending above) held A: %s" % _sent

    # the same loop with a NEWER ruling on A: it is sent once more
    session_dir, gitdir, head_path, key_a, _key_b = _two_important(tmp_path, "c7-twice")
    assert _rule(session_dir, _guidance_file(tmp_path, "g1.json", key_a, "FIRST"))["ok"]
    _drive_one_phase(session_dir, gitdir, [], head_path)
    state = _drive_until(session_dir, gitdir, head_path, P_FIXER)
    assert _offered(state, session_dir, key_a)
    assert _rule(session_dir, _guidance_file(tmp_path, "g2.json", key_a, "SECOND"))["ok"]
    _drive_one_phase(session_dir, gitdir, [], head_path)
    state = _drive_until(session_dir, gitdir, head_path, P_FIXER)
    assert state["round"] == 3 and _offered(state, session_dir, key_a)
    assert "SECOND" in _order_text(session_dir) and "FIRST" not in _order_text(session_dir)


def test_a_ruling_on_a_finding_the_next_round_rewords_reaches_the_reworded_row(
        tmp_path, keep_severity, monkeypatch):
    """axis: LINEAGE — guidance given on F while its fixer is out binds the finding the next round
    raises at the same place under other words: the fixer order carries that one row, with the
    guidance, and the old wording is not sent a second time."""
    wrapped = _TRI._payload_for

    def reword(session_dir, state, pend, seat, panel_findings, head_diff_path):
        payload = wrapped(session_dir, state, pend, seat, panel_findings, head_diff_path)
        if pend["phase"] == RD.P_SCOPED and state["round"] == 2:
            return {"findings": [_finding("bounds F, said differently", 1)]}
        return payload

    monkeypatch.setattr(_TRI, "_payload_for", reword)
    session_dir, gitdir, head_path = _session(tmp_path, [_finding("bounds F", 1)], name="c7-reword")
    key_old = _finding_key_by_title(_state(session_dir), "bounds F")
    assert _rule(session_dir, _guidance_file(tmp_path, "g.json", key_old, "FOR-BOTH-WORDINGS"))["ok"]
    _drive_one_phase(session_dir, gitdir, [], head_path)
    state = _drive_until(session_dir, gitdir, head_path, P_FIXER)
    assert state["round"] == 2
    key_new = _finding_key_by_title(state, "bounds F, said differently")
    assert key_new != key_old and _batch_keys(state) == [key_new]
    assert _offered(state, session_dir, key_new)
    assert "FOR-BOTH-WORDINGS" in _order_text(session_dir)


def test_every_fixer_batch_passes_the_one_resolution_point():
    """axis: ONE WRITER — the fixer batch is assigned in exactly one function of the driver, and that
    function runs the batch through `_resolve_ruled_batch` before it does."""
    import ast
    with open(RD.__file__, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    writers = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        for node in ast.walk(fn):
            if (isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)
                    and t.value.id == "state" and isinstance(t.slice, ast.Constant)
                    and t.slice.value == "_fixBatch" for t in node.targets)):
                writers.add(fn.name)
    assert writers == {"_queue_fix_batch"}, writers
    queue = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_queue_fix_batch")
    calls = [n.func.id for n in ast.walk(queue)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    assert "_resolve_ruled_batch" in calls


# --- the owner gate and below-blocking product choices (units over the driver's own fold) --------

def _unit_finding(key, line, severity, *, tradeoff=False, kind="real"):
    return dict(findingKey=key, title=key, file="a.py", line=line, severity=severity,
                tradeoff=tradeoff, consequenceKind=kind)


def _unit_round(findings):
    """A state with `findings` routed through the driver's own settle entry point."""
    state = RD.new_state()
    RD._set_findings(state, [dict(f) for f in findings])
    RD._after_findings_settled(state, state["config"])
    return state


def _unit_rulings(state, *rows):
    state.update(rulingSeqCounter=len(rows),
                 rulingsLog=[dict(row, seq=i) for i, row in enumerate(rows, 1)])


def _unit_batch(state):
    return [row["findingKey"] for row in state.get("_fixBatch") or []]


def _unit_gate_ids(state):
    return RD._judgment_row_ids(state["_judgmentFindings"])


@pytest.mark.parametrize("blocker_is_tradeoff", [False, True], ids=["mechanical", "gate-blocker"])
def test_an_undecided_product_choice_is_left_for_the_owner(blocker_is_tradeoff):
    """axis: NO AUTONOMOUS LIFT — an undecided below-blocking product choice never enters the owner
    gate or a fix batch, and the end-of-loop settle leaves it for the owner."""
    state = _unit_round([_unit_finding("B", 1, "Important", tradeoff=blocker_is_tradeoff),
                         _unit_finding("M", 2, "Minor", tradeoff=True)])
    if blocker_is_tradeoff:
        assert state["step"] == RD.P_JUDGMENT
        assert [r["findingKey"] for r in state["_judgmentFindings"]] == ["B"]
        RD._fold_judgment(state, state["config"], {"dispositions": [
            {"id": _unit_gate_ids(state)[0], "disposition": "fix-as-suggested"}]})
    assert state["step"] == P_FIXER
    assert _unit_batch(state) == ["B"] and not state.get("_fixQueue")
    RD._set_terminal(state, "converged")
    ledger, fault = RD._disposition_ledger_by_key(state)
    assert fault is None
    assert ledger["M"]["disposition"] == "left-for-owner", ledger["M"]


def test_a_guided_choice_survives_skipping_the_only_gate_blocker():
    """axis: OWNER-NAMED — with the gate's only blocker skipped, a product choice a `guidance` ruling
    names still reaches a fixer through the one resolution point."""
    state = _unit_round([_unit_finding("J", 1, "Important", tradeoff=True),
                         _unit_finding("M", 2, "Minor", tradeoff=True)])
    assert [r["findingKey"] for r in state["_judgmentFindings"]] == ["J"]
    _unit_rulings(state, dict(findingKey="M", ruling="guidance", guidance="apply it"))
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": _unit_gate_ids(state)[0], "disposition": "skip", "reason": "keep current"}]})
    assert state["step"] == P_FIXER and _unit_batch(state) == ["M"]
    assert not state.get("terminal")


def test_an_undecided_choice_does_not_survive_skipping_the_only_gate_blocker():
    """axis: NO AUTONOMOUS LIFT — with the gate's only blocker skipped and nothing owner-named, the
    round settles as it always did: no fix batch, nothing counted as excluded."""
    state = _unit_round([_unit_finding("J", 1, "Important", tradeoff=True),
                         _unit_finding("M", 2, "Minor", tradeoff=True)])
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": _unit_gate_ids(state)[0], "disposition": "skip", "reason": "keep current"}]})
    assert state.get("terminal") == "converged"
    assert state["step"] != P_FIXER and not state.get("_fixBatch")
    assert "fixBatchExcludedByDischarge" not in state["rounds"]["1"]
    assert not any(d["kind"] == "fix-batch-ruled" for d in state["decisions"])


@pytest.mark.parametrize("target,other", [("Q", "M"), ("M", "Q")], ids=["quality", "choice"])
def test_the_fixer_receives_only_the_owner_named_minor(target, other):
    """axis: OWNER-NAMED — with the mechanical blocker ruled out and the gate's blocker skipped, the
    fixer batch holds the one Minor an owner decision names and never the other."""
    state = _unit_round([
        _unit_finding("B", 1, "Important"),
        _unit_finding("J", 2, "Important", tradeoff=True),
        _unit_finding("M", 3, "Minor", tradeoff=True),
        _unit_finding("Q", 4, "Minor", kind="code-quality")])
    assert [r["findingKey"] for r in state["_judgmentFindings"]] == ["J"]
    assert [r["findingKey"] for r in state["_judgmentMechanical"]] == ["B"]
    _unit_rulings(state, dict(findingKey="B", ruling="out-of-scope"),
                  dict(findingKey=target, ruling="guidance", guidance="apply it"))
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": _unit_gate_ids(state)[0], "disposition": "skip", "reason": "keep current"}]})
    assert state["step"] == P_FIXER
    assert _unit_batch(state) == [target]
    assert other not in _unit_batch(state) + [r["findingKey"] for r in state.get("_fixQueue") or []]


def test_guidance_before_the_orders_go_out_brings_in_a_finding_the_batch_lacks(
        tmp_path, keep_severity):
    """axis: NOT YET EMITTED — before the fixer order is emitted, a ruling re-runs the batch through
    the one resolution point: a code-quality Minor a `guidance` ruling names joins the batch and the
    order it is rendered into carries the guidance."""
    session_dir, _g, _h = _session(
        tmp_path, [_finding("blocker B", 1), _finding("quality minor", 2, "Minor", "code-quality")],
        name="c7-before-emit")
    state = _state(session_dir)
    key_q = _finding_key_by_title(state, "quality minor")
    assert _batch_keys(state) == [_finding_key_by_title(state, "blocker B")]
    _RC._strip_fixer_orders_emitted(session_dir)
    assert _rule(session_dir, _guidance_file(tmp_path, "g.json", key_q, "PULL-IT-IN"))["ok"]
    state = _state(session_dir)
    assert key_q in _batch_keys(state)
    assert key_q in [_key(row) for row in state["pending"]["payload"]["batch"]]
    assert "PULL-IT-IN" in _order_text(session_dir)
