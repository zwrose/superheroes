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
# the literal integer the release before dispatch history stamped, not derived from the current constant
PRE_DISPATCH_HISTORY_GENERATION = 4
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


def _order_path(session_dir):
    state = _state(session_dir)
    pend = state["pending"]
    roster, reason = round_adapters.roster_for(pend["phase"], state, state.get("config") or {})
    assert reason is None, reason
    seat, occurrence = RR.roster_slots(roster)[0]
    skey = RR.storage_key(seat, occurrence)
    return RR.order_prompt_path(session_dir, pend["round"], pend["phase"], skey, pend["attempt"]), skey


def _order_text(session_dir):
    """The fixer order the driver EMITTED for the pending attempt: the saved prompt, checked against
    the emission anchor's hash (never a fresh render of the current state)."""
    state = _state(session_dir)
    pend = state["pending"]
    path, skey = _order_path(session_dir)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    anchor = RD._orders_anchor(state, session_dir, pend["round"], pend["phase"], pend["attempt"])
    assert anchor and anchor["orders"][skey] == RR.sha256_text(text), "saved prompt is not the emitted one"
    return text


def _emit_pending_orders(session_dir):
    """Emit the pending fixer attempt's orders the way `next` does."""
    state = _state(session_dir)
    pend = state["pending"]
    roster, reason = round_adapters.roster_for(pend["phase"], state, state.get("config") or {})
    assert reason is None, reason
    RD._emit_orders_manifest(session_dir, state, pend["round"], pend["phase"], pend["attempt"],
                             roster, journal_cmd="next", pending_payload=pend.get("payload"),
                             seat_map=RD._effective_seat_map(state))


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
    original_order = _order_text(session_dir)
    assert "TAKE-THE-SECOND-OPTION" not in original_order
    path, _skey = _order_path(session_dir)

    out = _rule(session_dir, _guidance_file(tmp_path, "r.json", key_a, "TAKE-THE-SECOND-OPTION"))
    assert out.get("ok") is True, out
    after = _state(session_dir)
    assert after["pending"] == emitted["pending"] and after["_fixBatch"] == emitted["_fixBatch"]
    assert after["rulingsLog"][-1]["ruling"] == "guidance"
    with open(path, encoding="utf-8") as fh:
        assert fh.read() == original_order, "the order already out is left byte-identical"

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


def test_a_restaged_row_keeps_the_guidance_link_to_its_ruling(tmp_path, keep_severity):
    """axis: RESTAGE IDENTITY — the restaged row (live no more, only in the ledger) still renders its
    ruling under its own file, line and title, the identity a fixer matches guidance by.

    bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1b_c7_ruling_window.md (element viii)
    """
    session_dir, gitdir, head_path, key_a, _key_b = _two_important(tmp_path, "c7-restage-id")
    assert _rule(session_dir, _guidance_file(tmp_path, "g.json", key_a, "DO-NOT-DELETE-IT"))["ok"]
    _drive_one_phase(session_dir, gitdir, [], head_path)  # the fixer folds
    _drive_one_phase(session_dir, gitdir, [], head_path)  # the audit discharges A
    state = _drive_until(session_dir, gitdir, head_path, P_FIXER)
    assert RD._live_finding_by_key(state, key_a) is None
    row = _ledger_row(state, key_a)
    text = _order_text(session_dir)
    assert "### %s:%s \u2014 %s" % (row["file"], row["line"], row["title"]) in text
    assert "(file not recorded)" not in text and "(no title)" not in text


def test_a_session_from_the_generation_before_dispatch_history_is_refused_at_next(tmp_path):
    """axis: GENERATION GATE — a generation-4 session (the release before `sentUnderDecision` and
    `restagedAfterDispositionSeq`) is refused at `next` with `session-from-earlier-version`.

    bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1b_c7_ruling_window.md (element ix)
    """
    from test_session_pickup_and_upgrade_1721 import _assert_refusal, _light_folder
    session_dir = _light_folder(tmp_path, generation=PRE_DISPATCH_HISTORY_GENERATION)
    out = RD.cmd_next(session_dir)
    _assert_refusal(out, already_restarted=False)
    assert out["reason"] == "session-from-earlier-version"


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


def _unit_round(findings, rulings=()):
    """A state with `findings` (and any `rulings`, given before the round settles) routed through the
    driver's own settle entry point."""
    state = RD.new_state()
    RD._set_findings(state, [dict(f) for f in findings])
    if rulings:
        _unit_rulings(state, *rulings)
    RD._after_findings_settled(state, state["config"])
    return state


