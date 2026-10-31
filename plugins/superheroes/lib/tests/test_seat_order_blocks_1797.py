"""#1797 WO-B — every seat order carries the lens brief, the project threat model and the session's
standing rulings; the panel follows the seeded seat map's roster.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/wo_b_1797_seat_orders.md
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import round_adapters as RA  # noqa: E402
import receipt_disclosures as RDS  # noqa: E402
import round_driver as RD  # noqa: E402
import round_orders as RO  # noqa: E402
import seat_map as SM  # noqa: E402
import session_contract  # noqa: E402
import test_round_driver_order_channel as OC  # noqa: E402
import test_rulings_channel_1445 as RUL  # noqa: E402

# A literal double-brace placeholder token, assembled so this file never carries one verbatim.
_BRACES = "{" + "{"
_TOKEN = _BRACES + "ROUND}}"

_ROLE_BRIEF_PREFIX = "- Your role brief (read it first; it binds over the generic assignment above): "
_CRITICAL_EXCEPTION = "a finding that is now Critical is always reported"


def _context(phase, host_seat, brief_for=None, **ctx_extra):
    channel = RD.CHANNEL_FILE if host_seat else RD.CHANNEL_STDOUT
    placeholders = OC._phase_placeholders(phase, channel)
    if brief_for is not None:
        placeholders["ROLE_BRIEF_PATH"] = RD._role_brief_path(brief_for)
    context = {
        "session_dir": OC.SESSION, "round": 1, "attempt": 1,
        "diff_path": OC.SESSION + "/round-1/diff.txt",
        "rubric_path": "/plugin/rubric/review-base.md",
        "core_path": "/proj/core.md", "layer_path": "/proj/layer.md", "repo_root": "/proj",
        "landing_path": OC.BARE if host_seat else OC.LANDING,
        "envelope_stub_path": OC.SESSION + "/round-1/landing/p/skey.a1.stub.json",
        "ratified_residuals": "", "residuals_provenance": "prov", "residuals_read_failure": None,
        "threat_model": "", "threat_model_read_failure": None,
        "standing_rulings": [], "standing_rulings_read_failure": None,
        "payload": {}, "host_seat": host_seat, "placeholders": placeholders,
    }
    context.update(ctx_extra)
    return context


def _render(phase, host_seat, seat="seat", brief_for=None, **ctx_extra):
    text, reason = RO.render_order(phase, seat, _context(phase, host_seat, brief_for, **ctx_extra))
    assert reason is None, (phase, host_seat, reason)
    return text


def _core_md(threat_model):
    return ("# Core\n\n```json superheroes-core\n"
            '{"schemaVersion": 1, "verifyCommand": null, "stackTags": []}\n```\n\n'
            "## Threat model\n%s\n\n## Canonical patterns\nnone\n" % threat_model)


# --- B2: every lens seat's panel order carries its role brief, on every engine ------------------

def test_every_lens_seat_has_a_brief_file_and_role_brief_seats_is_derived():
    # axis: the brief file EXISTS for every AGENT_SUFFIX seat and the set is derived from it —
    # see bite-proof record wo_b_1797_seat_orders
    assert RD.ROLE_BRIEF_SEATS == frozenset(RD.AGENT_SUFFIX)
    for seat in RD.AGENT_SUFFIX:
        path = RD._role_brief_path(seat)
        assert path.endswith(os.path.join("agents", "%s.md" % seat)), seat
        assert os.path.isabs(path), seat
        assert os.path.isfile(path), "no brief file for lens seat %s: %s" % (seat, path)


@pytest.mark.parametrize("host_seat", [True, False], ids=["host-file", "engine-stdout"])
@pytest.mark.parametrize("seat", sorted(RD.AGENT_SUFFIX))
def test_panel_order_names_each_lens_seats_brief_on_both_channels(seat, host_seat):
    # axis: a lens seat's panel order dropping its own absolute brief path, per channel —
    # see bite-proof record wo_b_1797_seat_orders
    text = _render(RD.P_PANEL, host_seat, seat=seat, brief_for=seat)
    expected = _ROLE_BRIEF_PREFIX + RD._role_brief_path(seat)
    assert expected in text.splitlines(), seat


# --- B3: every order carries the project's threat model (quoted data) ---------------------------

@pytest.mark.parametrize("host_seat", [True, False], ids=["host-file", "engine-stdout"])
@pytest.mark.parametrize("phase", RO.ORDER_PHASES)
def test_threat_model_block_on_every_phase(phase, host_seat):
    # axis: the threat-model block missing from one phase's order — see bite-proof record
    # wo_b_1797_seat_orders
    text = _render(phase, host_seat, threat_model="Attackers can forge session cookies.")
    assert ("## Project threat model (project calibration, quoted data)\n\n-----\n"
            "Attackers can forge session cookies.\n-----") in text, phase


@pytest.mark.parametrize("phase", RO.ORDER_PHASES)
def test_threat_model_unreadable_states_are_explicit_lines_never_an_absent_block(phase):
    heading = "## Project threat model (project calibration, quoted data)"
    unresolved = _render(phase, True, threat_model="",
                         threat_model_read_failure=RO.THREAT_MODEL_CORE_UNRESOLVED)
    assert ("%s\n\nThe project's threat model could not be read: core calibration not resolved."
            % heading) in unresolved
    refused = _render(phase, True, threat_model="",
                      threat_model_read_failure="core calibration refused (json block missing or corrupt)")
    assert "could not be read: core calibration refused (json block missing or corrupt)." in refused
    empty = _render(phase, True, threat_model="  \n")
    assert "%s\n\nNo threat model is recorded for this project." % heading in empty
    # a context that never carried the keys at all still renders the block, as a failure line
    context_less = {k: v for k, v in _context(phase, True).items()
                    if k not in ("threat_model", "threat_model_read_failure")}
    text, reason = RO.render_order(phase, "seat", context_less)
    assert reason is None, reason
    assert ("%s\n\nThe project's threat model could not be read: not supplied to the renderer."
            % heading) in text


@pytest.mark.parametrize("phase", RO.ORDER_PHASES)
def test_double_brace_in_threat_model_and_rulings_is_escaped_not_refused(phase):
    # axis: the double-brace escape on BOTH quoted-data blocks (an unescaped token trips the
    # renderer's unfilled-placeholder refusal) — see bite-proof record wo_b_1797_seat_orders
    text = _render(phase, True, threat_model="Never trust %s ever." % _TOKEN,
                   standing_rulings=[{"findingKey": "k-%s" % _TOKEN,
                                      "reason": "reason with %s inside" % _TOKEN}])
    assert _TOKEN not in text
    assert "Never trust { {ROUND}} ever." in text
    assert "- k-{ {ROUND}}: out of scope — reason with { {ROUND}} inside" in text


def test_resolve_order_threat_model_reads_the_core_prose_and_names_every_failure(tmp_path):
    good = tmp_path / "core.md"
    good.write_text(_core_md("Phishing of the operator account."), encoding="utf-8")
    assert RO.resolve_order_threat_model(str(good)) == ("Phishing of the operator account.", None)
    empty = tmp_path / "empty.md"
    empty.write_text(_core_md(""), encoding="utf-8")
    assert RO.resolve_order_threat_model(str(empty)) == ("", None)
    # unresolved core path
    assert RO.resolve_order_threat_model(None) == ("", RO.THREAT_MODEL_CORE_UNRESOLVED)
    assert RO.resolve_order_threat_model("") == ("", RO.THREAT_MODEL_CORE_UNRESOLVED)
    # unreadable file
    text, reason = RO.resolve_order_threat_model(str(tmp_path / "absent.md"))
    assert text == "" and reason.startswith("core calibration unreadable")
    # parse refused: no json block
    broken = tmp_path / "broken.md"
    broken.write_text("## Threat model\nsomething\n", encoding="utf-8")
    text, reason = RO.resolve_order_threat_model(str(broken))
    assert text == "" and reason.startswith("core calibration refused")
    # parse refused: a malformed verifyCommand raises inside the parser
    bad_verify = tmp_path / "bad_verify.md"
    bad_verify.write_text(_core_md("t").replace('"verifyCommand": null', '"verifyCommand": 7'),
                          encoding="utf-8")
    text, reason = RO.resolve_order_threat_model(str(bad_verify))
    assert text == "" and reason.startswith("core calibration refused")


# --- B4: every order carries the session's standing rulings (quoted data) -----------------------

@pytest.mark.parametrize("host_seat", [True, False], ids=["host-file", "engine-stdout"])
@pytest.mark.parametrize("phase", RO.ORDER_PHASES)
def test_standing_rulings_block_on_every_phase(phase, host_seat):
    # axis: the standing-rulings block missing from one phase's order — see bite-proof record
    # wo_b_1797_seat_orders
    text = _render(phase, host_seat, standing_rulings=[
        {"findingKey": "src/a.py:Edge case", "reason": "owner deferred it to the next milestone"}])
    assert "## Standing rulings (recorded this session, quoted data)" in text, phase
    assert "- src/a.py:Edge case: out of scope — owner deferred it to the next milestone" in text
    assert _CRITICAL_EXCEPTION in text


@pytest.mark.parametrize("phase", RO.ORDER_PHASES)
def test_standing_rulings_empty_and_unreadable_states_are_explicit_lines(phase):
    empty = _render(phase, True)
    assert "No standing rulings are recorded for this session." in empty
    assert _CRITICAL_EXCEPTION not in empty
    unreadable = _render(phase, True, standing_rulings=[],
                         standing_rulings_read_failure="rulings-log-malformed: rulingsLog must be a list")
    assert ("Standing rulings could not be read: rulings-log-malformed: "
            "rulingsLog must be a list.") in unreadable
    context_less = {k: v for k, v in _context(phase, True).items()
                    if k not in ("standing_rulings", "standing_rulings_read_failure")}
    text, reason = RO.render_order(phase, "seat", context_less)
    assert reason is None, reason
    assert "Standing rulings could not be read: not supplied to the renderer." in text


def test_standing_rulings_for_orders_reads_only_the_latest_out_of_scope_rows():
    state = {"rulingsLog": [
        {"findingKey": "k1", "ruling": "out-of-scope", "reason": "first", "id": "a"},
        {"findingKey": "k2", "ruling": "guidance", "reason": "fix it", "id": "b"},
        {"findingKey": "k3", "ruling": "out-of-scope", "reason": "later lifted", "id": "c"},
        {"findingKey": "k3", "ruling": "guidance", "reason": "now fix", "id": "c"},
    ]}
    assert RD._standing_rulings_for_orders(state) == (
        [{"findingKey": "k1", "reason": "first"}], None)
    assert RD._standing_rulings_for_orders({}) == ([], None)
    rows, fault = RD._standing_rulings_for_orders({"rulingsLog": "nope"})
    assert rows == [] and fault.startswith(RD.RULINGS_LOG_MALFORMED)


def test_ruled_finding_reaches_every_phase_and_is_not_reraised_as_new(tmp_path):
    session_dir, _g, _h, row_a, row_b = RUL._pending_apply_fixes_two_findings(tmp_path)
    id_b = row_b.get("id") or RD._fix_batch_row_key(row_b)
    key_b = RD._fix_batch_row_key(row_b)
    path = RUL._write_ruling_file(tmp_path / "r.json", [
        {"id": id_b, "ruling": "out-of-scope", "reason": "belongs to the next milestone",
         "followUp": RUL._follow_up()}])
    assert RUL._rule(session_dir, path)["ok"]
    state = RUL._state(session_dir)

    # (a) the driver's rows reach the order of EVERY phase ...
    rows, fault = RD._standing_rulings_for_orders(state)
    assert fault is None
    assert rows == [{"findingKey": key_b, "reason": "belongs to the next milestone"}]
    for phase in RO.ORDER_PHASES:
        for host_seat in (True, False):
            text = _render(phase, host_seat, standing_rulings=rows)
            assert "- %s: out of scope — belongs to the next milestone" % key_b in text, phase
    # ... and the pending `apply-fixes` step makes no order: its batch file leaves the ruled-out row out
    assert key_b not in RUL._apply_fixes_text(session_dir)

    # (b) a later round's finding with the same identity is dispositioned out of scope and stays
    # out of the fix batch
    later = dict(row_b)
    later["severity"] = "Minor"
    state["round"] = state["round"] + 1
    RD._stage_findings(state, [later])
    ledger = state.get(session_contract.DISPOSITION_LEDGER_KEY) or []
    entry = next(e for e in ledger if RD._finding_identity_key(e) == key_b)
    assert entry.get("disposition") == "out-of-scope"
    filtered, ffault = RD._filter_excluded_discharged_fixes(state, [later])
    assert ffault is None
    assert filtered == []

    # (c) a later Critical finding with the same identity is NOT dispositioned out of scope
    crit = dict(row_b)
    crit["severity"] = "Critical"
    state2 = RUL._state(session_dir)
    state2["round"] = state2["round"] + 1
    RD._stage_findings(state2, [crit])
    ledger2 = state2.get(session_contract.DISPOSITION_LEDGER_KEY) or []
    entry2 = next(e for e in ledger2 if RD._finding_identity_key(e) == key_b)
    assert entry2.get("disposition") != "out-of-scope"
    filtered2, ffault2 = RD._filter_excluded_discharged_fixes(state2, [crit])
    assert ffault2 is None
    assert len(filtered2) == 1


# --- B1: the panel follows the seeded seat map's roster -----------------------------------------

def test_panel_dimensions_follow_the_seeded_seat_map_roster_in_dimensions_order():
    # axis: the roster-derived default dimensions (neutralize back to all five) — see bite-proof
    # record wo_b_1797_seat_orders
    # "grounding-seat" is a stale name an older persisted map may still carry: read as an unknown seat
    seat_map = {"roster": ["test-role", "grounding-seat", "code-reviewer", "unknown-seat"],
                "laneBasis": {"floor": None}}
    cfg = RD._default_config({"seatMap": seat_map})
    assert cfg["dimensions"] == ["code-reviewer", "test-role"]
    state = RD.new_state({"seatMap": seat_map})
    assert RA.roster_for(RD.P_PANEL, state, state["config"]) == (["code-reviewer", "test-role"], None)
    full = {"roster": ["architecture-reviewer", "code-reviewer", "security-reviewer", "test-role",
                       "premortem-reviewer", "grounding-seat"]}
    assert RD._default_config({"seatMap": full})["dimensions"] == list(RD.DIMENSIONS)


@pytest.mark.parametrize("seat_map", [
    None, "a-string", ["code-reviewer"], {}, {"roster": None}, {"roster": "code-reviewer"},
    {"roster": []}, {"roster": ["code-reviewer", 7]}, {"roster": ["grounding-seat"]},
    {"roster": ["unknown-seat"]},
], ids=lambda m: repr(m)[:40])
def test_unreadable_roster_keeps_the_five_default_dimensions(seat_map):
    assert RD._default_config({"seatMap": seat_map})["dimensions"] == list(RD.DIMENSIONS)


@pytest.mark.parametrize("basis", [None, {}, {"floor": "full"}, "unreadable"])
def test_a_reduced_roster_without_a_no_floor_basis_keeps_the_five_dimensions(basis):
    # axis: the roster is validated against its lane basis before it reduces the lenses — see bite-proof record wo_a_1797_roster
    sm = {"roster": ["code-reviewer", "test-role", "grounding-seat"], "laneBasis": basis}
    assert RD._default_config({"seatMap": sm})["dimensions"] == list(RD.DIMENSIONS)


def test_explicit_dimensions_beat_the_roster():
    cfg = RD._default_config({"seatMap": {"roster": ["code-reviewer"]},
                              "dimensions": ["security-reviewer"]})
    assert cfg["dimensions"] == ["security-reviewer"]


# --- the lane basis is re-evaluated at each new reviewed head ----------------------------------

_RISKY_DIFF = ("diff --git a/src/payments/charge.py b/src/payments/charge.py\n"
               "--- a/src/payments/charge.py\n+++ b/src/payments/charge.py\n@@ -1 +1 @@\n-old\n+new\n")


def _reduced_state(tmp_path):
    state = RD.new_state({"repoRoot": str(tmp_path),
                          "seatMap": {"roster": list(SM.BASE_ROSTER), "laneBasis": {"floor": None}}})
    # No diff was seeded, so the first-panel lane recheck halted the session at creation; these tests
    # exercise the LATER heads from a session that is still running, so put it back at the first panel.
    state.update({"terminal": None, "certification": None, "decisions": [], "step": RD.P_PANEL})
    return state


def _assert_halted_lane_expanded(state):
    assert state["terminal"] == "halted"
    assert state["step"] == RD.P_TERMINAL
    assert state["terminal"] != "converged"
    assert state["decisions"][-1]["kind"] == "lane-expanded-recompose"
    assert "fresh" in state["decisions"][-1]["detail"] or "freshly" in state["certification"]["reason"]
    assert state["certification"]["shape"] is None
    nxt = RD._advance(state, state["config"])
    assert nxt["action"] == RD.P_TERMINAL and nxt["payload"]["verdict"] == "halted"


@pytest.mark.parametrize("diff", [_RISKY_DIFF, "not a git diff", ""])
def test_a_head_the_lane_call_cannot_clear_halts_lane_expanded_recompose(tmp_path, diff):
    # axis: a reduced session reaching a risky or unreadable head halts, never recomposes — see bite-proof record wo_a_1797_roster
    state = _reduced_state(tmp_path)
    assert state["config"]["dimensions"] == ["code-reviewer", "test-role"]
    state["round"] = 2
    state["headDiff"] = diff
    RD._enter_delta_round(state, state["config"])
    _assert_halted_lane_expanded(state)
    assert state["config"]["dimensions"] == ["code-reviewer", "test-role"]
    assert "roundKind" not in state["rounds"].get("2", {})


def test_an_unreadable_head_diff_halts_lane_expanded_recompose(tmp_path):
    state = _reduced_state(tmp_path)
    state["round"] = 2
    state["headDiff"] = None
    assert RD._reevaluate_lane_dimensions(state, state["config"], None) is True
    _assert_halted_lane_expanded(state)


def test_a_halted_session_dispatches_no_further_phase(tmp_path):
    state = _reduced_state(tmp_path)
    state["round"] = 2
    state["headDiff"] = _RISKY_DIFF
    RD._enter_delta_round(state, state["config"])
    _assert_halted_lane_expanded(state)
    assert state.get("step") != RD.P_AUDITS and state.get("step") != RD.P_SCOPED


_PAYMENTS_AREA = {"name": "Payments", "covers": ["src/payments/*"],
                  "why": "Charges customers.", "undo": "Hard: a charge needs a refund."}
_DOCS_DIFF = ("diff --git a/docs/readme.md b/docs/readme.md\n"
              "--- a/docs/readme.md\n+++ b/docs/readme.md\n@@ -1 +1 @@\n-old\n+new\n")
# The round's fix batch: a fix surface is only known from a batch that names the fixed findings.
_DOCS_FIXED_FINDING = {"file": "docs/readme.md", "line": 1, "title": "stale wording",
                       "severity": "Important"}


def _calibrated_reduced_state(tmp_path, monkeypatch):
    """A reduced session over a real repo whose core.md declares a ``src/payments/*`` risk area; the
    real ``lane_call.call`` reads it (no stub)."""
    import core_md
    repo = str(tmp_path / "repo")
    store = str(tmp_path / "store")
    os.makedirs(repo)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    core_md.write(repo, {"verifyCommand": "npm test", "stackTags": ["node"],
                         "threatModel": "single-user", "patterns": "- x: a.ts:1"},
                  "confirmed", root=store, now="2026-06-26")
    res = core_md.write_project_config_item(repo, core_md.RISK_AREAS_KEY, [_PAYMENTS_AREA], root=store)
    assert res["action"] == "written"
    import lane_call
    real_call = lane_call.call  # the real floor, pointed at the temp store; paths pass through untouched
    monkeypatch.setattr(lane_call, "call", lambda cwd, paths, proposed=None, root=None:
                        real_call(cwd, paths, proposed=proposed, root=store))
    return RD.new_state({"repoRoot": repo, "diff": _DOCS_DIFF,
                         "seatMap": {"roster": list(SM.BASE_ROSTER), "laneBasis": {"floor": None}}})


def _delta_state_after_round_one(tmp_path, monkeypatch, head_diff):
    """A calibrated reduced session whose round-1 diff is clean (the lane call clears it, so the
    session proceeds reduced) and is then put at a delta entry whose only unreviewed change is
    ``head_diff``'s: the baseline never names the risk area, so a halt is the new head's doing."""
    state = _calibrated_reduced_state(tmp_path, monkeypatch)
    assert not state.get("terminal")
    assert state["config"]["dimensions"] == ["code-reviewer", "test-role"]
    state["round"] = 2
    state["deltaBaseline"] = {"round": 2, "diff": _DOCS_DIFF}
    state["headDiff"] = head_diff
    state["fixBatch"] = [dict(_DOCS_FIXED_FINDING)]
    return state


def test_a_delta_round_after_a_risky_head_cannot_reach_converged(tmp_path, monkeypatch):
    # v6/v4: the halt is attributable to the NEW head — the round-1 baseline is clean
    state = _delta_state_after_round_one(tmp_path, monkeypatch, _DOCS_DIFF + _RISKY_DIFF)
    assert state.get("terminal") is None and state["step"] == RD.P_PANEL
    RD._enter_delta_round(state, state["config"])
    _assert_halted_lane_expanded(state)
    assert state.get("step") != RD.P_AUDITS and state.get("step") != RD.P_SCOPED


def test_a_delta_round_after_a_docs_only_head_is_not_halted(tmp_path, monkeypatch):
    head = _DOCS_DIFF + _DOCS_DIFF.replace("readme", "guide")
    state = _delta_state_after_round_one(tmp_path, monkeypatch, head)
    RD._enter_delta_round(state, state["config"], panel_diff_seam=lambda *_: (head, None),
                          panel_head="a" * 40)
    assert state.get("terminal") is None
    assert state["config"]["dimensions"] == ["code-reviewer", "test-role"]


def test_the_head_change_decision_depends_on_the_paths_the_head_changed(tmp_path, monkeypatch):
    # axis: the lane call is asked about the paths the head diff names — a mutant substituting a fixed
    # path passes only one of these two assertions
    state = _calibrated_reduced_state(tmp_path, monkeypatch)
    assert state["config"]["dimensions"] == ["code-reviewer", "test-role"]
    # a docs-only head touches no risk area: the reduced session continues
    assert RD._reevaluate_lane_dimensions(state, state["config"], _DOCS_DIFF) is False
    assert not state.get("terminal")
    # a payments head touches the declared risk area: the session halts
    assert RD._reevaluate_lane_dimensions(state, state["config"], _RISKY_DIFF) is True
    _assert_halted_lane_expanded(state)


def test_the_delta_round_entry_depends_on_the_paths_the_head_changed(tmp_path, monkeypatch):
    # the head the delta round is entered on is the one the lane call is asked about: a clean head
    # continues the reduced session, a risky one halts it
    clean = _calibrated_reduced_state(tmp_path, monkeypatch)
    clean.update({"round": 2, "deltaBaseline": {"round": 2, "diff": _DOCS_DIFF},
                  "headDiff": _DOCS_DIFF + _DOCS_DIFF.replace("readme", "guide"),
                  "fixBatch": [dict(_DOCS_FIXED_FINDING)]})
    RD._enter_delta_round(clean, clean["config"])
    assert not clean.get("terminal")
    assert clean["config"]["dimensions"] == ["code-reviewer", "test-role"]
    risky = RD.new_state({"repoRoot": clean["config"]["repoRoot"], "diff": _DOCS_DIFF,
                         "seatMap": clean["config"]["seatMap"]})
    risky.update({"round": 2, "deltaBaseline": {"round": 2, "diff": _DOCS_DIFF},
                  "headDiff": _RISKY_DIFF, "fixBatch": [dict(_DOCS_FIXED_FINDING)]})
    RD._enter_delta_round(risky, risky["config"])
    _assert_halted_lane_expanded(risky)


def test_the_unknown_surface_entry_hands_back_whatever_the_head_would_have_changed(tmp_path, monkeypatch):
    # an unknown fix surface is never re-derived and never put to the lane call: the PR is handed back
    # with its findings open, clean head or risky, and no panel or scoped round is entered
    clean = _calibrated_reduced_state(tmp_path, monkeypatch)
    risky = RD.new_state({"repoRoot": clean["config"]["repoRoot"], "diff": _DOCS_DIFF,
                         "seatMap": clean["config"]["seatMap"]})
    for state, head in ((clean, _DOCS_DIFF), (risky, _RISKY_DIFF)):
        state["round"] = 2
        state["_headDiffUnknown"] = True
        state["headDiff"] = head
        RD._enter_delta_round(state, state["config"], panel_diff_seam=lambda *_: (head, None),
                              panel_head="a" * 40)
        assert state["terminal"] == "handed-back" and state["step"] == RD.P_TERMINAL
        assert state["decisions"][-1]["kind"] == "fix-surface-unknown"
        assert state["certification"]["shape"] is None
        assert all(d["kind"] != RD.LANE_EXPANDED_RECOMPOSE for d in state["decisions"])
        assert "roundKind" not in state["rounds"].get("2", {})
        assert state["config"]["dimensions"] == ["code-reviewer", "test-role"]


# --- the first panel is dispatched only after the lane basis is re-asked over the round-1 diff ----

def test_a_reduced_seat_map_over_a_risky_round_one_diff_halts_before_any_panel_order(tmp_path, monkeypatch):
    # axis: the seeded map's lane basis is rechecked against the round-1 diff before the first panel — see bite-proof record wo_a_1797_roster
    clean = _calibrated_reduced_state(tmp_path, monkeypatch)
    repo = clean["config"]["repoRoot"]
    risky = RD.new_state({"repoRoot": repo, "diff": _RISKY_DIFF, "seatMap": clean["config"]["seatMap"]})
    _assert_halted_lane_expanded(risky)
    assert RD._advance(risky, risky["config"])["action"] == RD.P_TERMINAL


def test_a_reduced_seat_map_over_a_clean_round_one_diff_proceeds_with_the_reduced_dimensions(tmp_path, monkeypatch):
    state = _calibrated_reduced_state(tmp_path, monkeypatch)
    assert not state.get("terminal")
    nxt = RD._advance(state, state["config"])
    assert nxt["action"] == RD.P_PANEL
    assert nxt["payload"]["dimensions"] == ["code-reviewer", "test-role"]


def test_a_reduced_seat_map_with_no_round_one_diff_halts_rather_than_assuming_clean(tmp_path):
    state = RD.new_state({"repoRoot": str(tmp_path),
                          "seatMap": {"roster": list(SM.BASE_ROSTER), "laneBasis": {"floor": None}}})
    _assert_halted_lane_expanded(state)


def test_the_lane_expanded_decision_token_is_owned_by_decision_kinds():
    import decision_kinds
    assert RD.LANE_EXPANDED_RECOMPOSE is decision_kinds.LANE_EXPANDED_RECOMPOSE
    assert decision_kinds.LANE_EXPANDED_RECOMPOSE in decision_kinds.DECISION_KINDS
    assert decision_kinds.map_terminal_cause("halted", decision_kinds.LANE_EXPANDED_RECOMPOSE) == {"kind": "loop", "reason": "detector"}
