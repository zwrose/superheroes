"""Invariant: public pilot_lifecycle / pilot_journal entry points never leak builtin exceptions."""
import inspect
import json
import os
import shutil
import sys
import tempfile

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_journal as pj  # noqa: E402
import pilot_lifecycle as pl  # noqa: E402
import pilot_slot  # noqa: E402

NOW = "2026-01-01T00:00:00Z"
SLOT = "slot1"
SLOT_REF = "slot1@1"
ACCOUNTS = [{"account": "owner", "role": "resource-owner"}]

HOSTILE_VALUES = [
    [],
    {},
    set(),
    None,
    0,
    "",
    b"x",
    object(),
    [[]],
    {"k": set()},
    "x" * 10000,
    float("nan"),
]

ALLOWED_EXCEPTIONS = (
    pl.PilotLifecycleError,
    pj.PilotJournalError,
    pilot_slot.PilotSlotError,
)


def _safe_path_under(tmp, hostile):
    """Hostile path values for write-capable helpers must stay under tmp."""
    if isinstance(hostile, str):
        return os.path.join(tmp, hostile)
    return hostile


def _public_callables(module):
    names = set()
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if inspect.isclass(obj):
            continue
        if callable(obj):
            names.add(name)
    return names


def _valid_record():
    return pl.new_record(SLOT, ACCOUNTS, now=NOW)


def _tmp_dir():
    return tempfile.mkdtemp()


