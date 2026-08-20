"""Tests for package_read_audit (#937)."""
import copy
import itertools
import json
import os
import re
import subprocess
import sys

import pytest

import package_read_audit as pra

_HERE = os.path.dirname(os.path.abspath(__file__))
_MODULE = os.path.join(os.path.dirname(_HERE), "package_read_audit.py")
_PYTHON = sys.executable
_PYFLAGS = ["-B", "-X", "pycache_prefix=/private/tmp/superheroes-pyc"]


def _run_cli(*args):
    cmd = [_PYTHON, *_PYFLAGS, _MODULE, *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def _stdout_has_no_json(stdout):
    text = stdout.strip()
    if not text:
        return True
    try:
        json.loads(text)
    except json.JSONDecodeError:
        return True
    return False


def _assert_write_result_keys(result):
    assert set(result.keys()) == set(pra.WRITE_RESULT_FIELDS)


def _assert_check_result_keys(result):
    assert set(result.keys()) == set(pra.CHECK_RESULT_FIELDS)


def _trail_bytes(path):
    if not os.path.isfile(path):
        return b""
    return path.read_bytes() if hasattr(path, "read_bytes") else open(path, "rb").read()


def _open_default(tmp_path, trail=None, invocation="inv-1", ceiling=3, seats=None):
    if trail is None:
        trail = tmp_path / "trail.md"
    if seats is None:
        seats = ["seat-a"]
    code, out, _err = _run_cli(
        "open",
        "--trail", str(trail),
        "--invocation", invocation,
        "--cause", "initial read",
        "--weight", pra.WEIGHT_LIGHT,
        "--children", "2",
        "--register-entries", "1",
        "--ceiling", str(ceiling),
        "--seat", seats[0],
        *[
            arg for seat in seats[1:]
            for arg in ("--seat", seat)
        ],
    )
    assert code == pra.EXIT_RECORDED, out
    payload = json.loads(out.strip())
    _assert_write_result_keys(payload)
    return trail, payload


def _record_round(
    trail,
    invocation="inv-1",
    round_no=1,
    lenses=None,
    parts=None,
    control_probe=pra.CONTROL_PROBE_ENGAGED,
    findings=None,
    declined=None,
    mechanical_only=False,
):
    if lenses is None:
        lenses = [pra.LENS_SPEC_CONTRADICTION]
    if parts is None:
        parts = ["slice-a:unreviewed"]
    if findings is None:
        findings = []
    if declined is None:
        declined = []
    args = [
        "record-round",
        "--trail", str(trail),
        "--invocation", invocation,
        "--round", str(round_no),
        "--control-probe", control_probe,
    ]
    for lens in lenses:
        args.extend(["--lens", lens])
    for part in parts:
        args.extend(["--part", part])
    for finding in findings:
        args.extend(["--finding", finding])
    for fid in declined:
        args.extend(["--declined-extension", fid])
    if mechanical_only:
        args.append("--mechanical-only")
    return _run_cli(*args)


def _record_verification(
    trail,
    invocation="inv-1",
    findings=None,
    sync_checks=None,
    evidence=None,
):
    if findings is None:
        findings = []
    if sync_checks is None:
        sync_checks = []
    if evidence is None:
        evidence = []
    args = [
        "record-verification",
        "--trail", str(trail),
        "--invocation", invocation,
    ]
    for finding in findings:
        args.extend(["--finding", finding])
    for item in evidence:
        args.extend(["--evidence", item])
    for sync_check in sync_checks:
        args.extend(["--sync-check", sync_check])
    return _run_cli(*args)


# --- happy path per verb ----------------------------------------------------


def test_open_happy_path(tmp_path):
    trail = tmp_path / "trail.md"
    code, out, _err = _run_cli(
        "open",
        "--trail", str(trail),
        "--invocation", "inv-1",
        "--cause", "weight call",
        "--weight", pra.WEIGHT_FULL,
        "--children", "4",
        "--register-entries", "7",
        "--ceiling", "2",
        "--override", "small epic",
        "--seat", "alpha",
        "--seat", "beta",
    )
    assert code == pra.EXIT_RECORDED
    payload = json.loads(out.strip())
    assert payload["result"] == pra.RESULT_RECORDED
    assert payload["ok"] is True
    assert payload["record"] == {
        "kind": "invocation",
        "invocation": "inv-1",
        "cause": "weight call",
        "weight": "full",
        "measurables": {"children": 4, "registerEntries": 7},
        "ceiling": 2,
        "override": "small epic",
        "seats": ["alpha", "beta"],
    }
    text = trail.read_text(encoding="utf-8")
    assert text.startswith(pra.TRAIL_HEADING)
    assert pra.RECORD_MARKER in text


def test_record_round_happy_path(tmp_path):
    trail, _open_payload = _open_default(tmp_path)
    code, out, _err = _record_round(
        trail,
        findings=["f-1:spec-contradiction"],
        parts=["slice-a:unreviewed", "slice-b:reviewed"],
        lenses=[pra.LENS_COLLISIONS, pra.LENS_DOD_ADEQUACY],
    )
    assert code == pra.EXIT_RECORDED
    payload = json.loads(out.strip())
    assert payload["record"] == {
        "kind": "round",
        "invocation": "inv-1",
        "round": 1,
        "lenses": [pra.LENS_COLLISIONS, pra.LENS_DOD_ADEQUACY],
        "parts": [
            {"part": "slice-a", "status": "unreviewed"},
            {"part": "slice-b", "status": "reviewed"},
        ],
        "controlProbe": pra.CONTROL_PROBE_ENGAGED,
        "findings": [{"finding": "f-1", "lens": pra.LENS_SPEC_CONTRADICTION}],
        "declinedExtension": [],
        "mechanicalOnly": False,
    }


def test_record_verification_happy_path(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    code, out, _err = _record_verification(
        trail,
        findings=["f-1:package-fix:verified"],
        sync_checks=["child-a:pass"],
    )
    assert code == pra.EXIT_RECORDED
    payload = json.loads(out.strip())
    assert payload["record"] == {
        "kind": "verification",
        "invocation": "inv-1",
        "findings": [{
            "finding": "f-1",
            "disposition": "package-fix",
            "outcome": "verified",
        }],
        "syncChecks": [{"child": "child-a", "result": "pass"}],
    }


def test_check_happy_path(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail)
    _record_verification(
        trail,
        findings=[],
        sync_checks=["c1:pass", "c2:pass"],
    )
    result = pra.verb_check(str(trail))
    _assert_check_result_keys(result)
    assert result["result"] == pra.RESULT_CONFORMING


# --- round trip -------------------------------------------------------------


def test_round_trip_conforming(tmp_path):
    trail, _ = _open_default(tmp_path, ceiling=2)
    _record_round(
        trail,
        round_no=1,
        findings=["f-1:register-drift"],
        parts=["pkg:unreviewed"],
    )
    _record_round(
        trail,
        round_no=2,
        mechanical_only=True,
        parts=["pkg:reviewed"],
    )
    _record_verification(
        trail,
        findings=["f-1:package-fix:verified"],
        sync_checks=["c1:pass", "c2:pass"],
    )
    code, out, _err = _run_cli("check", "--trail", str(trail))
    assert code == pra.EXIT_CONFORMING
    payload = json.loads(out.strip())
    assert payload["result"] == pra.RESULT_CONFORMING
    summary = payload["invocations"][0]
    assert summary["roundsRecorded"] == 2
    assert summary["findingsRecorded"] == 1
    assert "converged" not in summary
    assert "ceilingReached" not in summary
    assert "parkOwed" not in summary


def test_round_trip_unconverged_below_ceiling(tmp_path):
    trail, _ = _open_default(tmp_path, ceiling=3)
    _record_round(
        trail,
        round_no=1,
        findings=["f-1:collisions"],
        parts=["pkg:unreviewed"],
    )
    code, out, _err = _run_cli("check", "--trail", str(trail))
    assert code == pra.EXIT_NONCONFORMING
    payload = json.loads(out.strip())
    assert any(
        item["kind"] == pra.NONCONFORMITY_ELEMENT_MISSING
        and "verification record" in item["detail"]
        for item in payload["findings"]
    )


def test_park_owed_is_conforming(tmp_path):
    trail, _ = _open_default(tmp_path, ceiling=1)
    _record_round(
        trail,
        round_no=1,
        findings=["f-1:collisions"],
        parts=["pkg:unreviewed"],
    )
    _record_verification(
        trail,
        findings=["f-1:package-fix:failed"],
        sync_checks=["c1:pass", "c2:pass"],
    )
    code, out, _err = _run_cli("check", "--trail", str(trail))
    assert code == pra.EXIT_CONFORMING
    payload = json.loads(out.strip())
    assert payload["findings"] == []
    summary = payload["invocations"][0]
    assert "converged" not in summary
    assert "ceilingReached" not in summary
    assert "parkOwed" not in summary


# --- refusal reasons --------------------------------------------------------


def _assert_refusal_no_append(trail, before, code, out, reason):
    assert code == pra.EXIT_REFUSED
    payload = json.loads(out.strip())
    assert payload["reason"] == reason
    assert payload["ok"] is False
    assert payload["result"] == pra.RESULT_REFUSED
    after = _trail_bytes(trail)
    assert after == before


def test_refusal_trail_unreadable(tmp_path, monkeypatch):
    trail = tmp_path / "trail.md"
    trail.write_text(pra.TRAIL_HEADING + "\n", encoding="utf-8")
    before = _trail_bytes(trail)
    monkeypatch.setattr(pra, "_read_lines", lambda _path: None)
    result = pra.verb_record_round(
        str(trail),
        "inv-1",
        1,
        [pra.LENS_COLLISIONS],
        ["pkg:unreviewed"],
        pra.CONTROL_PROBE_ENGAGED,
        [],
        [],
        False,
    )
    assert result["reason"] == pra.REFUSAL_TRAIL_UNREADABLE
    assert result["ok"] is False
    assert _trail_bytes(trail) == before


def test_refusal_trail_missing(tmp_path):
    trail = tmp_path / "missing.md"
    before = b""
    code, out, _err = _record_round(trail)
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_TRAIL_MISSING)


def test_refusal_trail_malformed_on_write(tmp_path):
    trail = tmp_path / "trail.md"
    trail.write_text(
        pra.TRAIL_HEADING + "\n\n"
        + pra.RECORD_MARKER + "\n"
        + "```json\n"
        + "[1, 2]\n"
        + "```\n",
        encoding="utf-8",
    )
    before = _trail_bytes(trail)
    code, out, _err = _record_round(trail)
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_TRAIL_MALFORMED)


def test_refusal_invocation_duplicate(tmp_path):
    trail, _ = _open_default(tmp_path)
    before = _trail_bytes(trail)
    code, out, _err = _run_cli(
        "open",
        "--trail", str(trail),
        "--invocation", "inv-1",
        "--cause", "again",
        "--weight", pra.WEIGHT_LIGHT,
        "--children", "1",
        "--register-entries", "1",
        "--ceiling", "1",
        "--seat", "seat-a",
    )
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_INVOCATION_DUPLICATE)


def test_refusal_invocation_unknown(tmp_path):
    trail, _ = _open_default(tmp_path)
    before = _trail_bytes(trail)
    code, out, _err = _record_round(trail, invocation="missing")
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_INVOCATION_UNKNOWN)


def test_refusal_round_duplicate(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, round_no=1)
    before = _trail_bytes(trail)
    code, out, _err = _record_round(trail, round_no=1)
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_ROUND_DUPLICATE)


def test_refusal_round_exceeds_ceiling(tmp_path):
    trail, _ = _open_default(tmp_path, ceiling=1)
    _record_round(trail, round_no=1)
    before = _trail_bytes(trail)
    code, out, _err = _record_round(trail, round_no=2)
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_ROUND_EXCEEDS_CEILING)


def test_refusal_round_invalid(tmp_path):
    trail, _ = _open_default(tmp_path)
    before = _trail_bytes(trail)
    code, out, _err = _record_round(trail, round_no=0)
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_ROUND_INVALID)


def test_refusal_lens_unrecognized(tmp_path):
    trail, _ = _open_default(tmp_path)
    before = _trail_bytes(trail)
    code, out, _err = _run_cli(
        "record-round",
        "--trail", str(trail),
        "--invocation", "inv-1",
        "--round", "1",
        "--lens", "bogus-lens",
        "--part", "pkg:unreviewed",
        "--control-probe", pra.CONTROL_PROBE_ENGAGED,
    )
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_LENS_UNRECOGNIZED)


def test_refusal_part_malformed(tmp_path):
    trail, _ = _open_default(tmp_path)
    before = _trail_bytes(trail)
    code, out, _err = _record_round(trail, parts=["nopartstatus"])
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_PART_MALFORMED)


def test_refusal_part_status_unrecognized(tmp_path):
    trail, _ = _open_default(tmp_path)
    before = _trail_bytes(trail)
    code, out, _err = _record_round(trail, parts=["pkg:wip"])
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_PART_STATUS_UNRECOGNIZED)


def test_refusal_control_probe_unrecognized(tmp_path):
    trail, _ = _open_default(tmp_path)
    before = _trail_bytes(trail)
    code, out, _err = _record_round(trail, control_probe="maybe")
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_CONTROL_PROBE_UNRECOGNIZED)


def test_refusal_finding_malformed(tmp_path):
    trail, _ = _open_default(tmp_path)
    before = _trail_bytes(trail)
    code, out, _err = _record_round(trail, findings=["nofindinglens"])
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_FINDING_MALFORMED)


