#!/usr/bin/env python3
"""Durable per-seat record layer for the review round driver (#723).

CONTRACT. This is the storage seam BETWEEN an orchestrator dispatch and the round driver's
state machine: a dispatched seat lands its envelope as a file (the LANDING area, written by the
host), and this module INGESTS that landing into the durable per-seat STORE — fail-closed at
every edge, atomically, with a torn-write detector, an attempt fence, a compare-and-swap for
supersede, and a two-commit reconcile that treats the STORE FILE as authoritative and the
journal as the log.

It deliberately does NOT import `round_driver` — round_driver imports THIS module, so the
dependency runs one way only. Two consequences the reader must know:

  - the phase strings (`round_driver.P_*`) are plain arguments here; this module validates them
    structurally (non-empty, path-safe) and never against the driver's phase vocabulary. The one
    literal it must spell for itself is the panel phase directory name used by `canary_path`
    (`_PANEL_PHASE_DIRNAME`), whose single source of truth is `round_driver.P_PANEL`; a drift
    guard for that pair belongs in the layer that can import both.
  - the canonical-JSON form and the sha256 helper are respelled here with the SAME shape
    round_driver uses (`sort_keys=True, separators=(",", ":"), ensure_ascii=True`), because
    importing them would be the cycle.

Like its decider siblings: DETERMINISTIC, stdlib-only, FAIL-CLOSED. `ingest_landing` NEVER
raises on bad input — it returns a refusal dict whose `reason` string IS the contract.
"""
import contextlib
import datetime
import errno
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import model_registry  # noqa: E402
import round_phases  # noqa: E402

# =============================================================================================
# schema constants
# =============================================================================================

SEAT_RESULT_SCHEMA = "seat-result/1"
SEAT_MISSING_SCHEMA = "seat-missing/1"
SIDECAR_SCHEMA = "handback-sidecar/1"

# The seat-result envelope's declared fields. `payload` carries the seat's artifact; the store
# copy is verified against `payloadSha256` at ingestion (the torn-write detector).
SEAT_RESULT_FIELDS = ("schema", "session", "round", "phase", "seat", "attempt", "vendor",
                      "model", "dispatchRef", "orderSha256", "manifestSha256", "recordedAt",
                      "payloadSha256", "payload")
# A seat-missing envelope records a seat that produced NO artifact. Same envelope minus the
# payload pair, plus a `reason` from MISSING_REASONS and an optional free-text `evidence`.
SEAT_MISSING_FIELDS = ("schema", "session", "round", "phase", "seat", "attempt", "vendor",
                       "model", "dispatchRef", "orderSha256", "manifestSha256", "recordedAt",
                       "reason", "evidence")
MISSING_REASONS = ("forfeit", "timeout", "refusal", "killed", "malformed-output")

SIDECAR_FIELDS = ("schema", "repoId", "branch", "headSha", "baseRef", "baseSha", "diffSha256",
                  "verdict", "certificationShape", "receiptPath", "receiptSha256",
                  "policySha256", "sessionDir")

# An envelope emitted before order-prompt files exist carries this literal in place of the
# order/manifest hashes. It is accepted ONLY when there is no emission-time anchor to check it
# against; an envelope claiming REAL hashes with no anchor is `manifest-anchor-unanchored`.
NOT_EMITTED = "not-emitted"

META_FILE = "meta.json"
LOCK_FILE = "session.lock"
# Orchestrator-written files live in the `_` namespace inside the landing area; a seat key may
# therefore never begin with `_` (`storage_key` refuses one).
RESERVED_PREFIX = "_"
DISPATCH_MANIFEST_STEM = "_dispatch"
CANARY_DIRNAME = "_canary"
# The panel phase directory name — imported from the shared phase constants module.
_PANEL_PHASE_DIRNAME = round_phases.P_PANEL

# Compare-and-swap token for a stored `seat-missing/1` envelope. It is NOT a payload hash (those
# are 64-char hex); a caller cannot satisfy `cas-mismatch` by guessing a real seat-result hash.
MISSING_CAS_TOKEN = SEAT_MISSING_SCHEMA

# Directory fsync is a no-op (or unsupported) on some exotic/remote filesystems; only these
# errnos are swallowed. Anything else propagates — a durability failure must not go quiet.
_FSYNC_DIR_TOLERATED = (errno.EINVAL, errno.ENOTSUP, errno.EPERM)

_SLUG_MAX = 40
_SHA_PREFIX = 16
_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_NON_SLUG = re.compile(r"[^a-z0-9]+")


# =============================================================================================
# canonical json + hashing (same shape as round_driver._canonical/_sha256 — see module docstring)
# =============================================================================================

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def payload_sha256(payload):
    """The hash the torn-write detector compares against: sha256 over the payload's canonical
    JSON, so a re-serialization with different key order or spacing still matches."""
    return sha256_text(canonical(payload))


