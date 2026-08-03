"""Doc↔code census: pilot_appctl.py / pilot_wave.py contract matches pilot-contract.md."""
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_appctl as pa  # noqa: E402
import pilot_contract as pc  # noqa: E402
import pilot_wave as pw  # noqa: E402

_PILOT_CONTRACT = os.path.join(
    os.path.dirname(_LIB), "reference", "pilot-contract.md"
)

_SECTION_APP = "## Per-slot app lifecycle"
_SECTION_WAVE = "## Wave runtime — deadline and teardown"
_DECLARE_SECTION = "## Declare and exercise"

_APP_TOKEN_HEADER = "| Token | When returned |"
_WAVE_TOKEN_HEADER = "| Token | When returned |"
_INSTANCE_STATE_HEADER = "| State | Meaning |"
_PHASE_HEADER = "| Phase | Boundary | Admission |"
_STEP_HEADER = "| Step | Phase |"
_STATUS_HEADER = "| Status | Meaning |"
_INTENT_HEADER = "| Intent | Meaning |"
_DISPOSITION_HEADER = "| Disposition | When |"


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


def _prefix_constants(module, prefix):
    return {
        getattr(module, name)
        for name in dir(module)
        if name.startswith(prefix)
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


def _parse_first_column_table(doc, header_line, duplicate_label):
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


def _append_table_row(doc, header_line, row_line, after=None):
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


def _assert_bidirectional_vocab(code_vocab, doc_vocab, label):
    missing_from_doc = code_vocab - doc_vocab
    extra_in_doc = doc_vocab - code_vocab
    assert missing_from_doc == set() and extra_in_doc == set(), (
        "pilot-contract.md %s vocabulary mismatch — missing from doc: %s; in doc but not in code: %s (file: %s)"
        % (
            label,
            ", ".join(sorted(missing_from_doc)) or "(none)",
            ", ".join(sorted(extra_in_doc)) or "(none)",
            _PILOT_CONTRACT,
        )
    )


def test_b5_sections_in_contents():
    doc = _load_contract()
    contents_end = doc.find("\n---\n")
    assert contents_end != -1, "pilot-contract.md missing Contents separator"
    contents = doc[:contents_end]
    for heading in (_SECTION_APP, _SECTION_WAVE):
        assert heading in doc, "missing section %s (file: %s)" % (heading, _PILOT_CONTRACT)
        anchor = heading.lstrip("# ").lower().replace(" ", "-").replace("—", "-")
        assert anchor in contents.lower() or re.search(
            r"\[%s\]" % re.escape(heading.lstrip("# ")),
            contents,
            re.IGNORECASE,
        ), "Contents list missing entry for %s (file: %s)" % (heading, _PILOT_CONTRACT)


def test_appctl_reason_tokens_bidirectional():
    doc = _load_contract()
    section = _extract_section(doc, _SECTION_APP)
    assert section is not None
    doc_tokens = _parse_token_table(section, _APP_TOKEN_HEADER)
    code_tokens = _reason_constants(pa)
    _assert_bidirectional_tokens(code_tokens, doc_tokens, "pilot_appctl REASON_*")


def test_wave_reason_tokens_bidirectional():
    doc = _load_contract()
    section = _extract_section(doc, _SECTION_WAVE)
    assert section is not None
    doc_tokens = _parse_token_table(section, _WAVE_TOKEN_HEADER)
    code_tokens = _reason_constants(pw)
    _assert_bidirectional_tokens(code_tokens, doc_tokens, "pilot_wave REASON_*")


def test_instance_states_bidirectional():
    doc = _load_contract()
    section = _extract_section(doc, _SECTION_APP)
    assert section is not None
    doc_states = _parse_first_column_table(
        section, _INSTANCE_STATE_HEADER, "instance-state"
    )
    _assert_bidirectional_vocab(set(pa.INSTANCE_STATES), doc_states, "INSTANCE_STATES")


def test_wave_phases_bidirectional():
    doc = _load_contract()
    section = _extract_section(doc, _SECTION_WAVE)
    assert section is not None
    doc_phases = _parse_first_column_table(section, _PHASE_HEADER, "phase")
    code_phases = _prefix_constants(pw, "PHASE_")
    _assert_bidirectional_vocab(code_phases, doc_phases, "wave phase")


def test_wave_steps_bidirectional():
    doc = _load_contract()
    section = _extract_section(doc, _SECTION_WAVE)
    assert section is not None
    doc_steps = _parse_first_column_table(section, _STEP_HEADER, "step")
    code_steps = set(pw.STEP_ORDER)
    _assert_bidirectional_vocab(code_steps, doc_steps, "wave step")


def test_wave_statuses_bidirectional():
    doc = _load_contract()
    section = _extract_section(doc, _SECTION_WAVE)
    assert section is not None
    doc_statuses = _parse_first_column_table(section, _STATUS_HEADER, "status")
    code_statuses = _prefix_constants(pw, "STATUS_")
    _assert_bidirectional_vocab(code_statuses, doc_statuses, "wave status")


def test_wave_intents_bidirectional():
    doc = _load_contract()
    section = _extract_section(doc, _SECTION_WAVE)
    assert section is not None
    doc_intents = _parse_first_column_table(section, _INTENT_HEADER, "intent")
    code_intents = _prefix_constants(pw, "INTENT_")
    _assert_bidirectional_vocab(code_intents, doc_intents, "wave intent")


def test_wave_dispositions_bidirectional():
    doc = _load_contract()
    section = _extract_section(doc, _SECTION_WAVE)
    assert section is not None
    doc_dispositions = _parse_first_column_table(
        section, _DISPOSITION_HEADER, "disposition"
    )
    code_dispositions = _prefix_constants(pw, "DISPOSITION_")
    _assert_bidirectional_vocab(
        code_dispositions, doc_dispositions, "wave disposition"
    )


def test_retryable_reasons_strict_subset():
    all_reasons = _reason_constants(pa)
    assert pa.RETRYABLE_REASONS <= all_reasons
    assert pa.REASON_BIND_CONFLICT not in pa.RETRYABLE_REASONS


def test_step_order_fence_plus_destructive_disjoint():
    assert pw.STEP_ORDER == (
        pw.STEP_APP,
        pw.STEP_AUTOMATION,
        pw.STEP_CLEANUP,
        pw.STEP_RECLAIM,
    )
    assert pw.FENCE_STEPS == (pw.STEP_APP, pw.STEP_AUTOMATION)
    assert pw.DESTRUCTIVE_STEPS == (pw.STEP_CLEANUP, pw.STEP_RECLAIM)
    assert set(pw.FENCE_STEPS).isdisjoint(set(pw.DESTRUCTIVE_STEPS))


def test_retryable_reasons_reachable_in_appctl_source():
    import pathlib
    import re

    source = pathlib.Path(pa.__file__).read_text(encoding="utf-8")
    name_by_token = {
        getattr(pa, name): name
        for name in dir(pa)
        if name.startswith("REASON_") and isinstance(getattr(pa, name), str)
    }
    for token in pa.RETRYABLE_REASONS:
        const_name = name_by_token[token]
        assigned = re.search(
            r"readiness_reason\s*=\s*" + re.escape(const_name),
            source,
        )
        returned = re.search(
            r"return\s+_stand_up_failure\(\s*" + re.escape(const_name),
            source,
        )
        assert assigned or returned, (
            "%s is in RETRYABLE_REASONS but is not assigned to readiness_reason "
            "or returned from stand_up" % const_name
        )


def test_app_lifecycle_declaration_kind():
    assert "app-lifecycle" in pc.DECLARATION_KINDS
    doc = _load_contract()
    declare = _extract_section(doc, _DECLARE_SECTION)
    assert declare is not None
    assert "`app-lifecycle`" in declare or "app-lifecycle" in declare


def test_contract_missing_fails_loudly(tmp_path, monkeypatch):
    missing = tmp_path / "missing.md"
    monkeypatch.setattr(
        sys.modules[__name__], "_PILOT_CONTRACT", str(missing)
    )
    with pytest.raises(FileNotFoundError):
        _load_contract()


def test_census_red_on_undocumented_appctl_reason(monkeypatch):
    doc = _load_contract()
    fake = "app-census-probe"
    assert fake not in doc
    monkeypatch.setattr(pa, "REASON_CENSUS_PROBE", fake, raising=False)
    with pytest.raises(AssertionError, match="missing from doc.*app-census-probe"):
        test_appctl_reason_tokens_bidirectional()


def test_census_red_on_undocumented_wave_reason(monkeypatch):
    doc = _load_contract()
    fake = "wave-census-probe"
    assert fake not in doc
    monkeypatch.setattr(pw, "REASON_CENSUS_PROBE", fake, raising=False)
    with pytest.raises(AssertionError, match="missing from doc.*wave-census-probe"):
        test_wave_reason_tokens_bidirectional()


def test_census_red_on_unreachable_retryable_reason():
    import pathlib
    import re

    source = pathlib.Path(pa.__file__).read_text(encoding="utf-8")
    neutralized = source.replace(
        "readiness_reason = REASON_READINESS_TRANSPORT_ERROR",
        "readiness_reason = REASON_READINESS_TIMEOUT",
    )
    name_by_token = {
        getattr(pa, name): name
        for name in dir(pa)
        if name.startswith("REASON_") and isinstance(getattr(pa, name), str)
    }
    missing = []
    for token in pa.RETRYABLE_REASONS:
        const_name = name_by_token[token]
        assigned = re.search(
            r"readiness_reason\s*=\s*" + re.escape(const_name),
            neutralized,
        )
        returned = re.search(
            r"return\s+_stand_up_failure\(\s*" + re.escape(const_name),
            neutralized,
        )
        if not (assigned or returned):
            missing.append(const_name)
    assert missing == ["REASON_READINESS_TRANSPORT_ERROR"]


def test_census_red_on_bind_conflict_in_retryable(monkeypatch):
    monkeypatch.setattr(
        pa,
        "RETRYABLE_REASONS",
        pa.RETRYABLE_REASONS | frozenset({pa.REASON_BIND_CONFLICT}),
    )
    with pytest.raises(AssertionError):
        test_retryable_reasons_strict_subset()


def test_census_red_on_doc_only_wave_token(monkeypatch):
    doc = _load_contract()
    fake = "wave-census-extra-probe"
    assert fake not in doc
    section = _extract_section(doc, _SECTION_WAVE)
    modified = _append_table_row(
        section,
        _WAVE_TOKEN_HEADER,
        "| `%s` | probe extra |" % fake,
    )
    full = doc.replace(section, modified)
    monkeypatch.setattr(sys.modules[__name__], "_load_contract", lambda: full)
    with pytest.raises(AssertionError, match="in doc but not in code"):
        test_wave_reason_tokens_bidirectional()
