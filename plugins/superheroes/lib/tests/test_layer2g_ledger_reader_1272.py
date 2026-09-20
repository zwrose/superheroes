"""#1272 layer 2g: disposition-ledger validating reader and census guards."""
import ast
import importlib.util
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

_WRITER_NAME = "_ensure_disposition_ledger_for_write"
_ALLOWED_WRITER_FUNCTIONS = frozenset({
    _WRITER_NAME,
    "_stage_findings",
    "_record_disposition",
    "_record_merged_into",
    "_archive_departures",
})
_ALLOWED_LEDGER_KEY_FUNCTIONS = frozenset({_WRITER_NAME})
_SESSION_CONTRACT_BASENAME = "session_contract.py"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SC = _load("session_contract")
RC = _load("round_certification")
RD = _load("round_driver")


def _product_py_paths():
    paths = []
    for name in sorted(os.listdir(_LIB)):
        if not name.endswith(".py"):
            continue
        if name.startswith("test_"):
            continue
        paths.append(os.path.join(_LIB, name))
    return paths


def _enclosing_function_name(node, parent_map):
    current = node
    while current is not None:
        if isinstance(current, ast.FunctionDef):
            return current.name
        current = parent_map.get(current)
    return "<module>"


def _build_parent_map(tree):
    parent_map = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_map[child] = parent
    return parent_map


def _census_ledger_touch_sites():
    writer_sites = []
    key_sites = []
    literal_sites = []
    for path in _product_py_paths():
        relpath = os.path.relpath(path, _LIB)
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=path)
        parent_map = _build_parent_map(tree)
        for node in ast.walk(tree):
            func = _enclosing_function_name(node, parent_map)
            if isinstance(node, ast.FunctionDef) and node.name == _WRITER_NAME:
                writer_sites.append((relpath, func))
            if isinstance(node, ast.Name) and node.id == _WRITER_NAME:
                if isinstance(node.ctx, (ast.Load, ast.Store)):
                    writer_sites.append((relpath, func))
            if isinstance(node, ast.Name) and node.id == "DISPOSITION_LEDGER_KEY":
                key_sites.append((relpath, func))
            if isinstance(node, ast.Attribute) and node.attr == "DISPOSITION_LEDGER_KEY":
                key_sites.append((relpath, func))
            if isinstance(node, ast.Constant) and node.value == "dispositionLedger":
                literal_sites.append((relpath, func))
    return writer_sites, key_sites, literal_sites


def _state_bytes(state):
    return json.dumps(state, sort_keys=True)


def _ledger_owned_state(**over):
    base = {
        "schemaVersion": 5,
        "dispositionLedgerOwner": "ledger",
        "dispositionLedger": [],
        "findings": [],
        "_records": [],
    }
    base.update(over)
    return base


