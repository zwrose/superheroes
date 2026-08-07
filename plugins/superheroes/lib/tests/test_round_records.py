"""Tests for `round_records` — the durable per-seat record layer for the round driver (#723).

The contract these pin is the REFUSAL STRING, not merely the falsity of `ok`: every fail-closed
edge in `ingest_landing` gets its own test asserting the exact `reason`, because a caller routes
on that string (a test that only asserted `ok is False` would pass against any refusal, including
the wrong one).

Also pinned: storage-key injectivity and filename safety (roster keys carry `/` and `:` and audit
ids can legitimately collide), the session-dir path fence, the atomic write, the attempt fence
against a LATE ingest of a superseded attempt, the torn/partial-write detector, the supersede CAS,
the two-commit `reconcile` classes, the session lock, `mint_session_id`'s idempotency and its
must-not-clobber of the SKILL-written meta.json, and the handback sidecar.
"""
import importlib.util
import json
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RR = _load("round_records")

SESSION = "s" * 32
PHASE = "dispatch-verifiers"
SEAT = "src/a/b.py:3"
OTHER_SEAT = "src/a/b.py:4"
ROSTER = [SEAT, OTHER_SEAT]


# --- helpers ----------------------------------------------------------------------------------

def _session(tmp_path, **meta_extra):
    sd = str(tmp_path / "session")
    os.makedirs(sd, exist_ok=True)
    meta = {"sessionId": SESSION}
    meta.update(meta_extra)
    RR.atomic_write_json(os.path.join(sd, "meta.json"), meta)
    return sd


def _env(payload=None, **over):
    payload = {"findings": ["f1"]} if payload is None else payload
    env = {
        "schema": RR.SEAT_RESULT_SCHEMA,
        "session": SESSION,
        "round": 1,
        "phase": PHASE,
        "seat": SEAT,
        "attempt": 1,
        "vendor": "claude",
        "model": "sonnet-5",
        "dispatchRef": "dispatch-abc",
        "orderSha256": RR.NOT_EMITTED,
        "manifestSha256": RR.NOT_EMITTED,
        "recordedAt": "2026-08-07T00:00:00",
        "payloadSha256": RR.payload_sha256(payload),
        "payload": payload,
    }
    env.update(over)
    return env


def _missing_env(**over):
    env = {
        "schema": RR.SEAT_MISSING_SCHEMA,
        "session": SESSION,
        "round": 1,
        "phase": PHASE,
        "seat": SEAT,
        "attempt": 1,
        "vendor": "codex",
        "model": "gpt-5",
        "dispatchRef": "dispatch-abc",
        "orderSha256": RR.NOT_EMITTED,
        "manifestSha256": RR.NOT_EMITTED,
        "recordedAt": "2026-08-07T00:00:00",
        "reason": "forfeit",
    }
    env.update(over)
    return env


def _land(sd, env, rnd=1, phase=PHASE, seat=SEAT, attempt=1):
    path = RR.landing_path(sd, rnd, phase, RR.storage_key(seat), attempt)
    RR.atomic_write_json(path, env)
    return path


def _ingest(sd, seat=SEAT, attempt=1, current=1, rnd=1, phase=PHASE, **kw):
    return RR.ingest_landing(sd, rnd, phase, seat, attempt,
                             current_attempt=current, roster=ROSTER, **kw)


# --- storage keys -----------------------------------------------------------------------------

def test_storage_key_is_filename_safe_and_slug_plus_hash():
    key = RR.storage_key(SEAT)
    assert key == "src-a-b-py-3-" + RR.sha256_text(SEAT)[:16]
    assert "/" not in key and ":" not in key and ".." not in key
    assert not key.startswith("_")


def test_storage_key_shape_holds_for_audit_ids_and_long_keys():
    for seat in (SEAT, "src/a/b.py::some very long finding title that runs on and on and on",
                 "A/B-C", "123"):
        key = RR.storage_key(seat)
        assert RR._KEY_RE.match(key), key
        assert os.sep not in key and ".." not in key


def test_storage_key_distinguishes_keys_that_share_a_truncated_slug():
    # Two distinct roster keys whose slugs are identical for the first 40 chars: only the hash
    # tail keeps them apart, which is exactly the collision the slug alone would lose.
    long_a = "src/very/long/path/to/a/module/file.py:1000"
    long_b = "src/very/long/path/to/a/module/file.py:1001"
    ka, kb = RR.storage_key(long_a), RR.storage_key(long_b)
    assert ka[:40] == kb[:40]
    assert ka != kb


