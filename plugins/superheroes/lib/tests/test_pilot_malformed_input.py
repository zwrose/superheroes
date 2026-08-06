"""Invariant: public pilot_lifecycle / pilot_journal / pilot_appctl / pilot_wave entry points never leak builtin exceptions."""
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

import pilot_contract as pc  # noqa: E402
import pilot_journal as pj  # noqa: E402
import pilot_lifecycle as pl  # noqa: E402
import pilot_appctl as pa  # noqa: E402
import pilot_wave as pw  # noqa: E402
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
    pa.PilotAppctlError,
    pw.PilotWaveError,
)


def _safe_path_under(tmp, hostile):
    """Hostile path values for write-capable helpers must stay under tmp."""
    if isinstance(hostile, str):
        return os.path.join(tmp, hostile)
    return hostile


def _public_callables(module):
    names = set()
    mod_name = module.__name__
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if inspect.isclass(obj):
            continue
        if callable(obj) and getattr(obj, "__module__", None) == mod_name:
            names.add(name)
    return names


def _valid_record():
    return pl.new_record(SLOT, ACCOUNTS, now=NOW)


def _tmp_dir():
    return tempfile.mkdtemp()


def _valid_instance():
    return {
        "schemaVersion": pa.SCHEMA,
        "slot": SLOT,
        "slotRef": SLOT_REF,
        "state": pa.STATE_READY,
        "pid": 1,
        "pgid": 1,
        "launchNonce": "a" * 32,
        "cwd": os.path.realpath(tempfile.gettempdir()),
        "allocation": {
            "host": "127.0.0.1",
            "port": 9,
            "hostnames": [],
            "containers": [],
            "envMetadata": {},
        },
        "command": ["echo", "hi"],
        "readinessUrl": "http://127.0.0.1:9/",
        "readinessAttribution": pa.READINESS_ATTRIBUTION_UNATTRIBUTED,
        "stdoutPath": os.path.join(os.path.realpath(tempfile.gettempdir()), "app.stdout.log"),
        "stderrPath": os.path.join(os.path.realpath(tempfile.gettempdir()), "app.stderr.log"),
        "startedAt": NOW,
        "updatedAt": NOW,
        "stopReceipt": None,
    }


def _valid_launch(cwd):
    return {
        "authorized": {
            "schemaVersion": 1,
            "slotRef": SLOT_REF,
            "baseUrl": "http://127.0.0.1/",
            "readinessUrl": "http://127.0.0.1:9/",
            "policyDigest": "abc",
        },
        "slot": SLOT,
        "slotRef": SLOT_REF,
        "cwd": cwd,
        "argv": ["echo", "hi"],
        "env": {},
        "allocation": {
            "host": "127.0.0.1",
            "port": 9,
            "hostnames": [],
            "containers": [],
            "envMetadata": {},
        },
        "readinessUrl": "http://127.0.0.1:9/",
        "readinessAttribution": pa.READINESS_ATTRIBUTION_UNATTRIBUTED,
        "readinessTimeoutSeconds": 1.0,
        "pollSeconds": 0.1,
    }


def _valid_anchor():
    return {
        "schemaVersion": pw.SCHEMA,
        "launchedAt": NOW,
        "launchedAtMono": 0.0,
        "deadlineSeconds": 10.0,
        "marginSeconds": 5.0,
    }