def _unit_rulings(state, *rows):
    state.update(rulingSeqCounter=len(rows),
                 rulingsLog=[dict(row, seq=i) for i, row in enumerate(rows, 1)])


def _unit_batch(state):
    return [row["findingKey"] for row in state.get("_fixBatch") or []]


@pytest.mark.parametrize("blocker_is_tradeoff", [False, True], ids=["mechanical", "held-blocker"])
def test_an_undecided_product_choice_is_left_for_the_owner(blocker_is_tradeoff):
    """axis: NO AUTONOMOUS LIFT — an undecided below-blocking product choice never enters a fix batch,
    and the end-of-loop settle leaves it for the owner; a blocking one is held and handed back."""
    state = _unit_round([_unit_finding("B", 1, "Important", tradeoff=blocker_is_tradeoff),
                         _unit_finding("M", 2, "Minor", tradeoff=True)])
    if blocker_is_tradeoff:
        assert state["terminal"] == "handed-back" and state["ownerChoiceHeld"] == ["B"]
        assert not state.get("_fixBatch")
    else:
        assert state["step"] == P_FIXER
        assert _unit_batch(state) == ["B"] and not state.get("_fixQueue")
        RD._set_terminal(state, "converged")
    ledger, fault = RD._disposition_ledger_by_key(state)
    assert fault is None
    assert ledger["M"]["disposition"] == "left-for-owner", ledger["M"]


def test_a_guided_choice_survives_the_only_blocker_being_held():
    """axis: OWNER-NAMED — with the round's only blocker held for the owner, a product choice a
    `guidance` ruling names still reaches a fixer through the one resolution point."""
    state = _unit_round([_unit_finding("J", 1, "Important", tradeoff=True),
                         _unit_finding("M", 2, "Minor", tradeoff=True)],
                        rulings=[dict(findingKey="M", ruling="guidance", guidance="apply it")])
    assert state["ownerChoiceHeld"] == ["J"]
    assert state["step"] == P_FIXER and _unit_batch(state) == ["M"]
    assert not state.get("terminal")


def test_an_undecided_choice_does_not_survive_the_only_blocker_being_held():
    """axis: NO AUTONOMOUS LIFT — with the round's only blocker held and nothing owner-named, no fix
    batch is built, nothing is counted as excluded, and the PR is handed back."""
    state = _unit_round([_unit_finding("J", 1, "Important", tradeoff=True),
                         _unit_finding("M", 2, "Minor", tradeoff=True)])
    assert state.get("terminal") == "handed-back"
    assert state["decisions"][-1]["kind"] == "owner-choice-open"
    assert state["step"] != P_FIXER and not state.get("_fixBatch")
    assert "fixBatchExcludedByDischarge" not in state["rounds"]["1"]
    assert not any(d["kind"] == "fix-batch-ruled" for d in state["decisions"])


@pytest.mark.parametrize("target,other", [("Q", "M"), ("M", "Q")], ids=["quality", "choice"])
def test_the_fixer_receives_only_the_owner_named_minor(target, other):
    """axis: OWNER-NAMED — with the mechanical blocker ruled out and the other blocker held, the
    fixer batch holds the one Minor an owner decision names and never the other."""
    state = _unit_round([
        _unit_finding("B", 1, "Important"),
        _unit_finding("J", 2, "Important", tradeoff=True),
        _unit_finding("M", 3, "Minor", tradeoff=True),
        _unit_finding("Q", 4, "Minor", kind="code-quality")],
        rulings=[dict(findingKey="B", ruling="out-of-scope"),
                 dict(findingKey=target, ruling="guidance", guidance="apply it")])
    assert state["ownerChoiceHeld"] == ["J"]
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
    _emit_pending_orders(session_dir)
    assert "PULL-IT-IN" in _order_text(session_dir)


# --- one identity for a ruling: merges and lineage followed together ---------------------------

def _unit_pair(merged_into, member):
    """A state whose live rows are `merged_into` (the representative) and `member` merged into it."""
    state = _unit_state({"file": "a.py", "line": 1, "title": "rep"})
    rep = RD._fix_batch_row_key(state["findings"][0])
    state["findings"].append({"file": "a.py", "line": 2, "title": "member", "severity": "Important",
                              "consequenceKind": "real", "id": "member",
                              session_contract.MERGED_INTO_FIELD: rep})
    return state, rep, RD._fix_batch_row_key(state["findings"][1])


