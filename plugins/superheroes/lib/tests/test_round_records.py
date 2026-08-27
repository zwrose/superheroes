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
import errno

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

def _session(tmp_path, name="session", **meta_extra):
    sd = str(tmp_path / name)
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


# --- roster_slots -----------------------------------------------------------------------------
# axis (first three tests): repeated roster keys expand to distinct occurrence slots without loss/overwrite; order preserved

def test_roster_slots_no_repeats_every_occurrence_is_zero_order_preserved():
    roster = ["a.py:1", "b.py:2", "c.py:3"]
    assert RR.roster_slots(roster) == [("a.py:1", 0), ("b.py:2", 0), ("c.py:3", 0)]


def test_roster_slots_repeated_key_twice_expands_occurrence_order_preserved():
    roster = ["a.py:1", "b.py:2", "a.py:1"]
    assert RR.roster_slots(roster) == [("a.py:1", 0), ("b.py:2", 0), ("a.py:1", 1)]


def test_roster_slots_repeated_key_three_times_interleaved():
    roster = ["a.py:1", "b.py:2", "a.py:1", "c.py:3", "a.py:1"]
    assert RR.roster_slots(roster) == [
        ("a.py:1", 0), ("b.py:2", 0), ("a.py:1", 1), ("c.py:3", 0), ("a.py:1", 2)]


@pytest.mark.parametrize("bad", [None, "seat", 3, {}])
def test_roster_slots_non_sequence_returns_empty_no_exception(bad):
    # axis: non-sequence roster input must fail-closed to empty expansion (no exception)
    assert RR.roster_slots(bad) == []


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


def test_guard_within_refuses_symlink_escape(tmp_path):
    """A symlink under the session dir whose target is outside must not pass the path fence."""
    sd = str(tmp_path / "session")
    os.makedirs(sd)
    outside = str(tmp_path / "outside")
    os.makedirs(outside)
    os.symlink(outside, os.path.join(sd, "round-1"))
    with pytest.raises(ValueError, match="escapes"):
        RR.round_dir(sd, 1)


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


