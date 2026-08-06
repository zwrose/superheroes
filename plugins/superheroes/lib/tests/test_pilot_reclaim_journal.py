"""Tests for pilot reclaim journal rotation and segment retention."""
import json
import os
import shutil
import stat
import sys
import tempfile

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_journal as pj  # noqa: E402
import pilot_lifecycle as pl  # noqa: E402
import pilot_reclaim as pr  # noqa: E402

_NOW = "2026-08-02T12:00:00Z"
_NOW2 = "2026-08-02T12:01:00Z"
_SLOT = "slot-a"
_SLOT_REF = "slot-a@1"
_ACCOUNTS = [{"account": "owner", "role": "resource-owner"}]


def _slots_dir(tmp_path):
    path = os.path.join(str(tmp_path), "slots")
    os.makedirs(path)
    return path


def _journal_path(slots_dir, slot, name="journal.ndjson"):
    return os.path.join(slots_dir, slot, name)


def _create_slot(slots_dir, slot=_SLOT, now=_NOW):
    result = pl.create_slot(slots_dir, slot, _ACCOUNTS, now=now)
    assert result["ok"] is True
    return result["record"]


def _mutate_to_state(slots_dir, slot, target_state, now=_NOW):
    _create_slot(slots_dir, slot)

    def _to_provisioned(rec):
        return pl.transition(rec, pl.STATE_PROVISIONED, now=now)

    def _to_occupied(rec):
        return pl.transition(
            pl.transition(rec, pl.STATE_PROVISIONED, now=now),
            pl.STATE_OCCUPIED,
            now=now,
        )

    def _to_released(rec):
        rec = pl.transition(rec, pl.STATE_PROVISIONED, now=now)
        rec = pl.transition(rec, pl.STATE_OCCUPIED, now=now)
        return pl.transition(rec, pl.STATE_RELEASED, now=now)

    def _to_failed(rec):
        return pl.transition(rec, pl.STATE_FAILED, now=now)

    def _to_retired(rec):
        rec = pl.transition(rec, pl.STATE_FAILED, now=now)
        return pl.transition(rec, pl.STATE_RETIRED, now=now)

    handlers = {
        pl.STATE_PROVISIONING: lambda rec: rec,
        pl.STATE_PROVISIONED: _to_provisioned,
        pl.STATE_OCCUPIED: _to_occupied,
        pl.STATE_RELEASED: _to_released,
        pl.STATE_FAILED: _to_failed,
        pl.STATE_RETIRED: _to_retired,
    }
    result = pl.mutate(slots_dir, slot, handlers[target_state])
    assert result["ok"] is True
    return result["record"]


def _append_paired_effect(journal_path, *, slot_ref=_SLOT_REF, effect_id, kind=pj.KIND_APP_STARTED):
    begin = pj.begin_effect(
        journal_path, slot_ref=slot_ref, kind=kind, at=_NOW, effect_id=effect_id,
    )
    assert begin["ok"] is True
    end = pj.end_effect(
        journal_path, slot_ref=slot_ref, effect_id=effect_id, kind=kind,
        outcome=pj.OUTCOME_APPLIED, at=_NOW2,
    )
    assert end["ok"] is True


def _min_pairs():
    """Paired begin/end records produce two journal lines each."""
    return pr.ROTATE_MIN_RECORDS // 2


def _fill_journal(journal_path, pair_count, *, slot_ref=_SLOT_REF, prefix="eff"):
    for i in range(pair_count):
        _append_paired_effect(
            journal_path,
            slot_ref=slot_ref,
            effect_id="%s-%04d" % (prefix, i),
        )


def _setup_released_with_journal(slots_dir, pair_count=None, slot=_SLOT):
    if pair_count is None:
        pair_count = _min_pairs()
    record = _mutate_to_state(slots_dir, slot, pl.STATE_RELEASED)
    journal = _journal_path(slots_dir, slot)
    _fill_journal(journal, pair_count, slot_ref="%s@%d" % (slot, record["generation"]))
    return record, journal


@pytest.mark.parametrize("slots_dir_path", [None, "", 123, []])
def test_rotate_journal_rejects_invalid_slots_dir(slots_dir_path):
    journal = os.path.join(tempfile.gettempdir(), "journal.ndjson")
    result = pr.rotate_journal(slots_dir_path, _SLOT, journal, now=_NOW)
    assert result == {
        "ok": False,
        "reason": pr.REASON_SLOTS_DIR_INVALID,
        "rotated": False,
        "segmentPath": None,
    }


