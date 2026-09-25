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


def _malformed_pairs(parsed):
    return [(m["entry"], m["reason"]) for m in parsed["malformed"]]


def _section_duplicated_core():
    base = CM.render_core(dict(_CORE_FACTS), "confirmed", "2026-06-26", "2026-06-26")
    insert = "## Vet checks\n\n### One\n- **Evidence:** a\n- **The vet records:** b\n\n"
    at = base.index("```json superheroes-core")
    return (
        base[:at]
        + insert
        + "## Vet checks\n\n### Two\n- **Evidence:** c\n- **The vet records:** d\n\n"
        + base[at:]
    )


def _section_empty_core():
    text = _render_with_vet("")
    text = text.replace(_HEALTHY_BODY, "")
    at = text.index("```json superheroes-core")
    return text[:at] + "## Vet checks\n\n\n" + text[at:]


@pytest.mark.parametrize(
    "text,expected_malformed,expected_checks",
    [
        pytest.param(
            "section-duplicated",
            [(None, "section-duplicated")],
            [{"name": "One", "evidence": "a", "records": "b"}],
            id="section-duplicated",
        ),
        pytest.param(
            "section-empty",
            [(None, "section-empty")],
            [],
            id="section-empty",
        ),
        pytest.param(
            "line one\nline two",
            [(None, "stray-text")],
            [],
            id="stray-text-two-lines",
        ),
        pytest.param(
            "intro\n\n### X\n- **Evidence:** a\n- **The vet records:** b",
            [(None, "stray-text")],
            [{"name": "X", "evidence": "a", "records": "b"}],
            id="stray-text",
        ),
        pytest.param(
            "### \n- **Evidence:** a\n- **The vet records:** b",
            [(None, "name-empty")],
            [],
            id="name-empty",
        ),
        pytest.param(
            "### Same\n- **Evidence:** a\n- **The vet records:** b\n\n### same\n"
            "- **Evidence:** c\n- **The vet records:** d",
            [("same", "name-duplicated")],
            [{"name": "Same", "evidence": "a", "records": "b"}],
            id="name-duplicated",
        ),
        pytest.param(
            "### X\n- **Evidence:** a\n- **Evidence:** b\n- **The vet records:** c",
            [("X", "field-duplicated")],
            [],
            id="field-duplicated-evidence",
        ),
        pytest.param(
            "### X\n- **Evidence:** a\n- **The vet records:** r1\n- **The vet records:** r2",
            [("X", "field-duplicated")],
            [],
            id="field-duplicated-records",
        ),
        pytest.param(
            "### X\n- **Evidence:**\n- **The vet records:** c",
            [("X", "field-empty")],
            [],
            id="field-empty-evidence",
        ),
        pytest.param(
            "### X\n- **Evidence:** a\n- **The vet records:**",
            [("X", "field-empty")],
            [],
            id="field-empty-records",
        ),
        pytest.param(
            "### X\n- **The vet records:** c",
            [("X", "evidence-missing")],
            [],
            id="evidence-missing",
        ),
        pytest.param(
            "### X\n- **Evidence:** a",
            [("X", "records-missing")],
            [],
            id="records-missing",
        ),
        pytest.param(
            "### X\n- **Evidence:** a\n- **The vet records:** b\nnot a field",
            [("X", "unrecognized-line")],
            [],
            id="unrecognized-line-in-entry",
        ),
        pytest.param(
            "### X\n  orphan indent\n- **Evidence:** a\n- **The vet records:** b",
            [("X", "unrecognized-line")],
            [],
            id="unrecognized-line-indent-no-field",
        ),
        pytest.param(
            "### X\n- **The vet records:**",
            [("X", "evidence-missing"), ("X", "field-empty")],
            [],
            id="two-reasons-one-entry",
        ),
    ],
)
def test_parse_malformed_tokens(text, expected_malformed, expected_checks):
    if text == "section-duplicated":
        core_text = _section_duplicated_core()
    elif text == "section-empty":
        core_text = _section_empty_core()
    else:
        core_text = _render_with_vet(text)
    parsed = CM.parse_vet_checks(core_text)
    assert _malformed_pairs(parsed) == expected_malformed
    assert parsed["checks"] == expected_checks


