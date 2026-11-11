"""#2450 — an order a review seat receives states exactly one result contract, and it is the contract
the dispatch reads.

A stdout-channel order in every phase except sweep (a host reply phase) is dispatched through
`dispatch-review`, where the runner appends its native schema contract; the order itself therefore
carries no `## Payload contract` block and defers to the runner's. A host-seat (file-channel) order
keeps its `## Payload contract` block — that is its one contract. And no seat-facing text tells a seat
to omit a field the result schema requires.

Structure only (rubric/review-discipline.md § One home per rule, and the pin rule): this file counts
headings, compares against production constants, and reads the schema. It pins no doctrine sentence.
"""
import os
import re

import pytest

import engine_result_channel as ERC
import order_contract
import round_orders as RO
import round_phases as RP

import test_round_orders as TRO
from test_engine_dispatch import (
    ED, FakeRunner, _codex_seat, _fake_build_view, _repo, _review_opened_record, _valid_prompt,
)
import test_round_driver_order_channel as TROC

_TESTS = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(_TESTS))
_PAYLOAD_HEADING = order_contract.PAYLOAD_CONTRACT_HEADING
_CONTRACT_LINE_PREFIX = "Review result contract"

# phase -> (placeholder builder, result kind a codex seat is dispatched with)
_NATIVE_KIND_PHASES = (
    (RP.P_PANEL, TRO._panel_placeholders, "findings"),
    (RP.P_VERIFIERS, TRO._verifier_placeholders, "verdicts"),
    (RP.P_SYNTHESIS, TRO._synthesis_placeholders, "grouping"),
    (RP.P_AUDITS, TRO._audits_placeholders, "ruling"),
)

_PLACEHOLDERS_BY_PHASE = {
    RP.P_PANEL: TRO._panel_placeholders,
    RP.P_VERIFIERS: TRO._verifier_placeholders,
    RP.P_SYNTHESIS: TRO._synthesis_placeholders,
    RP.P_SEAMS: TRO._seams_placeholders,
    RP.P_SECOND_TEST: TRO._second_test_placeholders,
    RP.P_AUDITS: TRO._audits_placeholders,
    RP.P_SCOPED: TRO._scoped_placeholders,
    RP.P_SWEEP: TRO._sweep_placeholders,
}


def _codex_native_contract(kind):
    return ERC.review_result_contract_from_schema(
        ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW, kind),
        delivery=ERC.RESULT_DELIVERY_ARGV,
    )


def _findings_item_properties():
    """Property names of one finding member, read from the schema a codex review run declares."""
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW, "findings")
    findings = schema["properties"]["result"]["properties"]["findings"]
    return sorted(findings["items"]["properties"])


def _heading_count(text):
    return sum(1 for line in text.splitlines() if line.strip() == _PAYLOAD_HEADING)


def _omit_lines(text, properties):
    """Lines that name a findings-item property in backticks or quotes AND say `omit` (any inflection).

    Keyed on the property name being named in the same line as the omission: a line that uses
    "omits"/"omitting" about code (security-reviewer.md:83,85) or about a whole reply (dispatch-panel.md
    "do NOT silently omit it") names no findings-item property in backticks or quotes, so it does not
    trip. No line is exempted by hand.
    """
    named = re.compile(r"""[`"'](%s)[`"']""" % "|".join(re.escape(p) for p in properties))
    hits = []
    for number, line in enumerate(text.splitlines(), 1):
        if re.search(r"\bomit", line, re.IGNORECASE) and named.search(line):
            hits.append((number, line.strip()))
    return hits


def _render(phase, *, host_seat, channel):
    ctx = TRO._GOLDEN_CONTEXTS[phase]()
    ctx["host_seat"] = host_seat
    ctx["placeholders"] = _PLACEHOLDERS_BY_PHASE[phase](channel)
    text, reason = RO.render_order(phase, "seat", ctx)
    assert reason is None, reason
    return text


# --- (a) a real codex order, dispatched, carries exactly one contract --------------------------------