def _valid_teardown_entry():
    return {
        "slot": SLOT,
        "slotRef": SLOT_REF,
        "intent": pw.INTENT_COMPLETE,
        "instance": None,
        "allocation": None,
        "stepTimeoutSeconds": None,
    }


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
                "kind": pj.KIND_APP_STARTED,
                "outcome": pj.OUTCOME_APPLIED,
                "at": NOW,
            }
            if param == "journal_path":
                return pj.end_effect(hostile, **kwargs)
            if param == "slot_ref":
                kwargs["slot_ref"] = hostile
            elif param == "effect_id":
                kwargs["effect_id"] = hostile
            elif param == "kind":
                kwargs["kind"] = hostile
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
        if name == "replay_sources":
            if param == "paths":
                return pj.replay_sources(hostile, slot_ref=SLOT_REF, journal_path=journal_path)
            if param == "slot_ref":
                return pj.replay_sources([journal_path], slot_ref=hostile, journal_path=journal_path)
            return pj.replay_sources([journal_path], slot_ref=SLOT_REF, journal_path=hostile)
        if name == "partial_failure_report":
            return pj.partial_failure_report(hostile)
        raise AssertionError("unhandled journal function %r" % name)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _invoke_appctl(name, hostile, param):
    tmp = _tmp_dir()
    try:
        slots_path = os.path.join(tmp, "slots")
        journal_path = os.path.join(tmp, "journal.jsonl")
        open(journal_path, "a", encoding="utf-8").close()
        cwd = os.path.realpath(tempfile.gettempdir())
        if name == "instance_path":
            if param == "slots_dir_path":
                return pa.instance_path(_safe_path_under(tmp, hostile), SLOT)
            return pa.instance_path(slots_path, hostile)
        if name == "resolve_invocation":
            if param == "dev_command":
                return pa.resolve_invocation(hostile, params={}, readiness_url="http://x/")
            if param == "params":
                return pa.resolve_invocation(["echo"], params=hostile, readiness_url="http://x/")
            if param == "readiness_url":
                return pa.resolve_invocation(["echo"], params={}, readiness_url=hostile)
            return pa.resolve_invocation(["echo"], params={}, readiness_url="http://x/", env=hostile)
        if name == "assert_unique_endpoints":
            return pa.assert_unique_endpoints(hostile)
        if name == "check_endpoint_free":
            if param == "host":
                return pa.check_endpoint_free(hostile, 9)
            if param == "port":
                return pa.check_endpoint_free("127.0.0.1", hostile)
            if param == "timeout":
                return pa.check_endpoint_free("127.0.0.1", 9, timeout=hostile)
            return pa.check_endpoint_free("127.0.0.1", 9, connect=hostile)
        if name == "retry_gate":
            return pa.retry_gate(hostile)
        if name == "write_instance":
            inst = _valid_instance()
            if param == "slots_dir_path":
                return pa.write_instance(_safe_path_under(tmp, hostile), SLOT, inst)
            if param == "slot":
                return pa.write_instance(slots_path, hostile, inst)
            if param == "instance":
                return pa.write_instance(slots_path, SLOT, hostile)
            return pa.write_instance(slots_path, SLOT, inst, timeout=hostile)
        if name == "read_instance":
            if param == "slots_dir_path":
                return pa.read_instance(_safe_path_under(tmp, hostile), SLOT)
            return pa.read_instance(slots_path, hostile)
        if name == "clear_instance":
            if param == "slots_dir_path":
                return pa.clear_instance(_safe_path_under(tmp, hostile), SLOT)
            if param == "slot":
                return pa.clear_instance(slots_path, hostile)
            return pa.clear_instance(slots_path, SLOT, timeout=hostile)
        if name == "stand_up":
            launch = _valid_launch(cwd)
            kwargs = {
                "journal_path": journal_path,
                "slots_dir_path": slots_path,
                "now": NOW,
                "now_fn": lambda: NOW,
                "registry": {},
                "declaration": {},
            }
            if param == "launch":
                return pa.stand_up(hostile, **kwargs)
            if param == "journal_path":
                kwargs["journal_path"] = hostile
            elif param == "slots_dir_path":
                kwargs["slots_dir_path"] = _safe_path_under(tmp, hostile)
            elif param == "now":
                kwargs["now"] = hostile
            elif param == "now_fn":
                kwargs["now_fn"] = hostile
            elif param == "registry":
                kwargs["registry"] = hostile
            elif param == "declaration":
                kwargs["declaration"] = hostile
            elif param == "spawn":
                kwargs["spawn"] = hostile
            elif param == "readiness_probe":
                kwargs["readiness_probe"] = hostile
            elif param == "monotonic":
                kwargs["monotonic"] = hostile
            else:
                kwargs["sleep"] = hostile
            return pa.stand_up(launch, **kwargs)
        if name == "stop":
            inst = _valid_instance()
            kwargs = {"now_fn": lambda: NOW}
            if param == "instance":
                return pa.stop(hostile, **kwargs)
            if param == "now_fn":
                kwargs["now_fn"] = hostile
            elif param == "terminate":
                kwargs["terminate"] = hostile
            elif param == "poll_alive":
                kwargs["poll_alive"] = hostile
            elif param == "corroborate":
                kwargs["corroborate"] = hostile
            elif param == "check_free":
                kwargs["check_free"] = hostile
            elif param == "wait_seconds":
                kwargs["wait_seconds"] = hostile
            elif param == "sleep":
                kwargs["sleep"] = hostile
            else:
                kwargs["monotonic"] = hostile
            return pa.stop(inst, **kwargs)
        raise AssertionError("unhandled appctl function %r" % name)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _invoke_wave(name, hostile, param):
    tmp = _tmp_dir()
    try:
        slots_path = os.path.join(tmp, "slots")
        journal_path = os.path.join(tmp, "journal.jsonl")
        open(journal_path, "a", encoding="utf-8").close()
        if name == "park_latch_path":
            if param == "slots_dir_path":
                return pw.park_latch_path(_safe_path_under(tmp, hostile), SLOT)
            return pw.park_latch_path(slots_path, hostile)
        if name == "wave_anchor":
            kwargs = {
                "launched_at": NOW,
                "deadline_seconds": 10,
                "margin_seconds": 5,
            }
            if param == "launched_at":
                kwargs["launched_at"] = hostile
            elif param == "deadline_seconds":
                kwargs["deadline_seconds"] = hostile
            elif param == "margin_seconds":
                kwargs["margin_seconds"] = hostile
            else:
                kwargs["monotonic"] = hostile
            return pw.wave_anchor(**kwargs)
        if name == "wave_phase":
            anchor = _valid_anchor()
            if param == "anchor":
                return pw.wave_phase(hostile)
            return pw.wave_phase(anchor, monotonic=hostile)
        if name == "admit_work":
            anchor = _valid_anchor()
            if param == "anchor":
                return pw.admit_work(hostile)
            return pw.admit_work(anchor, monotonic=hostile)
        if name == "latch_park":
            kwargs = {
                "slot_ref": SLOT_REF,
                "now": NOW,
                "reason": "park",
            }
            if param == "slots_dir_path":
                return pw.latch_park(_safe_path_under(tmp, hostile), SLOT, **kwargs)
            if param == "slot":
                return pw.latch_park(slots_path, hostile, **kwargs)
            if param == "slot_ref":
                kwargs["slot_ref"] = hostile
            elif param == "now":
                kwargs["now"] = hostile
            elif param == "reason":
                kwargs["reason"] = hostile
            else:
                kwargs["timeout"] = hostile
            return pw.latch_park(slots_path, SLOT, **kwargs)
        if name == "read_park_latch":
            if param == "slots_dir_path":
                return pw.read_park_latch(_safe_path_under(tmp, hostile), SLOT)
            if param == "slot":
                return pw.read_park_latch(slots_path, hostile)
            return pw.read_park_latch(slots_path, SLOT, timeout=hostile)
        if name == "validate_step_result":
            if param == "result":
                return pw.validate_step_result(hostile, step=pw.STEP_APP, slot_ref=SLOT_REF)
            if param == "step":
                return pw.validate_step_result({}, step=hostile, slot_ref=SLOT_REF)
            return pw.validate_step_result({}, step=pw.STEP_APP, slot_ref=hostile)
        if name == "assert_destructive_allowed":
            if param == "step":
                return pw.assert_destructive_allowed(hostile, intent=pw.INTENT_COMPLETE, latched=False)
            if param == "intent":
                return pw.assert_destructive_allowed(pw.STEP_CLEANUP, intent=hostile, latched=False)
            return pw.assert_destructive_allowed(pw.STEP_CLEANUP, intent=pw.INTENT_COMPLETE, latched=hostile)
        if name == "teardown_slot":
            entry = _valid_teardown_entry()
            kwargs = {
                "handlers": {},
                "slots_dir_path": slots_path,
                "journal_path": journal_path,
                "now_fn": lambda: NOW,
            }
            if param == "entry":
                return pw.teardown_slot(hostile, **kwargs)
            if param == "handlers":
                kwargs["handlers"] = hostile
            elif param == "slots_dir_path":
                kwargs["slots_dir_path"] = _safe_path_under(tmp, hostile)
            elif param == "journal_path":
                kwargs["journal_path"] = hostile
            elif param == "now_fn":
                kwargs["now_fn"] = hostile
            else:
                kwargs["monotonic"] = hostile
            return pw.teardown_slot(entry, **kwargs)
        if name == "run_teardown":
            entry = _valid_teardown_entry()
            kwargs = {
                "handlers": {},
                "slots_dir_path": slots_path,
                "journal_path": journal_path,
                "now_fn": lambda: NOW,
            }
            if param == "slots":
                return pw.run_teardown(hostile, **kwargs)
            if param == "handlers":
                kwargs["handlers"] = hostile
            elif param == "slots_dir_path":
                kwargs["slots_dir_path"] = _safe_path_under(tmp, hostile)
            elif param == "journal_path":
                kwargs["journal_path"] = hostile
            elif param == "now_fn":
                kwargs["now_fn"] = hostile
            else:
                kwargs["monotonic"] = hostile
            return pw.run_teardown([entry], **kwargs)
        if name == "wave_report":
            return pw.wave_report(hostile)
        raise AssertionError("unhandled wave function %r" % name)
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
        return ("journal_path", "slot_ref", "effect_id", "kind", "outcome", "at", "reason")
    if name == "effect":
        return ("journal_path", "slot_ref", "kind", "at", "detail", "effect_id")
    if name == "replay":
        return ("journal_path", "slot_ref")
    if name == "replay_sources":
        return ("paths", "slot_ref", "journal_path")
    if name == "partial_failure_report":
        return ("slots",)
    raise AssertionError("add driver params for new public function %r" % name)


