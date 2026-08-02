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
_LIFECYCLE_TOKEN_HEADER = "| Token | When returned |"
_JOURNAL_TOKEN_HEADER = "| Token | When returned |"
_BLOCKER_TOKEN_HEADER = "| Token | When raised |"
_END_OUTCOME_HEADER = "| Outcome | Meaning |"
_REPLAY_STATE_HEADER = "| Replay state | Source |"


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


def _parse_token_table(doc, header_line):
    """Parse a two-column token table into a set of token strings from the first column."""
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
        if from_state in transitions:
            raise ValueError("duplicate transition row for from_state %r" % from_state)
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
        kind = kind_cell.strip("`")
        if kind in kinds:
            raise ValueError("duplicate effect-kind row for kind %r" % kind)
        kinds[kind] = scope_cell.strip("`")
    return kinds


def _parse_first_column_table(doc, header_line, duplicate_label):
    """Parse a markdown table's first column into a set, refusing duplicate rows."""
    rows = _parse_markdown_table(doc, header_line)
    if rows is None:
        raise AssertionError(
            "table header %r not found in pilot-contract.md (file: %s)"
            % (header_line, _PILOT_CONTRACT)
        )
    tokens = []
    for row in rows:
        token = row[0].strip("`")
        if token in tokens:
            raise ValueError(
                "duplicate %s row: %r" % (duplicate_label, token)
            )
        tokens.append(token)
    return set(tokens)


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


def _append_table_row(doc, header_line, row_line, after=None):
    """Append a row to the first markdown table matching header_line in doc text."""
    if after is not None:
        anchor_pos = doc.index(after)
        return doc[:anchor_pos] + _append_table_row(
            doc[anchor_pos:], header_line, row_line
        )
    lines = doc.splitlines()
    try:
        start = lines.index(header_line)
    except ValueError:
        raise AssertionError("header %r not found" % header_line)
    insert_at = start + 2
    for i in range(start + 2, len(lines)):
        if not lines[i].startswith("|"):
            insert_at = i
            break
        insert_at = i + 1
    new_lines = lines[:insert_at] + [row_line] + lines[insert_at:]
    return "\n".join(new_lines)


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


def test_lifecycle_reason_tokens_bidirectional():
    doc = _load_contract()
    lifecycle_section = doc.split("## The provisioning journal")[0]
    token_start = lifecycle_section.index("### Lifecycle refusal tokens")
    lifecycle_tokens_section = lifecycle_section[token_start:]
    doc_tokens = _parse_token_table(lifecycle_tokens_section, _LIFECYCLE_TOKEN_HEADER)
    code_tokens = _reason_constants(pilot_lifecycle)
    _assert_bidirectional_tokens(code_tokens, doc_tokens, "pilot_lifecycle REASON_*")


def test_journal_reason_tokens_bidirectional():
    doc = _load_contract()
    journal_section = doc.split("## The partial-failure report")[0]
    partial_start = journal_section.index("## The provisioning journal")
    journal_section = journal_section[partial_start:]
    token_start = journal_section.index("### Journal refusal tokens")
    journal_tokens_section = journal_section[token_start:]
    doc_tokens = _parse_token_table(journal_tokens_section, _JOURNAL_TOKEN_HEADER)
    code_tokens = _reason_constants(pilot_journal)
    _assert_bidirectional_tokens(code_tokens, doc_tokens, "pilot_journal REASON_*")


def test_block_tokens_bidirectional():
    doc = _load_contract()
    report_section = doc.split("## The partial-failure report")[1]
    token_start = report_section.index("### Blocker tokens")
    blocker_section = report_section[token_start:]
    doc_tokens = _parse_token_table(blocker_section, _BLOCKER_TOKEN_HEADER)
    code_tokens = _block_constants(pilot_journal)
    _assert_bidirectional_tokens(code_tokens, doc_tokens, "BLOCK_*")


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


