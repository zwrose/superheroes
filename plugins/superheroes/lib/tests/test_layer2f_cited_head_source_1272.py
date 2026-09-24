"""#1272 layer 2f: citedHeadSource declaration, binder chokepoint, and census."""
import importlib.util
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_driver as RD  # noqa: E402
import round_records as RR  # noqa: E402

_TCH_SPEC = importlib.util.spec_from_file_location(
    "test_cited_head_1272",
    os.path.join(_HERE, "test_cited_head_1272.py"))
_TCH = importlib.util.module_from_spec(_TCH_SPEC)
_TCH_SPEC.loader.exec_module(_TCH)

from test_recorded_row_chokepoint_1272 import FakeAdapters  # noqa: E402

_STATE = _TCH._state

_SESSION = _TCH._session
_PENDING = _TCH._pending
_AT_RUN_VERIFY = _TCH._at_run_verify
_ADVANCE = _TCH._advance

_INVALID_SOURCE = "runner-veiw"

_ENVELOPE_CITED_HEAD_ASSIGN = re.compile(
    r'\[\s*["\']citedHeadSource["\']\s*\]\s*=')


def _shipped_lib_py_paths():
    for dirpath, _dirnames, filenames in os.walk(_LIB):
        if os.path.basename(dirpath) == "tests":
            continue
        for name in filenames:
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)


def _envelope_cited_head_assign_sites():
    sites = []
    for path in _shipped_lib_py_paths():
        with open(path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                if _ENVELOPE_CITED_HEAD_ASSIGN.search(line):
                    sites.append((path, lineno, line.rstrip()))
    return sites


@pytest.fixture
def adapters(monkeypatch):
    fake = FakeAdapters()
    monkeypatch.setitem(sys.modules, "round_adapters", fake)
    return fake


def test_envelope_bind_cited_head_source_refuses_invalid():
    envelope = {"schema": RR.SEAT_RESULT_SCHEMA_V2, "payload": {"findings": []}}
    with pytest.raises(RR.IncompleteRevisionIdentity) as excinfo:
        RR.envelope_bind_cited_head_source(envelope, _INVALID_SOURCE)
    assert excinfo.value.missing == ("citedHeadSource",)


def test_record_missing_sink_inherits_binder_refusal(tmp_path, adapters, monkeypatch):
    monkeypatch.setattr(RR, "CITED_HEAD_SOURCE_ORDER_ANCHOR", _INVALID_SOURCE)
    monkeypatch.setattr(
        RR, "ingest_landing",
        lambda *args, **kwargs: {"ok": True, "storePath": os.path.join(args[0], "noop.json")})
    monkeypatch.setattr(RR, "read_json", lambda _path: ({}, None))
    monkeypatch.setattr(RR, "recorded_row_fields", lambda *args, **kwargs: {})
    monkeypatch.setattr(RD, "_journal_event", lambda *args, **kwargs: None)
    d = _SESSION(tmp_path)
    pend = _PENDING(d)
    with pytest.raises(RR.IncompleteRevisionIdentity) as excinfo:
        RD.cmd_record_missing(d, "security-reviewer", pend["attempt"], "forfeit")
    assert excinfo.value.missing == ("citedHeadSource",)


def test_orchestrator_fulfilled_sink_inherits_binder_refusal(tmp_path, adapters, monkeypatch):
    d = _SESSION(tmp_path)
    state = _STATE(d)
    pend = _PENDING(d)
    monkeypatch.setattr(RR, "CITED_HEAD_SOURCE_ORDER_ANCHOR", _INVALID_SOURCE)
    with pytest.raises(RR.IncompleteRevisionIdentity) as excinfo:
        RD._orchestrator_fulfilled_envelope(
            d, state, RD.P_VERIFY, pend["round"], pend["attempt"], "verify", 0,
            {"result": "pass"}, RD._meta_session_id(d))
    assert excinfo.value.missing == ("citedHeadSource",)


def test_record_missing_sink_binds_order_anchor(tmp_path, adapters):
    d = _SESSION(tmp_path)
    pend = _PENDING(d)
    seat = "security-reviewer"
    out = RD.cmd_record_missing(d, seat, pend["attempt"], "forfeit")
    assert out["ok"], out
    store_path = out["storePath"]
    stored, err = RR.read_json(store_path)
    assert err is None
    assert stored["citedHeadSource"] == RR.CITED_HEAD_SOURCE_ORDER_ANCHOR


def test_orchestrator_fulfilled_sink_binds_order_anchor(tmp_path, adapters):
    d = _SESSION(tmp_path, seatMap=_TCH.RUNNER_SEAT_MAP)
    _AT_RUN_VERIFY(tmp_path, d)
    pend = _PENDING(d)
    skey = RR.storage_key("verify")
    path = RR.bare_payload_path(d, pend["round"], pend["phase"], skey, pend["attempt"])
    RR.atomic_write_json(path, {"result": "pass"})
    out = _ADVANCE(d, tmp_path)
    assert out["ok"], out
    store_path = RR.store_path(d, pend["round"], RD.P_VERIFY, skey, pend["attempt"])
    stored, err = RR.read_json(store_path)
    assert err is None
    assert stored["citedHeadSource"] == RR.CITED_HEAD_SOURCE_ORDER_ANCHOR


def test_cited_head_source_envelope_writer_census():
    sites = _envelope_cited_head_assign_sites()
    assert len(sites) == 1, "expected exactly one envelope citedHeadSource assign; got %r" % sites
    path, lineno, _line = sites[0]
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    before = "".join(lines[:lineno - 1])
    func_name = re.findall(r"def (\w+)\(", before)[-1]
    assert func_name == "envelope_bind_cited_head_source"
    driver_path = os.path.join(_LIB, "round_driver.py")
    with open(driver_path, encoding="utf-8") as fh:
        driver_text = fh.read()
    assert '"citedHeadSource":' not in driver_text
