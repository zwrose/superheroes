"""Issue 2527: an empty synthesis grouping is a valid answer when there was nothing to group.

A round whose findings were all refuted, while the PR has earlier findings, still dispatches a
repeat-only synthesis order; the seat correctly answers `{"grouping": []}`. The runner used to grade
every empty grouping with no `investigated` list vacuous, so every attempt forfeited. A review run
opened with `--nothing-to-group` now grades that answer ok from a seat the runner saw use tools.

Every grade case drives the real grader `ED._grade_review_attempt` over a real opened review run
(`_open_run` is `_manual_open_review_run` with the flag threaded through the real
`_build_resolved_inputs` and `_open_review_run`). The record-time cases drive the real driver and
the real adapter (no `round_adapters` stub) through `record-result --evidence-run-dir` over a run
the real `dispatch_review` entry produced; only the engine process is a scripted `FakeRunner`.

Guarded elements (one test function each unless noted):
  G-I1  T1  flagged run, empty grouping ([] and null), engaged -> ok, value kept exactly as parsed
  G-I1b T2  flagged run, empty grouping, toolCalls None or 0 -> vacuous forfeit (the engagement floor)
  E3    T3  unflagged run, empty grouping, engaged -> vacuous forfeit (today's grading)
  E6    T4  flagged run: non-empty grouping ok as today; findings/verdicts with no payload stay vacuous
  I2    T5  `nothingToGroup` on `run-opened` and the execution record; a continuation cannot add or drop it
  I3    T6  the synthesis payload carries `nothingToGroup` exactly when `findings` is empty
  G-I4  T7  record-result of a flagged run on a round with survivors refuses `evidence-nothing-to-group-mismatch`
  DoD1  T8  the reported shape end to end: all findings refuted, earlier pool present -> clean terminal
  G-I5  T9  a landing with no runner evidence reads `no-runner-evidence`; a wrong or barred vendor keeps its name

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/wo_a_2527_nothing_to_group.md
"""
import json
import os
import sys
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from bite_support import _stamp_ended_from_native_result  # noqa: E402
import repeat_marks as RM  # noqa: E402
import round_adapters as RA  # noqa: E402
import round_driver as RD  # noqa: E402
import round_records as RR  # noqa: E402
import test_repeat_marks_c1l8 as C8  # noqa: E402
import test_round_driver_integration as TRI  # noqa: E402
import test_synthesis_seat_1858 as S1858  # noqa: E402
import test_verifier_vendor_provenance_1797 as P17  # noqa: E402
from test_engine_dispatch import (  # noqa: E402
    ED,
    FakeRunner,
    _codex_event_stream,
    _codex_seat,
    _fake_build_view,
    _fed_prompt,
    _repo,
    _sync_native_review_result_from_stdout,
    _valid_prompt,
)
from test_engine_dispatch import _pin_temp_base_to_tmp_path  # noqa: E402,F401  autouse: keeps views and journals under tmp_path

VACUOUS = ED.engine_adapter.REVIEW_FORFEIT_VACUOUS
A_GROUP = {"grouping": [{"member_ids": ["f1", "f2"], "repeatOf": None}]}


# ---------------------------------------------------------------------------------------------
# a real opened review run, graded by the real grader
# ---------------------------------------------------------------------------------------------