def test_a_member_merged_into_a_reworded_finding_binds_the_newer_guidance():
    """axis: MERGE + LINEAGE — M merged into K, K reworded as N: M's newer guidance, not K's older,
    is what the row for N carries, and the emitted batch row says where it came from."""
    state, rep, member = _unit_pair(None, None)
    state["findings"][0] = dict(state["findings"][0], title="reworded", line=3,
                                 findingKey="a.py::reworded@L3")
    new = RD._fix_batch_row_key(state["findings"][0])
    assert new != rep
    state["findingLineage"] = {new: rep}
    _log_ruling(state, rep, guidance="OLD-GUIDANCE")
    _log_ruling(state, member, guidance="NEW-GUIDANCE")
    batch = RD._resolve_ruled_batch(state, [dict(state["findings"][0])])
    assert [(RD._fix_batch_row_key(r), r.get("ruledBy")) for r in batch] == [(new, member)]
    assert batch[0]["ruledBy"] == member and member != rep


def test_a_newer_fix_ruling_on_a_merged_member_outranks_the_representatives_skip():
    """axis: MERGE — K carries an older out-of-scope ruling, merged-in M a newer guidance: the batch
    keeps K (exclusion and dispatch read the same decision)."""
    state, rep, member = _unit_pair(None, None)
    _log_ruling(state, rep, ruling="out-of-scope")
    _log_ruling(state, member, guidance="STILL-FIX-IT")
    filtered, fault = RD._filter_excluded_discharged_fixes(state, [dict(state["findings"][0])])
    assert fault is None and [RD._fix_batch_row_key(r) for r in filtered] == [rep]


def test_a_restaged_finding_is_not_settled_by_its_stale_fixed_disposition():
    """axis: RESTAGE — a finding whose `fixed` disposition an owner ruling reopened is settled at the
    end of the loop like any open one, not reported as fixed."""
    state = _unit_round([_unit_finding("A", 1, "Important")])
    key = "A"
    RD._record_disposition(state, key, "fixed", 2)
    for entry in state[session_contract.DISPOSITION_LEDGER_KEY]:
        entry[session_contract.RAISED_SEQ_FIELD] = 0  # raised before the discharge
    ledger, _ = RD._disposition_ledger_by_key(state)
    assert ledger[key]["disposition"] == "fixed"
    state["restagedAfterDispositionSeq"] = {key: state["dispositionSeqCounter"]}
    RD._set_terminal(state, "held")
    ledger, _ = RD._disposition_ledger_by_key(state)
    assert ledger[key]["disposition"] != "fixed", ledger[key]


def test_a_restaged_finding_that_is_capped_reads_unresolved_in_the_review_record():
    """axis: RESTAGE + RECORD — restaged after `fixed`, then the loop caps without a discharge: the
    review record's per-finding outcome is not `fixed`."""
    import review_record_session as RRS
    state = _unit_round([_unit_finding("A", 1, "Important")])
    key = "A"
    RD._record_disposition(state, key, "fixed", 1)
    for entry in state[session_contract.DISPOSITION_LEDGER_KEY]:
        entry[session_contract.RAISED_SEQ_FIELD] = 0
    state["restagedAfterDispositionSeq"] = {key: state["dispositionSeqCounter"]}
    RD._set_terminal(state, "capped-with-open-blocker", cap=True)
    ledger, _ = RD._disposition_ledger_by_key(state)
    by_key = {key: ledger[key]}
    outcome, reason, _rep = RRS._decide(ledger[key], by_key, {})
    assert outcome != "fixed" and "fixed and audited" not in str(reason), (outcome, reason)


def test_guidance_on_a_merged_member_reaches_the_live_row_the_representative_was_reworded_into():
    """axis: MERGE + LINEAGE — M merged into K, K reworded as live Minor N, newer guidance on M, and
    N absent from the offered batch: the resolver sends N, not archived K."""
    state = _unit_round([_unit_finding("N", 1, "Minor")])
    RD._record_disposition(state, "K", "fixed", 1)
    state["findingLineage"] = {"N": "K"}
    state["findings"].append(_unit_finding("M", 2, "Important"))
    state["findings"][-1][session_contract.MERGED_INTO_FIELD] = "K"
    _log_ruling(state, "M", guidance="FOR-THE-LIVE-ONE")
    batch = RD._resolve_ruled_batch(state, [])
    assert [(RD._fix_batch_row_key(r), r.get("ruledBy")) for r in batch] == [("N", "M")]


