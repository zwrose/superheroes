"""Doc↔code census: artifact store and conformance contract matches pilot-contract.md."""
import glob
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
import pilot_conformance_declarations as pcd # noqa: E402
import pilot_conformance_runtime as pcr # noqa: E402

_CONFORMANCE_CENSUS_MODULES = (pc, pcc, pcr, pcd)

_PILOT_CONTRACT = os.path.join(
    os.path.dirname(_LIB), "reference", "pilot-contract.md"
)

_SECTION_ARTIFACT = "## The per-slot artifact store"
_SECTION_CONFORMANCE = "## The conformance run"
_SECTION_DECLARE_EXERCISE = "## Declare and exercise"
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


def _discovered_pilot_conformance_modules():
    paths = sorted(glob.glob(os.path.join(_LIB, "pilot_conformance*.py")))
    return {os.path.splitext(os.path.basename(path))[0] for path in paths}


def _conformance_census_module_names():
    return {module.__name__ for module in _CONFORMANCE_CENSUS_MODULES}


def _conformance_reason_constants():
    tokens = set()
    for module in _CONFORMANCE_CENSUS_MODULES:
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
    # pilot_conformance_declarations reuses a refusal token documented under
    # Declare and exercise, not the conformance token table.
    declarations_only = code_tokens & _reason_constants(pcd)
    cross_section = declarations_only - doc_tokens
    if cross_section:
        declare_section = _extract_section(doc, _SECTION_DECLARE_EXERCISE)
        assert declare_section is not None
        declare_doc_tokens = _parse_token_table(
            declare_section, _CONFORMANCE_TOKEN_HEADER
        )
        doc_tokens |= declare_doc_tokens & cross_section
    _assert_bidirectional_tokens(code_tokens, doc_tokens, "conformance REASON_*")


def test_conformance_census_modules_cover_all_siblings():
    """Every pilot_conformance*.py sibling must appear in the census module set."""
    discovered = _discovered_pilot_conformance_modules()
    declared = _conformance_census_module_names()
    missing_from_census = discovered - declared
    extra_in_census = declared - discovered
    assert missing_from_census == set() and extra_in_census == set(), (
        "conformance census module set mismatch — "
        "modules on disk not in census: %s; "
        "modules in census not on disk: %s"
        % (
            ", ".join(sorted(missing_from_census)) or "(none)",
            ", ".join(sorted(extra_in_census)) or "(none)",
        )
    )


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


def _surface_exercise_map_from_registrations():
    mapping = {}
    for fn in pc.default_exercises():
        exercise_name = fn.conformance_exercise
        for surface in fn.conformance_surfaces:
            mapping[surface] = exercise_name
    return mapping


def test_surface_exercise_table_matches_registrations():
    """bite-axis: doc surface table — must agree bidirectionally with default_exercises()."""
    doc = _load_contract()
    section = _extract_section(doc, _SECTION_CONFORMANCE)
    assert section is not None
    rows = _parse_markdown_table(section, _SURFACE_HEADER)
    assert rows is not None
    doc_map = {row[0].strip("`"): row[1].strip("`") for row in rows}
    code_map = _surface_exercise_map_from_registrations()
    missing_from_doc = set(code_map) - set(doc_map)
    extra_in_doc = set(doc_map) - set(code_map)
    mismatched = {
        surface for surface in code_map
        if surface in doc_map and doc_map[surface] != code_map[surface]
    }
    assert (
        missing_from_doc == set()
        and extra_in_doc == set()
        and mismatched == set()
    ), (
        "pilot-contract.md surface→exercise mismatch — missing from doc: %s; "
        "extra in doc: %s; value mismatch: %s (file: %s)"
        % (
            ", ".join(sorted(missing_from_doc)) or "(none)",
            ", ".join(sorted(extra_in_doc)) or "(none)",
            ", ".join(sorted(mismatched)) or "(none)",
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