def test_storage_key_occurrence_disambiguates_colliding_ids():
    base = RR.storage_key(SEAT)
    assert RR.storage_key(SEAT, 1) == base + "-o1"
    assert RR.storage_key(SEAT, 2) != RR.storage_key(SEAT, 1)


def test_storage_key_empty_slug_falls_back_to_hash_form():
    key = RR.storage_key("///:::")
    assert key == "seat-" + RR.sha256_text("///:::")[:16]
    assert RR._KEY_RE.match(key)


@pytest.mark.parametrize("bad", [None, "", 3, [], {}])
def test_storage_key_rejects_non_string_or_empty_seat_key(bad):
    with pytest.raises(ValueError):
        RR.storage_key(bad)


def test_storage_key_rejects_reserved_underscore_namespace():
    with pytest.raises(ValueError):
        RR.storage_key("_dispatch")


@pytest.mark.parametrize("bad", [-1, 1.5, "1", None, True])
def test_storage_key_rejects_bad_occurrence(bad):
    with pytest.raises(ValueError):
        RR.storage_key(SEAT, bad)


# --- paths ------------------------------------------------------------------------------------

def test_path_builders_place_files_where_the_contract_says(tmp_path):
    sd = _session(tmp_path)
    skey = RR.storage_key(SEAT)
    assert RR.landing_path(sd, 2, PHASE, skey, 3) == os.path.join(
        sd, "round-2", "landing", PHASE, skey + ".a3.json")
    assert RR.store_path(sd, 2, PHASE, skey, 3) == os.path.join(
        sd, "round-2", "seats", PHASE, skey + ".a3.json")
    assert RR.dispatch_manifest_path(sd, 2, PHASE, 3) == os.path.join(
        sd, "round-2", "landing", PHASE, "_dispatch.a3.json")
    assert RR.canary_path(sd, 2, "codex", 3) == os.path.join(
        sd, "round-2", "landing", "dispatch-panel", "_canary", "codex.a3.json")


def test_path_builders_reject_a_traversal_phase(tmp_path):
    sd = _session(tmp_path)
    for phase in ("../..", "../../../etc", "a/b", "."):
        with pytest.raises(ValueError):
            RR.landing_path(sd, 1, phase, RR.storage_key(SEAT), 1)


def test_path_builders_reject_a_traversal_seat_key(tmp_path):
    sd = _session(tmp_path)
    with pytest.raises(ValueError):
        RR.store_path(sd, 1, PHASE, "../../escape", 1)
    # ...and a seat key containing traversal text can never BECOME one: it slugifies.
    assert ".." not in RR.storage_key("../../escape")


def test_canary_path_rejects_an_unknown_vendor(tmp_path):
    sd = _session(tmp_path)
    with pytest.raises(ValueError):
        RR.canary_path(sd, 1, "acme", 1)


def test_path_builders_reject_bad_round_or_attempt(tmp_path):
    sd = _session(tmp_path)
    with pytest.raises(ValueError):
        RR.landing_path(sd, -1, PHASE, RR.storage_key(SEAT), 1)
    with pytest.raises(ValueError):
        RR.landing_path(sd, 1, PHASE, RR.storage_key(SEAT), "1")


# --- durable write ----------------------------------------------------------------------------

def test_atomic_write_json_lands_parseable_and_leaves_no_tmp(tmp_path):
    path = str(tmp_path / "deep" / "nest" / "out.json")
    RR.atomic_write_json(path, {"b": 1, "a": [2, 3]})
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    assert json.loads(raw) == {"b": 1, "a": [2, 3]}
    assert raw == '{"a":[2,3],"b":1}'  # canonical: sorted keys, no spaces
    assert not os.path.exists(path + ".tmp")


def test_atomic_write_json_replaces_in_place(tmp_path):
    path = str(tmp_path / "out.json")
    RR.atomic_write_json(path, {"v": 1})
    RR.atomic_write_json(path, {"v": 2})
    obj, err = RR.read_json(path)
    assert (obj, err) == ({"v": 2}, None)
    assert not os.path.exists(path + ".tmp")


# --- ingestion: the happy path ----------------------------------------------------------------