def _open_run(tmp_path, run_dir, *, nothing_to_group):
    """Open a real review run (no process spawned) with the flag as asked — `_manual_open_review_run`
    plus the flag, through the real snapshot builder and the real run-opened writer."""
    repo_root = _repo(tmp_path)
    view = _fake_build_view(tmp_path)(os.path.realpath(repo_root))
    cwd = os.path.realpath(view["path"])
    seat = _codex_seat()
    built = ED.engine_adapter.build_argv_result(seat, "review", {"model": "sonnet", "cwd": cwd})
    prompt_path = _valid_prompt(tmp_path)
    with open(prompt_path, encoding="utf-8") as fh:
        base = fh.read()
    os.makedirs(run_dir, exist_ok=True)
    progress_path = os.path.join(run_dir, "progress.jsonl")
    resolved_inputs = ED._build_resolved_inputs(
        seat=seat, role_kind="review", repo_root=os.path.realpath(repo_root), run_dir_real=run_dir,
        run_dir_source="caller", staged_prompt_path=os.path.join(run_dir, ED.PROMPT_NAME),
        timeout=ED.RETRY_MIN_TIMEOUT, timeout_source="default",
        retry_timeout=ED.RETRY_MIN_TIMEOUT, retry_timeout_source="default",
        max_wait=None, max_wait_source="default", preflight_timeout=None,
        preflight_timeout_source="declared-none", mode="review", mode_source="default",
        expected_result_kind=None, expected_result_kind_source="declared-none",
        base_sha=None, base_sha_source="declared-none", diff_base=view.get("diffBase"),
        diff_base_source="resolved" if view.get("diffBase") is not None else "declared-none",
        progress_path=progress_path, progress_path_source="resolved",
        engine_model_opts={"cwd": cwd}, nothing_to_group=nothing_to_group,
    )
    ok, detail = ED._open_review_run(
        run_dir, engine="codex", argv=built["argv"], cwd=cwd,
        timeout=ED.RETRY_MIN_TIMEOUT, retry_timeout=ED.RETRY_MIN_TIMEOUT,
        prompt_path=prompt_path, view_path=view["path"], view_meta=view,
        fed_prompt=_fed_prompt(base, view_meta=view), order_id="test-order",
        progress_path=progress_path, repo_root=os.path.realpath(repo_root),
        resolved_inputs=resolved_inputs, nothing_to_group=nothing_to_group,
        echo_nonce="nonce-2527",
    )
    assert ok, detail
    return view


def _grade(tmp_path, payload, *, nothing_to_group, tool_calls, run_name="run"):
    """Open a real run, stage `payload` as attempt 1's result with `tool_calls` completed tool calls
    in the engine's event stream (None: a stream with no tool-call channel), grade it for real."""
    run_dir = str(tmp_path / run_name)
    _open_run(tmp_path, run_dir, nothing_to_group=nothing_to_group)
    text = json.dumps(payload)
    stdout = text if tool_calls is None else _codex_event_stream(text, action_items=tool_calls)
    with open(os.path.join(run_dir, "attempt-1.stdout"), "w", encoding="utf-8") as fh:
        fh.write(stdout)
    with open(os.path.join(run_dir, "attempt-1.stderr"), "w", encoding="utf-8") as fh:
        fh.write("")
    _sync_native_review_result_from_stdout(run_dir, text)
    ED._journal_append(run_dir, {"kind": "attempt-started", "attempt": 1, "childPid": 1,
                                 "at": time.time()})
    ended = _stamp_ended_from_native_result(run_dir, {
        "exit": 0, "timedOut": False, "signal": None, "refusal": None, "at": time.time(),
        "wallSeconds": 1.0, "stdoutBytes": len(stdout),
    })
    ED._journal_append(run_dir, {"kind": "attempt-ended", "attempt": 1, **ended})
    records, _ = ED._journal_read(run_dir)
    return ED._grade_review_attempt(run_dir, ED._journal_state(records), 1)


@pytest.mark.parametrize("grouping, tool_calls", [
    pytest.param([], 1, id="empty-list-one-call"),
    pytest.param(None, 1, id="null-one-call"),
    pytest.param([], 5, id="empty-list-five-calls"),
])
def test_t1_flagged_empty_grouping_from_an_engaged_seat_is_ok_and_keeps_its_value(
        tmp_path, grouping, tool_calls):
    # axis: the nothing-to-group ok branch — an engaged seat's empty grouping is graded ok, not vacuous (G-I1, I1, E5)
    grade = _grade(tmp_path, {"grouping": grouping}, nothing_to_group=True, tool_calls=tool_calls)
    assert grade.get("ok") is True, grade
    assert grade.get("resultKind") == "grouping"
    assert "grouping" in grade and grade["grouping"] == grouping
    assert (grade["grouping"] is None) == (grouping is None)  # null stays null, [] stays []
    assert "forfeit" not in grade
    assert grade["engagement"]["read"] == "engaged"
    assert grade["engagement"]["toolCalls"] == tool_calls