def test_an_undispatched_ruling_on_a_fixed_finding_settles_as_left_for_the_owner():
    """axis: TERMINAL — A was fixed and audited, guidance on A was recorded but no fixer order ever
    carried it, and the loop ends: A settles as left for the owner naming the ruling, not `fixed`."""
    state = _unit_round([_unit_finding("A", 1, "Important")])
    RD._record_disposition(state, "A", "fixed", 1)
    seq = _log_ruling(state, "A", guidance="NEVER-SENT")
    RD._set_terminal(state, "capped-with-open-blocker", cap=True)
    ledger, _ = RD._disposition_ledger_by_key(state)
    assert ledger["A"]["disposition"] == "left-for-owner", ledger["A"]
    assert "owner ruling %s" % seq in ledger["A"]["settledReason"], ledger["A"]


def test_newer_guidance_on_a_member_survives_a_merge_reword_merge_chain():
    """axis: MERGE + LINEAGE — M merged into K, K reworded as N, N merged into live P: the guidance
    on M, newer than K's already-sent one, is the one P carries; locating and selecting agree."""
    state = _unit_round([_unit_finding("P", 1, "Important")])
    for key, into in (("K", None), ("M", "K"), ("N", "P")):
        row = _unit_finding(key, 2, "Important")
        if into:
            row[session_contract.MERGED_INTO_FIELD] = into
        state["findings"].append(row)
    state["findingLineage"] = {"N": "K"}
    old = _log_ruling(state, "K", guidance="OLD")
    state["sentUnderDecision"] = {RD._lineage_root(RD._lineage_map(state), "K"): old}
    _log_ruling(state, "M", guidance="NEW")
    ledger, _ = RD._disposition_ledger_by_key(state)
    roots = {RD._ruling_root(state, ledger, k) for k in ("K", "M", "N", "P")}
    assert len(roots) == 1
    batch = RD._resolve_ruled_batch(state, [dict(state["findings"][0])])
    assert [(RD._fix_batch_row_key(r), r.get("ruledBy")) for r in batch] == [("P", "M")]


def test_a_restaged_finding_reported_as_code_quality_keeps_its_real_consequence():
    """axis: RESTAGE — a fixed real-consequence finding reopened by a ruling and re-reported as code
    quality only keeps its real consequence when reseeded."""
    state = _unit_round([_unit_finding("A", 1, "Important")])
    RD._record_disposition(state, "A", "fixed", 1)
    for entry in state[session_contract.DISPOSITION_LEDGER_KEY]:
        entry[session_contract.RAISED_SEQ_FIELD] = 0
        entry["consequence"], entry["consequenceKind"] = "data loss", "real"
    state["restagedAfterDispositionSeq"] = {"A": state["dispositionSeqCounter"]}
    ledger = state[session_contract.DISPOSITION_LEDGER_KEY]
    seen = {"A": 0}
    entry = RD._seed_ledger_entry(
        state, ledger, seen,
        dict(_unit_finding("A", 1, "Important", kind="code-quality"), consequence="harder to read"),
        "A", 2)
    assert entry["consequenceKind"] == "real" and "data loss" in entry["consequence"], entry


def test_a_capped_pending_newer_ruling_on_a_merged_member_is_not_hidden_by_an_old_skip():
    """axis: TERMINAL + MERGE — B merged into A, A carries an older out-of-scope skip, newer guidance
    on B never sent, loop caps: the record names the unsent ruling, not the obsolete skip."""
    state = _unit_round([_unit_finding("A", 1, "Important")])
    RD._record_disposition(state, "A", "out-of-scope", 1, outOfScopeReason="leave it as it is")
    state["findings"].append(_unit_finding("B", 2, "Important"))
    state["findings"][-1][session_contract.MERGED_INTO_FIELD] = "A"
    _log_ruling(state, "A", ruling="out-of-scope")
    seq = _log_ruling(state, "B", guidance="DO-IT")
    RD._set_terminal(state, "capped-with-open-blocker", cap=True)
    ledger, _ = RD._disposition_ledger_by_key(state)
    assert "owner ruling %s" % seq in str(ledger["A"].get("settledReason")), ledger["A"]