def envelope_cas_token(envelope):
    """The compare-and-swap token for a stored envelope — payload hash for results, a fixed schema
    literal for seat-missing (which carries no payloadSha256)."""
    if not isinstance(envelope, dict):
        return None
    schema = envelope.get("schema")
    if schema == SEAT_RESULT_SCHEMA:
        return envelope.get("payloadSha256")
    if schema == SEAT_MISSING_SCHEMA:
        return MISSING_CAS_TOKEN
    return None


def record_identity(phase, seat, occurrence, attempt):
    """The durable identity of one per-seat store record — the join key for reconcile."""
    return {"phase": phase, "seat": seat, "occurrence": occurrence, "attempt": attempt}


def _identity_key(phase, seat, occurrence, attempt):
    return (phase, seat, occurrence, attempt)


def _identity_key_from_mapping(ident, default_phase=None):
    if not isinstance(ident, dict):
        return None
    seat = ident.get("seat")
    if not isinstance(seat, str) or not seat:
        return None
    occurrence = ident.get("occurrence", 0)
    if isinstance(occurrence, bool) or not isinstance(occurrence, int) or occurrence < 0:
        return None
    attempt = ident.get("attempt")
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 0:
        return None
    phase = ident.get("phase", default_phase)
    if not isinstance(phase, str) or not phase:
        return None
    return _identity_key(phase, seat, occurrence, attempt)


def head_diff_store_path(session_dir, rnd, phase, seat_key, attempt, occurrence=0):
    """The driver-owned headdiff blob path for one roster slot."""
    skey = storage_key(seat_key, occurrence)
    spath = store_path(session_dir, rnd, phase, skey, attempt)
    return os.path.join(os.path.dirname(spath), "%s.a%d.headdiff" % (skey, attempt))


def head_diff_store_path_valid(store_path_value, session_dir, rnd, phase, seat_key, attempt,
                               occurrence=0):
    """True when `store_path_value` is exactly this session's store copy for the slot."""
    if not isinstance(store_path_value, str) or not store_path_value:
        return False
    if not isinstance(session_dir, str) or not session_dir:
        return False
    try:
        expected = head_diff_store_path(session_dir, rnd, phase, seat_key, attempt, occurrence)
    except ValueError:
        return False
    return os.path.normpath(store_path_value) == os.path.normpath(expected)


def _now_iso():
    return datetime.datetime.now().replace(microsecond=0).isoformat()


# =============================================================================================
# storage keys — roster keys are NOT safe filenames
# =============================================================================================

def storage_key(seat_key, occurrence=0):
    """Map a roster seat key onto a filename-safe, collision-resistant storage key.

    Roster keys are not filenames: a verifier cluster key is `src/a/b.py:3` and an audit target
    id is `src/a/b.py::some-title@L5` (or `...#1` when occurrence-suffixed) — both carry `/` and
    `:`, and two DISTINCT audit targets can legitimately share one roster seat key (hence
    `occurrence`). The key is `<slug>-<sha16>`: the slug is for
    a human reading `ls`, the sha16 is what actually carries identity, so two seat keys that
    collapse onto the same truncated slug still get different keys.

    Fail-closed: a non-`str`/empty `seat_key` and a `_`-prefixed one (the reserved orchestrator
    namespace) raise `ValueError`; a `seat_key` whose slug normalizes away entirely falls back
    to `seat-<sha16>` rather than an empty or `-`-only name; a non-int / negative `occurrence`
    raises `ValueError`. The result always matches `^[a-z0-9][a-z0-9-]*$`, so it can carry
    neither a path separator nor `..` nor a leading `_`.
    """
    if not isinstance(seat_key, str) or not seat_key:
        raise ValueError("seat_key must be a non-empty str, got %r" % (seat_key,))
    if seat_key.startswith(RESERVED_PREFIX):
        raise ValueError("seat_key may not start with %r (reserved namespace): %r"
                         % (RESERVED_PREFIX, seat_key))
    if isinstance(occurrence, bool) or not isinstance(occurrence, int) or occurrence < 0:
        raise ValueError("occurrence must be a non-negative int, got %r" % (occurrence,))
    digest = sha256_text(seat_key)[:_SHA_PREFIX]
    slug = _NON_SLUG.sub("-", seat_key.lower()).strip("-")[:_SLUG_MAX].strip("-")
    key = ("%s-%s" % (slug, digest)) if slug else ("seat-%s" % digest)
    if occurrence:
        key = "%s-o%d" % (key, occurrence)
    if not _KEY_RE.match(key):
        # Belt-and-braces: the slug path above cannot produce this, but a key that failed the
        # shape is never returned — fall back to the hash-only form.
        key = "seat-%s" % digest
        if occurrence:
            key = "%s-o%d" % (key, occurrence)
    return key


