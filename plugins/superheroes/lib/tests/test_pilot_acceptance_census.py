"""Census: pilot_acceptance framework rows and evidence pointers stay honest."""
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
_PLUGIN = os.path.realpath(os.path.join(_LIB, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_acceptance as pa  # noqa: E402
import pilot_boundary as pb  # noqa: E402
import pilot_conformance as pc  # noqa: E402
import pilot_conformance_declarations as pcd  # noqa: E402
import pilot_conformance_runtime as pcr  # noqa: E402
import pilot_provision as pp  # noqa: E402

_PILOT_CONTRACT = os.path.join(_PLUGIN, "reference", "pilot-contract.md")
_TEST_PILOT_INIT_SKILL = os.path.join(_PLUGIN, "skills", "test-pilot-init", "SKILL.md")
_CONFIGURE_SET_UP = os.path.join(
    _PLUGIN, "skills", "configure", "reference", "set-up.md"
)

_TOKEN_LITERAL_RE = re.compile(r"`([a-z][a-z0-9-]+)`")

_SECTION_TARGET_BOUNDARY = "## The target boundary"
_SECTION_DECLARE_EXERCISE = "## Declare and exercise"
_SECTION_PROVISIONING_GATE = "## The provisioning gate"
_SECTION_CONFORMANCE = "## The conformance run"
_SECTION_ACCEPTANCE = "## The acceptance matrix"

_RUNTIME_NEW_EXERCISE_TOKENS = frozenset({
    pcr.REASON_BOUNDARY_EXPECTATION_UNMET,
    pcr.REASON_HORIZON_EXPECTATION_UNMET,
    pcr.REASON_OWNERSHIP_PROBE_UNDECLARED,
    pcr.REASON_OWNERSHIP_PROBE_REFUSED,
    pcr.REASON_OWNERSHIP_PROBE_ANSWER_INVALID,
})

_EXPECTED_DECLARED_LIMITS = {
    "results-only-key-position": {
        "ruling": pa.RULING_OWNER_RULED,
        "claim": (
            "An account name shaped like a field name is not matched in dict-key position, "
            "so a producer keying a result dict by account name leaks that name past the guard. "
            "Value-position detection and all non-account material are unchanged."
        ),
        "closure_path": (
            "The schema-key-position exemption design (fourteen call sites), funded only if a "
            "project's threat model names key-position account-name leakage."
        ),
    },
    "sentinel-account-attestation": {
        "ruling": pa.RULING_OWNER_RULED,
        "claim": (
            "The framework verifies the sentinel account is absent from the mint allowlist but not "
            "that it names no real account; a real-but-not-mintable account satisfies every "
            "framework-side check."
        ),
        "closure_path": (
            "Project attestation; promote to an A1 schema field only if a project's threat model "
            "demands it."
        ),
    },
    "appctl-stop-pgid-reuse": {
        "ruling": pa.RULING_OWNER_RULED,
        "claim": (
            "Reaping releases the child pid, so signals sent after a successful reap address the "
            "process group by number rather than pinned identity; a pid recycled into a group leader "
            "between two adjacent syscalls would be mis-signalled."
        ),
        "closure_path": (
            "Platform-specific group-membership enumeration, funded only if a project's threat model "
            "names pid-wraparound races."
        ),
    },
    "bounded-run-clean-exit-containment": {
        "ruling": pa.RULING_OWNER_RULED,
        "claim": (
            "The shared runner signals the whole process group on every termination path, but a "
            "command that exits cleanly after detaching a helper never has its group signalled, so "
            "the helper survives."
        ),
        "closure_path": (
            "A containment-on-success semantics decision, funded only on field evidence: a real "
            "leaked helper observed reopens it."
        ),
    },
    "residue-scan-encoded-material": {
        "ruling": pa.RULING_PENDING_OWNER_RULING,
        "claim": (
            "A substring scan cannot catch base64, UTF-16, or percent-encoded material, so "
            "redaction is established only against plain-text residue of declared material."
        ),
        "closure_path": "Awaiting owner ruling.",
    },
    "screenshot-pixels-uninspectable": {
        "ruling": pa.RULING_PENDING_OWNER_RULING,
        "claim": (
            "The capture receipt binds bytes to a digest and checks format; nothing establishes "
            "that what was rendered carries no secret."
        ),
        "closure_path": "Awaiting owner ruling.",
    },
    "trace-retention-usually-refuses": {
        "ruling": pa.RULING_PENDING_OWNER_RULING,
        "claim": (
            "Any binary archive member refuses retention fail-closed, and real browser traces carry "
            "binary screencast frames, so the opt-in trace path exists and is exercised but rarely "
            "retains."
        ),
        "closure_path": "Awaiting owner ruling.",
    },
}


def _load_contract():
    with open(_PILOT_CONTRACT, encoding="utf-8") as fh:
        return fh.read()


def _read_skill(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _reason_constants(module):
    return {
        getattr(module, name)
        for name in dir(module)
        if name.startswith("REASON_")
        and isinstance(getattr(module, name), str)
    }


def _refusal_constants(module):
    return {
        getattr(module, name)
        for name in dir(module)
        if name.startswith("REFUSAL_")
        and isinstance(getattr(module, name), str)
    }


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


def _literal_tokens_in_text(text):
    return set(_TOKEN_LITERAL_RE.findall(text))


def _doc_tokens_in_sections(doc, headings, predicate):
    tokens = set()
    for heading in headings:
        section = _extract_section(doc, heading)
        assert section is not None, (
            "pilot-contract.md missing section heading %s (file: %s)"
            % (heading, _PILOT_CONTRACT)
        )
        tokens |= {t for t in _literal_tokens_in_text(section) if predicate(t)}
    return tokens


def _assert_bidirectional_tokens(code_tokens, doc_tokens, label):
    missing_from_doc = code_tokens - doc_tokens
    extra_in_doc = doc_tokens - code_tokens
    assert missing_from_doc == set() and extra_in_doc == set(), (
        "pilot-contract.md %s token mismatch — missing from doc: %s; "
        "in doc but not in code: %s (file: %s)"
        % (
            label,
            ", ".join(sorted(missing_from_doc)) or "(none)",
            ", ".join(sorted(extra_in_doc)) or "(none)",
            _PILOT_CONTRACT,
        )
    )


def _validate_population(label, code_tokens, doc_tokens):
    if not code_tokens:
        raise AssertionError(
            "%s yielded zero code tokens — census would pass vacuously" % label
        )
    if not doc_tokens:
        raise AssertionError(
            "pilot-contract.md %s parsed to zero doc tokens (file: %s)"
            % (label, _PILOT_CONTRACT)
        )


def _exercise_evidence_pointers():
    pointers = []
    for spec in pa.EXTRAPOLATION_POINTS:
        evidence = spec.get("evidence")
        if evidence is not None:
            pointers.append((spec["id"], evidence))
    for spec in pa.TRIPWIRE_ROWS:
        evidence = spec.get("evidence")
        if evidence is not None:
            pointers.append((spec["id"], evidence))
    return pointers


def _registered_exercise_names():
    return {fn.conformance_exercise for fn in pc.default_exercises()}


def test_framework_declared_limits_census_bidirectional():
    actual = {row["limit_id"]: row for row in pa.FRAMEWORK_DECLARED_LIMITS}
    assert set(actual) == set(_EXPECTED_DECLARED_LIMITS)
    assert len(actual) == len(_EXPECTED_DECLARED_LIMITS)
    for limit_id, expected in _EXPECTED_DECLARED_LIMITS.items():
        row = actual[limit_id]
        assert row["ruling"] == expected["ruling"]
        assert row["claim"] == expected["claim"]
        assert row["closure_path"] == expected["closure_path"]


@pytest.mark.parametrize("row_id,evidence", _exercise_evidence_pointers())
def test_evidence_pointer_surface_in_required_inventory(row_id, evidence):
    assert evidence["surface"] in pc.REQUIRED_SURFACES, (
        "%s cites unknown surface %s" % (row_id, evidence["surface"])
    )


@pytest.mark.parametrize("row_id,evidence", _exercise_evidence_pointers())
def test_evidence_pointer_exercise_in_default_registry(row_id, evidence):
    assert evidence["exercise"] in _registered_exercise_names(), (
        "%s cites unknown exercise %s" % (row_id, evidence["exercise"])
    )


def test_boundary_target_not_local_token_bidirectional():
    code_tokens = {pb.REFUSAL_TARGET_NOT_LOCAL}
    doc = _load_contract()
    doc_tokens = _doc_tokens_in_sections(
        doc,
        (_SECTION_TARGET_BOUNDARY,),
        lambda token: token == pb.REFUSAL_TARGET_NOT_LOCAL,
    )
    _validate_population("pilot_boundary.REFUSAL_TARGET_NOT_LOCAL", code_tokens, doc_tokens)
    _assert_bidirectional_tokens(
        code_tokens, doc_tokens, "pilot_boundary.REFUSAL_TARGET_NOT_LOCAL"
    )


def test_provision_account_class_tokens_bidirectional():
    code_tokens = {
        pp.REFUSAL_ACCOUNT_CLASS_UNDECLARED,
        pp.REFUSAL_ACCOUNT_CLASS_SPAN,
    }
    doc = _load_contract()
    doc_tokens = _doc_tokens_in_sections(
        doc,
        (_SECTION_DECLARE_EXERCISE, _SECTION_PROVISIONING_GATE),
        lambda token: token.startswith("provision-account-class-"),
    )
    _validate_population("pilot_provision account-class", code_tokens, doc_tokens)
    _assert_bidirectional_tokens(code_tokens, doc_tokens, "pilot_provision account-class")


def test_acceptance_reason_tokens_bidirectional():
    code_tokens = _reason_constants(pa)
    doc = _load_contract()
    doc_tokens = _doc_tokens_in_sections(
        doc,
        (_SECTION_ACCEPTANCE,),
        lambda token: token.startswith("acceptance-"),
    )
    _validate_population("pilot_acceptance REASON_*", code_tokens, doc_tokens)
    _assert_bidirectional_tokens(code_tokens, doc_tokens, "pilot_acceptance REASON_*")


def test_conformance_declaration_reason_tokens_bidirectional():
    code_tokens = _reason_constants(pcd)
    doc = _load_contract()
    doc_tokens = _doc_tokens_in_sections(
        doc,
        (_SECTION_CONFORMANCE,),
        lambda token: token.startswith("conformance-declaration-"),
    )
    doc_tokens |= _doc_tokens_in_sections(
        doc,
        (_SECTION_DECLARE_EXERCISE,),
        lambda token: token == pcd.REASON_DECLARATION_UNEXERCISED,
    )
    _validate_population(
        "pilot_conformance_declarations REASON_*", code_tokens, doc_tokens
    )
    _assert_bidirectional_tokens(
        code_tokens, doc_tokens, "pilot_conformance_declarations REASON_*"
    )


def test_runtime_new_exercise_tokens_bidirectional():
    code_tokens = set(_RUNTIME_NEW_EXERCISE_TOKENS)
    doc = _load_contract()
    doc_tokens = _doc_tokens_in_sections(
        doc,
        (_SECTION_CONFORMANCE,),
        lambda token: token in code_tokens,
    )
    _validate_population(
        "pilot_conformance_runtime new-exercise tokens", code_tokens, doc_tokens
    )
    _assert_bidirectional_tokens(
        code_tokens, doc_tokens, "pilot_conformance_runtime new-exercise tokens"
    )


@pytest.mark.parametrize(
    "label,path",
    (
        ("test-pilot-init/SKILL.md", _TEST_PILOT_INIT_SKILL),
        ("configure/reference/set-up.md", _CONFIGURE_SET_UP),
    ),
)
def test_configure_surfaces_invoke_pilot_acceptance_matrix(label, path):
    text = _read_skill(path)
    assert "pilot_acceptance.py" in text, (
        "%s must invoke pilot_acceptance.py for the acceptance matrix" % label
    )
    assert "matrix" in text, (
        "%s must invoke the acceptance-matrix subcommand" % label
    )


def test_census_red_code_to_doc_missing_boundary_token(monkeypatch):
    """Bite-proof: an undocumented module token must fail code→doc."""
    doc = _load_contract()
    fake = "boundary-census-probe"
    assert fake not in doc
    monkeypatch.setattr(pb, "REFUSAL_TARGET_NOT_LOCAL", fake, raising=False)
    code_tokens = {pb.REFUSAL_TARGET_NOT_LOCAL}
    doc_tokens = _doc_tokens_in_sections(
        doc,
        (_SECTION_TARGET_BOUNDARY,),
        lambda token: token == pb.REFUSAL_TARGET_NOT_LOCAL,
    )
    with pytest.raises(AssertionError, match="missing from doc.*boundary-census-probe"):
        _assert_bidirectional_tokens(
            code_tokens, doc_tokens, "pilot_boundary.REFUSAL_TARGET_NOT_LOCAL"
        )


def test_census_red_doc_to_code_fictitious_acceptance_token(monkeypatch):
    """Bite-proof: a fictitious documented token must fail doc→code."""
    doc = _load_contract()
    fake = "acceptance-census-fictitious-token"
    assert fake not in doc
    section = _extract_section(doc, _SECTION_ACCEPTANCE)
    assert section is not None
    modified = doc.replace(
        section,
        section + "\n| `%s` | probe extra |\n" % fake,
    )
    monkeypatch.setattr(
        sys.modules[__name__], "_load_contract", lambda: modified
    )
    with pytest.raises(AssertionError, match="in doc but not in code.*acceptance-census-fictitious-token"):
        test_acceptance_reason_tokens_bidirectional()