def test_a_dispatched_newer_guidance_on_a_merged_member_is_not_settled_as_out_of_scope():
    """axis: TERMINAL + MERGE — the same pair, but the guidance on B went to a fixer and the loop caps
    before a discharge: the record gives the open reason, not the representative's obsolete skip."""
    state = _unit_round([_unit_finding("A", 1, "Important")])
    RD._record_disposition(state, "A", "out-of-scope", 1, outOfScopeReason="leave it as it is")
    state["findings"].append(_unit_finding("B", 2, "Important"))
    state["findings"][-1][session_contract.MERGED_INTO_FIELD] = "A"
    _log_ruling(state, "A", ruling="out-of-scope")
    _log_ruling(state, "B", guidance="DO-IT")
    batch = RD._resolve_ruled_batch(state, [])
    assert [RD._fix_batch_row_key(r) for r in batch] == ["A"]
    RD._note_sent_under_decision(state, batch)
    RD._set_terminal(state, "capped-with-open-blocker", cap=True)
    ledger, _ = RD._disposition_ledger_by_key(state)
    reason = str(ledger["A"].get("settledReason"))
    assert "out of scope" not in reason and "still open when the loop reached its round cap" in reason, ledger["A"]


def _rendered_guidance(state):
    """The owner-guidance text the fixer order carries for the queued batch (the real render path)."""
    assert RD._queue_fix_batch(state, state["config"], [dict(r) for r in state["findings"]
                                                          if not r.get(session_contract.MERGED_INTO_FIELD)]
                               ) == "queued"
    return RD._gate_guidance_block(RD._gate_guidance_entries(state, state["round"]))


def test_guidance_on_a_merged_member_is_rendered_in_the_representatives_fixer_order():
    """axis: MERGE — M merged into live K, guidance on M: the resolver sends K under M's decision and
    the rendered order carries that guidance."""
    state = _unit_round([_unit_finding("K", 1, "Important")])
    state["findings"].append(_unit_finding("M", 2, "Important"))
    state["findings"][-1][session_contract.MERGED_INTO_FIELD] = "K"
    _log_ruling(state, "M", guidance="FROM-THE-MEMBER")
    assert "FROM-THE-MEMBER" in _rendered_guidance(state)


def test_a_reworded_representative_with_decisions_on_it_and_its_member_takes_the_latest_guidance():
    """axis: MERGE + LINEAGE — M merged into K, guidance on both (M's newer), K reworded at its
    location and staged: one row N goes out, carrying the newest guidance, with no archived K beside it."""
    state = _unit_state({"file": "a.py", "line": 1, "title": "K"},
                        {"file": "a.py", "line": 2, "title": "M"})
    k, m = (RD._fix_batch_row_key(f) for f in state["findings"])
    RD._record_merged_into(state, m, k)
    for key, text in ((k, "OLD-ON-K"), (m, "NEWER-ON-M")):
        _log_ruling(state, key, guidance=text)
        state["rulingsLog"][-1].update(file="a.py", line=1 if key == k else 2)
    state["round"] = 3
    state["rounds"]["3"] = {}
    reworded = _unit_finding("K reworded", 1, "Important")
    RD._stage_findings(state, [reworded])
    assert state["findingLineage"] == {"K reworded": k}
    RD._set_findings(state, [dict(reworded)])
    assert [RD._fix_batch_row_key(r) for r in RD._resolve_ruled_batch(state, [dict(reworded)])] == [
        "K reworded"]
    assert "NEWER-ON-M" in _rendered_guidance(state)


def test_the_order_renders_the_decision_the_resolver_selected_not_a_later_skip_on_its_key():
    """axis: RENDER — N carries K's guidance, the owner then skips K (a skip binds K alone), N is merged
    into P: the order for P still carries the guidance the resolver selected."""
    state = _unit_round([_unit_finding("P", 1, "Important")])
    state["findings"].append(_unit_finding("N", 2, "Important"))
    state["findings"][-1][session_contract.MERGED_INTO_FIELD] = "P"
    state["findingLineage"] = {"N": "K"}
    _log_ruling(state, "K", guidance="STILL-BINDING")
    _log_ruling(state, "K", ruling="out-of-scope")
    assert "STILL-BINDING" in _rendered_guidance(state)


