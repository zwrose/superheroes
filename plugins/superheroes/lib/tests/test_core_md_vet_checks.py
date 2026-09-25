# plugins/superheroes/lib/tests/test_core_md_vet_checks.py
import importlib.util
import json
import os
import subprocess
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_LIB = os.path.join(_REPO_ROOT, "plugins/superheroes/lib")
_CORE_MD = os.path.join(_LIB, "core_md.py")


def _load(name):
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    path = os.path.join(_LIB, name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CM = _load("core_md")

_CORE_FACTS = {"verifyCommand": "npm test", "stackTags": ["node"],
               "threatModel": "single-user", "patterns": "- x: a.ts:1"}

_HEALTHY_BODY = (
    "### Alpha check\n"
    "- **Evidence:** PR section Summary\n"
    "- **The vet records:** alpha receipt\n"
    "\n"
    "### Beta check\n"
    "- **Evidence:** ledger path\n"
    "  continued evidence\n"
    "- **The vet records:** beta receipt"
)


def _render_with_vet(body):
    facts = dict(_CORE_FACTS, vetChecks=body)
    return CM.render_core(facts, "confirmed", "2026-06-26", "2026-06-26")


def _write_core(repo, store, **extra):
    facts = dict(_CORE_FACTS, **extra)
    CM.write(repo, facts, "confirmed", root=store, now="2026-06-26")


def test_parse_healthy_vet_checks_two_entries_with_continuation():
    text = _render_with_vet(_HEALTHY_BODY)
    got = CM.parse_vet_checks(text)
    assert got["declared"] is True
    assert got["malformed"] == []
    assert got["checks"] == [
        {"name": "Alpha check", "evidence": "PR section Summary", "records": "alpha receipt"},
        {"name": "Beta check", "evidence": "ledger path continued evidence",
         "records": "beta receipt"},
    ]


@pytest.mark.parametrize("body,token", [
    ("## Vet checks\n\n## Vet checks\n\n### X\n- **Evidence:** a\n- **The vet records:** b",
     "section-duplicated"),
    ("", "section-empty"),
    ("intro\n\n### X\n- **Evidence:** a\n- **The vet records:** b", "stray-text"),
    ("### \n- **Evidence:** a\n- **The vet records:** b", "name-empty"),
    ("### Same\n- **Evidence:** a\n- **The vet records:** b\n\n### same\n"
     "- **Evidence:** c\n- **The vet records:** d", "name-duplicated"),
    ("### X\n- **Evidence:** a\n- **Evidence:** b\n- **The vet records:** c", "field-duplicated"),
    ("### X\n- **Evidence:**\n- **The vet records:** c", "field-empty"),
    ("### X\n- **The vet records:** c", "evidence-missing"),
    ("### X\n- **Evidence:** a", "records-missing"),
    ("### X\n- **Evidence:** a\n- **The vet records:** b\nnot a field", "unrecognized-line"),
])
def test_parse_malformed_tokens(body, token):
    if token == "section-duplicated":
        base = CM.render_core(dict(_CORE_FACTS), "confirmed", "2026-06-26", "2026-06-26")
        insert = "## Vet checks\n\n### One\n- **Evidence:** a\n- **The vet records:** b\n\n"
        at = base.index("```json superheroes-core")
        text = base[:at] + insert + "## Vet checks\n\n### Two\n- **Evidence:** c\n- **The vet records:** d\n\n" + base[at:]
    elif token == "section-empty":
        text = _render_with_vet("")
        text = text.replace(_HEALTHY_BODY, "")
        # empty vetChecks omits heading — inject empty section
        at = text.index("```json superheroes-core")
        text = text[:at] + "## Vet checks\n\n\n" + text[at:]
    else:
        text = _render_with_vet(body)
    parsed = CM.parse_vet_checks(text)
    reasons = [m["reason"] for m in parsed["malformed"]]
    assert token in reasons


def test_literal_pins_for_vet_checks_markers():
    heading = "## Vet checks"
    evidence = "- **Evidence:**"
    records = "- **The vet records:**"
    assert heading == "## Vet checks"
    assert evidence == "- **Evidence:**"
    assert records == "- **The vet records:**"
    sample = heading + "\n\n### N\n" + evidence + " x\n" + records + " y\n"
    assert sample.count(heading) == 1


def test_read_vet_checks_no_section_declared_false_reason_null(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _write_core(repo, store)
    got = CM.read_vet_checks(repo, root=store)
    assert got == {"declared": False, "checks": [], "malformed": [], "reason": None}


def test_read_vet_checks_absent_core(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    got = CM.read_vet_checks(repo, root=store)
    assert got["declared"] is False
    assert got["checks"] == []
    assert got["malformed"] == []
    assert got["reason"] == "core-md-absent"


def test_read_vet_checks_corrupt_json(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _write_core(repo, store, vetChecks=_HEALTHY_BODY)
    path = CM.core_path(repo, store)
    text = open(path, encoding="utf-8").read()
    broken = text.replace('"schemaVersion": 2', '"schemaVersion": "bad"')
    open(path, "w", encoding="utf-8").write(broken)
    got = CM.read_vet_checks(repo, root=store)
    assert got["declared"] is False
    assert got["checks"] == []
    assert got["malformed"] == []
    assert got["reason"] == "core-md-unparseable"


def test_confirm_preserves_vet_checks_on_provisional_core(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    before = CM.parse_vet_checks(_render_with_vet(_HEALTHY_BODY))["checks"]
    CM.write(repo, dict(_CORE_FACTS, vetChecks=_HEALTHY_BODY), "provisional", root=store, now="2026-06-26")
    res = CM.confirm(repo, root=store, now="2026-06-28")
    assert res["action"] == "confirmed"
    path = CM.core_path(repo, store)
    text = open(path, encoding="utf-8").read()
    assert "## Vet checks" in text
    after = CM.parse_vet_checks(text)
    assert after["checks"] == before


def _repo_store(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _write_core(repo, store)
    return repo, store


def test_write_vet_checks_written_and_read_back(tmp_path):
    repo, store = _repo_store(tmp_path)
    res = CM.write_vet_checks(repo, _HEALTHY_BODY, root=store)
    assert res == {"action": "written"}
    got = CM.read_vet_checks(repo, root=store)
    assert got["declared"] is True
    assert len(got["checks"]) == 2


def test_write_vet_checks_noop(tmp_path):
    repo, store = _repo_store(tmp_path)
    CM.write_vet_checks(repo, _HEALTHY_BODY, root=store)
    res = CM.write_vet_checks(repo, _HEALTHY_BODY, root=store)
    assert res == {"action": "noop"}


def test_write_vet_checks_clear(tmp_path):
    repo, store = _repo_store(tmp_path)
    CM.write_vet_checks(repo, _HEALTHY_BODY, root=store)
    res = CM.write_vet_checks(repo, "", root=store)
    assert res == {"action": "written"}
    got = CM.read_vet_checks(repo, root=store)
    assert got["declared"] is False
    assert got["reason"] is None


def test_write_vet_checks_refused_malformed(tmp_path):
    repo, store = _repo_store(tmp_path)
    bad = "### X\n- **The vet records:** only records"
    res = CM.write_vet_checks(repo, bad, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == "vet-checks-malformed"
    assert any(m["reason"] == "evidence-missing" for m in res["malformed"])


def test_write_vet_checks_refused_heading_in_body(tmp_path):
    repo, store = _repo_store(tmp_path)
    bad = "## Sneaky\n\n### X\n- **Evidence:** a\n- **The vet records:** b"
    res = CM.write_vet_checks(repo, bad, root=store)
    assert res == {"action": "refused", "reason": "vet-checks-round-trip-refused"}


def test_write_vet_checks_refused_absent_core(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    res = CM.write_vet_checks(repo, _HEALTHY_BODY, root=store)
    assert res == {"action": "refused", "reason": "core-md-absent"}


def test_write_vet_checks_preserves_other_sections(tmp_path):
    repo, store = _repo_store(tmp_path)
    path = CM.core_path(repo, store)
    before = open(path, encoding="utf-8").read()
    threat_before = CM._section(before, "Threat model")
    CM.write_vet_checks(repo, _HEALTHY_BODY, root=store)
    after = open(path, encoding="utf-8").read()
    assert CM._section(after, "Threat model") == threat_before


def test_cli_vet_checks(tmp_path):
    repo, store = _repo_store(tmp_path)
    CM.write_vet_checks(repo, _HEALTHY_BODY, root=store)
    proc = subprocess.run(
        ["/usr/bin/python3", "-B", _CORE_MD, "vet-checks", "--cwd", repo, "--root", store],
        check=True, capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": _LIB},
    )
    assert proc.returncode == 0
    got = json.loads(proc.stdout)
    assert got["declared"] is True
    assert len(got["checks"]) == 2


def test_cli_write_vet_checks(tmp_path):
    repo, store = _repo_store(tmp_path)
    proc = subprocess.run(
        ["/usr/bin/python3", "-B", _CORE_MD, "write-vet-checks", "--cwd", repo, "--root", store],
        input=_HEALTHY_BODY, check=True, capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": _LIB},
    )
    assert proc.returncode == 0
    got = json.loads(proc.stdout)
    assert got["action"] == "written"