def test_read_json_never_raises_census(tmp_path):
    """read_json returns a 2-tuple for every input class and never raises."""
    missing = str(tmp_path / "missing.json")
    directory = str(tmp_path / "adir")
    os.makedirs(directory)
    valid = str(tmp_path / "valid.json")
    with open(valid, "w", encoding="utf-8") as fh:
        fh.write('{"a":1}')
    malformed = str(tmp_path / "malformed.json")
    with open(malformed, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    invalid_utf8 = str(tmp_path / "bad_utf8.json")
    with open(invalid_utf8, "wb") as fh:
        fh.write(b"\xff\xfe")
    cases = (
        (missing, None, "missing"),
        (directory, None, "missing"),
        (valid, {"a": 1}, None),
        (malformed, None, "unparseable"),
        (invalid_utf8, None, "not-utf-8"),
    )
    for path, expected_obj, expected_err in cases:
        obj, err = RR.read_json(path)
        assert (obj, err) == (expected_obj, expected_err)


def test_mint_session_id_refuses_not_utf8_meta(tmp_path):
    sd = str(tmp_path / "session")
    os.makedirs(sd)
    meta_path = os.path.join(sd, "meta.json")
    with open(meta_path, "wb") as fh:
        fh.write(b"\xff\xfe")
    sid, reason = RR.mint_session_id(sd)
    assert sid is None and reason == "meta-unparseable"


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


def test_refusal_schema_unknown_when_schema_key_absent(tmp_path):
    sd = _session(tmp_path)
    env = _env()
    del env["schema"]
    _land(sd, env)
    out = _ingest(sd)
    assert out["reason"] == "schema-unknown"
    assert out["schema"] is None


def test_refusal_landing_torn_when_envelope_is_not_a_dict(tmp_path):
    sd = _session(tmp_path)
    path = _land(sd, _env())
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("[]")
    out = _ingest(sd)
    assert out["reason"] == "landing-torn"


def test_refusal_landing_torn_when_bare_payload_is_findings_array(tmp_path):
    sd = _session(tmp_path)
    skey = RR.storage_key(SEAT)
    stub_path = RR.envelope_stub_path(sd, 1, PHASE, skey, 1)
    os.makedirs(os.path.dirname(stub_path), exist_ok=True)
    RR.atomic_write_json(stub_path, _stub_header(sd))
    RR.atomic_write_json(RR.bare_payload_path(sd, 1, PHASE, skey, 1), [{"id": "f1"}])
    out = _ingest(sd)
    assert out["reason"] == "landing-torn"


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
    anchor = {"manifestSha256": "m" * 64, "orders": {RR.storage_key(SEAT): "different" * 8}}
    assert _ingest(sd, anchor=anchor)["reason"] == "manifest-anchor-mismatch"


def test_anchor_match_is_accepted(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _env(manifestSha256="m" * 64, orderSha256="o" * 64))
    anchor = {"manifestSha256": "m" * 64, "orders": {RR.storage_key(SEAT): "o" * 64}}
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


def test_sweep_reports_full_envelope_stray_as_stale_landing(tmp_path):
    sd = _session(tmp_path)
    stray = RR.landing_path(sd, 1, PHASE, "stray-seat", 1)
    RR.atomic_write_json(stray, _env(seat="stray-seat"))
    out = RR.sweep_landing(sd, 1, PHASE, current_attempt=1, roster=ROSTER)
    stale = [r for r in out if r.get("reason") == "stale-landing"]
    assert len(stale) == 1
    assert stale[0]["ok"] is False
    assert stale[0]["reason"] == "stale-landing"
    assert stale[0]["storageKey"] == "stray-seat"
    assert os.path.basename(stray) in stale[0]["landingPaths"]


def test_sweep_reports_bare_payload_stray_as_stale_landing(tmp_path):
    sd = _session(tmp_path)
    skey = "stray-seat"
    bare = RR.bare_payload_path(sd, 1, PHASE, skey, 1)
    RR.atomic_write_json(bare, {"findings": ["x"]})
    out = RR.sweep_landing(sd, 1, PHASE, current_attempt=1, roster=ROSTER)
    stale = [r for r in out if r.get("reason") == "stale-landing"]
    assert len(stale) == 1
    assert stale[0]["ok"] is False
    assert stale[0]["reason"] == "stale-landing"
    assert stale[0]["storageKey"] == skey
    assert os.path.basename(bare) in stale[0]["landingPaths"]


def test_sweep_dedupes_stray_both_shapes_per_storage_key(tmp_path):
    sd = _session(tmp_path)
    skey = "stray-seat"
    env_path = RR.landing_path(sd, 1, PHASE, skey, 1)
    bare_path = RR.bare_payload_path(sd, 1, PHASE, skey, 1)
    RR.atomic_write_json(env_path, _env(seat=skey))
    RR.atomic_write_json(bare_path, {"findings": ["x"]})
    out = RR.sweep_landing(sd, 1, PHASE, current_attempt=1, roster=ROSTER)
    stale = [r for r in out if r.get("reason") == "stale-landing"]
    assert len(stale) == 1
    assert set(stale[0]["landingPaths"]) == {os.path.basename(env_path), os.path.basename(bare_path)}


def test_sweep_journals_roster_seats_before_stale_landing_refusals(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _env(), seat=SEAT)
    stray_skey = "a-stale"  # sorts before RR.storage_key(SEAT); untiered sort would put stray first
    stray = RR.landing_path(sd, 1, PHASE, stray_skey, 1)
    RR.atomic_write_json(stray, _env(seat="orphan"))
    out = RR.sweep_landing(sd, 1, PHASE, current_attempt=1, roster=ROSTER)
    roster_results = [r for r in out if r.get("reason") != "stale-landing"]
    stale = [r for r in out if r.get("reason") == "stale-landing"]
    assert roster_results[0]["ok"] is True and roster_results[0]["seatKey"] == SEAT
    assert stale[0]["reason"] == "stale-landing"
    assert out.index(roster_results[0]) < out.index(stale[0])
    assert os.path.exists(roster_results[0]["storePath"])


def _dangling_symlink_inside_session(session_dir, path):
    """Dead symlink target inside session_dir — inside edge 1's _guard_within boundary."""
    target = os.path.join(session_dir, "no-such-in-session-target")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.lexists(path):
        os.remove(path)
    os.symlink(target, path)
    assert os.path.lexists(path) and not os.path.exists(path)


def _dangling_symlink_outside_session(session_dir, path):
    """Dead symlink target outside session_dir — refuses at path-build time (edge 1)."""
    outside = os.path.join(os.path.dirname(session_dir), "outside-no-such-target")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.lexists(path):
        os.remove(path)
    os.symlink(outside, path)
    assert os.path.lexists(path) and not os.path.exists(path)


def test_sweep_reports_dangling_roster_landing_symlink_as_landing_torn(tmp_path):
    """T1 — site 1: a roster slot whose landing is a dangling symlink is swept, not skipped."""
    sd = _session(tmp_path)
    lpath = RR.landing_path(sd, 1, PHASE, RR.storage_key(SEAT), 1)
    _dangling_symlink_inside_session(sd, lpath)
    out = RR.sweep_landing(sd, 1, PHASE, current_attempt=1, roster=ROSTER)
    slot_results = [r for r in out if r.get("seatKey") == SEAT]
    assert len(slot_results) == 1
    assert slot_results[0]["ok"] is False
    assert slot_results[0]["reason"] == "landing-torn"


def test_sweep_reports_dangling_bare_payload_landing_symlink_as_landing_torn(tmp_path):
    """site 1, bare arm: a roster slot whose BARE PAYLOAD landing is a dangling symlink is swept, not skipped."""
    sd = _session(tmp_path)
    bare = RR.bare_payload_path(sd, 1, PHASE, RR.storage_key(SEAT), 1)
    _dangling_symlink_inside_session(sd, bare)
    out = RR.sweep_landing(sd, 1, PHASE, current_attempt=1, roster=ROSTER)
    slot_results = [r for r in out if r.get("seatKey") == SEAT]
    assert len(slot_results) == 1
    assert slot_results[0]["ok"] is False
    assert slot_results[0]["reason"] == "landing-torn"


def test_ingest_refuses_dangling_symlink_store_entry(tmp_path):
    """T2 — site 2: a store entry that is a dangling symlink refuses store-exists, never clobbers."""
    sd = _session(tmp_path)
    _land(sd, _env())
    spath = RR.store_path(sd, 1, PHASE, RR.storage_key(SEAT), 1)
    _dangling_symlink_inside_session(sd, spath)
    out = _ingest(sd)
    assert out["ok"] is False
    assert out["reason"] == "store-exists"
    assert os.path.islink(spath)
    assert os.path.lexists(spath)


def test_sweep_reports_dangling_stray_landing_symlink_as_stale_landing(tmp_path):
    """T3 — site 4: a stray landing that is a dangling symlink matches real-stray vocabulary."""
    sd = _session(tmp_path)
    stray = RR.landing_path(sd, 1, PHASE, "stray-seat", 1)
    _dangling_symlink_inside_session(sd, stray)
    out = RR.sweep_landing(sd, 1, PHASE, current_attempt=1, roster=ROSTER)
    stale = [r for r in out if r.get("reason") == "stale-landing"]
    sd_real = _session(tmp_path, name="session-real-stray")
    real_stray = RR.landing_path(sd_real, 1, PHASE, "stray-seat", 1)
    RR.atomic_write_json(real_stray, _env(seat="stray-seat"))
    real_out = RR.sweep_landing(sd_real, 1, PHASE, current_attempt=1, roster=ROSTER)
    real_stale = [r for r in real_out if r.get("reason") == "stale-landing"]
    assert len(stale) == 1
    assert stale[0]["ok"] is False
    assert stale[0]["reason"] == "stale-landing"
    assert stale[0]["storageKey"] == "stray-seat"
    assert os.path.basename(stray) in stale[0]["landingPaths"]
    assert set(stale[0].keys()) == set(real_stale[0].keys())


def test_sweep_skips_real_directory_named_like_landing_file(tmp_path):
    """T3b — site 4: a real directory named like a landing file is still skipped silently."""
    sd = _session(tmp_path)
    skey = "stray-seat"
    ldir = RR.landing_dir(sd, 1, PHASE)
    os.makedirs(ldir, exist_ok=True)
    os.mkdir(os.path.join(ldir, "%s.a1.json" % skey))
    out = RR.sweep_landing(sd, 1, PHASE, current_attempt=1, roster=ROSTER)
    stale = [r for r in out if r.get("reason") == "stale-landing"]
    assert stale == []


def test_sweep_already_stored_when_store_file_is_unparseable_not_a_symlink(tmp_path):
    """T4 — site 3: readability is not the discriminator; a resolving store file is already-stored."""
    sd = _session(tmp_path)
    _land(sd, _env())
    spath = RR.store_path(sd, 1, PHASE, RR.storage_key(SEAT), 1)
    os.makedirs(os.path.dirname(spath), exist_ok=True)
    bad_bytes = b"{not valid json"
    with open(spath, "wb") as fh:
        fh.write(bad_bytes)
    out = RR.sweep_landing(sd, 1, PHASE, current_attempt=1, roster=ROSTER)
    slot_results = [r for r in out if r.get("seatKey") == SEAT]
    assert len(slot_results) == 1
    assert slot_results[0]["ok"] is True
    assert slot_results[0]["reason"] == "already-stored"
    with open(spath, "rb") as fh:
        assert fh.read() == bad_bytes


def test_sweep_refuses_dangling_symlink_store_entry_not_already_stored(tmp_path):
    """T4b — site 3: a dangling store entry refuses store-exists, never a false already-stored."""
    sd = _session(tmp_path)
    _land(sd, _env())
    spath = RR.store_path(sd, 1, PHASE, RR.storage_key(SEAT), 1)
    _dangling_symlink_inside_session(sd, spath)
    out = RR.sweep_landing(sd, 1, PHASE, current_attempt=1, roster=ROSTER)
    slot_results = [r for r in out if r.get("seatKey") == SEAT]
    assert len(slot_results) == 1
    assert slot_results[0]["ok"] is False
    assert slot_results[0]["reason"] == "store-exists"
    assert spath in slot_results[0]["message"]
    assert not any(r.get("reason") == "already-stored" for r in slot_results)


def test_sweep_refuses_out_of_session_dangling_landing_symlink_at_path_build(tmp_path):
    """T5 — edge 1: out-of-session dangling landing refuses bad-argument from sweep_landing."""
    sd = _session(tmp_path)
    lpath = RR.landing_path(sd, 1, PHASE, RR.storage_key(SEAT), 1)
    _dangling_symlink_outside_session(sd, lpath)
    out = RR.sweep_landing(sd, 1, PHASE, current_attempt=1, roster=ROSTER)
    bad = [r for r in out if r.get("reason") == "bad-argument" and r.get("seatKey") == SEAT]
    assert len(bad) == 1


def test_sweep_refuses_out_of_session_dangling_bare_payload_symlink_at_path_build(tmp_path):
    """T5b — edge 1, bare arm: out-of-session dangling bare payload refuses bad-argument."""
    sd = _session(tmp_path)
    bare = RR.bare_payload_path(sd, 1, PHASE, RR.storage_key(SEAT), 1)
    _dangling_symlink_outside_session(sd, bare)
    out = RR.sweep_landing(sd, 1, PHASE, current_attempt=1, roster=ROSTER)
    bad = [r for r in out if r.get("reason") == "bad-argument" and r.get("seatKey") == SEAT]
    assert len(bad) == 1


def test_probe_store_entry_outcomes(tmp_path, monkeypatch):
    """_probe_store_entry: present, absent (ENOENT), and indeterminate (other errno)."""
    present_path = tmp_path / "present.json"
    present_path.write_text("{}", encoding="utf-8")
    absent_path = tmp_path / "missing.json"
    indeterminate_path = tmp_path / "blocked.json"

    present, refusal = RR._probe_store_entry(str(present_path))
    assert present is True and refusal is None

    present, refusal = RR._probe_store_entry(str(absent_path))
    assert present is False and refusal is None

    real_lstat = os.lstat

    def deny_lstat(path):
        if path == str(indeterminate_path):
            raise OSError(errno.EACCES, "permission denied")
        return real_lstat(path)

    monkeypatch.setattr(RR.os, "lstat", deny_lstat)
    present, refusal = RR._probe_store_entry(str(indeterminate_path))
    assert present is None
    assert refusal["ok"] is False
    assert refusal["reason"] == "store-exists"
    assert "indeterminate" in refusal["message"]


def test_ingest_refuses_indeterminate_store_probe(tmp_path, monkeypatch):
    """Indeterminate store probe refuses store-exists rather than clobbering."""
    sd = _session(tmp_path)
    _land(sd, _env())
    spath = RR.store_path(sd, 1, PHASE, RR.storage_key(SEAT), 1)
    real_lstat = RR.os.lstat

    def deny_store_lstat(path):
        if path == spath:
            raise OSError(errno.EACCES, "permission denied")
        return real_lstat(path)

    monkeypatch.setattr(RR.os, "lstat", deny_store_lstat)
    out = _ingest(sd)
    assert out["ok"] is False
    assert out["reason"] == "store-exists"
    assert "indeterminate" in out["message"]


def test_sweep_refuses_indeterminate_store_probe(tmp_path, monkeypatch):
    """Sweep decorates an indeterminate store probe and never reports already-stored."""
    sd = _session(tmp_path)
    _land(sd, _env())
    spath = RR.store_path(sd, 1, PHASE, RR.storage_key(SEAT), 1)
    real_lstat = RR.os.lstat

    def deny_store_lstat(path):
        if path == spath:
            raise OSError(errno.EACCES, "permission denied")
        return real_lstat(path)

    monkeypatch.setattr(RR.os, "lstat", deny_store_lstat)
    out = RR.sweep_landing(sd, 1, PHASE, current_attempt=1, roster=ROSTER)
    slot_results = [r for r in out if r.get("seatKey") == SEAT]
    assert len(slot_results) == 1
    assert slot_results[0]["ok"] is False
    assert slot_results[0]["reason"] == "store-exists"
    assert "indeterminate" in slot_results[0]["message"]
    assert not any(r.get("reason") == "already-stored" for r in out)


def test_ingest_refuses_enotdir_store_directory_ancestor(tmp_path):
    """ENOTDIR on the store path refuses store-exists rather than treating the entry as absent."""
    sd = _session(tmp_path)
    _land(sd, _env())
    spath = RR.store_path(sd, 1, PHASE, RR.storage_key(SEAT), 1)
    store_parent = os.path.dirname(spath)
    os.makedirs(os.path.dirname(store_parent), exist_ok=True)
    with open(store_parent, "w", encoding="utf-8") as fh:
        fh.write("not a directory")
    out = _ingest(sd)
    assert out["ok"] is False
    assert out["reason"] == "store-exists"
    assert "indeterminate" in out["message"]
    assert not os.path.lexists(spath)


def test_ingest_refuses_out_of_session_dangling_store_symlink_at_path_build(tmp_path):
    """T6 — edge 1: out-of-session dangling store entry refuses invalid-path from ingest_landing."""
    sd = _session(tmp_path)
    _land(sd, _env())
    spath = RR.store_path(sd, 1, PHASE, RR.storage_key(SEAT), 1)
    _dangling_symlink_outside_session(sd, spath)
    out = _ingest(sd)
    assert out["reason"] == "invalid-path"


def test_round_records_presence_checks_use_entry_not_target():
    """T7 — census: exists/isfile follow the symlink target; presence here is about the entry."""
    with open(RR.__file__, encoding="utf-8") as fh:
        src = fh.read()
    assert "os.path.isfile(" not in src
    assert "os.path.exists(" not in src


def test_ingest_unknown_seat_unchanged_for_addressed_off_roster_seat(tmp_path):
    sd = _session(tmp_path)
    out = _ingest(sd, seat="src/z.py:9")
    assert out["reason"] == "unknown-seat"


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
    out = RR.reconcile(sd, 1, PHASE, [])
    assert out["ingestNow"] == []
    assert [e["payloadSha256"] for e in out["reappend"]] == [env["payloadSha256"]]
    assert out["journalOrphan"] == []


def test_reconcile_reports_a_journal_identity_with_no_store_file_as_orphan(tmp_path):
    sd = _session(tmp_path)
    env = _env()
    _land(sd, env)
    assert _ingest(sd)["ok"] is True
    ghost = RR.record_identity(PHASE, OTHER_SEAT, 0, 1)
    out = RR.reconcile(sd, 1, PHASE, [RR.record_identity(PHASE, SEAT, 0, 1), ghost])
    assert out["reappend"] == []
    assert out["journalOrphan"] == [ghost]


def test_reconcile_does_not_orphan_a_superseded_payload_hash(tmp_path):
    """Identity-based reconcile: the journal may still carry the pre-supersede hash, but the slot
    is satisfied by the store file — no `journalOrphan`."""
    sd = _session(tmp_path)
    first = _env()
    _land(sd, first)
    assert _ingest(sd)["ok"] is True
    second = _env(payload={"findings": ["replaced"]})
    _land(sd, second)
    assert _ingest(sd, supersede=True, expect_sha256=first["payloadSha256"])["ok"] is True
    journal = [
        RR.record_identity(PHASE, SEAT, 0, 1),
        {"phase": PHASE, "seat": SEAT, "occurrence": 0, "attempt": 1,
         "payloadSha256": first["payloadSha256"]},
    ]
    out = RR.reconcile(sd, 1, PHASE, journal)
    assert out["journalOrphan"] == []
    assert len(out["reappend"]) == 1
    stored, _err = RR.read_json(out["reappend"][0]["path"])
    assert out["reappend"][0]["payloadSha256"] == stored["payloadSha256"]


def test_reconcile_distinguishes_identical_payloads_on_different_seats(tmp_path):
    """Content hashes are not identities — a journal append for seat B must not be masked by seat A
    carrying the same payload."""
    sd = _session(tmp_path)
    shared = {"findings": []}
    env_a = _env(payload=shared, seat=SEAT)
    env_b = _env(payload=shared, seat=OTHER_SEAT)
    _land(sd, env_a)
    _land(sd, env_b, seat=OTHER_SEAT)
    assert _ingest(sd, seat=SEAT)["ok"] is True
    assert _ingest(sd, seat=OTHER_SEAT)["ok"] is True
    out = RR.reconcile(sd, 1, PHASE, [RR.record_identity(PHASE, SEAT, 0, 1)])
    assert out["journalOrphan"] == []
    assert len(out["reappend"]) == 1
    assert out["reappend"][0]["recordIdentity"]["seat"] == OTHER_SEAT


def test_reconcile_reappends_when_the_store_revision_is_newer_than_the_journal(tmp_path):
    """Crash between supersede write and journal append: slot identity is satisfied but the store
    token moved — reconcile must reappend the newer revision."""
    sd = _session(tmp_path)
    first = _env()
    _land(sd, first)
    assert _ingest(sd)["ok"] is True
    second = _env(payload={"findings": ["replaced"]})
    _land(sd, second)
    spath = _ingest(sd, supersede=True, expect_sha256=first["payloadSha256"])["storePath"]
    stored, _err = RR.read_json(spath)
    assert stored["payloadSha256"] != first["payloadSha256"]
    journal = [RR.record_identity(PHASE, SEAT, 0, 1)]
    journal[0]["payloadSha256"] = first["payloadSha256"]
    out = RR.reconcile(sd, 1, PHASE, journal)
    assert out["journalOrphan"] == []
    assert len(out["reappend"]) == 1
    assert out["reappend"][0]["payloadSha256"] == stored["payloadSha256"]


def test_head_diff_store_path_valid_requires_exact_session_store_path(tmp_path):
    sd = _session(tmp_path)
    expected = RR.head_diff_store_path(sd, 1, PHASE, SEAT, 1)
    assert RR.head_diff_store_path_valid(expected, sd, 1, PHASE, SEAT, 1) is True
    lookalike = os.path.join("/attacker", "round-1", "seats", PHASE,
                             "%s.a1.headdiff" % RR.storage_key(SEAT))
    assert RR.head_diff_store_path_valid(lookalike, sd, 1, PHASE, SEAT, 1) is False


def test_reconcile_keeps_the_store_file_authoritative(tmp_path):
    # The journal is the log: reconcile never deletes or rewrites a store file to match it.
    sd = _session(tmp_path)
    env = _env()
    _land(sd, env)
    spath = _ingest(sd)["storePath"]
    with open(spath, "rb") as fh:
        before = fh.read()
    RR.reconcile(sd, 1, PHASE, [])
    with open(spath, "rb") as fh:
        assert fh.read() == before


# --- session lock -----------------------------------------------------------------------------

def test_session_lock_is_mutually_exclusive(tmp_path):
    """A lockfile owned by another process still refuses acquisition — re-entrancy is not 'always allow'."""
    sd = _session(tmp_path)
    RR.atomic_write_json(RR.session_lock_path(sd),
                         {"pid": 424242, "createdAt": "2026-08-07T00:00:00"})
    with pytest.raises(RR.SessionLockHeld) as exc:
        with RR.session_lock(sd):
            pass
    assert exc.value.pid == 424242
    assert exc.value.created_at == "2026-08-07T00:00:00"


def test_session_lock_is_reentrant_within_one_process(tmp_path):
    sd = _session(tmp_path)
    lock_path = RR.session_lock_path(sd)
    with RR.session_lock(sd):
        assert os.path.exists(lock_path)
        with RR.session_lock(sd):
            assert os.path.exists(lock_path)
    assert not os.path.exists(lock_path)


def test_session_lock_reentrant_exception_releases_outer(tmp_path):
    sd = _session(tmp_path)
    lock_path = RR.session_lock_path(sd)
    with pytest.raises(RuntimeError):
        with RR.session_lock(sd):
            with RR.session_lock(sd):
                raise RuntimeError("boom")
    assert not os.path.exists(lock_path)
    with RR.session_lock(sd):
        pass


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


def _validate(sd, seat=SEAT, attempt=1, current=1, rnd=1, phase=PHASE, **kw):
    return RR.validate_landing(sd, rnd, phase, seat, attempt,
                               current_attempt=current, roster=ROSTER, **kw)


# --- validate_landing: refusal tokens write nothing -------------------------------------------

@pytest.mark.parametrize("reason,setup", [
    ("bootstrap-required", lambda sd: None),
    ("reserved-seat-name", lambda sd: None),
    ("unknown-seat", lambda sd: None),
    ("stale-attempt", lambda sd: _land(sd, _env())),
    ("landing-missing", lambda sd: None),
    ("attempt-mismatch", lambda sd: _land(sd, _env(attempt=1), attempt=2)),
    ("session-mismatch", lambda sd: _land(sd, _env(session="a" * 32))),
    ("phase-mismatch", lambda sd: _land(sd, _env(phase="dispatch-audits"))),
    ("round-mismatch", lambda sd: _land(sd, _env(round=2))),
    ("schema-unknown", lambda sd: _land(sd, _env(schema="seat-result/2"))),
    ("missing-reason", lambda sd: _land(sd, _missing_env(reason="vibes"))),
    ("manifest-anchor-mismatch",
     lambda sd: _land(sd, _env(manifestSha256="m" * 64, orderSha256="o" * 64))),
    ("manifest-anchor-unanchored",
     lambda sd: _land(sd, _env(manifestSha256="m" * 64, orderSha256="o" * 64))),
    ("store-exists", lambda sd: (_land(sd, _env()), _ingest(sd))),
    ("cas-expect-required", lambda sd: (_land(sd, _env()), _ingest(sd), _land(sd, _env()))),
    ("cas-mismatch", lambda sd: (_land(sd, _env()), _ingest(sd), _land(sd, _env()))),
    ("invalid-path", lambda sd: None),
])
def test_validate_landing_refusal_writes_nothing(tmp_path, reason, setup):
    if reason == "bootstrap-required":
        sd = str(tmp_path / "bare")
        os.makedirs(sd)
    else:
        sd = _session(tmp_path)
    setup(sd)
    kwargs = {}
    seat = SEAT
    attempt = 1
    current = 1
    phase = PHASE
    if reason == "reserved-seat-name":
        seat = "_dispatch"
    elif reason == "unknown-seat":
        seat = "src/z.py:9"
    elif reason == "stale-attempt":
        current = 2
    elif reason == "attempt-mismatch":
        attempt = 2
        current = 2
    elif reason == "invalid-path":
        phase = "../../etc"
    elif reason == "manifest-anchor-mismatch":
        kwargs["anchor"] = {"manifestSha256": "m" * 64,
                              "orders": {RR.storage_key(SEAT): "different" * 8}}
    elif reason == "manifest-anchor-unanchored":
        kwargs["anchor"] = None
    elif reason == "store-exists":
        pass
    elif reason == "cas-expect-required":
        kwargs["supersede"] = True
    elif reason == "cas-mismatch":
        kwargs["supersede"] = True
        kwargs["expect_sha256"] = "0" * 64
    plan, refusal = _validate(sd, seat=seat, attempt=attempt, current=current, phase=phase, **kwargs)
    assert plan is None
    assert refusal is not None and refusal["reason"] == reason
    if reason in ("invalid-path", "reserved-seat-name", "unknown-seat", "bootstrap-required"):
        return
    check_seat = SEAT if seat == "_dispatch" else seat
    try:
        spath = RR.store_path(sd, 1, PHASE, RR.storage_key(check_seat, 0), attempt)
    except ValueError:
        return
    if reason in ("store-exists", "cas-expect-required", "cas-mismatch"):
        assert os.path.exists(spath)
    else:
        assert not os.path.exists(spath)


def test_validate_landing_refusal_landing_torn_payload(tmp_path):
    sd = _session(tmp_path)
    env = _env(payload={"findings": ["f1", "f2", "f3"]})
    torn = dict(env)
    torn["payload"] = {"findings": ["f1"]}
    _land(sd, torn)
    plan, refusal = _validate(sd)
    assert plan is None and refusal["reason"] == "landing-torn"
    assert not os.path.exists(RR.store_path(sd, 1, PHASE, RR.storage_key(SEAT), 1))


def test_validate_landing_refusal_landing_torn_unparseable(tmp_path):
    sd = _session(tmp_path)
    path = _land(sd, _env())
    with open(path, "w", encoding="utf-8") as fh:
        fh.write('{"schema": "seat-result/1", "payl')
    plan, refusal = _validate(sd)
    assert plan is None and refusal["reason"] == "landing-torn"
    assert not os.path.exists(RR.store_path(sd, 1, PHASE, RR.storage_key(SEAT), 1))


def test_validate_landing_refusal_seat_mismatch(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _env())
    assert _ingest(sd)["ok"] is True
    swapped_path = RR.landing_path(sd, 1, PHASE, RR.storage_key(OTHER_SEAT), 1)
    RR.atomic_write_json(swapped_path, _env(seat=SEAT))
    plan, refusal = _validate(sd, seat=OTHER_SEAT)
    assert plan is None and refusal["reason"] == "seat-mismatch"
    assert not os.path.exists(RR.store_path(sd, 1, PHASE, RR.storage_key(OTHER_SEAT), 1))


def test_validate_landing_refusal_unknown_occurrence(tmp_path):
    sd = _session(tmp_path)
    plan, refusal = _validate(sd, occurrence=1)
    assert plan is None and refusal["reason"] == "unknown-occurrence"
    assert not os.path.exists(RR.store_path(sd, 1, PHASE, RR.storage_key(SEAT, 1), 1))


def test_validate_landing_refusal_occurrence_mismatch(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _env(occurrence=1))
    plan, refusal = _validate(sd, occurrence=0)
    assert plan is None and refusal["reason"] == "occurrence-mismatch"
    assert not os.path.exists(RR.store_path(sd, 1, PHASE, RR.storage_key(SEAT), 1))


def test_validate_landing_refusal_bad_argument(tmp_path):
    sd = _session(tmp_path)
    plan, refusal = RR.validate_landing(sd, 1, PHASE, SEAT, 1,
                                        current_attempt=1, roster=ROSTER, occurrence=-1)
    assert plan is None and refusal["reason"] == "bad-argument"
    assert not os.path.exists(RR.store_path(sd, 1, PHASE, RR.storage_key(SEAT), 1))


def test_validate_landing_happy_path_writes_nothing_and_matches_ingest_bytes(tmp_path):
    sd = _session(tmp_path)
    env = _env()
    _land(sd, env)
    plan, refusal = _validate(sd)
    assert refusal is None and plan is not None
    spath = plan["storePath"]
    assert not os.path.exists(spath)
    ingest_out = _ingest(sd)
    assert ingest_out["ok"] is True
    with open(spath, "rb") as fh:
        direct_bytes = fh.read()
    os.remove(spath)
    RR.atomic_write_json(plan["storePath"], plan["envelope"])
    with open(spath, "rb") as fh:
        validate_bytes = fh.read()
    assert validate_bytes == direct_bytes


def test_validate_landing_supersede_plan_and_cas_mismatch_preserves_store(tmp_path):
    sd = _session(tmp_path)
    first = _env()
    _land(sd, first)
    assert _ingest(sd)["ok"] is True
    spath = RR.store_path(sd, 1, PHASE, RR.storage_key(SEAT), 1)
    with open(spath, "rb") as fh:
        before = fh.read()
    second = _env(payload={"findings": ["f1", "f2"]})
    _land(sd, second)
    plan, refusal = _validate(sd, supersede=True, expect_sha256=first["payloadSha256"])
    assert refusal is None and plan["superseded"] is True
    with open(spath, "rb") as fh:
        assert fh.read() == before
    _, cas_refusal = _validate(sd, supersede=True, expect_sha256="0" * 64)
    assert cas_refusal["reason"] == "cas-mismatch"
    with open(spath, "rb") as fh:
        assert fh.read() == before


# --- finding 1: seat-mismatch -----------------------------------------------------------------

def test_refusal_seat_mismatch_before_store(tmp_path):
    """An envelope whose embedded seat disagrees with the addressed slot is refused with nothing stored."""
    sd = _session(tmp_path)
    _land(sd, _env())
    assert _ingest(sd)["ok"] is True
    swapped_path = RR.landing_path(sd, 1, PHASE, RR.storage_key(OTHER_SEAT), 1)
    RR.atomic_write_json(swapped_path, _env(seat=SEAT))
    refused = _ingest(sd, seat=OTHER_SEAT)
    assert refused["ok"] is False and refused["reason"] == "seat-mismatch"
    assert refused["addressedSeat"] == OTHER_SEAT
    assert refused["envelopeSeat"] == SEAT
    assert not os.path.exists(RR.store_path(sd, 1, PHASE, RR.storage_key(OTHER_SEAT), 1))


# --- finding 4: seat-missing CAS token --------------------------------------------------------

def test_seat_missing_supersede_uses_the_schema_cas_token(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _missing_env())
    assert _ingest(sd)["ok"] is True
    _land(sd, _env())
    assert _ingest(sd, supersede=True)["reason"] == "cas-expect-required"
    out = _ingest(sd, supersede=True, expect_sha256=RR.MISSING_CAS_TOKEN)
    assert out["ok"] is True and out["superseded"] is True
    stored, _err = RR.read_json(out["storePath"])
    assert stored["schema"] == RR.SEAT_RESULT_SCHEMA


# --- WO-6: per-slot order anchors and dual landing shapes ------------------------------------

def _stub_header(sd, seat=SEAT, order_sha="o" * 64, manifest_sha="m" * 64, attempt=1):
    return {
        "schema": RR.SEAT_RESULT_SCHEMA,
        "session": SESSION,
        "round": 1,
        "phase": PHASE,
        "seat": seat,
        "attempt": attempt,
        "vendor": "claude",
        "model": "sonnet-5",
        "dispatchRef": manifest_sha,
        "orderSha256": order_sha,
        "manifestSha256": manifest_sha,
    }


def test_two_slots_sharing_a_seat_key_bind_distinct_order_hashes(tmp_path):
    """Per-slot anchor binding — R6 closure proof."""
    sd = _session(tmp_path)
    seat = SEAT
    roster = [seat, seat]
    skey0 = RR.storage_key(seat, 0)
    skey1 = RR.storage_key(seat, 1)
    anchor = {"manifestSha256": "m" * 64,
              "orders": {skey0: "a" * 64, skey1: "b" * 64}}
    payload0 = {"findings": ["slot0"]}
    payload1 = {"findings": ["slot1"]}
    for occurrence, skey, order_sha, payload in (
            (0, skey0, "a" * 64, payload0), (1, skey1, "b" * 64, payload1)):
        stub_path = RR.envelope_stub_path(sd, 1, PHASE, skey, 1)
        os.makedirs(os.path.dirname(stub_path), exist_ok=True)
        RR.atomic_write_json(stub_path, _stub_header(sd, order_sha=order_sha))
        RR.atomic_write_json(RR.bare_payload_path(sd, 1, PHASE, skey, 1), payload)
        out = RR.ingest_landing(sd, 1, PHASE, seat, 1, current_attempt=1, roster=roster,
                                anchor=anchor, occurrence=occurrence)
        assert out["ok"] is True, out
        stored, _ = RR.read_json(out["storePath"])
        assert stored["orderSha256"] == order_sha
        assert stored["payloadHashSource"] == "driver-computed"


def test_refusal_not_emitted_against_real_anchor(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _env(orderSha256=RR.NOT_EMITTED, manifestSha256="m" * 64))
    anchor = {"manifestSha256": "m" * 64, "orders": {RR.storage_key(SEAT): "o" * 64}}
    assert _ingest(sd, anchor=anchor)["reason"] == "manifest-anchor-mismatch"


def test_bare_key_fallback_is_legacy_only(tmp_path):
    """A/B — a real bare-key hash does not satisfy a slot with no per-slot entry."""
    manifest_sha = "m" * 64
    real_hash = "o" * 64
    # A: per-slot entry present — ingest accepts
    sd = _session(tmp_path, name="per-slot")
    anchor_ok = {"manifestSha256": manifest_sha,
                 "orders": {RR.storage_key(SEAT): real_hash}}
    _land(sd, _env(manifestSha256=manifest_sha, orderSha256=real_hash))
    assert _ingest(sd, anchor=anchor_ok)["ok"] is True
    # B: only a bare-key real hash — no per-slot entry, fallback must not bind
    sd2 = _session(tmp_path, name="bare-key")
    anchor_bad = {"manifestSha256": manifest_sha, "orders": {SEAT: real_hash}}
    _land(sd2, _env(manifestSha256=manifest_sha, orderSha256=real_hash))
    assert _ingest(sd2, anchor=anchor_bad)["reason"] == "manifest-anchor-mismatch"


def test_legacy_bare_key_not_emitted_accepted(tmp_path):
    sd = _session(tmp_path)
    anchor = {"manifestSha256": RR.NOT_EMITTED, "orders": {SEAT: RR.NOT_EMITTED}}
    _land(sd, _env())
    assert _ingest(sd, anchor=anchor)["ok"] is True


def test_legacy_bare_key_not_emitted_refuses_real_envelope_hash(tmp_path):
    sd = _session(tmp_path)
    manifest_sha = "m" * 64
    anchor = {"manifestSha256": manifest_sha, "orders": {SEAT: RR.NOT_EMITTED}}
    _land(sd, _env(manifestSha256=manifest_sha, orderSha256="o" * 64))
    assert _ingest(sd, anchor=anchor)["reason"] == "manifest-anchor-mismatch"


def test_refusal_landing_ambiguous_when_both_shapes_present(tmp_path):
    sd = _session(tmp_path)
    skey = RR.storage_key(SEAT)
    _land(sd, _env())
    RR.atomic_write_json(RR.bare_payload_path(sd, 1, PHASE, skey, 1), {"findings": []})
    assert _ingest(sd)["reason"] == "landing-ambiguous"


def test_refusal_envelope_stub_missing_for_bare_payload(tmp_path):
    sd = _session(tmp_path)
    skey = RR.storage_key(SEAT)
    RR.atomic_write_json(RR.bare_payload_path(sd, 1, PHASE, skey, 1), {"findings": []})
    assert _ingest(sd)["reason"] == "envelope-stub-missing"


def test_bare_payload_ingests_with_driver_computed_hash_source(tmp_path):
    sd = _session(tmp_path)
    skey = RR.storage_key(SEAT)
    order_sha = "o" * 64
    manifest_sha = "m" * 64
    payload = {"findings": ["x"]}
    stub_path = RR.envelope_stub_path(sd, 1, PHASE, skey, 1)
    os.makedirs(os.path.dirname(stub_path), exist_ok=True)
    RR.atomic_write_json(stub_path, _stub_header(sd, order_sha=order_sha,
                                                 manifest_sha=manifest_sha))
    RR.atomic_write_json(RR.bare_payload_path(sd, 1, PHASE, skey, 1), payload)
    anchor = {"manifestSha256": manifest_sha, "orders": {skey: order_sha}}
    out = _ingest(sd, anchor=anchor)
    assert out["ok"] is True
    stored, _ = RR.read_json(out["storePath"])
    assert stored["payloadHashSource"] == "driver-computed"
    assert stored["payloadSha256"] == RR.payload_sha256(payload)


def test_full_envelope_records_seat_declared_hash_source(tmp_path):
    sd = _session(tmp_path)
    _land(sd, _env())
    out = _ingest(sd)
    assert out["ok"] is True
    stored, _ = RR.read_json(out["storePath"])
    assert stored.get("payloadHashSource") == "seat-declared"


# --- finding 7: phase-name drift guard --------------------------------------------------------

def test_phase_name_constants_agree_across_modules():
    import round_adapters as RA
    import round_driver as RD
    import round_phases as RP
    shared = (
        ("P_PANEL", RP.P_PANEL),
        ("P_VERIFIERS", RP.P_VERIFIERS),
        ("P_SYNTHESIS", RP.P_SYNTHESIS),
        ("P_AUDITS", RP.P_AUDITS),
        ("P_SCOPED", RP.P_SCOPED),
        ("P_GAPSWEEP", RP.P_GAPSWEEP),
        ("P_VERIFY", RP.P_VERIFY),
        ("P_FIXER", RP.P_FIXER),
    )
    for attr, expected in shared:
        assert getattr(RD, attr) == expected == getattr(RA, attr)
    for attr in ("P_JUDGMENT", "P_STALL", "P_TERMINAL"):
        assert getattr(RD, attr) == getattr(RP, attr)
    assert RR._PANEL_PHASE_DIRNAME == RP.P_PANEL