def roster_slots(roster):
    """[(seat_key, occurrence)] — a roster expanded so a REPEATED key stays addressable.

    THE SINGLE HOME for the slot expansion, so no layer above invents a second one. Identity on
    every layer that consumes a roster is (seat_key, occurrence), never the seat key alone: two
    DISTINCT audit targets can legitimately share one roster seat key (same per-location id before
    occurrence suffixing), so a roster carrying the same key twice describes TWO real seats. `storage_key` already gives each
    its own file; this gives every caller the same enumeration of them.

    Order is preserved, never sorted — it is SEMANTIC on the multi-seat phases (the panel folds in
    dimension order; the audits artifact lists results in target order). A non-sequence roster
    expands to no slots rather than raising: the callers all fail closed on an empty roster.
    """
    seen = {}
    slots = []
    for key in roster if isinstance(roster, (list, tuple)) else []:
        occurrence = seen.get(key, 0)
        seen[key] = occurrence + 1
        slots.append((key, occurrence))
    return slots


# =============================================================================================
# paths — every builder is fenced inside the session dir
# =============================================================================================

def _require_token(name, value):
    """A path component supplied by a caller: non-empty str, no separator, no `..`, no NUL."""
    if not isinstance(value, str) or not value:
        raise ValueError("%s must be a non-empty str, got %r" % (name, value))
    if value in (".", "..") or "/" in value or "\\" in value or "\x00" in value:
        raise ValueError("%s is not a safe path component: %r" % (name, value))
    return value


