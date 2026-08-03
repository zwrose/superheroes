"""Doc↔code census: B6 auth modules match pilot-contract.md sections 18–21."""
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_horizon  # noqa: E402
import pilot_identity  # noqa: E402
import pilot_mint  # noqa: E402

_PILOT_CONTRACT = os.path.join(
    os.path.dirname(_LIB), "reference", "pilot-contract.md"
)

_NEW_SECTIONS = (
    "## The identity-probe exercise",
    "## Mid-wave lapse",
    "## Credential validity margin",
    "## Minted sign-in exercises",
)

_TOKEN_HEADER = "| Token | When returned |"

_IDENTITY_PROBE_TOKEN_SUBHEADER = "### Identity-probe refusal tokens"
_LAPSE_TOKEN_SUBHEADER = "### Lapse refusal tokens"
_HORIZON_TOKEN_SUBHEADER = "### Horizon refusal tokens"
_MINT_TOKEN_SUBHEADER = "### Mint exercise refusal tokens"

_MODULE_CONFIG = (
    {
        "label": "pilot_identity",
        "module": pilot_identity,
        "sections": (
            {
                "heading": _NEW_SECTIONS[0],
                "token_subheader": _IDENTITY_PROBE_TOKEN_SUBHEADER,
            },
            {
                "heading": _NEW_SECTIONS[1],
                "token_subheader": _LAPSE_TOKEN_SUBHEADER,
            },
        ),
    },
    {
        "label": "pilot_horizon",
        "module": pilot_horizon,
        "sections": (
            {
                "heading": _NEW_SECTIONS[2],
                "token_subheader": _HORIZON_TOKEN_SUBHEADER,
            },
        ),
    },
    {
        "label": "pilot_mint",
        "module": pilot_mint,
        "sections": (
            {
                "heading": _NEW_SECTIONS[3],
                "token_subheader": _MINT_TOKEN_SUBHEADER,
            },
        ),
    },
)


def _load_contract():
    with open(_PILOT_CONTRACT, encoding="utf-8") as fh:
        return fh.read()


def _refusal_constants(module):
    """Discover REFUSAL_* string constants via dir(module)."""
    return {
        getattr(module, name)
        for name in dir(module)
        if name.startswith("REFUSAL_")
        and isinstance(getattr(module, name), str)
    }


def _action_constants(module):
    """Discover ACTION_* string constants via dir(module)."""
    return {
        getattr(module, name)
        for name in dir(module)
        if name.startswith("ACTION_")
        and isinstance(getattr(module, name), str)
    }


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


def _parse_token_table(doc, header_line):
    """Parse a two-column token table into a set of token strings."""
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
            raise ValueError(
                "duplicate token row in table %r: %r" % (header_line, token)
            )
        tokens.add(token)
    return tokens


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


def _section_doc_tokens(doc, heading, subheader):
    section = _extract_section(doc, heading)
    if section is None:
        raise AssertionError(
            "pilot-contract.md missing section heading %s (file: %s)"
            % (heading, _PILOT_CONTRACT)
        )
    if subheader not in section:
        raise AssertionError(
            "pilot-contract.md section %s missing %s (file: %s)"
            % (heading, subheader, _PILOT_CONTRACT)
        )
    sub_start = section.index(subheader)
    sub_section = section[sub_start:]
    return _parse_token_table(sub_section, _TOKEN_HEADER)


def _module_doc_tokens(doc, config):
    """Union token tables from every section in a module config."""
    tokens = set()
    for section_cfg in config["sections"]:
        tokens |= _section_doc_tokens(
            doc, section_cfg["heading"], section_cfg["token_subheader"],
        )
    return tokens