def test_ingest_stores_the_envelope_and_reports_the_payload_hash(tmp_path):
    sd = _session(tmp_path)
    env = _env()
    _land(sd, env)
    out = _ingest(sd)
    assert out["ok"] is True and out["reason"] is None
    assert out["superseded"] is False
    assert out["payloadSha256"] == env["payloadSha256"]
    stored, err = RR.read_json(out["storePath"])
    assert err is None
    assert stored["payload"] == env["payload"]
    assert out["storePath"] == RR.store_path(sd, 1, PHASE, RR.storage_key(SEAT), 1)


def test_ingest_accepts_a_wellformed_seat_missing_envelope(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _missing_env())
    out = _ingest(sd)
    assert out["ok"] is True
    assert RR.read_json(out["storePath"])[0]["reason"] == "forfeit"


# --- ingestion: every refusal reason ----------------------------------------------------------

def test_refusal_bootstrap_required_when_meta_missing(tmp_path):
    sd = str(tmp_path / "session")
    os.makedirs(sd)
    assert _ingest(sd)["reason"] == "bootstrap-required"


def test_refusal_bootstrap_required_when_session_id_blank(tmp_path):
    sd = _session(tmp_path)
    RR.atomic_write_json(os.path.join(sd, "meta.json"), {"sessionId": ""})
    assert _ingest(sd)["reason"] == "bootstrap-required"


def test_refusal_unknown_seat_enumerates_the_valid_keys_sorted(tmp_path):
    sd = _session(tmp_path)
    out = _ingest(sd, seat="src/z.py:9")
    assert out["reason"] == "unknown-seat"
    assert out["validKeys"] == sorted(ROSTER)
    assert ", ".join(sorted(ROSTER)) in out["message"]


def test_refusal_reserved_seat_name_beats_unknown_seat(tmp_path):
    # A `_`-prefixed key is structurally illegal whatever the roster says; reporting it as merely
    # unknown would hide the namespace collision behind an apparent roster typo.
    sd = _session(tmp_path)
    assert _ingest(sd, seat="_dispatch")["reason"] == "reserved-seat-name"


def test_refusal_stale_attempt(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _env())
    out = _ingest(sd, attempt=1, current=2)
    assert out["reason"] == "stale-attempt"


def test_refusal_landing_missing(tmp_path):
    sd = _session(tmp_path)
    assert _ingest(sd)["reason"] == "landing-missing"


def test_refusal_attempt_mismatch_between_envelope_and_filename(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _env(attempt=1), attempt=2)
    assert _ingest(sd, attempt=2, current=2)["reason"] == "attempt-mismatch"


def test_refusal_session_mismatch(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _env(session="a" * 32))
    assert _ingest(sd)["reason"] == "session-mismatch"


def test_refusal_phase_mismatch(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _env(phase="dispatch-audits"))
    assert _ingest(sd)["reason"] == "phase-mismatch"


def test_refusal_round_mismatch(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _env(round=2))
    assert _ingest(sd)["reason"] == "round-mismatch"


def test_refusal_landing_torn_when_payload_is_truncated_after_hashing(tmp_path):
    # The torn/partial-host-Write detector: the envelope's declared payloadSha256 is the hash of
    # the WHOLE payload; truncating the payload afterwards is exactly what a half-written file
    # looks like from the reader's side.
    sd = _session(tmp_path)
    env = _env(payload={"findings": ["f1", "f2", "f3"]})
    torn = dict(env)
    torn["payload"] = {"findings": ["f1"]}  # truncated; payloadSha256 still the full hash
    _land(sd, torn)
    out = _ingest(sd)
    assert out["reason"] == "landing-torn"
    assert out["declared"] == env["payloadSha256"]
    assert not os.path.exists(RR.store_path(sd, 1, PHASE, RR.storage_key(SEAT), 1))


def test_refusal_landing_torn_when_the_file_is_unparseable(tmp_path):
    sd = _session(tmp_path)
    path = _land(sd, _env())
    with open(path, "w", encoding="utf-8") as fh:
        fh.write('{"schema": "seat-result/1", "payl')  # half a host Write
    assert _ingest(sd)["reason"] == "landing-torn"


def test_refusal_schema_unknown(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _env(schema="seat-result/2"))
    out = _ingest(sd)
    assert out["reason"] == "schema-unknown"
    assert out["schema"] == "seat-result/2"


def test_refusal_missing_reason_enumerates_the_allowed_set(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _missing_env(reason="vibes"))
    out = _ingest(sd)
    assert out["reason"] == "missing-reason"
    for allowed in RR.MISSING_REASONS:
        assert allowed in out["message"]