def _appctl_params(name):
    if name == "instance_path":
        return ("slots_dir_path", "slot")
    if name == "resolve_invocation":
        return ("dev_command", "params", "readiness_url", "env")
    if name == "assert_unique_endpoints":
        return ("allocations",)
    if name == "check_endpoint_free":
        return ("host", "port", "connect", "timeout")
    if name == "retry_gate":
        return ("reason",)
    if name == "write_instance":
        return ("slots_dir_path", "slot", "instance", "timeout")
    if name == "read_instance":
        return ("slots_dir_path", "slot")
    if name == "clear_instance":
        return ("slots_dir_path", "slot", "timeout")
    if name == "stand_up":
        return (
            "launch", "journal_path", "slots_dir_path", "now", "now_fn",
            "registry", "declaration", "spawn", "readiness_probe",
            "monotonic", "sleep",
        )
    if name == "stop":
        return (
            "instance", "now_fn", "terminate", "poll_alive", "corroborate",
            "check_free", "wait_seconds", "sleep", "monotonic",
        )
    raise AssertionError("add driver params for new public function %r" % name)


def _wave_params(name):
    if name == "park_latch_path":
        return ("slots_dir_path", "slot")
    if name == "wave_anchor":
        return ("launched_at", "deadline_seconds", "margin_seconds", "monotonic")
    if name in ("wave_phase", "admit_work"):
        return ("anchor", "monotonic")
    if name == "latch_park":
        return ("slots_dir_path", "slot", "slot_ref", "now", "reason", "timeout")
    if name == "read_park_latch":
        return ("slots_dir_path", "slot", "timeout")
    if name == "validate_step_result":
        return ("result", "step", "slot_ref")
    if name == "assert_destructive_allowed":
        return ("step", "intent", "latched")
    if name == "teardown_slot":
        return ("entry", "handlers", "slots_dir_path", "journal_path", "now_fn", "monotonic")
    if name == "run_teardown":
        return ("slots", "handlers", "slots_dir_path", "journal_path", "now_fn", "monotonic")
    if name == "wave_report":
        return ("results",)
    raise AssertionError("add driver params for new public function %r" % name)