@pytest.mark.parametrize("grouping", [[], None], ids=["empty-list", "null"])
@pytest.mark.parametrize("tool_calls", [None, 0], ids=["no-telemetry", "zero-tool-calls"])
def test_t2_flagged_empty_grouping_without_observed_tool_calls_is_vacuous(
        tmp_path, grouping, tool_calls):
    # axis: the engagement floor inside the nothing-to-group branch — no observed tool call, no ok (G-I1b, E1, E2)
    grade = _grade(tmp_path, {"grouping": grouping}, nothing_to_group=True, tool_calls=tool_calls)
    assert grade.get("forfeit") is True, grade
    assert grade.get("reason") == VACUOUS
    assert "ok" not in grade


@pytest.mark.parametrize("grouping", [[], None], ids=["empty-list", "null"])
def test_t3_unflagged_empty_grouping_from_an_engaged_seat_stays_vacuous(tmp_path, grouping):
    # axis: a run opened without the flag is graded exactly as before (E3) — the seat answered nothing
    grade = _grade(tmp_path, {"grouping": grouping}, nothing_to_group=False, tool_calls=3)
    assert grade.get("forfeit") is True, grade
    assert grade.get("reason") == VACUOUS


def test_t4_the_flag_touches_only_the_grouping_kind(tmp_path):
    # axis: a flagged run grades a non-empty grouping ok as today and every other kind exactly as before (E6)
    group = _grade(tmp_path, A_GROUP, nothing_to_group=True, tool_calls=None, run_name="group")
    assert group.get("ok") is True and group["grouping"][0]["member_ids"] == ["f1", "f2"], group
    assert "forfeit" not in group
    for kind, run_name in (("findings", "findings"), ("verdicts", "verdicts")):
        grade = _grade(tmp_path, {kind: []}, nothing_to_group=True, tool_calls=3, run_name=run_name)
        assert grade.get("forfeit") is True, (kind, grade)
        assert grade.get("reason") == VACUOUS, (kind, grade)


# ---------------------------------------------------------------------------------------------
# I2 — the journal and the execution record
# ---------------------------------------------------------------------------------------------

def _dispatch(tmp_path, run_dir, grouping, *, nothing_to_group, prompt_path=None, tool_calls=1,
              responses=None, **kw):
    """The real `dispatch_review` entry; only the engine process is the scripted `FakeRunner`."""
    stdout = _codex_event_stream(json.dumps({"grouping": grouping}), action_items=tool_calls)
    runner = FakeRunner(responses if responses is not None else [(stdout, False, 0, "")] * 6)
    return ED.dispatch_review(
        seat=_codex_seat(), prompt_path=prompt_path or _valid_prompt(tmp_path),
        repo_root=_repo(tmp_path), run_engine=runner, build_view=kw.pop(
            "build_view", _fake_build_view(tmp_path)),
        run_dir=run_dir, order_id=kw.pop("order_id", "order-2527"),
        nothing_to_group=nothing_to_group, **kw)


def _opened(run_dir):
    records, _ = ED._journal_read(run_dir)
    return next(r for r in records if r.get("kind") == "run-opened")