def test_a_ruling_restages_the_latest_wording_of_a_lineage_not_the_first_lexical_one():
    """axis: RESTAGE — A (Minor, code quality) reworded as Z (Critical, real), both fixed, a ruling on Z:
    the fixer is sent Z with its severity and consequence, and Z is the version marked reopened."""
    state = _unit_round([_unit_finding("Q", 1, "Minor")])
    state["findings"] = []
    for key, severity, kind, rnd in (("A", "Minor", "code-quality", 1), ("Z", "Critical", "real", 3)):
        RD._record_disposition(state, key, "fixed", rnd)
        for entry in state[session_contract.DISPOSITION_LEDGER_KEY]:
            if RD._finding_identity_key(entry) == key:
                entry.update(severity=severity, consequenceKind=kind,
                             **{session_contract.RAISED_ROUND_FIELD: rnd,
                                session_contract.RAISED_SEQ_FIELD: 0})
    state["findingLineage"] = {"Z": "A"}
    state["sentUnderDecision"] = {"A": 0}
    _log_ruling(state, "Z", guidance="RESTAGE-Z")
    batch = RD._resolve_ruled_batch(state, [])
    assert [(RD._fix_batch_row_key(r), r["severity"], r["consequenceKind"]) for r in batch] == [
        ("Z", "Critical", "real")]
    assert set(state["restagedAfterDispositionSeq"]) == {"Z", "A"}  # the discharged ancestor reopens too


def test_a_ruling_awaiting_batch_resolution_keeps_the_real_consequence_on_a_same_key_restage():
    """axis: RESTAGE — a fixed real-consequence finding with a ruling no fixer was sent yet is re-staged
    as code quality before the batch resolves: the real consequence stays on the ledger row."""
    state = _unit_round([_unit_finding("A", 1, "Important")])
    RD._record_disposition(state, "A", "fixed", 1)
    for entry in state[session_contract.DISPOSITION_LEDGER_KEY]:
        entry[session_contract.RAISED_SEQ_FIELD] = 0
        entry["consequence"], entry["consequenceKind"] = "data loss", "real"
    _log_ruling(state, "A", guidance="NOT-YET-SENT")
    ledger = state[session_contract.DISPOSITION_LEDGER_KEY]
    entry = RD._seed_ledger_entry(
        state, ledger, {"A": 0},
        dict(_unit_finding("A", 1, "Important", kind="code-quality"), consequence="harder to read"),
        "A", 2)
    assert entry["consequenceKind"] == "real" and "data loss" in entry["consequence"], entry


def test_a_ruling_skips_a_lineage_member_whose_own_decision_is_a_skip_and_reaches_the_one_it_binds():
    """axis: LINEAGE — live Minors A and Z share a lineage link, guidance on Z then a skip on A alone:
    the resolver sends Z (the row the guidance binds), not A first in the closure."""
    state = _unit_round([_unit_finding("A", 1, "Minor"), _unit_finding("Z", 2, "Minor")])
    state["findingLineage"] = {"Z": "A"}
    _log_ruling(state, "Z", guidance="FIX-Z")
    _log_ruling(state, "A", ruling="out-of-scope")
    batch = RD._resolve_ruled_batch(state, [])
    assert [RD._fix_batch_row_key(r) for r in batch] == ["Z"]


def test_late_guidance_on_a_fixed_finding_reopens_it_when_a_live_rewording_carries_the_ruling():
    """axis: RESTAGE — fixed real-consequence A gets guidance, live rewording Z is sent: A is marked
    reopened too, so a retry that ends undischarged does not settle A as fixed."""
    state = _unit_round([_unit_finding("Z", 2, "Minor", kind="code-quality")])
    RD._record_disposition(state, "A", "fixed", 1)
    for entry in state[session_contract.DISPOSITION_LEDGER_KEY]:
        entry[session_contract.RAISED_SEQ_FIELD] = 0
        entry["consequence"], entry["consequenceKind"] = "data loss", "real"
    state["findingLineage"] = {"Z": "A"}
    _log_ruling(state, "A", guidance="LATE")
    batch = RD._resolve_ruled_batch(state, [])
    assert [RD._fix_batch_row_key(r) for r in batch] == ["Z"]
    assert state["restagedAfterDispositionSeq"] == {"A": state["dispositionSeqCounter"]}
    RD._set_terminal(state, "held")
    ledger, _ = RD._disposition_ledger_by_key(state)
    assert ledger["A"]["disposition"] != "fixed", ledger["A"]


