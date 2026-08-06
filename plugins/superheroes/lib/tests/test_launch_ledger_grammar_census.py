"""Census: pilot-contract.md's launch-ledger slot grammar matches launch_ledger.py (#830).

`pilot-contract.md` manually restates `_BOUNDARY_RECORD_KEYS` and the boundary refusal
vocabulary owned by `launch_ledger.py`. Nothing reads that section today — the two sides
are in sync, but a prior fix batch added six refusal tokens and the doc had to be caught
up by hand. This census is told nothing: it derives both sides and requires them to agree.

Coverage limit: every boundary refusal token in `launch_ledger.py` is a written string
literal today (`grep` over `fold-bad-field:reserved:boundary` shows only `return "…"`
sites, no concatenation). A token built by string concatenation rather than written as a
literal would be invisible to this source-parsing census.
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

import launch_ledger  # noqa: E402

_PILOT_CONTRACT = os.path.join(
    os.path.dirname(_LIB), "reference", "pilot-contract.md"
)
_LAUNCH_LEDGER_PY = os.path.join(_LIB, "launch_ledger.py")

_SECTION_HEADING = "## The launch ledger's slot grammar"
_TOKEN_SUBSECTION_RE = re.compile(
    r"^### Slot-grammar refusal tokens$", re.MULTILINE
)
_FIELD_TABLE_HEADER = "| Field | Type | Nullable |"
_TOKEN_TABLE_HEADER = "| Token | When returned |"

_BOUNDARY_TOKEN_RE = re.compile(
    r"^(?:fold-bad-field:reserved:boundary|ledger-boundary-)"
)


def _load_contract():
    with open(_PILOT_CONTRACT, encoding="utf-8") as fh:
        return fh.read()


def _extract_section(doc, heading):
    """Return text from heading through the next heading of equal or higher level."""
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
    """Return list of row tuples for a markdown table after header_line."""
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


def _module_boundary_keys():
    return set(launch_ledger._BOUNDARY_RECORD_KEYS)


def _parse_field_table(doc):
    section = _extract_section(doc, _SECTION_HEADING)
    if section is None:
        raise AssertionError(
            "pilot-contract.md missing section heading %s (file: %s)"
            % (_SECTION_HEADING, _PILOT_CONTRACT)
        )
    rows = _parse_markdown_table(section, _FIELD_TABLE_HEADER)
    if rows is None:
        raise AssertionError(
            "field table header %r not found in %s (file: %s)"
            % (_FIELD_TABLE_HEADER, _SECTION_HEADING, _PILOT_CONTRACT)
        )
    keys = set()
    for field_cell, *_rest in rows:
        key = field_cell.strip("`")
        if not key:
            raise ValueError(
                "empty field key in %s field table (file: %s)"
                % (_SECTION_HEADING, _PILOT_CONTRACT)
            )
        if key in keys:
            raise ValueError(
                "duplicate field key in %s field table: %r (file: %s)"
                % (_SECTION_HEADING, key, _PILOT_CONTRACT)
            )
        keys.add(key)
    return keys


def _doc_refusal_tokens(doc):
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
        if token in tokens:
            raise ValueError(
                "duplicate token row in %s refusal table: %r (file: %s)"
                % (_SECTION_HEADING, token, _PILOT_CONTRACT)
            )
        if _BOUNDARY_TOKEN_RE.match(token):
            tokens.add(token)
    return tokens


def _parse_launch_ledger_source():
    with open(_LAUNCH_LEDGER_PY, encoding="utf-8") as fh:
        source = fh.read()
    try:
        return ast.parse(source, filename=_LAUNCH_LEDGER_PY), source
    except SyntaxError as exc:
        raise RuntimeError(
            "Census cannot parse %s: %s" % (_LAUNCH_LEDGER_PY, exc)
        ) from exc


def _code_refusal_tokens():
    tree, _source = _parse_launch_ledger_source()
    tokens = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant):
            continue
        if not isinstance(node.value, str):
            continue
        if _BOUNDARY_TOKEN_RE.match(node.value):
            tokens.add(node.value)
    return tokens


def _assert_bidirectional_sets(code_set, doc_set, label, key_label):
    missing_from_doc = code_set - doc_set
    extra_in_doc = doc_set - code_set
    assert missing_from_doc == set() and extra_in_doc == set(), (
        "pilot-contract.md %s %s mismatch — in module but not doc: %s; "
        "in doc but not module: %s (file: %s)"
        % (
            label,
            key_label,
            ", ".join(sorted(missing_from_doc)) or "(none)",
            ", ".join(sorted(extra_in_doc)) or "(none)",
            _PILOT_CONTRACT,
        )
    )


def test_census_population_is_non_vacuous():
    # axis: a parse that silently found nothing would make every assertion below trivially true.
    doc = _load_contract()
    module_keys = _module_boundary_keys()
    doc_keys = _parse_field_table(doc)
    code_tokens = _code_refusal_tokens()
    doc_tokens = _doc_refusal_tokens(doc)
    assert module_keys, (
        "launch_ledger._BOUNDARY_RECORD_KEYS parsed to zero keys"
    )
    assert doc_keys, (
        "%s field table parsed to zero keys (file: %s)"
        % (_SECTION_HEADING, _PILOT_CONTRACT)
    )
    assert code_tokens, (
        "launch_ledger.py AST census parsed to zero boundary refusal tokens"
    )
    assert doc_tokens, (
        "%s refusal table parsed to zero boundary tokens (file: %s)"
        % (_SECTION_HEADING, _PILOT_CONTRACT)
    )


def test_boundary_field_keys_agree():
    # axis: a key added to _BOUNDARY_RECORD_KEYS without a doc row — or a doc row with no
    # module key — reddens.
    doc = _load_contract()
    module_keys = _module_boundary_keys()
    doc_keys = _parse_field_table(doc)
    assert module_keys, (
        "launch_ledger._BOUNDARY_RECORD_KEYS parsed to zero keys"
    )
    assert doc_keys, (
        "%s field table parsed to zero keys (file: %s)"
        % (_SECTION_HEADING, _PILOT_CONTRACT)
    )
    _assert_bidirectional_sets(
        module_keys, doc_keys, _SECTION_HEADING, "field keys"
    )


def test_boundary_refusal_tokens_agree():
    # axis: a refusal literal added to launch_ledger.py without a doc row — or a doc row with
    # no module literal — reddens.
    doc = _load_contract()
    code_tokens = _code_refusal_tokens()
    doc_tokens = _doc_refusal_tokens(doc)
    assert code_tokens, (
        "launch_ledger.py AST census parsed to zero boundary refusal tokens"
    )
    assert doc_tokens, (
        "%s refusal table parsed to zero boundary tokens (file: %s)"
        % (_SECTION_HEADING, _PILOT_CONTRACT)
    )
    _assert_bidirectional_sets(
        code_tokens, doc_tokens, _SECTION_HEADING, "refusal tokens"
    )
