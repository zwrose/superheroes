"""Doc↔code census: artifact store and conformance contract matches pilot-contract.md."""
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_artifacts as pa # noqa: E402
import pilot_conformance as pc # noqa: E402
import pilot_conformance_cleanup as pcc # noqa: E402
import pilot_conformance_runtime as pcr # noqa: E402

_PILOT_CONTRACT = os.path.join(
    os.path.dirname(_LIB), "reference", "pilot-contract.md"
)

_SECTION_ARTIFACT = "## The per-slot artifact store"
_SECTION_CONFORMANCE = "## The conformance run"
_ARTIFACT_TOKEN_HEADER = "| Token | When returned |"
_CONFORMANCE_TOKEN_HEADER = "| Token | When returned |"
_CLASS_HEADER = "| Class | Default / opt-in | Redaction basis | Default retention (hours) |"
_SURFACE_HEADER = "| Surface | Exercise |"


def _load_contract():
    with open(_PILOT_CONTRACT, encoding="utf-8") as fh:
        return fh.read()


def _reason_constants(module):
    return {
        getattr(module, name)
        for name in dir(module)
        if name.startswith("REASON_")
        and isinstance(getattr(module, name), str)
    }


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


def _parse_token_table(doc, header_line):
    rows = _parse_markdown_table(doc, header_line)
    if rows is None:
        raise AssertionError(
            "token table header %r not found in pilot-contract.md (file: %s)"
            % (header_line, _PILOT_CONTRACT)
        )
    tokens = set()
    for token_cell, _desc in rows:
        token = token_cell.strip("`")
        if token in tokens:
            raise ValueError("duplicate token row in table %r: %r" % (header_line, token))
        tokens.add(token)
    return tokens


def _extract_section(doc, heading):
    lines = doc.splitlines()
    try:
        start = next(
            i for i, line in enumerate(lines) if line.strip() == heading
        )
    except StopIteration:
        return None
    level = len(heading) - len(heading.lstrip("#"))
    heading_re = re.compile(r"^#{1,6} ")
    end = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if heading_re.match(line):
            heading_level = len(line) - len(line.lstrip("#"))
            if heading_level <= level:
                end = i
                break
    return "\n".join(lines[start:end])


def _assert_bidirectional_tokens(code_tokens, doc_tokens, label):
    missing_from_doc = code_tokens - doc_tokens
    extra_in_doc = doc_tokens - code_tokens
    assert missing_from_doc == set() and extra_in_doc == set(), (
        "pilot-contract.md %s token mismatch — missing from doc: %s; in doc but not in code: %s (file: %s)"
        % (
            label,
            ", ".join(sorted(missing_from_doc)) or "(none)",
            ", ".join(sorted(extra_in_doc)) or "(none)",
            _PILOT_CONTRACT,
        )
    )


def _conformance_reason_constants():
    tokens = set()
    for module in (pc, pcr, pcc):
        tokens |= _reason_constants(module)
    return tokens


def test_artifact_reason_tokens_bidirectional():
    doc = _load_contract()
    section = _extract_section(doc, _SECTION_ARTIFACT)
    assert section is not None
    doc_tokens = _parse_token_table(section, _ARTIFACT_TOKEN_HEADER)
    code_tokens = _reason_constants(pa)
    _assert_bidirectional_tokens(code_tokens, doc_tokens, "pilot_artifacts REASON_*")


def test_conformance_reason_tokens_bidirectional():
    doc = _load_contract()
    section = _extract_section(doc, _SECTION_CONFORMANCE)
    assert section is not None
    doc_tokens = _parse_token_table(section, _CONFORMANCE_TOKEN_HEADER)
    code_tokens = _conformance_reason_constants()
    _assert_bidirectional_tokens(code_tokens, doc_tokens, "conformance REASON_*")


def test_required_surfaces_match_inventory_table():
    doc = _load_contract()
    section = _extract_section(doc, _SECTION_CONFORMANCE)
    assert section is not None
    rows = _parse_markdown_table(section, _SURFACE_HEADER)
    assert rows is not None
    doc_surfaces = {row[0].strip("`") for row in rows}
    code_surfaces = set(pc.REQUIRED_SURFACES)
    missing_from_doc = code_surfaces - doc_surfaces
    extra_in_doc = doc_surfaces - code_surfaces
    assert missing_from_doc == set() and extra_in_doc == set(), (
        "pilot-contract.md surface inventory mismatch — missing from doc: %s; in doc but not in code: %s (file: %s)"
        % (
            ", ".join(sorted(missing_from_doc)) or "(none)",
            ", ".join(sorted(extra_in_doc)) or "(none)",
            _PILOT_CONTRACT,
        )
    )


def test_artifact_class_table_matches_module():
    doc = _load_contract()
    section = _extract_section(doc, _SECTION_ARTIFACT)
    assert section is not None
    rows = _parse_markdown_table(section, _CLASS_HEADER)
    assert rows is not None
    doc_by_class = {}
    for class_cell, default_cell, basis_cell, hours_cell in rows:
        class_name = class_cell.strip("`")
        doc_by_class[class_name] = {
            "default": default_cell.strip().lower(),
            "basis": basis_cell.strip("`"),
            "hours": int(hours_cell.strip()),
        }
    code_classes = set(pa.CLASSES)
    assert set(doc_by_class) == code_classes, (
        "artifact class table membership mismatch — doc: %s; code: %s (file: %s)"
        % (sorted(doc_by_class), sorted(code_classes), _PILOT_CONTRACT)
    )
    for class_name in code_classes:
        doc_row = doc_by_class[class_name]
        expected_default = (
            "default" if class_name in pa.DEFAULT_CLASSES else "opt-in"
        )
        assert doc_row["default"] == expected_default, (
            "class %r default/opt-in mismatch in doc (file: %s)" % (class_name, _PILOT_CONTRACT)
        )
        assert doc_row["basis"] == pa.CLASS_BASIS[class_name], (
            "class %r basis mismatch in doc (file: %s)" % (class_name, _PILOT_CONTRACT)
        )
        assert doc_row["hours"] == pa.DEFAULT_RETENTION_HOURS[class_name], (
            "class %r retention hours mismatch in doc (file: %s)"
            % (class_name, _PILOT_CONTRACT)
        )