def test_t5_the_flag_is_journaled_at_open_and_rides_the_execution_record(tmp_path):
    # axis: I2 — `nothingToGroup` is on run-opened and the execution record only for a run opened with the flag
    flagged_dir = str(tmp_path / "flagged")
    flagged = _dispatch(tmp_path, flagged_dir, [], nothing_to_group=True)
    assert flagged["ok"] is True and flagged["grouping"] == [], flagged
    opened = _opened(flagged_dir)
    assert opened["nothingToGroup"] is True
    assert opened["resolvedInputs"]["nothingToGroup"] is True
    assert opened["resolvedInputs"]["nothingToGroupSource"] == "caller"
    record, err = ED.run_execution_record(flagged_dir)
    assert err is None and record["nothingToGroup"] is True, (record, err)

    plain_dir = str(tmp_path / "plain")
    plain = _dispatch(tmp_path, plain_dir, A_GROUP["grouping"], nothing_to_group=False)
    assert plain["ok"] is True, plain
    opened = _opened(plain_dir)
    assert "nothingToGroup" not in opened and "nothingToGroup" not in opened["resolvedInputs"]
    record, err = ED.run_execution_record(plain_dir)
    assert err is None and "nothingToGroup" not in record, (record, err)


def test_t5_a_continuation_can_neither_add_nor_drop_the_flag(tmp_path):
    # axis: E8 — the journaled value governs a continuation; a flag supplied on a continuation is ignored
    kept = str(tmp_path / "kept")
    _open_run(tmp_path, kept, nothing_to_group=True)
    out = _dispatch(tmp_path, kept, [], nothing_to_group=False,  # a continuation that drops the flag
                    order_id="test-order")
    assert _opened(kept)["nothingToGroup"] is True
    assert out["ok"] is True and out["grouping"] == [], out  # graded under the journaled flag

    unflagged = str(tmp_path / "unflagged")
    _open_run(tmp_path, unflagged, nothing_to_group=False)
    out = _dispatch(tmp_path, unflagged, [], nothing_to_group=True,  # a continuation that adds it
                    order_id="test-order")
    assert "nothingToGroup" not in _opened(unflagged)
    assert out["ok"] is not True and out.get("reason") == VACUOUS, out  # still graded as unflagged
    record, err = ED.run_execution_record(unflagged)
    assert err is None and "nothingToGroup" not in record, (record, err)


def test_t5_the_cli_flag_is_a_boolean_threaded_to_the_library_entry(tmp_path, monkeypatch):
    # axis: the flag is a store_true on dispatch-review only, and `main` hands it to `dispatch_review`
    parser = ED.build_parser()
    base = ["dispatch-review", "--seat", "{}", "--prompt-path", "p", "--repo-root", _repo(tmp_path)]
    assert parser.parse_args(base).nothing_to_group is False
    assert parser.parse_args(base + ["--nothing-to-group"]).nothing_to_group is True
    seen = {}

    def capture(**kw):
        seen.update(kw)
        return {"ok": False, "terminal": True, "reason": "unrunnable", "attempts": 0,
                "forfeited": False}

    monkeypatch.setattr(ED, "dispatch_review", capture)
    ED.main(base + ["--nothing-to-group"])
    assert seen["nothing_to_group"] is True
    seen.clear()
    ED.main(base)
    assert seen["nothing_to_group"] is False


# ---------------------------------------------------------------------------------------------
# a real session at the synthesis step (real driver, real adapter)
# ---------------------------------------------------------------------------------------------

def _earlier_entries():
    entries, _ = RM.read_earlier_findings(C8._record_payload(
        [C8._record_finding(C8._raw("an earlier record finding", line=4), "craft")]))
    assert entries
    return entries