def _invoke_lifecycle(name, hostile, param):
    rec = _valid_record()
    tmp = _tmp_dir()
    try:
        slots_path = os.path.join(tmp, "slots")
        path = pl.record_path(slots_path, SLOT)
        if name == "generation_check":
            if param == "carried":
                return pl.generation_check(hostile, 1)
            return pl.generation_check(1, hostile)
        if name == "new_record":
            if param == "slot":
                return pl.new_record(hostile, ACCOUNTS, now=NOW)
            if param == "accounts":
                return pl.new_record(SLOT, hostile, now=NOW)
            return pl.new_record(SLOT, ACCOUNTS, now=hostile)
        if name == "transition":
            if param == "record":
                return pl.transition(hostile, pl.STATE_PROVISIONED, now=NOW)
            if param == "to":
                return pl.transition(rec, hostile, now=NOW)
            if param == "now":
                return pl.transition(rec, pl.STATE_PROVISIONED, now=hostile)
            return pl.transition(rec, pl.STATE_PROVISIONED, now=NOW, detail=hostile)
        if name == "begin_generation":
            if param == "record":
                return pl.begin_generation(hostile, now=NOW)
            return pl.begin_generation(rec, now=hostile)
        if name == "slot_ref":
            return pl.slot_ref(hostile)
        if name == "provisioning_outcome":
            return pl.provisioning_outcome(hostile)
        if name == "slots_dir":
            if param == "cwd":
                return pl.slots_dir(hostile)
            return pl.slots_dir(tmp, root=hostile)
        if name == "record_path":
            if param == "slots_dir_path":
                return pl.record_path(hostile, SLOT)
            return pl.record_path(slots_path, hostile)
        if name == "lock_path":
            if param == "slots_dir_path":
                return pl.lock_path(hostile, SLOT)
            return pl.lock_path(slots_path, hostile)
        if name == "slot_lock":
            if param == "slots_dir_path":
                ctx = pl.slot_lock(_safe_path_under(tmp, hostile), SLOT)
            elif param == "slot":
                ctx = pl.slot_lock(slots_path, hostile)
            elif param == "timeout":
                ctx = pl.slot_lock(slots_path, SLOT, timeout=hostile)
            else:
                ctx = pl.slot_lock(slots_path, SLOT, poll=hostile)
            with ctx:
                pass
            return None
        if name == "read_record":
            return pl.read_record(hostile)
        if name == "write_record":
            if param == "path":
                return pl.write_record(_safe_path_under(tmp, hostile), rec)
            return pl.write_record(path, hostile)
        if name == "mutate":
            if param == "slots_dir_path":
                return pl.mutate(_safe_path_under(tmp, hostile), SLOT, lambda r: r)
            if param == "slot":
                return pl.mutate(slots_path, hostile, lambda r: r)
            if param == "fn":
                return pl.mutate(slots_path, SLOT, hostile)
            return pl.mutate(slots_path, SLOT, lambda r: r, timeout=hostile)
        if name == "create_slot":
            if param == "slots_dir_path":
                return pl.create_slot(
                    _safe_path_under(tmp, hostile), SLOT, ACCOUNTS, now=NOW
                )
            if param == "slot":
                return pl.create_slot(slots_path, hostile, ACCOUNTS, now=NOW)
            if param == "accounts":
                return pl.create_slot(slots_path, SLOT, hostile, now=NOW)
            if param == "now":
                return pl.create_slot(slots_path, SLOT, ACCOUNTS, now=hostile)
            return pl.create_slot(slots_path, SLOT, ACCOUNTS, now=NOW, timeout=hostile)
        raise AssertionError("unhandled lifecycle function %r" % name)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _invoke_journal(name, hostile, param):
    tmp = _tmp_dir()
    try:
        journal_path = os.path.join(tmp, "journal.jsonl")
        if name == "begin_effect":
            kwargs = {
                "slot_ref": SLOT_REF,
                "kind": pj.KIND_APP_STARTED,
                "at": NOW,
            }
            if param == "journal_path":
                return pj.begin_effect(hostile, **kwargs)
            if param == "slot_ref":
                kwargs["slot_ref"] = hostile
            elif param == "kind":
                kwargs["kind"] = hostile
            elif param == "at":
                kwargs["at"] = hostile
            elif param == "detail":
                kwargs["detail"] = hostile
            else:
                kwargs["effect_id"] = hostile
            return pj.begin_effect(journal_path, **kwargs)
        if name == "end_effect":
            kwargs = {
                "slot_ref": SLOT_REF,
                "effect_id": "eff1",
                "outcome": pj.OUTCOME_APPLIED,
                "at": NOW,
            }
            if param == "journal_path":
                return pj.end_effect(hostile, **kwargs)
            if param == "slot_ref":
                kwargs["slot_ref"] = hostile
            elif param == "effect_id":
                kwargs["effect_id"] = hostile
            elif param == "outcome":
                kwargs["outcome"] = hostile
            elif param == "at":
                kwargs["at"] = hostile
            else:
                kwargs["reason"] = hostile
            return pj.end_effect(journal_path, **kwargs)
        if name == "effect":
            kwargs = {
                "slot_ref": SLOT_REF,
                "kind": pj.KIND_APP_STARTED,
                "at": NOW,
            }
            if param == "journal_path":
                with pj.effect(hostile, **kwargs):
                    pass
                return None
            if param == "slot_ref":
                kwargs["slot_ref"] = hostile
            elif param == "kind":
                kwargs["kind"] = hostile
            elif param == "at":
                kwargs["at"] = hostile
            elif param == "detail":
                kwargs["detail"] = hostile
            else:
                kwargs["effect_id"] = hostile
            with pj.effect(journal_path, **kwargs):
                pass
            return None
        if name == "replay":
            if param == "journal_path":
                return pj.replay(hostile)
            return pj.replay(journal_path, slot_ref=hostile)
        if name == "partial_failure_report":
            return pj.partial_failure_report(hostile)
        raise AssertionError("unhandled journal function %r" % name)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _lifecycle_params(name):
    if name == "generation_check":
        return ("carried", "current")
    if name == "new_record":
        return ("slot", "accounts", "now")
    if name == "transition":
        return ("record", "to", "now", "detail")
    if name == "begin_generation":
        return ("record", "now")
    if name == "slot_ref":
        return ("record",)
    if name == "provisioning_outcome":
        return ("state",)
    if name == "slots_dir":
        return ("cwd", "root")
    if name in ("record_path", "lock_path"):
        return ("slots_dir_path", "slot")
    if name == "slot_lock":
        return ("slots_dir_path", "slot", "timeout", "poll")
    if name == "read_record":
        return ("path",)
    if name == "write_record":
        return ("path", "record")
    if name == "mutate":
        return ("slots_dir_path", "slot", "fn", "timeout")
    if name == "create_slot":
        return ("slots_dir_path", "slot", "accounts", "now", "timeout")
    raise AssertionError("add driver params for new public function %r" % name)


def _journal_params(name):
    if name == "begin_effect":
        return ("journal_path", "slot_ref", "kind", "at", "detail", "effect_id")
    if name == "end_effect":
        return ("journal_path", "slot_ref", "effect_id", "outcome", "at", "reason")
    if name == "effect":
        return ("journal_path", "slot_ref", "kind", "at", "detail", "effect_id")
    if name == "replay":
        return ("journal_path", "slot_ref")
    if name == "partial_failure_report":
        return ("slots",)
    raise AssertionError("add driver params for new public function %r" % name)


