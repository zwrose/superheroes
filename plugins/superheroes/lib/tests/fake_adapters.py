"""The one adapter double for driver-layer tests.

Shared by the test modules that stub `round_adapters` through `sys.modules`, so there is a single
copy to keep in step with the real seam. `test_driver_adapter_contract.py` checks that it has every
seam member. Deliberately not named `test_*`, so pytest never collects it.
"""
import os
import sys

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_driver as RD  # noqa: E402
import round_records as RR  # noqa: E402


class FakeAdapters(object):
    """A stand-in for the parallel `round_adapters` module, exactly at the pinned interface."""

    ADAPTER_PHASES = (RD.P_PANEL, RD.P_VERIFIERS, RD.P_SYNTHESIS, RD.P_SEAMS, RD.P_AUDITS,
                      RD.P_SCOPED, RD.P_VERIFY, RD.P_APPLY_FIXES)

    def __init__(self):
        self.rosters = {RD.P_PANEL: list(RD.DIMENSIONS),
                        RD.P_VERIFIERS: [],
                        RD.P_SYNTHESIS: ["synthesis"],
                        RD.P_APPLY_FIXES: ["apply-fixes"],
                        RD.P_VERIFY: ["verify"]}
        self.roster_reasons = {}
        self.faults = {}
        self.assemble_reason = None
        self.assembled = []
        self.policies = {}

    def roster_for(self, phase, state, config):
        if phase in self.roster_reasons:
            return [], self.roster_reasons[phase]
        return list(self.rosters.get(phase, [])), None

    def payload_fault(self, phase, payload, seat_key, record_boundary=False):
        return self.faults.get(seat_key)

    def missing_policy(self, phase):
        return self.policies.get(phase, "seat-status")

    def is_orchestrator_fulfilled(self, phase):
        return phase in (RD.P_VERIFY, RD.P_APPLY_FIXES)

    def orchestrator_payload_fault(self, phase, payload):
        if phase == RD.P_VERIFY:
            return RD.verify_result_fault(payload)
        if phase == RD.P_APPLY_FIXES:
            return RD.payload_contracts.payload_fault(phase, payload, "apply-fixes")
        return "orchestrator-payload-unknown-phase:%s" % phase

    def sweep_seat_key(self, sweep_id, part):
        return "searcher:%s:%d" % (sweep_id, part)

    def assemble(self, phase, envelopes, state, config, dispatch_manifest=None,
                 session_dir=None, orders_manifest=None):
        self.assembled.append({"phase": phase, "envelopes": envelopes,
                               "dispatch_manifest": dispatch_manifest,
                               "session_dir": session_dir})
        if self.assemble_reason is not None:
            return None, self.assemble_reason
        if phase == RD.P_PANEL:
            # `envelopes` is a LIST, keyed by each envelope's own `seat` — the real
            # `round_adapters.assemble` contract (`_index_envelopes` refuses anything else with
            # `envelopes-not-a-list`). This stub consumed a {seat: envelope} MAPPING while the
            # driver handed one over, and the agreement of the two shapes is precisely what a
            # stubbed seam cannot check: see test_round_driver_integration.py.
            seats = {}
            for env in (envelopes or []):
                if not isinstance(env, dict):
                    continue
                seat = env.get("seat")
                if env.get("schema") == RR.SEAT_MISSING_SCHEMA:
                    seats[seat] = {"findings": [], "missing": True}
                else:
                    seats[seat] = env.get("payload") or {"findings": []}
            return {"seats": seats}, None
        if phase == RD.P_VERIFIERS:
            verdicts = []
            seat_vendors = {}
            for env in (envelopes or []):
                if not isinstance(env, dict):
                    continue
                if env.get("schema") == RR.SEAT_MISSING_SCHEMA:
                    continue
                payload = env.get("payload")
                if not isinstance(payload, dict):
                    continue
                source = (env.get("executionEvidence") or {}).get("source")
                for verdict in payload.get("verdicts") or []:
                    if isinstance(verdict, dict):
                        verdicts.append(dict(verdict))
                        if isinstance(verdict.get("id"), str):
                            seat_vendors[verdict["id"]] = (
                                source if source in ("claude", "codex", "cursor") else "")
            artifact = {"verdicts": verdicts, "verifierSeatVendors": seat_vendors}
            # like the real adapter (per seat): the executed vendor is the envelope's execution evidence
            sources = {(env.get("executionEvidence") or {}).get("source") for env in (envelopes or [])
                       if isinstance(env, dict) and env.get("schema") != RR.SEAT_MISSING_SCHEMA}
            if len(sources) == 1 and next(iter(sources)) in ("claude", "codex", "cursor"):
                artifact["verifierVendor"] = next(iter(sources))
            return artifact, None
        if phase == RD.P_SYNTHESIS:
            return {"grouping": None}, None
        if phase == RD.P_VERIFY:
            for env in (envelopes or []):
                if isinstance(env, dict) and env.get("schema") != RR.SEAT_MISSING_SCHEMA:
                    return dict(env.get("payload") or {"result": "pass"}), None
            return None, "missing-verify"
        return {}, None