def _drive_phase(session_dir, gitdir, panel_findings, head_path, *, refute=False):
    """Land and record every roster slot of the pending phase through the real adapter, then advance.
    With `refute`, every verifier verdict is REFUTED instead of the fixture's CONFIRMED."""
    TRI._assert_adapters_are_real()
    state = TRI._state(session_dir)
    pend = state["pending"]
    phase = pend["phase"]
    roster, reason = RA.roster_for(phase, state, state.get("config") or {})
    assert reason is None, (phase, reason)
    slots = TRI._slots_of(roster)
    TRI._write_dispatch_manifest(session_dir, pend, slots, TRI._auditor_vendor_for(state))
    for seat, occurrence in slots:
        if refute and phase == RD.P_VERIFIERS:
            cluster = TRI._cluster_for(pend, seat)
            payload = {"verdicts": [{"id": f["id"], "verdict": "REFUTED", "reason": "the guard holds"}
                                    for f in cluster.get("findings") or []]}
        else:
            payload = TRI._payload_for(session_dir, state, pend, seat, panel_findings, head_path)
        TRI._land(session_dir, state, pend, seat, payload, occurrence=occurrence)
        out = TRI._record(session_dir, seat, occurrence=occurrence)
        assert out["ok"], (phase, seat, out)
    out = RD.cmd_advance(session_dir, git=TRI._fake_git(gitdir))
    assert out["ok"], (phase, out)
    return phase


def _session_at_synthesis(tmp_path, name, *, refute):
    """A session whose round 1 reported one finding, the verifiers judged it (refuted or confirmed) and
    synthesis is pending. An earlier-findings pool is supplied so a fully refuted round still offers it."""
    finding = TRI._blocking_finding("a claim the verifier will judge", 3)
    session_dir, gitdir, head_path = TRI._bootstrap(
        tmp_path, name=name, earlierFindings=_earlier_entries())
    assert _drive_phase(session_dir, gitdir, [finding], head_path) == RD.P_PANEL
    assert _drive_phase(session_dir, gitdir, [finding], head_path, refute=refute) == RD.P_VERIFIERS
    pend = TRI._state(session_dir)["pending"]
    assert pend["phase"] == RD.P_SYNTHESIS, pend  # the order is offered
    return session_dir, gitdir, head_path, finding


def _flagged_synthesis_run(tmp_path, session_dir, run_name, grouping, *, nothing_to_group):
    """A real `dispatch_review` run over the pending synthesis order, its view at the order's head."""
    state = TRI._state(session_dir)
    pend = state["pending"]
    order_path = RR.order_prompt_path(session_dir, pend["round"], pend["phase"],
                                      RR.storage_key(RA.SEAT_SYNTHESIS), pend["attempt"])
    anchor = RD._orders_anchor(state, session_dir, pend["round"], pend["phase"], pend["attempt"])
    head = (anchor or {}).get("headSha")
    assert head
    base_view = _fake_build_view(tmp_path)

    def build_view(repo, **kw):
        return dict(base_view(repo, **kw), headSha=head)

    run_dir = str(tmp_path / run_name)
    out = _dispatch(tmp_path, run_dir, grouping, nothing_to_group=nothing_to_group,
                    prompt_path=order_path, build_view=build_view, order_id="synthesis-order")
    return run_dir, out


def _land_synthesis(session_dir, grouping):
    state = TRI._state(session_dir)
    pend = state["pending"]
    TRI._write_dispatch_manifest(session_dir, pend, [(RA.SEAT_SYNTHESIS, 0)],
                                 TRI._auditor_vendor_for(state))
    return TRI._dispatch_observed_land(session_dir, state, pend, RA.SEAT_SYNTHESIS,
                                       {"grouping": grouping})