DRIVERS_LIFECYCLE = {name: _invoke_lifecycle for name in _public_callables(pl)}
DRIVERS_JOURNAL = {name: _invoke_journal for name in _public_callables(pj)}

assert set(DRIVERS_LIFECYCLE) == _public_callables(pl), (
    "pilot_lifecycle public API changed — add drivers for: %s"
    % sorted(_public_callables(pl) - set(DRIVERS_LIFECYCLE))
)
assert set(DRIVERS_JOURNAL) == _public_callables(pj), (
    "pilot_journal public API changed — add drivers for: %s"
    % sorted(_public_callables(pj) - set(DRIVERS_JOURNAL))
)


def _assert_no_leaked_exceptions(module_label, name, param, hostile, invoke):
    try:
        invoke(name, hostile, param)
    except ALLOWED_EXCEPTIONS:
        return
    except Exception as exc:
        pytest.fail(
            "%s.%s param=%r hostile=%r raised %s: %s"
            % (module_label, name, param, hostile, type(exc).__name__, exc)
        )


@pytest.mark.parametrize("name", sorted(DRIVERS_LIFECYCLE))
@pytest.mark.parametrize("hostile", HOSTILE_VALUES, ids=lambda v: repr(v)[:40])
def test_pilot_lifecycle_public_api_never_leaks_builtin_exceptions(name, hostile):
    for param in _lifecycle_params(name):
        _assert_no_leaked_exceptions("pilot_lifecycle", name, param, hostile, _invoke_lifecycle)


@pytest.mark.parametrize("name", sorted(DRIVERS_JOURNAL))
@pytest.mark.parametrize("hostile", HOSTILE_VALUES, ids=lambda v: repr(v)[:40])
def test_pilot_journal_public_api_never_leaks_builtin_exceptions(name, hostile):
    for param in _journal_params(name):
        _assert_no_leaked_exceptions("pilot_journal", name, param, hostile, _invoke_journal)


def test_replay_refuses_hostile_journal_lines():
    tmp = _tmp_dir()
    try:
        journal_path = os.path.join(tmp, "journal.jsonl")
        hostile_lines = [
            json.dumps({
                "schemaVersion": 1,
                "phase": "begin",
                "effectId": [],
                "slotRef": "s1@1",
                "kind": "app-started",
                "at": NOW,
            }),
            json.dumps({
                "schemaVersion": 1,
                "phase": "begin",
                "effectId": "eff1",
                "slotRef": "s1@1",
                "kind": "app-started",
                "at": NOW,
            }).replace('"eff1"', '[]'),
            "[]",
        ]
        with open(journal_path, "w", encoding="utf-8") as fh:
            for line in hostile_lines:
                fh.write(line + "\n")
        result = pj.replay(journal_path)
        assert isinstance(result, dict)
        assert "ok" in result
        assert result["ok"] is True
        assert isinstance(result.get("anomalies"), list)

        with open(journal_path, "wb") as fh:
            fh.write(b"\xff\xfe\n")
        bad_utf8 = pj.replay(journal_path)
        assert bad_utf8["ok"] is False
        assert bad_utf8["reason"] == pj.REASON_JOURNAL_UNREADABLE
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_read_record_refuses_hostile_on_disk_state():
    tmp = _tmp_dir()
    try:
        path = os.path.join(tmp, "slot.json")
        rec = pl.new_record(SLOT, ACCOUNTS, now=NOW)
        rec["state"] = []
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        result = pl.read_record(path)
        assert result == {
            "ok": False,
            "reason": pl.REASON_RECORD_INVALID,
            "record": None,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _cwd_listing():
    return set(os.listdir(os.getcwd()))


def _exercise_write_capable_lifecycle_helpers(tmp):
    slots_path = os.path.join(tmp, "slots")
    rec = pl.new_record(SLOT, ACCOUNTS, now=NOW)
    path = pl.record_path(slots_path, SLOT)
    pl.write_record(path, rec)
    with pl.slot_lock(slots_path, SLOT):
        pass
    pl.mutate(slots_path, SLOT, lambda r: r)
    pl.create_slot(slots_path, "slot2", ACCOUNTS, now=NOW)


def test_lifecycle_helpers_do_not_write_into_repository_cwd():
    repo_cwd = os.getcwd()
    before = _cwd_listing()
    tmp = _tmp_dir()
    try:
        _exercise_write_capable_lifecycle_helpers(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    after = _cwd_listing()
    assert repo_cwd == os.getcwd()
    assert after == before