def test_ledger_restage_skips_a_candidate_whose_own_decision_is_a_later_skip():
    """axis: RESTAGE — A and reworded Z fixed, newer guidance on A then a skip on Z: the ledger fallback
    ranks only rows the guidance binds, so A is sent, not the skipped newest wording Z."""
    state = _unit_round([_unit_finding("Q", 1, "Minor")])
    state["findings"] = []
    for key, rnd in (("A", 1), ("Z", 3)):
        RD._record_disposition(state, key, "fixed", rnd)
        for entry in state[session_contract.DISPOSITION_LEDGER_KEY]:
            if RD._finding_identity_key(entry) == key:
                entry.update(**{session_contract.RAISED_ROUND_FIELD: rnd,
                                session_contract.RAISED_SEQ_FIELD: 0})
    state["findingLineage"] = {"Z": "A"}
    state["sentUnderDecision"] = {"A": 0}
    _log_ruling(state, "A", guidance="GUIDE-A")
    _log_ruling(state, "Z", ruling="out-of-scope")
    batch = RD._resolve_ruled_batch(state, [])
    assert [RD._fix_batch_row_key(r) for r in batch] == ["A"]


def test_late_guidance_reopens_a_discharged_ancestor_when_the_rewording_is_already_offered():
    """axis: RESTAGE — fixed real-consequence A gets guidance and rewording Z is already in the offered
    batch: no second row is added, A is still marked reopened, and an undischarged retry does not
    settle A as fixed."""
    state = _unit_round([_unit_finding("Z", 2, "Important", kind="code-quality")])
    RD._record_disposition(state, "A", "fixed", 1)
    for entry in state[session_contract.DISPOSITION_LEDGER_KEY]:
        entry[session_contract.RAISED_SEQ_FIELD] = 0
        entry["consequence"], entry["consequenceKind"] = "data loss", "real"
    state["findingLineage"] = {"Z": "A"}
    _log_ruling(state, "A", guidance="LATE")
    batch = RD._resolve_ruled_batch(state, [dict(state["findings"][0])])
    assert [RD._fix_batch_row_key(r) for r in batch] == ["Z"]
    assert state["restagedAfterDispositionSeq"] == {"A": state["dispositionSeqCounter"]}
    RD._note_sent_under_decision(state, batch)
    RD._set_terminal(state, "held")
    ledger, _ = RD._disposition_ledger_by_key(state)
    assert ledger["A"]["disposition"] != "fixed", ledger["A"]


def test_audit_discharge_of_the_ruled_rewording_supersedes_the_reopened_ancestor():
    """axis: RESTAGE — A fixed, reopened for rewording Z, Z discharged at the audit fold: A's reopening
    is superseded, so convergence does not settle A as left-for-owner."""
    state = RD.new_state({"leg": "code", "vendors": ["claude", "codex"], "diff": "d",
                          "fixerVendor": "codex", "seatMap": {"hostFamily": "anthropic"}})
    state["round"] = 2
    state["config"][RD.FIX_FOLD_HEAD_KEY] = "b" * 40
    state["rounds"] = {"2": {"verifyResult": "pass"}}
    z = {"title": "Z", "severity": "Important", "file": "f.py", "line": 1}
    state["fixBatch"] = [z]
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    zid = RD._finding_key_of(z)
    RD._set_findings(state, [z])
    RD._record_disposition(state, "A", "fixed", 1)
    state["findingLineage"] = {zid: "A"}
    state["restagedAfterDispositionSeq"] = {"A": state["dispositionSeqCounter"]}
    state["_newSurface"] = True
    auditor = state["_auditTargets"][0]["auditorVendor"]
    RD._fold_audits(state, state["config"], {
        "results": [{"id": zid, "ruling": "discharged", "reason": "gone"}],
        "collectionManifest": {zid: auditor}})
    assert "A" not in (state.get("restagedAfterDispositionSeq") or {})


def test_audit_discharge_keeps_every_restage_mark_when_the_open_list_cannot_be_resolved(monkeypatch):
    """axis: FAIL CLOSED — the same discharge, but the not-discharged list cannot be turned into open
    ids: the ancestor's reopening is not superseded, so a failed settle cannot read it as fixed.

    bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1b_c7_ruling_window.md (element x)
    """
    state = RD.new_state({"leg": "code", "vendors": ["claude", "codex"], "diff": "d",
                          "fixerVendor": "codex", "seatMap": {"hostFamily": "anthropic"}})
    state["round"] = 2
    state["config"][RD.FIX_FOLD_HEAD_KEY] = "b" * 40
    state["rounds"] = {"2": {"verifyResult": "pass"}}
    z = {"title": "Z", "severity": "Important", "file": "f.py", "line": 1}
    state["fixBatch"] = [z]
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    zid = RD._finding_key_of(z)
    RD._set_findings(state, [z])
    RD._record_disposition(state, "A", "fixed", 1)
    state["findingLineage"] = {zid: "A"}
    mark = state["dispositionSeqCounter"]
    state["restagedAfterDispositionSeq"] = {"A": mark}
    state["_newSurface"] = True
    monkeypatch.setattr(RD, "_open_audit_ids_from_not_discharged", lambda _not_discharged: None)
    auditor = state["_auditTargets"][0]["auditorVendor"]
    RD._fold_audits(state, state["config"], {
        "results": [{"id": zid, "ruling": "discharged", "reason": "gone"}],
        "collectionManifest": {zid: auditor}})
    assert state["restagedAfterDispositionSeq"] == {"A": mark}


