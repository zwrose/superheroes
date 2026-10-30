#!/usr/bin/env python3
"""The one-entrypoint review-loop round driver (#507).

CONTRACT. This module collapses the review-code auto-fix loop's per-round script choreography
(plan → dispatch → compile → verify → synthesis → gate → persist → fix → re-review) into ONE
deterministic entrypoint so the mandated path is the easiest path — ~6/24 corpus runs routed
AROUND the old scripts because the choreography was several separate invocations. It has two
layers over one core:

  - Layer 1 (`run_loop`): the ported control-flow of `review_panel_shell.js::reviewPanel` with
    every effectful step behind an injectable seam (`reviewer`, `synthesis`, `verifier`,
    `auditor`, `fix_step`, `fix_commits`, `fix_step_head`, `verify_runner`, `changed_subjects`, `panel_diff`, `io`). Same run-SHAPE, not the JS
    idioms. `changed_subjects` derives the fix's changed policy subjects from git (the reviewed vs
    head diff), NEVER the session's self-report (#157/#158) — the library default + the CLI path wire
    the real derivation; the eval harness injects a scripted replay. `panel_diff` derives the
    post-fix git head diff — the library default + the CLI path wire the real git helper; run_loop
    may inject a scripted replay.
  - Layer 2 (`next`/`submit` CLI): the state machine BETWEEN orchestrator dispatches — `next`
    emits the one action to run, `submit` folds its artifact and advances.

Nothing from the review reaches the owner mid-review: every phase is a `dispatch-*` phase,
`run-verify` or `terminal`. A tradeoff/product-choice blocker only the owner can settle is held out
of the fix batch (`_hold_owner_choice`) and handed back open (`handed-back` /
`owner-choice-open`) when the loop would otherwise converge over it; an audit stall that persists
after the one recovery attempt hands the PR back too (`fix-keeps-failing`), and so does a fix
surface the driver cannot work out (`fix-surface-unknown`). Only round 1 runs a full panel: every
later round runs the fix auditor over each fix and the scoped finder over the fixes' own diff, and
a converged review that needed fixes ends on a round's audit and scoped finder. `_hand_back` is the
one writer of the `handed-back` verdict.

Like its decider siblings (audits / delta_surface / verification): DETERMINISTIC, stdlib-only,
FAIL-CLOSED. Junk in → conservative out + disclosure; never certify on silence; a wrong
`discharged`, a receipt-missing seat, a lost independence, an unknown surface all fail toward
MORE review, a park, or a disclosed downgrade — never toward a silent clean. The judgments live
in the pure deciders this module imports (`audits`, `verification`, `circuit_breaker`,
`review_round_policy`, `delta_surface`, `model_registry`); the driver only SEQUENCES them and
RECORDS what happened, and every terminal writes the driver receipt (`validate_receipt` guards
its shape). The reviewer re-dispatch budget (`loop_plan_common.REDISPATCH_BUDGET` — the single
home) and receipt validation (`panel_tally._valid_final_receipt`, consumed bit-compatibly, never
modified) are reused, not re-implemented.
"""
import argparse
import copy
import difflib
import errno
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import traceback
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cli_contract  # noqa: E402
import audits  # noqa: E402
import break_it  # noqa: E402
import calibration_resolve  # noqa: E402
import core_md  # noqa: E402
import countable_lines  # noqa: E402
import circuit_breaker  # noqa: E402
import mode_registry  # noqa: E402
import decision_kinds  # noqa: E402
import delta_surface  # noqa: E402
import dispatch_outcome  # noqa: E402
import diff_scope  # noqa: E402
import engine_adapter  # noqa: E402
import finding_outcomes  # noqa: E402
import payload_contracts  # noqa: E402
import engine_pref  # noqa: E402
import loop_plan_common  # noqa: E402
import model_registry  # noqa: E402
import order_lint  # noqa: E402
import panel_tally  # noqa: E402
import payload_contracts  # noqa: E402
import review_base_guard  # noqa: E402
import review_diff_bytes  # noqa: E402
import review_loop_plan  # noqa: E402
import review_memory  # noqa: E402
import risk_areas  # noqa: E402
import review_round_policy  # noqa: E402
import review_seats  # noqa: E402
import pr_body_stage  # noqa: E402
import receipt_disclosures  # noqa: E402
import repeat_marks  # noqa: E402
import review_findings_schema  # noqa: E402
import round_commit  # noqa: E402
import round_orders  # noqa: E402
import round_records  # noqa: E402
import round_phases  # noqa: E402
import seat_map  # noqa: E402
import seat_map_receipts  # noqa: E402
import session_contract  # noqa: E402
import session_mode  # noqa: E402
import store_core  # noqa: E402
import verification  # noqa: E402
from finding_identity import finding_identity, finding_label, normalize_title  # noqa: E402

# --- constants (the DIMENSIONS/AGENT_SUFFIX home, moved off the retired code_loop_plan) --------
# The code leg is the FIVE shared reviewers. `grounding-reviewer` is spec-leg-only (doc
# provenance) — deliberately absent here; test_dispatch_tables pins the per-leg subset.
DIMENSIONS = round_phases.DIMENSIONS
AGENT_SUFFIX = review_seats.AGENT_SUFFIX
# The cross-cutting lenses always get the WHOLE diff even when a big diff is sharded per-lens —
# architecture and failure-mode reasoning is non-local, so a shard would blind them.
CROSS_CUTTING_LENSES = ("architecture-reviewer", "premortem-reviewer")
# Every lens seat's panel order names its agent file as a role brief — a seat on another vendor
# never sees its agent's system prompt, so the order is where the brief reaches it. Derived from
# AGENT_SUFFIX so a lens added there carries its brief without a second list to forget.
ROLE_BRIEF_SEATS = frozenset(AGENT_SUFFIX)

DEEP = "reviewer-deep"
CHEAP = "reviewer"
# The reviewer re-dispatch budget rides through its single home (#350/#525): a receipt-missing /
# stale seat is re-dispatched at most this many times before it is recorded terminal `missing`
# with its findings carried as unverified. The code leg's read goes through the constant now.
REDISPATCH_BUDGET = loop_plan_common.REDISPATCH_BUDGET
# Fold-owned guidance record key inside judgmentDispositions entries.
GATE_GUIDANCE_RECORD_KEY = "userGuidance"
# The verifier's grade on a finding; only `_fold_verifiers` writes it (`_seed_ledger_entry` strips a seat's).
GRADE_FIELD = "grade"

GATE_GUIDANCE_ROW_BYTE_CAP = 2000
GATE_GUIDANCE_AGGREGATE_BYTE_CAP = 8000
# Bounds each header field so one oversized value cannot cost its entry a place under the
# 8000-byte aggregate cap. Kept loose (not tight to title length): a truncated title still
# matches by prefix, while a truncated shared title prefix would not match at all.
GATE_GUIDANCE_HEADER_FIELD_BYTE_CAP = 200
_GATE_GUIDANCE_NO_GUIDANCE = "No owner-gate guidance is attached to this batch."
_GATE_GUIDANCE_ROW_CARRIED_CHANNEL = "gateGuidanceRowCarried"
GATE_GUIDANCE_UNUSABLE_REFUSAL = "gate-guidance-unusable"
GATE_GUIDANCE_OVERSIZE = "gate-guidance-oversize"
GATE_GUIDANCE_AGGREGATE_OVERSIZE = "gate-guidance-aggregate-oversize"
RULING_GUIDANCE_OMITTED = "ruling-guidance-omitted"

# --- version spelling: pinned declaration block (BEGIN) ---
SCHEMA_VERSION = 2
STATE_FILE = session_contract.STATE_FILE
MIRROR_FILE = session_contract.MIRROR_FILE
MIRROR_SCHEMA = "loop-state-mirror/1"
JOURNAL_FILE = session_contract.JOURNAL_FILE
JOURNAL_FAULT_FILE = session_contract.JOURNAL_FAULT_FILE
RULE_CMD = session_contract.RULE_CMD
EXTRA_AUDIT_CMD = "extra-audit"
BREAK_IT_CHANGE_CMD = "break-it-change"
# The test role's original block content, kept on a finding when `break-it-change` first rewrites it.
REVIEWER_TEST_FIELD = "reviewerTest"
RULING_KINDS =frozenset(("out-of-scope", "guidance"))
RULING_FILE_UNREADABLE = "ruling-file-unreadable"
RULING_FILE_SHAPE = "ruling-file-shape"
RULING_PROVENANCE_MALFORMED = "ruling-provenance-malformed"
RULING_UNKNOWN_KIND = "ruling-unknown-kind"
RULING_TARGET_UNKNOWN = "ruling-target-unknown"
RULING_TARGET_AMBIGUOUS = "ruling-target-ambiguous"
RULING_REASON_MISSING = "ruling-reason-missing"
RULING_SESSION_TERMINAL = "ruling-session-terminal"
RULING_FOLLOW_UP_MALFORMED = "ruling-follow-up-malformed"
RULING_DECIDED_BY_MALFORMED = "ruling-decided-by-malformed"
RULING_GUIDANCE_OVERSIZE = "ruling-guidance-oversize"
RULING_CRITICAL_OUT_OF_SCOPE = "ruling-critical-out-of-scope"
RULINGS_LOG_MALFORMED = "rulings-log-malformed"
RECEIPT_FILE = "round-receipt.json"
RECEIPT_INTERIM_FILE = "round-receipt-interim.json"

# --- the #723 schema matrix -------------------------------------------------------------------
# `SCHEMA_VERSION` stays the version a v2 RECEIPT keys off (and the version an in-flight v2 state
# carries). NEW state is minted at `STATE_SCHEMA_VERSION`; `load_state` accepts every member of
# `SUPPORTED_STATE_VERSIONS`.
#
# THE HASH-PRESERVATION RULE. A loaded state's `schemaVersion` is NEVER mutated and NO default
# field for the current version is written into the dict on load: `state_hash` hashes the WHOLE
# canonical state, so injecting a key on load would change the hash of an already-emitted
# `expectedStateHash` and every in-flight session's next `submit` would fail its echo fence.
# Version-gated fields are therefore read with `.get()` at their read sites, never seeded on load.
#
# Rollback residual (#1185): this bump protects state minted from here on; state already persisted
# at `schemaVersion: 3` by a post-#681 build carries the new shape under the old number and a
# rolled-back v3 reader will still accept it. A scoped migration is technically POSSIBLE — `advance`
# recomputes `state_hash`, so re-versioning that population would not break the echo fence; the
# hash-preservation rule above binds the hand-submit path, which this population is already refused.
# It is declined as not worth the machinery (owner ruling 2026-08-27): a persisted `schemaVersion: 3`
# is SHAPE-AMBIGUOUS after #681 — a genuine pre-#681 v3 state and a post-#681 state carrying the v4
# shape under the old number are indistinguishable on disk — so a migration would have to guess which
# one it is holding. The residual is disclosed rather than fixed.
STATE_SCHEMA_VERSION = 5
SUPPORTED_STATE_VERSIONS = (2, 3, 4, 5)

# The receipt VERSION derives from the STATE's version: a v2 state terminates to
# `receipt-certified/2` (today's shape, byte-for-byte unchanged — no key added), a v3 state to
# `receipt-certified/3`, a v4 state to `receipt-certified/4`. `attest` writes `receipt-attested/1`,
# which carries an `attestation` block
# and NO `certification`/`certificationShape` — so the certified and attested shapes are
# structurally un-confusable and `validate_receipt` dispatches on that.
RECEIPT_CERTIFIED_SCHEMA = "receipt-certified/%d"
RECEIPT_ATTESTED_SCHEMA = "receipt-attested/1"
RECEIPT_INTERIM_SCHEMA = "receipt-interim/1"
# --- version spelling: pinned declaration block (END) ---
# The session generation. `new_state` stamps it into state it MINTS and nothing else ever writes it:
# a loaded state is never given the key (the hash-preservation rule above). A saved state whose
# `sessionGeneration` is absent or is not exactly this integer was started by an earlier plugin
# version; while it is unfinished, `_upgrade_gate` refuses every command on it, except a state of a
# generation in `CONTINUABLE_EARLIER_GENERATIONS`: that session finishes under the rules it started
# with and keeps its stamp, so its hash never moves.
SESSION_GENERATION = 7
# The earlier generations whose unfinished sessions are continued, not refused. Each keeps the round
# cap it recorded at its start (`_round_cap` reads the stored `maxRounds`), has no ceiling above it
# and no owner gate: one waiting at a gate this version no longer has is handed back
# (`_finish_retired_gate_step`).
CONTINUABLE_EARLIER_GENERATIONS = (6,)
SESSION_FROM_EARLIER_VERSION = "session-from-earlier-version"
RESTART_FRESH_SESSION = "fresh-session"
UPGRADE_RESTART_MARKER_FILE = "restarted-on-upgrade.json"
UPGRADE_RESTART_MARKER_SCHEMA = "restarted-on-upgrade/1"
UPGRADE_REFUSAL_DETAIL = ("this session was started by an earlier plugin version and is not "
                          "continued; start the review again in a fresh session directory")
RECEIPT_FORM_CERTIFIED = "certified"
RECEIPT_FORM_ATTESTED = "attested"
RECEIPT_FORM_INTERIM = "interim"
RECEIPT_KEY_REQUIRED = "required"
RECEIPT_KEY_OPTIONAL = "optional"
_ALL_RECEIPT_FORMS = (RECEIPT_FORM_CERTIFIED, RECEIPT_FORM_ATTESTED, RECEIPT_FORM_INTERIM)
# ONE declaration: key → {form: required|optional}. A form absent from a key's mapping is FORBIDDEN
# for that form. Required, optional, and forbidden sets per form DERIVE from here — no second list.
RECEIPT_KEY_FORMS = {
    "rounds": {RECEIPT_FORM_CERTIFIED: RECEIPT_KEY_REQUIRED,
               RECEIPT_FORM_ATTESTED: RECEIPT_KEY_REQUIRED,
               RECEIPT_FORM_INTERIM: RECEIPT_KEY_REQUIRED},
    "findings": {RECEIPT_FORM_CERTIFIED: RECEIPT_KEY_REQUIRED,
                 RECEIPT_FORM_ATTESTED: RECEIPT_KEY_REQUIRED,
                 RECEIPT_FORM_INTERIM: RECEIPT_KEY_REQUIRED},
    "decisions": {RECEIPT_FORM_CERTIFIED: RECEIPT_KEY_REQUIRED,
                  RECEIPT_FORM_ATTESTED: RECEIPT_KEY_REQUIRED,
                  RECEIPT_FORM_INTERIM: RECEIPT_KEY_REQUIRED},
    "seatMap": {RECEIPT_FORM_CERTIFIED: RECEIPT_KEY_REQUIRED,
                RECEIPT_FORM_ATTESTED: RECEIPT_KEY_REQUIRED,
                RECEIPT_FORM_INTERIM: RECEIPT_KEY_REQUIRED},
    "scriptRan": {RECEIPT_FORM_CERTIFIED: RECEIPT_KEY_REQUIRED,
                  RECEIPT_FORM_ATTESTED: RECEIPT_KEY_REQUIRED,
                  RECEIPT_FORM_INTERIM: RECEIPT_KEY_REQUIRED},
    "degraded": {RECEIPT_FORM_CERTIFIED: RECEIPT_KEY_REQUIRED,
                 RECEIPT_FORM_ATTESTED: RECEIPT_KEY_REQUIRED,
                 RECEIPT_FORM_INTERIM: RECEIPT_KEY_REQUIRED},
    "skippedBlockers": {RECEIPT_FORM_CERTIFIED: RECEIPT_KEY_REQUIRED,
                        RECEIPT_FORM_ATTESTED: RECEIPT_KEY_REQUIRED,
                        RECEIPT_FORM_INTERIM: RECEIPT_KEY_REQUIRED},
    "schemaVersion": {RECEIPT_FORM_CERTIFIED: RECEIPT_KEY_REQUIRED},
    "certification": {RECEIPT_FORM_CERTIFIED: RECEIPT_KEY_REQUIRED},
    "certificationShape": {RECEIPT_FORM_CERTIFIED: RECEIPT_KEY_REQUIRED},
    "verdict": {RECEIPT_FORM_CERTIFIED: RECEIPT_KEY_REQUIRED,
                RECEIPT_FORM_ATTESTED: RECEIPT_KEY_REQUIRED},
    "schema": {RECEIPT_FORM_CERTIFIED: RECEIPT_KEY_OPTIONAL,
               RECEIPT_FORM_ATTESTED: RECEIPT_KEY_REQUIRED,
               RECEIPT_FORM_INTERIM: RECEIPT_KEY_REQUIRED},
    "attestation": {RECEIPT_FORM_ATTESTED: RECEIPT_KEY_REQUIRED},
    "artifacts": {RECEIPT_FORM_ATTESTED: RECEIPT_KEY_REQUIRED},
    "roster": {RECEIPT_FORM_ATTESTED: RECEIPT_KEY_REQUIRED},
    "stop": {RECEIPT_FORM_INTERIM: RECEIPT_KEY_REQUIRED},
    "base": {RECEIPT_FORM_CERTIFIED: RECEIPT_KEY_OPTIONAL,
             RECEIPT_FORM_ATTESTED: RECEIPT_KEY_OPTIONAL,
             RECEIPT_FORM_INTERIM: RECEIPT_KEY_OPTIONAL},
    "policyApplied": {RECEIPT_FORM_CERTIFIED: RECEIPT_KEY_OPTIONAL,
                      RECEIPT_FORM_ATTESTED: RECEIPT_KEY_OPTIONAL,
                      RECEIPT_FORM_INTERIM: RECEIPT_KEY_OPTIONAL},
    "baseGuard": {RECEIPT_FORM_CERTIFIED: RECEIPT_KEY_OPTIONAL,
                  RECEIPT_FORM_ATTESTED: RECEIPT_KEY_OPTIONAL,
                  RECEIPT_FORM_INTERIM: RECEIPT_KEY_OPTIONAL},
}


def _receipt_required_keys(form):
    return tuple(key for key, forms in RECEIPT_KEY_FORMS.items()
                 if forms.get(form) == RECEIPT_KEY_REQUIRED)


def _receipt_optional_keys(form):
    return tuple(key for key, forms in RECEIPT_KEY_FORMS.items()
                 if forms.get(form) == RECEIPT_KEY_OPTIONAL)


def _receipt_forbidden_keys(form):
    return tuple(key for key, forms in RECEIPT_KEY_FORMS.items()
                 if form not in forms)


# Per-round receipt entry keys gated by minimum certified version and non-certified schemas.
# Each gated key maps to:
#   min_certified_version — certified receipts at this state version or later carry the key
#   non_certified_schemas — attested/interim receipt schemas that also carry the key
ROUND_ENTRY_KEY_FORMS = receipt_disclosures.ROUND_ENTRY_KEY_FORMS
_round_entry_key_declared = receipt_disclosures.round_entry_key_declared
_round_entry_key_allowed = receipt_disclosures.round_entry_key_allowed
_declared_disclosures = receipt_disclosures.declared_disclosures
_receipt_round_disclosures = receipt_disclosures.receipt_round_disclosures
_normalize_adapter_provenance = receipt_disclosures.normalize_adapter_provenance
CARRIED_DISCLOSURE_CHANNELS = receipt_disclosures.CARRIED_DISCLOSURE_CHANNELS
_dict_list = receipt_disclosures.dict_list
_bool_value = receipt_disclosures.bool_value
build_degraded_prose = receipt_disclosures.build_degraded_prose
degraded = receipt_disclosures.degraded
base_degraded = receipt_disclosures.base_degraded
author_family = receipt_disclosures.author_family
maker_author_family = receipt_disclosures.maker_author_family
same_family_seats = receipt_disclosures.same_family_seats
same_family_seats_for_receipt = receipt_disclosures.same_family_seats_for_receipt
same_family_degraded = receipt_disclosures.same_family_degraded
seat_map_violations = receipt_disclosures.seat_map_violations
seat_map_violated = receipt_disclosures.seat_map_violated
seat_map_violation_breach_prose = receipt_disclosures.seat_map_violation_breach_prose
seat_pin_excused_seats = receipt_disclosures.seat_pin_excused_seats
seat_map_unjudgeable = receipt_disclosures.seat_map_unjudgeable
declared_disclosures = receipt_disclosures.declared_disclosures
round_entry_key_declared = receipt_disclosures.round_entry_key_declared
round_entry_key_allowed = receipt_disclosures.round_entry_key_allowed
receipt_round_disclosures = receipt_disclosures.receipt_round_disclosures
normalize_adapter_provenance = receipt_disclosures.normalize_adapter_provenance
live_vendors = receipt_disclosures.live_vendors
independent_auditor = receipt_disclosures.independent_auditor
independent_reviewer = receipt_disclosures.independent_reviewer
nonpanel_reviewer = receipt_disclosures.nonpanel_reviewer
nonpanel_cell_proven = receipt_disclosures.nonpanel_cell_proven
nonpanel_candidates = receipt_disclosures.nonpanel_candidates
host_family = receipt_disclosures.host_family
independent_auditor_available = receipt_disclosures.independent_auditor_available
unfilled_seats = receipt_disclosures.unfilled_seats
maker_families = receipt_disclosures.maker_families
pinned_auditor_vendors = receipt_disclosures.pinned_auditor_vendors
auditor_constraints = receipt_disclosures.auditor_constraints
_live_vendors = receipt_disclosures.live_vendors
str_list = receipt_disclosures.str_list
dict_list = receipt_disclosures.dict_list
bool_value = receipt_disclosures.bool_value
adapter_provenance_shape = receipt_disclosures.adapter_provenance_shape
order_vendor_provenance_gaps_shape = receipt_disclosures.order_vendor_provenance_gaps_shape
_degraded = degraded
_base_degraded = base_degraded
_driver_author_family = author_family
_same_family_seats = same_family_seats
_same_family_degraded = same_family_degraded
_seat_map_violated = seat_map_violated
_seat_map_unjudgeable = seat_map_unjudgeable


ATTESTED_VERDICT = "uncertified-manual"
CHECKPOINT_STOP_REASONS = ("tripwire", "park")
# The verdicts a CERTIFIED receipt may carry — every `state["terminal"]` the folds can set. An
# unlisted verdict is a receipt nobody in this module produced.
CERTIFIED_VERDICTS = ("converged", "halted", "held", "stalled", "cannot-certify",
                      "capped-with-open-critical", "capped-with-open-blocker", "handed-back")

# A finished session of an earlier schema version is refused by every hand command that loads state
# through `_load_driver_state` (`record-result`, `advance` and the others) under this reason (an
# unfinished one never gets that far: the upgrade gate refuses it first).
LEGACY_SESSION_REFUSAL = "legacy-session-use-next-submit"
LEGACY_SESSION_REFUSAL_DETAIL = ("this session is from an earlier plugin version and has finished; "
                                 "start a fresh session")

# The per-attempt orders manifest `advance` emits for a dispatch-* phase. The phase rides the PATH
# because one round emits several dispatch phases at the same attempt number (`dispatch-panel` a0
# and `dispatch-verifiers` a0 both exist in round 1) — the order's flat
# `round-<N>/orders/manifest.a<K>.json` would collide between them.
ORDERS_DIRNAME = "orders"
ORDERS_MANIFEST_SCHEMA = "orders-manifest/1"
# External engines run in a shell and land a full envelope; host seats write payload-only.

# The handback sidecar's path under the repo's git dir (§6). Nothing in this module READS it for
# enforcement — the hook that does is a later PR.
SIDECAR_DIRNAME = "superheroes"
SIDECAR_FILE = "review-receipt.json"

# The two attest-eligibility classes every #723 journal event is stamped with. `caller-error` is
# NEVER attest-eligible (the caller can retry it); `driver-internal-error` is the allowlist.
FAULT_CALLER = "caller-error"
FAULT_INTERNAL = "driver-internal-error"

# Phases (the `action` a `next` emits; each is fulfilled by exactly one orchestrator dispatch).
# Re-exported from `round_phases` so external callers keep importing from here.
P_PANEL = round_phases.P_PANEL
P_VERIFIERS = round_phases.P_VERIFIERS
P_SYNTHESIS = round_phases.P_SYNTHESIS
P_AUDITS = round_phases.P_AUDITS
P_SCOPED = round_phases.P_SCOPED
P_GAPSWEEP = round_phases.P_GAPSWEEP
P_SECOND_TEST = round_phases.P_SECOND_TEST
P_VERIFY = round_phases.P_VERIFY
P_APPLY_FIXES = round_phases.P_APPLY_FIXES
P_TERMINAL = round_phases.P_TERMINAL

BASE_GUARD_CHECKED = "checked-stat-bound"

FOLLOWUP_MALFORMED_CAUSE = "follow-up-malformed"
STAGED_ID_UNRESOLVABLE_CAUSE = "staged-id-unresolvable"

# Named refusal when loop-state carries an unrecognized dispositionLedgerOwner marker value.
DISPOSITION_LEDGER_OWNER_UNRECOGNIZED_CAUSE = "disposition-ledger-owner-unrecognized"
JOURNAL_DAMAGED_CAUSE = "journal-damaged"
AUDITOR_UNSEATABLE_CAUSE = "auditor-unseatable"
JOURNAL_DAMAGED_DETAIL = (
    "the session journal has an unreadable or malformed row; the result was not recorded"
)

# ONE declaration of the ``_provenance`` block a ruling file carries: required field → the shape it
# must satisfy. ``_owner_artifact_provenance_well_formed`` is the only reader. Unknown extra keys
# inside ``_provenance`` are tolerated.
OWNER_PROVENANCE_FIELD_SHAPES = {
    "ruledBy": "non-empty string",
    "ruledAt": "non-empty string",
    "records": "non-empty list of non-empty strings",
}

ROUND_PHASE_NOT_PENDING_REFUSAL = "round-phase-not-pending"


# Per-round disclosure channels recorded during hand `submit` (not `_fold_panel`). Each name here
# must also appear in `CARRIED_DISCLOSURE_CHANNELS` so resume and `build_receipt` share the same
# one home.
SUBMIT_DISCLOSURE_CHANNELS = ("recordOrphansIgnored",)

# Per-round disclosure channels recorded during order emission (`orders-emit`, not `_fold_panel`).
# Each name here must also appear in `CARRIED_DISCLOSURE_CHANNELS` so resume and `build_receipt`
# share the same one home.
ORDER_EMISSION_DISCLOSURE_CHANNELS = (
    "orderVendorProvenanceGaps", "priorCommentsUnavailable", "gateGuidanceRowCarried",
)

# Per-round disclosure channels `_fold_verifiers` records (not `_fold_panel`). Each name here must
# also appear in `CARRIED_DISCLOSURE_CHANNELS` so resume and `build_receipt` share the same home.
VERIFIER_FOLD_DISCLOSURE_CHANNELS = ("verifyPasses", "verifierProvenance", "synthesisUnseatable",
                                     "secondTestUnseatable")

# Per-round disclosure channels `_record_adapter_provenance` records in `_fold` (shared across phases,
# not `_fold_panel`). Each name here must also appear in `CARRIED_DISCLOSURE_CHANNELS` so resume
# and `build_receipt` share the same one home.
FOLD_PROVENANCE_DISCLOSURE_CHANNELS = ("adapterProvenance",)

# The per-round disclosure channel an earlier version's judgment fold recorded. Nothing records it
# any more; it stays so a resumed earlier-version session's `judgmentDispositions` still has its one
# home in the census (it must also appear in `CARRIED_DISCLOSURE_CHANNELS`).
JUDGMENT_FOLD_DISCLOSURE_CHANNELS = ("judgmentDispositions",)

# Per-round disclosure channels `_break_it_kept_step` records at the converge gate (not
# `_fold_panel`). Each name here must also appear in `CARRIED_DISCLOSURE_CHANNELS` so resume and
# `build_receipt` share the same home.
TERMINAL_DISCLOSURE_CHANNELS = ("breakItKept",)

# Per-round disclosure channel `_fold_verify` records on a verify fold that reaches a `pass` (not
# `_fold_panel`). Each name here must also appear in `CARRIED_DISCLOSURE_CHANNELS` so resume and
# `build_receipt` share the same home.
VERIFY_FOLD_DISCLOSURE_CHANNELS = ("verifyVia",)

# Every OTHER per-round key `_fold_panel` or `_fold_verifiers` records, named here so the census can
# close the set: a new `_record_round` key lands in one home or the other, deliberately, or the
# census fails. None of these is restorable on resume — `compileDrops` and `unverified` carry
# finding-shaped EVIDENCE rows that round-records.json deliberately never stores (review_memory's
# persist-skeleton contract); `seatStatus` / `missingSeats` are the panel's own coverage
# bookkeeping, owned by the round that actually ran its seats (`seatStatus` is emitted
# unconditionally, not as a disclosure); `lensCoverage` is the panel's per-round coverage anchor
# owned by the round that ran the panel; `verify` carries finding-shaped verifier evidence (drops,
# downgrades, unverified, ambiguous) that round-records.json never stores — the receipt gets
# `verifyPasses` instead (restorable via `VERIFIER_FOLD_DISCLOSURE_CHANNELS`).
UNRESTORED_PANEL_ROUND_KEYS = ("seatStatus", "lensCoverage", "compileDrops", "unverified", "missingSeats",
                               "verify")

def _round_disclosure_key(value):
    """The rounds-map key for a durable record's round value — one home for producer and restorer.

    Int-normalized so `1`, `1.0`, and `"1"` key the same round. Junk returns None (no disclosure
    block persisted or restored, never a crash): bools, non-integral floats (a `1.5` must not alias
    round 1's evidence), non-finite floats (`int(inf)` raises OverflowError), and unparseable values."""
    n = review_loop_plan._round_number(value)
    if n is None:
        return None
    return str(n)


# =============================================================================================
# canonical json + hashing + journal
# =============================================================================================

def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def state_hash(state):
    """sha256 over the canonical state JSON. Stable between a `next` (which persists the pending
    step) and the matching `submit`, so a stale/forked submit is caught by an echo mismatch."""
    return _sha256(_canonical(state))


class MaxRoundsRefusal(ValueError):
    """Load-time refusal for an invalid ``maxRounds`` on a fresh state.

    Raised only from ``_default_config`` — the single config load point — when ``maxRounds`` is not
    a positive non-bool ``int``. The ``next`` CLI refuses a value above ``round_phases.ROUND_CAP`` too,
    before this point."""
    def __init__(self, reason, value=None):
        super().__init__(reason)
        self.reason = reason
        self.value = value


class FixBatchCapRefusal(ValueError):
    """Load-time refusal for an invalid ``fixBatchCap`` — sibling of ``MaxRoundsRefusal``.

    Raised only from ``_default_config`` when ``fixBatchCap`` is present, not ``None``, and not a
    positive non-bool ``int``."""
    def __init__(self, reason, value=None):
        super().__init__(reason)
        self.reason = reason
        self.value = value


class DispositionLedgerOwnerRefusal(ValueError):
    """Fold-time refusal for an unrecognized ``dispositionLedgerOwner`` marker — sibling of
    ``MaxRoundsRefusal``.

    Raised only from ``_fold`` — the single chokepoint every fold passes through."""
    def __init__(self, reason, value=None):
        super().__init__(reason)
        self.reason = reason
        self.value = value


UNFILLED_SEAT_REASON = "unfilled"


class AuditorUnseatable(ValueError):
    """Refusal when a durable-path audit target seats a non-runner-channel auditor."""

    def __init__(self, detail, live_vendors, fixer_vendor):
        super().__init__(detail)
        self.detail = detail
        self.live_vendors = live_vendors
        self.fixer_vendor = fixer_vendor


RECEIPT_FAULT_WRITE = "receipt-write"                 # round-receipt.json could not be written
RECEIPT_FAULT_VERIFY = "receipt-verify"               # the on-disk receipt failed re-verification
RECEIPT_FAULT_KINDS = (RECEIPT_FAULT_WRITE, RECEIPT_FAULT_VERIFY)


class ReceiptFault(str):
    """A terminal-receipt fault detail that carries its class as data. It IS the detail string
    (every consumer — CLI responses, `_receiptFault` in state, the tests that read it — keeps
    reading a str); `kind` is the classification minted at the raise site."""
    def __new__(cls, detail, kind):
        if kind not in RECEIPT_FAULT_KINDS:
            raise ValueError("unknown receipt fault kind %r" % (kind,))
        obj = str.__new__(cls, detail)
        obj.kind = kind
        return obj


class ReceiptWriteError(Exception):
    """Raised by `_write_receipt` around the OSError: the raise site names the class."""
    kind = RECEIPT_FAULT_WRITE


class JournalFaultUnrecordable(Exception):
    """Last-resort fail-loud (#507 WO-FIX-RECOVERY): the journal append failed AND the durable fault
    marker that would have made finalization park ALSO could not be written. There is NO silent tier
    below this — the run must fail LOUDLY (the CLI exits nonzero) or PARK cannot-certify (a library
    driver), never continue as though the ran-evidence were intact. Carries both underlying OSErrors
    so the CLI can print them to stderr."""

    def __init__(self, journal_error, marker_error):
        self.journal_error = journal_error
        self.marker_error = marker_error
        super().__init__("journal write failed (%s) and the fault marker was also unwritable (%s)"
                         % (journal_error, marker_error))


def _journal_append(session_dir, entry):
    """Append one next/submit event to the journal — this is the `scriptRan` evidence. A journal miss
    never derails the run mid-flight, but it is NOT swallowed: a failed append is a LOST piece of the
    driver's ran-evidence, so it records a durable fault marker that `_finalize_receipt` fails closed
    on (a partial-journal gap must never quietly certify — #507 R2 residual-4). If BOTH the journal
    and the marker are unwritable, `_mark_journal_fault` raises `JournalFaultUnrecordable` — the
    last-resort fail-loud, propagated here (never swallowed). ts via time.time."""
    entry = dict(entry)
    entry.setdefault("ts", time.time())
    round_records.require_complete_revision(entry)
    try:
        with open(os.path.join(session_dir, JOURNAL_FILE), "a", encoding="utf-8") as fh:
            fh.write(_canonical(entry) + "\n")
    except OSError as exc:
        _mark_journal_fault(session_dir, entry, exc)


def _mark_journal_fault(session_dir, entry, exc):
    """Record a durable journal-write fault so finalization fails closed. This is the LAST recordable
    tier: if the marker ALSO cannot be written, there is NO silent tier below it — raise
    `JournalFaultUnrecordable` so the run fails loud (CLI nonzero) or parks cannot-certify (library),
    never swallowing the fault (the R2 detectability gap, one level down: `except OSError: pass` here
    let a doubly-unwritable dir go silent). The exception carries both OSErrors for the stderr
    report. #507 WO-FIX-RECOVERY.

    #723: the marker also records WHICH event was lost — `{sessionId, round, phase, attempt,
    entryHash, seq}` — so the recoverable neighbour of `JournalFaultUnrecordable` (journal append
    failed, marker succeeded → `journal-degraded`) is REFERENCABLE: `attest --failure
    marker:<entryHash>` binds to exactly this row. `JournalFaultUnrecordable` itself stays
    un-attestable by construction — when both writes fail there is no evidence of either, so it can
    never be its own evidence. `seq` is the journal sequence the lost entry WOULD have taken (the
    count of entries that did land, plus one); it is advisory, and `entryHash` is the binding key."""
    entry_hash = _sha256(_canonical(entry))
    try:
        with open(os.path.join(session_dir, JOURNAL_FAULT_FILE), "a", encoding="utf-8") as fh:
            fh.write(_canonical({"ts": time.time(), "error": str(exc),
                                 "cmd": entry.get("cmd"), "phase": entry.get("phase"),
                                 "sessionId": _meta_session_id(session_dir),
                                 "round": entry.get("round"), "attempt": entry.get("attempt"),
                                 "entryHash": entry_hash,
                                 "seq": len(read_journal(session_dir)) + 1}) + "\n")
    except OSError as marker_exc:
        raise JournalFaultUnrecordable(exc, marker_exc) from marker_exc


def _journal_faulted(session_dir):
    return os.path.exists(os.path.join(session_dir, JOURNAL_FAULT_FILE))


def read_journal(session_dir, *, report_lossy=False):
    out = []
    lossy = False
    path = os.path.join(session_dir, JOURNAL_FILE)
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    # axis: a lossy journal read flags unparseable lines
                    if report_lossy:
                        lossy = True
                    continue
    except OSError:
        if report_lossy:
            lossy = True
    except UnicodeError:
        if report_lossy:
            lossy = True
        else:
            raise
    if report_lossy:
        return out, lossy
    return out


def read_fault_markers(session_dir):
    """Every durable journal-fault marker row (`journal-degraded` evidence). Never raises."""
    out = []
    path = os.path.join(session_dir, JOURNAL_FAULT_FILE)
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError:
        pass
    return out


def _meta_session_id(session_dir):
    """The session id `round_records.mint_session_id` minted into meta.json, or None."""
    obj, err = round_records.read_json(os.path.join(session_dir, round_records.META_FILE))
    if err is not None or not isinstance(obj, dict):
        return None
    sid = obj.get("sessionId")
    return sid if isinstance(sid, str) and sid else None


_REVIEW_SESSION_MARKER = "review-session.json"
_REVIEW_SESSION_SCHEMA = "review-session/1"


def _journal_bootstrap_marker_failure(session_dir, reason):
    try:
        _journal_append(session_dir, {"cmd": "bootstrap-review-session-marker",
                                      "outcome": "failed", "reason": reason})
    except Exception:
        pass


def _review_session_marker_path(gitdir):
    return os.path.join(gitdir, SIDECAR_DIRNAME, _REVIEW_SESSION_MARKER)


def _bootstrap_review_session_marker(session_dir):
    """Write review-session.json scope marker; failures are swallowed (#624 §4)."""
    try:
        meta = _session_meta(session_dir)
        repo_root = meta.get("repoRoot")
        if not isinstance(repo_root, str) or not repo_root:
            repo_root = store_core.repo_root(os.getcwd())
        if not repo_root:
            _journal_bootstrap_marker_failure(session_dir, "repo-root-unresolvable")
            return
        repo_root = os.path.realpath(repo_root)
        branch = store_core.run_git(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
        if not branch or branch == "HEAD":
            _journal_bootstrap_marker_failure(session_dir, "detached-head")
            return
        gitdir = store_core.get_worktree_gitdir(repo_root)
        super_dir = os.path.join(gitdir, SIDECAR_DIRNAME)
        os.makedirs(super_dir, exist_ok=True)
        marker = {
            "schema": _REVIEW_SESSION_SCHEMA,
            "sessionDir": os.path.realpath(session_dir),
            "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "repoRoot": repo_root,
            "branch": branch,
        }
        marker_path = _review_session_marker_path(gitdir)
        round_commit.atomic_write_bytes(marker_path, _canonical(marker).encode("utf-8"))
    except Exception as exc:
        _journal_bootstrap_marker_failure(session_dir, str(exc))


def _state_version(state):
    """The state's `schemaVersion` when it is one this driver knows, else None. Read-only — a
    loaded state is NEVER stamped with a version it did not carry (the hash-preservation rule)."""
    if not isinstance(state, dict):
        return None
    version = state.get("schemaVersion")
    if isinstance(version, bool) or not isinstance(version, int):
        return None
    return version if version in SUPPORTED_STATE_VERSIONS else None


def _seat_result_schema(state):
    return round_records.seat_result_schema_for_state_version(_state_version(state))


def _receipt_version(state):
    """The receipt schemaVersion for a state: the STATE's version drives it via
    ``RECEIPT_CERTIFIED_SCHEMA % _state_version(state)``."""
    return _state_version(state) or SCHEMA_VERSION


def receipt_kind(receipt):
    """The receipt's shape name — `receipt-certified/<v>`, `receipt-attested/1`,
    `receipt-interim/1`, or None."""
    if not isinstance(receipt, dict):
        return None
    if receipt.get("schema") == RECEIPT_ATTESTED_SCHEMA:
        return RECEIPT_ATTESTED_SCHEMA
    if receipt.get("schema") == RECEIPT_INTERIM_SCHEMA:
        return RECEIPT_INTERIM_SCHEMA
    version = receipt.get("schemaVersion")
    if isinstance(version, bool) or not isinstance(version, int):
        return None
    if version not in SUPPORTED_STATE_VERSIONS:
        return None
    return RECEIPT_CERTIFIED_SCHEMA % version


def _scriptran_summary(session_dir):
    """The scriptRan evidence for the receipt: per-phase counts from the journal, plus the raw
    invocation total. A terminal with an empty journal is impossible on the mandated path — the
    summary is how the orchestrator's vet proves the driver actually ran."""
    counts = {}
    invocations = 0
    for e in read_journal(session_dir):
        invocations += 1
        key = "%s:%s" % (e.get("cmd"), e.get("phase"))
        counts[key] = counts.get(key, 0) + 1
    return {"invocations": invocations, "byPhase": counts}


# =============================================================================================
# mechanical compile (SKILL §4 steps 1-4 + 6 — deterministic, main-context)
# =============================================================================================

_NIT_CAP = 5


def _diff_scope_ok(finding, valid):
    """A finding is in diff scope iff its (file, line) is an anchorable RIGHT-side line of the
    round diff — the same hunk-walking `diff_scope.parse_diff_lines` uses. `valid` is None
    when no diff was supplied (scope check skipped)."""
    if valid is None:
        return True
    if finding.get("file") == pr_body_stage.CITATION:
        return True  # the PR body is never in the git diff; the fixer fixes it in the staged copy
    file_lines = valid.get(finding.get("file"))
    if not file_lines:
        return False
    return finding.get("line") in file_lines


COMPILE_DROP_LINE_NOT_INTEGER = "line is not an integer"
COMPILE_DROP_NO_CONSEQUENCE = "no stated consequence"


def _coerce_line(value):
    return session_contract.coerce_line(value)


def _nit_cap(findings):
    """After dedupe, keep at most 5 code-quality Nits; the overflow collapses to ONE summary entry
    so the readout isn't buried (the base rubric's severity cap). Only a Nit whose consequenceKind
    is exactly "code-quality" collapses: a Nit with any other kind is kept, whatever the count. The
    summary row's `members` holds the collapsed Nit dicts, so each still reaches the ledger."""
    kept = []
    nits = []
    for f in findings:
        if isinstance(f, dict) and circuit_breaker.canonical_severity(f.get("severity")) == "Nit":
            nits.append(f)
        else:
            kept.append(f)
    members = []
    quality_seen = 0
    for nit in nits:
        if nit.get(review_findings_schema.CONSEQUENCE_KIND_KEY) == review_findings_schema.CODE_QUALITY:
            quality_seen += 1
            if quality_seen > _NIT_CAP:
                members.append(nit)
                continue
        kept.append(nit)
    if members:
        kept.append({
            "title": "+ %d more Nits — see findings-*.json for details" % len(members),
            "severity": "Nit", "file": None, "line": None, "summaryEntry": True,
            "members": members,
        })
    return kept


def _merge_same_finding(existing, incoming):
    """Higher severity wins the base dict, dimension unioned, tradeoff OR-ed. When exactly one side carries a
    break-it test with the driver's stamp, the merged dict keeps that side's `suggestion`, `breakItRun` and
    `breakItRuns`, so an ordinary finding that wins the base never drops the attached test."""
    dims = panel_tally._merge_dims(existing, incoming)
    if circuit_breaker.severity_rank(incoming.get("severity")) \
            < circuit_breaker.severity_rank(existing.get("severity")):
        merged = dict(incoming)
    else:
        merged = dict(existing)
    carriers = [s for s in (existing, incoming)
                if break_it.carries_test(s) and isinstance(s.get(break_it.RUN_FIELD), dict)]
    if len(carriers) == 1:
        # axis: an attached test, its stamp and its runs survive a same-anchor merge the other finding wins
        for field in ("suggestion", break_it.RUN_FIELD, break_it.RUNS_FIELD, REVIEWER_TEST_FIELD):
            if field in carriers[0]:
                merged[field] = carriers[0][field]
            else:
                merged.pop(field, None)
    merged["consequence"], merged["consequenceKind"] = finding_outcomes.merged_consequence(
        [existing, incoming])
    merged["dimension"] = dims
    merged["tradeoff"] = bool(existing.get("tradeoff") or incoming.get("tradeoff"))
    merged["classification"] = "judgment" if merged["tradeoff"] else "mechanical"
    seqs = [f.get(session_contract.RAISED_SEQ_FIELD) for f in (existing, incoming)]
    seqs = [q for q in seqs if isinstance(q, int) and not isinstance(q, bool)]
    if seqs:  # the newest raise, so settlement sees the merged live copy as current
        merged[session_contract.RAISED_SEQ_FIELD] = max(seqs)
    return merged


COMPILE_DROP_MERGED_SAME_PLACE = "merged with a finding at the same place and title"


def _finding_anchor(finding):
    """The per-LOCATION anchor — (file, line, normalized title) — two findings share iff they merge."""
    return (finding.get("file"), finding.get("line"), normalize_title(str(finding.get("title") or "")))


def _merge_drops(findings):
    """One drop row for each finding `_compile_by_anchor` absorbs into an earlier one at its anchor."""
    seen = set()
    drops = []
    for f in findings:
        key = _finding_anchor(f)
        if key in seen:
            drops.append({"file": f.get("file"), "line": f.get("line"), "title": f.get("title"),
                          "reason": COMPILE_DROP_MERGED_SAME_PLACE})
        seen.add(key)
    return drops


def _compile_by_anchor(findings):
    """Dedupe by the binding review workflow's per-LOCATION anchor — (file, line, normalized-title)
    — NOT panel_tally's line-less `file::normalized-title` identity. The line was the DROPPED key:
    two distinct findings that share a title at DIFFERENT lines are distinct blockers and BOTH must
    survive (else a blocker at a second line is silently collapsed away). For the SAME anchor,
    higher severity wins, dimensions are unioned, and tradeoff is OR-ed; FR-4 classification is
    stamped from the surviving tradeoff state. All inputs are already cited (file+line present)."""
    by_anchor = {}
    order = []
    for f in findings:
        key = _finding_anchor(f)
        if key in by_anchor:
            by_anchor[key] = _merge_same_finding(by_anchor[key], f)
        else:
            by_anchor[key] = dict(f)
            order.append(key)
    out = [by_anchor[k] for k in order]
    for f in out:  # FR-4: deterministic mechanical/judgment classification (no action taken)
        f["classification"] = "judgment" if f.get("tradeoff") else "mechanical"
    return out


def mechanical_compile(findings, diff_text=None, scope_exempt=None, stamped=None):
    """Port of SKILL §4 steps 1-4 + 6, deterministic and fail-closed:
      1. citation check — drop file/line-less findings;
      2. diff-scope check — drop findings whose (file,line) is not an anchor of the round diff;
         `scope_exempt` is a set of `id()`s of input dicts the break-it intercept marked per-area
         scope-exempt — only those skip this check; `stamped` is a set of `id()`s of input dicts the
         intercept stamped itself — only those keep their `breakItRun` and `breakItRuns`, and every
         other finding (all of them, by default) has both stripped;
      4. dedupe by the per-LOCATION anchor (file, line, normalized-title) — higher severity wins,
         dimensions unioned, tradeoff OR-ed. NOT the line-less file::title identity, which collapses
         two distinct-line findings that share a title (a dropped blocker);
      6. nit cap.
    A finding that states no consequence (`finding_outcomes.has_stated_consequence`) is dropped
    after the citation, line and diff-scope checks; a break-it-stamped finding is held to the same
    rule — `scope_exempt` exempts diff scope only.
    Returns (compiled, drops) where each drop names WHY (never silently dropped)."""
    if not isinstance(findings, list):
        findings = []
    valid = diff_scope.parse_diff_lines(diff_text) if diff_text is not None else None
    exempt = scope_exempt if isinstance(scope_exempt, (set, frozenset)) else frozenset()
    stamped_ids = stamped if isinstance(stamped, (set, frozenset)) else frozenset()
    kept, drops = [], []
    for f in findings:
        if not isinstance(f, dict):
            continue
        if not isinstance(f.get("file"), str) or f.get("line") is None:
            drops.append({"file": f.get("file"), "title": f.get("title"),
                          "reason": "uncited — no file:line"})
            continue
        ok, line = _coerce_line(f.get("line"))
        if not ok:
            drops.append({"file": f.get("file"), "line": f.get("line"),
                          "title": f.get("title"), "reason": COMPILE_DROP_LINE_NOT_INTEGER})
            continue
        fc = dict(f)
        fc["line"] = line
        if id(f) not in stamped_ids:
            # axis: a stamp the seat supplied itself never survives compile — only the intercept's own copies carry one
            fc.pop(break_it.RUN_FIELD, None)
            fc.pop(break_it.RUNS_FIELD, None)
        # axis: a seat never marks its own finding as having had its one more test, whatever value it sends — only the driver's second-test step (staged without compile) sets it
        fc.pop(SECOND_TEST_FIELD, None)
        if id(f) not in exempt and not _diff_scope_ok(fc, valid):
            drops.append({"file": fc.get("file"), "line": fc.get("line"),
                          "title": fc.get("title"), "reason": "outside the round diff scope"})
            continue
        if not finding_outcomes.has_stated_consequence(f):
            drops.append({"file": fc.get("file"), "line": fc.get("line"),
                          "title": fc.get("title"), "reason": COMPILE_DROP_NO_CONSEQUENCE})
            continue
        fc.pop(session_contract.FINDING_KEY_FIELD, None)
        fc["severity"] = circuit_breaker.effective_severity(fc.get("severity"))
        if "dimension" in fc:
            norm = panel_tally.normalize_dimension(fc["dimension"])
            if norm:
                fc["dimension"] = norm
            else:
                fc.pop("dimension", None)
        kept.append(fc)
    compiled = _compile_by_anchor(kept)
    drops.extend(_merge_drops(kept))
    compiled = _nit_cap(compiled)
    collapsed = [m for f in compiled if f.get("summaryEntry") for m in f.get("members") or []]
    _mint_finding_keys(compiled + collapsed)
    return compiled, drops


# =============================================================================================
# author-justification POST-filter (#230-consistent NEW ordering: after merge_and_rank)
# =============================================================================================

_SUBSTANTIVE_MIN = 15


def _prior_justification(finding, prior_comments):
    """The substantive prior-author justification on this finding's (file,line), or None. A thread
    body under the length floor is not substantive (a bare '+1'/'wontfix' is not a justification)."""
    if not isinstance(prior_comments, list):
        return None
    for c in prior_comments:
        if not isinstance(c, dict):
            continue
        file = c.get("file") if c.get("file") is not None else c.get("path")
        if file != finding.get("file") or c.get("line") != finding.get("line"):
            continue
        body = c.get("body")
        if isinstance(body, str) and len(body.strip()) >= _SUBSTANTIVE_MIN:
            return body.strip()
    return None


def author_justification_filter(findings, prior_comments):
    """POST-filter (runs AFTER merge_and_rank, #230-consistent). May drop ONLY a finding whose
    verdict is present and != CONFIRMED, and only for a substantive prior justification, recording
    the justification quoted. A CONFIRMED finding with a prior justification SURVIVES, stamped
    `challenge: "author-justified"`. A finding with NO verdict is never dropped (silence never
    certifies a drop)."""
    if not isinstance(findings, list):
        return [], []
    kept, drops = [], []
    for f in findings:
        if not isinstance(f, dict):
            kept.append(f)
            continue
        just = _prior_justification(f, prior_comments)
        if not just:
            kept.append(f)
            continue
        verdict = f.get("verdict")
        if verdict == "CONFIRMED":
            g = dict(f)
            g["challenge"] = "author-justified"
            kept.append(g)
        elif verdict is None:
            # no verdict → never dropped (a finding that got no verdict this round must not be
            # certified away by a prior comment).
            kept.append(f)
        else:
            drops.append({"id": f.get("id"), "file": f.get("file"), "title": f.get("title"),
                          "reason": "author-justified (verdict %s, not CONFIRMED)" % verdict,
                          "justification": just})
    return kept, drops


# =============================================================================================
# independence + certification shape
# =============================================================================================

def _auditor_vendor(config, fixer_vendor, runner_only=False, maker_families=frozenset(),
                    pinned_vendors=None):
    """The auditor of a fix is never the fixer's model FAMILY, nor any maker's family (CONVENTIONS
    §7.5 — independence keys on family, not the dispatch CLI). Independence is NEVER satisfied between
    two cursor first-party models (#651, owner-ratified 2026-07-26): composer and grok share the `xai`
    family, so a cursor-grok auditor is NOT independent of a cursor-composer fix. When no eligible
    vendor is live there is no auditor at all: `(None, "unseatable")`, the audit counts as not run,
    and no vendor stands in. `runner_only` narrows the pool to runner-channel vendors."""
    vendor, _fam = receipt_disclosures.independent_auditor(
        config, fixer_vendor, runner_only=runner_only, maker_families=maker_families,
        pinned_vendors=pinned_vendors)
    if vendor is not None:
        return vendor, "independent"
    return None, "unseatable"


# Seat-map receipt projections (#681) — leaf module ``seat_map_receipts``; thin aliases for in-module
# call sites and existing tests.
_seat_map_receipts = seat_map_receipts.receipts
_sm_latest_with_seats = seat_map_receipts.latest_with_seats
_sm_any_seats = seat_map_receipts.any_seats
_sm_unexcused_violations = seat_map_receipts.unexcused_violations
_sm_pin_excused_records = seat_map_receipts.pin_excused_records
_emit_receipt_seat_map = seat_map_receipts.emit_receipt_seat_map
_sm_unjudgeable_receipts = seat_map_receipts.unjudgeable_receipts
_sm_unjudgeable_run_level_disclosure = seat_map_receipts.unjudgeable_run_level_disclosure
_sm_round_governing_unjudgeable = seat_map_receipts.round_governing_unjudgeable


def _seat_map_violations(state):
    return seat_map_violations(state)


def _seat_pin_excused(state):
    return bool(_sm_pin_excused_records(state, _driver_author_family(state)))


def _seat_map_unproven_liveness(state):
    for v in _seat_map_violations(state):
        if isinstance(v, dict) and v.get("evidence") == "unproven-liveness":
            return True
    return False


def _seat_map_unavailable(state):
    """Whether the run lacks a usable seat map — rounds ∪ receipt projections union idiom.

    UNION of (a) any round recorded ``seatMapUnavailable`` and (b) no receipt anywhere carries
    seats, so neither channel alone is load-bearing.

    A new session starts with empty ``rounds`` and no ``seatMapReceipts`` beyond a supplied seat
    map; nothing is carried in from a records file."""
    for rec in (state.get("rounds") or {}).values():
        if not isinstance(rec, dict):
            continue
        if rec.get("seatMapUnavailable"):
            return True
    return not _sm_any_seats(state)


def _certification_base(state):
    """Tri-state base provenance for certification — never infer fetched from absence."""
    if _base_degraded(state):
        return "degraded"
    cfg = state.get("config") or {}
    if cfg.get("baseGuard") == BASE_GUARD_CHECKED:
        return "fetched"
    return "not-checked"


def _cert_shape(state, base):
    if _seat_map_violated(state):
        return base + "-constraint-violated"
    if (
        _degraded(state)
        or _base_degraded(state)
        or _same_family_degraded(state)
        or _seat_pin_excused(state)
        # bite-axis: absent seat map never certifies unqualified-clean — projection 1 of 3 (#681).
        or _seat_map_unavailable(state)
        or _seat_map_unjudgeable(state)
    ):
        return base + "-degraded"
    return base


# =============================================================================================
# state lifecycle
# =============================================================================================

def _roster_lens_dimensions(seat_map_obj):
    """The lens seats of a seeded seat map's ``roster``, in ``DIMENSIONS`` order; ``[]`` when the
    map, the roster, or its lens members cannot be read, or when the roster omits a seat its own
    lane basis requires (the caller then keeps all five lenses). The roster is read through
    ``seat_map.effective_roster``; an unknown seat name is ignored."""
    roster = seat_map.effective_roster(seat_map_obj)
    if roster is None:
        return []
    basis = seat_map_obj.get("laneBasis")
    # axis: a roster short of its lane basis never reduces the lenses — see bite-proof record wo_a_1797_roster
    if any(n not in roster for n in seat_map.roster_for(basis)):
        return []
    return [d for d in DIMENSIONS if d in roster]


def _diff_header_sides(line):
    """The (a-side, b-side) canonical paths of one ``diff --git`` header (git C-quoting undone), or
    None when it cannot be read unambiguously. Delegates to the canonical reader in
    ``sanitized_view`` — this module keeps no path decoder of its own; the rename policy (both sides
    count as changed paths) is this caller's."""
    import sanitized_view
    try:
        return sanitized_view.sides_from_diff_git_line(line.encode("utf-8", "surrogateescape"))
    except (UnicodeError, ValueError):
        return None


def _diff_changed_paths(diff_text):
    """The canonical paths a git diff names (both sides of each file header, git C-quoting undone), or
    None when the diff cannot be read as such (not text, no file header, or a header this reader
    cannot parse). Read from the diff in hand rather than re-derived from a pinned head: the head a
    post-fix diff describes is not on the config, and a stale head would fail open."""
    if not isinstance(diff_text, str):
        return None
    headers = [ln for ln in diff_text.split("\n") if ln.startswith("diff --git ")]
    if not headers:
        return None
    paths = []
    for ln in headers:
        sides = _diff_header_sides(ln)
        if sides is None:
            return None
        for p in sides:
            if p not in paths:
                paths.append(p)
    return paths


LANE_EXPANDED_RECOMPOSE = decision_kinds.LANE_EXPANDED_RECOMPOSE


def _reevaluate_lane_dimensions(state, config, diff_text):
    """Re-ask the lane call at a new reviewed head (#1797). A session whose seat map was composed for
    a reduced roster (``laneBasis.floor`` None) continues unchanged while the head still touches no
    risk area. When the head's basis calls for seats the governing map's roster lacks, or its risk
    cannot be read, the session HALTS ``lane-expanded-recompose``: the driver holds none of the
    setup-time facts to recompose a seat map mid-session, so the review restarts with a freshly
    composed map on the current head. Returns True when it halted. Never raises."""
    sm = config.get("seatMap")
    basis = sm.get("laneBasis") if isinstance(sm, dict) else None
    if not (isinstance(basis, dict) and "floor" in basis and basis["floor"] is None):
        return False
    new_basis = None
    try:
        import lane_call
        paths = _diff_changed_paths(diff_text)
        repo_root = config.get("repoRoot")
        if paths is None or not isinstance(repo_root, str) or not repo_root:
            new_basis = lane_call.unavailable("lane-basis-unavailable: head diff or repo root unreadable",
                                              proposed="full")
        else:
            new_basis = lane_call.call(repo_root, paths, proposed="full")
    except Exception:
        new_basis = {"floor": "full"}
    if not isinstance(new_basis, dict) or new_basis.get("floor") is None:
        return False
    roster = seat_map.effective_roster(sm)
    if roster is not None and all(n in roster for n in seat_map.roster_for(new_basis)):
        return False
    if _is_extra_audit_round(state):
        # the extra audit round composes no panel, so a head that now calls for more seats hands back
        _hand_back(state, "extra-audit-open",
                   "the head now touches a risk area (or its risk cannot be read) beyond the reduced "
                   "seat map, and the extra audit round composes no panel; the fixes stay unaudited",
                   cap=True)
        return True
    _set_terminal(state, "halted")
    state["certification"] = {
        "shape": None,
        "reason": (LANE_EXPANDED_RECOMPOSE + ": this change now touches a risk area (or its risk cannot "
                   "be read), and the seat map was composed for a smaller roster — the review must "
                   "restart with a freshly composed seat map on the current head; certification "
                   "withheld")}
    _decision(state, LANE_EXPANDED_RECOMPOSE,
              "the head touches a risk area (or its risk cannot be read) beyond the reduced seat "
              "map — halt; run Setup again into a fresh session on the current head")
    state["step"] = P_TERMINAL
    return True


def _default_config(overrides=None):
    cfg = {
        "leg": "code",
        "panel": False,
        "code": True,
        "vendors": ["claude"],
        "fixerVendor": None,  # UNKNOWN by default — auditor independence must DEGRADE, not assume claude (#608)
        "verifyCommand": "none",
        "maxRounds": round_phases.ROUND_CAP,
        "dimensions": None,  # resolved below: explicit list, else the seat map's lens roster, else all five
        # Optional records export (#507 WO-D). When `recordsPath` is set the driver writes the
        # session's round-records ledger there after each folded round — written whole, replacing
        # whatever was at that path, and never read back. Absent → nothing is written.
        # The library producer lives in `run_loop`'s post-fold step; the command-line path routes
        # the producer through `cmd_submit`'s `round_commit` submit-accept transaction rather than
        # calling it from `_fold`, because `_fold` runs before that transaction opens.
        "recordsPath": None,
        # PR-mode prior review comments (a list) for the author-justification post-filter. Wired from
        # the CLI's `--prior-comments` (#507 v7); None → the filter never fires.
        "priorComments": None,
        # `next --earlier-findings`: the review record's findings as pool entries (`repeat_marks`), and the reason
        # the file gave none (a missing record is silent); read once at the first `next`.
        "earlierFindings": None,
        "earlierFindingsUnavailable": None,
        # #723 `next --seat-map`: the #510 seat map for round 1. Before #681, `state["seatMap"]`
        # was populated ONLY by `_fold_panel` off the panel artifact; receipt list (#681) stores
        # each round's submission in `seatMapReceipts` instead.
        "seatMap": None,
        # `next --copy-proof`: the checksum proof naming files the change copies byte for byte. Checked once
        # at new_state; the copies it proves are left out of every seat's diff. None → nothing is left out.
        "copyProof": None,
        "fixBatchCap": None,
    }
    if isinstance(overrides, dict):
        cfg.update({k: v for k, v in overrides.items() if v is not None})
    cfg["panel"] = cfg.get("leg") == "panel"
    cfg["code"] = cfg.get("leg") != "panel"
    if not isinstance(cfg.get("dimensions"), list) or not cfg["dimensions"]:
        cfg["dimensions"] = _roster_lens_dimensions(cfg.get("seatMap")) or list(DIMENSIONS)
    cap_val = cfg.get("fixBatchCap")
    if cap_val is not None:
        if not isinstance(cap_val, int) or isinstance(cap_val, bool) or cap_val < 1:
            raise FixBatchCapRefusal("fix-batch-cap-invalid", cap_val)
    rounds_val = cfg["maxRounds"]
    # The library path (harnesses, tests) takes any positive int; the `next` CLI also bounds it by ROUND_CAP.
    if not isinstance(rounds_val, int) or isinstance(rounds_val, bool) or rounds_val < 1:
        raise MaxRoundsRefusal("max-rounds-invalid", rounds_val)
    return cfg


def _fix_batch_cap(config):
    """Return the configured fix-batch cap, or ``FIX_BATCH_CAP_DEFAULT`` when unset/invalid."""
    val = config.get("fixBatchCap") if isinstance(config, dict) else None
    if isinstance(val, int) and not isinstance(val, bool) and val >= 1:
        return val
    return round_phases.FIX_BATCH_CAP_DEFAULT


VERIFY_THEN_CAP = "cap"
VERIFY_THEN_POST_AUDITS = "post-audits"
DELTA_BASELINE_ABSENT = "delta-baseline-absent"
HEAD_DIFF_MISMATCH_CAUSE = "head-diff-mismatch"
HEAD_DIFF_UNVERIFIABLE_CAUSE = "head-diff-unverifiable"


def _round_cap(config):
    """Return the round cap this session runs under: the config's ``maxRounds`` when it is a positive
    non-bool int, else ``ROUND_CAP``. A malformed value never means "no cap". A loaded config above
    ``ROUND_CAP`` (a session an earlier version minted) is honored as stored."""
    val = config.get("maxRounds") if isinstance(config, dict) else None
    if isinstance(val, int) and not isinstance(val, bool) and val >= 1:
        return val
    return round_phases.ROUND_CAP


def _build_session_vendor(seat_map_obj):
    """The vendor token of the build session's family: the seat map's `hostFamily`, else its
    `authorFamily`, mapped to the registered vendor whose models sit in that family. None when the
    map names no family, or the family maps to no vendor (the fixer stays unknown: a disclosed
    degraded audit, never a guess)."""
    if not isinstance(seat_map_obj, dict):
        return None
    family = next((f for f in (seat_map_obj.get("hostFamily"), seat_map_obj.get("authorFamily"))
                   if isinstance(f, str) and f), None)
    for vendor in model_registry.vendors():
        if family is not None and model_registry.family_for("reviewer", vendor) == family:
            return vendor
    return None


def _with_build_session_vendor(config_overrides):
    """The CLI path's session config with `fixerVendor` set to the build session's vendor, read from
    the supplied seat map; a `fixerVendor` already given is kept, and no seat map leaves it unset."""
    overrides = dict(config_overrides) if config_overrides else {}
    if overrides.get("fixerVendor") is None:
        vendor = _build_session_vendor(overrides.get("seatMap"))
        if vendor is not None:
            overrides["fixerVendor"] = vendor
    return overrides or None


def new_state(config=None):
    cfg = _default_config(config)
    seeded_seat_map = cfg.get("seatMap")
    state = {
        "schemaVersion": STATE_SCHEMA_VERSION,
        "sessionGeneration": SESSION_GENERATION,
        "config": cfg,
        "round": 1,
        "step": P_PANEL,
        "pending": None,
        "lastAccepted": None,
        "rounds": {},
        "findings": [],
        "decisions": [],
        "auditRounds": [],
        "selfRecovered": False,
        # A single live vendor is degraded only when no live vendor is family-independent of the
        # declared fixer; duplicate vendor entries never count twice toward the two-vendor pool.
        "independenceDegraded": (
            len(_live_vendors(cfg)) < 2
            and not receipt_disclosures.independent_auditor_available(
                cfg, *receipt_disclosures.auditor_constraints({"config": cfg}))[0]
        ),
        # Seeded from `--seat-map` when one was supplied (#723) as receipt round "0".
        "seatMapReceipts": ([{"round": "0", "map": dict(seeded_seat_map)}]
                            if isinstance(seeded_seat_map, dict) and seeded_seat_map else []),
        "reviewedDiff": cfg.get("diff"),
        "headDiff": None,
        "dispositionSeqCounter": 0,
        "fixBatch": [],
        "fullPanelRan": False,
        # A configured lens that never ran is an OUTSTANDING coverage gap: set when a panel is
        # incomplete, cleared only when a COMPLETE panel re-establishes coverage. A converge resting
        # on it is withheld (silence never certifies — #507 R2 residual-1).
        "_incompletePanel": False,
        "terminal": None,
        "certification": None,
        # #507 WO-D: the in-memory review-record ledger (one record per REVIEW round) the
        # challenged-coverage / recurrence breaker reads, plus the accumulated coverage decisions.
        "_records": [],
        "_coverage": [],
    }
    _check_copy_proof(state, cfg)
    # axis: a reduced roster is re-checked against the round-1 diff before the first panel — see bite-proof record wo_a_1797_roster
    _reevaluate_lane_dimensions(state, cfg, state["reviewedDiff"])
    return state


COPY_PROOF_HEAD_TIMEOUT = 60


def _resolve_head_commit(repo_root):
    """The commit sha ``HEAD`` names in ``repo_root``, or None when Git cannot say."""
    try:
        proc = subprocess.run(
            ["git", "-C", os.fspath(repo_root), "rev-parse", "--verify", "HEAD^{commit}"],
            capture_output=True, timeout=COPY_PROOF_HEAD_TIMEOUT)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return None
    sha = proc.stdout.decode("utf-8", "replace").strip() if proc.returncode == 0 else ""
    return sha or None


def _check_copy_proof(state, cfg):
    """Check the configured copy proof once against the round-1 diff and the head commit, and store what it
    proved (each copy with its diff section's digest), what it rejected, and the head it was checked at. Writes
    nothing when there is no well-formed proof or no diff."""
    proof = cfg.get("copyProof")
    diff_text = cfg.get("diff")
    if not isinstance(diff_text, str) or countable_lines.proof_fault(proof) is not None:
        return
    repo_root = cfg.get("repoRoot") or os.getcwd()
    # A head that cannot be resolved is passed on as None, which the counter reads as unreadable for every copy.
    head = _resolve_head_commit(repo_root)
    proven, rejected = countable_lines.proven_copies(diff_text, repo_root, proof, head=head)
    state["provenCopies"] = [dict(copy, section=countable_lines.section_digest(diff_text, copy["file"]))
                             for copy in proven]
    state["copyProofRejected"] = rejected
    state["provenCopiesHead"] = head


def _finding_identity_key(finding):
    return session_contract.finding_identity_key(finding)


def _mint_finding_keys(findings):
    """Stamp findingKey on dict findings that lack a non-empty one; ensure list-wide uniqueness."""
    if not isinstance(findings, list):
        return findings
    entries = []
    for f in findings:
        if not isinstance(f, dict):
            continue
        minted = session_contract.minted_identity_key(f)
        bare = session_contract.location_key(f)
        preset_raw = f.get(session_contract.FINDING_KEY_FIELD)
        preset = preset_raw if isinstance(preset_raw, str) and preset_raw else None
        if preset is None:
            kind = "unkeyed"
            identity = minted
            legacy_key = None
        elif preset == minted:
            kind = "loop-owned"
            identity = minted
            legacy_key = None
        elif preset == bare and minted != bare:
            kind = "legacy-owned"
            identity = minted
            legacy_key = preset
        else:
            kind = "foreign"
            identity = preset
            legacy_key = None
        entries.append((f, kind, identity, legacy_key))
    by_identity = {}
    for idx, (f, kind, identity, legacy_key) in enumerate(entries):
        by_identity.setdefault(identity, []).append((idx, f, kind, legacy_key))
    claimants = {}
    for identity, group in by_identity.items():
        for _, f, kind, legacy_key in group:
            bare = session_contract.location_key(f)
            if kind in ("unkeyed", "loop-owned") and identity == bare:
                claimants.setdefault(bare, set()).add(identity)
            elif kind == "foreign":
                claimants.setdefault(identity, set()).add(identity)
            elif kind == "legacy-owned" and legacy_key:
                claimants.setdefault(legacy_key, set()).add(identity)
    for identity, group in by_identity.items():
        has_foreign = any(kind == "foreign" for _, _, kind, _ in group)
        if not has_foreign:
            legacy_keys = [lk for _, _, kind, lk in group if kind == "legacy-owned" and lk]
            # Parent build minted list-wide-unique keys; two bare legacy rows cannot come from
            # stored state — this branch is fail-closed hardening when claims collide.
            if legacy_keys and len(claimants.get(legacy_keys[0], set())) == 1:
                chosen_key = legacy_keys[0]
            else:
                chosen_key = identity
            for _, f, _, _ in group:
                f[session_contract.FINDING_KEY_FIELD] = chosen_key
        else:
            contents = {session_contract.finding_content_canonical(f) for _, f, _, _ in group}
            if len(group) == 1 or len(contents) == 1:
                for _, f, _, _ in group:
                    f[session_contract.FINDING_KEY_FIELD] = identity
            else:
                for _, f, _, _ in group:
                    f[session_contract.FINDING_KEY_FIELD] = (
                        identity + "#" + session_contract.content_hash_suffix(f))
    return findings


def _finding_key_of(finding):
    """Pure read of a finding's identity — the leaf's one derivation."""
    return session_contract.finding_identity_key(finding)


def _ensure_disposition_ledger_for_write(state):
    """Fold-time writer for ``dispositionLedger`` — not for terminal or certification reads."""
    ledger = state.get(session_contract.DISPOSITION_LEDGER_KEY)
    if not isinstance(ledger, list):
        ledger = []
        state[session_contract.DISPOSITION_LEDGER_KEY] = ledger
    return ledger


def _ledger_index_by_key(ledger):
    seen = {}
    for i, entry in enumerate(ledger):
        if isinstance(entry, dict):
            key = _finding_identity_key(entry)
            if key:
                seen[key] = i
    return seen


def _live_finding_by_key(state, key):
    for finding in state.get("findings") or []:
        if isinstance(finding, dict) and _finding_identity_key(finding) == key:
            return finding
    return None


def _strip_disposition_family(entry):
    return session_contract.strip_disposition_family(entry)


def _apply_disposition_family(target, family):
    session_contract.apply_disposition_family(target, family)


def _backfill_ledger_from_records(state, ledger, seen):
    """On first ledger-owner activation, seed missing keys from review-record history."""
    preexisting = set(seen)
    family_snapshots = {}
    for key in preexisting:
        idx = seen[key]
        entry = ledger[idx]
        if isinstance(entry, dict):
            family_snapshots[key] = session_contract.disposition_family_snapshot(entry)
    for rec in state.get("_records") or []:
        if not isinstance(rec, dict):
            continue
        for finding in rec.get("findings") or []:
            if not isinstance(finding, dict):
                continue
            key = _finding_identity_key(finding)
            if not key:
                continue
            entry = _strip_disposition_family(dict(finding))
            entry.pop(session_contract.RAISED_SEQ_FIELD, None)
            entry.pop(session_contract.DISPOSITION_SEQ_FIELD, None)
            if key in preexisting:
                entry.update(family_snapshots.get(key, {}))
            if key in seen:
                ledger[seen[key]] = entry
            else:
                seen[key] = len(ledger)
                ledger.append(entry)


def _seed_ledger_entry(state, ledger, seen, finding, key, round_no):
    """Seed (or re-seed) one finding's ledger entry — identity key, raisedRound, raisedSeq — and
    return the entry. A same-round disposition family already on the ledger entry is carried over;
    any other is stripped. Touches neither ``_toVerify`` nor the live findings."""
    existing = ledger[seen[key]] if key in seen else None
    entry = _strip_disposition_family(dict(finding))
    # axis: a grade a seat supplied is never seeded; only the verifier fold grades — see bite-proof record c1l7_wo_b_verifier_grade
    entry.pop(GRADE_FIELD, None)
    entry.pop(session_contract.RAISED_SEQ_FIELD, None)
    entry.pop(session_contract.DISPOSITION_SEQ_FIELD, None)
    entry[session_contract.RAISED_ROUND_FIELD] = round_no
    if (isinstance(existing, dict)
            and session_contract.has_disposition_family(existing)
            and existing.get("dispositionRound") == round_no):
        for field in session_contract.DISPOSITION_FAMILY_FIELDS:
            if field in existing:
                entry[field] = existing[field]
        if GRADE_FIELD in existing:  # a finding refuted earlier this round keeps the grade that closed it
            entry[GRADE_FIELD] = existing[GRADE_FIELD]
    else:
        entry = _strip_disposition_family(entry)
        entry.pop(session_contract.RAISED_SEQ_FIELD, None)
        entry.pop(session_contract.DISPOSITION_SEQ_FIELD, None)
        entry[session_contract.RAISED_ROUND_FIELD] = round_no
    if isinstance(existing, dict) and (
            not _disposition_is_current(existing) or _restaged_after(state, key, existing)
            or _undispatched_ruling(state, _live_ruling_by_key(state),
                                    {k: ledger[i] for k, i in seen.items()}, key) is not None):
        # An unresolved finding re-raised keeps a consequence it held: a later code-quality report
        # never turns a real one into a craft decision.
        entry["consequence"], entry["consequenceKind"] = finding_outcomes.merged_consequence(
            [existing, entry])
    entry[session_contract.RAISED_SEQ_FIELD] = _next_disposition_seq(state)
    held_runs = existing.get(break_it.RUNS_FIELD) if isinstance(existing, dict) else None
    if isinstance(held_runs, list):
        # axis: a finding raised again keeps the break-it runs it held; its new runs read after them, none twice
        new_runs = entry.get(break_it.RUNS_FIELD, [])
        if isinstance(new_runs, list):
            merged = list(held_runs)
            for run in new_runs:
                if run not in merged:
                    merged.append(run)
            entry[break_it.RUNS_FIELD] = merged
    if key in seen:
        ledger[seen[key]] = entry
    else:
        seen[key] = len(ledger)
        ledger.append(entry)
    return entry


def _seed_collapsed_nits(state, ledger, seen, finding, round_no):
    """Seed each Nit a summary row collapsed and record it ``craft`` at once; a row without members
    (or any other finding) seeds nothing."""
    members = finding.get("members") if finding.get("summaryEntry") else None
    if not isinstance(members, list):
        return
    for member in members:
        key = _finding_identity_key(member) if isinstance(member, dict) else None
        if not key:
            continue
        held = ledger[seen[key]] if key in seen else None
        live = _live_finding_by_key(state, key)
        if any(isinstance(h, dict) and h.get(review_findings_schema.CONSEQUENCE_KIND_KEY)
               != review_findings_schema.CODE_QUALITY for h in (held, live)):
            continue  # an already-held finding (ledger or live) with a real consequence keeps its owner path
        _seed_ledger_entry(state, ledger, seen, member, key, round_no)
        _record_disposition(
            state, key, "craft", round_no,
            settledReason="over the readout cap; code quality only: "
            + str(member.get(review_findings_schema.CONSEQUENCE_KEY) or "no consequence stated"))


class _LineageCarry:
    """A reworded finding takes the decision of the finding it rewords (``state["findingLineage"]``).

    The round's view: the keys raised this round (this compile's, plus every finding an earlier
    staging in the same round — the panel before a gap sweep — already seeded on the ledger), the
    count of those findings per (file, line), and the decided keys with the location their decision
    row records. ``apply`` carries only when ALL hold: the finding has no decision and no lineage
    entry of its own; exactly one lineage root holds a decision recorded at the finding's file and
    integer line, and that root's effective decision is guidance (a skip never carries); that root's
    group has no member raised this round; and the finding is the only finding raised this round at
    that file and line."""

    def __init__(self, state, compiled, ledger=None):
        self.compiled_keys = set()
        self.at_location = {}
        raised = {}
        unkeyed = []
        rows = []
        for finding in compiled:
            if not isinstance(finding, dict):
                continue
            rows.append(finding)
            # A Nit-cap summary row's collapsed members are raised this round too.
            members = finding.get("members") if finding.get("summaryEntry") else None
            if isinstance(members, list):
                rows.extend(m for m in members if isinstance(m, dict))
        for finding in rows:
            key = _finding_identity_key(finding)
            if key:
                raised.setdefault(key, finding)
            else:
                unkeyed.append(finding)
        round_no = state.get("round") if isinstance(state, dict) else None
        for entry in ledger if isinstance(ledger, list) else []:
            if not isinstance(entry, dict) or entry.get("summaryEntry"):
                continue
            if entry.get(session_contract.RAISED_ROUND_FIELD) != round_no:
                continue
            key = _finding_identity_key(entry)
            if key:
                raised.setdefault(key, entry)
        self.round_no = round_no
        self.raised = raised
        self.compiled_keys = set(raised)
        for finding in list(raised.values()) + unkeyed:
            location = self.location_of(finding)
            if location is not None:
                self.at_location[location] = self.at_location.get(location, 0) + 1
        rows, readable = _decision_candidates(state)
        self.readable = readable
        self.effective = _effective_decisions(state) if readable else {}
        self.decided = {}
        for index, row in enumerate(rows):
            key = row.get("findingKey")
            if isinstance(key, str) and key:
                held = self.decided.get(key)
                if held is None or _decision_order((index, row)) > _decision_order(held):
                    self.decided[key] = (index, row)

    @staticmethod
    def location_of(row):
        file = row.get("file")
        line = row.get("line")
        if isinstance(file, str) and file and _is_plain_int(line):
            return (file, line)
        return None

    def apply(self, state, finding, key):
        lineage = _lineage_map(state)
        if not self.readable or key in self.decided or key in lineage:
            return
        location = self.location_of(finding)
        if location is None or self.at_location.get(location) != 1:
            return
        roots = set()
        for decided_key, (_index, row) in self.decided.items():
            if self.location_of(row) == location:
                roots.add(_lineage_root(lineage, decided_key))
        if len(roots) != 1:
            return
        root = next(iter(roots))
        # Only a guidance decision carries. A skip (a ``rule`` out-of-scope ruling or an owner-gate
        # skip) never does: a location match does not prove the new finding is the one the owner
        # waived, so it is judged fresh — fixed, or left for the owner.
        effective = self.effective.get(root)
        if not isinstance(effective, dict) or effective.get("ruling") != "guidance":
            return
        group = {root} | {k for k in lineage if _lineage_root(lineage, k) == root}
        if group & self.compiled_keys:
            return
        state.setdefault("findingLineage", {})[key] = root
        state.setdefault("findingLineageRound", {})[key] = state.get("round")
        _decision(state, "ruling-carried",
                  "%s takes the decision on %s (same file and line, reworded)" % (key, root))

    def revoke_ambiguous(self, state):
        """Undo a carry an earlier staging of THIS round made, when the round's view now breaks
        one of its conditions — another finding raised at its file and line, or a member of its
        group (the decided original included) raised this round. A carry is provisional until the
        round's last staging; one from an earlier round stands. The inherited out-of-scope
        disposition goes with the revoked carry, so the finding is judged fresh."""
        lineage = _lineage_map(state)
        rounds = state.get("findingLineageRound")
        if not lineage or not isinstance(rounds, dict):
            return
        for key in sorted(lineage):
            if rounds.get(key) != self.round_no or key not in self.raised:
                continue
            root = _lineage_root(lineage, key)
            group = {root} | {k for k in lineage if _lineage_root(lineage, k) == root}
            location = self.location_of(self.raised[key])
            if (location is not None and self.at_location.get(location) == 1
                    and not ((group - {key}) & self.compiled_keys)):
                continue
            state["findingLineage"].pop(key, None)
            rounds.pop(key, None)
            lineage = _lineage_map(state)
            if _live_out_of_scope_ruling_for_key(state, key) is None:
                _clear_out_of_scope_disposition(state, key)
            _decision(state, "ruling-carry-revoked",
                      "%s no longer takes the decision on %s (a later staging this round raised "
                      "another finding at that place, or the original)" % (key, root))


def _ledger_out_of_scope_entry(ledger, seen, key):
    if not isinstance(key, str) or key not in seen:
        return None
    entry = ledger[seen[key]]
    if not isinstance(entry, dict) or entry.get("disposition") != "out-of-scope":
        return None
    return entry


def _ledger_out_of_scope_reason(ledger, seen, key):
    entry = _ledger_out_of_scope_entry(ledger, seen, key)
    return entry.get("outOfScopeReason") if entry is not None else None


def _ledger_follow_up(ledger, seen, key, *, reason=None):
    """The ``followUp`` an out-of-scope ledger entry holds for ``key``, else None; with ``reason``,
    only when that entry was recorded for a decision with that reason."""
    entry = _ledger_out_of_scope_entry(ledger, seen, key)
    if entry is None:
        return None
    if reason is not None and entry.get("outOfScopeReason") != reason:
        return None
    return _follow_up_of(entry)


def _follow_up_of(row):
    """A copy of the row's ``followUp`` when it holds one as an object, else None."""
    follow_up = row.get("followUp") if isinstance(row, dict) else None
    return dict(follow_up) if isinstance(follow_up, dict) else None


def _snapshot_earlier_pool(state):
    """Snapshot the PR's earlier findings once per round into ``state["_earlierPool"]``, before staging
    re-seeds (and strips the disposition of) a re-raised ledger row. Discloses a record the file did not give."""
    held = state.get("_earlierPool")
    if isinstance(held, dict) and held.get("round") == state["round"]:
        return
    cfg = state.get("config") if isinstance(state.get("config"), dict) else {}
    record = cfg.get("earlierFindings")
    state["_earlierPool"] = {"round": state["round"], "entries": repeat_marks.build_pool(
        state, state["round"], record if isinstance(record, list) else [])}
    reason = cfg.get("earlierFindingsUnavailable") or ("not-supplied" if record is None else None)
    if reason:
        _record_round(state, "earlierFindingsUnavailable", reason)


def _earlier_pool(state):
    """The round's earlier-findings pool (entries with their ``eN`` refs), as snapshotted before staging."""
    held = state.get("_earlierPool")
    entries = held.get("entries") if isinstance(held, dict) else None
    return [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []


def _stage_findings(state, compiled):
    """The only writer of ``_toVerify`` — seeds one ledger entry per compiled candidate. Each member
    a Nit-cap summary row collapsed is seeded too and recorded ``craft`` at once."""
    if not isinstance(compiled, list):
        state["_toVerify"] = compiled
        return
    ledger = _ensure_disposition_ledger_for_write(state)
    _snapshot_earlier_pool(state)
    seen = _ledger_index_by_key(ledger)
    owner_class = session_contract.disposition_ledger_owner_classification(state)
    first_ledger_owner = owner_class == session_contract.DISPOSITION_LEDGER_OWNER_ABSENT
    if first_ledger_owner:
        _backfill_ledger_from_records(state, ledger, seen)
    round_no = state["round"]
    seeded = False
    sanitized = []
    carry = _LineageCarry(state, compiled, ledger)
    carry.revoke_ambiguous(state)
    for finding in compiled:
        if not isinstance(finding, dict):
            sanitized.append(finding)
            continue
        key = _finding_identity_key(finding)
        if not key:
            # No ledger entry to seed, but a seat's grade must not reach `_toVerify` either.
            sanitized.append({k: v for k, v in finding.items() if k != GRADE_FIELD}
                             if GRADE_FIELD in finding else finding)
            continue
        carry.apply(state, finding, key)
        held_follow_up = _ledger_follow_up(ledger, seen, key)
        held_reason = _ledger_out_of_scope_reason(ledger, seen, key)
        entry = _seed_ledger_entry(state, ledger, seen, finding, key, round_no)
        sanitized.append(entry)
        live_oos = _live_out_of_scope_ruling_for_key(state, key)
        if live_oos is not None and not _live_out_of_scope_blocks_row(entry):
            # Only a legacy decision row — an unsequenced gate skip, written before skips carried
            # their follow-up — recovers one from the ledger, and only from an entry recorded for
            # that same decision (its reason): this key's own (read before the re-seed stripped
            # it), else the decided key's. A sequenced decision without a follow-up keeps none.
            follow_up = _follow_up_of(live_oos)
            if (follow_up is None and live_oos.get("source") == "gate"
                    and not _is_plain_int(live_oos.get("seq"))):
                reason = live_oos.get("reason")
                follow_up = (held_follow_up if held_reason == reason else None)
                if follow_up is None:
                    follow_up = _ledger_follow_up(ledger, seen, live_oos.get("findingKey"),
                                                  reason=reason)
            _record_disposition(
                state, key, "out-of-scope", round_no,
                outOfScopeReason=live_oos.get("reason"),
                followUp=follow_up,
                rulingSeq=live_oos.get("seq"))
        _seed_collapsed_nits(state, ledger, seen, finding, round_no)
        seeded = True
    state["_toVerify"] = sanitized
    if seeded:
        state[session_contract.DISPOSITION_LEDGER_OWNER_FIELD] = (
            session_contract.DISPOSITION_LEDGER_OWNER_VALUE
        )


def _next_disposition_seq(state):
    counter = state.get("dispositionSeqCounter", 0) + 1
    state["dispositionSeqCounter"] = counter
    return counter


def _next_ruling_seq(state):
    counter = state.get("rulingSeqCounter", 0) + 1
    state["rulingSeqCounter"] = counter
    return counter


def _stamp_ruling_seq(state, entry):
    """Stamp an owner-gate decision with ``rulingSeq`` from the counter the ``rule`` verb uses, so the
    two decision sources share one sequence. A malformed counter leaves the entry unsequenced (older
    than every sequenced decision) rather than failing the fold."""
    if _ruling_seq_counter_fault(state) is None:
        entry["rulingSeq"] = _next_ruling_seq(state)


def _read_rulings_log(state):
    """Pure read of ``rulingsLog`` — never mutates ``state``.

    Returns ``(rows, None)`` or ``([], (token, detail))`` when malformed."""
    if not isinstance(state, dict):
        return [], (RULINGS_LOG_MALFORMED, "state must be an object")
    if "rulingsLog" not in state:
        return [], None
    log = state["rulingsLog"]
    if not isinstance(log, list):
        return [], (RULINGS_LOG_MALFORMED, "rulingsLog must be a list")
    rows = []
    for entry in log:
        if not isinstance(entry, dict):
            return [], (RULINGS_LOG_MALFORMED, "rulingsLog row must be an object")
        key = entry.get("findingKey")
        if not isinstance(key, str) or not key:
            return [], (RULINGS_LOG_MALFORMED, "rulingsLog row lacks findingKey")
        rows.append(dict(entry))
    return rows, None


def _ruling_seq_counter_fault(state):
    """Return ``(token, detail)`` when ``rulingSeqCounter`` is present but not a non-negative int."""
    if not isinstance(state, dict) or "rulingSeqCounter" not in state:
        return None
    counter = state["rulingSeqCounter"]
    if not isinstance(counter, int) or counter < 0:
        return (RULINGS_LOG_MALFORMED, "rulingSeqCounter must be a non-negative integer")
    return None


def _writable_rulings_log(state):
    """Append target for ``rulingsLog`` — only after precondition reads pass."""
    log = state.get("rulingsLog")
    if log is None:
        log = []
        state["rulingsLog"] = log
    return log


def _lineage_map(state):
    """``{key: rootKey}`` from ``state["findingLineage"]`` — malformed entries read as absent."""
    raw = state.get("findingLineage") if isinstance(state, dict) else None
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items()
            if isinstance(k, str) and k and isinstance(v, str) and v}


def _holds_out_of_scope_disposition(state, key):
    """True when the live finding or the ledger entry for ``key`` holds an out-of-scope disposition."""
    live = _live_finding_by_key(state, key)
    if isinstance(live, dict) and live.get("disposition") == "out-of-scope":
        return True
    ledger_by_key, fault = _disposition_ledger_by_key(state)
    if fault is not None:
        return False
    stored = ledger_by_key.get(key)
    return isinstance(stored, dict) and stored.get("disposition") == "out-of-scope"


def _lineage_group(state, key):
    """Every key sharing ``key``'s lineage root (``key`` and the root included), sorted."""
    lineage = _lineage_map(state)
    root = _lineage_root(lineage, key)
    return sorted({key, root} | {k for k in lineage if _lineage_root(lineage, k) == root})


def _lineage_root(lineage, key):
    """The root of ``key``: itself when absent from the lineage; a cycle reads as its own root."""
    root = key
    for _ in range(len(lineage) + 1):
        nxt = lineage.get(root)
        if nxt is None or nxt == root:
            return root
        root = nxt
    return key


def _is_plain_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _gate_decision_candidates(state):
    """Owner-gate decisions across every round's ``judgmentDispositions``, shaped like ruling rows.

    ``skip`` is an ``out-of-scope`` decision (carrying its ``followUp`` when the fold recorded one),
    ``fix-with-guidance`` a ``guidance`` decision (a ``fix`` decision when it carries no guidance
    text), and ``fix-as-suggested`` a ``fix`` decision — the owner's choice to fix as suggested, which supersedes an earlier skip or
    guidance and itself neither excludes nor guides; every other gate disposition is not a
    decision."""
    rounds = state.get("rounds") if isinstance(state, dict) else None
    if not isinstance(rounds, dict):
        return []
    out = []
    for rnd_key in sorted(rounds.keys(), key=_round_record_sort_key):
        round_entry = rounds[rnd_key]
        if not isinstance(round_entry, dict):
            continue
        try:
            rnd_num = int(rnd_key)
        except (TypeError, ValueError):
            continue
        log = round_entry.get("judgmentDispositions")
        if not isinstance(log, list):
            continue
        for item in log:
            if not isinstance(item, dict):
                continue
            disposition = item.get("disposition")
            if disposition == "skip":
                ruling = "out-of-scope"
            elif disposition == "fix-with-guidance":
                ruling = "guidance"
            elif disposition == "fix-as-suggested":
                ruling = "fix"
            else:
                continue
            key = _history_row_key(item)
            if not key:
                continue
            row = {"findingKey": key, "ruling": ruling, "reason": item.get("reason"),
                   "seq": item.get("rulingSeq") if _is_plain_int(item.get("rulingSeq")) else None,
                   "round": rnd_num, "source": "gate"}
            if ruling == "guidance":
                guidance = item.get(GATE_GUIDANCE_RECORD_KEY)
                if isinstance(guidance, str) and guidance.strip():
                    row["guidance"] = guidance.strip()
                else:
                    # fix-with-guidance with no usable text is a fix decision: it still
                    # supersedes earlier guidance rather than letting that guidance return.
                    row["ruling"] = "fix"
            if ruling == "out-of-scope" and _follow_up_of(item) is not None:
                session_contract.copy_follow_up_field(item, row)
            for field in ("file", "line", "title", "severity"):
                if item.get(field) is not None:
                    row[field] = item.get(field)
            out.append(row)
    return out


def _decision_candidates(state, *, with_rules=True):
    """``(rows, readable)``: every ``rulingsLog`` row (``source: "rule"``) and every owner-gate
    decision, in log order. ``readable`` is False — and ``rows`` empty — when ``rulingsLog`` is
    malformed; ``with_rules=False`` reads the gate decisions alone."""
    rows = []
    if with_rules:
        rule_rows, fault = _read_rulings_log(state)
        if fault is not None:
            return [], False
        for entry in rule_rows:
            entry["source"] = "rule"
            rows.append(entry)
    rows.extend(_gate_decision_candidates(state))
    return rows, True


def _decision_order(indexed_row):
    """Sort key for the one sequence: a sequenced decision outranks every unsequenced one; among
    unsequenced decisions the later round wins; a remaining tie goes to the later row."""
    index, row = indexed_row
    seq = row.get("seq")
    rnd = row.get("round")
    return (1 if _is_plain_int(seq) else 0,
            seq if _is_plain_int(seq) else 0,
            rnd if _is_plain_int(rnd) else -1,
            index)


def _effective_decisions(state, *, with_rules=True):
    """``{key: row}``: the one effective decision for every finding key that has one.

    Invariant: for every finding the loop holds there is exactly ONE effective decision — the
    latest one by a single sequence (``rulingSeq`` from ``_next_ruling_seq``, shared by the ``rule``
    verb and the owner-judgment gate fold; a gate entry with no sequence is older than every
    sequenced decision, and among those the later round wins) — read through this one reader.
    A guidance or fix decision binds the finding under any wording a later round gives it at the
    same location (``state["findingLineage"]``, written by ``_stage_findings``): it is the decision of
    every key of the lineage group. An out-of-scope decision (a skip) binds only the key it was given
    on — through a lineage it never reaches another member, which reads the latest decision that does
    reach it. The fixer order renders only the effective decision."""
    rows, readable = _decision_candidates(state, with_rules=with_rules)
    if not readable:
        return {}
    lineage = _lineage_map(state)
    groups = {}
    for indexed in enumerate(rows):
        key = indexed[1].get("findingKey")
        if not isinstance(key, str) or not key:
            continue
        groups.setdefault(_lineage_root(lineage, key), []).append(indexed)
    by_key = {}
    for key in set(lineage) | {indexed[1]["findingKey"] for group in groups.values()
                               for indexed in group}:
        best = None
        for indexed in groups.get(_lineage_root(lineage, key), []):
            row = indexed[1]
            if row.get("ruling") == "out-of-scope" and row.get("findingKey") != key:
                continue  # a skip stays on the finding it was given on
            if best is None or _decision_order(indexed) > _decision_order(best):
                best = indexed
        if best is not None:
            by_key[key] = best[1]
    return by_key


def _live_ruling_by_key(state):
    """The effective decision per finding key (``{key: row}``) — see ``_effective_decisions``.
    An unreadable ``rulingsLog`` reads as ``{}``."""
    return _effective_decisions(state)


def _live_out_of_scope_ruling_for_key(state, key):
    if not isinstance(key, str) or not key:
        return None
    live = _live_ruling_by_key(state).get(key)
    if isinstance(live, dict) and live.get("ruling") == "out-of-scope":
        return live
    return None


def _live_out_of_scope_blocks_row(row):
    """True when a live out-of-scope ruling may exclude or restage this row (never Critical)."""
    if not isinstance(row, dict):
        return False
    sev = row.get("severity")
    return circuit_breaker.is_critical(sev)


def _live_out_of_scope_ruling_keys(state):
    keys = set()
    for key, entry in _live_ruling_by_key(state).items():
        if entry.get("ruling") == "out-of-scope":
            keys.add(key)
    return keys


def _append_round_rulings(state, rows):
    rec = state["rounds"].setdefault(str(state["round"]), {})
    prev = rec.get("rulings")
    if not isinstance(prev, list):
        prev = []
    rec["rulings"] = prev + list(rows)


def _record_disposition(state, key, disposition, round_no, *, clear_out_of_scope=False, **fields):
    if clear_out_of_scope:
        if not isinstance(key, str) or not key:
            return
        live = _live_finding_by_key(state, key)
        if isinstance(live, dict) and live.get("disposition") == "out-of-scope":
            for field in session_contract.DISPOSITION_FAMILY_FIELDS:
                live.pop(field, None)
            live.pop(session_contract.DISPOSITION_SEQ_FIELD, None)
        ledger_by_key, fault = _disposition_ledger_by_key(state)
        if fault is not None:
            return
        entry = ledger_by_key.get(key)
        if not isinstance(entry, dict) or entry.get("disposition") != "out-of-scope":
            return
        ledger = _ensure_disposition_ledger_for_write(state)
        seen = _ledger_index_by_key(ledger)
        if key not in seen:
            return
        stored = ledger[seen[key]]
        if not isinstance(stored, dict) or stored.get("disposition") != "out-of-scope":
            return
        cleared = _strip_disposition_family(dict(stored))
        cleared.pop(session_contract.DISPOSITION_SEQ_FIELD, None)
        ledger[seen[key]] = cleared
        return
    if disposition not in session_contract.DISPOSITIONS:
        raise ValueError("unknown disposition %r" % (disposition,))
    disp_seq = _next_disposition_seq(state)
    ledger = _ensure_disposition_ledger_for_write(state)
    seen = _ledger_index_by_key(ledger)
    live = _live_finding_by_key(state, key)
    if key in seen and isinstance(ledger[seen[key]], dict):
        entry = dict(ledger[seen[key]])
    elif live is not None:
        entry = dict(live)
        entry[session_contract.RAISED_ROUND_FIELD] = state.get("round", round_no)
    else:
        entry = {session_contract.FINDING_KEY_FIELD: key}
    family = {"disposition": disposition, "dispositionRound": round_no}
    for fname, val in fields.items():
        if val is not None:
            family[fname] = val
    _apply_disposition_family(entry, family)
    entry[session_contract.DISPOSITION_SEQ_FIELD] = disp_seq
    if key in seen:
        ledger[seen[key]] = entry
    else:
        ledger.append(entry)
    if live is not None:
        _apply_disposition_family(live, family)
        live[session_contract.DISPOSITION_SEQ_FIELD] = disp_seq


def _record_grade(state, key, grade):
    """Set the verifier's ``grade`` on the finding's ledger entry (created when the key has none) and
    on its live finding when there is one. A non-dict grade or an empty key writes nothing."""
    if not isinstance(grade, dict) or not isinstance(key, str) or not key:
        return
    ledger = _ensure_disposition_ledger_for_write(state)
    seen = _ledger_index_by_key(ledger)
    live = _live_finding_by_key(state, key)
    if key in seen and isinstance(ledger[seen[key]], dict):
        entry = dict(ledger[seen[key]])
    elif live is not None:
        entry = dict(live)
        entry[session_contract.RAISED_ROUND_FIELD] = state.get("round")
    else:
        entry = {session_contract.FINDING_KEY_FIELD: key}
    entry[GRADE_FIELD] = dict(grade)
    if key in seen:
        ledger[seen[key]] = entry
    else:
        ledger.append(entry)
    if live is not None:
        live[GRADE_FIELD] = dict(grade)


def _clear_grade(state, key):
    """Drop a grade from the finding's ledger entry and its live finding. A finding the current
    verification left ungraded must not keep a grade an earlier raise earned."""
    if not isinstance(key, str) or not key:
        return
    ledger = _ensure_disposition_ledger_for_write(state)
    seen = _ledger_index_by_key(ledger)
    if key in seen and isinstance(ledger[seen[key]], dict) and GRADE_FIELD in ledger[seen[key]]:
        entry = dict(ledger[seen[key]])
        entry.pop(GRADE_FIELD, None)
        ledger[seen[key]] = entry
    live = _live_finding_by_key(state, key)
    if live is not None:
        live.pop(GRADE_FIELD, None)


def _clear_out_of_scope_disposition(state, key):
    """Drop a live out-of-scope disposition family; rulingsLog retains the history."""
    _record_disposition(state, key, None, 0, clear_out_of_scope=True)


def _record_merged_into(state, key, into_key):
    ledger = _ensure_disposition_ledger_for_write(state)
    seen = _ledger_index_by_key(ledger)
    live = _live_finding_by_key(state, key)
    if key in seen and isinstance(ledger[seen[key]], dict):
        entry = dict(ledger[seen[key]])
    elif live is not None:
        entry = dict(live)
        entry[session_contract.RAISED_ROUND_FIELD] = state.get("round", state["round"])
    else:
        entry = {session_contract.FINDING_KEY_FIELD: key}
    family = {session_contract.MERGED_INTO_FIELD: into_key}
    _apply_disposition_family(entry, family)
    if key in seen:
        ledger[seen[key]] = entry
    else:
        ledger.append(entry)
    if live is not None:
        _apply_disposition_family(live, family)


# ---- terminal chokepoint + end-of-loop settle -------------------------------------------------

def _set_terminal(state, verdict, *, cap=False):
    """The one writer of the loop's terminal verdict: set it, then give every finding the review
    took in an outcome (`_settle_open_findings`). `cap` marks a stop at a round cap. A `verdict` of
    `None` reopens the session and settles nothing."""
    state["terminal"] = verdict
    if verdict is not None:
        _settle_open_findings(state, cap=cap)


def _decision_sources(state):
    """The `sources` dict `finding_outcomes.on_record` reads: the Canon text and the ratified
    residuals. A source that cannot be read is left out — an unresolvable decision is not on record."""
    config = state.get("config") if isinstance(state.get("config"), dict) else {}
    return finding_outcomes.decision_sources(config.get("repoRoot"), config.get("baseRef"))


def _compile_drop_recorded(state, drop):
    rounds = state.get("rounds")
    for rec in (rounds.values() if isinstance(rounds, dict) else ()):
        recorded = rec.get("compileDrops") if isinstance(rec, dict) else None
        if isinstance(recorded, list) and drop in recorded:
            return True
    return False


def _seed_pending_new_issues(state):
    """Compile the auditors' new issues that never reached the ledger and seed the survivors, so a
    terminal reached before they were folded still settles them. Drops are recorded once."""
    pending = state.get("_newIssues")
    pending = [ni for ni in pending if isinstance(ni, dict)] if isinstance(pending, list) else []
    if not pending:
        return
    compiled, drops = mechanical_compile(pending, state.get("reviewedDiff"))
    _record_compile_drops(state, [d for d in drops if not _compile_drop_recorded(state, d)])
    ledger = _ensure_disposition_ledger_for_write(state)
    seen = _ledger_index_by_key(ledger)
    round_no = state["round"]
    seeded = False
    for finding in compiled:
        _seed_collapsed_nits(state, ledger, seen, finding, round_no)
        key = _finding_identity_key(finding)
        if finding.get("summaryEntry") or not key:
            continue
        # A pending issue is unprocessed whatever its identity: re-seed it over any entry that
        # shares the key, which drops that entry's disposition (the re-raise outranks it).
        _seed_ledger_entry(state, ledger, seen, finding, key, round_no)
        seeded = True
    state.pop("_newIssues", None)  # seeded once: a second settle finds nothing pending
    if seeded:
        state[session_contract.DISPOSITION_LEDGER_OWNER_FIELD] = (
            session_contract.DISPOSITION_LEDGER_OWNER_VALUE)


def _newest_content(row, live):
    """The live copy, unless the ledger row was raised after it (staged, not yet synthesized)."""
    if not isinstance(live, dict):
        return row
    live_seq = live.get(session_contract.RAISED_SEQ_FIELD)
    row_seq = row.get(session_contract.RAISED_SEQ_FIELD)
    if (isinstance(live_seq, int) and not isinstance(live_seq, bool)
            and isinstance(row_seq, int) and not isinstance(row_seq, bool) and row_seq > live_seq):
        kind_key = review_findings_schema.CONSEQUENCE_KIND_KEY
        cq = review_findings_schema.CODE_QUALITY
        if live.get(kind_key) != cq and row.get(kind_key) == cq:
            return live  # a newer code-quality report never replaces a consequence the owner decides
        return row
    return live


def _disposition_is_current(row):
    """True when row carries a known disposition newer than the finding's last raise."""
    disp = row.get("disposition")
    disp_seq = row.get(session_contract.DISPOSITION_SEQ_FIELD)
    raised_seq = row.get(session_contract.RAISED_SEQ_FIELD)
    return (disp in session_contract.DISPOSITIONS and disp != "out-of-scope"
            and isinstance(disp_seq, int) and not isinstance(disp_seq, bool)
            and isinstance(raised_seq, int) and not isinstance(raised_seq, bool)
            and disp_seq > raised_seq)


def _restaged_after(state, key, row):
    """True when an owner ruling sent the finding back to a fixer after ``row``'s disposition: that
    disposition is the one the ruling reopened, so it no longer settles the finding."""
    mark = (state.get("restagedAfterDispositionSeq") or {}).get(key)
    seq = row.get(session_contract.DISPOSITION_SEQ_FIELD)
    return _is_plain_int(mark) and _is_plain_int(seq) and seq <= mark


def _skip_settle(state, fault):
    token = getattr(fault, "token", None) or "ledger-fault"
    detail = getattr(fault, "detail", None) or str(fault)
    # A state field, not a decision: the last decision is the terminal's cause and must stay put.
    state["settleSkipped"] = {"token": token, "detail": detail}


def _settle_open_findings(state, cap=False):
    """Give every finding the review took in exactly one outcome once the loop has ended.

    A finding that is fixed or refuted (and not re-raised since) keeps it, and a finding merged
    into another follows that one. Every other finding — no disposition, a stale one, or
    out-of-scope — is settled by `finding_outcomes.settle` and written through `_record_disposition`.
    Severity is never passed on. Idempotent: a second call finds nothing left to settle."""
    ledger_by_key, fault = _disposition_ledger_by_key(state)
    if fault is None and session_contract.disposition_ledger_owner_classification(state) \
            == session_contract.DISPOSITION_LEDGER_OWNER_ABSENT:
        _, fault = session_contract.read_disposition_ledger(state, required=False)
    if fault is not None:
        _skip_settle(state, fault)
        return
    _seed_pending_new_issues(state)
    ledger_by_key, fault = _disposition_ledger_by_key(state)
    if fault is not None:
        _skip_settle(state, fault)
        return
    live_by_key = {}
    for finding in state.get("findings") or []:
        key = _finding_identity_key(finding) if isinstance(finding, dict) else None
        if key and not finding.get("summaryEntry"):
            live_by_key.setdefault(key, finding)
    rulings = _live_ruling_by_key(state)
    verdict = state.get("terminal")
    if cap:
        why_open = "still open when the loop reached its round cap"
    elif verdict == "converged":
        why_open = "left unfixed when the review loop converged"
    else:
        why_open = "still open when the review loop ended (" + str(verdict) + ")"
    todo = []
    for key in list(ledger_by_key) + [k for k in live_by_key if k not in ledger_by_key]:
        row = ledger_by_key.get(key) or live_by_key[key]
        if not isinstance(row, dict) or row.get("summaryEntry") or row.get(session_contract.MERGED_INTO_FIELD):
            continue
        pending = _undispatched_ruling(state, rulings, ledger_by_key, key)
        if _disposition_is_current(row) and not _restaged_after(state, key, row) and pending is None:
            continue
        todo.append((key, row, _newest_content(row, live_by_key.get(key))))
    if not todo:
        return
    sources = {}
    bound = {key: _row_decision(state, rulings, ledger_by_key, key) or rulings.get(key)
             for key, _, _ in todo}
    if any(session_contract.decided_by_of(bound[key]) for key, _, _ in todo):
        try:
            sources = _decision_sources(state)
        except Exception:  # noqa: BLE001 — fail closed: no sources, nothing on record
            sources = {}
        if not isinstance(sources, dict):
            sources = {}
    for key, row, content in todo:
        reason = why_open
        pending = _undispatched_ruling(state, rulings, ledger_by_key, key)
        if pending is not None:
            reason = "owner ruling %s (%s) was recorded but never sent to a fixer; %s" % (
                pending["seq"], pending["ruling"], why_open)
        # a newer guidance decision on a merged member binds the finding over the older skip;
        # with no bound decision at all the out-of-scope reason stands
        if (row.get("disposition") == "out-of-scope" and pending is None
                and (not bound[key] or bound[key].get("ruling") == "out-of-scope")):
            reason = "out of scope: " + str(row.get("outOfScopeReason")) + "; " + why_open
        result = finding_outcomes.settle(
            content, ruling=bound[key], sources=sources, open_reason=reason)
        live = live_by_key.get(key)
        if content is row and live is not None and live is not row:
            # The newer staged report outranks the live copy: the owner record reads live content first.
            live.update({k: v for k, v in row.items()
                         if k not in session_contract.DISPOSITION_FAMILY_FIELDS})
        carried = {}
        if row.get("disposition") == "out-of-scope":
            carried = {name: row[name] for name in ("outOfScopeReason", "followUp") if name in row}
        _record_disposition(state, key, result["outcome"], state["round"],
                            settledReason=result["reason"], decidedBy=result["decidedBy"], **carried)


def _fixed_disposition_receipt(state, session_dir, finding_key, target=None):
    cfg = state.get("config") or {}
    head = cfg.get(FIX_FOLD_HEAD_KEY) if isinstance(cfg, dict) else None
    if isinstance(head, str) and head:
        return {"headSha": head}
    return {}


def _fixed_ledger_rows(state):
    """Fixed disposition-ledger rows as ordered (key, entry) pairs plus the by_key map.

    A pure read: under a recognized owner a malformed ledger yields no rows and is never
    repaired here. Legacy (owner-absent) ledgers skip malformed rows instead."""
    owner = session_contract.disposition_ledger_owner_classification(state)
    if owner == session_contract.DISPOSITION_LEDGER_OWNER_ABSENT:
        rows = []
        by_key = {}
        for key, entry in session_contract.legacy_disposition_ledger_rows(state):
            if not isinstance(entry, dict) or entry.get("disposition") != "fixed":
                continue
            rows.append((key, entry))
            by_key[key] = entry
        return rows, by_key, None
    required = owner == session_contract.DISPOSITION_LEDGER_OWNER_RECOGNIZED
    ledger_rows, fault = session_contract.read_disposition_ledger(state, required=required)
    if fault is not None:
        return [], {}, fault
    seen = _ledger_index_by_key(ledger_rows)
    by_key = {
        key: ledger_rows[idx]
        for key, idx in seen.items()
        if isinstance(ledger_rows[idx], dict)
    }
    rows = []
    for key, idx in list(seen.items()):
        entry = ledger_rows[idx]
        if not isinstance(entry, dict) or entry.get("disposition") != "fixed":
            continue
        rows.append((key, entry))
    return rows, by_key, None


def _archive_departures(state, departing):
    """Write every departing keyed finding into dispositionLedger (replace-by-key)."""
    if not departing:
        return
    ledger = _ensure_disposition_ledger_for_write(state)
    seen = _ledger_index_by_key(ledger)
    for finding in departing:
        if not isinstance(finding, dict):
            continue
        key = _finding_identity_key(finding)
        if not key:
            continue
        replacement = dict(finding)
        if key in seen and isinstance(ledger[seen[key]], dict):
            prior = ledger[seen[key]]
            raised_round = replacement.get(session_contract.RAISED_ROUND_FIELD)
            if raised_round is None:
                raised_round = prior.get(session_contract.RAISED_ROUND_FIELD)
            if prior.get("dispositionRound") == raised_round:
                for field in session_contract.DISPOSITION_FAMILY_FIELDS:
                    if field in prior and field not in replacement:
                        replacement[field] = prior[field]
            raised = session_contract.RAISED_ROUND_FIELD
            if raised in prior and raised not in replacement:
                replacement[raised] = prior[raised]
            prior_runs = prior.get(break_it.RUNS_FIELD)
            if isinstance(prior_runs, list):
                # axis: a live row older than the ledger entry never overwrites the runs the ledger accumulated (changedWhy included)
                live_runs = replacement.get(break_it.RUNS_FIELD)
                merged = list(live_runs) if isinstance(live_runs, list) else []
                extra = [run for run in prior_runs if run not in merged]
                if extra:
                    replacement[break_it.RUNS_FIELD] = merged + extra
                    if isinstance(prior.get(break_it.RUN_FIELD), dict):
                        replacement[break_it.RUN_FIELD] = prior[break_it.RUN_FIELD]
                        # axis: the kept run stamp and the test text it ran come from the same ledger row
                        if "suggestion" in prior:
                            replacement["suggestion"] = prior["suggestion"]
        if key in seen:
            ledger[seen[key]] = replacement
        else:
            seen[key] = len(ledger)
            ledger.append(replacement)


def _set_findings(state, new_findings):
    """The only assignment site for state['findings'] — archives disposition-bearing departures."""
    prior = state.get("findings") or []
    if not isinstance(prior, list):
        prior = []
    new_list = list(new_findings) if new_findings is not None else []
    _mint_finding_keys(new_list)
    merged_by_key = {}
    for finding in new_list:
        if not isinstance(finding, dict):
            continue
        key = _finding_identity_key(finding)
        if not key:
            continue
        if key in merged_by_key:
            merged_by_key[key] = _merge_same_finding(merged_by_key[key], finding)
        else:
            merged_by_key[key] = finding
    if merged_by_key:
        seen_keys = set()
        compact = []
        for finding in new_list:
            if not isinstance(finding, dict):
                compact.append(finding)
                continue
            key = _finding_identity_key(finding)
            if not key:
                compact.append(finding)
                continue
            if key in seen_keys:
                continue
            seen_keys.add(key)
            compact.append(merged_by_key[key])
        new_list = compact
    new_keys = set()
    for finding in new_list:
        if isinstance(finding, dict):
            key = _finding_identity_key(finding)
            if key:
                new_keys.add(key)
    departing = []
    for finding in prior:
        if not isinstance(finding, dict):
            continue
        key = _finding_identity_key(finding)
        if key and key not in new_keys:
            departing.append(finding)
    _archive_departures(state, departing)
    state["findings"] = new_list


def _park_finding_key(finding):
    """Stable dedupe identity for the park-time findings merge — the leaf's per-location key, so two
    same-title candidates at different lines stay distinct. Returns None when no key can be derived,
    and an unidentifiable candidate is KEPT rather than dropped: a halted receipt owes
    over-reporting before under-reporting."""
    if not isinstance(finding, dict):
        return None
    try:
        return session_contract.finding_identity_key(finding)
    except Exception:
        return None


def _seed_findings_before_record_park(state):
    # A park between a fold and synthesis leaves that round's compiled candidates in _toVerify
    # only. On round 1 `findings` is empty and this is a copy; on a DELTA or GAP-SWEEP fold
    # `findings` already carries the prior round's open findings while `_toVerify` holds this
    # round's FRESH candidates — so this merges rather than assigns, or the halted receipt
    # under-reports exactly the candidates the round just gathered.
    fresh = state.get("_toVerify")
    if not isinstance(fresh, list) or not fresh:
        return
    existing = state.get("findings") or []
    seen = set()
    key_to_idx = {}
    for idx, f in enumerate(existing):
        key = _park_finding_key(f)
        if key is not None:
            seen.add(key)
            key_to_idx[key] = idx
    merged = list(existing)
    for f in fresh:
        key = _park_finding_key(f)
        if key is not None and key in seen:
            prior_idx = key_to_idx.get(key)
            if prior_idx is not None:
                prior = merged[prior_idx]
                if circuit_breaker.severity_rank(f.get("severity")) \
                        < circuit_breaker.severity_rank(prior.get("severity")):
                    replacement = dict(f)
                    replacement["dimension"] = panel_tally._merge_dims(prior, f)
                    replacement["tradeoff"] = bool(prior.get("tradeoff") or f.get("tradeoff"))
                    merged[prior_idx] = replacement
            continue
        if key is not None:
            seen.add(key)
            key_to_idx[key] = len(merged)
        merged.append(f)
    _set_findings(state, merged)


def _round_records_payload(state, config):
    """The ONE producer of the outgoing round-records list (#1196 WO-B).

    Returns a tagged outcome: ``nothing`` (no path, or an empty ledger) or
    ``ready`` (path + this session's full records list for ``records_bytes``). The list is built
    from the in-memory ledger alone; the file at ``path`` is never opened."""
    path = config.get("recordsPath")
    if not path:
        return {"outcome": "nothing"}

    outgoing = []
    for record in state.get("_records") or []:
        if not isinstance(record, dict):
            continue
        durable = review_memory.summarize_record(record)
        # A `1.0` round must not silently persist no disclosures: the key spelling is the shared
        # `_round_disclosure_key`.
        rkey = _round_disclosure_key(record.get("round"))
        block = _declared_disclosures(state["rounds"].get(rkey) or {}) if rkey else {}
        if block:
            durable[review_memory.DISCLOSURES_FIELD] = block
        outgoing.append(durable)
    outgoing.sort(key=lambda r: r.get("round") if isinstance(r.get("round"), int) else 0)
    if not outgoing:
        return {"outcome": "nothing"}
    # Single merge: when the ledger holds two records for one round the later one wins, so
    # CLI-path bytes and library-path bytes agree.
    record = outgoing[-1]
    outgoing = [r for r in outgoing[:-1] if r.get("round") != record.get("round")]
    outgoing.append(record)
    outgoing.sort(key=lambda r: r.get("round") if isinstance(r.get("round"), int) else 0)
    return {"outcome": "ready", "path": path, "records": outgoing}


def _persist_round_records(state, config):
    """Keep the round-records export equal to the in-memory ledger, disclosures included.

    Runs after every folded phase in `run_loop` when `recordsPath` is set. The file is written
    whole in one atomic write, replacing whatever was there, and is never read. A run that could
    not persist its disclosures must park `cannot-certify` — the degraded line in a terminal
    receipt lives only in the current run, so certifying after a failed write would recreate the
    quiet-evidence-loss class #720 closes."""
    payload = _round_records_payload(state, config)
    if payload["outcome"] == "nothing":
        return
    path = payload["path"]
    try:
        round_commit.atomic_write_bytes(path, review_memory.records_bytes(payload["records"]))
    except OSError as exc:
        _seed_findings_before_record_park(state)
        _park_cannot_certify(
            state,
            "durable round records at %s could not be persisted (%s)"
            % (path, exc))


def load_state(session_dir):
    """(ok, state_or_reason). A missing file → (True, None) fresh. A v1 file is REFUSED — session
    dirs are per-invocation, there is no migration; the caller must start fresh.

    #723: every member of `SUPPORTED_STATE_VERSIONS` is accepted — `SCHEMA_VERSION` (2, an in-flight
    session) through `STATE_SCHEMA_VERSION` (the current mint version) — and a loaded state is
    returned EXACTLY as it was persisted: `schemaVersion` is never rewritten and no default field
    for the current version is injected. `state_hash` hashes the whole canonical state, so seeding
    one gated key here would invalidate the `expectedStateHash` a session's last `next` already
    handed out and break its next `submit`. Version-gated fields are read with `.get()` at their
    read sites instead."""
    path = os.path.join(session_dir, STATE_FILE)
    if not os.path.exists(path):
        return True, None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return False, "loop-state.json is unreadable — start a fresh session dir"
    if not isinstance(data, dict) or _state_version(data) is None:
        return False, ("loop-state.json is schemaVersion %r, not one of %s — session dirs are "
                       "per-invocation with no migration; start a fresh session dir"
                       % (data.get("schemaVersion") if isinstance(data, dict) else None,
                          ", ".join(str(v) for v in SUPPORTED_STATE_VERSIONS)))
    return True, data


def _mirror_bytes(session_dir, state_bytes):
    """The mirror envelope for the exact bytes about to be written to the state file: the session id
    (None when `meta.json` is absent or unreadable), the sha256 of those bytes, and the bytes
    themselves as text. `_repair_state_if_damaged` restores the state file from it."""
    return _canonical({
        "schema": MIRROR_SCHEMA,
        "sessionId": _meta_session_id(session_dir),
        "stateSha256": hashlib.sha256(state_bytes).hexdigest(),
        "state": state_bytes.decode("utf-8"),
    }).encode("utf-8")


def _stage_state(c, session_dir, state_bytes):
    """Stage the state file and its mirror in commit `c`. Every two-phase commit that replaces the
    state file goes through here, so no commit writes the state without its mirror."""
    c.add_replace_file(os.path.join(session_dir, STATE_FILE), state_bytes)
    c.add_replace_file(os.path.join(session_dir, MIRROR_FILE), _mirror_bytes(session_dir, state_bytes))


def _write_state_bytes(session_dir, state_bytes):
    """The one direct writer of the state file: the state and its mirror land in one two-phase
    commit, so a crash between them replays to both or leaves both as they were."""
    c = round_commit.begin(session_dir, "state-write")
    _stage_state(c, session_dir, state_bytes)
    c.run()


def save_state(session_dir, state):
    _write_state_bytes(session_dir, _canonical(state).encode("utf-8"))


# =============================================================================================
# the round flow — planner + fold (shared by run_loop and the CLI)
# =============================================================================================

def _blocking(findings):
    return [f for f in findings if isinstance(f, dict)
            and circuit_breaker.is_blocking(f.get("severity"))]


# ---- challenged-coverage + the in-memory review-record ledger (#507 WO-D) --------------------

def _annotate_challenged(coverage, findings):
    """Port of review_panel_shell.annotateChallengedCoverage — a blocking finding whose class key
    matches an ALREADY-RECORDED coverage decision stamps that decision `challengedBy` (the fix's
    coverage rationale was recorded on a principle the reviewer is still raising). The challenged
    decision then feeds circuit_breaker's `challenged-principle-recurring` halt when the class
    recurs. Returns a fresh (copied) coverage list so the accumulator is never mutated in place."""
    out = [dict(d) for d in (coverage or []) if isinstance(d, dict)]
    known = {d.get("classKey") for d in out if d.get("classKey")}
    by_class = {d.get("classKey"): d for d in out if d.get("classKey")}
    for f in findings or []:
        if not isinstance(f, dict) or not circuit_breaker.is_blocking(f.get("severity")):
            continue
        key = f.get("classKey") or review_memory.class_key(f)
        if key in known and key in by_class:
            by_class[key]["challengedBy"] = f.get("dimension") or "reviewer"
    return out


def _append_review_record(state, rnd, kind, dim_map, findings):
    """Append (or replace) this round's in-memory review record for the challenged-coverage /
    recurrence breaker. The record carries the round's compiled findings, a per-dimension run map
    (so `_round_reviewed` reads it), the challenged-annotated coverage
    accumulated so far, and the recurrence-derived generalize grace (recurrent_classes over PRIOR
    records + coverage — the same current=compiled / prior=record split tally_round_decider uses)."""
    findings = [
        _strip_disposition_family(dict(f)) if isinstance(f, dict) else f
        for f in (findings or [])
        if isinstance(f, dict)
    ]
    coverage = _annotate_challenged(state.get("_coverage") or [], findings)
    prior = [r for r in (state.get("_records") or []) if r.get("round") != rnd]
    record = {
        "schemaVersion": 2,
        "round": rnd,
        "kind": kind,
        "dimensions": dim_map or {},
        "findings": findings,
        "changedSubjects": state.get("_changedSubjects"),
        "coverageDecisions": coverage,
        "generalizeRequired": review_memory.recurrent_classes(prior, coverage),
        "confirmationPending": False,
    }
    records = [r for r in (state.get("_records") or []) if r.get("round") != rnd]
    records.append(record)
    records.sort(key=lambda r: r.get("round") if isinstance(r.get("round"), int) else 0)
    state["_records"] = records


def _challenged_recurring_halt(state, config):
    """Run circuit_breaker over the in-memory ledger; act ONLY on `challenged-principle-recurring`
    (a coverage decision recorded on a WRONG principle whose class recurs). The plain
    recurring-finding / no-net-progress halts are the JS in-panel schedule's job — the #507 driver
    replaces them with the audit-keyed breaker + generalize grace — so they are NOT acted on here;
    the challenged path is the one safety property the delta schedule would otherwise drop. Returns
    the breaker dict when it fires a challenged halt, else None."""
    records = state.get("_records") or []
    if len(records) < 2:
        return None
    brk = circuit_breaker.check_circuit_breaker(records, _round_cap(config))
    if brk.get("halt") and brk.get("reason") == "challenged-principle-recurring":
        return brk
    return None


def _park_cannot_certify(state, detail):
    """A fail-closed park with certification withheld (challenged principle / corrupt resume). Maps
    to a `halted` terminal — never a silent clean."""
    _set_terminal(state, "cannot-certify")
    state["certification"] = {"shape": None, "reason": detail or "cannot certify — park"}
    _decision(state, "cannot-certify", detail)
    state["step"] = P_TERMINAL


VERIFY_BASE_TOKEN = store_core.VERIFY_BASE_TOKEN


def _verify_command(config):
    """The command `run-verify` hands the orchestrator, with `{baseRef}` bound to the session's
    pinned base commit. A touched-tests gate that diffs against main selects a stacked branch's
    whole stack (PR #1332 vet 244, collector @244-3); the token lets the calibrated command diff
    against the pinned base instead. Without a full-hex pin the token stays verbatim — the gate's
    own `base ref does not resolve` refusal is the loud failure, never a silent fall-back to main."""
    cmd = config.get("verifyCommand", "none")
    if not isinstance(cmd, str) or VERIFY_BASE_TOKEN not in cmd:
        return cmd
    base = config.get("baseRef")
    if isinstance(base, str) and store_core.VERIFY_BASE_PIN_RE.fullmatch(base):
        return cmd.replace(VERIFY_BASE_TOKEN, base)
    return cmd


def _shard_payload(diff_text, dimensions):
    """The panel dispatch payload: dims + tiers, and — when shard_plan says big — per-lens shards.
    The cross-cutting lenses always carry the whole diff."""
    plan = delta_surface.shard_plan(diff_text or "")
    tier = DEEP  # round 1 / full panels are always reviewer-deep
    payload = {"dimensions": list(dimensions), "tier": tier, "big": bool(plan.get("big"))}
    if plan.get("big"):
        lens_shards = {}
        for d in dimensions:
            if d in CROSS_CUTTING_LENSES:
                lens_shards[d] = {"wholeDiff": True}
            else:
                lens_shards[d] = {"shards": plan.get("shards", [])}
        payload["shards"] = lens_shards
    return payload


def _panel_dimensions(config):
    return round_phases.panel_dimensions(config)


# The held finding's fields the second-test seat reads: the finding as staged, its first test, that
# test's runs with their output, and the note the verifier gave for holding it.
_SECOND_TEST_ENTRY_FIELDS = ("id", "title", "file", "line", "severity", "body", "consequence",
                             "suggestion", break_it.RUNS_FIELD)


def _second_test_entry(row):
    """One order entry of the second-test payload from a `_secondTestHeld` row (`finding`, `note`)."""
    finding = row.get("finding") if isinstance(row.get("finding"), dict) else {}
    entry = {field: finding.get(field) for field in _SECOND_TEST_ENTRY_FIELDS}
    entry["verifierNote"] = row.get("note")
    return entry


def _advance(state, config):
    """Given the state, return the next step to dispatch (or the terminal). Pure read — never
    mutates. `next` and run_loop both call this."""
    if state.get("terminal"):
        return {"action": P_TERMINAL, "round": state["round"], "phase": P_TERMINAL,
                "payload": {"verdict": state["terminal"], "certification": state.get("certification")}}
    step = state["step"]
    rnd = state["round"]
    payload = {}
    dims = _panel_dimensions(config)
    if step == P_PANEL:
        diff_text = state.get("reviewedDiff")
        if isinstance(diff_text, str):
            # axis: the shard lists name the reviewer's files, which leave out the copies still proven — see bite-proof record c1l5b_wo_d_proven_copies
            diff_text = countable_lines.reviewer_diff(diff_text, _left_out(state, diff_text))
        payload = _shard_payload(diff_text, dims)
    elif step == P_VERIFIERS:
        staged = verification.stage_ids(state.get("_toVerify") or [])
        payload = {"clusters": verification.cluster_findings(staged)}
    elif step == P_SYNTHESIS:
        payload = {"findings": state.get("_verified") or [], "refuted": state.get("_refuted") or [],
                   "earlier": repeat_marks.order_list(_earlier_pool(state))}
    elif step == P_GAPSWEEP:
        payload = {"verifiedFindings": state.get("findings") or [],
                   "fullDiff": True}
    elif step == P_SECOND_TEST:
        payload = {"findings": [_second_test_entry(row) for row in state.get("_secondTestHeld") or []
                                if isinstance(row, dict)]}
    elif step == P_AUDITS:
        payload = {"targets": state.get("_auditTargets") or []}
        if state.get("_verifyThen") == VERIFY_THEN_POST_AUDITS:
            payload["verify"] = {"phase": P_VERIFY,
                                 "command": config.get("verifyCommand", "none")}
    elif step == P_SCOPED:
        payload = {"hunks": state.get("_newSurface") or {}, "tier": DEEP}
    elif step == P_VERIFY:
        payload = {"command": _verify_command(config)}
    elif step == P_APPLY_FIXES:
        payload = {"batch": state.get("_fixBatch") or [], "startHead": state.get("_fixStepHead")}
    return {"action": step, "round": rnd, "phase": step, "payload": payload}


def _record_round(state, key, value):
    rec = state["rounds"].setdefault(str(state["round"]), {})
    rec[key] = value


def _clear_round(state, key):
    """Remove one per-round key — the inverse of `_record_round`, so a channel recomputed on a
    later fold of the SAME round cannot leave a stale value behind (#1204)."""
    rec = state["rounds"].setdefault(str(state["round"]), {})
    rec.pop(key, None)


def _record_round_append(state, key, value):
    """Append one value to a per-round list without disturbing `_record_round`'s overwrite semantics."""
    rec = state["rounds"].setdefault(str(state["round"]), {})
    existing = rec.get(key)
    if existing is None:
        rec[key] = [value]
    elif isinstance(existing, list):
        existing.append(value)
    else:
        rec[key] = [existing, value]


def _record_compile_drops(state, drops):
    """Extend the round's `compileDrops` list — never overwrite an existing panel write."""
    if not drops:
        return
    for drop in drops:
        _record_round_append(state, "compileDrops", drop)


def _decision(state, kind, detail):
    if kind not in decision_kinds.DECISION_KINDS:
        raise ValueError("decision-kind-unregistered:%s" % kind)
    state["decisions"].append({"round": state["round"], "kind": kind, "detail": detail})


def _record_adapter_provenance(state, artifact, phase):
    """Persist adapter trust disclosures for the receipt/resume path (#720).

    Each phase's disclosures accumulate under `adapterProvenance.byPhase[phase]`; a second fold of
    the same phase replaces that phase's entry only. A legacy flat value migrates on write to
    `byPhase["unknown-phase"]` before the new entry is merged."""
    if not isinstance(artifact, dict):
        return
    prov = artifact.pop("provenance", None)
    if isinstance(prov, dict) and prov:
        rec = state["rounds"].setdefault(str(state["round"]), {})
        existing = rec.get("adapterProvenance")
        if isinstance(existing, dict) and "byPhase" in existing:
            by_phase = existing.get("byPhase")
            by_phase = dict(by_phase) if isinstance(by_phase, dict) else {}
        elif isinstance(existing, dict) and existing:
            by_phase = {"unknown-phase": dict(existing)}
        else:
            by_phase = {}
        by_phase[phase] = dict(prov)
        rec["adapterProvenance"] = {"byPhase": by_phase}


def _fold(state, config, phase, artifact, changed_subjects_seam=None, session_dir=None,
          verified_head_resolution=None, panel_diff_seam=None, fix_commits=None):
    """Fold one submitted artifact and advance state. Big switch on phase; each arm delegates the
    JUDGMENT to a pure decider and only records/sequences here. Returns the mutated state.

    `changed_subjects_seam` is threaded to the apply-fixes fold: run_loop passes the injected seam
    (the eval harness replays the fixture's subjects); the CLI submit path passes None so the fold
    wires the real git derivation. It is inert for every other phase.

    `panel_diff_seam` is threaded to the verify and apply-fixes folds: run_loop passes the injected
    seam; the CLI submit path passes None so those folds wire the real git derivation. It is inert
    for every other phase.

    `verified_head_resolution` is inert for every phase but ``P_VERIFY``. `fix_commits` is inert
    for every phase but ``P_APPLY_FIXES``: the bindings the submit chokepoint verified against git."""
    if session_contract.disposition_ledger_owner_classification(state) == (
        session_contract.DISPOSITION_LEDGER_OWNER_UNRECOGNIZED
    ):
        raise DispositionLedgerOwnerRefusal(DISPOSITION_LEDGER_OWNER_UNRECOGNIZED_CAUSE)
    artifact = artifact if isinstance(artifact, dict) else {}
    _record_adapter_provenance(state, artifact, phase)
    if phase == P_PANEL:
        _fold_panel(state, config, artifact, session_dir=session_dir)
    elif phase == P_VERIFIERS:
        _fold_verifiers(state, config, artifact, session_dir=session_dir)
    elif phase == P_SYNTHESIS:
        _fold_synthesis(state, config, artifact, session_dir=session_dir)
    elif phase == P_GAPSWEEP:
        _fold_gapsweep(state, config, artifact)
    elif phase == P_SECOND_TEST:
        _fold_second_test(state, config, artifact, session_dir=session_dir)
    elif phase == P_AUDITS:
        _fold_audits(state, config, artifact, session_dir=session_dir)
    elif phase == P_SCOPED:
        _fold_scoped(state, config, artifact)
    elif phase == P_VERIFY:
        _fold_verify(state, config, artifact, resolution=verified_head_resolution,
                     panel_diff_seam=panel_diff_seam)
    elif phase == P_APPLY_FIXES:
        _fold_apply_fixes(state, config, artifact, changed_subjects_seam, session_dir=session_dir,
                          panel_diff_seam=panel_diff_seam, fix_commits=fix_commits)
    return state


# ---- round-1 panel legs ---------------------------------------------------------------------

_PANEL_VENDORS = tuple(model_registry.VENDORS)  # SSOT — never a hand-maintained copy (#563/§11)

# The four artifact-envelope keys of a panel artifact. They are NOT seat keys. `canaryResult` is
# tolerated and never read: an older-shaped artifact that still carries it is accepted, the key is
# ignored, and it is never refused as an unknown seat.
# In the legacy shape (no dict-valued `artifact["seats"]`, so the artifact ITSELF is the seats map)
# these names must be subtracted before judging seat keys; in the explicit `{"seats": {...}}` shape
# nothing is subtracted, so one of these names appearing INSIDE the seats map is a real mis-key.
_PANEL_ENVELOPE_KEYS = ("seats", "seatMap", "ranManifest", "canaryResult")

def _fell_open_rows(seat_map, ran_manifest, seat_status):
    """(rows, provenance_missing) for #563 DoD1 (loud fall-open by machinery).

    `rows` = one dispatch-provenance row per `run` seat whose TRUSTED ran vendor (`ran_manifest`, the
    orchestrator's own record of which vendor produced each seat's folded findings — mirrors
    dispatch-audits' `collectionManifest`; an in-seat `ranVendor` echo is advisory only and is NEVER
    consulted here) differs from its CONFIGURED vendor (`seat_map.seats[dim].vendor`, the #510 seat
    map). Each row snapshots {seat, configured, ran, reason} AT FOLD TIME so a later seat-map mutation
    cannot rewrite provenance on receipt rebuild. Only `run` seats produce a row — a `missing` seat
    rides the existing unverified coverage-gap path. Malformed manifest entries (unknown dim,
    non-string, unknown vendor) are skipped — never a false fall-open.

    `provenance_missing` = the sorted cross-vendor (non-claude) CONFIGURED `run` seats that have NO
    trusted ran vendor reported (no manifest at all, or a manifest missing/malformed for that seat),
    so an omitted manifest is itself disclosed — the machinery is never silently lost."""
    manifest = ran_manifest if isinstance(ran_manifest, dict) else {}
    status = seat_status if isinstance(seat_status, dict) else {}

    def _ran_vendor(dim):
        v = manifest.get(dim)
        return v if isinstance(v, str) and v in _PANEL_VENDORS else None

    rows = []
    for dim in sorted(status):
        if status.get(dim) != "run":
            continue
        configured, ran = _seat_map_configured_vendor(seat_map, dim), _ran_vendor(dim)
        if configured and ran and configured != ran:
            rows.append({"seat": dim, "configured": configured, "ran": ran,
                         "reason": "forfeit-fell-open"})
    provenance_missing = sorted(
        dim for dim in status
        if status.get(dim) == "run"
        and _seat_map_configured_vendor(seat_map, dim) not in (None, "claude")
        and _ran_vendor(dim) is None)
    return rows, provenance_missing


def _usable_findings(seat):
    """Findings this panel will actually fold — only dict members count.

    ``_fold_panel`` judges a seat's status and folds its findings through this one predicate, so a
    seat cannot count as run while contributing nothing foldable (e.g. ``findings=[None]``).
    """
    if isinstance(seat, dict):
        raw = seat.get("findings")
    elif isinstance(seat, list):
        raw = seat
    else:
        raw = []
    if not isinstance(raw, list):
        raw = []
    return [f for f in raw if isinstance(f, dict)]


def _seat_map_configured_vendor(seat_map, dim):
    """Configured vendor for `dim` from a #510 seat map, or None if absent/unknown."""
    if not isinstance(seat_map, dict) or not isinstance(seat_map.get("seats"), dict):
        return None
    c = seat_map["seats"].get(dim)
    v = c.get("vendor") if isinstance(c, dict) else None
    return v if isinstance(v, str) and v in _PANEL_VENDORS else None


def panel_seat_keys(artifact):
    """The candidate seat keys of a panel artifact, resolved EXACTLY as `_fold_panel` resolves
    `seats` — so the guard and the fold can never read different maps.

    Returns a sorted list of string keys. Non-string keys are ignored (the fold's `seats.get(dim)`
    can never match one). The legacy shape — no dict-valued `artifact["seats"]`, so the artifact
    itself is the seats map — has `_PANEL_ENVELOPE_KEYS` subtracted; the explicit shape does not.
    """
    if not isinstance(artifact, dict):
        return []
    if isinstance(artifact.get("seats"), dict):
        keys = [k for k in artifact["seats"] if isinstance(k, str)]
    else:
        keys = [k for k in artifact if isinstance(k, str) and k not in _PANEL_ENVELOPE_KEYS]
    return sorted(keys)


def panel_seat_key_fault(dimensions, artifact):
    """None when every seat key in `artifact` is a configured dimension; otherwise a reason string
    naming the offending keys.

    An EMPTY candidate key set is not a mis-key — there is no wrong key to name — so it returns None
    and `_fold_panel`'s own fail-closed path (every configured dimension folds `missing`, nothing
    certifies) is left exactly as it is.
    """
    dims = ([d for d in dimensions if isinstance(d, str)]
            if isinstance(dimensions, (list, tuple)) else [])
    keys = panel_seat_keys(artifact)
    if not keys:
        return None
    if not dims:
        return None
    unknown = [k for k in keys if k not in dims]
    if not unknown:
        return None
    stem_to_dim = {AGENT_SUFFIX[d]: d for d in dims if d in AGENT_SUFFIX}
    hints = [f"{k} is the findings-file stem for {stem_to_dim[k]}"
             for k in sorted(unknown) if k in stem_to_dim]
    parts = [
        "unknown seat key(s): %s" % ", ".join(sorted(unknown)),
        "configured dimensions: %s" % ", ".join(sorted(dims)),
        "re-key the seats map and resubmit the same phase/attempt/state-hash",
    ]
    if hints:
        parts.append(", ".join(hints))
    return "; ".join(parts)


def _break_it_scope(session_dir, state, config):
    """The (repo root, head) the break-it intercept runs against; either may be None, which the
    runner turns into a `head-unresolved` not-run."""
    if session_dir:
        return _resolve_repo_root(session_dir, state), _session_certified_head(session_dir, state)
    return config.get("repoRoot"), config.get("headSha")


def _break_it_run_keys(runs, compiled):
    """Put the compiled finding's key on each run entry, passed runs included: the run binds to the compiled
    finding that carries its test (the same (file, normalized title) match, per-area or attached). A run whose
    proposal compile merged away is `supersededAtCompile` with no key; a run whose finding compile dropped is
    `droppedAtCompile` with no key."""
    by_anchor, by_identity = {}, {}
    flat = []
    for f in compiled:
        flat.append(f)
        # axis: a Nit a summary row collapsed still carries its attached test, so its run binds to the member
        members = f.get("members") if isinstance(f, dict) and f.get("summaryEntry") else None
        if isinstance(members, list):
            flat.extend(members)
    for f in flat:
        # axis: a finding whose file is not a string is never hashed into the lookup, so a run cannot bind to it and nothing raises
        if isinstance(f, dict) and break_it.carries_test(f) and isinstance(f.get("file"), str):
            ident = (f.get("file"), normalize_title(str(f.get("title") or "")))
            # axis: compile keeps same-file, same-title findings at different lines apart, so a run binds to the full (file, title, line) anchor — see bite-proof record wo_a_2210_break_it_working_copy
            line_ok, line = _coerce_line(f.get("line"))
            if line_ok:
                by_anchor.setdefault(ident + (line,), f)
            by_identity.setdefault(ident, f)
    out = []
    for run in runs:
        entry = dict(run)
        ident = (entry.get("file"), normalize_title(str(entry.get("title") or "")))
        if not isinstance(entry.get("file"), str):
            # axis: a run whose file is not a string is never hashed into the lookup; it binds to nothing and reads droppedAtCompile
            match = None
        elif "line" in entry:
            # axis: a line the coercion rejects (a list, a dict) is never hashed into the lookup; the run stays unmatched and reads droppedAtCompile
            line_ok, line = _coerce_line(entry.get("line"))
            match = by_anchor.get(ident + (line,)) if line_ok else None
        else:
            match = by_identity.get(ident)
        stamp = match.get(break_it.RUN_FIELD) if match else None
        if match is not None and isinstance(stamp, dict) and any(
                stamp.get(k) != entry.get(k) for k in ("sha256", "command", "reason")):
            # axis: a run whose proposal compile merged away binds to no finding, so the kept-check sees only the surviving test
            entry["findingKey"] = None
            entry["supersededAtCompile"] = True
        else:
            entry["findingKey"] = match.get(session_contract.FINDING_KEY_FIELD) if match else None
            if match is None:
                entry["droppedAtCompile"] = True
        out.append(entry)
    return out


def _fold_panel(state, config, artifact, session_dir=None):
    """Fold a full reviewer-deep panel. `artifact` maps dimension → {findings, receiptMissing?,
    receiptStale?}. A persistently receipt-missing/stale seat is terminal `missing` (shell
    :823-827 parity) but its findings ride the round record as UNVERIFIED/provisional — surfaced,
    never silently dropped (coordination note 2)."""
    seats = artifact.get("seats") if isinstance(artifact.get("seats"), dict) else artifact
    seat_map = artifact.get("seatMap") if isinstance(artifact.get("seatMap"), dict) else {}
    # A submitted map never releases a seat the map already governing this round left unfilled.
    unfilled = receipt_disclosures.unfilled_seats(
        seat_map_receipts.round_governing_map(state, state["round"]))
    if seat_map:
        receipts = state.get("seatMapReceipts")
        if not isinstance(receipts, list):
            receipts = []
            state["seatMapReceipts"] = receipts
        receipts.append({"round": str(state["round"]), "map": dict(seat_map)})
    # A seat the governing map leaves unfilled never ran, whatever payload was submitted for it:
    # drop it so the dimension folds `missing` and none of its findings are credited.
    unfilled = unfilled | receipt_disclosures.unfilled_seats(
        seat_map_receipts.round_governing_map(state, state["round"]))
    if unfilled and isinstance(seats, dict):
        seats = {dim: seat for dim, seat in seats.items() if dim not in unfilled}
    raw = []
    break_it_raw = []
    seat_status = {}
    unverified = []
    missing_dims = []
    vacuous_dims = []
    engaged_artifact_dims = []
    for dim in _panel_dimensions(config):
        seat = seats.get(dim) if isinstance(seats, dict) else None
        findings = _usable_findings(seat)
        status = "run"
        if isinstance(seat, dict):
            reason = seat.get("reason")
            if dispatch_outcome.payload_did_not_run(seat):
                status = "missing"
            if seat.get("vacuous") is True or (
                    isinstance(reason, str)
                    and reason == engine_adapter.REVIEW_FORFEIT_VACUOUS):
                vacuous_dims.append(dim)
            elif isinstance(reason, str) and (
                    reason == dispatch_outcome.REASON_FORFEIT_ENGAGED_ARTIFACT):
                engaged_artifact_dims.append(dim)
        elif not isinstance(seat, list):
            # A configured dimension with NO dict/list seat did not run: an omitted / null / mangled
            # seat is a silent coverage gap. Fail closed — status `missing`, never a clean `run`, so
            # it cannot count toward a full-panel certification (silence never certifies).
            status = "missing"
        if status == "missing":
            missing_dims.append(dim)
        seat_status[dim] = status
        for f in findings:
            g = dict(f)
            g.setdefault("dimension", dim)
            if status == "missing":
                g["unverified"] = True
                unverified.append({"dimension": dim, "title": g.get("title"),
                                   "file": g.get("file"), "line": g.get("line")})
            raw.append(g)
            # axis: only the test role's own seat can trigger a run; the trust is the roster seat key, never the finding's own dimension or taxonomy
            if dim == break_it.ROLE:
                break_it_raw.append(g)
    if vacuous_dims:
        _record_round(state, "vacuousSeats", list(vacuous_dims))
        _decision(state, "seat-vacuous",
                  "%d seat(s) returned no findings and no verifiable investigation record (%s) — "
                  "classed as never-ran; certification cannot rest on them"
                  % (len(vacuous_dims), ", ".join(vacuous_dims)))
    if engaged_artifact_dims:
        _record_round(state, "engagedArtifactSeats", list(engaged_artifact_dims))
        _decision(state, "seat-engaged-artifact",
                  "%d seat(s) produced a review our transport could not carry (%s) — they do "
                  "not count toward certification; salvaged artifacts are available for "
                  "independent verification"
                  % (len(engaged_artifact_dims), ", ".join(engaged_artifact_dims)))
    incomplete = bool(missing_dims)
    # axis: the break-it tests run in the session's own working copy BEFORE compile; compiling `raw` would drop a not-yet-existing test file as out of scope
    repo_root, head = _break_it_scope(session_dir, state, config)
    # axis: a break-it python run executes under the project's own interpreter launcher, read from the calibrated `breakItInterpreter` key when set, else from the verify command, never a PATH python — see bite-proof records wo_3_1910_break_it_interpreter and wo_1_1961_break_it_interpreter_key
    intercepted, runs, exempt, stamped = break_it.intercept(
        break_it_raw, repo_root, head,
        interpreter=break_it.resolve_interpreter(config), scratch=session_dir)
    # Every other seat's findings skip the intercept; the intercepted ones keep the place of the
    # test role's first finding, so the original order holds.
    break_it_ids = {id(g) for g in break_it_raw}
    kept, placed = [], False
    for g in raw:
        if id(g) not in break_it_ids:
            kept.append(g)
        elif not placed:
            kept.extend(intercepted)
            placed = True
    compiled, drops = mechanical_compile(kept, state.get("reviewedDiff"), scope_exempt=exempt, stamped=stamped)
    if runs:
        runs = _break_it_run_keys(runs, compiled)
        _record_round(state, "breakItRuns", runs)
        _decision(state, "break-it-run",
                  "%d run: %d exited 0, %d exited non-zero, %d not run"
                  % (len(runs),
                     sum(1 for r in runs if r.get("outcome") == break_it.OUTCOME_PASSED),
                     sum(1 for r in runs if r.get("outcome") == break_it.OUTCOME_FAILED),
                     sum(1 for r in runs if r.get("outcome") == break_it.OUTCOME_NOT_RUN)))
    _record_round(state, "seatStatus", seat_status)
    _panel_dims = _panel_dimensions(config)
    _expected = len(_panel_dims)
    if _expected > 0:
        _ran = sum(1 for d in _panel_dims if seat_status.get(d) == "run")
        _record_round(state, "lensCoverage",
                      {"ran": _ran, "expected": _expected, "floor": incomplete})
    # #563 DoD1 — loud fall-open by MACHINERY, not builder discipline: compare the trusted ranManifest
    # against the #510 seat map's configured vendors and record a per-round dispatch-provenance row for
    # any `run` seat that fell open to a different vendor; disclose an omitted manifest too (below).
    ran_manifest = artifact.get("ranManifest") if isinstance(artifact.get("ranManifest"), dict) else None
    fell_open, prov_missing = _fell_open_rows(_sm_latest_with_seats(state), ran_manifest, seat_status)
    if fell_open:
        _record_round(state, "fellOpen", fell_open)
    if prov_missing:
        _record_round(state, "fellOpenProvenanceMissing", prov_missing)
    # #563 DoD1 v7 / #681: an ABSENT seat-map baseline would silently disable all fall-open detection
    # (both outputs anchor on the configured seat map). If no seat map was submitted, disclose
    # provenance-unavailable for the whole panel — regardless of which panel vendors are live.
    if not _sm_any_seats(state):
        _live_panel = sorted({v for v in (config.get("vendors") or [])
                              if isinstance(v, str) and v in _PANEL_VENDORS})
        if not _live_panel:
            _live_panel = ["unknown"]
        _record_round(state, "seatMapUnavailable", _live_panel)
    # #1204: per-round record reflects the map governing THIS round; terminal predicate stays whole-history.
    _unjudgeable = _sm_round_governing_unjudgeable(
        state, state["round"], _driver_author_family(state))
    _bases = sorted({entry["basis"] for entry in _unjudgeable if isinstance(entry, dict)})
    if _bases:
        _record_round(state, "seatMapUnjudgeable", _bases)
    else:
        _clear_round(state, "seatMapUnjudgeable")
    _sm_violations = _sm_unexcused_violations(state, _driver_author_family(state))
    if _sm_violations:
        _record_round(state, "seatMapViolations", _sm_violations)
        _parts = []
        for v in _sm_violations:
            c = v.get("constraint") or "unknown"
            s = v.get("seat")
            _parts.append("%s@%s" % (c, s) if s else c)
        _decision(state, "seat-map-constraint-violated",
                  "unexcused seat-map constraint violation(s): %s" % ", ".join(_parts))
    _record_round(state, "compileDrops", drops)
    if unverified:
        _record_round(state, "unverified", unverified)
        _decision(state, "receipt-missing-seat",
                  "%d finding(s) carried unverified from receipt-missing seat(s)" % len(unverified))
    if incomplete:
        if missing_dims:
            _record_round(state, "missingSeats", list(missing_dims))
            _decision(state, "panel-seat-missing",
                      "panel incomplete — %d configured lens(es) did not run (%s); certification cannot "
                      "be full-panel-confirmed" % (len(missing_dims), ", ".join(missing_dims)))
    # Only a COMPLETE panel can anchor a full-panel-confirmed certification. A missing seat leaves
    # fullPanelRan False so a clean finish downgrades to audited-chain and names the gap.
    state["fullPanelRan"] = not incomplete
    # Track the OUTSTANDING coverage gap across the loop: an incomplete panel arms it (a converge
    # resting on it is withheld — a lens never ran); a COMPLETE panel recovers coverage and clears it
    # (#507 R2 residual-1). A scoped delta round leaves it untouched, so a round-1 gap never silently
    # clears on a delta finish.
    state["_incompletePanel"] = incomplete
    # In-memory review record for the challenged-coverage / recurrence breaker: only round 1 runs a
    # full panel, so its record is the `baseline`.
    kind = "baseline"
    dim_map = {}
    for dim in _panel_dimensions(config):
        seat = seats.get(dim) if isinstance(seats, dict) else None
        s_findings = []
        # A missing seat defaults to LOW confidence, never high — an absent lens must never lend a
        # high-confidence run to the record.
        confidence = "low" if seat_status.get(dim) == "missing" else "high"
        tier = DEEP
        if isinstance(seat, dict):
            s_findings = _usable_findings(seat)
            if seat_status.get(dim) != "missing":
                confidence = seat.get("confidence") or "high"
            tier = seat.get("tier") or DEEP
        elif isinstance(seat, list):
            s_findings = seat
        dim_map[dim] = {"dimension": dim, "status": seat_status.get(dim, "run"),
                        "confidence": confidence, "tier": tier, "findings": s_findings}
    _append_review_record(state, state["round"], kind, dim_map, compiled)
    _stage_findings(state, compiled)
    state["step"] = P_VERIFIERS


def _staged_by_id_map(staged):
    """Build staged-id → finding; refuse duplicate ids."""
    by_id = {}
    for finding in staged:
        if not isinstance(finding, dict):
            continue
        staged_id = finding.get("id")
        if staged_id is None:
            continue
        if staged_id in by_id:
            return None, "%s: duplicate staged id %r" % (STAGED_ID_UNRESOLVABLE_CAUSE, staged_id)
        by_id[staged_id] = finding
    return by_id, None


def _staged_id_resolution_fault(staged, staged_id):
    """None when staged_id resolves to exactly one keyed finding; otherwise a named cause."""
    if staged_id is None:
        return "%s: missing staged id" % STAGED_ID_UNRESOLVABLE_CAUSE
    by_id, map_fault = _staged_by_id_map(staged)
    if map_fault:
        return map_fault
    finding = by_id.get(staged_id)
    if finding is None:
        return "%s: staged id %r maps to no entry" % (STAGED_ID_UNRESOLVABLE_CAUSE, staged_id)
    if not _finding_identity_key(finding):
        return "%s: staged id %r has no derivable finding key" % (STAGED_ID_UNRESOLVABLE_CAUSE,
                                                                  staged_id)
    return None


def _resolve_staged_finding(staged, staged_id):
    """Return (finding, fault). fault is None on success."""
    fault = _staged_id_resolution_fault(staged, staged_id)
    if fault:
        return None, fault
    by_id, _ = _staged_by_id_map(staged)
    return by_id.get(staged_id), None


def verifier_drop_staged_id_fault(state, artifact):
    """Refuse verifier drops whose staged ids do not resolve before fold."""
    if verifier_results_fault(artifact) is not None:
        return None
    staged = verification.stage_ids(state.get("_toVerify") or [])
    verdicts = artifact.get("verdicts") if isinstance(artifact.get("verdicts"), list) else []
    applied = verification.apply_verdicts(staged, verdicts)
    for drop in applied["drops"]:
        fault = _staged_id_resolution_fault(staged, drop.get("id"))
        if fault:
            return fault
    by_id = {}
    for verdict in verdicts:
        if isinstance(verdict, dict) and isinstance(verdict.get("id"), str):
            by_id[verdict["id"]] = verdict
    for staged_id in applied.get("unmatched") or []:
        verdict = by_id.get(staged_id)
        if isinstance(verdict, dict) and verdict.get("verdict") == "REFUTED":
            fault = _staged_id_resolution_fault(staged, staged_id)
            if fault:
                return fault
    for staged_id in applied.get("ambiguous") or []:
        fault = _staged_id_resolution_fault(staged, staged_id)
        if fault:
            return fault
    return None


def _format_grouping_coverage_fault(fault):
    """Map ``verification.grouping_coverage_fault`` output to a synthesis refusal string."""
    if not fault:
        return None
    kind = fault.get("kind")
    member_id = fault.get("member_id")
    if kind == "duplicate_member":
        return "%s: duplicate member %r in grouping[%d]" % (
            STAGED_ID_UNRESOLVABLE_CAUSE, member_id, fault.get("index"))
    if kind == "omits":
        return "%s: grouping omits staged id %r" % (STAGED_ID_UNRESOLVABLE_CAUSE, member_id)
    if kind == "extra":
        return "%s: staged id %r maps to no entry" % (STAGED_ID_UNRESOLVABLE_CAUSE, member_id)
    if kind == "repeat_ref":
        return "%s: repeatOf %r is not an earlier-finding ref of this order (null or one of its `earlier` refs)" % (
            STAGED_ID_UNRESOLVABLE_CAUSE, member_id)
    return "%s: grouping does not cover every survivor exactly once" % STAGED_ID_UNRESOLVABLE_CAUSE


def synthesis_staged_id_fault(state, artifact, session_dir=None):
    """Refuse synthesis author-justified drops and merge members whose ids do not resolve, and a repeat
    name that is not null or an earlier-finding ref of the order (the fold applies the same validation)."""
    verified = state.get("_verified") or []
    refuted = state.get("_refuted") or []
    grouping = artifact.get("grouping") if isinstance(artifact.get("grouping"), list) else None
    if isinstance(grouping, list):
        fault = _format_grouping_coverage_fault(
            repeat_marks.grouping_fault(verified, refuted, grouping, _earlier_pool(state)))
        if fault:
            return fault
        for group in grouping:
            if not isinstance(group, dict):
                continue
            for member_id in group.get("member_ids") or []:
                fault = _staged_id_resolution_fault(verified + refuted, member_id)
                if fault:
                    return fault
    plan = _repeat_plan(state, grouping, session_dir)
    merged = verification.merge_and_rank(plan["survivors"], plan["grouping"])
    findings = merged["findings"]
    config = state.get("config") or {}
    _kept, aj_drops = author_justification_filter(findings, config.get("priorComments"))
    for drop in aj_drops:
        fault = _staged_id_resolution_fault(verified, drop.get("id"))
        if fault:
            return fault
    for merge in merged.get("merges") or []:
        if not isinstance(merge, dict):
            continue
        kept_id = merge.get("kept_id")
        kept_finding, fault = _resolve_staged_finding(verified, kept_id)
        if fault:
            return fault
        if kept_finding is None:
            continue
        for member_id in merge.get("member_ids") or []:
            if member_id == kept_id:
                continue
            fault = _staged_id_resolution_fault(verified, member_id)
            if fault:
                return fault
    return None


def _anchored_orders_manifest(state, session_dir, rnd, phase, attempt):
    """The orders manifest the dispatch of ``(rnd, phase, attempt)`` emitted, only when its canonical
    hash equals the state-mirrored emission anchor (the file alone is mutable); else None. One home
    for every reader of the driver's own record of who each seat was dispatched on. Never raises."""
    try:
        anchor = _orders_anchor(state, session_dir, rnd, phase, attempt)
        manifest, err = round_records.read_json(
            _orders_manifest_path(session_dir, rnd, phase, attempt))
    except Exception:  # noqa: BLE001 — a missing record falls back to the live selection
        return None
    if err is not None or not isinstance(manifest, dict) or not isinstance(anchor, dict):
        return None
    if round_records.sha256_text(round_records.canonical(manifest)) != anchor.get("manifestSha256"):
        return None
    return manifest


def _latest_emission_attempt(state, session_dir, phase):
    """The latest attempt number of this round's ``phase`` dispatch that was emitted, found through
    the state-mirrored emission anchors AND the journalled ``orders-emitted`` events (the same two
    homes `_orders_anchor` resolves an emission from, so a session that lost its state mirror still
    names its emission), or None when none was emitted. Never raises."""
    if not session_dir:
        return None
    rnd = state.get("round")
    best = None
    anchors = state.get("_ordersAnchors")
    for key in (anchors if isinstance(anchors, dict) else ()):
        parts = key.split(":") if isinstance(key, str) else []
        if len(parts) == 3 and parts[0] == str(rnd) and parts[1] == phase \
                and parts[2].isdigit() and (best is None or int(parts[2]) > best):
            best = int(parts[2])
    try:
        events = read_journal(session_dir)
    except Exception:  # noqa: BLE001 — an unreadable journal contributes no emission
        events = []
    for event in events if isinstance(events, list) else ():
        if not isinstance(event, dict) or event.get("outcome") != "orders-emitted":
            continue
        attempt = event.get("attempt")
        if event.get("round") == rnd and event.get("phase") == phase \
                and isinstance(attempt, int) and not isinstance(attempt, bool) \
                and (best is None or attempt > best):
            best = attempt
    return best


def _emission_unverifiable(state, session_dir, phase):
    """The reason (truthy) when this round's ``phase`` dispatch recorded an emission anchor but its orders
    manifest is unreadable, unverified, or names several vendors: nothing it ordered can be
    authenticated (fail closed — never a fallback to the live selection)."""
    best = _latest_emission_attempt(state, session_dir, phase)
    if best is None:
        return None
    manifest = _anchored_orders_manifest(state, session_dir, state.get("round"), phase, best)
    seats = manifest.get("seats") if isinstance(manifest, dict) else None
    if len({e.get("vendor") for e in seats.values() if isinstance(e, dict)} if isinstance(seats, dict) else ()) > 1:
        return "emission-manifest-mixed-vendors"  # one phase, several vendors: no single vendor to bind
    return "emission-manifest-unverifiable" if manifest is None else None


def _recorded_phase_vendor(state, session_dir, phase):
    """The vendor the dispatch of ``phase`` in the current round recorded at emission (its orders
    manifest's per-seat ``vendor``), or None when nothing was emitted, the manifest does not verify
    against the state-mirrored anchor, or the seats do not name exactly one vendor. The fold runs
    after ``pending`` is cleared, so the dispatch is found through the mirrored emission anchors
    (latest attempt of this round's phase). Never raises."""
    best = _latest_emission_attempt(state, session_dir, phase)
    if best is None:
        return None
    manifest = _anchored_orders_manifest(state, session_dir, state.get("round"), phase, best)
    seats = manifest.get("seats") if isinstance(manifest, dict) else None
    vendors = {entry.get("vendor") for entry in seats.values() if isinstance(entry, dict)} \
        if isinstance(seats, dict) else set()
    if len(vendors) == 1:
        only = next(iter(vendors))
        if isinstance(only, str) and only:
            return only
    return None


def _recorded_claim_required(state, session_dir, phase):
    """True when the ``phase`` dispatch recorded that its result must claim the vendor that ran."""
    best = _latest_emission_attempt(state, session_dir, phase)
    manifest = _anchored_orders_manifest(state, session_dir, state.get("round"), phase, best) \
        if best is not None else None
    return isinstance(manifest, dict) and manifest.get("claimRequired") is True


def _recorded_verifier_vendor(state, session_dir):
    """`_recorded_phase_vendor` for the verifier dispatch."""
    return _recorded_phase_vendor(state, session_dir, P_VERIFIERS)


def _fold_verifiers(state, config, artifact, session_dir=None):
    """Apply per-finding verification verdicts deterministically (verification.apply_verdicts)."""
    verdicts = artifact.get("verdicts") if isinstance(artifact.get("verdicts"), list) else []
    if _nonpanel_unseatable(state, session_dir, P_VERIFIERS):
        # No verifier could be seated outside the makers: any verdict submitted never ran, so it
        # folds exactly like silence (every staged finding stays unverified), as an unseatable
        # audit target does.
        verdicts = []
    # axis: the verdicts count only when the vendor that ran them is the driver's selected non-maker
    # vendor; a replaced (independent) selection with no vendor claim, or a different one, ran in an
    # unproven family and folds like silence.
    selected, source = _nonpanel_selection(state, session_dir, P_VERIFIERS)
    barred = receipt_disclosures.nonpanel_barred(state, config)
    unverifiable = _emission_unverifiable(state, session_dir, P_VERIFIERS)
    if selected is not None and verdicts and unverifiable:
        # The dispatch anchored an emission but its manifest is unreadable, tampered or mixed: the
        # vendor it ordered is unknown, so the verdicts fold as silence and the loss is disclosed.
        _record_round_append(state, "verifierProvenance", {
            "expected": selected, "ran": None, "outcome": "verdicts-ignored", "reason": unverifiable})
        verdicts = []
    # The dispatch recorded its vendor at emission; a preference edited while the verifiers ran must
    # not re-judge them against a selection nobody dispatched.
    recorded = _recorded_verifier_vendor(state, session_dir)
    rebound = recorded is not None and recorded != selected
    if recorded is not None:
        selected = recorded
    seat_vendors = artifact.get("verifierSeatVendors")
    if isinstance(seat_vendors, dict):
        # Durable path: each seat's executed vendor authenticates only the verdicts that seat
        # supplied; an unproven seat's verdicts fold as silence while a proven seat's still fold.
        if selected is not None:
            outcomes = {}
            kept = []
            seat_provenance = artifact.get("verifierSeatProvenance")
            seat_provenance = seat_provenance if isinstance(seat_provenance, dict) else {}
            via_manifest = set()
            for verdict in verdicts:
                vid = verdict.get("id") if isinstance(verdict, dict) else None
                ran_vendor = seat_vendors.get(vid) if isinstance(vid, str) else None
                ran_vendor = ran_vendor.strip() if isinstance(ran_vendor, str) and ran_vendor.strip() \
                    else None
                proven = ran_vendor == selected and not barred(ran_vendor)
                outcomes.setdefault(ran_vendor, proven)
                if seat_provenance.get(vid) == round_records.AUDIT_PROVENANCE_LEGACY_DISPATCH_MANIFEST:
                    via_manifest.add(ran_vendor)
                if proven:
                    kept.append(verdict)
            for ran_vendor, proven in outcomes.items():
                row = {"expected": selected, "ran": ran_vendor,
                       "outcome": "verdicts-folded" if proven else "verdicts-ignored"}
                if ran_vendor == selected and not proven:
                    row["reason"] = "vendor-ineligible"
                if ran_vendor in via_manifest:
                    row["provenance"] = round_records.AUDIT_PROVENANCE_LEGACY_DISPATCH_MANIFEST
                _record_round_append(state, "verifierProvenance", row)
            verdicts = kept
    else:
        ran = artifact.get("verifierVendor")
        claimed = ran.strip() if isinstance(ran, str) and ran.strip() else None
        # A claim is required when the selection replaced the reviewer engine (whatever the
        # preference read's provenance) and on the durable path, which always carries the key.
        claim_required = (source == VENDOR_SOURCE_INDEPENDENT or "verifierVendor" in artifact
                          or rebound or _nonpanel_replaced(state, selected, session_dir)
                          or _recorded_claim_required(state, session_dir, P_VERIFIERS))
        mismatch = (claimed is not None and claimed != selected) or (claim_required and claimed is None)
        ineligible = not mismatch and selected is not None and barred(selected)
        if verdicts and selected is not None and (mismatch or ineligible):
            row = {"expected": selected, "ran": claimed, "outcome": "verdicts-ignored"}
            if ineligible:
                row["reason"] = "vendor-ineligible"
            _record_round_append(state, "verifierProvenance", row)
            verdicts = []
        elif verdicts:
            _record_round_append(state, "verifierProvenance", {
                "expected": selected, "ran": claimed if claimed is not None else selected,
                "outcome": "verdicts-folded"})
    staged = verification.stage_ids(state.get("_toVerify") or [])
    applied = verification.apply_verdicts(staged, verdicts)
    second_pass = state.get("_secondTestPass") is True
    survivors = list(applied["findings"])
    if second_pass:
        # every finding in this pass has had its one more test, so nothing is held; one that is anyway is
        # kept, graded, and never held a second time
        again, fault = _keep_held_again(state, staged, applied["held"])
        if fault:
            _park_cannot_certify(state, fault)
            state["step"] = P_TERMINAL
            return
        survivors += again
    state["_verified"] = survivors
    verify_record = {"drops": applied["drops"], "downgrades": applied["downgrades"],
                     "unverified": applied["unverified"], "ambiguous": applied["ambiguous"],
                     "notExecuted": applied["notExecuted"],
                     # axis: the findings a passing test missed the path of are listed on the verify record, where the docs promise them — see bite-proof record c1l7_wo_f_held_record
                     "held": applied["held"]}
    prior_verify = state["rounds"].get(str(state["round"]), {}).get("verify") if second_pass else None
    if isinstance(prior_verify, dict):
        # axis: the first pass's drops, downgrades and the rest stay on the round's record beside the second's
        for field, rows in verify_record.items():
            if field == "held":
                continue
            held_rows = prior_verify.get(field)
            verify_record[field] = (list(held_rows) if isinstance(held_rows, list) else []) + rows
        # the second pass holds nothing, so the held list is the first pass's alone; an older record without one reads empty
        first_held = prior_verify.get("held")
        verify_record["held"] = list(first_held) if isinstance(first_held, list) else []
    _record_round(state, "verify", verify_record)
    # axis: each verifier fold appends one verifyPasses entry; a second wave must not overwrite.
    _record_round_append(state, "verifyPasses", {
        "CONFIRMED": sum(1 for f in survivors if f.get("verdict") == "CONFIRMED"),
        "PLAUSIBLE": sum(1 for f in survivors if f.get("verdict") == "PLAUSIBLE"),
        "REFUTED": len(applied["drops"]),
        "drops": len(applied["drops"]),
        "downgrades": len(applied["downgrades"]),
        "unverified": len(applied["unverified"]),
        "ambiguous": len(applied["ambiguous"]),
        "held": len(applied["held"]),
    })
    for survivor in survivors:
        grade = survivor.get(GRADE_FIELD)
        # A survivor whose staged id resolves to no keyed finding keeps the grade on its copy only.
        staged_finding, fault = _resolve_staged_finding(staged, survivor.get("id"))
        if not fault and isinstance(staged_finding, dict):
            key = _finding_identity_key(staged_finding)
            if isinstance(grade, dict):
                _record_grade(state, key, grade)
            else:
                # axis: a survivor this fold left ungraded drops the grade an earlier raise left on its ledger row, so a re-raised finding is never closed shown-wrong on a stale grade
                _clear_grade(state, key)
    refuted = []
    for d in applied["drops"]:
        _decision(state, "verifier-refuted", d.get("reason"))
        staged_finding, fault = _resolve_staged_finding(staged, d.get("id"))
        if fault:
            _park_cannot_certify(state, fault)
            state["step"] = P_TERMINAL
            return
        if isinstance(staged_finding, dict):
            refuted.append(dict(staged_finding, **{GRADE_FIELD: d.get(GRADE_FIELD)}))
            key = _finding_identity_key(staged_finding)
            if key:
                reason = d.get("reason") or "verifier refuted (no reason recorded)"
                # axis: the refuted ledger row carries the wrong grade that closed it, written before the disposition — see bite-proof record c1l7_wo_b_verifier_grade
                _record_grade(state, key, d.get(GRADE_FIELD))
                _record_disposition(state, key, "refuted", state["round"], refutedReason=reason)
    state["_refuted"] = refuted  # this round's refuted findings (staged ids): they carry a repeat mark, never a merge
    for n in applied["notExecuted"]:
        _decision(state, "verifier-not-executed", n.get("reason"))
    if applied["held"] and not second_pass:
        # axis: a finding whose passing test missed its path is neither graded nor closed on that test; it gets one more test — see bite-proof record c1l7_wo_c_second_test
        state["_verified"] = []
        _hold_for_second_test(state, session_dir, staged, applied["held"], survivors, refuted)
        return
    if second_pass:
        carried = state.pop("_secondTestCarry", None)
        carried_refuted = state.pop("_secondTestRefutedCarry", None)
        state.pop("_secondTestHeld", None)
        state.pop("_secondTestPass", None)
        carried = carried if isinstance(carried, list) else []
        carried_refuted = carried_refuted if isinstance(carried_refuted, list) else []
        # axis: the first pass's survivors and refuted findings and this pass's are staged afresh together, so the round's two lists carry unique ids and its refuted list holds both passes' — see bite-proof record c1l8_wo_a_repeat_marks
        restaged = verification.stage_ids(carried + survivors + carried_refuted + refuted)
        split = len(carried) + len(survivors)
        state["_verified"], state["_refuted"] = restaged[:split], restaged[split:]
    # round-1 findings and delta scoped candidates both route to synthesis; the delta settle is
    # armed on the delta path (see _fold_scoped) so _after_findings_settled re-settles the delta.
    # A round with refuted findings against a non-empty earlier pool still dispatches synthesis, to name repeats only.
    # axis: a round with no verified survivors emits no synthesis order and folds to its next step — see bite-proof record wo_1_1910_synthesis_no_survivors
    if not state["_verified"] and not (state["_refuted"] and _earlier_pool(state)):
        _decision(state, "synthesis-no-survivors",
                  "verification left no findings, so no grouping seat was dispatched")
        _fold_synthesis(state, config, {"grouping": []}, session_dir, exact_only="synthesis-no-survivors")
        return
    if _nonpanel_unseatable(state, session_dir, P_SYNTHESIS):
        # No grouping seat outside the makers' families on a proven synthesis cell: no order is
        # emitted and the round folds exactly as an empty grouping would — every verified finding
        # stays separate (nothing dropped) and the receipt discloses it.
        cfg = state.get("config") or {}
        _record_round_append(state, "synthesisUnseatable", {
            "makerFamilies": sorted(receipt_disclosures.accumulated_maker_families(state)),
            "fixerVendor": cfg.get("fixerVendor")})
        _decision(state, "synthesis-unseatable",
                  "no synthesis seat outside the makers' families on a proven cell; findings not grouped")
        _fold_synthesis(state, config, {"grouping": None}, session_dir, exact_only="synthesis-unseatable")
        return
    state["step"] = P_SYNTHESIS


SECOND_TEST_FIELD = verification.SECOND_TEST_FIELD
SECOND_TEST_HELD_AGAIN_REASON = "held again after its one more test; kept as a judgment call"


def _record_second_test(state, **fields):
    """Merge ``fields`` into the round's `secondTest` entry; a list already there is extended, never replaced."""
    rec = state["rounds"].setdefault(str(state["round"]), {})
    entry = rec.get("secondTest")
    entry = dict(entry) if isinstance(entry, dict) else {}
    for name, value in fields.items():
        held = entry.get(name)
        entry[name] = (list(held) + value) if isinstance(held, list) and isinstance(value, list) else value
    _record_round(state, "secondTest", entry)


def _stage_second_pass(state, copies):
    """Stage the held findings (``copies``, each already marked `secondTest`) for the verifiers' second pass."""
    for copy_ in copies:
        copy_.pop("id", None)  # the staged id the first pass gave is not part of the finding
    _stage_findings(state, copies)
    state["_secondTestPass"] = True
    state["step"] = P_VERIFIERS


def _hold_for_second_test(state, session_dir, staged, held, survivors, refuted=()):
    """Pass 1: keep the held findings (``held``, from `apply_verdicts`), the pass-1 ``survivors`` and the pass-1
    ``refuted`` findings aside and send the held ones to the second-test seat; when no seat can be seated, skip
    the seat and go straight to the verifiers' second pass with each held finding marked, and no new test."""
    rows = []
    for entry in held:
        finding, fault = _resolve_staged_finding(staged, entry.get("id"))
        if fault:
            _park_cannot_certify(state, fault)
            state["step"] = P_TERMINAL
            return
        rows.append({"finding": finding, "note": entry.get("note")})
    state["_secondTestHeld"] = rows
    state["_secondTestCarry"] = survivors
    state["_secondTestRefutedCarry"] = list(refuted)
    keys = [_finding_identity_key(row["finding"]) for row in rows]
    _record_second_test(state, held=[{"findingKey": key, "note": row["note"]} for key, row in zip(keys, rows)])
    _decision(state, "second-test-held",
              "%d finding(s) held for one more test: the break-it test passed and the verifier judged it "
              "did not reach the finding's path" % len(rows))
    # axis: with no second-test seat to seat there is no order; the held findings are graded in the second pass with the test they have — see bite-proof record c1l7_wo_c_second_test
    if _nonpanel_unseatable(state, session_dir, P_SECOND_TEST):
        cfg = state.get("config") or {}
        _record_round_append(state, "secondTestUnseatable", {
            "makerFamilies": sorted(receipt_disclosures.accumulated_maker_families(state)),
            "fixerVendor": cfg.get("fixerVendor"), "held": keys})
        _decision(state, "second-test-unseatable",
                  "no second-test seat outside the makers' families on a proven cell; the held findings "
                  "were graded with the test they have")
        _stage_second_pass(state, [dict(row["finding"], **{SECOND_TEST_FIELD: True}) for row in rows])
        return
    state["step"] = P_SECOND_TEST


def _keep_held_again(state, staged, held):
    """Pass 2: ``(survivors, fault)`` for any finding `apply_verdicts` held although it had its one more test:
    each is kept PLAUSIBLE with a `plausible` grade, never held again, never dropped."""
    kept = []
    for entry in held:
        finding, fault = _resolve_staged_finding(staged, entry.get("id"))
        if fault:
            return [], fault
        survivor = dict(finding)
        survivor["verdict"] = "PLAUSIBLE"
        survivor[GRADE_FIELD] = {"verdict": "plausible", "reason": SECOND_TEST_HELD_AGAIN_REASON}
        kept.append(survivor)
        _decision(state, "second-test-held-again", "%s: %s" % (entry.get("id"), entry.get("note")))
    return kept, None


def _fold_second_test(state, config, artifact, session_dir=None):
    """The second-test seat's result: for each held finding, the result finding with the same staged id whose
    `suggestion` is a break-it block supplies the one more test, run as the panel's tests are; any other held
    finding goes to the verifiers' second pass with the test it has. Nothing else of a result is taken."""
    rows = state.get("_secondTestHeld")
    rows = [row for row in rows if isinstance(row, dict) and isinstance(row.get("finding"), dict)] \
        if isinstance(rows, list) else []
    results = artifact.get("findings") if isinstance(artifact.get("findings"), list) else []
    by_id, duplicated = {}, set()
    for result in results:
        rid = result.get("id") if isinstance(result, dict) else None
        if not isinstance(rid, str):
            continue
        if rid in by_id:
            duplicated.add(rid)
        by_id[rid] = result
    held_ids = {row["finding"].get("id") for row in rows}
    unmatched = sorted(rid for rid in set(by_id) | duplicated if rid not in held_ids)
    repo_root, head = _break_it_scope(session_dir, state, config)
    copies, no_test, ran = [], [], []
    for row in rows:
        held = row["finding"]
        key = _finding_identity_key(held)
        result = by_id.get(held.get("id"))
        block = break_it.carried_block(result)[0] if result is not None else None
        copy_ = dict(held)
        copy_[SECOND_TEST_FIELD] = True
        if held.get("id") in duplicated:
            no_test.append({"findingKey": key, "reason": "duplicate-id"})
        elif result is None:
            no_test.append({"findingKey": key, "reason": "no-result"})
        elif block is None:
            no_test.append({"findingKey": key, "reason": "no-block"})
        else:
            copy_["suggestion"] = result.get("suggestion")
            if result.get(break_it.REDACTED_FIELD) is True:
                copy_[break_it.REDACTED_FIELD] = True  # the transport altered the test's bytes: it is never run altered
            else:
                copy_.pop(break_it.REDACTED_FIELD, None)
            stamped, runs, _exempt, _stamped = break_it.intercept(
                [copy_], repo_root, head, interpreter=break_it.resolve_interpreter(config), scratch=session_dir)
            copy_ = stamped[0]
            first_runs = held.get(break_it.RUNS_FIELD)
            first_runs = list(first_runs) if isinstance(first_runs, list) else []
            copy_[break_it.RUNS_FIELD] = first_runs + [r for r in copy_.get(break_it.RUNS_FIELD, [])
                                                       if r not in first_runs]
            for run in runs:
                # axis: the second test's run joins the round's history as the finding's latest, so the kept-check reads it — see bite-proof record c1l7_wo_c_second_test
                _record_round_append(state, "breakItRuns", dict(run, findingKey=key))
                ran.append({"findingKey": key, "outcome": run.get("outcome")})
        copies.append(copy_)
    _record_second_test(state, ran=ran, noTest=no_test, unmatched=unmatched)
    _stage_second_pass(state, copies)


def _sync_merged_consequences(state, kept):
    """Carry a synthesized representative's merged consequence onto its ledger row, so a later
    re-seed or restage from the ledger cannot lose a member's real consequence."""
    ledger = _ensure_disposition_ledger_for_write(state)
    seen = _ledger_index_by_key(ledger)
    for finding in kept:
        key = _finding_identity_key(finding) if isinstance(finding, dict) else None
        if key in seen:
            for field in ("consequence", "consequenceKind"):
                if field in finding:
                    ledger[seen[key]][field] = finding[field]


def _verifier_head(state, session_dir, rnd):
    """The head the verifier phase of round ``rnd`` judged on (its orders anchor), or None when unreadable."""
    prefix = "%s:%s:" % (rnd, P_VERIFIERS)
    anchors = state.get("_ordersAnchors")
    attempts = [int(k[len(prefix):]) for k in (anchors if isinstance(anchors, dict) else ())
                if isinstance(k, str) and k.startswith(prefix) and k[len(prefix):].isdigit()]
    if not attempts and session_dir:
        try:
            events = read_journal(session_dir)
        except Exception:  # noqa: BLE001 — an unreadable journal names no attempt
            events = []
        attempts = [e["attempt"] for e in events if isinstance(e, dict) and e.get("outcome") == "orders-emitted"
                    and e.get("round") == rnd and e.get("phase") == P_VERIFIERS and _is_plain_int(e.get("attempt"))]
    try:
        return _anchor_cited_head(state, session_dir, rnd, P_VERIFIERS, max(attempts)) if attempts else None
    except Exception:  # noqa: BLE001 — an unreadable anchor is an unknown head, which counts as changed
        return None


def _repeat_changed(state, session_dir, entry):
    """Whether the code changed between the head the earlier finding was judged on and the head this round's
    verifier judged on; an unreadable head or a failed comparison is a change."""
    earlier = entry.get("head") if entry["source"] == "record" else _verifier_head(
        state, session_dir, entry.get("round"))
    if not earlier:  # an unknown judged head (every record finding's) is a change, with no git run
        return True
    return repeat_marks.code_changed((state.get("config") or {}).get("repoRoot"), earlier,
                                     _verifier_head(state, session_dir, state["round"]))


def _grade_verdict(finding):
    grade = finding.get(GRADE_FIELD) if isinstance(finding, dict) else None
    return grade.get("verdict") if isinstance(grade, dict) else None


def _repeat_plan(state, grouping, session_dir, exact_only=None):
    """Take every staged finding's repeat decision on its own grade, before the merge, and return what the
    merge sees: the survivors without the kept repeats and the grouping without kept and refuted ids, so a kept
    row is never aliased into a fresh finding and a fresh member is never filtered out with a kept one. The
    judge's names apply only when the grouping validates and the synthesis seat ran."""
    verified, refuted = state.get("_verified") or [], state.get("_refuted") or []
    pool = _earlier_pool(state)
    fault = repeat_marks.grouping_fault(verified, refuted, grouping, pool)
    judged = exact_only is None and fault is None
    staged = [f for f in verified + refuted if isinstance(f, dict)]
    marks = {}
    for sid, (entry, source) in repeat_marks.mark_repeats(
            staged, pool, repeat_marks.judge_refs(grouping) if judged else {}).items():
        finding = next(f for f in staged if f.get("id") == sid)
        kept, fix_holds = repeat_marks.decide(
            entry["outcome"], _grade_verdict(finding), lambda e=entry: _repeat_changed(state, session_dir, e))
        marks[sid] = {"finding": finding, "entry": entry, "source": source, "kept": kept, "fixHolds": fix_holds}
    kept_ids = {sid for sid, m in marks.items() if m["kept"]}
    # axis: a kept repeat is out of the survivors and every group before the merge, so it never merges into a fresh finding — see bite-proof record c1l8_wo_a_repeat_marks
    removed = kept_ids | {f.get("id") for f in refuted if isinstance(f, dict)}
    return {"marks": marks, "survivors": [s for s in verified if s.get("id") not in kept_ids],
            "grouping": repeat_marks.strip_groups(grouping, removed), "pool": pool,
            "matching": repeat_marks.MATCH_JUDGE if judged else repeat_marks.MATCH_EXACT_ONLY,
            "reason": exact_only or ("grouping-invalid" if fault else None)}


def _record_repeat(state, key, repeat_of, repeat_kept):
    """Write ``repeatOf`` (and ``repeatKept`` when kept) on the finding's ledger row, and on its live finding
    when it has one, so the later archive of a departed finding never replaces the marked row with an unmarked copy."""
    ledger = _ensure_disposition_ledger_for_write(state)
    seen = _ledger_index_by_key(ledger)
    rows = [ledger[seen[key]]] if key in seen else []
    live = _live_finding_by_key(state, key)
    # axis: the repeat mark is on the live finding too, so the archive that replaces the ledger row with the live copy keeps it — see bite-proof record c1l8_wo_a_repeat_marks
    rows += [live] if live is not None else []
    for row in rows:
        row["repeatOf"] = copy.deepcopy(repeat_of)
        row.pop("repeatKept", None)
        if repeat_kept is not None:
            row["repeatKept"] = copy.deepcopy(repeat_kept)


def _record_kept_disposition(state, key, entry, reason, grade_verdict, restore):
    """Give a kept repeat's row the disposition its earlier outcome stands for. A same-key repeat is the earlier
    finding itself (``restore``): its snapshotted decision family comes back, and a ``shown-wrong`` row this
    round's grade does not call wrong gets the snapshotted ``wrong`` grade back."""
    token = repeat_marks.disposition_of(entry["outcome"])
    fields = {} if token == "fixed" else {"refutedReason" if token == "refuted" else "settledReason": reason}
    round_no = state["round"]
    if restore:
        family = entry.get("family") or {}
        round_no = family.get("dispositionRound") if _is_plain_int(family.get("dispositionRound")) else round_no
        fields = dict({k: v for k, v in family.items() if k not in (
            "disposition", "dispositionRound", session_contract.MERGED_INTO_FIELD, "refutedReason",
            "settledReason")}, **fields)
    _record_disposition(state, key, token, round_no, **fields)
    held = entry.get(GRADE_FIELD)
    if restore and entry["outcome"] == repeat_marks.SHOWN_WRONG and grade_verdict != "wrong" \
            and isinstance(held, dict) and held.get("verdict") == "wrong":
        _record_grade(state, key, held)


def _apply_repeat_marks(state, plan):
    """Write each marked finding's ``repeatOf`` / ``repeatKept`` (and a kept repeat's disposition) on its ledger
    row, and the round's marks and matching mode on the round record."""
    rows = []
    for sid, mark in plan["marks"].items():
        finding, entry = mark["finding"], mark["entry"]
        key = _finding_identity_key(finding)
        if not key:
            continue
        repeat_of = {"findingKey": entry["key"], "id": entry.get("id"), "fixHolds": mark["fixHolds"]}
        original = entry.get("repeatOf") if mark["source"] == "exact" else None
        if isinstance(original, dict) and isinstance(original.get("findingKey"), str) \
                and original["findingKey"].strip() and original["findingKey"] not in (key, entry["key"]):
            # a finding matched to itself keeps its original link to the earlier finding it repeats: a self-link
            # would cut its route to that finding's verifier closure and duplicate its owner card
            # axis: the preserved link keeps its target and takes this round's fixHolds, never the old one — see bite-proof record c1l8_wo_a_repeat_marks
            repeat_of = {"findingKey": original["findingKey"], "id": original.get("id"), "fixHolds": mark["fixHolds"]}
        repeat_kept = None
        if mark["kept"]:
            reason = repeat_marks.kept_reason(entry, mark["fixHolds"])
            repeat_kept = {"outcome": entry["outcome"], "reason": reason}
            _record_kept_disposition(state, key, entry, reason, _grade_verdict(finding),
                                     mark["source"] == "exact" and entry["source"] == "session")
        _record_repeat(state, key, repeat_of, repeat_kept)
        rows.append({"id": sid, "findingKey": key, "source": mark["source"], "kept": mark["kept"],
                     "repeatOf": repeat_of, GRADE_FIELD: finding.get(GRADE_FIELD)})
    if plan["pool"]:
        _record_round(state, "repeatMatching", plan["matching"])
        if plan["reason"]:
            _record_round(state, "repeatMatchingReason", plan["reason"])
    if rows:
        _record_round(state, "repeatMarks", rows)


def _fold_synthesis(state, config, artifact, session_dir=None, exact_only=None):
    """Merge same-root-cause survivors (verification.merge_and_rank, coverage-guaranteed), then the
    author-justification POST-filter, then decide gap-sweep / fix / terminal. Repeats of an earlier finding
    are decided first (`_repeat_plan`); a kept repeat leaves the merge and the findings. ``exact_only``
    (a reason) marks by exact identity alone, as when the synthesis seat was not dispatched."""
    grouping = artifact.get("grouping") if isinstance(artifact.get("grouping"), list) else None
    verified = state.get("_verified") or []
    plan = _repeat_plan(state, grouping, session_dir, exact_only)
    merged = verification.merge_and_rank(plan["survivors"], plan["grouping"])
    findings = merged["findings"]
    kept, aj_drops = author_justification_filter(findings, config.get("priorComments"))
    for d in aj_drops:
        _decision(state, "author-justified-drop", d.get("justification"))
        staged_finding, fault = _resolve_staged_finding(verified, d.get("id"))
        if fault:
            _park_cannot_certify(state, fault)
            state["step"] = P_TERMINAL
            return
        if isinstance(staged_finding, dict):
            key = _finding_identity_key(staged_finding)
            if key:
                justification = d.get("justification") or ""
                _record_disposition(
                    state, key, "refuted", state["round"],
                    refutedReason="author-justified: " + justification)
    for merge in merged.get("merges") or []:
        if not isinstance(merge, dict):
            continue
        kept_id = merge.get("kept_id")
        kept_finding, kept_fault = _resolve_staged_finding(verified, kept_id)
        if kept_fault:
            _park_cannot_certify(state, kept_fault)
            state["step"] = P_TERMINAL
            return
        kept_key = _finding_identity_key(kept_finding) if isinstance(kept_finding, dict) else None
        if not kept_key:
            _park_cannot_certify(state, "%s: staged id %r has no derivable finding key"
                                % (STAGED_ID_UNRESOLVABLE_CAUSE, kept_id))
            state["step"] = P_TERMINAL
            return
        for member_id in merge.get("member_ids") or []:
            if member_id == kept_id:
                continue
            member, member_fault = _resolve_staged_finding(verified, member_id)
            if member_fault:
                _park_cannot_certify(state, member_fault)
                state["step"] = P_TERMINAL
                return
            if isinstance(member, dict):
                key = _finding_identity_key(member)
                if key:
                    _record_merged_into(state, key, kept_key)
    _record_round(state, "authorJustifiedDrops", aj_drops)
    _record_round(state, "merges", merged["merges"])
    _set_findings(state, kept)
    _sync_merged_consequences(state, kept)
    _apply_repeat_marks(state, plan)
    # big diff → a gap-sweep over verified findings + the whole diff, before the fix leg. (Not on
    # a delta settle — the delta round has its own scoped scan + audit breaker.)
    plan = delta_surface.shard_plan(state.get("reviewedDiff") or "")
    if plan.get("big") and not state.get("_settleDelta") \
            and not state.get("_gapSweptRound") == state["round"]:
        state["_gapSweptRound"] = state["round"]
        state["step"] = P_GAPSWEEP
        return
    _after_findings_settled(state, config)


def _fold_gapsweep(state, config, artifact):
    """Big-diff gap sweep: candidate findings from the full-diff pass fold through the same
    stage/cluster/verify path, then re-settle."""
    candidates = artifact.get("findings") if isinstance(artifact.get("findings"), list) else []
    compiled, drops = mechanical_compile(candidates, state.get("reviewedDiff"))
    _record_compile_drops(state, drops)
    if compiled:
        # route candidates through verification like any other findings.
        _stage_findings(state, compiled)
        state["_gapMerge"] = True
        state["step"] = P_VERIFIERS
        # after verifiers → synthesis will merge with the already-settled findings.
        state["_verifiedCarry"] = state.get("findings") or []
        return
    _after_findings_settled(state, config)


# One home: `round_orders.escape_placeholder_syntax` (the order renderer also escapes the threat-model
# and standing-rulings blocks with it).
_escape_guidance_placeholder_syntax = round_orders.escape_placeholder_syntax


def _guidance_oversize(text):
    """The one measure for owner guidance (#1691): True when the stripped text's UTF-8 length is over
    ``GATE_GUIDANCE_ROW_BYTE_CAP``. Gate submit, the fold, the ruling path and the order renderer all
    ask this."""
    return isinstance(text, str) and len(text.strip().encode("utf-8")) > GATE_GUIDANCE_ROW_BYTE_CAP


def _truncate_utf8_bytes(text, max_bytes):
    """Return ``(prefix, withheld_byte_count)`` truncating on a UTF-8 boundary."""
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text, 0
    cut = raw[:max_bytes]
    while cut:
        try:
            return cut.decode("utf-8"), len(raw) - len(cut)
        except UnicodeDecodeError:
            cut = cut[:-1]
    return "", len(raw)


def _normalize_gate_guidance_header_field(value):
    """Prepare one owner-gate guidance header field for safe single-line interpolation."""
    text = str(value)
    text = re.sub(r"[\x00-\x1f\x7f\u2028\u2029]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text, withheld = _truncate_utf8_bytes(text, GATE_GUIDANCE_HEADER_FIELD_BYTE_CAP)
    if withheld:
        text = "%s (%d bytes withheld)" % (text, withheld)
    return _escape_guidance_placeholder_syntax(text)


def _gate_guidance_header_file_part(entry):
    raw = entry.get("file")
    if isinstance(raw, str) and raw.strip():
        return _normalize_gate_guidance_header_field(raw.strip())
    return "(file not recorded)"


def _gate_guidance_header_line_part(entry):
    raw = entry.get("line")
    if raw is not None:
        return _normalize_gate_guidance_header_field(raw)
    return "(line not recorded)"


def _gate_guidance_identity_line(entry):
    file_part = _gate_guidance_header_file_part(entry)
    line_part = _gate_guidance_header_line_part(entry)
    raw = entry.get("title")
    title = _normalize_gate_guidance_header_field(raw if raw is not None else "")
    if not title:
        title = "(no title)"
    return "### %s:%s — %s" % (file_part, line_part, title)


def _gate_guidance_record_id_line(fid):
    label = fid.strip() if isinstance(fid, str) and fid.strip() else "(no finding id)"
    return "Record id (auditing only, not for matching): %s" % (
        _normalize_gate_guidance_header_field(label))


def _round_record_sort_key(rnd_key):
    """Numeric round order for ``state['rounds']`` keys; non-numeric keys sort last."""
    try:
        return (0, int(rnd_key))
    except (TypeError, ValueError):
        return (1, str(rnd_key))


def _fix_batch_row_key(row):
    """Disposition key for one fix-batch row — content-derived via ``_finding_key_of``."""
    if not isinstance(row, dict):
        return None
    return _finding_key_of(row)


def _history_row_key(row):
    """Identity of one durable history row (judgment log / audit record): the stamped
    findingKey marker when present; else the leaf's content derivation when the row carries a
    location and a label; else None. Never `id`."""
    if not isinstance(row, dict):
        return None
    marker = row.get(session_contract.FINDING_KEY_FIELD)
    if isinstance(marker, str) and marker:
        return marker
    if row.get("file") is None or row.get("line") is None:
        return None
    if not finding_label(row):
        return None
    return session_contract.finding_identity_key(row)


def _finding_history(state):
    """Latest gate and audit rulings per finding key across ``state['rounds']``."""
    history = {}
    rounds = state.get("rounds") if isinstance(state, dict) else None
    if not isinstance(rounds, dict):
        return history
    for rnd_key in sorted(rounds.keys(), key=_round_record_sort_key):
        round_entry = rounds[rnd_key]
        if not isinstance(round_entry, dict):
            continue
        try:
            rnd_num = int(rnd_key)
        except (TypeError, ValueError):
            continue
        log = round_entry.get("judgmentDispositions")
        if isinstance(log, list):
            for item in log:
                if not isinstance(item, dict):
                    continue
                key = _history_row_key(item)
                if not key:
                    continue
                gate_ruling = {"round": rnd_num, "disposition": item.get("disposition")}
                if item.get("reason") is not None:
                    gate_ruling["reason"] = item.get("reason")
                guidance = item.get(GATE_GUIDANCE_RECORD_KEY)
                if isinstance(guidance, str) and guidance.strip():
                    gate_ruling["guidance"] = guidance.strip()
                if item.get("title") is not None:
                    gate_ruling["title"] = item.get("title")
                if item.get("file") is not None:
                    gate_ruling["file"] = item.get("file")
                if item.get("line") is not None:
                    gate_ruling["line"] = item.get("line")
                slot = history.setdefault(key, {"gateRuling": None, "priorAudit": None})
                slot["gateRuling"] = gate_ruling
        audits = round_entry.get("audits")
        if isinstance(audits, list):
            for item in audits:
                if not isinstance(item, dict):
                    continue
                key = _history_row_key(item)
                if not key:
                    continue
                prior = {"round": rnd_num, "ruling": item.get("ruling")}
                if item.get("reason") is not None:
                    prior["reason"] = item.get("reason")
                if item.get("unauthenticatedCause") is not None:
                    prior["unauthenticatedCause"] = item.get("unauthenticatedCause")
                slot = history.setdefault(key, {"gateRuling": None, "priorAudit": None})
                slot["priorAudit"] = prior
    return history


def _validate_gate_guidance_logs(rounds, rnd, batch_keys):
    """Refuse untrustworthy fold-owned guidance ids in any round's judgment log."""
    if not isinstance(rounds, dict):
        return
    if batch_keys is None:
        batch_keys = set()
    for rnd_key in sorted(rounds.keys(), key=_round_record_sort_key):
        round_entry = rounds[rnd_key]
        if not isinstance(round_entry, dict):
            continue
        try:
            rnd_num = int(rnd_key)
        except (TypeError, ValueError):
            continue
        is_current = rnd_num == rnd
        log = round_entry.get("judgmentDispositions")
        if not isinstance(log, list):
            continue
        seen_ids = set()
        for item in log:
            if not isinstance(item, dict):
                continue
            if item.get("disposition") != "fix-with-guidance":
                continue
            guidance = item.get(GATE_GUIDANCE_RECORD_KEY)
            if not isinstance(guidance, str) or not guidance.strip():
                continue
            key = _history_row_key(item)
            if not key:
                if is_current:
                    raise ValueError("order-render-refused:%s" % GATE_GUIDANCE_UNUSABLE_REFUSAL)
                continue
            if key in seen_ids:
                if is_current or key in batch_keys:
                    raise ValueError("order-render-refused:%s" % GATE_GUIDANCE_UNUSABLE_REFUSAL)
            seen_ids.add(key)


def _gate_guidance_entries(state, rnd):
    """Return validated fold-owned guidance records for order rendering."""
    rounds = state.get("rounds") if isinstance(state, dict) else None
    if not isinstance(rounds, dict):
        return []
    batch = state.get("_fixBatch")
    if not isinstance(batch, list):
        batch = state.get("fixBatch")
    if not isinstance(batch, list):
        batch = []
    batch_keys = set()
    for row in batch:
        key = _fix_batch_row_key(row)
        if key:
            batch_keys.add(key)
    sliced = bool(state.get("_fixQueue")) or (state.get("_fixBatchIndex") or 0) >= 1
    _validate_gate_guidance_logs(rounds, rnd, batch_keys)
    effective = _live_ruling_by_key(state)
    if _read_rulings_log(state)[1] is not None:
        # An unreadable rulings log still hides every rule decision (the reader returns {}); the
        # owner-gate decisions stay readable on their own, as they were before the shared reader.
        effective = _effective_decisions(state, with_rules=False)

    # The decision the resolution point selected for a row is rendered as selected: the row names
    # it by finding key and sequence, and no lookup by the key alone can pick a different one.
    selected = {}
    for row in batch:
        if isinstance(row, dict) and row.get("ruledBy"):
            for decision in effective.values():
                if (decision.get("findingKey") == row["ruledBy"]
                        and decision.get("seq") == row.get("ruledBySeq")
                        and decision.get("ruling") in _OWNER_FIX_RULINGS):
                    selected[_fix_batch_row_key(row)] = decision

    def guided(key):
        """The effective decision for ``key`` (the one the resolution point attached to its batch
        row, when a ruling was given to a finding merged into it) when it is a usable ``guidance``,
        else None."""
        live = selected.get(key, effective.get(key))
        if not isinstance(live, dict) or live.get("ruling") != "guidance":
            return None
        guidance = live.get("guidance")
        if not isinstance(guidance, str) or not guidance.strip():
            return None
        return live

    out = []
    covered_keys = set()
    round_entry = rounds.get(str(rnd))
    if isinstance(round_entry, dict):
        log = round_entry.get("judgmentDispositions")
        if isinstance(log, list):
            for item in log:
                if not isinstance(item, dict):
                    continue
                if item.get("disposition") != "fix-with-guidance":
                    continue
                guidance = item.get(GATE_GUIDANCE_RECORD_KEY)
                if not isinstance(guidance, str) or not guidance.strip():
                    continue
                key = _history_row_key(item)
                if not key:
                    continue
                if sliced and key not in batch_keys:
                    continue
                live = guided(key)
                if (live is None or live.get("source") != "gate" or live.get("findingKey") != key
                        or str(live.get("round")) != str(rnd)
                        or live.get("guidance") != guidance.strip()):
                    continue
                covered_keys.add(key)
                out.append({"id": key, "title": item.get("title"),
                            "file": item.get("file"), "line": item.get("line"),
                            "guidance": guidance.strip()})
    ruling_channel = []
    batch_rows = {_fix_batch_row_key(row): row for row in batch if isinstance(row, dict)}
    for key in sorted(batch_keys):
        if key in covered_keys:
            continue
        live = guided(key)
        if live is None:
            continue
        carried_from = live.get("findingKey") if live.get("findingKey") != key else None
        live_row = _live_finding_by_key(state, key) or batch_rows.get(key)  # restaged: only the batch row
        if live.get("source") == "gate":
            entry = {"id": key, "title": live.get("title"), "file": live.get("file"),
                     "line": live.get("line"), "guidance": live["guidance"].strip(),
                     "round": live.get("round")}
            if carried_from is not None and isinstance(live_row, dict):
                for field in ("title", "file", "line"):
                    if live_row.get(field) is not None:
                        entry[field] = live_row.get(field)
            if carried_from is not None:
                entry["carriedFrom"] = carried_from
            out.append(entry)
            continue
        entry = {"id": key, "guidance": live["guidance"].strip(), "rulingChannel": True}
        if isinstance(live_row, dict):
            for field in ("title", "file", "line"):
                if live_row.get(field) is not None:
                    entry[field] = live_row.get(field)
        if carried_from is not None:
            entry["carriedFrom"] = carried_from
        ruling_channel.append(entry)
    return out + ruling_channel


def _gate_guidance_block(entries):
    """Derive the owner-gate guidance prose the build session reads for an apply-fixes step.

    The only producer of owner-gate guidance prose in the fix guidance file. Input is the
    pre-validated list from ``_gate_guidance_entries``. Wording never claims whether a gate ran.
    The block never omits an entry; over the aggregate cap it refuses."""
    if not isinstance(entries, list):
        return _GATE_GUIDANCE_NO_GUIDANCE
    guided = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        guidance = entry.get("guidance")
        if not isinstance(guidance, str) or not guidance.strip():
            continue
        fid = entry.get("id")
        fid_stripped = fid.strip() if isinstance(fid, str) and fid.strip() else None
        guided.append((entry, guidance.strip(), fid_stripped))
    if not guided:
        return _GATE_GUIDANCE_NO_GUIDANCE
    for _entry, guidance, _fid in guided:
        if _guidance_oversize(guidance):
            raise ValueError("order-render-refused:%s" % GATE_GUIDANCE_OVERSIZE)
    identity_counts = {}
    identity_lines = []
    for entry, _guidance, _fid in guided:
        identity_line = _gate_guidance_identity_line(entry)
        identity_lines.append(identity_line)
        identity_counts[identity_line] = identity_counts.get(identity_line, 0) + 1
    parts = []
    aggregate_bytes = 0
    for idx, ((entry, guidance, fid), identity_line) in enumerate(zip(guided, identity_lines)):
        from_ruling = bool(entry.get("rulingChannel"))
        if from_ruling and aggregate_bytes >= GATE_GUIDANCE_AGGREGATE_BYTE_CAP:
            raise ValueError("order-render-refused:%s" % RULING_GUIDANCE_OMITTED)
        if aggregate_bytes >= GATE_GUIDANCE_AGGREGATE_BYTE_CAP:
            if any(guided[j][0].get("rulingChannel") for j in range(idx, len(guided))):
                raise ValueError("order-render-refused:%s" % RULING_GUIDANCE_OMITTED)
            raise ValueError("order-render-refused:%s" % GATE_GUIDANCE_AGGREGATE_OVERSIZE)
        header_lines = [identity_line]
        entry_round = entry.get("round")
        if entry_round is not None:
            header_lines.append("Ruled in round %s" % entry_round)
        if identity_counts[identity_line] >= 2:
            header_lines.append(
                "Note: %d guided findings share this identity (file, line, title) — "
                "read all guidance blocks before applying any fix."
                % identity_counts[identity_line])
        header_lines.append(_gate_guidance_record_id_line(fid))
        escaped = _escape_guidance_placeholder_syntax(guidance)
        body_lines = ["BEGIN owner-gate guidance"]
        for line in escaped.splitlines() or [""]:
            body_lines.append("> " + line)
        body_lines.append("END owner-gate guidance")
        entry_text = "\n".join(header_lines + body_lines)
        entry_bytes = len(entry_text.encode("utf-8"))
        remaining = GATE_GUIDANCE_AGGREGATE_BYTE_CAP - aggregate_bytes
        if entry_bytes > remaining:
            if from_ruling:
                raise ValueError("order-render-refused:%s" % RULING_GUIDANCE_OMITTED)
            if any(guided[j][0].get("rulingChannel") for j in range(idx + 1, len(guided))):
                raise ValueError("order-render-refused:%s" % RULING_GUIDANCE_OMITTED)
            raise ValueError("order-render-refused:%s" % GATE_GUIDANCE_AGGREGATE_OVERSIZE)
        parts.append(entry_text)
        aggregate_bytes += entry_bytes
    result = "\n\n".join(parts)
    while "{{" in result:
        result = _escape_guidance_placeholder_syntax(result)
    return result


def _hold_owner_choice(state, blocking):
    """Triage before composing an autonomous fix batch. A blocking finding carrying `tradeoff: true`
    is a PRODUCT-CHOICE call only the owner can settle, so it is held OUT of the fix batch: the
    batch returns without it, its identity key joins the persisted `ownerChoiceHeld` list (deduped,
    append-only) and the hold is journaled once per call. A held finding is not dropped — it is
    handed back open unless something settles it (`_terminal_converged` refuses to converge over an
    unsettled one), and an effective `rule` decision that names it still sends it to the fixer
    through `_resolve_ruled_batch`, which this does not touch. Returns the rest of the batch."""
    # A tradeoff whose effective decision is already a (non-Critical) skip — the owner's own, or one
    # carried to a rewording — is not held again: the fix-batch exclusion honors it.
    decided_out = _live_out_of_scope_ruling_keys(state)
    # A tradeoff whose effective decision is a guidance/fix ruling is the owner's call already made:
    # it stays in the batch for ordinary blocking-work routing instead of being held again.
    ledger_by_key, ledger_fault = _disposition_ledger_by_key(state)
    effective = {} if ledger_fault is not None else _live_ruling_by_key(state)

    def _decided_to_fix(f):
        key = _finding_key_of(f)
        decision = _row_decision(state, effective, ledger_by_key, key) if key else None
        return isinstance(decision, dict) and decision.get("ruling") in _OWNER_FIX_RULINGS

    held = [f for f in blocking if isinstance(f, dict) and f.get("tradeoff")
            and not (_finding_key_of(f) in decided_out
                     and not _live_out_of_scope_blocks_row(f))
            and not _decided_to_fix(f)]
    if not held:
        return list(blocking)
    keys = state.get("ownerChoiceHeld")
    if not isinstance(keys, list):
        keys = state["ownerChoiceHeld"] = []
    for f in held:
        key = _finding_key_of(f)
        if key not in keys:
            keys.append(key)
    _decision(state, "owner-choice-held",
              "%d tradeoff/product-choice blocker(s) held out of the fix batch — only the owner's "
              "choice can settle them: %s"
              % (len(held), "; ".join(f.get("title") or "?" for f in held)))
    held_ids = {id(f) for f in held}
    return [f for f in blocking if id(f) not in held_ids]


def _owner_choice_settled(state, ledger_by_key, effective, key):
    """True when something has settled a held finding: its ledger row carries a current `fixed` or
    `refuted` disposition (a fixed guidance/fix ruling lands here), or its effective decision is an
    out-of-scope ruling that a Critical escalation has not outgrown."""
    row = ledger_by_key.get(key)
    live_member = _live_finding_by_key(state, key)
    member = live_member if isinstance(live_member, dict) and live_member.get(
        session_contract.MERGED_INTO_FIELD) else row
    if isinstance(member, dict) and member.get(session_contract.MERGED_INTO_FIELD):
        # Merged into a representative: that one's disposition settles it, provided it is current
        # against this member's latest raise; an unresolved chain settles nothing.
        target = session_contract.resolve_merged_into_entry(member, ledger_by_key)
        if isinstance(target, dict) and target is not member:
            target_key = _finding_identity_key(target)
            member_raised = max(
                (v for v in (member.get(session_contract.RAISED_SEQ_FIELD),
                             (row or {}).get(session_contract.RAISED_SEQ_FIELD)) if _is_plain_int(v)),
                default=None)
            disp_seq = target.get(session_contract.DISPOSITION_SEQ_FIELD)
            if (target.get("disposition") in ("fixed", "refuted") and _disposition_is_current(target)
                    and not _restaged_after(state, target_key, target)
                    and (member_raised is None
                         or (_is_plain_int(disp_seq) and disp_seq > member_raised))):
                return True
    elif (isinstance(row, dict) and row.get("disposition") in ("fixed", "refuted")
            and _disposition_is_current(row) and not _restaged_after(state, key, row)):
        return True
    decision = _row_decision(state, effective, ledger_by_key, key)
    if isinstance(decision, dict) and decision.get("ruling") == "out-of-scope":
        live = _live_finding_by_key(state, key) or row
        return not (isinstance(live, dict) and _escalated_since_out_of_scope(decision, live))
    return False


def _unsettled_owner_choices(state):
    """``[(key, title)]`` for every finding held for the owner's choice that nothing has settled.
    A ledger that cannot be read settles nothing: every held finding is unsettled (fail closed)."""
    held = state.get("ownerChoiceHeld")
    if held is None:
        return []
    if not isinstance(held, list):
        return [("ownerChoiceHeld", "the held-finding list is unreadable")]
    ledger_by_key, fault = _disposition_ledger_by_key(state)
    effective = {} if fault is not None else _live_ruling_by_key(state)
    unsettled = []
    for key in held:
        if fault is None and isinstance(key, str) and _owner_choice_settled(
                state, ledger_by_key, effective, key):
            continue
        row = None
        if isinstance(key, str):
            row = _live_finding_by_key(state, key) or ledger_by_key.get(key)
        title = row.get("title") if isinstance(row, dict) else None
        unsettled.append((key, title or str(key)))
    return unsettled


def _after_findings_settled(state, config):
    """After the round's findings are verified + merged + justification-filtered: route to the fix
    leg when there is a blocking finding, else to the terminal decision (round 1 clean = certify).

    ONE definition (no post-def override): a delta round routes its scoped/gap candidates through
    verify+synthesis, so when the delta settle is armed it must re-settle the delta (audit breaker)
    rather than the round-1 fix/terminal path. Either way the gap/verify
    carry is merged back first."""
    # merge any gap-sweep / verify carry back in.
    if state.get("_verifiedCarry") is not None:
        carry = state.pop("_verifiedCarry")
        _set_findings(state, (carry or []) + (state.get("findings") or []))
        state.pop("_gapMerge", None)
    if state.get("_settleDelta"):
        _settle_delta(state, config)
        return
    blocking = _blocking(state.get("findings") or [])
    _record_round(state, "blockingCount", len(blocking))
    if blocking:
        batch = _hold_owner_choice(state, blocking)
        # A round whose only blockers are held for the owner has nothing to fix: it settles, and the
        # convergence chokepoint hands the held findings back open.
        if _queue_fix_batch(state, config, [dict(f) for f in batch]) == "empty":
            _terminal_converged(state, config, full_panel=state.get("fullPanelRan"))
    elif _queue_fix_batch(state, config, []) == "empty":
        _terminal_converged(state, config, full_panel=state.get("fullPanelRan"))


# ---- fix + verify legs ----------------------------------------------------------------------

def _disposition_ledger_by_key(state):
    """Non-mutating ledger lookup keyed by finding identity — ``None`` on read fault."""
    owner = session_contract.disposition_ledger_owner_classification(state)
    if owner == session_contract.DISPOSITION_LEDGER_OWNER_ABSENT:
        by_key = {}
        for key, entry in session_contract.legacy_disposition_ledger_rows(state):
            if key:
                by_key[key] = entry
        return by_key, None
    required = owner == session_contract.DISPOSITION_LEDGER_OWNER_RECOGNIZED
    ledger_rows, fault = session_contract.read_disposition_ledger(state, required=required)
    if fault is not None:
        return {}, fault
    by_key = {}
    for entry in ledger_rows:
        key = _finding_identity_key(entry)
        if key:
            by_key[key] = entry
    return by_key, None


def _excluded_discharged_fix_row(ledger_by_key, row, restaged=None):
    """True when a discharged fix must not re-enter the fix batch (A1 chokepoint predicate).

    ``restaged`` maps a finding key to the disposition counter when an owner ruling sent its finding
    back to a fixer: a disposition at or before that mark is the one the ruling reopened, not a
    discharge."""
    key = _finding_identity_key(row)
    if not key:
        return False
    entry = ledger_by_key.get(key)
    if not isinstance(entry, dict):
        return False
    if entry.get("disposition") != "fixed":
        return False
    disp_seq = entry.get(session_contract.DISPOSITION_SEQ_FIELD)
    raised_seq = entry.get(session_contract.RAISED_SEQ_FIELD)
    disp_is_int = isinstance(disp_seq, int) and not isinstance(disp_seq, bool)
    raised_is_int = isinstance(raised_seq, int) and not isinstance(raised_seq, bool)
    if disp_is_int and raised_is_int:
        mark = (restaged or {}).get(key)
        if _is_plain_int(mark) and disp_seq <= mark:
            return False
        return disp_seq > raised_seq
    return False


def _filter_excluded_discharged_fixes(state, rows):
    if not rows:
        return rows, None
    ledger_by_key, fault = _disposition_ledger_by_key(state)
    if fault is not None:
        return rows, fault
    oos_keys = _live_out_of_scope_ruling_keys(state)
    restaged = state.get("restagedAfterDispositionSeq") or {}
    effective = _live_ruling_by_key(state)
    filtered = []
    for row in rows:
        if _excluded_discharged_fix_row(ledger_by_key, row, restaged):
            continue
        key = _fix_batch_row_key(row)
        if key and key in oos_keys and not _live_out_of_scope_blocks_row(row):
            bound = _row_decision(state, effective, ledger_by_key, key)
            if bound is None or bound.get("ruling") not in _OWNER_FIX_RULINGS:
                continue  # a newer fix ruling given to a merged-in finding outranks the skip
        filtered.append(row)
    return filtered, None


def _out_of_scope_episode(decision):
    """The episode id of an out-of-scope decision: its ``seq``, or ``round:<n>`` for an unsequenced
    legacy gate decision."""
    seq = decision.get("seq")
    if _is_plain_int(seq):
        return seq
    return "round:%s" % decision.get("round")


def _escalated_since_out_of_scope(decision, row):
    """True when ``row`` is Critical now but the out-of-scope decision recorded a lower severity at
    ruling time (the decision's own snapshot: the ledger entry is replaced on every restage)."""
    if not isinstance(decision, dict) or not circuit_breaker.is_critical(row.get("severity")):
        return False
    recorded = decision.get("severity")
    if isinstance(recorded, str) and recorded.strip().lower() in circuit_breaker._TIER_BY_LOWER:
        return not circuit_breaker.is_critical(recorded)
    # A missing or unrecognized snapshot (the older decision shape) is unknown: not spent, so a
    # Critical stays in the batch (fail toward fixing).
    return True


def _drop_spent_out_of_scope_rows(state, rows):
    """``(kept, spent)``: ``rows`` less those whose finding is out of scope and was already offered to
    a fixer in an earlier round of the same episode. A row that passes while out of scope is recorded
    in ``state["outOfScopeFixerRounds"]`` (keyed by the finding's own key). A spent row's out-of-scope
    disposition is recorded again with the round it was offered in, keeping its ``followUp``."""
    effective = _live_ruling_by_key(state)
    ledger_by_key, _fault = _disposition_ledger_by_key(state)
    this_round = state["round"]
    spent_log = state.get("outOfScopeFixerRounds")
    if not isinstance(spent_log, dict):
        spent_log = {}
    kept, spent = [], []
    for row in rows:
        key = _fix_batch_row_key(row)
        decision = _row_decision(state, effective, ledger_by_key, key) if key else None
        if not isinstance(decision, dict) or decision.get("ruling") != "out-of-scope":
            kept.append(row)
            continue
        if _escalated_since_out_of_scope(decision, row):
            # Ruled out of scope while below Critical, now a Critical blocker: the ruling never
            # covered it. Dropping it would empty the batch and let the review certify with the
            # Critical still open, so it stays in the batch; the round caps bound repeat offers.
            kept.append(row)
            continue
        episode = _out_of_scope_episode(decision)
        # The record is keyed by the finding's own identity: two findings that share a lineage root
        # but carry separate decisions each keep their own episode, so neither overwrites the other.
        held = spent_log.get(key)
        offered = (held.get("rounds") if isinstance(held, dict) and held.get("episode") == episode
                   and isinstance(held.get("rounds"), list) else [])
        earlier = [rnd for rnd in offered if rnd != this_round]
        if earlier:
            spent.append((key, row, earlier[0]))
            continue
        spent_log[key] = {"episode": episode, "rounds": [this_round]}
        kept.append(row)
    if spent_log:
        state["outOfScopeFixerRounds"] = spent_log
    for key, row, offered_round in spent:
        held_row = ledger_by_key.get(key)
        if not isinstance(held_row, dict):
            held_row = row
        # Re-record the disposition whole (it replaces the family), keeping what it carried — its
        # followUp included, from the effective decision when a restage dropped it from the snapshot.
        fields = {name: value for name, value
                  in session_contract.disposition_family_snapshot(held_row).items()
                  if name not in ("disposition", "dispositionRound")}
        recovered = _follow_up_of(_live_out_of_scope_ruling_for_key(state, key))
        if recovered and not _follow_up_of(fields):
            session_contract.copy_follow_up_field({"followUp": recovered}, fields)
        reason = (
            "out of scope; already offered to a fixer in round %s and not offered again while it "
            "stays out of scope" % offered_round)
        _record_disposition(state, key, "out-of-scope", this_round,
                            **dict(fields, outOfScopeReason=reason))
        _decision(state, "out-of-scope-fix-spent",
                  "%s is out of scope and was already offered to a fixer in round %s — not offered "
                  "again" % (key, offered_round))
    return kept, [key for key, _row, _rnd in spent]


def _resolve_empty_fix_batch_convergence(state, config):
    """Route an exclusion-emptied batch through the path's own resolver (A2)."""
    round_rec = state.get("rounds", {}).get(str(state["round"]), {})
    if round_rec.get("roundKind") == "delta":
        _settle_delta_converged(state, config)
        return
    _terminal_converged(state, config, full_panel=state.get("fullPanelRan"))


def _fix_row_roots(state, rows, ledger_by_key=None):
    """The ruling roots of the finding keys the ``rows`` hold — a reworded finding, the one it
    rewords and the findings merged into either are one finding."""
    roots = set()
    for row in rows or []:
        key = _fix_batch_row_key(row)
        if key:
            roots.add(_ruling_root(state, ledger_by_key or {}, key))
    return roots


# The effective decisions that are the owner's word to fix a finding: a fix choice at the owner gate
# and guidance (from the gate or the `rule` verb).
_OWNER_FIX_RULINGS = ("fix", "guidance")


def _decision_seq(decision):
    seq = decision.get("seq") if isinstance(decision, dict) else None
    return seq if _is_plain_int(seq) else 0


def _ruling_root(state, ledger_by_key, key):
    """The one identity a ruling is matched on: the smallest key of ``key``'s ``_ruling_closure`` —
    the same closure ``_ruled_row`` locates a row by, so every member of the group shares one root."""
    return min(_ruling_closure(state, ledger_by_key, key))


def _row_decision(state, effective, ledger_by_key, key):
    """The decision that binds the fix-batch row ``key``: its own effective decision, or a later
    ``guidance``/``fix`` decision given to a finding that was merged into it."""
    best = effective.get(key)
    root = _ruling_root(state, ledger_by_key, key)
    for member, decision in effective.items():
        if (member != key and decision.get("ruling") in _OWNER_FIX_RULINGS
                and _ruling_root(state, ledger_by_key, member) == root
                and (best is None or _decision_order((0, decision)) > _decision_order((0, best)))):
            best = decision
    return best


def _reopened_ledger_row(ledger_by_key, key):
    """The finding's own ledger row as an open finding again (its disposition dropped), or None."""
    row = ledger_by_key.get(key)
    if not isinstance(row, dict):
        return None
    reopened = _strip_disposition_family(dict(row))
    reopened.pop(session_contract.DISPOSITION_SEQ_FIELD, None)
    return reopened


def _ruling_closure(state, ledger_by_key, key):
    """Every key ``key`` reaches by alternating lineage-group membership and ``mergedInto`` (a key
    merged into another, or another merged into it), until no new key appears. Cycle-safe."""
    merged_into = {}
    for finding in list(state.get("findings") or []) + list(ledger_by_key.values()):
        at = _finding_identity_key(finding) if isinstance(finding, dict) else None
        into = finding.get(session_contract.MERGED_INTO_FIELD) if at else None
        if isinstance(into, str) and into:
            merged_into.setdefault(at, into)
    seen, todo = set(), [key]
    while todo:
        at = todo.pop()
        if at in seen:
            continue
        seen.add(at)
        todo += _lineage_group(state, at)
        todo += [merged_into[at]] if at in merged_into else []
        todo += [k for k, into in merged_into.items() if into == at]
    return seen


def _ruled_row(state, ledger_by_key, decision, sent, effective=None):
    """``(row, from_ledger)`` for the row an owner decision sends to a fixer, ``(None, False)`` when
    it names no live finding: the one live, unmerged finding in the ruling's closure, else the
    restage candidate from the ledger (a finding a fixer order carried before the ruling, or one that
    left the live list with no disposition)."""
    lineage = _lineage_map(state)
    closure = sorted(_ruling_closure(state, ledger_by_key, decision["findingKey"]))
    if effective is None:
        effective = _live_ruling_by_key(state)
    for at in closure:
        row = _live_finding_by_key(state, at)
        if (isinstance(row, dict) and not row.get(session_contract.MERGED_INTO_FIELD)
                and not (row.get("disposition") in ("fixed", "refuted")
                         and _disposition_is_current(row))
                and _row_decision(state, effective, ledger_by_key, at) is decision):
            return dict(row), False
    sent_before = any(_lineage_root(lineage, k) in sent for k in closure)
    latest = None  # the most recently raised eligible version, not the first lexical one
    for at in closure:
        ledger_row = ledger_by_key.get(at)
        if ((sent_before or not session_contract.disposition_value(ledger_row))
                and not (isinstance(ledger_row, dict) and ledger_row.get(session_contract.MERGED_INTO_FIELD))
                and _row_decision(state, effective, ledger_by_key, at) is decision):
            row = _reopened_ledger_row(ledger_by_key, at)
            if row is None:
                continue
            raised = (ledger_row.get(session_contract.RAISED_ROUND_FIELD),
                      ledger_row.get(session_contract.RAISED_SEQ_FIELD))
            order = tuple(v if _is_plain_int(v) else -1 for v in raised)
            if latest is None or order > latest[0]:
                latest = (order, row)
    return (latest[1], True) if latest else (None, False)


def _undispatched_ruling(state, effective, ledger_by_key, key):
    """The owner ``fix``/``guidance`` decision binding ``key`` that no fixer was ever sent, or None."""
    decision = _row_decision(state, effective, ledger_by_key, key)
    if (not isinstance(decision, dict) or decision.get("ruling") not in _OWNER_FIX_RULINGS
            or not _is_plain_int(decision.get("seq"))):
        return None
    lineage = _lineage_map(state)
    sent = state.get("sentUnderDecision") or {}
    ats = (key, decision["findingKey"])
    if any(sent.get(_lineage_root(lineage, at), -1) >= decision["seq"] for at in ats):
        return None
    return decision


def _resolve_ruled_batch(state, rows):
    """THE one place a ruling reaches a fixer's batch — worked out once, as the batch is finalized.

    ``rows`` are the findings already offered (after the out-of-scope and discharge exclusions). Each
    effective ``guidance``/``fix`` decision is attached to the row it binds (``ruledBy``), and each
    finding such a decision names that no fixer has been sent under that decision joins the batch,
    whatever its severity (``sentUnderDecision``: the decision's ``seq`` it was last sent under, by
    lineage root). A decision that names no live finding is recorded and left to the settle."""
    ledger_by_key, fault = _disposition_ledger_by_key(state)
    if fault is not None:
        return list(rows)
    effective = _live_ruling_by_key(state)
    lineage = _lineage_map(state)
    sent = state.get("sentUnderDecision") or {}
    batch = [dict(row) for row in rows]
    held = _fix_row_roots(state, batch, ledger_by_key)
    added = []
    decisions = {id(d): d for d in effective.values()}.values()
    for decision in sorted(decisions, key=_decision_seq):
        if (decision.get("ruling") not in _OWNER_FIX_RULINGS or not _is_plain_int(decision.get("seq"))
                or sent.get(_lineage_root(lineage, decision["findingKey"]), -1) >= decision["seq"]):
            continue
        row, from_ledger = _ruled_row(state, ledger_by_key, decision, sent, effective)
        key = _fix_batch_row_key(row) if row else None
        if key is None:
            note = "ruling %s on %s names no live finding" % (decision["seq"], decision["findingKey"])
            if not any(d["kind"] == "ruling-no-live-finding" and d["detail"] == note
                       for d in state["decisions"]):
                _decision(state, "ruling-no-live-finding", note)
            continue
        root = _ruling_root(state, ledger_by_key, key)
        if _row_decision(state, effective, ledger_by_key, key) is not decision:
            continue
        queued = root in held  # already offered: the ruling is satisfied by that row, not restaged
        held.add(root)
        own = set()
        if from_ledger and not queued:  # the ledger keeps its disposition; mark it as the one this ruling reopened
            state.setdefault("restagedAfterDispositionSeq", {})[_finding_identity_key(row)] = (
                state.get("dispositionSeqCounter", 0))
            state.setdefault("restagedInRound", {})[_finding_identity_key(row)] = state["round"]
            own = {key, _finding_identity_key(row)}
        elif not queued:
            own = {key}
        # the closure's discharged members are reopened too, whichever way the ruled row was reached
        for member in _ruling_closure(state, ledger_by_key, key) - own:
            entry = ledger_by_key.get(member)
            if (isinstance(entry, dict) and entry.get("disposition") in ("fixed", "refuted")
                    and _disposition_is_current(entry)):
                state.setdefault("restagedAfterDispositionSeq", {})[member] = (
                    state.get("dispositionSeqCounter", 0))
                state.setdefault("restagedInRound", {})[member] = state["round"]
        if not queued:
            added.append(row)
    added.sort(key=lambda row: circuit_breaker.severity_rank(row.get("severity")))
    if added:
        _decision(state, "fix-batch-ruled",
                  "%d finding(s) named by an owner ruling join this fix batch: %s"
                  % (len(added), ", ".join(_fix_batch_row_key(row) for row in added)))
    batch += added
    for row in batch:
        row.pop("ruledBy", None)
        row.pop("ruledBySeq", None)
        key = _fix_batch_row_key(row)
        decision = _row_decision(state, effective, ledger_by_key, key) if key else None
        if decision is not None and decision is not effective.get(key):
            row["ruledBy"] = decision["findingKey"]  # a ruling given to a merged-in finding
            row["ruledBySeq"] = decision.get("seq")
    return batch


def _note_sent_under_decision(state, rows):
    """Remember, by lineage root, the decision each row of an emitted slice goes to a fixer under
    (0 when none): a decision is sent once, and a finding sent before a ruling can be sent back."""
    ledger_by_key, _fault = _disposition_ledger_by_key(state)
    effective = _live_ruling_by_key(state)
    lineage = _lineage_map(state)
    sent = state.setdefault("sentUnderDecision", {})
    for row in rows:
        key = _fix_batch_row_key(row)
        decision = _row_decision(state, effective, ledger_by_key, key) if key else None
        for at in {key, decision.get("findingKey") if decision else None} - {None}:
            root = _lineage_root(lineage, at)
            sent[root] = max(sent.get(root, 0), _decision_seq(decision))


def _queue_fix_batch(state, config, rows, *, reset_accumulator=True, batch_index=0,
                     keep_step_start=False):
    """The ONE writer of ``state["_fixBatch"]`` — slice the round's blocking batch by cap.

    It also records the head the step starts at (``_fixStepHead``) and clears the staged PR body
    snapshot the next emission takes. ``keep_step_start`` re-slices the step already under way (a
    ruling arriving) and leaves both as they are.

    Every batch passes ``_resolve_ruled_batch``, which adds the findings an owner ruling names. With
    no offered row and none named, nothing is recorded and the caller settles.

    May terminate the round (park cannot-certify or resolve empty-batch convergence) instead of
    setting P_APPLY_FIXES. Returns ``"queued"`` when a fix batch was queued, ``"excluded"`` when
    the batch was emptied by discharge exclusion (settling the round only when ``batch_index``
    is 0; on a continuation the caller enters post-fix), ``"empty"`` when no row was offered and
    none is named by a ruling (the caller settles), or ``"faulted"`` when a disposition-
    ledger read fault parked the session.
    """
    cap = _fix_batch_cap(config)
    offered_nonempty = bool(rows)
    filtered, ledger_fault = _filter_excluded_discharged_fixes(state, rows)
    if ledger_fault is not None:
        _park_cannot_certify(state, ledger_fault.detail)
        return "faulted"
    discharge_survivors = len(filtered)
    spent_keys = []
    if filtered:
        filtered, spent_keys = _drop_spent_out_of_scope_rows(state, filtered)
    filtered = _resolve_ruled_batch(state, filtered)
    if not filtered and not offered_nonempty:
        return "empty"
    if reset_accumulator:
        state["fixBatch"] = []
    if not filtered:
        # Only rows the discharge filter dropped count as excluded by discharge; rows the
        # once-per-episode rule dropped do not.
        excluded_by_discharge = len(rows) - discharge_survivors
        if excluded_by_discharge:
            rec = state["rounds"].setdefault(str(state["round"]), {})
            prior = rec.get("fixBatchExcludedByDischarge") or 0
            _record_round(state, "fixBatchExcludedByDischarge", prior + excluded_by_discharge)
        why = ("discharged-finding exclusion" if not spent_keys else
               "the once-per-episode out-of-scope rule (%d finding(s) already offered for a fix)"
               % len(spent_keys))
        if batch_index == 0:
            _decision(state, "fix-batch-excluded",
                      "fix batch emptied by %s — no fixes to apply" % why)
            _resolve_empty_fix_batch_convergence(state, config)
        else:
            _decision(state, "fix-batch-excluded",
                      "fix batch emptied by %s — remaining queue exhausted, the round proceeds "
                      "to post-fix" % why)
        return "excluded"
    _note_sent_under_decision(state, filtered[:cap])
    state["_fixBatch"] = filtered[:cap]
    state["_fixQueue"] = filtered[cap:]
    state["_fixBatchIndex"] = batch_index
    if not keep_step_start:
        state["_fixStepHead"] = _fix_step_head(config)
        state.pop("_prBodyAtStep", None)
    state["step"] = P_APPLY_FIXES
    return "queued"


def _fix_step_head(config):
    """The head the apply-fixes step starts at: HEAD of the configured repository, else None."""
    repo_root = config.get("repoRoot") if isinstance(config, dict) else None
    if not _nonempty_str(repo_root):
        return None
    head = store_core.run_git(repo_root, "rev-parse", "HEAD")
    return head if _nonempty_str(head) else None


def _offered_fix_rows(state, extra_rows=None):
    """Current fix slice plus queue, then any extra rows (guidance-lifted) not already present."""
    offered = []
    seen = set()
    for row in list(state.get("_fixBatch") or []) + list(state.get("_fixQueue") or []):
        if not isinstance(row, dict):
            continue
        key = _fix_batch_row_key(row)
        if key:
            if key in seen:
                continue
            seen.add(key)
        offered.append(row)
    for row in extra_rows or []:
        if not isinstance(row, dict):
            continue
        key = _fix_batch_row_key(row)
        if key:
            if key in seen:
                continue
            seen.add(key)
        offered.append(dict(row))
    return offered


def _sync_pending_after_ruling_reconcile(state):
    """Drop or refresh a stored apply-fixes pending whose payload no longer matches the reconciled slice."""
    pending = state.get("pending")
    fix_pending = isinstance(pending, dict) and pending.get("phase") == P_APPLY_FIXES
    if state.get("terminal") or state.get("step") != P_APPLY_FIXES:
        if fix_pending:
            state["pending"] = None
        return
    if not fix_pending:
        return
    payload = dict(pending.get("payload") or {})
    payload["batch"] = list(state.get("_fixBatch") or [])
    updated = dict(pending)
    updated["payload"] = payload
    state["pending"] = updated


def _reconcile_fix_queue_after_rulings(state, config, extra_rows=None, session_dir=None):
    """Re-slice `_fixBatch`/`_fixQueue` through the ruling filter after a committed ruling."""
    if state.get("step") != P_APPLY_FIXES:
        return None
    offered = _offered_fix_rows(state, extra_rows)
    if not offered:
        return None
    batch_index = state.get("_fixBatchIndex") or 0
    status = _queue_fix_batch(
        state, config, offered, reset_accumulator=False, batch_index=batch_index,
        keep_step_start=True)
    if status == "excluded" and batch_index >= 1 and not state.get("terminal"):
        state.pop("_fixQueue", None)
        state.pop("_fixBatchIndex", None)
        _enter_post_fix(state, config, session_dir=session_dir)
    _sync_pending_after_ruling_reconcile(state)
    return status


def _subjects_for_dimension(dimension):
    """Policy subjects mentioned by a compiled finding's dimension label — a single label
    ('Security') or a merged one ('Security + Code'). Reuses review_round_policy's mapping so the
    driver derives subjects the one way the review record reads them (never a second mapping)."""
    out = set()
    if not isinstance(dimension, str):
        return out
    for token in re.split(r"[^A-Za-z-]+", dimension):
        subject = review_round_policy._policy_subject(token)
        if subject:
            out.add(subject)
    return out


def derive_changed_subjects(reviewed_diff_text, head_diff_text, accumulated_findings):
    """The REAL #157/#158 derivation: the policy subjects the fix TOUCHED, script-computed from git
    and NEVER the fixer's self-report. The files whose unified-diff sections differ between the
    reviewed diff and the post-fix head diff (`delta_surface.changed_files`), mapped to policy
    subjects through the accumulated compiled findings — a changed file is attributed to a subject
    when ANY reviewer cited it. Returns a KNOWN list (possibly empty) or None (unknown surface →
    the caller's existing run-everything rule). Any unreadable / unparseable diff → None."""
    changed = delta_surface.changed_files(reviewed_diff_text, head_diff_text)
    if changed is None:
        return None
    subjects = set()
    for f in accumulated_findings or []:
        if isinstance(f, dict) and f.get("file") in changed:
            subjects |= _subjects_for_dimension(f.get("dimension"))
    return sorted(subjects)


def _accumulated_findings(state):
    """The attribution surface the git-derived changed-subjects mapping reads: the UNION of every
    round's compiled findings (the in-memory record ledger) plus this round's settled findings.
    Attributing rework through the accumulated history — not only the deciding round — lets a
    later round's fix files be attributed to a subject an earlier round's reviewer cited."""
    out = []
    for rec in state.get("_records") or []:
        for f in rec.get("findings") or []:
            if isinstance(f, dict):
                out.append(f)
    for f in state.get("findings") or []:
        if isinstance(f, dict):
            out.append(f)
    return out


def _read_supplied_head_diff(artifact):
    """Read the post-fix diff an `apply-fixes` artifact supplies, keeping presence apart from
    content. Returns (present, text, source, readable). A key holding None is absent. Inline
    `headDiff` (the empty string included) wins over `headDiffPath`; the path must be absolute and
    readable text, and an empty file is present with text "". A present value the driver cannot read
    (a non-absolute or unreadable path, a non-text inline value) is present but not readable."""
    inline = artifact.get("headDiff")
    if inline is not None:
        return True, inline, "inline", isinstance(inline, str)
    path = artifact.get("headDiffPath")
    if path is None:
        return False, None, None, True
    if isinstance(path, str) and path and os.path.isabs(path):
        try:
            with open(path, encoding="utf-8") as fh:
                return True, fh.read(), "path", True
        except (OSError, UnicodeDecodeError):
            pass
    return True, None, "path", False


def _resolve_head_diff(artifact):
    """The supplied post-fix head diff as a run with no repository takes it: inline `headDiff` wins;
    else an absolute readable non-empty `headDiffPath`; anything else is an UNKNOWN surface, never an
    empty diff, so the next round hands the PR back (`fix-surface-unknown`). Returns (head_or_None, source) where source is 'inline'|'path'|'unknown'."""
    present, text, source, readable = _read_supplied_head_diff(artifact)
    if present and source == "inline":
        return text, "inline"
    if present and readable and text:
        return text, "path"
    return None, "unknown"


def _diff_header_paths(diff_text):
    """The file paths named by the `diff --git a/X b/Y` headers of a diff (the b side)."""
    return {m.group(1) for m in re.finditer(r"^diff --git a/.+? b/(.+)$", diff_text or "", re.M)}


def _head_diff_mismatch_detail(supplied_source, supplied, git_text):
    """The `head-diff-mismatch` park detail: the supplied source, sha256 and byte length of each
    side, and up to ten files whose `diff --git` header appears on one side only."""
    in_git = _diff_header_paths(git_text)
    in_supplied = _diff_header_paths(supplied)
    return (
        "%s: the supplied %s head diff differs from git diff of the fix-fold head "
        "(supplied sha256 %s, %d bytes; git sha256 %s, %d bytes); only-in-git=%s only-in-supplied=%s"
        % (HEAD_DIFF_MISMATCH_CAUSE, supplied_source,
           _sha256(supplied), len(supplied.encode("utf-8")),
           _sha256(git_text), len(git_text.encode("utf-8")),
           sorted(in_git - in_supplied)[:10], sorted(in_supplied - in_git)[:10]))


def _norm_newlines(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _nonempty_str(value):
    return isinstance(value, str) and bool(value)


FIX_REFUSED_REASON = "fold-refused"
FIX_WITHOUT_TEST = "fix-without-break-it-test"
FIX_FINDING_UNKNOWN = "fix-finding-unknown"
FIX_BINDING_MALFORMED = "fix-binding-malformed"
UNFIXED_FINDING_UNKNOWN = "unfixed-finding-unknown"
FIX_NO_BINDING = "no-binding"
FIX_COMMIT_UNKNOWN = "commit-unknown"
FIX_COMMIT_NOT_IN_STEP = "commit-not-in-step"
FIX_TEST_MISSING = "test-missing"
FIX_TEST_BYTES_DIFFER = "test-bytes-differ"
FIX_NO_FIX_CHANGE = "no-fix-change"
FIX_UNVERIFIABLE = "unverifiable"


def _slice_finding_resolver(slice_):
    """``{value: finding key}`` for the slice: each row's identity key and its staged id name it."""
    names = {}
    for row in slice_ if isinstance(slice_, list) else []:
        key = _finding_identity_key(row) if isinstance(row, dict) else None
        if not key:
            continue
        names[key] = key
    for row in slice_ if isinstance(slice_, list) else []:
        key = _finding_identity_key(row) if isinstance(row, dict) else None
        rid = row.get("id") if key else None
        if isinstance(rid, str) and rid:
            names.setdefault(rid, key)
    return names


def _report_bindings(artifact):
    """The ``{"finding", "commit"}`` entries of the report's ``fixes`` — the session's own binding of
    a fixed finding to the commit that holds its fix."""
    fixes = artifact.get("fixes") if isinstance(artifact, dict) else None
    return [entry for entry in fixes if isinstance(entry, dict) and "finding" in entry
            and "commit" in entry] if isinstance(fixes, list) else []


def _malformed_binding_index(artifact):
    """The position in ``fixes`` of the first object that names a ``finding`` or a ``commit`` without
    both being non-empty strings (None when there is none). Plain notes and objects with neither key
    are not bindings."""
    fixes = artifact.get("fixes") if isinstance(artifact, dict) else None
    for index, entry in enumerate(fixes if isinstance(fixes, list) else []):
        if isinstance(entry, dict) and ("finding" in entry or "commit" in entry) and not (
                _nonempty_str(entry.get("finding")) and _nonempty_str(entry.get("commit"))):
            return index
    return None


def _git_bytes(repo_root, *args):
    """The stdout bytes of ``git -C repo_root args``, or None when git fails or cannot run."""
    try:
        proc = subprocess.run(["git", "-C", repo_root, *args], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def _git_fix_commit_facts(config, step_head, commits, test_paths):
    """``{commit: {"sha", "reachable", "inStep", "paths", "files", "startFiles"}}`` read from git at
    the session's repository for each commit it names. A commit git does not know has no entry."""
    repo_root = config.get("repoRoot")
    facts = {}
    for commit in commits:
        resolved = _git_bytes(repo_root, "rev-parse", "--verify", "--quiet", "%s^{commit}" % commit)
        if resolved is None:
            continue
        sha = resolved.decode("utf-8", errors="replace").strip()
        names = _git_bytes(repo_root, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r",
                           "-z", sha)
        facts[commit] = {
            "sha": sha,
            "reachable": _git_bytes(repo_root, "merge-base", "--is-ancestor", sha, "HEAD") is not None,
            "inStep": _git_bytes(repo_root, "merge-base", "--is-ancestor", sha, step_head) is not None,
            "paths": ([p for p in names.decode("utf-8", errors="replace").split("\0") if p]
                      if names is not None else []),
            "files": {p: _git_bytes(repo_root, "cat-file", "blob", "%s:%s" % (sha, p))
                      for p in test_paths},
            "startFiles": {p: _git_bytes(repo_root, "cat-file", "blob", "%s:%s" % (step_head, p))
                           for p in test_paths},
        }
    return facts


def _fix_commit_test_fault(facts, block):
    """The reason a commit does not carry the fix with its test (None when it does). The commit must
    be reachable from HEAD and not from the step's start head, hold the block's bytes at the block's
    path (the bytes are read from the commit itself; a commit that leaves the test path unchanged is
    a repair of a test already there at the start head), and change at least one path besides the
    test."""
    if not isinstance(facts, dict) or facts.get("reachable") is not True:
        return FIX_COMMIT_UNKNOWN
    if facts.get("inStep") is not False:
        return FIX_COMMIT_NOT_IN_STEP
    path = block["path"]
    wanted = block["content"].encode("utf-8")
    changed = [p for p in facts.get("paths") or [] if isinstance(p, str)]
    have = (facts.get("files") or {}).get(path)
    if have is not None and path not in changed:
        # the repair exception: a source-only commit must follow a test that already stood at the start head
        start = facts.get("startFiles")
        if isinstance(start, dict) and start.get(path) is None:
            return FIX_TEST_MISSING
    if have is None:
        return FIX_TEST_MISSING
    # axis: the test is at the block's path with the block's bytes exactly — see bite-proof record c1l9a_wo3_apply_fixes
    if have != wanted:
        return FIX_TEST_BYTES_DIFFER
    # axis: the commit changes something besides the test, so a test committed alone is no fix — see bite-proof record c1l9a_wo3_apply_fixes
    if not any(p != path for p in changed):
        return FIX_NO_FIX_CHANGE
    return None


def _apply_fixes_commit_fault(state, config, artifact, commit_seam=None):
    """``(detail, commits)`` for an apply-fixes report: ``detail`` names why the report cannot fold
    (None when it can) and ``commits`` are the verified ``{"finding", "commit"}`` bindings.

    Each finding of the slice that carries a break-it test and is not listed in ``unfixed`` needs a
    binding to a commit that carries its fix together with the test, checked against git (or the
    ``commit_seam`` a run without a repository supplies). A report with no commit and no such
    finding passes: a PR-body-only slice commits nothing. A ``fixes`` object that names a
    ``finding`` or a ``commit`` must give both as non-empty strings, else it is refused before any
    lookup. Each verified binding records the resolved full sha: git's own, or the seam entry's
    ``sha`` (the supplied value when the entry has none)."""
    malformed = _malformed_binding_index(artifact)
    # axis: a binding with a non-string or empty finding or commit is refused before any lookup — see bite-proof record c1l9a_wo8_review1
    if malformed is not None:
        return "%s:%d" % (FIX_BINDING_MALFORMED, malformed), []
    slice_ = state.get("_fixBatch") or []
    names = _slice_finding_resolver(slice_)
    bindings = _report_bindings(artifact)
    unfixed = [e for e in (artifact.get("unfixed") or []) if isinstance(e, dict)]
    for entry in unfixed:
        if entry.get("finding") not in names:
            return "%s:%s" % (UNFIXED_FINDING_UNKNOWN, entry.get("finding")), []
    for entry in bindings:
        if entry.get("finding") not in names:
            return "%s:%s" % (FIX_FINDING_UNKNOWN, entry.get("finding")), []
    left = {names[entry["finding"]] for entry in unfixed}
    bound = {}
    for entry in bindings:
        bound.setdefault(names[entry["finding"]], []).append(entry.get("commit"))
    owed = []
    for row in slice_:
        block, _kind = break_it.carried_block(row)
        key = _finding_identity_key(row) if isinstance(row, dict) else None
        if block is not None and key and key not in left:
            owed.append((key, block))
    named = [c for key, _block in owed for c in bound.get(key, []) if isinstance(c, str) and c]
    facts = None
    if named:
        test_paths = sorted({block["path"] for _key, block in owed})
        if commit_seam is not None:
            facts = commit_seam(sorted(set(named)), test_paths)
        elif _nonempty_str(config.get("repoRoot")) and _nonempty_str(config.get("baseRef")) \
                and _nonempty_str(state.get("_fixStepHead")):
            facts = _git_fix_commit_facts(config, state["_fixStepHead"], sorted(set(named)),
                                          test_paths)
    commits = []
    for key, block in owed:
        candidates = [c for c in bound.get(key, []) if isinstance(c, str) and c]
        # axis: a finding that carries a break-it test and is not left unfixed owes a binding — see bite-proof record c1l9a_wo3_apply_fixes
        if not candidates:
            return "%s:%s:%s" % (FIX_WITHOUT_TEST, key, FIX_NO_BINDING), []
        if not isinstance(facts, dict):
            return "%s:%s:%s" % (FIX_WITHOUT_TEST, key, FIX_UNVERIFIABLE), []
        faults = [_fix_commit_test_fault(facts.get(c), block) for c in candidates]
        if all(fault is not None for fault in faults):
            return "%s:%s:%s" % (FIX_WITHOUT_TEST, key, faults[0]), []
        chosen = candidates[faults.index(None)]
        # axis: the stored binding names the resolved sha, never the expression as given — see bite-proof record c1l9a_wo8_review1
        resolved = (facts.get(chosen) or {}).get("sha")
        commits.append({"finding": key, "commit": resolved if _nonempty_str(resolved) else chosen})
    return None, commits


def _staged_pr_body_sha256(session_dir):
    """The sha256 of the staged PR body, or None when there is no staged file."""
    try:
        with open(pr_body_stage.paths(session_dir)["staged"], "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None


def _fold_apply_fixes(state, config, artifact, changed_subjects_seam=None, session_dir=None,
                      panel_diff_seam=None, fix_commits=None):
    """Record the build session's own fix report; the fix-batch COMPOSITION stays orchestrator-side
    (the artifact), the driver sequences + records. What was committed is read from git by the
    submit chokepoint (`fix_commits` are the bindings it verified), never from the report's own
    word. In a run with a repository the post-fix head diff is DERIVED
    from git (`git diff <baseRef>...<fix-fold head>`) and is never text the artifact supplied: a
    supplied `headDiff` / absolute `headDiffPath` is a cross-check only, so a difference parks
    `head-diff-mismatch` and a derivation git cannot make beside a supplied diff parks
    `head-diff-unverifiable`. A derivation that fails with nothing supplied is an unknown surface
    (the next round hands the PR back as `fix-surface-unknown`). A run with no repository takes the
    supplied diff as `_resolve_head_diff` reads it.
    The changed policy subjects the review record carries are SCRIPT-DERIVED here — from
    the reviewed-vs-head diff through the accumulated findings (#157/#158), NEVER the session's
    self-report. The derivation is an injectable seam symmetrical with reviewer/fix step/verify:
    run_loop may inject a scripted replay (the eval harness); the library default + the CLI path
    wire the real git derivation. An unknown/unparseable surface derives None."""
    index = state.get("_fixBatchIndex") or 0
    slice_ = state.get("_fixBatch") or []
    if index == 0:
        state["fixBatch"] = list(slice_)
    else:
        state["fixBatch"] = (state.get("fixBatch") or []) + list(slice_)
    fold_head, fold_head_err = None, None
    if session_dir:
        fold_head, fold_head_err = _resolve_fix_fold_head_sha(session_dir, state)
    else:
        cfg_head = config.get(FIX_FOLD_HEAD_KEY)
        fold_head = cfg_head if _nonempty_str(cfg_head) else None
    present, supplied, supplied_source, readable = _read_supplied_head_diff(artifact)
    has_repo = panel_diff_seam is not None or (
        _nonempty_str(config.get("repoRoot")) and _nonempty_str(config.get("baseRef")))
    park_detail = None
    if not has_repo:
        head, head_source = _resolve_head_diff(artifact)
        head_check = "no-repository"
    else:
        if fold_head or panel_diff_seam is not None:
            derive_head = panel_diff_seam or _derive_panel_diff_at_head
            git_text, refuse = derive_head(config, fold_head)
            if refuse is None and not isinstance(git_text, str):
                git_text, refuse = None, "derived diff is not text"
        else:
            git_text, refuse = None, fold_head_err or "head unresolved"
        if refuse is None:
            head, head_source = git_text, "git"
            if not present:
                head_check = "none-supplied"
            elif not readable:
                head_check = "supplied-unreadable"
            elif _norm_newlines(supplied) == _norm_newlines(git_text):
                head_check = "match"
            else:
                head, head_check = None, "mismatch"
                park_detail = _head_diff_mismatch_detail(supplied_source, supplied, git_text)
        else:
            head, head_source, head_check = None, "unknown", "unverifiable"
            if present:
                park_detail = "%s: git cannot verify the supplied %s head diff: %s" % (
                    HEAD_DIFF_UNVERIFIABLE_CAUSE, supplied_source, refuse)
    state["headDiff"] = head
    state["_headDiffSource"] = head_source
    state["_headDiffUnknown"] = head_source == "unknown" and park_detail is None
    _record_round(state, "headDiffSource", head_source)
    _record_round(state, "headDiffCheck", head_check)
    derive = changed_subjects_seam or derive_changed_subjects
    state["_changedSubjects"] = derive(
        state.get("reviewedDiff"), state.get("headDiff"), _accumulated_findings(state))
    # Accumulate the fix's coverage decisions so the challenged-coverage breaker can see a decision
    # recorded on a principle a later round re-raises (annotateChallengedCoverage input).
    cds = artifact.get("coverageDecisions")
    if isinstance(cds, list):
        state.setdefault("_coverage", []).extend(d for d in cds if isinstance(d, dict))
    rec = state.get("rounds", {}).get(str(state["round"]), {})
    prior_fix = rec.get("fix") if isinstance(rec, dict) else None
    fixes = list(artifact.get("fixes") or [])
    unfixed = [e for e in (artifact.get("unfixed") or []) if isinstance(e, dict)]
    commits = list(fix_commits or [])
    if index >= 1 and isinstance(prior_fix, dict):
        fixes = list(prior_fix.get("fixes") or []) + fixes
        unfixed = list(prior_fix.get("unfixed") or []) + unfixed
        commits = list(prior_fix.get("commits") or []) + commits
    fix_rec = {"fixes": fixes, "commits": commits}
    if unfixed:
        fix_rec["unfixed"] = unfixed
    _record_round(state, "fix", fix_rec)
    _record_round_append(state, "fixBatches",
                         {"index": index, "size": len(slice_),
                          "fixes": len(artifact.get("fixes") or [])})
    # A `fixes` entry is the session's own note and may name no finding, so the keys of the findings
    # this slice handed it, less those it reports unfixed, ride beside it: the later-panel credit
    # reads them.
    reported_keys = list(rec.get("fixReportedKeys") or []) if index >= 1 and isinstance(rec, dict) else []
    if artifact.get("fixes"):
        names = _slice_finding_resolver(slice_)
        left = {names[e.get("finding")] for e in (artifact.get("unfixed") or [])
                if isinstance(e, dict) and e.get("finding") in names}
        reported_keys += [k for k in (_finding_identity_key(f) for f in slice_ if isinstance(f, dict))
                          if k and k not in left]
    _record_round(state, "fixReportedKeys", reported_keys)
    _record_round(state, "fixerVendor", config.get("fixerVendor"))
    if session_dir:
        pr_body_after = _staged_pr_body_sha256(session_dir)
        pr_body_before = state.get("_prBodyAtStep")
        if pr_body_after is not None and pr_body_after != pr_body_before:
            prior_pr_body = (state["rounds"].get(str(state["round"])) or {}).get("prBodyFix")
            earlier = prior_pr_body.get("before") if isinstance(prior_pr_body, dict) else None
            _record_round(state, "prBodyFix",
                          {"before": earlier if earlier else pr_body_before,
                           "after": pr_body_after})
        if fold_head_err:
            _record_round(state, "fixFoldHeadRefused", fold_head_err)
        else:
            _record_round(state, "fixFoldHead", fold_head)
    if park_detail is not None:
        state.pop("_fixQueue", None)
        state.pop("_fixBatchIndex", None)
        _park_cannot_certify(state, park_detail)
        return
    state.pop("_prBodyAtStep", None)
    queue = state.get("_fixQueue") or []
    if queue:
        cap = _fix_batch_cap(config)
        done = len(slice_)
        queued = len(queue) - min(cap, len(queue))
        status = _queue_fix_batch(
            state, config, queue, reset_accumulator=False, batch_index=index + 1)
        if status == "queued":
            _decision(state, "fix-batch-split",
                      "fix batch slice %d of this round dispatched (%d findings; %d queued)"
                      % (index + 1, done, queued))
            return
        if status == "faulted":
            return
    state.pop("_fixStepHead", None)
    state.pop("_fixQueue", None)
    state.pop("_fixBatchIndex", None)
    _enter_post_fix(state, config, session_dir=session_dir, panel_diff_seam=panel_diff_seam)


_VERIFY_SKIP = ("skipped", "none", "unverified")

# ---- #885: submit-shape guards (verify + audits) --------------------------------------------
#
# A wrong-SHAPE artifact at these two submits used to cost the build its certification receipt
# silently: the fold recorded the malformed value (`result: None`; a `discharged-but-new-issue`
# ruling with no usable `newIssues`), failed closed into `halted`/`not-discharged`, and the terminal
# state was journalled and IMMUTABLE — a corrected resubmit refused. Three recorded losses in one
# week (#878 submitted `{exitCode, passed, output}`; #880 submitted `newIssue` as a bare string;
# #883/#892 re-ran an entire panel round rather than hand back uncertified).
#
# So these refuse at the chokepoint — BEFORE the fold, exactly as the #845 panel seat-key guard
# does — leaving the pending step intact so recovery is a corrected resubmit on the same
# phase/attempt/state-hash. They are SHAPE guards only: an artifact that faithfully expresses what
# the auditor or the verify runner actually said still folds exactly as it does today, including
# every deliberate fail-closed path (a real `fail`, a real `timeout`, silence, unauthenticated
# provenance). The line is "the artifact cannot express a usable answer", never "the answer is bad".

# The verify vocabulary the fold RECOGNIZES. `pass` advances; the skip tokens take the skip arm;
# `fail` and `timeout` are real reported outcomes the fold halts on deliberately. A value OUTSIDE
# this set is not an outcome anyone reported — it is a mis-shaped artifact.
# `test_verify_vocabulary_census` holds this tuple equal to the token/fold-arm table, and
# `test_submit_verify_recognized_token_accepted` drives each token through the guard to the arm it
# lands in — together they keep this tuple from drifting away from `_fold_verify`.
_VERIFY_RESULTS = ("pass", "fail", "timeout") + _VERIFY_SKIP

# Keys of the shapes real orchestrators submitted instead of `{"result": ...}` — the raw runner
# envelope (#878, #883/#892). Hinting them by name turns a generic shape refusal into the one-line
# correction the builder needs, the same way the seat-key guard names the findings-file stem.
_VERIFY_RUNNER_ENVELOPE_HINTS = {
    "passed": "`passed` is the raw runner envelope's key — the driver consumes {\"result\": "
              "\"pass\"} (or \"fail\"), never a boolean",
    "exitCode": "`exitCode` is the raw runner envelope's key — translate it to a `result` token",
    "status": "`status` is not the driver's key — the driver consumes `result`",
}


def verify_result_fault(artifact):
    """None when a verify artifact carries a RECOGNIZED `result` token; otherwise a reason string."""
    return round_phases.verify_result_fault(artifact)


def _audit_result_entry_fault(entry, index, target_ids, targets_by_id=None):
    """The shape fault (a reason string) in ONE audit-result entry, or None.

    `target_ids` is the driver's own set of audit-target ids — a result keyed to an id outside it
    can never match a target, so it is the audit-side twin of the #845 seat mis-key. An EMPTY set
    means the driver has no targets to key against, so no id is judged (mirroring the seat-key
    guard's empty-key rule) — never a false refusal. `targets_by_id` maps each id to its target, so
    the three checks (and the test comparison) are judged against the target the result answers.

    axis: REFUSAL of a ruling the fold cannot honor as written — not whether the ruling is correct.
    Each branch below bites on one distinct way an entry fails to express a usable answer.
    """
    where = "results[%d]" % index
    # axis: shape of the entry itself — a non-object can carry no ruling at all.
    if not isinstance(entry, dict):
        return "%s is %s, not a ruling object; expected {\"id\", \"ruling\", \"reason\", ...}" % (
            where, type(entry).__name__)
    rid = entry.get("id")
    # axis: presence of a binding id — without one the ruling can never reach any finding.
    if not isinstance(rid, str) or not rid:
        return ("%s has no usable `id` (got %r) — a ruling with no finding id can never reach its "
                "target; expected the target's staged id" % (where, rid))
    # axis: that the id BINDS to a real target of this round — the audit-side twin of the #845 mis-key.
    if target_ids and rid not in target_ids:
        return ("%s is keyed to %r, which is not an audit target of this round; targets: %s; "
                "re-key the ruling to its target's staged id" % (where, rid,
                                                                ", ".join(sorted(target_ids))))
    ruling = entry.get("ruling")
    # axis: that the verdict token is one the fold has an arm for — never a near-miss word.
    if not isinstance(ruling, str) or ruling not in audits.AUDIT_RULINGS:
        return ("%s has an unrecognized `ruling` (got %r); expected one of: %s" % (
            where, ruling, ", ".join(audits.AUDIT_RULINGS)))
    # axis: that a CLEARING ruling carries its grounds — a bare discharge is the unproven claim.
    # The grounds test is `audits.has_usable_reason`, the fold's OWN predicate — one function, not a
    # second copy of the rule, so the guard can never accept a reason the fold rejects (or refuse one
    # it would honor). Same shared-home discipline as `has_usable_new_issues` below.
    named_seq = entry.get("unnamedChangeAllowedBySeq")
    if named_seq is not None and not audits.is_decision_seq(named_seq):
        return ("%s `unnamedChangeAllowedBySeq` is %r, not an integer; expected the sequence number "
                "of the one carried owner decision that permits the change, or leave the field out"
                % (where, named_seq))
    unnamed = entry.get("unnamedChange")
    if unnamed is not None and not isinstance(unnamed, str):
        return ("%s `unnamedChange` is %s, not a string; expected a plain-words string, or leave the "
                "field out when the fix changes nothing beyond what the finding names"
                % (where, type(unnamed).__name__))
    claim_field = audits.unnamed_change_claims_fault(entry.get("unnamedChangeFixes"),
                                                     entry.get("unnamedChangeReverts"))
    if claim_field is not None:
        return ("%s `%s` is %r, not a list of non-blank strings; expected the ids of the target's "
                "`roundFindings` (fixes) or the refs of its `reportedUnnamedChanges` (reverts), or "
                "leave the field out" % (where, claim_field, entry.get(claim_field)))
    if ruling == "discharged" and not audits.has_usable_reason(entry.get("reason")):
        return ("%s rules `discharged` with no `reason` — a bare discharge is the unproven claim "
                "the audit fold exists to reject; expected a non-empty `reason` string" % where)
    # axis: that the NEW-ISSUE payload is usable — the #880 loss, where the receipt understated the
    # auditor's ruling because `newIssues` carried nothing the fold could emit.
    if ruling == "discharged-but-new-issue" and not audits.has_usable_new_issues(
            entry.get("newIssues")):
        detail = ("%s rules `discharged-but-new-issue` with no usable `newIssues` (got %r); "
                  "expected a non-empty list of issue objects" % (where, entry.get("newIssues")))
        if "newIssue" in entry:
            detail += ("; the artifact carries `newIssue` (singular) — the driver consumes "
                       "`newIssues`, a LIST")
        return detail
    # axis: that EVERY result, whatever its ruling, answers the three checks (and the test comparison
    # where the committed break-it test was changed) — `audits.audit_checks_fault`, the fold's own judge
    checks_fault = audits.audit_checks_fault(entry, (targets_by_id or {}).get(rid))
    if checks_fault is not None:
        return ("%s is refused: %s; expected `checks` with `right`, `brokeNothing` and `testWouldFail`, "
                "each {\"answer\": \"yes\" or \"no\", \"why\": <reason>}" % (where, checks_fault))
    return None


def synthesis_results_fault(artifact):
    """None when a synthesis artifact satisfies the declared payload contract; otherwise a reason
    string naming the offending field.

    `grouping: null` (no merging proposed) is a real answer and is not a fault — only a missing,
    mis-keyed, or mis-shaped `grouping` is refused at the submit chokepoint."""
    if not isinstance(artifact, dict):
        return ("synthesis artifact is %s, not a grouping object; expected {\"grouping\": ...}; "
                "resubmit the same phase/attempt/state-hash with a corrected artifact"
                % type(artifact).__name__)
    if "grouping" not in artifact:
        return ("synthesis artifact carries no `grouping` key; expected {\"grouping\": ...}; "
                "resubmit the same phase/attempt/state-hash with a corrected artifact")
    fault = payload_contracts.payload_fault(payload_contracts.P_SYNTHESIS, artifact, "hand-submit")
    if fault is not None:
        return fault
    return None


def verifier_results_fault(artifact):
    """None when a verifiers artifact carries a RECOGNIZED `verdicts` list; otherwise a reason string.

    An EMPTY `verdicts` list is a real outcome (zero clusters verified) and is not a fault — only a
    missing or mis-keyed `verdicts` is refused at the submit chokepoint."""
    if not isinstance(artifact, dict):
        return ("verifiers artifact is %s, not a verdict object; expected {\"verdicts\": [...]}; "
                "resubmit the same phase/attempt/state-hash with a corrected artifact"
                % type(artifact).__name__)
    if "verdicts" not in artifact:
        parts = [
            "verifiers artifact carries no `verdicts` key",
            "expected {\"verdicts\": [...]}",
            "resubmit the same phase/attempt/state-hash with a corrected artifact",
        ]
        if "findings" in artifact:
            parts.append(
                "the artifact carries `findings` — the driver consumes `verdicts`, a LIST; "
                "apply_verdicts keys on `id`, and a verdict it cannot key reaches no finding at all"
            )
        return "; ".join(parts)
    verdicts = artifact.get("verdicts")
    if not isinstance(verdicts, list):
        return ("verifiers artifact `verdicts` is %s, not a list; expected {\"verdicts\": [...]}; "
                "resubmit the same phase/attempt/state-hash with a corrected artifact"
                % type(verdicts).__name__)
    fault = payload_contracts.payload_fault(payload_contracts.P_VERIFIERS, artifact, "hand-submit")
    if fault is not None:
        return fault
    return None


def audit_results_fault(artifact, targets):
    """None when every entry of an audits artifact's `results` expresses a usable ruling; otherwise
    a reason string naming the expected shape.

    Scope is deliberately SHAPE only. An ABSENT or empty `results` is not a fault — genuine auditor
    silence is a real answer the fold discloses as `unaudited` and fails closed on. Provenance
    (the collection-manifest authentication) is a trust boundary, not a shape, and stays entirely in
    the fold: a correctly-shaped ruling the manifest cannot authenticate must still fold to
    not-discharged, never be handed back for a "corrected" resubmit.

    DUPLICATE ids are likewise NOT a shape fault. A repeated RESULT id is ambiguous — honor none —
    and `audits.apply_audit_results` already fails closed on that case. Duplicate TARGET ids in a
    persisted session (minted before per-location ids) are likewise fail-closed in the fold, not
    refused here. Refusing a repeated result id would be an unresolvable loop when two distinct
    targets once shared one line-less id and the orchestrator submitted one ruling per target.

    axis: REFUSAL of an audits artifact that cannot express its rulings — not the rulings' merit.
    """
    # axis: the ENVELOPE's own shape — the submit CLI loads the artifact with `json.load`, which
    # accepts ANY root, so a `null` or bare-list artifact reaches the fold, normalizes to `{}`, and
    # folds EVERY target `unaudited` → not-discharged with the pending step gone: the #885 loss class
    # arriving through a root the `results` checks below never inspect.
    if not isinstance(artifact, dict):
        return ("audits artifact is %s, not a results object; expected {\"results\": [{\"id\", "
                "\"ruling\", \"reason\", ...}]}; resubmit the same phase/attempt/state-hash with a "
                "corrected artifact" % type(artifact).__name__)
    # The original absent-`results` test keeps its own non-dict guard rather than leaning on the
    # branch above: that branch must be independently neutralizable, so a bite-proof mutation of it
    # lands on the REFUSAL axis (a non-dict artifact walks through) instead of crashing here.
    if not isinstance(artifact, dict) or "results" not in artifact:
        return None
    results = artifact["results"]
    # axis: the container's shape — a non-list `results` silently folds to zero rulings today.
    if not isinstance(results, list):
        return ("audits artifact `results` is %s, not a list of ruling objects; expected "
                "{\"results\": [{\"id\", \"ruling\", \"reason\", ...}]}; resubmit the same "
                "phase/attempt/state-hash with a corrected artifact" % type(results).__name__)
    target_ids = {t.get("id") for t in targets if isinstance(t, dict)
                  and isinstance(t.get("id"), str)} if isinstance(targets, list) else set()
    targets_by_id = {t.get("id"): t for t in targets if isinstance(t, dict)
                     and isinstance(t.get("id"), str)} if isinstance(targets, list) else {}
    for index, entry in enumerate(results):
        fault = _audit_result_entry_fault(entry, index, target_ids, targets_by_id)
        if fault:
            return "%s; resubmit the same phase/attempt/state-hash with a corrected artifact" % fault
    return None


def collection_manifest_fault(artifact, targets):
    """None when an audits artifact's `collectionManifest` keys are acceptable; otherwise
    a reason string naming the mistake.

    Scope is deliberately KEYS only. An ABSENT or partial manifest is not a fault — missing
    provenance is a trust boundary the fold discloses as `unauthenticated` and fails closed on.
    Refusing a subset manifest here would hand back a "correctable shape fault" for what is really
    a trust failure, inviting the orchestrator to resubmit a forged entry. Manifest VALUES are out
    of scope entirely — this guard judges keys, never vendors.

    axis: REFUSAL of a collection manifest that cannot express its provenance — not the merit of
    the rulings it accompanies.
    """
    # axis: artifact envelope — the sibling `audit_results_fault` already refuses non-dict roots.
    if not isinstance(artifact, dict):
        return None
    # axis: absent manifest — legitimate omission; the fold treats absence as no manifest.
    if "collectionManifest" not in artifact:
        return None
    manifest = artifact["collectionManifest"]
    # axis: manifest container shape — a non-dict cannot express provenance at all.
    if not isinstance(manifest, dict):
        return ("collectionManifest is %s, not a provenance map; expected "
                "{<target-id>: <vendor>, ...}; resubmit the same phase/attempt/state-hash with a "
                "corrected artifact" % type(manifest).__name__)
    # axis: unavailable target set — no keys can be judged; refusing would trap legacy sessions.
    if targets is None:
        return None
    # axis: known target set — every manifest key must bind to a real target id of this round.
    if isinstance(targets, list):
        target_ids = {t["id"] for t in targets if isinstance(t, dict)
                      and isinstance(t.get("id"), str)}
        identity_to_ids = {}
        for t in targets:
            if isinstance(t, dict) and isinstance(t.get("id"), str):
                ident = t.get("identity")
                if isinstance(ident, str) and ident:
                    identity_to_ids.setdefault(ident, set()).add(t["id"])
        # axis: non-string manifest key — name the key and its type; never let sorted() raise.
        non_string_keys = [k for k in manifest if not isinstance(k, str)]
        if non_string_keys:
            bad_key = min(non_string_keys, key=lambda k: (type(k).__name__, repr(k)))
            return ("collectionManifest key %r is %s, not a target id string; expected "
                    "{<target-id>: <vendor>, ...}; resubmit the same phase/attempt/state-hash with a "
                    "corrected artifact" % (bad_key, type(bad_key).__name__))
        bad_keys = sorted(k for k in manifest if k not in target_ids)
        if bad_keys:
            bad_key = bad_keys[0]
            # axis: identity-vs-id confusion — name the mistake so the orchestrator re-keys to id.
            if bad_key in identity_to_ids:
                ids_for_identity = sorted(identity_to_ids[bad_key])
                if len(ids_for_identity) == 1:
                    return ("collectionManifest key %r is targets[].identity (driver-internal; must not "
                            "be used as a transport key), not targets[].id — re-key to %r; valid target "
                            "ids: %s; resubmit the same phase/attempt/state-hash with a corrected artifact"
                            % (bad_key, ids_for_identity[0], ", ".join(sorted(target_ids))))
                id_list = ", ".join(repr(i) for i in ids_for_identity)
                return ("collectionManifest key %r is targets[].identity (driver-internal; must not "
                        "be used as a transport key), not targets[].id — re-key to a per-location "
                        "target id for each location: %s; valid target ids: %s; resubmit the same "
                        "phase/attempt/state-hash with a corrected artifact"
                        % (bad_key, id_list, ", ".join(sorted(target_ids))))
            # axis: unknown key — refuse with the valid target-id set for recovery.
            return ("collectionManifest key %r is not an audit target of this round; valid target "
                    "ids: %s; resubmit the same phase/attempt/state-hash with a corrected artifact"
                    % (bad_key, ", ".join(sorted(target_ids))))
    return None


def _verify_command_configured(config):
    """True when the profile configures a REAL verify command (not absent / `none`). A configured
    command must actually PASS — a skip result then means the run did not execute, so it fails closed
    rather than advancing unverified (#507 R2 residual-2)."""
    return core_md.verify_command_configured(config.get("verifyCommand"))


def _verify_via_row(config, artifact):
    """Which verify a pass rests on: the local command, or a CI run on the exact head."""
    if artifact.get("via") == "ci-exact-head":
        ci = artifact["ci"]
        return {"via": "ci-exact-head", "workflow": ci["workflow"], "runId": str(ci["runId"]),
                "headSha": ci["headSha"], "conclusion": ci["conclusion"], "reason": artifact["reason"]}
    command = artifact.get("command")
    return {"via": "local", "command": command if isinstance(command, str) and command
            else config.get("verifyCommand")}


_VERIFY_RUN_OUTPUT_CHARS = 4000
_VERIFY_HEX = frozenset("0123456789abcdefABCDEF")


def _usable_verify_head(value):
    """True for a full commit id: 40 or 64 hex digits."""
    return isinstance(value, str) and len(value) in (40, 64) and all(c in _VERIFY_HEX for c in value)


def _verify_execution_head(artifact, fold_head):
    """(head, source, moved) for one verify run. The head is the one the run recorded when it holds
    still across the run (`run`), else the head resolved at the fold (`fold`), else none
    (`unknown`). `moved` is True when the run's own two reads disagree: a run that straddled a
    head change ran at no single head."""
    ran = artifact.get("headSha")
    after = artifact.get("headShaAfter")
    ran = ran if _usable_verify_head(ran) else None
    after = after if _usable_verify_head(after) else None
    if ran is not None and after is not None and after != ran:
        return ran, "run", True
    if ran is not None:
        return ran, "run", False
    if _usable_verify_head(fold_head):
        return fold_head, "fold", False
    return None, "unknown", False


def _verify_run_output(artifact):
    """The last characters of the output file a run left, or "" when none can be read."""
    path = artifact.get("outputPath")
    if not isinstance(path, str) or not path:
        return ""
    try:
        with open(path, "rb") as fh:
            size = fh.seek(0, os.SEEK_END)
            fh.seek(max(0, size - 4 * _VERIFY_RUN_OUTPUT_CHARS))
            data = fh.read()
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")[-_VERIFY_RUN_OUTPUT_CHARS:]


def _verify_run_row(artifact):
    """One verify run as the review record's run shape: ran with its exit code, timed out, or not
    started (the reason names the result token)."""
    result = artifact.get("result")
    exit_code = artifact.get("exitCode")
    if result == "timeout":
        return {"status": "timed-out", "exitCode": None, "output": _verify_run_output(artifact),
                "reason": "timeout"}
    if isinstance(exit_code, int) and not isinstance(exit_code, bool):
        return {"status": "ran", "exitCode": exit_code, "output": _verify_run_output(artifact),
                "reason": None}
    return {"status": "not-started", "exitCode": None, "output": "",
            "reason": result if isinstance(result, str) else None}


def _verify_rerun_heads_moved(first_head, artifact, head, moved):
    """(earlier, later) when the re-run did not run at the first run's head, else None. A re-run
    that straddled a head change names the two heads it read; a head that is unknown on either side
    is not a difference."""
    if moved:
        return artifact.get("headSha"), artifact.get("headShaAfter")
    if first_head is not None and head is not None and first_head != head:
        return first_head, head
    return None


def _verify_artifact_trees(artifact):
    """The working-tree digests a verify run read (before and, when it moved, after); unknown
    sides are left out."""
    return [t for t in (artifact.get("treeSha"), artifact.get("treeShaAfter"))
            if isinstance(t, str) and t]


def _fold_verify(state, config, artifact, *, resolution, panel_diff_seam=None):
    """Fold the verify result. FAIL-CLOSED (#507 v10): advance ONLY on an explicit `pass` or — WHEN NO
    verify command is configured — an explicit unverified skip (`skipped`/`none`/`unverified`). A
    `fail`, a `timeout`, a missing/None result, any unrecognized value, OR a skip result while a real
    verify command IS configured (the command did not actually run) HALTS with an honest reason that
    names the class — never advances into a delta round that could later certify.

    The head the next panel's diff is derived from is resolved at the submit chokepoint (or passed
    explicitly by the in-process leg) and forwarded as ``(head, error)``; a missing resolution
    raises before anything is recorded. An error resolution passes no head on."""
    if not (isinstance(resolution, tuple) and len(resolution) == 2):
        raise ValueError("verify fold: no verified-head resolution was forwarded")
    verified_head, verified_head_err = resolution
    if verified_head_err:
        verified_head = None
    result = artifact.get("result")
    _record_round(state, "verifyResult", result)
    head, head_source, moved = _verify_execution_head(artifact, verified_head)
    first = state.pop("_verifyRerun", None)
    # axis: a first fail does not halt — the gate is pending again once, and the second result decides — see bite-proof record c1l9a_wo1_verify_rerun
    if first is None:
        if result == "fail" and not moved and artifact.get("via") != "ci-exact-head":
            state["_verifyRerun"] = {"run": _verify_run_row(artifact), "head": head,
                                     "headSource": head_source,
                                     "trees": _verify_artifact_trees(artifact)}
            _decision(state, "verify-rerun",
                      "verify gate failed once at head %s — re-running the same check once"
                      % (head or "unknown"))
            return
    else:
        second = _verify_run_row(artifact)
        first_run = dict(first.get("run") or {}, head=first.get("head"),
                         headSource=first.get("headSource"))
        second_run = dict(second, head=head, headSource=head_source)
        if moved:
            # axis: a re-run whose own head moved records where it ended, so the record never calls it unchanged code — see bite-proof record c1l9b_wod_head_after
            second_run["headAfter"] = artifact.get("headShaAfter")
        # axis: the record holds the first failure and the one re-run, both runs — see bite-proof record c1l9a_wo1_verify_rerun
        _record_round_append(state, "rerunChecks", {"check": "verify", "runs": [first_run, second_run]})
        # axis: a re-run that passed counts only at the head the first run ran at — see bite-proof record c1l9a_wo1_verify_rerun
        moved_heads = _verify_rerun_heads_moved(first.get("head"), artifact, head, moved)
        if result == "pass" and moved_heads is not None:
            _set_terminal(state, "halted")
            state["certification"] = {
                "shape": None,
                "reason": ("verify re-run ran at a different head (%s then %s) — halt, "
                           "certification withheld" % moved_heads)}
            _decision(state, "verify-rerun-head-moved",
                      "verify re-run ran at a different head (%s then %s) — halt, certification "
                      "withheld" % moved_heads)
            state["step"] = P_TERMINAL
            return
        # axis: a re-run that passed counts only on the working-tree contents the first run saw — see bite-proof record c1l9a_wo1_verify_rerun
        trees = set(first.get("trees") or []) | set(_verify_artifact_trees(artifact))
        if result == "pass" and len(trees) > 1:
            _set_terminal(state, "halted")
            state["certification"] = {
                "shape": None,
                "reason": "verify re-run ran on changed working-tree contents — halt, "
                          "certification withheld"}
            _decision(state, "verify-rerun-tree-changed",
                      "verify re-run ran on changed working-tree contents — halt, certification "
                      "withheld")
            state["step"] = P_TERMINAL
            return
    if result == "fail":
        _set_terminal(state, "halted")
        state["certification"] = {"shape": None, "reason": "verify gate failed"}
        _decision(state, "verify-fail", "verify gate failed — halt, certification withheld")
        state["step"] = P_TERMINAL
        return
    if result in _VERIFY_SKIP:
        if _verify_command_configured(config):
            # A configured verify command reported a skip — it did NOT actually run its checks. Fail
            # closed: a configured verification must PASS, never advance on a skip (#507 R2 residual-2).
            _set_terminal(state, "halted")
            state["certification"] = {
                "shape": None,
                "reason": ("verify gate reported %r but a verify command is configured (%r) — the "
                           "gate did not run; halt, certification withheld"
                           % (result, config.get("verifyCommand")))}
            _decision(state, "verify-skip-but-configured",
                      "verify result %r with a configured verify command — fail closed, the gate "
                      "did not actually run" % result)
            state["step"] = P_TERMINAL
            return
        _decision(state, "verify-skipped",
                  "verify gate skipped (%s) — advancing unverified (no verify command)" % result)
    elif result != "pass":
        # timeout / missing / unknown → the gate did NOT pass; fail closed.
        _set_terminal(state, "halted")
        state["certification"] = {
            "shape": None,
            "reason": "verify gate did not pass (result %r) — halt, certification withheld" % (result,)}
        _decision(state, "verify-unresolved",
                  "verify result %r is not pass/skip — fail closed, certification withheld" % (result,))
        state["step"] = P_TERMINAL
        return
    if result == "pass":
        # axis: the receipt and review record name which verify stood behind the pass — see bite-proof record wo_b_2072_ci_verify
        _record_round(state, "verifyVia", _verify_via_row(config, artifact))
    then = state.pop("_verifyThen", None)
    if then == VERIFY_THEN_POST_AUDITS:
        _after_audits(state, config)
        return
    # VERIFY_THEN_CAP, and the legacy position (a gate pending with no flag): the round advance is
    # here — past the cap it hands back `round-cap`; otherwise it enters the delta round.
    if not _advance_round(state, config, reason="post-verify-advance"):
        return
    state["reviewedDiff"] = state.get("headDiff") or state.get("reviewedDiff")
    _enter_delta_round(state, config)


def _enter_post_fix(state, config, session_dir=None, panel_diff_seam=None):
    """After the round's last fix-batch slice folds: advance or run the gate at the cap."""
    next_round = state["round"] + 1
    if next_round > _round_cap(config):
        # The round at the cap completes — fix AND gate — before the boundary refuses the next
        # round. The gate always runs on the post-fix head, including when the round's earlier gate
        # already passed.
        state["_verifyThen"] = VERIFY_THEN_CAP
        state["step"] = P_VERIFY
        return
    if not _advance_round(state, config, reason="post-fix-advance"):
        return
    state["reviewedDiff"] = state.get("headDiff") or state.get("reviewedDiff")
    state["_postFixEntry"] = True
    _enter_delta_round(state, config)


# ---- delta rounds (2+) ----------------------------------------------------------------------

def _derive_panel_diff_at_head(config, head_sha):
    """Derive ``git diff <baseRef>...<head_sha>`` at ``config.repoRoot``: the post-fix head diff.

    Returns ``(diff_text, None)`` on success or ``(None, detail)`` when derivation must refuse."""
    repo_root = config.get("repoRoot")
    base = config.get("baseRef")
    if not isinstance(repo_root, str) or not repo_root:
        return None, "repoRoot missing"
    if not isinstance(base, str) or not base:
        return None, "baseRef missing"
    if not isinstance(head_sha, str) or not head_sha:
        return None, "head unresolved"
    try:
        verify = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", "%s^{commit}" % base],
            cwd=repo_root,
            capture_output=True,
            timeout=120,
        )
    except (FileNotFoundError, OSError) as exc:
        return None, "git unavailable: %s" % exc
    except subprocess.SubprocessError as exc:
        return None, "git rev-parse failed: %s" % exc
    if verify.returncode != 0:
        return None, "baseRef not a commit"
    verified_base = verify.stdout.decode("utf-8", errors="replace").strip()
    if not verified_base:
        return None, "baseRef not a commit"
    try:
        proc = review_diff_bytes.run_git_diff_three_dot(
            repo_root, verified_base, head_sha, timeout=120)
    except (FileNotFoundError, OSError) as exc:
        return None, "git unavailable: %s" % exc
    except subprocess.SubprocessError as exc:
        return None, "git diff failed: %s" % exc
    except ValueError as exc:
        return None, str(exc)
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace") if proc.stderr else ""
        err = err.strip()
        msg = "git diff exit %d" % proc.returncode
        if err:
            msg += ": %s" % err
        return None, msg
    try:
        diff_text = proc.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, "diff not UTF-8: %s" % exc
    if not diff_text:
        return None, "empty diff"
    return diff_text, None


def _hand_back_unknown_fix_surface(state, detail):
    """The fail-closed answer to a fix surface the driver cannot work out: the PR is handed back with
    its findings still open, never a panel and never an empty scoped round. The extra audit round
    keeps its own handback."""
    if _is_extra_audit_round(state):
        _hand_back(state, "extra-audit-open",
                   "the extra audit round could not derive the surface of the cap round's fixes "
                   "(%s) and runs no panel; the fixes stay unaudited" % detail, cap=True)
        return
    _hand_back(state, "fix-surface-unknown",
               "The driver could not work out what this round's fixes changed (%s), so the fixes "
               "cannot be audited and the new code they touched cannot be searched. The PR is "
               "handed back with its findings still open; certification is withheld." % detail,
               cap=False)


def _fix_batch_keys(state):
    """The finding keys of the previous round's fix batch, in batch order, each once."""
    keys = []
    for f in state.get("fixBatch") or []:
        if isinstance(f, dict):
            key = _finding_key_of(f)
            if key not in keys:
                keys.append(key)
    return keys


def _enter_delta_round(state, config, panel_diff_seam=None, panel_head=None):
    """Rounds 2+: split_fix_surface(reviewed, head, fixBatch). Audit the fixed findings and scoped-find
    the fixes' own diff. A surface the driver cannot work out hands the PR back (`fix-surface-unknown`);
    no later round runs a panel. ``panel_diff_seam`` and ``panel_head`` are accepted and unused, so
    callers written before that need not change."""
    post_fix = bool(state.pop("_postFixEntry", False))
    if not state.get("_headDiffUnknown"):
        if _reevaluate_lane_dimensions(state, config, state.get("headDiff")):
            return
    # An unresolvable post-fix head diff (a missing/unreadable `headDiffPath`, no inline diff) is an
    # unknown surface BEFORE the split runs — never fold it through as an empty diff (#507). The PR is
    # handed back, not scanned over nothing.
    if state.pop("_headDiffUnknown", False):
        _hand_back_unknown_fix_surface(
            state, "post-fix head diff unresolvable (source %r)" % state.get("_headDiffSource"))
        return
    baseline = state.get("deltaBaseline")
    if not isinstance(baseline, dict):
        cause = "no baseline record" if baseline is None else "baseline is not a record"
        _hand_back_unknown_fix_surface(state, "%s: %s" % (DELTA_BASELINE_ABSENT, cause))
        return
    stamped_round = baseline.get("round")
    current_round = state["round"]
    if (not isinstance(stamped_round, int) or isinstance(stamped_round, bool)
            or stamped_round != current_round):
        _hand_back_unknown_fix_surface(
            state, "%s: baseline stamped round %s, current round %s"
            % (DELTA_BASELINE_ABSENT, stamped_round, current_round))
        return
    reviewed = baseline.get("diff")
    if not isinstance(reviewed, str):
        _hand_back_unknown_fix_surface(
            state, "%s: baseline diff is not text" % DELTA_BASELINE_ABSENT)
        return
    split = delta_surface.split_fix_surface(
        reviewed, state.get("headDiff"), state.get("fixBatch") or [])
    if split.get("unknown"):
        _hand_back_unknown_fix_surface(state, "delta surface unknown")
        return
    # The scoped finder reads the fixes' own diff and nothing else of the change; a delta that cannot
    # be worked out for some file leaves the whole round's surface unknown, never silently empty.
    fix_delta = _fix_delta_surface(state, reviewed, state.get("headDiff"))
    if fix_delta is None:
        _hand_back_unknown_fix_surface(state, "the fixes' own diff could not be computed for every file")
        return
    # a delta (scoped) round is NOT a full panel — reset the flag so a scoped certifying finish is
    # `audited-chain`, not `full-panel-confirmed`.
    state["fullPanelRan"] = False
    state["_auditTargets"] = _audit_targets(
        state, config, split.get("auditTargets") or {},
        reviewed_diff=reviewed)
    state["_newSurface"], state["_fixDeltaDiff"] = fix_delta
    _record_round(state, "roundKind", "delta")
    _record_round(state, "focus", {"on": "fixes", "fixes": _fix_batch_keys(state)})
    if post_fix:
        state["_verifyThen"] = VERIFY_THEN_POST_AUDITS
    state["step"] = P_AUDITS


def _fix_hunks_over_line(audit_targets_map, file, line):
    """The hunks of the fix surface in ``file`` over the finding's location — the same location
    (the line and its margin) and the same overlap test ``delta_surface.split_fix_surface`` used to
    attribute them; empty when the file or line is unusable."""
    if not isinstance(audit_targets_map, dict) or not isinstance(file, str) or not file:
        return []
    ranges = delta_surface.fixed_locations([{"file": file, "line": line}]).get(file)
    if not ranges:
        return []
    return [hunk for hunk in audit_targets_map.get(file) or []
            if isinstance(hunk, dict) and delta_surface._overlaps(hunk, ranges)]


def _diff_section(diff_text, file):
    """The lines of ``file``'s section of a unified diff — header, hunk headers, context and all."""
    out, inside = [], False
    for ln in (diff_text or "").splitlines():
        if ln.startswith("diff --git "):
            inside = ln == "diff --git a/%s b/%s" % (file, file)
        if inside:
            out.append(ln)
    return out


def _line_spans(section):
    """Per section line, the new-file (start, end) of the hunk it sits in (None before the first hunk)."""
    spans, cur = [], None
    for ln in section:
        m = delta_surface._HUNK.match(ln)
        if m:
            start = int(m.group(1))
            cur = (start, start + max(int(m.group(2) or 1) - 1, 0))
        spans.append(cur)
    return spans


def _fixer_delta_lines(reviewed_diff, head_diff, file, line, *, whole_file=False):
    """The fix's own diff at a finding's location (every hunk of the file when ``whole_file``): the unified diff between the file's section of the
    reviewed (pre-fix) diff and of the post-fix head diff, hunk headers and context kept, only the hunks
    that sit over the finding's line (and margin). Each line keeps the PR diff's own prefix after the
    diff mark, so ``-+x`` is a PR addition the fixer removed and ``++x`` one it made. A file the fix
    left alone has identical sections and yields nothing."""
    ranges = delta_surface.fixed_locations([{"file": file, "line": line}]).get(file)
    before, after = _diff_section(reviewed_diff, file), _diff_section(head_diff, file)
    if (not ranges and not whole_file) or before == after:
        return []
    spans_b, spans_a = _line_spans(before), _line_spans(after)

    def over(spans, lo, hi):
        if whole_file:
            return True
        near = spans[lo:hi] if hi > lo else spans[max(lo - 1, 0):lo + 1]
        return any(sp and delta_surface._overlaps({"start": sp[0], "end": sp[1]}, ranges)
                   for sp in near)

    delta = []
    matcher = difflib.SequenceMatcher(None, before, after, autojunk=False)
    for group in matcher.get_grouped_opcodes(3):
        if not any(op != "equal" and (over(spans_b, i1, i2) or over(spans_a, j1, j2))
                   for op, i1, i2, j1, j2 in group):
            continue
        first, last = group[0], group[-1]
        delta.append("@@ -%d,%d +%d,%d @@" % (
            first[1] + 1, last[2] - first[1], first[3] + 1, last[4] - first[3]))
        for op, i1, i2, j1, j2 in group:
            if op == "equal":
                delta.extend(" " + ln for ln in before[i1:i2])
                continue
            delta.extend("-" + ln for ln in before[i1:i2])
            delta.extend("+" + ln for ln in after[j1:j2])
    return delta


def _diff_files(diff_text):
    """The files a unified diff names, in order of first appearance."""
    files = []
    for ln in (diff_text or "").splitlines():
        m = re.match(r"diff --git a/(.+) b/(.+)$", ln)
        if m and m.group(2) not in files:
            files.append(m.group(2))
    return files


def _attempt_fixer_delta(reviewed_diff, head_diff, leave_out=()):
    """The whole fixer attempt's delta: the fix's own diff (reviewed head -> fixed head) over every
    file the attempt changed, not only a finding's location. A file in ``leave_out`` (a proven copy)
    has no section in it."""
    delta = []
    for file in _diff_files(reviewed_diff) + [f for f in _diff_files(head_diff)
                                              if f not in _diff_files(reviewed_diff)]:
        if file in leave_out:
            continue
        lines = _fixer_delta_lines(reviewed_diff, head_diff, file, None, whole_file=True)
        if lines:
            delta.append("diff --git a/%s b/%s" % (file, file))
            delta.extend(lines)
    return delta


_FIX_DELTA_GROUP_HEADER = re.compile(r"^@@ -\d+,\d+ \+(\d+),(\d+) @@$")


def _head_line_numbers(section):
    """Per line of one file's diff section, the head-file line it sits on, else None (a header line, or a
    line before the first hunk). A line the diff removes sits on the head line that follows it."""
    numbers, following = [], None
    for ln in section:
        hunk = delta_surface._HUNK.match(ln)
        if hunk:
            following = int(hunk.group(1))
            numbers.append(None)
        elif following is None or ln.startswith("\\"):
            numbers.append(None)
        else:
            numbers.append(following)
            if not ln.startswith("-"):
                following += 1
    return numbers


def _fix_delta_groups(delta, head_numbers):
    """The groups of one file's fix delta (``_fixer_delta_lines``) that change more than the
    line numbers of the PR diff's own hunk headers, as ``(lines, head_lines)``: the group's lines,
    header first, and the head-file lines its changed lines sit on. None when a group cannot be read."""
    groups, current = [], None
    for ln in delta:
        if _FIX_DELTA_GROUP_HEADER.match(ln):
            current = [ln]
            groups.append(current)
        elif current is not None and ln[:1] in (" ", "-", "+"):
            current.append(ln)
        else:
            return None
    kept = []
    for lines in groups:
        index = int(_FIX_DELTA_GROUP_HEADER.match(lines[0]).group(1)) - 1
        head_lines, content = [], False
        for ln in lines[1:]:
            mark, text = ln[0], ln[1:]
            if mark == "-":
                content = content or not text.startswith("@@")
                continue
            if mark == "+":
                if index < 0 or index >= len(head_numbers):
                    return None
                content = content or not text.startswith("@@")
                if head_numbers[index] is not None and not text.startswith("@@"):
                    head_lines.append(head_numbers[index])
            index += 1
        if content:
            kept.append((lines, head_lines))
    return kept


def _fix_delta_surface(state, reviewed_diff, head_diff):
    """``(surface, text)`` for the round's own fix delta, or None when it cannot be worked out.

    ``surface`` is the scoped finder's hunks, ``{file: [{start, end, text}]}``: for each file whose
    section differs between the reviewed (pre-fix) diff and the post-fix head diff, the head-file lines
    its changed lines sit on, one entry per group of changes, and for a file the fix removed the
    removal marker ``delta_surface.split_fix_surface`` uses. ``text`` is the same delta as a diff, each
    file under its ``diff --git`` line. A proven copy, which every seat's files leave out, is in neither."""
    reviewed_hunks = delta_surface.parse_hunks(reviewed_diff)
    head_hunks = delta_surface.parse_hunks(head_diff)
    if reviewed_hunks is None or head_hunks is None:
        return None
    left_out = set(_left_out_files(state))
    surface, text = {}, []
    for file in _diff_files(reviewed_diff) + [f for f in _diff_files(head_diff)
                                              if f not in _diff_files(reviewed_diff)]:
        if file in left_out:
            continue
        before, after = _diff_section(reviewed_diff, file), _diff_section(head_diff, file)
        if before == after:
            continue
        delta = _fixer_delta_lines(reviewed_diff, head_diff, file, None, whole_file=True)
        groups = _fix_delta_groups(delta, _head_line_numbers(after))
        if groups is None:
            return None
        if not groups:
            continue
        text.append("diff --git a/%s b/%s" % (file, file))
        for lines, _head_lines in groups:
            text.extend(lines)
        if not head_hunks.get(file) and reviewed_hunks.get(file):
            surface[file] = [{"start": 0, "end": 0, "removed": True,
                              "text": "@@ file removed between the reviewed and head diffs @@"}]
            continue
        surface[file] = [{"start": start, "end": end, "text": "\n".join(lines)}
                         for lines, head_lines in groups for start, end in _line_runs(head_lines)]
    return surface, "".join(ln + "\n" for ln in text)


def _line_runs(numbers, gap=3):
    """``[[start, end], ...]`` over the sorted distinct ``numbers``, a run kept whole while its next line
    is within ``gap`` lines of its last; ``[[0, 0]]`` when there are none (a change with no head line)."""
    runs = []
    for number in sorted(set(numbers)):
        if runs and number - runs[-1][1] <= gap:
            runs[-1][1] = number
        else:
            runs.append([number, number])
    return runs or [[0, 0]]


def _carried_owner_ruling(decision):
    """The owner-fix decision an audit target (or a sibling record) carries: ``(ownerRuling, seq)``,
    or ``(None, None)`` when the decision is not an owner fix ruling."""
    if not (isinstance(decision, dict) and decision.get("ruling") in _OWNER_FIX_RULINGS):
        return None, None
    owner_ruling = {"ruling": decision["ruling"], "reason": decision.get("reason")}
    for carried in ("guidance", "allowsChange"):
        if decision.get(carried) is not None:
            owner_ruling[carried] = decision[carried]
    return owner_ruling, _decision_seq(decision)


def _reported_unnamed_changes(state):
    """Every unnamed change an audit of this review recorded, oldest first: ``{ref, round, id, text}``
    with ``ref`` = ``r<round>:<audit entry id>``. The text is the entry's ``reportedUnnamedChange``;
    an entry recorded before that key existed gives it back from its reason (the downgraded-clearing
    prefix, or the ``Unnamed change:`` tail a not-discharged ruling keeps). One entry per ref."""
    rounds = state.get("rounds") if isinstance(state, dict) else None
    if not isinstance(rounds, dict):
        return []
    reported, seen = [], set()
    for rnd_key in sorted(rounds.keys(), key=_round_record_sort_key):
        try:
            rnd_num = int(rnd_key)
        except (TypeError, ValueError):
            continue
        entries = rounds[rnd_key].get("audits") if isinstance(rounds[rnd_key], dict) else None
        for entry in entries if isinstance(entries, list) else []:
            if not (isinstance(entry, dict) and isinstance(entry.get("id"), str) and entry["id"]):
                continue
            text = entry.get("reportedUnnamedChange")
            if not audits.has_usable_unnamed_change(text):
                reason = entry.get("reason")
                text = None
                if isinstance(reason, str) and reason.startswith(audits.UNNAMED_CHANGE_REASON_PREFIX):
                    text = reason[len(audits.UNNAMED_CHANGE_REASON_PREFIX):]
                elif (entry.get("ruling") == "not-discharged" and isinstance(reason, str)
                        and " Unnamed change: " in reason):
                    text = reason.split(" Unnamed change: ", 1)[1]
                if not audits.has_usable_unnamed_change(text):
                    continue
            ref = "r%d:%s" % (rnd_num, entry["id"])
            if ref not in seen:
                seen.add(ref)
                reported.append({"ref": ref, "round": rnd_num, "id": entry["id"],
                                 "text": text.strip()})
    return reported


def _changed_why(finding):
    """The build session's reason for changing the finding's break-it test: the latest non-blank
    `changedWhy` on its run list, else None."""
    runs = finding.get(break_it.RUNS_FIELD)
    for run in reversed(runs if isinstance(runs, list) else []):
        why = run.get("changedWhy") if isinstance(run, dict) else None
        if isinstance(why, str) and why.strip():
            return why.strip()
    return None


def _audit_head(state, config):
    """The post-fix head the round audits: the fix round's recorded `fixFoldHead`, else the head the
    repository names now; None when neither can be read."""
    rounds = state.get("rounds") if isinstance(state.get("rounds"), dict) else {}
    current = state.get("round")
    for rnd in (current - 1, current) if isinstance(current, int) else ():
        record = rounds.get(str(rnd))
        head = record.get("fixFoldHead") if isinstance(record, dict) else None
        if _nonempty_str(head):
            return head
    repo_root = config.get("repoRoot")
    return _resolve_head_commit(repo_root) if _nonempty_str(repo_root) else None


def _break_it_target_facts(state, config, finding, head):
    """The `breakIt` block of an audit target: the test role's test, the test committed at the audited
    head, the build session's reason for a change, and how the two compare (`audits.BREAK_IT_MATCHES`).
    Fails closed: a committed test git cannot read is `missing`."""
    block, _kind = break_it.carried_block(finding)
    path = block["path"] if block is not None else None
    current = block["content"] if block is not None else None
    kept = finding.get(REVIEWER_TEST_FIELD)
    reviewer = kept if isinstance(kept, str) else current
    committed = None
    repo_root = config.get("repoRoot")
    if path is not None and _nonempty_str(repo_root) and _nonempty_str(head):
        raw = _git_bytes(repo_root, "cat-file", "blob", "%s:%s" % (head, path))
        try:
            committed = raw.decode("utf-8") if raw is not None else None
        except UnicodeDecodeError:
            committed = None
    why = _changed_why(finding)
    if committed is None:
        match = audits.MATCH_MISSING
    elif committed == reviewer:
        match = audits.MATCH_SAME
    elif committed == current and why is not None:
        match = audits.MATCH_CHANGED_EXPLAINED
    else:
        match = audits.MATCH_CHANGED_UNEXPLAINED
    return {"path": path, "reviewerTest": reviewer, "committedTest": committed,
            "changedWhy": why, "match": match}


def _audit_targets(state, config, audit_targets_map, reviewed_diff=None):
    """Location-grouped audit targets, each carrying the fixer's vendor so the orchestrator seats a
    DIFFERENT auditor vendor. Grounded in the fix batch (the fixed findings), attributed to the
    hunks that sit over their lines. Rows sharing a finding key collapse to one target — first
    occurrence wins. A re-queued target keys by its findingKey marker, never by id."""
    fixer_vendor = config.get("fixerVendor")
    runner_only = bool(state.get("_advanceUsed"))
    maker_families, pinned_vendors = receipt_disclosures.auditor_constraints(state)
    auditor_vendor, independence = _auditor_vendor(
        config, fixer_vendor, runner_only=runner_only, maker_families=maker_families,
        pinned_vendors=pinned_vendors)
    if independence != "independent":
        state["independenceDegraded"] = True
    targets = []
    seen_keys = set()
    effective = _live_ruling_by_key(state)
    ledger_by_key, _fault = _disposition_ledger_by_key(state)
    history = _finding_history(state)
    # The attempt's whole delta and the batch's findings in compact form ride every target, so the
    # auditor attributes a change to any finding of the batch before calling it unnamed.
    # A proven copy is no seat's input: it is in neither the fix hunks nor the delta.
    left_out = set(_left_out_files(state))
    audit_targets_map = {file: hunks for file, hunks in (audit_targets_map or {}).items()
                         if file not in left_out}
    attempt_delta = (_attempt_fixer_delta(reviewed_diff, state.get("headDiff"), left_out)
                     if reviewed_diff is not None else None)
    batch_findings = []
    for bf in state.get("fixBatch") or []:
        if isinstance(bf, dict) and _finding_key_of(bf) not in [b["id"] for b in batch_findings]:
            sibling = {"id": _finding_key_of(bf), "file": bf.get("file"),
                       "line": bf.get("line"), "title": bf.get("title")}
            # A sibling carries its scope: body, suggestion and its effective owner ruling, so the
            # auditor attributes a change to the finding whose scope names it.
            for carried in ("body", "suggestion"):
                if bf.get(carried) is not None:
                    sibling[carried] = bf[carried]
            sib_ruling, sib_seq = _carried_owner_ruling(
                _row_decision(state, effective, ledger_by_key, sibling["id"]))
            if sib_ruling is not None:
                sibling["ownerRuling"] = sib_ruling
                sibling["ownerRulingSeq"] = sib_seq
            batch_findings.append(sibling)
    # The round's other findings ride every target: a change the fix makes that the auditor can
    # attribute to one of them is that finding's fix, not an unnamed change. Findings the owner
    # skipped or ruled out of scope, and refuted ones, are no round finding to attribute a change to.
    batch_keys = {_finding_key_of(bf) for bf in state.get("fixBatch") or [] if isinstance(bf, dict)}
    round_findings = []
    for rf in state.get("findings") or []:
        rkey = _finding_key_of(rf) if isinstance(rf, dict) else None
        if (not isinstance(rkey, str) or rkey in batch_keys
                or any(r["id"] == rkey for r in round_findings)):
            continue
        rdecision = _row_decision(state, effective, ledger_by_key, rkey)
        if rdecision is not None and rdecision.get("ruling") not in _OWNER_FIX_RULINGS:
            continue
        if (ledger_by_key.get(rkey) or {}).get("disposition") in ("refuted", "out-of-scope"):
            continue
        round_findings.append(_round_finding_entry(
            rkey, rf, _carried_owner_ruling(rdecision)))
    # A finding an audit raised, whose parent this batch carries again, is audited under its own key:
    # a rider. Its content and the round-findings entry it needs (so its parent's auditor can attribute
    # the fix of it) come from the ledger or the live findings, whichever is newer.
    riders = _spawned_riders(state, effective, ledger_by_key, _fault, batch_keys)
    for child, _parent, content in riders:
        if not any(r["id"] == child for r in round_findings):
            round_findings.append(_round_finding_entry(
                child, content, _carried_owner_ruling(_row_decision(state, effective, ledger_by_key, child))))
    reported_changes = _reported_unnamed_changes(state)
    audited_head = {}

    def target_row(f, tid):
        """One audit target row — a batch finding's and a rider's alike, so the two never drift."""
        row = {
            "id": tid,
            session_contract.FINDING_KEY_FIELD: tid,
            "identity": finding_identity(f),
            "file": f.get("file"), "line": f.get("line"), "title": f.get("title"),
            "severity": f.get("severity"),
            # Carry the recurrence class keys so the audit-stall breaker's alias-tolerant match
            # (circuit_breaker._audit_outcome_aliases) sees them: a retitled-but-same-class finding
            # must still stall across consecutive not-discharged rounds (#507 v0).
            "classKey": f.get("classKey") or review_memory.class_key(f),
            "dimension": f.get("dimension"),
            "taxonomy": f.get("taxonomy"),
            "fixerVendor": fixer_vendor,
            "independence": independence,
            "verdict": f.get("verdict"),
            "evidence": f.get("evidence"),
        }
        # The auditor compares the fix with what the finding names: its body, suggestion and
        # consequence ride every target, beside the hunks of the fix over the finding's line.
        for carried in ("body", "suggestion", review_findings_schema.CONSEQUENCE_KEY):
            if f.get(carried) is not None:
                row[carried] = f[carried]
        row["fixHunks"] = _fix_hunks_over_line(audit_targets_map, f.get("file"), f.get("line"))
        # `fixerDelta` is the attempt's own diff (reviewed head -> fixed head) over every file it
        # changed; `batchFindings` are the attempt's other findings (id, file, line, title).
        if attempt_delta is not None:
            row["fixerDelta"] = list(attempt_delta)
        row["batchFindings"] = [b for b in batch_findings if b["id"] != tid]
        row["roundFindings"] = [r for r in round_findings if r["id"] != tid]
        row["reportedUnnamedChanges"] = list(reported_changes)
        # The finding's effective ruling rides the target, so an auditor weighing a change the finding
        # does not name sees whether the owner's guidance allows it. A scope refusal is an audit ruling
        # that was not discharged (audits.UNNAMED_CHANGE_REASON_PREFIX): it stays open through the
        # ordinary not-discharged loop, with no state of its own.
        # The finding's last audit rides the target too (derived from the audit history, as the fixer
        # order's does), so the auditor sees why the last audit refused.
        slot = history.get(tid)
        prior = slot.get("priorAudit") if isinstance(slot, dict) else None
        if isinstance(prior, dict):
            row["priorAudit"] = {k: prior[k] for k in ("round", "ruling", "reason") if k in prior}
        decision = _row_decision(state, effective, ledger_by_key, tid)
        owner_ruling, owner_seq = _carried_owner_ruling(decision)
        if owner_ruling is not None:
            row["ownerRulingSeq"] = owner_seq
            row["ownerRuling"] = owner_ruling
        if break_it.carries_test(f):
            # axis: a re-queued target that carries a break-it test must still hand the next fixer its exact test block, body and run records
            for carried in ("suggestion", "body", break_it.RUN_FIELD, break_it.RUNS_FIELD):
                if f.get(carried) is not None:
                    row[carried] = f[carried]
            # axis: the audit compares the test committed at the audited head with the test role's version
            if "head" not in audited_head:
                audited_head["head"] = _audit_head(state, config)
            row["breakIt"] = _break_it_target_facts(state, config, f, audited_head["head"])
        if auditor_vendor is not None:
            row["auditorVendor"] = auditor_vendor
        return row

    for f in state.get("fixBatch") or []:
        if not isinstance(f, dict):
            continue
        tid = _finding_key_of(f)
        if tid in seen_keys:
            continue
        seen_keys.add(tid)
        targets.append(target_row(f, tid))
    for child, parent, content in riders:
        if child in seen_keys:
            continue
        seen_keys.add(child)
        rider = target_row(content, child)
        rider["spawnedFrom"] = parent
        targets.append(rider)
    return targets


def _round_finding_entry(key, finding, carried_ruling):
    """One round-findings entry — id, place, title, body and suggestion, and the finding's carried owner
    ruling — in the one shape every audit target lists its round's other findings in."""
    entry = {"id": key, "file": finding.get("file"), "line": finding.get("line"),
             "title": finding.get("title")}
    for carried in ("body", "suggestion"):
        if finding.get(carried) is not None:
            entry[carried] = finding[carried]
    entry_ruling, entry_seq = carried_ruling
    if entry_ruling is not None:
        entry["ownerRuling"] = entry_ruling
        entry["ownerRulingSeq"] = entry_seq
    return entry


def _spawned_riders(state, effective, ledger_by_key, ledger_fault, batch_keys):
    """The findings an audit raised that ride this round's audits as targets of their own, as
    ``(child key, parent key, content)`` in child-key order. A child rides when its parent is in the
    fix batch again, it is no batch finding itself, and it has no disposition settling it: never a
    summary row, a merged-in or out-of-scope one, nor one a current disposition (a ruling the owner has
    not reopened) already closed, nor one whose effective owner decision rules anything but a fix
    (``_OWNER_FIX_RULINGS``). A ledger that cannot be read gives no riders."""
    spawned = _audit_spawned(state)
    if not spawned or ledger_fault is not None:
        return []
    live_by_key = {}
    for finding in state.get("findings") or []:
        key = _finding_identity_key(finding) if isinstance(finding, dict) else None
        if key and not finding.get("summaryEntry"):
            live_by_key.setdefault(key, finding)
    riders = []
    for child in sorted(k for k in spawned if isinstance(k, str)):
        parent = spawned[child]
        if not isinstance(parent, str) or parent not in batch_keys or child in batch_keys:
            continue
        live = live_by_key.get(child)
        row = ledger_by_key.get(child) or live
        if (not isinstance(row, dict) or row.get("summaryEntry")
                or row.get(session_contract.MERGED_INTO_FIELD)
                or row.get("disposition") == "out-of-scope"
                or (_disposition_is_current(row) and not _restaged_after(state, child, row))):
            continue
        rdecision = _row_decision(state, effective, ledger_by_key, child)
        if rdecision is not None and rdecision.get("ruling") not in _OWNER_FIX_RULINGS:
            continue
        riders.append((child, parent, _newest_content(row, live)))
    return riders


AUDIT_PROVENANCE_RUNNER_RECORD = round_records.AUDIT_PROVENANCE_RUNNER_RECORD
AUDIT_PROVENANCE_HAND_LANDED = round_records.AUDIT_PROVENANCE_HAND_LANDED
AUDIT_PROVENANCE_MIXED = round_records.AUDIT_PROVENANCE_MIXED
AUDIT_PROVENANCE_COLLECTION_MANIFEST = round_records.AUDIT_PROVENANCE_COLLECTION_MANIFEST
_LEGACY_AUDIT_PROVENANCE_DISPATCH_MANIFEST = round_records.AUDIT_PROVENANCE_LEGACY_DISPATCH_MANIFEST


def _audit_adapter_disclosures(state, artifact):
    """The adapter disclosures block for the audits fold — from the artifact if still present, else
    from the round record `_record_adapter_provenance` wrote earlier in the same `_fold` call."""
    prov = artifact.get("provenance") if isinstance(artifact, dict) else None
    if isinstance(prov, dict):
        return prov
    rec = state.get("rounds", {}).get(str(state["round"]), {})
    adapter = rec.get("adapterProvenance")
    if not isinstance(adapter, dict):
        return None
    by_phase = adapter.get("byPhase")
    if isinstance(by_phase, dict):
        phase_prov = by_phase.get(P_AUDITS)
        return phase_prov if isinstance(phase_prov, dict) else None
    return adapter if adapter and "byPhase" not in adapter else None


def _audit_provenance_basis(state, artifact):
    """Per-round auditProvenance from adapter-recorded seat sources, not the fold path alone."""
    if state.get("_submitUsed"):
        return AUDIT_PROVENANCE_COLLECTION_MANIFEST
    disclosures = _audit_adapter_disclosures(state, artifact)
    prov_src = (disclosures.get("provenanceSource")
                if isinstance(disclosures, dict) else None)
    if not isinstance(prov_src, dict) or not prov_src:
        return AUDIT_PROVENANCE_COLLECTION_MANIFEST
    targets = state.get("_auditTargets") or []
    seat_ids = [t.get("id") for t in targets
                if isinstance(t, dict) and t.get("id") is not None]
    if not seat_ids:
        seat_ids = list(prov_src)
    sources = set()
    for seat in seat_ids:
        src = prov_src.get(seat)
        if src is None:
            return AUDIT_PROVENANCE_MIXED
        sources.add(src)
    if not sources:
        return AUDIT_PROVENANCE_COLLECTION_MANIFEST
    if len(sources) == 1:
        only = next(iter(sources))
        if only == AUDIT_PROVENANCE_RUNNER_RECORD:
            return AUDIT_PROVENANCE_RUNNER_RECORD
        if only == AUDIT_PROVENANCE_HAND_LANDED:
            return AUDIT_PROVENANCE_HAND_LANDED
        if only == _LEGACY_AUDIT_PROVENANCE_DISPATCH_MANIFEST:
            return AUDIT_PROVENANCE_COLLECTION_MANIFEST
        return AUDIT_PROVENANCE_MIXED
    return AUDIT_PROVENANCE_MIXED


def _fold_audits(state, config, artifact, session_dir=None):
    """Consume the fix-audit rulings deterministically (audits.apply_audit_results). Record the
    audit round for the audit-keyed breaker; new-issue candidates join the scoped-finder scan."""
    results = artifact.get("results") if isinstance(artifact.get("results"), list) else []
    targets = state.get("_auditTargets") or []
    # The DRIVER records the SELECTED independent auditor per target (its own seating decision).
    expected_auditors = {t.get("id"): t.get("auditorVendor")
                         for t in targets if isinstance(t, dict) and t.get("id") is not None}
    # Provenance rests on the recorded dispatch provenance (the runner record at state v5; the
    # dispatch manifest on a legacy session) — {result-id: vendor} carried in the submit artifact's
    # `collectionManifest`, NEVER derived from the result contents. The fold authenticates a clearing
    # ruling against THIS manifest (must exist AND equal the recorded selection); the in-result
    # `auditorVendor` echo is advisory only. The driver cannot cryptographically verify engine
    # identity and does not pretend to — the guarantee is exactly as strong as the recorded dispatch
    # provenance (#507 WO-FIX-RECOVERY).
    collection_manifest = artifact.get("collectionManifest")
    if not isinstance(collection_manifest, dict):
        collection_manifest = None
    # A target with no eligible auditor was never audited: any result submitted for it is ignored, so
    # it folds exactly like silence — `unaudited`, not-discharged, never credited as audited.
    no_auditor_ids = {tid for tid, vendor in expected_auditors.items() if not vendor}
    if no_auditor_ids:
        results = [r for r in results
                   if not (isinstance(r, dict) and r.get("id") in no_auditor_ids)]
    # A fix may change behaviour its finding does not name only where the finding's one effective
    # decision is a guidance ruling that says so (`allowsChange`); the owner gate never carries it.
    # The binding decision is the one fixer dispatch resolves (`_row_decision`, merged members
    # included), and it authorizes only when it is the decision the auditor's target carried: a
    # ruling recorded after the audit order went out was never weighed, so it stays pending.
    effective = _live_ruling_by_key(state)
    ledger_by_key, _fault = _disposition_ledger_by_key(state)
    # The auditor names the one carried decision whose guidance permits the reported change
    # (`unnamedChangeAllowedBySeq`); the fold verifies it. The named seq must be carried on this target
    # (its own or a batch sibling's), still be that finding's current effective decision, and allow
    # the change; a sibling's decision never overrides the target's own `allowsChange: false`. Any
    # other case credits nothing, and the change stays an unnamed-change refusal.
    named_by_id = {}
    for r in results:
        if isinstance(r, dict) and isinstance(r.get("id"), str):
            named_by_id.setdefault(r["id"], r.get("unnamedChangeAllowedBySeq"))
    bound_by_id = {}
    for t in targets:
        if not (isinstance(t, dict) and isinstance(t.get("id"), str)):
            continue
        named = named_by_id.get(t["id"])
        if not audits.is_decision_seq(named):
            continue
        candidates = [(t["id"], t.get("ownerRulingSeq"))]
        for b in t.get("batchFindings") or []:
            if isinstance(b, dict) and isinstance(b.get("id"), str):
                candidates.append((b["id"], b.get("ownerRulingSeq")))
        own_now = _row_decision(state, effective, ledger_by_key, t["id"])
        credited = []
        for cid, carried_seq in candidates:
            if carried_seq != named:
                continue
            bound = _row_decision(state, effective, ledger_by_key, cid)
            if (isinstance(bound, dict)
                    and bound.get("ruling") == "guidance"
                    and bound.get("allowsChange") is True
                    and carried_seq == _decision_seq(bound)):
                if (cid != t["id"] and isinstance(own_now, dict)
                        and own_now.get("allowsChange") is False):
                    continue
                credited.append(bound)
        if credited:
            bound_by_id[t["id"]] = credited[:1]
    change_allowed_ids = list(bound_by_id)
    outcome = audits.apply_audit_results(targets, results, expected_auditors=expected_auditors,
                                         collection_manifest=collection_manifest,
                                         carry_fields=(session_contract.FINDING_KEY_FIELD,),
                                         change_allowed_ids=change_allowed_ids)
    # A rider is a finding an audit raised, audited under its own key beside its parent's target. A
    # discharge records it `fixed` below; anything else leaves it with no disposition, for the settle.
    # It never joins the fix list, the breaker's outcomes or the PR-body audited set, so it leaves
    # `notDischarged` here, before anything reads that list. The disclosure lists stay as they are.
    spawned_from = {t["id"]: t["spawnedFrom"] for t in targets
                    if isinstance(t, dict) and isinstance(t.get("id"), str)
                    and t.get("spawnedFrom") is not None}
    rider_ids = set(spawned_from)
    riders_open = [i for i in outcome["notDischarged"] if i in rider_ids]
    outcome["notDischarged"] = [i for i in outcome["notDischarged"] if i not in rider_ids]
    state["_auditOutcome"] = outcome
    # the audit round for check_audit_breaker: identity + effective ruling PLUS the recurrence class
    # keys the alias-tolerant stall match consumes (#507 v0) — carried straight off each audit entry
    # (audits.apply_audit_results threads them from the target). The `title` MUST ride too: without it
    # the breaker's canonical class key collapses to a title-less `dim::tax::` alias that merges two
    # DISTINCT classKeys sharing dimension/taxonomy into a false stall (#507 R2 v2).
    audit_round = {"round": state["round"], "outcomes": [
        {"identity": a.get("identity"), "ruling": a.get("ruling"),
         "title": a.get("title"), "classKey": a.get("classKey"),
         "dimension": a.get("dimension"), "taxonomy": a.get("taxonomy")}
        for a in outcome["audits"] if a.get("id") not in rider_ids]}
    state["auditRounds"].append(audit_round)
    mismatch_ids = list(outcome.get("testMismatch") or [])
    if mismatch_ids:
        _record_round(state, "testMismatch", mismatch_ids)
        _decision(state, "break-it-test-mismatch",
                  "the committed break-it test is not the test role's version, or weakens it, so the "
                  "fix is not discharged: %s" % ", ".join(mismatch_ids))
    for pid in outcome.get("unauthenticated", []):
        audit_reason = None
        audit_cause = None
        for audit in outcome.get("audits", []):
            if isinstance(audit, dict) and audit.get("id") == pid:
                audit_reason = audit.get("reason")
                audit_cause = audit.get("unauthenticatedCause")
                break
        if audit_cause in (audits.UNAUTHENTICATED_MANIFEST_VENDOR_MISMATCH,
                           audits.UNAUTHENTICATED_NO_AUDITOR_RECORDED):
            detail = "audit result for %s could not be authenticated — %s" % (pid, audit_reason)
        elif audit_cause == audits.UNAUTHENTICATED_MANIFEST_ENTRY_MISSING:
            if isinstance(collection_manifest, dict) and pid in collection_manifest:
                detail = "audit result for %s could not be authenticated — %s" % (pid, audit_reason)
            else:
                found_keys = (sorted(collection_manifest)
                              if isinstance(collection_manifest, dict) else [])
                detail = ("audit result for %s could not be authenticated — expected a "
                          "collectionManifest entry keyed %r (payload.targets[].id); manifest keys "
                          "found: %s — not-discharged"
                          % (pid, pid, found_keys))
        else:
            found_keys = (sorted(collection_manifest)
                          if isinstance(collection_manifest, dict) else [])
            detail = ("audit result for %s could not be authenticated — expected a "
                      "collectionManifest entry keyed %r (payload.targets[].id); manifest keys "
                      "found: %s — not-discharged"
                      % (pid, pid, found_keys))
        _decision(state, "audit-provenance-fail", detail)
    unnamed_ids = list(outcome.get("unnamedChange") or [])
    if unnamed_ids:
        _record_round(state, "auditUnnamedChange", unnamed_ids)
        _decision(state, "audit-unnamed-change",
                  "the fix changes behaviour its finding does not name, so it is not accepted "
                  "without a ruling: %s" % ", ".join(unnamed_ids))
    attributed_ids = list(outcome.get("attributedChange") or [])
    if attributed_ids:
        _record_round(state, "auditAttributedChange", attributed_ids)
        _decision(state, "audit-attributed-change",
                  "the fix's other change is the fix of a round finding or a revert of a reported "
                  "change, checked against the review's own record: %s" % ", ".join(attributed_ids))
    for pid in outcome.get("echoMismatch", []):
        _decision(state, "audit-echo-mismatch",
                  "audit result for %s echoed a vendor other than the recorded dispatch provenance "
                  "— advisory only; the manifest governed and the discharge stands" % pid)
    # Provenance rests on the adapter-recorded seat sources (never the fold path alone) — recorded
    # per round so the receipt discloses the trust basis (#507 WO-FIX-RECOVERY, #1272 WO-R3).
    _record_round(state, "auditProvenance", _audit_provenance_basis(state, artifact))
    _record_round(state, "audits", outcome["audits"])
    spawned_audits = [{"id": a.get("id"), "spawnedFrom": spawned_from[a.get("id")],
                       "ruling": a.get("ruling")}
                      for a in outcome["audits"] if a.get("id") in rider_ids]
    if spawned_audits:
        _record_round(state, "spawnedAudits", spawned_audits)
    # The staged PR body is audited only when every target of the round folded to an authenticated
    # clearing ruling: `discharged` holds exactly those (a clearing ruling the manifest could not
    # authenticate folds to not-discharged), and `notDischarged` holds every other target.
    # The fix folds in round N and its audits in round N+1 (`_enter_post_fix` advances the round).
    fix_round = state["rounds"].get(str(state["round"] - 1))
    pr_body_fix = fix_round.get("prBodyFix") if isinstance(fix_round, dict) else None
    audit_ids = {t.get("id") for t in targets if isinstance(t, dict) and t.get("id") not in rider_ids}
    if (isinstance(pr_body_fix, dict) and isinstance(pr_body_fix.get("after"), str)
            and pr_body_fix["after"] and audit_ids
            and not outcome.get("notDischarged")
            and audit_ids <= set(outcome.get("discharged") or [])):
        _record_round(state, "prBodyAudited", pr_body_fix["after"])
    _record_round(state, "auditIndependence",
                  targets[0]["independence"] if targets else "n/a")
    targets_by_id = {t.get("id"): t for t in targets if isinstance(t, dict) and t.get("id")}
    # A decision the audit credited a fix under has been delivered: the resolver must not send it again.
    lineage = _lineage_map(state)
    discharged_ids = set(outcome.get("discharged") or [])
    for audit in outcome["audits"]:
        marked = []
        if audit.get("allowedChange") and audit.get("id") in change_allowed_ids:
            marked.extend(bound_by_id[audit["id"]])
        if audit.get("id") in discharged_ids and audit.get("id") in targets_by_id:
            # The allowing ruling reached the audit and the audit cleared the fix: delivered, with or without
            # an unnamed change, so the resolver does not reopen it.
            own = _row_decision(state, effective, ledger_by_key, audit["id"])
            carried_seq = targets_by_id[audit["id"]].get("ownerRulingSeq")
            if (isinstance(own, dict) and own.get("ruling") == "guidance"
                    and own.get("allowsChange") is True and carried_seq is not None
                    and carried_seq == _decision_seq(own)):
                marked.append(own)
        sent = state.setdefault("sentUnderDecision", {})
        for decision in marked:
            for at in (audit["id"], decision.get("findingKey")):
                root = _lineage_root(lineage, at)
                sent[root] = max(sent.get(root, 0), _decision_seq(decision))
    still_open = _open_audit_ids_from_not_discharged(outcome.get("notDischarged"))
    if still_open is not None:
        still_open |= set(riders_open)  # a rider left open still holds its restage marks
    for tid in outcome.get("discharged") or []:
        receipt = _fixed_disposition_receipt(state, session_dir, tid, targets_by_id.get(tid))
        _record_disposition(state, tid, "fixed", state["round"], dispositionReceipt=receipt)
        # The discharge supersedes the closure's earlier dispositions the ruling had reopened.
        # An unresolvable notDischarged list leaves every restage mark in place (fail closed).
        reopened = state.get("restagedAfterDispositionSeq")
        if reopened and still_open is not None:
            ledger_now, _lf = _disposition_ledger_by_key(state)
            for member in _ruling_closure(state, ledger_now or {}, tid) - {tid} - still_open:
                reopened.pop(member, None)
                (state.get("restagedInRound") or {}).pop(member, None)
    state["_newIssues"] = outcome["newIssues"]
    for aid in outcome["notDischarged"]:
        _decision(state, "not-discharged", aid)
    for aid in riders_open:
        _decision(state, "spawned-audit-not-discharged", aid)
    if state.get("_verifyThen") == VERIFY_THEN_POST_AUDITS:
        state["step"] = P_VERIFY
        return
    _after_audits(state, config)


def _after_audits(state, config):
    """Scoped-finder routing after audits fold — or after the post-audits verify gate passes."""
    # axis: the extra audit round runs no scoped finder, gap sweep, fixer or verify after its audits — see bite-proof record c1l4b_wo_a
    if _is_extra_audit_round(state):
        _settle_extra_audit(state, config)
        return
    # Scoped-finder routing (#507 WO-R2b). Dispatch the scoped new-finding scan whenever the round's
    # fix delta left a NON-EMPTY surface (`_newSurface`, set by `_enter_delta_round`: the head-side
    # lines the fixes changed in every file that is not a proven copy). A genuinely empty surface (the
    # fixes touched only proven copies — an unknown surface never reaches audits, it hands the PR
    # back) SKIPS the scoped dispatch with a receipt-visible note, rather than dispatching a vacuous
    # scan that reviews nothing while looking conformant. The audits' own new-issue candidates still
    # route through the same fold (an empty-artifact `_fold_scoped`).
    if state.get("_newSurface"):
        state["step"] = P_SCOPED
        return
    _record_round(state, "scopedFinder", "skipped-empty-surface")
    _decision(state, "scoped-finder-skipped",
              "scopedFinder: skipped-empty-surface — the fixes' own diff left an empty "
              "surface; the scoped new-finding scan was skipped (audit new-issues still routed)")
    _fold_scoped(state, config, {})


AUDIT_ORIGIN_FIELD = "originAuditId"
AUDIT_SPAWNED_KEY = "auditSpawned"


def _audit_spawned(state):
    """The driver's spawn map ``{child finding key: parent finding key}`` — a finding an audit raised,
    keyed to the audit target it came from. Absent or not a dict (an older session) reads as empty."""
    spawned = state.get(AUDIT_SPAWNED_KEY) if isinstance(state, dict) else None
    return spawned if isinstance(spawned, dict) else {}


def _bind_audit_spawned(state, new_issues, compiled):
    """Record, for each compiled survivor an audit's new issue produced, the audit target it came from.

    Bound by compile anchor, never by reading ``originAuditId`` off a survivor: when a scoped candidate
    and an audit candidate share an anchor at equal severity, the compile keeps the scoped dict and the
    audit's link is lost. A survivor links only when exactly one distinct origin raised its anchor; none,
    or two, link nothing (the finding is then left to the settle for the owner). A survivor raised by
    two or more origins in this fold also loses any link an earlier round bound: an uncertain link is
    not kept."""
    origins_by_anchor = {}
    for ni in new_issues:
        origin = ni.get(AUDIT_ORIGIN_FIELD)
        if not (isinstance(origin, str) and origin.strip()) or not isinstance(ni.get("file"), str):
            continue
        if ni.get("line") is None:
            continue
        ok, line = _coerce_line(ni.get("line"))
        if not ok:
            continue
        anchor = _finding_anchor(dict(ni, line=line))
        origins_by_anchor.setdefault(anchor, set()).add(origin)
    bound, ambiguous = {}, []
    for finding in compiled:
        if not isinstance(finding, dict) or finding.get("summaryEntry"):
            continue
        key = _finding_identity_key(finding)
        origins = origins_by_anchor.get(_finding_anchor(finding))
        if key and origins and len(origins) == 1:
            bound[key] = next(iter(origins))
        elif key and origins:
            ambiguous.append(key)
    existing = state.get(AUDIT_SPAWNED_KEY)
    if isinstance(existing, dict):
        for key in ambiguous:
            existing.pop(key, None)
    if bound:
        spawned = state.get(AUDIT_SPAWNED_KEY)
        if not isinstance(spawned, dict):
            spawned = state[AUDIT_SPAWNED_KEY] = {}
        spawned.update(bound)


def _fold_scoped(state, config, artifact):
    """Fold the scoped new-finding scan over the fix's new surface; its candidates + the audits'
    new-issue candidates route through the same stage/cluster/verify fold."""
    candidates = artifact.get("findings") if isinstance(artifact.get("findings"), list) else []
    new_issues = state.pop("_newIssues", None) or []  # consumed: the terminal seeds only what is left
    new_issues = [ni for ni in new_issues if isinstance(ni, dict)]
    # axis: a scoped-finder seat never supplies a parent link — only an audit's new issue carries one
    scoped = [{k: v for k, v in c.items() if k != AUDIT_ORIGIN_FIELD} if isinstance(c, dict) else c
              for c in candidates]
    compiled, drops = mechanical_compile(scoped + new_issues, state.get("reviewedDiff"))
    _bind_audit_spawned(state, new_issues, compiled)
    _record_compile_drops(state, drops)
    state["_postAudit"] = True
    if compiled:
        _stage_findings(state, compiled)
        state["step"] = P_VERIFIERS
        # after verify+synthesis, _after_findings_settled runs; but for delta rounds we need the
        # audit-breaker, handled in _settle_delta.
        state["_settleDelta"] = True
        return
    _set_findings(state, [])
    _settle_delta(state, config)


def _settle_delta(state, config):
    """Delta-round terminal logic: audit-keyed breaker → self-recovery → hand back; open-work →
    fix leg; else the converged decision."""
    state.pop("_settleDelta", None)
    state.pop("_postAudit", None)
    outcome = state.get("_auditOutcome") or {"notDischarged": [], "discharged": []}
    # Record this delta round in the in-memory ledger and run the challenged-coverage breaker BEFORE
    # any terminal routing: a coverage decision recorded on a wrong principle whose class recurs must
    # park (cannot-certify), never certify as clean (the wrong_principle safety property).
    delta_findings = [f for f in (state.get("findings") or []) if isinstance(f, dict)]
    dim_map = {}
    for f in delta_findings:
        dname = f.get("dimension") or "scoped-finder"
        seat = dim_map.setdefault(dname, {"dimension": dname, "status": "run",
                                          "confidence": "high", "tier": DEEP, "findings": []})
        seat["findings"].append(f)
    if not dim_map:
        dim_map = {"scoped-finder": {"dimension": "scoped-finder", "status": "run",
                                     "confidence": "high", "tier": DEEP, "findings": []}}
    _append_review_record(state, state["round"], "delta", dim_map, delta_findings)
    challenged = _challenged_recurring_halt(state, config)
    if challenged:
        _park_cannot_certify(state, challenged.get("detail"))
        return
    breaker = circuit_breaker.check_audit_breaker(state["auditRounds"])
    new_blocking = _blocking(state.get("findings") or [])

    if breaker.get("halt") and breaker.get("reason") == "audit-stall":
        _handle_stall(state, config, breaker)
        return
    if breaker.get("halt"):
        _park_cannot_certify(
            state, "unhandled circuit-breaker halt (%s) — cannot certify"
            % (breaker.get("reason") or "<missing-reason>",))
        return

    # a scoped-finder / new-issue blocking finding OR a not-discharged audit means the round still
    # has work — fix it. #507 v4: the next fix batch is the UNION of the unresolved audit targets and
    # the new blocking findings (deduped by finding identity), so a not-discharged target is NEVER
    # dropped when a new blocker arrives in the same round. Targets carry file/line/severity so the
    # next round's split_fix_surface can re-derive its surface.
    if bool(outcome.get("notDischarged")) or bool(new_blocking):
        nd_raw = outcome.get("notDischarged", [])
        nd_ids = _open_audit_ids_from_not_discharged(nd_raw)
        if nd_ids is None:
            _park_cannot_certify(
                state,
                "malformed _auditOutcome.notDischarged — cannot dispatch fix batch")
            return
        audit_targets = state.get("_auditTargets") or []
        matched_ids = {t.get("id") for t in audit_targets
                       if isinstance(t, dict) and t.get("id") in nd_ids}
        unmatched = sorted(nd_ids - matched_ids)
        if unmatched:
            _park_cannot_certify(
                state,
                "settle-delta — open audit id(s) have no _auditTargets entry (%s); "
                "cannot dispatch fix batch" % ", ".join(unmatched))
            return
        nd_targets = [dict(t) for t in audit_targets
                      if isinstance(t, dict) and t.get("id") in nd_ids]
        batch = _hold_owner_choice(state, _union_open_blockers(new_blocking, nd_targets))
        # Only owner-choice blockers were open: nothing to fix, so the delta settles as a clean one
        # and the convergence chokepoint hands the held findings back open.
        if _queue_fix_batch(state, config, batch) == "empty":
            _settle_delta_converged(state, config)
        return

    if _queue_fix_batch(state, config, []) != "empty":
        return
    _settle_delta_converged(state, config)


def _settle_delta_converged(state, config):
    """Converged candidate tail shared by `_settle_delta` and stall self-recovery when no open work
    remains: the review ends on this round's audit and scoped finder, never on a further panel."""
    _terminal_converged(state, config, full_panel=False)


def _cap_blocks(state, config, next_round, refused_at):
    """The ONE round-cap predicate. Hands the PR back when `next_round` would exceed the cap.

    Bites on the ROUND BOUNDARY: it asks whether the round about to BEGIN is allowed, never
    whether the round just finished was. Returns True when it handed back (caller returns at once)."""
    cap = _round_cap(config)
    # axis: the cap round itself runs; only the round after it is refused — see bite-proof record c1l4_wo_b
    if not next_round > cap:
        return False
    detail = (
        "Round cap %s reached: rounds reached %s, round %s not begun. The PR is handed back with "
        "its findings still open; certification is withheld." % (cap, next_round - 1, next_round)
    )
    if refused_at:
        detail = "%s (refused at: %s)" % (detail, refused_at)
    _hand_back(state, "round-cap", detail, cap=True)
    return True


def _cap_blocks_loaded(state, config):
    """Persisted-state entry guard: a loaded non-terminal state already above its cap must hand back.

    Equality is allowed (`round == cap` runs); hand back only when `round > cap`. A stored
    terminal (including pending idempotent re-emit) is left unchanged. Returns True when it handed back."""
    if state.get("terminal"):
        return False
    cap = _round_cap(config)
    rnd = state["round"]
    if not rnd > cap:
        return False
    # axis: a loaded state sits one past its cap only while the extra audit round it was ordered is the round it holds — see bite-proof record c1l4b_wo_a
    if rnd == cap + 1 and _is_extra_audit_round(state):
        return False
    detail = (
        "Round cap %s reached: round %s had already begun and is halted. The PR is handed back "
        "with its findings still open; certification is withheld. (refused at: resumed-state)"
        % (cap, rnd)
    )
    _hand_back(state, "round-cap", detail, cap=True)
    return True


def _advance_round(state, config, *, reason):
    """The ONE writer of `state["round"]` on the advance path (#1030, owner ruling 19-c).

    The cap is a BOUNDARY, not a settle-path terminal: the round at the cap completes, and the loop
    then refuses to begin the next one. Returns True when the counter advanced, False when it
    handed back `round-cap` — a False return means the caller must return immediately without any
    further state mutation. This function is also the one writer of `state["deltaBaseline"]`."""
    next_round = state["round"] + 1
    if _cap_blocks(state, config, next_round, reason):
        return False
    state["round"] = next_round
    state["deltaBaseline"] = {"round": next_round, "diff": state.get("reviewedDiff")}
    return True


def _is_extra_audit_round(state):
    """True while the session sits in the one extra audit round the advisor ordered at the cap."""
    extra = state.get("extraAudit")
    return (isinstance(extra, dict) and _is_plain_int(extra.get("round"))
            and _is_plain_int(state.get("round")) and extra["round"] == state["round"])


def _begin_extra_audit_round(state, config):
    """The second and last writer of `state["round"]`: the one extra audit round, ordered at the cap.

    `_advance_round` refuses every round past the cap; this begins round `cap + 1` only for the
    `extra-audit` verb, which has put `extraAudit` in the state first. The round audits the cap
    round's fix batch and nothing else: it enters the audit derivation a delta round uses, with no
    post-audit verify, and an unknown surface or a lane that would need a panel hands the PR back
    open (`_hand_back_unknown_fix_surface`, `_reevaluate_lane_dimensions`)."""
    next_round = _round_cap(config) + 1
    state["round"] = next_round
    state["deltaBaseline"] = {"round": next_round, "diff": state.get("reviewedDiff")}
    state["reviewedDiff"] = state.get("headDiff") or state.get("reviewedDiff")
    state.pop("_verifyThen", None)
    state.pop("_postFixEntry", None)
    _enter_delta_round(state, config)
    if state.get("terminal"):
        return
    if state.get("step") == P_AUDITS and not state.get("_auditTargets"):
        _hand_back(state, "extra-audit-open",
                   "the cap round's fix batch yields no audit target, so the extra audit round has "
                   "nothing to audit", cap=True)


def _settle_extra_audit(state, config):
    """The extra audit round's end: its audits folded, and nothing else runs after them.

    No scoped finder, gap sweep, fixer, stall recovery or verify follows. When
    every audit target discharged and the audits raised no new issue, the one convergence chokepoint
    decides; otherwise the PR is handed back open. The terminal settle seeds and settles an audit's
    pending new issues; nothing searches them."""
    outcome = state.get("_auditOutcome") if isinstance(state.get("_auditOutcome"), dict) else {}
    open_ids = _open_audit_ids_from_not_discharged(outcome.get("notDischarged"))
    new_issues = [ni for ni in (state.get("_newIssues") or []) if isinstance(ni, dict)]
    if open_ids is None or open_ids or new_issues:
        parts = []
        if open_ids is None:
            parts.append("the audit outcome is unreadable")
        elif open_ids:
            parts.append("not discharged: %s" % ", ".join(sorted(open_ids)))
        if new_issues:
            parts.append("new issue(s) raised: %s"
                         % "; ".join(str(ni.get("title")) for ni in new_issues))
        _hand_back(state, "extra-audit-open",
                   "The extra audit round left the cap round's fixes open (%s). The PR is handed "
                   "back with its findings still open; certification is withheld." % "; ".join(parts),
                   cap=True)
        return
    pending = _pending_owner_rulings(state)
    # axis: a guidance ruling no fixer ever received keeps the extra round from converging — see bite-proof record c1l4b_wo_g
    if pending:
        _hand_back(state, "extra-audit-open",
                   "The extra audit round ended with owner guidance recorded but never sent to a "
                   "fixer (%s). The PR is handed back with its findings still open; certification "
                   "is withheld." % "; ".join(pending),
                   cap=True)
        return
    _terminal_converged(state, config, full_panel=False)


def _pending_owner_rulings(state):
    """The effective owner fix/guidance rulings no fixer was sent, as readable labels (sorted).
    A ledger read fault reads as none: the terminal settle skips on the same fault."""
    ledger_by_key, fault = _disposition_ledger_by_key(state)
    if fault is not None:
        return []
    effective = _live_ruling_by_key(state)
    found = set()
    for key in effective:
        decision = _undispatched_ruling(state, effective, ledger_by_key, key)
        if decision is not None:
            found.add("%s (%s)" % (decision["seq"], decision["ruling"]))
    return sorted(found)


def _hand_back(state, kind, detail, *, cap):
    """The ONE writer of the `handed-back` verdict: the review ends and the PR goes back to its
    owner with the findings still open. `kind` is the decision kind that names why; `cap` marks a
    stop at a round cap."""
    _set_terminal(state, "handed-back", cap=cap)
    state["certification"] = {"shape": None, "reason": detail}
    _decision(state, kind, detail)
    state["step"] = P_TERMINAL


# The state an earlier generation left when it stopped at an owner gate this version no longer has:
# the judgment gate kept the blockers it put to the owner in `_judgmentFindings`; the stall menu
# kept the choices and the stalled targets it offered in `_stallChoices` and `_stallTargets`.
RETIRED_JUDGMENT_FIELD = "_judgmentFindings"
RETIRED_STALL_FIELDS = ("_stallChoices", "_stallTargets")


# The step an earlier build of this driver dispatched a separate fixer on. A saved state at it is
# moved to `apply-fixes` before any command acts on it (`_migrate_fixer_step`), so it is never
# classified as a retired owner gate.
RETIRED_FIXER_PHASE = "dispatch-fixer"


def _migrate_fixer_step(session_dir, state):
    """Move a saved, unfinished state whose step, or pending action or phase, is the retired fixer
    dispatch to `apply-fixes`, whatever its generation. Returns ``(True, old attempt)`` when it
    moved (the caller persists the state), else ``(False, None)``.

    The pending action is cleared, the step is set, and the step's start head is the head the old
    order was emitted at (the orders anchor's `headSha`), else the current head. The next `next`
    emits `apply-fixes` at a fresh attempt; whatever the old phase left on disk is never read."""
    if not isinstance(state, dict) or state.get("terminal"):
        return False, None
    pending = state.get("pending")
    old = pending if isinstance(pending, dict) else {}
    if RETIRED_FIXER_PHASE not in (state.get("step"), old.get("action"), old.get("phase")):
        return False, None
    attempt = old.get("attempt") if type(old.get("attempt")) is int else None
    rnd = old.get("round") if type(old.get("round")) is int else state.get("round")
    anchor = (_orders_anchor(state, session_dir, rnd, RETIRED_FIXER_PHASE, attempt)
              if attempt is not None else None)
    head = anchor.get("headSha") if isinstance(anchor, dict) else None
    state["pending"] = None
    state["step"] = P_APPLY_FIXES
    state["_fixStepHead"] = head if _nonempty_str(head) else _fix_step_head(state.get("config"))
    state.pop("_escalatedRung", None)
    return True, attempt


def _step_is_retired(state):
    """True when the state's step, or the action and phase it has pending, is not one of
    `round_phases.ALL_PHASES`. Only a session of an earlier generation can hold one."""
    held = [state.get("step")]
    pending = state.get("pending")
    if isinstance(pending, dict):
        held += [pending.get("action"), pending.get("phase")]
    return any(name not in round_phases.ALL_PHASES for name in held)


def _finish_retired_gate_step(state):
    """Hand back a session of a continuable earlier generation that was waiting at an owner gate
    this version no longer has. Returns True when it did; the caller persists the state.

    A retired step is told by its name not being in `round_phases.ALL_PHASES`. Which gate it was is
    told by the state it left: held judgment findings mean the judgment gate (`owner-choice-open`,
    each held finding joining `ownerChoiceHeld`); otherwise a stall menu's fields mean the stall
    menu (`fix-keeps-failing`); anything else is handed back as `fix-keeps-failing` with the detail
    saying the step could not be classified. The pending gate action is cleared, so nothing emits
    it, and `_hand_back` ends the review with every finding given an outcome. A finished state, and a
    state of any other generation, are left as they are."""
    if (not isinstance(state, dict) or state.get("terminal")
            or not _generation_is_continuable_earlier(state)):
        return False
    # axis: a step outside ALL_PHASES hands the session back before any command acts on it — see bite-proof record c1l4b_wo_b
    if not _step_is_retired(state):
        return False
    state["pending"] = None
    held = state.get(RETIRED_JUDGMENT_FIELD)
    judgment = [f for f in (held if isinstance(held, list) else []) if isinstance(f, dict)]
    stalled = any(name in state for name in RETIRED_STALL_FIELDS)
    # axis: the judgment gate and the stall menu hand back under different decision kinds — see bite-proof record c1l4b_wo_b
    if judgment:
        keys = state.get("ownerChoiceHeld")
        if not isinstance(keys, list):
            keys = state["ownerChoiceHeld"] = []
        for finding in judgment:
            key = _finding_key_of(finding)
            if key and key not in keys:
                keys.append(key)
        _hand_back(state, "owner-choice-open",
                   "%d finding(s) need the owner's choice and are still open: %s. The review was "
                   "waiting at a judgment gate this version no longer has, so the PR is handed back "
                   "with its findings still open; certification is withheld."
                   % (len(judgment), "; ".join(str(f.get("title") or "?") for f in judgment)),
                   cap=False)
    elif stalled:
        _hand_back(state, "fix-keeps-failing",
                   "The review was waiting at a stall menu this version no longer has, after an "
                   "audit stall persisted past its recovery attempt. The PR is handed back with its "
                   "findings still open; certification is withheld.", cap=False)
    else:
        _hand_back(state, "fix-keeps-failing",
                   "The review was waiting at a step this version no longer has (%r), and it could "
                   "not be classified. The PR is handed back with its findings still open; "
                   "certification is withheld." % (state.get("step"),), cap=False)
    return True


# The `_verifyThen` flag an earlier build of this driver set on the verify gate that was to be followed
# by a full panel in a later round.
RETIRED_VERIFY_THEN_PANEL = "full-panel"


def _finish_retired_later_panel(state):
    """Hand back a saved, unfinished session of any generation the driver continues that was waiting at a
    panel in round 2 or later, or at the verify gate that was to be followed by one. Later rounds run no
    panel, so nothing may emit or fold it. Returns True when it handed back; the caller persists the state.

    The step, or the action or phase the state has pending, names the panel; the pending action is
    cleared and `_hand_back` ends the review with every finding given an outcome. A finished state, and
    a round-1 panel, are left as they are."""
    if not isinstance(state, dict) or state.get("terminal"):
        return False
    pending = state.get("pending")
    held = [state.get("step")]
    if isinstance(pending, dict):
        held += [pending.get("action"), pending.get("phase")]
    rnd = state.get("round")
    at_panel = P_PANEL in held and _is_plain_int(rnd) and rnd >= 2
    at_gate = state.get("_verifyThen") == RETIRED_VERIFY_THEN_PANEL
    if not (at_panel or at_gate):
        return False
    state["pending"] = None
    state.pop("_verifyThen", None)
    where = ("a full panel in round %s" % rnd if at_panel
             else "the verify gate that was to be followed by a full panel")
    _hand_back(state, "later-round-panel-retired",
               "The review was waiting at %s, which this version no longer runs: every round after "
               "the first checks only the fixes. The PR is handed back with its findings still open; "
               "certification is withheld." % where, cap=False)
    return True


# Stall self-recovery fix-batch refusal tokens — shared by composition and routing (#1107).
REFUSAL_UNRESOLVABLE_OPEN_SET = "unresolvable-open-set"
REFUSAL_OPEN_TARGET_UNREPRESENTABLE = "open-target-unrepresentable"
REFUSAL_OPEN_BLOCKING_UNCOMPOSABLE = "open-blocking-uncomposable"


class _OpenAuditTargets:
    """Tri-state open-audit-target resolution for stall self-recovery (#1107)."""

    __slots__ = ("kind", "ids")

    def __init__(self, kind, ids=None):
        self.kind = kind  # "resolved", "empty", or "unresolvable"
        self.ids = ids


def _open_audit_ids_from_not_discharged(not_discharged):
    """Validated boundary: _auditOutcome.notDischarged list → open-id set (#1107).

    Returns a set of str ids when every member is a usable id; None when unresolvable."""
    if not isinstance(not_discharged, list):
        return None
    for member in not_discharged:
        if not isinstance(member, str):
            return None
    return set(not_discharged)


def _resolve_open_audit_targets(state):
    """Report whether the per-location open-id set is resolved, genuinely empty, or unresolvable."""
    outcome = state.get("_auditOutcome")
    if isinstance(outcome, dict):
        nd = outcome.get("notDischarged")
        if isinstance(nd, list):
            ids = _open_audit_ids_from_not_discharged(nd)
            if ids is not None:
                return _OpenAuditTargets("resolved", ids)
            return _OpenAuditTargets("unresolvable")
    audit_targets = state.get("_auditTargets") or []
    audit_rounds = state.get("auditRounds") or []
    fix_batch = state.get("fixBatch") or []
    if not audit_targets and not audit_rounds and not fix_batch:
        return _OpenAuditTargets("empty")
    return _OpenAuditTargets("unresolvable")


def _stalled_open_targets(state, breaker):
    """Targets that are both stalled (alias match) and still open this round — the selection rule
    for stall self-recovery."""
    stalled = set(breaker.get("stalledIdentities") or [])
    if not stalled:
        return []
    open_set = _resolve_open_audit_targets(state)
    if open_set.kind == "empty":
        return []
    matched = []
    if open_set.kind == "resolved":
        open_ids = open_set.ids
        for t in state.get("_auditTargets") or []:
            if not isinstance(t, dict):
                continue
            if t.get("id") not in open_ids:
                continue
            if circuit_breaker.audit_target_aliases(t) & stalled:
                matched.append(t)
        return matched
    # Legacy: persisted session without per-location ids. Keys on the line-less identity DIRECTLY —
    # NOT circuit_breaker aliases, whose fail-closed direction is the opposite one (an empty alias
    # set must stay empty there so a malformed audit outcome is marked, not matched).
    for f in state.get("fixBatch") or []:
        if isinstance(f, dict) and finding_identity(f) in stalled:
            matched.append(f)
    return matched


# ---- stall self-recovery + menu -------------------------------------------------------------

def _commit_stall_self_recovery(state, config, breaker):
    """One-shot guard + record — single owner for both (#1107)."""
    state["selfRecovered"] = True
    _decision(state, "self-recovery", "audit-stall — one invisible self-recovery")
    _record_round(state, "selfRecovery", {"reason": breaker.get("detail")})


def _union_open_blockers(*groups):
    """Union open blockers into one fix batch — deduped by the leaf's identity key.

    First-wins: an admitted entry is never replaced, removed, or downgraded by a later group.
    ``_settle_delta`` passes id-less ``new_blocking`` before id-bearing ``nd_targets``; that
    ordering depends on first-wins."""
    batch = []
    seen_keys = set()
    for group in groups:
        for item in group:
            f = dict(item)
            key = session_contract.finding_identity_key(f)
            if key is None:
                continue
            if key in seen_keys:
                continue
            batch.append(f)
            seen_keys.add(key)
    return batch


def _compose_stall_fix_batch(state, breaker):
    """Compose the stall self-recovery fix batch and any refusal token (#1107).

    #1165 (option c): on audit stall, self-recovery dispatches the union of stalled
    alias-matching targets and not-discharged audit targets — never new blocking
    findings — or returns a refusal token (no partial batch).
    """
    stalled = [dict(t) for t in _stalled_open_targets(state, breaker)]
    outcome = state.get("_auditOutcome") if isinstance(state.get("_auditOutcome"), dict) else {}
    if "notDischarged" in outcome:
        nd_raw = outcome.get("notDischarged")
        if _open_audit_ids_from_not_discharged(nd_raw) is None:
            return [], REFUSAL_UNRESOLVABLE_OPEN_SET
        nd_ids = _open_audit_ids_from_not_discharged(nd_raw)
    else:
        nd_ids = None
    open_set = _resolve_open_audit_targets(state)
    if open_set.kind == "unresolvable" and not stalled:
        return [], REFUSAL_UNRESOLVABLE_OPEN_SET
    if nd_ids is not None:
        nd_targets = [dict(t) for t in (state.get("_auditTargets") or [])
                      if isinstance(t, dict) and t.get("id") in nd_ids]
        matched_ids = {t.get("id") for t in nd_targets}
        if nd_ids - matched_ids:
            return [], REFUSAL_OPEN_TARGET_UNREPRESENTABLE
    else:
        nd_targets = []
    if stalled:
        batch = _union_open_blockers(stalled, nd_targets)
        return batch, None
    batch = []
    new_blocking = _blocking(state.get("findings") or [])
    nd_members = nd_ids if nd_ids is not None else set()
    if nd_members or new_blocking:
        batch = _union_open_blockers(new_blocking, nd_targets)
        if not batch:
            return [], REFUSAL_OPEN_BLOCKING_UNCOMPOSABLE
    return batch, None


def _route_stall_self_recovery(state, config, batch, refusal, breaker):
    """Terminal routing for stall self-recovery — exhaustive over batch/refusal (#1107)."""
    if batch:
        if _queue_fix_batch(state, config, _hold_owner_choice(state, batch)) == "empty":
            _settle_delta_converged(state, config)
    elif refusal == REFUSAL_UNRESOLVABLE_OPEN_SET:
        _park_cannot_certify(
            state,
            "audit-stall self-recovery — open audit target set unresolvable "
            "(missing or malformed _auditOutcome); cannot dispatch fix batch")
    elif refusal == REFUSAL_OPEN_TARGET_UNREPRESENTABLE:
        outcome = state.get("_auditOutcome") if isinstance(state.get("_auditOutcome"), dict) else {}
        nd_raw = outcome.get("notDischarged")
        nd_ids = _open_audit_ids_from_not_discharged(nd_raw) if isinstance(nd_raw, list) else None
        if nd_ids is not None:
            matched = {t.get("id") for t in (state.get("_auditTargets") or [])
                       if isinstance(t, dict)}
            unmatched = sorted(nd_ids - matched)
        else:
            unmatched = []
        _park_cannot_certify(
            state,
            "audit-stall self-recovery — open audit target id(s) %s have no matching "
            "_auditTargets entry; cannot compose a complete fix batch" % unmatched)
    elif refusal == REFUSAL_OPEN_BLOCKING_UNCOMPOSABLE:
        _hand_back(
            state, "fix-keeps-failing",
            (breaker.get("detail") or "audit-stall self-recovery")
            + " — blocking finding(s) remain not-discharged; certification withheld", cap=False)
    else:
        open_set = _resolve_open_audit_targets(state)
        # Empty resolution: no audit has ever produced targets in this session, so there is
        # nothing to audit. Resolved/unresolvable paths settle through _settle_delta_converged.
        # Certification shape is carried from state["fullPanelRan"], never asserted here: this
        # branch cannot manufacture a full-panel claim (pinned by
        # test_empty_resolution_converge_never_claims_an_unrun_panel).
        if open_set.kind == "empty":
            _terminal_converged(state, config, full_panel=state.get("fullPanelRan"))
        else:
            _settle_delta_converged(state, config)


def _handle_stall(state, config, breaker):
    """audit-stall → ONE invisible self-recovery (the build session applies a recomposed fix batch,
    once, journaled). Still stalled → the PR is
    handed back (`fix-keeps-failing`); nothing is put to the owner mid-review. A stall found in the
    cap round runs no recovery: a recovered fix would be audited in a round the cap refuses, so the
    PR is handed back `round-cap` at once, with no fix leg."""
    # axis: a stall in the cap round hands back without a recovery attempt — see bite-proof record c1l4_wo_b
    if state["round"] >= _round_cap(config):
        _hand_back(state, "round-cap",
                   breaker.get("detail") or "audit-stall in the cap round", cap=True)
        return
    if not state.get("selfRecovered"):
        _commit_stall_self_recovery(state, config, breaker)
        batch, refusal = _compose_stall_fix_batch(state, breaker)
        _route_stall_self_recovery(state, config, batch, refusal, breaker)
        return
    _hand_back(state, "fix-keeps-failing",
               breaker.get("detail") or "audit-stall persists after self-recovery", cap=False)


# ---- terminal certification -----------------------------------------------------------------

def _break_it_ruled_exempt(state, key):
    """The ``rule``-verb out-of-scope ruling row that exempts a break-it finding's test from the kept
    check, or None. Exempt only when the finding's effective decision is that attributed ruling AND
    some round's recorded audit cleared the finding; either leg alone leaves the check owed."""
    ledger_by_key, _fault = _disposition_ledger_by_key(state)
    # merge-aware: a newer guidance/fix ruling given to a finding merged into this one binds it, as it does the fixer
    live = _row_decision(state, _live_ruling_by_key(state), ledger_by_key, key)
    # axis: only an out-of-scope ruling from the rule verb exempts — a fixed finding with no ruling still owes the kept check — see bite-proof record wo_a_2072_ruled_exempt
    if not (isinstance(live, dict) and live.get("ruling") == "out-of-scope"
            and live.get("source") == "rule"):
        return None
    prov = live.get("provenance")
    # axis: an unattributed ruling exempts nothing — ruledBy and ruledAt must both be non-empty strings — see bite-proof record wo_a_2072_ruled_exempt
    if not (isinstance(prov, dict)
            and all(isinstance(prov.get(f), str) and prov[f].strip() for f in ("ruledBy", "ruledAt"))):
        return None
    rounds = state.get("rounds")
    for rec in (rounds.values() if isinstance(rounds, dict) else ()):
        entries = rec.get("audits") if isinstance(rec, dict) else None
        for audit in (entries if isinstance(entries, list) else ()):
            # axis: a ruling with no clearing audit exempts nothing — the test must still be kept — see bite-proof record wo_a_2072_ruled_exempt
            if isinstance(audit, dict) and audit.get("id") == key and audit.get("ruling") in audits._CLEARS:
                return live
    return None


def _break_it_kept_step(state, config):
    """Before certifying: each fixed break-it finding's test must be a regular tracked file in the
    final diff with the exact bytes the loop ran, and pass at the final head. Returns True when it
    parked (certification withheld). A finding ruled out of scope and cleared by the audit owes no
    check; a finding with any other disposition besides fixed or out-of-scope owes none either."""
    for rkey in sorted(state.get("rounds") or {}, key=lambda k: int(k) if str(k).isdigit() else 0):
        for run in (state["rounds"][rkey].get("breakItRuns") or []):
            # axis: a per-area (or kind-less) break-it run that compile dropped and that did not pass withholds certification; an attached test's dropped run stays recorded and parks nothing, as its dropped finding would without a test
            if (isinstance(run, dict) and run.get("droppedAtCompile") is True
                    and run.get("outcome") != break_it.OUTCOME_PASSED
                    and run.get("kind") != break_it.KIND_ATTACHED):
                _park_cannot_certify(
                    state, "break-it run dropped at compile: %s (%s)"
                    % (run.get("path"), run.get("outcome")))
                return True
            # axis: a break-it run whose working-copy restore failed withholds certification whatever the finding's disposition and whatever later run replaced it, because the session's repository may be left altered
            if isinstance(run, dict) and run.get("reason") == "working-copy-restore-failed":
                _park_cannot_certify(
                    state, "break-it working copy not restored: %s (%s)"
                    % (run.get("path"), str(run.get("output") or "")[-200:]))
                return True
    latest = {}
    for rkey in sorted(state.get("rounds") or {}, key=lambda k: int(k) if str(k).isdigit() else 0):
        for run in (state["rounds"][rkey].get("breakItRuns") or []):
            # axis: the latest run per finding key wins, passed ones included, by round order and then list order, so a changed test's run is the one checked
            if isinstance(run, dict) and isinstance(run.get("findingKey"), str) and run.get("findingKey"):
                latest[run["findingKey"]] = run
    if not latest:
        return False
    _, by_key, fault = _fixed_ledger_rows(state)
    if fault is not None:
        _park_cannot_certify(state, "break-it test not kept: disposition ledger fault (%s)" % fault)
        return True
    head = config.get(FIX_FOLD_HEAD_KEY) or config.get("headSha")
    rows, failed = [], []
    for key, run in latest.items():
        entry = by_key.get(key)
        disposition = entry.get("disposition") if isinstance(entry, dict) else None
        if disposition is None:
            # axis: an absent disposition is unresolved, never a waiver — retention is not checked, so certification is withheld
            row = {"findingKey": key, "path": run.get("path"), "outcome": "unresolved",
                   "reason": "no-disposition", "run": None}
            rows.append(row)
            failed.append(row)
            continue
        # axis: an out-of-scope disposition owes the kept check like a fixed one unless the exemption holds, never a bare not-required — see bite-proof record wo_a_2072_ruled_exempt
        if disposition not in ("fixed", "out-of-scope"):
            rows.append({"findingKey": key, "path": run.get("path"), "outcome": "not-required",
                         "reason": disposition})
            continue
        # axis: the exemption is consulted before the kept check; without it a ruled-out-of-scope test parks — see bite-proof record wo_a_2072_ruled_exempt
        ruled = _break_it_ruled_exempt(state, key)
        if ruled is not None:
            rows.append({"findingKey": key, "path": run.get("path"), "outcome": "ruled-out-of-scope",
                         "reason": ruled.get("reason"), "ruledBy": ruled["provenance"]["ruledBy"],
                         "ruledAt": ruled["provenance"]["ruledAt"]})
            continue
        got = break_it.check_kept(config.get("repoRoot"), config.get("baseRef"), head, run,
                                  interpreter=break_it.resolve_interpreter(config))
        row = {"findingKey": key, "path": got.get("path"), "outcome": got.get("outcome"),
               "reason": got.get("reason"), "run": got.get("run")}
        rows.append(row)
        # axis: a fixed break-it finding whose test is not kept parks, it never certifies
        if got.get("outcome") != break_it.KEPT:
            failed.append(row)
    _record_round(state, "breakItKept", rows)
    unchecked = sum(1 for r in rows if r["outcome"] == "not-required")
    ruled_out = sum(1 for r in rows if r["outcome"] == "ruled-out-of-scope")
    _decision(state, "break-it-kept",
              "%d checked: %d kept, %d not kept, %d not required, %d ruled out of scope"
              % (len(rows) - unchecked - ruled_out,
                 sum(1 for r in rows if r["outcome"] == break_it.KEPT), len(failed),
                 unchecked, ruled_out))
    if failed:
        why = failed[0]["reason"] or (failed[0].get("run") or {}).get("output")
        _park_cannot_certify(
            state, "break-it test not kept: %s (%s%s)"
            % (failed[0]["path"], failed[0]["outcome"], ": %s" % str(why)[-200:] if why else ""))
        return True
    return False


def _terminal_converged(state, config, full_panel, note=None):
    """Certify: last round's fixes all discharged + verify pass. Shape is full-panel-confirmed (a
    round-1 panel converged with no fixes) or audited-chain (a review that needed fixes ends on a
    round's audit and scoped finder, with no final panel — say so). Degraded independence appends
    -degraded.

    A converge over ANY owner-skipped judgment blocker (one an earlier version recorded) is CLEAN
    EXCEPT FOR SKIPPED — never a plain success (the exit_skipped invariant): the certification
    `reason` leads with `clean-except-skipped: N blocker(s) skipped with citable reasons` (shape
    unchanged) so the terminal reads unmistakably non-plain, and the skips also ride the top-level
    receipt channel.

    This is the ONE convergence chokepoint (round 1, delta rounds, the recovery tail all route
    here), so it is also where a finding held for the owner's choice stops a converge: while any
    held finding is unsettled the PR is handed back open instead."""
    # axis: no path converges over a finding held for the owner's choice — see bite-proof record c1l4_wo_a
    unsettled = _unsettled_owner_choices(state)
    if unsettled:
        _hand_back(state, "owner-choice-open",
                   "%d finding(s) need the owner's choice and are still open: %s"
                   % (len(unsettled), "; ".join(title for _key, title in unsettled)), cap=False)
        return
    # An OUTSTANDING incomplete panel (a configured lens never ran, never recovered by a later
    # complete panel) cannot certify clean — a zero-finding finish over a coverage gap is "we did not
    # look", not "audited-chain". Silence never certifies: withhold + park (#507 R2 residual-1).
    if state.get("_incompletePanel"):
        _park_cannot_certify(
            state, "panel incomplete — a configured lens never ran and no complete panel has since "
            "recovered the coverage; certification withheld")
        return
    # axis: the converge gate calls the kept check; without it a dropped break-it test certifies
    if _break_it_kept_step(state, config):
        return
    base = "full-panel-confirmed" if full_panel else "audited-chain"
    shape = _cert_shape(state, base)
    shape_drivers = []
    if _degraded(state):
        shape_drivers.append("independence")
    if _base_degraded(state):
        shape_drivers.append("base")
    if _same_family_degraded(state):
        shape_drivers.append("same-family")
    if _seat_pin_excused(state):
        shape_drivers.append("seat-pin")
    # bite-axis: absent seat map names shapeDrivers — projection 2 of 3 (#681).
    if _seat_map_unavailable(state) or _seat_map_unjudgeable(state):
        shape_drivers.append("seat-map-unavailable")
    if _seat_map_violated(state):
        shape_drivers.append("seat-map-violation")
    if _seat_map_unproven_liveness(state):
        shape_drivers.append("unproven-liveness")
    _set_terminal(state, "converged")
    cert = {"shape": shape, "fullPanel": bool(full_panel),
            "independence": "degraded" if _degraded(state) else "independent",
            "base": _certification_base(state),
            "shapeDrivers": sorted(shape_drivers)}
    if note:
        cert["note"] = note
    skipped = state.get("_skippedBlockers") or []
    if skipped:
        cert["reason"] = ("clean-except-skipped: %d blocker(s) skipped with citable reasons"
                          % len(skipped))
    state["certification"] = cert
    _decision(state, "converged", "certified as %s" % shape)
    state["step"] = P_TERMINAL


# =============================================================================================
# the driver receipt + its validator
# =============================================================================================

def build_receipt(state, session_dir=None, form=RECEIPT_FORM_CERTIFIED):
    """The terminal driver receipt. Per-round schedule (planned vs executed), every finding's
    outcome, the decision ledger, the seat map, the scriptRan summary from the journal, and the
    degraded disclosures. Written to round-receipt.json at the terminal.

    RECEIPT WRITE-ORDER INVARIANT — by construction, not by call-site care: every write the
    terminal receipt must reflect is visible to this builder at build time. The receipt is
    write-once, so receipt-relevant state must be committed inside the fold transition
    (``cmd_submit``'s ``_fold`` and its immediate post-fold staging), never by a post-fold
    caller."""
    rounds = []
    for key in sorted(state.get("rounds") or {}, key=lambda k: int(k) if str(k).isdigit() else 0):
        rec = state["rounds"][key]
        rd = {"round": int(key) if str(key).isdigit() else key,
              "kind": rec.get("roundKind"),
              "seatStatus": rec.get("seatStatus"),
              "blockingCount": rec.get("blockingCount"),
              "verifyResult": rec.get("verifyResult"),
              "audits": rec.get("audits"),
              # The manifest-keyed audit-provenance boundary (LEDGERS §3): a round that ran
              # fix audits records `collection-manifest` here so the boundary — attestation,
              # not cryptographic executor identity — is visible at vet, matching the ledger.
              "auditProvenance": rec.get("auditProvenance"),
              "scopedFinder": rec.get("scopedFinder"),
              "headDiffSource": rec.get("headDiffSource"),
              "headDiffCheck": rec.get("headDiffCheck"),
              "rulings": rec.get("rulings"),
              "unverified": rec.get("unverified"),
              "authorJustifiedDrops": rec.get("authorJustifiedDrops"),
              "compileDrops": rec.get("compileDrops"),
              "selfRecovery": rec.get("selfRecovery"),
              "stallChoice": rec.get("stallChoice")}
        if rec.get("lensCoverage") is not None:
            rd["lensCoverage"] = rec.get("lensCoverage")
        # Fossil-channel census requires a literal per-channel round-record read — not a variable
        # key through the generic loop — so this channel is consumed here (form-gated, always-emit).
        # Bite axis (#1177-A): every emitted round entry on a form permitting the channel carries
        # verifyPasses as a list, empty when the round recorded none; absence is impossible.
        # Bite-proof: WO 1177-A — always-emit rule and v2 form gate; durable build record.
        if _round_entry_key_allowed("verifyPasses", form, state):
            verify_passes = rec.get("verifyPasses")
            rd["verifyPasses"] = verify_passes if isinstance(verify_passes, list) else []
        # The per-round disclosure channels ride their ONE home (#720) — the same set the records
        # writer persists. `_receipt_round_disclosures` applies the shared selection rule
        # (`_declared_disclosures` narrowed by the form gate) — same as the producer.
        # `verifyPasses` emits above (form-gated, always-emit when permitted).
        disclosures = _receipt_round_disclosures(rec, form, state)
        for chan in CARRIED_DISCLOSURE_CHANNELS:
            if chan == "verifyPasses":
                continue
            if chan in disclosures:
                rd[chan] = disclosures[chan]
        rounds.append(rd)
    findings = []
    for f in (state.get("findings") or []):
        if not isinstance(f, dict):
            continue
        row = {"id": f.get("id"), "file": f.get("file"), "line": f.get("line"),
               "title": f.get("title"), "severity": f.get("severity"),
               "verdict": f.get("verdict"), "challenge": f.get("challenge"),
               "unverified": f.get("unverified")}
        if (_state_version(state) or 0) >= STATE_SCHEMA_VERSION:
            finding_key = f.get(session_contract.FINDING_KEY_FIELD)
            if isinstance(finding_key, str) and finding_key:
                row[session_contract.FINDING_KEY_FIELD] = finding_key
        findings.append(row)
    cfg = state.get("config") or {}
    journal = read_journal(session_dir) if session_dir else None
    degraded, skipped_blockers = build_degraded_prose(state, form, journal=journal)
    scriptran = _scriptran_summary(session_dir) if session_dir else state.get("_scriptRan") or \
        {"invocations": 0, "byPhase": {}}
    base = {k: cfg.get(k) for k in ("baseRef", "baseBranch", "baseFetch", "baseRepo",
                                    "baseRepoCheck", "repoRoot", "diffBinding")
            if cfg.get(k) is not None}
    # "mode" is deliberately NOT part of the generic cfg-echo tuple above (#1107 WO-rc1): under
    # meta-wins precedence, the driver config's raw mode value is not necessarily the mode the
    # driver actually resolved and acted on — a receipt echoing it raw would be a false receipt.
    # Route it through the same session_mode.resolve the driver used elsewhere, and record it only
    # when the resolution is GROUNDED (never the UNRESOLVED_MODE default — that fail-closed "pr"
    # was never chosen by anything, so the receipt must not claim it was).
    _meta_for_mode = _session_meta(session_dir) if session_dir else {}
    _mode_resolved = session_mode.resolve(_meta_for_mode, cfg)
    if _mode_resolved["resolved"]:
        base["mode"] = _mode_resolved["mode"]
    receipt = {
        # The STATE's version drives the receipt's (#723): an in-flight v2 session still emits
        # today's `receipt-certified/2` shape, unchanged and with no added key.
        "schemaVersion": _receipt_version(state),
        "verdict": state.get("terminal"),
        "certificationShape": (state.get("certification") or {}).get("shape"),
        "certification": state.get("certification"),
        "rounds": rounds,
        "findings": findings,
        "decisions": list(state.get("decisions") or []),
        "seatMap": _emit_receipt_seat_map(state, _driver_author_family(state)),
        "scriptRan": scriptran,
        "degraded": degraded,
        "skippedBlockers": skipped_blockers,
        "baseGuard": cfg.get("baseGuard")
        if cfg.get("baseGuard") == BASE_GUARD_CHECKED
        else "not-checked",
    }
    if base:
        receipt["base"] = base
    policy_applied = state.get("_policyApplied")
    if isinstance(policy_applied, list) and policy_applied:
        receipt["policyApplied"] = list(policy_applied)
    return receipt


def build_interim_receipt(state, session_dir, stop_reason):
    """An interim driver receipt at a non-terminal stop — per-pass verdict totals without certification."""
    receipt = build_receipt(state, session_dir, form=RECEIPT_FORM_INTERIM)
    for key in _receipt_forbidden_keys(RECEIPT_FORM_INTERIM):
        receipt.pop(key, None)
    receipt["schema"] = RECEIPT_INTERIM_SCHEMA
    receipt["stop"] = {
        "reason": stop_reason,
        "writtenAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    return receipt


def _read_on_disk_receipt(session_dir):
    path = os.path.join(session_dir, RECEIPT_FILE)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _on_disk_receipt_class(session_dir):
    """Classify the on-disk receipt for overwrite policy.

    Returns ``absent``, ``interim``, ``terminal``, or ``untrusted`` (unreadable, unparseable, or
    unknown schema). Only ``interim`` and ``absent`` permit a new write."""
    path = os.path.join(session_dir, RECEIPT_FILE)
    if not os.path.exists(path):
        return "absent"
    receipt = _read_on_disk_receipt(session_dir)
    if receipt is None:
        return "untrusted"
    kind = receipt_kind(receipt)
    if kind is None:
        return "untrusted"
    ok, _reason = validate_receipt(receipt)
    if not ok:
        return "untrusted"
    if kind == RECEIPT_INTERIM_SCHEMA:
        return "interim"
    return "terminal"


def _receipt_write_refusal(session_dir, *, terminal_reason, untrusted_reason):
    """Refusal token when an on-disk receipt blocks overwrite, else None."""
    cls = _on_disk_receipt_class(session_dir)
    if cls == "terminal":
        return terminal_reason
    if cls == "untrusted":
        return untrusted_reason
    return None


def _terminal_receipt_on_disk(session_dir):
    """True when a certified or attested receipt sits at the terminal path (not an interim)."""
    return _on_disk_receipt_class(session_dir) == "terminal"


def _receipt_requires_round_verify_passes(receipt):
    """Whether round entries must carry verifyPasses (certified v3+, attested, interim only).

    Decodes ``ROUND_ENTRY_KEY_FORMS`` only through ``_round_entry_key_declared`` — the shared
    home with the live-state form gate (#1194 FU8); this function owns only the persisted-receipt
    identification (kind and version extraction), never the declaration's semantics."""
    if "verifyPasses" not in ROUND_ENTRY_KEY_FORMS:
        return True
    kind = receipt_kind(receipt)
    if kind is None:
        return False
    if _round_entry_key_declared("verifyPasses", kind, None):
        return True
    version = receipt.get("schemaVersion")
    if isinstance(version, bool) or not isinstance(version, int):
        return False
    if kind != RECEIPT_CERTIFIED_SCHEMA % version:
        return False
    return _round_entry_key_declared("verifyPasses", None, version)


def _validate_round_entries_verify_passes(receipt):
    """Every round entry on forms that permit the channel must carry verifyPasses as a list.

    Bite axis (#1177-A): a receipt on an applicable form whose round entry is missing
    ``verifyPasses``, or carries a non-list, is refused.
    Bite-proof: WO 1177-A — missing-channel refusal and malformed-channel refusal; durable build
    record."""
    if not _receipt_requires_round_verify_passes(receipt):
        return True, None
    for idx, rd in enumerate(receipt.get("rounds") or []):
        if not isinstance(rd, dict):
            return False, "round entry %s is not an object" % idx
        rnd = rd.get("round", idx)
        if "verifyPasses" not in rd:
            return False, (
                "round %s missing verifyPasses — receipt likely written before this requirement "
                "shipped; re-run the review rather than trusting the stale receipt" % rnd)
        if not isinstance(rd.get("verifyPasses"), list):
            return False, "round %s verifyPasses must be a list" % rnd
    return True, None


def validate_receipt(receipt):
    """Validate a driver receipt's SHAPE — version-dispatched since #723.

    Two shapes are valid and they are structurally UN-CONFUSABLE, which is the point: a CERTIFIED
    receipt (``RECEIPT_CERTIFIED_SCHEMA % <v>`` for a supported ``v``) carries its
    ``certification`` block and an allowlisted
    verdict; an ATTESTED receipt (`receipt-attested/1`, written by `attest`) carries an
    `attestation` block, the `uncertified-manual` verdict, and NO certification block at all. A
    reader can therefore never mistake a hand attestation for a certification, and a certified
    receipt can never smuggle in an attestation instead of a certification.

    Returns (ok, reason)."""
    if not isinstance(receipt, dict):
        return False, "receipt is not an object"
    if receipt.get("schema") == RECEIPT_ATTESTED_SCHEMA:
        return _validate_attested_receipt(receipt)
    if receipt.get("schema") == RECEIPT_INTERIM_SCHEMA:
        return _validate_interim_receipt(receipt)
    return _validate_certified_receipt(receipt)


def _validate_attested_receipt(receipt):
    """The `receipt-attested/1` shape: `attestation` REQUIRED, `certification` FORBIDDEN, verdict
    pinned to `uncertified-manual`. A certification block here would be exactly the confusion the
    split exists to prevent (an attested receipt reading as a certified one)."""
    for key in _receipt_required_keys(RECEIPT_FORM_ATTESTED):
        if key not in receipt:
            return False, "attested receipt missing required key %r" % key
    for key in _receipt_forbidden_keys(RECEIPT_FORM_ATTESTED):
        if key in receipt:
            return False, ("attested receipt must not carry %r — an attestation is NOT a "
                           "certification" % key)
    if receipt.get("verdict") != ATTESTED_VERDICT:
        return False, "attested receipt verdict must be %r" % ATTESTED_VERDICT
    if not isinstance(receipt.get("attestation"), dict):
        return False, "attested receipt attestation must be an object"
    if not isinstance(receipt.get("scriptRan"), dict):
        return False, "receipt scriptRan must be an object (the journal-derived evidence)"
    if "byPhase" not in receipt["scriptRan"]:
        return False, "receipt scriptRan must carry byPhase (the per-phase journal counts)"
    if not isinstance(receipt.get("seatMap"), dict):
        return False, "receipt seatMap must be an object"
    if not isinstance(receipt.get("artifacts"), dict):
        return False, "attested receipt artifacts must be an object (path -> sha256)"
    if not receipt.get("artifacts"):
        return False, "attested receipt artifacts must not be empty"
    if not isinstance(receipt.get("roster"), dict):
        return False, "attested receipt roster must be an object (seat -> disposition)"
    for key in ("rounds", "findings", "decisions", "degraded", "skippedBlockers"):
        if not isinstance(receipt.get(key), list):
            return False, "receipt %s must be a list" % key
    ok, reason = _validate_round_entries_verify_passes(receipt)
    if not ok:
        return ok, reason
    return True, None


def _validate_interim_receipt(receipt):
    """The `receipt-interim/1` shape: a `stop` block REQUIRED, `certification` FORBIDDEN — an interim
    is not a certification and must not be read as terminal evidence."""
    for key in _receipt_required_keys(RECEIPT_FORM_INTERIM):
        if key not in receipt:
            return False, "interim receipt missing required key %r" % key
    for key in _receipt_forbidden_keys(RECEIPT_FORM_INTERIM):
        if key in receipt:
            return False, ("interim receipt must not carry %r — an interim is NOT a certification"
                           % key)
    if receipt.get("schema") != RECEIPT_INTERIM_SCHEMA:
        return False, "interim receipt schema must be %r" % RECEIPT_INTERIM_SCHEMA
    stop = receipt.get("stop")
    if not isinstance(stop, dict):
        return False, "interim receipt stop must be an object"
    reason = stop.get("reason")
    if reason not in CHECKPOINT_STOP_REASONS:
        return False, ("interim receipt stop reason %r is not one of: %s"
                       % (reason, ", ".join(CHECKPOINT_STOP_REASONS)))
    if not isinstance(stop.get("writtenAt"), str) or not stop.get("writtenAt"):
        return False, "interim receipt stop must carry writtenAt"
    if not isinstance(receipt.get("scriptRan"), dict):
        return False, "receipt scriptRan must be an object (the journal-derived evidence)"
    if "byPhase" not in receipt["scriptRan"]:
        return False, "receipt scriptRan must carry byPhase (the per-phase journal counts)"
    if not isinstance(receipt.get("seatMap"), dict):
        return False, "receipt seatMap must be an object"
    for key in ("rounds", "findings", "decisions", "degraded", "skippedBlockers"):
        if not isinstance(receipt.get(key), list):
            return False, "receipt %s must be a list" % key
    ok, reason = _validate_round_entries_verify_passes(receipt)
    if not ok:
        return ok, reason
    return True, None


def _validate_rounds_lens_coverage(receipt):
    """Per-round lensCoverage shape/consistency and convergence-anchor guard (#960).

    Returns (ok, reason). Legacy receipts with no lensCoverage on any round pass."""
    rounds = receipt.get("rounds")
    if not isinstance(rounds, list):
        return True, None
    for idx, rd in enumerate(rounds):
        if not isinstance(rd, dict):
            continue
        lc = rd.get("lensCoverage")
        if lc is None:
            continue
        rnd = rd.get("round", idx)
        if not isinstance(lc, dict):
            return False, "round %s lensCoverage must be an object" % rnd
        for key in ("ran", "expected", "floor"):
            if key not in lc:
                return False, "round %s lensCoverage missing key %r" % (rnd, key)
        ran, expected, floor = lc["ran"], lc["expected"], lc["floor"]
        if type(ran) is not int or type(expected) is not int:
            return False, "round %s lensCoverage ran and expected must be integers" % rnd
        if not isinstance(floor, bool):
            return False, "round %s lensCoverage floor must be a boolean" % rnd
        if expected <= 0:
            return False, "round %s lensCoverage expected must be positive" % rnd
        if ran < 0 or ran > expected:
            return False, ("round %s lensCoverage ran (%d) must satisfy 0 <= ran <= expected (%d)"
                           % (rnd, ran, expected))
        if ran < expected and not floor:
            return False, ("round %s lensCoverage claims floor:false with partial coverage "
                           "(ran %d < expected %d)" % (rnd, ran, expected))
    if receipt.get("verdict") != "converged":
        return True, None
    cert = receipt.get("certification") if isinstance(receipt.get("certification"), dict) else {}
    shape = receipt.get("certificationShape") or cert.get("shape")
    full_panel_anchor = bool(cert.get("fullPanel")) or (
        isinstance(shape, str) and shape.startswith("full-panel-confirmed"))
    if not full_panel_anchor:
        return True, None
    round_dicts = [rd for rd in rounds if isinstance(rd, dict)]
    if not any(rd.get("lensCoverage") is not None for rd in round_dicts):
        return True, None

    def _round_num(rd):
        r = rd.get("round")
        return int(r) if isinstance(r, int) or (isinstance(r, str) and str(r).isdigit()) else 0

    anchor = max(round_dicts, key=_round_num)
    anchor_lc = anchor.get("lensCoverage")
    if anchor_lc is None:
        return False, ("converged certification anchor round %s lacks lensCoverage"
                       % anchor.get("round"))
    if isinstance(anchor_lc, dict) and anchor_lc.get("floor"):
        return False, ("converged certification cannot anchor on floor-marked round %s"
                       % anchor.get("round"))
    return True, None


def _validate_certified_receipt(receipt):
    """Validate a driver receipt's SHAPE (NOT grafted onto panel_tally._valid_final_receipt — that
    is the reviewer-seat receipt; this is the loop's terminal receipt). Fail-closed: a receipt
    missing scriptRan or the seat map, or with a non-list rounds/findings/decisions/degraded/
    skippedBlockers, is rejected with a reason. `skippedBlockers` is REQUIRED (possibly empty) so a
    receipt can never omit the skipped-blocking channel (the exit_skipped invariant). Per-round entries
    may carry an `auditProvenance` field (`runner-record`, `hand-landed-evidence`, `mixed-evidence`,
    or `collection-manifest` on a hand `submit`) — it is
    ACCEPTED, not required. The optional top-level `base` block (pinned diff-base metadata from a CLI
    `next` that ran the base guard) is likewise ACCEPTED, not required — library/eval runs omit it. The
    always-present `baseGuard` field records whether the CLI base guard ran (``BASE_GUARD_CHECKED``,
    set explicitly on a fresh CLI `next` after the guard passes) or not (`not-checked`, including
    library/eval paths and any run that never received that flag); it is not inferred from guard-shaped config
    keys. It is not part of `_RECEIPT_REQUIRED` so older receipts remain valid.

    #723 adds two version-dispatched requirements: `schemaVersion` is one of
    `SUPPORTED_STATE_VERSIONS` (the receipt version follows the STATE's), and the receipt carries
    BOTH a `certification` block and a verdict off `CERTIFIED_VERDICTS`. Those two are what make a
    certified receipt un-confusable with the attested shape: an attestation can never satisfy them.
    Returns (ok, reason)."""
    if not isinstance(receipt, dict):
        return False, "receipt is not an object"
    for key in _receipt_required_keys(RECEIPT_FORM_CERTIFIED):
        if key not in receipt:
            return False, "receipt missing required key %r" % key
    for key in _receipt_forbidden_keys(RECEIPT_FORM_CERTIFIED):
        if key in receipt:
            return False, "certified receipt must not carry %r" % key
    if receipt.get("schemaVersion") not in SUPPORTED_STATE_VERSIONS:
        return False, ("receipt schemaVersion must be one of %s"
                       % ", ".join(str(v) for v in SUPPORTED_STATE_VERSIONS))
    if "certification" not in receipt:
        return False, "certified receipt missing required key 'certification'"
    if not isinstance(receipt.get("certification"), dict):
        return False, ("certified receipt certification must be an object — a certified receipt "
                       "carries its certification block")
    if receipt.get("verdict") not in CERTIFIED_VERDICTS:
        return False, ("certified receipt verdict %r is not one of: %s"
                       % (receipt.get("verdict"), ", ".join(CERTIFIED_VERDICTS)))
    if not isinstance(receipt.get("scriptRan"), dict):
        return False, "receipt scriptRan must be an object (the journal-derived evidence)"
    if "byPhase" not in receipt["scriptRan"]:
        return False, "receipt scriptRan must carry byPhase (the per-phase journal counts)"
    if not isinstance(receipt.get("seatMap"), dict):
        return False, "receipt seatMap must be an object"
    for key in ("rounds", "findings", "decisions", "degraded", "skippedBlockers"):
        if not isinstance(receipt.get(key), list):
            return False, "receipt %s must be a list" % key
    if not receipt.get("verdict"):
        return False, "receipt verdict is empty"
    ok, reason = _validate_rounds_lens_coverage(receipt)
    if not ok:
        return ok, reason
    ok, reason = _validate_round_entries_verify_passes(receipt)
    if not ok:
        return ok, reason
    return True, None


# =============================================================================================
# Layer 1 — library loop
# =============================================================================================

_RUN_LOOP_GUARD = 200


def _reviewer_findings(result):
    """Normalize a reviewer-seam return into a findings list.

    Panel seats return a full seat dict ``{findings, confidence, verificationReceipt, ...}``
    (the JS ``reviewerAgent`` shape). Scoped-finder / gap-sweep reuse the same seam; unwrap
    the dict so ``_fold_scoped`` / ``_fold_gapsweep`` see a list — a bare list remains valid
    (the library tests' compact form)."""
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        findings = result.get("findings")
        return findings if isinstance(findings, list) else []
    return []


def _run_seam(seams, action, payload, state, config):
    """Call the seam for one action and return its artifact in the shape `_fold` expects. Seams are
    injectable; a missing seam is a hard fail (the loop cannot proceed without the effect)."""
    io = seams.get("io") or {}
    if action == P_PANEL:
        seats = {}
        for dim in _panel_dimensions(config):
            tier = payload.get("tier", DEEP)
            result = seams["reviewer"](dim, tier, state["round"], payload)
            # bounded re-dispatch on a receipt-missing/stale seat (REDISPATCH_BUDGET), then missing.
            attempts = 0
            while attempts < REDISPATCH_BUDGET and isinstance(result, dict) \
                    and (result.get("receiptMissing") or result.get("receiptStale")):
                attempts += 1
                result = seams["reviewer"](dim, tier, state["round"], payload)
            seats[dim] = result
        out = {"seats": seats}
        if isinstance(io, dict):
            sm = io.get("seatMap")
            if isinstance(sm, dict):
                out["seatMap"] = sm
        return out
    if action == P_VERIFIERS:
        result = seams["verifier"](payload.get("clusters"), state["round"])
        # The callback may report the vendor it actually ran on: `{"verdicts": [...], "vendor": v}`.
        # A bare list reports nothing. Never the driver's selection: that is an assertion of who ran
        # with no execution record.
        reported = None
        if isinstance(result, dict) and "verdicts" in result:
            vendor = result.get("vendor")
            reported = vendor.strip() if isinstance(vendor, str) and vendor.strip() else None
            result = result["verdicts"]
        artifact = {"verdicts": result}
        fault = verifier_results_fault(artifact)
        if fault is not None:
            return {"verdicts": [], "_verifierArtifactFault": fault}
        # No report leaves the key absent, so `_fold_verifiers` applies its own rule (an unclaimed
        # verdict is ignored when the selection replaced the reviewer engine).
        if reported is not None:
            artifact["verifierVendor"] = reported
        return artifact
    if action == P_SYNTHESIS:
        result = seams["synthesis"](payload.get("findings"), state["round"])
        # The callback may report the vendor it ran on: `{"grouping": [...], "vendor": v}`; a bare
        # grouping reports nothing and is accepted.
        if isinstance(result, dict) and "grouping" in result:
            vendor = result.get("vendor")
            artifact = {"grouping": result["grouping"]}
            if isinstance(vendor, str) and vendor.strip():
                artifact["synthesisVendor"] = vendor.strip()
            return artifact
        return {"grouping": result}
    if action in (P_GAPSWEEP, P_SECOND_TEST, P_SCOPED):
        seat = {P_GAPSWEEP: "gap-sweep", P_SECOND_TEST: "second-test", P_SCOPED: "scoped-finder"}[action]
        result = seams["reviewer"](seat, DEEP, state["round"], payload)
        artifact = {"findings": _reviewer_findings(result)}
        # The callback may report who ran: `{"findings": [...], "vendor": v}`; a bare list reports none.
        vendor = result.get("vendor") if isinstance(result, dict) else None
        if isinstance(vendor, str) and vendor.strip():
            artifact["reviewerVendor"] = vendor.strip()
        return artifact
    if action == P_AUDITS:
        # This library layer IS the orchestrator here: it records its OWN dispatch manifest
        # out-of-band from the auditor's results — {target-id: the vendor it seated}, read straight
        # off the dispatch payload (which the driver stamped), NEVER derived from what the auditor
        # returns. The CLI path carries the real orchestrator's `collectionManifest` in the submit
        # artifact instead (see round-driver.md dispatch-audits). #507 WO-FIX-RECOVERY.
        targets = payload.get("targets") or []
        manifest = {t.get("id"): t.get("auditorVendor")
                    for t in targets if isinstance(t, dict) and t.get("id") is not None}
        return {"results": seams["auditor"](payload.get("targets"), state["round"]),
                "collectionManifest": manifest}
    if action == P_VERIFY:
        return {"result": seams["verify_runner"](payload.get("command"), state["round"])}
    if action == P_APPLY_FIXES:
        return seams["fix_step"](payload.get("batch"), state["round"], payload)
    return {}


FIX_FOLD_HEAD_KEY = session_contract.FIX_FOLD_HEAD_KEY


def _persist_fix_fold_head_sha(session_dir, state, head):
    """Write the fix-fold head into state config and meta.json for resumed sessions."""
    if not isinstance(head, str) or not head:
        return
    cfg = state.setdefault("config", {})
    if isinstance(cfg, dict):
        cfg[FIX_FOLD_HEAD_KEY] = head
    meta_path = os.path.join(session_dir, round_records.META_FILE)
    if not os.path.isfile(meta_path):
        return
    try:
        with open(meta_path, encoding="utf-8") as fh:
            meta_obj = json.load(fh)
    except (OSError, ValueError):
        return
    if not isinstance(meta_obj, dict):
        return
    meta_obj[FIX_FOLD_HEAD_KEY] = head
    round_commit.atomic_write_bytes(
        meta_path,
        (json.dumps(meta_obj, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def _verified_head_at_fold(session_dir, state):
    """Resolve the head the next panel's diff is derived from and persist it as the session's fix-fold head.

    Called at the submit chokepoint and by the in-process leg, never from inside the fold.
    Returns (head, error). With a session dir this is the fixer fold's resolver: the resolved head
    is written into state config and ``meta.json`` as the fix-fold head, the same head orders
    emission anchors to. WITHOUT a session dir (`run_loop`'s in-process leg) there is NO fallback:
    `config["headSha"]` is the session-SETUP head and could name a head a fixer seam had already
    moved past, so it returns an error and no head."""
    if session_dir:
        return _resolve_fix_fold_head_sha(session_dir, state)
    return (None, "verified head: no session dir — the in-process leg resolves no verified head")


def _resolve_fix_fold_head_sha(session_dir, state):
    """Resolve the certified head once at fix-fold time — never the session-setup headSha.

    Returns (head_sha, error). On success the head is persisted so a resumed session reads the
    same value rather than re-deriving a now-different one."""
    if _fix_batch_paths(state):
        repo_root = _resolve_repo_root(session_dir, state)
        if not repo_root:
            return None, "fix-fold head: repo root unresolvable"
        head = store_core.run_git(repo_root, "rev-parse", "HEAD")
        if not head:
            return None, "fix-fold head: git rev-parse HEAD failed in %r" % repo_root
        _persist_fix_fold_head_sha(session_dir, state, head)
        return head, None
    cfg = (state.get("config") or {}) if isinstance(state, dict) else {}
    persisted = cfg.get(FIX_FOLD_HEAD_KEY)
    if isinstance(persisted, str) and persisted:
        return persisted, None
    meta = _session_meta(session_dir)
    persisted = meta.get(FIX_FOLD_HEAD_KEY)
    if isinstance(persisted, str) and persisted:
        if isinstance(cfg, dict):
            cfg[FIX_FOLD_HEAD_KEY] = persisted
            state["config"] = cfg
        return persisted, None
    repo_root = _resolve_repo_root(session_dir, state)
    if not repo_root:
        return None, "fix-fold head: repo root unresolvable"
    head = store_core.run_git(repo_root, "rev-parse", "HEAD")
    if not head:
        return None, "fix-fold head: git rev-parse HEAD failed in %r" % repo_root
    _persist_fix_fold_head_sha(session_dir, state, head)
    return head, None


def _session_certified_head(session_dir, state):
    """The session's head SHA: fix-fold head, then session-setup head, from meta.json then config."""
    meta_path = os.path.join(session_dir, round_records.META_FILE)
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, encoding="utf-8") as fh:
                meta = json.load(fh)
            head = (meta or {}).get(FIX_FOLD_HEAD_KEY)
            if isinstance(head, str) and head:
                return head
            head = (meta or {}).get("headSha")
            if isinstance(head, str) and head:
                return head
        except (OSError, ValueError):
            pass
    cfg = (state.get("config") or {}) if isinstance(state, dict) else {}
    head = cfg.get(FIX_FOLD_HEAD_KEY)
    if isinstance(head, str) and head:
        return head
    head = cfg.get("headSha")
    if isinstance(head, str) and head:
        return head
    return None


def _resolve_repo_root(session_dir, state):
    """Repository root for byte-safe git reads — meta.json first, else cwd discovery."""
    meta = _session_meta(session_dir)
    repo_root = meta.get("repoRoot")
    if isinstance(repo_root, str) and repo_root:
        return os.path.realpath(repo_root)
    root = store_core.repo_root(os.getcwd())
    return os.path.realpath(root) if root else None


def _fix_batch_paths(state, artifact=None):
    paths = []
    seen = set()
    for batch in ((state or {}).get("_fixBatch"), (state or {}).get("fixBatch")):
        if not isinstance(batch, list):
            continue
        for item in batch:
            if not isinstance(item, dict):
                continue
            path = item.get("file")
            if isinstance(path, str) and path and path not in seen:
                seen.add(path)
                paths.append(path)
    if isinstance(artifact, dict):
        for fix in artifact.get("fixes") or []:
            if not isinstance(fix, dict):
                continue
            path = fix.get("file") or fix.get("path")
            if isinstance(path, str) and path and path not in seen:
                seen.add(path)
                paths.append(path)
    return paths


def _retain_unauthenticated_finder_findings(state, artifact):
    """Carry the candidates of a finder result that failed vendor authentication onto the state as
    explicitly UNVERIFIED rows, so the fail-closed park withholds certification without discarding
    the review work already obtained. Rows never enter the fold (no verification, no ledger)."""
    found = artifact.get("findings") if isinstance(artifact, dict) else None
    existing = state.get("findings")
    rows = list(existing) if isinstance(existing, list) else []
    for f in found if isinstance(found, list) else ():
        if isinstance(f, dict):
            row = dict(f)
            row["unverified"] = True
            rows.append(row)
    _set_findings(state, rows)


def _retain_verified_findings_unmerged(state):
    """Carry the verified survivors staged for synthesis onto the receipt-visible findings before an
    unauthenticated-synthesis park, WITHOUT applying the unauthenticated grouping: the confirmed
    blockers stay visible while certification is withheld. Outstanding carried findings are kept."""
    verified = state.get("_verified")
    if not isinstance(verified, list) or not verified:
        return
    existing = state.get("findings")
    rows = list(existing) if isinstance(existing, list) else []
    rows.extend(dict(f) if isinstance(f, dict) else f for f in verified)
    _set_findings(state, rows)


def _retain_second_test_findings(state):
    """Carry the findings the second-test step was holding onto the receipt-visible findings before an
    unauthenticated-second-test park: each held finding as an explicitly UNVERIFIED row and each first-pass
    survivor as it stands, so the park withholds certification without losing what the round already had."""
    held = state.get("_secondTestHeld")
    carried = state.get("_secondTestCarry")
    existing = state.get("findings")
    rows = list(existing) if isinstance(existing, list) else []
    for row in held if isinstance(held, list) else ():
        finding = row.get("finding") if isinstance(row, dict) else None
        if isinstance(finding, dict):
            rows.append(dict(finding, unverified=True))
    for f in carried if isinstance(carried, list) else ():
        if isinstance(f, dict):
            rows.append(dict(f))
    _set_findings(state, rows)


def _driver_receipt(state):
    """The terminal receipt of a run_loop state — the driver's own, built from the state alone."""
    return build_receipt(state, session_dir=None, form=RECEIPT_FORM_CERTIFIED)


def run_loop(seams, config=None):
    """Layer 1: drive the whole loop end-to-end with scripted seams. Ports the run-SHAPE of
    review_panel_shell.reviewPanel. Returns the driver's terminal receipt."""
    if not isinstance(seams, dict):
        raise ValueError("run_loop requires a seams dict")
    try:
        state = new_state(config)
    except (MaxRoundsRefusal, FixBatchCapRefusal) as refusal:
        state = new_state()
        _park_cannot_certify(state, refusal.reason)
        return _driver_receipt(state)
    guard = 0
    try:
        while not state.get("terminal") and guard < _RUN_LOOP_GUARD:
            guard += 1
            step = _advance(state, state["config"])
            action = step["action"]
            if action == P_TERMINAL:
                break
            # the finder is authenticated against the selection as it stood when the seam was called:
            # a preference edit made while the callback runs never re-judges its result.
            selected, replaced = None, False
            if action == P_SYNTHESIS:
                selected, _src = _nonpanel_selection(state, None, action)
            if action in (P_GAPSWEEP, P_SECOND_TEST, P_SCOPED):
                selected, _src = _nonpanel_selection(state, None, action)
                replaced = selected is not None and _nonpanel_replaced(state, selected)
            # handle the gap-sweep re-entry (verifiers → synthesis carries the merge back).
            artifact = _run_seam(seams, action, step["payload"], state, state["config"])
            if action == P_VERIFIERS and isinstance(artifact, dict):
                fault = artifact.pop("_verifierArtifactFault", None)
                if fault is not None:
                    _record_round_append(state, "verifierArtifactFault",
                                         {"fault": fault, "round": state["round"]})
            if action == P_SYNTHESIS and isinstance(artifact, dict):
                reported = artifact.pop("synthesisVendor", None)
                if reported is not None and (
                        reported != selected
                        or receipt_disclosures.nonpanel_barred(state, state["config"])(reported)):
                    _retain_verified_findings_unmerged(state)
                    _park_cannot_certify(
                        state, "nonpanel-synthesis-unauthenticated:expected=%s:reported=%s" % (
                            selected, reported))
                    return _driver_receipt(state)
            if action in (P_GAPSWEEP, P_SECOND_TEST, P_SCOPED):
                reported = artifact.pop("reviewerVendor", None) if isinstance(artifact, dict) else None
                if _library_finder_unauthenticated(state, reported, action, selected=selected,
                                                   replaced=replaced):
                    if action != P_SECOND_TEST:  # its items are findings already raised: they stay on the ledger, open
                        _retain_unauthenticated_finder_findings(state, artifact)
                    else:  # what the round already had — the held findings and the first pass's survivors — is kept
                        _retain_second_test_findings(state)
                    _park_cannot_certify(
                        state, "nonpanel-finder-unauthenticated:%s:expected=%s:reported=%s" % (
                            action, selected, reported))
                    return _driver_receipt(state)
            commits = None
            if action == P_APPLY_FIXES:
                # the same check the submit chokepoint makes, with the commit facts from the
                # `fix_commits` seam when the run has no repository
                detail, commits = _apply_fixes_commit_fault(
                    state, state["config"], artifact if isinstance(artifact, dict) else {},
                    commit_seam=seams.get("fix_commits"))
                if detail is not None:
                    _park_cannot_certify(state, "%s: %s" % (FIX_REFUSED_REASON, detail))
                    return _driver_receipt(state)
            try:
                _fold(state, state["config"], action, artifact, seams.get("changed_subjects"),
                      verified_head_resolution=_verified_head_at_fold(None, state),
                      panel_diff_seam=seams.get("panel_diff"), fix_commits=commits)
            except DispositionLedgerOwnerRefusal as refusal:
                _park_cannot_certify(state, refusal.reason)
                return _driver_receipt(state)
            if state.get("step") == P_APPLY_FIXES and seams.get("fix_step_head"):
                state["_fixStepHead"] = seams["fix_step_head"]()
            _persist_round_records(state, state["config"])
            # a delta round routes scoped candidates through verifiers; when that path is armed the
            # synthesis fold must re-settle the delta rather than the round-1 path.
            if state.pop("_settleDeltaAfterSynthesis", False):
                pass
    except JournalFaultUnrecordable as jf:
        # Last-resort fail-closed: a journal fault the driver could not even record parks
        # cannot-certify — the library layer NEVER continues (or crashes the caller) as though the
        # ran-evidence were intact. #507 WO-FIX-RECOVERY.
        _park_cannot_certify(state, "journal-fault-unrecordable: %s" % jf)
        return _driver_receipt(state)
    if guard >= _RUN_LOOP_GUARD and not state.get("terminal"):
        _set_terminal(state, "halted")
        state["certification"] = {"shape": None, "reason": "run_loop guard tripped — fail closed"}
    return _driver_receipt(state)


# =============================================================================================
# Layer 2 — the stepwise CLI (next / submit)
# =============================================================================================

def cmd_next(session_dir, config_overrides=None):
    """Emit the ONE next action. Idempotent: a second `next` before a `submit` returns the same
    pending step + hash. A v1 state file is refused with a fresh-start message.

    #723: a FRESH state also mints the session id into `meta.json` first
    (`round_records.mint_session_id`, which merges — the `review-code` SKILL owns that file and its
    other keys must survive). Every per-seat envelope is bound to that id, so a session that could
    not mint one can record nothing: an unmintable id refuses LOUDLY here rather than letting the
    record layer refuse `bootstrap-required` per seat later."""
    try:
        with round_records.session_lock(session_dir):
            upgrade = _upgrade_gate(session_dir, "next")
            if upgrade is not None:
                return upgrade
            refusal = _commit_recover_or_refuse(session_dir, "next")
            if refusal is not None:
                return refusal
            return _cmd_next_locked(session_dir, config_overrides)
    except round_records.SessionLockHeld as held:
        return _lock_held_refusal(session_dir, "next", held)


def _cmd_next_locked(session_dir, config_overrides=None):
    ok, loaded = load_state(session_dir)
    if not ok:
        fault_reason, fault, _detail = _state_load_fault(session_dir)
        _journal_append(session_dir, {"cmd": "next", "phase": None, "round": None,
                                      "attempt": None, "outcome": fault_reason, "fault": fault})
        return {"ok": False, "reason": loaded}
    if loaded is None:
        session_id, mint_reason = round_records.mint_session_id(session_dir)
        if mint_reason is not None or not session_id:
            _journal_append(session_dir, {"cmd": "next", "phase": None, "round": None,
                                          "attempt": None, "outcome": "refused-session-id",
                                          "reason": mint_reason})
            return {"ok": False, "reason": "session-id-unmintable", "detail": mint_reason}
        _bootstrap_review_session_marker(session_dir)
        try:
            state = new_state(_with_build_session_vendor(config_overrides))
        except MaxRoundsRefusal as refusal:
            _journal_append(session_dir, {"cmd": "next", "phase": None, "round": None,
                                          "attempt": None, "outcome": "refused-max-rounds",
                                          "reason": refusal.reason})
            return {"ok": False, "reason": refusal.reason, "value": refusal.value}
        except FixBatchCapRefusal as refusal:
            _journal_append(session_dir, {"cmd": "next", "phase": None, "round": None,
                                          "attempt": None, "outcome": "refused-fix-batch-cap",
                                          "reason": refusal.reason})
            return {"ok": False, "reason": refusal.reason, "value": refusal.value}
    else:
        state = loaded
        if config_overrides and config_overrides.get("recordsPath") is not None:
            loaded_path = (loaded.get("config") or {}).get("recordsPath")
            override_path = config_overrides.get("recordsPath")
            if override_path != loaded_path:
                _journal_append(session_dir, {"cmd": "next", "phase": None, "round": None,
                                              "attempt": None,
                                              "outcome": "refused-records-path-not-fresh"})
                return {"ok": False, "reason": "records-path-not-fresh-state"}
        if _cap_blocks_loaded(state, state["config"]):
            pending = {"action": P_TERMINAL, "round": state["round"], "phase": P_TERMINAL,
                       "attempt": 0,
                       "payload": {"verdict": state["terminal"],
                                   "certification": state.get("certification")}}
            state["pending"] = pending
            save_state(session_dir, state)
            _journal_append(session_dir, {"cmd": "next", "phase": P_TERMINAL,
                                          "round": state["round"], "attempt": 0,
                                          "outcome": "loaded-cap-hand-back"})
            fail = _terminal_receipt_gate(session_dir, state)
            if fail:
                return _receipt_fault_response(fail)
            return _next_response(session_dir, state, pending, "next")
    if state.get("pending"):
        # idempotent re-emit: the state is unchanged since the pending was persisted, so the hash
        # recomputed here equals the one the first `next` returned (the hash is NEVER stored in the
        # pending — that would make it un-reproducible on re-emit).
        pend = state["pending"]
        _journal_append(session_dir, {"cmd": "next", "phase": pend.get("phase"),
                                      "round": pend.get("round"), "attempt": pend.get("attempt"),
                                      "outcome": "re-emit"})
        # A REPLAYED terminal `next` re-emits the stored terminal pending WITHOUT re-running
        # _finalize_receipt — so re-verify the on-disk receipt (fault marker + fresh re-read +
        # validate_receipt) here, else a fault recorded/surfaced since the first emission is masked
        # by the replay's ok (#507). Any fault → fail-loud receipt-fault, never terminal-with-ok. The
        # gate re-verifies from disk (never re-writes) so a fault stays durable across invocations.
        if pend.get("phase") == P_TERMINAL:
            fault = _terminal_receipt_gate(session_dir, state)
            if fault:
                return _receipt_fault_response(fault)
        refusal = _disposition_ledger_owner_refusal(session_dir, state, pend, "next")
        if refusal is not None:
            return refusal
        if pend.get("phase") == P_APPLY_FIXES:
            # The step's files are derived from the state, so a re-emit rewrites any a ruling's
            # failed commit left stale.
            try:
                _apply_fixes_payload_fields(session_dir, state, pend.get("round"),
                                            pend.get("attempt"))
            except ValueError as exc:
                return _refuse_cmd(session_dir, "next", "order-render-refused", phase=P_APPLY_FIXES,
                                   rnd=pend.get("round"), attempt=pend.get("attempt"),
                                   detail=str(exc))
        return _next_response(session_dir, state, pend, "next")
    step = _advance(state, state["config"])
    attempt = _next_dispatch_attempt(session_dir, step["round"], step["phase"], state)
    pending = {"action": step["action"], "round": step["round"], "phase": step["phase"],
               "attempt": attempt, "payload": step["payload"]}
    verify = pending.get("payload", {}).get("verify") if isinstance(pending.get("payload"), dict) else None
    if pending["phase"] == P_AUDITS and isinstance(verify, dict):
        # attempt is allocated here from the same counter run-verify will use on submit — a mismatch
        # cannot arise when nothing was submitted for that phase in that round.
        attempt = _next_dispatch_attempt(session_dir, pending["round"], P_VERIFY, state)
        verify.update({
            "round": pending["round"],
            "attempt": attempt,
            "landingPath": round_records.bare_payload_path(
                session_dir, pending["round"], P_VERIFY,
                round_records.storage_key("verify"), attempt),
        })
    refusal = _disposition_ledger_owner_refusal(session_dir, state, pending, "next")
    if refusal is not None:
        return refusal
    if pending["phase"] == P_APPLY_FIXES:
        try:
            _stage_apply_fixes_step(session_dir, state, pending)
        except ValueError as exc:
            return _refuse_cmd(session_dir, "next", "order-render-refused", phase=pending["phase"],
                               rnd=pending.get("round"), attempt=attempt, detail=str(exc))
    state["pending"] = pending
    phase = pending.get("phase")
    if isinstance(phase, str) and phase.startswith("dispatch-"):
        roster, roster_refusal = _roster_of(session_dir, state, "next", phase,
                                            pending.get("round"), attempt)
        if roster_refusal is not None:
            return roster_refusal
        try:
            _emit_orders_manifest(session_dir, state, pending.get("round"), phase, attempt, roster,
                                  journal_cmd="next", pending_payload=pending.get("payload"),
                                  seat_map=_effective_seat_map(state))
        except round_commit.CommitRefused as exc:
            return _commit_refused_response(session_dir, "next", exc, phase=phase,
                                          rnd=pending.get("round"), attempt=attempt)
        except AuditorUnseatable as exc:
            return _refuse_cmd(session_dir, "next", AUDITOR_UNSEATABLE_CAUSE, phase=phase,
                               rnd=pending.get("round"), attempt=attempt,
                               liveVendors=exc.live_vendors, fixerVendor=exc.fixer_vendor,
                               detail=exc.detail)
        except ValueError as exc:
            return _refuse_cmd(session_dir, "next", "order-render-refused", phase=phase,
                               rnd=pending.get("round"), attempt=attempt, detail=str(exc))
    save_state(session_dir, state)
    _journal_append(session_dir, {"cmd": "next", "phase": pending["phase"],
                                  "round": pending["round"], "attempt": attempt,
                                  "outcome": "emitted"})
    if step["action"] == P_TERMINAL:
        fail = _terminal_receipt_gate(session_dir, state)
        if fail:
            return _receipt_fault_response(fail)
    return _next_response(session_dir, state, pending, "next")


def _stage_apply_fixes_step(session_dir, state, pending):
    """Make the apply-fixes step ready for the build session as `next` emits it: stage the PR body
    when the session reviews a PR, snapshot the staged copy so the fold can tell whether the session
    changed it, and add the step's file and landing paths to the pending payload."""
    cfg = state.get("config") or {}
    if session_mode.resolve(_session_meta(session_dir), cfg)["mode"] != session_mode.MODE_BRANCH:
        pr_body_stage.stage(session_dir)
    snapshot = _staged_pr_body_sha256(session_dir)
    if snapshot is not None:
        state["_prBodyAtStep"] = snapshot
    fields = _apply_fixes_payload_fields(session_dir, state, pending["round"], pending["attempt"])
    pending["payload"] = dict(pending.get("payload") or {}, **fields)


def _receipt_fault_response(detail):
    """A terminal receipt integrity fault — the fail-loud `receipt-fault` family (the same family as
    `journal-fault-unrecordable`). Answered on the terminal `next` (first emission or a replay) and
    the terminating `submit`; the CLI surfaces it NONZERO and it is NEVER a `terminal`-with-ok."""
    return {"ok": False, "reason": "receipt-fault", "detail": detail}


def _records_path_is_reserved(session_dir, records_path):
    """Return True when records_path lies inside the session directory."""
    if not records_path:
        return False
    resolved = os.path.realpath(os.path.abspath(records_path))
    session_real = os.path.realpath(os.path.abspath(session_dir))
    if resolved == session_real:
        return True
    try:
        return os.path.commonpath([resolved, session_real]) == session_real
    except ValueError:
        return False


def _refuse_base_guard(session_dir, reason, detail=None, value=None):
    """#648: a base-guard refusal — journalled first (so the refusal is durable evidence, not just a
    console line), then surfaced on stdout, nonzero. Journal-first matters: when the journal AND its
    fault marker are both unwritable the append raises JournalFaultUnrecordable, which `main` reports
    as the last-resort fail-loud — the existing contract, preserved."""
    _journal_append(session_dir, {"cmd": "next", "phase": None, "round": None, "attempt": None,
                                  "outcome": "refused-base-guard", "reason": reason})
    body = {"ok": False, "reason": reason}
    if detail is not None:
        body["detail"] = detail
    if value is not None:
        body["value"] = value
    sys.stdout.write(json.dumps(body) + "\n")
    return 1


def _disposition_ledger_owner_refusal(session_dir, state, pending, cmd):
    """Refuse hand-out when the disposition-ledger owner is unrecognized (non-terminal only)."""
    action = pending.get("action") if isinstance(pending, dict) else None
    if action == P_TERMINAL:
        return None
    if (session_contract.disposition_ledger_owner_classification(state)
            == session_contract.DISPOSITION_LEDGER_OWNER_UNRECOGNIZED):
        phase = pending.get("phase") if isinstance(pending, dict) else None
        rnd = pending.get("round") if isinstance(pending, dict) else None
        attempt = pending.get("attempt") if isinstance(pending, dict) else None
        return _refuse_cmd(session_dir, cmd, DISPOSITION_LEDGER_OWNER_UNRECOGNIZED_CAUSE,
                           phase=phase, rnd=rnd, attempt=attempt)
    return None


def _ruling_ledger_precondition_refusal(session_dir, state, pending):
    """Refuse `rule` before mutation when the ledger owner is unrecognized or the ledger is malformed."""
    pend = pending if isinstance(pending, dict) else {}
    owner_refusal = _disposition_ledger_owner_refusal(session_dir, state, pend, RULE_CMD)
    if owner_refusal is not None:
        return owner_refusal
    if session_contract.disposition_ledger_owner_classification(state) == (
            session_contract.DISPOSITION_LEDGER_OWNER_RECOGNIZED):
        _rows, fault = session_contract.read_disposition_ledger(state, required=True)
        if fault is not None:
            return _refuse_cmd(
                session_dir, RULE_CMD, fault.token,
                phase=pend.get("phase"), rnd=pend.get("round"), attempt=pend.get("attempt"),
                detail=fault.detail)
    _log_rows, log_fault = _read_rulings_log(state)
    if log_fault is not None:
        token, detail = log_fault
        return _refuse_cmd(
            session_dir, RULE_CMD, token,
            phase=pend.get("phase"), rnd=pend.get("round"), attempt=pend.get("attempt"),
            detail=detail)
    seq_fault = _ruling_seq_counter_fault(state)
    if seq_fault is not None:
        token, detail = seq_fault
        return _refuse_cmd(
            session_dir, RULE_CMD, token,
            phase=pend.get("phase"), rnd=pend.get("round"), attempt=pend.get("attempt"),
            detail=detail)
    return None


def _ensure_landing_folders(session_dir, pending):
    """Make the landing folders a pending step's seat or command will write into.

    Invariant: whenever the driver hands a caller a pending step whose phase is a seat dispatch
    (`dispatch-*`) or `run-verify`, `round-<N>/landing/<phase>/` already exists; and when the payload
    advertises a verify gate (`payload["verify"]["landingPath"]`) that the driver itself made, that
    path's parent folder exists too. An empty folder carries no claim — the landing readers read an
    empty or missing folder as nothing landed — so this changes no state and no journal. A terminal
    pending, or one whose round is not a plain int, makes no folder. An `OSError` propagates:
    a session folder that cannot be written fails loudly, as every other session write does."""
    rnd = pending.get("round")
    if isinstance(rnd, bool) or not isinstance(rnd, int):
        return
    phase = pending.get("phase")
    if isinstance(phase, str) and (phase.startswith("dispatch-")
                                   or phase in (P_VERIFY, P_APPLY_FIXES)):
        os.makedirs(round_records.landing_dir(session_dir, rnd, phase), exist_ok=True)
    payload = pending.get("payload")
    verify = payload.get("verify") if isinstance(payload, dict) else None
    landing_path = verify.get("landingPath") if isinstance(verify, dict) else None
    verify_round = verify.get("round") if isinstance(verify, dict) else None
    if (isinstance(landing_path, str) and landing_path
            and isinstance(verify_round, int) and not isinstance(verify_round, bool)):
        parent = os.path.dirname(landing_path)
        if parent == round_records.landing_dir(session_dir, verify_round, P_VERIFY):
            os.makedirs(parent, exist_ok=True)


def _next_response(session_dir, state, pending, cmd):
    _ensure_landing_folders(session_dir, pending)
    expected_hash = state_hash(state)
    return {
        "ok": True,
        "action": pending["action"],
        "round": pending["round"],
        "phase": pending["phase"],
        "attempt": pending["attempt"],
        "expectedStateHash": expected_hash,
        "payload": pending.get("payload"),
    }


def _journal_has_orders_emitted(session_dir, rnd, phase, attempt):
    for event in read_journal(session_dir):
        if event.get("outcome") != "orders-emitted":
            continue
        if (event.get("round") == rnd and event.get("phase") == phase
                and event.get("attempt") == attempt):
            return True
    return False


def _journal_damaged(session_dir):
    """True when the session journal has an unreadable or malformed row — callers must refuse."""
    journal, lossy = read_journal(session_dir, report_lossy=True)
    return lossy or any(not isinstance(event, dict) for event in journal)


def _refuse_journal_damaged(session_dir, cmd, **kwargs):
    return _refuse_cmd(session_dir, cmd, JOURNAL_DAMAGED_CAUSE,
                       detail=JOURNAL_DAMAGED_DETAIL, **kwargs)



def _severity_for_finding_key(state, key, fallback=None):
    if not isinstance(key, str) or not key:
        return fallback
    ordered = []
    for finding in state.get("findings") or []:
        if isinstance(finding, dict) and _finding_key_of(finding) == key:
            ordered.append(finding)
    for row in state.get("_toVerify") or []:
        if isinstance(row, dict) and _finding_key_of(row) == key:
            ordered.append(row)
    ledger_by_key, ledger_fault = _disposition_ledger_by_key(state)
    if ledger_fault is None:
        entry = ledger_by_key.get(key)
        if isinstance(entry, dict):
            ordered.append(entry)
    for row in (state.get("_fixBatch") or []) + (state.get("_fixQueue") or []):
        if isinstance(row, dict) and _fix_batch_row_key(row) == key:
            ordered.append(row)
    severities = [row.get("severity") for row in ordered
                  if isinstance(row, dict) and row.get("severity") is not None]
    if not severities:
        return fallback
    for sev in severities:
        if circuit_breaker.is_critical(sev):
            return sev
    return severities[0]


def _row_matches_ruling_finding_key(row, ruling_id):
    if not isinstance(row, dict) or not isinstance(ruling_id, str):
        return False
    fkey = row.get(session_contract.FINDING_KEY_FIELD)
    if isinstance(fkey, str) and fkey == ruling_id:
        return True
    derived = _finding_key_of(row)
    return derived == ruling_id if derived else False


def _resolve_ruling_target(state, ruling_id):
    if not isinstance(ruling_id, str) or not ruling_id.strip():
        return None, None, None
    rid = ruling_id.strip()
    for finding in state.get("findings") or []:
        if _row_matches_ruling_finding_key(finding, rid):
            return _finding_key_of(finding), dict(finding), None
    combined = ((state.get("_fixBatch") or []) + (state.get("_fixQueue") or [])
                + (state.get("fixBatch") or []))
    for row in combined:
        if _row_matches_ruling_finding_key(row, rid):
            return _fix_batch_row_key(row), dict(row), None
    ledger_by_key, ledger_fault = _disposition_ledger_by_key(state)
    if ledger_fault is not None:
        return None, None, RULING_FILE_UNREADABLE
    ledger_entries = list(ledger_by_key.values())
    for entry in ledger_entries:
        if isinstance(entry, dict) and _row_matches_ruling_finding_key(entry, rid):
            return _finding_identity_key(entry), dict(entry), None
    id_matches = []
    for finding in state.get("findings") or []:
        if isinstance(finding, dict) and finding.get("id") == rid:
            id_matches.append((_finding_key_of(finding), dict(finding)))
    for row in combined:
        if isinstance(row, dict) and row.get("id") == rid:
            id_matches.append((_fix_batch_row_key(row), dict(row)))
    for entry in ledger_entries:
        if isinstance(entry, dict) and entry.get("id") == rid:
            id_matches.append((_finding_identity_key(entry), dict(entry)))
    by_key = {}
    for key, row in id_matches:
        if isinstance(key, str) and key:
            by_key[key] = row
    if len(by_key) > 1:
        return None, None, RULING_TARGET_AMBIGUOUS
    if len(by_key) == 1:
        key = next(iter(by_key))
        return key, by_key[key], None
    return None, None, None


def _load_ruling_file(path):
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except OSError:
        return None, None, RULING_FILE_UNREADABLE
    try:
        doc = json.loads(raw)
    except ValueError:
        return None, None, RULING_FILE_UNREADABLE
    if not isinstance(doc, dict):
        return None, None, RULING_FILE_SHAPE
    file_sha = round_records.sha256_text(raw)
    return doc, file_sha, None


def _decided_by_well_formed(decided_by):
    """The shared decidedBy contract (finding_outcomes), the one home rule ingestion and settlement read."""
    return finding_outcomes.decided_by_well_formed(decided_by)


def _validate_ruling_entries(doc):
    rulings = doc.get("rulings")
    if not isinstance(rulings, list) or not rulings:
        return None, None, RULING_FILE_SHAPE
    provenance = doc.get("_provenance")
    if not _owner_artifact_provenance_well_formed({"_provenance": provenance}):
        return None, None, RULING_PROVENANCE_MALFORMED
    parsed = []
    for spec in rulings:
        if not isinstance(spec, dict):
            return None, None, RULING_FILE_SHAPE
        rid = spec.get("id")
        kind = spec.get("ruling")
        reason = spec.get("reason")
        if not isinstance(rid, str) or not rid.strip():
            return None, None, RULING_FILE_SHAPE
        if kind not in RULING_KINDS:
            return None, None, RULING_UNKNOWN_KIND
        if not isinstance(reason, str) or not reason.strip():
            return None, None, RULING_REASON_MISSING
        entry = {"id": rid.strip(), "ruling": kind, "reason": reason.strip()}
        if session_contract.has_decided_by(spec):
            if not _decided_by_well_formed(session_contract.decided_by_of(spec)):
                return None, None, RULING_DECIDED_BY_MALFORMED
            session_contract.copy_decided_by_field(spec, entry)
        if kind == "out-of-scope":
            follow_up = spec.get("followUp")
            fault = session_contract.follow_up_shape_fault(follow_up)
            if fault is not None:
                return None, None, RULING_FOLLOW_UP_MALFORMED
            entry["followUp"] = dict(follow_up)
        if kind == "guidance":
            guidance = spec.get("guidance")
            if not isinstance(guidance, str) or not guidance.strip():
                return None, None, RULING_FILE_SHAPE
            if _guidance_oversize(guidance):
                return None, None, RULING_GUIDANCE_OVERSIZE
            entry["guidance"] = guidance.strip()
            if "allowsChange" in spec:
                if not isinstance(spec.get("allowsChange"), bool):
                    return None, None, RULING_FILE_SHAPE
                entry["allowsChange"] = spec["allowsChange"]
        elif "allowsChange" in spec:
            return None, None, RULING_FILE_SHAPE
        parsed.append(entry)
    return parsed, provenance, None


def cmd_rule(session_dir, ruling_file, by):
    try:
        with round_records.session_lock(session_dir):
            upgrade = _upgrade_gate(session_dir, RULE_CMD)
            if upgrade is not None:
                return upgrade
            refusal = _commit_recover_or_refuse(session_dir, RULE_CMD)
            if refusal is not None:
                return refusal
            return _cmd_rule_locked(session_dir, ruling_file, by)
    except round_records.SessionLockHeld as held:
        return _lock_held_refusal(session_dir, RULE_CMD, held)


def _cmd_rule_locked(session_dir, ruling_file, by):
    ok, state = load_state(session_dir)
    if not ok or state is None:
        detail = state if not ok else "no state"
        return _refuse_cmd(session_dir, RULE_CMD, RULING_FILE_UNREADABLE, detail=detail)
    if state.get("terminal"):
        return _refuse_cmd(session_dir, RULE_CMD, RULING_SESSION_TERMINAL)
    doc, file_sha, load_reason = _load_ruling_file(ruling_file)
    if load_reason is not None:
        return _refuse_cmd(session_dir, RULE_CMD, load_reason, value=ruling_file)
    parsed, provenance, shape_reason = _validate_ruling_entries(doc)
    if shape_reason is not None:
        return _refuse_cmd(session_dir, RULE_CMD, shape_reason, value=ruling_file)
    pending = state.get("pending")
    ledger_refusal = _ruling_ledger_precondition_refusal(session_dir, state, pending)
    if ledger_refusal is not None:
        return ledger_refusal
    if isinstance(pending, dict):
        phase = pending.get("phase")
        rnd = pending.get("round")
        attempt = pending.get("attempt")
    else:
        phase = state.get("step")
        rnd = state.get("round")
        attempt = None
    for entry in parsed:
        key, candidate, target_fault = _resolve_ruling_target(state, entry["id"])
        if target_fault == RULING_TARGET_AMBIGUOUS:
            return _refuse_cmd(session_dir, RULE_CMD, RULING_TARGET_AMBIGUOUS, id=entry["id"])
        if target_fault == RULING_FILE_UNREADABLE:
            return _refuse_cmd(session_dir, RULE_CMD, RULING_FILE_UNREADABLE)
        if key is None:
            return _refuse_cmd(session_dir, RULE_CMD, RULING_TARGET_UNKNOWN, id=entry["id"])
        if entry["ruling"] == "out-of-scope":
            sev = _severity_for_finding_key(
                state, key,
                candidate.get("severity") if isinstance(candidate, dict) else None)
            if circuit_breaker.is_critical(sev):
                return _refuse_cmd(session_dir, RULE_CMD, RULING_CRITICAL_OUT_OF_SCOPE,
                                   id=entry["id"])
    # Timing never refuses a ruling: it is recorded whenever it arrives and binds the next fix of its
    # finding. While the apply-fixes step is pending the batch is re-sliced and its batch and
    # guidance files rewritten, so the next `next` hands the build session the current direction.
    cfg = state.get("config") or {}
    round_rulings = []
    restored_rows = []
    for entry in parsed:
        key, candidate, target_fault = _resolve_ruling_target(state, entry["id"])
        if target_fault == RULING_TARGET_AMBIGUOUS:
            return _refuse_cmd(session_dir, RULE_CMD, RULING_TARGET_AMBIGUOUS, id=entry["id"])
        if target_fault == RULING_FILE_UNREADABLE:
            return _refuse_cmd(session_dir, RULE_CMD, RULING_FILE_UNREADABLE)
        if key is None:
            return _refuse_cmd(session_dir, RULE_CMD, RULING_TARGET_UNKNOWN, id=entry["id"])
        prior_live = _live_ruling_by_key(state).get(key)
        seq = _next_ruling_seq(state)
        log_row = {
            "seq": seq,
            "round": state["round"],
            "phase": phase,
            "attempt": attempt,
            "id": entry["id"],
            "findingKey": key,
            "ruling": entry["ruling"],
            "reason": entry["reason"],
            "provenance": provenance,
            "rulingFileSha256": file_sha,
            "by": by,
        }
        if isinstance(candidate, dict):
            for field in ("file", "line"):
                if candidate.get(field) is not None:
                    log_row[field] = candidate.get(field)
        session_contract.copy_follow_up_field(entry, log_row)
        session_contract.copy_decided_by_field(entry, log_row)
        if entry["ruling"] == "out-of-scope":
            # the severity at ruling time, kept with the decision: a restage replaces the ledger's
            log_row["severity"] = _severity_for_finding_key(
                state, key, candidate.get("severity") if isinstance(candidate, dict) else None)
        if entry.get("guidance") is not None:
            log_row["guidance"] = entry["guidance"]
        if "allowsChange" in entry:
            log_row["allowsChange"] = entry["allowsChange"]
        _writable_rulings_log(state).append(log_row)
        round_rulings.append(dict(log_row))
        if entry["ruling"] == "out-of-scope":
            _record_disposition(
                state, key, "out-of-scope", state["round"],
                outOfScopeReason=entry["reason"], followUp=entry.get("followUp"),
                rulingSeq=seq)
        elif entry["ruling"] == "guidance":
            live_row = _live_finding_by_key(state, key)
            ledger_oos = isinstance(live_row, dict) and live_row.get("disposition") == "out-of-scope"
            if not ledger_oos:
                ledger_by_key, ledger_fault = _disposition_ledger_by_key(state)
                if ledger_fault is None:
                    stored = ledger_by_key.get(key)
                    ledger_oos = isinstance(stored, dict) and stored.get("disposition") == "out-of-scope"
            prior_oos = isinstance(prior_live, dict) and prior_live.get("ruling") == "out-of-scope"
            if prior_oos or ledger_oos:
                _clear_out_of_scope_disposition(state, key)
                restore = _live_finding_by_key(state, key) or candidate
                if isinstance(restore, dict):
                    restored_rows.append(dict(restore))
            # A lineage member whose own skip this guidance now supersedes reopens with it.
            for member in _lineage_group(state, key):
                if member == key or _live_out_of_scope_ruling_for_key(state, member) is not None:
                    continue
                if _holds_out_of_scope_disposition(state, member):
                    _clear_out_of_scope_disposition(state, member)
                    restore = _live_finding_by_key(state, member)
                    if isinstance(restore, dict):
                        restored_rows.append(dict(restore))
        _decision(state, "ruling-recorded",
                  "ruling %s on %s (%s)" % (entry["ruling"], entry["id"], entry["reason"]))
    _append_round_rulings(state, round_rulings)
    _reconcile_fix_queue_after_rulings(
        state, cfg, extra_rows=restored_rows, session_dir=session_dir)
    pending_now = state.get("pending")
    if (state.get("step") == P_APPLY_FIXES and not state.get("terminal")
            and isinstance(pending_now, dict) and pending_now.get("phase") == P_APPLY_FIXES):
        # The guidance render is checked, and the step's files rewritten, here; a commit that then
        # fails leaves them stale only until the next `next` rewrites them from the state.
        try:
            fields = _apply_fixes_payload_fields(session_dir, state, pending_now.get("round"),
                                                 pending_now.get("attempt"))
        except ValueError as exc:
            return _refuse_cmd(session_dir, RULE_CMD, "order-render-refused",
                               phase=pending_now.get("phase"), rnd=pending_now.get("round"),
                               attempt=pending_now.get("attempt"), detail=str(exc))
        payload = dict(pending_now.get("payload") or {})
        payload.update(fields)
        state["pending"] = dict(pending_now, payload=payload)
    elif state.get("step") == P_APPLY_FIXES and not state.get("terminal"):
        try:
            _gate_guidance_block(_gate_guidance_entries(state, state.get("round")))
        except ValueError as exc:
            return _refuse_cmd(session_dir, RULE_CMD, "order-render-refused",
                               phase=P_APPLY_FIXES, rnd=state.get("round"), attempt=None,
                               detail=str(exc))
    journal_entry = _journal_entry_for_commit(
        session_dir, RULE_CMD, "ruling-recorded", phase=phase, round=rnd, attempt=attempt,
        rulingFileSha256=file_sha, count=len(parsed))
    try:
        c = round_commit.begin(session_dir, "rule-record")
        _stage_state(c, session_dir, _canonical(state).encode("utf-8"))
        journal_path = os.path.join(session_dir, JOURNAL_FILE)
        c.add_journal_append(journal_path, journal_entry)
        c.run()
    except round_commit.CommitRefused as exc:
        return _commit_refused_response(session_dir, RULE_CMD, exc, phase=phase,
                                        rnd=rnd, attempt=attempt)
    response = {"ok": True, "recorded": len(parsed), "rulingFileSha256": file_sha}
    pending_after = state.get("pending")
    if (isinstance(pending_after, dict) and pending_after.get("action")
            and not state.get("terminal")):
        response.update(_next_response(session_dir, state, pending_after, RULE_CMD))
    return response


# --- the break-it test change -------------------------------------------------------------------
#
# While the verifiers' orders are out, the advisor may correct a break-it test whose run shows the
# test itself is broken (a syntax error, a wrong import), instead of letting the verifiers and the
# fixer work from it. `break-it-change` runs the corrected test, puts it on the staged finding and its
# ledger entry in place of the carried block, records the run beside the first, and clears the pending
# verifier orders so the next `next` re-emits them at a fresh attempt from the changed copies.

BREAK_IT_CHANGE_NOT_AT_VERIFIERS = "break-it-change-not-at-verifiers"
BREAK_IT_CHANGE_FINDING_UNKNOWN = "break-it-change-finding-unknown"
BREAK_IT_CHANGE_NO_TEST = "break-it-change-no-test"
BREAK_IT_CHANGE_WHY_MISSING = "break-it-change-why-missing"
BREAK_IT_CHANGE_CONTENT_UNREADABLE = "break-it-change-content-unreadable"
BREAK_IT_CHANGE_CONTENT_UNCHANGED = "break-it-change-content-unchanged"


def _break_it_change_target(state, ref):
    """``(staged id, staged finding, finding key)`` of the finding in ``_toVerify`` whose staged id or
    finding identity key is ``ref``; ``(None, None, None)`` when none is. A finding with no derivable
    key cannot be bound to its ledger entry or its runs, so it is not a target."""
    staged = state.get("_toVerify")
    if not isinstance(staged, list) or not isinstance(ref, str) or not ref:
        return None, None, None
    for numbered, finding in zip(verification.stage_ids(staged), staged):
        if not isinstance(finding, dict):
            continue
        key = _finding_identity_key(finding)
        if key and ref in (numbered["id"], key):
            return numbered["id"], finding, key
    return None, None, None


def _break_it_block_text(block, content):
    """The block text ``break_it.parse_block`` reads back as ``block``'s path and run with ``content``,
    laid out from ``break_it.BLOCK_TEMPLATE``, the grammar's one home."""
    template = break_it.BLOCK_TEMPLATE.split("\n")
    return "\n".join([template[0],
                      "%s %s" % (template[1].partition(" ")[0], block["path"]),
                      "%s %s" % (template[2].partition(" ")[0], block["run"]),
                      template[3], content])


def _rewrite_break_it_copy(copy_, text, record, why):
    """Put the changed block, its run record and the extra entry of its run list on one copy of a staged
    finding (the staged one, or its ledger entry), the run list reading after the entries it already holds."""
    runs = copy_.get(break_it.RUNS_FIELD)
    runs = list(runs) if isinstance(runs, list) else []
    runs.append(break_it.record_run(dict(record, file=copy_.get("file")), changed_why=why))
    # axis: the first change keeps the test role's version; a later change never replaces it
    original, _kind = break_it.carried_block(copy_)
    if original is not None and not isinstance(copy_.get(REVIEWER_TEST_FIELD), str):
        copy_[REVIEWER_TEST_FIELD] = original["content"]
    copy_["suggestion"] = text
    copy_[break_it.RUN_FIELD] = record
    copy_[break_it.RUNS_FIELD] = runs


def _carry_break_it_change_to_ledger(state, key, text, record, why):
    """Put the changed test on the finding's ledger entry, when it has one. Only the carried block, run and
    run list change; the entry's disposition family is never touched, and a state with no entry for ``key``
    is left byte for byte as it was."""
    rows, _fault = session_contract.read_disposition_ledger(state)
    if not any(_finding_identity_key(row) == key for row in rows):
        return
    ledger = _ensure_disposition_ledger_for_write(state)
    held = _ledger_index_by_key(ledger).get(key)
    if held is not None:
        _rewrite_break_it_copy(ledger[held], text, record, why)


def cmd_break_it_change(session_dir, finding, content_file, why):
    try:
        with round_records.session_lock(session_dir):
            upgrade = _upgrade_gate(session_dir, BREAK_IT_CHANGE_CMD)
            if upgrade is not None:
                return upgrade
            refusal = _commit_recover_or_refuse(session_dir, BREAK_IT_CHANGE_CMD)
            if refusal is not None:
                return refusal
            return _cmd_break_it_change_locked(session_dir, finding, content_file, why)
    except round_records.SessionLockHeld as held:
        return _lock_held_refusal(session_dir, BREAK_IT_CHANGE_CMD, held)


def _cmd_break_it_change_locked(session_dir, finding_ref, content_file, why):
    state, refusal = _load_driver_state(session_dir, BREAK_IT_CHANGE_CMD)
    if refusal is not None:
        return refusal
    rnd = state.get("round")
    pending = state.get("pending")
    # axis: the verb changes a test only while the verifiers' orders are the open step; at any other step the copies it rewrites are no longer the ones a verifier reads
    if state.get("step") != round_phases.P_VERIFIERS or state.get("terminal"):
        return _refuse_cmd(session_dir, BREAK_IT_CHANGE_CMD, BREAK_IT_CHANGE_NOT_AT_VERIFIERS,
                           phase=state.get("step"), rnd=rnd)
    staged_id, staged, key = _break_it_change_target(state, finding_ref)
    if staged is None:
        return _refuse_cmd(session_dir, BREAK_IT_CHANGE_CMD, BREAK_IT_CHANGE_FINDING_UNKNOWN,
                           phase=P_VERIFIERS, rnd=rnd)
    block, _kind = break_it.carried_block(staged)
    if not isinstance(staged.get(break_it.RUN_FIELD), dict) or block is None:
        return _refuse_cmd(session_dir, BREAK_IT_CHANGE_CMD, BREAK_IT_CHANGE_NO_TEST,
                           phase=P_VERIFIERS, rnd=rnd)
    if not isinstance(why, str) or not why.strip():
        return _refuse_cmd(session_dir, BREAK_IT_CHANGE_CMD, BREAK_IT_CHANGE_WHY_MISSING,
                           phase=P_VERIFIERS, rnd=rnd)
    why = why.strip()
    try:
        with open(content_file, "rb") as fh:
            content = fh.read().decode("utf-8")
    except (OSError, ValueError, TypeError):
        return _refuse_cmd(session_dir, BREAK_IT_CHANGE_CMD, BREAK_IT_CHANGE_CONTENT_UNREADABLE,
                           phase=P_VERIFIERS, rnd=rnd)
    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if sha == block["sha256"]:
        return _refuse_cmd(session_dir, BREAK_IT_CHANGE_CMD, BREAK_IT_CHANGE_CONTENT_UNCHANGED,
                           phase=P_VERIFIERS, rnd=rnd)
    config = state["config"]
    changed = {"path": block["path"], "run": block["run"], "content": content, "sha256": sha}
    repo_root, head = _break_it_scope(session_dir, state, config)
    record = break_it.run_one(repo_root, head, changed, scratch=session_dir,
                              interpreter=break_it.resolve_interpreter(config))
    text = _break_it_block_text(changed, content)
    # axis: the changed text and the old run's stamp are replaced together on the staged copy and its ledger entry, so what the verifiers read, what the fixer commits and what the record shows are the one test
    _rewrite_break_it_copy(staged, text, record, why)
    _carry_break_it_change_to_ledger(state, key, text, record, why)
    _record_round_append(state, "breakItRuns", dict(
        record, title=staged.get("title"), file=staged.get("file"),
        findingKey=key, changedWhy=why))
    _decision(state, "break-it-change",
              "the break-it test of %s (%s) changed: %s; the new run %s"
              % (staged_id, key, why, record.get("outcome")))
    superseded = pending.get("attempt") if isinstance(pending, dict) else None
    # axis: the verifiers' orders already out are dropped with the pending step, so the next `next` re-emits them from the changed copies
    if isinstance(pending, dict) and pending.get("phase") == P_VERIFIERS:
        state["pending"] = None
    journal_entry = _journal_entry_for_commit(
        session_dir, BREAK_IT_CHANGE_CMD, "changed", phase=P_VERIFIERS, round=rnd,
        attempt=superseded, supersededAttempt=superseded, finding=staged_id, findingKey=key,
        contentSha256=sha, runOutcome=record.get("outcome"))
    try:
        c = round_commit.begin(session_dir, "break-it-change")
        _stage_state(c, session_dir, _canonical(state).encode("utf-8"))
        c.add_journal_append(os.path.join(session_dir, JOURNAL_FILE), journal_entry)
        c.run()
    except round_commit.CommitRefused as exc:
        return _commit_refused_response(session_dir, BREAK_IT_CHANGE_CMD, exc, phase=P_VERIFIERS,
                                        rnd=rnd, attempt=superseded)
    return {"ok": True, "finding": staged_id, "run": record}


# --- the extra audit round ----------------------------------------------------------------------
#
# A session that was handed back at its round cap can be reopened once, by the advisor's order, for
# one more round: it audits the cap round's fixes and nothing else (no panel, scoped finder, gap
# sweep, fixer or verify), and it is labelled in the record. A PR gets at most one such round, across
# all its sessions. `_begin_extra_audit_round` is the only way a session begins round `cap + 1`.

EXTRA_AUDIT_STATE_UNREADABLE = "extra-audit-state-unreadable"
EXTRA_AUDIT_ORDER_INVALID = "extra-audit-order-invalid"
EXTRA_AUDIT_NOT_AT_CAP = "extra-audit-not-at-cap"
EXTRA_AUDIT_ALREADY_RUN = "extra-audit-already-run"
EXTRA_AUDIT_NOTHING_TO_AUDIT = "extra-audit-nothing-to-audit"
EXTRA_AUDIT_HEAD_UNRESOLVABLE = "extra-audit-head-unresolvable"
EXTRA_AUDIT_HEAD_MOVED = "extra-audit-head-moved"
EXTRA_AUDIT_RECEIPT_FAULTED = "extra-audit-receipt-faulted"
EXTRA_AUDIT_PR_HISTORY_UNREADABLE = "extra-audit-pr-history-unreadable"
EXTRA_AUDIT_ALREADY_RUN_ON_PR = "extra-audit-already-run-on-pr"
EXTRA_AUDIT_RESERVATION_FAILED = "extra-audit-reservation-failed"
EXTRA_AUDIT_SUPERSEDED_RECEIPT = "round-receipt.superseded-1.json"
_EXTRA_AUDIT_CAP_KINDS = ("round-cap", "fix-keeps-failing")
_RECEIPT_FINALIZED_MARKS = ("_receiptFinalized", "_receiptFault", "_receiptFaultClass")


def _checkout_head(session_dir, state):
    """The head of the checkout the session ran in, or None when git cannot name it."""
    repo_root = _resolve_repo_root(session_dir, state)
    if not repo_root:
        return None
    return store_core.run_git(repo_root, "rev-parse", "HEAD") or None


def _load_extra_audit_order(order_file):
    """(why, None) for an order file that is a JSON object with exactly one key, `why`, a non-blank
    string; else (None, what is wrong with it)."""
    try:
        with open(order_file, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        return None, "the order file is unreadable: %s" % exc
    if not isinstance(doc, dict) or set(doc) != {"why"}:
        return None, "the order file must be a JSON object with exactly one key, `why`"
    why = doc["why"]
    if not isinstance(why, str) or not why.strip():
        return None, "`why` must be a non-blank string"
    return why, None


def _cap_round_fix_unaudited(state):
    """True when the cap round applied a fix batch that no audit round has audited.

    A fix is audited in the round after the one that applied it, and `_advance_round` never begins a
    round past the cap. So a record of the cap round that carries a `fix`, in a session whose round is
    still the cap and whose last decision is the `round-cap` hand-back, names a fix whose audit round
    was refused at the boundary. A `fix-keeps-failing` hand-back is never this: it is found in an
    audit fold, in a round that holds no fix of its own (a fix would have advanced the round first),
    and its last decision is not `round-cap`."""
    rnd = state.get("round")
    if not (_is_plain_int(rnd) and rnd == _round_cap(state.get("config"))):
        return False
    rec = (state.get("rounds") or {}).get(str(rnd))
    if not (isinstance(rec, dict) and isinstance(rec.get("fix"), dict)):
        return False
    decisions = state.get("decisions")
    last = decisions[-1] if isinstance(decisions, list) and decisions else None
    return (isinstance(last, dict) and last.get("kind") == "round-cap" and last.get("round") == rnd
            and bool(_fix_batch_keys(state)))


def cmd_extra_audit(session_dir, order_file, by, pr, repo=None, readers=None):
    """Reopen a session handed back at its cap for one extra audit round, by the advisor's order.

    `readers` is a test seam for the record reader that checks the PR's earlier records."""
    try:
        with round_records.session_lock(session_dir):
            upgrade = _upgrade_gate(session_dir, EXTRA_AUDIT_CMD)
            if upgrade is not None:
                return upgrade
            refusal = _commit_recover_or_refuse(session_dir, EXTRA_AUDIT_CMD)
            if refusal is not None:
                return refusal
            return _cmd_extra_audit_locked(session_dir, order_file, by, pr, repo=repo,
                                           readers=readers)
    except round_records.SessionLockHeld as held:
        return _lock_held_refusal(session_dir, EXTRA_AUDIT_CMD, held)


def _extra_audit_pr_history_refusal(session_dir, state, pr, repo, readers):
    """(refusal, repo): the refusal for what the PR's earlier review records and reservations show, or
    None when none shows the round; repo is the repository the PR is read from."""
    import review_record  # noqa: E402 — lazy: the closure of this module stays unchanged
    if repo is None:
        try:
            resolved = review_record._readers(readers)["repo_name"](
                _resolve_repo_root(session_dir, state))
        except Exception:  # noqa: BLE001 — the seam is a foreign call; the history read then fails closed
            resolved = None
        if isinstance(resolved, str) and review_record._REPO_RE.fullmatch(resolved):
            repo = resolved
        else:
            # axis: a repository that cannot be resolved from the session checkout refuses, it never falls back to the ambient directory's
            return _refuse_cmd(session_dir, EXTRA_AUDIT_CMD, EXTRA_AUDIT_PR_HISTORY_UNREADABLE,
                               detail="the repository could not be resolved from the session checkout"), None
    history = review_record.extra_audit_history(pr, repo, readers, session_id=_meta_session_id(session_dir))
    # axis: PR history that cannot be read refuses, it never reads as "the round has not run" — see bite-proof record c1l4b_wo_a
    if not history.get("ok"):
        return _refuse_cmd(session_dir, EXTRA_AUDIT_CMD, EXTRA_AUDIT_PR_HISTORY_UNREADABLE,
                           detail=history.get("detail")), repo
    # axis: a PR whose earlier review record shows the extra audit round refuses a second one — see bite-proof record c1l4b_wo_a
    if history.get("ran"):
        return _refuse_cmd(session_dir, EXTRA_AUDIT_CMD, EXTRA_AUDIT_ALREADY_RUN_ON_PR,
                           sessionId=history.get("sessionId"), url=history.get("url")), repo
    return None, repo


def _supersede_receipt(session_dir):
    """(name, sha256, None) once `round-receipt.json` is copied byte for byte to its superseded name,
    or (None, None, None) when no receipt file exists; (None, None, detail) when the copy cannot be
    made or proven. The copy is atomic; a copy already there (a re-run after a crash) must hold the
    same bytes and is left as it is."""
    path = os.path.join(session_dir, RECEIPT_FILE)
    if not os.path.lexists(path):
        return None, None, None
    target = os.path.join(session_dir, EXTRA_AUDIT_SUPERSEDED_RECEIPT)
    try:
        with open(path, "rb") as fh:
            original = fh.read()
        digest = hashlib.sha256(original).hexdigest()
        if os.path.lexists(target):
            with open(target, "rb") as fh:
                held = hashlib.sha256(fh.read()).hexdigest()
            if held != digest:
                return None, None, ("%s already exists and differs from the current receipt"
                                    % EXTRA_AUDIT_SUPERSEDED_RECEIPT)
            return EXTRA_AUDIT_SUPERSEDED_RECEIPT, digest, None
        round_commit.atomic_write_bytes(target, original)
        with open(target, "rb") as fh:
            copied = hashlib.sha256(fh.read()).hexdigest()
    except OSError as exc:
        return None, None, "the receipt could not be copied: %s" % exc
    if copied != digest:
        try:
            os.unlink(target)
        except OSError:
            pass
        return None, None, "the copy of the receipt does not match its original"
    return EXTRA_AUDIT_SUPERSEDED_RECEIPT, digest, None


def _cmd_extra_audit_locked(session_dir, order_file, by, pr, repo=None, readers=None):
    ok, state = load_state(session_dir)
    if not ok or state is None:
        return _refuse_cmd(session_dir, EXTRA_AUDIT_CMD, EXTRA_AUDIT_STATE_UNREADABLE,
                           detail=state if not ok else "no state")
    why, order_fault = _load_extra_audit_order(order_file)
    if order_fault is not None:
        return _refuse_cmd(session_dir, EXTRA_AUDIT_CMD, EXTRA_AUDIT_ORDER_INVALID,
                           value=order_file, detail=order_fault)
    # A session that was ordered its extra round ends on that round's own terminal (converged, or a
    # hand-back that is not the cap's), never on the cap's, so this test comes before the at-cap one:
    # after it, the second order would otherwise meet "not at the cap" and never be named a repeat.
    # axis: a session that already ran its extra audit round refuses a second order — see bite-proof record c1l4b_wo_a
    if "extraAudit" in state:
        return _refuse_cmd(session_dir, EXTRA_AUDIT_CMD, EXTRA_AUDIT_ALREADY_RUN)
    decisions = state.get("decisions")
    last = decisions[-1] if isinstance(decisions, list) and decisions else None
    last_kind = last.get("kind") if isinstance(last, dict) else None
    if not (state.get("terminal") == "handed-back" and last_kind in _EXTRA_AUDIT_CAP_KINDS):
        return _refuse_cmd(session_dir, EXTRA_AUDIT_CMD, EXTRA_AUDIT_NOT_AT_CAP,
                           terminal=state.get("terminal"), lastDecision=last_kind)
    if not _cap_round_fix_unaudited(state):
        return _refuse_cmd(session_dir, EXTRA_AUDIT_CMD, EXTRA_AUDIT_NOTHING_TO_AUDIT)
    certified = _session_certified_head(session_dir, state)
    try:
        current = _checkout_head(session_dir, state)
    except Exception:  # noqa: BLE001 — a head that cannot be read is unresolvable, not a crash
        current = None
    if not certified or not current:
        return _refuse_cmd(session_dir, EXTRA_AUDIT_CMD, EXTRA_AUDIT_HEAD_UNRESOLVABLE,
                           certifiedHead=certified, checkoutHead=current)
    # axis: a checkout that moved off the session's certified head refuses before any write — see bite-proof record c1l4b_wo_a
    if certified != current:
        return _refuse_cmd(session_dir, EXTRA_AUDIT_CMD, EXTRA_AUDIT_HEAD_MOVED,
                           certifiedHead=certified, checkoutHead=current)
    if state.get("_receiptFinalized"):
        fault = _verify_terminal_receipt(session_dir)
        if fault:
            return _refuse_cmd(session_dir, EXTRA_AUDIT_CMD, EXTRA_AUDIT_RECEIPT_FAULTED,
                               detail=str(fault))
    refusal, repo = _extra_audit_pr_history_refusal(session_dir, state, pr, repo, readers)
    if refusal is not None:
        return refusal
    # axis: the allowance is reserved on the PR after every local check and before the receipt copy and the state commit, so a second session sees it — a reservation that cannot be posted refuses with nothing written
    import review_record  # noqa: E402 — lazy: the closure of this module stays unchanged
    reserved = review_record.reserve_extra_audit(pr, repo, _meta_session_id(session_dir), why, readers)
    if not reserved.get("ok"):
        return _refuse_cmd(session_dir, EXTRA_AUDIT_CMD, EXTRA_AUDIT_RESERVATION_FAILED,
                           detail=reserved.get("detail"))
    # axis: after posting, the verb re-reads the PR and proceeds only when no other session's reservation or round record has a lower comment id than its own — the first reservation posted wins; a loser leaves its reservation in place, and a failed re-read refuses with nothing written locally
    elected = review_record.extra_audit_history(pr, repo, readers, session_id=_meta_session_id(session_dir),
                                                own_id=reserved.get("id"))
    if not elected.get("ok"):
        return _refuse_cmd(session_dir, EXTRA_AUDIT_CMD, EXTRA_AUDIT_PR_HISTORY_UNREADABLE,
                           detail=elected.get("detail"))
    if elected.get("ran"):
        return _refuse_cmd(session_dir, EXTRA_AUDIT_CMD, EXTRA_AUDIT_ALREADY_RUN_ON_PR,
                           sessionId=elected.get("sessionId"), url=elected.get("url"))
    superseded, superseded_sha, copy_fault = _supersede_receipt(session_dir)
    if copy_fault is not None:
        return _refuse_cmd(session_dir, EXTRA_AUDIT_CMD, EXTRA_AUDIT_RECEIPT_FAULTED,
                           detail=copy_fault)
    config = state.get("config") or {}
    new_round = _round_cap(config) + 1
    state["extraAudit"] = {"why": why, "by": by, "round": new_round,
                           "orderedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                           "supersededReceipt": superseded, "supersededReceiptSha256": superseded_sha}
    _set_terminal(state, None)
    state["certification"] = None
    state["pending"] = None
    for mark in _RECEIPT_FINALIZED_MARKS:
        state.pop(mark, None)
    _decision(state, "extra-audit-ordered",
              "extra audit round %d ordered by %s: %s" % (new_round, by, why))
    _begin_extra_audit_round(state, config)
    journal_entry = _journal_entry_for_commit(
        session_dir, EXTRA_AUDIT_CMD, "accepted", round=new_round, by=by, pr=pr,
        supersededReceiptSha256=superseded_sha)
    try:
        c = round_commit.begin(session_dir, "extra-audit-order")
        _stage_state(c, session_dir, _canonical(state).encode("utf-8"))
        c.add_journal_append(os.path.join(session_dir, JOURNAL_FILE), journal_entry)
        c.run()
    except round_commit.CommitRefused as exc:
        return _commit_refused_response(session_dir, EXTRA_AUDIT_CMD, exc)
    return {"ok": True, "round": new_round, "supersededReceipt": superseded}


def _fetch_ci_run(repo_root, run_id):
    """Fetch one GitHub Actions run through `gh`. Returns (run dict, None) or (None, reason)."""
    argv = ["gh", "api", "repos/{owner}/{repo}/actions/runs/%s" % run_id]
    try:
        done = subprocess.run(argv, cwd=repo_root, capture_output=True, timeout=60,
                              stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, "gh api failed: %s" % exc
    if done.returncode != 0:
        return None, "gh api exited %s: %s" % (done.returncode,
                                               done.stdout[-200:] + done.stderr[-200:])
    try:
        run = json.loads(done.stdout)
    except ValueError:
        return None, "gh api returned non-JSON"
    return (run, None) if isinstance(run, dict) else (None, "gh api returned a non-object")


def _ci_verify_run_refusal(session_dir, state, artifact, resolution):
    """(token, detail) when a `ci-exact-head` verify artifact is not backed by the fetched run on the
    verified head; None when it is, and None for a local verify (which never fetches)."""
    if artifact.get("via") != "ci-exact-head":
        return None
    ci = artifact["ci"]
    verified_head, head_err = resolution
    repo_root = _resolve_repo_root(session_dir, state)
    # axis: an unresolved head or root is refused, never compared against None — see bite-proof record wo_b_2072_ci_verify
    if head_err or not verified_head or not repo_root:
        return "ci-verify-run-unreadable", head_err or "verified head or repo root unresolvable"
    # axis: the substitute must be the project's declared CI workflow, never a workflow the submitter names — see bite-proof record wo_b_2072_ci_verify
    import review_record  # noqa: E402 — lazy: the closure of this module stays unchanged
    declared_kind, declared = review_record._ci_workflow(repo_root)
    if declared_kind != "declared" or not declared:
        return "ci-verify-workflow-unconfigured", "the project declares no readable ciWorkflow (%s)" % declared_kind
    if ci["workflow"] != declared:
        return "ci-verify-workflow-mismatch", "claimed workflow %r is not the project's declared %r" % (ci["workflow"], declared)
    try:
        run, err = _fetch_ci_run(repo_root, ci["runId"])
    except Exception as exc:  # noqa: BLE001 — the seam is a foreign call; any failure is unreadable
        run, err = None, "%s: %s" % (type(exc).__name__, exc)
    # axis: a run that cannot be read is refused, never compared — see bite-proof record wo_b_2072_ci_verify
    if not isinstance(run, dict) or any(k not in run for k in ("id", "name", "head_sha", "status", "conclusion")):
        return "ci-verify-run-unreadable", err or "the fetched run lacks id, name, head_sha, status or conclusion"
    # axis: the run is the claimed run on the claimed and the verified head — see bite-proof record wo_b_2072_ci_verify
    # the claim's hex shape was already accepted upstream; GitHub reports lowercase, so a correct claim in uppercase is folded to lowercase before comparing
    if run["head_sha"] != ci["headSha"].lower():
        return "ci-verify-sha-mismatch", "run %s ran on %s, not the claimed %s" % (run["id"], run["head_sha"], ci["headSha"])
    if run["head_sha"] != verified_head:
        return "ci-verify-sha-mismatch", "run %s ran on %s, not the verified head %s" % (run["id"], run["head_sha"], verified_head)
    if str(run["id"]) != str(ci["runId"]):
        return "ci-verify-sha-mismatch", "fetched run id %s is not the claimed runId %s" % (run["id"], ci["runId"])
    # axis: the run is the claimed workflow — see bite-proof record wo_b_2072_ci_verify
    # construction bound (E9c): the `or run["name"] != declared` clause cannot reject on its own — the earlier `ci["workflow"] == declared` check already guarantees `ci["workflow"] == declared`, so it is subsumed by `run["name"] != ci["workflow"]`; see bite-proof record wo_b_2072_ci_verify (E9c)
    # what would make it provable: moving this comparison ahead of (or removing) the `ci["workflow"] != declared` refusal above, so a run name could differ from `declared` while equal to the claim
    # its separate protection is UNVERIFIED: no test can show this clause rejecting an input the first clause does not
    if run["name"] != ci["workflow"] or run["name"] != declared:
        return "ci-verify-workflow-mismatch", "run %s is workflow %r, not the claimed %r or the declared %r" % (run["id"], run["name"], ci["workflow"], declared)
    # axis: only a completed run that concluded `success`, as claimed, stands in — see bite-proof record wo_b_2072_ci_verify
    if run["status"] != "completed":
        return "ci-verify-conclusion-mismatch", "run %s is %r, not completed" % (run["id"], run["status"])
    if run["conclusion"] != ci["conclusion"]:
        return "ci-verify-conclusion-mismatch", "run %s concluded %r, not the claimed %r" % (run["id"], run["conclusion"], ci["conclusion"])
    if run["conclusion"] != "success":
        return "ci-verify-conclusion-mismatch", "run %s concluded %r, not success" % (run["id"], run["conclusion"])
    return None


def cmd_submit(session_dir, phase, attempt, state_hash_arg, artifact, _via_advance=False,
               _durable_record=None, _landed_payload_sha256=None):
    """Validate the echo (phase/attempt/hash must match the pending step), fold the artifact, and
    advance. Stale/mismatched → rejected {ok: false} (exit 0). An exact duplicate of an
    already-accepted submit → idempotent {ok: true, duplicate: true}.

    THE ONE FOLD CHOKEPOINT. `advance` (#723) assembles its artifact from the durable per-seat
    records and then folds it THROUGH HERE (`_via_advance=True`, a library-only argument the CLI
    never passes), so every fence this function already enforces — echo, state-hash, the #845 panel
    seat-key guard, the #885 verify/audit shape guards, the terminal receipt gate — still runs, and
    `_fold` keeps exactly the two callers its census pins.

    `_via_advance` is also the interleave fence: once a session has been driven by `advance`, a HAND
    `submit` is refused (`advance-submit-interleaved`) and journalled, because the two paths keep
    different bookkeeping (the record layer's roster/completeness proof vs. a caller-supplied
    artifact) and mixing them within one session silently certifies a phase whose seats were never
    recorded. The fence is per-SESSION rather than the work order's per-PHASE wording: strictly
    stronger, and it never permits anything the per-phase rule forbids.

    `_durable_record` (library-only, like `_via_advance`) is
    `{"storePath": str, "envelope": dict, "journal": dict}` — the orchestrator-fulfilled fold's
    durable seat record (#1037), added to THIS fold's commit so the record and the state advance
    land atomically. Every early return above the commit leaves it unwritten, which is the correct
    reading in each case: nothing folded, so there is no fold to reconstruct. In particular the
    DUPLICATE return leaves it unwritten — its one caller reaches this only after refusing
    `landing-ambiguous` on any record already in the slot, so a duplicate there means the record
    exists already, never that one is owed.

    `foldLanded` is authoritative on `ok: true` answers: present means the fold landed; absent on
    an `ok: true` answer means it did not. On `ok: false` answers the marker is not a landed/not-
    landed signal except on the `commit-cleanup-failed` path: `round_commit.run()` fsyncs its
    `DONE` marker — the fold is durable — and then cleanup raises, and the answer carries
    `foldLanded: True`. Callers must not read its absence on other `ok: false` answers as not-landed
    evidence.

    `_landed_payload_sha256` (library-only) is the hash of the `run-verify` payload as it landed,
    which `_advance_locked` fills from the stored envelope on the seat-record route — the assembled
    artifact keeps only some of the payload's fields, so its own hash is not the landed payload's.
    Absent, the artifact's own hash stands in (the bare route), so a caller that forgets it fails
    closed.

    On the verify phase the head the next panel's diff is derived from is resolved before the fold
    and forwarded to it; a resolution failure does not refuse the submit. Through `advance`, a
    non-CI verify result folds only when the journal holds the driver's own `run-verify` row for it
    (`verify-landing-not-driver-written`); a hand `submit` is not subject to that check."""
    try:
        with round_records.session_lock(session_dir):
            upgrade = _upgrade_gate(session_dir, "submit")
            if upgrade is not None:
                return upgrade
            refusal = _commit_recover_or_refuse(session_dir, "submit")
            if refusal is not None:
                return refusal
            prep = _cmd_submit_prepare(session_dir, phase, attempt, state_hash_arg, artifact,
                                       _via_advance=_via_advance)
            if not prep.get("_fold_ready"):
                return prep
            state = prep["state"]
            round_no = prep["round_no"]
            art_hash = prep["art_hash"]
            if phase == P_VERIFY:
                try:
                    resolution = _verified_head_at_fold(session_dir, state)
                except OSError as exc:
                    resolution = (None, "verified head: %s" % exc)
                # axis: the run check is called at the one submit chokepoint — see bite-proof record wo_b_2072_ci_verify
                refusal = _ci_verify_run_refusal(session_dir, state, artifact, resolution)
                if refusal:
                    _journal_append(session_dir, {"cmd": "submit", "phase": phase, "round": round_no,
                                                  "attempt": attempt, "outcome": refusal[0]})
                    return {"ok": False, "reason": refusal[0], "detail": refusal[1]}
                if _via_advance and not (isinstance(artifact, dict)
                                         and artifact.get("via") == "ci-exact-head"):
                    landed_sha = (_landed_payload_sha256 if _landed_payload_sha256 is not None
                                  else round_records.payload_sha256(artifact))
                    # axis: a non-CI verify result folds through advance only against the driver's own journal row for this round, attempt and payload hash — see bite-proof record wo_2133_run_verify
                    detail = _verify_landing_not_driver_written(session_dir, round_no, attempt,
                                                                landed_sha)
                    if detail is not None:
                        _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                                      "round": round_no, "attempt": attempt,
                                                      "outcome": VERIFY_LANDING_NOT_DRIVER_WRITTEN})
                        return {"ok": False, "reason": VERIFY_LANDING_NOT_DRIVER_WRITTEN,
                                "detail": detail}
            else:
                resolution = None
            if _via_advance and phase == P_VERIFIERS and isinstance(artifact, dict):
                # Durable path: the executed vendor is the runner's execution evidence, carried by the
                # assembled artifact. Never the driver's selection; absent evidence stays an empty
                # claim, which `_fold_verifiers` treats as a missing vendor claim.
                artifact = dict(artifact)
                artifact.setdefault("verifierSeatVendors", {})
            elif phase == P_VERIFIERS and isinstance(artifact, dict):
                # A hand artifact never carries durable execution evidence: its own per-seat
                # provenance map is a courier claim, so it is dropped and the `verifierVendor`
                # claim check decides.
                artifact = {k: v for k, v in artifact.items()
                            if k not in ("verifierSeatVendors", "verifierSeatProvenance")}
            try:
                _fold(state, state["config"], phase, artifact, session_dir=session_dir,
                      verified_head_resolution=resolution, fix_commits=prep.get("fix_commits"))
            except DispositionLedgerOwnerRefusal:
                _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                              "round": round_no, "attempt": attempt,
                                              "outcome": DISPOSITION_LEDGER_OWNER_UNRECOGNIZED_CAUSE})
                return {"ok": False, "reason": DISPOSITION_LEDGER_OWNER_UNRECOGNIZED_CAUSE}
            if _via_advance:
                state["_advanceUsed"] = True
            state["lastAccepted"] = {"phase": phase, "attempt": attempt, "round": round_no,
                                     "artifactHash": art_hash}
            records_payload = _round_records_payload(state, state["config"])
            round_records_sidecar = None
            if records_payload["outcome"] == "ready":
                rr_path = records_payload["path"]
                rr_bytes = review_memory.records_bytes(records_payload["records"])
                round_records_sidecar = (rr_path, rr_bytes)
            journal_entry = _journal_entry_for_commit(session_dir, "submit", "accepted",
                                                      phase=phase, round=round_no, attempt=attempt)
            orphan_journal = None
            orphan_seats = prep.get("orphan_seats_found")
            if isinstance(orphan_seats, list) and orphan_seats:
                orphan_journal = {
                    "cmd": "submit",
                    "outcome": "record-orphans-ignored",
                    "session": _meta_session_id(session_dir),
                    "fault": FAULT_CALLER,
                    "phase": phase,
                    "round": round_no,
                    "attempt": attempt,
                    "seats": orphan_seats,
                }
            try:
                c = round_commit.begin(session_dir, "submit-accept")
                _stage_state(c, session_dir, _canonical(state).encode("utf-8"))
                if round_records_sidecar is not None:
                    rr_path, rr_bytes = round_records_sidecar
                    c.add_external_sidecar(rr_bytes, lambda p=rr_path: p,
                                           target_kind=round_commit.SIDECAR_KIND_ROUND_RECORDS)
                # axis: ATOMICITY with the fold — that the record cannot land without the state
                # advance, or the advance without the record. Asserting the record merely exists
                # after a successful fold would pass against a second, separate commit.
                if _durable_record is not None:
                    c.add_replace_file(
                        _durable_record["storePath"],
                        round_records.canonical(_durable_record["envelope"]).encode("utf-8"))
                c.add_journal_append(os.path.join(session_dir, JOURNAL_FILE), journal_entry)
                if _durable_record is not None:
                    # The record and its journal identity ride the SAME commit, so `reconcile`
                    # never sees this slot as a two-commit-window remnant (neither `reappend`
                    # nor `journalOrphan`).
                    c.add_journal_append(os.path.join(session_dir, JOURNAL_FILE),
                                         _durable_record["journal"])
                if orphan_journal is not None:
                    c.add_journal_append(os.path.join(session_dir, JOURNAL_FILE), orphan_journal)
                c.run()
            except round_commit.CommitRefused as exc:
                extra = {}
                if exc.reason == "commit-cleanup-failed":
                    # submit-accept only: run() fsyncs DONE before _cleanup_commit can raise, so the
                    # fold is durable here. Do NOT generalize — recover() can also raise
                    # commit-cleanup-failed while deleting an unsealed commit (no fold landed), but
                    # cmd_submit's recover goes through _commit_recover_or_refuse which rewrites that
                    # to commit-recovery-failed, and begin() only raises invalid-commit-id.
                    extra["foldLanded"] = True
                return _commit_refused_response(session_dir, "submit", exc, phase=phase,
                                                rnd=round_no, attempt=attempt, **extra)
            if state.get("terminal"):
                fail = _terminal_receipt_gate(session_dir, state)
                if fail:
                    resp = _receipt_fault_response(fail)
                    resp["foldLanded"] = True
                    return resp
            # foldLanded marks a landed fold. It is authoritative on `ok: true` answers; its absence
            # there is the fail-closed default covering every future early return above the commit.
            # On an `ok: false` answer absence proves nothing — see the docstring's foldLanded note.
            return {"ok": True, "round": round_no, "phase": phase, "nextStep": state.get("step"),
                    "foldLanded": True}
    except round_records.SessionLockHeld as held:
        return _lock_held_refusal(session_dir, "submit", held)


def _cmd_submit_prepare(session_dir, phase, attempt, state_hash_arg, artifact, _via_advance=False):
    ok, loaded = load_state(session_dir)
    if not ok:
        fault_reason, fault, _detail = _state_load_fault(session_dir)
        _journal_append(session_dir, {"cmd": "submit", "phase": phase, "round": None,
                                      "attempt": attempt, "outcome": fault_reason, "fault": fault})
        return {"ok": False, "reason": loaded}
    if loaded is None:
        _journal_append(session_dir, {"cmd": "submit", "phase": phase, "round": None,
                                      "attempt": attempt, "outcome": "no-state"})
        return {"ok": False, "reason": "no loop-state.json — call next first"}
    state = loaded
    if _cap_blocks_loaded(state, state["config"]):
        pending = {"action": P_TERMINAL, "round": state["round"], "phase": P_TERMINAL,
                   "attempt": 0,
                   "payload": {"verdict": state["terminal"],
                               "certification": state.get("certification")}}
        state["pending"] = pending
        save_state(session_dir, state)
        _journal_append(session_dir, {"cmd": "submit", "phase": phase, "round": state["round"],
                                      "attempt": attempt, "outcome": "loaded-cap-hand-back"})
        fault = _terminal_receipt_gate(session_dir, state)
        if fault:
            return _receipt_fault_response(fault)
        return {"ok": True, "round": state["round"], "phase": phase, "nextStep": P_TERMINAL}
    if not _via_advance and state.get("_advanceUsed"):
        _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                      "round": (state.get("pending") or {}).get("round"),
                                      "attempt": attempt, "outcome": "advance-submit-interleaved",
                                      "fault": FAULT_CALLER, "session": _meta_session_id(session_dir)})
        return {"ok": False, "reason": "advance-submit-interleaved"}
    art_hash = _sha256(_canonical(artifact if artifact is not None else {}))
    prior = state.get("lastAccepted")
    is_duplicate = bool(prior and prior.get("phase") == phase and prior.get("attempt") == attempt
                        and prior.get("artifactHash") == art_hash)

    # CLASS invariant (#507, third audit): while the session is ALREADY at its terminal phase on
    # entry, NO submit answer — including a duplicate/replayed submit — may return ok without a FRESH
    # on-disk receipt verification. Route every terminal-phase submit through the gate before any
    # answer; a persisted or freshly-detected fault answers receipt-fault nonzero (the duplicate flag
    # preserved in the detail for honesty), never a masked ok. (The terminating submit itself reaches
    # terminal via THIS call's fold below, gated at its own site.)
    if state.get("terminal"):
        fault = _terminal_receipt_gate(session_dir, state)
        if fault:
            _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                          "round": prior.get("round") if prior else None,
                                          "attempt": attempt,
                                          "outcome": "duplicate-receipt-fault" if is_duplicate
                                          else "terminal-receipt-fault"})
            resp = _receipt_fault_response(
                ("duplicate submit replay; %s" % fault) if is_duplicate else fault)
            if is_duplicate:
                resp["duplicate"] = True
                resp["foldLanded"] = True
            return resp

    # duplicate detection (an already-accepted submit re-sent — its state hash is now stale, but the
    # phase/attempt/artifact triple identifies it as an exact replay). At a terminal phase the gate
    # above already re-verified the receipt, so this only answers ok when the receipt is intact.
    if is_duplicate:
        _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                      "round": prior.get("round"), "attempt": attempt,
                                      "outcome": "duplicate"})
        # foldLanded marks a landed fold. It is authoritative on `ok: true` answers; its absence
        # there is the fail-closed default covering every future early return above the commit.
        # On an `ok: false` answer absence proves nothing — see the docstring's foldLanded note.
        return {"ok": True, "duplicate": True, "foldLanded": True}

    pending = state.get("pending")
    if not pending:
        _journal_append(session_dir, {"cmd": "submit", "phase": phase, "round": None,
                                      "attempt": attempt, "outcome": "no-pending"})
        return {"ok": False, "reason": "no pending step — call next first"}
    if phase != pending.get("phase") or attempt != pending.get("attempt"):
        _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                      "round": pending.get("round"), "attempt": attempt,
                                      "outcome": "echo-mismatch"})
        return {"ok": False, "reason": "phase/attempt echo does not match the pending step"}
    if (not _via_advance and isinstance(phase, str) and phase.startswith("dispatch-")):
        # axis: a hand submit of a dispatch phase over a damaged journal is refused; the advance-driven fold is not
        if _journal_damaged(session_dir):
            _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                          "round": pending.get("round"), "attempt": attempt,
                                          "outcome": JOURNAL_DAMAGED_CAUSE})
            return {"ok": False, "reason": JOURNAL_DAMAGED_CAUSE,
                    "detail": JOURNAL_DAMAGED_DETAIL}
    # The state-hash echo is the anti-stale/fork fence — REQUIRED (#507 v13). A first-time fold with
    # no hash is refused (a missing hash must never fold fail-open); exact replays are already
    # returned as duplicates above, before this point.
    if state_hash_arg is None:
        _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                      "round": pending.get("round"), "attempt": attempt,
                                      "outcome": "missing-hash"})
        return {"ok": False, "reason": "state-hash is required — refusing a fold without the "
                                       "expected hash echo (the anti-stale/fork fence)"}
    current_hash = state_hash(state)
    if state_hash_arg != current_hash:
        _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                      "round": pending.get("round"), "attempt": attempt,
                                      "outcome": "hash-mismatch"})
        return {"ok": False, "reason": "state-hash mismatch — the state moved under a stale submit"}

    if session_contract.disposition_ledger_owner_classification(state) == (
        session_contract.DISPOSITION_LEDGER_OWNER_UNRECOGNIZED
    ):
        _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                      "round": pending.get("round"), "attempt": attempt,
                                      "outcome": DISPOSITION_LEDGER_OWNER_UNRECOGNIZED_CAUSE})
        return {"ok": False, "reason": DISPOSITION_LEDGER_OWNER_UNRECOGNIZED_CAUSE}

    # #845: the panel seat-key invariant, at the chokepoint. A `seats` map keyed by findings-file
    # stems instead of `payload.dimensions` submits `ok` today and fails phases later with empty
    # clusters and every seat `missing` — four recorded occurrences. Refuse HERE, before the fold, so
    # the pending step survives and recovery is a plain re-keyed resubmit on the same attempt/hash.
    if phase == P_PANEL:
        fault = panel_seat_key_fault(_panel_dimensions(state["config"]), artifact)
        if fault:
            _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                          "round": pending.get("round"), "attempt": attempt,
                                          "outcome": "seat-key-mismatch"})
            return {"ok": False, "reason": fault}

    # #885: the same chokepoint refusal for the two OTHER submits whose wrong-shape artifacts cost a
    # build its certification receipt — verify (`{exitCode, passed}` instead of `{"result": "pass"}`)
    # and audits (`newIssue` instead of `newIssues`). Both fold into a TERMINAL, journalled,
    # immutable state, so the loss is unrecoverable once folded; refusing here keeps the pending step
    # alive and makes recovery a corrected resubmit. The journalled outcome is a NON-TERMINAL refusal
    # event — the loop is never halted by a shape fault.
    #
    # axis (both wirings): that the refusal reaches the SUBMIT path — a guard that exists but is not
    # called at the chokepoint protects nothing. Placed AFTER the echo/hash fences so a stale or
    # forked submit keeps its own reason, and BEFORE the fold so no state mutates on a refusal.
    if phase == P_VERIFY:
        fault = verify_result_fault(artifact)
        if fault:
            _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                          "round": pending.get("round"), "attempt": attempt,
                                          "outcome": "verify-result-shape"})
            return {"ok": False, "reason": fault}
    if phase == P_AUDITS:
        # Ruling-shape first: `results` entries must be usable before manifest keys are judged.
        fault = audit_results_fault(artifact, state.get("_auditTargets") or [])
        if fault:
            _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                          "round": pending.get("round"), "attempt": attempt,
                                          "outcome": "audit-ruling-shape"})
            return {"ok": False, "reason": fault}
        fault = collection_manifest_fault(artifact, state.get("_auditTargets"))
        if fault:
            _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                          "round": pending.get("round"), "attempt": attempt,
                                          "outcome": "collection-manifest-key"})
            return {"ok": False, "reason": fault}
    if (not _via_advance and (phase in _NONPANEL_REVIEWER_PHASES or phase == P_SYNTHESIS)
            and _adapters().missing_policy(phase) == _adapters().MISSING_REFUSE_FOLD
            and _nonpanel_unseatable(state, session_dir, phase)):
        # No reviewer outside the makers' families can be seated: no order was emitted for this
        # phase, so a hand artifact for it is not a review that ran. Refuse the fold (the advance
        # path's refuse-fold policy for a single-seat phase) rather than let an empty artifact
        # converge the round.
        _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                      "round": pending.get("round"), "attempt": attempt,
                                      "outcome": "nonpanel-reviewer-unseatable"})
        return {"ok": False, "reason": "nonpanel-reviewer-unseatable",
                "detail": "no reviewer outside the makers' families can be seated for %s; no order "
                          "was emitted and a submitted artifact is not a review that ran" % phase}
    if not _via_advance and phase in (P_GAPSWEEP, P_SECOND_TEST, P_SCOPED) and not isinstance(artifact, dict):
        return {"ok": False, "reason": "nonpanel-reviewer-unauthenticated",
                "detail": "%s artifact must be a JSON object carrying `reviewerVendor`" % phase}
    if not _via_advance and phase in (P_GAPSWEEP, P_SECOND_TEST, P_SCOPED):
        # A hand artifact for a finder phase is a review by the vendor it claims. When the selection
        # replaced the reviewer engine, the claim (`reviewerVendor`) is required and must equal the
        # vendor the dispatch recorded at emission — the verifier hand-submit rule, one helper.
        claim_fault = _finder_hand_claim_fault(state, session_dir, phase, artifact)
        if claim_fault is not None:
            _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                          "round": pending.get("round"), "attempt": attempt,
                                          "outcome": "nonpanel-reviewer-unauthenticated"})
            return {"ok": False, "reason": "nonpanel-reviewer-unauthenticated",
                    "detail": claim_fault}
    if phase == P_VERIFIERS:
        fault = verifier_results_fault(artifact)
        if fault:
            _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                          "round": pending.get("round"), "attempt": attempt,
                                          "outcome": "verifier-results-shape"})
            return {"ok": False, "reason": fault}
        fault = verifier_drop_staged_id_fault(state, artifact)
        if fault:
            _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                          "round": pending.get("round"), "attempt": attempt,
                                          "outcome": "staged-id-unresolvable"})
            return {"ok": False, "reason": fault}
    if phase == P_SYNTHESIS:
        fault = synthesis_results_fault(artifact)
        if fault:
            _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                          "round": pending.get("round"), "attempt": attempt,
                                          "outcome": "synthesis-results-shape"})
            return {"ok": False, "reason": fault}
        fault = synthesis_staged_id_fault(state, artifact, session_dir)
        if fault:
            _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                          "round": pending.get("round"), "attempt": attempt,
                                          "outcome": "staged-id-unresolvable"})
            return {"ok": False, "reason": fault}
    fix_commits = None
    if phase == P_APPLY_FIXES:
        # A hand submission never reaches the payload contract, so the report's shape is checked
        # here, and what it claims is committed is checked against git, before the pending step is
        # consumed: a refusal leaves the step pending for a corrected resubmit.
        fault = _adapters().orchestrator_payload_fault(phase, artifact)
        if fault:
            _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                          "round": pending.get("round"), "attempt": attempt,
                                          "outcome": "apply-fixes-shape"})
            return {"ok": False, "reason": fault}
        detail, fix_commits = _apply_fixes_commit_fault(state, state["config"], artifact)
        if detail is not None:
            _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                          "round": pending.get("round"), "attempt": attempt,
                                          "outcome": FIX_REFUSED_REASON, "detail": detail})
            return {"ok": False, "reason": FIX_REFUSED_REASON, "detail": detail}
    # #977: the record-submit interleave fence — mirror image of `advance-submit-interleaved`.
    # `cmd_submit` never reads the durable store, so `record-result` (or `--sweep`) followed by a
    # HAND submit silently discards recorded seats and can certify an incomplete panel while
    # answering `ok`. Refuse HERE, before the fold, so the pending step survives; fold through
    # `advance` instead (or supersede a `seat-missing` slot on a refuse-fold phase, then advance).
    orphan_seats_found = None
    if not _via_advance:
        rnd = pending.get("round")
        # Only adapter phases carry durable store records. Resolve without journaling:
        # `_roster_of` would append a spurious `roster-unavailable` refusal row on lookup failure.
        if phase in _adapters().ADAPTER_PHASES:
            roster, roster_reason = _adapters().roster_for(
                phase, state, state.get("config") or {})
            if roster_reason is None and isinstance(roster, (list, tuple)):
                roster = [s for s in roster if isinstance(s, str)]
                # axis: REFUSAL of a hand fold when durable records exist at the pending slot — not
                # whether the caller's artifact is correct, and not whether the records are complete.
                found = _durable_slot_records(session_dir, rnd, phase, attempt, roster)
                if found:
                    if state.get("_submitUsed"):
                        # Session latch is authoritative — the fence defers. Orphan records at this
                        # slot are legacy-only (pre-latch sessions); record-result / record-missing
                        # latches prevent new records in hand-path sessions going forward.
                        orphan_seats_found = list(found)
                        state.setdefault("rounds", {}).setdefault(str(rnd), {})[
                            "recordOrphansIgnored"] = orphan_seats_found
                    else:
                        detail = ("durable seat record(s) at attempt %s for slot(s) %s — the durable-record "
                                  "path folds through `advance`; a hand submit ignores them. A slot recorded "
                                  "missing on a refuse-fold phase must first be replaced with a real result "
                                  "(`record-result --supersede --expect-sha256 …`) before `advance` can fold."
                                  % (attempt, ", ".join(found)))
                        _journal_append(session_dir, {"cmd": "submit", "phase": phase, "round": rnd,
                                                      "attempt": attempt,
                                                      "outcome": "record-submit-interleaved",
                                                      "fault": FAULT_CALLER,
                                                      "session": _meta_session_id(session_dir)})
                        return {"ok": False, "reason": "record-submit-interleaved", "detail": detail,
                                "seats": found}

    # accept: clear the pending, then fold through cmd_submit (the fold chokepoint).
    round_no = pending.get("round")
    state["pending"] = None
    if not _via_advance and _state_version(state) == STATE_SCHEMA_VERSION:
        # The other half of the interleave fence: a v3 session that has taken a HAND submit refuses
        # `advance` from here on. Only stamped on v3 state — a v2 state's dict is never touched.
        state["_submitUsed"] = True
    return {"_fold_ready": True, "state": state, "round_no": round_no, "art_hash": art_hash,
            "orphan_seats_found": orphan_seats_found, "fix_commits": fix_commits}


def _write_receipt(session_dir, state):
    """Write the terminal receipt atomically. ReceiptWriteError PROPAGATES — a receipt-write failure
    is itself a receipt defect the CLI must surface (see _finalize_receipt), never a silent swallow
    (#507 v14)."""
    receipt = build_receipt(state, session_dir)
    path = os.path.join(session_dir, RECEIPT_FILE)
    try:
        round_commit.atomic_write_bytes(
            path, (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    except OSError as exc:
        raise ReceiptWriteError(str(exc)) from exc
    return receipt


def _verify_terminal_receipt(session_dir):
    """Re-read the on-disk terminal receipt (FRESH from disk, never a cached copy) and re-check its
    integrity: readable, `validate_receipt`-shaped, non-empty scriptRan, and NO durable journal
    fault marker. Returns a reason string on ANY fault, else None.

    Shared by `_finalize_receipt` (the post-write check on the terminating fold / first emission) and
    the terminal-`next` re-check (below). A REPLAYED terminal `next` — a `next` on a session already
    at its terminal step — re-emits the stored pending WITHOUT re-running `_finalize_receipt`, so a
    receipt fault recorded or surfaced AFTER the receipt was first written (a fault-marker file, or a
    round-receipt.json that has become unreadable/invalid since) would otherwise be masked by the
    replay's `ok`. Re-checking here on every terminal `next` closes that hole (#507)."""
    try:
        with open(os.path.join(session_dir, RECEIPT_FILE), encoding="utf-8") as fh:
            on_disk = json.load(fh)
    except (OSError, ValueError) as exc:
        return ReceiptFault(
            "terminal receipt unreadable (%s) — cannot certify; treat as park" % exc,
            RECEIPT_FAULT_VERIFY)
    if receipt_kind(on_disk) == RECEIPT_INTERIM_SCHEMA:
        return ReceiptFault(
            "terminal receipt is interim — cannot certify; treat as park",
            RECEIPT_FAULT_VERIFY)
    ok, why = validate_receipt(on_disk)
    if not ok:
        return ReceiptFault(
            "terminal receipt invalid (%s) — cannot certify; treat as park" % why,
            RECEIPT_FAULT_VERIFY)
    if not (on_disk.get("scriptRan") or {}).get("invocations"):
        return ReceiptFault(
            "terminal receipt scriptRan is empty — the journal (the driver's ran evidence) did "
            "not persist; cannot certify; treat as park",
            RECEIPT_FAULT_VERIFY)
    if _journal_faulted(session_dir):
        return ReceiptFault(
            "driver journal recorded a write fault — the scriptRan evidence is incomplete "
            "(a next/submit event was lost); cannot certify; treat as park",
            RECEIPT_FAULT_VERIFY)
    return None


def _finalize_receipt(session_dir, state):
    """At a terminal, write + read back + validate the on-disk receipt. A write failure, an
    unreadable readback, an invalid shape, or an EMPTY scriptRan (the journal — the driver's `ran`
    evidence — did not persist) is a RECEIPT DEFECT: return a reason so the CLI fails closed (the
    orchestrator must treat it as a park), never certifying on a missing/short receipt (#507 v14).
    Returns None on success."""
    try:
        _write_receipt(session_dir, state)
    except ReceiptWriteError as exc:
        return ReceiptFault(
            "terminal receipt write failed (%s) — cannot certify; treat as park" % exc,
            exc.kind)
    return _verify_terminal_receipt(session_dir)


def _terminal_receipt_gate(session_dir, state):
    """The single terminal-answer gate — WRITE-ONCE, then RE-VERIFY-FROM-DISK forever. The FIRST
    terminal answer (whichever fires first: the terminating `submit` fold or the first terminal
    `next`) writes + verifies the receipt via `_finalize_receipt` and marks it finalized. EVERY later
    terminal invocation re-verifies the ON-DISK receipt via `_verify_terminal_receipt` and NEVER
    re-writes it.

    So a receipt fault detected at ANY terminal answer is DURABLE across invocations: a re-write from
    in-memory state can never overwrite a faulted receipt into an ok one — the auditor's path was a
    fault produced at the terminating `submit` (e.g. the receipt write failed) being masked by a
    later replayed `next` that re-wrote the receipt from state and answered ok. Once finalized, only a
    genuinely valid ON-DISK receipt (re-read fresh each call) clears the fault; a state overwrite
    cannot. Returns a fault detail string or None, persisting the finalized mark and the durable
    `_receiptFault` detail so the durability survives across separate CLI processes (#507). The fault
    class is data minted at the raise site, not inferred from exception text.

    INVARIANT (#507, third audit): no terminal-phase invocation — first-emission next, replayed next,
    terminating submit, or a duplicate/replayed submit — may answer ok without a fresh on-disk receipt
    verification through this gate, no exceptions."""
    if state.get("_receiptFinalized"):
        fault = _verify_terminal_receipt(session_dir)
    else:
        fault = _finalize_receipt(session_dir, state)
        if fault is not None and not isinstance(fault, ReceiptFault):
            raise TypeError("terminal receipt fault without a class: %r" % (fault,))
        # axis: every outcome of the first finalize — ok or a classed fault — marks the receipt
        # finalized; later invocations only re-verify from disk and never re-write.
        state["_receiptFinalized"] = True
    state["_receiptFault"] = fault or None
    state["_receiptFaultClass"] = fault.kind if fault else None
    save_state(session_dir, state)
    return fault


# =============================================================================================
# Layer 2b — the durable-record subcommands (#723): record-result / record-missing / advance / attest
# =============================================================================================
#
# `next`/`submit` drive a session whose only durable record is the folded state. #723 puts a
# per-seat RECORD layer underneath it: the orchestrator records each dispatched seat's envelope
# (`record-result`) or its ABSENCE (`record-missing`), and then `advance` — in this order — takes
# the session lock, reconciles the two-commit window, sweeps the landing area, proves the roster
# COMPLETE by name, asks `round_adapters` to assemble the phase artifact, folds it through the
# existing `cmd_submit` chokepoint, and emits the next action.
#
# Two boundaries the reader must know:
#
#   - `round_adapters` is imported at CALL time (`_adapters`), never at module import. It is a
#     sibling module landing in parallel; this module must still import without it, and a test must
#     be able to substitute one.
#   - every subcommand here takes the current schema version only. A finished session of an earlier
#     version is refused here with `legacy-session-use-next-submit`; an unfinished one never gets
#     this far, because the upgrade gate refuses it first (`session-from-earlier-version`).


def _adapters():
    """The phase-shape adapter module, imported at CALL time (see the section note)."""
    import round_adapters  # noqa: E402 — lazy by contract, not a module-level dependency
    return round_adapters


def _journal_event(session_dir, cmd, outcome, **fields):
    """Journal one #723 event. Every event carries its attest-eligibility `fault` class and the
    session id, so `attest` can bind a `--failure <seq>` to an event of THIS session and refuse one
    that is merely a caller error."""
    entry = {"cmd": cmd, "outcome": outcome, "session": _meta_session_id(session_dir)}
    entry.setdefault("fault", FAULT_CALLER)
    for key, value in fields.items():
        entry[key] = value
    entry.setdefault("phase", None)
    entry.setdefault("round", None)
    entry.setdefault("attempt", None)
    _journal_append(session_dir, entry)
    return entry


def _journal_identity_fields(phase, seat, occurrence, attempt):
    return {"recordIdentity": round_records.record_identity(phase, seat, occurrence, attempt)}


def _refuse_cmd(session_dir, cmd, reason, fault=FAULT_CALLER, phase=None, rnd=None, attempt=None,
                **extra):
    """Journal a refusal with its fault class and return the refusal body. The `reason` string IS
    the contract — a caller routes on it, so every refusal below is a distinct one."""
    _journal_event(session_dir, cmd, "refused", fault=fault, reason=reason, phase=phase, round=rnd,
                   attempt=attempt, **extra)
    body = {"ok": False, "reason": reason}
    body.update(extra)
    return body


def _lock_held_refusal(session_dir, cmd, held):
    return _refuse_cmd(session_dir, cmd, "%s-locked" % cmd,
                       holder={"pid": held.pid, "createdAt": held.created_at})


def _generation_is_current(state):
    """Only the integer `SESSION_GENERATION` is current: `true == 1` and `2.0 == 2` must not pass."""
    generation = state.get("sessionGeneration")
    return type(generation) is int and generation == SESSION_GENERATION


def _schema_version_is_earlier_supported(state):
    """True only for an integer `schemaVersion` that this driver still supports and that is older
    than `STATE_SCHEMA_VERSION`: `True == 1` and `4.0 == 4` do not count. A version this driver
    does not support (1, a future 6, `None`, `"5"`, `5.0`) is not an earlier session; `load_state`
    refuses it."""
    version = state.get("schemaVersion")
    return (type(version) is int and version in SUPPORTED_STATE_VERSIONS
            and version < STATE_SCHEMA_VERSION)


def _generation_is_continuable_earlier(state):
    """True only for an earlier generation this version finishes (`CONTINUABLE_EARLIER_GENERATIONS`)
    whose `schemaVersion` is exactly `STATE_SCHEMA_VERSION`. Both are exact integers: `true`, `6.0`
    and `"6"` are not generation 6. A continuable generation at any other schema version is not
    continuable: the gate refuses it as it refuses any earlier session."""
    generation = state.get("sessionGeneration")
    version = state.get("schemaVersion")
    # axis: a generation stamped true, 6.0 or "6" is not generation 6 and stays refused — see bite-proof record c1l4b_wo_b
    return (type(generation) is int and generation in CONTINUABLE_EARLIER_GENERATIONS
            and type(version) is int and version == STATE_SCHEMA_VERSION)


def _state_is_earlier_unfinished(state):
    """True for a JSON object that has no terminal answer and is either not of the current
    generation, or of an earlier supported schema version. This is the one place that keeps an
    earlier session from being continued: nothing past the gate ever reads an unfinished state of
    an earlier generation or supported schema version, except one of a continuable earlier
    generation at the current schema version, which finishes. A current-generation state whose
    `schemaVersion` is unsupported is not judged here; `load_state` refuses it."""
    if not isinstance(state, dict):
        return False
    # axis: an unfinished state of a continuable earlier generation at the current schema is not refused — see bite-proof record c1l4b_wo_b
    if _generation_is_continuable_earlier(state):
        return False
    if _generation_is_current(state) and not _schema_version_is_earlier_supported(state):
        return False
    return not state.get("terminal")


def _earlier_generation_unfinished(session_dir):
    """True when `loop-state.json` is a JSON object that has no terminal answer yet and is either
    not of the current generation or of an earlier supported schema version. It opens that one
    file and nothing else; an unreadable, non-JSON or non-object file is False, so the handling
    that exists for those cases stays in charge. When the file is ABSENT, the state a sealed,
    unfinished commit staged for it is judged the same way: an earlier version that stopped after
    sealing its first emit has no installed state yet, and recovery would otherwise finish that
    commit and hand out its orders."""
    try:
        with open(os.path.join(session_dir, STATE_FILE), encoding="utf-8") as fh:
            state = json.load(fh)
    except FileNotFoundError:
        for raw in round_commit.staged_replace_contents(session_dir, STATE_FILE):
            try:
                staged = json.loads(raw.decode("utf-8"))
            except (ValueError, RecursionError):
                continue
            if _state_is_earlier_unfinished(staged):
                return True
        return False
    except (OSError, ValueError, RecursionError):
        return False
    return _state_is_earlier_unfinished(state)


def _write_upgrade_marker(session_dir, cmd):
    """(already_restarted, written). The marker is created exclusively, so only the first refusal
    makes it; a later one finds it and leaves it as it is. Any other failure to create it, or to
    write it once created, still leaves the command refused: (False, False). A marker this call
    created but could not write is removed again, so a later call does not mistake it for a
    complete one."""
    path = os.path.join(session_dir, UPGRADE_RESTART_MARKER_FILE)
    body = {"schema": UPGRADE_RESTART_MARKER_SCHEMA,
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "cmd": cmd}
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return True, True
    except OSError:
        return False, False
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(_canonical(body))
            fh.flush()
            os.fsync(fh.fileno())
    except OSError:
        try:
            os.unlink(path)
        except OSError:
            # Accepted residual: if the partial file cannot be removed either, it stays, and the
            # next call sees it as already existing and answers `alreadyRestarted: true`. The
            # folder then refuses both removal and writing, and nothing more can be done there.
            pass
        return False, False
    return False, True


def _upgrade_gate(session_dir, cmd):
    """None to carry on, or the `session-from-earlier-version` refusal. The caller holds the session
    lock. An unfinished session from an earlier plugin version is never continued: this answers
    before any commit recovery, journal row, session id, order, record or fold, and writes only the
    once-only marker."""
    if not _earlier_generation_unfinished(session_dir):
        return None
    return _upgrade_refusal(session_dir, cmd)


def _upgrade_refusal(session_dir, cmd):
    """The `session-from-earlier-version` refusal body, writing the once-only marker."""
    already_restarted, written = _write_upgrade_marker(session_dir, cmd)
    refusal = {"ok": False, "reason": SESSION_FROM_EARLIER_VERSION,
               "restart": RESTART_FRESH_SESSION, "alreadyRestarted": already_restarted,
               "detail": UPGRADE_REFUSAL_DETAIL}
    if not written:
        refusal["markerWritten"] = False
    return refusal


def _upgrade_gate_unlocked(session_dir, cmd):
    """The gate for `main`, which does not hold the session lock: it takes the lock only for a session
    the gate will refuse, and a held lock answers as it does at every entry."""
    if not _earlier_generation_unfinished(session_dir):
        return None
    try:
        with round_records.session_lock(session_dir):
            return _upgrade_gate(session_dir, cmd)
    except round_records.SessionLockHeld as held:
        # The body `_lock_held_refusal` answers, without its journal row: the folder is one an
        # earlier version left, and nothing in it is written but the once-only marker.
        return {"ok": False, "reason": "%s-locked" % cmd,
                "holder": {"pid": held.pid, "createdAt": held.created_at}}
    except OSError:
        # The folder will not take a lock file (it is read-only): the command is still refused.
        return _upgrade_gate(session_dir, cmd)


def _commit_recover_or_refuse(session_dir, cmd, sidecar_target=None, sidecar_resolver_for=None):
    """None to carry on, or a refusal. The caller holds the session lock. Replays any sealed commit,
    repairs a damaged `loop-state.json` from its mirror, then hands back a session of an earlier
    generation that was waiting at a retired owner gate, then hands back a session of any generation that
    was waiting at a panel in round 2 or later: the one shared call path every locked command takes
    between its upgrade gate and its first state load, so no command reads such a session's retired
    step."""
    if sidecar_resolver_for is None:
        sidecar_resolver_for = _sidecar_resolver_for_recover_dispatch(session_dir)
    if sidecar_target is None:
        sidecar_target = _sidecar_target_for_recover(session_dir)
    try:
        round_commit.recover(session_dir, sidecar_target=sidecar_target,
                             sidecar_resolver_for=sidecar_resolver_for)
    except round_commit.CommitRefused as exc:
        return _refuse_cmd(session_dir, cmd, "commit-recovery-failed", fault=FAULT_INTERNAL,
                           detail="%s: %s" % (exc.reason, exc.detail))
    refusal = _repair_state_if_damaged(session_dir, cmd)
    if refusal is not None:
        return refusal
    _migrate_saved_fixer_step(session_dir, cmd)
    _hand_back_retired_gate(session_dir, cmd)
    _hand_back_retired_later_panel(session_dir, cmd)
    return None


def _migrate_saved_fixer_step(session_dir, cmd):
    """Persist `_migrate_fixer_step` over the saved state and journal it once. A state that cannot
    be read, or that is not at the retired fixer step, is left for the command's own load to answer.
    The caller holds the session lock."""
    ok, state = load_state(session_dir)
    if not ok or not isinstance(state, dict):
        return
    moved, attempt = _migrate_fixer_step(session_dir, state)
    if not moved:
        return
    save_state(session_dir, state)
    _journal_append(session_dir, {"cmd": cmd, "phase": RETIRED_FIXER_PHASE, "round": state["round"],
                                  "attempt": attempt, "outcome": "fix-step-migrated"})


def _hand_back_retired_gate(session_dir, cmd):
    """Persist `_finish_retired_gate_step` over the saved state and journal it once. A state that
    cannot be read, or that needs no hand-back, is left for the command's own load to answer. The
    caller holds the session lock."""
    ok, state = load_state(session_dir)
    if not ok or not isinstance(state, dict):
        return
    retired = state.get("step")
    if not _finish_retired_gate_step(state):
        return
    save_state(session_dir, state)
    _journal_append(session_dir, {"cmd": cmd, "phase": retired if isinstance(retired, str) else None,
                                  "round": state["round"], "attempt": 0,
                                  "outcome": "retired-gate-hand-back"})


def _hand_back_retired_later_panel(session_dir, cmd):
    """Persist `_finish_retired_later_panel` over the saved state and journal it once. A state that
    cannot be read, or that needs no hand-back, is left for the command's own load to answer. The
    caller holds the session lock."""
    ok, state = load_state(session_dir)
    if not ok or not isinstance(state, dict):
        return
    retired = state.get("step")
    if not _finish_retired_later_panel(state):
        return
    save_state(session_dir, state)
    _journal_append(session_dir, {"cmd": cmd, "phase": retired if isinstance(retired, str) else None,
                                  "round": state["round"], "attempt": 0,
                                  "outcome": "retired-gate-hand-back"})


def _state_damage(session_dir):
    """How `loop-state.json` is damaged: `missing`, `unreadable`, `not-json` or `not-an-object`; None
    when it reads as a JSON object. The same read `load_state` makes, classified."""
    path = os.path.join(session_dir, STATE_FILE)
    if not os.path.exists(path):
        return "missing"
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError:
        return "unreadable"
    except (ValueError, RecursionError):
        return "not-json"
    return None if isinstance(data, dict) else "not-an-object"


def _read_mirror_state(session_dir):
    """(state_bytes, state, earlier) from the mirror, or None when it cannot be trusted. `earlier`
    is True for a mirror of an unfinished earlier-version session, which is never restored."""
    try:
        obj, err = round_records.read_json(os.path.join(session_dir, MIRROR_FILE))
    except RecursionError:
        return None
    if err is not None or not isinstance(obj, dict) or obj.get("schema") != MIRROR_SCHEMA:
        return None
    text = obj.get("state")
    if not isinstance(text, str):
        return None
    state_bytes = text.encode("utf-8")
    # axis: a mirror whose bytes do not hash to the hash it carries is torn, so it restores nothing — see bite-proof record c7l3_wo3_driver
    if hashlib.sha256(state_bytes).hexdigest() != obj.get("stateSha256"):
        return None
    try:
        state = json.loads(text)
    except (ValueError, RecursionError):
        return None
    if not isinstance(state, dict):
        return None
    # axis: a mirror of an unfinished earlier-version session is refused with the restart answer, never restored — see bite-proof record c7l3_wo3_driver
    if _state_is_earlier_unfinished(state):
        return state_bytes, state, True
    if _state_version(state) is None:
        return None
    mirror_id = obj.get("sessionId")
    meta_id = _meta_session_id(session_dir)
    if mirror_id is not None and meta_id is not None and mirror_id != meta_id:
        return None
    return state_bytes, state, False


def _repair_state_if_damaged(session_dir, cmd):
    """None to carry on, or the `session-from-earlier-version` refusal. The caller holds the session
    lock and has run commit recovery. A `loop-state.json` that reads as a JSON object is left alone.
    A damaged one (missing, unreadable, not JSON, not an object) is restored from the mirror the last
    committed write left, byte for byte, and one `repair` row is journalled. A mirror that cannot be
    trusted changes nothing: the command then meets the refusal it always met. `load_state` never
    repairs, because it is also read outside the lock."""
    damaged = _state_damage(session_dir)
    if damaged is None:
        return None
    mirror = _read_mirror_state(session_dir)
    if mirror is None:
        return None
    state_bytes, state, earlier = mirror
    if earlier:
        return _upgrade_refusal(session_dir, cmd)
    try:
        _write_state_bytes(session_dir, state_bytes)
    except (OSError, round_commit.CommitRefused) as exc:
        if _state_damage(session_dir) not in (None, "missing"):
            return None  # still unreadable: the command meets its usual refusal
        # A missing state would bootstrap a fresh session over the mirror, and a sealed repair left
        # unfinished would be replayed over any later commit, so the command stops here.
        return _refuse_cmd(session_dir, cmd, "commit-recovery-failed", fault=FAULT_INTERNAL,
                           detail="session repair: %s" % exc)
    _journal_event(session_dir, "repair", "session-repaired", damaged=damaged,
                   round=state.get("round"))
    return None


def _sidecar_resolver_for_recover_dispatch(session_dir):
    """Dispatch ``recover`` sidecar replay by ``targetKind``: round-records paths resolve lazily
    from persisted session config; legacy parts without a kind use the review-receipt resolver;
    any other kind refuses."""
    receipt_resolver = _sidecar_target_for_recover(session_dir)

    def dispatch(part_spec):
        kind = part_spec.get("targetKind")
        if kind == round_commit.SIDECAR_KIND_ROUND_RECORDS:
            def resolve():
                ok, loaded = load_state(session_dir)
                if not ok or loaded is None:
                    return None
                path = (loaded.get("config") or {}).get("recordsPath")
                return path if path else None
            return resolve
        if kind is None:
            return receipt_resolver
        return None

    return dispatch


def _sidecar_target_for_recover(session_dir, state=None, git=None):
    """Zero-arg callable that lazily resolves the sidecar path for ``recover``.

    State load, gitdir resolution, and ``rev-parse HEAD`` run only when the callable is invoked
    (during ``external-sidecar`` replay), so recovery does not depend on pre-recovery session
    state or git subprocesses on the common path where no pending commit exists.

    The callable returns an absolute sidecar path, or ``None`` when state will not load, gitdir
    cannot be resolved, or ``rev-parse HEAD`` fails — ``round_commit`` then refuses sidecar replay
    loudly rather than skipping it."""
    supplied_state = state
    run_git = git or store_core.run_git

    def resolve():
        st = supplied_state
        if st is None:
            ok, loaded = load_state(session_dir)
            if not ok or loaded is None:
                return None
            st = loaded
        config = st.get("config") or {}
        repo_root = config.get("repoRoot") or os.getcwd()
        try:
            gitdir = store_core.get_worktree_gitdir(
                repo_root, run=_git_result_seam(git) if git is not None else None)
        except store_core.RepoRootUnavailable:
            return None
        if not run_git(repo_root, "rev-parse", "HEAD"):
            return None
        return _sidecar_path(gitdir)

    return resolve


def _journal_entry_for_commit(session_dir, cmd, outcome, **fields):
    entry = {"cmd": cmd, "outcome": outcome, "session": _meta_session_id(session_dir)}
    entry.setdefault("fault", FAULT_CALLER)
    for key, value in fields.items():
        entry[key] = value
    entry.setdefault("phase", None)
    entry.setdefault("round", None)
    entry.setdefault("attempt", None)
    return entry


def _commit_refused_response(session_dir, cmd, exc, phase=None, rnd=None, attempt=None, **extra):
    return _refuse_cmd(session_dir, cmd, exc.reason, fault=FAULT_INTERNAL, detail=exc.detail,
                       phase=phase, rnd=rnd, attempt=attempt, **extra)


def _state_load_fault(session_dir):
    """Classify a `load_state` failure for the record layer: (reason, fault_class, detail).

    The split matters for `attest`: an UNREADABLE or CORRUPT `loop-state.json` is machinery failure
    (attest-eligible), while an unsupported schemaVersion is a caller pointing at the wrong session
    dir (never eligible)."""
    path = os.path.join(session_dir, STATE_FILE)
    try:
        with open(path, encoding="utf-8") as fh:
            json.load(fh)
    except OSError as exc:
        return "state-unreadable", FAULT_INTERNAL, str(exc)
    except ValueError as exc:
        return "state-corrupt", FAULT_INTERNAL, str(exc)
    return "state-schema-unsupported", FAULT_CALLER, None


def _load_driver_state(session_dir, cmd):
    """(state, refusal) — the front door every #723 subcommand shares."""
    ok, loaded = load_state(session_dir)
    if not ok:
        reason, fault, detail = _state_load_fault(session_dir)
        if reason == "state-schema-unsupported":
            return None, _refuse_cmd(session_dir, cmd, LEGACY_SESSION_REFUSAL, fault=fault,
                                     detail=loaded)
        return None, _refuse_cmd(session_dir, cmd, reason, fault=fault, detail=detail)
    if loaded is None:
        return None, _refuse_cmd(session_dir, cmd, "bootstrap-required")
    if _state_version(loaded) != STATE_SCHEMA_VERSION:
        # Only a finished session of an earlier version gets here: the upgrade gate refuses an
        # unfinished one before any command reads it.
        return None, _refuse_cmd(session_dir, cmd, LEGACY_SESSION_REFUSAL,
                                 detail=LEGACY_SESSION_REFUSAL_DETAIL)
    return loaded, None


# --- the orders manifest anchor ----------------------------------------------------------------

def _orders_manifest_path(session_dir, rnd, phase, attempt):
    """`<session>/round-<N>/orders/<phase>/manifest.a<K>.json` — fenced inside the session dir."""
    if not isinstance(phase, str) or not phase or phase in (".", "..") \
            or "/" in phase or "\\" in phase or "\x00" in phase:
        raise ValueError("phase is not a safe path component: %r" % (phase,))
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 0:
        raise ValueError("attempt must be a non-negative int, got %r" % (attempt,))
    return os.path.join(round_records.round_dir(session_dir, rnd), ORDERS_DIRNAME, phase,
                        "manifest.a%d.json" % attempt)


def _journal_max_attempt(session_dir, rnd, phase):
    """Highest **accepted** submit attempt logged for `(rnd, phase)`, or -1 when none."""
    max_attempt = -1
    for event in read_journal(session_dir):
        if event.get("cmd") != "submit" or event.get("outcome") != "accepted":
            continue
        if event.get("round") != rnd or event.get("phase") != phase:
            continue
        att = event.get("attempt")
        if isinstance(att, bool) or not isinstance(att, int) or att < 0:
            continue
        max_attempt = max(max_attempt, att)
    return max_attempt


def _journal_max_superseded_attempt(session_dir, rnd, phase):
    """Highest attempt a ``break-it-change`` took back for ``(rnd, phase)``, or -1 when none: the orders of
    that attempt were dropped unanswered, so no result for it may be taken."""
    max_attempt = -1
    for event in read_journal(session_dir):
        if event.get("cmd") != BREAK_IT_CHANGE_CMD or event.get("outcome") != "changed":
            continue
        if event.get("round") != rnd or event.get("phase") != phase:
            continue
        att = event.get("supersededAttempt")
        if isinstance(att, bool) or not isinstance(att, int) or att < 0:
            continue
        max_attempt = max(max_attempt, att)
    return max_attempt


def _max_used_attempt(session_dir, rnd, phase):
    """Durable high-water attempt for ``(rnd, phase)`` from accepted journal entries, and from the attempts a
    ``break-it-change`` superseded.

    The durable seat store is excluded: it records landings, not acceptances, so counting it
    would advance past an unaccepted wave and orphan its recorded seats. A lost journal
    entry therefore surfaces as a loud landing collision at record time rather than silent
    orphaning (#1107)."""
    # axis: a superseded verifier attempt is never handed out again, so its late result meets the stale-attempt refusals (`submit` echo, `record-result` attempt-not-pending)
    return max(_journal_max_attempt(session_dir, rnd, phase),
               _journal_max_superseded_attempt(session_dir, rnd, phase))


def _next_dispatch_attempt(session_dir, rnd, phase, state):
    """Allocate the next unused attempt for a `(round, phase)` dispatch wave.

    Takes the maximum over accepted submit journal entries and ``lastAccepted`` when its phase
    and round match — then allocates above that high-water mark."""
    candidates = [
        _max_used_attempt(session_dir, rnd, phase),
    ]
    prior = state.get("lastAccepted")
    if prior and prior.get("phase") == phase and prior.get("round") == rnd:
        att = prior.get("attempt", 0)
        if not isinstance(att, bool) and isinstance(att, int) and att >= 0:
            candidates.append(att)
    max_used = max(candidates)
    if max_used < 0:
        return 0
    return max_used + 1


def _plugin_resource_root():
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _shipped_rubric_path():
    return os.path.join(_plugin_resource_root(), "rubric", "review-base.md")


def _role_brief_path(seat_key):
    """Absolute path of the seat's agent file when its panel order names one; else empty."""
    if seat_key not in ROLE_BRIEF_SEATS:
        return ""
    return os.path.join(_plugin_resource_root(), "agents", "%s.md" % seat_key)


_RISK_AREAS_MATCHED_SHOWN = 5
_RISK_AREAS_GIT_TIMEOUT_S = 120


def _risk_areas_unreadable(detail):
    line = " ".join(str(detail).split()) or "unknown"
    return "not set (changed-paths-unreadable: %s)" % line


def _risk_areas_changed_paths(repo_root, base, head):
    """(paths, None) for the change `base...head` touches, else (None, not-set text). Never raises."""
    if not isinstance(base, str) or not base:
        return None, _risk_areas_unreadable("base unresolved")
    if not isinstance(head, str) or not head:
        return None, _risk_areas_unreadable("head unresolved")
    try:
        proc = subprocess.run(
            ["git", "-C", repo_root, "diff", "--name-only", "-z", "--no-renames",
             "%s...%s" % (base, head)],
            capture_output=True, timeout=_RISK_AREAS_GIT_TIMEOUT_S)
    except FileNotFoundError:
        return None, _risk_areas_unreadable("git not found")
    except subprocess.TimeoutExpired:
        return None, _risk_areas_unreadable("git diff timed out")
    except OSError as exc:
        return None, _risk_areas_unreadable("%s: %s" % (type(exc).__name__, exc))
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip()
        return None, _risk_areas_unreadable(
            "git diff exited %d: %s" % (proc.returncode, err) if err
            else "git diff exited %d" % proc.returncode)
    names = proc.stdout.decode("utf-8", "surrogateescape").split("\0")
    return [name for name in names if name], None


def _risk_areas_text(seat_key, repo_root, base, head, leave_out=()):
    """The test role's risk-areas clause: which of the project's risk areas the reviewed change
    touches, as read by `risk_areas.touched` over every changed path less the `leave_out` paths (the
    proven copies no seat is given). Empty for any other seat.
    Never raises; a change that cannot be read says so rather than claiming it touches none."""
    if seat_key != "test-role":
        return ""
    try:
        paths, unreadable = _risk_areas_changed_paths(repo_root, base, head)
        if unreadable is not None:
            return unreadable
        # axis: a proven copy no seat is given is not named as touching a risk area — see bite-proof record c1l5b_wo_d_proven_copies
        left_out = set(leave_out)
        paths = [path for path in paths if path not in left_out]
        r = risk_areas.touched(repo_root, paths)
        if r["riskAreas"] == "not-set":
            detail = r.get("detail")
            if isinstance(detail, str) and detail:
                return "not set (%s: %s)" % (r["reason"], detail)
            return "not set (%s)" % r["reason"]
        if not r["touched"]:
            return "none of this project's risk areas"
        entries = []
        for hit in r["touched"]:
            matched = hit["matched"]
            shown = ", ".join(matched[:_RISK_AREAS_MATCHED_SHOWN])
            if len(matched) > _RISK_AREAS_MATCHED_SHOWN:
                shown += ", +%d more" % (len(matched) - _RISK_AREAS_MATCHED_SHOWN)
            entries.append("%s (matched: %s)" % (hit["area"]["name"], shown))
        return "; ".join(entries)
    except Exception as exc:  # the order render must never fail on this clause
        return _risk_areas_unreadable("%s: %s" % (type(exc).__name__, exc))


def _break_it_grammar_text(seat_key):
    """The test role's break-it block grammar: the fenced `break_it.BLOCK_TEMPLATE` and the rules for
    its `run` line and the rules its content must meet, built only from the three `break_it` constants.
    Empty for any other seat."""
    # axis: only the test role's order carries the grammar; every other seat's order stays free of it
    if seat_key != "test-role":
        return ""
    return "```\n%s\n```\n\n%s\n\n%s" % (break_it.BLOCK_TEMPLATE, break_it.RUN_RULES, break_it.CONTENT_RULES)


def _normalize_focus_notes(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def _calibration_path_placeholder(path, label, root_refusal=None):
    if root_refusal:
        return "(%s calibration refused — %s)" % (label, root_refusal)
    if isinstance(path, str) and path and os.path.isfile(path):
        return path
    return "(%s calibration not resolved for this project)" % label


def _claude_md_path_placeholder(repo_root):
    """Absolute live-checkout CLAUDE.md path, or a plain no-CLAUDE.md sentence. Never raises."""
    if isinstance(repo_root, str) and repo_root:
        path = os.path.join(repo_root, "CLAUDE.md")
        if os.path.isfile(path):
            return path
    return "(this project has no CLAUDE.md at %s)" % (repo_root,)


def _resolved_calibration_paths(repo_root):
    """(core_path_or_None, layer_path_or_None, root_refusal_or_None) from calibration_resolve."""
    cwd = repo_root if isinstance(repo_root, str) and repo_root else os.getcwd()
    try:
        info = calibration_resolve.resolve(cwd)
    except calibration_resolve.UnresolvableRootError as exc:
        refusal = core_md.gate_refusal_line(
            core_md.gate_refusal(exc.reason, str(exc.root)))
        return None, None, refusal
    core = info.get("dispatch_core")
    layer = info.get("dispatch_layer")
    core_path = core if isinstance(core, str) and os.path.isfile(core) else None
    layer_path = layer if isinstance(layer, str) and os.path.isfile(layer) else None
    return core_path, layer_path, None


def _vendor_is_external_engine(vendor):
    """True when ``vendor`` is a registered non-claude engine (codex/cursor today).

    Unknown vendors fail closed to host transport — they cannot land on the engine stdout branch."""
    return session_contract.runner_channel_vendor(vendor)


def _seat_is_engine(row):
    """True when the seat's vendor is an external engine (sandboxed stdout transport)."""
    return _vendor_is_external_engine(row.get("vendor"))


CHANNEL_FILE = session_contract.CHANNEL_FILE
CHANNEL_STDOUT = session_contract.CHANNEL_STDOUT

# Phases whose seats an orchestrator dispatches through `dispatch-review` — a READ-ONLY sandbox on
# an external engine: every order phase. DERIVED from `round_orders.ORDER_PHASES` (not hand-typed)
# so a phase added there and forgotten here cannot silently fold an unresolved vendor to the WRITE
# contract (#1035).
_READ_ONLY_CHANNEL_PHASES = frozenset(round_orders.ORDER_PHASES)


VENDOR_SOURCE_CONFIGURED = "configured"
VENDOR_SOURCE_DEFAULTED = "defaulted"
# A non-panel reviewer seat whose configured engine sat in a maker family and was replaced by a
# live vendor outside every maker family (`receipt_disclosures.independent_reviewer`).
VENDOR_SOURCE_INDEPENDENT = "independent"


def _vendor_is_resolved(row):
    """True when the row carries a vendor the driver actually RESOLVED — the channel is knowable.

    A non-empty vendor string is necessary but not sufficient (#1037 rider): a reviewer-phase row
    whose engine-preference read raised falls back to the literal `"claude"`, which is
    indistinguishable from a configured claude seat by its value alone. `vendorSource` carries that
    distinction, and a DEFAULTED vendor is treated exactly like an absent one — it is a guess the
    driver made, not evidence about the seat. Reading it the other way is what handed an
    engine-dispatched seat the landing-path WRITE contract, which a sandboxed engine forfeits on.
    """
    # axis: the SOURCE of the vendor claim, not its value. A `vendor == "claude"` check bites on
    # the value and cannot tell a configured claude seat from a defaulted one — which is exactly the
    # pair that must fold to opposite channels.
    if row.get("vendorSource") == VENDOR_SOURCE_DEFAULTED:
        return False
    # VENDOR_SOURCE_INDEPENDENT is a vendor the driver chose from the live set on positive evidence
    # (a known family outside the makers): resolved, so it falls through to the vendor check.
    vendor = row.get("vendor")
    return isinstance(vendor, str) and bool(vendor.strip())


def _seat_channel(phase, row):
    """The channel the seat's OUTPUT CONTRACT follows — the one home for that choice (#1035).

    The vendor fact is three-valued (host / engine / unknowable) and the contract is two-valued, so
    the fold direction is the whole design: a landing-path WRITE contract is stated only on positive
    evidence that the seat is a host seat that can write.

    * engine vendor -> stdout. A sandboxed seat forfeits on the forbidden write (#767 class).
    * absent vendor on a `dispatch-review` phase -> stdout. The driver cannot establish the channel,
      and the two errors are not symmetric: a host seat handed the stdout contract still returns its
      payload and the orchestrator lands it on the durable path, while an engine seat handed the
      write contract is lost to a forfeit. Fail-safe, not fail-open. The gap is still DISCLOSED as
      `orderVendorProvenanceGaps` — this makes it safe, it does not make it silent.
    * host vendor (and every phase outside `_READ_ONLY_CHANNEL_PHASES`) -> file. Unchanged.

    This is also the single switch behind BOTH the `host_seat` context flag and the `CHANNEL`
    placeholder; deriving them independently is how the two could disagree for one seat.
    """
    if _seat_is_engine(row):
        return CHANNEL_STDOUT
    if phase in _READ_ONLY_CHANNEL_PHASES and not _vendor_is_resolved(row):
        return CHANNEL_STDOUT
    return CHANNEL_FILE


def _reviewer_engine_vendor(repo_root):
    """`(vendor, source)` for single-seat reviewer phases (verifiers, gap-sweep, scoped).

    `source` is the marker `_vendor_is_resolved` reads: `configured` when the preference read
    answered from real configuration, `defaulted` when it did not and the stand-in on the host model
    below was used instead. Returning the bare string lost that distinction — a defaulted
    `"claude"` read as positive host evidence, and the seat was handed the write contract even
    when the orchestrator dispatched it on a real engine (a forfeit).

    **The failure path is a RETURN VALUE, not an exception.** `engine_pref.load_engine_prefs`
    documents "Never raises": an unreadable / refused core.md comes back as
    `refusal_engine_prefs(read_error)` — every role forced to claude, carrying `readError`. Keying
    this marker on `except` alone would therefore never fire on the path that actually produces the
    stand-in, leaving the whole rider inert. `readError` is that path's own marker, and it is what
    separates a refusal from `degenerate_engine_prefs()` (a genuinely absent config, whose
    documented defaults ARE the configuration). The `except` arms below stay as belt-and-braces
    for a contract violation, not as the primary signal."""
    try:
        prefs = engine_pref.load_engine_prefs(repo_root)
    except Exception:  # noqa: BLE001 — transport must degrade, never refuse render
        return "claude", VENDOR_SOURCE_DEFAULTED
    source = (VENDOR_SOURCE_DEFAULTED
              if isinstance(prefs, dict) and prefs.get("readError") is not None
              else VENDOR_SOURCE_CONFIGURED)
    try:
        return engine_pref.resolve_engine("review", prefs), source
    except Exception:  # noqa: BLE001 — same degradation, and the vendor is then a stand-in
        return "claude", VENDOR_SOURCE_DEFAULTED


_NONPANEL_REVIEWER_PHASES = (P_VERIFIERS, P_GAPSWEEP, P_SCOPED, P_SECOND_TEST)

# The cell role each non-panel phase dispatches on (`model_registry.matrix_config`): the verifier
# row for verifiers, the reviewer-deep row for gap sweep and scoped, the synthesis row for grouping.
# Synthesis is not in `_NONPANEL_REVIEWER_PHASES`: it finds and verifies nothing, so the finder and
# verifier claim rules do not apply to it.
_NONPANEL_PHASE_ROLE = {
    P_VERIFIERS: receipt_disclosures.NONPANEL_ROLE_VERIFIER,
    P_GAPSWEEP: receipt_disclosures.NONPANEL_ROLE_FINDER,
    P_SECOND_TEST: receipt_disclosures.NONPANEL_ROLE_FINDER,
    P_SCOPED: receipt_disclosures.NONPANEL_ROLE_FINDER,
    P_SYNTHESIS: receipt_disclosures.NONPANEL_ROLE_SYNTHESIS,
}


def _nonpanel_reviewer_vendor(state, config, repo_root, phase):
    """`(vendor, source)` for verifiers / gap-sweep / scoped, outside every maker family and on a
    vendor whose dispatched cell for ``phase`` the seat map proves live (a native host seat takes the
    seat map's host family); `(None, None)` when no candidate qualifies (the seat is unseatable).

    The reviewer engine is the preferred candidate, so when it qualifies the result is the engine
    with its own `vendorSource`."""
    vendor, source = _reviewer_engine_vendor(repo_root)
    cfg = config if isinstance(config, dict) else {}
    makers = receipt_disclosures.accumulated_maker_families(state)
    fixer = cfg.get("fixerVendor")
    chosen, _family = receipt_disclosures.nonpanel_reviewer(
        cfg, effective_seat_map(state), _NONPANEL_PHASE_ROLE[phase], vendor, makers, fixer)
    if chosen is None:
        return None, None
    if chosen == vendor or source == VENDOR_SOURCE_DEFAULTED:
        # A defaulted vendor stays DISCLOSED when replaced: the preference read did not answer, so
        # the provenance gap is still real and the seat still folds to the stdout contract.
        return chosen, source
    return chosen, VENDOR_SOURCE_INDEPENDENT


def _nonpanel_unseatable(state, session_dir, phase):
    """True when no reviewer outside every maker family, on a proven-live cell, can be seated for
    ``phase``. The same decision `_emit_orders_manifest` records slots missing on, read on the
    fold side so a hand-`submit` session cannot fold a result for a slot that never ran."""
    return _nonpanel_selection(state, session_dir, phase)[0] is None


def _nonpanel_selection(state, session_dir, phase):
    """`(vendor, source)` the non-panel reviewer selection stands on for ``phase`` in this session."""
    cfg = state.get("config") or {}
    meta = _session_meta(session_dir) if session_dir else {}
    repo_root = cfg.get("repoRoot") or meta.get("repoRoot") or os.getcwd()
    return _nonpanel_reviewer_vendor(state, cfg, repo_root, phase)


_LIVE_SELECTION = object()


def _library_finder_unauthenticated(state, reported, phase, selected=_LIVE_SELECTION, replaced=None):
    """True when a library gap-sweep / scoped result does not count: no selectable reviewer, a
    reported vendor that is not the selection or fails the eligibility bar, or no report when the
    selection replaced the reviewer engine. `run_loop` passes the selection (and whether it replaced
    the engine) captured before the callback ran; a caller that passes none reads the live one for ``phase``."""
    if selected is _LIVE_SELECTION:
        selected, _source = _nonpanel_selection(state, None, phase)
        replaced = None
    if selected is None:
        return True
    if reported is None:
        return _nonpanel_replaced(state, selected) if replaced is None else replaced
    return reported != selected or receipt_disclosures.nonpanel_barred(state, state.get("config"))(reported)


def _finder_hand_claim_fault(state, session_dir, phase, artifact):
    """Reason string when a hand-submitted gap-sweep / scoped artifact does not authenticate its
    reviewer, else None: the vendor claim (`reviewerVendor`) must equal the vendor the dispatch
    recorded at emission (the live selection when none was recorded), is required when the
    selection replaced the reviewer engine, and must pass the shared eligibility bar. An emission
    whose manifest no longer verifies authenticates nothing."""
    unverifiable = _emission_unverifiable(state, session_dir, phase)
    if unverifiable:
        return "%s dispatch recorded an emission whose orders manifest does not verify (%s); the " \
               "vendor it ordered is unknown, so no submitted artifact can be authenticated" \
               % (phase, unverifiable)
    selected, source = _nonpanel_selection(state, session_dir, phase)
    expected = _recorded_phase_vendor(state, session_dir, phase) or selected
    if expected is None:
        return None
    raw = artifact.get("reviewerVendor")
    claimed = raw.strip() if isinstance(raw, str) and raw.strip() else None
    required = (source == VENDOR_SOURCE_INDEPENDENT or _nonpanel_replaced(state, expected, session_dir)
                or _recorded_claim_required(state, session_dir, phase))
    if claimed is not None and claimed != expected:
        return ("%s artifact claims reviewerVendor %r but the dispatch recorded %r; a result from "
                "another vendor is not the independent review that was ordered"
                % (phase, claimed, expected))
    if required and claimed is None:
        return ("%s artifact carries no `reviewerVendor`; the selection replaced the reviewer "
                "engine, so the vendor that ran must be claimed (expected %r)" % (phase, expected))
    if receipt_disclosures.nonpanel_barred(state, state.get("config"))(expected):
        return ("%s reviewer %r is ineligible (a maker family, the fixer's vendor, or an unresolvable "
                "host family); its result is not the independent review that was ordered"
                % (phase, expected))
    return None


def _nonpanel_replaced(state, selected, session_dir=None):
    """True when the non-panel selection is not the reviewer engine itself (independence replaced it)."""
    cfg = state.get("config") or {}
    meta = _session_meta(session_dir) if session_dir else {}
    repo_root = cfg.get("repoRoot") or meta.get("repoRoot") or os.getcwd()
    return _reviewer_engine_vendor(repo_root)[0] != selected


def effective_seat_map(state):
    """Seat map for order emission — delegates to ``seat_map_receipts.effective_seat_map`` (#723).
    ``round_adapters._assemble_panel`` calls the ``seat_map_receipts`` home directly; this wrapper
    exists for in-module call sites and tests."""
    return seat_map_receipts.effective_seat_map(state)


def _effective_seat_map(state):
    return effective_seat_map(state)


def _disclose_order_vendor_provenance_gaps(state, gaps):
    if not gaps:
        return
    rnd_key = str(state["round"])
    rec = state["rounds"].get(rnd_key) or {}
    prior = rec.get("orderVendorProvenanceGaps")
    merged = list(prior) if isinstance(prior, list) else []
    # Keyed on PHASE too. While the collector was panel-only, `(seat, occurrence)` was unique
    # within a round; now that every read-only phase can contribute, two phases in one round can
    # carry the same seat key — a configured panel dimension may be named anything, including a
    # fixed reviewer seat name — and a phase-blind key silently drops the second phase's row.
    # Dropping a disclosure is the one thing this collector must never do.
    seen = {(row.get("phase"), row.get("seat"), row.get("occurrence"))
            for row in merged if isinstance(row, dict)}
    for row in gaps:
        if not isinstance(row, dict):
            continue
        key = (row.get("phase"), row.get("seat"), row.get("occurrence"))
        if key in seen:
            continue
        merged.append(row)
        seen.add(key)
    _record_round(state, "orderVendorProvenanceGaps", merged)


def _journal_transport_fields(envelope):
    """Transport derived once from a stored seat envelope — the journal chokepoint."""
    if not isinstance(envelope, dict):
        return {}
    phase = envelope.get("phase")
    provenance = envelope.get("provenance")
    if provenance == round_records.PROVENANCE_ORCHESTRATOR_FULFILLED:
        return {session_contract.SEAT_TRANSPORT_KEY: session_contract.SEAT_TRANSPORT_ORCHESTRATOR}
    if provenance == round_records.PROVENANCE_HAND_LANDED:
        return {session_contract.SEAT_TRANSPORT_KEY: session_contract.SEAT_TRANSPORT_HAND_LANDED}
    if _journal_execution_evidence_fields(envelope.get("executionEvidence")) is not None:
        return {session_contract.SEAT_TRANSPORT_KEY: session_contract.SEAT_TRANSPORT_RUNNER}
    return {session_contract.SEAT_TRANSPORT_KEY: session_contract.SEAT_TRANSPORT_NATIVE}


def _seat_transport_row(state, phase, seat_key, occurrence, config, pending_payload, repo_root,
                        seat_map=None):
    """{vendor, model, engine} for transport — one home keyed to the source that actually knows."""
    if phase == P_PANEL:
        return _seat_dispatch_row(state, seat_key, seat_map=seat_map)
    cfg = config if isinstance(config, dict) else {}
    payload = pending_payload if isinstance(pending_payload, dict) else {}
    if phase == P_AUDITS:
        targets = payload.get("targets")
        if not isinstance(targets, list):
            targets = []
        for target in targets:
            if isinstance(target, dict) and target.get("id") == seat_key:
                return {"vendor": target.get("auditorVendor"), "model": None, "engine": None}
        return {"vendor": None, "model": None, "engine": None}
    if phase in _NONPANEL_REVIEWER_PHASES or phase == P_SYNTHESIS:
        vendor, source = _nonpanel_reviewer_vendor(state, cfg, repo_root, phase)
        return {"vendor": vendor, "model": None, "engine": None, "vendorSource": source}
    return {"vendor": None, "model": None, "engine": None}


def _seat_transport_fault(row, seat_key):
    """Refuse when a seat names a vendor the driver does not recognise.

    Vendor absent is the normal unknowable-vendor case — not a refusal."""
    vendor = row.get("vendor")
    if vendor is None or (isinstance(vendor, str) and not vendor.strip()):
        return None
    if not isinstance(vendor, str):
        return "unknown-vendor:%s:%s" % (seat_key, _label(vendor))
    vendor = vendor.strip()
    if vendor in model_registry.vendors():
        return None
    return "unknown-vendor:%s:%s" % (seat_key, vendor)


def _panel_dimension_label(seat_key):
    """Rubric dimension label for a panel seat — from SUBJECT_FALLBACK, not filename stem."""
    return review_seats.dimension_label(seat_key)


def _label(value):
    return value if isinstance(value, str) else repr(value)


def _paths_match(emitted, expected):
    """True when ``emitted`` names ``expected``, whether shell-quoted or raw."""
    if not isinstance(expected, str) or not expected:
        return False
    if emitted == expected:
        return True
    if isinstance(emitted, str) and shlex.split(emitted) == [expected]:
        return True
    return False


def _shipped_resource_refusal(placeholders):
    """Refuse when a shipped plugin resource path in placeholders does not exist."""
    if not isinstance(placeholders, dict):
        return None
    checks = (
        ("RUBRIC_PATH", _shipped_rubric_path()),
    )
    for name, expected in checks:
        emitted = placeholders.get(name)
        if _paths_match(emitted, expected) and not os.path.isfile(expected):
            return "shipped-resource-missing:%s" % name
    return None


def _emitted_path_is_file(emitted):
    """True when ``emitted`` names an existing file — a raw driver-generated path, never shell-parsed."""
    if not isinstance(emitted, str) or not emitted:
        return False
    return os.path.isfile(emitted)


def _readable_file_input_refusal(placeholders):
    """Refuse when a registered readable file input in placeholders does not exist on disk."""
    if not isinstance(placeholders, dict):
        return None
    for name in ORDER_READABLE_FILE_INPUTS:
        emitted = placeholders.get(name)
        if emitted is None:
            continue
        if name == "PRIOR_COMMENTS_PATH":
            if not emitted or (isinstance(emitted, str) and emitted.strip().startswith("(")):
                continue
        if not _emitted_path_is_file(emitted):
            return "order-input-missing:%s" % name
    return None


def _order_input_refusal(placeholders):
    """Emit-time guard for shipped resources and driver/orchestrator-readable file inputs."""
    reason = _shipped_resource_refusal(placeholders)
    if reason is not None:
        return reason
    return _readable_file_input_refusal(placeholders)


# Order-input sidecar layout — one home for commit writes and order placeholders.
ORDER_SIDECAR_CLUSTERS_DIR = "clusters"
ORDER_SIDECAR_AUDIT_TARGETS_DIR = "audit-targets"
ORDER_SIDECAR_SCOPED_HUNKS_FILE = "scoped-hunks.json"
ORDER_SIDECAR_VERIFIED_FILE = "verified.json"
ORDER_SIDECAR_HELD_FILE = "second-test-held.json"

# Readable file inputs cited in emitted orders — existence guarded at emit (registry #723).
ORDER_READABLE_FILE_INPUTS = frozenset({
    "DIFF_PATH",
    "HEAD_DIFF_PATH",
    "FIX_DIFF_PATH",
    "CLUSTER_FINDINGS_PATH",
    "TARGET_SUMMARY_PATH",
    "HUNKS_PATH",
    "VERIFIED_FINDINGS_PATH",
    "HELD_FINDINGS_PATH",
    "PRIOR_COMMENTS_PATH",
})
ORDER_SHIPPED_RESOURCE_INPUTS = frozenset({
    "RUBRIC_PATH",
})
# Seat/orchestrator output paths — cited but not required to exist before dispatch.
ORDER_OUTPUT_PLACEHOLDERS = frozenset({
    "FINDINGS_OUTPUT_PATH",
    "GROUPING_OUTPUT_PATH",
})
# Substitution values — prose, derived blocks, or directories not file-existence-guarded here.
ORDER_DERIVED_PLACEHOLDERS = frozenset({
    "OUTPUT_CHANNEL_BLOCK",
    "PRIOR_COMMENTS_CONTEXT_LINE",
    "PRIOR_COMMENTS_INSTRUCTION_BLOCK",
    "FOCUS_CONTEXT_LINE",
    "ROLE_BRIEF_LINE",
    "RISK_AREAS_LINE",
    "BREAK_IT_GRAMMAR_BLOCK",
    "MODE",
    "MODE_EVIDENCE",
    "REPO",
    "TARGET",
    "DIMENSION",
    "CHANNEL",
    "FOCUS_NOTES",
    "CORE_PATH",
    "CLAUDE_MD_PATH",
    "LAYER_PATH",
    "VERIFICATION_ROOT",
    "TARGET_ID",
    "PR_BODY_LINE",
})


def _order_cluster_sidecar_path(rdir, index):
    return os.path.join(rdir, ORDER_SIDECAR_CLUSTERS_DIR, "%d.json" % index)


def _order_audit_target_sidecar_path(rdir, skey):
    return os.path.join(rdir, ORDER_SIDECAR_AUDIT_TARGETS_DIR, "%s.json" % skey)


def _order_scoped_hunks_sidecar_path(rdir):
    return os.path.join(rdir, ORDER_SIDECAR_SCOPED_HUNKS_FILE)


def _order_verified_sidecar_path(rdir):
    return os.path.join(rdir, ORDER_SIDECAR_VERIFIED_FILE)


def _order_held_sidecar_path(rdir):
    return os.path.join(rdir, ORDER_SIDECAR_HELD_FILE)


def _order_sidecar_writes(session_dir, rnd, phase, roster, pending_payload):
    """[(path, bytes)] sidecars named in orders, derived from the phase payload."""
    writes = []
    rdir = round_records.round_dir(session_dir, rnd)
    payload = pending_payload if isinstance(pending_payload, dict) else {}
    if phase == P_VERIFIERS:
        clusters = payload.get("clusters")
        if not isinstance(clusters, list):
            clusters = []
        for index, cluster in enumerate(clusters):
            if not isinstance(cluster, dict):
                cluster = {}
            path = _order_cluster_sidecar_path(rdir, index)
            writes.append((path, round_records.canonical(cluster).encode("utf-8")))
    elif phase == P_AUDITS:
        targets = payload.get("targets")
        if not isinstance(targets, list):
            targets = []
        for index, (seat_key, occurrence) in enumerate(round_records.roster_slots(roster)):
            target = targets[index] if index < len(targets) else {}
            if not isinstance(target, dict):
                target = {}
            skey = round_records.storage_key(seat_key, occurrence)
            path = _order_audit_target_sidecar_path(rdir, skey)
            writes.append((path, round_records.canonical(target).encode("utf-8")))
    elif phase == P_SCOPED:
        hunks = payload.get("hunks")
        if not isinstance(hunks, dict):
            hunks = {}
        path = _order_scoped_hunks_sidecar_path(rdir)
        writes.append((path, round_records.canonical(hunks).encode("utf-8")))
    elif phase == P_SYNTHESIS:
        findings = payload.get("findings")
        if not isinstance(findings, list):
            findings = []
        path = _order_verified_sidecar_path(rdir)
        lists = {name: payload[name] if isinstance(payload.get(name), list) else [] for name in ("refuted", "earlier")}
        writes.append((path, round_records.canonical({"findings": findings, **lists}).encode("utf-8")))
    elif phase == P_SECOND_TEST:
        findings = payload.get("findings")
        if not isinstance(findings, list):
            findings = []
        path = _order_held_sidecar_path(rdir)
        writes.append((path, round_records.canonical({"findings": findings}).encode("utf-8")))
    return writes


def _materialize_order_sidecars(session_dir, rnd, phase, roster, pending_payload):
    """Write every order-input sidecar for ``phase`` from the single ``_order_sidecar_writes`` derivation."""
    for path, content in _order_sidecar_writes(session_dir, rnd, phase, roster, pending_payload):
        _ensure_bytes_at_path(session_dir, path, content)


def _session_meta(session_dir):
    obj, err = round_records.read_json(os.path.join(session_dir, round_records.META_FILE))
    return obj if (err is None and isinstance(obj, dict)) else {}


def _ensure_bytes_at_path(session_dir, path, expected):
    """Write ``path`` when absent or content differs — atomic tmp+rename."""
    try:
        round_records._guard_within(session_dir, path)
    except ValueError as exc:
        if "path escapes the session dir" not in str(exc):
            raise
        raise ValueError("order-render-refused:path-escapes-session") from exc
    needs_write = True
    if os.path.isfile(path):
        try:
            with open(path, "rb") as fh:
                on_disk = fh.read()
            needs_write = on_disk != expected
        except OSError:
            needs_write = True
    if needs_write:
        round_commit.atomic_write_bytes(path, expected)
    return path


def _ensure_round_diff(session_dir, rnd, state):
    """Write `round-<N>/diff.txt` (the whole diff) when absent or untrusted so order templates have a real path to
    cite, and return the path a seat is given: `reviewer-diff.txt` beside it when a copy is left out, else `diff.txt`."""
    rdir = round_records.round_dir(session_dir, rnd)
    diff_path = os.path.join(rdir, "diff.txt")
    diff_text = state.get("reviewedDiff")
    if not isinstance(diff_text, str):
        raise ValueError("reviewed-diff-unavailable")
    _ensure_bytes_at_path(session_dir, diff_path, diff_text.encode("utf-8"))
    # axis: the seat-facing diff is its own file and never overwrites the round's diff.txt — see bite-proof record c1l5b_wo_d_proven_copies
    view = countable_lines.reviewer_diff(diff_text, _left_out(state, diff_text))
    _ensure_leave_out_file(session_dir, state)
    if view == diff_text:
        return diff_path
    return _ensure_bytes_at_path(session_dir, os.path.join(rdir, "reviewer-diff.txt"), view.encode("utf-8"))


def _ensure_round_head_diff(session_dir, rnd, state):
    """Write `round-<N>/head.diff` (the whole head diff) from state when absent or untrusted, and return the path a
    seat is given: `reviewer-head.diff` beside it when a copy is left out, else `head.diff`."""
    head_text = state.get("headDiff")
    if not isinstance(head_text, str):
        raise ValueError("order-render-refused:head-diff-unavailable")
    rdir = round_records.round_dir(session_dir, rnd)
    head_path = os.path.join(rdir, "head.diff")
    _ensure_bytes_at_path(session_dir, head_path, head_text.encode("utf-8"))
    view = countable_lines.reviewer_diff(head_text, _left_out(state, head_text))
    _ensure_leave_out_file(session_dir, state)
    if view == head_text:
        return head_path
    return _ensure_bytes_at_path(session_dir, os.path.join(rdir, "reviewer-head.diff"), view.encode("utf-8"))


def _ensure_round_fix_delta(session_dir, rnd, state):
    """Write `round-<N>/fix-delta.diff` — the round's own fix delta, the change between the reviewed (pre-fix)
    diff and the post-fix head diff, each file under its `diff --git` line and no proven copy in it — from
    state when absent or untrusted, and return its path: the only diff the scoped finder is given."""
    text = state.get("_fixDeltaDiff")
    if not isinstance(text, str):
        raise ValueError("order-render-refused:fix-delta-unavailable")
    path = os.path.join(round_records.round_dir(session_dir, rnd), "fix-delta.diff")
    return _ensure_bytes_at_path(session_dir, path, text.encode("utf-8"))


LEAVE_OUT_FILE = "reviewer-leave-out.json"


def _left_out(state, diff_text):
    """The stored proven copies still proven in ``diff_text`` — the one place a diff's left-out copies are
    decided. Entries that are malformed or whose diff section has changed since the check are not among them."""
    return countable_lines.still_proven(state.get("provenCopies") or [], diff_text)


def _left_out_files(state):
    """The files left out of the round's diff: the copies still proven in the head diff, else in the reviewed one."""
    diff_text = state.get("headDiff") or state.get("reviewedDiff")
    return [copy["file"] for copy in _left_out(state, diff_text)]


def _ensure_leave_out_file(session_dir, state):
    """Write ``reviewer-leave-out.json``, which names the files an engine reviewer's patch leaves out, so the
    recipe's ``--leave-out-file`` always names a file (an empty list when nothing is left out)."""
    import sanitized_view  # the loader's module owns the schema identifier; the writer reads it from there
    content = round_records.canonical({"schema": sanitized_view.LEAVE_OUT_SCHEMA, "files": _left_out_files(state)})
    return _ensure_bytes_at_path(session_dir, os.path.join(session_dir, LEAVE_OUT_FILE),
                                 content.encode("utf-8"))


def unread_surface(state, diff_text, read_lists):
    """The unread surface of a round, proven copies left out (FR-8): the changed parts of ``diff_text`` that no
    read list covers, with the sections of the copies still proven in it removed first."""
    return countable_lines.unread_surface(
        countable_lines.reviewer_diff(diff_text, _left_out(state, diff_text)), read_lists)


FIX_BATCH_HISTORY_FIELDS = ("priorAudit", "gateRuling")


def _materialized_fix_batch_rows(state):
    batch = state.get("_fixBatch")
    if not isinstance(batch, list):
        batch = state.get("fixBatch")
    if not isinstance(batch, list):
        raise ValueError("order-render-refused:fix-batch-unavailable")
    history = _finding_history(state)
    materialized = []
    for row in batch:
        if not isinstance(row, dict):
            materialized.append(row)
            continue
        row_copy = dict(row)
        for field in FIX_BATCH_HISTORY_FIELDS:
            row_copy.pop(field, None)
        key = _fix_batch_row_key(row_copy)
        if key and key in history:
            slot = history[key]
            if isinstance(slot, dict):
                prior = slot.get("priorAudit")
                if isinstance(prior, dict):
                    row_prior = {"round": prior.get("round"), "ruling": prior.get("ruling")}
                    if prior.get("reason") is not None:
                        row_prior["reason"] = prior.get("reason")
                    row_copy["priorAudit"] = row_prior
                gate_ruling = slot.get("gateRuling")
                if isinstance(gate_ruling, dict):
                    row_gate = {"round": gate_ruling.get("round"),
                                "disposition": gate_ruling.get("disposition")}
                    if gate_ruling.get("reason") is not None:
                        row_gate["reason"] = gate_ruling.get("reason")
                    row_copy["gateRuling"] = row_gate
        materialized.append(row_copy)
    return materialized


def _fix_batch_path_for_round(session_dir, rnd, state):
    rdir = round_records.round_dir(session_dir, rnd)
    batch_index = state.get("_fixBatchIndex") or 0
    if batch_index >= 1:
        return os.path.join(rdir, "fix-batch.%d.json" % batch_index)
    return os.path.join(rdir, "fix-batch.json")


def _fix_batch_canonical_bytes(state):
    return round_records.canonical(_materialized_fix_batch_rows(state)).encode("utf-8")


def _fix_batch_sha256_from_state(state):
    return round_records.sha256_text(_fix_batch_canonical_bytes(state).decode("utf-8"))


def _ensure_fix_batch_file(session_dir, rnd, state):
    """Materialize fix-batch.json from state for the apply-fixes step.

    Sibling parity with ``_ensure_round_diff`` and ``_ensure_round_head_diff``: unknown input
    (absent, ``None``, or wrong type) refuses before any path computation or write. A known
    batch — including a known-empty list — still materializes.
    """
    path = _fix_batch_path_for_round(session_dir, rnd, state)
    return _ensure_bytes_at_path(session_dir, path, _fix_batch_canonical_bytes(state))


def _fix_guidance_path_for_round(session_dir, rnd, state):
    """The guidance file beside the slice's fix batch, named the way the batch file is."""
    rdir = round_records.round_dir(session_dir, rnd)
    batch_index = state.get("_fixBatchIndex") or 0
    if batch_index >= 1:
        return os.path.join(rdir, "fix-guidance.%d.md" % batch_index)
    return os.path.join(rdir, "fix-guidance.md")


def _apply_fixes_payload_fields(session_dir, state, rnd, attempt):
    """Write the apply-fixes step's batch and guidance files from the state and return the payload
    fields that name them, with the step's landing path and the staged PR body path.

    Raises ``ValueError("order-render-refused:...")`` when the guidance cannot be rendered, the
    refusal channel `_cmd_next_locked` and `cmd_rule` both catch. The guidance renders before
    either file is written, so a refusal leaves both files as they were (c1l9a_wo7_render_first)."""
    guidance = _gate_guidance_block(_gate_guidance_entries(state, rnd))
    fields = {"fixBatchPath": _ensure_fix_batch_file(session_dir, rnd, state)}
    guidance_path = _fix_guidance_path_for_round(session_dir, rnd, state)
    if guidance == _GATE_GUIDANCE_NO_GUIDANCE:
        if os.path.lexists(guidance_path):
            os.unlink(guidance_path)
        fields["guidancePath"] = None
    else:
        fields["guidancePath"] = _ensure_bytes_at_path(
            session_dir, guidance_path, (guidance + "\n").encode("utf-8"))
    fields["landingPath"] = round_records.bare_payload_path(
        session_dir, rnd, P_APPLY_FIXES, round_records.storage_key(payload_contracts.SEAT_APPLY_FIXES),
        attempt)
    staged = pr_body_stage.paths(session_dir)["staged"]
    if os.path.isfile(staged):
        fields["prBodyPath"] = staged
    return fields


# Round-relative paths the driver materializes for order templates — production reads this registry.
ROUND_MATERIALIZER_REGISTRY = {
    "round_diff": _ensure_round_diff,
    "round_head_diff": _ensure_round_head_diff,
    "round_fix_delta": _ensure_round_fix_delta,
    "fix_batch": _ensure_fix_batch_file,
}


def _prior_comments_canonical_path(session_dir):
    return os.path.join(session_dir, "prior-comments.json")


def _materialize_prior_comments(session_dir, source_path, comments):
    """Write validated prior comments to the canonical session path.

    The CLI ``--prior-comments`` chokepoint calls this after validation so
    ``config["priorComments"]`` and ``_resolve_prior_comments_path`` read one file.
    Explicit ``--prior-comments`` wins over any pre-existing canonical file.
    When ``source_path`` already is the canonical file, skip rewrite to avoid
    truncating a file we are reading from.

    Returns True when the canonical file is present with ``comments``; False on
    write failure (caller must not set ``config["priorComments"]`` when False).
    """
    canonical = _prior_comments_canonical_path(session_dir)
    try:
        if os.path.samefile(source_path, canonical):
            return True
    except OSError:
        pass
    try:
        round_commit.atomic_write_json(canonical, comments)
        return True
    except OSError:
        return False


def _earlier_findings_canonical_path(session_dir):
    return os.path.join(session_dir, "earlier-findings.json")


def _earlier_findings_overrides(session_dir, flag_path):
    """The config overrides the first ``next`` takes from the earlier review record: its findings as pool
    entries, or the reason the file gave none (``review-record-missing`` is silent). An explicit flag wins over
    a canonical copy already in the session dir; the file read is copied there as ``earlier-findings.json``."""
    canonical = _earlier_findings_canonical_path(session_dir)
    source = flag_path or (canonical if os.path.isfile(canonical) else None)
    if source is None:
        return {}
    payload, entries, reason = repeat_marks.read_file(source)
    if payload is not None:
        try:
            if not os.path.samefile(source, canonical):
                round_commit.atomic_write_json(canonical, payload)
        except OSError:
            try:
                round_commit.atomic_write_json(canonical, payload)
            except OSError:
                entries, reason = [], "unwritable"
    return {"earlierFindings": entries, "earlierFindingsUnavailable": reason}


def _prior_comments_unavailable_marker():
    return "(prior-comments-unavailable — orchestrator did not supply prior-comments.json)"


def _resolve_prior_comments_path(session_dir, state):
    """Panel prior-comments path — never fabricates ``[]``.

    Mode comes from ``session_mode.resolve`` — the ONE owner of PR-vs-branch (#1107).
    No re-derivation from ``meta``/``config`` here.

    Branch mode: empty path — legitimately no prior comments.
    PR mode (or fail-closed unresolved mode, which ``session_mode.resolve`` treats as PR):
    real file when present; otherwise a prose marker plus a round disclosure.

    Render-only contract: a ``state`` that carries NO round bookkeeping at all — neither
    ``"rounds"`` nor ``"round"`` — is a read/render-layer caller (order-placeholder
    rendering must not raise for a state shape it was never handed round mutation
    responsibility over). That shape gets the rendered marker with no disclosure
    recorded, since there is nowhere honest to record it. A ``state`` that carries
    partial/malformed round bookkeeping (e.g. ``"rounds"`` present but ``"round"``
    absent) is a genuine driver-state bug, not a render-only context, and still raises —
    this is a narrow, documented tolerance, never a bare try/except.
    """
    path = _prior_comments_canonical_path(session_dir)
    if os.path.isfile(path):
        return path
    cfg = state.get("config") if isinstance(state, dict) else {}
    meta = _session_meta(session_dir)
    mode_resolved = session_mode.resolve(meta, cfg)
    if mode_resolved["mode"] == session_mode.MODE_BRANCH:
        return ""
    render_only = (
        isinstance(state, dict) and "rounds" not in state and "round" not in state
    )
    if not render_only:
        _record_round(state, "priorCommentsUnavailable", True)
    return _prior_comments_unavailable_marker()


def _order_paths(session_dir, rnd, phase, attempt, seat_key, occurrence, host_seat):
    skey = round_records.storage_key(seat_key, occurrence)
    env_landing = round_records.landing_path(session_dir, rnd, phase, skey, attempt)
    bare_landing = round_records.bare_payload_path(session_dir, rnd, phase, skey, attempt)
    landing = bare_landing if host_seat else env_landing
    return {
        "storage_key": skey,
        "landing_path": landing,
        "envelope_landing_path": env_landing,
        "bare_payload_path": bare_landing,
        "envelope_stub_path": round_records.envelope_stub_path(session_dir, rnd, phase, skey,
                                                               attempt),
        "order_path": round_records.order_prompt_path(session_dir, rnd, phase, skey, attempt),
    }


def _pr_body_line(phase, session_dir, rnd, state, meta, cfg, materialize_shared_inputs):
    """The ``PR_BODY_LINE`` value of a fixer or audit order: where the staged PR body is, or why
    there is none. Mode resolves exactly as the panel arm does. A render-only call (no mutation)
    only names paths."""
    def no_staged(reason):
        return ("no staged PR body (%s); a finding about a PR body is escalated, never fixed "
                "anywhere else" % reason)

    mode_resolved = session_mode.resolve(meta, cfg)
    if mode_resolved["mode"] == session_mode.MODE_BRANCH:
        return no_staged("branch mode")
    paths = pr_body_stage.paths(session_dir)
    if materialize_shared_inputs:
        staged = pr_body_stage.stage(session_dir)
        if not staged.get("ok") or not staged.get("staged"):
            return no_staged(staged.get("reason") or "not staged")
    return ("the staged copy %s, to be read against the original %s"
            % (paths["staged"], paths["original"]))


def _order_placeholders(phase, seat_key, occurrence, state, config, pending_payload,
                        session_dir, rnd, paths, channel, roster=None,
                        materialize_shared_inputs=True):
    """Phase-specific placeholder dict for `round_orders.render_order`.

    Raises `ValueError("order-render-refused:...")` when a slot cannot be filled truthfully
    — that IS the refusal channel, and `_cmd_next_locked` catches it. Do not add a caller
    that assumes this returns on every input.
    """
    meta = _session_meta(session_dir)
    cfg = config if isinstance(config, dict) else {}
    repo_root = cfg.get("repoRoot") or meta.get("repoRoot") or os.getcwd()
    rdir = round_records.round_dir(session_dir, rnd)
    diff_path = ROUND_MATERIALIZER_REGISTRY["round_diff"](session_dir, rnd, state)
    rubric_path = _shipped_rubric_path()
    core_resolved, layer_resolved, root_refusal = _resolved_calibration_paths(repo_root)
    core_path = _calibration_path_placeholder(core_resolved, "Core", root_refusal)
    layer_path = _calibration_path_placeholder(layer_resolved, "Review-crew layer",
                                              root_refusal)
    claude_md_path = _claude_md_path_placeholder(repo_root)
    payload = pending_payload if isinstance(pending_payload, dict) else {}
    sidecar_roster = roster if isinstance(roster, list) else [seat_key]
    ph = {}

    if phase == P_PANEL:
        dim_label = _panel_dimension_label(seat_key)
        if not dim_label:
            raise ValueError("order-render-refused:no-dimension-label:%s" % seat_key)
        mode_resolved = session_mode.resolve(meta, cfg)
        prior_comments_path = _resolve_prior_comments_path(session_dir, state)
        ph = {
            "MODE": mode_resolved["mode"],
            "MODE_EVIDENCE": session_mode.evidence_line(mode_resolved),
            "REPO": meta.get("repo") or cfg.get("repo") or "unknown",
            "TARGET": meta.get("branch") or cfg.get("branch") or "unknown",
            "DIFF_PATH": diff_path,
            "RUBRIC_PATH": rubric_path,
            "ROLE_BRIEF_PATH": _role_brief_path(seat_key),
            "RISK_AREAS_TEXT": _risk_areas_text(
                seat_key, repo_root, cfg.get("baseRef") or meta.get("baseRef"),
                _session_certified_head(session_dir, state), leave_out=_left_out_files(state)),
            "BREAK_IT_GRAMMAR_TEXT": _break_it_grammar_text(seat_key),
            "CORE_PATH": core_path,
            "LAYER_PATH": layer_path,
            "PRIOR_COMMENTS_PATH": prior_comments_path,
            "FOCUS_NOTES": _normalize_focus_notes(meta.get("focusNotes") or cfg.get("focusNotes")),
            "DIMENSION": dim_label,
            "CHANNEL": channel,
            "CLAUDE_MD_PATH": claude_md_path,
            "FINDINGS_OUTPUT_PATH": os.path.join(rdir, "findings-%s.json" % AGENT_SUFFIX.get(
                seat_key, seat_key)),
        }
    elif phase == P_VERIFIERS:
        prefix = "verifier:"
        cluster_key = seat_key[len(prefix):] if seat_key.startswith(prefix) else seat_key
        cluster_index = None
        for index, cluster in enumerate(payload.get("clusters") or []):
            if isinstance(cluster, dict) and cluster.get("key") == cluster_key:
                cluster_index = index
                break
        if cluster_index is None:
            raise ValueError("order-render-refused:unmatched-verifier-cluster:%s" % cluster_key)
        cluster = (payload.get("clusters") or [])[cluster_index]
        if not isinstance(cluster, dict):
            cluster = {}
        _materialize_order_sidecars(session_dir, rnd, phase, sidecar_roster, payload)
        cluster_path = _order_cluster_sidecar_path(rdir, cluster_index)
        ph = {
            "CLUSTER_FINDINGS_PATH": cluster_path,
            "DIFF_PATH": diff_path,
            "VERIFICATION_ROOT": repo_root,
            "RUBRIC_PATH": rubric_path,
            "CHANNEL": channel,
            "CLAUDE_MD_PATH": claude_md_path,
        }
    elif phase == P_SYNTHESIS:
        findings = payload.get("findings")
        if not isinstance(findings, list):
            findings = []
        _materialize_order_sidecars(session_dir, rnd, phase, sidecar_roster, payload)
        verified_path = _order_verified_sidecar_path(rdir)
        ph = {
            "VERIFIED_FINDINGS_PATH": verified_path,
            "DIFF_PATH": diff_path,
            "VERIFICATION_ROOT": repo_root,
            "RUBRIC_PATH": rubric_path,
            "GROUPING_OUTPUT_PATH": os.path.join(rdir, "grouping.json"),
            "CHANNEL": channel,
            "CLAUDE_MD_PATH": claude_md_path,
        }
    elif phase == P_GAPSWEEP:
        ph = {
            "DIFF_PATH": diff_path,
            "RUBRIC_PATH": rubric_path,
            "CORE_PATH": core_path,
            "LAYER_PATH": layer_path,
            "VERIFICATION_ROOT": repo_root,
            "FINDINGS_OUTPUT_PATH": os.path.join(rdir, "gap-sweep-findings.json"),
            "CHANNEL": channel,
            "CLAUDE_MD_PATH": claude_md_path,
        }
    elif phase == P_SECOND_TEST:
        _materialize_order_sidecars(session_dir, rnd, phase, sidecar_roster, payload)
        ph = {
            "HELD_FINDINGS_PATH": _order_held_sidecar_path(rdir),
            "DIFF_PATH": diff_path,
            "RUBRIC_PATH": rubric_path,
            "VERIFICATION_ROOT": repo_root,
            "ROLE_BRIEF_PATH": _role_brief_path(break_it.ROLE),
            "BREAK_IT_GRAMMAR_TEXT": _break_it_grammar_text(break_it.ROLE),
            "CHANNEL": channel,
            "CLAUDE_MD_PATH": claude_md_path,
        }
    elif phase == P_AUDITS:
        targets = payload.get("targets")
        if not isinstance(targets, list):
            targets = []
        if not any(isinstance(t, dict) and t.get("id") == seat_key for t in targets):
            raise ValueError("order-render-refused:unmatched-audit-target:%s" % seat_key)
        skey = round_records.storage_key(seat_key, occurrence)
        _materialize_order_sidecars(session_dir, rnd, phase, sidecar_roster, payload)
        target_path = _order_audit_target_sidecar_path(rdir, skey)
        head_diff_path = ROUND_MATERIALIZER_REGISTRY["round_head_diff"](session_dir, rnd, state)
        ph = {
            "TARGET_SUMMARY_PATH": target_path,
            "HEAD_DIFF_PATH": head_diff_path,
            "VERIFICATION_ROOT": repo_root,
            "RUBRIC_PATH": rubric_path,
            "TARGET_ID": seat_key,
            "CHANNEL": channel,
            "CLAUDE_MD_PATH": claude_md_path,
            "PR_BODY_LINE": _pr_body_line(phase, session_dir, rnd, state, meta, cfg,
                                          materialize_shared_inputs),
        }
    elif phase == P_SCOPED:
        hunks = payload.get("hunks")
        if not isinstance(hunks, dict):
            hunks = {}
        _materialize_order_sidecars(session_dir, rnd, phase, sidecar_roster, payload)
        hunks_path = _order_scoped_hunks_sidecar_path(rdir)
        fix_diff_path = ROUND_MATERIALIZER_REGISTRY["round_fix_delta"](session_dir, rnd, state)
        ph = {
            "HUNKS_PATH": hunks_path,
            "FIX_DIFF_PATH": fix_diff_path,
            "RUBRIC_PATH": rubric_path,
            "CORE_PATH": core_path,
            "LAYER_PATH": layer_path,
            "VERIFICATION_ROOT": repo_root,
            "FINDINGS_OUTPUT_PATH": os.path.join(rdir, "scoped-findings.json"),
            "CHANNEL": channel,
            "CLAUDE_MD_PATH": claude_md_path,
        }
    return ph


def _standing_rulings_for_orders(state):
    """``(rows, failure)``: the session's live out-of-scope rulings as ``{findingKey, reason}`` rows
    for every order's standing-rulings block, or ``([], "<token>: <detail>")`` when the rulings log
    is unreadable — an unreadable log is never rendered as 'no rulings'. Only out-of-scope rulings
    ride here: guidance rulings reach the fixer through ``GATE_GUIDANCE``."""
    _rows, fault = _read_rulings_log(state)
    if fault is not None:
        return [], "%s: %s" % fault
    ledger_by_key, ledger_fault = _disposition_ledger_by_key(state)
    effective = _live_ruling_by_key(state)
    # One resolution point: a skip a later owner fix/guidance on a merged-in member supersedes (the
    # same ``_row_decision`` the fix batch binds by) is not a standing ruling.
    return ([{"findingKey": key, "reason": entry.get("reason")}
             for key, entry in effective.items()
             if entry.get("ruling") == "out-of-scope" and entry.get("source") == "rule"
             and (ledger_fault is not None
                  or _row_decision(state, effective, ledger_by_key, key) is entry)], None)


def _build_order_render_context(session_dir, state, rnd, phase, attempt, seat_key, occurrence,
                                pending_payload, row, roster=None, materialize_shared_inputs=True):
    """Render the order context for one seat/occurrence, using the CALLER's resolved transport row.

    `row` is required — never re-resolved here. `_seat_transport_row` is not pure for the
    reviewer-engine phases (it re-reads engine prefs from disk behind a fallback), so a second
    resolution inside this function could return a different vendor than the one the manifest and
    envelope stub already recorded, telling a read-only engine seat to write a landing file (#1035).
    One seat, one transport-row resolution, per emission — the caller resolves it once and passes
    that same row to every consumer.
    """
    cfg = state.get("config") or {}
    meta = _session_meta(session_dir)
    repo_root = cfg.get("repoRoot") or meta.get("repoRoot") or os.getcwd()
    transport_fault = _seat_transport_fault(row, seat_key)
    if transport_fault is not None:
        skey = round_records.storage_key(seat_key, occurrence)
        raise ValueError("order-render-refused:%s:%s" % (skey, transport_fault))
    # Resolve the channel EXACTLY ONCE (from the row the caller resolved) and hand that value to
    # both consumers (`host_seat` here, the `CHANNEL` placeholder below).
    channel = _seat_channel(phase, row)
    host_seat = channel == CHANNEL_FILE
    paths = _order_paths(session_dir, rnd, phase, attempt, seat_key, occurrence, host_seat)
    base_ref = cfg.get("baseRef") or meta.get("baseRef")
    residuals, prov, res_failure = round_orders.resolve_order_residuals(repo_root, base_ref)
    if not isinstance(residuals, str):
        residuals = ""
    core_resolved, layer_resolved, _root_refusal = _resolved_calibration_paths(repo_root)
    threat_model, threat_failure = round_orders.resolve_order_threat_model(core_resolved)
    standing_rulings, standing_failure = _standing_rulings_for_orders(state)
    return {
        "session_dir": session_dir,
        "round": rnd,
        "attempt": attempt,
        "diff_path": ROUND_MATERIALIZER_REGISTRY["round_diff"](session_dir, rnd, state),
        "rubric_path": _shipped_rubric_path(),
        "core_path": core_resolved or "",
        "layer_path": layer_resolved or "",
        "repo_root": repo_root,
        "landing_path": paths["landing_path"],
        "envelope_stub_path": paths["envelope_stub_path"],
        "ratified_residuals": residuals,
        "residuals_provenance": prov,
        "residuals_read_failure": res_failure,
        "threat_model": threat_model,
        "threat_model_read_failure": threat_failure,
        "standing_rulings": standing_rulings,
        "standing_rulings_read_failure": standing_failure,
        "payload": pending_payload if isinstance(pending_payload, dict) else {},
        "host_seat": host_seat,
        "placeholders": _order_placeholders(phase, seat_key, occurrence, state,
                                              cfg, pending_payload,
                                              session_dir, rnd, paths, channel, roster=roster,
                                              materialize_shared_inputs=materialize_shared_inputs),
    }, paths


def _envelope_stub_header(session_dir, rnd, phase, attempt, seat_key, occurrence, row,
                          manifest_sha, order_sha, state, head_sha=None):
    """Seat-result header fields knowable at emission — NOT `recordedAt` / `payloadSha256`."""
    schema = _seat_result_schema(state)
    if schema is None:
        raise ValueError("unknown-state-version")
    header = {
        "schema": schema,
        "session": _meta_session_id(session_dir),
        "round": rnd,
        "phase": phase,
        "seat": seat_key,
        "attempt": attempt,
        "vendor": row["vendor"],
        "model": row["model"],
        "dispatchRef": manifest_sha,
        "orderSha256": order_sha,
        "manifestSha256": manifest_sha,
    }
    if occurrence:
        header["occurrence"] = occurrence
    if schema == round_records.SEAT_RESULT_SCHEMA_V2:
        header["provenance"] = round_records.PROVENANCE_DISPATCH_OBSERVED
        if head_sha:
            header["headSha"] = head_sha
    return header


def _anchor_key(rnd, phase, attempt):
    return "%s:%s:%s" % (rnd, phase, attempt)


def _orders_anchor(state, session_dir, rnd, phase, attempt):
    """The EMISSION-TIME dispatch anchor for a phase/attempt, mirrored into state so it rides the
    state-hash chain — or None when nothing was emitted.

    Ingestion checks an envelope's hashes against THIS, never against the manifest file on disk: the
    file is mutable, the mirrored hash is covered by the state hash. With no anchor in state,
    `_orders_anchor_from_journal` reconstructs one from the journalled `orders-emitted` event."""
    anchors = state.get("_ordersAnchors")
    if isinstance(anchors, dict):
        anchor = anchors.get(_anchor_key(rnd, phase, attempt))
        if isinstance(anchor, dict):
            return anchor
    return _orders_anchor_from_journal(session_dir, rnd, phase, attempt)


def _orders_anchor_from_journal(session_dir, rnd, phase, attempt):
    """Rebuild the dispatch anchor from the journalled emission hash when state lost the mirror.

    The rebuild re-verifies the manifest file against the journalled ``manifestSha256`` before
    trusting any per-seat order hashes read from disk."""
    for event in reversed(read_journal(session_dir)):
        if event.get("outcome") != "orders-emitted":
            continue
        if event.get("round") != rnd or event.get("phase") != phase or event.get("attempt") != attempt:
            continue
        manifest_sha = event.get("manifestSha256")
        if not isinstance(manifest_sha, str) or not manifest_sha:
            return None
        path = _orders_manifest_path(session_dir, rnd, phase, attempt)
        manifest, err = round_records.read_json(path)
        if err is not None or not isinstance(manifest, dict):
            return None
        computed_sha = round_records.sha256_text(round_records.canonical(manifest))
        if computed_sha != manifest_sha:
            return None
        orders = {}
        seats = manifest.get("seats")
        if isinstance(seats, dict):
            for skey, entry in seats.items():
                if not isinstance(entry, dict):
                    continue
                order_sha = entry.get("orderSha256")
                if isinstance(order_sha, str) and order_sha:
                    orders[skey] = order_sha
        if not orders:
            raw = manifest.get("seats")
            if isinstance(raw, dict):
                orders = {seat: round_records.NOT_EMITTED for seat in raw}
        anchor = {"manifestSha256": manifest_sha, "orders": orders, "path": path}
        head_sha = manifest.get("headSha")
        if isinstance(head_sha, str) and head_sha:
            anchor["headSha"] = head_sha
        return anchor
    return None


def _anchor_cited_head(state, session_dir, rnd, phase, attempt):
    return (_orders_anchor(state, session_dir, rnd, phase, attempt) or {}).get("headSha")


def _seat_dispatch_row(state, seat_key, seat_map=None):
    """{vendor, model, engine} for a seat, off the #510 seat map in state. Absent values stay None —
    the manifest records what is KNOWN, never a guessed vendor."""
    if seat_map is None:
        seat_map = _effective_seat_map(state)
    seats = (seat_map or {}).get("seats")
    entry = seats.get(seat_key) if isinstance(seats, dict) else None
    if not isinstance(entry, dict):
        return {"vendor": None, "model": None, "engine": None}
    return {"vendor": entry.get("vendor"), "model": entry.get("model"),
            "engine": entry.get("engine")}


def _unfilled_seat_missing_envelope(session_dir, state, rnd, phase, attempt, seat_key, occurrence,
                                    manifest_sha, seat_map):
    """The stored `seat-missing/1` envelope for a roster slot the seat map leaves unfilled — same
    shape `_cmd_record_missing_locked` builds, with reason `unfilled`. It cites the orders manifest
    but no order (none was emitted for the slot)."""
    row = _seat_dispatch_row(state, seat_key, seat_map=seat_map)
    envelope = {
        "schema": round_records.SEAT_MISSING_SCHEMA,
        "session": _meta_session_id(session_dir),
        "round": rnd,
        "phase": phase,
        "seat": seat_key,
        "attempt": attempt,
        "vendor": row["vendor"],
        "model": row["model"],
        "dispatchRef": manifest_sha,
        "orderSha256": round_records.NOT_EMITTED,
        "manifestSha256": manifest_sha,
        "recordedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "reason": UNFILLED_SEAT_REASON,
        "evidence": ("no auditor outside the makers' families is available for this target"
                     if phase == P_AUDITS else
                     "no reviewer outside the makers' families is available for this seat"
                     if phase in _NONPANEL_REVIEWER_PHASES else
                     "the seat map leaves this seat unfilled: no candidate outside the makers' families"),
        "occurrence": occurrence,
    }
    return round_records.envelope_bind_cited_head_source(
        envelope, round_records.CITED_HEAD_SOURCE_ORDER_ANCHOR)


def _cluster_finding_ids(pending, seat_key):
    """The staged finding ids of the cluster a verifier seat (`verifier:<cluster key>`) was ordered."""
    key = seat_key[len("verifier:"):]
    return [f["id"] for c in pending.get("clusters") or [] if isinstance(c, dict) and c.get("key") == key
            for f in c.get("findings") or [] if isinstance(f, dict) and isinstance(f.get("id"), str)]


def _emit_orders_manifest(session_dir, state, rnd, phase, attempt, roster, journal_cmd="advance",
                          pending_payload=None, seat_map=None, extra_journal_entries=()):
    """Emit per-slot order prompts, envelope stubs, and the orders manifest for a dispatch phase.

    Every roster SLOT is rendered, hashed, and written inside the single `orders-emit` commit
    together with the manifest and state anchor. A render refusal for any slot refuses the whole
    emission — a phase that dispatches some seats with orders and others without is worse than one
    that refuses."""
    pending_payload = pending_payload if isinstance(pending_payload, dict) else (
        (state.get("pending") or {}).get("payload") if isinstance(state.get("pending"), dict) else {})
    noauditor_ids = set()  # audit targets with no eligible auditor: no order, a missing envelope instead
    if phase == P_AUDITS:
        targets = pending_payload.get("targets")
        if not isinstance(targets, list):
            targets = []
        cfg = state.get("config") or {}
        for target in targets:
            if not isinstance(target, dict):
                continue
            if not session_contract.runner_channel_vendor(target.get("auditorVendor")):
                maker_families, pinned_vendors = receipt_disclosures.auditor_constraints(state)
                host_independent, _fam = receipt_disclosures.independent_auditor(
                    cfg, cfg.get("fixerVendor"), runner_only=False,
                    maker_families=maker_families, pinned_vendors=pinned_vendors)
                if host_independent is None and not target.get("auditorVendor"):
                    # No eligible auditor exists at all: nothing to seat on any channel, so the
                    # target folds as an audit that did not run rather than refusing the emission:
                    # its slot is recorded missing below, in the orders-emit commit, with no order.
                    # Both channels: a hand-submit session has no runner-channel rule to refuse
                    # under, but an ineligible target still gets no order.
                    if isinstance(target.get("id"), str):
                        noauditor_ids.add(target["id"])
                    continue
                if not state.get("_advanceUsed"):
                    continue  # hand next/submit: any seatable auditor is allowed, only the none-eligible case is skipped
                if host_independent is not None:
                    detail = (
                        "The durable-record path requires a fix auditor dispatched through the "
                        "runner (codex or cursor). The independent-family auditor vendor "
                        "%s is live but cannot prove it ran on the durable-record path, so the "
                        "fix cannot be audited independently. Start a fresh session whose "
                        "--vendors names a second runner vendor (codex or cursor) of a different "
                        "family from the fixer, or use hand next/submit for the whole session."
                        % host_independent)
                else:
                    detail = (
                        "The durable-record path requires a fix auditor dispatched through the "
                        "runner (codex or cursor), but none is among this session's vendors. "
                        "Start a fresh session seeded with --vendors naming a runner vendor "
                        "(for example codex or cursor), or use hand next/submit for the whole "
                        "session.")
                raise AuditorUnseatable(detail, _live_vendors(cfg), cfg.get("fixerVendor"))
    seat_map = seat_map if isinstance(seat_map, dict) else _effective_seat_map(state)
    unfilled = receipt_disclosures.unfilled_seats(seat_map) if phase == P_PANEL else frozenset(noauditor_ids)
    if phase in _NONPANEL_REVIEWER_PHASES:
        cfg = state.get("config") or {}
        repo_root = (cfg.get("repoRoot") or _session_meta(session_dir).get("repoRoot")
                     or os.getcwd())
        if _nonpanel_unseatable(state, session_dir, phase):
            # Every live vendor sits in a maker family: no reviewer can be seated for ANY slot of
            # this phase, on either channel (a hand-submit session has no runner-channel rule to
            # refuse under, but an unseatable slot still gets no order). The driver records each
            # slot missing in the orders-emit commit below; the fold counts it as not run.
            unfilled = frozenset(key for key, _occ in round_records.roster_slots(roster))
    seats = {}
    order_hashes = {}
    rendered = []
    unfilled_slots = []
    vendor_gaps = []
    for seat_key, occurrence in round_records.roster_slots(roster):
        if seat_key in unfilled:
            # No candidate outside the makers' families: nothing is dispatched for this slot and no
            # vendor stands in. The driver records it missing itself, in the orders-emit commit.
            unfilled_slots.append((seat_key, occurrence))
            continue
        pending = pending_payload if isinstance(pending_payload, dict) else {}
        cfg = state.get("config") or {}
        repo_root = (cfg.get("repoRoot") or _session_meta(session_dir).get("repoRoot")
                     or os.getcwd())
        row = _seat_transport_row(state, phase, seat_key, occurrence, cfg, pending, repo_root,
                                  seat_map=seat_map)
        skey = round_records.storage_key(seat_key, occurrence)
        # The disclosure derives from the SAME predicate `_seat_channel` folds on, so a channel that
        # fell back to stdout for want of vendor evidence can never do so silently. Previously
        # panel-only and keyed on an empty vendor string; a DEFAULTED reviewer vendor (#1037 rider)
        # is a gap by the same reasoning and was invisible under both halves of that condition.
        # axis: that a fallback fold is DISCLOSED, not that the fold is safe. Safety is
        # `_seat_channel`'s job and is checked separately; a safe fold with no receipt is the
        # silence this collector exists to prevent.
        if phase in _READ_ONLY_CHANNEL_PHASES:
            if not _vendor_is_resolved(row):
                vendor_gaps.append({"seat": seat_key, "storeKey": skey, "occurrence": occurrence,
                                    "phase": phase, "vendorSource": row.get("vendorSource")})
        context, paths = _build_order_render_context(session_dir, state, rnd, phase, attempt,
                                                     seat_key, occurrence, pending_payload, row,
                                                     roster=roster)
        resource_reason = _order_input_refusal(context.get("placeholders"))
        if resource_reason is not None:
            raise ValueError("order-render-refused:%s:%s" % (skey, resource_reason))
        # Order-input ownership at emission (see also round-driver.md §Emitted orders):
        #   driver commits in orders-emit: clusters/<i>.json, audit-targets/<skey>.json,
        #   scoped-hunks.json, verified.json
        #   driver materializes before emit: diff.txt, head.diff, fix-batch.json, phase sidecars;
        #   prior-comments.json only when orchestrator supplied it (PR-mode absence is disclosed)
        # STUB(#723): readable-input registry + fail-closed existence guard now cover driver-owned
        # file inputs; sidecar bytes are derived once in ``_order_sidecar_writes`` and materialized
        # via ``_materialize_order_sidecars`` before render and again at the orders-emit commit.
        order_text, render_reason = round_orders.render_order(phase, seat_key, context)
        if render_reason is not None or not isinstance(order_text, str):
            raise ValueError("order-render-refused:%s:%s" % (skey, render_reason or "empty"))
        order_sha = round_records.sha256_text(order_text)
        order_hashes[skey] = order_sha
        seats[skey] = {
            "storeKey": skey,
            "seat": seat_key,
            "occurrence": occurrence,
            "vendor": row["vendor"],
            "model": row["model"],
            "engine": row["engine"],
            "channel": _seat_channel(phase, row),
            "resultContract": _seat_result_schema(state),
            "orderSha256": order_sha,
            "orderPath": paths["order_path"],
            "envelopeStubPath": paths["envelope_stub_path"],
        }
        if phase == P_VERIFIERS:
            # The verdict ids this seat's order assigned: `_assemble_verifiers` counts a verdict only from
            # the seat that was ordered it (the manifest is hashed into the emission anchor).
            seats[skey]["ids"] = _cluster_finding_ids(pending, seat_key)
        rendered.append((paths["order_path"], order_text.encode("utf-8"),
                         paths["envelope_stub_path"], order_sha, row, occurrence, seat_key))

    if vendor_gaps:
        _disclose_order_vendor_provenance_gaps(state, vendor_gaps)

    certified_head = _session_certified_head(session_dir, state)
    manifest = {"schema": ORDERS_MANIFEST_SCHEMA, "session": _meta_session_id(session_dir),
                "round": rnd, "phase": phase, "attempt": attempt,
                "orders": round_records.NOT_EMITTED, "seats": seats}
    if certified_head:
        manifest["headSha"] = certified_head
    if phase in _NONPANEL_REVIEWER_PHASES:
        vendor, source = _nonpanel_selection(state, session_dir, phase)
        if vendor is not None and (source == VENDOR_SOURCE_INDEPENDENT
                                   or _nonpanel_replaced(state, vendor, session_dir)):
            manifest["claimRequired"] = True
    path = _orders_manifest_path(session_dir, rnd, phase, attempt)
    manifest_sha = round_records.sha256_text(round_records.canonical(manifest))
    anchor = {"manifestSha256": manifest_sha, "orders": dict(order_hashes), "path": path}
    if certified_head:
        anchor["headSha"] = certified_head
    if len(ran := {e.get("vendor") for e in seats.values() if isinstance(e, dict)}) == 1 and isinstance(v := next(iter(ran)), str):
        anchor["vendor"] = v  # the one vendor the emission dispatched on: the record writer's hand-submit finder provenance
    anchors = state.get("_ordersAnchors")
    if not isinstance(anchors, dict):
        anchors = {}
    anchors[_anchor_key(rnd, phase, attempt)] = anchor
    state["_ordersAnchors"] = anchors
    journal_entry = _journal_entry_for_commit(session_dir, journal_cmd, "orders-emitted",
                                              phase=phase, round=rnd, attempt=attempt,
                                              manifestSha256=manifest_sha)
    sidecar_writes = _order_sidecar_writes(session_dir, rnd, phase, roster, pending_payload)
    try:
        c = round_commit.begin(session_dir, "orders-emit")
        _stage_state(c, session_dir, _canonical(state).encode("utf-8"))
        c.add_replace_file(path, round_records.canonical(manifest).encode("utf-8"))
        for sidecar_path, sidecar_bytes in sidecar_writes:
            c.add_replace_file(sidecar_path, sidecar_bytes)
        for seat_key, occurrence in unfilled_slots:
            missing = _unfilled_seat_missing_envelope(session_dir, state, rnd, phase, attempt,
                                                      seat_key, occurrence, manifest_sha, seat_map)
            skey = round_records.storage_key(seat_key, occurrence)
            c.add_replace_file(round_records.store_path(session_dir, rnd, phase, skey, attempt),
                               round_records.canonical(missing).encode("utf-8"))
        for order_path, order_bytes, stub_path, order_sha, row, occurrence, seat_key in rendered:
            c.add_replace_file(order_path, order_bytes)
            # Projection of the anchor, never the authority — ingestion validates the mirrored hash.
            stub = _envelope_stub_header(session_dir, rnd, phase, attempt, seat_key, occurrence,
                                         row, manifest_sha, order_sha, state,
                                         head_sha=certified_head)
            c.add_replace_file(stub_path, round_records.canonical(stub).encode("utf-8"))
        journal_path = os.path.join(session_dir, JOURNAL_FILE)
        for extra_entry in extra_journal_entries:
            c.add_journal_append(journal_path, extra_entry)
        c.add_journal_append(journal_path, journal_entry)
        c.run()
    except round_commit.CommitRefused as exc:
        raise exc
    return anchor


# --- the durable per-seat records ---------------------------------------------------------------

def _slot_label(seat_key, occurrence):
    """How a roster SLOT is named to a caller: `<seat>` at occurrence 0, `<seat>#<n>` beyond it.

    A second seat sharing an id is a real, separately-dispatched seat, so a refusal that named only
    `<seat>` would read as "the whole target is missing" while its twin sits recorded on disk. The
    plain form is kept for the overwhelmingly common single-slot case so no existing caller's
    reason string changes shape."""
    return seat_key if not occurrence else "%s#%d" % (seat_key, occurrence)


def _record_result_recovery_cmd(session_dir, seat_key, occurrence, cas_token, attempt):
    """Shell-ready per-slot supersede command — matches round-driver.md invocation spelling.

    Round and phase are not separately addressable on this CLI; ``--attempt`` is the fence
    that binds the command to the slot it was produced for."""
    driver_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "round_driver.py")
    cmd = ("python3 -B %s record-result --session-dir %s --seat %s "
           "--occurrence %d --attempt %d --supersede --expect-sha256 %s"
           % (shlex.quote(driver_path), shlex.quote(session_dir), shlex.quote(seat_key),
              occurrence, attempt, shlex.quote(cas_token)))
    return cmd


def _record_result_cmd(session_dir, seat_key, occurrence, attempt):
    """Shell-ready first-ingest `record-result` for one slot (no stored record to supersede yet)."""
    driver_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "round_driver.py")
    cmd = ("python3 -B %s record-result --session-dir %s --seat %s --occurrence %d --attempt %d"
           % (shlex.quote(driver_path), shlex.quote(session_dir), shlex.quote(seat_key),
              occurrence, attempt))
    return cmd


def _store_file_exists(spath):
    """True when a store path is present for the record-submit fence — fail-closed on ambiguity.

    axis: EXISTENCE probe only — only a definite ``ENOENT`` / ``ENOTDIR`` counts as absent; a broken
    symlink, an unstattable path, and every other ``lstat`` outcome count as present so the fence
    refuses hand submit rather than folding over an unknown store state."""
    try:
        os.lstat(spath)
        return True
    except OSError as exc:
        if exc.errno in (errno.ENOENT, errno.ENOTDIR):
            return False
        return True


def _durable_slot_records(session_dir, rnd, phase, attempt, roster):
    """Sorted slot labels whose store file EXISTS at (round, phase, attempt).

    axis: EXISTENCE of a store file per roster slot — not readability; a broken symlink, an
    unstattable path, an uncomputable store path, and an unreadable record all count as present so
    the fence fails closed.

    Existence probe only — not a read/parse check. The record-submit interleave fence must treat an
    UNREADABLE store file as PRESENT (the durable-record path already wrote something a hand submit
    would ignore). ``_seat_slot_records`` maps unreadable JSON to ``None``, which would let the
    fence fail open if reused here."""
    found = []
    for seat_key, occurrence in round_records.roster_slots(roster):
        try:
            spath = round_records.store_path(
                session_dir, rnd, phase,
                round_records.storage_key(seat_key, occurrence), attempt)
        except ValueError:
            # Fail closed here (opposite of `_seat_slot_records`, which maps an uncomputable slot to
            # absent so `advance` refuses `incomplete-roster`). This probe refuses hand submit.
            found.append(_slot_label(seat_key, occurrence))
            continue
        if _store_file_exists(spath):
            if _is_unfilled_missing_record(spath):
                # the driver's own record for an unfilled seat — not a durable result a hand submit
                # would discard, so it never trips the interleave fence
                continue
            found.append(_slot_label(seat_key, occurrence))
    return sorted(found)


def _is_unfilled_missing_record(spath):
    """True only for a readable `seat-missing/1` envelope whose reason is `unfilled`; any other
    outcome (unreadable, other schema, other reason) is a record the fence must count."""
    obj, err = round_records.read_json(spath)
    return (err is None and isinstance(obj, dict)
            and obj.get("schema") == round_records.SEAT_MISSING_SCHEMA
            and obj.get("reason") == UNFILLED_SEAT_REASON)


def _seat_slot_records(session_dir, rnd, phase, attempt, roster):
    """[(seat_key, occurrence, stored_envelope_or_None)] for the CURRENT attempt, off the store.

    Keyed by SLOT, never by seat alone: `round_adapters.roster_for("dispatch-audits", ...)` is
    occurrence-indexed because two DISTINCT audit targets can legitimately share one roster seat
    key (same per-location id before occurrence suffixing, or a repeated key in the roster list),
    and a seat-keyed map cannot even represent them — one of the two records would be dropped before
    any fold saw it. The enumeration is `round_records.roster_slots`, the same one the adapter
    indexes envelopes with."""
    out = []
    for seat_key, occurrence in round_records.roster_slots(roster):
        try:
            spath = round_records.store_path(
                session_dir, rnd, phase, round_records.storage_key(seat_key, occurrence), attempt)
        except ValueError:
            out.append((seat_key, occurrence, None))
            continue
        obj, err = round_records.read_json(spath)
        out.append((seat_key, occurrence, obj if (err is None and isinstance(obj, dict)) else None))
    return out


def _journal_execution_evidence_fields(evidence):
    """Mandatory execution-evidence members plus each optional field when present. One home:
    ``round_records.execution_evidence_fields``, shared with ``recorded_row_fields`` and
    ``_assemble_dispatch_evidence`` so the copies cannot drift."""
    return round_records.execution_evidence_fields(evidence)


def _journal_record_identities(session_dir, rnd, phase):
    """Every record identity this session's journal logged for a phase — `reconcile`'s view of the
    LOG half of the two-commit window. The latest payload hash and CAS token per slot ride with
    each identity so a supersede whose journal append never landed still reconciles."""
    latest = {}
    for event in read_journal(session_dir):
        if event.get("phase") != phase or event.get("round") != rnd:
            continue
        if event.get("outcome") != "recorded":
            continue
        ident = event.get("recordIdentity")
        if not isinstance(ident, dict):
            seat = event.get("seat")
            if not isinstance(seat, str) or not seat:
                continue
            ident = round_records.record_identity(
                phase, seat, event.get("occurrence", 0), event.get("attempt"))
        key = round_records._identity_key_from_mapping(ident, default_phase=phase)
        if key is None:
            continue
        entry = dict(ident)
        if "payloadSha256" in event:
            entry["payloadSha256"] = event.get("payloadSha256")
        if "casToken" in event:
            entry["casToken"] = event.get("casToken")
        latest[key] = entry
    return list(latest.values())


def _seat_for_record_identity(session_dir, ident):
    """The seat label a journalled record identity belongs to (for a `journal-orphan` refusal that
    NAMES the seat), or None when the log does not say."""
    if not isinstance(ident, dict):
        return None
    seat = ident.get("seat")
    if not isinstance(seat, str) or not seat:
        return None
    occurrence = ident.get("occurrence", 0)
    if occurrence:
        return "%s#%d" % (seat, occurrence)
    return seat


def _read_landing_envelope(session_dir, rnd, phase, seat_key, attempt, occurrence=0):
    """(envelope, err, landing_replace_path) for a landed seat file — full envelope or bare host
    payload. ``landing_replace_path`` is the envelope file to rewrite when evidence stamping applies;
    ``None`` when the slot is bare-payload shaped and must stay single-file. Never raises."""
    try:
        skey = round_records.storage_key(seat_key, occurrence)
    except ValueError as exc:
        return None, str(exc), None
    envelope, refusal = round_records._read_landing_envelope(
        session_dir, rnd, phase, skey, attempt, occurrence)
    if refusal is not None:
        return None, refusal.get("reason"), None
    landing_replace_path = None
    # landing_replace_path follows the resolver's shape marker, not a second filesystem probe.
    if envelope.get("payloadHashSource") != "driver-computed":
        try:
            landing_replace_path = round_records.landing_path(session_dir, rnd, phase, skey, attempt)
        except ValueError:
            pass
    return envelope, None, landing_replace_path


def _preflight_payload_fault(phase, envelope, seat_key):
    """Adapter payload validation on a landing envelope BEFORE ingest. Returns a fault string or
    None. Only seat-result landings are checked — missing envelopes have no payload contract."""
    if not isinstance(envelope, dict):
        return None
    if envelope.get("schema") not in round_records.SEAT_RESULT_SCHEMAS:
        return None
    return _adapters().payload_fault(phase, envelope.get("payload"), seat_key,
                                     record_boundary=True)


def _round_phase_addressing_supplied(expect_round, expect_phase):
    """True when the caller supplied both round/phase addressing echoes from ``next``."""
    return expect_round is not None and expect_phase is not None


def _journal_addressing_fields(expect_round, expect_phase):
    return {"addressed": _round_phase_addressing_supplied(expect_round, expect_phase)}


def _pending_of(session_dir, state, cmd, expect_round=None, expect_phase=None):
    """(phase, round, attempt, refusal) for the pending step every record/advance call works on.

    Bite axis (#1177-C): optional ``expect_round`` / ``expect_phase`` must match the pending slot
    before any durable-store write; mismatches refuse ``round-phase-not-pending``.
    Bite-proof: WO 1177-C — four elements (round leg, phase leg, sweep coverage, record-missing
    coverage); durable build record."""
    pending = state.get("pending")
    if not isinstance(pending, dict) or not pending.get("phase"):
        return None, None, None, _refuse_cmd(session_dir, cmd, "no-pending-phase")
    phase = pending.get("phase")
    rnd = pending.get("round")
    attempt = pending.get("attempt")
    mismatch_extra = {}
    if expect_round is not None and expect_round != rnd:
        mismatch_extra["expectedRound"] = expect_round
        mismatch_extra["pendingRound"] = rnd
    if expect_phase is not None and expect_phase != phase:
        mismatch_extra["expectedPhase"] = expect_phase
        mismatch_extra["pendingPhase"] = phase
    if mismatch_extra:
        return None, None, None, _refuse_cmd(
            session_dir, cmd, ROUND_PHASE_NOT_PENDING_REFUSAL, phase=phase, rnd=rnd,
            attempt=attempt, **mismatch_extra)
    return phase, rnd, attempt, None


def _roster_of(session_dir, state, cmd, phase, rnd, attempt):
    """(roster, refusal) — the phase's seat roster, from the adapter that owns the phase shape."""
    roster, reason = _adapters().roster_for(phase, state, state.get("config") or {})
    if reason is not None or not isinstance(roster, (list, tuple)):
        return None, _refuse_cmd(session_dir, cmd, "roster-unavailable", phase=phase, rnd=rnd,
                                 attempt=attempt, detail=reason)
    return [s for s in roster if isinstance(s, str)], None


def cmd_record_result(session_dir, seat=None, attempt=None, supersede=False, expect_sha256=None,
                      sweep=False, occurrence=0, expect_round=None, expect_phase=None,
                      evidence_run_dir=None):
    """Ingest ONE landed seat envelope (or, with `sweep`, every unclaimed landing) into the durable
    store, and journal the outcome carrying its `payloadSha256`.

    The ingestion itself — the attempt fence, the torn-write detector, the supersede CAS, the
    manifest anchor — is `round_records`'; this layer supplies the roster (`round_adapters`), the
    emission-time anchor, the per-field payload validation, and the journal.

    `occurrence` addresses WHICH roster slot of a repeated seat key this envelope is (default 0 —
    the only slot a key that appears once has). Two distinct audit targets can legitimately share
    one id, so without it the second target's result is unaddressable and the first's would be
    superseded by it."""
    try:
        with round_records.session_lock(session_dir):
            upgrade = _upgrade_gate(session_dir, "record-result")
            if upgrade is not None:
                return upgrade
            refusal = _commit_recover_or_refuse(session_dir, "record-result")
            if refusal is not None:
                return refusal
            return _cmd_record_result_locked(session_dir, seat=seat, attempt=attempt,
                                             supersede=supersede, expect_sha256=expect_sha256,
                                             sweep=sweep, occurrence=occurrence,
                                             expect_round=expect_round,
                                             expect_phase=expect_phase,
                                             evidence_run_dir=evidence_run_dir)
    except round_records.SessionLockHeld as held:
        return _lock_held_refusal(session_dir, "record-result", held)


def _runner_shaped_result(phase, result_kind, envelope_payload):
    """The runner-shaped result whose payload the seat landed — derived from the seat-payload
    contract's declared type for the kind (payload_contracts), so the digest subject comes from
    engine_adapter's own semantics."""
    contract, _ = payload_contracts.payload_contract(phase)
    types = contract.get("types") or {}
    declared = types.get(result_kind)
    # List kinds wrap under the kind key; scalar kinds land the record itself
    # (payload_contracts.is_list_type).
    if payload_contracts.is_list_type(declared):
        return {"ok": True, "resultKind": result_kind, **envelope_payload}
    return {"ok": True, "resultKind": result_kind, result_kind: envelope_payload}


def _assemble_dispatch_evidence(session_dir, envelope, evidence_run_dir, anchor_cited_head,
                                phase):
    """Bind runner telemetry to the driver's order hash.

    Returns (envelope, refusal_reason, extra, cited_head_source)."""
    if not evidence_run_dir:
        return None, None, {}, None
    import engine_dispatch
    record, err = engine_dispatch.run_execution_record(evidence_run_dir)
    if err is not None:
        return None, "evidence-run-dir-unreadable", {"detail": err}, None
    prompt_sha = record.get("orderPromptSha256")
    order_sha = envelope.get("orderSha256")
    # Absent order-prompt hash cannot prove the binding — refuse rather than compare promptSha256.
    if not isinstance(prompt_sha, str) or not prompt_sha or prompt_sha != order_sha:
        return None, "evidence-order-mismatch", {"orderPromptSha256": prompt_sha,
                                                 "orderSha256": order_sha}, None
    result_digest = record.get("resultDigest")
    result_kind = record.get("resultKind")
    if (not isinstance(result_digest, str) or not result_digest
            or not isinstance(result_kind, str) or not result_kind):
        return None, "evidence-run-dir-unreadable", {"detail": "result-binding-incomplete"}, None
    run_kind = record.get("runKind")
    if run_kind == engine_dispatch.RUN_KIND_WRITE:
        if not session_contract.execution_only_admissible_for_phase(phase):
            return None, "evidence-run-kind-mismatch", {"runKind": run_kind, "phase": phase}, None
    envelope_payload = envelope.get("payload")
    payload_adopted = False
    if (result_kind in session_contract.RECORD_RESULT_KINDS
            and envelope_payload is None):
        result_content = record.get("resultContent")
        if isinstance(result_content, dict):
            envelope_payload = dict(result_content)
            payload_adopted = True
    if session_contract.evidence_binding(result_kind) == session_contract.EXECUTION_ONLY_BINDING:
        # axis: write-run stamp proves the run happened under this order — no transported payload
        # is bound; never read it as payload proof
        pass
    else:
        if not isinstance(envelope_payload, dict):
            mismatch_extra = {"resultDigest": result_digest, "resultKind": result_kind}
            result_content = record.get("resultContent")
            if isinstance(result_content, dict):
                mismatch_extra["expectedPayloadSha256"] = round_records.payload_sha256(
                    result_content)
            return None, "evidence-result-mismatch", mismatch_extra, None
        shaped = _runner_shaped_result(envelope.get("phase"), result_kind, envelope_payload)
        carried, adapter_subject = engine_adapter.review_payload_carried(shaped, result_kind)
        digest_carried, digest_subject = session_contract.evidence_digest_subject(
            envelope_payload, result_kind)
        # Leaf rule (session_contract.evidence_digest_subject) is the writer's rule; drift test
        # pins it equal to review_payload_carried on the runner-shaped result.
        if not carried or not digest_carried:
            return None, "evidence-result-mismatch", {"resultDigest": result_digest,
                                                       "resultKind": result_kind}, None
        if round_records.payload_sha256(adapter_subject) != round_records.payload_sha256(
                digest_subject):
            return None, "evidence-result-mismatch", {"resultDigest": result_digest,
                                                       "resultKind": result_kind,
                                                       "subjectDisagreement": True}, None
        payload_digest = round_records.payload_sha256(digest_subject)
        if result_digest != payload_digest:
            mismatch_extra = {"resultDigest": result_digest,
                              "payloadSha256": payload_digest,
                              "resultKind": result_kind}
            result_content = record.get("resultContent")
            if isinstance(result_content, dict):
                mismatch_extra["expectedPayloadSha256"] = round_records.payload_sha256(
                    result_content)
            return None, "evidence-result-mismatch", mismatch_extra, None
    cited_head_source = None
    view_head = None
    if run_kind == engine_dispatch.RUN_KIND_WRITE:
        cited_head_source = round_records.CITED_HEAD_SOURCE_ORDER_ANCHOR
    elif run_kind == engine_dispatch.RUN_KIND_REVIEW:
        view_head = record.get("viewHeadSha")
        if not isinstance(view_head, str) or not view_head:
            return None, "view-head-underivable", {"runKind": run_kind}, None
        if not isinstance(anchor_cited_head, str) or not anchor_cited_head:
            return None, "view-head-underivable", {"runKind": run_kind,
                                                    "anchorCitedHead": anchor_cited_head}, None
        if view_head != anchor_cited_head:
            return None, "view-head-anchor-mismatch", {"viewHeadSha": view_head,
                                                        "anchorCitedHead": anchor_cited_head}, None
        cited_head_source = round_records.CITED_HEAD_SOURCE_RUNNER_VIEW
    else:
        return None, "view-head-underivable", {"runKind": run_kind}, None
    evidence = _journal_execution_evidence_fields(record)
    if evidence is None:
        return None, "evidence-run-dir-unreadable", {"detail": "result-binding-incomplete"}, None
    out = dict(envelope)
    if payload_adopted:
        out["payload"] = envelope_payload
        out["payloadSha256"] = round_records.payload_sha256(envelope_payload)
    if cited_head_source == round_records.CITED_HEAD_SOURCE_RUNNER_VIEW:
        env_head = envelope.get("headSha")
        if env_head is None:
            out["headSha"] = view_head
        elif env_head != view_head:
            return None, "head-anchor-mismatch", {"envelopeHeadSha": env_head,
                                                   "viewHeadSha": view_head}, None
    out["executionEvidence"] = evidence
    out["envelopeSha256"] = round_records.envelope_sha256(out.get("payload"), evidence)
    return out, None, {}, cited_head_source


def _cmd_record_result_locked(session_dir, seat=None, attempt=None, supersede=False,
                              expect_sha256=None, sweep=False, occurrence=0,
                              expect_round=None, expect_phase=None, evidence_run_dir=None):
    state, refusal = _load_driver_state(session_dir, "record-result")
    if refusal is not None:
        return refusal
    if state.get("_submitUsed"):
        return _refuse_cmd(
            session_dir, "record-result", "record-submit-interleaved",
            detail=("this session already folded a phase by hand (`submit`); the durable-record and "
                    "hand-submit fold paths are mutually exclusive per session. For this phase, compile "
                    "the artifact and `submit` — do not use `advance` (this session's latch refuses it) "
                    "or `record-result`."))
    if seat is None and not sweep:
        return _refuse_cmd(session_dir, "record-result", "seat-required")
    phase, rnd, cur_attempt, refusal = _pending_of(
        session_dir, state, "record-result", expect_round=expect_round,
        expect_phase=expect_phase)
    if refusal is not None:
        return refusal
    if attempt is not None and attempt != cur_attempt:
        return _refuse_cmd(session_dir, "record-result", "attempt-not-pending", phase=phase,
                           rnd=rnd, attempt=attempt, pendingAttempt=cur_attempt)
    roster, refusal = _roster_of(session_dir, state, "record-result", phase, rnd, cur_attempt)
    if refusal is not None:
        return refusal
    anchor = _orders_anchor(state, session_dir, rnd, phase, cur_attempt)
    if sweep and evidence_run_dir:
        # A sweep spans every seat — one run directory cannot bind evidence for all of them.
        return _refuse_cmd(session_dir, "record-result", "sweep-evidence-unsupported",
                           phase=phase, rnd=rnd, attempt=cur_attempt,
                           detail=("--sweep cannot take --evidence-run-dir: evidence binds one "
                                   "seat's order hash; a sweep covers the whole roster."))
    if sweep and (supersede or expect_sha256 is not None):
        recovery = []
        for seat_key, occurrence in round_records.roster_slots(roster):
            try:
                skey = round_records.storage_key(seat_key, occurrence)
                spath = round_records.store_path(session_dir, rnd, phase, skey, cur_attempt)
            except ValueError:
                continue
            if not os.path.exists(spath):
                continue
            stored, store_err = round_records.read_json(spath)
            cas_token = (round_records.envelope_cas_token(stored)
                         if store_err is None else None)
            readable = isinstance(cas_token, str) and cas_token
            if not readable:
                recovery.append({
                    "seatKey": seat_key,
                    "occurrence": occurrence,
                    "attempt": cur_attempt,
                    "expectSha256": None,
                    "command": None,
                    "note": ("stored envelope has no readable CAS token; a supersede "
                             "command cannot be issued until the record is readable"),
                })
                continue
            envelope, landing_err, _ = _read_landing_envelope(session_dir, rnd, phase, seat_key,
                                                             cur_attempt, occurrence)
            if landing_err is not None:
                # Only `landing-missing` means there is genuinely nothing landed. EVERY other
                # refusal — including one a future reason introduces — means a landing IS present
                # and could not be read, and must be reported rather than silently skipped.
                if landing_err == "landing-missing":
                    continue
                recovery.append({
                    "seatKey": seat_key,
                    "occurrence": occurrence,
                    "attempt": cur_attempt,
                    "expectSha256": cas_token,
                    "command": None,
                    "note": ("the landing file is present but could not be read (%s); no "
                             "supersede command can be issued until the landing is readable"
                             % landing_err),
                })
                continue
            landing_token = round_records.envelope_cas_token(envelope)
            landing_readable = isinstance(landing_token, str) and landing_token
            if not landing_readable or landing_token == cas_token:
                continue
            recovery.append({
                "seatKey": seat_key,
                "occurrence": occurrence,
                "attempt": cur_attempt,
                "expectSha256": cas_token,
                "command": _record_result_recovery_cmd(session_dir, seat_key, occurrence,
                                                       cas_token, cur_attempt),
            })
        if recovery:
            detail = ("--sweep cannot supersede: supersede is compare-and-swap and the CAS token "
                      "is per-slot; supersede each slot individually with the commands listed.")
        else:
            detail = ("--sweep cannot supersede: supersede is compare-and-swap and the CAS token "
                      "is per-slot; no slot has both a stored record and a pending landing "
                      "that differs from the stored envelope — the flags were still "
                      "ineffective and are refused.")
        return _refuse_cmd(session_dir, "record-result", "sweep-supersede-unsupported",
                           phase=phase, rnd=rnd, attempt=cur_attempt,
                           detail=detail, recovery=recovery)
    if sweep:
        return _sweep_record(session_dir, state, "record-result", phase, rnd, cur_attempt, roster,
                             anchor, expect_round=expect_round, expect_phase=expect_phase)

    seat_schema = _seat_result_schema(state)
    if seat_schema is None:
        return _refuse_cmd(session_dir, "record-result", "state-version-unsupported", phase=phase,
                           rnd=rnd, attempt=cur_attempt, seat=_slot_label(seat, occurrence))

    # Validate BEFORE storing: a refusal must leave nothing behind.
    landing_replace_path = None
    assembled = None
    cited_head = _anchor_cited_head(state, session_dir, rnd, phase, cur_attempt)
    cited_head_source = round_records.CITED_HEAD_SOURCE_ORDER_ANCHOR
    if isinstance(seat, str) and seat in roster:
        envelope, _lerr, landing_replace_path = _read_landing_envelope(
            session_dir, rnd, phase, seat, cur_attempt, occurrence)
        if _lerr is not None:
            return _refuse_cmd(session_dir, "record-result", _lerr, phase=phase, rnd=rnd,
                               attempt=cur_attempt, seat=_slot_label(seat, occurrence))
        if (seat_schema == round_records.SEAT_RESULT_SCHEMA_V2 and isinstance(envelope, dict)
                and envelope.get("provenance") == round_records.PROVENANCE_DISPATCH_OBSERVED):
            assembled, ev_reason, ev_extra, assembly_source = _assemble_dispatch_evidence(
                session_dir, envelope, evidence_run_dir, cited_head, phase)
            if assembly_source is not None:
                cited_head_source = assembly_source
            if ev_reason is not None:
                return _refuse_cmd(session_dir, "record-result", ev_reason, phase=phase,
                                   rnd=rnd, attempt=cur_attempt, seat=_slot_label(seat, occurrence),
                                   **ev_extra)
        preflight_envelope = assembled if assembled is not None else envelope
        fault = _preflight_payload_fault(phase, preflight_envelope, seat)
        if fault:
            return _refuse_cmd(session_dir, "record-result", "payload-fault", phase=phase,
                               rnd=rnd, attempt=cur_attempt, seat=seat, detail=fault)
    # axis: a record-result over a damaged journal is refused before it stores a seat record
    if isinstance(phase, str) and phase.startswith("dispatch-") and _journal_damaged(session_dir):
        return _refuse_journal_damaged(
            session_dir, "record-result", phase=phase, rnd=rnd, attempt=cur_attempt,
            seat=_slot_label(seat, occurrence))
    plan, landing_refusal = round_records.validate_landing(
        session_dir, rnd, phase, seat, cur_attempt, current_attempt=cur_attempt, roster=roster,
        supersede=supersede, expect_sha256=expect_sha256, anchor=anchor, occurrence=occurrence,
        seat_result_schema=seat_schema,
        envelope_override=assembled,
        evidence_minted=assembled is not None)
    if landing_refusal is not None:
        return _refuse_cmd(session_dir, "record-result", landing_refusal.get("reason"), phase=phase,
                           rnd=rnd, attempt=cur_attempt, seat=_slot_label(seat, occurrence),
                           detail=landing_refusal.get("message") or landing_refusal.get("storePath"))
    envelope = round_records.envelope_bind_cited_head_source(plan["envelope"], cited_head_source)
    payload_sha = plan["payloadSha256"]
    row_cited_head = cited_head
    if cited_head_source == round_records.CITED_HEAD_SOURCE_RUNNER_VIEW:
        row_cited_head = assembled["headSha"]
    journal_entry = _journal_entry_for_commit(
        session_dir, "record-result", "recorded", phase=phase, round=rnd, attempt=cur_attempt,
        seat=seat, occurrence=occurrence,
        **round_records.recorded_row_fields(envelope, row_cited_head, cited_head_source),
        **_journal_transport_fields(envelope),
        superseded=bool(plan["superseded"]),
        **_journal_addressing_fields(expect_round, expect_phase),
        **_journal_identity_fields(phase, seat, occurrence, cur_attempt))
    try:
        c = round_commit.begin(session_dir, "record-ingest")
        # Stamp the landing file only when read from the full-envelope slot — bare-payload slots
        # stay single-file; the stamped envelope is written to the store copy alone.
        if landing_replace_path is not None and assembled is not None:
            stamped = round_records.envelope_bind_cited_head_source(assembled, cited_head_source)
            c.add_replace_file(landing_replace_path,
                                round_records.canonical(stamped).encode("utf-8"))
        c.add_replace_file(plan["storePath"], round_records.canonical(envelope).encode("utf-8"))
        c.add_journal_append(os.path.join(session_dir, JOURNAL_FILE), journal_entry)
        c.run()
    except round_commit.CommitRefused as exc:
        return _commit_refused_response(session_dir, "record-result", exc, phase=phase, rnd=rnd,
                                      attempt=cur_attempt, seat=_slot_label(seat, occurrence))
    cas_token = round_records.envelope_cas_token(envelope)
    return {"ok": True, "phase": phase, "round": rnd, "attempt": cur_attempt, "seat": seat,
            "occurrence": occurrence, "payloadSha256": payload_sha,
            "casToken": cas_token,
            "superseded": bool(plan["superseded"]),
            "storePath": plan["storePath"]}


def _sweep_record(session_dir, state, cmd, phase, rnd, attempt, roster, anchor,
                  expect_round=None, expect_phase=None):
    """Ingest every unclaimed landing for the pending phase. Idempotent by construction (a seat
    already stored comes back `already-stored`); ANY refusal in the sweep refuses the whole call,
    with the refusing seat's own reason — a landing nobody could ingest is never skipped in
    silence."""
    # axis: a sweep over a damaged journal is refused before it ingests any landing
    if isinstance(phase, str) and phase.startswith("dispatch-") and _journal_damaged(session_dir):
        return _refuse_journal_damaged(session_dir, cmd, phase=phase, rnd=rnd, attempt=attempt)
    for seat_key, occurrence in round_records.roster_slots(roster):
        try:
            skey = round_records.storage_key(seat_key, occurrence)
            lpath = round_records.landing_path(session_dir, rnd, phase, skey, attempt)
            spath = round_records.store_path(session_dir, rnd, phase, skey, attempt)
        except ValueError:
            continue
        try:
            bare_path = round_records.bare_payload_path(session_dir, rnd, phase, skey, attempt)
        except ValueError:
            bare_path = None
        has_landing = os.path.exists(lpath) or (
            bare_path is not None and os.path.exists(bare_path))
        if not has_landing or os.path.exists(spath):
            continue
        envelope, _lerr, _ = _read_landing_envelope(session_dir, rnd, phase, seat_key, attempt,
                                                    occurrence)
        fault = _preflight_payload_fault(phase, envelope, seat_key)
        if fault:
            return _refuse_cmd(session_dir, cmd, "payload-fault", phase=phase, rnd=rnd,
                               attempt=attempt, seat=seat_key, detail=fault)
    seat_schema = _seat_result_schema(state)
    if seat_schema is None:
        return _refuse_cmd(session_dir, cmd, "state-version-unsupported", phase=phase, rnd=rnd,
                           attempt=attempt)
    results = round_records.sweep_landing(session_dir, rnd, phase, current_attempt=attempt,
                                          roster=roster, anchor=anchor,
                                          seat_result_schema=seat_schema)
    recorded = []
    stale_strays = []
    for result in results:
        occurrence = result.get("occurrence") or 0
        if not result.get("ok"):
            if result.get("reason") == "stale-landing":
                stale_strays.append(result)
                continue
            return _refuse_cmd(session_dir, cmd, result.get("reason"), phase=phase, rnd=rnd,
                               attempt=attempt,
                               seat=_slot_label(result.get("seatKey"), occurrence),
                               detail=result.get("message"), recorded=recorded)
        if result.get("reason") == "already-stored":
            continue
        seat = result.get("seatKey")
        skey = round_records.storage_key(seat, occurrence)
        spath = round_records.store_path(session_dir, rnd, phase, skey, attempt)
        stored_envelope, read_err = round_records.read_json(spath)
        if read_err is not None or not isinstance(stored_envelope, dict):
            return _refuse_cmd(session_dir, cmd, "recorded-row-store-unreadable",
                               fault=FAULT_INTERNAL, phase=phase, rnd=rnd, attempt=attempt,
                               seat=seat, storePath=spath)
        cited_head = _anchor_cited_head(state, session_dir, rnd, phase, attempt)
        try:
            cited_head_source = round_records.stored_cited_head_source(stored_envelope)
        except round_records.IncompleteRevisionIdentity as exc:
            return _refuse_cmd(session_dir, cmd, "recorded-row-incomplete",
                               fault=FAULT_INTERNAL, phase=phase, rnd=rnd, attempt=attempt,
                               seat=seat, storePath=spath,
                               detail=", ".join(exc.missing))
        revision_fields = round_records.recorded_row_fields(
            stored_envelope, cited_head, cited_head_source)
        revision_fields.update(_journal_transport_fields(stored_envelope))
        _journal_event(session_dir, cmd, "recorded", phase=phase, round=rnd, attempt=attempt,
                       seat=seat, occurrence=occurrence, **revision_fields,
                       **_journal_addressing_fields(expect_round, expect_phase),
                       **_journal_identity_fields(phase, seat, occurrence, attempt))
        recorded.append(_slot_label(seat, occurrence))
    if stale_strays:
        first = stale_strays[0]
        strays = [{"storageKey": item.get("storageKey"),
                   "landingPaths": item.get("landingPaths")} for item in stale_strays]
        return _refuse_cmd(session_dir, cmd, "stale-landing", phase=phase, rnd=rnd,
                           attempt=attempt,
                           seat=_slot_label(first.get("seatKey"), first.get("occurrence") or 0),
                           detail=first.get("message"), recorded=recorded,
                           storageKey=first.get("storageKey"),
                           landingPaths=first.get("landingPaths"),
                           strays=strays)
    return {"ok": True, "phase": phase, "round": rnd, "attempt": attempt, "recorded": recorded}


def cmd_record_missing(session_dir, seat, attempt, reason, evidence_path=None, occurrence=0,
                       expect_round=None, expect_phase=None):
    """Record a seat that produced NO artifact: the driver writes the `seat-missing/1` envelope
    itself (there is, by definition, nothing for the seat to land) and ingests it through the same
    fences as a result — roster, attempt, session, phase, round, anchor.

    `occurrence` addresses which roster slot of a repeated seat key is absent (default 0), so one
    of two audit targets sharing an id can be recorded missing WITHOUT claiming its twin is."""
    try:
        with round_records.session_lock(session_dir):
            upgrade = _upgrade_gate(session_dir, "record-missing")
            if upgrade is not None:
                return upgrade
            refusal = _commit_recover_or_refuse(session_dir, "record-missing")
            if refusal is not None:
                return refusal
            return _cmd_record_missing_locked(session_dir, seat, attempt, reason, evidence_path,
                                              occurrence=occurrence, expect_round=expect_round,
                                              expect_phase=expect_phase)
    except round_records.SessionLockHeld as held:
        return _lock_held_refusal(session_dir, "record-missing", held)


def _cmd_record_missing_locked(session_dir, seat, attempt, reason, evidence_path=None,
                               occurrence=0, expect_round=None, expect_phase=None):
    state, refusal = _load_driver_state(session_dir, "record-missing")
    if refusal is not None:
        return refusal
    if state.get("_submitUsed"):
        return _refuse_cmd(
            session_dir, "record-missing", "record-submit-interleaved",
            detail=("this session already folded a phase by hand (`submit`); the durable-record and "
                    "hand-submit fold paths are mutually exclusive per session. For this phase, compile "
                    "the artifact and `submit` — do not use `advance` (this session's latch refuses it) "
                    "or `record-missing`."))
    phase, rnd, cur_attempt, refusal = _pending_of(
        session_dir, state, "record-missing", expect_round=expect_round,
        expect_phase=expect_phase)
    if refusal is not None:
        return refusal
    if attempt is not None and attempt != cur_attempt:
        return _refuse_cmd(session_dir, "record-missing", "attempt-not-pending", phase=phase,
                           rnd=rnd, attempt=attempt, pendingAttempt=cur_attempt)
    roster, refusal = _roster_of(session_dir, state, "record-missing", phase, rnd, cur_attempt)
    if refusal is not None:
        return refusal
    evidence = ""
    if evidence_path is not None:
        try:
            with open(evidence_path, encoding="utf-8") as fh:
                evidence = fh.read()
        except OSError as exc:
            return _refuse_cmd(session_dir, "record-missing", "evidence-unreadable", phase=phase,
                               rnd=rnd, attempt=cur_attempt, seat=seat, detail=str(exc))
    seat_schema = _seat_result_schema(state)
    if seat_schema is None:
        return _refuse_cmd(session_dir, "record-missing", "state-version-unsupported", phase=phase,
                           rnd=rnd, attempt=cur_attempt, seat=_slot_label(seat, occurrence))
    if not isinstance(seat, str) or seat not in roster:
        # Let the ingest layer own the enumerated `unknown-seat` refusal rather than respelling it.
        out = round_records.ingest_landing(session_dir, rnd, phase, seat, cur_attempt,
                                           current_attempt=cur_attempt, roster=roster,
                                           seat_result_schema=seat_schema)
        return _refuse_cmd(session_dir, "record-missing", out.get("reason"), phase=phase, rnd=rnd,
                           attempt=cur_attempt, seat=seat, detail=out.get("message"))
    slots = roster.count(seat)
    if isinstance(occurrence, int) and not isinstance(occurrence, bool) and occurrence >= slots:
        return _refuse_cmd(session_dir, "record-missing", "unknown-occurrence", phase=phase,
                           rnd=rnd, attempt=cur_attempt, seat=_slot_label(seat, occurrence),
                           detail="seat %r holds %d roster slot(s); occurrence %d addresses a slot "
                                  "that does not exist" % (seat, slots, occurrence))
    anchor = _orders_anchor(state, session_dir, rnd, phase, cur_attempt)
    cfg = state.get("config") or {}
    repo_root = cfg.get("repoRoot") or os.getcwd()
    pending =((state.get("pending") or {}).get("payload")
               if isinstance(state.get("pending"), dict) else {})
    row = _seat_transport_row(state, phase, seat, occurrence, cfg, pending, repo_root)
    envelope = {
        "schema": round_records.SEAT_MISSING_SCHEMA,
        "session": _meta_session_id(session_dir),
        "round": rnd,
        "phase": phase,
        "seat": seat,
        "attempt": cur_attempt,
        "vendor": row["vendor"],
        "model": row["model"],
        "dispatchRef": (anchor or {}).get("manifestSha256"),
        "orderSha256": ((anchor or {}).get("orders") or {}).get(
            round_records.storage_key(seat, occurrence), round_records.NOT_EMITTED),
        "manifestSha256": (anchor or {}).get("manifestSha256", round_records.NOT_EMITTED),
        "recordedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "reason": reason,
        "evidence": evidence,
        "occurrence": occurrence,
    }
    envelope = round_records.envelope_bind_cited_head_source(
        envelope, round_records.CITED_HEAD_SOURCE_ORDER_ANCHOR)
    try:
        lpath = round_records.landing_path(
            session_dir, rnd, phase, round_records.storage_key(seat, occurrence), cur_attempt)
    except ValueError as exc:
        return _refuse_cmd(session_dir, "record-missing", "invalid-path", phase=phase, rnd=rnd,
                           attempt=cur_attempt, seat=_slot_label(seat, occurrence),
                           detail=str(exc))
    round_records.atomic_write_json(lpath, envelope)
    out = round_records.ingest_landing(session_dir, rnd, phase, seat, cur_attempt,
                                       current_attempt=cur_attempt, roster=roster, anchor=anchor,
                                       occurrence=occurrence, seat_result_schema=seat_schema,
                                       cited_head_source=round_records.CITED_HEAD_SOURCE_ORDER_ANCHOR)
    if not out.get("ok"):
        return _refuse_cmd(session_dir, "record-missing", out.get("reason"), phase=phase, rnd=rnd,
                           attempt=cur_attempt, seat=_slot_label(seat, occurrence),
                           detail=out.get("message") or out.get("storePath"))
    store_path = out.get("storePath")
    stored_envelope, read_err = round_records.read_json(store_path)
    if read_err is not None or not isinstance(stored_envelope, dict):
        return _refuse_cmd(session_dir, "record-missing", "recorded-row-store-unreadable",
                           fault=FAULT_INTERNAL, phase=phase, rnd=rnd, attempt=cur_attempt,
                           seat=_slot_label(seat, occurrence), storePath=store_path)
    cited_head = _anchor_cited_head(state, session_dir, rnd, phase, cur_attempt)
    _journal_event(session_dir, "record-missing", "recorded", phase=phase, round=rnd,
                   attempt=cur_attempt, seat=seat, occurrence=occurrence, reason=reason,
                   **round_records.recorded_row_fields(
                       stored_envelope, cited_head, round_records.CITED_HEAD_SOURCE_ORDER_ANCHOR),
                   **_journal_addressing_fields(expect_round, expect_phase),
                   **_journal_identity_fields(phase, seat, occurrence, cur_attempt))
    return {"ok": True, "phase": phase, "round": rnd, "attempt": cur_attempt, "seat": seat,
            "occurrence": occurrence, "missingReason": reason, "storePath": out.get("storePath")}


# --- advance -------------------------------------------------------------------------------------

def cmd_advance(session_dir, break_lock=False, git=None):
    """Fold the pending phase off its DURABLE records and emit the next action.

    The order is the contract: lock → recover → reconcile → sweep → completeness → assemble → fold
    → emit. A held lock refuses `advance-locked` naming the holder; `--break-lock` breaks it and
    JOURNALS the broken holder as a `caller-error` (breaking someone else's lock is a caller's
    decision, and it is never attest-eligible)."""
    broke = None
    # An unfinished session from an earlier plugin version is refused under the lock below; it is
    # not a session whose lock is broken, and breaking it would journal a row in its folder.
    if break_lock and not _earlier_generation_unfinished(session_dir):
        holder = round_records.break_lock(session_dir) or {}
        broke = {"pid": holder.get("pid"), "createdAt": holder.get("createdAt")}
        _journal_event(session_dir, "advance", "lock-broken", fault=FAULT_CALLER, holder=broke)
    try:
        with round_records.session_lock(session_dir):
            upgrade = _upgrade_gate(session_dir, "advance")
            if upgrade is not None:
                return upgrade
            refusal = _commit_recover_or_refuse(
                session_dir, "advance",
                sidecar_target=_sidecar_target_for_recover(session_dir, git=git))
            if refusal is not None:
                return refusal
            state, refusal = _load_driver_state(session_dir, "advance")
            if refusal is not None:
                return refusal
            return _advance_locked(session_dir, state, git=git, broke=broke)
    except round_records.SessionLockHeld as held:
        return _refuse_cmd(session_dir, "advance", "advance-locked",
                           holder={"pid": held.pid, "createdAt": held.created_at})
    except JournalFaultUnrecordable:
        # The last-resort fail-loud keeps its own contract: `main` reports it nonzero. It is NOT
        # attestable — when the journal AND its marker both failed there is no evidence of either.
        raise
    except Exception as exc:  # noqa: BLE001
        # An unhandled exception inside the fold / adapter / receipt internals is MACHINERY failure,
        # not a caller error: journal it as `driver-internal-error` with a hash of the traceback (the
        # traceback text itself can carry paths and payload fragments, so only its hash is recorded)
        # and let `attest` bind to it. Re-raising instead would leave the run with no referencable
        # evidence of what happened.
        return _refuse_cmd(session_dir, "advance", "driver-internal-exception",
                           fault=FAULT_INTERNAL,
                           detail="%s: %s" % (type(exc).__name__, exc),
                           tracebackSha256=_sha256(traceback.format_exc()))


# --- run-verify ----------------------------------------------------------------------------------

RUN_VERIFY_CMD = "run-verify"
RUN_VERIFY_CLAIM_NAME = "_verify-claim.a%d.json"
RUN_VERIFY_OUTPUT_NAME = "_verify-output.a%d.%s.log"
RUN_VERIFY_PUBLISH_POLL_SECONDS = 0.5
VERIFY_LANDING_NOT_DRIVER_WRITTEN = "verify-landing-not-driver-written"


def _run_verify_slot(state):
    """(round, attempt) of the verify slot the pending step opens, or None. Two shapes open one: a
    pending `run-verify`, and a pending `dispatch-audits` whose payload carries the concurrent
    `verify` slot. Anything else — terminal, no pending, another phase — opens none."""
    pending = state.get("pending")
    if state.get("terminal") or not isinstance(pending, dict):
        return None
    phase = pending.get("phase")
    if phase == P_VERIFY:
        rnd, attempt = pending.get("round"), pending.get("attempt")
    elif phase == P_AUDITS:
        payload = pending.get("payload")
        verify = payload.get("verify") if isinstance(payload, dict) else None
        if not isinstance(verify, dict):
            return None
        rnd, attempt = verify.get("round"), verify.get("attempt")
    else:
        return None
    for value in (rnd, attempt):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
    return rnd, attempt


def _run_verify_pid_alive(pid):
    """True when `pid` names a process that exists. A permission error still means it exists."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _run_verify_claim_pid(claim_path):
    """The pid a claim file records, or None when it is unreadable, malformed or not a real pid."""
    obj, err = round_records.read_json(claim_path)
    if err is not None or not isinstance(obj, dict):
        return None
    pid = obj.get("pid")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return None
    return pid


def _run_verify_take_claim(claim_path):
    """(status, token, stale). `status` is `ok`, `in-progress` or `claim-failed`. The claim is
    created exclusively, so only one runner holds a slot; a claim whose holder is gone (dead pid,
    unreadable, malformed) is removed and taken over once."""
    token = uuid.uuid4().hex
    body = round_records.canonical({"pid": os.getpid(), "token": token,
                                    "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    stale = False
    for _attempt in range(2):
        try:
            fd = os.open(claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pid = _run_verify_claim_pid(claim_path)
            # axis: a live claim holds the slot — a second runner is refused, never let in beside it — see bite-proof record wo_2133_run_verify
            if pid is not None and _run_verify_pid_alive(pid):
                return "in-progress", None, stale
            stale = True
            try:
                os.remove(claim_path)
            except FileNotFoundError:
                pass
            except OSError:
                return "claim-failed", None, stale
            continue
        except OSError:
            return "claim-failed", None, stale
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(body)
                fh.flush()
                os.fsync(fh.fileno())
        except OSError:
            try:
                os.remove(claim_path)
            except OSError:
                pass
            return "claim-failed", None, stale
        return "ok", token, stale
    return "claim-failed", None, stale


def _run_verify_release_claim(claim_path, token):
    """Remove the claim this run took — only while it still carries this run's token."""
    obj, err = round_records.read_json(claim_path)
    if err is not None or not isinstance(obj, dict) or obj.get("token") != token:
        return
    try:
        os.remove(claim_path)
    except OSError:
        pass


def _run_verify_open(session_dir):
    """Takes the session lock itself, then: gate, resolve the verify slot, take the claim. Returns a
    refusal body, or the claim dict `_run_verify_run_and_publish` carries on with. Raises
    `round_records.SessionLockHeld` when the lock is held elsewhere."""
    with round_records.session_lock(session_dir):
        upgrade = _upgrade_gate(session_dir, RUN_VERIFY_CMD)
        if upgrade is not None:
            return upgrade
        refusal = _commit_recover_or_refuse(session_dir, RUN_VERIFY_CMD)
        if refusal is not None:
            return refusal
        state, refusal = _load_driver_state(session_dir, RUN_VERIFY_CMD)
        if refusal is not None:
            return refusal
        slot = _run_verify_slot(state)
        if slot is None:
            return _refuse_cmd(session_dir, RUN_VERIFY_CMD, "run-verify-not-pending",
                               detail="the pending step opens no verify slot")
        rnd, attempt = slot
        skey = round_records.storage_key("verify")
        try:
            landing_path = round_records.bare_payload_path(session_dir, rnd, P_VERIFY, skey, attempt)
            record_path = round_records.store_path(session_dir, rnd, P_VERIFY, skey, attempt)
            landing_dir = round_records.landing_dir(session_dir, rnd, P_VERIFY)
        except ValueError as exc:
            return _refuse_cmd(session_dir, RUN_VERIFY_CMD, "run-verify-not-pending", phase=P_VERIFY,
                               rnd=rnd, attempt=attempt, detail=str(exc))
        if _store_file_exists(landing_path) or _store_file_exists(record_path):
            return _refuse_cmd(session_dir, RUN_VERIFY_CMD, "run-verify-already-landed",
                               phase=P_VERIFY, rnd=rnd, attempt=attempt, path=landing_path,
                               storePath=record_path)
        config = state.get("config") or {}
        command = _verify_command(config)
        bash = None
        if _verify_command_configured(config):
            bash = shutil.which("bash")
            if bash is None:
                return _refuse_cmd(session_dir, RUN_VERIFY_CMD, "run-verify-no-bash", phase=P_VERIFY,
                                   rnd=rnd, attempt=attempt,
                                   detail="bash is not on PATH; the verify command runs under bash -c")
        try:
            os.makedirs(landing_dir, exist_ok=True)
        except OSError as exc:
            return _refuse_cmd(session_dir, RUN_VERIFY_CMD, "run-verify-claim-failed", phase=P_VERIFY,
                               rnd=rnd, attempt=attempt, detail=str(exc))
        claim_path = os.path.join(landing_dir, RUN_VERIFY_CLAIM_NAME % attempt)
        status, token, stale = _run_verify_take_claim(claim_path)
        if status == "in-progress":
            return _refuse_cmd(session_dir, RUN_VERIFY_CMD, "run-verify-in-progress", phase=P_VERIFY,
                               rnd=rnd, attempt=attempt, claimPath=claim_path)
        if status != "ok":
            return _refuse_cmd(session_dir, RUN_VERIFY_CMD, "run-verify-claim-failed", phase=P_VERIFY,
                               rnd=rnd, attempt=attempt, claimPath=claim_path)
        return {"slot": slot, "config": config, "command": command, "bash": bash,
                "landingPath": landing_path, "recordPath": record_path, "landingDir": landing_dir,
                "claimPath": claim_path, "token": token, "stale": stale}


_POST_KILL_DRAIN_SECONDS = 2


def _run_in_process_group(argv, *, timeout=None, **kwargs):
    """subprocess.run in its own process group; on timeout the whole group is killed, so a
    compound verify command leaves no surviving descendants."""
    kwargs.pop("start_new_session", None)
    kwargs.pop("stdin", None)

    def _on_sigterm(signum, frame):
        # The child sits in its own session, so cancelling the driver's group never reaches it;
        # turning SIGTERM into an exception runs the group-kill cleanup below.
        raise SystemExit(128 + signal.SIGTERM)

    try:
        previous = signal.signal(signal.SIGTERM, _on_sigterm)
    except ValueError:  # not the main thread: no handler can be installed
        previous = None
    try:
        return _run_in_process_group_supervised(argv, timeout, kwargs)
    finally:
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)


def _run_in_process_group_supervised(argv, timeout, kwargs):
    with subprocess.Popen(argv, stdin=subprocess.DEVNULL, start_new_session=True, **kwargs) as proc:
        try:
            out, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                proc.kill()
            try:
                out, _ = proc.communicate(timeout=_POST_KILL_DRAIN_SECONDS)
            except subprocess.TimeoutExpired as drain:
                # A descendant that left the group (its own session) still holds the pipe open:
                # return what was read and release the pipes rather than wait on it.
                out = drain.output
                for pipe in (proc.stdout, proc.stderr):
                    if pipe is not None:
                        pipe.close()
            raise subprocess.TimeoutExpired(argv, timeout, output=out)
        except BaseException:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                proc.kill()
            raise
        return subprocess.CompletedProcess(argv, proc.returncode, out, None)


_VERIFY_HEAD_READ_SECONDS = 30


def _verify_run_head(cwd):
    """The commit `git rev-parse HEAD` names in `cwd`, or None when it cannot be read. It reads
    through `subprocess.run` directly, never the verb's injectable `run`, which carries the verify
    command alone."""
    try:
        done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, stdin=subprocess.DEVNULL,
                              capture_output=True, timeout=_VERIFY_HEAD_READ_SECONDS)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    head = done.stdout.decode("utf-8", errors="replace").strip()
    return head if _usable_verify_head(head) else None


def _verify_run_tree(cwd):
    """A digest of the tracked working-tree changes against HEAD in `cwd` (the empty diff digests
    too), or None when it cannot be read. The verify command runs against the working tree, so a
    retry at one head can still run on different contents."""
    try:
        done = subprocess.run(["git", "diff", "HEAD", "--binary", "--no-ext-diff"], cwd=cwd,
                              stdin=subprocess.DEVNULL, capture_output=True,
                              timeout=_VERIFY_HEAD_READ_SECONDS)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return hashlib.sha256(done.stdout).hexdigest()


def _run_verify_execute(session_dir, claim, timeout, run):
    """Run the bound verify command outside the lock. Returns (payload, refusal)."""
    rnd, attempt = claim["slot"]
    if claim["bash"] is None:
        return {"result": "none", "ranBy": "round-driver"}, None
    command = claim["command"]
    cwd = _gate_policy_repo_root(claim["config"])
    exit_code = None
    head_before = _verify_run_head(cwd)
    tree_before = _verify_run_tree(cwd)
    try:
        done = run([claim["bash"], "-c", command], cwd=cwd, stdin=subprocess.DEVNULL,
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        output = done.stdout or b""
        exit_code = done.returncode
        result = "pass" if exit_code == 0 else "fail"
    except subprocess.TimeoutExpired as exc:
        output = exc.output or b""
        result = "timeout"
    except (OSError, ValueError) as exc:
        return None, _refuse_cmd(session_dir, RUN_VERIFY_CMD, "run-verify-spawn-failed",
                                 phase=P_VERIFY, rnd=rnd, attempt=attempt,
                                 detail="%s: %s" % (type(exc).__name__, exc))
    if isinstance(output, str):
        output = output.encode("utf-8", "replace")
    output_path = os.path.join(claim["landingDir"], RUN_VERIFY_OUTPUT_NAME % (attempt, claim["token"]))
    try:
        with open(output_path, "wb") as fh:
            fh.write(output)
            fh.flush()
            os.fsync(fh.fileno())
    except OSError as exc:
        return None, _refuse_cmd(session_dir, RUN_VERIFY_CMD, "run-verify-output-unwritable",
                                 phase=P_VERIFY, rnd=rnd, attempt=attempt, path=output_path,
                                 detail=str(exc))
    payload = {"result": result, "exitCode": exit_code,
               "outputSha256": hashlib.sha256(output).hexdigest(), "outputPath": output_path,
               "command": command, "ranBy": "round-driver"}
    # The head the command ran at: read before it and after it, an unreadable head left out. The
    # after-read is written only when the head moved, so a run that did not move carries one key.
    if head_before is not None:
        payload["headSha"] = head_before
    head_after = _verify_run_head(cwd) if head_before is not None else None
    if head_after is not None and head_after != head_before:
        payload["headShaAfter"] = head_after
    if tree_before is not None:
        payload["treeSha"] = tree_before
        tree_after = _verify_run_tree(cwd)
        if tree_after is not None and tree_after != tree_before:
            payload["treeShaAfter"] = tree_after
    return payload, None


def _run_verify_publish(session_dir, claim, payload, acquired):
    """Takes the session lock itself, then re-checks the slot and lands the payload and its journal
    row in one commit. State is not touched, so the state hash the audits echo does not move.

    `acquired` is a list the helper appends to once the lock is held, so the caller can tell a
    `SessionLockHeld` refused at acquisition (contention) from one raised under the held lock.
    (Renamed from `_run_verify_publish_locked`: the lock is now taken here, not by the caller.)"""
    with round_records.session_lock(session_dir):
        acquired.append(True)
        rnd, attempt = claim["slot"]
        refusal = _commit_recover_or_refuse(session_dir, RUN_VERIFY_CMD)
        if refusal is not None:
            return refusal
        state, refusal = _load_driver_state(session_dir, RUN_VERIFY_CMD)
        if refusal is not None:
            return refusal
        # axis: the slot is re-read under the lock before anything lands — a result computed for a slot that moved or filled is never published — see bite-proof record wo_2133_run_verify
        if (_run_verify_slot(state) != claim["slot"] or _store_file_exists(claim["landingPath"])
                or _store_file_exists(claim["recordPath"])):
            return _refuse_cmd(session_dir, RUN_VERIFY_CMD, "run-verify-slot-moved", phase=P_VERIFY,
                               rnd=rnd, attempt=attempt, path=claim["landingPath"])
        payload_sha = round_records.payload_sha256(payload)
        entry = _journal_entry_for_commit(session_dir, RUN_VERIFY_CMD, "landed", phase=P_VERIFY,
                                          round=rnd, attempt=attempt, payloadSha256=payload_sha,
                                          ts=time.time())
        try:
            c = round_commit.begin(session_dir, "run-verify-land")
            c.add_replace_file(claim["landingPath"], round_records.canonical(payload).encode("utf-8"))
            c.add_journal_append(os.path.join(session_dir, JOURNAL_FILE), entry)
            c.run()
        except round_commit.CommitRefused as exc:
            return _commit_refused_response(session_dir, RUN_VERIFY_CMD, exc, phase=P_VERIFY, rnd=rnd,
                                            attempt=attempt)
        out = {"ok": True, "result": payload["result"], "round": rnd, "attempt": attempt,
               "landingPath": claim["landingPath"], "outputPath": payload.get("outputPath"),
               "payloadSha256": payload_sha}
        if claim["stale"]:
            out["staleClaimTakenOver"] = True
        return out


def _run_verify_run_and_publish(session_dir, claim, timeout, run, sleep, clock, lock_wait):
    payload, refusal = _run_verify_execute(session_dir, claim, timeout, run)
    if refusal is not None:
        return refusal
    rnd, attempt = claim["slot"]
    deadline = clock() + lock_wait
    while True:
        acquired = []
        try:
            return _run_verify_publish(session_dir, claim, payload, acquired)
        except round_records.SessionLockHeld:
            if acquired:
                raise
        if clock() >= deadline:
            return _refuse_cmd(session_dir, RUN_VERIFY_CMD, "run-verify-publish-lock-held",
                               phase=P_VERIFY, rnd=rnd, attempt=attempt,
                               detail="the session lock stayed held for %s seconds; the result is "
                                      "not parked — run the verb again" % lock_wait)
        sleep(RUN_VERIFY_PUBLISH_POLL_SECONDS)


def cmd_run_verify(session_dir, timeout=3600, *, run=None, sleep=None, clock=None, lock_wait=300):
    """Run the session's bound verify command and land the result the driver itself observed.

    The orchestrator never writes a `run-verify` landing: this verb runs the command under
    `bash -c` in the repo root, writes the captured output to a per-claim log, and publishes
    `{result, exitCode, outputSha256, outputPath, command, ranBy}` as the bare landing, together
    with a `run-verify`/`landed` journal row carrying the payload's hash, in one commit. `advance`
    folds a non-CI `run-verify` landing only against that row (see `cmd_submit`).

    The session lock is held to read the slot and take an exclusive claim, released while the
    command runs, and taken again — with a bounded retry — to publish; no state is mutated. A
    refusal answers `ok: false` and exits 0, like `advance`'s."""
    run = run or _run_in_process_group
    sleep = sleep or time.sleep
    clock = clock or time.monotonic
    try:
        claim = _run_verify_open(session_dir)
    except round_records.SessionLockHeld as held:
        return _lock_held_refusal(session_dir, RUN_VERIFY_CMD, held)
    if "slot" not in claim:
        return claim
    try:
        return _run_verify_run_and_publish(session_dir, claim, timeout, run, sleep, clock,
                                           lock_wait)
    finally:
        _run_verify_release_claim(claim["claimPath"], claim["token"])


def _verify_landing_not_driver_written(session_dir, rnd, attempt, payload_sha):
    """None when the journal holds the driver's `run-verify`/`landed` row for exactly this round,
    attempt and payload hash; else the refusal detail. A lossy or unreadable journal cannot vouch
    for anything, so it refuses."""
    rows, lossy = read_journal(session_dir, report_lossy=True)
    if lossy:
        return "the journal is unreadable or lossy, so no driver-written row can be established"
    for row in rows:
        if (isinstance(row, dict) and row.get("cmd") == RUN_VERIFY_CMD
                and row.get("outcome") == "landed" and row.get("round") == rnd
                and row.get("attempt") == attempt and row.get("payloadSha256") == payload_sha):
            return None
    return ("no `run-verify` landed row for round %s attempt %s carries this payload's hash; run "
            "`round_driver.py run-verify` — the driver writes the landing, never the orchestrator"
            % (rnd, attempt))


def _gate_policy_repo_root(config):
    """The repo root a config names, else the cwd — `run-verify` runs the bound verify command there."""
    if isinstance(config, dict):
        repo_root = config.get("repoRoot")
        if isinstance(repo_root, str) and repo_root.strip():
            return repo_root
    return os.getcwd()


def _owner_provenance_shape_predicates():
    """Shape-description strings for ``OWNER_PROVENANCE_FIELD_SHAPES`` → per-field validators."""
    return {
        "non-empty string": lambda value: isinstance(value, str) and value.strip(),
        "non-empty list of non-empty strings": lambda value: (
            isinstance(value, list) and value
            and all(isinstance(entry, str) and entry.strip() for entry in value)
        ),
    }


def _owner_artifact_provenance_well_formed(artifact):
    """Return whether ``artifact`` carries a well-formed ``_provenance`` block.

    Bite axis (#1177-B): a ruling file is attributed only through a well-formed ``_provenance``
    block. Required fields derive from ``OWNER_PROVENANCE_FIELD_SHAPES`` — the single declaration
    of shapes this validator enforces. Bite-proof: WO 1177-B — object-type check, ``ruledBy``
    check, ``ruledAt`` check and ``records`` check; durable build record."""
    if not isinstance(artifact, dict):
        return False
    block = artifact.get("_provenance")
    if not isinstance(block, dict):
        return False
    predicates = _owner_provenance_shape_predicates()
    for field, shape in OWNER_PROVENANCE_FIELD_SHAPES.items():
        predicate = predicates.get(shape)
        if predicate is None or not predicate(block.get(field)):
            return False
    return True


def _advance_fold_failure(session_dir, folded, phase, rnd, attempt):
    """Convert a non-ok cmd_submit answer into advance's refusal."""
    reason = folded.get("reason")
    extra = {}
    if folded.get("foldLanded"):
        extra["foldLanded"] = True
    if reason == "receipt-fault":
        return _refuse_cmd(session_dir, "advance", "receipt-fault", fault=FAULT_INTERNAL,
                           detail=folded.get("detail"), phase=phase, rnd=rnd, attempt=attempt,
                           **extra)
    if reason == FIX_REFUSED_REASON:
        # the chokepoint's own refusal of an apply-fixes report names why in its detail
        return _refuse_cmd(session_dir, "advance", "fold-refused", phase=phase, rnd=rnd,
                           attempt=attempt, detail=folded.get("detail"), **extra)
    return _refuse_cmd(session_dir, "advance", "fold-refused", phase=phase, rnd=rnd,
                       attempt=attempt, detail=reason, **extra)


def _advance_not_folded(session_dir, phase, rnd, attempt, git=None, broke=None,
                        durable_record_owed=False):
    """Honest advance receipt when cmd_submit answered ok but no fold committed."""
    ok_pre, state_pre = load_state(session_dir)
    decision_kind = None
    if ok_pre and state_pre is not None:
        decisions = state_pre.get("decisions")
        if isinstance(decisions, list) and decisions:
            last = decisions[-1]
            if isinstance(last, dict):
                decision_kind = last.get("kind")
    _journal_event(session_dir, "advance", "not-folded", phase=phase, round=rnd,
                   attempt=attempt, reason=decision_kind)
    ok_loaded, state = load_state(session_dir)
    if not ok_loaded or state is None:
        reason, fault, detail = _state_load_fault(session_dir)
        return _refuse_cmd(session_dir, "advance", reason, fault=fault, detail=detail)
    fault = _terminal_receipt_gate(session_dir, state)
    if fault:
        return _receipt_fault_response(fault)
    side = _publish_sidecar(session_dir, state, git=git)
    if side.get("reason"):
        return _refuse_cmd(session_dir, "advance", side["reason"], fault=FAULT_INTERNAL,
                           detail=side.get("detail"))
    response = {"ok": True,
                "notFolded": {"phase": phase, "round": rnd, "attempt": attempt,
                              "reason": decision_kind},
                "terminal": state.get("terminal"),
                "sidecar": side.get("path"),
                "brokeLock": broke}
    if durable_record_owed:
        response["durableRecord"] = {
            "written": False,
            "reason": "no fold committed — the round-cap hand-back returned above the fold "
                      "commit, so the seat record that lands in the fold's commit was never "
                      "written",
        }
    return response


def _read_dispatch_manifest(path):
    """``read_json`` for the dispatch manifest at ``advance`` — never raises.

    ``read_json`` handles invalid UTF-8 at the chokepoint; this wrapper is defence-in-depth."""
    try:
        return round_records.read_json(path)
    except UnicodeDecodeError:
        return None, "not-utf-8"


def _dispatch_manifest_disclosure(mpath, merr):
    """Operator-facing block when the dispatch manifest is absent or unreadable.

    axis: which status is reported (absent vs unreadable) and that a path is named at all — not
    whether the manifest's contents are valid, and never a refusal (a manifest-less run is a
    disclosed degradation by design). A definite ``ENOENT`` / ``ENOTDIR`` is ``absent``; every other
    read failure on a path that exists (or cannot be ruled absent) is ``unreadable``.

    At state v5 the manifest is ignored when every landed envelope is ``seat-result/2``
    (`dispatchManifestIgnored`); provenance is the runner record on each stored envelope.

    Manifest-less runs are a disclosed degradation by design — this never refuses `advance`, only
    surfaces the expected path so an operator is not left guessing after a stall."""
    if merr is None:
        return None
    abs_path = os.path.abspath(mpath)
    try:
        os.lstat(abs_path)
        return {"path": abs_path, "status": "unreadable", "detail": merr}
    except OSError as exc:
        if exc.errno in (errno.ENOENT, errno.ENOTDIR):
            return {"path": abs_path, "status": "absent", "detail": None}
        return {"path": abs_path, "status": "unreadable", "detail": merr}


def _journal_dispatch_manifest_disclosure(session_dir, rnd, phase, attempt, disc):
    if disc is not None:
        _journal_event(session_dir, "advance", "dispatch-manifest-disclosure",
                       phase=phase, round=rnd, attempt=attempt, **disc)


def _attach_dispatch_manifest_disclosure(session_dir, response, rnd, phase, attempt, disc):
    if disc is not None:
        response = dict(response)
        response["dispatchManifest"] = disc
    return response


_ORCHESTRATOR_FULFILLED_USE_SEAT_PATH = object()


def _orchestrator_fulfilled_envelope(session_dir, state, phase, rnd, attempt, seat_key,
                                     occurrence, payload, session_id):
    """The durable `seat-result/1` record an orchestrator-fulfilled fold stores (#1037).

    Same envelope shape the seat path stores, built from the ACCEPTED bare payload rather than from
    a landing envelope: an orchestrator-fulfilled phase emits no orders manifest and no anchor, so
    the order/manifest hashes carry the `not-emitted` literal — the one claim `_anchor_check`
    accepts when there is nothing to check it against. Inventing real-looking hashes here would be
    a claim nobody verified.

    `fulfilledBy` is the provenance the pre-#1037 fold had nowhere to put: a reader of the store
    record alone can tell an orchestrator-fulfilled fold from a seat-written one, which is the
    reconstructability the bare-payload path was missing at vet.
    """
    cfg = state.get("config") or {}
    repo_root = cfg.get("repoRoot") or os.getcwd()
    pending = ((state.get("pending") or {}).get("payload")
               if isinstance(state.get("pending"), dict) else {})
    # One home for the vendor fact. For an orchestrator-fulfilled phase this resolves to None —
    # no seat was dispatched — and None is the honest record; naming a vendor would invent one.
    row = _seat_transport_row(state, phase, seat_key, occurrence, cfg, pending, repo_root)
    schema = _seat_result_schema(state)
    if schema is None:
        raise ValueError("unknown-state-version")
    envelope = {
        "schema": schema,
        "session": session_id,
        "round": rnd,
        "phase": phase,
        "seat": seat_key,
        "attempt": attempt,
        "occurrence": occurrence,
        "vendor": row["vendor"],
        "model": row["model"],
        "dispatchRef": None,
        "orderSha256": round_records.NOT_EMITTED,
        "manifestSha256": round_records.NOT_EMITTED,
        "recordedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "payloadSha256": round_records.payload_sha256(payload),
        "payload": payload,
        "fulfilledBy": "orchestrator",
    }
    if schema == round_records.SEAT_RESULT_SCHEMA_V2:
        envelope["provenance"] = round_records.PROVENANCE_ORCHESTRATOR_FULFILLED
        envelope["envelopeSha256"] = round_records.envelope_sha256(payload, None)
    return round_records.envelope_bind_cited_head_source(
        envelope, round_records.CITED_HEAD_SOURCE_ORDER_ANCHOR)


def _advance_orchestrator_fulfilled_locked(session_dir, state, phase, rnd, attempt, config,
                                           git=None, broke=None):
    """Fold an orchestrator-fulfilled phase from its host-seat bare payload when present.

    When the bare payload is absent, decline so the caller can fold through the durable
    seat-record path. A bare payload that is present but malformed refuses without fallback.

    #1037 closes the two design residuals #960 shipped disclosed:

    * The fold WRITES the durable `seat-result/1` record for the slot, in the SAME commit as the
      fold, so a `verifyResult` folded this way reconstructs from the store record alone — exactly
      as one folded through the seat path does. Same commit is the whole point: a fold with no
      record, or a record with no fold, is the reconstructability gap in a new shape.
    * A bare payload beside a durable seat record is TWO claims for one slot, and the pre-#1037
      precedence resolved it by fiat (bare wins, silently). It now refuses `landing-ambiguous` —
      the same reason, on the same invariant ("one artifact per slot"), that the seat path already
      refuses in `round_records._read_landing_envelope`.

    The refusal is UNCONDITIONAL, including on a re-entry after this path's own fold committed. An
    earlier revision carried a `replay` escape hatch that tried to recognise "the record in this
    slot is one I wrote" from `lastAccepted` plus the record's contents, so such a re-entry would
    re-fold idempotently. It was removed: that predicate re-derives, at `advance` time, the
    already-folded judgment `cmd_submit`'s duplicate contract owns, and the two disagreed in a new
    way on every review round (a foreign record waved through; a record edited under its own
    declared hash; a MISSING record reported `ok` because `cmd_submit` returned `duplicate` before
    the commit that would have written it). It also had no user: the re-entry it protected cannot
    make progress anyway, because a duplicate `submit` returns before `_cmd_submit_prepare` clears
    `state["pending"]`, so the following `next` re-emits the same step. A loud
    `landing-ambiguous` — delete whichever artifact is not the one you meant — is both the ratified
    behaviour and the honest one."""
    roster, refusal = _roster_of(session_dir, state, "advance", phase, rnd, attempt)
    if refusal is not None:
        return refusal
    if not roster:
        return _refuse_cmd(session_dir, "advance", "orchestrator-roster-empty", phase=phase,
                           rnd=rnd, attempt=attempt)
    seat_key = roster[0]
    skey = round_records.storage_key(seat_key)
    path = round_records.bare_payload_path(session_dir, rnd, phase, skey, attempt)
    payload, perr = round_records.read_json(path)
    if perr == "missing":
        slots = _seat_slot_records(session_dir, rnd, phase, attempt, roster)
        if any(env is not None for _seat, _occurrence, env in slots):
            return _ORCHESTRATOR_FULFILLED_USE_SEAT_PATH
        return _refuse_cmd(session_dir, "advance", "orchestrator-payload-missing", phase=phase,
                           rnd=rnd, attempt=attempt, seat=seat_key, path=path,
                           detail="expected host-seat payload at %s" % path)
    if perr is not None:
        return _refuse_cmd(session_dir, "advance", "orchestrator-payload-unreadable",
                           phase=phase, rnd=rnd, attempt=attempt, seat=seat_key, path=path,
                           detail=perr)
    fault = _adapters().orchestrator_payload_fault(phase, payload)
    if fault:
        return _refuse_cmd(session_dir, "advance", fault, phase=phase, rnd=rnd, attempt=attempt,
                           seat=seat_key)
    occurrence = 0
    record_path = round_records.store_path(session_dir, rnd, phase, skey, attempt)
    # One artifact per slot — the seat path's invariant, now enforced on the bare-vs-record pair
    # too. Placed AFTER the shape guard so a malformed payload keeps its own, more actionable
    # reason (#960's fixture): both refuse, neither folds, and the state hash is untouched.
    #
    # axis: that a SECOND claim for the slot REFUSES the fold — not that the fold prefers one
    # artifact over the other. A precedence rule (either direction) folds one claim and
    # silently discards the other, which is the residual this replaces, not a fix for it.
    #
    # `_store_file_exists`, not `os.path.exists`: the same fail-closed existence probe the
    # record-submit fence uses. `os.path.exists` follows symlinks and answers False for a
    # DANGLING one (and on some permission errors), which would fold the bare payload over an
    # unknown store state — the fail-open direction this guard exists to close.
    if _store_file_exists(record_path):
        return _refuse_cmd(
            session_dir, "advance", "landing-ambiguous", phase=phase, rnd=rnd, attempt=attempt,
            seat=seat_key, path=path, storePath=record_path,
            detail="both a host-seat bare payload (%s) and a durable seat record (%s) are "
                   "present for this slot" % (path, record_path))
    # A record must be bound to a live session id — the same precondition
    # `round_records.validate_landing` enforces as `bootstrap-required` before accepting any
    # seat record. This path does not route through that validation, so it refuses here rather
    # than committing an envelope whose `session` is null and whose provenance therefore
    # reconstructs nothing.
    # Read ONCE and carry that exact value into the envelope. Validating the id and then
    # letting the builder re-read `meta.json` leaves a window where the file (skill-owned, so
    # not ours to assume stable) changes between the two reads and the guard passes while the
    # committed envelope carries a different — or null — session.
    session_id = _meta_session_id(session_dir)
    if not session_id:
        return _refuse_cmd(session_dir, "advance", "bootstrap-required", phase=phase, rnd=rnd,
                           attempt=attempt, seat=seat_key,
                           detail="no session id in meta.json — refusing to write a durable "
                                  "seat record that could not carry its session provenance")
    envelope = _orchestrator_fulfilled_envelope(session_dir, state, phase, rnd, attempt,
                                                seat_key, occurrence, payload, session_id)
    cited_head = _anchor_cited_head(state, session_dir, rnd, phase, attempt)
    record = {
        "storePath": record_path,
        "envelope": envelope,
        "journal": _journal_entry_for_commit(
            session_dir, "advance", "recorded", phase=phase, round=rnd, attempt=attempt,
            seat=seat_key, occurrence=occurrence,
            **round_records.recorded_row_fields(
                envelope, cited_head, round_records.CITED_HEAD_SOURCE_ORDER_ANCHOR),
            superseded=False,
            **_journal_transport_fields(envelope),
            **_journal_identity_fields(phase, seat_key, occurrence, attempt)),
    }
    folded = cmd_submit(session_dir, phase, attempt, state_hash(state), payload,
                        _via_advance=True, _durable_record=record)
    if not folded.get("ok"):
        return _advance_fold_failure(session_dir, folded, phase, rnd, attempt)
    if not folded.get("foldLanded"):
        return _advance_not_folded(session_dir, phase, rnd, attempt, git=git, broke=broke,
                                   durable_record_owed=True)
    _journal_event(session_dir, "advance", "advanced", phase=phase, round=rnd, attempt=attempt)
    nxt = cmd_next(session_dir)
    if not nxt.get("ok"):
        return nxt
    ok_after, after = load_state(session_dir)
    if not ok_after or after is None:
        reason, fault_code, detail = _state_load_fault(session_dir)
        return _refuse_cmd(session_dir, "advance", reason, fault=fault_code, detail=detail)
    response = {"ok": True, "folded": {"phase": phase, "round": rnd, "attempt": attempt},
                "nextAction": nxt, "brokeLock": broke}
    if after.get("terminal"):
        side = _publish_sidecar(session_dir, after, git=git)
        if side.get("reason"):
            return _refuse_cmd(session_dir, "advance", side["reason"], fault=FAULT_INTERNAL,
                               detail=side.get("detail"))
        response["terminal"] = after.get("terminal")
        response["sidecar"] = side.get("path")
    return response


def _advance_locked(session_dir, state, git=None, broke=None):
    config = state.get("config") or {}
    if state.get("terminal"):
        # Idempotent on an EXISTING terminal: re-verify the on-disk receipt through the same gate
        # every terminal answer uses, then re-validate and (if stale or missing) republish the
        # sidecar. Nothing is re-folded and no receipt is re-written.
        fault = _terminal_receipt_gate(session_dir, state)
        if fault:
            return _receipt_fault_response(fault)
        side = _publish_sidecar(session_dir, state, git=git)
        if side.get("reason"):
            return _refuse_cmd(session_dir, "advance", side["reason"], fault=FAULT_INTERNAL,
                               detail=side.get("detail"))
        return {"ok": True, "terminal": state.get("terminal"), "idempotent": True,
                "sidecar": side.get("path"), "sidecarRepaired": bool(side.get("repaired"))}
    if state.get("_submitUsed"):
        return _refuse_cmd(session_dir, "advance", "advance-submit-interleaved")
    phase, rnd, attempt, refusal = _pending_of(session_dir, state, "advance")
    if refusal is not None:
        return refusal
    if _adapters().is_orchestrator_fulfilled(phase):
        orch = _advance_orchestrator_fulfilled_locked(session_dir, state, phase, rnd, attempt,
                                                      config, git=git, broke=broke)
        if orch is not _ORCHESTRATOR_FULFILLED_USE_SEAT_PATH:
            return orch
    roster, refusal = _roster_of(session_dir, state, "advance", phase, rnd, attempt)
    if refusal is not None:
        return refusal
    # axis: an advance over a damaged journal is refused before it folds anything
    if isinstance(phase, str) and phase.startswith("dispatch-") and _journal_damaged(session_dir):
        return _refuse_journal_damaged(session_dir, "advance", phase=phase, rnd=rnd,
                                       attempt=attempt)
    anchor = _orders_anchor(state, session_dir, rnd, phase, attempt)

    # 1. reconcile the two-commit window. THE STORE FILE IS AUTHORITATIVE.
    rec = round_records.reconcile(session_dir, rnd, phase,
                                  _journal_record_identities(session_dir, rnd, phase))
    # The storage key carries the SLOT, not the seat: a repeated seat key has one file per
    # occurrence, so mapping back to the bare seat would re-ingest slot 0 twice and never slot 1.
    by_storage = {round_records.storage_key(seat, occurrence): (seat, occurrence)
                  for seat, occurrence in round_records.roster_slots(roster)}
    for entry in rec.get("ingestNow") or []:
        slot = by_storage.get(entry.get("storageKey"))
        # A landing from a SUPERSEDED attempt is not this advance's business — the attempt fence in
        # `round_records` owns it, and refusing the advance over a stale leftover would deadlock a
        # phase that is otherwise complete.
        if slot is None or entry.get("attempt") != attempt:
            continue
        out = cmd_record_result(session_dir, slot[0], attempt=attempt, occurrence=slot[1])
        if not out.get("ok"):
            return out
    for entry in rec.get("reappend") or []:
        slot = by_storage.get(entry.get("storageKey"))
        ident = entry.get("recordIdentity")
        if not isinstance(ident, dict) and slot is not None:
            ident = round_records.record_identity(phase, slot[0], slot[1], entry.get("attempt"))
        storage_key = entry.get("storageKey")
        entry_attempt = entry.get("attempt")
        if storage_key is None or entry_attempt is None:
            return _refuse_cmd(session_dir, "advance", "recorded-row-store-unreadable",
                               fault=FAULT_INTERNAL, phase=phase, rnd=rnd, attempt=attempt,
                               detail="reappend entry missing storageKey or attempt")
        spath = round_records.store_path(session_dir, rnd, phase, storage_key, entry_attempt)
        stored_envelope, read_err = round_records.read_json(spath)
        if read_err is not None or not isinstance(stored_envelope, dict):
            seat_key = slot[0] if slot is not None else None
            return _refuse_cmd(session_dir, "advance", "recorded-row-store-unreadable",
                               fault=FAULT_INTERNAL, phase=phase, rnd=rnd, attempt=attempt,
                               seat=seat_key, storePath=spath)
        cited_head = _anchor_cited_head(state, session_dir, rnd, phase, entry_attempt)
        try:
            cited_head_source = round_records.stored_cited_head_source(stored_envelope)
        except round_records.IncompleteRevisionIdentity as exc:
            seat_key = slot[0] if slot is not None else None
            return _refuse_cmd(session_dir, "advance", "recorded-row-incomplete",
                               fault=FAULT_INTERNAL, phase=phase, rnd=rnd, attempt=attempt,
                               seat=seat_key, storePath=spath,
                               detail=", ".join(exc.missing))
        revision_fields = round_records.recorded_row_fields(
            stored_envelope, cited_head, cited_head_source)
        revision_fields.update(_journal_transport_fields(stored_envelope))
        _journal_event(session_dir, "advance", "recorded", phase=phase, round=rnd,
                       attempt=entry_attempt, seat=slot[0] if slot else None,
                       occurrence=slot[1] if slot else None,
                       reappended=True, recordIdentity=ident, **revision_fields)
    orphans = rec.get("journalOrphan") or []
    if orphans:
        seats = sorted(set(_seat_for_record_identity(session_dir, ident) or str(ident)
                           for ident in orphans))
        return _refuse_cmd(session_dir, "advance", "journal-orphan", fault=FAULT_INTERNAL,
                           phase=phase, rnd=rnd, attempt=attempt, seats=seats,
                           detail="the journal claims record(s) for seat(s) %s that no store file "
                                  "carries" % ", ".join(seats))

    # 2. sweep-ingest whatever landed without a `record-result`.
    swept = _sweep_record(session_dir, state, "advance", phase, rnd, attempt, roster, anchor)
    if not swept.get("ok"):
        return swept

    # 3. completeness — EVERY roster SLOT has a result or a missing envelope for this attempt.
    slots = _seat_slot_records(session_dir, rnd, phase, attempt, roster)
    absent = sorted(_slot_label(seat, occurrence)
                    for seat, occurrence, env in slots if env is None)
    if absent:
        return _refuse_cmd(session_dir, "advance", "incomplete-roster", phase=phase, rnd=rnd,
                           attempt=attempt, seats=absent,
                           detail="no result or missing envelope at attempt %s for seat(s): %s"
                                  % (attempt, ", ".join(absent)))

    # 4. assemble the phase artifact — the phase SHAPE is the adapter's, never this layer's.
    #
    # The adapter consumes a LIST of envelopes and indexes it by each envelope's own
    # (seat, occurrence) — the only shape that can carry two seats sharing one id (a seat-keyed
    # mapping cannot, and `assemble` refuses one outright: `envelopes-not-a-list`).
    records = [env for _seat, _occurrence, env in slots]
    manifest_path = round_records.dispatch_manifest_path(session_dir, rnd, phase, attempt)
    manifest, _merr = _read_dispatch_manifest(manifest_path)
    manifest_disc = _dispatch_manifest_disclosure(manifest_path, _merr)
    _journal_dispatch_manifest_disclosure(session_dir, rnd, phase, attempt, manifest_disc)
    # The driver's OWN emission record (verified against the state anchor; `{}` when unverifiable):
    # the verifier and finder seats read it for the vendor each seat was dispatched on.
    orders_manifest = _anchored_orders_manifest(state, session_dir, rnd, phase, attempt) or {}
    artifact, why = _adapters().assemble(phase, records, state, config,
                                         dispatch_manifest=manifest if _merr is None else None,
                                         session_dir=session_dir, orders_manifest=orders_manifest)
    if why is not None or not isinstance(artifact, dict):
        return _attach_dispatch_manifest_disclosure(
            session_dir,
            _refuse_cmd(session_dir, "advance", "assemble-refused", phase=phase, rnd=rnd,
                        attempt=attempt, detail=why),
            rnd, phase, attempt, manifest_disc)

    artifact_for_fold = dict(artifact)

    # The assembled verify artifact keeps only some of the landed payload's fields, so the hash the
    # chokepoint matches against the driver's journal row is the stored envelope's payload's.
    landed_sha = None
    if phase == P_VERIFY and records and isinstance(records[0].get("payload"), dict):
        landed_sha = round_records.payload_sha256(records[0]["payload"])

    # 5. fold through the EXISTING submit chokepoint (see `cmd_submit`).
    folded = cmd_submit(session_dir, phase, attempt, state_hash(state), artifact_for_fold,
                        _via_advance=True, _landed_payload_sha256=landed_sha)
    if not folded.get("ok"):
        return _attach_dispatch_manifest_disclosure(
            session_dir,
            _advance_fold_failure(session_dir, folded, phase, rnd, attempt),
            rnd, phase, attempt, manifest_disc)
    if not folded.get("foldLanded"):
        return _attach_dispatch_manifest_disclosure(
            session_dir,
            _advance_not_folded(session_dir, phase, rnd, attempt, git=git, broke=broke),
            rnd, phase, attempt, manifest_disc)
    _journal_event(session_dir, "advance", "advanced", phase=phase, round=rnd, attempt=attempt)
    # The `advanced` journal row has no partner artifact — it is a log-only row and stays outside
    # any commit so a later reader does not try to pair it with state or a manifest.

    # 6. emit the next action (through `cmd_next`, so the pending/journal contract is one home).
    nxt = cmd_next(session_dir)
    if not nxt.get("ok"):
        return nxt
    ok_after, after = load_state(session_dir)
    if not ok_after or after is None:
        reason, fault, detail = _state_load_fault(session_dir)
        return _refuse_cmd(session_dir, "advance", reason, fault=fault, detail=detail)
    response = {"ok": True, "folded": {"phase": phase, "round": rnd, "attempt": attempt},
                "nextAction": nxt, "brokeLock": broke}
    if after.get("terminal"):
        side = _publish_sidecar(session_dir, after, git=git)
        if side.get("reason"):
            return _attach_dispatch_manifest_disclosure(
                session_dir,
                _refuse_cmd(session_dir, "advance", side["reason"], fault=FAULT_INTERNAL,
                            detail=side.get("detail")),
                rnd, phase, attempt, manifest_disc)
        response["terminal"] = after.get("terminal")
        response["sidecar"] = side.get("path")
    return _attach_dispatch_manifest_disclosure(session_dir, response, rnd, phase, attempt,
                                                manifest_disc)


# --- the handback sidecar (§6) -------------------------------------------------------------------

def _sidecar_path(gitdir):
    return os.path.join(gitdir, SIDECAR_DIRNAME, SIDECAR_FILE)


def _git_result_seam(run_git):
    """Adapt the injected plain-output `git` seam to the `run_git_result`-shaped seam
    `store_core.get_worktree_gitdir` reads through.

    A seam that yields no output is reported UNAVAILABLE, never an authoritative decline: the
    sidecar must then REFUSE (`sidecar-gitdir-unresolvable`), not fall through the
    not-a-repository classification onto a working directory."""
    def run(cwd, *args):
        out = run_git(cwd, *args)
        if out:
            return store_core.GitResult(out, store_core.GIT_OK, None)
        return store_core.GitResult(
            None, store_core.GIT_UNAVAILABLE,
            "injected git seam produced no output for %s at %r" % (" ".join(args), cwd))
    return run


def _prepare_sidecar(session_dir, state, git=None, journal_cmd="advance", receipt_bytes=None):
    """Build and validate a sidecar for a terminal session without writing.

    Returns ``{"ok": True, "path": ..., "repaired": False, "needs_write": False}`` when the on-disk
    sidecar is already fresh, or a write bundle with ``needs_write: True`` when publication is
    required. Refusals use ``{"reason": ..., "detail": ...}``."""
    run_git = git or store_core.run_git
    config = state.get("config") or {}
    repo_root = config.get("repoRoot") or os.getcwd()
    try:
        gitdir = store_core.get_worktree_gitdir(
            repo_root, run=_git_result_seam(git) if git is not None else None)
    except store_core.RepoRootUnavailable as exc:
        return {"reason": "sidecar-gitdir-unresolvable", "detail": str(exc)}
    head_sha = run_git(repo_root, "rev-parse", "HEAD")
    if not head_sha:
        return {"reason": "sidecar-gitdir-unresolvable",
                "detail": "git could not resolve HEAD in %r" % repo_root}
    receipt_path = os.path.join(session_dir, RECEIPT_FILE)
    if receipt_bytes is None:
        try:
            with open(receipt_path, "rb") as fh:
                receipt_bytes = fh.read()
        except OSError as exc:
            return {"reason": "sidecar-receipt-unreadable", "detail": str(exc)}
    expected_base_ref = config.get("baseBranch") or "unpinned"
    path = _sidecar_path(gitdir)
    existing, err = round_records.read_json(path)
    if err is None and isinstance(existing, dict):
        stale, _why = round_records.sidecar_stale(existing, head_sha=head_sha,
                                                  receipt_bytes=receipt_bytes,
                                                  session_dir=session_dir)
        if not stale and existing.get("baseRef") != expected_base_ref:
            stale = True
        if not stale:
            return {"ok": True, "path": path, "repaired": False, "needs_write": False}
    branch = run_git(repo_root, "rev-parse", "--abbrev-ref", "HEAD") or "detached"
    base_ref = expected_base_ref
    base_pin = config.get("baseRef")
    base_sha = run_git(repo_root, "rev-parse", "--verify", "--quiet",
                       "%s^{commit}" % base_pin) if base_pin else None
    certification = state.get("certification") or {}
    sidecar = round_records.build_sidecar(
        repoId=(store_core.normalize_remote(run_git(repo_root, "remote", "get-url", "origin"))
                or os.path.realpath(repo_root)),
        branch=branch,
        headSha=head_sha,
        baseRef=base_ref,
        baseSha=base_sha or "unresolved",
        diffSha256=_sha256(state.get("reviewedDiff") or ""),
        verdict=state.get("terminal") or "unknown",
        certificationShape=(certification.get("shape")
                            or ("attested" if state.get("_attestation") else "withheld")),
        receiptPath=receipt_path,
        receiptSha256=hashlib.sha256(receipt_bytes).hexdigest(),
        policySha256=_sha256(_canonical(config)),
        sessionDir=session_dir)
    ok, why = round_records.validate_sidecar(sidecar)
    if not ok:
        return {"reason": "sidecar-invalid", "detail": why}
    receipt_sha = sidecar["receiptSha256"]
    begin_entry = _journal_entry_for_commit(session_dir, journal_cmd, "sidecar-repair-begin",
                                            sidecarPath=path, receiptSha256=receipt_sha)
    repaired_entry = _journal_entry_for_commit(session_dir, journal_cmd, "sidecar-repaired",
                                               sidecarPath=path, receiptSha256=receipt_sha)
    return {
        "ok": True,
        "needs_write": True,
        "path": path,
        "sidecar_bytes": round_records.canonical(sidecar).encode("utf-8"),
        "resolver": lambda: _sidecar_path(gitdir),
        "journal_entries": [begin_entry, repaired_entry],
        "receiptSha256": receipt_sha,
    }


def _commit_sidecar_parts(session_dir, prepared):
    """Apply a prepared sidecar write bundle in one commit."""
    try:
        c = round_commit.begin(session_dir, "sidecar-publish")
        c.add_external_sidecar(prepared["sidecar_bytes"], prepared["resolver"])
        for entry in prepared["journal_entries"]:
            c.add_journal_append(os.path.join(session_dir, JOURNAL_FILE), entry)
        c.run()
    except round_commit.CommitRefused as exc:
        return {"reason": exc.reason, "detail": exc.detail}
    return {"ok": True, "path": prepared["path"], "repaired": True}


def _publish_sidecar(session_dir, state, git=None, *, defer_commit=False):
    """Publish `<gitdir>/superheroes/review-receipt.json` for a terminal session.

    Sidecar bytes and its two journal halves are one commit when a write is required — the commit
  carries correctness, not ordering between journal and file. A sidecar that is already fresh
    (`round_records.sidecar_stale` says no) is left exactly as it is.

    Nothing in this PR READS the sidecar for enforcement — the hook that does is a later PR — so
    there is deliberately no gate here."""
    prepared = _prepare_sidecar(session_dir, state, git=git, journal_cmd="advance")
    if prepared.get("reason"):
        return prepared
    if not prepared.get("needs_write"):
        return {"ok": True, "path": prepared["path"], "repaired": False}
    if defer_commit:
        return prepared
    return _commit_sidecar_parts(session_dir, prepared)


# --- attest (§5) ----------------------------------------------------------------------------------

def _attest_recovered(events, index, phase):
    """A journalled failure that a LATER successful `advance` of the same phase recovered is void —
    the run went on to do the thing the failure claims it could not."""
    for later in events[index:]:
        if later.get("cmd") == "advance" and later.get("outcome") == "advanced" \
                and later.get("phase") == phase:
            return True
    return False


def _resolve_failure_ref(session_dir, ref):
    """(binding, refusal_reason) for `--failure <journal-seq|marker:HASH>`.

    ELIGIBILITY IS ALLOWLIST-ONLY. A journal sequence binds only to an event this driver stamped
    `driver-internal-error`; every `caller-error` (unknown seat, malformed artifact, wrong phase,
    bootstrap-required, premature advance, lock refusal, CAS refusal) is
    refused `attest-ineligible`. There is deliberately NO issue-reference path: a caller can file
    any open issue, which would make the eligibility self-authorizing.

    `marker:<entryHash>` binds to a `_mark_journal_fault` row — the `journal-degraded` class, whose
    defining property is that the journal append failed but the marker SUCCEEDED.
    `JournalFaultUnrecordable` (both writes failed) has no row by construction and can never be its
    own evidence."""
    events = read_journal(session_dir)
    session_id = _meta_session_id(session_dir)
    if isinstance(ref, str) and ref.startswith("marker:"):
        want = ref[len("marker:"):]
        for row in read_fault_markers(session_dir):
            if row.get("entryHash") != want:
                continue
            if session_id is not None and row.get("sessionId") not in (None, session_id):
                return None, "attest-session-mismatch"
            marker_seq = row.get("seq")
            start = (marker_seq - 1) if isinstance(marker_seq, int) and marker_seq >= 1 else 0
            if _attest_recovered(events, start, row.get("phase")):
                return None, "attest-failure-recovered"
            return {"ref": ref, "kind": "marker", "class": "journal-degraded",
                    "entryHash": want, "phase": row.get("phase"), "event": row}, None
        return None, "attest-failure-unknown"
    try:
        seq = int(ref)
    except (TypeError, ValueError):
        return None, "attest-failure-unknown"
    if seq < 1 or seq > len(events):
        return None, "attest-failure-unknown"
    event = events[seq - 1]
    if event.get("fault") != FAULT_INTERNAL:
        return None, "attest-ineligible"
    if session_id is not None and event.get("session") not in (None, session_id):
        return None, "attest-session-mismatch"
    if _attest_recovered(events, seq, event.get("phase")):
        return None, "attest-failure-recovered"
    return {"ref": str(seq), "kind": "journal", "class": event.get("reason"), "seq": seq,
            "phase": event.get("phase"), "event": event}, None


def _session_artifact_hashes(session_dir, exclude=None):
    """sha256 of EVERY file under the session dir, keyed by its path relative to it — the evidence
    an attested (uncertified) handback rests on, since no certification vouches for it.

    `exclude` names relative paths omitted from the digest set — the attestation receipt itself is
    excluded because it is written after the evidence snapshot and cannot hash itself."""
    skip = set(exclude or ())
    out = {}
    for root, dirs, files in os.walk(session_dir):
        dirs.sort()
        for name in sorted(files):
            full = os.path.join(root, name)
            rel = os.path.relpath(full, session_dir)
            if rel in skip:
                continue
            try:
                with open(full, "rb") as fh:
                    out[rel] = hashlib.sha256(fh.read()).hexdigest()
            except OSError:
                out[rel] = None
    return out


def _attest_roster(session_dir, state):
    """{slot: recorded|missing|superseded|absent} for the pending phase's FULL roster.

    Keyed by SLOT (`<seat>` / `<seat>#<n>`) so a repeated seat key reports BOTH of its dispositions
    — an attestation that collapsed two same-id targets onto one key would under-report the very
    coverage the attestation exists to disclose."""
    pending = state.get("pending")
    if not isinstance(pending, dict) or not pending.get("phase"):
        return {}
    phase, rnd, attempt = pending.get("phase"), pending.get("round"), pending.get("attempt")
    try:
        roster, reason = _adapters().roster_for(phase, state, state.get("config") or {})
    except Exception:  # noqa: BLE001 — an adapter fault must never crash the attestation
        return {}
    if reason is not None or not isinstance(roster, (list, tuple)):
        return {}
    roster = [s for s in roster if isinstance(s, str)]
    superseded = set(e.get("seat") for e in read_journal(session_dir) if e.get("superseded"))
    out = {}
    for seat, occurrence, env in _seat_slot_records(session_dir, rnd, phase, attempt, roster):
        label = _slot_label(seat, occurrence)
        if env is None:
            out[label] = "absent"
        elif seat in superseded:
            out[label] = "superseded"
        elif env.get("schema") == round_records.SEAT_MISSING_SCHEMA:
            out[label] = "missing"
        else:
            out[label] = "recorded"
    return out


def build_attestation_receipt(session_dir, state, binding, note, roster=None):
    """The `receipt-attested/1` terminal: verdict `uncertified-manual`, NO certification block, the
    attestation's own evidence, sha256 of every artifact under the session dir, and the full roster
    with each seat's disposition.

    `cmd_attest` finalizes `artifacts` after every other session mutation except the live journal and
    loop-state: the receipt is written once against the final bytes, then the sidecar is published
    against that receipt (which appends sidecar-repair journal lines), so `driver-journal.jsonl` and
    `loop-state.json` (and its mirror) are excluded from the digest set — same contract class as STATE_FILE. The
    receipt file itself is excluded because it is written last and cannot hash itself. `roster` may be supplied when `state` is
    already terminal (pending cleared) but was captured from the failure phase beforehand."""
    receipt = build_receipt(state, session_dir, form=RECEIPT_FORM_ATTESTED)
    for key in _receipt_forbidden_keys(RECEIPT_FORM_ATTESTED):
        receipt.pop(key, None)
    receipt["schema"] = RECEIPT_ATTESTED_SCHEMA
    receipt["verdict"] = ATTESTED_VERDICT
    receipt["attestation"] = {
        "failure": binding.get("ref"),
        "kind": binding.get("kind"),
        "class": binding.get("class"),
        "phase": binding.get("phase"),
        "event": binding.get("event"),
        "note": note,
        "attestedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "stateSchemaVersion": _state_version(state),
    }
    receipt["roster"] = roster if roster is not None else _attest_roster(session_dir, state)
    return receipt


def cmd_attest(session_dir, failure_ref, note, git=None):
    """Record an UNCERTIFIED manual attestation over a journalled driver-internal failure.

    Refuses outright if any terminal receipt already exists — an attestation is what a session
    writes INSTEAD of a terminal receipt, never over one."""
    if (not isinstance(note, str) or not note.strip()) \
            and not _earlier_generation_unfinished(session_dir):
        return _refuse_cmd(session_dir, "attest", "attest-note-required")
    try:
        with round_records.session_lock(session_dir):
            upgrade = _upgrade_gate(session_dir, "attest")
            if upgrade is not None:
                return upgrade
            refusal = _commit_recover_or_refuse(
                session_dir, "attest",
                sidecar_target=_sidecar_target_for_recover(session_dir, git=git))
            if refusal is not None:
                return refusal
            state, refusal = _load_driver_state(session_dir, "attest")
            if refusal is not None:
                return refusal
            receipt_refusal = _receipt_write_refusal(
                session_dir,
                terminal_reason="terminal-receipt-exists",
                untrusted_reason="terminal-receipt-unreadable",
            )
            if receipt_refusal or state.get("terminal"):
                return _refuse_cmd(session_dir, "attest", receipt_refusal or "terminal-receipt-exists")
            binding, why = _resolve_failure_ref(session_dir, failure_ref)
            if why is not None:
                return _refuse_cmd(session_dir, "attest", why, detail=str(failure_ref))
            artifact_snapshot = _session_artifact_hashes(session_dir,
                                                         exclude=(RECEIPT_FILE,
                                                                  RECEIPT_INTERIM_FILE,
                                                                  STATE_FILE,
                                                                  MIRROR_FILE,
                                                                  JOURNAL_FILE,
                                                                  round_records.LOCK_FILE))
            return _cmd_attest_locked(session_dir, failure_ref, note, git=git, state=state,
                                    binding=binding, artifact_snapshot=artifact_snapshot)
    except round_records.SessionLockHeld as held:
        return _lock_held_refusal(session_dir, "attest", held)


def _cmd_attest_locked(session_dir, failure_ref, note, git=None, state=None, binding=None,
                       artifact_snapshot=None):
    roster = _attest_roster(session_dir, state)
    _set_terminal(state, ATTESTED_VERDICT)
    state["certification"] = None
    state["_attestation"] = {
        "failure": binding.get("ref"),
        "kind": binding.get("kind"),
        "class": binding.get("class"),
        "phase": binding.get("phase"),
        "event": binding.get("event"),
        "note": note,
        "attestedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "stateSchemaVersion": _state_version(state),
    }
    state["step"] = P_TERMINAL
    state["pending"] = None
    state["_receiptFinalized"] = True
    receipt = build_attestation_receipt(session_dir, state, binding, note, roster=roster)
    receipt["artifacts"] = artifact_snapshot
    ok, invalid = validate_receipt(receipt)
    if not ok:
        return _refuse_cmd(session_dir, "attest", "attested-receipt-invalid", fault=FAULT_INTERNAL,
                           detail=invalid)
    path = os.path.join(session_dir, RECEIPT_FILE)
    receipt_bytes = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    prepared = _prepare_sidecar(session_dir, state, git=git, journal_cmd="advance",
                                receipt_bytes=receipt_bytes)
    if prepared.get("reason"):
        return _refuse_cmd(session_dir, "attest", prepared["reason"], fault=FAULT_INTERNAL,
                           detail=prepared.get("detail"))
    attested_entry = _journal_entry_for_commit(session_dir, "attest", "attested",
                                               phase=binding.get("phase"),
                                               failure=binding.get("ref"),
                                               attestClass=binding.get("class"))
    try:
        c = round_commit.begin(session_dir, "attest-finalize")
        c.add_replace_file(path, receipt_bytes)
        _stage_state(c, session_dir, _canonical(state).encode("utf-8"))
        c.add_journal_append(os.path.join(session_dir, JOURNAL_FILE), attested_entry)
        if prepared.get("needs_write"):
            c.add_external_sidecar(prepared["sidecar_bytes"], prepared["resolver"])
            for entry in prepared["journal_entries"]:
                c.add_journal_append(os.path.join(session_dir, JOURNAL_FILE), entry)
        c.run()
    except round_commit.CommitRefused as exc:
        if exc.reason in ("sidecar-invalid", "sidecar-target-unresolvable",
                          "sidecar-receipt-unreadable"):
            return _refuse_cmd(session_dir, "attest", exc.reason, fault=FAULT_INTERNAL,
                               detail=exc.detail)
        if exc.reason == "commit-apply-failed":
            return _refuse_cmd(session_dir, "attest", "attested-receipt-unwritable",
                               fault=FAULT_INTERNAL, detail=exc.detail)
        return _commit_refused_response(session_dir, "attest", exc)
    side_path = prepared.get("path")
    return {"ok": True, "verdict": ATTESTED_VERDICT, "receiptPath": path,
            "attestation": receipt["attestation"], "roster": receipt["roster"],
            "sidecar": side_path}


def cmd_checkpoint(session_dir, stop_reason):
    """Write an interim receipt at a non-terminal stop.

    Re-invoking checkpoint after an earlier checkpoint is allowed — a run can stop, resume, and stop
    again — and each write supersedes the previous interim. The write-once terminal rule applies only
    to certified/attested receipts, not to interim supersession."""
    if (stop_reason not in CHECKPOINT_STOP_REASONS
            and not _earlier_generation_unfinished(session_dir)):
        return _refuse_cmd(session_dir, "checkpoint", "checkpoint-stop-reason-unknown",
                           detail=stop_reason)
    try:
        with round_records.session_lock(session_dir):
            upgrade = _upgrade_gate(session_dir, "checkpoint")
            if upgrade is not None:
                return upgrade
            refusal = _commit_recover_or_refuse(session_dir, "checkpoint")
            if refusal is not None:
                return refusal
            state, refusal = _load_driver_state(session_dir, "checkpoint")
            if refusal is not None:
                return refusal
            if state.get("terminal"):
                return _refuse_cmd(session_dir, "checkpoint", "checkpoint-session-terminal")
            receipt_refusal = _receipt_write_refusal(
                session_dir,
                terminal_reason="checkpoint-terminal-receipt-exists",
                untrusted_reason="checkpoint-terminal-receipt-unreadable",
            )
            if receipt_refusal:
                return _refuse_cmd(session_dir, "checkpoint", receipt_refusal)
            receipt = build_interim_receipt(state, session_dir, stop_reason)
            ok, invalid = validate_receipt(receipt)
            if not ok:
                return _refuse_cmd(session_dir, "checkpoint", "interim-receipt-invalid",
                                   fault=FAULT_INTERNAL, detail=invalid)
            path = os.path.join(session_dir, RECEIPT_INTERIM_FILE)
            receipt_bytes = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
            checkpoint_entry = _journal_entry_for_commit(
                session_dir, "checkpoint", "checkpointed", stopReason=stop_reason)
            try:
                c = round_commit.begin(session_dir, "checkpoint")
                c.add_replace_file(path, receipt_bytes)
                c.add_journal_append(os.path.join(session_dir, JOURNAL_FILE), checkpoint_entry)
                c.run()
            except OSError as exc:
                return _refuse_cmd(session_dir, "checkpoint", "interim-receipt-unwritable",
                                   fault=FAULT_INTERNAL, detail=str(exc))
            except round_commit.CommitRefused as exc:
                if exc.reason == "commit-apply-failed":
                    return _refuse_cmd(session_dir, "checkpoint", "interim-receipt-unwritable",
                                       fault=FAULT_INTERNAL, detail=exc.detail)
                return _commit_refused_response(session_dir, "checkpoint", exc)
            return {"ok": True, "receiptPath": path, "schema": receipt["schema"],
                    "stop": receipt["stop"]}
    except round_records.SessionLockHeld as held:
        return _lock_held_refusal(session_dir, "checkpoint", held)


def _parse_seat_map(raw):
    """Parse `next --seat-map <path>`: (seat_map, None) or (None, 'seat-map-unparseable'). A file
    that does not read, does not parse, or is not a JSON OBJECT all fail loud — same discipline as
    `--vendors`, because a silently-dropped seat map leaves the record layer with no vendor source
    on round 1 and every seat's provenance unverified."""
    try:
        with open(raw, encoding="utf-8") as fh:
            loaded = json.load(fh)
    except (OSError, ValueError):
        return None, "seat-map-unparseable"
    if not isinstance(loaded, dict):
        return None, "seat-map-unparseable"
    return loaded, None


def _parse_vendors(raw):
    """Parse the `--vendors` CLI value. Accepts BOTH a JSON list ('["codex","cursor"]') and a
    comma-separated string ('codex,cursor'). Returns (vendors, None) on success or (None, reason)
    on ANY failure — an unparseable JSON, an empty result, non-string members, or an unknown vendor
    all fail loud so the CLI can exit nonzero. NEVER falls through to the ["claude"] default
    silently: a silent fall-through drops cross-vendor independence and stamps every audit degraded
    when other vendors are actually live (same fail-open class as the v14 journal-swallow, #507)."""
    stripped = raw.strip()
    if stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
        except ValueError:
            return None, "vendors-unparseable"
        if not isinstance(parsed, list):
            return None, "vendors-unparseable"
        members = parsed
    else:
        members = stripped.split(",")
    cleaned = []
    for member in members:
        if not isinstance(member, str):
            return None, "vendors-unparseable"
        member = member.strip()
        if member:
            cleaned.append(member)
    if not cleaned:
        return None, "vendors-unparseable"
    for member in cleaned:
        if member not in model_registry.VENDORS:
            return None, "vendors-unknown: %s" % member
    return cleaned, None


def build_parser():
    parser = argparse.ArgumentParser(
        description="the one-entrypoint review-loop round driver (#507)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pn = sub.add_parser("next")
    cli_contract.add_argument(pn, "--session-dir", contract="existing-directory", required=True)
    cli_contract.add_argument(pn, "--leg", contract="free-text", default=None)
    cli_contract.add_argument(pn, "--vendors", contract="free-text", default=None,
                              help="live vendors (fresh state only): a JSON list "
                                   "('[\"codex\",\"cursor\"]') OR a comma-separated string "
                                   "('codex,cursor'). Unparseable / unknown / on non-fresh state "
                                   "→ fails loud (nonzero), never a silent default")
    cli_contract.add_argument(pn, "--verify-command", contract="free-text", default=None)
    cli_contract.add_argument(pn, "--break-it-interpreter", contract="free-text", default=None,
                              help="the Python launcher break-it runs use (fresh state only): "
                                   "stored as config breakItInterpreter and read instead of the "
                                   "verify command. On non-fresh state → fails loud (nonzero)")
    cli_contract.add_argument(pn, "--max-rounds", contract="integer", default=None, type=int,
                              help="the round cap (fresh state only; default and largest value "
                                   "%d): a positive integer no larger than the default, else "
                                   "refused with max-rounds-invalid. Ignored on a loaded state"
                                   % round_phases.ROUND_CAP)
    cli_contract.add_argument(pn, "--fix-batch-cap", contract="integer", default=None, type=int)
    cli_contract.add_argument(pn, "--diff-path", contract="free-text", default=None,
                              help="round-1 reviewed diff (fresh state only)")
    cli_contract.add_argument(pn, "--repo-root", contract="repo-root", default=None,
                              help="repo root the base guard resolves the pinned base against "
                                   "(default: cwd)")
    cli_contract.add_argument(pn, "--prior-comments", contract="free-text", default=None,
                              help="PR-mode prior review comments JSON (a list) for the "
                                   "author-justification post-filter (fresh state only)")
    cli_contract.add_argument(pn, "--earlier-findings", contract="free-text", default=None,
                              help="PR-mode earlier review record JSON (what `review_record.py read --pr N` "
                                   "prints) naming the PR's earlier findings, so a repeat of one keeps its "
                                   "earlier outcome (fresh state only). Missing / unreadable / refused → no "
                                   "record-sourced findings, disclosed; never a crash")
    cli_contract.add_argument(pn, "--seat-map", contract="free-text", default=None,
                              help="the #510 seat map JSON object (fresh state only) seeding "
                                   "config/state so round 1 has a vendor source. Unparseable / "
                                   "non-object / on non-fresh state → fails loud (nonzero), never "
                                   "a silent default")
    cli_contract.add_argument(pn, "--copy-proof", contract="free-text", default=None,
                              help="the copy-proof JSON (fresh state only): files the change copies byte "
                                   "for byte from a named source, each with the sha256 of its bytes at the "
                                   "head. A proven copy is left out of every seat's diff. Unreadable / "
                                   "malformed / on non-fresh state → fails loud (nonzero), never a silent "
                                   "'no proof'")
    cli_contract.add_argument(pn, "--records-path", contract="free-text", default=None,
                              help="durable round-records file path (fresh state only)")

    ps = sub.add_parser("submit")
    cli_contract.add_argument(ps, "--session-dir", contract="existing-directory", required=True)
    cli_contract.add_argument(ps, "--phase", contract="free-text", required=True)
    cli_contract.add_argument(ps, "--attempt", contract="integer", required=True, type=int)
    cli_contract.add_argument(ps, "--state-hash", contract="free-text", default=None)
    cli_contract.add_argument(ps, "--artifact", contract="free-text", required=True,
                              help="path to the artifact JSON")

    pr = sub.add_parser("record-result")
    cli_contract.add_argument(pr, "--session-dir", contract="existing-directory", required=True)
    cli_contract.add_argument(pr, "--seat", contract="free-text", default=None,
                              help="the roster seat to ingest; not needed with --sweep")
    cli_contract.add_argument(pr, "--attempt", contract="integer", default=None, type=int)
    cli_contract.add_argument(pr, "--supersede", contract="boolean-flag")
    cli_contract.add_argument(pr, "--expect-sha256", contract="free-text", default=None)
    cli_contract.add_argument(pr, "--sweep", contract="boolean-flag")
    cli_contract.add_argument(pr, "--occurrence", contract="integer", default=0, type=int,
                              help="which roster SLOT of a repeated seat key this envelope is "
                                   "(default 0). Two distinct audit targets can legitimately "
                                   "share one id; without this the second is unaddressable")
    cli_contract.add_argument(pr, "--round", contract="integer", default=None, type=int,
                              help="expected pending round; when supplied, a mismatch refuses")
    cli_contract.add_argument(pr, "--phase", contract="free-text", default=None,
                              help="expected pending phase; when supplied, a mismatch refuses")
    cli_contract.add_argument(pr, "--evidence-run-dir", contract="free-text", default=None,
                              dest="evidence_run_dir",
                              help="runner run directory whose journal supplies execution evidence "
                                   "for a dispatch-observed landing under state schema v5")

    pm = sub.add_parser("record-missing")
    cli_contract.add_argument(pm, "--session-dir", contract="existing-directory", required=True)
    cli_contract.add_argument(pm, "--seat", contract="free-text", required=True)
    cli_contract.add_argument(pm, "--attempt", contract="integer", required=True, type=int)
    pm.add_argument("--reason", required=True, choices=list(round_records.MISSING_REASONS))
    cli_contract.add_argument(pm, "--evidence", contract="free-text", default=None)
    cli_contract.add_argument(pm, "--occurrence", contract="integer", default=0, type=int,
                              help="which roster SLOT of a repeated seat key is absent (default 0), "
                                   "so one of two same-id targets can be recorded missing without "
                                   "claiming its twin is")
    cli_contract.add_argument(pm, "--round", contract="integer", default=None, type=int,
                              help="expected pending round; when supplied, a mismatch refuses")
    cli_contract.add_argument(pm, "--phase", contract="free-text", default=None,
                              help="expected pending phase; when supplied, a mismatch refuses")

    pa = sub.add_parser("advance")
    cli_contract.add_argument(pa, "--session-dir", contract="existing-directory", required=True)
    cli_contract.add_argument(pa, "--break-lock", contract="boolean-flag")

    prv = sub.add_parser("run-verify")
    cli_contract.add_argument(prv, "--session-dir", contract="existing-directory", required=True)
    cli_contract.add_argument(prv, "--timeout", contract="integer", default=3600, type=int,
                              help="seconds the verify command may run before it lands `timeout` "
                                   "(default 3600)")

    pt = sub.add_parser("attest")
    cli_contract.add_argument(pt, "--session-dir", contract="existing-directory", required=True)
    cli_contract.add_argument(pt, "--failure", contract="free-text", required=True,
                              help="a journal sequence number, or marker:<entryHash> for a "
                                   "journal-degraded fault marker. There is NO issue reference — "
                                   "eligibility is allowlist-only")
    cli_contract.add_argument(pt, "--note", contract="free-text", required=True)

    pc = sub.add_parser("checkpoint")
    cli_contract.add_argument(pc, "--session-dir", contract="existing-directory", required=True)
    pc.add_argument("--stop-reason", required=True, choices=list(CHECKPOINT_STOP_REASONS))

    pru = sub.add_parser("rule")
    cli_contract.add_argument(pru, "--session-dir", contract="existing-directory", required=True)
    cli_contract.add_argument(pru, "--ruling-file", contract="free-text", required=True,
                              dest="ruling_file")
    cli_contract.add_argument(pru, "--by", contract="free-text", required=True)

    pbc = sub.add_parser(BREAK_IT_CHANGE_CMD)
    cli_contract.add_argument(pbc, "--session-dir", contract="existing-directory", required=True)
    cli_contract.add_argument(pbc, "--finding", contract="free-text", required=True,
                              help="the staged id (v0, v1, ...) or the finding key of the finding "
                                   "whose break-it test changes")
    cli_contract.add_argument(pbc, "--content-file", contract="free-text", required=True,
                              dest="content_file",
                              help="path to the changed test file's complete content (UTF-8 text)")
    cli_contract.add_argument(pbc, "--why", contract="free-text", required=True,
                              help="the reason the test changed; it rides the new run's record")

    pea = sub.add_parser(EXTRA_AUDIT_CMD)
    cli_contract.add_argument(pea, "--session-dir", contract="existing-directory", required=True)
    cli_contract.add_argument(pea, "--order-file", contract="free-text", required=True,
                              dest="order_file",
                              help="path to a JSON object with one key, `why`: the advisor's reason")
    cli_contract.add_argument(pea, "--by", contract="free-text", required=True)
    cli_contract.add_argument(pea, "--pr", contract="integer", required=True, type=int)
    cli_contract.add_argument(pea, "--repo", contract="free-text", default=None,
                              help="OWNER/NAME; resolved from the session's checkout when omitted")

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return _dispatch(args)
    except JournalFaultUnrecordable as jf:
        # Last-resort fail-loud: the journal AND its fault marker were both unwritable — there is no
        # silent tier below this. The CLI invocation itself FAILS: the reason to stdout, the
        # underlying errors to stderr, nonzero exit. #507 WO-FIX-RECOVERY.
        sys.stdout.write(json.dumps({"ok": False, "reason": "journal-fault-unrecordable",
                                     "detail": str(jf)}) + "\n")
        sys.stderr.write("journal write error: %s\nfault-marker write error: %s\n"
                         % (jf.journal_error, jf.marker_error))
        return 1


def _repair_before_fresh_checks(session_dir):
    """None to carry on, or a refusal. Takes the session lock for a damaged `loop-state.json` with a mirror only,
    and runs the recovery and repair `cmd_next` would run."""
    if _state_damage(session_dir) is None or not os.path.exists(os.path.join(session_dir, MIRROR_FILE)):
        return None
    try:
        with round_records.session_lock(session_dir):
            return _commit_recover_or_refuse(session_dir, "next")
    except round_records.SessionLockHeld as held:
        return _lock_held_refusal(session_dir, "next", held)


def _dispatch(args):
    # An unfinished session from an earlier plugin version is refused before any other check here
    # reads its saved state.
    upgrade = _upgrade_gate_unlocked(args.session_dir, args.cmd)
    if upgrade is not None:
        sys.stdout.write(json.dumps(upgrade) + "\n")
        return 1
    if args.cmd == "next":
        # A missing state file with a valid mirror is repaired before the fresh-session checks below
        # read it as a new session.
        pre = _repair_before_fresh_checks(args.session_dir)
        if pre is not None:
            sys.stdout.write(json.dumps(pre) + "\n")
            return 1
        overrides = {}
        if args.leg:
            overrides["leg"] = args.leg
        if args.vendors is not None:
            vendors, reason = _parse_vendors(args.vendors)
            if reason is not None:
                sys.stdout.write(json.dumps({"ok": False, "reason": reason,
                                             "value": args.vendors}) + "\n")
                return 1
            # `--vendors` can only take effect on FRESH state — the config is read ONCE at
            # new_state; a later `next` on existing state would silently ignore it. Reject loudly
            # rather than accept a flag that cannot take effect (#507).
            st_ok, st = load_state(args.session_dir)
            if not (st_ok and st is None):
                sys.stdout.write(json.dumps({"ok": False, "reason": "vendors-not-fresh-state",
                                             "value": args.vendors}) + "\n")
                return 1
            overrides["vendors"] = vendors
        if args.seat_map is not None:
            # Same fresh-state-only discipline as `--vendors`: the seat map is read ONCE at
            # new_state, so accepting it on existing state would silently ignore it (#723).
            seat_map_obj, reason = _parse_seat_map(args.seat_map)
            if reason is not None:
                sys.stdout.write(json.dumps({"ok": False, "reason": reason,
                                             "value": args.seat_map}) + "\n")
                return 1
            st_ok, st = load_state(args.session_dir)
            if not (st_ok and st is None):
                sys.stdout.write(json.dumps({"ok": False, "reason": "seat-map-not-fresh-state",
                                             "value": args.seat_map}) + "\n")
                return 1
            overrides["seatMap"] = seat_map_obj
        if args.copy_proof is not None:
            # Same fresh-state-only discipline as `--seat-map`: the proof is checked ONCE at new_state,
            # so accepting it on existing state would silently ignore it.
            proof, fault = countable_lines.load_proof(args.copy_proof)
            if fault is not None:
                sys.stdout.write(json.dumps({"ok": False, "reason": "copy-proof-invalid",
                                             "detail": fault, "value": args.copy_proof}) + "\n")
                return 1
            st_ok, st = load_state(args.session_dir)
            if not (st_ok and st is None):
                sys.stdout.write(json.dumps({"ok": False, "reason": "copy-proof-not-fresh-state",
                                             "value": args.copy_proof}) + "\n")
                return 1
            overrides["copyProof"] = proof
        if args.break_it_interpreter is not None:
            # Same fresh-state-only discipline as `--seat-map`: the calibration is read ONCE at
            # new_state, so accepting it on existing state would silently ignore it (#1961).
            st_ok, st = load_state(args.session_dir)
            if not (st_ok and st is None):
                sys.stdout.write(json.dumps({"ok": False,
                                             "reason": "break-it-interpreter-not-fresh-state",
                                             "value": args.break_it_interpreter}) + "\n")
                return 1
            overrides[break_it.INTERPRETER_KEY] = args.break_it_interpreter
        if args.verify_command is not None:
            overrides["verifyCommand"] = args.verify_command
        if args.max_rounds is not None:
            overrides["maxRounds"] = args.max_rounds
            st_ok, st = load_state(args.session_dir)
            if st_ok and st is None:
                # axis: a fresh CLI session refuses a cap above ROUND_CAP before any state is written — see bite-proof record c1l4_wo_b
                if args.max_rounds > round_phases.ROUND_CAP:
                    sys.stdout.write(json.dumps({"ok": False, "reason": "max-rounds-invalid",
                                                 "value": args.max_rounds}) + "\n")
                    return 1
                try:
                    _default_config(dict(overrides))
                except MaxRoundsRefusal as refusal:
                    sys.stdout.write(json.dumps({"ok": False, "reason": refusal.reason,
                                                 "value": refusal.value}) + "\n")
                    return 1
        if args.fix_batch_cap is not None:
            st_ok, st = load_state(args.session_dir)
            if not (st_ok and st is None):
                sys.stdout.write(json.dumps({"ok": False,
                                             "reason": "fix-batch-cap-not-fresh-state",
                                             "value": args.fix_batch_cap}) + "\n")
                return 1
            overrides["fixBatchCap"] = args.fix_batch_cap
            try:
                _default_config(dict(overrides))
            except FixBatchCapRefusal as refusal:
                sys.stdout.write(json.dumps({"ok": False, "reason": refusal.reason,
                                             "value": refusal.value}) + "\n")
                return 1
        st_ok, st = load_state(args.session_dir)
        if st_ok:
            fresh = st is None
            prior_pin = (st.get("config") or {}).get("baseRef") if isinstance(st, dict) else None
            repo_root = args.repo_root or os.getcwd()
            guard = review_base_guard.check_base(args.session_dir, repo_root, prior_pin=prior_pin)
            if not guard["ok"]:
                return _refuse_base_guard(args.session_dir, guard["reason"], guard.get("detail"))
            if fresh:
                res = review_base_guard.check_round_diff(args.diff_path)
                if not res["ok"]:
                    return _refuse_base_guard(args.session_dir, res["reason"], res.get("detail"),
                                              value=args.diff_path if args.diff_path else None)
                overrides["diff"] = res["text"]
                bind = review_base_guard.check_diff_binding(
                    res["text"], guard["baseRef"], repo_root)
                if not bind["ok"]:
                    return _refuse_base_guard(
                        args.session_dir, bind["reason"], bind.get("detail"))
                for key in ("baseRef", "baseBranch", "baseFetch", "baseDegraded", "mode", "baseRepo",
                            "baseRepoCheck", "repoRoot"):
                    if guard.get(key) is not None:
                        overrides[key] = guard[key]
                overrides["baseGuard"] = BASE_GUARD_CHECKED
                overrides["diffBinding"] = bind["binding"]
            elif args.diff_path:
                return _refuse_base_guard(args.session_dir, "diff-path-not-fresh-state",
                                          value=args.diff_path)
        # A state file that cannot be loaded must surface its own refusal from cmd_next — do not
        # mask it with a base refusal.
        if args.prior_comments:
            # Same fresh-state-only discipline as `--vendors`: priorComments is read ONCE at
            # new_state, and materializing to the canonical file on existing state would disagree
            # with persisted config (#1107 WO-c6C).
            st_ok, st = load_state(args.session_dir)
            if not (st_ok and st is None):
                sys.stdout.write(json.dumps({"ok": False, "reason": "prior-comments-not-fresh-state",
                                             "value": args.prior_comments}) + "\n")
                return 1
            # Load + validate the PR-mode prior comments into `priorComments` so the
            # author-justification post-filter is actually reachable (#507 v7). A missing / unreadable
            # / non-list file leaves priorComments unset (the filter simply does not fire) — never a
            # crash and never a silent drop.
            # One source of truth (#1107 WO-c6A): validated comments are materialized to
            # $SESSION_DIR/prior-comments.json before priorComments is set, so the filter and
            # _resolve_prior_comments_path cannot disagree. Explicit --prior-comments wins over
            # any pre-existing canonical file.
            try:
                with open(args.prior_comments, encoding="utf-8") as fh:
                    loaded = json.load(fh)
                if isinstance(loaded, list):
                    if _materialize_prior_comments(args.session_dir, args.prior_comments, loaded):
                        overrides["priorComments"] = loaded
            except (OSError, ValueError):
                pass
        st_ok, st = load_state(args.session_dir)
        if args.earlier_findings and not (st_ok and st is None):
            sys.stdout.write(json.dumps({"ok": False, "reason": "earlier-findings-not-fresh-state",
                                         "value": args.earlier_findings}) + "\n")
            return 1
        if st_ok and st is None:
            overrides.update(_earlier_findings_overrides(args.session_dir, args.earlier_findings))
        if args.records_path is not None:
            if _records_path_is_reserved(args.session_dir, args.records_path):
                sys.stdout.write(json.dumps({"ok": False, "reason": "records-path-reserved",
                                             "value": args.records_path}) + "\n")
                return 1
            # Same fresh-state-only discipline as `--seat-map`: recordsPath is taken once, when the
            # session is minted; a later `next` on existing state would silently ignore it (#1196).
            st_ok, st = load_state(args.session_dir)
            if not (st_ok and st is None):
                sys.stdout.write(json.dumps({"ok": False, "reason": "records-path-not-fresh-state",
                                             "value": args.records_path}) + "\n")
                return 1
            overrides["recordsPath"] = os.path.abspath(args.records_path)
        out = cmd_next(args.session_dir, overrides or None)
    elif args.cmd == "record-result":
        out = cmd_record_result(args.session_dir, args.seat, attempt=args.attempt,
                                supersede=args.supersede, expect_sha256=args.expect_sha256,
                                sweep=args.sweep, occurrence=args.occurrence,
                                expect_round=args.round, expect_phase=args.phase,
                                evidence_run_dir=args.evidence_run_dir)
    elif args.cmd == "record-missing":
        out = cmd_record_missing(args.session_dir, args.seat, args.attempt, args.reason,
                                 evidence_path=args.evidence, occurrence=args.occurrence,
                                 expect_round=args.round, expect_phase=args.phase)
    elif args.cmd == "advance":
        out = cmd_advance(args.session_dir, break_lock=args.break_lock)
    elif args.cmd == "run-verify":
        out = cmd_run_verify(args.session_dir, timeout=args.timeout)
    elif args.cmd == "attest":
        out = cmd_attest(args.session_dir, args.failure, args.note)
    elif args.cmd == "checkpoint":
        out = cmd_checkpoint(args.session_dir, args.stop_reason)
    elif args.cmd == "rule":
        out = cmd_rule(args.session_dir, args.ruling_file, args.by)
        sys.stdout.write(json.dumps(out) + "\n")
        return 1 if not out.get("ok") else 0
    elif args.cmd == BREAK_IT_CHANGE_CMD:
        out = cmd_break_it_change(args.session_dir, args.finding, args.content_file, args.why)
        sys.stdout.write(json.dumps(out) + "\n")
        return 1 if not out.get("ok") else 0
    elif args.cmd == EXTRA_AUDIT_CMD:
        out = cmd_extra_audit(args.session_dir, args.order_file, args.by, args.pr, repo=args.repo)
        sys.stdout.write(json.dumps(out) + "\n")
        return 1 if not out.get("ok") else 0
    else:
        try:
            with open(args.artifact, encoding="utf-8") as fh:
                artifact = json.load(fh)
        except (OSError, ValueError) as exc:
            out = {"ok": False, "reason": "unreadable artifact: %s" % exc}
            sys.stdout.write(json.dumps(out) + "\n")
            return 0
        out = cmd_submit(args.session_dir, args.phase, args.attempt, args.state_hash, artifact)
    sys.stdout.write(json.dumps(out) + "\n")
    # A terminal receipt integrity fault fails LOUD: nonzero exit, the same fail-loud family as
    # journal-fault-unrecordable (a masked-by-replay receipt fault must never look like a clean exit).
    return 1 if out.get("reason") in ("receipt-fault", SESSION_FROM_EARLIER_VERSION) else 0


if __name__ == "__main__":
    sys.exit(main())