def _section_code_tokens(module, subheader):
    """Map each token subheader to the REFUSAL_* constants in that section."""
    if subheader == _IDENTITY_PROBE_TOKEN_SUBHEADER:
        lapse_tokens = {
            pilot_identity.REFUSAL_LAPSE_SIGN_IN_PATH_INVALID,
            pilot_identity.REFUSAL_LAPSE_REPROBE_BUDGET_INVALID,
            pilot_identity.REFUSAL_LAPSE_PROBE_NOT_CALLABLE,
            pilot_identity.REFUSAL_LAPSE_REMINT_UNAVAILABLE,
            pilot_identity.REFUSAL_LAPSE_REMINT_FAILED,
        }
        return _refusal_constants(module) - lapse_tokens
    if subheader == _LAPSE_TOKEN_SUBHEADER:
        return {
            pilot_identity.REFUSAL_LAPSE_SIGN_IN_PATH_INVALID,
            pilot_identity.REFUSAL_LAPSE_REPROBE_BUDGET_INVALID,
            pilot_identity.REFUSAL_LAPSE_PROBE_NOT_CALLABLE,
            pilot_identity.REFUSAL_LAPSE_REMINT_UNAVAILABLE,
            pilot_identity.REFUSAL_LAPSE_REMINT_FAILED,
        }
    if subheader in (_HORIZON_TOKEN_SUBHEADER, _MINT_TOKEN_SUBHEADER):
        return _refusal_constants(module)
    raise AssertionError("unknown token subheader %r" % subheader)


def _validate_population(config, code_tokens, doc_tokens):
    """Fail loudly when heading, table, or module population collapses."""
    doc = _load_contract()
    for section_cfg in config["sections"]:
        if _extract_section(doc, section_cfg["heading"]) is None:
            raise AssertionError(
                "pilot-contract.md missing section heading %s (file: %s)"
                % (section_cfg["heading"], _PILOT_CONTRACT)
            )
    if not code_tokens:
        raise AssertionError(
            "%s yielded zero REFUSAL_* constants — census would pass vacuously"
            % config["label"]
        )
    if not doc_tokens:
        raise AssertionError(
            "pilot-contract.md token tables for %s parsed to zero rows (file: %s)"
            % (config["label"], _PILOT_CONTRACT)
        )


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


def _remove_table_row(doc, token):
    """Remove the table row whose first cell contains token."""
    pattern = re.compile(
        r"^\| `%s` \|.*\n" % re.escape(token), re.MULTILINE
    )
    new_doc, count = pattern.subn("", doc, count=1)
    if count != 1:
        raise AssertionError("token row %r not found for removal" % token)
    return new_doc


@pytest.mark.parametrize("config", _MODULE_CONFIG, ids=lambda c: c["label"])
def test_module_tokens_code_to_doc(config):
    doc = _load_contract()
    code_tokens = _refusal_constants(config["module"])
    doc_tokens = _module_doc_tokens(doc, config)
    _validate_population(config, code_tokens, doc_tokens)
    for section_cfg in config["sections"]:
        section_doc = _section_doc_tokens(
            doc, section_cfg["heading"], section_cfg["token_subheader"],
        )
        assert section_doc, (
            "%s section %s parsed to zero doc tokens (file: %s)"
            % (config["label"], section_cfg["heading"], _PILOT_CONTRACT)
        )
        section_code = _section_code_tokens(
            config["module"], section_cfg["token_subheader"],
        )
        assert section_code, (
            "%s section %s yielded zero code tokens"
            % (config["label"], section_cfg["token_subheader"])
        )
        _assert_bidirectional_tokens(
            section_code,
            section_doc,
            "%s/%s" % (config["label"], section_cfg["token_subheader"]),
        )


@pytest.mark.parametrize("config", _MODULE_CONFIG, ids=lambda c: c["label"])
def test_module_tokens_doc_to_code(config):
    doc = _load_contract()
    code_tokens = _refusal_constants(config["module"])
    doc_tokens = _module_doc_tokens(doc, config)
    _validate_population(config, code_tokens, doc_tokens)
    for section_cfg in config["sections"]:
        section_doc = _section_doc_tokens(
            doc, section_cfg["heading"], section_cfg["token_subheader"],
        )
        section_code = _section_code_tokens(
            config["module"], section_cfg["token_subheader"],
        )
        _assert_bidirectional_tokens(
            section_code,
            section_doc,
            "%s/%s" % (config["label"], section_cfg["token_subheader"]),
        )