@pytest.mark.parametrize("slot", ["", "BAD SLOT", None, 1])
def test_rotate_journal_rejects_invalid_slot(slot, tmp_path):
    slots_dir = _slots_dir(tmp_path)
    journal = _journal_path(slots_dir, _SLOT)
    result = pr.rotate_journal(slots_dir, slot, journal, now=_NOW)
    assert result["ok"] is False
    assert result["reason"] == pr.REASON_SLOT_INVALID
    assert result["rotated"] is False


@pytest.mark.parametrize("now", ["", "not-a-date", "2026-01-01T00:00:00", None])
def test_rotate_journal_rejects_invalid_now(now, tmp_path):
    slots_dir = _slots_dir(tmp_path)
    journal = _journal_path(slots_dir, _SLOT)
    result = pr.rotate_journal(slots_dir, _SLOT, journal, now=now)
    assert result == {
        "ok": False,
        "reason": pr.REASON_NOW_INVALID,
        "rotated": False,
        "segmentPath": None,
    }


@pytest.mark.parametrize("journal_path", [None, "", "relative/journal.ndjson", 42])
def test_rotate_journal_rejects_invalid_journal_path(journal_path, tmp_path):
    slots_dir = _slots_dir(tmp_path)
    result = pr.rotate_journal(slots_dir, _SLOT, journal_path, now=_NOW)
    assert result["ok"] is False
    assert result["reason"] == pr.REASON_JOURNAL_PATH_INVALID
    assert result["rotated"] is False