def test_refusal_store_exists_without_supersede(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _env())
    assert _ingest(sd)["ok"] is True
    assert _ingest(sd)["reason"] == "store-exists"


def test_refusal_cas_expect_required(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _env())
    assert _ingest(sd)["ok"] is True
    assert _ingest(sd, supersede=True)["reason"] == "cas-expect-required"


def test_refusal_cas_mismatch_on_a_stale_expectation(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _env())
    assert _ingest(sd)["ok"] is True
    out = _ingest(sd, supersede=True, expect_sha256="0" * 64)
    assert out["reason"] == "cas-mismatch"


def test_supersede_with_the_correct_expectation_succeeds(tmp_path):
    sd = _session(tmp_path)
    first = _env()
    _land(sd, first)
    assert _ingest(sd)["ok"] is True
    second = _env(payload={"findings": ["f1", "f2"]})
    _land(sd, second)
    out = _ingest(sd, supersede=True, expect_sha256=first["payloadSha256"])
    assert out["ok"] is True and out["superseded"] is True
    assert RR.read_json(out["storePath"])[0]["payload"] == second["payload"]


def test_refusal_manifest_anchor_mismatch(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _env(manifestSha256="m" * 64, orderSha256="o" * 64))
    anchor = {"manifestSha256": "m" * 64, "orders": {SEAT: "different" * 8}}
    assert _ingest(sd, anchor=anchor)["reason"] == "manifest-anchor-mismatch"


def test_anchor_match_is_accepted(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _env(manifestSha256="m" * 64, orderSha256="o" * 64))
    anchor = {"manifestSha256": "m" * 64, "orders": {SEAT: "o" * 64}}
    assert _ingest(sd, anchor=anchor)["ok"] is True


def test_refusal_manifest_anchor_unanchored_when_hashes_claimed_with_no_anchor(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _env(manifestSha256="m" * 64, orderSha256="o" * 64))
    assert _ingest(sd, anchor=None)["reason"] == "manifest-anchor-unanchored"


def test_not_emitted_literal_is_accepted_when_there_is_no_anchor(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _env())  # orderSha256/manifestSha256 == "not-emitted"
    assert _ingest(sd, anchor=None)["ok"] is True


def test_refusal_invalid_path_for_a_crafted_phase(tmp_path):
    sd = _session(tmp_path)
    out = _ingest(sd, phase="../../etc")
    assert out["reason"] == "invalid-path"


# --- attempt fence: a LATE ingest of a superseded attempt (register item R2) --------------------

def test_late_ingest_of_a_stale_attempt_leaves_the_current_store_byte_unchanged(tmp_path):
    sd = _session(tmp_path)
    a1 = _env(attempt=1, payload={"findings": ["old"]})
    a2 = _env(attempt=2, payload={"findings": ["new"]})
    _land(sd, a1, attempt=1)
    _land(sd, a2, attempt=2)

    out = RR.ingest_landing(sd, 1, PHASE, SEAT, 2, current_attempt=2, roster=ROSTER)
    assert out["ok"] is True
    spath = out["storePath"]
    with open(spath, "rb") as fh:
        before = fh.read()

    late = RR.ingest_landing(sd, 1, PHASE, SEAT, 1, current_attempt=2, roster=ROSTER)
    assert late["reason"] == "stale-attempt"
    with open(spath, "rb") as fh:
        assert fh.read() == before
    assert not os.path.exists(RR.store_path(sd, 1, PHASE, RR.storage_key(SEAT), 1))


# --- sweep ------------------------------------------------------------------------------------

def test_sweep_ingests_every_landed_seat_and_is_idempotent(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _env(), seat=SEAT)
    _land(sd, _env(seat=OTHER_SEAT), seat=OTHER_SEAT)
    first = RR.sweep_landing(sd, 1, PHASE, current_attempt=1, roster=ROSTER)
    assert [r["ok"] for r in first] == [True, True]
    assert set(r["seatKey"] for r in first) == set(ROSTER)

    second = RR.sweep_landing(sd, 1, PHASE, current_attempt=1, roster=ROSTER)
    assert [r["ok"] for r in second] == [True, True]
    assert set(r["reason"] for r in second) == {"already-stored"}