def test_literal_pins_for_vet_checks_markers():
    heading = "## Vet checks"
    evidence = "- **Evidence:**"
    records = "- **The vet records:**"
    body = (
        "### Pin check\n"
        + evidence + " e\n"
        + records + " r\n"
    )
    facts = dict(_CORE_FACTS, vetChecks=body)
    text = CM.render_core(facts, "confirmed", "2026-06-26", "2026-06-26")
    assert heading in text
    got = CM.parse_vet_checks(text)
    assert got["malformed"] == []
    assert got["checks"] == [{"name": "Pin check", "evidence": "e", "records": "r"}]


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


def test_confirm_refused_when_vet_checks_section_duplicated(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    dup_core = (
        _section_duplicated_core()
        .replace("status=confirmed", "status=provisional", 1)
        .replace('"status": "confirmed"', '"status": "provisional"', 1)
    )
    path = CM.core_path(repo, store)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(dup_core)
    before = open(path, encoding="utf-8").read()
    res = CM.confirm(repo, root=store, now="2026-06-28")
    assert res["action"] == "refused"
    assert res["reason"] == "vet-checks-malformed"
    assert [(m["entry"], m["reason"]) for m in res["malformed"]] == [
        (None, "section-duplicated"),
    ]
    assert open(path, encoding="utf-8").read() == before
    assert CM.read(repo, root=store)["status"] == "provisional"


def _write_core(repo, store, **extra):
    facts = dict(_CORE_FACTS, **extra)
    CM.write(repo, facts, "confirmed", root=store, now="2026-06-26")


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
    assert [(m["entry"], m["reason"]) for m in res["malformed"]] == [
        ("X", "evidence-missing"),
    ]


def test_write_vet_checks_refused_unchanged_malformed(tmp_path):
    repo, store = _repo_store(tmp_path)
    bad = "### X\n- **The vet records:** only records"
    path = CM.core_path(repo, store)
    text = open(path, encoding="utf-8").read()
    at = text.index("```json superheroes-core")
    open(path, "w", encoding="utf-8").write(
        text[:at]
        + "## Vet checks\n\n"
        + bad
        + "\n\n"
        + text[at:]
    )
    before = open(path, encoding="utf-8").read()
    res = CM.write_vet_checks(repo, bad, root=store)
    assert res["action"] == "refused"
    assert res["reason"] == "vet-checks-malformed"
    assert [(m["entry"], m["reason"]) for m in res["malformed"]] == [
        ("X", "evidence-missing"),
    ]
    assert open(path, encoding="utf-8").read() == before


_PATTERNS_WITH_PSEUDO_VET_HEADINGS = (
    "before\n"
    "\n"
    "```markdown\n"
    "## Vet checks\n"
    "keep-me-fenced\n"
    "```\n"
    "\n"
    "    ## Vet checks\n"
    "    keep-me-indented\n"
    "\n"
    "after"
)


def test_write_vet_checks_preserves_patterns_with_pseudo_vet_headings(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    _write_core(repo, store, patterns=_PATTERNS_WITH_PSEUDO_VET_HEADINGS)
    path = CM.core_path(repo, store)
    before = open(path, encoding="utf-8").read()
    patterns_before = CM._section(before, "Canonical patterns")
    res = CM.write_vet_checks(repo, _HEALTHY_BODY, root=store)
    assert res == {"action": "written"}
    after = open(path, encoding="utf-8").read()
    assert "keep-me-fenced" in after
    assert "keep-me-indented" in after
    assert CM._section(after, "Canonical patterns") == patterns_before


def test_confirm_does_not_manufacture_vet_checks_from_patterns_pseudo_heading(tmp_path):
    repo = str(tmp_path)
    store = str(tmp_path / "store")
    CM.write(
        repo,
        dict(_CORE_FACTS, patterns=_PATTERNS_WITH_PSEUDO_VET_HEADINGS),
        "provisional",
        root=store,
        now="2026-06-26",
    )
    path = CM.core_path(repo, store)
    before = open(path, encoding="utf-8").read()
    assert CM.parse_core(before)["vetChecks"] == ""
    patterns_before = CM._section(before, "Canonical patterns")
    res = CM.confirm(repo, root=store, now="2026-06-28")
    assert res["action"] == "confirmed"
    text = open(path, encoding="utf-8").read()
    assert CM.parse_vet_checks(text) == {"declared": False, "checks": [], "malformed": []}
    assert CM._section(text, "Canonical patterns") == patterns_before


def test_write_vet_checks_refused_clear_when_section_duplicated(tmp_path):
    repo, store = _repo_store(tmp_path)
    path = CM.core_path(repo, store)
    text = open(path, encoding="utf-8").read()
    at = text.index("```json superheroes-core")
    dup = (
        text[:at]
        + "## Vet checks\n\n### One\n- **Evidence:** a\n- **The vet records:** b\n\n"
        + "## Vet checks\n\n### Two\n- **Evidence:** c\n- **The vet records:** d\n\n"
        + text[at:]
    )
    open(path, "w", encoding="utf-8").write(dup)
    before = open(path, encoding="utf-8").read()
    res = CM.write_vet_checks(repo, "", root=store)
    assert res["action"] == "refused"
    assert res["reason"] == "vet-checks-malformed"
    assert [(m["entry"], m["reason"]) for m in res["malformed"]] == [
        (None, "section-duplicated"),
    ]
    assert open(path, encoding="utf-8").read() == before


def test_write_vet_checks_refused_heading_in_body(tmp_path):
    repo, store = _repo_store(tmp_path)
    bad = "## Sneaky\n\n### X\n- **Evidence:** a\n- **The vet records:** b"
    res = CM.write_vet_checks(repo, bad, root=store)
    assert res == {"action": "refused", "reason": "vet-checks-round-trip-refused"}


def test_vet_checks_body_forbidden_json_fence_line():
    assert CM._vet_checks_body_forbidden("```json superheroes-core") is True


def test_write_vet_checks_refused_when_evidence_smuggles_json_block(tmp_path):
    repo, store = _repo_store(tmp_path)
    path = CM.core_path(repo, store)
    before = open(path, encoding="utf-8").read()
    body = (
        "### X\n- **The vet records:** b\n"
        "- **Evidence:** ```json superheroes-core\n"
        '  {"schemaVersion": 2, "verifyCommand": "evil"}'
    )
    res = CM.write_vet_checks(repo, body, root=store)
    assert res == {"action": "refused", "reason": "vet-checks-round-trip-refused"}
    assert open(path, encoding="utf-8").read() == before


def test_write_vet_checks_refused_when_evidence_smuggles_non_json_block(tmp_path):
    repo, store = _repo_store(tmp_path)
    path = CM.core_path(repo, store)
    before = open(path, encoding="utf-8").read()
    body = (
        "### X\n- **The vet records:** b\n"
        "- **Evidence:** ```json superheroes-core\n"
        "  not-json"
    )
    res = CM.write_vet_checks(repo, body, root=store)
    assert res == {"action": "refused", "reason": "vet-checks-round-trip-refused"}
    assert open(path, encoding="utf-8").read() == before


def test_read_vet_checks_invalid_utf8(tmp_path):
    repo, store = _repo_store(tmp_path)
    path = CM.core_path(repo, store)
    with open(path, "wb") as fh:
        fh.write(b"\xff")
    got = CM.read_vet_checks(repo, root=store)
    assert got["declared"] is False
    assert got["checks"] == []
    assert got["malformed"] == []
    assert got["reason"] == "core-md-unparseable"


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
