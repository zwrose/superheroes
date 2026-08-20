"""Tests for package_read_audit (#937)."""
import json
import os
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


def test_record_value_invalid_extra_key_allowed(tmp_path):
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
    assert code == pra.EXIT_CONFORMING


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


def test_check_order_independence_same_kinds(tmp_path):
    trail_a_path = tmp_path / "a" / "trail.md"
    trail_a_path.parent.mkdir(parents=True)
    trail_a, _ = _open_default(tmp_path / "a", trail=trail_a_path)
    _record_round(trail_a, round_no=1, findings=["f-1:collisions"])
    _record_round(trail_a, round_no=2, mechanical_only=True, parts=["pkg:reviewed"])
    _record_verification(
        trail_a,
        findings=["f-1:package-fix:verified"],
        sync_checks=["c1:pass", "c2:pass"],
    )

    trail_b_path = tmp_path / "b" / "trail.md"
    trail_b_path.parent.mkdir(parents=True)
    trail_b, _ = _open_default(tmp_path / "b", trail=trail_b_path)
    _record_round(trail_b, round_no=1, findings=["f-1:collisions"])
    _record_round(trail_b, round_no=2, mechanical_only=True, parts=["pkg:reviewed"])
    _record_verification(
        trail_b,
        findings=["f-1:package-fix:verified"],
        sync_checks=["c1:pass", "c2:pass"],
    )
    text_b = trail_b.read_text(encoding="utf-8")
    blocks = text_b.split(pra.RECORD_MARKER)
    invocation_block = blocks[1]
    round1_block = blocks[2]
    round2_block = blocks[3]
    verification_block = blocks[4]
    reordered = (
        pra.TRAIL_HEADING + "\n"
        + pra.RECORD_MARKER + invocation_block
        + pra.RECORD_MARKER + round2_block
        + pra.RECORD_MARKER + verification_block
        + pra.RECORD_MARKER + round1_block
    )
    trail_b.write_text(reordered, encoding="utf-8")

    code_a, out_a, _ = _run_cli("check", "--trail", str(trail_a))
    code_b, out_b, _ = _run_cli("check", "--trail", str(trail_b))
    payload_a = json.loads(out_a.strip())
    payload_b = json.loads(out_b.strip())
    assert code_a == code_b
    assert payload_a["result"] == payload_b["result"]
    kinds_a = {item["kind"] for item in payload_a["findings"]}
    kinds_b = {item["kind"] for item in payload_b["findings"]}
    assert kinds_a == kinds_b


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
        text = trail.read_text(encoding="utf-8")
        if field_name == "round":
            text = text.replace('"round": 1', '"round": null', 1)
        elif field_name == "mechanicalOnly":
            text = text.replace('"mechanicalOnly": false', '"mechanicalOnly": null', 1)
        elif field_name == "controlProbe":
            text = text.replace(
                '"controlProbe": "%s"' % pra.CONTROL_PROBE_ENGAGED,
                '"controlProbe": null',
                1,
            )
        trail.write_text(text, encoding="utf-8")
        code, out, _err = _run_cli("check", "--trail", str(trail))
        payload = json.loads(out.strip())
        summary = payload["invocations"][0]
        assert summary["roundsAsserted"][0][summary_key] is None
    else:
        text = trail.read_text(encoding="utf-8")
        if field_name == "ceiling":
            text = text.replace('"ceiling": 3', '"ceiling": null', 1)
        elif field_name == "weight":
            text = text.replace('"weight": "light"', '"weight": null', 1)
        elif field_name == "seats":
            text = text.replace(
                '"seats": [\n  "seat-a"\n ]',
                '"seats": null',
                1,
            )
        trail.write_text(text, encoding="utf-8")
        _record_round(trail)
        code, out, _err = _run_cli("check", "--trail", str(trail))
        payload = json.loads(out.strip())
        summary = payload["invocations"][0]
        assert summary[summary_key] is None