def test_sweep_reports_an_unrostered_landing_file_as_unknown_seat(tmp_path):
    sd = _session(tmp_path)
    stray = RR.landing_path(sd, 1, PHASE, "stray-seat", 1)
    RR.atomic_write_json(stray, _env())
    out = RR.sweep_landing(sd, 1, PHASE, current_attempt=1, roster=ROSTER)
    assert [r["reason"] for r in out] == ["unknown-seat"]


def test_sweep_ignores_the_reserved_orchestrator_files(tmp_path):
    sd = _session(tmp_path)
    RR.atomic_write_json(RR.dispatch_manifest_path(sd, 1, PHASE, 1), {SEAT: {"vendor": "claude"}})
    assert RR.sweep_landing(sd, 1, PHASE, current_attempt=1, roster=ROSTER) == []


# --- reconcile --------------------------------------------------------------------------------

def test_reconcile_reports_a_landing_with_no_store_copy_as_ingest_now(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _env())
    out = RR.reconcile(sd, 1, PHASE, set())
    assert [e["storageKey"] for e in out["ingestNow"]] == [RR.storage_key(SEAT)]
    assert out["reappend"] == [] and out["journalOrphan"] == []


def test_reconcile_reports_a_store_copy_the_journal_never_logged_as_reappend(tmp_path):
    sd = _session(tmp_path)
    env = _env()
    _land(sd, env)
    assert _ingest(sd)["ok"] is True
    out = RR.reconcile(sd, 1, PHASE, set())
    assert out["ingestNow"] == []
    assert [e["payloadSha256"] for e in out["reappend"]] == [env["payloadSha256"]]
    assert out["journalOrphan"] == []


def test_reconcile_reports_a_journal_hash_with_no_store_file_as_orphan(tmp_path):
    sd = _session(tmp_path)
    env = _env()
    _land(sd, env)
    assert _ingest(sd)["ok"] is True
    out = RR.reconcile(sd, 1, PHASE, {env["payloadSha256"], "z" * 64})
    assert out["reappend"] == []
    assert out["journalOrphan"] == ["z" * 64]


def test_reconcile_keeps_the_store_file_authoritative(tmp_path):
    # The journal is the log: reconcile never deletes or rewrites a store file to match it.
    sd = _session(tmp_path)
    env = _env()
    _land(sd, env)
    spath = _ingest(sd)["storePath"]
    with open(spath, "rb") as fh:
        before = fh.read()
    RR.reconcile(sd, 1, PHASE, {"z" * 64})
    with open(spath, "rb") as fh:
        assert fh.read() == before


# --- session lock -----------------------------------------------------------------------------

def test_session_lock_is_mutually_exclusive(tmp_path):
    sd = _session(tmp_path)
    with RR.session_lock(sd):
        with pytest.raises(RR.LockHeld) as exc:
            with RR.session_lock(sd):
                pass
        assert exc.value.pid == os.getpid()
        assert isinstance(exc.value.created_at, str) and exc.value.created_at


def test_session_lock_is_released_on_exception(tmp_path):
    sd = _session(tmp_path)
    with pytest.raises(RuntimeError):
        with RR.session_lock(sd):
            raise RuntimeError("boom")
    assert not os.path.exists(RR.session_lock_path(sd))
    with RR.session_lock(sd):  # re-acquirable
        pass


def test_break_lock_returns_the_holder_and_removes_the_lockfile(tmp_path):
    sd = _session(tmp_path)
    RR.atomic_write_json(RR.session_lock_path(sd),
                         {"pid": 4242, "createdAt": "2026-08-07T00:00:00"})
    holder = RR.break_lock(sd)
    assert holder == {"pid": 4242, "createdAt": "2026-08-07T00:00:00"}
    assert not os.path.exists(RR.session_lock_path(sd))
    assert RR.break_lock(sd) is None


# --- session id -------------------------------------------------------------------------------

def test_mint_session_id_creates_a_missing_meta(tmp_path):
    sd = str(tmp_path / "session")
    os.makedirs(sd)
    sid, reason = RR.mint_session_id(sd)
    assert reason is None
    assert isinstance(sid, str) and len(sid) == 32
    assert RR.read_json(os.path.join(sd, "meta.json"))[0] == {"sessionId": sid}


def test_mint_session_id_is_idempotent(tmp_path):
    sd = _session(tmp_path)
    assert RR.mint_session_id(sd) == (SESSION, None)
    assert RR.mint_session_id(sd) == (SESSION, None)


