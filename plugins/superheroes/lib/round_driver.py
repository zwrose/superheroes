#!/usr/bin/env python3
"""The one-entrypoint review-loop round driver (#507).

CONTRACT. This module collapses the review-code auto-fix loop's per-round script choreography
(plan → dispatch → compile → verify → synthesis → gate → persist → fix → re-review) into ONE
deterministic entrypoint so the mandated path is the easiest path — ~6/24 corpus runs routed
AROUND the old scripts because the choreography was several separate invocations. It has two
layers over one core:

  - Layer 1 (`run_loop`): the ported control-flow of `review_panel_shell.js::reviewPanel` with
    every effectful step behind an injectable seam (`reviewer`, `synthesis`, `verifier`,
    `auditor`, `fix_step`, `verify_runner`, `changed_subjects`, `io`). Same run-SHAPE, not the JS
    idioms. `changed_subjects` derives the fix's changed policy subjects from git (the reviewed vs
    head diff), NEVER the fixer's self-report (#157/#158) — the library default + the CLI path wire
    the real derivation; the eval harness injects a scripted replay.
  - Layer 2 (`next`/`submit` CLI): the state machine BETWEEN orchestrator dispatches — `next`
    emits the one action to run, `submit` folds its artifact and advances.

A tradeoff/product-choice blocker is an OWNER-JUDGMENT call: it routes to the `present-judgment`
INTERVENTION gate (fix-as-suggested / fix-with-guidance / skip-with-reason), whose fixes fold back
into the round's fix leg — it is NOT a terminal (#507 R2a; the `present-stall-menu` terminal is
reachable only from the audit-stall path). `load_state` migrates a state persisted under the OLD
routing (a judgment blocker dead-ended at `present-stall-menu`) onto the judgment gate in place;
`schemaVersion` stays 2 (session dirs are per-invocation — this only rescues a run parked mid-cut).

Like its decider siblings (audits / delta_surface / verification): DETERMINISTIC, stdlib-only,
FAIL-CLOSED. Junk in → conservative out + disclosure; never certify on silence; a wrong
`discharged`, a receipt-missing seat, a lost independence, an unknown surface all fail toward
MORE review, a park, or a disclosed downgrade — never toward a silent clean. The judgments live
in the pure deciders this module imports (`audits`, `verification`, `circuit_breaker`,
`review_round_policy`, `delta_surface`, `model_registry`); the driver only SEQUENCES them and
RECORDS what happened, and every terminal writes the driver receipt (`validate_receipt` guards
its shape). The confirmation economics (`review_round_policy.confirmation_followup` /
`is_cross_cutting`, MAX_CONFIRMATIONS=2), the reviewer re-dispatch budget
(`loop_plan_common.REDISPATCH_BUDGET` — the single home), and receipt validation
(`panel_tally._valid_final_receipt`, consumed bit-compatibly, never modified) are all reused,
not re-implemented.
"""
import argparse
import errno
import hashlib
import json
import os
import re
import shlex
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cli_contract  # noqa: E402
import audits  # noqa: E402
import calibration_resolve  # noqa: E402
import core_md  # noqa: E402
import circuit_breaker  # noqa: E402
import mode_registry  # noqa: E402
import delta_surface  # noqa: E402
import dispatch_outcome  # noqa: E402
import engine_adapter  # noqa: E402
import engine_pref  # noqa: E402
import model_tier_overrides  # noqa: E402
import loop_plan_common  # noqa: E402
import model_registry  # noqa: E402
import panel_tally  # noqa: E402
import resolve_diff_lines  # noqa: E402
import review_base_guard  # noqa: E402
import review_loop_plan  # noqa: E402
import review_memory  # noqa: E402
import review_gate_policy  # noqa: E402
import review_round_policy  # noqa: E402
import round_commit  # noqa: E402
import round_orders  # noqa: E402
import round_records  # noqa: E402
import round_phases  # noqa: E402
import seat_map  # noqa: E402
import store_core  # noqa: E402
import verification  # noqa: E402
from finding_identity import finding_identity, normalize_title  # noqa: E402

_seat_map_unexcused_violations = seat_map.unexcused_violations
_seat_map_classify_violations = seat_map.classify_violations

# --- constants (the DIMENSIONS/AGENT_SUFFIX home, moved off the retired code_loop_plan) --------
# The code leg is the FIVE shared reviewers. `grounding-reviewer` is spec-leg-only (doc
# provenance) — deliberately absent here; test_dispatch_tables pins the per-leg subset.
DIMENSIONS = round_phases.DIMENSIONS
AGENT_SUFFIX = {"architecture-reviewer": "architecture", "code-reviewer": "code",
                "security-reviewer": "security", "test-reviewer": "test",
                "premortem-reviewer": "premortem"}
# The cross-cutting lenses always get the WHOLE diff even when a big diff is sharded per-lens —
# architecture and failure-mode reasoning is non-local, so a shard would blind them.
CROSS_CUTTING_LENSES = ("architecture-reviewer", "premortem-reviewer")

DEEP = "reviewer-deep"
CHEAP = "reviewer"
# The reviewer re-dispatch budget rides through its single home (#350/#525): a receipt-missing /
# stale seat is re-dispatched at most this many times before it is recorded terminal `missing`
# with its findings carried as unverified. The code leg's read goes through the constant now.
REDISPATCH_BUDGET = loop_plan_common.REDISPATCH_BUDGET
MAX_CONFIRMATIONS = review_round_policy.MAX_CONFIRMATIONS
# Claude-ladder rung for self-recovery escalation — not owner-configurable.
# escalate() returns None (no escalation recorded) when the fixer vendor's ladder
# does not contain this pair (codex/cursor ladders omit it).
_SELF_RECOVERY_FIXER_MODEL = "sonnet-5"
_SELF_RECOVERY_FIXER_EFFORT = "high"

SCHEMA_VERSION = 2
STATE_FILE = "loop-state.json"
JOURNAL_FILE = "driver-journal.jsonl"
JOURNAL_FAULT_FILE = "driver-journal-fault.jsonl"
RECEIPT_FILE = "round-receipt.json"

# --- the #723 schema matrix -------------------------------------------------------------------
# `SCHEMA_VERSION` stays the version a v2 RECEIPT keys off (and the version an in-flight v2 state
# carries). NEW state is minted at `STATE_SCHEMA_VERSION`; `load_state` accepts BOTH.
#
# THE HASH-PRESERVATION RULE. A loaded state's `schemaVersion` is NEVER mutated and NO v3 default
# field is written into the dict on load: `state_hash` hashes the WHOLE canonical state, so
# injecting a v3 key on load would change the hash of an already-emitted `expectedStateHash` and
# every in-flight v2 session's next `submit` would fail its echo fence. Every v3-only field is
# therefore read with `.get()` at its read site, never seeded on load.
STATE_SCHEMA_VERSION = 3
SUPPORTED_STATE_VERSIONS = (2, 3)

# The receipt VERSION derives from the STATE's version: a v2 state terminates to
# `receipt-certified/2` (today's shape, byte-for-byte unchanged — no key added), a v3 state to
# `receipt-certified/3`. `attest` writes `receipt-attested/1`, which carries an `attestation` block
# and NO `certification`/`certificationShape` — so the certified and attested shapes are
# structurally un-confusable and `validate_receipt` dispatches on that.
RECEIPT_CERTIFIED_SCHEMA = "receipt-certified/%d"
RECEIPT_ATTESTED_SCHEMA = "receipt-attested/1"
ATTESTED_VERDICT = "uncertified-manual"
# The verdicts a CERTIFIED receipt may carry — every `state["terminal"]` the folds can set. An
# unlisted verdict is a receipt nobody in this module produced.
CERTIFIED_VERDICTS = ("converged", "halted", "held", "stalled", "cannot-certify",
                      "capped-with-open-critical", "capped-with-open-blocker")

# A v2 session keeps `next`/`submit` and is refused by every #723 subcommand under this reason.
LEGACY_SESSION_REFUSAL = "legacy-session-use-next-submit"

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
P_VERIFY = round_phases.P_VERIFY
P_FIXER = round_phases.P_FIXER
P_JUDGMENT = round_phases.P_JUDGMENT
P_STALL = round_phases.P_STALL
P_TERMINAL = round_phases.P_TERMINAL

STALL_CHOICES = round_phases.STALL_CHOICES
ONE_MORE_ROUND_CHOICE = round_phases.ONE_MORE_ROUND_CHOICE
ACCEPT_RISK_CHOICE = round_phases.ACCEPT_RISK_CHOICE
HOLD_CHOICE = round_phases.HOLD_CHOICE
RETIRED_STALL_CHOICES = round_phases.RETIRED_STALL_CHOICES
RETIRED_STALL_CHOICE_PREFIX = round_phases.RETIRED_STALL_CHOICE_PREFIX
STALL_CHOICE_NOT_OFFERED_PREFIX = "stall-choice-not-offered:"
STALL_ACCEPT_RISK_NOT_ELIGIBLE = "stall-accept-risk-not-eligible"
JUDGMENT_DISPOSITIONS = round_phases.JUDGMENT_DISPOSITIONS

BASE_GUARD_CHECKED = "checked-stat-bound"

# Citable reason recorded when gate policy pre-authorizes a judgment `skip` disposition.
_GATE_POLICY_SKIP_REASON = "pre-authorized by gate policy (calibration)"

# Named refusal when a submit artifact lists the same judgment id with conflicting dispositions.
JUDGMENT_DISPOSITION_COLLISION_CAUSE = "judgment-disposition-collision"


# --- the per-round disclosure channels (#720) -------------------------------------------------
# Shape predicates for a channel value coming off a DURABLE record. A record is external input: a
# channel whose value has the wrong shape is DROPPED on resume rather than restored, because a
# truthy-but-wrong value would either crash the receipt's prose or emit a false disclosure.

def _str_list(value):
    return isinstance(value, list) and all(isinstance(x, str) for x in value)


def _dict_list(value):
    return isinstance(value, list) and all(isinstance(x, dict) for x in value)


def _canary_failed_shape(value):
    # build_receipt joins cf["seats"] into prose, so the seat names must be strings.
    return isinstance(value, dict) and _str_list(value.get("seats") or [])


def _canary_verified_shape(value):
    # build_receipt sorts the vendor keys, so mixed key types would raise.
    return isinstance(value, dict) and all(isinstance(k, str) for k in value)


def _adapter_provenance_shape(value):
    if not isinstance(value, dict):
        return False
    if "byPhase" in value:
        return isinstance(value.get("byPhase"), dict)
    return True


def _order_vendor_provenance_gaps_shape(value):
    # build_receipt joins gap seat names into prose, so each row's seat must be a non-empty string.
    if not isinstance(value, list):
        return False
    for row in value:
        if not isinstance(row, dict):
            return False
        seat = row.get("seat")
        if not isinstance(seat, str) or not seat:
            return False
        if "occurrence" in row:
            occ = row.get("occurrence")
            if not isinstance(occ, int) or occ < 0:
                return False
    return True


def _normalize_adapter_provenance(prov):
    """Return {phase: disclosures} for either the per-phase `byPhase` shape or the legacy flat
    value (keyed as `unknown-phase`). Non-dict / corrupt `byPhase` → empty."""
    if not isinstance(prov, dict):
        return {}
    if "byPhase" in prov:
        by_phase = prov.get("byPhase")
        if not isinstance(by_phase, dict):
            return {}
        return dict(by_phase)
    if prov:
        return {"unknown-phase": dict(prov)}
    return {}


# The ONE home for the per-round disclosure channels. `build_receipt` emits exactly these onto each
# round entry, and a `recordsPath` resume restores exactly these out of a durable record's
# `disclosures` block (#720 — before that, `_seed_resume` restored findings/coverage but no
# disclosure state, so a resumed run's terminal receipt silently UNDER-DISCLOSED every pre-resume
# round). Each value is the shape the restore requires. The census test
# (`test_panel_round_channels_are_all_accounted_for`) closes the set by construction against
# `_fold_panel`'s recorded keys, so a new channel cannot ship without a resume path.
RESUMABLE_DISCLOSURE_CHANNELS = {
    "fellOpen": _dict_list,
    "fellOpenProvenanceMissing": _str_list,
    "seatMapUnavailable": _str_list,
    "seatMapViolations": _dict_list,
    "vacuousSeats": _str_list,
    "engagedArtifactSeats": _str_list,
    "canaryUnverified": _str_list,
    "canaryFailed": _canary_failed_shape,
    "canaryVerified": _canary_verified_shape,
    "adapterProvenance": _adapter_provenance_shape,
    "recordOrphansIgnored": _str_list,
    "orderVendorProvenanceGaps": _order_vendor_provenance_gaps_shape,
}

# Per-round disclosure channels recorded during hand `submit` (not `_fold_panel`). Each name here
# must also appear in `RESUMABLE_DISCLOSURE_CHANNELS` so resume and `build_receipt` share the same
# one home.
SUBMIT_DISCLOSURE_CHANNELS = ("recordOrphansIgnored",)

# Per-round disclosure channels recorded during order emission (`orders-emit`, not `_fold_panel`).
# Each name here must also appear in `RESUMABLE_DISCLOSURE_CHANNELS` so resume and `build_receipt`
# share the same one home.
ORDER_EMISSION_DISCLOSURE_CHANNELS = ("orderVendorProvenanceGaps",)

# Per-round disclosure channels `_record_adapter_provenance` records in `_fold` (shared across phases,
# not `_fold_panel`). Each name here must also appear in `RESUMABLE_DISCLOSURE_CHANNELS` so resume
# and `build_receipt` share the same one home.
FOLD_PROVENANCE_DISCLOSURE_CHANNELS = ("adapterProvenance",)

# Every OTHER per-round key `_fold_panel` records, named here so the census can close the set: a new
# `_record_round` key lands in one home or the other, deliberately, or the census fails. None of
# these is restorable on resume — `compileDrops` and `unverified` carry finding-shaped EVIDENCE rows
# that round-records.json deliberately never stores (review_memory's persist-skeleton contract), and
# `seatStatus` / `missingSeats` are the panel's own coverage bookkeeping, owned by the round that
# actually ran its seats (`seatStatus` is emitted unconditionally, not as a disclosure).
UNRESTORED_PANEL_ROUND_KEYS = ("seatStatus", "lensCoverage", "compileDrops", "unverified", "missingSeats")

# `canaryVerified` is the one channel whose EMPTY value still belongs in the receipt (a control probe
# that ran and carried an empty evidence object is still a probe that ran), so it emits on PRESENCE.
# Every other channel emits on truthiness — an empty channel is not a disclosure.
_DISCLOSE_ON_PRESENCE = ("canaryVerified",)


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


class RoundCeilingRefusal(ValueError):
    """The one load-time refusal for an invalid ``maxRoundsAbsolute`` vs ``maxRounds`` pairing.

    Raised only from ``_default_config`` — the single config load point — when
    ``circuit_breaker.resolve_round_ceiling`` refuses the named ceiling."""
    def __init__(self, reason, value=None):
        super().__init__(reason)
        self.reason = reason
        self.value = value


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


def read_journal(session_dir):
    out = []
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
                    continue
    except OSError:
        pass
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
        marker_path = os.path.join(super_dir, _REVIEW_SESSION_MARKER)
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


def _receipt_version(state):
    """The receipt schemaVersion for a state: the STATE's version drives it, so a v2 session still
    terminates to today's `receipt-certified/2` and only a v3 session emits `receipt-certified/3`."""
    return _state_version(state) or SCHEMA_VERSION