DRIVERS_LIFECYCLE = {name: _invoke_lifecycle for name in _public_callables(pl)}
DRIVERS_JOURNAL = {name: _invoke_journal for name in _public_callables(pj)}
DRIVERS_APPCTL = {name: _invoke_appctl for name in _public_callables(pa)}
DRIVERS_WAVE = {name: _invoke_wave for name in _public_callables(pw)}

assert set(DRIVERS_LIFECYCLE) == _public_callables(pl), (
    "pilot_lifecycle public API changed — add drivers for: %s"
    % sorted(_public_callables(pl) - set(DRIVERS_LIFECYCLE))
)
assert set(DRIVERS_JOURNAL) == _public_callables(pj), (
    "pilot_journal public API changed — add drivers for: %s"
    % sorted(_public_callables(pj) - set(DRIVERS_JOURNAL))
)
assert set(DRIVERS_APPCTL) == _public_callables(pa), (
    "pilot_appctl public API changed — add drivers for: %s"
    % sorted(_public_callables(pa) - set(DRIVERS_APPCTL))
)
assert set(DRIVERS_WAVE) == _public_callables(pw), (
    "pilot_wave public API changed — add drivers for: %s"
    % sorted(_public_callables(pw) - set(DRIVERS_WAVE))
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


@pytest.mark.parametrize("name", sorted(DRIVERS_APPCTL))
@pytest.mark.parametrize("hostile", HOSTILE_VALUES, ids=lambda v: repr(v)[:40])
def test_pilot_appctl_public_api_never_leaks_builtin_exceptions(name, hostile):
    for param in _appctl_params(name):
        _assert_no_leaked_exceptions("pilot_appctl", name, param, hostile, _invoke_appctl)


@pytest.mark.parametrize("name", sorted(DRIVERS_WAVE))
@pytest.mark.parametrize("hostile", HOSTILE_VALUES, ids=lambda v: repr(v)[:40])
def test_pilot_wave_public_api_never_leaks_builtin_exceptions(name, hostile):
    for param in _wave_params(name):
        _assert_no_leaked_exceptions("pilot_wave", name, param, hostile, _invoke_wave)


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


def test_stand_up_exercised_registry_refuses_nul_argv_without_leak():
    tmp = _tmp_dir()
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        os.makedirs(slots_dir, exist_ok=True)
        created = pl.create_slot(slots_dir, SLOT, ACCOUNTS, now=NOW)
        rec = pl.transition(created["record"], pl.STATE_PROVISIONED, now=NOW)
        pl.write_record(pl.record_path(slots_dir, SLOT), rec)
        journal = os.path.join(tmp, "journal.jsonl")
        launch = _valid_launch(cwd)
        launch["argv"] = ["echo\x00", "hi"]
        digest = pc.declaration_digest({"evidence": "app-lifecycle exercised"})
        registry = {
            "schemaVersion": pc.REGISTRY_SCHEMA_VERSION,
            "records": [{
                "kind": "app-lifecycle",
                "declarationDigest": digest,
                "exercisedAt": NOW,
                "receipt": {"result": "pass", "evidence": "ok"},
            }],
        }
        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir,
            now=NOW,
            now_fn=lambda: NOW,
            registry=registry,
            declaration={"evidence": "app-lifecycle exercised"},
            monotonic=lambda: 0.0,
            sleep=lambda _t: None,
        )
        assert result["reason"] == pa.REASON_COMMAND_INVALID
    finally:
        shutil.rmtree(tmp)