@pytest.mark.parametrize("phase,placeholders,kind", _NATIVE_KIND_PHASES, ids=[k for _p, _f, k in _NATIVE_KIND_PHASES])
def test_element_a_codex_fed_prompt_states_one_result_contract(tmp_path, phase, placeholders, kind):
    # axis: the prompt a codex seat is fed carries exactly one result contract (the native one), no
    # payload-contract block, the null-for-omitted line once, and no line telling it to omit a member
    ctx = TRO._base_context(host_seat=False, placeholders=placeholders("stdout"))
    order, reason = RO.render_order(phase, "seat", ctx)
    assert reason is None, reason
    run_dir = str(tmp_path / "run")
    ED.dispatch_review(
        seat=_codex_seat(),
        prompt_path=_valid_prompt(tmp_path, order),
        repo_root=_repo(tmp_path),
        run_engine=FakeRunner([]),
        build_view=_fake_build_view(tmp_path),
        expected_result_kind=kind,
        run_dir=run_dir,
        max_wait=0,
    )
    fed = _review_opened_record(run_dir)["fedPrompt"]
    native = _codex_native_contract(kind)
    headings = [ln for ln in fed.splitlines() if ln.startswith(_CONTRACT_LINE_PREFIX)]
    assert len(headings) == 1, headings
    assert native in fed
    assert fed.endswith(native)
    assert _PAYLOAD_HEADING not in fed
    assert fed.count(ERC.NATIVE_NULL_FOR_OMITTED_LINE) == 1
    assert _omit_lines(fed, _findings_item_properties()) == []


# --- (b) the files the order points the seat at tell it to omit no member --------------------------


def _seat_facing_files():
    files = [os.path.join(_PLUGIN_ROOT, "rubric", "review-base.md")]
    agents = os.path.join(_PLUGIN_ROOT, "agents")
    files.extend(
        os.path.join(agents, name) for name in sorted(os.listdir(agents))
        if name.endswith("-reviewer.md") or name == "test-role.md"
    )
    return files


def test_element_b_pointed_at_files_tell_no_seat_to_omit_a_member():
    # axis: no line of the rubric or a reviewer agent file names a findings-item property as the thing omitted
    files = _seat_facing_files()
    assert any(f.endswith("review-base.md") for f in files)
    assert any(f.endswith("test-role.md") for f in files)
    properties = _findings_item_properties()
    offenders = []
    for path in files:
        with open(path, encoding="utf-8") as fh:
            for number, line in _omit_lines(fh.read(), properties):
                offenders.append("%s:%s: %s" % (os.path.relpath(path, _PLUGIN_ROOT), number, line[:160]))
    assert offenders == []


# --- (c) the real driver emission ------------------------------------------------------------------


def test_element_c_driver_emission_codex_seat_defers_and_claude_host_seat_keeps_its_one_contract(tmp_path):
    # axis: the order the driver actually writes for a codex seat carries no payload contract and the
    # deferral; a claude host seat in the same emission keeps its one payload contract
    orders = TROC._emit(tmp_path, "mixed", TROC._mixed_seat_map())
    engine_order = orders[TROC.ENGINE_SEAT]
    assert _heading_count(engine_order) == 0
    assert RO.STDOUT_RESULT_DEFERRAL in engine_order
    host_order = orders[TROC.NATIVE_SEAT]
    assert _heading_count(host_order) == 1
    assert RO.STDOUT_RESULT_DEFERRAL not in host_order


# --- (d) healthy sibling at render level -----------------------------------------------------------


@pytest.mark.parametrize("phase", RO.ORDER_PHASES)
def test_element_d_render_contract_count_by_channel(phase):
    # axis: host-seat render = exactly one payload contract in every phase; stdout-channel render = none,
    # except sweep (out of scope, a host reply phase) which keeps exactly one
    host = _render(phase, host_seat=True, channel="file")
    assert _heading_count(host) == 1
    stdout = _render(phase, host_seat=False, channel="stdout")
    if phase == RP.P_SWEEP:
        assert _heading_count(stdout) == 1
    else:
        assert _heading_count(stdout) == 0
        assert RO.STDOUT_RESULT_DEFERRAL in stdout
