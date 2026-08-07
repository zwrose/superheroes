"""Census: launcher slot-gate refusal tokens stay aligned with pilot-contract.md.

``_slot_reservation_gate`` and ``_GATE_REFUSAL_REASONS`` manually restate a small
refusal vocabulary; ``pilot-contract.md`` carries a third copy in the slot-grammar
table. This census derives gate tokens from ``launcher.py`` itself and requires
explicit adjudication of whether each is parallelism evidence.
"""
import ast
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import launcher  # noqa: E402

_LAUNCHER_PY = os.path.join(_LIB, "launcher.py")
_PILOT_CONTRACT = os.path.join(
    os.path.dirname(_LIB), "reference", "pilot-contract.md"
)

_SECTION_HEADING = "## The launch ledger's slot grammar"
_TOKEN_SUBSECTION_RE = re.compile(
    r"^### Slot-grammar refusal tokens$", re.MULTILINE
)
_TOKEN_TABLE_HEADER = "| Token | When returned |"

_GATE_TOKEN_PREFIXES = ("preflight-slot-", "post-reserve-")

# Per-token adjudication: True when returned only after parallel=True in the gate.
_ADJUDICATED = {
    "preflight-slot-reservation-required": True,
    "preflight-slot-calibration-unreadable": True,
    "post-reserve-ledger-unreadable": False,
}


def _load_contract():
    with open(_PILOT_CONTRACT, encoding="utf-8") as fh:
        return fh.read()


def _extract_section(doc, heading):
    lines = doc.splitlines()
    try:
        start = next(
            i for i, line in enumerate(lines) if line.strip() == heading
        )
    except StopIteration:
        return None
    level = len(heading) - len(heading.lstrip("#"))
    end = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line.startswith("#"):
            heading_level = len(line) - len(line.lstrip("#"))
            if heading_level <= level:
                end = i
                break
    return "\n".join(lines[start:end])


def _parse_markdown_table(doc, header_line):
    lines = doc.splitlines()
    try:
        start = lines.index(header_line)
    except ValueError:
        return None
    rows = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(tuple(cells))
    return rows


def _is_gate_token(token):
    return any(token.startswith(prefix) for prefix in _GATE_TOKEN_PREFIXES)


def _doc_gate_refusal_tokens(doc):
    section = _extract_section(doc, _SECTION_HEADING)
    if section is None:
        raise AssertionError(
            "pilot-contract.md missing section heading %s (file: %s)"
            % (_SECTION_HEADING, _PILOT_CONTRACT)
        )
    match = _TOKEN_SUBSECTION_RE.search(section)
    if match is None:
        return set()
    sub_section = section[match.start() :]
    rows = _parse_markdown_table(sub_section, _TOKEN_TABLE_HEADER)
    if rows is None:
        return set()
    tokens = set()
    for token_cell, _desc in rows:
        token = token_cell.strip("`")
        if not _is_gate_token(token):
            continue
        if token in tokens:
            raise ValueError(
                "duplicate gate token row in %s refusal table: %r (file: %s)"
                % (_SECTION_HEADING, token, _PILOT_CONTRACT)
            )
        tokens.add(token)
    return tokens


def _parse_launcher_source():
    with open(_LAUNCHER_PY, encoding="utf-8") as fh:
        source = fh.read()
    try:
        return ast.parse(source, filename=_LAUNCHER_PY), source
    except SyntaxError as exc:
        raise RuntimeError(
            "Census cannot parse %s: %s" % (_LAUNCHER_PY, exc)
        ) from exc


def _fail_reason_literals(func_node):
    tokens = set()
    for node in ast.walk(func_node):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == "_fail"):
            continue
        if not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            tokens.add(first.value)
    return tokens


def _gate_refusal_tokens_from_ast():
    tree, _source = _parse_launcher_source()
    gate_fn = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_slot_reservation_gate":
            gate_fn = node
            break
    if gate_fn is None:
        raise AssertionError("_slot_reservation_gate not found in launcher.py")
    return _fail_reason_literals(gate_fn)


def _parallelism_evidence_subset(adjudicated):
    return frozenset(
        token for token, is_evidence in adjudicated.items() if is_evidence
    )


def test_census_population_is_non_vacuous():
    # axis: a parse that silently found nothing would make every assertion below trivially true.
    derived = _gate_refusal_tokens_from_ast()
    doc_tokens = _doc_gate_refusal_tokens(_load_contract())
    assert derived, (
        "launcher.py AST census parsed to zero slot-gate refusal tokens"
    )
    assert doc_tokens, (
        "%s gate refusal table parsed to zero tokens (file: %s)"
        % (_SECTION_HEADING, _PILOT_CONTRACT)
    )


def test_gate_tokens_fully_adjudicated():
    # axis: a new gate token without explicit adjudication reddens.
    derived = _gate_refusal_tokens_from_ast()
    missing = derived - set(_ADJUDICATED)
    extra = set(_ADJUDICATED) - derived
    assert missing == set() and extra == set(), (
        "slot-gate token adjudication mismatch — derived but not adjudicated: %s; "
        "adjudicated but not in gate: %s"
        % (
            ", ".join(sorted(missing)) or "(none)",
            ", ".join(sorted(extra)) or "(none)",
        )
    )


def test_gate_refusal_reasons_match_parallelism_evidence():
    # axis: _GATE_REFUSAL_REASONS must equal exactly the adjudicated parallelism subset.
    expected = _parallelism_evidence_subset(_ADJUDICATED)
    assert launcher._GATE_REFUSAL_REASONS == expected, (
        "_GATE_REFUSAL_REASONS %s != adjudicated parallelism-evidence subset %s"
        % (sorted(launcher._GATE_REFUSAL_REASONS), sorted(expected))
    )


def test_gate_refusal_tokens_agree_with_contract():
    # axis: a gate token added to launcher.py without a doc row — or a stale doc row — reddens.
    doc = _load_contract()
    derived = _gate_refusal_tokens_from_ast()
    doc_tokens = _doc_gate_refusal_tokens(doc)
    missing_from_doc = derived - doc_tokens
    extra_in_doc = doc_tokens - derived
    assert missing_from_doc == set() and extra_in_doc == set(), (
        "pilot-contract.md slot-gate refusal tokens mismatch — in launcher but not doc: %s; "
        "in doc but not launcher: %s (file: %s)"
        % (
            ", ".join(sorted(missing_from_doc)) or "(none)",
            ", ".join(sorted(extra_in_doc)) or "(none)",
            _PILOT_CONTRACT,
        )
    )