@pytest.mark.parametrize("config", _MODULE_CONFIG, ids=lambda c: c["label"])
def test_module_token_population_non_vacuous(config):
    doc = _load_contract()
    code_tokens = _refusal_constants(config["module"])
    doc_tokens = _module_doc_tokens(doc, config)
    _validate_population(config, code_tokens, doc_tokens)


def test_new_sections_in_contents():
    doc = _load_contract()
    contents_end = doc.find("\n---\n")
    assert contents_end != -1, "pilot-contract.md missing Contents separator"
    contents = doc[:contents_end]
    for heading in _NEW_SECTIONS:
        assert heading in doc, (
            "missing section %s (file: %s)" % (heading, _PILOT_CONTRACT)
        )
        anchor = heading.lstrip("# ").lower().replace(" ", "-")
        assert anchor in contents.lower() or re.search(
            r"\[%s\]" % re.escape(heading.lstrip("# ")),
            contents,
            re.IGNORECASE,
        ), "Contents list missing entry for %s (file: %s)" % (
            heading,
            _PILOT_CONTRACT,
        )


def test_identity_actions_in_lapse_section():
    doc = _load_contract()
    section = _extract_section(doc, "## Mid-wave lapse")
    assert section is not None, (
        "pilot-contract.md missing ## Mid-wave lapse (file: %s)"
        % _PILOT_CONTRACT
    )
    actions = _action_constants(pilot_identity)
    assert actions, "pilot_identity yielded zero ACTION_* constants"
    missing = [action for action in sorted(actions) if action not in section]
    assert missing == [], (
        "Mid-wave lapse section missing ACTION_* value(s): %s (file: %s)"
        % (", ".join(missing), _PILOT_CONTRACT)
    )


def test_parse_token_table_rejects_duplicate_row():
    table_text = (
        "| Token | When returned |\n"
        "|---|---|\n"
        "| `identity-answer-invalid` | probe |\n"
        "| `identity-answer-invalid` | duplicate |\n"
    )
    with pytest.raises(ValueError, match="duplicate token row"):
        _parse_token_table(table_text, _TOKEN_HEADER)


def test_census_red_per_section_union_collapse(monkeypatch):
    """Bite-proof: union collapse must fail when one section's table vanishes."""
    doc = _load_contract()
    token = pilot_identity.REFUSAL_LAPSE_SIGN_IN_PATH_INVALID
    modified = _remove_table_row(doc, token)
    monkeypatch.setattr(sys.modules[__name__], "_load_contract", lambda: modified)
    with pytest.raises(AssertionError):
        test_module_tokens_code_to_doc(_MODULE_CONFIG[0])


def test_census_red_code_to_doc_missing_token(monkeypatch):
    """Bite-proof: undocumented module token must fail code→doc."""
    doc = _load_contract()
    token = pilot_identity.REFUSAL_IDENTITY_ANSWER_INVALID
    modified = _remove_table_row(doc, token)
    monkeypatch.setattr(sys.modules[__name__], "_load_contract", lambda: modified)
    with pytest.raises(AssertionError):
        test_module_tokens_code_to_doc(_MODULE_CONFIG[0])


def test_census_red_doc_to_code_fictitious_token(monkeypatch):
    """Bite-proof: fictitious documented token must fail doc→code."""
    doc = _load_contract()
    fake = "auth-census-fictitious-token"
    assert fake not in doc
    modified = _append_table_row(
        doc,
        _TOKEN_HEADER,
        "| `%s` | probe extra |" % fake,
        after=_HORIZON_TOKEN_SUBHEADER,
    )
    monkeypatch.setattr(sys.modules[__name__], "_load_contract", lambda: modified)
    with pytest.raises(AssertionError):
        test_module_tokens_doc_to_code(_MODULE_CONFIG[1])


def test_census_red_missing_section_heading(monkeypatch):
    """Bite-proof: renamed section heading must fail population check."""
    doc = _load_contract()
    modified = doc.replace(
        "## Credential validity margin",
        "## Credential validity margin (renamed)",
    )
    monkeypatch.setattr(sys.modules[__name__], "_load_contract", lambda: modified)
    with pytest.raises(AssertionError, match="missing section heading"):
        test_module_token_population_non_vacuous(_MODULE_CONFIG[1])