def test_end_outcomes_bidirectional():
    doc = _load_contract()
    journal_section = doc.split("## The partial-failure report")[0]
    partial_start = journal_section.index("## The provisioning journal")
    journal_section = journal_section[partial_start:]
    doc_tokens = _parse_first_column_table(
        journal_section, _END_OUTCOME_HEADER, "end-outcome"
    )
    code_tokens = set(pilot_journal.END_OUTCOMES)
    _assert_bidirectional_tokens(code_tokens, doc_tokens, "END_OUTCOME")


def test_effect_states_bidirectional():
    doc = _load_contract()
    journal_section = doc.split("## The partial-failure report")[0]
    partial_start = journal_section.index("## The provisioning journal")
    journal_section = journal_section[partial_start:]
    doc_tokens = _parse_first_column_table(
        journal_section, _REPLAY_STATE_HEADER, "replay-state"
    )
    code_tokens = set(pilot_journal.EFFECT_STATES)
    _assert_bidirectional_tokens(code_tokens, doc_tokens, "EFFECT_STATE")


def test_provisioning_outcome_vocabulary_matches_slot_outcomes():
    lifecycle_outcomes = {
        pilot_lifecycle.provisioning_outcome(state)
        for state in pilot_lifecycle.SLOT_STATES
    }
    lifecycle_outcomes.discard(None)
    journal_outcomes = set(pilot_journal.SLOT_OUTCOMES)
    assert lifecycle_outcomes == journal_outcomes, (
        "provisioning_outcome vocabulary %r != SLOT_OUTCOMES %r"
        % (sorted(lifecycle_outcomes), sorted(journal_outcomes))
    )


def test_slot_outcomes_in_contract():
    doc = _load_contract()
    section = _extract_section(doc, "### Input shape per slot")
    assert section is not None, (
        "pilot-contract.md missing ### Input shape per slot (file: %s)"
        % _PILOT_CONTRACT
    )
    for outcome in sorted(pilot_journal.SLOT_OUTCOMES):
        assert outcome in section, (
            "pilot-contract.md input-shape section missing slot outcome %r (file: %s)"
            % (outcome, _PILOT_CONTRACT)
        )


def test_parse_transition_table_rejects_duplicate_row():
    table_text = (
        "| From state | Legal targets |\n"
        "|---|---|\n"
        "| `provisioning` | `failed` |\n"
        "| `provisioning` | `provisioned`, `failed` |\n"
    )
    with pytest.raises(ValueError, match="duplicate transition row"):
        _parse_transition_table(table_text)


def test_parse_effect_kind_table_rejects_duplicate_row():
    table_text = (
        "| Kind | Scope |\n"
        "|---|---|\n"
        "| `worktree-created` | `shared` |\n"
        "| `worktree-created` | `slot` |\n"
    )
    with pytest.raises(ValueError, match="duplicate effect-kind row"):
        _parse_effect_kind_table(table_text)


def test_parse_end_outcome_table_rejects_duplicate_row():
    table_text = (
        "| Outcome | Meaning |\n"
        "|---|---|\n"
        "| `applied` | probe |\n"
        "| `applied` | duplicate |\n"
    )
    with pytest.raises(ValueError, match="duplicate end-outcome row"):
        _parse_first_column_table(table_text, _END_OUTCOME_HEADER, "end-outcome")


def test_parse_replay_state_table_rejects_duplicate_row():
    table_text = (
        "| Replay state | Source |\n"
        "|---|---|\n"
        "| `applied` | probe |\n"
        "| `applied` | duplicate |\n"
    )
    with pytest.raises(ValueError, match="duplicate replay-state row"):
        _parse_first_column_table(table_text, _REPLAY_STATE_HEADER, "replay-state")


def test_slot_states_extra_in_doc(monkeypatch):
    doc = _load_contract()
    fake = "census-extra-state"
    assert fake not in doc
    modified = _append_table_row(
        doc,
        _TRANSITION_HEADER,
        "| `%s` | *(none)* |" % fake,
    )
    monkeypatch.setattr(
        sys.modules[__name__], "_load_contract", lambda: modified
    )
    with pytest.raises(AssertionError, match="unknown state"):
        test_slot_states_bidirectional()