def test_mint_session_id_preserves_the_skill_written_meta_keys(tmp_path):
    # `review-code`'s SKILL owns meta.json; minting MERGES into it. Clobbering would drop the
    # base ref the whole round is diffed against.
    sd = str(tmp_path / "session")
    os.makedirs(sd)
    RR.atomic_write_json(os.path.join(sd, "meta.json"),
                         {"baseRef": "origin/main", "headSha": "abc123"})
    sid, reason = RR.mint_session_id(sd)
    assert reason is None
    meta = RR.read_json(os.path.join(sd, "meta.json"))[0]
    assert meta == {"baseRef": "origin/main", "headSha": "abc123", "sessionId": sid}


def test_mint_session_id_never_overwrites_an_unparseable_meta(tmp_path):
    sd = str(tmp_path / "session")
    os.makedirs(sd)
    path = os.path.join(sd, "meta.json")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    assert RR.mint_session_id(sd) == (None, "meta-unparseable")
    with open(path, encoding="utf-8") as fh:
        assert fh.read() == "{not json"


# --- sidecar ----------------------------------------------------------------------------------

def _sidecar(**over):
    fields = {
        "repoId": "zwrose/superheroes",
        "branch": "wh723-wo1",
        "headSha": "head-sha",
        "baseRef": "origin/main",
        "baseSha": "base-sha",
        "diffSha256": "diff-sha",
        "verdict": "pass",
        "certificationShape": "audited-chain",
        "receiptPath": "/tmp/receipt.json",
        "receiptSha256": RR.sha256_text("receipt"),
        "policySha256": "policy-sha",
        "sessionDir": "/tmp/session",
    }
    fields.update(over)
    return RR.build_sidecar(**fields)


def test_build_sidecar_pins_the_schema_and_every_key():
    obj = _sidecar()
    assert obj["schema"] == RR.SIDECAR_SCHEMA
    assert sorted(obj) == sorted(RR.SIDECAR_FIELDS)
    assert RR.validate_sidecar(obj) == (True, None)


def test_build_sidecar_rejects_an_unknown_field():
    with pytest.raises(ValueError):
        RR.build_sidecar(repoId="r", nonsense="x")


def test_build_sidecar_leaves_an_omitted_field_for_the_validator_to_refuse():
    obj = RR.build_sidecar(repoId="r")
    assert RR.validate_sidecar(obj) == (False, "empty-field:branch")


@pytest.mark.parametrize("obj,expected", [
    ("not a dict", "not-a-dict"),
    ({"schema": "handback-sidecar/2"}, "schema-unknown"),
])
def test_validate_sidecar_refusals(obj, expected):
    assert RR.validate_sidecar(obj) == (False, expected)


def test_validate_sidecar_refuses_a_missing_and_a_non_string_field():
    obj = _sidecar()
    del obj["branch"]
    assert RR.validate_sidecar(obj) == (False, "missing-field:branch")
    obj2 = _sidecar()
    obj2["headSha"] = 7
    assert RR.validate_sidecar(obj2) == (False, "non-string-field:headSha")


def test_sidecar_fresh_when_nothing_moved():
    obj = _sidecar()
    assert RR.sidecar_stale(obj, head_sha="head-sha", receipt_bytes=b"receipt",
                            session_dir="/tmp/session") == (False, None)


def test_sidecar_stale_when_head_moved():
    obj = _sidecar()
    assert RR.sidecar_stale(obj, head_sha="moved", receipt_bytes=b"receipt",
                            session_dir="/tmp/session") == (True, "head-moved")


def test_sidecar_stale_when_the_receipt_changed():
    obj = _sidecar()
    assert RR.sidecar_stale(obj, head_sha="head-sha", receipt_bytes=b"rewritten",
                            session_dir="/tmp/session") == (True, "receipt-changed")


def test_sidecar_stale_when_the_session_dir_differs():
    obj = _sidecar()
    assert RR.sidecar_stale(obj, head_sha="head-sha", receipt_bytes=b"receipt",
                            session_dir="/tmp/other") == (True, "session-dir-mismatch")


def test_sidecar_stale_when_the_sidecar_itself_is_invalid():
    obj = _sidecar()
    obj["schema"] = "handback-sidecar/2"
    stale, reason = RR.sidecar_stale(obj, head_sha="head-sha", receipt_bytes=b"receipt",
                                     session_dir="/tmp/session")
    assert stale is True and reason == "sidecar-invalid:schema-unknown"