def test_rotate_journal_rejects_symlink_journal_path(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    _mutate_to_state(slots_dir, _SLOT, pl.STATE_RELEASED)
    slot_dir = os.path.join(slots_dir, _SLOT)
    real_journal = os.path.join(slot_dir, "journal.ndjson")
    _fill_journal(real_journal, _min_pairs())
    link = os.path.join(slot_dir, "linked.ndjson")
    os.symlink(real_journal, link)
    result = pr.rotate_journal(slots_dir, _SLOT, link, now=_NOW)
    assert result["reason"] == pr.REASON_JOURNAL_PATH_INVALID


def test_rotate_journal_rejects_journal_outside_slot(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    _mutate_to_state(slots_dir, _SLOT, pl.STATE_RELEASED)
    outside = os.path.join(slots_dir, "journal.ndjson")
    open(outside, "w", encoding="utf-8").close()
    result = pr.rotate_journal(slots_dir, _SLOT, outside, now=_NOW)
    assert result["reason"] == pr.REASON_JOURNAL_OUTSIDE_SLOT


def test_rotate_journal_rejects_near_miss_slot_directory(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    near_miss = _SLOT + "x"
    os.makedirs(os.path.join(slots_dir, near_miss))
    journal = _journal_path(slots_dir, near_miss)
    open(journal, "w", encoding="utf-8").close()
    result = pr.rotate_journal(slots_dir, _SLOT, journal, now=_NOW)
    assert result["reason"] == pr.REASON_JOURNAL_OUTSIDE_SLOT


@pytest.mark.parametrize("state", [
    pl.STATE_PROVISIONING,
    pl.STATE_PROVISIONED,
    pl.STATE_OCCUPIED,
])
def test_rotate_journal_rejects_active_slot_state(state, tmp_path):
    slots_dir = _slots_dir(tmp_path)
    record = _mutate_to_state(slots_dir, _SLOT, state)
    journal = _journal_path(slots_dir, _SLOT)
    _fill_journal(journal, _min_pairs(), slot_ref="%s@%d" % (_SLOT, record["generation"]))
    result = pr.rotate_journal(slots_dir, _SLOT, journal, now=_NOW)
    assert result == {
        "ok": False,
        "reason": pr.REASON_ROTATE_SLOT_ACTIVE,
        "rotated": False,
        "segmentPath": None,
    }


def test_rotate_journal_rejects_failed_slot_state(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    record = _mutate_to_state(slots_dir, _SLOT, pl.STATE_FAILED)
    journal = _journal_path(slots_dir, _SLOT)
    _fill_journal(journal, _min_pairs(), slot_ref="%s@%d" % (_SLOT, record["generation"]))
    result = pr.rotate_journal(slots_dir, _SLOT, journal, now=_NOW)
    assert result == {
        "ok": False,
        "reason": pr.REASON_ROTATE_SLOT_FAILED,
        "rotated": False,
        "segmentPath": None,
    }


@pytest.mark.parametrize("state", [pl.STATE_RELEASED, pl.STATE_RETIRED])
def test_rotate_journal_proceeds_for_quiescent_terminal_states(state, tmp_path):
    slots_dir = _slots_dir(tmp_path)
    record = _mutate_to_state(slots_dir, _SLOT, state)
    journal = _journal_path(slots_dir, _SLOT)
    slot_ref = "%s@%d" % (_SLOT, record["generation"])
    _fill_journal(journal, _min_pairs(), slot_ref=slot_ref)
    result = pr.rotate_journal(slots_dir, _SLOT, journal, now=_NOW)
    assert result["ok"] is True
    assert result["rotated"] is True
    assert result["segmentPath"] == _journal_path(slots_dir, _SLOT, "journal.0001.ndjson")


def test_rotate_journal_rejects_absent_journal(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    _mutate_to_state(slots_dir, _SLOT, pl.STATE_RELEASED)
    journal = _journal_path(slots_dir, _SLOT)
    result = pr.rotate_journal(slots_dir, _SLOT, journal, now=_NOW)
    assert result == {
        "ok": False,
        "reason": pr.REASON_JOURNAL_ABSENT,
        "rotated": False,
        "segmentPath": None,
    }


def test_rotate_journal_rejects_unreadable_slot_record(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    _mutate_to_state(slots_dir, _SLOT, pl.STATE_RELEASED)
    journal = _journal_path(slots_dir, _SLOT)
    _fill_journal(journal, _min_pairs())
    record_path = pl.record_path(slots_dir, _SLOT)
    os.remove(record_path)
    result = pr.rotate_journal(slots_dir, _SLOT, journal, now=_NOW)
    assert result["reason"] == pr.REASON_ROTATE_SLOT_UNREADABLE


def test_rotate_journal_rejects_open_effect(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    record = _mutate_to_state(slots_dir, _SLOT, pl.STATE_RELEASED)
    journal = _journal_path(slots_dir, _SLOT)
    slot_ref = "%s@%d" % (_SLOT, record["generation"])
    _fill_journal(journal, _min_pairs(), slot_ref=slot_ref)
    begin = pj.begin_effect(
        journal, slot_ref=slot_ref, kind=pj.KIND_APP_STARTED, at=_NOW, effect_id="open1",
    )
    assert begin["ok"] is True
    result = pr.rotate_journal(slots_dir, _SLOT, journal, now=_NOW)
    assert result["reason"] == pr.REASON_ROTATE_NOT_QUIESCENT
    assert os.path.isfile(journal)


def test_rotate_journal_rejects_torn_journal(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    record = _mutate_to_state(slots_dir, _SLOT, pl.STATE_RELEASED)
    journal = _journal_path(slots_dir, _SLOT)
    slot_ref = "%s@%d" % (_SLOT, record["generation"])
    _fill_journal(journal, _min_pairs(), slot_ref=slot_ref)
    with open(journal, "ab") as fh:
        fh.write(b'{"incomplete": true}')
    result = pr.rotate_journal(slots_dir, _SLOT, journal, now=_NOW)
    assert result["reason"] == pr.REASON_ROTATE_NOT_QUIESCENT


def test_rotate_journal_rejects_orphan_end_anomaly(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    record = _mutate_to_state(slots_dir, _SLOT, pl.STATE_RELEASED)
    journal = _journal_path(slots_dir, _SLOT)
    slot_ref = "%s@%d" % (_SLOT, record["generation"])
    _fill_journal(journal, _min_pairs(), slot_ref=slot_ref)
    with open(journal, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "schemaVersion": pj.SCHEMA,
            "phase": pj.PHASE_END,
            "effectId": "orphan1",
            "slotRef": slot_ref,
            "outcome": pj.OUTCOME_APPLIED,
            "at": _NOW2,
        }, sort_keys=True) + "\n")
    replayed = pj.replay(journal)
    anomaly_reasons = [a["reason"] for a in replayed["anomalies"]]
    assert "orphan-end" in anomaly_reasons
    result = pr.rotate_journal(slots_dir, _SLOT, journal, now=_NOW)
    assert result["reason"] == pr.REASON_ROTATE_NOT_QUIESCENT


def test_rotate_journal_rejects_duplicate_begin_anomaly(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    record = _mutate_to_state(slots_dir, _SLOT, pl.STATE_RELEASED)
    journal = _journal_path(slots_dir, _SLOT)
    slot_ref = "%s@%d" % (_SLOT, record["generation"])
    _fill_journal(journal, _min_pairs(), slot_ref=slot_ref)
    pj.begin_effect(
        journal, slot_ref=slot_ref, kind=pj.KIND_APP_STARTED, at=_NOW, effect_id="dup1",
    )
    pj.begin_effect(
        journal, slot_ref=slot_ref, kind=pj.KIND_APP_STARTED, at=_NOW, effect_id="dup1",
    )
    with open(journal, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "schemaVersion": pj.SCHEMA,
            "phase": pj.PHASE_END,
            "effectId": "dup1",
            "slotRef": slot_ref,
            "outcome": pj.OUTCOME_APPLIED,
            "at": _NOW2,
        }, sort_keys=True) + "\n")
    replayed = pj.replay(journal)
    anomaly_reasons = [a["reason"] for a in replayed["anomalies"]]
    assert "duplicate-begin" in anomaly_reasons
    result = pr.rotate_journal(slots_dir, _SLOT, journal, now=_NOW)
    assert result["reason"] == pr.REASON_ROTATE_NOT_QUIESCENT


def test_rotate_journal_rejects_indeterminate_outcome(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    record = _mutate_to_state(slots_dir, _SLOT, pl.STATE_RELEASED)
    journal = _journal_path(slots_dir, _SLOT)
    slot_ref = "%s@%d" % (_SLOT, record["generation"])
    _fill_journal(journal, _min_pairs() - 1, slot_ref=slot_ref)
    effect_id = "indet1"
    pj.begin_effect(
        journal, slot_ref=slot_ref, kind=pj.KIND_APP_STARTED, at=_NOW, effect_id=effect_id,
    )
    pj.end_effect(
        journal, slot_ref=slot_ref, effect_id=effect_id,
        kind=pj.KIND_APP_STARTED,
        outcome=pj.OUTCOME_INDETERMINATE, at=_NOW2,
    )
    result = pr.rotate_journal(slots_dir, _SLOT, journal, now=_NOW)
    assert result["reason"] == pr.REASON_ROTATE_NOT_QUIESCENT


def test_rotate_journal_below_threshold_is_ok_noop(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    record = _mutate_to_state(slots_dir, _SLOT, pl.STATE_RELEASED)
    journal = _journal_path(slots_dir, _SLOT)
    slot_ref = "%s@%d" % (_SLOT, record["generation"])
    _fill_journal(journal, _min_pairs() - 1, slot_ref=slot_ref)
    result = pr.rotate_journal(slots_dir, _SLOT, journal, now=_NOW)
    assert result == {
        "ok": True,
        "reason": pr.REASON_ROTATE_BELOW_THRESHOLD,
        "rotated": False,
        "segmentPath": None,
    }
    assert os.path.isfile(journal)


def test_rotate_journal_rejects_existing_segment_path(tmp_path, monkeypatch):
    slots_dir = _slots_dir(tmp_path)
    _setup_released_with_journal(slots_dir)
    journal = _journal_path(slots_dir, _SLOT)
    expected_segment = _journal_path(slots_dir, _SLOT, "journal.0001.ndjson")
    real_lexists = os.path.lexists

    def _lexists(path):
        if os.path.realpath(path) == os.path.realpath(expected_segment):
            return True
        return real_lexists(path)

    monkeypatch.setattr(os.path, "lexists", _lexists)
    result = pr.rotate_journal(slots_dir, _SLOT, journal, now=_NOW)
    assert result == {
        "ok": False,
        "reason": pr.REASON_ROTATE_SEGMENT_EXISTS,
        "rotated": False,
        "segmentPath": None,
    }
    assert os.path.isfile(journal)


def test_rotate_journal_rename_failure_leaves_journal_intact(tmp_path, monkeypatch):
    slots_dir = _slots_dir(tmp_path)
    _setup_released_with_journal(slots_dir)
    journal = _journal_path(slots_dir, _SLOT)
    original_content = open(journal, encoding="utf-8").read()
    monkeypatch.setattr(os, "rename", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("fail")))
    result = pr.rotate_journal(slots_dir, _SLOT, journal, now=_NOW)
    assert result == {
        "ok": False,
        "reason": pr.REASON_ROTATE_FAILED,
        "rotated": False,
        "segmentPath": None,
    }
    assert os.path.isfile(journal)
    assert open(journal, encoding="utf-8").read() == original_content
    assert not os.path.exists(_journal_path(slots_dir, _SLOT, "journal.0001.ndjson"))


def test_rotate_journal_sequence_allocation_three_times(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    record, journal = _setup_released_with_journal(slots_dir)
    slot_ref = "%s@%d" % (_SLOT, record["generation"])

    first = pr.rotate_journal(slots_dir, _SLOT, journal, now=_NOW)
    assert first["rotated"] is True
    assert first["segmentPath"].endswith("journal.0001.ndjson")

    _fill_journal(journal, _min_pairs(), slot_ref=slot_ref, prefix="round2")
    second = pr.rotate_journal(slots_dir, _SLOT, journal, now=_NOW)
    assert second["rotated"] is True
    assert second["segmentPath"].endswith("journal.0002.ndjson")

    _fill_journal(journal, _min_pairs(), slot_ref=slot_ref, prefix="round3")
    third = pr.rotate_journal(slots_dir, _SLOT, journal, now=_NOW)
    assert third["rotated"] is True
    assert third["segmentPath"].endswith("journal.0003.ndjson")

    listed = pr.journal_segments(slots_dir, _SLOT, journal)
    assert listed["ok"] is True
    assert [os.path.basename(p) for p in listed["segments"]] == [
        "journal.0001.ndjson",
        "journal.0002.ndjson",
        "journal.0003.ndjson",
    ]


def test_post_rotation_replay_correctness(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    record, journal = _setup_released_with_journal(slots_dir)
    slot_ref = "%s@%d" % (_SLOT, record["generation"])

    before = pj.replay(journal)
    assert before["ok"] is True
    assert before["torn"] is False
    assert before["anomalies"] == []

    result = pr.rotate_journal(slots_dir, _SLOT, journal, now=_NOW)
    assert result["rotated"] is True
    segment = result["segmentPath"]

    segment_replay = pj.replay(segment)
    assert segment_replay["ok"] is True
    assert segment_replay["torn"] is False
    assert segment_replay["anomalies"] == []
    assert len(segment_replay["effects"]) == _min_pairs()
    for effect in segment_replay["effects"]:
        assert effect["state"] == pj.STATE_APPLIED

    assert not os.path.exists(journal)
    _append_paired_effect(journal, slot_ref=slot_ref, effect_id="live-after-rotate")
    live_replay = pj.replay(journal)
    assert live_replay["ok"] is True
    assert live_replay["torn"] is False
    assert live_replay["anomalies"] == []
    assert len(live_replay["effects"]) == 1
    assert live_replay["effects"][0]["state"] == pj.STATE_APPLIED


def test_split_pair_regression_released_slot_with_open_begin(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    record = _mutate_to_state(slots_dir, _SLOT, pl.STATE_RELEASED)
    journal = _journal_path(slots_dir, _SLOT)
    slot_ref = "%s@%d" % (_SLOT, record["generation"])
    _fill_journal(journal, _min_pairs(), slot_ref=slot_ref)
    pj.begin_effect(
        journal, slot_ref=slot_ref, kind=pj.KIND_APP_STARTED, at=_NOW, effect_id="split-begin",
    )
    original_inode = os.stat(journal).st_ino
    result = pr.rotate_journal(slots_dir, _SLOT, journal, now=_NOW)
    assert result == {
        "ok": False,
        "reason": pr.REASON_ROTATE_NOT_QUIESCENT,
        "rotated": False,
        "segmentPath": None,
    }
    assert os.path.isfile(journal)
    assert os.stat(journal).st_ino == original_inode


def test_journal_segments_missing_slot_dir_returns_empty(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    journal = _journal_path(slots_dir, _SLOT)
    result = pr.journal_segments(slots_dir, _SLOT, journal)
    assert result == {"ok": True, "reason": None, "segments": []}


def test_journal_segments_rejects_outside_journal(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    os.makedirs(os.path.join(slots_dir, _SLOT))
    outside = os.path.join(slots_dir, "journal.ndjson")
    open(outside, "w", encoding="utf-8").close()
    result = pr.journal_segments(slots_dir, _SLOT, outside)
    assert result["reason"] == pr.REASON_JOURNAL_OUTSIDE_SLOT


def test_journal_segments_unreadable_slot_dir(tmp_path, monkeypatch):
    slots_dir = _slots_dir(tmp_path)
    slot_dir = os.path.join(slots_dir, _SLOT)
    os.makedirs(slot_dir)
    journal = _journal_path(slots_dir, _SLOT)

    real_listdir = os.listdir

    def _fail_listdir(path):
        if os.path.realpath(path) == os.path.realpath(slot_dir):
            raise OSError("denied")
        return real_listdir(path)

    monkeypatch.setattr(os, "listdir", _fail_listdir)
    result = pr.journal_segments(slots_dir, _SLOT, journal)
    assert result["reason"] == pr.REASON_SEGMENTS_UNREADABLE


def test_filtered_replay_disagreement_blocks_when_unfiltered_required(tmp_path):
    """Guard #6: filtered replay must not substitute for unfiltered quiescence."""
    slots_dir = _slots_dir(tmp_path)
    record = _mutate_to_state(slots_dir, _SLOT, pl.STATE_RELEASED)

    def _bump_generation(rec):
        rec = pl.begin_generation(rec, now=_NOW)
        rec = pl.transition(rec, pl.STATE_PROVISIONED, now=_NOW)
        rec = pl.transition(rec, pl.STATE_OCCUPIED, now=_NOW)
        return pl.transition(rec, pl.STATE_RELEASED, now=_NOW)

    bumped = pl.mutate(slots_dir, _SLOT, _bump_generation)
    assert bumped["ok"] is True
    record = bumped["record"]
    current_ref = "%s@%d" % (_SLOT, record["generation"])
    old_ref = "%s@%d" % (_SLOT, record["generation"] - 1)

    journal = _journal_path(slots_dir, _SLOT)
    _fill_journal(journal, _min_pairs(), slot_ref=current_ref)
    pj.begin_effect(
        journal, slot_ref=old_ref, kind=pj.KIND_APP_STARTED, at=_NOW, effect_id="old-gen-open",
    )
    unfiltered = pj.replay(journal)
    filtered = pj.replay(journal, slot_ref=current_ref)
    assert unfiltered["ok"] is True
    assert any(e["state"] == pj.STATE_POSSIBLY_APPLIED for e in unfiltered["effects"])
    assert filtered["ok"] is True
    assert all(
        e["state"] in (pj.STATE_APPLIED, pj.STATE_NOT_APPLIED)
        for e in filtered["effects"]
    )
    result = pr.rotate_journal(slots_dir, _SLOT, journal, now=_NOW)
    assert result["reason"] == pr.REASON_ROTATE_NOT_QUIESCENT


def _segment_path(slot_dir, journal_path, seq):
    base = os.path.basename(journal_path)
    stem, ext = os.path.splitext(base)
    return os.path.join(slot_dir, "%s.%04d%s" % (stem, seq, ext))


def _write_segment_record(path, record):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def _setup_slot_dir(slots_dir, slot=_SLOT):
    slot_dir = os.path.join(slots_dir, slot)
    os.makedirs(slot_dir, exist_ok=True)
    return slot_dir


def test_aggregate_replay_cross_segment_begin_end_applied(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    slot_dir = _setup_slot_dir(slots_dir)
    journal = _journal_path(slots_dir, _SLOT)
    seg1 = _segment_path(slot_dir, journal, 1)
    _write_segment_record(seg1, {
        "schemaVersion": pj.SCHEMA,
        "phase": pj.PHASE_BEGIN,
        "effectId": "cross-eff",
        "slotRef": _SLOT_REF,
        "kind": pj.KIND_APP_STARTED,
        "at": _NOW,
    })
    with open(journal, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "schemaVersion": pj.SCHEMA,
            "phase": pj.PHASE_END,
            "effectId": "cross-eff",
            "slotRef": _SLOT_REF,
            "outcome": pj.OUTCOME_APPLIED,
            "at": _NOW2,
        }, sort_keys=True) + "\n")
    result = pr.aggregate_replay(slots_dir, _SLOT, journal, slot_ref=_SLOT_REF)
    assert result["ok"] is True
    assert len(result["effects"]) == 1
    assert result["effects"][0]["state"] == pj.STATE_APPLIED
    assert result["effects"][0]["state"] != pj.STATE_POSSIBLY_APPLIED


def test_aggregate_replay_segments_folded_in_numeric_order(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    slot_dir = _setup_slot_dir(slots_dir)
    journal = _journal_path(slots_dir, _SLOT)
    seg2 = _segment_path(slot_dir, journal, 2)
    seg10 = _segment_path(slot_dir, journal, 10)
    _write_segment_record(seg2, {
        "schemaVersion": pj.SCHEMA,
        "phase": pj.PHASE_BEGIN,
        "effectId": "cross-eff",
        "slotRef": _SLOT_REF,
        "kind": pj.KIND_APP_STARTED,
        "at": _NOW,
    })
    _write_segment_record(seg10, {
        "schemaVersion": pj.SCHEMA,
        "phase": pj.PHASE_END,
        "effectId": "cross-eff",
        "slotRef": _SLOT_REF,
        "outcome": pj.OUTCOME_APPLIED,
        "at": _NOW2,
    })
    result = pr.aggregate_replay(slots_dir, _SLOT, journal, slot_ref=_SLOT_REF)
    assert result["ok"] is True
    assert result["effects"][0]["state"] == pj.STATE_APPLIED


def test_aggregate_replay_begin_seg1_end_seg2_live_absent(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    slot_dir = _setup_slot_dir(slots_dir)
    journal = _journal_path(slots_dir, _SLOT)
    seg1 = _segment_path(slot_dir, journal, 1)
    seg2 = _segment_path(slot_dir, journal, 2)
    _write_segment_record(seg1, {
        "schemaVersion": pj.SCHEMA,
        "phase": pj.PHASE_BEGIN,
        "effectId": "cross-eff",
        "slotRef": _SLOT_REF,
        "kind": pj.KIND_APP_STARTED,
        "at": _NOW,
    })
    _write_segment_record(seg2, {
        "schemaVersion": pj.SCHEMA,
        "phase": pj.PHASE_END,
        "effectId": "cross-eff",
        "slotRef": _SLOT_REF,
        "outcome": pj.OUTCOME_APPLIED,
        "at": _NOW2,
    })
    result = pr.aggregate_replay(slots_dir, _SLOT, journal, slot_ref=_SLOT_REF)
    assert result["ok"] is True
    assert result["effects"][0]["state"] == pj.STATE_APPLIED


def test_aggregate_replay_possibly_applied_stays_unresolved(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    slot_dir = _setup_slot_dir(slots_dir)
    journal = _journal_path(slots_dir, _SLOT)
    seg1 = _segment_path(slot_dir, journal, 1)
    _write_segment_record(seg1, {
        "schemaVersion": pj.SCHEMA,
        "phase": pj.PHASE_BEGIN,
        "effectId": "open-eff",
        "slotRef": _SLOT_REF,
        "kind": pj.KIND_APP_STARTED,
        "at": _NOW,
    })
    result = pr.aggregate_replay(slots_dir, _SLOT, journal, slot_ref=_SLOT_REF)
    assert result["ok"] is True
    assert result["effects"][0]["state"] == pj.STATE_POSSIBLY_APPLIED


def test_aggregate_replay_torn_segment_makes_aggregate_torn(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    slot_dir = _setup_slot_dir(slots_dir)
    journal = _journal_path(slots_dir, _SLOT)
    seg1 = _segment_path(slot_dir, journal, 1)
    with open(seg1, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "schemaVersion": pj.SCHEMA,
            "phase": pj.PHASE_BEGIN,
            "effectId": "torn-eff",
            "slotRef": _SLOT_REF,
            "kind": pj.KIND_APP_STARTED,
            "at": _NOW,
        }, sort_keys=True))
    with open(journal, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "schemaVersion": pj.SCHEMA,
            "phase": pj.PHASE_END,
            "effectId": "clean-eff",
            "slotRef": _SLOT_REF,
            "outcome": pj.OUTCOME_APPLIED,
            "at": _NOW2,
        }, sort_keys=True) + "\n")
    result = pr.aggregate_replay(slots_dir, _SLOT, journal, slot_ref=_SLOT_REF)
    assert result["ok"] is True
    assert result["torn"] is True


def test_aggregate_replay_unreadable_segment_fails(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    slot_dir = _setup_slot_dir(slots_dir)
    journal = _journal_path(slots_dir, _SLOT)
    seg1 = _segment_path(slot_dir, journal, 1)
    os.makedirs(seg1)
    result = pr.aggregate_replay(slots_dir, _SLOT, journal, slot_ref=_SLOT_REF)
    assert result["ok"] is False
    assert result["reason"] == pj.REASON_JOURNAL_UNREADABLE


def test_aggregate_replay_gap_emits_anomaly_and_report_blocker(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    slot_dir = _setup_slot_dir(slots_dir)
    journal = _journal_path(slots_dir, _SLOT)
    seg1 = _segment_path(slot_dir, journal, 1)
    seg3 = _segment_path(slot_dir, journal, 3)
    _write_segment_record(seg1, {
        "schemaVersion": pj.SCHEMA,
        "phase": pj.PHASE_BEGIN,
        "effectId": "eff1",
        "slotRef": _SLOT_REF,
        "kind": pj.KIND_APP_STARTED,
        "at": _NOW,
    })
    _write_segment_record(seg3, {
        "schemaVersion": pj.SCHEMA,
        "phase": pj.PHASE_END,
        "effectId": "eff1",
        "slotRef": _SLOT_REF,
        "outcome": pj.OUTCOME_APPLIED,
        "at": _NOW2,
    })
    result = pr.aggregate_replay(slots_dir, _SLOT, journal, slot_ref=_SLOT_REF)
    assert result["ok"] is True
    gap_anomalies = [
        a for a in result["anomalies"]
        if a.get("reason") == pr.ANOMALY_SEGMENT_SEQUENCE_GAP
    ]
    assert gap_anomalies
    assert gap_anomalies[0]["missingSequence"] == 2
    entry = {
        "slot": _SLOT,
        "slotRef": _SLOT_REF,
        "outcome": pj.SLOT_OUTCOME_FAILED,
        "replay": result,
        "fencing": {"slotRef": _SLOT_REF, "fenced": True},
    }
    report = pj.partial_failure_report([entry])
    assert pj.BLOCK_JOURNAL_ANOMALY in {b["reason"] for b in report["blockers"]}


def test_aggregate_replay_first_sequence_above_one_emits_anomaly(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    slot_dir = _setup_slot_dir(slots_dir)
    journal = _journal_path(slots_dir, _SLOT)
    seg2 = _segment_path(slot_dir, journal, 2)
    _write_segment_record(seg2, {
        "schemaVersion": pj.SCHEMA,
        "phase": pj.PHASE_BEGIN,
        "effectId": "eff1",
        "slotRef": _SLOT_REF,
        "kind": pj.KIND_APP_STARTED,
        "at": _NOW,
    })
    result = pr.aggregate_replay(slots_dir, _SLOT, journal, slot_ref=_SLOT_REF)
    assert result["ok"] is True
    not_one = [
        a for a in result["anomalies"]
        if a.get("reason") == pr.ANOMALY_SEGMENT_SEQUENCE_NOT_ONE
    ]
    assert not_one
    assert not_one[0]["firstSequence"] == 2


def test_aggregate_replay_segments_present_live_absent_ok(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    slot_dir = _setup_slot_dir(slots_dir)
    journal = _journal_path(slots_dir, _SLOT)
    seg1 = _segment_path(slot_dir, journal, 1)
    begin = {
        "schemaVersion": pj.SCHEMA,
        "phase": pj.PHASE_BEGIN,
        "effectId": "eff1",
        "slotRef": _SLOT_REF,
        "kind": pj.KIND_APP_STARTED,
        "at": _NOW,
    }
    end = {
        "schemaVersion": pj.SCHEMA,
        "phase": pj.PHASE_END,
        "effectId": "eff1",
        "slotRef": _SLOT_REF,
        "outcome": pj.OUTCOME_APPLIED,
        "at": _NOW2,
    }
    with open(seg1, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(begin, sort_keys=True) + "\n")
        fh.write(json.dumps(end, sort_keys=True) + "\n")
    result = pr.aggregate_replay(slots_dir, _SLOT, journal, slot_ref=_SLOT_REF)
    assert result["ok"] is True
    assert result["effects"][0]["state"] == pj.STATE_APPLIED


def test_aggregate_replay_no_segments_no_live_refuses(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    _setup_slot_dir(slots_dir)
    journal = _journal_path(slots_dir, _SLOT)
    result = pr.aggregate_replay(slots_dir, _SLOT, journal, slot_ref=_SLOT_REF)
    assert result["ok"] is False
    assert result["reason"] == pj.REASON_JOURNAL_UNREADABLE


def test_aggregate_replay_invalid_slot_ref_refuses(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    _setup_slot_dir(slots_dir)
    journal = _journal_path(slots_dir, _SLOT)
    result = pr.aggregate_replay(slots_dir, _SLOT, journal, slot_ref="not-a-ref")
    assert result["ok"] is False
    assert result["reason"] == pj.REASON_SLOT_REF_INVALID


def test_aggregate_replay_slot_ref_slot_mismatch_refuses(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    _setup_slot_dir(slots_dir)
    journal = _journal_path(slots_dir, _SLOT)
    result = pr.aggregate_replay(slots_dir, _SLOT, journal, slot_ref="other-slot@1")
    assert result["ok"] is False
    assert result["reason"] == pj.REASON_SLOT_REF_INVALID


def test_aggregate_replay_slot_ref_passes_partial_failure_report(tmp_path):
    slots_dir = _slots_dir(tmp_path)
    slot_dir = _setup_slot_dir(slots_dir)
    journal = _journal_path(slots_dir, _SLOT)
    seg1 = _segment_path(slot_dir, journal, 1)
    _write_segment_record(seg1, {
        "schemaVersion": pj.SCHEMA,
        "phase": pj.PHASE_BEGIN,
        "effectId": "eff1",
        "slotRef": _SLOT_REF,
        "kind": pj.KIND_APP_STARTED,
        "at": _NOW,
    })
    with open(journal, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "schemaVersion": pj.SCHEMA,
            "phase": pj.PHASE_END,
            "effectId": "eff1",
            "slotRef": _SLOT_REF,
            "outcome": pj.OUTCOME_APPLIED,
            "at": _NOW2,
        }, sort_keys=True) + "\n")
    replay = pr.aggregate_replay(slots_dir, _SLOT, journal, slot_ref=_SLOT_REF)
    entry = {
        "slot": _SLOT,
        "slotRef": _SLOT_REF,
        "outcome": pj.SLOT_OUTCOME_PROVISIONED,
        "replay": replay,
        "fencing": None,
    }
    report = pj.partial_failure_report([entry])
    assert pj.BLOCK_REPLAY_SLOT_MISMATCH not in {b["reason"] for b in report["blockers"]}
    assert replay["slotRef"] == _SLOT_REF