def test_refusal_finding_duplicate(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    before = _trail_bytes(trail)
    code, out, _err = _record_round(
        trail,
        round_no=2,
        findings=["f-1:collisions"],
    )
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_FINDING_DUPLICATE)


def test_refusal_finding_unknown_on_round(tmp_path):
    trail, _ = _open_default(tmp_path)
    before = _trail_bytes(trail)
    code, out, _err = _run_cli(
        "record-round",
        "--trail", str(trail),
        "--invocation", "inv-1",
        "--round", "1",
        "--lens", pra.LENS_COLLISIONS,
        "--part", "pkg:unreviewed",
        "--control-probe", pra.CONTROL_PROBE_ENGAGED,
        "--declined-extension", "ghost",
    )
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_FINDING_UNKNOWN)


def test_refusal_finding_unknown_on_verification(tmp_path):
    trail, _ = _open_default(tmp_path)
    before = _trail_bytes(trail)
    code, out, _err = _record_verification(
        trail,
        findings=["ghost:package-fix:verified"],
    )
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_FINDING_UNKNOWN)


def test_refusal_verification_duplicate(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    _record_verification(trail, findings=["f-1:package-fix:verified"])
    before = _trail_bytes(trail)
    code, out, _err = _record_verification(
        trail,
        findings=["f-1:spec-amendment:verified"],
        sync_checks=["c1:pass", "c2:pass"],
    )
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_VERIFICATION_DUPLICATE)


def test_refusal_disposition_unrecognized(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    before = _trail_bytes(trail)
    code, out, _err = _record_verification(
        trail,
        findings=["f-1:bogus:verified"],
    )
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_DISPOSITION_UNRECOGNIZED)


def test_refusal_outcome_unrecognized(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    before = _trail_bytes(trail)
    code, out, _err = _record_verification(
        trail,
        findings=["f-1:package-fix:bogus"],
    )
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_OUTCOME_UNRECOGNIZED)


def test_refusal_sync_check_malformed(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    before = _trail_bytes(trail)
    code, out, _err = _record_verification(
        trail,
        findings=["f-1:package-fix:verified"],
        sync_checks=["childonly"],
    )
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_SYNC_CHECK_MALFORMED)


def test_refusal_sync_result_unrecognized(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    before = _trail_bytes(trail)
    code, out, _err = _record_verification(
        trail,
        findings=["f-1:package-fix:verified"],
        sync_checks=["child-a:bogus"],
    )
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_SYNC_RESULT_UNRECOGNIZED)


def test_refusal_weight_unrecognized(tmp_path):
    trail = tmp_path / "trail.md"
    code, out, _err = _run_cli(
        "open",
        "--trail", str(trail),
        "--invocation", "inv-1",
        "--cause", "x",
        "--weight", "heavy",
        "--children", "1",
        "--register-entries", "1",
        "--ceiling", "1",
        "--seat", "seat-a",
    )
    assert code == pra.EXIT_REFUSED
    payload = json.loads(out.strip())
    assert payload["reason"] == pra.REFUSAL_WEIGHT_UNRECOGNIZED
    assert not trail.exists()


def test_refusal_ceiling_invalid(tmp_path):
    trail = tmp_path / "trail.md"
    code, out, _err = _run_cli(
        "open",
        "--trail", str(trail),
        "--invocation", "inv-1",
        "--cause", "x",
        "--weight", pra.WEIGHT_LIGHT,
        "--children", "1",
        "--register-entries", "1",
        "--ceiling", "0",
        "--seat", "seat-a",
    )
    assert code == pra.EXIT_REFUSED
    payload = json.loads(out.strip())
    assert payload["reason"] == pra.REFUSAL_CEILING_INVALID
    assert not trail.exists()


def test_refusal_measurable_invalid_children(tmp_path):
    trail = tmp_path / "trail.md"
    code, out, _err = _run_cli(
        "open",
        "--trail", str(trail),
        "--invocation", "inv-1",
        "--cause", "x",
        "--weight", pra.WEIGHT_LIGHT,
        "--children", "-1",
        "--register-entries", "1",
        "--ceiling", "1",
        "--seat", "seat-a",
    )
    assert code == pra.EXIT_REFUSED
    payload = json.loads(out.strip())
    assert payload["reason"] == pra.REFUSAL_MEASURABLE_INVALID


def test_refusal_measurable_invalid_register_entries(tmp_path):
    trail = tmp_path / "trail.md"
    code, out, _err = _run_cli(
        "open",
        "--trail", str(trail),
        "--invocation", "inv-1",
        "--cause", "x",
        "--weight", pra.WEIGHT_LIGHT,
        "--children", "1",
        "--register-entries", "nope",
        "--ceiling", "1",
        "--seat", "seat-a",
    )
    assert code == pra.EXIT_REFUSED
    payload = json.loads(out.strip())
    assert payload["reason"] == pra.REFUSAL_MEASURABLE_INVALID


def test_refusal_seats_missing(tmp_path):
    trail = tmp_path / "trail.md"
    code, out, _err = _run_cli(
        "open",
        "--trail", str(trail),
        "--invocation", "inv-1",
        "--cause", "x",
        "--weight", pra.WEIGHT_LIGHT,
        "--children", "1",
        "--register-entries", "1",
        "--ceiling", "1",
    )
    assert code == pra.EXIT_REFUSED
    payload = json.loads(out.strip())
    assert payload["reason"] == pra.REFUSAL_SEATS_MISSING


def test_refusal_usage_record_verification(tmp_path):
    trail, _ = _open_default(tmp_path)
    before = _trail_bytes(trail)
    code, out, _err = _record_verification(trail, findings=[], sync_checks=[])
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_USAGE)


def test_refusal_usage_cli(tmp_path):
    code, out, _err = _run_cli("open", "--trail", str(tmp_path / "t.md"))
    assert code == pra.EXIT_REFUSED
    payload = json.loads(out.strip())
    assert payload["reason"] == pra.REFUSAL_USAGE


def test_refusal_internal_error(tmp_path, monkeypatch, capsys):
    trail, _ = _open_default(tmp_path)

    def boom(*_args, **_kwargs):
        raise RuntimeError("probe")

    monkeypatch.setattr(pra, "verb_record_round", boom)
    code = pra.main([
        "record-round",
        "--trail", str(trail),
        "--invocation", "inv-1",
        "--round", "1",
        "--lens", pra.LENS_COLLISIONS,
        "--part", "pkg:unreviewed",
        "--control-probe", pra.CONTROL_PROBE_ENGAGED,
    ])
    out = capsys.readouterr().out
    assert code == pra.EXIT_REFUSED
    payload = json.loads(out.strip())
    assert payload["reason"] == pra.REFUSAL_INTERNAL_ERROR


# --- nonconformity kinds ----------------------------------------------------


def _hand_append_record(trail, record):
    block = pra._format_record(record)
    with open(trail, "a", encoding="utf-8", newline="") as fh:
        fh.write("\n")
        fh.write(block.lstrip("\n"))


def test_nonconformity_round_missing(tmp_path):
    trail, _ = _open_default(tmp_path)
    code, out, _err = _run_cli("check", "--trail", str(trail))
    assert code == pra.EXIT_NONCONFORMING
    payload = json.loads(out.strip())
    assert payload["findings"][0]["kind"] == pra.NONCONFORMITY_ROUND_MISSING


def test_nonconformity_element_missing_lenses(tmp_path):
    trail, _ = _open_default(tmp_path)
    _hand_append_record(trail, {
        "kind": "round",
        "invocation": "inv-1",
        "round": 1,
        "lenses": [],
        "parts": [{"part": "slice-a", "status": "unreviewed"}],
        "controlProbe": pra.CONTROL_PROBE_ENGAGED,
        "findings": [],
        "declinedExtension": [],
        "mechanicalOnly": False,
    })
    code, out, _err = _run_cli("check", "--trail", str(trail))
    assert code == pra.EXIT_NONCONFORMING
    findings = json.loads(out.strip())["findings"]
    kinds = {item["kind"] for item in findings}
    assert pra.NONCONFORMITY_ELEMENT_MISSING in kinds
    assert any(
        item["kind"] == pra.NONCONFORMITY_ELEMENT_MISSING
        and "lenses" in item["detail"]
        for item in findings
    )


def test_nonconformity_element_missing_parts(tmp_path):
    trail, _ = _open_default(tmp_path)
    _hand_append_record(trail, {
        "kind": "round",
        "invocation": "inv-1",
        "round": 1,
        "lenses": [pra.LENS_COLLISIONS],
        "parts": [],
        "controlProbe": pra.CONTROL_PROBE_ENGAGED,
        "findings": [],
        "declinedExtension": [],
        "mechanicalOnly": False,
    })
    code, out, _err = _run_cli("check", "--trail", str(trail))
    assert code == pra.EXIT_NONCONFORMING
    findings = json.loads(out.strip())["findings"]
    kinds = {item["kind"] for item in findings}
    assert pra.NONCONFORMITY_ELEMENT_MISSING in kinds
    assert any(
        item["kind"] == pra.NONCONFORMITY_ELEMENT_MISSING
        and "parts" in item["detail"]
        for item in findings
    )


def test_nonconformity_element_missing_control_probe(tmp_path):
    trail, _ = _open_default(tmp_path)
    _hand_append_record(trail, {
        "kind": "round",
        "invocation": "inv-1",
        "round": 1,
        "lenses": [pra.LENS_COLLISIONS],
        "parts": [{"part": "slice-a", "status": "unreviewed"}],
        "controlProbe": None,
        "findings": [],
        "declinedExtension": [],
        "mechanicalOnly": False,
    })
    code, out, _err = _run_cli("check", "--trail", str(trail))
    assert code == pra.EXIT_NONCONFORMING
    findings = json.loads(out.strip())["findings"]
    kinds = {item["kind"] for item in findings}
    assert pra.NONCONFORMITY_ELEMENT_MISSING in kinds
    assert any(
        item["kind"] == pra.NONCONFORMITY_ELEMENT_MISSING
        and "controlProbe" in item["detail"]
        for item in findings
    )