def _read(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as fh:
        return fh.read()


def test_t6_the_synthesis_payload_carries_nothing_to_group_exactly_when_findings_is_empty():
    # axis: I3 — the key rides the pending payload only for a repeat-only order
    state = RD.new_state(S1858._cfg())
    state["step"] = RD.P_SYNTHESIS
    state["round"] = 1
    state["_earlierPool"] = {"entries": RM.build_pool(state, 1, _earlier_entries())}
    survivor = dict(S1858._A_FINDING[0], id="f1", verdict="CONFIRMED")
    refuted = dict(S1858._A_FINDING[0], id="f2", verdict="REFUTED")

    state["_verified"], state["_refuted"] = [], [refuted]
    repeat_only = RD._advance(state, state["config"])["payload"]
    assert repeat_only["findings"] == [] and repeat_only["nothingToGroup"] is True, repeat_only
    assert repeat_only["earlier"], repeat_only  # the earlier pool is what the order asks about

    state["_verified"] = [survivor]
    mixed = RD._advance(state, state["config"])["payload"]
    assert mixed["findings"] == [survivor] and "nothingToGroup" not in mixed, mixed


def test_t7_a_flagged_run_cannot_answer_a_round_that_has_survivors(tmp_path):
    # axis: the record-time binding refuses a nothing-to-group run on a round with survivors (G-I4, I4, E4)
    session_dir, _gitdir, _head, _finding = _session_at_synthesis(tmp_path, "t7", refute=False)
    state = TRI._state(session_dir)
    assert state["_verified"], "premise: the round has a survivor"
    pend = state["pending"]
    assert "nothingToGroup" not in pend["payload"]

    run_dir, out = _flagged_synthesis_run(tmp_path, session_dir, "t7-flagged", [], nothing_to_group=True)
    assert out["ok"] is True, out  # the runner graded the seat's own answer ok ...
    landing = _land_synthesis(session_dir, [])
    before = _read(landing)
    refused = RD.cmd_record_result(session_dir, RA.SEAT_SYNTHESIS, evidence_run_dir=run_dir)
    assert refused["ok"] is False  # ... the driver still refuses it for this round
    assert refused["reason"] == "evidence-nothing-to-group-mismatch", refused
    assert _read(landing) == before  # the landing is untouched
    store = RR.store_path(session_dir, pend["round"], pend["phase"],
                          RR.storage_key(RA.SEAT_SYNTHESIS), pend["attempt"])
    assert not os.path.exists(store)  # nothing stored

    # the same round binds an unflagged run as before
    plain_dir, plain = _flagged_synthesis_run(tmp_path, session_dir, "t7-plain", A_GROUP["grouping"],
                                              nothing_to_group=False)
    assert plain["ok"] is True, plain
    _land_synthesis(session_dir, A_GROUP["grouping"])
    bound = RD.cmd_record_result(session_dir, RA.SEAT_SYNTHESIS, evidence_run_dir=plain_dir)
    assert bound["ok"] is True, bound


@pytest.mark.parametrize("grouping", [[], None], ids=["empty-list", "null"])
def test_t8_refuted_round_with_earlier_findings_lands_an_empty_grouping_and_finishes_clean(
        tmp_path, grouping):
    # axis: DoD 1 — the reported shape end to end, through the real grader, binding and driver
    session_dir, gitdir, head_path, finding = _session_at_synthesis(tmp_path, "t8", refute=True)
    state = TRI._state(session_dir)
    assert state["_verified"] == [] and state["_refuted"], "premise: every finding was refuted"
    pend = state["pending"]
    assert pend["payload"]["findings"] == [] and pend["payload"]["nothingToGroup"] is True, pend

    run_dir, out = _flagged_synthesis_run(tmp_path, session_dir, "t8-run", grouping, nothing_to_group=True)
    assert out["ok"] is True and out["resultKind"] == "grouping", out
    assert out["grouping"] == grouping and (out["grouping"] is None) == (grouping is None), out
    assert "forfeit" not in out and out.get("forfeited") is not True, out
    _land_synthesis(session_dir, grouping)
    recorded = RD.cmd_record_result(session_dir, RA.SEAT_SYNTHESIS, evidence_run_dir=run_dir)
    assert recorded["ok"] is True, recorded
    advanced = RD.cmd_advance(session_dir, git=TRI._fake_git(gitdir))
    assert advanced["ok"] is True, advanced
    assert advanced["folded"]["phase"] == RD.P_SYNTHESIS, advanced

    for _ in range(12):  # whatever steps follow the grouping fold reach the terminal
        if TRI._state(session_dir).get("terminal"):
            break
        _drive_phase(session_dir, gitdir, [finding], head_path)
    final = TRI._state(session_dir)
    assert final["terminal"] == "converged", final.get("terminal")
    ledger = final[RD.session_contract.DISPOSITION_LEDGER_KEY]
    assert [e["disposition"] for e in ledger] == ["refuted"], ledger
    assert RD.build_receipt(final)


# ---------------------------------------------------------------------------------------------
# I5 — what a refused finder landing is called
# ---------------------------------------------------------------------------------------------

def _synthesis_landing(source=None):
    env = P17._finder_envelope(RA.SEAT_SYNTHESIS, source=source)
    env["payload"] = {"grouping": []}
    return env


def _assemble(state, source=None, recorded="claude"):
    return RA.assemble(RD.P_SYNTHESIS, [_synthesis_landing(source)], state, state["config"],
                       orders_manifest=P17._finder_manifest(RA.SEAT_SYNTHESIS, vendor=recorded))


def _disclosure(state, source=None, recorded="claude"):
    roster, _ = RA.roster_for(RD.P_SYNTHESIS, state, state["config"])
    indexed, fault = RA._index_envelopes(RD.P_SYNTHESIS, [_synthesis_landing(source)], roster)
    assert fault is None, fault
    disclosures = {}
    reason = RA._authenticate_finder(
        roster, indexed, None, P17._finder_manifest(RA.SEAT_SYNTHESIS, vendor=recorded),
        RA._maker_barred(state, state["config"]), disclosures)
    return reason, disclosures


def test_t9_a_landing_with_no_runner_evidence_is_named_for_what_is_missing():
    # axis: the no-runner-evidence branch — no executed vendor and an eligible recorded one is not a wrong vendor (G-I5, I5)
    art, why = _assemble(S1858._state(), source=None, recorded="claude")
    assert art is None, art
    assert why.startswith("missing-seat-refuse-fold:%s:no-runner-evidence:" % RA.SEAT_SYNTHESIS), why
    assert why.endswith("recorded=claude") and "unauthenticated-vendor" not in why, why
    reason, disclosures = _disclosure(S1858._state(), source=None, recorded="claude")
    assert reason == why
    assert disclosures["unauthenticatedFinder"] == {
        "seat": RA.SEAT_SYNTHESIS, "executed": None, "recorded": "claude"}


def test_t9_a_barred_recorded_vendor_keeps_the_unauthenticated_vendor_name():
    # axis: E7 — executed None with a barred recorded vendor stays unauthenticated-vendor ... :vendor-ineligible
    state = S1858._state(makers=["anthropic"])
    art, why = _assemble(state, source=None, recorded="claude")
    assert art is None, art
    assert why.startswith("missing-seat-refuse-fold:%s:unauthenticated-vendor:" % RA.SEAT_SYNTHESIS), why
    assert "executed=None" in why and "recorded=claude" in why and why.endswith(":vendor-ineligible"), why
    _reason, disclosures = _disclosure(state, source=None, recorded="claude")
    assert disclosures["unauthenticatedFinder"]["executed"] is None


def test_t9_a_different_executed_vendor_keeps_the_unauthenticated_vendor_name():
    # axis: a non-None executed vendor that differs from the recorded one keeps today's spelling
    art, why = _assemble(S1858._state(), source="codex", recorded="claude")
    assert art is None, art
    assert ":unauthenticated-vendor:executed=codex:recorded=claude" in why, why
    assert "no-runner-evidence" not in why and not why.endswith(":vendor-ineligible"), why
    _reason, disclosures = _disclosure(S1858._state(), source="codex", recorded="claude")
    assert disclosures["unauthenticatedFinder"]["executed"] == "codex"