def _exercised_registry(declaration):
    digest = pc.declaration_digest(declaration)
    return {
        "schemaVersion": pc.REGISTRY_SCHEMA_VERSION,
        "records": [{
            "kind": "app-lifecycle",
            "declarationDigest": digest,
            "exercisedAt": NOW,
            "receipt": {"result": "pass", "evidence": "ok"},
        }],
    }


@pytest.mark.parametrize(
    "registry,declaration,slots_dir_path,expected",
    [
        (
            _exercised_registry({"evidence": "x"}),
            {"bad": {1, 2, 3}},
            None,
            pa.REASON_DECLARATION_UNEXERCISED,
        ),
        (
            _exercised_registry({"value": 1.0}),
            {"value": float("nan")},
            None,
            pa.REASON_DECLARATION_UNEXERCISED,
        ),
        (
            _exercised_registry({"evidence": "x"}),
            ["not", "a", "dict"],
            None,
            pa.REASON_DECLARATION_UNEXERCISED,
        ),
        (
            ["not", "a", "dict"],
            {"evidence": "app-lifecycle exercised"},
            None,
            pa.REASON_DECLARATION_UNEXERCISED,
        ),
        (
            _exercised_registry({"evidence": "x"}),
            {"evidence": "app-lifecycle exercised"},
            ["not", "a", "path"],
            pa.REASON_INSTANCE_RECORD_INVALID,
        ),
        (
            _exercised_registry({"evidence": "x"}),
            {"evidence": "app-lifecycle exercised"},
            42,
            pa.REASON_INSTANCE_RECORD_INVALID,
        ),
    ],
)
def test_stand_up_malformed_inputs_with_exercised_registry(
    registry, declaration, slots_dir_path, expected,
):
    tmp = _tmp_dir()
    try:
        cwd = os.path.join(tmp, "wt")
        os.makedirs(cwd)
        slots_dir = os.path.join(tmp, "slots")
        os.makedirs(slots_dir, exist_ok=True)
        created = pl.create_slot(slots_dir, SLOT, ACCOUNTS, now=NOW)
        rec = pl.transition(created["record"], pl.STATE_PROVISIONED, now=NOW)
        pl.write_record(pl.record_path(slots_dir, SLOT), rec)
        journal = os.path.join(tmp, "journal.jsonl")
        launch = _valid_launch(cwd)
        result = pa.stand_up(
            launch,
            journal_path=journal,
            slots_dir_path=slots_dir if slots_dir_path is None else slots_dir_path,
            now=NOW,
            now_fn=lambda: NOW,
            registry=registry,
            declaration=declaration,
            monotonic=lambda: 0.0,
            sleep=lambda _t: None,
        )
        assert result["reason"] == expected
    finally:
        shutil.rmtree(tmp)