def _require_index(name, value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("%s must be a non-negative int, got %r" % (name, value))
    return value


def _guard_within(session_dir, path):
    """Refuse a built path that escapes the session dir.

    Containment is decided on `realpath` of the candidate — a symlink component that resolves
    outside the session dir must refuse even when the unresolved `abspath` sits lexically under the
    session root. The session root itself is `realpath(session_dir)` so a caller's spelling of the
    session prefix (macOS `/tmp` vs `/private/tmp`) does not false-refuse legitimate joins. The
    RETURNED path is the un-resolved join, so a caller's paths stay in the spelling it handed in."""
    if not isinstance(session_dir, str) or not session_dir:
        raise ValueError("session_dir must be a non-empty str, got %r" % (session_dir,))
    root = os.path.realpath(session_dir)
    candidate = os.path.abspath(path)
    resolved = os.path.realpath(candidate)
    try:
        common = os.path.commonpath([root, resolved])
    except ValueError:  # different drives / mixed absolute-relative
        raise ValueError("path escapes the session dir: %r" % (path,))
    if common != root or resolved == root:
        raise ValueError("path escapes the session dir: %r" % (path,))
    return path


def round_dir(session_dir, rnd):
    _require_index("rnd", rnd)
    return _guard_within(session_dir, os.path.join(session_dir, "round-%d" % rnd))


def landing_dir(session_dir, rnd, phase):
    _require_token("phase", phase)
    return _guard_within(session_dir,
                         os.path.join(round_dir(session_dir, rnd), "landing", phase))


def store_dir(session_dir, rnd, phase):
    _require_token("phase", phase)
    return _guard_within(session_dir,
                         os.path.join(round_dir(session_dir, rnd), "seats", phase))


def _seat_filename(skey, attempt):
    _require_token("skey", skey)
    _require_index("attempt", attempt)
    return "%s.a%d.json" % (skey, attempt)


def landing_path(session_dir, rnd, phase, skey, attempt):
    return _guard_within(session_dir, os.path.join(landing_dir(session_dir, rnd, phase),
                                                   _seat_filename(skey, attempt)))


def store_path(session_dir, rnd, phase, skey, attempt):
    return _guard_within(session_dir, os.path.join(store_dir(session_dir, rnd, phase),
                                                   _seat_filename(skey, attempt)))


def dispatch_manifest_path(session_dir, rnd, phase, attempt):
    """The ORCHESTRATOR-written per-attempt dispatch manifest: `{seatKey: {vendor, model,
    engine}}`. It lives in the reserved `_` namespace so no seat key can ever address it."""
    _require_index("attempt", attempt)
    name = "%s.a%d.json" % (DISPATCH_MANIFEST_STEM, attempt)
    return _guard_within(session_dir,
                         os.path.join(landing_dir(session_dir, rnd, phase), name))


def canary_path(session_dir, rnd, vendor, attempt):
    """The per-vendor control-probe landing slot for the panel phase."""
    if vendor not in model_registry.VENDORS:
        raise ValueError("unknown vendor %r (expected one of %s)"
                         % (vendor, ", ".join(sorted(model_registry.VENDORS))))
    _require_index("attempt", attempt)
    return _guard_within(session_dir, os.path.join(
        landing_dir(session_dir, rnd, _PANEL_PHASE_DIRNAME), CANARY_DIRNAME,
        "%s.a%d.json" % (vendor, attempt)))


def session_lock_path(session_dir):
    return _guard_within(session_dir, os.path.join(session_dir, LOCK_FILE))


def meta_path(session_dir):
    return _guard_within(session_dir, os.path.join(session_dir, META_FILE))


# =============================================================================================
# durable write
# =============================================================================================

def _fsync_dir(directory):
    """Directory fsync with the exotic-filesystem errno allowlist — delegated to ``round_commit``."""
    import round_commit
    return round_commit.fsync_dir_tolerant(directory)


def atomic_write_json(path, obj):
    """Write canonical JSON so a reader sees either the OLD file or the WHOLE new one.

    tmp -> flush -> fsync(file) -> os.replace -> fsync(parent dir). The directory fsync is what
    makes the RENAME durable, not just the bytes; its failure is swallowed only for the three
    errnos exotic filesystems raise for an unsupported dir-fsync, and anything else propagates.
    The durability sequence lives in ``round_commit.atomic_write_bytes`` (lazy import — no cycle).
    """
    import round_commit
    return round_commit.atomic_write_bytes(path, canonical(obj).encode("utf-8"))


def read_json(path):
    """(obj, error) — `error` is `"missing"`, `"unparseable"`, or None. Never raises."""
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except OSError:
        return None, "missing"
    try:
        return json.loads(raw), None
    except ValueError:
        return None, "unparseable"


# =============================================================================================
# ingestion
# =============================================================================================

def _refuse(reason, **extra):
    out = {"ok": False, "reason": reason}
    out.update(extra)
    return out


def _normalize_envelope(envelope, occurrence=0):
    """The store copy: a shallow copy with `round`/`attempt` coerced to int and the SLOT's
    `occurrence` stamped. No key is dropped (an unknown key is a future field, not garbage to
    discard) and no value is invented — the occurrence stamped is the one this ingestion was
    addressed to, which is also the slot the file lives in, so the stored record says WHICH of two
    same-id seats it is rather than leaving the reader to infer it from the filename."""
    out = dict(envelope)
    out["occurrence"] = occurrence
    for key in ("round", "attempt"):
        value = out.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            continue
        if isinstance(value, str):
            try:
                out[key] = int(value)
            except ValueError:
                pass
    return out


def _session_id(session_dir):
    obj, err = read_json(os.path.join(session_dir, META_FILE))
    if err is not None or not isinstance(obj, dict):
        return None
    sid = obj.get("sessionId")
    if not isinstance(sid, str) or not sid:
        return None
    return sid


def _roster_keys(roster):
    if isinstance(roster, (list, tuple, set, frozenset)):
        return sorted(k for k in roster if isinstance(k, str))
    if isinstance(roster, dict):
        return sorted(k for k in roster.keys() if isinstance(k, str))
    return []


def _anchor_check(envelope, seat_key, anchor):
    """Bind an envelope to the emission-time dispatch anchor. Returns a refusal reason or None.

    `anchor` is `{"manifestSha256": ..., "orders": {seatKey: sha}}` captured when the dispatch
    was emitted. With no anchor the ONLY accepted claim is the `not-emitted` literal (PR-1 emits
    no order prompt files yet); an envelope claiming real hashes with nothing to check them
    against is `manifest-anchor-unanchored` — an unanchored claim is a claim nobody verified.
    """
    env_manifest = envelope.get("manifestSha256")
    env_order = envelope.get("orderSha256")
    if anchor is None:
        if env_manifest == NOT_EMITTED and env_order == NOT_EMITTED:
            return None
        return "manifest-anchor-unanchored"
    if not isinstance(anchor, dict):
        return "manifest-anchor-mismatch"
    orders = anchor.get("orders")
    want_order = orders.get(seat_key) if isinstance(orders, dict) else None
    if env_manifest != anchor.get("manifestSha256") or env_order != want_order:
        return "manifest-anchor-mismatch"
    return None


def validate_landing(session_dir, rnd, phase, seat_key, attempt, *, current_attempt, roster,
                     supersede=False, expect_sha256=None, anchor=None, occurrence=0):
    """Every check `ingest_landing` performs, with NO write.

    Returns (plan, refusal). Exactly one is None.
      plan = {"storePath": <abs>, "envelope": <the normalized envelope dict to write>,
              "payloadSha256": <str or None>, "superseded": <bool>,
              "seatKey": ..., "storageKey": ..., "occurrence": ...}
      refusal = the SAME dict `ingest_landing` returns on refusal today
                ({"ok": False, "reason": ..., ...extra}).
    """
    session_id = _session_id(session_dir)
    if session_id is None:
        return None, _refuse("bootstrap-required")
    if isinstance(seat_key, str) and seat_key.startswith(RESERVED_PREFIX):
        return None, _refuse("reserved-seat-name")
    valid = _roster_keys(roster)
    if not isinstance(seat_key, str) or seat_key not in valid:
        return None, _refuse("unknown-seat",
                             message="seat %r is not on this phase's roster; valid keys: %s"
                                     % (seat_key, ", ".join(valid) if valid else "(none)"),
                             validKeys=valid)
    slots = valid.count(seat_key)
    if isinstance(occurrence, int) and not isinstance(occurrence, bool) and occurrence >= slots:
        return None, _refuse("unknown-occurrence", occurrence=occurrence, occurrences=slots,
                             message="seat %r holds %d roster slot(s); occurrence %d addresses a slot "
                                     "that does not exist" % (seat_key, slots, occurrence))
    if attempt != current_attempt:
        return None, _refuse("stale-attempt", attempt=attempt, currentAttempt=current_attempt)

    try:
        skey = storage_key(seat_key, occurrence)
    except ValueError as exc:
        return None, _refuse("bad-argument", message=str(exc))
    try:
        lpath = landing_path(session_dir, rnd, phase, skey, attempt)
        spath = store_path(session_dir, rnd, phase, skey, attempt)
    except ValueError as exc:
        reason = "bad-argument" if "non-negative int" in str(exc) else "invalid-path"
        return None, _refuse(reason, message=str(exc))

    envelope, err = read_json(lpath)
    if err == "missing":
        return None, _refuse("landing-missing", landingPath=lpath)
    if err == "unparseable" or not isinstance(envelope, dict):
        return None, _refuse("landing-torn", landingPath=lpath)

    if envelope.get("attempt") != attempt:
        return None, _refuse("attempt-mismatch", envelopeAttempt=envelope.get("attempt"),
                             fileAttempt=attempt)
    if envelope.get("occurrence", occurrence) != occurrence:
        # The SLOT is the file's identity, and the ingestion names it. An envelope claiming a
        # different occurrence is a dispatch accounting fault: stamping the slot over the claim
        # would silently rewrite which of two same-id seats this record is.
        return None, _refuse("occurrence-mismatch", envelopeOccurrence=envelope.get("occurrence"),
                             occurrence=occurrence)
    if envelope.get("session") != session_id:
        return None, _refuse("session-mismatch", envelopeSession=envelope.get("session"),
                             sessionId=session_id)
    if envelope.get("phase") != phase:
        return None, _refuse("phase-mismatch", envelopePhase=envelope.get("phase"), phase=phase)
    if envelope.get("round") != rnd:
        return None, _refuse("round-mismatch", envelopeRound=envelope.get("round"), round=rnd)
    if envelope.get("seat") != seat_key:
        return None, _refuse("seat-mismatch", addressedSeat=seat_key, envelopeSeat=envelope.get("seat"))

    schema = envelope.get("schema")
    stored_sha = None
    if schema == SEAT_RESULT_SCHEMA:
        stored_sha = payload_sha256(envelope.get("payload"))
        if stored_sha != envelope.get("payloadSha256"):
            return None, _refuse("landing-torn", computed=stored_sha,
                                 declared=envelope.get("payloadSha256"), landingPath=lpath)
    elif schema == SEAT_MISSING_SCHEMA:
        if envelope.get("reason") not in MISSING_REASONS:
            return None, _refuse("missing-reason",
                                 message="seat-missing reason %r is not one of: %s"
                                         % (envelope.get("reason"), ", ".join(MISSING_REASONS)))
    else:
        return None, _refuse("schema-unknown", schema=schema)

    anchor_reason = _anchor_check(envelope, seat_key, anchor)
    if anchor_reason is not None:
        return None, _refuse(anchor_reason, manifestSha256=envelope.get("manifestSha256"),
                             orderSha256=envelope.get("orderSha256"))

    exists = os.path.exists(spath)
    if exists and not supersede:
        return None, _refuse("store-exists", storePath=spath)
    if supersede:
        if expect_sha256 is None:
            return None, _refuse("cas-expect-required", storePath=spath)
        current, cur_err = read_json(spath)
        current_sha = envelope_cas_token(current) if (cur_err is None and isinstance(current, dict)) else None
        if current_sha != expect_sha256:
            return None, _refuse("cas-mismatch", expected=expect_sha256, actual=current_sha,
                                 storePath=spath)

    plan = {
        "storePath": spath,
        "envelope": _normalize_envelope(envelope, occurrence),
        "payloadSha256": stored_sha,
        "superseded": bool(exists and supersede),
        "seatKey": seat_key,
        "storageKey": skey,
        "occurrence": occurrence,
    }
    return plan, None


def ingest_landing(session_dir, rnd, phase, seat_key, attempt, *, current_attempt, roster,
                   supersede=False, expect_sha256=None, anchor=None, occurrence=0):
    """Ingest ONE landed seat envelope into the durable store. Never raises on bad input.

    Returns `{"ok": True, "storePath", "payloadSha256", "superseded"}` or a refusal
    `{"ok": False, "reason": <str>, ...}`. The `reason` string is the contract — every refusal
    below is a distinct one, and every one of them is fail-closed (nothing is stored):

      bootstrap-required, reserved-seat-name, unknown-seat, unknown-occurrence, stale-attempt,
      landing-missing, landing-torn, attempt-mismatch, seat-mismatch, occurrence-mismatch,
      session-mismatch, phase-mismatch, round-mismatch, schema-unknown, missing-reason, store-exists,
      cas-expect-required, cas-mismatch, manifest-anchor-mismatch, manifest-anchor-unanchored

    plus two defensive reasons outside that roster: `invalid-path` (a crafted phase/seat/round
    that would escape the session dir) and `bad-argument` (a malformed `attempt`/`occurrence`).

    Three evaluation-order notes, all deliberate:
      - `reserved-seat-name` is decided BEFORE `unknown-seat`: a `_`-prefixed key is
        structurally illegal whatever the roster says, and reporting it as merely unknown would
        hide the namespace collision behind a roster typo.
      - `unknown-occurrence` follows `unknown-seat`, and is its second half: the roster slot is
        (seat_key, occurrence), so an occurrence past the number of times the key appears
        addresses a seat that does not exist. Storing it would put a real record in a slot no
        fold ever reads — silent loss, which is exactly what the enumerated refusals exist to
        prevent.
      - an UNPARSEABLE landing file is reported `landing-torn`, not a separate reason: a
        half-written host Write is exactly what "torn" names, and it is the same fail-closed
        outcome as a payload-hash mismatch.
    The caller journals the outcome; this function does not.
    """
    plan, refusal = validate_landing(session_dir, rnd, phase, seat_key, attempt,
                                     current_attempt=current_attempt, roster=roster,
                                     supersede=supersede, expect_sha256=expect_sha256,
                                     anchor=anchor, occurrence=occurrence)
    if refusal is not None:
        return refusal
    atomic_write_json(plan["storePath"], plan["envelope"])
    return {"ok": True, "reason": None, "storePath": plan["storePath"],
            "payloadSha256": plan["payloadSha256"], "superseded": plan["superseded"],
            "seatKey": plan["seatKey"], "storageKey": plan["storageKey"],
            "occurrence": plan["occurrence"]}


def sweep_landing(session_dir, rnd, phase, *, current_attempt, roster, anchor=None):
    """Ingest every unclaimed landing file for `phase` at `current_attempt`.

    Idempotent by construction: a seat already in the store is reported `already-stored` with
    `ok: True` (re-running a sweep after a crash must not manufacture an error), and a landing
    file that maps to no roster seat is reported with the enumerated `unknown-seat` refusal
    rather than skipped in silence. Returns one result dict per SLOT/file, sorted by storage key.

    The sweep walks SLOTS — (seat_key, occurrence) — not bare seat keys: a roster carrying one id
    twice owes two landings, and sweeping by key alone would claim the first slot's file twice and
    leave the second's unswept (and then reported as an `unknown-seat` stray).
    """
    results = []
    claimed = set()
    for seat_key, occurrence in roster_slots(_roster_keys(roster)):
        try:
            skey = storage_key(seat_key, occurrence)
            lpath = landing_path(session_dir, rnd, phase, skey, current_attempt)
            spath = store_path(session_dir, rnd, phase, skey, current_attempt)
        except ValueError as exc:
            results.append(_refuse("bad-argument", seatKey=seat_key, occurrence=occurrence,
                                   message=str(exc)))
            continue
        claimed.add(os.path.basename(lpath))
        if not os.path.exists(lpath):
            continue
        if os.path.exists(spath):
            results.append({"ok": True, "reason": "already-stored", "seatKey": seat_key,
                            "storageKey": skey, "storePath": spath, "occurrence": occurrence})
            continue
        out = ingest_landing(session_dir, rnd, phase, seat_key, current_attempt,
                             current_attempt=current_attempt, roster=roster, anchor=anchor,
                             occurrence=occurrence)
        out.setdefault("seatKey", seat_key)
        out.setdefault("storageKey", skey)
        out.setdefault("occurrence", occurrence)
        results.append(out)

    valid = _roster_keys(roster)
    suffix = ".a%d.json" % current_attempt if isinstance(current_attempt, int) else None
    try:
        names = sorted(os.listdir(landing_dir(session_dir, rnd, phase)))
    except (OSError, ValueError):
        names = []
    for name in names:
        if name in claimed or name.startswith(RESERVED_PREFIX) or suffix is None:
            continue
        if not name.endswith(suffix):
            continue
        results.append(_refuse("unknown-seat", storageKey=name[:-len(suffix)],
                               message="landing file %r maps to no roster seat; valid keys: %s"
                                       % (name, ", ".join(valid) if valid else "(none)"),
                               validKeys=valid))
    results.sort(key=lambda r: (r.get("storageKey") or "", r.get("seatKey") or ""))
    return results


# =============================================================================================
# two-commit recovery
# =============================================================================================

_SEAT_FILE_RE = re.compile(r"^(?P<key>[a-z0-9][a-z0-9-]*)\.a(?P<attempt>\d+)\.json$")


def _seat_files(directory):
    out = {}
    try:
        names = os.listdir(directory)
    except OSError:
        return out
    for name in sorted(names):
        m = _SEAT_FILE_RE.match(name)
        if not m:
            continue
        out[name] = {"storageKey": m.group("key"), "attempt": int(m.group("attempt")),
                     "path": os.path.join(directory, name)}
    return out


def reconcile(session_dir, rnd, phase, journal_identities):
    """Recover the two-commit window between "the store file landed" and "the journal recorded it".

    THE STORE FILE IS AUTHORITATIVE; the journal is the log. Reconciliation therefore repairs the
    JOURNAL to match the files, never the files to match the journal:

      - a landing file with no store copy      -> `ingestNow`      (the ingest half never ran)
      - a store copy whose record identity is not in `journal_identities` -> `reappend` (the append
        half never ran; the record is real and the log is behind)
      - an identity in `journal_identities` with no store file for that slot -> `journalOrphan` —
        the ONE machinery-failure class here: the log claims a record that does not exist on disk.
        The caller turns it into a refusal naming the seat; nothing here deletes or invents a file.

    Record identity is `(phase, seat, occurrence, attempt)` — NOT the payload hash alone. Payload
    hashes ride the journal as the revision token: a supersede writes a new store file into the SAME
    slot, so reconcile must reappend when the store's current token differs from the latest token the
    journal recorded for that slot.
    """
    identities = []
    for ident in (journal_identities or []):
        key = _identity_key_from_mapping(ident, default_phase=phase)
        if key is not None:
            identities.append(ident)
    journal_keys = set()
    journal_tokens = {}
    for ident in identities:
        key = _identity_key_from_mapping(ident, default_phase=phase)
        if key is not None:
            journal_keys.add(key)
            token = ident.get("payloadSha256")
            if token is not None:
                journal_tokens[key] = token
    try:
        ldir = landing_dir(session_dir, rnd, phase)
        sdir = store_dir(session_dir, rnd, phase)
    except ValueError:
        return {"ingestNow": [], "reappend": [], "journalOrphan": list(identities)}

    landings = _seat_files(ldir)
    stores = _seat_files(sdir)

    ingest_now = []
    for name in sorted(landings):
        if name not in stores:
            ingest_now.append(dict(landings[name]))

    reappend = []
    store_keys = set()
    for name in sorted(stores):
        entry = dict(stores[name])
        obj, err = read_json(entry["path"])
        sha = obj.get("payloadSha256") if (err is None and isinstance(obj, dict)) else None
        entry["payloadSha256"] = sha
        if err is None and isinstance(obj, dict):
            key = _identity_key_from_mapping(
                record_identity(phase, obj.get("seat"), obj.get("occurrence", 0), obj.get("attempt")))
            if key is not None:
                store_keys.add(key)
                entry["recordIdentity"] = record_identity(*key)
                store_token = envelope_cas_token(obj)
                journaled = journal_tokens.get(key)
                if key not in journal_keys:
                    reappend.append(entry)
                elif journaled is not None and store_token is not None and journaled != store_token:
                    reappend.append(entry)
    orphans = [ident for ident in identities
               if _identity_key_from_mapping(ident, default_phase=phase) not in store_keys]
    return {"ingestNow": ingest_now, "reappend": reappend, "journalOrphan": orphans}


# =============================================================================================
# session lock + session id
# =============================================================================================

class LockHeld(Exception):
    """Another holder owns the session lock. Carries the holder's recorded pid and ISO timestamp
    so the caller can report WHO holds it (and decide, elsewhere, whether to break it)."""

    def __init__(self, pid, created_at):
        self.pid = pid
        self.created_at = created_at
        super().__init__("session lock held by pid %r since %r" % (pid, created_at))


# Re-entrant depth for this process only — the on-disk lockfile contract is unchanged; a different
# process still sees LockHeld. Only same-process nested acquire/release skips the file.
_session_lock_depth = 0


def read_lock(session_dir):
    """The recorded holder `{"pid","createdAt"}`, or None when the lock is absent/unreadable."""
    try:
        path = session_lock_path(session_dir)
    except ValueError:
        return None
    obj, err = read_json(path)
    if err is not None or not isinstance(obj, dict):
        return None
    return {"pid": obj.get("pid"), "createdAt": obj.get("createdAt")}


@contextlib.contextmanager
def session_lock(session_dir):
    """Exclusive session lock via `O_CREAT | O_EXCL` — the create IS the mutual exclusion.

    Raises `LockHeld(pid, created_at)` when the lockfile already exists and is owned by a
    different process. Re-entrant within this process: a nested acquire increments depth and does
    not touch the lockfile; only the outermost release removes it. The lockfile is always removed
    on exit, INCLUDING on exception, so a raising body never leaves a stale lock.
    """
    global _session_lock_depth
    path = session_lock_path(session_dir)
    if _session_lock_depth > 0:
        _session_lock_depth += 1
        try:
            yield path
        finally:
            _session_lock_depth -= 1
        return
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        holder = read_lock(session_dir) or {}
        raise LockHeld(holder.get("pid"), holder.get("createdAt"))
    _session_lock_depth = 1
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(canonical({"pid": os.getpid(), "createdAt": _now_iso()}))
            fh.flush()
            os.fsync(fh.fileno())
        yield path
    finally:
        _session_lock_depth -= 1
        try:
            os.remove(path)
        except OSError:
            pass


def break_lock(session_dir):
    """Remove the lockfile and return the broken holder `{"pid","createdAt"}` (or None).

    It decides NO policy — whether breaking a live holder's lock is legitimate is the caller's
    call, and the caller journals it.
    """
    holder = read_lock(session_dir)
    try:
        os.remove(session_lock_path(session_dir))
    except (OSError, ValueError):
        return holder
    return holder


def mint_session_id(session_dir):
    """(sessionId, reason) — mint the session id into `meta.json`, idempotently.

    An existing non-empty `sessionId` is returned unchanged. Otherwise the id is
    sha256(abspath(session_dir) + now + 16 random bytes) truncated to 32 hex chars, MERGED into
    the existing meta dict — `review-code`'s SKILL writes that file, so its other keys
    (`baseRef`, ...) must survive — and written atomically. An UNPARSEABLE meta.json returns
    `(None, "meta-unparseable")` and is never overwritten: clobbering it would destroy the only
    record of what the session was.
    """
    path = os.path.join(session_dir, META_FILE)
    meta, err = read_json(path)
    if err == "unparseable":
        return None, "meta-unparseable"
    if err is None and not isinstance(meta, dict):
        return None, "meta-unparseable"
    if err == "missing" or meta is None:
        meta = {}
    existing = meta.get("sessionId")
    if isinstance(existing, str) and existing:
        return existing, None
    seed = "%s%s%s" % (os.path.abspath(session_dir), _now_iso(), os.urandom(16).hex())
    sid = sha256_text(seed)[:32]
    meta = dict(meta)
    meta["sessionId"] = sid
    atomic_write_json(path, meta)
    return sid, None


# =============================================================================================
# handback sidecar
# =============================================================================================

def build_sidecar(**fields):
    """Build the `handback-sidecar/1` dict. `schema` is always the constant (a caller cannot
    declare a different one); an unknown keyword is a `ValueError` rather than a silently
    dropped field. A field the caller omits comes back as `""`, which `validate_sidecar` then
    refuses — an incomplete sidecar fails at the validator, never at the consumer."""
    unknown = sorted(k for k in fields if k not in SIDECAR_FIELDS)
    if unknown:
        raise ValueError("unknown sidecar field(s): %s (expected: %s)"
                         % (", ".join(unknown), ", ".join(SIDECAR_FIELDS)))
    out = {}
    for key in SIDECAR_FIELDS:
        out[key] = fields.get(key, "")
    out["schema"] = SIDECAR_SCHEMA
    return out


def validate_sidecar(obj):
    """(ok, reason). Every declared key required, every value a NON-EMPTY str, `schema` exact."""
    if not isinstance(obj, dict):
        return False, "not-a-dict"
    if obj.get("schema") != SIDECAR_SCHEMA:
        return False, "schema-unknown"
    for key in SIDECAR_FIELDS:
        if key not in obj:
            return False, "missing-field:%s" % key
        value = obj.get(key)
        if not isinstance(value, str):
            return False, "non-string-field:%s" % key
        if not value:
            return False, "empty-field:%s" % key
    return True, None


def sidecar_stale(obj, *, head_sha, receipt_bytes, session_dir):
    """(stale, reason) — is this sidecar still describing the world it was written for?

    Stale when the head moved, when the receipt bytes no longer hash to the recorded
    `receiptSha256`, or when it points at a different session dir. An INVALID sidecar is stale
    too (`sidecar-invalid:<reason>`): an unverifiable sidecar is never treated as fresh.
    """
    ok, reason = validate_sidecar(obj)
    if not ok:
        return True, "sidecar-invalid:%s" % reason
    if obj.get("headSha") != head_sha:
        return True, "head-moved"
    if isinstance(receipt_bytes, str):
        receipt_bytes = receipt_bytes.encode("utf-8")
    if not isinstance(receipt_bytes, (bytes, bytearray)):
        return True, "receipt-unreadable"
    if hashlib.sha256(bytes(receipt_bytes)).hexdigest() != obj.get("receiptSha256"):
        return True, "receipt-changed"
    if obj.get("sessionDir") != session_dir:
        return True, "session-dir-mismatch"
    return False, None