def test_transitions_extra_in_doc(monkeypatch):
    doc = _load_contract()
    fake_dst = "census-extra-target"
    assert fake_dst not in doc
    modified = doc.replace(
        "| `provisioning` | `provisioned`, `failed` |",
        "| `provisioning` | `provisioned`, `failed`, `%s` |" % fake_dst,
    )
    monkeypatch.setattr(
        sys.modules[__name__], "_load_contract", lambda: modified
    )
    with pytest.raises(AssertionError, match="extra edge"):
        test_transitions_bidirectional()


def test_lifecycle_reason_tokens_extra_in_doc(monkeypatch):
    doc = _load_contract()
    fake = "slot-census-extra-probe"
    assert fake not in doc
    modified = _append_table_row(
        doc,
        _LIFECYCLE_TOKEN_HEADER,
        "| `%s` | probe extra |" % fake,
        after="### Lifecycle refusal tokens",
    )
    monkeypatch.setattr(
        sys.modules[__name__], "_load_contract", lambda: modified
    )
    with pytest.raises(AssertionError, match="in doc but not in code"):
        test_lifecycle_reason_tokens_bidirectional()


def test_journal_reason_tokens_extra_in_doc(monkeypatch):
    doc = _load_contract()
    fake = "journal-census-extra-probe"
    assert fake not in doc
    modified = _append_table_row(
        doc,
        _JOURNAL_TOKEN_HEADER,
        "| `%s` | probe extra |" % fake,
        after="### Journal refusal tokens",
    )
    monkeypatch.setattr(
        sys.modules[__name__], "_load_contract", lambda: modified
    )
    with pytest.raises(AssertionError, match="in doc but not in code"):
        test_journal_reason_tokens_bidirectional()


def test_block_tokens_extra_in_doc(monkeypatch):
    doc = _load_contract()
    fake = "report-census-extra-probe"
    assert fake not in doc
    modified = _append_table_row(
        doc,
        _BLOCKER_TOKEN_HEADER,
        "| `%s` | probe extra |" % fake,
    )
    monkeypatch.setattr(
        sys.modules[__name__], "_load_contract", lambda: modified
    )
    with pytest.raises(AssertionError, match="in doc but not in code"):
        test_block_tokens_bidirectional()


def test_effect_kinds_extra_in_doc(monkeypatch):
    doc = _load_contract()
    fake = "census-extra-effect-kind"
    assert fake not in doc
    modified = _append_table_row(
        doc,
        _EFFECT_KIND_HEADER,
        "| `%s` | `shared` |" % fake,
    )
    monkeypatch.setattr(
        sys.modules[__name__], "_load_contract", lambda: modified
    )
    with pytest.raises(AssertionError, match="unknown effect kind"):
        test_effect_kinds_bidirectional()


def test_end_outcomes_extra_in_doc(monkeypatch):
    doc = _load_contract()
    fake = "census-extra-outcome"
    assert fake not in doc
    modified = _append_table_row(
        doc,
        _END_OUTCOME_HEADER,
        "| `%s` | probe extra |" % fake,
    )
    monkeypatch.setattr(
        sys.modules[__name__], "_load_contract", lambda: modified
    )
    with pytest.raises(AssertionError, match="in doc but not in code"):
        test_end_outcomes_bidirectional()


def test_effect_states_extra_in_doc(monkeypatch):
    doc = _load_contract()
    fake = "census-extra-effect-state"
    assert fake not in doc
    modified = _append_table_row(
        doc,
        _REPLAY_STATE_HEADER,
        "| `%s` | probe extra |" % fake,
    )
    monkeypatch.setattr(
        sys.modules[__name__], "_load_contract", lambda: modified
    )
    with pytest.raises(AssertionError, match="in doc but not in code"):
        test_effect_states_bidirectional()


