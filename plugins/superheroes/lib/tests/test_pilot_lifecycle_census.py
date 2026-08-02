"""Doc↔code census: pilot lifecycle and journal contract matches pilot_lifecycle.py / pilot_journal.py."""
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_journal  # noqa: E402
import pilot_lifecycle  # noqa: E402

_PILOT_CONTRACT = os.path.join(
    os.path.dirname(_LIB), "reference", "pilot-contract.md"
)

_NEW_SECTIONS = (
    "## Slot lifecycle and generations",
    "## The provisioning journal",
    "## The partial-failure report",
)

_TRANSITION_HEADER = "| From state | Legal targets |"
_EFFECT_KIND_HEADER = "| Kind | Scope |"


def _load_contract():
    with open(_PILOT_CONTRACT, encoding="utf-8") as fh:
        return fh.read()


def _reason_constants(module):
    """Discover REASON_* string constants via dir(module)."""
    return {
        getattr(module, name)
        for name in dir(module)
        if name.startswith("REASON_")
        and isinstance(getattr(module, name), str)
    }


def _block_constants(module):
    """Discover BLOCK_* string constants via dir(module)."""
    return {
        getattr(module, name)
        for name in dir(module)
        if name.startswith("BLOCK_")
        and isinstance(getattr(module, name), str)
    }


def _parse_markdown_table(doc, header_line):
    """Return list of row tuples (cell, cell, ...) for a markdown table after header_line."""
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


def _parse_transition_table(doc):
    """Parse the lifecycle transition table into {from_state: frozenset(to_states)}."""
    rows = _parse_markdown_table(doc, _TRANSITION_HEADER)
    if rows is None:
        raise AssertionError(
            "transition table header not found in pilot-contract.md (file: %s)"
            % _PILOT_CONTRACT
        )
    transitions = {}
    all_states = set()
    for from_cell, targets_cell in rows:
        from_state = from_cell.strip("`")
        all_states.add(from_state)
        if targets_cell.strip() in ("*(none)*", "(none)", "—", ""):
            transitions[from_state] = frozenset()
            continue
        targets = set()
        for part in targets_cell.split(","):
            token = part.strip().strip("`").strip()
            if not token:
                continue
            targets.add(token)
            all_states.add(token)
        transitions[from_state] = frozenset(targets)
    return transitions, all_states


def _parse_effect_kind_table(doc):
    """Parse effect-kind table into {kind: scope}."""
    rows = _parse_markdown_table(doc, _EFFECT_KIND_HEADER)
    if rows is None:
        raise AssertionError(
            "effect-kind table header not found in pilot-contract.md (file: %s)"
            % _PILOT_CONTRACT
        )
    kinds = {}
    for kind_cell, scope_cell in rows:
        kinds[kind_cell.strip("`")] = scope_cell.strip("`")
    return kinds


def test_new_sections_in_contents():
    doc = _load_contract()
    contents_end = doc.find("\n---\n")
    assert contents_end != -1, "pilot-contract.md missing Contents separator"
    contents = doc[:contents_end]
    for heading in _NEW_SECTIONS:
        assert heading in doc, "missing section %s (file: %s)" % (heading, _PILOT_CONTRACT)
        anchor = heading.lstrip("# ").lower().replace(" ", "-")
        assert anchor in contents.lower() or re.search(
            r"\[%s\]" % re.escape(heading.lstrip("# ")),
            contents,
            re.IGNORECASE,
        ), "Contents list missing entry for %s (file: %s)" % (heading, _PILOT_CONTRACT)


def test_slot_states_bidirectional():
    doc = _load_contract()
    _, table_states = _parse_transition_table(doc)
    code_states = set(pilot_lifecycle.SLOT_STATES)
    missing_from_doc = code_states - table_states
    assert missing_from_doc == set(), (
        "pilot-contract.md transition table missing state(s): %s (file: %s)"
        % (", ".join(sorted(missing_from_doc)), _PILOT_CONTRACT)
    )
    extra_in_doc = table_states - code_states
    assert extra_in_doc == set(), (
        "pilot-contract.md transition table names unknown state(s): %s (file: %s)"
        % (", ".join(sorted(extra_in_doc)), _PILOT_CONTRACT)
    )