def receipt_kind(receipt):
    """The receipt's shape name — `receipt-certified/<v>`, `receipt-attested/1`, or None."""
    if not isinstance(receipt, dict):
        return None
    if receipt.get("schema") == RECEIPT_ATTESTED_SCHEMA:
        return RECEIPT_ATTESTED_SCHEMA
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
    round diff — the same hunk-walking `resolve_diff_lines.parse_diff_lines` uses. `valid` is None
    when no diff was supplied (scope check skipped)."""
    if valid is None:
        return True
    file_lines = valid.get(finding.get("file"))
    if not file_lines:
        return False
    return finding.get("line") in file_lines


def _nit_cap(findings):
    """After dedupe, keep at most 5 Nits; the overflow collapses to ONE summary entry so the
    readout isn't buried (the base rubric's severity cap)."""
    kept = []
    nits = []
    for f in findings:
        if isinstance(f, dict) and f.get("severity") == "Nit":
            nits.append(f)
        else:
            kept.append(f)
    if len(nits) <= _NIT_CAP:
        kept.extend(nits)
        return kept
    kept.extend(nits[:_NIT_CAP])
    overflow = len(nits) - _NIT_CAP
    kept.append({
        "title": "+ %d more Nits — see findings-*.json for details" % overflow,
        "severity": "Nit", "file": None, "line": None, "summaryEntry": True,
    })
    return kept


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
        key = (f.get("file"), f.get("line"), normalize_title(str(f.get("title") or "")))
        if key in by_anchor:
            ex = by_anchor[key]
            dims = panel_tally._merge_dims(ex, f)
            if panel_tally.SEV_RANK.get(f.get("severity"), 99) \
                    < panel_tally.SEV_RANK.get(ex.get("severity"), 99):
                merged = dict(f)
            else:
                merged = dict(ex)
            merged["dimension"] = dims
            merged["tradeoff"] = bool(ex.get("tradeoff") or f.get("tradeoff"))
            by_anchor[key] = merged
        else:
            by_anchor[key] = dict(f)
            order.append(key)
    out = [by_anchor[k] for k in order]
    for f in out:  # FR-4: deterministic mechanical/judgment classification (no action taken)
        f["classification"] = "judgment" if f.get("tradeoff") else "mechanical"
    return out


def mechanical_compile(findings, diff_text=None):
    """Port of SKILL §4 steps 1-4 + 6, deterministic and fail-closed:
      1. citation check — drop file/line-less findings;
      2. diff-scope check — drop findings whose (file,line) is not an anchor of the round diff;
      4. dedupe by the per-LOCATION anchor (file, line, normalized-title) — higher severity wins,
         dimensions unioned, tradeoff OR-ed. NOT the line-less file::title identity, which collapses
         two distinct-line findings that share a title (a dropped blocker);
      6. nit cap.
    Returns (compiled, drops) where each drop names WHY (never silently dropped)."""
    if not isinstance(findings, list):
        findings = []
    valid = resolve_diff_lines.parse_diff_lines(diff_text) if diff_text is not None else None
    kept, drops = [], []
    for f in findings:
        if not isinstance(f, dict):
            continue
        if f.get("file") is None or f.get("line") is None:
            drops.append({"file": f.get("file"), "title": f.get("title"),
                          "reason": "uncited — no file:line"})
            continue
        if not _diff_scope_ok(f, valid):
            drops.append({"file": f.get("file"), "line": f.get("line"),
                          "title": f.get("title"), "reason": "outside the round diff scope"})
            continue
        fc = dict(f)
        if "dimension" in fc:
            norm = panel_tally.normalize_dimension(fc["dimension"])
            if norm:
                fc["dimension"] = norm
            else:
                fc.pop("dimension", None)
        kept.append(fc)
    compiled = _compile_by_anchor(kept)
    compiled = _nit_cap(compiled)
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

def _live_vendors(config):
    vendors = config.get("vendors") if isinstance(config, dict) else None
    if not isinstance(vendors, list) or not vendors:
        return ["claude"]
    return [v for v in vendors if isinstance(v, str) and v]


def _auditor_vendor(config, fixer_vendor):
    """The auditor of a fix is never the fixer's model FAMILY (CONVENTIONS §7.5 — independence keys
    on family, not the dispatch CLI). Independence is NEVER satisfied between two cursor first-party
    models (#651, owner-ratified 2026-07-26): composer and grok share the `xai` family, so a
    cursor-grok auditor is NOT independent of a cursor-composer fix. When no family-independent
    vendor is live the audit still RUNS but is stamped degraded — never silently counted as
    independent. The same-vendor fallback loop was removed as unreachable post-#651 (issue #652
    rider 4a); see test_verifier_and_code_fixer_families_match_per_vendor in test_model_registry."""
    live = _live_vendors(config)
    fixer_fam = model_registry.family_for("code-fixer", fixer_vendor)
    if fixer_fam is None:
        return (live[0] if live else fixer_vendor), "degraded"
    for v in live:
        if v != fixer_vendor:
            cand_fam = model_registry.family_for("verifier", v)
            if cand_fam is not None and cand_fam != fixer_fam:
                return v, "independent"
    return (live[0] if live else fixer_vendor), "degraded"


def _degraded(state):
    return bool(state.get("independenceDegraded"))


def _base_degraded(state):
    return bool((state.get("config") or {}).get("baseDegraded"))


def _same_family_seats(state):
    """Seats the #510 seat map had to fill with the MAKER's own model family because no alternative
    family was live (#670, owner-ratified 2026-07-26). A disclosed degradation, never a violation —
    but a panel that reviewed itself must never certify as plainly clean, so it joins independence
    and base provenance in the certification shape. Read off the seat map's own receipt; never
    recomputed here."""
    sm = state.get("seatMap")
    degradations = sm.get("degradations") if isinstance(sm, dict) else None
    if not isinstance(degradations, list):
        return []
    seats = []
    for deg in degradations:
        if isinstance(deg, dict) and deg.get("constraint") == "same-family":
            seat = deg.get("seat")
            seats.append(seat if isinstance(seat, str) and seat else "unnamed-seat")
    return sorted(set(seats))


def _same_family_degraded(state):
    return bool(_same_family_seats(state))


def _seat_map_violations(state):
    """Unexcused seat-map constraint violations — a BREACH channel, distinct from the disclosed
    degradations (#680). The UNION of what each round recorded and what the live merged seat map
    carries, so neither channel alone is load-bearing: `state["rounds"]` is lost across a
    `recordsPath` resume, and `state["seatMap"].update()` lets a later round's map overwrite an
    earlier one. Deduped by (constraint, seat), sorted."""
    seen: set[tuple] = set()
    merged: list[dict] = []
    for rec in (state.get("rounds") or {}).values():
        if not isinstance(rec, dict):
            continue
        for v in rec.get("seatMapViolations") or []:
            if not isinstance(v, dict):
                continue
            key = (str(v.get("constraint", "")), str(v.get("seat") or ""))
            if key in seen:
                continue
            seen.add(key)
            merged.append(v)
    for v in _seat_map_unexcused_violations(state.get("seatMap") or {}):
        key = (str(v.get("constraint", "")), str(v.get("seat") or ""))
        if key in seen:
            continue
        seen.add(key)
        merged.append(v)
    merged.sort(
        key=lambda item: (str(item.get("constraint", "")), str(item.get("seat") or "")),
    )
    return merged


def _seat_map_violated(state):
    return bool(_seat_map_violations(state))


def _seat_map_violation_breach_prose(v: dict) -> str:
    """One-line breach prose for build_receipt — constraint, seat, and evidence class (#680 R3)."""
    c = v.get("constraint") or "unknown"
    s = v.get("seat")
    ev = v.get("evidence")
    if ev == "unproven-liveness":
        ev_phrase = "excusal unprovable — liveness evidence unusable"
    elif ev == "alternative-live":
        ev_phrase = "an alternative was available"
    else:
        ev_phrase = None
    if isinstance(s, str) and s and ev_phrase:
        return "%s (seat %s; %s)" % (c, s, ev_phrase)
    if ev_phrase:
        return "%s (%s)" % (c, ev_phrase)
    if isinstance(s, str) and s:
        return "%s (seat %s)" % (c, s)
    return c


def _seat_pin_excused(state):
    sm = state.get("seatMap")
    if not isinstance(sm, dict):
        return False
    return bool(_seat_map_classify_violations(sm).get("excusedByPin"))


def _seat_pin_excused_seats(state):
    sm = state.get("seatMap")
    if not isinstance(sm, dict):
        return []
    seats: set[str] = set()
    for rec in _seat_map_classify_violations(sm).get("excusedByPin") or []:
        if not isinstance(rec, dict):
            continue
        for s in rec.get("excusedSeats") or []:
            if isinstance(s, str) and s:
                seats.add(s)
    return sorted(seats)


def _seat_map_unproven_liveness(state):
    for v in _seat_map_violations(state):
        if isinstance(v, dict) and v.get("evidence") == "unproven-liveness":
            return True
    return False


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
    ):
        return base + "-degraded"
    return base


# =============================================================================================
# state lifecycle
# =============================================================================================

def _default_config(overrides=None):
    cfg = {
        "leg": "code",
        "panel": False,
        "code": True,
        "vendors": ["claude"],
        "fixerVendor": None,  # UNKNOWN by default — auditor independence must DEGRADE, not assume claude (#608)
        "verifyCommand": "none",
        "maxRounds": 7,
        # Hard round ceiling (default circuit_breaker.DEFAULT_MAX_ROUNDS_ABSOLUTE) — owner-tunable
        # like maxRounds. A named ceiling below maxRounds refuses at load; unnamed uses the flat default.
        "maxRoundsAbsolute": None,
        "dimensions": list(DIMENSIONS),
        # Optional resume/records seam (#507 WO-D). When `recordsPath` is set the driver reads it
        # ONCE at new_state to resume at round N+1 from the durable seeds (review_loop_plan's
        # entry-bootstrap / _resume_round twins); a corrupt/mangled record state fails closed to a
        # cannot-certify park. `coveragePath` seeds the accumulated coverage decisions the
        # challenged-coverage breaker reads. Absent → a fresh round-1 run (the library-test shape).
        "recordsPath": None,
        "coveragePath": None,
        # PR-mode prior review comments (a list) for the author-justification post-filter. Wired from
        # the CLI's `--prior-comments` (#507 v7); None → the filter never fires.
        "priorComments": None,
        # #723 `next --seat-map`: the #510 seat map for round 1. Before this, `state["seatMap"]` was
        # populated ONLY by `_fold_panel` off the panel artifact, so the record layer's adapter had
        # no vendor/model source on round 1 (the round that dispatches the panel). Fresh-state-only,
        # same refusal discipline as `--vendors`.
        "seatMap": None,
    }
    if isinstance(overrides, dict):
        cfg.update({k: v for k, v in overrides.items() if v is not None})
    cfg["panel"] = cfg.get("leg") == "panel"
    cfg["code"] = cfg.get("leg") != "panel"
    if not isinstance(cfg.get("dimensions"), list) or not cfg["dimensions"]:
        cfg["dimensions"] = list(DIMENSIONS)
    ceiling, refusal = circuit_breaker.resolve_round_ceiling(
        cfg["maxRounds"], cfg.get("maxRoundsAbsolute"))
    if refusal is not None:
        raise RoundCeilingRefusal(refusal, cfg.get("maxRoundsAbsolute"))
    cfg["maxRoundsAbsolute"] = ceiling
    return cfg


def _round_ceiling(config):
    """Return the resolved unconditional round ceiling for this session.

    Persisted state from before #1030 may lack ``maxRoundsAbsolute`` on ``config``; in that case
    re-resolve from ``maxRounds`` with an unnamed ceiling so the flat default still applies — a
    resumed session never runs ceiling-less."""
    ceiling = config.get("maxRoundsAbsolute")
    if isinstance(ceiling, int) and not isinstance(ceiling, bool):
        return ceiling
    ceiling, _ = circuit_breaker.resolve_round_ceiling(config.get("maxRounds", 7), None)
    return ceiling


def new_state(config=None):
    cfg = _default_config(config)
    seeded_seat_map = cfg.get("seatMap")
    state = {
        "schemaVersion": STATE_SCHEMA_VERSION,
        "config": cfg,
        "round": 1,
        "step": P_PANEL,
        "pending": None,
        "lastAccepted": None,
        "rounds": {},
        "findings": [],
        "decisions": [],
        "auditRounds": [],
        "confirmations": 0,
        "selfRecovered": False,
        "independenceDegraded": len(_live_vendors(cfg)) < 2,
        # Seeded from `--seat-map` when one was supplied (#723) — `_fold_panel`'s own
        # `state["seatMap"].update(...)` still wins for every round that submits a map.
        "seatMap": dict(seeded_seat_map) if isinstance(seeded_seat_map, dict) else {},
        "reviewedDiff": cfg.get("diff"),
        "headDiff": None,
        "fixBatch": [],
        "fullPanelRan": False,
        # A configured lens that never ran is an OUTSTANDING coverage gap: set when a panel is
        # incomplete, cleared only when a COMPLETE panel re-establishes coverage. A converge resting
        # on it is withheld (silence never certifies — #507 R2 residual-1).
        "_incompletePanel": False,
        # The UNION of policy subjects the fix touched since the last full panel — the cross-cutting
        # re-arm reads THIS accumulation, not a single round's delta, so rework that spreads across
        # MULTIPLE post-confirmation fixes still trips the bar (#507 R2 residual-5). None = an unknown
        # surface since the panel (fail toward one more confirmation).
        "_changedSubjectsSincePanel": [],
        "terminal": None,
        "certification": None,
        # #507 WO-D: the in-memory review-record ledger (one record per REVIEW round) the
        # challenged-coverage / recurrence breaker reads, plus the accumulated coverage decisions.
        "_records": [],
        "_coverage": [],
        "_resumeCorrupt": None,
    }
    _seed_resume(state, cfg)
    return state


def _seed_resume(state, cfg):
    """Resume seam (#507 WO-D): when `recordsPath` names a durable round-records file, read it ONCE
    and resume at round N+1 the way review_panel_shell's entry-bootstrap did. A corrupt/mangled
    record state fails closed (flagged so run_loop parks cannot-certify). Reuses the review_loop_plan
    twins (`entry_bootstrap`/`_resume_round`) and `review_memory.load_records_state` — no re-impl."""
    records_path = cfg.get("recordsPath")
    if not records_path:
        return
    dims = _panel_dimensions(cfg)
    loaded = review_memory.load_records_state(records_path, dims)
    if not loaded.get("ok"):
        state["_resumeCorrupt"] = (
            "resume state %s (%s) — cannot certify; a fresh full reviewer-deep round is owed"
            % (loaded.get("state") or "unreadable", loaded.get("reason") or "unreadable"))
        return
    records = [r for r in (loaded.get("records") or []) if isinstance(r, dict)]
    # Seed the accumulated coverage decisions the challenged-coverage breaker reads: prefer the
    # explicit coveragePath, else fold the records' own coverage decisions.
    coverage = []
    cov_path = cfg.get("coveragePath")
    if cov_path and os.path.exists(cov_path):
        try:
            with open(cov_path, encoding="utf-8") as fh:
                loaded_cov = json.load(fh)
            if isinstance(loaded_cov, list):
                coverage = [d for d in loaded_cov if isinstance(d, dict)]
        except (OSError, ValueError):
            coverage = []
    if not coverage:
        for rec in records:
            for d in rec.get("coverageDecisions") or []:
                if isinstance(d, dict):
                    coverage.append(d)
    state["_records"] = records
    state["_coverage"] = coverage
    _restore_round_disclosures(state, records)
    if not records:
        return
    resume_round = review_loop_plan._resume_round(records)
    if resume_round <= 1:
        return
    # A qualifying full confirmation panel among the seeds counts toward the confirmation budget; a
    # degraded (not-all-fresh-deep-high-confidence) confirmation does NOT — _confirmation_qualifies
    # is the #167 bar, so a seeded degraded panel cannot anchor certification (a proper panel is owed).
    qualifying = sum(1 for r in records
                     if r.get("kind") == "confirmation" and review_loop_plan._confirmation_qualifies(r))
    state["confirmations"] = qualifying
    if resume_round > _round_ceiling(cfg):
        if _ceiling_halt(state, cfg, prospective_round=resume_round):
            return
    state["round"] = resume_round
    state["step"] = P_PANEL
    state["fullPanelRan"] = False
    eb = review_loop_plan.entry_bootstrap(records_path, dims)
    owed = review_loop_plan._further_confirmation_owed(records)
    if eb.get("ok") and eb.get("confirmationPending") and owed.get("owed"):
        # The loop stopped mid-confirmation and a further FULL confirmation panel is still owed (the
        # seeded panel was degraded / no qualifying panel has run) — resume by running that panel.
        _decision(state, "resume-confirmation",
                  "resumed with a pending confirmation and no qualifying panel — running a full "
                  "confirmation panel (a degraded seed cannot anchor certification)")


def _restore_round_disclosures(state, records):
    """#720: put back the per-round DISCLOSURE channels a `recordsPath` resume would otherwise lose.
    `build_receipt` reads them out of `state["rounds"]`, so before this a resumed run whose
    pre-resume rounds had recorded a vacuous seat / fall-open / canary gap / seat-map breach emitted
    a terminal receipt that silently claimed LESS than the run knew.

    Additive by construction: a channel is written with `setdefault`, so a live post-resume round's
    own `_record_round` for the same round number always wins and nothing already in the round entry
    is clobbered. Fail-closed on every edge — a record with no `disclosures` block resumes exactly as
    before (no key is invented; absence must never read as "checked and clean"), an EMPTY channel is
    not a disclosure and is left out, a wrong-shaped value is DROPPED while the round still resumes,
    and a record whose round number is not an integer is skipped rather than keyed on junk."""
    for rec in records:
        raw = rec.get(review_memory.DISCLOSURES_FIELD)
        if not isinstance(raw, dict):
            continue
        try:
            key = str(int(rec.get("round")))
        except (TypeError, ValueError):
            continue
        target = state["rounds"].setdefault(key, {})
        for chan, shape_ok in RESUMABLE_DISCLOSURE_CHANNELS.items():
            if chan in _DISCLOSE_ON_PRESENCE:
                if chan not in raw:
                    continue
                value = raw.get(chan)
            else:
                value = raw.get(chan)
                if not value:
                    continue
            if not shape_ok(value):
                continue
            target.setdefault(chan, value)
        if not target:
            # Nothing survived: leave `rounds` exactly as an older (channel-less) file leaves it,
            # so a resume never invents an empty round entry in the receipt.
            state["rounds"].pop(key, None)


def load_state(session_dir):
    """(ok, state_or_reason). A missing file → (True, None) fresh. A v1 file is REFUSED — session
    dirs are per-invocation, there is no migration; the caller must start fresh.

    #723: BOTH `SCHEMA_VERSION` (2, an in-flight session) and `STATE_SCHEMA_VERSION` (3, a session
    minted after #723) are accepted, and a loaded state is returned EXACTLY as it was persisted:
    `schemaVersion` is never rewritten and no v3 default field is injected. `state_hash` hashes the
    whole canonical state, so seeding one v3 key here would invalidate the `expectedStateHash` a v2
    session's last `next` already handed out and break its next `submit`. v3-only fields are read
    with `.get()` at their read sites instead. (`_migrate_judgment_step` is the ONE pre-existing
    in-place migration; it is unchanged, fires only for the #507 R2a stall/judgment state, and
    predates the hash-preservation rule it deliberately trades against.)"""
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
    _migrate_judgment_step(data)
    return True, data


def _migrate_judgment_step(state):
    """#507 R2a step migration (schemaVersion stays 2). A state persisted under the OLD routing —
    tradeoff/judgment blockers dead-ended at the `present-stall-menu` terminal — is re-pointed to
    the `present-judgment` gate so `next` re-emits the judgment action under the new contract. The
    tell is a state parked at `present-stall-menu` that still carries `_judgmentFindings` (only the
    old judgment→stall routing set both together; the audit-stall path never sets judgment findings).
    The stale stall `pending` is dropped so `next` recomputes the action from state. In-place."""
    if not isinstance(state, dict):
        return state
    if state.get("step") == P_STALL and state.get("_judgmentFindings"):
        state["step"] = P_JUDGMENT
        state.pop("_stallChoices", None)
        state.pop("_acceptRiskEligible", None)
        pend = state.get("pending")
        if isinstance(pend, dict) and pend.get("phase") == P_STALL:
            state["pending"] = None
    return state


def save_state(session_dir, state):
    path = os.path.join(session_dir, STATE_FILE)
    round_commit.atomic_write_bytes(path, _canonical(state).encode("utf-8"))


# =============================================================================================
# the round flow — planner + fold (shared by run_loop and the CLI)
# =============================================================================================

def _blocking(findings):
    return [f for f in findings if isinstance(f, dict)
            and circuit_breaker.is_blocking(f.get("severity"))]


def _open_critical(findings):
    return [f for f in findings if isinstance(f, dict)
            and circuit_breaker.is_critical(f.get("severity"))]


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
    (so `_round_reviewed` / `_confirmation_qualifies` read it), the challenged-annotated coverage
    accumulated so far, and the recurrence-derived generalize grace (recurrent_classes over PRIOR
    records + coverage — the same current=compiled / prior=record split tally_round_decider uses)."""
    findings = [f for f in (findings or []) if isinstance(f, dict)]
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
    brk = circuit_breaker.check_circuit_breaker(records, config.get("maxRounds", 7))
    if brk.get("halt") and brk.get("reason") == "challenged-principle-recurring":
        return brk
    return None


def _park_cannot_certify(state, detail):
    """A fail-closed park with certification withheld (challenged principle / corrupt resume). Maps
    to a `halted` terminal — never a silent clean."""
    state["terminal"] = "cannot-certify"
    state["certification"] = {"shape": None, "reason": detail or "cannot certify — park"}
    _decision(state, "cannot-certify", detail)
    state["step"] = P_TERMINAL


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
        payload = _shard_payload(state.get("reviewedDiff"), dims)
    elif step == P_VERIFIERS:
        staged = verification.stage_ids(state.get("_toVerify") or [])
        payload = {"clusters": verification.cluster_findings(staged)}
    elif step == P_SYNTHESIS:
        payload = {"findings": state.get("_verified") or []}
    elif step == P_GAPSWEEP:
        payload = {"verifiedFindings": state.get("findings") or [],
                   "fullDiff": True}
    elif step == P_AUDITS:
        payload = {"targets": state.get("_auditTargets") or []}
    elif step == P_SCOPED:
        payload = {"hunks": state.get("_newSurface") or {}, "tier": DEEP}
    elif step == P_VERIFY:
        payload = {"command": config.get("verifyCommand", "none")}
    elif step == P_FIXER:
        payload = {"batch": state.get("_fixBatch") or []}
        if state.get("_escalatedRung"):
            payload["escalatedRung"] = state["_escalatedRung"]
    elif step == P_JUDGMENT:
        judgment = [f for f in (state.get("_judgmentFindings") or []) if isinstance(f, dict)]
        row_ids = _judgment_row_ids(judgment)
        payload = {"findings": [
            {"id": row_ids[i], "file": f.get("file"), "line": f.get("line"),
             "title": f.get("title"), "severity": f.get("severity"),
             "classification": "judgment", "dispositions": list(JUDGMENT_DISPOSITIONS)}
            for i, f in enumerate(judgment)]}
    elif step == P_STALL:
        # The stall menu is the audit-stall TERMINAL only (a tradeoff/judgment blocker routes to
        # present-judgment, never here — #507 R2a). No judgment findings ride this payload.
        #
        # Both fields are advertised from the PERSISTED `_stallTargets` snapshot, the same source
        # the submit chokepoint (`stall-accept-risk-not-eligible`) and the fold already re-check
        # against — never from the cached `_acceptRiskEligible` boolean, which a prior version may
        # have written under a broader rule. The chokepoint was already honest; this makes the
        # DISPLAY honest too, so the menu can no longer offer a choice the fold will refuse.
        # axis: the SOURCE the menu advertises from. Asserting the flag's value would pass against
        # a menu still reading the cached boolean whenever the two happen to agree.
        eligible = _stall_targets_accept_risk_eligible(state)
        choices = list(state.get("_stallChoices") or STALL_CHOICES)
        if not eligible:
            choices = [c for c in choices if c != ACCEPT_RISK_CHOICE]
        payload = {"choices": choices, "acceptRiskEligible": eligible}
    return {"action": step, "round": rnd, "phase": step, "payload": payload}


def _record_round(state, key, value):
    rec = state["rounds"].setdefault(str(state["round"]), {})
    rec[key] = value


def _decision(state, kind, detail):
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


def _fold(state, config, phase, artifact, changed_subjects_seam=None):
    """Fold one submitted artifact and advance state. Big switch on phase; each arm delegates the
    JUDGMENT to a pure decider and only records/sequences here. Returns the mutated state.

    `changed_subjects_seam` is threaded to the fixer fold: run_loop passes the injected seam (the
    eval harness replays the fixture's subjects); the CLI submit path passes None so the fixer fold
    wires the real git derivation. It is inert for every other phase."""
    artifact = artifact if isinstance(artifact, dict) else {}
    _record_adapter_provenance(state, artifact, phase)
    if phase == P_PANEL:
        _fold_panel(state, config, artifact)
    elif phase == P_VERIFIERS:
        _fold_verifiers(state, config, artifact)
    elif phase == P_SYNTHESIS:
        _fold_synthesis(state, config, artifact)
    elif phase == P_GAPSWEEP:
        _fold_gapsweep(state, config, artifact)
    elif phase == P_AUDITS:
        _fold_audits(state, config, artifact)
    elif phase == P_SCOPED:
        _fold_scoped(state, config, artifact)
    elif phase == P_VERIFY:
        _fold_verify(state, config, artifact)
    elif phase == P_FIXER:
        _fold_fixer(state, config, artifact, changed_subjects_seam)
    elif phase == P_JUDGMENT:
        _fold_judgment(state, config, artifact)
    elif phase == P_STALL:
        _fold_stall(state, config, artifact)
    return state


# ---- round-1 / full-panel legs --------------------------------------------------------------

_PANEL_VENDORS = tuple(model_registry.VENDORS)  # SSOT — never a hand-maintained copy (#563/§11)

# The four artifact-envelope keys `_fold_panel` reads off a panel artifact. They are NOT seat keys.
# In the legacy shape (no dict-valued `artifact["seats"]`, so the artifact ITSELF is the seats map)
# these names must be subtracted before judging seat keys; in the explicit `{"seats": {...}}` shape
# nothing is subtracted, so one of these names appearing INSIDE the seats map is a real mis-key.
_PANEL_ENVELOPE_KEYS = ("seats", "seatMap", "ranManifest", "canaryResult")

# Derived from dispatch_outcome.py — the single home for not-run reason tokens (#747).
_DISPATCH_NOT_RUN_REASONS = dispatch_outcome.NOT_RUN_REASONS


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


def _canary_effective_vendor(seat_map, ran_manifest, dim):
    """Effective vendor for canary scope (rule 1): trusted ranManifest when known, else seat-map config."""
    manifest = ran_manifest if isinstance(ran_manifest, dict) else {}
    ran = manifest.get(dim)
    if isinstance(ran, str) and ran in _PANEL_VENDORS:
        return ran
    return _seat_map_configured_vendor(seat_map, dim)


def _usable_findings(seat):
    """Findings this panel will actually fold — only dict members count.

    ``canary_liveness`` and ``_fold_panel`` must share this predicate so a seat cannot
    skip the liveness probe while contributing nothing foldable (e.g. ``findings=[None]``).
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


def _canary_dimension_list(dimensions):
    if isinstance(dimensions, (list, tuple)):
        return [d for d in dimensions if isinstance(d, str)]
    return []


def _canary_probe_sort_key(probe):
    if not isinstance(probe, dict):
        return ("", "", "")
    eng = probe.get("engine")
    eng_s = eng if isinstance(eng, str) else repr(eng)
    engaged_s = repr(probe.get("engaged"))
    try:
        stable = json.dumps(probe, sort_keys=True, default=repr)
    except (TypeError, ValueError):
        stable = repr(probe)
    return (eng_s, engaged_s, stable)


def canary_liveness(dimensions, seat_status, seats, seat_map, ran_manifest, canary_result):
    """Per-vendor liveness judgement for a panel's cross-vendor seats.

    Pure on normalized inputs: malformed ``dimensions`` (non-list/tuple, or non-string
    members) are dropped; other arguments are type-guarded. Does not raise on those shapes.
    """
    dims = _canary_dimension_list(dimensions)
    status = seat_status if isinstance(seat_status, dict) else {}
    seat_data = seats if isinstance(seats, dict) else {}
    manifest = ran_manifest if isinstance(ran_manifest, dict) else {}
    probes = _normalize_canary_probes(canary_result)

    by_dim = {}
    vendor_dims = {}
    for dim in dims:
        eff = _canary_effective_vendor(seat_map, manifest, dim)
        if status.get(dim) != "run" or eff is None or eff == "claude":
            by_dim[dim] = "n/a"
        else:
            vendor_dims.setdefault(eff, []).append(dim)

    by_vendor = {}
    for vendor in sorted(vendor_dims):
        dims_v = sorted(vendor_dims[vendor])
        has_finding = False
        for dim in dims_v:
            if _usable_findings(seat_data.get(dim)):
                has_finding = True
                break
        if has_finding:
            for dim in dims_v:
                by_dim[dim] = "n/a"
            continue

        matching = []
        for probe in probes:
            if not isinstance(probe, dict):
                continue
            eng = probe.get("engine")
            if isinstance(eng, str) and eng == vendor:
                matching.append(probe)

        # Fail-closed on disagreement: any non-engaged match makes the vendor dead regardless of
        # list order (first-wins would let an engaged entry mask a failed duplicate).
        failing = [p for p in matching if p.get("engaged") is not True]
        engaged_ok = [p for p in matching if p.get("engaged") is True]
        if failing:
            deciding = sorted(failing, key=_canary_probe_sort_key)[0]
            st = "dead"
        elif engaged_ok:
            deciding = sorted(engaged_ok, key=_canary_probe_sort_key)[0]
            st = "proven"
        else:
            deciding = None
            st = "unproven"

        if deciding is not None:
            det = deciding.get("detail")
            detail_s = det if isinstance(det, str) else None
            ev = deciding.get("evidence")
            evidence = ev if isinstance(ev, dict) else None
        else:
            detail_s = None
            evidence = None

        by_vendor[vendor] = {
            "status": st, "seats": dims_v, "detail": detail_s, "evidence": evidence,
        }
        for dim in dims_v:
            by_dim[dim] = st

    for dim in dims:
        by_dim.setdefault(dim, "n/a")

    return {"byDim": by_dim, "byVendor": by_vendor}


def _normalize_canary_probes(canary_raw):
    if isinstance(canary_raw, dict):
        return [canary_raw]
    if isinstance(canary_raw, list):
        return [p for p in canary_raw if isinstance(p, dict)]
    return []


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


def _fold_panel(state, config, artifact):
    """Fold a full reviewer-deep panel. `artifact` maps dimension → {findings, receiptMissing?,
    receiptStale?}. A persistently receipt-missing/stale seat is terminal `missing` (shell
    :823-827 parity) but its findings ride the round record as UNVERIFIED/provisional — surfaced,
    never silently dropped (coordination note 2)."""
    seats = artifact.get("seats") if isinstance(artifact.get("seats"), dict) else artifact
    seat_map = artifact.get("seatMap") if isinstance(artifact.get("seatMap"), dict) else {}
    if seat_map:
        state["seatMap"].update(seat_map)
    raw = []
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
            not_run = seat.get("vacuous") is True or (
                isinstance(reason, str) and reason in _DISPATCH_NOT_RUN_REASONS)
            if not_run:
                status = "missing"
                if seat.get("vacuous") is True or (
                        isinstance(reason, str)
                        and reason == engine_adapter.REVIEW_FORFEIT_VACUOUS):
                    vacuous_dims.append(dim)
                elif isinstance(reason, str) and (
                        reason == dispatch_outcome.REASON_FORFEIT_ENGAGED_ARTIFACT):
                    engaged_artifact_dims.append(dim)
            if seat.get("receiptMissing") or seat.get("receiptStale"):
                status = "missing"
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
    # Cross-vendor liveness canary — per-vendor judgement via canary_liveness (pure).
    _sm_for_canary = state.get("seatMap") if isinstance(state.get("seatMap"), dict) else seat_map
    canary_panel_gap = False
    ran_manifest_canary = (artifact.get("ranManifest")
                           if isinstance(artifact.get("ranManifest"), dict) else {})
    live = canary_liveness(
        _panel_dimensions(config), seat_status, seats, _sm_for_canary,
        ran_manifest_canary, artifact.get("canaryResult"))
    unverified_dims = []
    failed_vendors = {}
    verified_by_vendor = {}
    for vendor, info in (live.get("byVendor") or {}).items():
        if not isinstance(info, dict):
            continue
        st = info.get("status")
        vdims = info.get("seats") if isinstance(info.get("seats"), list) else []
        if st == "unproven":
            unverified_dims.extend(vdims)
        elif st == "dead":
            for dim in vdims:
                if dim not in missing_dims:
                    missing_dims.append(dim)
                seat_status[dim] = "missing"
            failed_vendors[vendor] = info
        elif st == "proven":
            ev = info.get("evidence")
            verified_by_vendor[vendor] = ev if isinstance(ev, dict) else {}
    if unverified_dims:
        canary_panel_gap = True
        _record_round(state, "canaryUnverified", sorted(set(unverified_dims)))
        _decision(state, "canary-unverified",
                  "cross-vendor seat(s) (%s) returned zero findings and no engaged control "
                  "probe for their vendor — external-seat liveness unverified"
                  % ", ".join(sorted(set(unverified_dims))))
    if failed_vendors:
        failed_dims = sorted({d for info in failed_vendors.values()
                              for d in (info.get("seats") or [])})
        if len(failed_vendors) == 1:
            only = next(iter(failed_vendors.values()))
            cf_rec = {
                "seats": failed_dims,
                "detail": only.get("detail"),
                "evidence": only.get("evidence"),
            }
        else:
            cf_rec = {
                "seats": failed_dims,
                "vendors": {
                    v: {"detail": info.get("detail"), "evidence": info.get("evidence")}
                    for v, info in sorted(failed_vendors.items())
                },
            }
        _record_round(state, "canaryFailed", cf_rec)
        for vendor, info in sorted(failed_vendors.items()):
            vdims = sorted(info.get("seats") or [])
            detail = info.get("detail") or "engaged not true"
            _decision(state, "canary-failed",
                      "control probe for vendor %s showed no engagement (%s) — cross-vendor "
                      "seat(s) %s downgraded to never-ran"
                      % (vendor, detail, ", ".join(vdims)))
    if verified_by_vendor:
        if len(live.get("byVendor") or {}) == 1:
            _record_round(state, "canaryVerified",
                          next(iter(verified_by_vendor.values())))
        else:
            _record_round(state, "canaryVerified", verified_by_vendor)
    incomplete = bool(missing_dims) or canary_panel_gap
    compiled, drops = mechanical_compile(raw, state.get("reviewedDiff"))
    # A full reviewer-deep panel that runs COMPLETE in a DELTA round (round ≥ 2) is a qualifying
    # confirmation panel: it consumes one of the two-panel budget (the #174 bar). An INCOMPLETE panel
    # (a missing seat) does NOT qualify — it neither counts a confirmation nor resets/reseeds the
    # surfaced-since tracker, so the owed confirmation stays owed rather than being discharged on a
    # coverage gap. A complete panel resets the tracker and reseeds it from its OWN blocking findings
    # so a Critical it surfaces re-arms another confirmation (#174 requirement 2).
    if state["round"] >= 2 and not incomplete:
        state["confirmations"] = state.get("confirmations", 0) + 1
        state["surfacedSinceLastPanel"] = [
            "Critical" if circuit_breaker.is_critical(f.get("severity")) else "Important"
            for f in _blocking(compiled)]
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
    fell_open, prov_missing = _fell_open_rows(state.get("seatMap"), ran_manifest, seat_status)
    if fell_open:
        _record_round(state, "fellOpen", fell_open)
    if prov_missing:
        _record_round(state, "fellOpenProvenanceMissing", prov_missing)
    # #563 DoD1 v7: an ABSENT seat-map baseline would silently disable all fall-open detection (both
    # outputs anchor on the configured seat map). If the driver's live vendor pool has a cross-vendor
    # engine but no seat map was submitted, disclose provenance-unavailable for the whole panel — so an
    # absent seat map is loud, not silent (the exact class this feature prevents).
    _sm = state.get("seatMap")
    _seat_map_empty = not (isinstance(_sm, dict) and isinstance(_sm.get("seats"), dict) and _sm.get("seats"))
    _live_cross = sorted(v for v in (config.get("vendors") or [])
                         if isinstance(v, str) and v in _PANEL_VENDORS and v != "claude")
    if _seat_map_empty and _live_cross:
        _record_round(state, "seatMapUnavailable", _live_cross)
    _sm_violations = _seat_map_unexcused_violations(state.get("seatMap") or {})
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
        elif canary_panel_gap:
            unv = sorted({
                d for info in (live.get("byVendor") or {}).values()
                if isinstance(info, dict) and info.get("status") == "unproven"
                for d in (info.get("seats") or [])
            })
            vendors = sorted(
                v for v, info in (live.get("byVendor") or {}).items()
                if isinstance(info, dict) and info.get("status") == "unproven")
            _decision(state, "panel-incomplete-canary-gap",
                      "panel incomplete — cross-vendor seat(s) %s lack an engaged control probe "
                      "for vendor(s) %s; certification cannot be full-panel-confirmed"
                      % (", ".join(unv), ", ".join(vendors)))
    # Only a COMPLETE panel can anchor a full-panel-confirmed certification. A missing seat leaves
    # fullPanelRan False so a clean finish downgrades to audited-chain and names the gap.
    state["fullPanelRan"] = not incomplete
    # Track the OUTSTANDING coverage gap across the loop: an incomplete panel arms it (a converge
    # resting on it is withheld — a lens never ran); a COMPLETE panel recovers coverage and clears it
    # (#507 R2 residual-1). A scoped delta round leaves it untouched, so a round-1 gap never silently
    # clears on a delta finish.
    state["_incompletePanel"] = incomplete
    # A full panel re-establishes the review baseline: reset the cross-cutting-rework accumulator so a
    # broad fix BEFORE this panel does not count as the panel's rework, and the union runs from this
    # panel forward across every later fix (#507 R2 residual-5).
    state["_changedSubjectsSincePanel"] = []
    # In-memory review record for the challenged-coverage / recurrence breaker: a round-1 panel is
    # `baseline`, a re-armed / resumed full panel (round ≥ 2) is a `confirmation` (its per-dim run
    # map lets _confirmation_qualifies judge whether it can anchor certification).
    kind = "baseline" if state["round"] <= 1 else "confirmation"
    dim_map = {}
    for dim in _panel_dimensions(config):
        seat = seats.get(dim) if isinstance(seats, dict) else None
        s_findings = []
        # A missing seat defaults to LOW confidence, never high — an absent lens must never lend a
        # high-confidence run to `_confirmation_qualifies`.
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
    state["_toVerify"] = compiled
    state["step"] = P_VERIFIERS


def _fold_verifiers(state, config, artifact):
    """Apply per-finding verification verdicts deterministically (verification.apply_verdicts)."""
    verdicts = artifact.get("verdicts") if isinstance(artifact.get("verdicts"), list) else []
    staged = verification.stage_ids(state.get("_toVerify") or [])
    applied = verification.apply_verdicts(staged, verdicts)
    state["_verified"] = applied["findings"]
    _record_round(state, "verify", {"drops": applied["drops"], "downgrades": applied["downgrades"],
                                    "unverified": applied["unverified"], "ambiguous": applied["ambiguous"]})
    for d in applied["drops"]:
        _decision(state, "verifier-refuted", d.get("reason"))
    # round-1 findings and delta scoped candidates both route to synthesis; the delta settle is
    # armed on the delta path (see _fold_scoped) so _after_findings_settled re-settles the delta.
    state["step"] = P_SYNTHESIS


def _fold_synthesis(state, config, artifact):
    """Merge same-root-cause survivors (verification.merge_and_rank, coverage-guaranteed), then the
    author-justification POST-filter, then decide gap-sweep / fix / terminal."""
    grouping = artifact.get("grouping") if isinstance(artifact.get("grouping"), list) else None
    merged = verification.merge_and_rank(state.get("_verified") or [], grouping)
    findings = merged["findings"]
    kept, aj_drops = author_justification_filter(findings, config.get("priorComments"))
    for d in aj_drops:
        _decision(state, "author-justified-drop", d.get("justification"))
    _record_round(state, "authorJustifiedDrops", aj_drops)
    _record_round(state, "merges", merged["merges"])
    state["findings"] = kept
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
    compiled, _drops = mechanical_compile(candidates, state.get("reviewedDiff"))
    if compiled:
        # route candidates through verification like any other findings.
        state["_toVerify"] = compiled
        state["_gapMerge"] = True
        state["step"] = P_VERIFIERS
        # after verifiers → synthesis will merge with the already-settled findings.
        state["_verifiedCarry"] = state.get("findings") or []
        return
    _after_findings_settled(state, config)


def _location_id(finding):
    """Per-LOCATION key: line-less `finding_identity` plus line. Two same-title findings at
    DIFFERENT lines get DISTINCT keys (#507 R2 v5); audit target ids reuse this form with an
    occurrence suffix when the same file+title+line repeats in one batch."""
    return "%s@L%s" % (finding_identity(finding), finding.get("line"))


def _judgment_row_ids(findings):
    """Per-row disposition keys for judgment findings. Reuses the audit-target occurrence pattern:
    the first row at a location gets the bare per-location id; repeats get ``#1``, ``#2``, … so two
    surviving tradeoff findings at the same location (e.g. different severities) never share one id."""
    ids = []
    seen_location = {}
    for f in findings:
        if not isinstance(f, dict):
            ids.append(None)
            continue
        loc = _location_id(f)
        n = seen_location.get(loc, 0)
        seen_location[loc] = n + 1
        ids.append(loc if n == 0 else "%s#%d" % (loc, n))
    return ids


def _route_judgment_blockers(state, blocking):
    """Triage before composing an autonomous fix batch. A blocking finding carrying `tradeoff: true`
    is a PRODUCT-CHOICE / judgment call — the review-code contract routes it to the OWNER, never to
    the fixer for autonomous change. But the judgment gate is an INTERVENTION, not a terminal (#507
    R2a — the old routing dead-ended these in the stall menu, so a tradeoff blocker could never be
    fixed-and-audited): the owner disposes EACH judgment finding (fix-as-suggested /
    fix-with-guidance / skip) at the `present-judgment` phase, and the loop then folds the fixes into
    the round's fix batch and proceeds into the fix leg — the skips ride the exit disclosure. Any
    mechanical (non-tradeoff) blockers in the SAME batch are carried through the gate and ride
    straight into the fix batch alongside the fix-disposed judgment findings (never abandoned).
    Returns True when it took over routing (the caller must return); False when the batch is purely
    mechanical (the caller composes the fix batch as before)."""
    judgment = [f for f in blocking if isinstance(f, dict) and f.get("tradeoff")]
    if not judgment:
        return False
    mechanical = [f for f in blocking if isinstance(f, dict) and not f.get("tradeoff")]
    state["_judgmentFindings"] = [dict(f) for f in judgment]
    state["_judgmentMechanical"] = [dict(f) for f in mechanical]
    row_ids = _judgment_row_ids(judgment)
    _record_round(state, "judgmentBlockers", [
        {"id": row_ids[i], "file": f.get("file"), "line": f.get("line"),
         "title": f.get("title"), "severity": f.get("severity"), "classification": "judgment"}
        for i, f in enumerate(judgment)])
    _decision(state, "judgment-gate",
              "%d tradeoff/product-choice blocker(s) routed to owner judgment — never auto-fixed; "
              "each offered fix-as-suggested / fix-with-guidance / skip: %s"
              % (len(judgment), "; ".join(f.get("title") or "?" for f in judgment)))
    state["step"] = P_JUDGMENT
    return True


def _skipped_note(state):
    """The certification note for a run whose ONLY blocking work was owner-skipped judgment
    findings — they are disclosed product-choice tradeoffs, cited in the ledger, not fixed."""
    skipped = state.get("_skippedBlockers") or []
    if not skipped:
        return None
    return ("%d blocking finding(s) owner-skipped as product-choice tradeoffs — disclosed, not "
            "fixed: %s" % (len(skipped), "; ".join(s.get("title") or "?" for s in skipped)))


def _fold_judgment(state, config, artifact):
    """Fold the owner's per-finding judgment dispositions (#507 R2a — the judgment gate is an
    INTERVENTION, not a terminal). The artifact is `{dispositions: [{id, disposition, guidance?,
    reason?}, ...]}`, keyed to each `present-judgment` finding's identity. Each judgment finding is
    disposed:

      - `fix-as-suggested`  → folds into the round's fix batch;
      - `fix-with-guidance` → folds into the fix batch with the owner's free-text `guidance` attached;
      - `skip`              → requires a citable `reason` (recorded in the decision ledger); the
                              skipped blocker rides the exit disclosure (the skipped-blocking channel).

    FAIL-CLOSED: a listed judgment finding with a MISSING or UNKNOWN disposition — or a `skip` with
    no citable reason — folds as `fix-as-suggested`. A judgment blocker is NEVER silently skipped.
    The fixes join the round's fix batch alongside the mechanical (non-tradeoff) blockers carried
    through the gate, and the loop proceeds to `dispatch-fixer`; when the WHOLE fix batch is empty
    (every judgment finding skipped and no mechanical blocker) the loop settles into a converged
    terminal with the skips disclosed."""
    raw = artifact.get("dispositions") if isinstance(artifact.get("dispositions"), list) else []
    by_id = {}
    for d in raw:
        if not isinstance(d, dict) or d.get("id") is None:
            continue
        fid = d.get("id")
        prior = by_id.get(fid)
        if prior is not None and prior.get("disposition") != d.get("disposition"):
            _park_cannot_certify(state, "%s: %s" % (JUDGMENT_DISPOSITION_COLLISION_CAUSE, fid))
            state.pop("_judgmentFindings", None)
            state.pop("_judgmentMechanical", None)
            return
        by_id[fid] = d
    judgment = [f for f in (state.get("_judgmentFindings") or []) if isinstance(f, dict)]
    row_ids = _judgment_row_ids(judgment)
    fix_batch = [dict(f) for f in (state.get("_judgmentMechanical") or []) if isinstance(f, dict)]
    skipped = []
    disposition_log = []
    for i, f in enumerate(judgment):
        fid = row_ids[i]
        d = by_id.get(fid) if isinstance(by_id.get(fid), dict) else {}
        disposition = d.get("disposition")
        reason = d.get("reason")
        if disposition == "skip" and isinstance(reason, str) and reason.strip():
            skipped.append({"id": fid, "file": f.get("file"), "line": f.get("line"),
                            "title": f.get("title"), "severity": f.get("severity"),
                            "reason": reason.strip()})
            disposition_log.append({"id": fid, "title": f.get("title"), "disposition": "skip",
                                    "reason": reason.strip()})
            _decision(state, "judgment-skip",
                      "owner skipped judgment blocker %r — reason: %s"
                      % (f.get("title") or fid, reason.strip()))
            continue
        g = dict(f)
        if disposition == "fix-with-guidance":
            g["judgmentDisposition"] = "fix-with-guidance"
            guidance = d.get("guidance")
            if isinstance(guidance, str) and guidance.strip():
                g["guidance"] = guidance.strip()
            disposition_log.append({"id": fid, "title": f.get("title"),
                                    "disposition": "fix-with-guidance"})
        elif disposition == "fix-as-suggested":
            g["judgmentDisposition"] = "fix-as-suggested"
            disposition_log.append({"id": fid, "title": f.get("title"),
                                    "disposition": "fix-as-suggested"})
        else:
            # missing / unknown disposition, or a skip with no citable reason → fail closed to fix.
            g["judgmentDisposition"] = "fix-as-suggested"
            g["judgmentFailClosed"] = True
            disposition_log.append({"id": fid, "title": f.get("title"),
                                    "disposition": "fix-as-suggested", "failClosed": True})
            _decision(state, "judgment-fail-closed",
                      "judgment blocker %r had no valid disposition (%r) — folded as "
                      "fix-as-suggested (a judgment blocker is never silently skipped)"
                      % (f.get("title") or fid, disposition))
        fix_batch.append(g)
    if skipped:
        state["_skippedBlockers"] = (state.get("_skippedBlockers") or []) + skipped
        _record_round(state, "skippedBlockers", skipped)
    _record_round(state, "judgmentDispositions", disposition_log)
    state.pop("_judgmentFindings", None)
    state.pop("_judgmentMechanical", None)
    if fix_batch:
        state["_fixBatch"] = fix_batch
        state["step"] = P_FIXER
        return
    # Everything skipped and no mechanical blocker: settle. The skipped blockers are owner-accepted
    # product-choice tradeoffs (cited in the ledger) — converge, naming them on the exit disclosure.
    _terminal_converged(state, config, full_panel=state.get("fullPanelRan"),
                        note=_skipped_note(state))


def _after_findings_settled(state, config):
    """After the round's findings are verified + merged + justification-filtered: route to the fix
    leg when there is a blocking finding, else to the terminal decision (round 1 clean = certify).

    ONE definition (no post-def override): a delta round routes its scoped/gap candidates through
    verify+synthesis, so when the delta settle is armed it must re-settle the delta (audit breaker +
    #174 confirmation re-arm) rather than the round-1 fix/terminal path. Either way the gap/verify
    carry is merged back first."""
    # merge any gap-sweep / verify carry back in.
    if state.get("_verifiedCarry") is not None:
        carry = state.pop("_verifiedCarry")
        state["findings"] = (carry or []) + (state.get("findings") or [])
        state.pop("_gapMerge", None)
    if _ceiling_halt(state, config):
        return
    if state.get("_settleDelta"):
        _settle_delta(state, config)
        return
    blocking = _blocking(state.get("findings") or [])
    _record_round(state, "blockingCount", len(blocking))
    if blocking:
        if _route_judgment_blockers(state, blocking):
            return
        state["_fixBatch"] = [dict(f) for f in blocking]
        state["step"] = P_FIXER
    else:
        _terminal_converged(state, config, full_panel=state.get("fullPanelRan"))


# ---- fix + verify legs ----------------------------------------------------------------------

def _subjects_for_dimension(dimension):
    """Policy subjects mentioned by a compiled finding's dimension label — a single label
    ('Security') or a merged one ('Security + Code'). Reuses review_round_policy's mapping so the
    driver derives subjects the one way the confirmation economics read them (never a second
    mapping)."""
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
    Attributing rework through the accumulated history — not only the deciding round — is what lets
    a confirmation panel's own surfaced findings attribute the post-panel rework files, so the
    cross-cutting-rework re-arm is not structurally inert."""
    out = []
    for rec in state.get("_records") or []:
        for f in rec.get("findings") or []:
            if isinstance(f, dict):
                out.append(f)
    for f in state.get("findings") or []:
        if isinstance(f, dict):
            out.append(f)
    return out


def _resolve_head_diff(artifact):
    """Resolve the post-fix head diff the delta split reads. The `dispatch-fixer` artifact may carry
    it INLINE (`headDiff`) or, since a real `git diff BASE...HEAD` can be hundreds of KB and cannot
    reasonably inline into a JSON submit artifact, as an ABSOLUTE file path (`headDiffPath`) the
    driver reads itself (#507). Inline WINS when present. A missing / non-absolute / unreadable path,
    or empty file content, is NOT an empty diff — it is an UNKNOWN surface, so the caller escalates
    to a full panel (the fail-closed unknown→run-everything rule) rather than silently computing an
    empty scoped surface. Returns (head_or_None, source) where source is 'inline'|'path'|'unknown'."""
    inline = artifact.get("headDiff")
    if inline is not None:
        return inline, "inline"
    path = artifact.get("headDiffPath")
    if isinstance(path, str) and path and os.path.isabs(path):
        try:
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            content = None
        if content:
            return content, "path"
    return None, "unknown"


def _fold_fixer(state, config, artifact, changed_subjects_seam=None):
    """Record the fixer's result; the fix-batch COMPOSITION stays orchestrator-side (the artifact),
    the driver sequences + records. The post-fix head diff rides the artifact (git, per the
    dispatch-fixer contract) so the next delta round can split_fix_surface against git — INLINE
    (`headDiff`) or as an absolute `headDiffPath` the driver reads (`_resolve_head_diff`); an
    unresolvable path fails to an unknown surface (full panel), never a silent empty scoped skip. The
    changed policy subjects the #174 confirmation re-arm consumes are SCRIPT-DERIVED here — from the
    reviewed-vs-head diff through the accumulated findings (#157/#158), NEVER the fixer's
    self-report. The derivation is an injectable seam symmetrical with reviewer/fixer/verify:
    run_loop may inject a scripted replay (the eval harness); the library default + the CLI path
    wire the real git derivation. Unknown/unparseable surface → None → the run-everything rule."""
    state["fixBatch"] = state.get("_fixBatch") or []
    head, head_source = _resolve_head_diff(artifact)
    state["headDiff"] = head
    state["_headDiffSource"] = head_source
    state["_headDiffUnknown"] = head_source == "unknown"
    _record_round(state, "headDiffSource", head_source)
    derive = changed_subjects_seam or derive_changed_subjects
    state["_changedSubjects"] = derive(
        state.get("reviewedDiff"), state.get("headDiff"), _accumulated_findings(state))
    # Accumulate the changed subjects since the last full panel so the #174 cross-cutting re-arm sees
    # rework that spreads across MULTIPLE post-confirmation fixes, not just this round's single-pair
    # delta (#507 R2 residual-5). ONLY delta/confirmation-round fixes (round ≥ 2) count as the
    # confirmation's rework — the round-1 BASELINE fix that resolves the initial review is not "rework
    # since the panel" (a broad baseline fix must not force a confirmation). An unknown surface (None)
    # makes the accumulation sticky-unknown (fail toward one more confirmation) until a panel resets it.
    subjects = state.get("_changedSubjects")
    if state["round"] >= 2:
        if subjects is None:
            state["_changedSubjectsSincePanel"] = None
        elif state.get("_changedSubjectsSincePanel") is not None:
            acc = set(state.get("_changedSubjectsSincePanel") or [])
            acc |= {s for s in subjects if isinstance(s, str)}
            state["_changedSubjectsSincePanel"] = sorted(acc)
    # Accumulate the fix's coverage decisions so the challenged-coverage breaker can see a decision
    # recorded on a principle a later round re-raises (annotateChallengedCoverage input).
    cds = artifact.get("coverageDecisions")
    if isinstance(cds, list):
        state.setdefault("_coverage", []).extend(d for d in cds if isinstance(d, dict))
    _record_round(state, "fix", {"fixes": artifact.get("fixes") or [],
                                 "escalated": bool(artifact.get("escalated") or state.get("_escalatedRung"))})
    state.pop("_escalatedRung", None)
    state["step"] = P_VERIFY


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


def _audit_result_entry_fault(entry, index, target_ids):
    """The shape fault (a reason string) in ONE audit-result entry, or None.

    `target_ids` is the driver's own set of audit-target ids — a result keyed to an id outside it
    can never match a target, so it is the audit-side twin of the #845 seat mis-key. An EMPTY set
    means the driver has no targets to key against, so no id is judged (mirroring the seat-key
    guard's empty-key rule) — never a false refusal.

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
    for index, entry in enumerate(results):
        fault = _audit_result_entry_fault(entry, index, target_ids)
        if fault:
            return "%s; resubmit the same phase/attempt/state-hash with a corrected artifact" % fault
    return None


def _verify_command_configured(config):
    """True when the profile configures a REAL verify command (not absent / `none`). A configured
    command must actually PASS — a skip result then means the run did not execute, so it fails closed
    rather than advancing unverified (#507 R2 residual-2)."""
    cmd = config.get("verifyCommand")
    if not isinstance(cmd, str):
        return False
    return cmd.strip().lower() not in ("", "none")


def _fold_verify(state, config, artifact):
    """Fold the verify result. FAIL-CLOSED (#507 v10): advance ONLY on an explicit `pass` or — WHEN NO
    verify command is configured — an explicit unverified skip (`skipped`/`none`/`unverified`). A
    `fail`, a `timeout`, a missing/None result, any unrecognized value, OR a skip result while a real
    verify command IS configured (the command did not actually run) HALTS with an honest reason that
    names the class — never advances into a delta round that could later certify."""
    result = artifact.get("result")
    _record_round(state, "verifyResult", result)
    if result == "fail":
        state["terminal"] = "halted"
        state["certification"] = {"shape": None, "reason": "verify gate failed"}
        _decision(state, "verify-fail", "verify gate failed — halt, certification withheld")
        state["step"] = P_TERMINAL
        return
    if result in _VERIFY_SKIP:
        if _verify_command_configured(config):
            # A configured verify command reported a skip — it did NOT actually run its checks. Fail
            # closed: a configured verification must PASS, never advance on a skip (#507 R2 residual-2).
            state["terminal"] = "halted"
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
        state["terminal"] = "halted"
        state["certification"] = {
            "shape": None,
            "reason": "verify gate did not pass (result %r) — halt, certification withheld" % (result,)}
        _decision(state, "verify-unresolved",
                  "verify result %r is not pass/skip — fail closed, certification withheld" % (result,))
        state["step"] = P_TERMINAL
        return
    # advance to the next (delta) round. The diff the just-finished round's panel/audit saw is the
    # `reviewed` side of the next split_fix_surface; the fixer's head diff is the `head` side.
    state["_priorReviewedDiff"] = state.get("reviewedDiff")
    state["round"] += 1
    state["reviewedDiff"] = state.get("headDiff") or state.get("reviewedDiff")
    _enter_delta_round(state, config)


# ---- delta rounds (2+) ----------------------------------------------------------------------

def _schedule_full_panel_unknown(state, detail):
    """The fail-closed unknown→run-everything rule: an unresolvable delta surface schedules a FULL
    reviewer-deep panel, never a silently-scoped (or silently-skipped) round."""
    _decision(state, "unknown-surface", detail)
    _record_round(state, "roundKind", "full-panel-unknown-surface")
    state["fullPanelRan"] = False
    state["step"] = P_PANEL


def _enter_delta_round(state, config):
    """Rounds 2+: split_fix_surface(reviewed, head, fixBatch). unknown → schedule a FULL panel
    (the existing unknown→run-everything rule). Else audit the fixed findings + scoped-find the new
    surface."""
    # An unresolvable post-fix head diff (a missing/unreadable `headDiffPath`, no inline diff) is an
    # unknown surface BEFORE the split runs — never fold it through as an empty diff (#507). This is
    # the honest recovery for the field defect: a lost head diff now runs a full panel, not a vacuous
    # scoped scan over nothing.
    if state.pop("_headDiffUnknown", False):
        _schedule_full_panel_unknown(
            state, "post-fix head diff unresolvable (source %r) — full reviewer-deep panel"
            % state.get("_headDiffSource"))
        return
    split = delta_surface.split_fix_surface(
        state.get("_priorReviewedDiff") or state.get("reviewedDiff"),
        state.get("headDiff"), state.get("fixBatch") or [])
    if split.get("unknown"):
        _schedule_full_panel_unknown(state, "delta surface unknown — full reviewer-deep panel")
        return
    # a delta (scoped) round is NOT a full panel — reset the flag so a scoped certifying finish is
    # `audited-chain`, not `full-panel-confirmed`. A re-armed confirmation panel re-sets it True.
    state["fullPanelRan"] = False
    state["_auditTargets"] = _audit_targets(state, config, split.get("auditTargets") or {})
    state["_newSurface"] = split.get("newSurface") or {}
    _record_round(state, "roundKind", "delta")
    state["step"] = P_AUDITS


def _audit_targets(state, config, audit_targets_map):
    """Location-grouped audit targets, each carrying the fixer's vendor so the orchestrator seats a
    DIFFERENT auditor vendor. Grounded in the fix batch (the fixed findings), attributed to the
    hunks that sit over their lines."""
    fixer_vendor = config.get("fixerVendor")
    auditor_vendor, independence = _auditor_vendor(config, fixer_vendor)
    if independence == "degraded":
        state["independenceDegraded"] = True
    targets = []
    seen_location = {}
    for f in state.get("fixBatch") or []:
        if not isinstance(f, dict):
            continue
        loc = _location_id(f)
        n = seen_location.get(loc, 0)
        seen_location[loc] = n + 1
        # Same ``%s#%d`` format as ``_slot_label`` roster occurrence suffixes; the two namespaces
        # stay disjoint because audit roster keys are per-location unique (no occurrence suffix)
        # and pre-change persisted ids carry no ``#``.
        tid = loc if n == 0 else "%s#%d" % (loc, n)
        targets.append({
            "id": tid,
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
            "auditorVendor": auditor_vendor,
            "independence": independence,
            "verdict": f.get("verdict"),
            "evidence": f.get("evidence"),
        })
    return targets


def _fold_audits(state, config, artifact):
    """Consume the fix-audit rulings deterministically (audits.apply_audit_results). Record the
    audit round for the audit-keyed breaker; new-issue candidates join the scoped-finder scan."""
    results = artifact.get("results") if isinstance(artifact.get("results"), list) else []
    targets = state.get("_auditTargets") or []
    # The DRIVER records the SELECTED independent auditor per target (its own seating decision).
    expected_auditors = {t.get("id"): t.get("auditorVendor")
                         for t in targets if isinstance(t, dict) and t.get("id") is not None}
    # Provenance rests on the ORCHESTRATOR's out-of-band dispatch manifest — {result-id: vendor} the
    # orchestrator recorded from its OWN dispatch records and carried in the submit artifact's
    # `collectionManifest`, NEVER derived from the result contents. The fold authenticates a clearing
    # ruling against THIS manifest (must exist AND equal the recorded selection); the in-result
    # `auditorVendor` echo is advisory only. The driver cannot cryptographically verify engine
    # identity and does not pretend to — the guarantee is exactly as strong as the orchestrator's
    # dispatch manifest (#507 WO-FIX-RECOVERY).
    collection_manifest = artifact.get("collectionManifest")
    if not isinstance(collection_manifest, dict):
        collection_manifest = None
    outcome = audits.apply_audit_results(targets, results, expected_auditors=expected_auditors,
                                         collection_manifest=collection_manifest)
    state["_auditOutcome"] = outcome
    # the audit round for check_audit_breaker: identity + effective ruling PLUS the recurrence class
    # keys the alias-tolerant stall match consumes (#507 v0) — carried straight off each audit entry
    # (audits.apply_audit_results threads them from the target). The `title` MUST ride too: without it
    # the breaker's canonical class key collapses to a title-less `dim::tax::` alias that merges two
    # DISTINCT classKeys sharing dimension/taxonomy into a false stall (#507 R2 v2).
    audit_round = {"round": state["round"], "outcomes": [
        {"identity": a.get("identity") or a.get("id"), "ruling": a.get("ruling"),
         "title": a.get("title"), "classKey": a.get("classKey"),
         "dimension": a.get("dimension"), "taxonomy": a.get("taxonomy")}
        for a in outcome["audits"]]}
    state["auditRounds"].append(audit_round)
    for pid in outcome.get("unauthenticated", []):
        _decision(state, "audit-provenance-fail",
                  "audit result for %s could not be authenticated against the orchestrator's "
                  "dispatch manifest (missing entry or wrong vendor) — not-discharged" % pid)
    for pid in outcome.get("echoMismatch", []):
        _decision(state, "audit-echo-mismatch",
                  "audit result for %s echoed a vendor other than the orchestrator's dispatch "
                  "manifest — advisory only; the manifest governed and the discharge stands" % pid)
    # Provenance rests on the orchestrator's dispatch manifest (never the result echo) — recorded
    # per round so the receipt discloses the trust basis (#507 WO-FIX-RECOVERY).
    _record_round(state, "auditProvenance", "collection-manifest")
    _record_round(state, "audits", outcome["audits"])
    _record_round(state, "auditIndependence",
                  targets[0]["independence"] if targets else "n/a")
    state["_newIssues"] = outcome["newIssues"]
    for aid in outcome["notDischarged"]:
        _decision(state, "not-discharged", aid)
    # Scoped-finder routing (#507 WO-R2b). Dispatch the scoped new-finding scan ONLY when the delta
    # split computed a NON-EMPTY new surface (`_newSurface`, set by `_enter_delta_round`). A
    # genuinely empty new surface (`unknown` was False — an unknown surface never reaches audits, it
    # routes to a full panel) SKIPS the scoped dispatch with a receipt-visible note, rather than
    # dispatching a vacuous scan that reviews nothing while looking conformant. The audits' own
    # new-issue candidates still route through the same fold (an empty-artifact `_fold_scoped`).
    if state.get("_newSurface"):
        state["step"] = P_SCOPED
        return
    _record_round(state, "scopedFinder", "skipped-empty-surface")
    _decision(state, "scoped-finder-skipped",
              "scopedFinder: skipped-empty-surface — the delta split computed an empty new "
              "surface; the scoped new-finding scan was skipped (audit new-issues still routed)")
    _fold_scoped(state, config, {})


def _fold_scoped(state, config, artifact):
    """Fold the scoped new-finding scan over the fix's new surface; its candidates + the audits'
    new-issue candidates route through the same stage/cluster/verify fold."""
    candidates = artifact.get("findings") if isinstance(artifact.get("findings"), list) else []
    new_issues = state.get("_newIssues") or []
    combined = list(candidates) + [ni for ni in new_issues if isinstance(ni, dict)]
    compiled, _drops = mechanical_compile(combined, state.get("reviewedDiff"))
    state["_postAudit"] = True
    if compiled:
        state["_toVerify"] = compiled
        state["step"] = P_VERIFIERS
        # after verify+synthesis, _after_findings_settled runs; but for delta rounds we need the
        # audit-breaker + confirmation re-arm, handled in _settle_delta.
        state["_settleDelta"] = True
        return
    state["findings"] = []
    _settle_delta(state, config)


def _settle_delta(state, config):
    """Delta-round terminal logic: audit-keyed breaker → self-recovery → stall menu; open-work →
    fix leg; else the converged decision (with the #174 confirmation re-arm)."""
    state.pop("_settleDelta", None)
    state.pop("_postAudit", None)
    outcome = state.get("_auditOutcome") or {"notDischarged": [], "discharged": []}
    max_rounds = config.get("maxRounds", 7)
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
    if _ceiling_halt(state, config):
        return
    breaker = circuit_breaker.check_audit_breaker(state["auditRounds"], max_rounds)
    new_blocking = _blocking(state.get("findings") or [])

    # track the severities surfaced THIS delta round since the last qualifying panel (for the #174
    # re-arm). Derived from the compiled findings, never the fixer's self-report.
    if new_blocking:
        state.setdefault("surfacedSinceLastPanel", []).extend(
            "Critical" if circuit_breaker.is_critical(f.get("severity")) else "Important"
            for f in new_blocking)
    for aid in outcome.get("notDischarged", []):
        if _batch_severity_is_critical(state, aid):
            state.setdefault("surfacedSinceLastPanel", []).append("Critical")

    if breaker.get("halt") and breaker.get("reason") == "audit-stall":
        _handle_stall(state, config, breaker)
        return
    if breaker.get("halt") and breaker.get("reason") == "max-iterations":
        crit = _open_critical(state.get("findings") or []) or _stalled_critical(state, config, breaker)
        if crit:
            _park_capped(state, breaker.get("detail"))
            return
        # #507 v12: at the audit-round cap, ONLY a latest round with zero not-discharged outcomes and
        # no open blocking finding may certify. An Important still not-discharged (or a new blocker)
        # parks — never certify clean over an unresolved blocker. Owner-accepted residual risk must
        # route through the stall menu's accept-the-disclosed-risk, not this auto-certify.
        if outcome.get("notDischarged") or new_blocking:
            _park_capped_open(state, (breaker.get("detail") or "reached the audit-round cap")
                              + " — blocking finding(s) remain not-discharged; certification withheld")
            return
        _terminal_converged(state, config, full_panel=False, note=breaker.get("detail"))
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
        nd = set(outcome.get("notDischarged", []))
        nd_targets = [dict(t) for t in (state.get("_auditTargets") or []) if t.get("id") in nd]
        batch = [dict(f) for f in new_blocking]
        # Dedupe on the per-LOCATION key (line-less identity + line), NOT the line-less identity alone:
        # a new blocker sharing a target's file+title at a DIFFERENT line is a DISTINCT finding, so
        # keying on identity alone would silently drop the unresolved audit target (#507 R2 residual-3).
        seen = {(finding_identity(f), f.get("line")) for f in batch}
        for t in nd_targets:
            ident = t.get("identity") or finding_identity(t)
            key = (ident, t.get("line"))
            if ident is not None and key not in seen:
                batch.append(t)
                seen.add(key)
        if _route_judgment_blockers(state, batch):
            return
        state["_fixBatch"] = batch
        state["step"] = P_FIXER
        return

    # converged candidate: last round's fixes all discharged + verify pass. Apply the #174
    # confirmation economics before certifying — a Critical surfaced since the last qualifying
    # panel, or cross-cutting rework, owes one more full confirmation panel (budget 2).
    surfaced = list(state.get("surfacedSinceLastPanel") or [])
    # Cross-cutting fires when EITHER the round's own resolving fix is cross-cutting (the single-round
    # signal) OR the UNION of delta rework since the last full panel is (reset in _fold_panel,
    # accumulated in _fold_fixer). The union disjunct is additive — it catches rework that spreads
    # across MULTIPLE post-confirmation fixes where no single fix is broad (#507 R2 residual-5),
    # without ever suppressing a re-arm the single-round signal already earns.
    cross = (review_round_policy.is_cross_cutting(state.get("_changedSubjects"))
             or review_round_policy.is_cross_cutting(state.get("_changedSubjectsSincePanel")))
    followup = review_round_policy.confirmation_followup(
        surfaced, state.get("confirmations", 0), cross,
        max_confirmations=MAX_CONFIRMATIONS)
    _record_round(state, "confirmationFollowup", followup)
    if followup.get("park"):
        _park_capped(state, followup.get("reason"))
        return
    if followup.get("rearm"):
        _decision(state, "confirmation-rearm", followup.get("reason"))
        state["round"] += 1
        state["fullPanelRan"] = False
        _record_round(state, "roundKind", "confirmation")
        state["reviewedDiff"] = state.get("headDiff") or state.get("reviewedDiff")
        state["step"] = P_PANEL
        return
    _terminal_converged(state, config, full_panel=state.get("fullPanelRan"))


def _batch_severity_is_critical(state, target_id):
    """True when `target_id` names a Critical audit target. `notDischarged` carries target ids
    (per-location, possibly occurrence-suffixed), so look up severity on `_auditTargets` first;
    fall back to line-less fixBatch scan only for a pre-change session whose targets lack a match."""
    for t in state.get("_auditTargets") or []:
        if isinstance(t, dict) and t.get("id") == target_id \
                and circuit_breaker.is_critical(t.get("severity")):
            return True
    for f in state.get("fixBatch") or []:
        if isinstance(f, dict) and finding_identity(f) == target_id \
                and circuit_breaker.is_critical(f.get("severity")):
            return True
    return False


def _ceiling_halt(state, config, prospective_round=None):
    """Ask the unconditional round ceiling; park loud when ``round >= ceiling``."""
    brk = circuit_breaker.check_round_ceiling(
        prospective_round if prospective_round is not None else state["round"],
        _round_ceiling(config))
    if brk.get("halt"):
        _park_round_ceiling(state, brk.get("detail"))
        return True
    return False


def _park_round_ceiling(state, detail):
    state["terminal"] = "halted"
    state["certification"] = {"shape": None, "reason": detail or "round ceiling reached"}
    _decision(state, "round-ceiling", detail)
    state["step"] = P_TERMINAL


def _park_capped(state, detail):
    state["terminal"] = "capped-with-open-critical"
    state["certification"] = {"shape": None, "reason": detail or "capped with an open Critical — park"}
    _decision(state, "capped-with-open-critical", detail)
    state["step"] = P_TERMINAL


def _park_capped_open(state, detail):
    """The audit-round cap reached with a non-Critical blocker still not-discharged: park, withhold
    certification — never certify clean over an unresolved Important (#507 v12)."""
    state["terminal"] = "capped-with-open-blocker"
    state["certification"] = {"shape": None,
                              "reason": detail or "capped with open blocking findings — park"}
    _decision(state, "capped-with-open-blocker", detail)
    state["step"] = P_TERMINAL


def _open_audit_target_ids(state):
    """Per-location ids still open this round, or None when the open set cannot be determined
    (legacy persisted session without ``_auditOutcome``)."""
    outcome = state.get("_auditOutcome")
    if not isinstance(outcome, dict):
        return None
    nd = outcome.get("notDischarged")
    if not isinstance(nd, list):
        return None
    return set(nd)


def _stalled_open_targets(state, breaker):
    """Targets that are both stalled (alias match) and still open this round — the single selection
    rule shared by stall self-recovery and the capped-with-open-critical check."""
    stalled = set(breaker.get("stalledIdentities") or [])
    if not stalled:
        return []
    open_ids = _open_audit_target_ids(state)
    matched = []
    if open_ids is not None:
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


def _stalled_critical(state, config, breaker):
    """A stalled identity whose fix batch carried a Critical still counts as an open Critical at the
    cap (fail toward park)."""
    for t in _stalled_open_targets(state, breaker):
        if circuit_breaker.is_critical(t.get("severity")):
            return [t]
    return []


# ---- stall self-recovery + menu -------------------------------------------------------------

def _handle_stall(state, config, breaker):
    """audit-stall → ONE invisible self-recovery (fixer re-dispatched one rung up via
    model_registry.escalate and/or another vendor, once, journaled). Still stalled → the stall
    menu."""
    if not state.get("selfRecovered"):
        state["selfRecovered"] = True
        fixer_vendor = config.get("fixerVendor")
        rung = model_registry.escalate(
            fixer_vendor, _SELF_RECOVERY_FIXER_MODEL, _SELF_RECOVERY_FIXER_EFFORT)
        if rung is not None:
            # A null escalation (unknown fixer vendor, or already top-of-ladder) is NOT recorded as an
            # escalation — leaving _escalatedRung unset keeps the P_FIXER payload and the fix record
            # honest (escalated:false), never a null-rung mislabeled escalated:true (#608 review).
            state["_escalatedRung"] = {"rung": rung, "vendor": fixer_vendor}
        _decision(state, "self-recovery",
                  "audit-stall — one invisible self-recovery (%s)"
                  % ("fixer escalated to %r" % (rung,) if rung is not None
                     else "no escalation rung available — fixer unchanged, escalated:false"))
        _record_round(state, "selfRecovery", {"rung": rung, "reason": breaker.get("detail")})
        batch = [dict(t) for t in _stalled_open_targets(state, breaker)]
        state["_fixBatch"] = batch or [dict(f) for f in (state.get("fixBatch") or [])]
        state["step"] = P_FIXER
        return
    # already self-recovered and still stalled → present the stall menu (never judge the dispute).
    accept_eligible = _accept_risk_eligible(state, breaker)
    stall_targets = [dict(t) for t in _stalled_open_targets(state, breaker)]
    state["_stallTargets"] = stall_targets
    choices = list(STALL_CHOICES) if accept_eligible else \
        [c for c in STALL_CHOICES if c != ACCEPT_RISK_CHOICE]
    if state.get("_oneMoreRoundUsed"):
        choices = [c for c in choices if c != ONE_MORE_ROUND_CHOICE]
    if not stall_targets:
        choices = [c for c in choices if c != ONE_MORE_ROUND_CHOICE]
    state["_stallChoices"] = choices
    state["_acceptRiskEligible"] = accept_eligible
    _decision(state, "stall-menu", "audit-stall persists after self-recovery — owner choice")
    state["step"] = P_STALL


def _accept_risk_eligible(state, breaker):
    """accept-the-disclosed-risk is offerable ONLY when a stalled audit target is CONFIRMED with a
    receipt (an owner may knowingly accept a proven, disclosed risk — never an unproven one)."""
    for t in _stalled_open_targets(state, breaker):
        if isinstance(t, dict) and t.get("verdict") == "CONFIRMED" and t.get("evidence"):
            return True
    return False


def _stall_targets_accept_risk_eligible(state):
    """Fold-time accept-risk eligibility from the persisted stall-target snapshot — never a cached
    boolean a prior version may have written under a broader rule."""
    for t in state.get("_stallTargets") or []:
        if isinstance(t, dict) and t.get("verdict") == "CONFIRMED" and t.get("evidence"):
            return True
    return False


def _fold_stall(state, config, artifact):
    """Fold the owner's stall choice; journal it. hold → park; accept-the-disclosed-risk → certify
    when eligible; one-more-round → re-enter the fix leg from the persisted stall-target snapshot."""
    choice = artifact.get("choice")
    _record_round(state, "stallChoice", choice)
    _decision(state, "stall-choice", choice)
    if choice == HOLD_CHOICE:
        state["terminal"] = "held"
        state["certification"] = {"shape": None, "reason": "owner chose to hold"}
    elif choice == ACCEPT_RISK_CHOICE and _stall_targets_accept_risk_eligible(state):
        _terminal_converged(state, config, full_panel=False,
                            note="owner accepted the disclosed (CONFIRMED) risk")
        return
    elif choice == ONE_MORE_ROUND_CHOICE:
        targets = state.get("_stallTargets") or []
        if not targets:
            _park_cannot_certify(
                state, "one-more-round requested but stalled targets could not be resolved")
            state["step"] = P_TERMINAL
            return
        state["_oneMoreRoundUsed"] = True
        state["_fixBatch"] = [dict(t) for t in targets]
        state["step"] = P_FIXER
        return
    else:
        # an ineligible accept-the-risk or an unknown choice fails closed to a park.
        state["terminal"] = "stalled"
        state["certification"] = {"shape": None,
                                  "reason": "stall unresolved — certification withheld"}
    state["step"] = P_TERMINAL


# ---- terminal certification -----------------------------------------------------------------

def _terminal_converged(state, config, full_panel, note=None):
    """Certify: last round's fixes all discharged + verify pass. Shape is full-panel-confirmed (a
    qualifying full confirmation panel ran) or audited-chain (scoped certifying finish, no final
    full panel — say so). Degraded independence appends -degraded.

    A converge over ANY owner-skipped judgment blocker is CLEAN EXCEPT FOR SKIPPED — never a plain
    success (the exit_skipped invariant): the certification `reason` leads with
    `clean-except-skipped: N blocker(s) skipped with citable reasons` (shape unchanged) so the
    terminal reads unmistakably non-plain, and the skips also ride the top-level receipt channel."""
    # An OUTSTANDING incomplete panel (a configured lens never ran, never recovered by a later
    # complete panel) cannot certify clean — a zero-finding finish over a coverage gap is "we did not
    # look", not "audited-chain". Silence never certifies: withhold + park (#507 R2 residual-1).
    if state.get("_incompletePanel"):
        _park_cannot_certify(
            state, "panel incomplete — a configured lens never ran and no complete panel has since "
            "recovered the coverage; certification withheld")
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
    if _seat_map_violated(state):
        shape_drivers.append("seat-map-violation")
    if _seat_map_unproven_liveness(state):
        shape_drivers.append("unproven-liveness")
    state["terminal"] = "converged"
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

def build_receipt(state, session_dir=None):
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
              "unverified": rec.get("unverified"),
              "authorJustifiedDrops": rec.get("authorJustifiedDrops"),
              "compileDrops": rec.get("compileDrops"),
              "selfRecovery": rec.get("selfRecovery"),
              "stallChoice": rec.get("stallChoice")}
        if rec.get("lensCoverage") is not None:
            rd["lensCoverage"] = rec.get("lensCoverage")
        # The per-round disclosure channels ride their ONE home (#720) — the same set a
        # `recordsPath` resume restores, so a resumed round's receipt discloses what its round
        # actually recorded. Emission is unchanged: truthiness, except the presence-emitting
        # channels named by `_DISCLOSE_ON_PRESENCE`.
        for chan in RESUMABLE_DISCLOSURE_CHANNELS:
            value = rec.get(chan)
            if value or (value is not None and chan in _DISCLOSE_ON_PRESENCE):
                rd[chan] = value
        rounds.append(rd)
    findings = [{"id": f.get("id"), "file": f.get("file"), "line": f.get("line"),
                 "title": f.get("title"), "severity": f.get("severity"),
                 "verdict": f.get("verdict"), "challenge": f.get("challenge"),
                 "unverified": f.get("unverified")}
                for f in (state.get("findings") or []) if isinstance(f, dict)]
    cfg = state.get("config") or {}
    degraded = []
    if _degraded(state):
        degraded.append("independence: a single live vendor — the fix's auditor is the fixer's "
                        "vendor; independence degraded and named in the certification shape")
    if _base_degraded(state):
        degraded.append(
            "base: reviewed against a base whose fetch degraded (%s) — the pin may be stale; "
            "named in the certification shape"
            % (cfg.get("baseFetch") or "baseFetch absent"))
    if _same_family_degraded(state):
        degraded.append(
            "panel independence: seat(s) %s were filled with the MAKER's own model family — no "
            "alternative family was live; disclosed by the seat map and named in the certification "
            "shape" % ", ".join(_same_family_seats(state)))
    _pin_seats = _seat_pin_excused_seats(state)
    if _pin_seats:
        degraded.append(
            "seat-map pin excusal: seat(s) %s authorized a disclosed constraint relaxation via pin; "
            "named in the certification shape" % ", ".join(_pin_seats))
    if _seat_map_violated(state):
        _viol_parts = []
        for v in _seat_map_violations(state):
            _viol_parts.append(_seat_map_violation_breach_prose(v))
        _shape = (state.get("certification") or {}).get("shape")
        if isinstance(_shape, str) and _shape.endswith("-constraint-violated"):
            degraded.append(
                "seat-map constraint breach: %s — certification shape marked -constraint-violated"
                % ", ".join(_viol_parts))
        else:
            degraded.append(
                "seat-map constraint breach: %s — breach recorded; certification withheld"
                % ", ".join(_viol_parts))
    # The skipped-blocking channel (#507 R2a): an owner-skipped judgment blocker rides the exit
    # disclosure — a product-choice tradeoff shipped un-fixed, cited by its owner reason. It appears
    # BOTH in the degraded disclosure prose AND as the dedicated top-level `skippedBlockers` list
    # (required by validate_receipt, possibly empty) so the channel can never be omitted.
    skipped_blockers = []
    for s in state.get("_skippedBlockers") or []:
        if not isinstance(s, dict):
            continue
        skipped_blockers.append({"id": s.get("id"), "title": s.get("title"),
                                 "severity": s.get("severity"), "reason": s.get("reason")})
        degraded.append("skipped-blocker: %r (%s:%s) owner-skipped as a product-choice tradeoff — "
                        "reason: %s" % (s.get("title"), s.get("file"), s.get("line"), s.get("reason")))
    for rkey in sorted((state.get("rounds") or {}), key=lambda k: int(k) if str(k).isdigit() else 0):
        rrec = state["rounds"][rkey]
        for row in (rrec.get("fellOpen") or []):
            degraded.append(
                "reviewer-fell-open (round %s): seat %s configured %s forfeited (%s) → re-ran on %s; "
                "that seat's cross-vendor mix degraded" % (
                    rkey, row.get("seat"), row.get("configured"), row.get("reason"), row.get("ran")))
        miss = rrec.get("fellOpenProvenanceMissing")
        if miss:
            degraded.append(
                "reviewer-fell-open-provenance-unavailable (round %s): cross-vendor seat(s) %s ran "
                "without a trusted ranManifest entry — fall-open provenance unverified" % (
                    rkey, ", ".join(miss)))
        smu = rrec.get("seatMapUnavailable")
        if smu:
            degraded.append(
                "reviewer-fell-open-seatmap-unavailable (round %s): live cross-vendor vendor(s) %s "
                "but no seat map submitted — fall-open provenance unverified for the panel" % (
                    rkey, ", ".join(smu)))
        vac = rrec.get("vacuousSeats")
        if vac:
            degraded.append(
                "vacuous-seat (round %s): seat(s) %s returned no findings and no verifiable "
                "investigation record — classed as never-ran" % (rkey, ", ".join(vac)))
        eng_art = rrec.get("engagedArtifactSeats")
        if eng_art:
            degraded.append(
                "engaged-artifact-seat (round %s): seat(s) %s produced a review our transport "
                "could not carry — they do not count toward certification; salvaged artifacts "
                "are available for independent verification" % (rkey, ", ".join(eng_art)))
        cuv = rrec.get("canaryUnverified")
        if cuv:
            cv = rrec.get("canaryVerified")
            verified_vendors = []
            if isinstance(cv, dict):
                if cv and all(isinstance(v, dict) for v in cv.values()):
                    verified_vendors = sorted(cv)
                elif cv:
                    verified_vendors = ["(probe submitted)"]
            probe_note = ""
            if verified_vendors:
                probe_note = " (engaged probe recorded for vendor(s) %s)" % ", ".join(verified_vendors)
            degraded.append(
                "canary-unverified (round %s): cross-vendor seat(s) %s returned zero findings "
                "with no engaged control probe for their vendor%s — external-seat liveness unverified"
                % (rkey, ", ".join(cuv), probe_note))
        cf = rrec.get("canaryFailed")
        if cf:
            seats_down = cf.get("seats") if isinstance(cf, dict) else []
            detail = cf.get("detail") if isinstance(cf, dict) else None
            evidence = cf.get("evidence") if isinstance(cf, dict) else None
            if isinstance(cf, dict) and isinstance(cf.get("vendors"), dict):
                parts = []
                for vendor, vinfo in sorted(cf["vendors"].items()):
                    if not isinstance(vinfo, dict):
                        continue
                    ev = vinfo.get("evidence")
                    ev_note = ""
                    if isinstance(ev, dict) and ev:
                        ev_note = "; evidence=%s" % ev
                    parts.append(
                        "vendor %s (%s%s)" % (
                            vendor, vinfo.get("detail") or "engaged not true", ev_note))
                detail_str = "; ".join(parts) if parts else (detail or "engaged not true")
            else:
                detail_str = detail or "engaged not true"
                if evidence and isinstance(evidence, dict):
                    detail_str = "%s; evidence=%s" % (detail_str, evidence)
            degraded.append(
                "canary-failed (round %s): the control probe showed no engagement (%s) — "
                "cross-vendor seat(s) %s downgraded to never-ran" % (
                    rkey, detail_str, ", ".join(seats_down or [])))
        roi = rrec.get("recordOrphansIgnored")
        if roi:
            degraded.append(
                "record-orphans-ignored (round %s): hand submit folded with durable seat record(s) "
                "%s still at this slot — records ignored (session already on hand-submit path)"
                % (rkey, ", ".join(roi)))
        ovg = rrec.get("orderVendorProvenanceGaps")
        if ovg:
            # Provenance-NEUTRAL wording: since the collector spans every read-only phase, a gap
            # can come from an absent seat-map entry OR from a DEFAULTED engine-preference read,
            # and those have different recoveries. Naming the seat map for both would send an
            # operator to the wrong file, so each row says which it was.
            seats = []
            for row in ovg:
                if not isinstance(row, dict):
                    continue
                seat = row.get("seat")
                if not (isinstance(seat, str) and seat):
                    continue
                label = seat
                phase_name = row.get("phase")
                if isinstance(phase_name, str) and phase_name:
                    label = "%s@%s" % (label, phase_name)
                if row.get("vendorSource") == VENDOR_SOURCE_DEFAULTED:
                    label = "%s (vendor defaulted — engine preferences unreadable)" % label
                seats.append(label)
            if seats:
                degraded.append(
                    "order-vendor-provenance-gap (round %s): seat(s) %s emitted without a resolved "
                    "vendor" % (rkey, ", ".join(seats)))
        prov_by_phase = _normalize_adapter_provenance(rrec.get("adapterProvenance"))
        for phase_name, prov in prov_by_phase.items():
            if not isinstance(prov, dict):
                continue
            if prov.get("dispatchManifestUnavailable"):
                degraded.append(
                    "adapter-provenance (round %s, %s): dispatch manifest unavailable — trusted "
                    "ranManifest/collectionManifest omitted" % (rkey, phase_name))
            mismatch = prov.get("vendorEchoMismatch")
            if isinstance(mismatch, list) and mismatch:
                parts = ["%s echo=%r manifest=%r" % (row.get("seat"), row.get("echo"),
                                                     row.get("manifest"))
                         for row in mismatch if isinstance(row, dict)]
                degraded.append(
                    "adapter-provenance (round %s, %s): vendor echo mismatch on seat(s): %s"
                    % (rkey, phase_name, "; ".join(parts)))
    scriptran = _scriptran_summary(session_dir) if session_dir else state.get("_scriptRan") or \
        {"invocations": 0, "byPhase": {}}
    base = {k: cfg.get(k) for k in ("baseRef", "baseBranch", "baseFetch", "mode", "baseRepo",
                                    "baseRepoCheck", "repoRoot", "diffBinding")
            if cfg.get(k) is not None}
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
        "seatMap": dict(state.get("seatMap") or {}),
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


_RECEIPT_REQUIRED = ("schemaVersion", "verdict", "certificationShape", "rounds", "findings",
                     "decisions", "seatMap", "scriptRan", "degraded", "skippedBlockers")


_ATTESTED_REQUIRED = ("schema", "verdict", "attestation", "rounds", "findings", "decisions",
                      "seatMap", "scriptRan", "degraded", "skippedBlockers", "artifacts", "roster")


def validate_receipt(receipt):
    """Validate a driver receipt's SHAPE — version-dispatched since #723.

    Two shapes are valid and they are structurally UN-CONFUSABLE, which is the point: a CERTIFIED
    receipt (`receipt-certified/2` or `/3`) carries its `certification` block and an allowlisted
    verdict; an ATTESTED receipt (`receipt-attested/1`, written by `attest`) carries an
    `attestation` block, the `uncertified-manual` verdict, and NO certification block at all. A
    reader can therefore never mistake a hand attestation for a certification, and a certified
    receipt can never smuggle in an attestation instead of a certification.

    Returns (ok, reason)."""
    if not isinstance(receipt, dict):
        return False, "receipt is not an object"
    if receipt.get("schema") == RECEIPT_ATTESTED_SCHEMA:
        return _validate_attested_receipt(receipt)
    return _validate_certified_receipt(receipt)


def _validate_attested_receipt(receipt):
    """The `receipt-attested/1` shape: `attestation` REQUIRED, `certification` FORBIDDEN, verdict
    pinned to `uncertified-manual`. A certification block here would be exactly the confusion the
    split exists to prevent (an attested receipt reading as a certified one)."""
    for key in _ATTESTED_REQUIRED:
        if key not in receipt:
            return False, "attested receipt missing required key %r" % key
    for key in ("certification", "certificationShape"):
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
    may carry an `auditProvenance` field (`collection-manifest` when the round ran fix audits) — it is
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
    for key in _RECEIPT_REQUIRED:
        if key not in receipt:
            return False, "receipt missing required key %r" % key
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
        return {"seats": seats, "seatMap": io.get("seatMap") if isinstance(io, dict) else {}}
    if action == P_VERIFIERS:
        return {"verdicts": seams["verifier"](payload.get("clusters"), state["round"])}
    if action == P_SYNTHESIS:
        return {"grouping": seams["synthesis"](payload.get("findings"), state["round"])}
    if action == P_GAPSWEEP:
        return {"findings": _reviewer_findings(
            seams["reviewer"]("gap-sweep", DEEP, state["round"], payload))}
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
    if action == P_SCOPED:
        return {"findings": _reviewer_findings(
            seams["reviewer"]("scoped-finder", DEEP, state["round"], payload))}
    if action == P_VERIFY:
        return {"result": seams["verify_runner"](payload.get("command"), state["round"])}
    if action == P_FIXER:
        return seams["fix_step"](payload.get("batch"), state["round"], payload)
    if action == P_JUDGMENT:
        gate = io.get("judgment_gate") if isinstance(io, dict) else None
        if callable(gate):
            return gate(payload)
        # No gate wired → fail closed, fix every judgment finding as suggested (never auto-skip).
        return {"dispositions": [{"id": f.get("id"), "disposition": "fix-as-suggested"}
                                 for f in (payload.get("findings") or [])]}
    if action == P_STALL:
        menu = io.get("stall_menu") if isinstance(io, dict) else None
        return {"choice": menu(payload) if callable(menu) else "hold"}
    return {}


def run_loop(seams, config=None):
    """Layer 1: drive the whole loop end-to-end with scripted seams. Ports the run-SHAPE of
    review_panel_shell.reviewPanel. Returns the driver receipt (validate_receipt-shaped)."""
    if not isinstance(seams, dict):
        raise ValueError("run_loop requires a seams dict")
    try:
        state = new_state(config)
    except RoundCeilingRefusal as refusal:
        state = new_state()
        _park_cannot_certify(state, refusal.reason)
        state["_scriptRan"] = {"invocations": 0, "byPhase": {}}
        return build_receipt(state)
    if state.get("_resumeCorrupt"):
        # A corrupt/mangled resume state fails closed — never certify off unreadable memory.
        _park_cannot_certify(state, state["_resumeCorrupt"])
        state["_scriptRan"] = {"invocations": 0, "byPhase": {}}
        return build_receipt(state)
    guard = 0
    try:
        while not state.get("terminal") and guard < _RUN_LOOP_GUARD:
            guard += 1
            step = _advance(state, state["config"])
            action = step["action"]
            if action == P_TERMINAL:
                break
            # handle the gap-sweep re-entry (verifiers → synthesis carries the merge back).
            artifact = _run_seam(seams, action, step["payload"], state, state["config"])
            _fold(state, state["config"], action, artifact, seams.get("changed_subjects"))
            # a delta round routes scoped candidates through verifiers; when that path is armed the
            # synthesis fold must re-settle the delta rather than the round-1 path.
            if state.pop("_settleDeltaAfterSynthesis", False):
                pass
    except JournalFaultUnrecordable as jf:
        # Last-resort fail-closed: a journal fault the driver could not even record parks
        # cannot-certify — the library layer NEVER continues (or crashes the caller) as though the
        # ran-evidence were intact. #507 WO-FIX-RECOVERY.
        _park_cannot_certify(state, "journal-fault-unrecordable: %s" % jf)
        state["_scriptRan"] = {"invocations": guard, "byPhase": {}}
        return build_receipt(state)
    if guard >= _RUN_LOOP_GUARD and not state.get("terminal"):
        state["terminal"] = "halted"
        state["certification"] = {"shape": None, "reason": "run_loop guard tripped — fail closed"}
    state["_scriptRan"] = {"invocations": guard, "byPhase": {}}
    return build_receipt(state)


# =============================================================================================
# Layer 2 — the stepwise CLI (next / submit)
# =============================================================================================

def _pending_step(state):
    return state.get("pending")


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
            sidecar_target = _sidecar_target_for_recover(session_dir)
            refusal = _commit_recover_or_refuse(session_dir, "next",
                                                sidecar_target=sidecar_target)
            if refusal is not None:
                return refusal
            return _cmd_next_locked(session_dir, config_overrides)
    except round_records.SessionLockHeld as held:
        return _lock_held_refusal(session_dir, "next", held)


def _cmd_next_locked(session_dir, config_overrides=None):
    ok, loaded = load_state(session_dir)
    if not ok:
        _journal_append(session_dir, {"cmd": "next", "phase": None, "round": None,
                                      "attempt": None, "outcome": "refused-v1"})
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
            state = new_state(config_overrides)
        except RoundCeilingRefusal as refusal:
            _journal_append(session_dir, {"cmd": "next", "phase": None, "round": None,
                                          "attempt": None, "outcome": "refused-round-ceiling",
                                          "reason": refusal.reason})
            return {"ok": False, "reason": refusal.reason, "value": refusal.value}
    else:
        state = loaded
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
        return _next_response(pend, state_hash(state))
    step = _advance(state, state["config"])
    attempt = 0
    prior = state.get("lastAccepted")
    if prior and prior.get("phase") == step["phase"] and prior.get("round") == step["round"]:
        attempt = prior.get("attempt", 0) + 1
    pending = {"action": step["action"], "round": step["round"], "phase": step["phase"],
               "attempt": attempt, "payload": step["payload"]}
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
    return _next_response(pending, state_hash(state))


def _receipt_fault_response(detail):
    """A terminal receipt integrity fault — the fail-loud `receipt-fault` family (the same family as
    `journal-fault-unrecordable`). Answered on the terminal `next` (first emission or a replay) and
    the terminating `submit`; the CLI surfaces it NONZERO and it is NEVER a `terminal`-with-ok."""
    return {"ok": False, "reason": "receipt-fault", "detail": detail}


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


def _next_response(pending, expected_hash):
    return {
        "ok": True,
        "action": pending["action"],
        "round": pending["round"],
        "phase": pending["phase"],
        "attempt": pending["attempt"],
        "expectedStateHash": expected_hash,
        "payload": pending.get("payload"),
    }


def cmd_submit(session_dir, phase, attempt, state_hash_arg, artifact, _via_advance=False,
               _pending_policy_applied=None, _durable_record=None):
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
    exists already, never that one is owed."""
    try:
        with round_records.session_lock(session_dir):
            sidecar_target = _sidecar_target_for_recover(session_dir)
            refusal = _commit_recover_or_refuse(session_dir, "submit",
                                                sidecar_target=sidecar_target)
            if refusal is not None:
                return refusal
            prep = _cmd_submit_prepare(session_dir, phase, attempt, state_hash_arg, artifact,
                                       _via_advance=_via_advance)
            if not prep.get("_fold_ready"):
                return prep
            state = prep["state"]
            round_no = prep["round_no"]
            art_hash = prep["art_hash"]
            _fold(state, state["config"], phase, artifact)
            if _via_advance and _pending_policy_applied is not None:
                applied = state.get("_policyApplied")
                if not isinstance(applied, list):
                    applied = []
                state["_policyApplied"] = list(applied) + [_pending_policy_applied]
            if _via_advance:
                state["_advanceUsed"] = True
            state["lastAccepted"] = {"phase": phase, "attempt": attempt, "round": round_no,
                                     "artifactHash": art_hash}
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
                c.add_replace_file(os.path.join(session_dir, STATE_FILE),
                                   _canonical(state).encode("utf-8"))
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
                return _commit_refused_response(session_dir, "submit", exc, phase=phase,
                                              rnd=round_no, attempt=attempt)
            if state.get("terminal"):
                fail = _terminal_receipt_gate(session_dir, state)
                if fail:
                    return _receipt_fault_response(fail)
            return {"ok": True, "round": round_no, "phase": phase, "nextStep": state.get("step")}
    except round_records.SessionLockHeld as held:
        return _lock_held_refusal(session_dir, "submit", held)


def _cmd_submit_prepare(session_dir, phase, attempt, state_hash_arg, artifact, _via_advance=False):
    ok, loaded = load_state(session_dir)
    if not ok:
        _journal_append(session_dir, {"cmd": "submit", "phase": phase, "round": None,
                                      "attempt": attempt, "outcome": "refused-v1"})
        return {"ok": False, "reason": loaded}
    if loaded is None:
        _journal_append(session_dir, {"cmd": "submit", "phase": phase, "round": None,
                                      "attempt": attempt, "outcome": "no-state"})
        return {"ok": False, "reason": "no loop-state.json — call next first"}
    state = loaded
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
            return resp

    # duplicate detection (an already-accepted submit re-sent — its state hash is now stale, but the
    # phase/attempt/artifact triple identifies it as an exact replay). At a terminal phase the gate
    # above already re-verified the receipt, so this only answers ok when the receipt is intact.
    if is_duplicate:
        _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                      "round": prior.get("round"), "attempt": attempt,
                                      "outcome": "duplicate"})
        return {"ok": True, "duplicate": True}

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
        fault = audit_results_fault(artifact, state.get("_auditTargets") or [])
        if fault:
            _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                          "round": pending.get("round"), "attempt": attempt,
                                          "outcome": "audit-ruling-shape"})
            return {"ok": False, "reason": fault}
    if phase == P_VERIFIERS:
        fault = verifier_results_fault(artifact)
        if fault:
            _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                          "round": pending.get("round"), "attempt": attempt,
                                          "outcome": "verifier-results-shape"})
            return {"ok": False, "reason": fault}
    if phase == P_STALL:
        choice = artifact.get("choice") if isinstance(artifact, dict) else None
        if isinstance(choice, str) and choice in RETIRED_STALL_CHOICES:
            reason = "%s%s" % (RETIRED_STALL_CHOICE_PREFIX, choice)
            _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                          "round": pending.get("round"), "attempt": attempt,
                                          "outcome": "stall-choice-retired"})
            return {"ok": False, "reason": reason}
        offered = state.get("_stallChoices")
        if offered is None:
            # Legacy persisted stall without a recorded menu — fail closed: only hold (and accept-risk
            # when the session recorded eligibility) were ever safe terminals.
            offered = [HOLD_CHOICE]
            if _stall_targets_accept_risk_eligible(state):
                offered.insert(0, ACCEPT_RISK_CHOICE)
        if isinstance(choice, str) and choice not in offered:
            reason = "%s%s" % (STALL_CHOICE_NOT_OFFERED_PREFIX, choice)
            _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                          "round": pending.get("round"), "attempt": attempt,
                                          "outcome": "stall-choice-not-offered"})
            return {"ok": False, "reason": reason}
        if choice == ACCEPT_RISK_CHOICE and not _stall_targets_accept_risk_eligible(state):
            _journal_append(session_dir, {"cmd": "submit", "phase": phase,
                                          "round": pending.get("round"), "attempt": attempt,
                                          "outcome": STALL_ACCEPT_RISK_NOT_ELIGIBLE})
            return {"ok": False, "reason": STALL_ACCEPT_RISK_NOT_ELIGIBLE}

    # #977: the record-submit interleave fence — mirror image of `advance-submit-interleaved`.
    # `cmd_submit` never reads the durable store, so `record-result` (or `--sweep`) followed by a
    # HAND submit silently discards recorded seats and can certify an incomplete panel while
    # answering `ok`. Refuse HERE, before the fold, so the pending step survives; fold through
    # `advance` instead (or supersede a `seat-missing` slot on a refuse-fold phase, then advance).
    orphan_seats_found = None
    if not _via_advance:
        rnd = pending.get("round")
        # Only adapter phases carry durable store records — gate phases (present-judgment,
        # present-stall-menu) are hand-submitted and have no roster. Resolve without journaling:
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
            "orphan_seats_found": orphan_seats_found}


def _write_receipt(session_dir, state):
    """Write the terminal receipt atomically. OSError PROPAGATES — a receipt-write failure is itself
    a receipt defect the CLI must surface (see _finalize_receipt), never a silent swallow (#507
    v14)."""
    receipt = build_receipt(state, session_dir)
    path = os.path.join(session_dir, RECEIPT_FILE)
    round_commit.atomic_write_bytes(
        path, (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"))
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
        return "terminal receipt unreadable (%s) — cannot certify; treat as park" % exc
    ok, why = validate_receipt(on_disk)
    if not ok:
        return "terminal receipt invalid (%s) — cannot certify; treat as park" % why
    if not (on_disk.get("scriptRan") or {}).get("invocations"):
        return ("terminal receipt scriptRan is empty — the journal (the driver's ran evidence) did "
                "not persist; cannot certify; treat as park")
    if _journal_faulted(session_dir):
        return ("driver journal recorded a write fault — the scriptRan evidence is incomplete "
                "(a next/submit event was lost); cannot certify; treat as park")
    return None


def _finalize_receipt(session_dir, state):
    """At a terminal, write + read back + validate the on-disk receipt. A write failure, an
    unreadable readback, an invalid shape, or an EMPTY scriptRan (the journal — the driver's `ran`
    evidence — did not persist) is a RECEIPT DEFECT: return a reason so the CLI fails closed (the
    orchestrator must treat it as a park), never certifying on a missing/short receipt (#507 v14).
    Returns None on success."""
    try:
        _write_receipt(session_dir, state)
    except OSError as exc:
        return "terminal receipt write failed (%s) — cannot certify; treat as park" % exc
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
    `_receiptFault` detail so the durability survives across separate CLI processes (#507).

    INVARIANT (#507, third audit): no terminal-phase invocation — first-emission next, replayed next,
    terminating submit, or a duplicate/replayed submit — may answer ok without a fresh on-disk receipt
    verification through this gate, no exceptions."""
    if state.get("_receiptFinalized"):
        fault = _verify_terminal_receipt(session_dir)
    else:
        fault = _finalize_receipt(session_dir, state)
        state["_receiptFinalized"] = True
    state["_receiptFault"] = fault or None
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
#   - every subcommand here is v3-ONLY. A session already in flight when this shipped carries a v2
#     state that has none of this bookkeeping, so it keeps `next`/`submit` and is refused here with
#     `legacy-session-use-next-submit` — writing v3 defaults into a loaded v2 state would change its
#     `state_hash` and break its next `submit` (see `load_state`).


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


def _commit_recover_or_refuse(session_dir, cmd, sidecar_target=None):
    try:
        round_commit.recover(session_dir, sidecar_target=sidecar_target)
    except round_commit.CommitRefused as exc:
        return _refuse_cmd(session_dir, cmd, "commit-recovery-failed", fault=FAULT_INTERNAL,
                           detail="%s: %s" % (exc.reason, exc.detail))
    return None


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


def _envelope_with_head_diff(session_dir, envelope, content, rnd, phase, seat_key, attempt,
                             occurrence):
    diff_path = round_records.head_diff_store_path(session_dir, rnd, phase, seat_key, attempt,
                                                   occurrence)
    payload = dict(envelope.get("payload") or {})
    payload["headDiffStorePath"] = diff_path
    final = dict(envelope)
    final["landedPayloadSha256"] = envelope.get("payloadSha256")
    final["payload"] = payload
    final["payloadSha256"] = round_records.payload_sha256(payload)
    return diff_path, content.encode("utf-8"), final, final["payloadSha256"]


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
        return None, _refuse_cmd(session_dir, cmd, LEGACY_SESSION_REFUSAL,
                                 detail="loop-state.json is schemaVersion %r; `next`/`submit` "
                                        "finish it" % (loaded.get("schemaVersion"),))
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


def _plugin_resource_root():
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _shipped_rubric_path():
    return os.path.join(_plugin_resource_root(), "rubric", "review-base.md")


def _shipped_escalation_wrapper_path():
    return os.path.join(_plugin_resource_root(), "lib", "escalation_resolve.py")


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
    if not isinstance(vendor, str) or not vendor.strip():
        return False
    v = vendor.strip()
    if v == "claude":
        return False
    return v in model_registry.vendors()


def _seat_is_engine(row):
    """True when the seat's vendor is an external engine (sandboxed stdout transport)."""
    return _vendor_is_external_engine(row.get("vendor"))


CHANNEL_FILE = "file"
CHANNEL_STDOUT = "stdout"

# Phases whose seats an orchestrator dispatches through `dispatch-review` — a READ-ONLY sandbox on
# an external engine. `dispatch-fixer` is deliberately absent: it is a foreground in-place writer,
# never a `dispatch-review` consumer, and its vendor is UNKNOWN by default (#608), so folding an
# absent vendor to the stdout contract there would rewrite a deliberate default rather than close a
# forfeit. DERIVED from `round_orders.ORDER_PHASES` (not hand-typed) so a phase added there and
# forgotten here cannot silently fold an unresolved vendor to the WRITE contract (#1035).
_READ_ONLY_CHANNEL_PHASES = frozenset(round_orders.ORDER_PHASES) - {P_FIXER}


VENDOR_SOURCE_CONFIGURED = "configured"
VENDOR_SOURCE_DEFAULTED = "defaulted"


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
    answered from real configuration, `defaulted` when it did not and the all-claude stand-in
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


def _effective_seat_map(state):
    """Seat map for order emission: the state copy wins; otherwise the seeded config (#723)."""
    sm = state.get("seatMap")
    if isinstance(sm, dict) and isinstance(sm.get("seats"), dict) and sm.get("seats"):
        return sm
    cfg_sm = (state.get("config") or {}).get("seatMap")
    if isinstance(cfg_sm, dict):
        return cfg_sm
    return sm if isinstance(sm, dict) else {}


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


def _seat_transport_row(state, phase, seat_key, occurrence, config, pending_payload, repo_root,
                        seat_map=None):
    """{vendor, model, engine} for transport — one home keyed to the source that actually knows."""
    if phase == P_PANEL:
        return _seat_dispatch_row(state, seat_key, seat_map=seat_map)
    cfg = config if isinstance(config, dict) else {}
    payload = pending_payload if isinstance(pending_payload, dict) else {}
    if phase == P_FIXER:
        return {"vendor": cfg.get("fixerVendor"), "model": None, "engine": None}
    if phase == P_AUDITS:
        targets = payload.get("targets")
        if not isinstance(targets, list):
            targets = []
        for target in targets:
            if isinstance(target, dict) and target.get("id") == seat_key:
                return {"vendor": target.get("auditorVendor"), "model": None, "engine": None}
        return {"vendor": None, "model": None, "engine": None}
    if phase == P_SYNTHESIS:
        # Synthesis is Claude-only ($SYNTH_MODEL); never route through external reviewer engines.
        return {"vendor": "claude", "model": None, "engine": None}
    if phase in (P_VERIFIERS, P_GAPSWEEP, P_SCOPED):
        vendor, source = _reviewer_engine_vendor(repo_root)
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


def _profile_path_for_orders(repo_root):
    """Resolved project profile path for fixer orders — never a hand-typed layout guess."""
    try:
        path = model_tier_overrides.resolve_profile_path(repo_root)
    except calibration_resolve.UnresolvableRootError as exc:
        refusal = core_md.gate_refusal_line(
            core_md.gate_refusal(exc.reason, str(exc.root)))
        return "(Project profile refused — %s)" % refusal
    if isinstance(path, str) and path.strip():
        return path
    return "(Project profile not resolved for this project)"


def _shell_quote_path(path):
    """Shell-safe quoted path for commands the fixer order tells the seat to run."""
    return shlex.quote(path if isinstance(path, str) and path else "")


def _panel_dimension_label(seat_key):
    """Rubric dimension label for a panel seat — from SUBJECT_FALLBACK, not filename stem."""
    stem = AGENT_SUFFIX.get(seat_key)
    if not isinstance(stem, str) or not stem:
        return None
    return review_round_policy.SUBJECT_FALLBACK.get(stem.split("-")[0].lower())


def _session_pr_checkout_path(session_dir):
    """Detached PR checkout path when the read-only paths created one; else empty."""
    path = os.path.join(session_dir, "repo")
    return path if os.path.isdir(path) else ""


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
        ("ESCALATION_WRAPPER_PATH", _shipped_escalation_wrapper_path()),
    )
    for name, expected in checks:
        emitted = placeholders.get(name)
        if _paths_match(emitted, expected) and not os.path.isfile(expected):
            return "shipped-resource-missing:%s" % name
    return None


# Order-input sidecar layout — one home for commit writes and order placeholders.
ORDER_SIDECAR_CLUSTERS_DIR = "clusters"
ORDER_SIDECAR_AUDIT_TARGETS_DIR = "audit-targets"
ORDER_SIDECAR_SCOPED_HUNKS_FILE = "scoped-hunks.json"
ORDER_SIDECAR_VERIFIED_FILE = "verified.json"


def _order_cluster_sidecar_path(rdir, index):
    return os.path.join(rdir, ORDER_SIDECAR_CLUSTERS_DIR, "%d.json" % index)


def _order_audit_target_sidecar_path(rdir, skey):
    return os.path.join(rdir, ORDER_SIDECAR_AUDIT_TARGETS_DIR, "%s.json" % skey)


def _order_scoped_hunks_sidecar_path(rdir):
    return os.path.join(rdir, ORDER_SIDECAR_SCOPED_HUNKS_FILE)


def _order_verified_sidecar_path(rdir):
    return os.path.join(rdir, ORDER_SIDECAR_VERIFIED_FILE)


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
        writes.append((path, round_records.canonical({"findings": findings}).encode("utf-8")))
    return writes


def _session_meta(session_dir):
    obj, err = round_records.read_json(os.path.join(session_dir, round_records.META_FILE))
    return obj if (err is None and isinstance(obj, dict)) else {}


def _ensure_round_diff(session_dir, rnd, state):
    """Write `round-<N>/diff.txt` when absent or untrusted so order templates have a real path to cite."""
    rdir = round_records.round_dir(session_dir, rnd)
    diff_path = os.path.join(rdir, "diff.txt")
    diff_text = state.get("reviewedDiff")
    if not isinstance(diff_text, str):
        raise ValueError("reviewed-diff-unavailable")
    expected = diff_text.encode("utf-8")
    needs_write = True
    if os.path.isfile(diff_path):
        try:
            with open(diff_path, "rb") as fh:
                on_disk = fh.read()
            needs_write = on_disk != expected
        except OSError:
            needs_write = True
    if needs_write:
        round_commit.atomic_write_bytes(diff_path, expected)
    return diff_path


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


def _order_placeholders(phase, seat_key, occurrence, state, config, pending_payload,
                        session_dir, rnd, paths, channel):
    """Phase-specific placeholder dict for `round_orders.render_order`.

    Raises `ValueError("order-render-refused:...")` when a slot cannot be filled truthfully
    — that IS the refusal channel, and `_cmd_next_locked` catches it. Do not add a caller
    that assumes this returns on every input.
    """
    meta = _session_meta(session_dir)
    cfg = config if isinstance(config, dict) else {}
    repo_root = cfg.get("repoRoot") or meta.get("repoRoot") or os.getcwd()
    rdir = round_records.round_dir(session_dir, rnd)
    diff_path = _ensure_round_diff(session_dir, rnd, state)
    rubric_path = _shipped_rubric_path()
    core_resolved, layer_resolved, root_refusal = _resolved_calibration_paths(repo_root)
    core_path = _calibration_path_placeholder(core_resolved, "Core", root_refusal)
    layer_path = _calibration_path_placeholder(layer_resolved, "Review-crew layer",
                                              root_refusal)
    payload = pending_payload if isinstance(pending_payload, dict) else {}
    ph = {}

    if phase == P_PANEL:
        dim_label = _panel_dimension_label(seat_key)
        if not dim_label:
            raise ValueError("order-render-refused:no-dimension-label:%s" % seat_key)
        pr_checkout = _session_pr_checkout_path(session_dir)
        ph = {
            "MODE": meta.get("mode") or cfg.get("mode") or "branch",
            "REPO": meta.get("repo") or cfg.get("repo") or "unknown",
            "TARGET": meta.get("branch") or cfg.get("branch") or "unknown",
            "DIFF_PATH": diff_path,
            "RUBRIC_PATH": rubric_path,
            "CORE_PATH": core_path,
            "LAYER_PATH": layer_path,
            "PR_CHECKOUT_PATH": pr_checkout,
            "PRIOR_COMMENTS_PATH": os.path.join(session_dir, "prior-comments.json"),
            "FOCUS_NOTES": _normalize_focus_notes(meta.get("focusNotes") or cfg.get("focusNotes")),
            "DIMENSION": dim_label,
            "CHANNEL": channel,
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
        ph = {
            "CLUSTER_FINDINGS_PATH": _order_cluster_sidecar_path(rdir, cluster_index),
            "DIFF_PATH": diff_path,
            "VERIFICATION_ROOT": repo_root,
            "RUBRIC_PATH": rubric_path,
            "CHANNEL": channel,
        }
    elif phase == P_SYNTHESIS:
        ph = {
            "VERIFIED_FINDINGS_PATH": _order_verified_sidecar_path(rdir),
            "DIFF_PATH": diff_path,
            "VERIFICATION_ROOT": repo_root,
            "RUBRIC_PATH": rubric_path,
            "GROUPING_OUTPUT_PATH": os.path.join(rdir, "grouping.json"),
            "CHANNEL": channel,
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
        }
    elif phase == P_AUDITS:
        targets = payload.get("targets")
        if not isinstance(targets, list):
            targets = []
        if not any(isinstance(t, dict) and t.get("id") == seat_key for t in targets):
            raise ValueError("order-render-refused:unmatched-audit-target:%s" % seat_key)
        ph = {
            "TARGET_SUMMARY_PATH": _order_audit_target_sidecar_path(
                rdir, round_records.storage_key(seat_key, occurrence)),
            "HEAD_DIFF_PATH": os.path.join(rdir, "head.diff"),
            "VERIFICATION_ROOT": repo_root,
            "RUBRIC_PATH": rubric_path,
            "TARGET_ID": seat_key,
            "CHANNEL": channel,
        }
    elif phase == P_SCOPED:
        ph = {
            "HUNKS_PATH": _order_scoped_hunks_sidecar_path(rdir),
            "HEAD_DIFF_PATH": os.path.join(rdir, "head.diff"),
            "RUBRIC_PATH": rubric_path,
            "CORE_PATH": core_path,
            "LAYER_PATH": layer_path,
            "VERIFICATION_ROOT": repo_root,
            "FINDINGS_OUTPUT_PATH": os.path.join(rdir, "scoped-findings.json"),
            "CHANNEL": channel,
        }
    elif phase == P_FIXER:
        ph = {
            "FIX_BATCH_PATH": os.path.join(rdir, "fix-batch.json"),
            "PROFILE_PATH": _profile_path_for_orders(repo_root),
            "RUBRIC_PATH": rubric_path,
            "CWD": repo_root,
            "REPO_ROOT": _shell_quote_path(repo_root),
            "ESCALATION_WRAPPER_PATH": _shell_quote_path(_shipped_escalation_wrapper_path()),
            "VERIFY_COMMAND": cfg.get("verifyCommand") or "none",
            "ROUND": str(rnd),
        }
    return ph


def _build_order_render_context(session_dir, state, rnd, phase, attempt, seat_key, occurrence,
                                pending_payload, row):
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
    return {
        "session_dir": session_dir,
        "round": rnd,
        "attempt": attempt,
        "diff_path": _ensure_round_diff(session_dir, rnd, state),
        "rubric_path": _shipped_rubric_path(),
        "core_path": core_resolved or "",
        "layer_path": layer_resolved or "",
        "repo_root": repo_root,
        "landing_path": paths["landing_path"],
        "envelope_stub_path": paths["envelope_stub_path"],
        "ratified_residuals": residuals,
        "residuals_provenance": prov,
        "residuals_read_failure": res_failure,
        "payload": pending_payload if isinstance(pending_payload, dict) else {},
        "host_seat": host_seat,
        "placeholders": _order_placeholders(phase, seat_key, occurrence, state,
                                              cfg, pending_payload,
                                              session_dir, rnd, paths, channel),
    }, paths


def _envelope_stub_header(session_dir, rnd, phase, attempt, seat_key, occurrence, row,
                          manifest_sha, order_sha):
    """`seat-result/1` header fields knowable at emission — NOT `recordedAt` / `payloadSha256`."""
    header = {
        "schema": round_records.SEAT_RESULT_SCHEMA,
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
        return {"manifestSha256": manifest_sha, "orders": orders, "path": path}
    return None


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


def _emit_orders_manifest(session_dir, state, rnd, phase, attempt, roster, journal_cmd="advance",
                          pending_payload=None, seat_map=None):
    """Emit per-slot order prompts, envelope stubs, and the orders manifest for a dispatch phase.

    Every roster SLOT is rendered, hashed, and written inside the single `orders-emit` commit
    together with the manifest and state anchor. A render refusal for any slot refuses the whole
    emission — a phase that dispatches some seats with orders and others without is worse than one
    that refuses."""
    pending_payload = pending_payload if isinstance(pending_payload, dict) else (
        (state.get("pending") or {}).get("payload") if isinstance(state.get("pending"), dict) else {})
    seat_map = seat_map if isinstance(seat_map, dict) else _effective_seat_map(state)
    seats = {}
    order_hashes = {}
    rendered = []
    vendor_gaps = []
    for seat_key, occurrence in round_records.roster_slots(roster):
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
        if phase in _READ_ONLY_CHANNEL_PHASES and not _seat_is_engine(row):
            if not _vendor_is_resolved(row):
                vendor_gaps.append({"seat": seat_key, "storeKey": skey, "occurrence": occurrence,
                                    "phase": phase, "vendorSource": row.get("vendorSource")})
        context, paths = _build_order_render_context(session_dir, state, rnd, phase, attempt,
                                                     seat_key, occurrence, pending_payload, row)
        resource_reason = _shipped_resource_refusal(context.get("placeholders"))
        if resource_reason is not None:
            raise ValueError("order-render-refused:%s:%s" % (skey, resource_reason))
        # Order-input ownership at emission (see also round-driver.md §Emitted orders):
        #   driver commits in orders-emit: clusters/<i>.json, audit-targets/<skey>.json,
        #   scoped-hunks.json, verified.json
        #   driver writes outside orders-emit commit: diff.txt (via _ensure_round_diff when absent
        #   or untrusted — atomic tmp+rename, content-checked against state)
        #   orchestrator must supply before dispatch: diff.txt (real git diff), head.diff,
        #   fix-batch.json (skills/review-code/reference/setup.md session-artifact table).
        # STUB(#723): order-input existence class not closed — placeholder set and sidecar set
        # must derive from one source before a fail-closed guard can land here.
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
            "resultContract": round_records.SEAT_RESULT_SCHEMA,
            "orderSha256": order_sha,
            "orderPath": paths["order_path"],
            "envelopeStubPath": paths["envelope_stub_path"],
        }
        rendered.append((paths["order_path"], order_text.encode("utf-8"),
                         paths["envelope_stub_path"], order_sha, row, occurrence, seat_key))

    if vendor_gaps:
        _disclose_order_vendor_provenance_gaps(state, vendor_gaps)

    manifest = {"schema": ORDERS_MANIFEST_SCHEMA, "session": _meta_session_id(session_dir),
                "round": rnd, "phase": phase, "attempt": attempt,
                "orders": round_records.NOT_EMITTED, "seats": seats}
    path = _orders_manifest_path(session_dir, rnd, phase, attempt)
    manifest_sha = round_records.sha256_text(round_records.canonical(manifest))
    anchor = {"manifestSha256": manifest_sha, "orders": dict(order_hashes), "path": path}
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
        c.add_replace_file(os.path.join(session_dir, STATE_FILE),
                           _canonical(state).encode("utf-8"))
        c.add_replace_file(path, round_records.canonical(manifest).encode("utf-8"))
        for sidecar_path, sidecar_bytes in sidecar_writes:
            c.add_replace_file(sidecar_path, sidecar_bytes)
        for order_path, order_bytes, stub_path, order_sha, row, occurrence, seat_key in rendered:
            c.add_replace_file(order_path, order_bytes)
            # Projection of the anchor, never the authority — ingestion validates the mirrored hash.
            stub = _envelope_stub_header(session_dir, rnd, phase, attempt, seat_key, occurrence,
                                         row, manifest_sha, order_sha)
            c.add_replace_file(stub_path, round_records.canonical(stub).encode("utf-8"))
        c.add_journal_append(os.path.join(session_dir, JOURNAL_FILE), journal_entry)
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
            found.append(_slot_label(seat_key, occurrence))
    return sorted(found)


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


def _journal_record_identities(session_dir, rnd, phase):
    """Every record identity this session's journal logged for a phase — `reconcile`'s view of the
    LOG half of the two-commit window. The latest `payloadSha256` per slot rides with each identity
    so a supersede whose journal append never landed still reconciles."""
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
    """(envelope, err) for a landed seat file — full envelope or bare host payload. Never raises."""
    try:
        skey = round_records.storage_key(seat_key, occurrence)
    except ValueError as exc:
        return None, str(exc)
    envelope, refusal = round_records._read_landing_envelope(
        session_dir, rnd, phase, skey, attempt, occurrence)
    if refusal is not None:
        return None, refusal.get("reason")
    return envelope, None


def _preflight_payload_fault(phase, envelope, seat_key):
    """Adapter payload validation on a landing envelope BEFORE ingest. Returns a fault string or
    None. Only seat-result landings are checked — missing envelopes have no payload contract."""
    if not isinstance(envelope, dict):
        return None
    if envelope.get("schema") != round_records.SEAT_RESULT_SCHEMA:
        return None
    return _adapters().payload_fault(phase, envelope.get("payload"), seat_key,
                                     record_boundary=True)


def _fixer_head_diff_landing(session_dir, rnd, phase, seat_key, attempt, occurrence=0):
    """(payload, head_diff_path) for a landed `dispatch-fixer` envelope, or (None, None)."""
    try:
        lpath = round_records.landing_path(
            session_dir, rnd, phase, round_records.storage_key(seat_key, occurrence), attempt)
    except ValueError:
        return None, None
    envelope, err = round_records.read_json(lpath)
    if err is not None or not isinstance(envelope, dict):
        return None, None
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        return None, None
    return payload, payload.get("headDiffPath")


def _read_head_diff(path):
    """(content, reason). A non-absolute or unreadable `headDiffPath` is `head-diff-unreadable` —
    refused at RECORD time, not degraded at fold time. `_resolve_head_diff` would otherwise
    dereference a caller-controlled path long after the payload hash was taken, so the bytes the
    fold reads would not be the bytes the record attests."""
    if not isinstance(path, str) or not path or not os.path.isabs(path):
        return None, "head-diff-unreadable"
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read(), None
    except OSError:
        return None, "head-diff-unreadable"


def _store_head_diff(session_dir, rnd, phase, seat_key, attempt, content, occurrence=0,
                     journal_entry=None):
    """Copy the fixer's head diff into the STORE beside its envelope and stamp the immutable copy's
    path into the stored payload.

    Blob and envelope are published in one commit so a crash cannot leave them disagreeing."""
    skey = round_records.storage_key(seat_key, occurrence)
    spath = round_records.store_path(session_dir, rnd, phase, skey, attempt)
    envelope, err = round_records.read_json(spath)
    if err is not None or not isinstance(envelope, dict):
        diff_path = round_records.head_diff_store_path(session_dir, rnd, phase, seat_key, attempt,
                                                       occurrence)
        round_commit.atomic_write_bytes(diff_path, content.encode("utf-8"))
        return diff_path, None
    diff_path, diff_bytes, final, payload_sha = _envelope_with_head_diff(
        session_dir, envelope, content, rnd, phase, seat_key, attempt, occurrence)
    try:
        c = round_commit.begin(session_dir, "head-diff-bind")
        c.add_replace_file(diff_path, diff_bytes)
        c.add_replace_file(spath, round_records.canonical(final).encode("utf-8"))
        if journal_entry is not None:
            journal_entry["payloadSha256"] = payload_sha
            c.add_journal_append(os.path.join(session_dir, JOURNAL_FILE), journal_entry)
        c.run()
    except round_commit.CommitRefused as exc:
        raise exc
    return diff_path, payload_sha


def _fixer_head_diff_needs_repair(stored):
    """True when a stored fixer envelope references a head diff that is not durably copied yet."""
    if not isinstance(stored, dict):
        return False
    payload = stored.get("payload")
    if not isinstance(payload, dict):
        return False
    if payload.get("headDiffPath") is None:
        return False
    store_path_val = payload.get("headDiffStorePath")
    if not isinstance(store_path_val, str) or not store_path_val:
        return True
    return not os.path.exists(store_path_val)


def _repair_fixer_head_diff(session_dir, rnd, phase, seat_key, attempt, occurrence, cmd=None):
    """Repair a fixer store record whose head-diff blob was not yet bound.

    Returns (payload_sha, detail) where detail is None, a refusal token string, or a
    ``CommitRefused`` when the commit failed."""
    skey = round_records.storage_key(seat_key, occurrence)
    spath = round_records.store_path(session_dir, rnd, phase, skey, attempt)
    stored, err = round_records.read_json(spath)
    if err is not None or not isinstance(stored, dict):
        return None, None
    if not _fixer_head_diff_needs_repair(stored):
        return stored.get("payloadSha256"), None
    payload = stored.get("payload") if isinstance(stored.get("payload"), dict) else {}
    head_path = payload.get("headDiffPath")
    content, why = _read_head_diff(head_path)
    if why is not None:
        return None, why
    journal_entry = None
    if cmd is not None:
        journal_entry = _journal_entry_for_commit(
            session_dir, cmd, "recorded", phase=phase, round=rnd, attempt=attempt,
            seat=seat_key, occurrence=occurrence, headDiffRepaired=True,
            **_journal_identity_fields(phase, seat_key, occurrence, attempt))
    try:
        _path, payload_sha = _store_head_diff(session_dir, rnd, phase, seat_key, attempt, content,
                                              occurrence, journal_entry=journal_entry)
    except round_commit.CommitRefused as exc:
        return None, exc
    return payload_sha, None


def _pending_of(session_dir, state, cmd):
    """(phase, round, attempt, refusal) for the pending step every record/advance call works on."""
    pending = state.get("pending")
    if not isinstance(pending, dict) or not pending.get("phase"):
        return None, None, None, _refuse_cmd(session_dir, cmd, "no-pending-phase")
    return pending.get("phase"), pending.get("round"), pending.get("attempt"), None


def _roster_of(session_dir, state, cmd, phase, rnd, attempt):
    """(roster, refusal) — the phase's seat roster, from the adapter that owns the phase shape."""
    roster, reason = _adapters().roster_for(phase, state, state.get("config") or {})
    if reason is not None or not isinstance(roster, (list, tuple)):
        return None, _refuse_cmd(session_dir, cmd, "roster-unavailable", phase=phase, rnd=rnd,
                                 attempt=attempt, detail=reason)
    return [s for s in roster if isinstance(s, str)], None


def cmd_record_result(session_dir, seat=None, attempt=None, supersede=False, expect_sha256=None,
                      sweep=False, occurrence=0):
    """Ingest ONE landed seat envelope (or, with `sweep`, every unclaimed landing) into the durable
    store, and journal the outcome carrying its `payloadSha256`.

    The ingestion itself — the attempt fence, the torn-write detector, the supersede CAS, the
    manifest anchor — is `round_records`'; this layer supplies the roster (`round_adapters`), the
    emission-time anchor, the per-field payload validation, the fixer's head-diff durability, and
    the journal.

    `occurrence` addresses WHICH roster slot of a repeated seat key this envelope is (default 0 —
    the only slot a key that appears once has). Two distinct audit targets can legitimately share
    one id, so without it the second target's result is unaddressable and the first's would be
    superseded by it."""
    try:
        with round_records.session_lock(session_dir):
            sidecar_target = _sidecar_target_for_recover(session_dir)
            refusal = _commit_recover_or_refuse(session_dir, "record-result",
                                                sidecar_target=sidecar_target)
            if refusal is not None:
                return refusal
            return _cmd_record_result_locked(session_dir, seat=seat, attempt=attempt,
                                             supersede=supersede, expect_sha256=expect_sha256,
                                             sweep=sweep, occurrence=occurrence)
    except round_records.SessionLockHeld as held:
        return _lock_held_refusal(session_dir, "record-result", held)


def _cmd_record_result_locked(session_dir, seat=None, attempt=None, supersede=False,
                              expect_sha256=None, sweep=False, occurrence=0):
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
    phase, rnd, cur_attempt, refusal = _pending_of(session_dir, state, "record-result")
    if refusal is not None:
        return refusal
    if attempt is not None and attempt != cur_attempt:
        return _refuse_cmd(session_dir, "record-result", "attempt-not-pending", phase=phase,
                           rnd=rnd, attempt=attempt, pendingAttempt=cur_attempt)
    roster, refusal = _roster_of(session_dir, state, "record-result", phase, rnd, cur_attempt)
    if refusal is not None:
        return refusal
    anchor = _orders_anchor(state, session_dir, rnd, phase, cur_attempt)
    if sweep:
        return _sweep_record(session_dir, state, "record-result", phase, rnd, cur_attempt, roster,
                             anchor)

    # Validate BEFORE storing: a refusal must leave nothing behind.
    if isinstance(seat, str) and seat in roster:
        envelope, _lerr = _read_landing_envelope(session_dir, rnd, phase, seat, cur_attempt,
                                                 occurrence)
        fault = _preflight_payload_fault(phase, envelope, seat)
        if fault:
            return _refuse_cmd(session_dir, "record-result", "payload-fault", phase=phase,
                               rnd=rnd, attempt=cur_attempt, seat=seat, detail=fault)
        head_content = None
        if phase == P_FIXER:
            payload, head_path = _fixer_head_diff_landing(session_dir, rnd, phase, seat,
                                                          cur_attempt, occurrence)
            if head_path is not None:
                head_content, why = _read_head_diff(head_path)
                if why is not None:
                    return _refuse_cmd(session_dir, "record-result", why, phase=phase, rnd=rnd,
                                       attempt=cur_attempt, seat=seat, headDiffPath=head_path)
    else:
        head_content = None

    plan, landing_refusal = round_records.validate_landing(
        session_dir, rnd, phase, seat, cur_attempt, current_attempt=cur_attempt, roster=roster,
        supersede=supersede, expect_sha256=expect_sha256, anchor=anchor, occurrence=occurrence)
    if landing_refusal is not None:
        return _refuse_cmd(session_dir, "record-result", landing_refusal.get("reason"), phase=phase,
                           rnd=rnd, attempt=cur_attempt, seat=_slot_label(seat, occurrence),
                           detail=landing_refusal.get("message") or landing_refusal.get("storePath"))
    envelope = plan["envelope"]
    payload_sha = plan["payloadSha256"]
    head_store_path = None
    head_diff_bytes = None
    if head_content is not None:
        head_store_path, head_diff_bytes, envelope, payload_sha = _envelope_with_head_diff(
            session_dir, envelope, head_content, rnd, phase, seat, cur_attempt, occurrence)
    journal_entry = _journal_entry_for_commit(
        session_dir, "record-result", "recorded", phase=phase, round=rnd, attempt=cur_attempt,
        seat=seat, occurrence=occurrence, payloadSha256=payload_sha,
        superseded=bool(plan["superseded"]), headDiffStorePath=head_store_path,
        **_journal_identity_fields(phase, seat, occurrence, cur_attempt))
    try:
        c = round_commit.begin(session_dir, "record-ingest")
        c.add_replace_file(plan["storePath"], round_records.canonical(envelope).encode("utf-8"))
        if head_store_path is not None:
            c.add_replace_file(head_store_path, head_diff_bytes)
        c.add_journal_append(os.path.join(session_dir, JOURNAL_FILE), journal_entry)
        c.run()
    except round_commit.CommitRefused as exc:
        return _commit_refused_response(session_dir, "record-result", exc, phase=phase, rnd=rnd,
                                      attempt=cur_attempt, seat=_slot_label(seat, occurrence))
    return {"ok": True, "phase": phase, "round": rnd, "attempt": cur_attempt, "seat": seat,
            "occurrence": occurrence, "payloadSha256": payload_sha,
            "superseded": bool(plan["superseded"]),
            "storePath": plan["storePath"], "headDiffStorePath": head_store_path}


def _sweep_record(session_dir, state, cmd, phase, rnd, attempt, roster, anchor):
    """Ingest every unclaimed landing for the pending phase. Idempotent by construction (a seat
    already stored comes back `already-stored`); ANY refusal in the sweep refuses the whole call,
    with the refusing seat's own reason — a landing nobody could ingest is never skipped in
    silence."""
    for seat_key, occurrence in round_records.roster_slots(roster):
        if phase != P_FIXER:
            continue
        try:
            spath = round_records.store_path(session_dir, rnd, phase,
                                             round_records.storage_key(seat_key, occurrence),
                                             attempt)
        except ValueError:
            continue
        if not os.path.exists(spath):
            continue
        stored, _lerr = round_records.read_json(spath)
        if not _fixer_head_diff_needs_repair(stored):
            continue
        rehashed, detail = _repair_fixer_head_diff(session_dir, rnd, phase, seat_key, attempt,
                                                   occurrence, cmd=cmd)
        if detail == "head-diff-unreadable":
            payload = stored.get("payload") if isinstance(stored, dict) else {}
            return _refuse_cmd(session_dir, cmd, detail, phase=phase, rnd=rnd, attempt=attempt,
                               seat=seat_key, headDiffPath=payload.get("headDiffPath"))
        if isinstance(detail, round_commit.CommitRefused):
            return _commit_refused_response(session_dir, cmd, detail, phase=phase, rnd=rnd,
                                          attempt=attempt, seat=seat_key)
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
        envelope, _lerr = _read_landing_envelope(session_dir, rnd, phase, seat_key, attempt,
                                                 occurrence)
        fault = _preflight_payload_fault(phase, envelope, seat_key)
        if fault:
            return _refuse_cmd(session_dir, cmd, "payload-fault", phase=phase, rnd=rnd,
                               attempt=attempt, seat=seat_key, detail=fault)
    results = round_records.sweep_landing(session_dir, rnd, phase, current_attempt=attempt,
                                          roster=roster, anchor=anchor)
    recorded = []
    for result in results:
        occurrence = result.get("occurrence") or 0
        if not result.get("ok"):
            return _refuse_cmd(session_dir, cmd, result.get("reason"), phase=phase, rnd=rnd,
                               attempt=attempt,
                               seat=_slot_label(result.get("seatKey"), occurrence),
                               detail=result.get("message"))
        if result.get("reason") == "already-stored":
            if phase == P_FIXER:
                stored, _stored_err = round_records.read_json(result.get("storePath"))
                if _fixer_head_diff_needs_repair(stored):
                    seat = result.get("seatKey")
                    occurrence = result.get("occurrence") or 0
                    rehashed, detail = _repair_fixer_head_diff(session_dir, rnd, phase, seat,
                                                               attempt, occurrence, cmd=cmd)
                    if detail == "head-diff-unreadable":
                        payload = stored.get("payload") if isinstance(stored, dict) else {}
                        return _refuse_cmd(session_dir, cmd, detail, phase=phase, rnd=rnd,
                                           attempt=attempt, seat=seat,
                                           headDiffPath=payload.get("headDiffPath"))
                    if isinstance(detail, round_commit.CommitRefused):
                        return _commit_refused_response(session_dir, cmd, detail, phase=phase,
                                                      rnd=rnd, attempt=attempt, seat=seat)
                    if rehashed:
                        recorded.append(_slot_label(seat, occurrence))
            continue
        seat = result.get("seatKey")
        payload_sha = result.get("payloadSha256")
        stored = round_records.read_json(result.get("storePath"))[0]
        head_diff_journaled = False
        if phase == P_FIXER:
            payload = stored.get("payload") if isinstance(stored, dict) else None
            head_path = payload.get("headDiffPath") if isinstance(payload, dict) else None
            if head_path is not None and not (isinstance(payload, dict)
                                              and payload.get("headDiffStorePath")):
                content, why = _read_head_diff(head_path)
                if why is not None:
                    return _refuse_cmd(session_dir, cmd, why, phase=phase, rnd=rnd,
                                       attempt=attempt, seat=seat, headDiffPath=head_path)
                journal_entry = _journal_entry_for_commit(
                    session_dir, cmd, "recorded", phase=phase, round=rnd, attempt=attempt,
                    seat=seat, occurrence=occurrence,
                    **_journal_identity_fields(phase, seat, occurrence, attempt))
                try:
                    _unused, rehashed = _store_head_diff(session_dir, rnd, phase, seat, attempt,
                                                         content, occurrence,
                                                         journal_entry=journal_entry)
                except round_commit.CommitRefused as exc:
                    return _commit_refused_response(session_dir, cmd, exc, phase=phase, rnd=rnd,
                                                  attempt=attempt, seat=seat)
                payload_sha = rehashed or payload_sha
                head_diff_journaled = True
        if not head_diff_journaled:
            _journal_event(session_dir, cmd, "recorded", phase=phase, round=rnd, attempt=attempt,
                           seat=seat, occurrence=occurrence, payloadSha256=payload_sha,
                           **_journal_identity_fields(phase, seat, occurrence, attempt))
        recorded.append(_slot_label(seat, occurrence))
    return {"ok": True, "phase": phase, "round": rnd, "attempt": attempt, "recorded": recorded}


def cmd_record_missing(session_dir, seat, attempt, reason, evidence_path=None, occurrence=0):
    """Record a seat that produced NO artifact: the driver writes the `seat-missing/1` envelope
    itself (there is, by definition, nothing for the seat to land) and ingests it through the same
    fences as a result — roster, attempt, session, phase, round, anchor.

    `occurrence` addresses which roster slot of a repeated seat key is absent (default 0), so one
    of two audit targets sharing an id can be recorded missing WITHOUT claiming its twin is."""
    try:
        with round_records.session_lock(session_dir):
            sidecar_target = _sidecar_target_for_recover(session_dir)
            refusal = _commit_recover_or_refuse(session_dir, "record-missing",
                                                sidecar_target=sidecar_target)
            if refusal is not None:
                return refusal
            return _cmd_record_missing_locked(session_dir, seat, attempt, reason, evidence_path,
                                              occurrence=occurrence)
    except round_records.SessionLockHeld as held:
        return _lock_held_refusal(session_dir, "record-missing", held)


def _cmd_record_missing_locked(session_dir, seat, attempt, reason, evidence_path=None,
                               occurrence=0):
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
    phase, rnd, cur_attempt, refusal = _pending_of(session_dir, state, "record-missing")
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
    if not isinstance(seat, str) or seat not in roster:
        # Let the ingest layer own the enumerated `unknown-seat` refusal rather than respelling it.
        out = round_records.ingest_landing(session_dir, rnd, phase, seat, cur_attempt,
                                           current_attempt=cur_attempt, roster=roster)
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
    pending = ((state.get("pending") or {}).get("payload")
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
                                       occurrence=occurrence)
    if not out.get("ok"):
        return _refuse_cmd(session_dir, "record-missing", out.get("reason"), phase=phase, rnd=rnd,
                           attempt=cur_attempt, seat=_slot_label(seat, occurrence),
                           detail=out.get("message") or out.get("storePath"))
    _journal_event(session_dir, "record-missing", "recorded", phase=phase, round=rnd,
                   attempt=cur_attempt, seat=seat, occurrence=occurrence, reason=reason,
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
    if break_lock:
        holder = round_records.break_lock(session_dir) or {}
        broke = {"pid": holder.get("pid"), "createdAt": holder.get("createdAt")}
        _journal_event(session_dir, "advance", "lock-broken", fault=FAULT_CALLER, holder=broke)
    try:
        with round_records.session_lock(session_dir):
            sidecar_target = _sidecar_target_for_recover(session_dir, git=git)
            refusal = _commit_recover_or_refuse(session_dir, "advance",
                                                sidecar_target=sidecar_target)
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


def _gate_policy_repo_root(config):
    if isinstance(config, dict):
        repo_root = config.get("repoRoot")
        if isinstance(repo_root, str) and repo_root.strip():
            return repo_root
    return os.getcwd()


def _gate_policy_overlay_from_config(config):
    """Read the calibration overlay through core.md — never from caller-supplied advance flags."""
    repo_root = _gate_policy_repo_root(config)
    return core_md.review_gate_policy_for_gate(cwd=repo_root)


def _judgment_policy_rows(state):
    judgment = [f for f in (state.get("_judgmentFindings") or []) if isinstance(f, dict)]
    row_ids = _judgment_row_ids(judgment)
    rows = []
    for i, finding in enumerate(judgment):
        severity = finding.get("severity")
        finding_class = "judgment:%s" % (severity.lower() if isinstance(severity, str) else "")
        rows.append({
            "id": row_ids[i],
            "findingClass": finding_class,
            "severity": severity,
            "title": finding.get("title"),
            "file": finding.get("file"),
            "line": finding.get("line"),
        })
    return rows


def _stall_policy_class(state):
    """The stall class gate policy resolves against — from the PERSISTED stall-target snapshot.

    Same source as the submit chokepoint and the fold, so the policy that picks a resolution can
    never classify a state as accept-risk-eligible that the fold will then refuse."""
    if _stall_targets_accept_risk_eligible(state):
        return review_gate_policy.STALL_CLASS_ELIGIBLE
    return review_gate_policy.STALL_CLASS_INELIGIBLE


def _judgment_artifact_from_resolution(state, resolution):
    judgment = [f for f in (state.get("_judgmentFindings") or []) if isinstance(f, dict)]
    dispositions = []
    for match in resolution.get("matches") or []:
        if not isinstance(match, dict):
            continue
        row_index = match.get("rowIndex")
        if not isinstance(row_index, int) or row_index < 0 or row_index >= len(judgment):
            continue
        finding = judgment[row_index]
        rule = match.get("rule") if isinstance(match.get("rule"), dict) else {}
        disposition = rule.get("disposition")
        row_ids = _judgment_row_ids(judgment)
        entry = {"id": row_ids[row_index], "disposition": disposition}
        if disposition == review_gate_policy.JUDGMENT_SKIP_DISPOSITION:
            entry["reason"] = _GATE_POLICY_SKIP_REASON
        dispositions.append(entry)
    return {"dispositions": dispositions}


def _policy_applied_record(phase, resolution):
    layers = []
    for layer in resolution.get("layers") or []:
        ident = layer.get("identity") if isinstance(layer, dict) else None
        if isinstance(ident, dict):
            layers.append({"source": ident.get("source"), "schema": ident.get("schema"),
                           "sha256": ident.get("sha256")})
    action = resolution.get("action")
    if isinstance(action, dict):
        action = dict(action)
    return {"phase": phase, "layers": layers, "matches": list(resolution.get("matches") or []),
            "action": action}


def _gate_policy_layer_archive_tag(identity):
    source = identity.get("source") if isinstance(identity, dict) else ""
    if not isinstance(source, str):
        source = ""
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def _commit_gate_policy_archive(session_dir, rnd, resolution):
    """Archive each used layer's normalized rules under round-<N>/gate-policy.<tag>.json."""
    try:
        c = round_commit.begin(session_dir, "gate-policy-archive")
        for layer in resolution.get("layers") or []:
            if not isinstance(layer, dict) or not layer.get("used"):
                continue
            ident = layer.get("identity")
            if not isinstance(ident, dict):
                continue
            tag = _gate_policy_layer_archive_tag(ident)
            rel = os.path.join("round-%d" % rnd, "gate-policy.%s.json" % tag)
            archive = {"identity": dict(ident),
                       "normalizedRules": [dict(rule) for rule in (layer.get("normalizedRules")
                                                                   or []) if isinstance(rule, dict)]}
            c.add_replace_file(os.path.join(session_dir, rel),
                               _canonical(archive).encode("utf-8"))
        c.run()
    except round_commit.CommitRefused as exc:
        return exc
    return None


GATE_POLICY_CALIBRATION_PARK_CAUSE_UNREADABLE = "gate-policy-calibration-unreadable"
GATE_POLICY_CALIBRATION_PARK_CAUSE_ABSENT = "gate-policy-calibration-absent"
GATE_POLICY_CALIBRATION_PARK_CAUSE_REFUSED = "gate-policy-calibration-refused"
GATE_POLICY_CALIBRATION_PARK_CAUSE_STRUCTURAL = "gate-policy-calibration-structurally-ambiguous"

GATE_POLICY_JUDGMENT_NO_FINDINGS_PARK_CAUSE = "gate-policy-judgment-no-findings"
GATE_POLICY_UNKNOWN_PHASE_PARK_CAUSE = "gate-policy-unknown-phase"
GATE_POLICY_PARK_CAUSE = "gate-policy-park"

GATE_POLICY_RESOLVER_PARK_CAUSES = frozenset({
    GATE_POLICY_JUDGMENT_NO_FINDINGS_PARK_CAUSE,
    GATE_POLICY_UNKNOWN_PHASE_PARK_CAUSE,
    GATE_POLICY_PARK_CAUSE,
}) | review_gate_policy.RESOLVER_PARK_CAUSES

GATE_POLICY_UNMATCHED_CLASS_PREFIX = "gate-policy-unmatched-class:"


def owner_gate_policy_park_detail_causes():
    """Exact park-detail cause tokens ``advance`` may emit on owner gates (no parameterized suffixes)."""
    causes = set(GATE_POLICY_RESOLVER_PARK_CAUSES)
    causes.add(GATE_POLICY_CALIBRATION_PARK_CAUSE_UNREADABLE)
    causes.add(GATE_POLICY_CALIBRATION_PARK_CAUSE_ABSENT)
    causes.add(GATE_POLICY_CALIBRATION_PARK_CAUSE_REFUSED)
    causes.add(GATE_POLICY_CALIBRATION_PARK_CAUSE_STRUCTURAL)
    causes.add(core_md.GATE_REASON_ROOT_UNAVAILABLE)
    return frozenset(causes)


def _gate_policy_calibration_park_detail(gate):
    """Distinct park cause when core.md gate classification refuses overlay read."""
    if core_md.review_gate_config_is_policy_ambiguous(gate):
        return gate.detail or GATE_POLICY_CALIBRATION_PARK_CAUSE_REFUSED
    if core_md.review_gate_config_is_structurally_ambiguous(gate):
        detail = GATE_POLICY_CALIBRATION_PARK_CAUSE_STRUCTURAL
        if gate.detail:
            detail = "%s: %s" % (detail, gate.detail)
        return detail
    if core_md.review_gate_config_is_unreadable(gate):
        detail = GATE_POLICY_CALIBRATION_PARK_CAUSE_UNREADABLE
        if gate.detail:
            detail = "%s: %s" % (detail, gate.detail)
        return detail
    if core_md.review_gate_config_is_absent(gate):
        return GATE_POLICY_CALIBRATION_PARK_CAUSE_ABSENT
    if core_md.review_gate_config_is_refusal(gate):
        try:
            reason = core_md.gate_refusal_reason_for_status(gate.status)
        except KeyError:
            reason = GATE_POLICY_CALIBRATION_PARK_CAUSE_REFUSED
        if gate.detail:
            return "%s: %s" % (reason, gate.detail)
        return reason
    return GATE_POLICY_CALIBRATION_PARK_CAUSE_REFUSED


def _resolve_owner_gate_policy(phase, state, config):
    """Resolve judgment/stall gate policy.

    Returns ``{"authorized": True, ...}`` when policy authorizes advance, else
    ``{"authorized": False, "parkDetail": "<cause>"}`` so advance can park with a
    distinguishable refusal detail while keeping the top-level park reason."""
    gate = _gate_policy_overlay_from_config(config)
    if (core_md.review_gate_config_is_policy_ambiguous(gate)
            or core_md.review_gate_config_is_structurally_ambiguous(gate)
            or core_md.review_gate_config_is_unreadable(gate)
            or core_md.review_gate_config_is_absent(gate)
            or core_md.review_gate_config_is_refusal(gate)):
        return {"authorized": False, "parkDetail": _gate_policy_calibration_park_detail(gate)}
    overlay = gate.overlay
    if phase == P_JUDGMENT:
        rows = _judgment_policy_rows(state)
        if not rows:
            return {"authorized": False,
                    "parkDetail": GATE_POLICY_JUDGMENT_NO_FINDINGS_PARK_CAUSE}
        resolution = review_gate_policy.resolve_judgment(rows, overlay)
    elif phase == P_STALL:
        resolution = review_gate_policy.resolve_stall(_stall_policy_class(state), overlay)
    else:
        return {"authorized": False, "parkDetail": GATE_POLICY_UNKNOWN_PHASE_PARK_CAUSE}
    if resolution.get("action") == review_gate_policy.PARK:
        return {"authorized": False,
                "parkDetail": resolution.get("reason") or GATE_POLICY_PARK_CAUSE}
    if phase == P_JUDGMENT:
        artifact = _judgment_artifact_from_resolution(state, resolution)
    else:
        artifact = dict(resolution.get("action") or {})
    return {"authorized": True, "artifact": artifact,
            "policyApplied": _policy_applied_record(phase, resolution),
            "resolution": resolution}


def _advance_owner_gate(session_dir, state, phase, rnd, attempt, config, git=None, broke=None):
    """Fold an owner gate through cmd_submit when calibration pre-authorizes it."""
    resolved = _resolve_owner_gate_policy(phase, state, config)
    park_reason = "advance-judgment-park" if phase == P_JUDGMENT else "advance-stall-park"
    if not resolved.get("authorized"):
        return _refuse_cmd(session_dir, "advance", park_reason, phase=phase, rnd=rnd,
                           attempt=attempt, detail=resolved.get("parkDetail"))
    archive_refused = _commit_gate_policy_archive(session_dir, rnd, resolved["resolution"])
    if archive_refused is not None:
        return _commit_refused_response(session_dir, "advance", archive_refused, phase=phase,
                                        rnd=rnd, attempt=attempt)
    folded = cmd_submit(session_dir, phase, attempt, state_hash(state), resolved["artifact"],
                        _via_advance=True,
                        _pending_policy_applied=resolved["policyApplied"])
    if not folded.get("ok"):
        return _refuse_cmd(session_dir, "advance", "fold-refused", phase=phase, rnd=rnd,
                           attempt=attempt, detail=folded.get("reason"))
    ok_folded, state = load_state(session_dir)
    if not ok_folded or state is None:
        reason, fault, detail = _state_load_fault(session_dir)
        return _refuse_cmd(session_dir, "advance", reason, fault=fault, detail=detail)
    journal_entry = _journal_entry_for_commit(session_dir, "advance", "advanced",
                                              phase=phase, round=rnd, attempt=attempt,
                                              policyApplied=resolved["policyApplied"])
    try:
        c = round_commit.begin(session_dir, "advance-policy-applied")
        c.add_replace_file(os.path.join(session_dir, STATE_FILE),
                           _canonical(state).encode("utf-8"))
        c.add_journal_append(os.path.join(session_dir, JOURNAL_FILE), journal_entry)
        c.run()
    except round_commit.CommitRefused as exc:
        return _commit_refused_response(session_dir, "advance", exc, phase=phase,
                                        rnd=rnd, attempt=attempt)
    nxt = cmd_next(session_dir)
    if not nxt.get("ok"):
        return nxt
    ok_after, after = load_state(session_dir)
    if not ok_after or after is None:
        reason, fault, detail = _state_load_fault(session_dir)
        return _refuse_cmd(session_dir, "advance", reason, fault=fault, detail=detail)
    response = {"ok": True, "folded": {"phase": phase, "round": rnd, "attempt": attempt},
                "nextAction": nxt, "brokeLock": broke, "policyApplied": resolved["policyApplied"]}
    if after.get("terminal"):
        side = _publish_sidecar(session_dir, after, git=git)
        if side.get("reason"):
            return _refuse_cmd(session_dir, "advance", side["reason"], fault=FAULT_INTERNAL,
                               detail=side.get("detail"))
        response["terminal"] = after.get("terminal")
        response["sidecar"] = side.get("path")
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
    return {
        "schema": round_records.SEAT_RESULT_SCHEMA,
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
    record = {
        "storePath": record_path,
        "envelope": envelope,
        "journal": _journal_entry_for_commit(
            session_dir, "advance", "recorded", phase=phase, round=rnd, attempt=attempt,
            seat=seat_key, occurrence=occurrence,
            payloadSha256=envelope["payloadSha256"], superseded=False,
            **_journal_identity_fields(phase, seat_key, occurrence, attempt)),
    }
    folded = cmd_submit(session_dir, phase, attempt, state_hash(state), payload,
                        _via_advance=True, _durable_record=record)
    if not folded.get("ok"):
        return _refuse_cmd(session_dir, "advance", "fold-refused", phase=phase, rnd=rnd,
                           attempt=attempt, detail=folded.get("reason"))
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
    if phase == P_JUDGMENT or phase == P_STALL:
        return _advance_owner_gate(session_dir, state, phase, rnd, attempt, config, git=git,
                                   broke=broke)
    if _adapters().is_orchestrator_fulfilled(phase):
        orch = _advance_orchestrator_fulfilled_locked(session_dir, state, phase, rnd, attempt,
                                                      config, git=git, broke=broke)
        if orch is not _ORCHESTRATOR_FULFILLED_USE_SEAT_PATH:
            return orch
    roster, refusal = _roster_of(session_dir, state, "advance", phase, rnd, attempt)
    if refusal is not None:
        return refusal
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
        _journal_event(session_dir, "advance", "recorded", phase=phase, round=rnd,
                       attempt=entry.get("attempt"), seat=slot[0] if slot else None,
                       occurrence=slot[1] if slot else None,
                       payloadSha256=entry.get("payloadSha256"), reappended=True,
                       recordIdentity=ident)
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
    artifact, why = _adapters().assemble(phase, records, state, config,
                                         dispatch_manifest=manifest if _merr is None else None,
                                         canary=_canary_landings(session_dir, state, rnd, attempt),
                                         session_dir=session_dir)
    if why is not None or not isinstance(artifact, dict):
        return _attach_dispatch_manifest_disclosure(
            session_dir,
            _refuse_cmd(session_dir, "advance", "assemble-refused", phase=phase, rnd=rnd,
                        attempt=attempt, detail=why),
            rnd, phase, attempt, manifest_disc)

    artifact_for_fold = dict(artifact)

    # 5. fold through the EXISTING submit chokepoint (see `cmd_submit`).
    folded = cmd_submit(session_dir, phase, attempt, state_hash(state), artifact_for_fold,
                        _via_advance=True)
    if not folded.get("ok"):
        return _attach_dispatch_manifest_disclosure(
            session_dir,
            _refuse_cmd(session_dir, "advance", "fold-refused", phase=phase, rnd=rnd,
                        attempt=attempt, detail=folded.get("reason")),
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


def _canary_landings(session_dir, state, rnd, attempt):
    """The per-vendor control-probe landings for the panel phase, or None. Read-only.

    Returns a LIST of probe objects — the shape `round_adapters._normalize_canary` consumes — not a
    vendor-keyed map."""
    probes = []
    for vendor in _live_vendors(state.get("config") or {}):
        try:
            path = round_records.canary_path(session_dir, rnd, vendor, attempt)
        except ValueError:
            continue
        obj, err = round_records.read_json(path)
        if err is None and isinstance(obj, dict):
            probes.append(obj)
    return probes or None


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
    bootstrap-required, premature advance, lock refusal, CAS refusal, judgment/stall park) is
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
    `loop-state.json` are excluded from the digest set — same contract class as STATE_FILE. The
    receipt file itself is excluded because it is written last and cannot hash itself. `roster` may be supplied when `state` is
    already terminal (pending cleared) but was captured from the failure phase beforehand."""
    receipt = build_receipt(state, session_dir)
    for key in ("certification", "certificationShape", "schemaVersion"):
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
    if not isinstance(note, str) or not note.strip():
        return _refuse_cmd(session_dir, "attest", "attest-note-required")
    try:
        with round_records.session_lock(session_dir):
            sidecar_target = _sidecar_target_for_recover(session_dir, git=git)
            refusal = _commit_recover_or_refuse(session_dir, "attest",
                                                sidecar_target=sidecar_target)
            if refusal is not None:
                return refusal
            state, refusal = _load_driver_state(session_dir, "attest")
            if refusal is not None:
                return refusal
            if os.path.exists(os.path.join(session_dir, RECEIPT_FILE)) or state.get("terminal"):
                return _refuse_cmd(session_dir, "attest", "terminal-receipt-exists")
            binding, why = _resolve_failure_ref(session_dir, failure_ref)
            if why is not None:
                return _refuse_cmd(session_dir, "attest", why, detail=str(failure_ref))
            artifact_snapshot = _session_artifact_hashes(session_dir,
                                                         exclude=(RECEIPT_FILE, STATE_FILE,
                                                                  JOURNAL_FILE,
                                                                  round_records.LOCK_FILE))
            return _cmd_attest_locked(session_dir, failure_ref, note, git=git, state=state,
                                    binding=binding, artifact_snapshot=artifact_snapshot)
    except round_records.SessionLockHeld as held:
        return _lock_held_refusal(session_dir, "attest", held)


def _cmd_attest_locked(session_dir, failure_ref, note, git=None, state=None, binding=None,
                       artifact_snapshot=None):
    roster = _attest_roster(session_dir, state)
    state["terminal"] = ATTESTED_VERDICT
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
        c.add_replace_file(os.path.join(session_dir, STATE_FILE),
                           _canonical(state).encode("utf-8"))
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
    cli_contract.add_argument(pn, "--fixer-vendor", contract="free-text", default=None,
                              help="the ACTUAL fix-implementer vendor (fresh state only): the "
                                   "auditor is seated as a DIFFERENT vendor, so a wrong value "
                                   "labels a self-audit independent. Unknown vendor / on non-fresh "
                                   "state → fails loud (nonzero), never a silent default")
    cli_contract.add_argument(pn, "--verify-command", contract="free-text", default=None)
    cli_contract.add_argument(pn, "--max-rounds", contract="integer", default=None, type=int)
    cli_contract.add_argument(pn, "--max-rounds-absolute", contract="integer", default=None,
                              type=int,
                              help="hard round ceiling (fresh state only): owner-tunable like "
                                   "--max-rounds; an effective ceiling below maxRounds refuses "
                                   "at load")
    cli_contract.add_argument(pn, "--diff-path", contract="free-text", default=None,
                              help="round-1 reviewed diff (fresh state only)")
    cli_contract.add_argument(pn, "--repo-root", contract="repo-root", default=None,
                              help="repo root the base guard resolves the pinned base against "
                                   "(default: cwd)")
    cli_contract.add_argument(pn, "--prior-comments", contract="free-text", default=None,
                              help="PR-mode prior review comments JSON (a list) for the "
                                   "author-justification post-filter (fresh state only)")
    cli_contract.add_argument(pn, "--seat-map", contract="free-text", default=None,
                              help="the #510 seat map JSON object (fresh state only) seeding "
                                   "config/state so round 1 has a vendor source. Unparseable / "
                                   "non-object / on non-fresh state → fails loud (nonzero), never "
                                   "a silent default")

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

    pa = sub.add_parser("advance")
    cli_contract.add_argument(pa, "--session-dir", contract="existing-directory", required=True)
    cli_contract.add_argument(pa, "--break-lock", contract="boolean-flag")

    pt = sub.add_parser("attest")
    cli_contract.add_argument(pt, "--session-dir", contract="existing-directory", required=True)
    cli_contract.add_argument(pt, "--failure", contract="free-text", required=True,
                              help="a journal sequence number, or marker:<entryHash> for a "
                                   "journal-degraded fault marker. There is NO issue reference — "
                                   "eligibility is allowlist-only")
    cli_contract.add_argument(pt, "--note", contract="free-text", required=True)
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


def _dispatch(args):
    if args.cmd == "next":
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
        if args.fixer_vendor is not None:
            # The fixer vendor is read ONCE at new_state and drives the independent-auditor seating —
            # an unknown vendor or a later `next` on existing state that silently ignored it would
            # mislabel a self-audit independent. Reject loudly, same discipline as `--vendors` (#507).
            fixer = args.fixer_vendor.strip()
            if fixer not in model_registry.VENDORS:
                sys.stdout.write(json.dumps({"ok": False, "reason": "fixer-vendor-unknown",
                                             "value": args.fixer_vendor}) + "\n")
                return 1
            st_ok, st = load_state(args.session_dir)
            if not (st_ok and st is None):
                sys.stdout.write(json.dumps({"ok": False, "reason": "fixer-vendor-not-fresh-state",
                                             "value": args.fixer_vendor}) + "\n")
                return 1
            overrides["fixerVendor"] = fixer
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
        if args.verify_command is not None:
            overrides["verifyCommand"] = args.verify_command
        if args.max_rounds is not None:
            overrides["maxRounds"] = args.max_rounds
        if args.max_rounds_absolute is not None:
            st_ok, st = load_state(args.session_dir)
            if not (st_ok and st is None):
                sys.stdout.write(json.dumps({"ok": False,
                                             "reason": "max-rounds-absolute-not-fresh-state",
                                             "value": args.max_rounds_absolute}) + "\n")
                return 1
            overrides["maxRoundsAbsolute"] = args.max_rounds_absolute
            try:
                _default_config(dict(overrides))
            except RoundCeilingRefusal as refusal:
                sys.stdout.write(json.dumps({"ok": False, "reason": refusal.reason,
                                             "value": args.max_rounds_absolute}) + "\n")
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
        # A v1 state file must surface refused-v1 from cmd_next — do not mask it with a base refusal.
        if args.prior_comments:
            # Load + validate the PR-mode prior comments into `priorComments` so the
            # author-justification post-filter is actually reachable (#507 v7). A missing / unreadable
            # / non-list file leaves priorComments unset (the filter simply does not fire) — never a
            # crash and never a silent drop.
            try:
                with open(args.prior_comments, encoding="utf-8") as fh:
                    loaded = json.load(fh)
                if isinstance(loaded, list):
                    overrides["priorComments"] = loaded
            except (OSError, ValueError):
                pass
        out = cmd_next(args.session_dir, overrides or None)
    elif args.cmd == "record-result":
        out = cmd_record_result(args.session_dir, args.seat, attempt=args.attempt,
                                supersede=args.supersede, expect_sha256=args.expect_sha256,
                                sweep=args.sweep, occurrence=args.occurrence)
    elif args.cmd == "record-missing":
        out = cmd_record_missing(args.session_dir, args.seat, args.attempt, args.reason,
                                 evidence_path=args.evidence, occurrence=args.occurrence)
    elif args.cmd == "advance":
        out = cmd_advance(args.session_dir, break_lock=args.break_lock)
    elif args.cmd == "attest":
        out = cmd_attest(args.session_dir, args.failure, args.note)
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
    return 1 if out.get("reason") == "receipt-fault" else 0


if __name__ == "__main__":
    sys.exit(main())