def _cfg():
    return {"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "codex"}


def _panel_artifact():
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    seats["code-reviewer"] = {
        "findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}],
    }
    return {"seats": seats}


def _session_state_bytes(session_dir):
    with open(os.path.join(session_dir, RD.STATE_FILE), "rb") as fh:
        return fh.read()


# --- census detector ------------------------------------------------------------------

def test_census_writer_only_at_fold_time_sites():
    writer_sites, key_sites, literal_sites = _census_ledger_touch_sites()
    unexpected_writer = sorted({
        "%s:%s" % (relpath, func)
        for relpath, func in writer_sites
        if func not in _ALLOWED_WRITER_FUNCTIONS
    })
    assert unexpected_writer == [], "writer outside fold-time sites: %s" % unexpected_writer

    unexpected_key = sorted({
        "%s:%s" % (relpath, func)
        for relpath, func in key_sites
        if relpath != _SESSION_CONTRACT_BASENAME and func not in _ALLOWED_LEDGER_KEY_FUNCTIONS
    })
    assert unexpected_key == [], "DISPOSITION_LEDGER_KEY outside allowlist: %s" % unexpected_key

    unexpected_literal = sorted({
        "%s:%s" % (relpath, func)
        for relpath, func in literal_sites
        if relpath != _SESSION_CONTRACT_BASENAME and func not in _ALLOWED_LEDGER_KEY_FUNCTIONS
    })
    assert unexpected_literal == [], (
        "dispositionLedger literal outside allowlist: %s" % unexpected_literal
    )


# --- immutability detector ------------------------------------------------------------

_MALFORMED_CASES = (
    ("non-list", {"dispositionLedger": None}),
    ("non-object-row", {"dispositionLedger": ["not-a-dict"]}),
)


@pytest.mark.parametrize("label,ledger_over", _MALFORMED_CASES)
def test_terminal_read_paths_do_not_mutate_malformed_ledger(label, ledger_over):
    state = _ledger_owned_state(**ledger_over)
    before = _state_bytes(state)
    rows, by_key, fault = RD._fixed_ledger_rows(state)
    assert rows == []
    assert by_key == {}
    assert fault is not None
    assert fault.token == SC.DISPOSITION_LEDGER_MALFORMED_TOKEN
    assert _state_bytes(state) == before
    by_key_cert, refusal = RC._certification_findings_by_key(state)
    assert by_key_cert == {}
    assert refusal is not None
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["bindingFailure"] == SC.DISPOSITION_LEDGER_MALFORMED_TOKEN
    assert _state_bytes(state) == before


def test_terminal_read_paths_do_not_mutate_keyless_ledger_row(monkeypatch):
    """Keyless ledger row — production identity can mint from content; force the refusal arm."""
    state = _ledger_owned_state(dispositionLedger=[{"file": "x.py", "line": 1}])
    contract = RD.session_contract
    real_key = contract.finding_identity_key

    def _key_or_none(finding):
        if isinstance(finding, dict) and finding.get("_force_keyless"):
            return None
        return real_key(finding)

    monkeypatch.setattr(contract, "finding_identity_key", _key_or_none)
    state["dispositionLedger"][0]["_force_keyless"] = True
    before = _state_bytes(state)
    rows, by_key, fault = RD._fixed_ledger_rows(state)
    assert rows == []
    assert by_key == {}
    assert fault is not None
    assert fault.detail == "dispositionLedger row lacks a finding key"
    assert _state_bytes(state) == before
    by_key_cert, refusal = RC._certification_findings_by_key(state)
    assert by_key_cert == {}
    assert refusal is not None
    assert refusal["bindingFailure"] == SC.DISPOSITION_LEDGER_MALFORMED_TOKEN
    assert _state_bytes(state) == before


def test_read_disposition_ledger_defensive_copy_blocks_alias_mutation():
    key = "k-alias"
    state = _ledger_owned_state(
        dispositionLedger=[{
            SC.FINDING_KEY_FIELD: key,
            "file": "a.py", "line": 1, "title": "t", "severity": "Minor",
            "disposition": "fixed", "dispositionRound": 1,
        }],
    )
    before = _state_bytes(state)
    rows, fault = SC.read_disposition_ledger(state)
    assert fault is None
    assert len(rows) == 1
    rows[0]["disposition"] = "refuted"
    assert _state_bytes(state) == before
    assert state["dispositionLedger"][0]["disposition"] == "fixed"


def test_absent_ledger_key_is_not_malformed():
    state = {"schemaVersion": 5, "findings": []}
    rows, fault = SC.read_disposition_ledger(state)
    assert rows == []
    assert fault is None


def test_unrecognized_owner_refuses():
    state = {
        "schemaVersion": 5,
        "dispositionLedgerOwner": None,
        "dispositionLedger": None,
        "findings": [],
        "_records": [],
    }
    before = _state_bytes(state)
    by_key, refusal = RC._certification_findings_by_key(state)
    assert refusal is not None
    assert refusal["bindingFailure"] == "disposition-ledger-owner-unrecognized"
    assert _state_bytes(state) == before


def test_legacy_branch_tolerates_malformed_ledger_row():
    good_key = "good@L1"
    state = {
        "schemaVersion": 5,
        "dispositionLedger": [
            {
                SC.FINDING_KEY_FIELD: good_key,
                "file": "good.py",
                "line": 1,
                "title": "ok",
                "severity": "Minor",
            },
            "not-a-dict",
        ],
        "findings": [],
        "_records": [],
    }
    before = _state_bytes(state)
    by_key, refusal = RC._certification_findings_by_key(state)
    assert refusal is None
    assert good_key in by_key
    assert _state_bytes(state) == before


# --- BP-2f-b: submit preflight journal row --------------------------------------------

def test_bite_bp2f_b_submit_preflight_journals_unrecognized_owner(tmp_path):
    """axis: unrecognized dispositionLedgerOwner refuses submit before fold — preflight journal only."""
    session_dir = str(tmp_path)
    n = RD.cmd_next(session_dir, _cfg())
    assert n["ok"], n
    ok, state = RD.load_state(session_dir)
    assert ok and state is not None
    state["dispositionLedgerOwner"] = "ledger-v2"
    RD.save_state(session_dir, state)
    n = RD.cmd_next(session_dir)
    assert n["ok"], n
    before_state = _session_state_bytes(session_dir)
    out = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"],
                        _panel_artifact())
    assert out["ok"] is False
    assert out["reason"] == RD.DISPOSITION_LEDGER_OWNER_UNRECOGNIZED_CAUSE
    assert _session_state_bytes(session_dir) == before_state
    journal = RD.read_journal(session_dir)
    preflight_rows = [
        row for row in journal
        if row.get("cmd") == "submit"
        and row.get("outcome") == RD.DISPOSITION_LEDGER_OWNER_UNRECOGNIZED_CAUSE
    ]
    assert len(preflight_rows) == 1
    assert journal[-1].get("outcome") == RD.DISPOSITION_LEDGER_OWNER_UNRECOGNIZED_CAUSE
    ok, after = RD.load_state(session_dir)
    assert ok and after is not None
    assert after.get("pending") is not None
    submit_outcomes = [row.get("outcome") for row in journal if row.get("cmd") == "submit"]
    assert submit_outcomes.count(RD.DISPOSITION_LEDGER_OWNER_UNRECOGNIZED_CAUSE) == 1