def test_transitions_bidirectional():
    doc = _load_contract()
    doc_transitions, _ = _parse_transition_table(doc)
    code_transitions = {
        src: set(dsts) for src, dsts in pilot_lifecycle.TRANSITIONS.items()
    }
    missing_edges = []
    for src, dsts in code_transitions.items():
        doc_dsts = doc_transitions.get(src)
        if doc_dsts is None:
            missing_edges.append("%s → (row missing)" % src)
            continue
        for dst in sorted(dsts - set(doc_dsts)):
            missing_edges.append("%s → %s" % (src, dst))
    extra_edges = []
    for src, doc_dsts in doc_transitions.items():
        code_dsts = code_transitions.get(src, set())
        for dst in sorted(set(doc_dsts) - code_dsts):
            extra_edges.append("%s → %s" % (src, dst))
    assert missing_edges == [], (
        "pilot-contract.md transition table missing edge(s): %s (file: %s)"
        % (", ".join(missing_edges), _PILOT_CONTRACT)
    )
    assert extra_edges == [], (
        "pilot-contract.md transition table has extra edge(s): %s (file: %s)"
        % (", ".join(extra_edges), _PILOT_CONTRACT)
    )


def test_lifecycle_reason_tokens_in_contract():
    doc = _load_contract()
    tokens = _reason_constants(pilot_lifecycle)
    missing = [t for t in sorted(tokens) if t not in doc]
    assert missing == [], (
        "pilot-contract.md missing pilot_lifecycle REASON_* token(s): %s (file: %s)"
        % (", ".join(missing), _PILOT_CONTRACT)
    )


def test_journal_reason_tokens_in_contract():
    doc = _load_contract()
    tokens = _reason_constants(pilot_journal)
    missing = [t for t in sorted(tokens) if t not in doc]
    assert missing == [], (
        "pilot-contract.md missing pilot_journal REASON_* token(s): %s (file: %s)"
        % (", ".join(missing), _PILOT_CONTRACT)
    )


def test_block_tokens_in_contract():
    doc = _load_contract()
    tokens = _block_constants(pilot_journal)
    missing = [t for t in sorted(tokens) if t not in doc]
    assert missing == [], (
        "pilot-contract.md missing BLOCK_* token(s): %s (file: %s)"
        % (", ".join(missing), _PILOT_CONTRACT)
    )


def test_effect_kinds_bidirectional():
    doc = _load_contract()
    doc_kinds = set(_parse_effect_kind_table(doc))
    code_kinds = set(pilot_journal.EFFECT_KINDS)
    missing = code_kinds - doc_kinds
    assert missing == set(), (
        "pilot-contract.md missing effect kind(s): %s (file: %s)"
        % (", ".join(sorted(missing)), _PILOT_CONTRACT)
    )
    extra = doc_kinds - code_kinds
    assert extra == set(), (
        "pilot-contract.md names unknown effect kind(s): %s (file: %s)"
        % (", ".join(sorted(extra)), _PILOT_CONTRACT)
    )


def test_effect_scope_matches_code():
    assert set(pilot_journal.EFFECT_SCOPE) == pilot_journal.EFFECT_KINDS
    doc = _load_contract()
    doc_scopes = _parse_effect_kind_table(doc)
    mismatches = []
    for kind in sorted(pilot_journal.EFFECT_KINDS):
        expected = pilot_journal.EFFECT_SCOPE[kind]
        actual = doc_scopes.get(kind)
        if actual != expected:
            mismatches.append("%s: doc=%r code=%r" % (kind, actual, expected))
    assert mismatches == [], (
        "pilot-contract.md effect scope mismatch: %s (file: %s)"
        % ("; ".join(mismatches), _PILOT_CONTRACT)
    )


def test_end_outcomes_and_effect_states_in_contract():
    doc = _load_contract()
    for token in sorted(pilot_journal.END_OUTCOMES):
        assert token in doc, (
            "pilot-contract.md missing END_OUTCOME %r (file: %s)"
            % (token, _PILOT_CONTRACT)
        )
    for token in sorted(pilot_journal.EFFECT_STATES):
        assert token in doc, (
            "pilot-contract.md missing EFFECT_STATE %r (file: %s)"
            % (token, _PILOT_CONTRACT)
        )


def test_census_red_on_undocumented_lifecycle_reason(monkeypatch):
    """Bite-proof axis: a REASON_* added in code but not in the doc must fail."""
    doc = _load_contract()
    tokens = _reason_constants(pilot_lifecycle)
    fake = "slot-reason-census-probe-undocumented"
    assert fake not in tokens
    assert fake not in doc
    augmented = tokens | {fake}
    monkeypatch.setattr(
        "test_pilot_lifecycle_census._reason_constants",
        lambda module: augmented if module is pilot_lifecycle else _reason_constants(module),
    )
    with pytest.raises(AssertionError, match=fake):
        test_lifecycle_reason_tokens_in_contract()
