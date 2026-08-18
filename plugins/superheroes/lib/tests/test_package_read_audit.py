"""Tests for package_read_audit (#937)."""
import json
import os
import subprocess
import sys

import pytest

import package_read_audit as pra

_HERE = os.path.dirname(os.path.abspath(__file__))
_MODULE = os.path.join(os.path.dirname(_HERE), "package_read_audit.py")
_PYTHON = "/usr/bin/python3"
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
        *(
            ["--seat", seat] for seat in seats[1:]
        ),
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
):
    if findings is None:
        findings = []
    if sync_checks is None:
        sync_checks = []
    args = [
        "record-verification",
        "--trail", str(trail),
        "--invocation", invocation,
    ]
    for finding in findings:
        args.extend(["--finding", finding])
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
    assert summary["converged"] is True
    assert summary["ceilingReached"] is True
    assert summary["parkOwed"] is False


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
        sync_checks=["c1:pass"],
    )
    code, out, _err = _run_cli("check", "--trail", str(trail))
    assert code == pra.EXIT_CONFORMING
    payload = json.loads(out.strip())
    summary = payload["invocations"][0]
    assert summary["parkOwed"] is True
    assert summary["ceilingReached"] is True
    assert summary["converged"] is False
    assert payload["findings"] == []


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
        findings=["f-1:refutation:verified"],
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


def test_nonconformity_element_missing(tmp_path):
    trail, _ = _open_default(tmp_path)
    _hand_append_record(trail, {
        "kind": "round",
        "invocation": "inv-1",
        "round": 1,
        "lenses": [],
        "parts": [],
        "controlProbe": None,
        "findings": [],
        "declinedExtension": [],
        "mechanicalOnly": False,
    })
    code, out, _err = _run_cli("check", "--trail", str(trail))
    assert code == pra.EXIT_NONCONFORMING
    kinds = {item["kind"] for item in json.loads(out.strip())["findings"]}
    assert pra.NONCONFORMITY_ELEMENT_MISSING in kinds


def test_nonconformity_finding_unverified(tmp_path):
    trail, _ = _open_default(tmp_path)
    _record_round(trail, findings=["f-1:collisions"])
    code, out, _err = _run_cli("check", "--trail", str(trail))
    assert code == pra.EXIT_NONCONFORMING
    payload = json.loads(out.strip())
    assert any(
        item["kind"] == pra.NONCONFORMITY_FINDING_UNVERIFIED
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
        sync_checks=["c1:fail"],
    )
    code, out, _err = _run_cli("check", "--trail", str(trail))
    payload = json.loads(out.strip())
    assert code == pra.EXIT_NONCONFORMING
    assert any(
        item["kind"] == pra.NONCONFORMITY_SYNC_CHECK_FAILED
        for item in payload["findings"]
    )


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
    records, reason, _detail = pra._parse_records(pra._read_lines(str(trail)))
    assert reason is None
    assert len(records) == 1
    assert records[0]["kind"] == "invocation"


def test_marker_discipline_marker_without_fence_malformed(tmp_path):
    trail, _ = _open_default(tmp_path)
    text = trail.read_text(encoding="utf-8")
    text += "\n" + pra.RECORD_MARKER + "\n"
    trail.write_text(text, encoding="utf-8")
    records, reason, _detail = pra._parse_records(pra._read_lines(str(trail)))
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
    records, reason, _detail = pra._parse_records(pra._read_lines(str(trail)))
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


# --- vocabulary drift guards ------------------------------------------------


def test_refusal_reasons_complete():
    assert pra.REFUSAL_REASONS


def test_nonconformity_kinds_complete():
    assert pra.NONCONFORMITY_KINDS


def test_undecided_reasons_complete():
    assert pra.UNDECIDED_REASONS