def test_nonconformity_finding_unverified(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions", "f-2:register-drift"])
    _record_verification(
        trail,
        findings=["f-1:package-fix:verified"],
        sync_checks=["c1:pass", "c2:pass"],
    )
    code, out, _err = _run_cli("check", "--trail", str(trail))
    assert code == pra.EXIT_NONCONFORMING
    payload = json.loads(out.strip())
    assert any(
        item["kind"] == pra.NONCONFORMITY_FINDING_UNVERIFIED
        and "f-2" in item["detail"]
        for item in payload["findings"]
    )


def test_nonconformity_disposition_mismatch_declined_not_named(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    _record_verification(
        trail,
        findings=["f-1:declined-extension:verified"],
        sync_checks=["c1:pass"],
    )
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING
    assert any(
        item["kind"] == pra.NONCONFORMITY_DISPOSITION_MISMATCH
        for item in payload["findings"]
    )


def test_nonconformity_disposition_mismatch_named_not_declined(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(
        trail,
        findings=["f-1:collisions"],
        declined=["f-1"],
    )
    _record_verification(
        trail,
        findings=["f-1:package-fix:verified"],
        sync_checks=["c1:pass"],
    )
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING
    assert any(
        item["kind"] == pra.NONCONFORMITY_DISPOSITION_MISMATCH
        for item in payload["findings"]
    )


def test_nonconformity_sync_check_missing(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    _record_verification(trail, findings=["f-1:package-fix:verified"])
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING
    assert any(
        item["kind"] == pra.NONCONFORMITY_SYNC_CHECK_MISSING
        for item in payload["findings"]
    )


def test_nonconformity_sync_check_failed(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    _record_verification(
        trail,
        findings=["f-1:package-fix:verified"],
        sync_checks=["c1:fail", "c2:pass"],
    )
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING
    assert any(
        item["kind"] == pra.NONCONFORMITY_SYNC_CHECK_FAILED
        for item in payload["findings"]
    )


def test_nonconformity_sync_check_incomplete(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    _record_verification(
        trail,
        findings=["f-1:package-fix:verified"],
        sync_checks=["c1:pass"],
    )
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING
    assert any(
        item["kind"] == pra.NONCONFORMITY_SYNC_CHECK_INCOMPLETE
        for item in payload["findings"]
    )


def test_nonconformity_refutation_evidence_missing_survives_later_legal_verification(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    _hand_append_record(trail, {
        "kind": "verification",
        "invocation": "inv-1",
        "findings": [{
            "finding": "f-1",
            "disposition": "refutation",
            "outcome": "failed",
        }],
        "syncChecks": [],
    })
    _hand_append_record(trail, {
        "kind": "verification",
        "invocation": "inv-1",
        "findings": [{
            "finding": "f-1",
            "disposition": "package-fix",
            "outcome": "verified",
        }],
        "syncChecks": [
            {"child": "c1", "result": "pass"},
            {"child": "c2", "result": "pass"},
        ],
    })
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING
    assert any(
        item["kind"] == pra.NONCONFORMITY_REFUTATION_EVIDENCE_MISSING
        for item in payload["findings"]
    )


def test_nonconformity_disposition_not_allowed_for_lens_hand_appended(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:spec-contradiction"])
    _hand_append_record(trail, {
        "kind": "verification",
        "invocation": "inv-1",
        "findings": [{
            "finding": "f-1",
            "disposition": "declined-extension",
            "outcome": "verified",
        }],
        "syncChecks": [{"child": "c1", "result": "pass"}, {"child": "c2", "result": "pass"}],
    })
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING
    assert any(
        item["kind"] == pra.NONCONFORMITY_DISPOSITION_NOT_ALLOWED_FOR_LENS
        for item in payload["findings"]
    )


def test_nonconformity_refutation_evidence_missing(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    _hand_append_record(trail, {
        "kind": "verification",
        "invocation": "inv-1",
        "findings": [{
            "finding": "f-1",
            "disposition": "refutation",
            "outcome": "verified",
        }],
        "syncChecks": [{"child": "c1", "result": "pass"}, {"child": "c2", "result": "pass"}],
    })
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING
    assert any(
        item["kind"] == pra.NONCONFORMITY_REFUTATION_EVIDENCE_MISSING
        for item in payload["findings"]
    )


def test_nonconformity_element_missing_invocation_cause(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail)
    text = trail.read_text(encoding="utf-8")
    text = text.replace('"cause": "initial read"', '"cause": null', 1)
    trail.write_text(text, encoding="utf-8")
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING
    assert any(
        item["kind"] == pra.NONCONFORMITY_ELEMENT_MISSING
        and "cause" in item["detail"]
        for item in payload["findings"]
    )


def test_verification_pass_missing_element(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, mechanical_only=True)
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING
    assert any(
        item["kind"] == pra.NONCONFORMITY_ELEMENT_MISSING
        and item["detail"] == "invocation has no verification record"
        for item in payload["findings"]
    )


def test_refusal_disposition_not_allowed_for_lens(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(
        trail,
        findings=["f-1:spec-contradiction"],
        declined=["f-1"],
    )
    before = _trail_bytes(trail)
    code, out, _err = _record_verification(
        trail,
        findings=["f-1:declined-extension:verified"],
        sync_checks=["c1:pass", "c2:pass"],
    )
    _assert_refusal_no_append(
        trail,
        before,
        code,
        out,
        pra.REFUSAL_DISPOSITION_NOT_ALLOWED_FOR_LENS,
    )


def test_refusal_evidence_empty(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    before = _trail_bytes(trail)
    code, out, _err = _record_verification(
        trail,
        findings=["f-1:refutation:verified"],
        evidence=["f-1: "],
        sync_checks=["c1:pass", "c2:pass"],
    )
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_EVIDENCE_EMPTY)


def test_refusal_sync_check_duplicate(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    before = _trail_bytes(trail)
    code, out, _err = _record_verification(
        trail,
        findings=["f-1:package-fix:verified"],
        sync_checks=["c1:pass", "c1:pass"],
    )
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_SYNC_CHECK_DUPLICATE)


def test_refutation_with_evidence_happy_path(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    code, out, _err = _record_verification(
        trail,
        findings=["f-1:refutation:verified"],
        evidence=["f-1:spec section 4 covers this case"],
        sync_checks=["c1:pass", "c2:pass"],
    )
    assert code == pra.EXIT_RECORDED
    payload = json.loads(out.strip())
    assert payload["record"]["findings"][0]["evidence"] == "spec section 4 covers this case"


def test_open_multi_seat(tmp_path):
    trail, payload = _open_default(tmp_path, seats=["alpha", "beta", "gamma"])
    assert payload["record"]["seats"] == ["alpha", "beta", "gamma"]


def test_check_groups_multiple_invocations(tmp_path):
    trail, _ = _open_default(tmp_path, invocation="inv-1")
    _record_round(trail, invocation="inv-1")
    _record_verification(
        trail,
        invocation="inv-1",
        findings=[],
        sync_checks=["c1:pass", "c2:pass"],
    )
    _run_cli(
        "open",
        "--trail", str(trail),
        "--invocation", "inv-2",
        "--cause", "re-read",
        "--weight", pra.WEIGHT_LIGHT,
        "--children", "2",
        "--register-entries", "1",
        "--ceiling", "2",
        "--seat", "seat-b",
    )
    _record_round(trail, invocation="inv-2", round_no=1)
    _record_verification(
        trail,
        invocation="inv-2",
        findings=[],
        sync_checks=["c1:pass", "c2:pass"],
    )
    code, out, _err = _run_cli("check", "--trail", str(trail))
    assert code == pra.EXIT_CONFORMING
    payload = json.loads(out.strip())
    inv_ids = [item["invocation"] for item in payload["invocations"]]
    assert inv_ids == ["inv-1", "inv-2"]


def test_check_invocation_filter_selects_one(tmp_path):
    trail, _ = _open_default(tmp_path, invocation="inv-1")
    _record_round(trail, invocation="inv-1")
    _run_cli(
        "open",
        "--trail", str(trail),
        "--invocation", "inv-2",
        "--cause", "re-read",
        "--weight", pra.WEIGHT_LIGHT,
        "--children", "2",
        "--register-entries", "1",
        "--ceiling", "2",
        "--seat", "seat-b",
    )
    _record_round(trail, invocation="inv-2", round_no=1)
    code, out, _err = _run_cli(
        "check", "--trail", str(trail), "--invocation", "inv-2",
    )
    payload = json.loads(out.strip())
    assert [item["invocation"] for item in payload["invocations"]] == ["inv-2"]


# --- undecided reasons ------------------------------------------------------


def test_undecided_trail_unreadable(tmp_path, monkeypatch):
    trail = tmp_path / "trail.md"
    trail.write_text(pra.TRAIL_HEADING + "\n", encoding="utf-8")
    monkeypatch.setattr(pra, "_read_lines", lambda _path: None)
    result = pra.verb_check(str(trail))
    assert result["reason"] == pra.UNDECIDED_TRAIL_UNREADABLE
    assert result["result"] == pra.RESULT_UNDECIDED


def test_undecided_trail_missing(tmp_path):
    trail = tmp_path / "missing.md"
    code, out, _err = _run_cli("check", "--trail", str(trail))
    assert code == pra.EXIT_UNDECIDED
    payload = json.loads(out.strip())
    assert payload["reason"] == pra.UNDECIDED_TRAIL_MISSING


def test_undecided_trail_empty(tmp_path):
    trail = tmp_path / "trail.md"
    trail.write_text(pra.TRAIL_HEADING + "\n", encoding="utf-8")
    code, out, _err = _run_cli("check", "--trail", str(trail))
    assert code == pra.EXIT_UNDECIDED
    payload = json.loads(out.strip())
    assert payload["reason"] == pra.UNDECIDED_TRAIL_EMPTY


def test_undecided_trail_malformed(tmp_path):
    trail = tmp_path / "trail.md"
    trail.write_text(
        pra.TRAIL_HEADING + "\n\n```json\n{}\n",
        encoding="utf-8",
    )
    code, out, _err = _run_cli("check", "--trail", str(trail))
    assert code == pra.EXIT_UNDECIDED
    payload = json.loads(out.strip())
    assert payload["reason"] == pra.UNDECIDED_TRAIL_MALFORMED


def test_undecided_invocation_unknown(tmp_path):
    trail, _ = _open_default(tmp_path)
    code, out, _err = _run_cli(
        "check", "--trail", str(trail), "--invocation", "missing",
    )
    assert code == pra.EXIT_UNDECIDED
    payload = json.loads(out.strip())
    assert payload["reason"] == pra.UNDECIDED_INVOCATION_UNKNOWN


def test_undecided_usage_cli():
    code, out, _err = _run_cli("check")
    assert code == pra.EXIT_UNDECIDED
    payload = json.loads(out.strip())
    assert payload["reason"] == pra.UNDECIDED_USAGE


def test_undecided_internal_error(tmp_path, monkeypatch, capsys):
    trail, _ = _open_default(tmp_path)

    def boom(*_args, **_kwargs):
        raise RuntimeError("probe")

    monkeypatch.setattr(pra, "verb_check", boom)
    code = pra.main(["check", "--trail", str(trail)])
    out = capsys.readouterr().out
    assert code == pra.EXIT_UNDECIDED
    payload = json.loads(out.strip())
    assert payload["reason"] == pra.UNDECIDED_INTERNAL_ERROR


def test_check_records_without_invocation_nonconforming(tmp_path):
    trail = tmp_path / "trail.md"
    trail.write_text(pra.TRAIL_HEADING + "\n", encoding="utf-8")
    _hand_append_record(trail, {
        "kind": "round",
        "invocation": "orphan",
        "round": 1,
        "lenses": [pra.LENS_COLLISIONS],
        "parts": [{"part": "pkg", "status": "unreviewed"}],
        "controlProbe": pra.CONTROL_PROBE_ENGAGED,
        "findings": [],
        "declinedExtension": [],
        "mechanicalOnly": False,
    })
    code, out, _err = _run_cli("check", "--trail", str(trail))
    assert code == pra.EXIT_NONCONFORMING
    payload = json.loads(out.strip())
    assert payload["invocations"] == []
    assert payload["findings"] == []


# --- marker discipline ------------------------------------------------------


def test_marker_discipline_unmarked_fence_ignored(tmp_path):
    trail, _ = _open_default(tmp_path)
    text = trail.read_text(encoding="utf-8")
    text += (
        "\n```json\n"
        '{"kind": "round", "invocation": "inv-1", "round": 99}\n'
        "```\n"
    )
    trail.write_text(text, encoding="utf-8")
    records, _positions, _opener_lines, _marker_lines, reason, _detail = pra._parse_records(
        pra._read_lines(str(trail)),
    )
    assert reason is None
    assert len(records) == 1
    assert records[0]["kind"] == "invocation"


def test_marker_discipline_marker_without_fence_malformed(tmp_path):
    trail, _ = _open_default(tmp_path)
    text = trail.read_text(encoding="utf-8")
    text += "\n" + pra.RECORD_MARKER + "\n"
    trail.write_text(text, encoding="utf-8")
    records, _positions, _opener_lines, _marker_lines, reason, _detail = pra._parse_records(
        pra._read_lines(str(trail)),
    )
    assert records is None
    assert reason == pra.REFUSAL_TRAIL_MALFORMED


def test_marker_discipline_nested_fence_not_double_counted(tmp_path):
    trail, _ = _open_default(tmp_path)
    text = trail.read_text(encoding="utf-8")
    text += (
        "\n````text\n"
        + pra.RECORD_MARKER
        + "\n"
        + "```json\n"
        + '{"kind": "round", "invocation": "inv-1", "round": 99}\n'
        + "```\n"
        + "````\n"
    )
    trail.write_text(text, encoding="utf-8")
    records, _positions, _opener_lines, _marker_lines, reason, _detail = pra._parse_records(
        pra._read_lines(str(trail)),
    )
    assert reason is None
    assert len(records) == 1
    assert records[0]["kind"] == "invocation"


# --- help -------------------------------------------------------------------


@pytest.mark.parametrize("args", [
    ["--help"],
    ["open", "--help"],
    ["record-round", "--help"],
    ["record-verification", "--help"],
    ["check", "--help"],
])
def test_help_exits_zero_without_json(args):
    code, out, _err = _run_cli(*args)
    assert code == 0
    assert out.strip()
    assert _stdout_has_no_json(out)


def test_mid_read_nonconforming_with_unverified_finding(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    code, out, _err = _run_cli("check", "--trail", str(trail))
    assert code == pra.EXIT_NONCONFORMING
    payload = json.loads(out.strip())
    assert any(
        item["kind"] == pra.NONCONFORMITY_FINDING_UNVERIFIED
        and "f-1" in item["detail"]
        for item in payload["findings"]
    )
    assert any(
        item["kind"] == pra.NONCONFORMITY_ELEMENT_MISSING
        and item["detail"] == "invocation has no verification record"
        for item in payload["findings"]
    )
    summary = payload["invocations"][0]
    assert "converged" not in summary


def test_nonconformity_sync_check_incomplete_over_count(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    _record_verification(
        trail,
        findings=["f-1:package-fix:verified"],
        sync_checks=["c1:pass", "c2:pass", "c3:pass"],
    )
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING
    assert any(
        item["kind"] == pra.NONCONFORMITY_SYNC_CHECK_INCOMPLETE
        and "3" in item["detail"]
        and "2" in item["detail"]
        for item in payload["findings"]
    )


def test_refusal_refutation_missing_evidence_entirely(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    before = _trail_bytes(trail)
    code, out, _err = _record_verification(
        trail,
        findings=["f-1:refutation:verified"],
        sync_checks=["c1:pass", "c2:pass"],
    )
    _assert_refusal_no_append(trail, before, code, out, pra.REFUSAL_EVIDENCE_EMPTY)
    payload = json.loads(out.strip())
    assert "requires --evidence" in payload["detail"]


def test_nonconformity_element_missing_invocation_weight(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail)
    text = trail.read_text(encoding="utf-8")
    text = text.replace('"weight": "light"', '"weight": null', 1)
    trail.write_text(text, encoding="utf-8")
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING
    assert any(
        item["kind"] == pra.NONCONFORMITY_ELEMENT_MISSING
        and "weight" in item["detail"]
        for item in payload["findings"]
    )


def test_nonconformity_element_missing_measurables_children(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail)
    text = trail.read_text(encoding="utf-8")
    text = text.replace('"children": 2', '"children": null', 1)
    trail.write_text(text, encoding="utf-8")
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING
    assert any(
        item["kind"] == pra.NONCONFORMITY_ELEMENT_MISSING
        and "measurables.children" in item["detail"]
        for item in payload["findings"]
    )


def test_nonconformity_element_missing_measurables_register_entries(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail)
    text = trail.read_text(encoding="utf-8")
    text = text.replace('"registerEntries": 1', '"registerEntries": null', 1)
    trail.write_text(text, encoding="utf-8")
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING
    assert any(
        item["kind"] == pra.NONCONFORMITY_ELEMENT_MISSING
        and "measurables.registerEntries" in item["detail"]
        for item in payload["findings"]
    )


def test_nonconformity_element_missing_invocation_ceiling(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail)
    text = trail.read_text(encoding="utf-8")
    text = text.replace('"ceiling": 3', '"ceiling": null', 1)
    trail.write_text(text, encoding="utf-8")
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING
    assert any(
        item["kind"] == pra.NONCONFORMITY_ELEMENT_MISSING
        and "ceiling" in item["detail"]
        for item in payload["findings"]
    )


def test_nonconformity_element_missing_invocation_seats(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail)
    text = trail.read_text(encoding="utf-8")
    text = text.replace(
        '"seats": [\n  "seat-a"\n ]',
        '"seats": null',
        1,
    )
    trail.write_text(text, encoding="utf-8")
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING
    assert any(
        item["kind"] == pra.NONCONFORMITY_ELEMENT_MISSING
        and "seats" in item["detail"]
        for item in payload["findings"]
    )


def test_refusal_spec_contradiction_disposition_not_allowed(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:spec-contradiction"])
    before = _trail_bytes(trail)
    code, out, _err = _record_verification(
        trail,
        findings=["f-1:declined-extension:verified"],
        sync_checks=["c1:pass", "c2:pass"],
    )
    _assert_refusal_no_append(
        trail,
        before,
        code,
        out,
        pra.REFUSAL_DISPOSITION_NOT_ALLOWED_FOR_LENS,
    )


@pytest.mark.parametrize("disposition", sorted(pra.SPEC_CONTRADICTION_DISPOSITIONS))
def test_spec_contradiction_allowed_dispositions(tmp_path, disposition):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:spec-contradiction"])
    evidence = []
    if disposition == pra.DISPOSITION_REFUTATION:
        evidence = ["f-1:spec covers this"]
    code, out, _err = _record_verification(
        trail,
        findings=["f-1:%s:verified" % disposition],
        sync_checks=["c1:pass", "c2:pass"],
        evidence=evidence,
    )
    assert code == pra.EXIT_RECORDED, out


# --- completeness bites (element-missing) -----------------------------------


def test_completeness_bite_verification_pass_missing(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail)
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING
    assert any(
        item["kind"] == pra.NONCONFORMITY_ELEMENT_MISSING
        and item["detail"] == "invocation has no verification record"
        for item in payload["findings"]
    )


# --- typed-value validation -------------------------------------------------


def _trail_with_bad_value(tmp_path, replace_from, replace_to):
    trail, _ = _open_default(tmp_path)
    _record_round(trail)
    text = trail.read_text(encoding="utf-8")
    text = text.replace(replace_from, replace_to, 1)
    trail.write_text(text, encoding="utf-8")
    return trail


def _assert_record_value_invalid(trail, field_path_fragment):
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING
    assert any(
        item["kind"] == pra.NONCONFORMITY_RECORD_VALUE_INVALID
        and field_path_fragment in item["detail"]
        for item in payload["findings"]
    )


def test_record_value_invalid_invocation_id_list(tmp_path):
    trail = _trail_with_bad_value(tmp_path, '"invocation": "inv-1"', '"invocation": ["inv-1"]')
    _assert_record_value_invalid(trail, "invocation")


def test_record_value_invalid_cause_empty(tmp_path):
    trail = _trail_with_bad_value(tmp_path, '"cause": "initial read"', '"cause": ""')
    _assert_record_value_invalid(trail, "cause")


def test_record_value_invalid_weight(tmp_path):
    trail = _trail_with_bad_value(tmp_path, '"weight": "light"', '"weight": "heavy"')
    _assert_record_value_invalid(trail, "weight")


def test_record_value_invalid_ceiling_zero(tmp_path):
    trail = _trail_with_bad_value(tmp_path, '"ceiling": 3', '"ceiling": 0')
    _assert_record_value_invalid(trail, "ceiling")


def test_record_value_invalid_ceiling_bool(tmp_path):
    trail = _trail_with_bad_value(tmp_path, '"ceiling": 3', '"ceiling": true')
    _assert_record_value_invalid(trail, "ceiling")


def test_record_value_invalid_measurables_not_object(tmp_path):
    trail = _trail_with_bad_value(
        tmp_path,
        '"measurables": {\n  "children": 2,\n  "registerEntries": 1\n }',
        '"measurables": "bad"',
    )
    _assert_record_value_invalid(trail, "measurables")


def test_record_value_invalid_measurables_children_negative(tmp_path):
    trail = _trail_with_bad_value(tmp_path, '"children": 2', '"children": -1')
    _assert_record_value_invalid(trail, "measurables.children")


def test_record_value_invalid_measurables_children_bool(tmp_path):
    trail = _trail_with_bad_value(tmp_path, '"children": 2', '"children": true')
    _assert_record_value_invalid(trail, "measurables.children")


def test_record_value_invalid_measurables_register_entries_string(tmp_path):
    trail = _trail_with_bad_value(tmp_path, '"registerEntries": 1', '"registerEntries": "1"')
    _assert_record_value_invalid(trail, "measurables.registerEntries")


def test_record_value_invalid_override_not_string(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail)
    text = trail.read_text(encoding="utf-8")
    text = text.replace('"override": null', '"override": 42', 1)
    trail.write_text(text, encoding="utf-8")
    _assert_record_value_invalid(trail, "override")


def test_record_value_invalid_seats_empty_list(tmp_path):
    trail = _trail_with_bad_value(
        tmp_path,
        '"seats": [\n  "seat-a"\n ]',
        '"seats": []',
    )
    _assert_record_value_invalid(trail, "seats")


def test_record_value_invalid_round_zero(tmp_path):
    trail, _ = _open_default(tmp_path)
    _hand_append_record(trail, {
        "kind": "round",
        "invocation": "inv-1",
        "round": 0,
        "lenses": [pra.LENS_COLLISIONS],
        "parts": [{"part": "pkg", "status": "unreviewed"}],
        "controlProbe": pra.CONTROL_PROBE_ENGAGED,
        "findings": [],
        "declinedExtension": [],
        "mechanicalOnly": False,
    })
    _assert_record_value_invalid(trail, "round")


def test_record_value_invalid_lenses_scalar(tmp_path):
    trail, _ = _open_default(tmp_path)
    _hand_append_record(trail, {
        "kind": "round",
        "invocation": "inv-1",
        "round": 1,
        "lenses": pra.LENS_COLLISIONS,
        "parts": [{"part": "pkg", "status": "unreviewed"}],
        "controlProbe": pra.CONTROL_PROBE_ENGAGED,
        "findings": [],
        "declinedExtension": [],
        "mechanicalOnly": False,
    })
    _assert_record_value_invalid(trail, "lenses")


def test_record_value_invalid_parts_scalar(tmp_path):
    trail, _ = _open_default(tmp_path)
    _hand_append_record(trail, {
        "kind": "round",
        "invocation": "inv-1",
        "round": 1,
        "lenses": [pra.LENS_COLLISIONS],
        "parts": "pkg:unreviewed",
        "controlProbe": pra.CONTROL_PROBE_ENGAGED,
        "findings": [],
        "declinedExtension": [],
        "mechanicalOnly": False,
    })
    _assert_record_value_invalid(trail, "parts")


def test_record_value_invalid_part_entry_scalar(tmp_path):
    trail, _ = _open_default(tmp_path)
    _hand_append_record(trail, {
        "kind": "round",
        "invocation": "inv-1",
        "round": 1,
        "lenses": [pra.LENS_COLLISIONS],
        "parts": ["bad"],
        "controlProbe": pra.CONTROL_PROBE_ENGAGED,
        "findings": [],
        "declinedExtension": [],
        "mechanicalOnly": False,
    })
    _assert_record_value_invalid(trail, "parts[0]")


def test_record_value_invalid_control_probe(tmp_path):
    trail, _ = _open_default(tmp_path)
    _hand_append_record(trail, {
        "kind": "round",
        "invocation": "inv-1",
        "round": 1,
        "lenses": [pra.LENS_COLLISIONS],
        "parts": [{"part": "pkg", "status": "unreviewed"}],
        "controlProbe": "bogus",
        "findings": [],
        "declinedExtension": [],
        "mechanicalOnly": False,
    })
    _assert_record_value_invalid(trail, "controlProbe")


def test_record_value_invalid_mechanical_only_string_refused_not_coerced(tmp_path):
    trail, _ = _open_default(tmp_path)
    _hand_append_record(trail, {
        "kind": "round",
        "invocation": "inv-1",
        "round": 1,
        "lenses": [pra.LENS_COLLISIONS],
        "parts": [{"part": "pkg", "status": "unreviewed"}],
        "controlProbe": pra.CONTROL_PROBE_ENGAGED,
        "findings": [],
        "declinedExtension": [],
        "mechanicalOnly": "false",
    })
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING
    assert any(
        item["kind"] == pra.NONCONFORMITY_RECORD_VALUE_INVALID
        and "mechanicalOnly" in item["detail"]
        and "'false'" in item["detail"]
        for item in payload["findings"]
    )
    summary = payload["invocations"][0]
    # mechanicalOnly must not be coerced to True from string "false"
    if summary.get("roundsAsserted"):
        assert summary["roundsAsserted"][0]["mechanicalOnly"] == "false"


def test_record_value_invalid_round_findings_scalar(tmp_path):
    trail, _ = _open_default(tmp_path)
    _hand_append_record(trail, {
        "kind": "round",
        "invocation": "inv-1",
        "round": 1,
        "lenses": [pra.LENS_COLLISIONS],
        "parts": [{"part": "pkg", "status": "unreviewed"}],
        "controlProbe": pra.CONTROL_PROBE_ENGAGED,
        "findings": "bad",
        "declinedExtension": [],
        "mechanicalOnly": False,
    })
    _assert_record_value_invalid(trail, "findings")


def test_record_value_invalid_round_finding_entry_scalar(tmp_path):
    trail, _ = _open_default(tmp_path)
    _hand_append_record(trail, {
        "kind": "round",
        "invocation": "inv-1",
        "round": 1,
        "lenses": [pra.LENS_COLLISIONS],
        "parts": [{"part": "pkg", "status": "unreviewed"}],
        "controlProbe": pra.CONTROL_PROBE_ENGAGED,
        "findings": ["bad"],
        "declinedExtension": [],
        "mechanicalOnly": False,
    })
    _assert_record_value_invalid(trail, "findings[0]")


def test_record_value_invalid_declined_extension_scalar(tmp_path):
    trail, _ = _open_default(tmp_path)
    _hand_append_record(trail, {
        "kind": "round",
        "invocation": "inv-1",
        "round": 1,
        "lenses": [pra.LENS_COLLISIONS],
        "parts": [{"part": "pkg", "status": "unreviewed"}],
        "controlProbe": pra.CONTROL_PROBE_ENGAGED,
        "findings": [],
        "declinedExtension": "f-1",
        "mechanicalOnly": False,
    })
    _assert_record_value_invalid(trail, "declinedExtension")


def test_record_value_invalid_verification_findings_scalar(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    _hand_append_record(trail, {
        "kind": "verification",
        "invocation": "inv-1",
        "findings": "bad",
        "syncChecks": [{"child": "c1", "result": "pass"}],
    })
    _assert_record_value_invalid(trail, "findings")


def test_record_value_invalid_verification_finding_disposition(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    _hand_append_record(trail, {
        "kind": "verification",
        "invocation": "inv-1",
        "findings": [{"finding": "f-1", "disposition": "bogus", "outcome": "verified"}],
        "syncChecks": [{"child": "c1", "result": "pass"}],
    })
    _assert_record_value_invalid(trail, "findings[0].disposition")


def test_record_value_invalid_verification_evidence_not_string(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    _hand_append_record(trail, {
        "kind": "verification",
        "invocation": "inv-1",
        "findings": [{
            "finding": "f-1",
            "disposition": "refutation",
            "outcome": "verified",
            "evidence": 42,
        }],
        "syncChecks": [{"child": "c1", "result": "pass"}],
    })
    _assert_record_value_invalid(trail, "findings[0].evidence")


def test_record_value_invalid_sync_checks_scalar(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    _hand_append_record(trail, {
        "kind": "verification",
        "invocation": "inv-1",
        "findings": [{"finding": "f-1", "disposition": "package-fix", "outcome": "verified"}],
        "syncChecks": "bad",
    })
    _assert_record_value_invalid(trail, "syncChecks")


def test_record_value_invalid_sync_check_result(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    _hand_append_record(trail, {
        "kind": "verification",
        "invocation": "inv-1",
        "findings": [{"finding": "f-1", "disposition": "package-fix", "outcome": "verified"}],
        "syncChecks": [{"child": "c1", "result": "bogus"}],
    })
    _assert_record_value_invalid(trail, "syncChecks[0].result")


def test_record_value_invalid_absent_field_not_doubled(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail)
    text = trail.read_text(encoding="utf-8")
    text = text.replace('"weight": "light"', '"weight": null', 1)
    trail.write_text(text, encoding="utf-8")
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING
    assert any(item["kind"] == pra.NONCONFORMITY_ELEMENT_MISSING for item in payload["findings"])
    assert not any(
        item["kind"] == pra.NONCONFORMITY_RECORD_VALUE_INVALID
        and "weight" in item["detail"]
        for item in payload["findings"]
    )


def test_unknown_field_is_nonconforming(tmp_path):
    """A field no declaration mentions is reported, never silently accepted."""
    trail, _ = _open_default(tmp_path)
    _record_round(trail)
    _record_verification(
        trail,
        findings=[],
        sync_checks=["c1:pass", "c2:pass"],
    )
    text = trail.read_text(encoding="utf-8")
    text = text.replace(
        '"mechanicalOnly": false',
        '"mechanicalOnly": false,\n "futureField": "ok"',
        1,
    )
    trail.write_text(text, encoding="utf-8")
    code, out, _err = _run_cli("check", "--trail", str(trail))
    assert code == pra.EXIT_NONCONFORMING, out
    payload = json.loads(out.strip())
    assert payload["result"] == pra.RESULT_NONCONFORMING, out
    assert any(
        item["kind"] == pra.NONCONFORMITY_RECORD_VALUE_INVALID
        and item["path"] == "futureField"
        for item in payload["findings"]
    ), payload["findings"]


# --- asserted-echo and order-independence -----------------------------------


def test_rounds_asserted_echo_mechanical_only_false(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, mechanical_only=False)
    _record_verification(
        trail,
        findings=[],
        sync_checks=["c1:pass", "c2:pass"],
    )
    code, out, _err = _run_cli("check", "--trail", str(trail))
    assert code == pra.EXIT_CONFORMING
    summary = json.loads(out.strip())["invocations"][0]
    assert summary["roundsAsserted"][0]["mechanicalOnly"] is False
    assert "converged" not in summary
    assert "ceilingReached" not in summary
    assert "parkOwed" not in summary


# --- WO-F: permutation oracle, census, hostile sweep, empty-string pairing ---
#
# Cap: none. Every fixture below has at most 5 records (5! = 120). A 6-record
# fixture is 720 perms; if one is added, cap itertools.permutations at 120
# here and name that cap in this comment.


_TRAIL_POSITION_IN_DETAIL = re.compile(r"trail positions? \d+(?:, \d+)*")


def _write_trail(path, records):
    text = pra.TRAIL_HEADING + "\n"
    for record in records:
        text += pra._format_record(record)
    path.write_text(text, encoding="utf-8")


def _valid_record(kind):
    if kind == pra.RECORD_KIND_INVOCATION:
        return {
            "kind": kind,
            "invocation": "i1",
            "cause": "read",
            "weight": pra.WEIGHT_LIGHT,
            "measurables": {"children": 2, "registerEntries": 1},
            "ceiling": 2,
            "override": "none",
            "seats": ["seat-a"],
        }
    if kind == pra.RECORD_KIND_ROUND:
        return {
            "kind": kind,
            "invocation": "i1",
            "round": 1,
            "lenses": [pra.LENS_COLLISIONS],
            "parts": [{"part": "pkg", "status": pra.PART_STATUS_UNREVIEWED}],
            "controlProbe": pra.CONTROL_PROBE_ENGAGED,
            "findings": [{"finding": "f-1", "lens": pra.LENS_COLLISIONS}],
            "declinedExtension": ["f-1"],
            "mechanicalOnly": False,
        }
    if kind == pra.RECORD_KIND_VERIFICATION:
        return {
            "kind": kind,
            "invocation": "i1",
            "findings": [{
                "finding": "f-1",
                "disposition": pra.DISPOSITION_PACKAGE_FIX,
                "outcome": pra.OUTCOME_VERIFIED,
                "evidence": "note",
            }],
            "syncChecks": [{"child": "c1", "result": pra.SYNC_RESULT_PASS}],
        }
    raise AssertionError("no valid-record template for kind %r" % kind)


def _sync_two_pass():
    return [
        {"child": "c1", "result": pra.SYNC_RESULT_PASS},
        {"child": "c2", "result": pra.SYNC_RESULT_PASS},
    ]


def _round_n(round_no, findings=None, mechanical_only=False):
    rec = _valid_record(pra.RECORD_KIND_ROUND)
    rec["round"] = round_no
    rec["findings"] = [] if findings is None else findings
    rec["declinedExtension"] = []
    rec["mechanicalOnly"] = mechanical_only
    return rec


def _ver(findings=None, sync=None):
    rec = _valid_record(pra.RECORD_KIND_VERIFICATION)
    rec["findings"] = [] if findings is None else findings
    rec["syncChecks"] = _sync_two_pass() if sync is None else sync
    return rec


def _f1_finding():
    return [{"finding": "f-1", "lens": pra.LENS_COLLISIONS}]


def _f1_verified():
    return [{
        "finding": "f-1",
        "disposition": pra.DISPOSITION_PACKAGE_FIX,
        "outcome": pra.OUTCOME_VERIFIED,
    }]


def _complete_four():
    """Invocation, round 1 (finding), round 2 (mechanical), verification."""
    return [
        _valid_record(pra.RECORD_KIND_INVOCATION),
        _round_n(1, findings=_f1_finding()),
        _round_n(2, mechanical_only=True),
        _ver(findings=_f1_verified()),
    ]


def _complete_three():
    return [
        _valid_record(pra.RECORD_KIND_INVOCATION),
        _round_n(1, findings=[]),
        _ver(findings=[], sync=_sync_two_pass()),
    ]


def _path_segments(path):
    segments = []
    current = ""
    idx = 0
    while idx < len(path):
        ch = path[idx]
        if ch == ".":
            if current:
                segments.append(current)
                current = ""
            idx += 1
            continue
        if ch == "[":
            if current:
                segments.append(current)
                current = ""
            close = path.index("]", idx)
            segments.append(int(path[idx + 1:close]))
            idx = close + 1
            continue
        current += ch
        idx += 1
    if current:
        segments.append(current)
    return segments


def _set_path(record, path, value):
    segs = _path_segments(path)
    target = record
    for seg in segs[:-1]:
        target = target[seg]
    target[segs[-1]] = value


def _iter_constraints(declaration, prefix=""):
    fields = declaration.get("fields", {})
    if not isinstance(fields, dict):
        return
    for name, constraint in fields.items():
        path = "%s.%s" % (prefix, name) if prefix else name
        yield path, constraint
        if not isinstance(constraint, dict):
            continue
        if constraint.get("type") == "array" and "items" in constraint:
            items = constraint["items"]
            item_path = "%s[0]" % path
            yield item_path, items
            if isinstance(items, dict) and items.get("type") == "object":
                yield from _iter_constraints(items, item_path)
        if constraint.get("type") == "object" and "fields" in constraint:
            yield from _iter_constraints(constraint, path)


def _nonempty_fields():
    rows = []
    for kind, declaration in pra.RECORD_SCHEMAS.items():
        for path, constraint in _iter_constraints(declaration):
            if isinstance(constraint, dict) and constraint.get("nonEmpty"):
                rows.append((kind, path))
    return rows


def _wrong_type_value(type_name):
    return {
        "string": 0,
        "integer": True,
        "boolean": "not-bool",
        "object": [],
        "array": {},
    }[type_name]


def _check_exit_code(payload):
    if payload["result"] == pra.RESULT_CONFORMING:
        return pra.EXIT_CONFORMING
    if payload["result"] == pra.RESULT_NONCONFORMING:
        return pra.EXIT_NONCONFORMING
    return pra.EXIT_UNDECIDED


def _canonical_check_payload(payload):
    """Whole check payload minus physical trail positions (PRA-007)."""
    findings = []
    for item in payload["findings"]:
        detail = item.get("detail")
        if isinstance(detail, str):
            detail = _TRAIL_POSITION_IN_DETAIL.sub("trail position *", detail)
        findings.append({
            "kind": item["kind"],
            "invocation": item.get("invocation"),
            "path": item.get("path"),
            "detail": detail,
        })
    findings.sort(key=lambda row: json.dumps(row, sort_keys=True))
    return {
        "result": payload["result"],
        "ok": payload["ok"],
        "invocations": payload["invocations"],
        "findings": findings,
    }


def _ver_before_highest(records):
    round_idxs = [
        (idx, rec["round"])
        for idx, rec in enumerate(records)
        if rec.get("kind") == pra.RECORD_KIND_ROUND and isinstance(rec.get("round"), int)
    ]
    ver_idxs = [
        idx for idx, rec in enumerate(records)
        if rec.get("kind") == pra.RECORD_KIND_VERIFICATION
    ]
    if not round_idxs or not ver_idxs:
        return False
    highest_n = max(n for _idx, n in round_idxs)
    highest_idx = min(idx for idx, n in round_idxs if n == highest_n)
    return min(ver_idxs) < highest_idx


def _rounds_adjacent(records):
    idxs = [
        idx for idx, rec in enumerate(records)
        if rec.get("kind") == pra.RECORD_KIND_ROUND
    ]
    if len(idxs) < 2:
        return False
    return abs(idxs[0] - idxs[1]) == 1


def _oracle_fixtures():
    clean = _complete_four()
    ver_before = [
        clean[0],
        clean[1],
        clean[3],
        clean[2],
    ]
    inv_a = _valid_record(pra.RECORD_KIND_INVOCATION)
    inv_b = _valid_record(pra.RECORD_KIND_INVOCATION)
    inv_b["ceiling"] = 3
    inv_b["weight"] = pra.WEIGHT_FULL
    inv_b["seats"] = ["seat-b"]
    conflicting = [
        inv_a,
        inv_b,
        _round_n(1, findings=_f1_finding()),
        _round_n(2, mechanical_only=True),
        _ver(findings=_f1_verified()),
    ]
    r1 = _round_n(1, findings=[])
    r1_dup = _round_n(1, findings=[])
    duplicate_round = [
        _valid_record(pra.RECORD_KIND_INVOCATION),
        r1,
        r1_dup,
        _ver(findings=[]),
    ]
    no_ceiling = _valid_record(pra.RECORD_KIND_INVOCATION)
    no_ceiling["ceiling"] = None
    return [
        {
            "id": "verification_before_highest_round",
            "records": ver_before,
            "expected_result": pra.RESULT_CONFORMING,
            "expected_kinds": set(),
            "flip": "verification_before_highest",
        },
        {
            "id": "conflicting_invocations",
            "records": conflicting,
            "expected_result": pra.RESULT_NONCONFORMING,
            "expected_kinds": {pra.NONCONFORMITY_RECORD_DUPLICATE},
            "expected_summaries": 0,
            "flip": "conflicting_payloads",
        },
        {
            "id": "duplicate_round",
            "records": duplicate_round,
            "expected_result": pra.RESULT_NONCONFORMING,
            "expected_kinds": {pra.NONCONFORMITY_RECORD_DUPLICATE},
            "flip": "duplicate_round",
        },
        {
            "id": "clean",
            "records": clean,
            "expected_result": pra.RESULT_CONFORMING,
            "expected_kinds": set(),
            "flip": "clean",
        },
        {
            "id": "round_exceeds_ceiling",
            "records": [
                _valid_record(pra.RECORD_KIND_INVOCATION),
                _round_n(7, findings=_f1_finding()),
                _ver(findings=_f1_verified()),
            ],
            "expected_result": pra.RESULT_NONCONFORMING,
            "expected_kinds": {pra.NONCONFORMITY_ROUND_EXCEEDS_CEILING},
        },
        {
            "id": "unknown_finding",
            "records": [
                _valid_record(pra.RECORD_KIND_INVOCATION),
                _round_n(1, findings=_f1_finding()),
                _ver(findings=[{
                    "finding": "ghost",
                    "disposition": pra.DISPOSITION_PACKAGE_FIX,
                    "outcome": pra.OUTCOME_VERIFIED,
                }]),
            ],
            "expected_result": pra.RESULT_NONCONFORMING,
            "expected_kinds": {
                pra.NONCONFORMITY_FINDING_UNKNOWN,
                pra.NONCONFORMITY_FINDING_UNVERIFIED,
            },
        },
        {
            "id": "duplicate_sync_check",
            "records": [
                dict(_valid_record(pra.RECORD_KIND_INVOCATION), **{"measurables": {
                    "children": 1, "registerEntries": 1,
                }}),
                _round_n(1, findings=_f1_finding()),
                _ver(
                    findings=_f1_verified(),
                    sync=[
                        {"child": "c1", "result": pra.SYNC_RESULT_FAIL},
                        {"child": "c1", "result": pra.SYNC_RESULT_FAIL},
                    ],
                ),
            ],
            "expected_result": pra.RESULT_NONCONFORMING,
            "expected_kinds": {
                pra.NONCONFORMITY_RECORD_DUPLICATE,
                pra.NONCONFORMITY_SYNC_CHECK_FAILED,
            },
        },
        {
            "id": "verification_finding_id_only",
            "records": [
                _valid_record(pra.RECORD_KIND_INVOCATION),
                _round_n(1, findings=_f1_finding()),
                _ver(findings=[{"finding": "f-1"}]),
            ],
            "expected_result": pra.RESULT_NONCONFORMING,
            "expected_kinds": {pra.NONCONFORMITY_ELEMENT_MISSING},
        },
        {
            "id": "invocation_without_ceiling",
            "records": [
                no_ceiling,
                _round_n(1, findings=_f1_finding()),
                _ver(findings=_f1_verified()),
            ],
            "expected_result": pra.RESULT_NONCONFORMING,
            "expected_kinds": {pra.NONCONFORMITY_ELEMENT_MISSING},
        },
    ]


@pytest.mark.parametrize(
    "fixture",
    _oracle_fixtures(),
    ids=lambda f: f["id"],
)
def test_check_verdict_is_order_independent(tmp_path, fixture):
    records = fixture["records"]
    assert len(records) <= 5, (
        "fixture %s has %d records; cap permutations at 120 and name the cap"
        % (fixture["id"], len(records))
    )
    orders = list(itertools.permutations(records))
    if fixture.get("flip") == "verification_before_highest":
        assert _ver_before_highest(records)
        assert any(_ver_before_highest(order) for order in orders)
        assert any(not _ver_before_highest(order) for order in orders)
    elif fixture.get("flip") == "conflicting_payloads":
        invs = [rec for rec in records if rec["kind"] == pra.RECORD_KIND_INVOCATION]
        assert len(invs) == 2
        assert invs[0]["invocation"] == invs[1]["invocation"]
        assert invs[0]["ceiling"] != invs[1]["ceiling"]
        assert invs[0]["weight"] != invs[1]["weight"]
        assert invs[0]["seats"] != invs[1]["seats"]
    elif fixture.get("flip") == "duplicate_round":
        rounds = [rec for rec in records if rec["kind"] == pra.RECORD_KIND_ROUND]
        assert len(rounds) == 2
        assert rounds[0]["round"] == rounds[1]["round"]
        assert any(_rounds_adjacent(order) for order in orders)
        assert any(not _rounds_adjacent(order) for order in orders)

    trail = tmp_path / "trail.md"
    distinct = set()
    listed_payload = None
    for idx, order in enumerate(orders):
        _write_trail(trail, order)
        payload = pra.verb_check(str(trail))
        if idx == 0:
            listed_payload = payload
        canonical = _canonical_check_payload(payload)
        distinct.add(json.dumps(canonical, sort_keys=True))
        if fixture["id"] == "clean":
            assert payload["result"] == pra.RESULT_CONFORMING, fixture["id"]
            assert payload["findings"] == [], fixture["id"]

    assert listed_payload is not None
    assert listed_payload["result"] == fixture["expected_result"], fixture["id"]
    kinds = {item["kind"] for item in listed_payload["findings"]}
    assert kinds == fixture["expected_kinds"], (fixture["id"], kinds)
    if "expected_summaries" in fixture:
        assert len(listed_payload["invocations"]) == fixture["expected_summaries"], (
            fixture["id"]
        )
    if fixture["id"] == "invocation_without_ceiling":
        summary = listed_payload["invocations"][0]
        assert summary["ceiling"] is None
        assert summary["seats"] == ["seat-a"]
    assert len(distinct) == 1, (
        "fixture %s produced %d distinct canonical verdicts"
        % (fixture["id"], len(distinct))
    )


def test_finding_positions_point_at_the_right_records(tmp_path):
    records = [
        dict(_valid_record(pra.RECORD_KIND_INVOCATION), cause=""),
        _round_n(7, findings=_f1_finding()),
        _ver(findings=[{
            "finding": "ghost",
            "disposition": pra.DISPOSITION_PACKAGE_FIX,
            "outcome": pra.OUTCOME_VERIFIED,
        }]),
    ]
    trail = tmp_path / "trail.md"
    _write_trail(trail, records)
    payload = pra.verb_check(str(trail))
    got = {
        (item["kind"], item["path"], item["position"])
        for item in payload["findings"]
    }
    expected = {
        (pra.NONCONFORMITY_RECORD_VALUE_INVALID, "cause", 1),
        (pra.NONCONFORMITY_ROUND_EXCEEDS_CEILING, "round", 2),
        (pra.NONCONFORMITY_FINDING_UNKNOWN, "findings[0].finding", 3),
        (pra.NONCONFORMITY_FINDING_UNVERIFIED, "finding", 2),
    }
    assert got == expected


# --- vocabulary drift guards ------------------------------------------------


def _string_constants_by_prefix(prefix, aggregate_name):
    derived = set()
    for name in dir(pra):
        if not name.startswith(prefix) or name == aggregate_name:
            continue
        val = getattr(pra, name)
        if isinstance(val, str):
            derived.add(val)
    return derived


def test_refusal_reasons_complete():
    assert pra.REFUSAL_REASONS == _string_constants_by_prefix(
        "REFUSAL_", "REFUSAL_REASONS",
    )


def test_nonconformity_kinds_complete():
    assert pra.NONCONFORMITY_KINDS == _string_constants_by_prefix(
        "NONCONFORMITY_", "NONCONFORMITY_KINDS",
    )


def test_undecided_reasons_complete():
    assert pra.UNDECIDED_REASONS == _string_constants_by_prefix(
        "UNDECIDED_", "UNDECIDED_REASONS",
    )


# --- declaration layer (WO-A) -----------------------------------------------


def test_declarations_are_well_formed():
    assert pra._declaration_violations() == []


def test_declaration_self_check_catches_a_bad_declaration():
    problems = pra._validate_constraint(
        "test",
        {"bogusKey": True, "type": "string"},
    )
    assert any("unknown constraint key" in p for p in problems)

    problems = pra._validate_constraint(
        "test",
        {"type": "bogus"},
    )
    assert any("unknown type" in p for p in problems)

    problems = pra._validate_declaration(
        "test",
        {
            "required": ("missing_field",),
            "fields": {"present": {"type": "string"}},
        },
    )
    assert any("required names undeclared field" in p for p in problems)

    problems = pra._validate_constraint(
        "test",
        {"type": "string", "refusal": "not-a-real-reason"},
    )
    assert any("not in REFUSAL_REASONS" in p for p in problems)


@pytest.mark.parametrize(
    "record",
    [
        {"kind": "invocation", "invocation": "inv-1", "weight": []},
        {"kind": "invocation", "invocation": "inv-1", "weight": {}},
        {
            "kind": "round",
            "invocation": "inv-1",
            "round": 1,
            "controlProbe": [],
        },
        {
            "kind": "verification",
            "invocation": "inv-1",
            "findings": [{
                "finding": "f-1",
                "disposition": {},
                "outcome": "verified",
            }],
        },
        {"kind": [], "invocation": "inv-1"},
        {"kind": 3, "invocation": "inv-1"},
        {"kind": None, "invocation": "inv-1"},
        3,
        "x",
        [],
    ],
)
def test_walker_never_raises_on_hostile_values(record):
    if isinstance(record, dict):
        violations = pra._walk_record_for_kind(record)
    else:
        violations = pra._walk_envelope(record)
    assert isinstance(violations, list)
    assert violations


def test_bool_is_not_an_integer_and_not_a_string():
    ceiling_record = {
        "kind": pra.RECORD_KIND_INVOCATION,
        "invocation": "inv-1",
        "ceiling": True,
        "weight": pra.WEIGHT_LIGHT,
        "seats": ["seat-a"],
        "measurables": {"children": 1, "registerEntries": 1},
        "cause": "x",
    }
    violations = pra._walk_record_for_kind(ceiling_record)
    assert any(
        v["path"] == "ceiling"
        and v["code"] == pra.VIOLATION_TYPE_INVALID
        for v in violations
    )

    cause_record = dict(ceiling_record, ceiling=1, cause=True)
    violations = pra._walk_record_for_kind(cause_record)
    assert any(
        v["path"] == "cause"
        and v["code"] == pra.VIOLATION_TYPE_INVALID
        for v in violations
    )


def test_check_reports_hostile_kind_and_value_as_nonconforming(tmp_path):
    trail, _ = _open_default(tmp_path)
    text = trail.read_text(encoding="utf-8")
    text = text.replace('"weight": "light"', '"weight": []', 1)
    trail.write_text(text, encoding="utf-8")
    _hand_append_record(trail, {"kind": [], "invocation": "inv-1"})
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING
    assert payload["result"] == pra.RESULT_NONCONFORMING
    assert payload["schema"] == pra.SCHEMA
    assert any(
        item["kind"] == pra.NONCONFORMITY_RECORD_VALUE_INVALID
        and item["position"] == 2
        and item["path"] == "kind"
        for item in payload["findings"]
    )


@pytest.mark.parametrize(
    "expected_reason,cli_args",
    [
        (
            pra.REFUSAL_SEATS_MISSING,
            [
                "open",
                "--trail", "TRAIL",
                "--invocation", "inv-1",
                "--cause", "x",
                "--weight", pra.WEIGHT_LIGHT,
                "--children", "1",
                "--register-entries", "1",
                "--ceiling", "1",
            ],
        ),
        (
            pra.REFUSAL_WEIGHT_UNRECOGNIZED,
            [
                "open",
                "--trail", "TRAIL",
                "--invocation", "inv-1",
                "--cause", "x",
                "--weight", "heavy",
                "--children", "1",
                "--register-entries", "1",
                "--ceiling", "1",
                "--seat", "seat-a",
            ],
        ),
        (
            pra.REFUSAL_CEILING_INVALID,
            [
                "open",
                "--trail", "TRAIL",
                "--invocation", "inv-1",
                "--cause", "x",
                "--weight", pra.WEIGHT_LIGHT,
                "--children", "1",
                "--register-entries", "1",
                "--ceiling", "0",
                "--seat", "seat-a",
            ],
        ),
        (
            pra.REFUSAL_MEASURABLE_INVALID,
            [
                "open",
                "--trail", "TRAIL",
                "--invocation", "inv-1",
                "--cause", "x",
                "--weight", pra.WEIGHT_LIGHT,
                "--children", "-1",
                "--register-entries", "1",
                "--ceiling", "1",
                "--seat", "seat-a",
            ],
        ),
        (
            pra.REFUSAL_ROUND_INVALID,
            [
                "record-round",
                "--trail", "TRAIL",
                "--invocation", "inv-1",
                "--round", "0",
                "--lens", pra.LENS_COLLISIONS,
                "--part", "pkg:unreviewed",
                "--control-probe", pra.CONTROL_PROBE_ENGAGED,
            ],
        ),
        (
            pra.REFUSAL_LENS_UNRECOGNIZED,
            [
                "record-round",
                "--trail", "TRAIL",
                "--invocation", "inv-1",
                "--round", "1",
                "--lens", "bogus-lens",
                "--part", "pkg:unreviewed",
                "--control-probe", pra.CONTROL_PROBE_ENGAGED,
            ],
        ),
        (
            pra.REFUSAL_PART_STATUS_UNRECOGNIZED,
            [
                "record-round",
                "--trail", "TRAIL",
                "--invocation", "inv-1",
                "--round", "1",
                "--lens", pra.LENS_COLLISIONS,
                "--part", "pkg:wip",
                "--control-probe", pra.CONTROL_PROBE_ENGAGED,
            ],
        ),
        (
            pra.REFUSAL_CONTROL_PROBE_UNRECOGNIZED,
            [
                "record-round",
                "--trail", "TRAIL",
                "--invocation", "inv-1",
                "--round", "1",
                "--lens", pra.LENS_COLLISIONS,
                "--part", "pkg:unreviewed",
                "--control-probe", "maybe",
            ],
        ),
        (
            pra.REFUSAL_DISPOSITION_UNRECOGNIZED,
            [
                "record-verification",
                "--trail", "TRAIL",
                "--invocation", "inv-1",
                "--finding", "f-1:bogus:verified",
            ],
        ),
        (
            pra.REFUSAL_OUTCOME_UNRECOGNIZED,
            [
                "record-verification",
                "--trail", "TRAIL",
                "--invocation", "inv-1",
                "--finding", "f-1:package-fix:bogus",
            ],
        ),
        (
            pra.REFUSAL_SYNC_RESULT_UNRECOGNIZED,
            [
                "record-verification",
                "--trail", "TRAIL",
                "--invocation", "inv-1",
                "--finding", "f-1:package-fix:verified",
                "--sync-check", "child-a:bogus",
            ],
        ),
    ],
)
def test_writer_refusals_come_from_the_declaration(
    tmp_path,
    expected_reason,
    cli_args,
):
    trail = tmp_path / "trail.md"
    args = [arg if arg != "TRAIL" else str(trail) for arg in cli_args]
    if cli_args[0] == "record-round":
        _open_default(tmp_path, trail=trail)
    if cli_args[0] == "record-verification":
        trail, _ = _open_default(tmp_path, trail=trail)
        _record_round(trail, findings=["f-1:collisions"])
    code, out, _err = _run_cli(*args)
    assert code == pra.EXIT_REFUSED
    payload = json.loads(out.strip())
    assert payload["reason"] == expected_reason


# --- read boundary and summary echo (WO-B) ----------------------------------


def test_verification_finding_missing_outcome_is_nonconforming(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    _hand_append_record(trail, {
        "kind": "verification",
        "invocation": "inv-1",
        "findings": [{"finding": "f-1", "disposition": "package-fix"}],
        "syncChecks": [{"child": "c1", "result": "pass"}, {"child": "c2", "result": "pass"}],
    })
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING
    assert any(
        item["kind"] == pra.NONCONFORMITY_ELEMENT_MISSING
        and item["path"] == "findings[0].outcome"
        for item in payload["findings"]
    )


def _trail_with_single_record(tmp_path, record):
    trail = tmp_path / "trail.md"
    trail.write_text(pra.TRAIL_HEADING + "\n", encoding="utf-8")
    _hand_append_record(trail, record)
    return trail


@pytest.mark.parametrize(
    "case",
    [
        {
            "label": "file missing",
            "trail": None,
            "setup": lambda _tmp: None,
            "expected_result": pra.RESULT_UNDECIDED,
            "expected_exit": pra.EXIT_UNDECIDED,
        },
        {
            "label": "not UTF-8",
            "trail": "trail",
            "setup": lambda tmp: (
                tmp / "trail.md"
            ).write_bytes(b"\xff\xfe"),
            "expected_result": pra.RESULT_UNDECIDED,
            "expected_exit": pra.EXIT_UNDECIDED,
        },
        {
            "label": "no records",
            "trail": "trail",
            "setup": lambda tmp: (
                tmp / "trail.md"
            ).write_text(pra.TRAIL_HEADING + "\n", encoding="utf-8"),
            "expected_result": pra.RESULT_UNDECIDED,
            "expected_exit": pra.EXIT_UNDECIDED,
        },
        {
            "label": "unterminated fence",
            "trail": "trail",
            "setup": lambda tmp: (
                tmp / "trail.md"
            ).write_text(
                pra.TRAIL_HEADING + "\n\n```json\n{}\n",
                encoding="utf-8",
            ),
            "expected_result": pra.RESULT_UNDECIDED,
            "expected_exit": pra.EXIT_UNDECIDED,
        },
        {
            "label": "JSON will not load",
            "trail": "trail",
            "setup": lambda tmp: (
                tmp / "trail.md"
            ).write_text(
                pra.TRAIL_HEADING + "\n\n"
                + pra.RECORD_MARKER + "\n"
                + "```json\n"
                + "{bad json}\n"
                + "```\n",
                encoding="utf-8",
            ),
            "expected_result": pra.RESULT_UNDECIDED,
            "expected_exit": pra.EXIT_UNDECIDED,
        },
        {
            "label": "parsed but not object",
            "trail": "trail",
            "setup": lambda tmp: _trail_with_single_record(
                tmp,
                3,
            ),
            "expected_result": pra.RESULT_NONCONFORMING,
            "expected_exit": pra.EXIT_NONCONFORMING,
        },
        {
            "label": "unrecognized kind",
            "trail": "trail",
            "setup": lambda tmp: _trail_with_single_record(
                tmp,
                {"kind": "invokation", "invocation": "inv-1"},
            ),
            "expected_result": pra.RESULT_NONCONFORMING,
            "expected_exit": pra.EXIT_NONCONFORMING,
        },
        {
            "label": "non-string kind",
            "trail": "trail",
            "setup": lambda tmp: _trail_with_single_record(
                tmp,
                {"kind": [], "invocation": "inv-1"},
            ),
            "expected_result": pra.RESULT_NONCONFORMING,
            "expected_exit": pra.EXIT_NONCONFORMING,
        },
        {
            "label": "missing required field",
            "trail": "trail",
            "setup": lambda tmp: _trail_with_single_record(
                tmp,
                {
                    "kind": "verification",
                    "invocation": "inv-1",
                    "findings": [{"finding": "f-1"}],
                    "syncChecks": [],
                },
            ),
            "expected_result": pra.RESULT_NONCONFORMING,
            "expected_exit": pra.EXIT_NONCONFORMING,
        },
        {
            "label": "bad value",
            "trail": "trail",
            "setup": lambda tmp: _trail_with_single_record(
                tmp,
                {
                    "kind": "invocation",
                    "invocation": "inv-1",
                    "weight": "heavy",
                    "cause": "x",
                    "measurables": {"children": 1, "registerEntries": 1},
                    "ceiling": 1,
                    "seats": ["seat-a"],
                },
            ),
            "expected_result": pra.RESULT_NONCONFORMING,
            "expected_exit": pra.EXIT_NONCONFORMING,
        },
    ],
    ids=lambda c: c["label"],
)
def test_read_boundary_matrix(tmp_path, case):
    trail_path = tmp_path / "trail.md"
    if case["trail"] is None:
        missing = tmp_path / "missing.md"
        code, out, _err = _run_cli("check", "--trail", str(missing))
    else:
        case["setup"](tmp_path)
        code, out, _err = _run_cli("check", "--trail", str(trail_path))
    payload = json.loads(out.strip())
    assert code == case["expected_exit"]
    assert payload["result"] == case["expected_result"]


def _delete_key_from_kind(trail, kind, key):
    """Remove `key` from the first marked record of `kind` (absent, not null)."""
    text = trail.read_text(encoding="utf-8")
    marker = pra.RECORD_MARKER + "\n```json\n"
    start = 0
    while True:
        idx = text.find(marker, start)
        if idx < 0:
            raise AssertionError("no %r record carrying %r" % (kind, key))
        json_start = idx + len(marker)
        json_end = text.find("\n```", json_start)
        obj = json.loads(text[json_start:json_end])
        if obj.get("kind") == kind and key in obj:
            del obj[key]
            dumped = json.dumps(obj, sort_keys=True, indent=1)
            trail.write_text(text[:json_start] + dumped + text[json_end:], encoding="utf-8")
            return
        start = json_end


@pytest.mark.parametrize(
    "field_name,summary_key,round_field",
    [
        ("ceiling", "ceiling", False),
        ("weight", "weight", False),
        ("seats", "seats", False),
        ("round", "round", True),
        ("mechanicalOnly", "mechanicalOnly", True),
        ("controlProbe", "controlProbe", True),
    ],
)
def test_summary_never_manufactures_a_value(
    tmp_path,
    field_name,
    summary_key,
    round_field,
):
    trail, _ = _open_default(tmp_path)
    if round_field:
        _record_round(trail)
        _delete_key_from_kind(trail, pra.RECORD_KIND_ROUND, field_name)
        code, out, _err = _run_cli("check", "--trail", str(trail))
        payload = json.loads(out.strip())
        summary = payload["invocations"][0]
        assert summary["roundsAsserted"][0][summary_key] is None
    else:
        _delete_key_from_kind(trail, pra.RECORD_KIND_INVOCATION, field_name)
        _record_round(trail)
        code, out, _err = _run_cli("check", "--trail", str(trail))
        payload = json.loads(out.strip())
        summary = payload["invocations"][0]
        assert summary[summary_key] is None


# --- WO-G: duplicate-rule census, hostile sweep, empty-string pairing --------


def _duplicate_family_tokens():
    """The writer duplicate-refusal family, derived from the module at run time.

    The family is filtered out of REFUSAL_REASONS by its `-duplicate` suffix
    rather than listed by hand. A sixth duplicate refusal joins the family the
    day it lands, and the census below then demands a DUPLICATE_RULES entry for
    it without anyone remembering to edit this test.
    """
    return {
        reason for reason in pra.REFUSAL_REASONS
        if reason.endswith("-duplicate")
    }


_DUPLICATE_SCOPES = frozenset({
    pra.DUPLICATE_SCOPE_TRAIL,
    pra.DUPLICATE_SCOPE_INVOCATION,
    pra.DUPLICATE_SCOPE_RECORD,
})


def test_duplicate_rules_cover_every_writer_duplicate_refusal():
    family = _duplicate_family_tokens()
    # Fail-closed: a derivation that collapsed to the empty set would make both
    # directions below vacuously true.
    assert len(family) >= 5, sorted(family)

    declared = {rule["token"] for rule in pra.DUPLICATE_RULES}
    assert family - declared == set(), sorted(family - declared)
    assert declared - family == set(), sorted(declared - family)

    for rule in pra.DUPLICATE_RULES:
        assert rule["kind"] in pra.RECORD_KINDS, rule
        assert rule["kind"] in pra.RECORD_SCHEMAS, rule
        assert rule["scope"] in _DUPLICATE_SCOPES, rule
        assert isinstance(rule["identity"], str) and rule["identity"], rule
        collection = rule.get("collection")
        if collection is None:
            continue
        fields = pra.RECORD_SCHEMAS[rule["kind"]]["fields"]
        assert collection in fields, rule
        assert fields[collection]["type"] == "array", rule


def _sweep_base_records():
    """A conforming three-record trail; every sweep case mutates one record.

    The verification disposition is declined-extension because the round
    template names f-1 in declinedExtension, which keeps declinedExtension[0]
    populated so a generated case can reach that path.
    """
    return [
        _valid_record(pra.RECORD_KIND_INVOCATION),
        _valid_record(pra.RECORD_KIND_ROUND),
        _ver(findings=[{
            "finding": "f-1",
            "disposition": pra.DISPOSITION_DECLINED_EXTENSION,
            "outcome": pra.OUTCOME_VERIFIED,
        }]),
    ]


def _sweep_mutation(kind, path, value):
    records = _sweep_base_records()
    for idx, record in enumerate(records):
        if record["kind"] == kind:
            mutated = copy.deepcopy(record)
            _set_path(mutated, path, value)
            records[idx] = mutated
            return records
    raise AssertionError("no %r record in the sweep base" % kind)


def _duplicate_fixture(token):
    """A trail that trips one duplicate class, or None if no fixture exists."""
    records = _sweep_base_records()
    if token == pra.REFUSAL_INVOCATION_DUPLICATE:
        return records + [copy.deepcopy(records[0])]
    if token == pra.REFUSAL_ROUND_DUPLICATE:
        return records + [copy.deepcopy(records[1])]
    if token == pra.REFUSAL_FINDING_DUPLICATE:
        second_round = copy.deepcopy(records[1])
        second_round["round"] = 2
        return records + [second_round]
    if token == pra.REFUSAL_VERIFICATION_DUPLICATE:
        return records + [copy.deepcopy(records[2])]
    if token == pra.REFUSAL_SYNC_CHECK_DUPLICATE:
        records[2] = copy.deepcopy(records[2])
        records[2]["syncChecks"] = [
            {"child": "c1", "result": pra.SYNC_RESULT_PASS},
            {"child": "c1", "result": pra.SYNC_RESULT_PASS},
        ]
        return records
    return None


def _sweep_id(*parts):
    text = "-".join(str(part) for part in parts)
    return text.replace("[", "_").replace("]", "").replace(".", "_")


def _sweep_case(
    case_id,
    records,
    family,
    kind=None,
    expect=None,
    path=None,
    duplicate=False,
    token=None,
):
    return {
        "id": case_id,
        "records": records,
        "family": family,
        "kind": kind,
        "expect": expect,
        "path": path,
        "duplicate": duplicate,
        "token": token,
    }


def _hostile_cases():
    """Hostile check fixtures, generated from RECORD_SCHEMAS and DUPLICATE_RULES.

    Generated rather than hand-listed: a field or duplicate rule added later is
    swept the day it lands, which is the omission class this whole file exists
    to remove.
    """
    cases = []

    unknown_kind = _sweep_base_records()
    unknown_kind[0] = dict(unknown_kind[0], kind="invokation")
    cases.append(_sweep_case(
        "unknown-record-kind", unknown_kind, "kind",
        expect=pra.RESULT_NONCONFORMING, path="kind",
    ))

    non_string_kind = _sweep_base_records()
    non_string_kind[0] = dict(non_string_kind[0], kind=[])
    cases.append(_sweep_case(
        "non-string-record-kind", non_string_kind, "kind",
        expect=pra.RESULT_NONCONFORMING, path="kind",
    ))

    cases.append(_sweep_case(
        "unknown-field-top-level",
        _sweep_mutation(pra.RECORD_KIND_INVOCATION, "bogusField", "x"),
        "unknown-field",
        expect=pra.RESULT_NONCONFORMING,
        path="bogusField",
    ))
    cases.append(_sweep_case(
        "unknown-field-nested",
        _sweep_mutation(pra.RECORD_KIND_ROUND, "parts[0].bogusField", "x"),
        "unknown-field",
        expect=pra.RESULT_NONCONFORMING,
        path="parts[0].bogusField",
    ))

    for kind, declaration in pra.RECORD_SCHEMAS.items():
        for path, constraint in _iter_constraints(declaration):
            cases.append(_sweep_case(
                _sweep_id("wrong-type", kind, path),
                _sweep_mutation(kind, path, _wrong_type_value(constraint["type"])),
                "wrong-type",
                kind=kind,
                expect=pra.RESULT_NONCONFORMING,
                path=path,
            ))

    for kind, path in _nonempty_fields():
        cases.append(_sweep_case(
            _sweep_id("empty-string", kind, path),
            _sweep_mutation(kind, path, ""),
            "empty-string",
            kind=kind,
            expect=pra.RESULT_NONCONFORMING,
            path=path,
        ))

    for rule in pra.DUPLICATE_RULES:
        fixture = _duplicate_fixture(rule["token"])
        assert fixture is not None, (
            "no duplicate fixture for rule token %r; every DUPLICATE_RULES "
            "entry owes one" % rule["token"]
        )
        cases.append(_sweep_case(
            _sweep_id("duplicate", rule["token"]), fixture, "duplicate",
            kind=rule["kind"],
            expect=pra.RESULT_NONCONFORMING,
            duplicate=True,
            token=rule["token"],
        ))

    permuted_token = pra.REFUSAL_SYNC_CHECK_DUPLICATE
    # Derived, not assumed: the permuted fixture only claims a duplicate finding
    # while a rule still declares that class.
    permuted_duplicate = any(
        rule["token"] == permuted_token for rule in pra.DUPLICATE_RULES
    )
    for idx, order in enumerate(itertools.permutations(
        _duplicate_fixture(permuted_token),
    )):
        cases.append(_sweep_case(
            "permuted-sync-check-duplicate-%d" % idx, list(order), "permuted",
            expect=pra.RESULT_NONCONFORMING,
            duplicate=permuted_duplicate,
        ))

    assert cases, "the hostile sweep generated no cases"
    return cases


def _assert_sweep_census(cases):
    """Fail-closed floor: a generated sweep that yields nothing is worthless."""
    wrong_type_per_kind = {}
    for case in cases:
        if case["family"] != "wrong-type":
            continue
        wrong_type_per_kind[case["kind"]] = wrong_type_per_kind.get(
            case["kind"], 0,
        ) + 1
    for kind in pra.RECORD_SCHEMAS:
        assert wrong_type_per_kind.get(kind, 0) >= 1, (kind, wrong_type_per_kind)

    nonempty = _nonempty_fields()
    assert nonempty, "RECORD_SCHEMAS declares no nonEmpty constraint"
    empty_cases = [case for case in cases if case["family"] == "empty-string"]
    assert len(empty_cases) == len(nonempty), (len(empty_cases), len(nonempty))

    duplicate_tokens = {
        case["token"] for case in cases if case["family"] == "duplicate"
    }
    assert duplicate_tokens == {rule["token"] for rule in pra.DUPLICATE_RULES}


_HOSTILE_CASES = _hostile_cases()


@pytest.mark.parametrize("case", _HOSTILE_CASES, ids=lambda case: case["id"])
def test_hostile_input_sweep(tmp_path, case):
    _assert_sweep_census(_HOSTILE_CASES)

    trail = tmp_path / "trail.md"
    _write_trail(trail, case["records"])
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())

    assert code in (pra.EXIT_CONFORMING, pra.EXIT_NONCONFORMING), out
    assert code != pra.EXIT_UNDECIDED, out
    assert payload["result"] in (
        pra.RESULT_CONFORMING, pra.RESULT_NONCONFORMING,
    ), out
    assert payload["result"] != pra.RESULT_UNDECIDED, out
    assert code == _check_exit_code(payload), out

    for item in payload["findings"]:
        position = item["position"]
        assert isinstance(position, int) and not isinstance(position, bool), item
        assert isinstance(item["path"], str) and item["path"], item

    if case["expect"] is not None:
        assert payload["result"] == case["expect"], payload["findings"]
    if case["path"] is not None:
        assert any(
            item["kind"] == pra.NONCONFORMITY_RECORD_VALUE_INVALID
            and item["path"] == case["path"]
            for item in payload["findings"]
        ), payload["findings"]
    if case["duplicate"]:
        assert any(
            item["kind"] == pra.NONCONFORMITY_RECORD_DUPLICATE
            for item in payload["findings"]
        ), payload["findings"]


def _open_with_empty(dirpath, invocation="inv-1", cause="x", seat="seat-a"):
    return _run_cli(
        "open",
        "--trail", str(dirpath / "trail.md"),
        "--invocation", invocation,
        "--cause", cause,
        "--weight", pra.WEIGHT_LIGHT,
        "--children", "1",
        "--register-entries", "1",
        "--ceiling", "2",
        "--seat", seat,
    )


def _round_after_open(dirpath, **kwargs):
    trail, _ = _open_default(dirpath)
    return _record_round(trail, **kwargs)


def _verification_after_open(dirpath, **kwargs):
    trail, _ = _open_default(dirpath)
    _record_round(trail, findings=["f-1:collisions"])
    return _record_verification(trail, **kwargs)


# nonEmpty paths a writer CLI can carry an empty value into, all the way down to
# the declaration walk.
_EMPTY_DRIVEN_BY_WRITER = {
    (pra.RECORD_KIND_INVOCATION, "seats[0]"):
        lambda d: _open_with_empty(d, seat=""),
    (pra.RECORD_KIND_INVOCATION, "cause"):
        lambda d: _open_with_empty(d, cause=""),
    (pra.RECORD_KIND_INVOCATION, "invocation"):
        lambda d: _open_with_empty(d, invocation=""),
}

# nonEmpty paths no writer CLI can carry an empty value into: the verb refuses
# earlier, on the structural shape of the flag, so the declaration walk is never
# reached. Each row names the reason the CLI actually gives, which keeps the
# un-driveable set explicit and small instead of a silent skip -- and a writer
# that later does reach the declaration reddens this test until its path moves
# up to the driven map.
_EMPTY_NOT_DRIVEN_BY_WRITER = {
    (pra.RECORD_KIND_ROUND, "invocation"): (
        lambda d: _round_after_open(d, invocation=""),
        pra.REFUSAL_INVOCATION_UNKNOWN,
    ),
    (pra.RECORD_KIND_ROUND, "parts[0].part"): (
        lambda d: _round_after_open(d, parts=[":unreviewed"]),
        pra.REFUSAL_PART_MALFORMED,
    ),
    (pra.RECORD_KIND_ROUND, "findings[0].finding"): (
        lambda d: _round_after_open(d, findings=[":collisions"]),
        pra.REFUSAL_FINDING_MALFORMED,
    ),
    (pra.RECORD_KIND_VERIFICATION, "invocation"): (
        lambda d: _verification_after_open(
            d,
            invocation="",
            findings=["f-1:package-fix:verified"],
        ),
        pra.REFUSAL_INVOCATION_UNKNOWN,
    ),
    (pra.RECORD_KIND_VERIFICATION, "findings[0].finding"): (
        lambda d: _verification_after_open(
            d, findings=[":package-fix:verified"],
        ),
        pra.REFUSAL_FINDING_MALFORMED,
    ),
    (pra.RECORD_KIND_VERIFICATION, "syncChecks[0].child"): (
        lambda d: _verification_after_open(d, sync_checks=[":pass"]),
        pra.REFUSAL_SYNC_CHECK_MALFORMED,
    ),
}


@pytest.mark.parametrize("kind,path", _nonempty_fields())
def test_empty_string_bounds_nonconform_exactly_as_writers_refuse(
    tmp_path,
    kind,
    path,
):
    """PRA-005: writer refusal and check nonconformity are one declaration."""
    driven = set(_EMPTY_DRIVEN_BY_WRITER)
    not_driven = set(_EMPTY_NOT_DRIVEN_BY_WRITER)
    assert driven & not_driven == set(), sorted(driven & not_driven)
    assert driven | not_driven == set(_nonempty_fields()), sorted(
        set(_nonempty_fields()) ^ (driven | not_driven),
    )

    check_dir = tmp_path / "check"
    check_dir.mkdir()
    trail = check_dir / "trail.md"
    _write_trail(trail, _sweep_mutation(kind, path, ""))
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING, out
    assert payload["result"] == pra.RESULT_NONCONFORMING, out
    assert any(
        item["kind"] == pra.NONCONFORMITY_RECORD_VALUE_INVALID
        and item["path"] == path
        for item in payload["findings"]
    ), payload["findings"]

    declared_reason = pra._refusal_for_violation(
        {"path": path, "value": "", "code": pra.VIOLATION_EMPTY_STRING},
        _valid_record(kind),
    )
    writer_dir = tmp_path / "writer"
    writer_dir.mkdir()
    if (kind, path) in _EMPTY_DRIVEN_BY_WRITER:
        code, out, _err = _EMPTY_DRIVEN_BY_WRITER[(kind, path)](writer_dir)
        payload = json.loads(out.strip())
        assert code == pra.EXIT_REFUSED, out
        assert payload["result"] == pra.RESULT_REFUSED, out
        assert payload["reason"] == declared_reason, payload
    else:
        driver, structural_reason = _EMPTY_NOT_DRIVEN_BY_WRITER[(kind, path)]
        code, out, _err = driver(writer_dir)
        payload = json.loads(out.strip())
        assert code == pra.EXIT_REFUSED, out
        assert payload["result"] == pra.RESULT_REFUSED, out
        assert payload["reason"] == structural_reason, payload
        assert payload["reason"] != declared_reason, payload


# --- WO-H: writer/declaration round trip and refusal totality ---------------


def _trail_records(trail):
    lines = pra._read_lines(str(trail))
    records, _positions, _openers, _markers, reason, detail = pra._parse_records(
        lines,
    )
    assert records is not None, (reason, detail)
    return records


def test_writer_output_round_trips_clean(tmp_path):
    """Every field every writer verb emits is declared.

    The standing guarantee that the writers and the declaration cannot drift:
    with unknown-field live, a field a writer emits that no declaration
    mentions would make the writers refuse their own output. Driven through
    the CLI so the record read back is the one a real caller appends.
    """
    plain = tmp_path / "plain"
    plain.mkdir()
    trail, _payload = _open_default(plain)
    code, out, _err = _record_round(
        trail,
        lenses=[pra.LENS_COLLISIONS, pra.LENS_DOD_ADEQUACY],
        parts=["slice-a:unreviewed", "slice-b:reviewed"],
        findings=["f-1:collisions", "f-2:collisions"],
        declined=["f-2"],
    )
    assert code == pra.EXIT_RECORDED, out
    code, out, _err = _record_verification(
        trail,
        findings=[
            "f-1:refutation:verified",
            "f-2:declined-extension:verified",
        ],
        evidence=["f-1:the register says otherwise"],
        sync_checks=["c1:pass", "c2:pass"],
    )
    assert code == pra.EXIT_RECORDED, out

    overridden = tmp_path / "overridden"
    overridden.mkdir()
    over_trail = overridden / "trail.md"
    code, out, _err = _run_cli(
        "open",
        "--trail", str(over_trail),
        "--invocation", "inv-2",
        "--cause", "second read",
        "--weight", pra.WEIGHT_FULL,
        "--children", "0",
        "--register-entries", "0",
        "--ceiling", "1",
        "--override", "owner said so",
        "--seat", "seat-a",
        "--seat", "seat-b",
    )
    assert code == pra.EXIT_RECORDED, out

    records = _trail_records(trail) + _trail_records(over_trail)
    kinds_seen = set()
    for record in records:
        violations = pra._walk_record_for_kind(record)
        assert violations == [], (record, violations)
        kinds_seen.add(record["kind"])
    # Fail-closed floor: a round trip that inspected nothing proves nothing.
    assert kinds_seen == set(pra.RECORD_KINDS), sorted(kinds_seen)
    assert len(records) == 4, records

    # Optional shapes the writers can emit are present in what was walked:
    # an evidence string on one verification finding and not the other, and a
    # populated declinedExtension.
    round_record = [
        record for record in records
        if record["kind"] == pra.RECORD_KIND_ROUND
    ][0]
    assert round_record["declinedExtension"] == ["f-2"], round_record
    ver_record = [
        record for record in records
        if record["kind"] == pra.RECORD_KIND_VERIFICATION
    ][0]
    evidence_present = [
        item for item in ver_record["findings"] if "evidence" in item
    ]
    assert len(evidence_present) == 1, ver_record["findings"]

    # An invocation opened without --override still emits the key, as null.
    # Null on a non-required field is an absent value -- neither an unknown
    # field nor a bad string.
    no_override = [
        record for record in records
        if record["kind"] == pra.RECORD_KIND_INVOCATION
        and record["invocation"] == "inv-1"
    ]
    assert len(no_override) == 1, no_override
    assert "override" in no_override[0], no_override[0]
    assert no_override[0]["override"] is None, no_override[0]

    # End to end: the writers' own trail is conforming to the reader.
    code, out, _err = _run_cli("check", "--trail", str(trail))
    assert code == pra.EXIT_CONFORMING, out


@pytest.mark.parametrize(
    "kind,path",
    [
        (pra.RECORD_KIND_INVOCATION, "bogusField"),
        (pra.RECORD_KIND_INVOCATION, "measurables.bogusField"),
        (pra.RECORD_KIND_ROUND, "parts[0].bogusField"),
        (pra.RECORD_KIND_ROUND, "findings[0].bogusField"),
        (pra.RECORD_KIND_VERIFICATION, "syncChecks[0].bogusField"),
    ],
)
def test_unknown_field_reported_with_its_full_path(tmp_path, kind, path):
    """Depth is no hiding place: nested and array-item keys carry full paths."""
    trail = tmp_path / "trail.md"
    _write_trail(trail, _sweep_mutation(kind, path, "x"))
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING, out
    assert any(
        item["kind"] == pra.NONCONFORMITY_RECORD_VALUE_INVALID
        and item["path"] == path
        for item in payload["findings"]
    ), payload["findings"]


_VIOLATION_CODES = (
    pra.VIOLATION_FIELD_MISSING,
    pra.VIOLATION_TYPE_INVALID,
    pra.VIOLATION_ENUM_INVALID,
    pra.VIOLATION_EMPTY_STRING,
    pra.VIOLATION_BELOW_MINIMUM,
    pra.VIOLATION_TOO_FEW_ITEMS,
    pra.VIOLATION_UNKNOWN_FIELD,
)


def test_no_declaration_violation_projects_to_internal_error():
    """internal-error means the tool broke; a bad value must never claim it.

    Proved by enumeration over every constraint the declaration carries, not
    by example: a constraint added later without a refusal reddens this.
    """
    projected = 0
    for kind, declaration in pra.RECORD_SCHEMAS.items():
        for path, _constraint in _iter_constraints(declaration):
            for code in _VIOLATION_CODES:
                reason = pra._refusal_for_violation(
                    {"path": path, "value": "", "code": code},
                    {"kind": kind},
                )
                assert reason != pra.REFUSAL_INTERNAL_ERROR, (kind, path, code)
                assert reason in pra.REFUSAL_REASONS, (kind, path, code, reason)
                projected += 1
    # Fail-closed floor: an enumeration that projected nothing proves nothing.
    assert projected >= len(_VIOLATION_CODES) * 3, projected


def test_declaration_self_check_requires_a_refusal_on_every_constraint():
    problems = pra._validate_constraint("test", {"type": "string"})
    assert any("is missing refusal" in p for p in problems), problems

    problems = pra._validate_constraint(
        "test",
        {"type": "string", "refusal": pra.REFUSAL_RECORD_FIELD_INVALID},
    )
    assert problems == [], problems


def test_open_empty_cause_refuses_with_a_declared_token(tmp_path):
    """An ordinary bad argument is refused, and never as an internal error."""
    code, out, _err = _open_with_empty(tmp_path, cause="")
    payload = json.loads(out.strip())
    assert code == pra.EXIT_REFUSED, out
    assert payload["result"] == pra.RESULT_REFUSED, out
    assert payload["reason"] != pra.REFUSAL_INTERNAL_ERROR, payload
    assert payload["reason"] == pra.REFUSAL_RECORD_FIELD_INVALID, payload
    assert payload["reason"] == pra._refusal_for_violation(
        {
            "path": "cause",
            "value": "",
            "code": pra.VIOLATION_EMPTY_STRING,
        },
        _valid_record(pra.RECORD_KIND_INVOCATION),
    ), payload