def test_standing_rulings_omit_a_skip_a_merged_members_newer_guidance_supersedes():
    """axis: MERGE — M merged into K, K skipped at seq 1, guidance on M at seq 2: the batch binds the
    guidance and the orders' standing-rulings block no longer tells seats to drop K."""
    state = _unit_round([_unit_finding("K", 1, "Important")])
    state["findings"].append(_unit_finding("M", 2, "Important"))
    state["findings"][-1][session_contract.MERGED_INTO_FIELD] = "K"
    _log_ruling(state, "K", ruling="out-of-scope")
    RD._writable_rulings_log(state)[-1]["source"] = "rule"
    assert [r["findingKey"] for r in RD._standing_rulings_for_orders(state)[0]] == ["K"]
    _log_ruling(state, "M", guidance="FIX")
    assert RD._standing_rulings_for_orders(state) == ([], None)


def test_late_guidance_on_a_ledger_ancestor_reopens_it_when_a_ledger_rewording_is_restaged():
    """axis: RESTAGE — A and its rewording Z both archived fixed, guidance on A: Z is restaged and A
    is marked reopened too, so a failed retry does not settle A as fixed."""
    state = _unit_round([_unit_finding("Q", 1, "Minor")])
    state["findings"] = []
    for key, rnd in (("A", 1), ("Z", 3)):
        RD._record_disposition(state, key, "fixed", rnd)
        for entry in state[session_contract.DISPOSITION_LEDGER_KEY]:
            if RD._finding_identity_key(entry) == key:
                entry.update(**{session_contract.RAISED_ROUND_FIELD: rnd,
                                session_contract.RAISED_SEQ_FIELD: 0})
    state["findingLineage"] = {"Z": "A"}
    state["sentUnderDecision"] = {"A": 0}
    _log_ruling(state, "A", guidance="LATE")
    batch = RD._resolve_ruled_batch(state, [])
    assert [RD._fix_batch_row_key(r) for r in batch] == ["Z"]
    assert set(state["restagedAfterDispositionSeq"]) == {"A", "Z"}


def test_a_successful_audit_keeps_the_reopening_mark_of_a_member_that_still_fails_audit():
    """axis: RESTAGE — A reopened, Z (lineage A) discharged while A is not-discharged in the same
    fold: A's reopening mark survives."""
    state = RD.new_state({"leg": "code", "vendors": ["claude", "codex"], "diff": "d",
                          "fixerVendor": "codex", "seatMap": {"hostFamily": "anthropic"}})
    state["round"] = 2
    state["config"][RD.FIX_FOLD_HEAD_KEY] = "b" * 40
    state["rounds"] = {"2": {"verifyResult": "pass"}}
    z = {"title": "Z", "severity": "Important", "file": "f.py", "line": 1}
    a = {"title": "A", "severity": "Important", "file": "f.py", "line": 2}
    state["fixBatch"] = [z, a]
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    zid, aid = RD._finding_key_of(z), RD._finding_key_of(a)
    RD._set_findings(state, [z, a])
    RD._record_disposition(state, aid, "fixed", 1)
    state["findingLineage"] = {zid: aid}
    state["restagedAfterDispositionSeq"] = {aid: state["dispositionSeqCounter"]}
    state["_newSurface"] = True
    auditor = state["_auditTargets"][0]["auditorVendor"]
    RD._fold_audits(state, state["config"], {
        "results": [{"id": zid, "ruling": "discharged", "reason": "gone"},
                    {"id": aid, "ruling": "not-discharged", "reason": "still broken"}],
        "collectionManifest": {zid: auditor, aid: auditor}})
    assert aid in (state.get("restagedAfterDispositionSeq") or {})