def test_slot_outcomes_missing_from_input_shape_section(monkeypatch):
    doc = _load_contract()
    section = _extract_section(doc, "### Input shape per slot")
    assert section is not None
    stripped = section
    for outcome in pilot_journal.SLOT_OUTCOMES:
        stripped = re.sub(r"\b%s\b" % re.escape(outcome), "REMOVED", stripped)
    modified = doc.replace(section, stripped)
    monkeypatch.setattr(
        sys.modules[__name__], "_load_contract", lambda: modified
    )
    with pytest.raises(AssertionError, match="provisioned|failed"):
        test_slot_outcomes_in_contract()


def test_census_red_on_undocumented_lifecycle_reason(monkeypatch):
    """Bite-proof: a REASON_* added in code but not in the doc must fail."""
    doc = _load_contract()
    fake = "slot-census-probe"
    assert fake not in doc
    monkeypatch.setattr(
        pilot_lifecycle, "REASON_CENSUS_PROBE", fake, raising=False
    )
    with pytest.raises(AssertionError, match="missing from doc.*slot-census-probe"):
        test_lifecycle_reason_tokens_bidirectional()


def test_census_red_on_undocumented_journal_reason(monkeypatch):
    """Bite-proof: a REASON_* added in pilot_journal but not in the doc must fail."""
    doc = _load_contract()
    fake = "journal-census-probe"
    assert fake not in doc
    monkeypatch.setattr(
        pilot_journal, "REASON_CENSUS_PROBE", fake, raising=False
    )
    with pytest.raises(AssertionError, match="missing from doc.*journal-census-probe"):
        test_journal_reason_tokens_bidirectional()


def test_census_red_on_undocumented_block_token(monkeypatch):
    """Bite-proof: a BLOCK_* added in code but not in the doc must fail."""
    doc = _load_contract()
    fake = "report-census-probe"
    assert fake not in doc
    monkeypatch.setattr(
        pilot_journal, "BLOCK_CENSUS_PROBE", fake, raising=False
    )
    with pytest.raises(AssertionError, match="missing from doc.*report-census-probe"):
        test_block_tokens_bidirectional()


def test_census_red_on_undocumented_effect_kind(monkeypatch):
    """Bite-proof: an effect kind added in code but not in the doc must fail."""
    doc = _load_contract()
    fake = "census-probe-effect"
    assert fake not in doc
    monkeypatch.setattr(
        pilot_journal, "KIND_CENSUS_PROBE", fake, raising=False
    )
    monkeypatch.setattr(
        pilot_journal,
        "EFFECT_KINDS",
        pilot_journal.EFFECT_KINDS | frozenset({fake}),
    )
    with pytest.raises(AssertionError, match="missing effect kind"):
        test_effect_kinds_bidirectional()


def test_census_red_on_undocumented_slot_state(monkeypatch):
    """Bite-proof: a slot state added in code but not in the doc must fail."""
    doc = _load_contract()
    fake = "census-probe-state"
    assert fake not in doc
    monkeypatch.setattr(
        pilot_lifecycle,
        "SLOT_STATES",
        pilot_lifecycle.SLOT_STATES | frozenset({fake}),
    )
    with pytest.raises(AssertionError, match="missing state"):
        test_slot_states_bidirectional()


def test_census_red_on_undocumented_transition_edge(monkeypatch):
    """Bite-proof: a transition edge added in code but not in the doc must fail."""
    doc = _load_contract()
    fake_dst = "census-probe-target"
    assert fake_dst not in doc
    new_transitions = dict(pilot_lifecycle.TRANSITIONS)
    new_transitions[pilot_lifecycle.STATE_PROVISIONED] = (
        new_transitions[pilot_lifecycle.STATE_PROVISIONED] | frozenset({fake_dst})
    )
    monkeypatch.setattr(pilot_lifecycle, "TRANSITIONS", new_transitions)
    with pytest.raises(AssertionError, match="missing edge"):
        test_transitions_bidirectional()
