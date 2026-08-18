"""Drift guards for the three-exit discovery doctrine (issue #935).

Enforces: (1) the old spec-only exit vocabulary is gone from architect-discovery;
(2) the new doctrine clauses are present section-scoped in discovery, architect-spec,
and showrunner duty-1; (3) a light-weight spec is the same artifact class as a full spec.
"""
# What this file does and does not guard (owner ruling 21-d, issue #935; byte-literal floor 2026-08-17).
#
# Every assertion here rests on one of: cross-doc literal-agreement pins, hard-line sentence pins,
# an absence census of literals, a cardinality floor over those censuses, an extractor whose only
# job is bounding one of those pins to its home block, or a lib/-behavior / fixture-frontmatter
# test that is not a prose guard at all.
#
# The charter's MEANING is guarded by review, not by CI. Guards that tried to decide whether prose
# said the right thing — a negation regex over handoff messages, a disposition vocabulary sourced
# from an editable template, substring checks wearing structural labels — were removed rather than
# patched: three review rounds showed each one could be evaded by prose that satisfied the letter
# and inverted the sense. Do not reintroduce that class. If a doctrine claim can only be checked by
# judging what a sentence means, it belongs to the review panel.
import importlib.util
import json
import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_REPO_ROOT = os.path.normpath(os.path.join(_HERE, "..", "..", "..", ".."))
_FIXTURES = os.path.join(_HERE, "fixtures")
_LIGHT_SPEC_FIXTURE = os.path.join(_FIXTURES, "light_spec_sample.md")

_DISCOVERY_CHARTER = "skills/architect-discovery/SKILL.md"
_ARCHITECT_SPEC_CHARTER = "skills/architect-spec/SKILL.md"
_SHOWRUNNER_CHARTER = "skills/showrunner/SKILL.md"

# Pinned register literals (epic register is home of record; duplicated here because
# lib/tests/ ships inside the plugin to projects that do not carry the register file).
R5_WEIGHT_VOCABULARY = (
    "A weight call names `light` or `full`, states its measurables (gradable-line count "
    "for a spec draft; child count and register-entry count for a package read), names a "
    "round ceiling when it governs a read loop, and may be overridden in either direction "
    "by one stated sentence; the numeric bars are guidelines, never gates."
)

R7_PARK_SURFACE = (
    "A park lands the full park note — what was elicited or found so far, explicitly "
    "marked unapproved — on the owner's reading surface at park time: in the advisor's "
    "delivery message when the owner is present, else as the opening item of the "
    "advisor's next delivery message; a durable copy lands as a comment on the parked "
    "item's issue or PR, and the durable copy is for the record — it is never required "
    "owner reading."
)

# Old charter sentences that asserted spec-only exit or widget routing — must not return.
_BANNED_DISCOVERY_STRINGS = [
    ("AskUserQuestion", "widget tool name for consequential choices"),
    (
        "and ends with the owner's approval.",
        "spec-only terminal gate phrasing",
    ),
    (
        "Turn a fuzzy idea into an owner-approved definition-doc",
        "spec-only discovery framing in the opening",
    ),
    (
        "A spec can be short; it cannot be skipped, and its gates cannot be",
        "spec cannot be skipped hard gate",
    ),
    ("Prefer multiple-choice", "widget-first elicitation routing"),
    (
        "the phase ends with the owner's approval, never with a plan document",
        "approval-only phase ending",
    ),
    (
        "Discovery is done — hand back",
        "single-exit handback phrase",
    ),
    (
        "hands back with no spec at all",
        "retired park-without-spec phrasing",
    ),
    (
        "coming straight to you",
        "bypass owner review phrasing removed in #935",
    ),
    (
        "the draft rides the park note",
        "retired two-artifact park phrasing",
    ),
    (
        "canonical `docs/superheroes/<work-item>/spec.md` path",
        "in-repo-only draft path, retired by A1",
    ),
    (
        "at its canonical `spec.md` path",
        "mode-blind draft-path phrasing, retired by A1",
    ),
]

_DISCOVERY_HARD_GATE_CLAUSES = [
    "do NOT author the spec, write any code, mint a work-item, or hand off until you have presented the framing (the **what**) and the owner has explicitly approved it.",
    "never approve on your own behalf",
    "hands back with no approved spec",
    "the draft stays on disk at the spec path `resolve-write --doc spec` reports, with `status: draft`",
    "the park note carries that path, never a second copy",
]

_DISCOVERY_SECTION_CLAUSES = {
    "## The one front door": [
        "The plugin offers no separate spike",
        "when an investigation ends, discovery's exit gate is still",
        "A decision the owner has already made needs no discovery.",
        "is the advisor's call, not",
    ],
    "## The three exits": [
        "exactly one of three exits",
        "every exit reports to the advisor",
        "No spec is ever fabricated to close a discovery.",
    ],
    "### Exit B — the findings record": [
        "findings.md",
        "lib/definition_doc.py\" mint --title",
        "Take its directory; never write to the",
        "no frontmatter block, no gates",
        "that no spec is being written, and why",
        "The ratification is the owner's, never yours",
        "Report the exit to the advisor",
        "not writing the findings record.",
        "cannot mint the work-item",
        "mint returned an empty work-item",
    ],
    "### Exit C — the park note": [
        R7_PARK_SURFACE,
        "Explicitly marked unapproved",
        "Nothing elicited is lost.",
        "Report the park to the advisor",
        "One durable artifact per home: the note points at the draft, it never carries a copy of it.",
    ],
    "### 2. The consent gate — investigation spend is the owner's to authorize": [
        "Consent before spend, with the spend named.",
        "Silence is not consent. Spend never starts on silence.",
        "waits or parks",
        "stops the investigation",
        "asks again",
        "This is the only mid-flight consent point.",
        "take Exit B",
    ],
    "### 3. Requirements dialogue (one question at a time)": [
        "No up-front ceremony choice",
        "ask whether they care",
        "recorded disposition",
        "The spec's dispositions table is the stopping rule, not a question quota.",
        "the spec's `## Coverage` section",
        "closes having asked only the questions its table needed",
        "Never route a consequential choice through a pick-one widget",
        "Accept free-form answers and carry the dialogue forward.",
        "never re-present the same list demanding a single selection",
        "Re-forcing the choice after a clarifying answer is the failure this rule names.",
    ],
    "### 7. The weight call, then review at that weight": [
        R5_WEIGHT_VOCABULARY,
        "The weight call is the advisor's — always.",
        "the completed draft waits for the advisor's call",
        "Gradable requirement lines",
        "Interlocking sections",
        "At or under 10 gradable requirement lines with no interlocking sections calls `light`; above calls `full`.",
        "Both inputs must hold for `light`",
        "An override is valid only when stated, and one stated sentence is enough",
        "The 10-line bar is a guideline, never a gate.",
        "item parks (Exit C) with the draft left at the spec path `resolve-write --doc spec` reports, `status: draft`,",
    ],
    "### 8. Owner review & final approval (terminal gate)": [
        "How you ask depends on the weight called in step 7.",
        "Exit A is done — report and hand back.",
        "Report the exit to the advisor",
        "At `light` weight:",
        "At `full` weight:",
        "There is no fourth message.",
        "never offer them a spec that had none",
        "re-review the revised draft at its effective weight",
        "without a re-review at the effective weight",
    ],
}

_ARCHITECT_SPEC_SECTION_CLAUSES = {
    "## Weight never changes the artifact class": [
        "Same template.",
        "There is no light template.",
        "Same home.",
        "There is no light home.",
        "Same anchor power.",
        "A light spec is not a weaker citation.",
        "Same owner approval authority.",
        "There is no lighter approval.",
        "Empty sections are omitted, never filled.",
        "A heading with nothing",
        "is recorded by hand today rather than",
        "[#1062](https://github.com/zwrose/superheroes/issues/1062)'s work, not this skill's",
    ],
}

_DUTY1_START = "1. **Think at the project level.**"
_DUTY1_END = "2. **Board hygiene"

_DUTY1_CLAUSES = [
    "An abandoned discovery is parked, never left silent.",
    R7_PARK_SURFACE,
    "nothing elicited is mistaken for approved content",
    "Silence is not a disposition",
    "The review weight on a completed spec draft is yours to call.",
    R5_WEIGHT_VOCABULARY,
    "a discovery session",
    "never weighs its own draft",
]

_WEIGHT_SECTION = "### 7. The weight call, then review at that weight"


def _load_definition_doc():
    path = os.path.join(_HERE, "..", "definition_doc.py")
    spec = importlib.util.spec_from_file_location("definition_doc_discovery_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DD = _load_definition_doc()


def _read_plugin(rel):
    path = rel if os.path.isabs(rel) else os.path.join(_PLUGIN_ROOT, rel)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _normalized(text):
    return re.sub(r"\s+", " ", text.replace("*", "")).strip()


def _expect_error(fn, exc_type, *, match):
    """Require fn() to raise exc_type matching `match`.

    `pytest.raises(exc_type)` is not enough for a bite-proof: a detector that regresses
    into `pytest.skip` raises `Skipped`, which derives from BaseException, so
    pytest.raises declines it and the whole test is reported SKIPPED — green. This
    helper catches BaseException and turns anything that is not a matching exc_type into
    a failure, so a detector that stopped biting is always red.
    """
    exc_name = exc_type.__name__
    try:
        fn()
    except exc_type as exc:
        if not re.search(match, str(exc)):
            raise AssertionError(
                "detector raised %s but message %r does not match %r"
                % (exc_name, str(exc), match)
            ) from None
        return exc
    except BaseException as exc:  # noqa: BLE001 — Skipped is a BaseException, and that is the point
        raise AssertionError(
            "detector did not bite: expected %s, got %s: %s"
            % (exc_name, type(exc).__name__, exc)
        ) from None
    raise AssertionError("detector did not bite: no exception raised")


def _expect_assertion_error(fn, *, match):
    return _expect_error(fn, AssertionError, match=match)


def _heading_level(line):
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None
    match = re.match(r"^(#+)\s", stripped)
    if not match:
        return None
    return len(match.group(1))


def _file_section(rel, heading, read_text=None):
    """Extract a named section; raises if heading is absent or duplicated."""
    return _normalized(_file_section_raw(rel, heading, read_text))


def _file_section_raw(rel, heading, read_text=None):
    """Extract a named section as raw text; raises if heading is absent or duplicated."""
    if read_text is None:
        read_text = _read_plugin
    text = read_text(rel)
    lines = text.splitlines()
    indices = [i for i, line in enumerate(lines) if line.strip() == heading]
    if len(indices) == 0:
        raise RuntimeError(f"{rel}: heading {heading!r} not found")
    if len(indices) > 1:
        raise RuntimeError(
            f"{rel}: heading {heading!r} appears {len(indices)} times"
        )
    start = indices[0]
    start_level = _heading_level(lines[start])
    end = len(lines)
    for i in range(start + 1, len(lines)):
        level = _heading_level(lines[i])
        if level is not None and level <= start_level:
            end = i
            break
    return "\n".join(lines[start:end])


def _extract_hard_gate_block(text):
    """Return normalized text strictly between <HARD-GATE> and </HARD-GATE>."""
    lines = text.splitlines()
    open_indices = [
        i for i, line in enumerate(lines) if line.strip() == "<HARD-GATE>"
    ]
    close_indices = [
        i for i, line in enumerate(lines) if line.strip() == "</HARD-GATE>"
    ]
    if len(open_indices) != 1:
        raise RuntimeError(
            "<HARD-GATE> found %d times (expected 1)" % len(open_indices)
        )
    if len(close_indices) != 1:
        raise RuntimeError(
            "</HARD-GATE> found %d times (expected 1)" % len(close_indices)
        )
    open_idx = open_indices[0]
    close_idx = close_indices[0]
    if close_idx <= open_idx:
        raise RuntimeError("</HARD-GATE> precedes <HARD-GATE>")
    return _normalized("\n".join(lines[open_idx + 1:close_idx]))


def _assert_clauses_in_text(text, clauses, label):
    """Fail if any required clause is absent from normalized text."""
    normalized = _normalized(text)
    for clause in clauses:
        if _normalized(clause) not in normalized:
            raise AssertionError(
                f"{label}: required clause missing: {clause!r}"
            )


def _check_banned_absent(text, banned_strings, label):
    """Fail if any banned substring appears in normalized text."""
    normalized = _normalized(text)
    for banned, _comment in banned_strings:
        if _normalized(banned) not in normalized:
            continue
        line_no = None
        for i, line in enumerate(text.splitlines()):
            if banned in line:
                line_no = i + 1
                break
        if line_no is not None:
            raise AssertionError(
                f"{label}: banned string found — {banned!r} at line {line_no}"
            )
        raise AssertionError(
            f"{label}: banned string found — {banned!r} at "
            "line: unknown (matched only after normalization)"
        )


def _assert_clause_survives_normalization(table_label, section_key, clause):
    """Refuse clause literals that _normalized would make unmatchable."""
    if "*" in clause:
        raise AssertionError(
            f"{table_label}[{section_key!r}]: clause contains '*' "
            f"(stripped by _normalized): {clause!r}"
        )
    if "\n" in clause:
        raise AssertionError(
            f"{table_label}[{section_key!r}]: clause contains newline "
            f"(collapsed by _normalized): {clause!r}"
        )
    if "  " in clause:
        raise AssertionError(
            f"{table_label}[{section_key!r}]: clause contains consecutive spaces "
            f"(collapsed by _normalized): {clause!r}"
        )


def _assert_clause_tables_survive_normalization(section_clause_tables, list_clause_tables=None):
    """Walk clause tables and refuse literals _normalized cannot match."""
    for table_label, table in section_clause_tables.items():
        for section_key, clauses in table.items():
            for clause in clauses:
                _assert_clause_survives_normalization(table_label, section_key, clause)
    if list_clause_tables:
        for table_label, clauses in list_clause_tables.items():
            for index, clause in enumerate(clauses):
                _assert_clause_survives_normalization(table_label, index, clause)


def _assert_section_clauses(rel, section_clauses, read_text=None):
    """Assert every clause appears in its declared section body."""
    if read_text is None:
        read_text = _read_plugin
    for heading, clauses in section_clauses.items():
        section_text = _file_section(rel, heading, read_text)
        for clause in clauses:
            if clause not in section_text:
                raise AssertionError(
                    f"{rel}: clause missing from section {heading!r}: {clause!r}"
                )


def _extract_duty1_block(text):
    """Return normalized duty-1 block between numbered list boundaries."""
    lines = text.splitlines()
    start_indices = [
        i for i, line in enumerate(lines) if line.strip().startswith(_DUTY1_START)
    ]
    end_indices = [
        i for i, line in enumerate(lines) if line.strip().startswith(_DUTY1_END)
    ]
    if len(start_indices) != 1:
        raise RuntimeError(
            f"{_SHOWRUNNER_CHARTER}: duty-1 start {_DUTY1_START!r} "
            f"found {len(start_indices)} times (expected 1)"
        )
    if len(end_indices) != 1:
        raise RuntimeError(
            f"{_SHOWRUNNER_CHARTER}: duty-1 end {_DUTY1_END!r} "
            f"found {len(end_indices)} times (expected 1)"
        )
    start = start_indices[0]
    end = end_indices[0]
    if end <= start:
        raise RuntimeError(
            f"{_SHOWRUNNER_CHARTER}: duty-1 end precedes start"
        )
    return _normalized("\n".join(lines[start:end]))


# --- 1a. Absence census ----------------------------------------------------


def test_discovery_charter_banned_strings_absent():
    text = _read_plugin(_DISCOVERY_CHARTER)
    _check_banned_absent(text, _BANNED_DISCOVERY_STRINGS, _DISCOVERY_CHARTER)


def test_discovery_charter_hard_gate_clauses_present():
    text = _read_plugin(_DISCOVERY_CHARTER)
    block = _extract_hard_gate_block(text)
    _assert_clauses_in_text(block, _DISCOVERY_HARD_GATE_CLAUSES, _DISCOVERY_CHARTER)


def test_census_tables_are_populated():
    expected_discovery_keys = {
        "## The one front door",
        "## The three exits",
        "### Exit B — the findings record",
        "### Exit C — the park note",
        "### 2. The consent gate — investigation spend is the owner's to authorize",
        "### 3. Requirements dialogue (one question at a time)",
        "### 7. The weight call, then review at that weight",
        "### 8. Owner review & final approval (terminal gate)",
    }
    assert set(_DISCOVERY_SECTION_CLAUSES) == expected_discovery_keys
    expected_architect_spec_keys = {"## Weight never changes the artifact class"}
    assert set(_ARCHITECT_SPEC_SECTION_CLAUSES) == expected_architect_spec_keys
    for clauses in _DISCOVERY_SECTION_CLAUSES.values():
        assert len(clauses) >= 3
    for clauses in _ARCHITECT_SPEC_SECTION_CLAUSES.values():
        assert len(clauses) >= 3
    assert _BANNED_DISCOVERY_STRINGS
    assert len(_DISCOVERY_HARD_GATE_CLAUSES) >= 5
    assert _DUTY1_CLAUSES
    assert len(_DUTY1_CLAUSES) >= 8


# --- 1b. Section-scoped presence, architect-discovery ----------------------


@pytest.mark.parametrize(
    "heading,clauses",
    [
        (heading, clauses)
        for heading, clauses in _DISCOVERY_SECTION_CLAUSES.items()
    ],
    ids=list(_DISCOVERY_SECTION_CLAUSES),
)
def test_discovery_charter_section_clauses(heading, clauses):
    _assert_section_clauses(_DISCOVERY_CHARTER, {heading: clauses})


# --- 1c. Section-scoped presence, architect-spec ---------------------------


def test_architect_spec_weight_equivalence_clauses():
    _assert_section_clauses(_ARCHITECT_SPEC_CHARTER, _ARCHITECT_SPEC_SECTION_CLAUSES)
    labels = _ARCHITECT_SPEC_SECTION_CLAUSES["## Weight never changes the artifact class"]
    for label in ("Same template.", "Same home.", "Same anchor power.", "Same owner approval authority."):
        assert label in labels, "missing equivalence label %r in table" % label


# --- 1d. Showrunner duty-1 block -------------------------------------------


def test_showrunner_duty1_discovery_doctrine_clauses():
    text = _read_plugin(_SHOWRUNNER_CHARTER)
    duty1 = _extract_duty1_block(text)
    for clause in _DUTY1_CLAUSES:
        if clause not in duty1:
            raise AssertionError(
                f"{_SHOWRUNNER_CHARTER}: duty-1 clause missing: {clause!r}"
            )


# --- 1e. Light-spec fixture — lib behavior ---------------------------------


def test_light_spec_same_home(tmp_path):
    # In-repo mode only — the global-mode resolver needs a configured project store
    # this test does not have.
    fm, _body = DD.read_frontmatter(_LIGHT_SPEC_FIXTURE)
    work_item = fm["workItem"]
    work_dir = DD.work_item_dir(work_item, root=str(tmp_path))
    assert os.path.basename(work_dir) == work_item
    expected_dir = os.path.join(str(tmp_path), "docs", "superheroes", work_item)
    assert work_dir == expected_dir
    spec_path = DD.doc_path(work_item, "spec", root=str(tmp_path))
    expected_spec = os.path.join(expected_dir, "spec.md")
    assert spec_path == expected_spec
    plan_path = DD.doc_path(work_item, "plan", root=str(tmp_path))
    tasks_path = DD.doc_path(work_item, "tasks", root=str(tmp_path))
    assert os.path.dirname(spec_path) == os.path.dirname(plan_path) == os.path.dirname(tasks_path)
    assert spec_path != plan_path
    assert spec_path != tasks_path
    assert plan_path.endswith("plan.md")
    assert tasks_path.endswith("tasks.md")


def test_light_spec_same_anchor_power():
    # Inputs a spec-section anchor resolves against: approved status, dated approval,
    # docType spec, and at least one citeable ## heading in the body.
    fm, body = DD.read_frontmatter(_LIGHT_SPEC_FIXTURE)
    assert fm.get("status") == "approved"
    assert fm.get("docType") == "spec"
    approved = fm.get("approved", "").strip('"')
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", approved), approved
    assert re.search(r"^## ", body, re.MULTILINE), "body needs a ## heading for anchors"


def test_light_spec_same_owner_approval_authority(tmp_path):
    import shutil

    dest = tmp_path / "light-spec.md"
    shutil.copy2(_LIGHT_SPEC_FIXTURE, dest)
    text = dest.read_text(encoding="utf-8")
    result_pending = DD.set_gate(
        str(dest),
        "pending",
        expected_hash=DD.content_hash(text),
        run_id="test-light-spec-pending",
    )
    assert result_pending.get("ok") is True, result_pending
    assert DD.read_gate(str(dest)) == "pending"
    fm, _body = DD.read_frontmatter(str(dest))
    assert fm.get("status") == "draft"
    text_after_pending = dest.read_text(encoding="utf-8")
    result_passed = DD.set_gate(
        str(dest),
        "passed",
        expected_hash=DD.content_hash(text_after_pending),
        run_id="test-light-spec-passed",
    )
    assert result_passed.get("ok") is True, result_passed
    assert DD.read_gate(str(dest)) == "passed"
    fm, _body = DD.read_frontmatter(str(dest))
    assert fm.get("status") == "approved"


# --- Negative tests (synthetic in-memory strings; no repo mutation) ----------


def test_negative_hard_gate_clause_missing_in_synthetic():
    synthetic = "\n".join([
        "<HARD-GATE>",
        "hands back with no approved spec only",
        "</HARD-GATE>",
    ])
    block = _extract_hard_gate_block(synthetic)
    _expect_assertion_error(
        lambda: _assert_clauses_in_text(
            block, _DISCOVERY_HARD_GATE_CLAUSES, "synthetic",
        ),
        match="required clause missing",
    )


def test_negative_hard_gate_duplicate_open_raises():
    synthetic = "\n".join([
        "<HARD-GATE>",
        "<HARD-GATE>",
        "content",
        "</HARD-GATE>",
    ])
    _expect_error(
        lambda: _extract_hard_gate_block(synthetic),
        RuntimeError,
        match="<HARD-GATE>",
    )


def test_negative_hard_gate_missing_close_raises():
    synthetic = "\n".join([
        "<HARD-GATE>",
        "content without close tag",
    ])
    _expect_error(
        lambda: _extract_hard_gate_block(synthetic),
        RuntimeError,
        match="</HARD-GATE>",
    )


def test_negative_banned_string_detected_in_synthetic():
    synthetic = "Some charter text.\nAskUserQuestion\nMore text."
    _expect_assertion_error(
        lambda: _check_banned_absent(synthetic, _BANNED_DISCOVERY_STRINGS, "synthetic"),
        match="banned string found",
    )


def test_negative_banned_string_line_wrapped_in_synthetic():
    banned = "and ends with the owner's approval."
    synthetic = "\n".join([
        "Some charter text.",
        "and ends with the owner's",
        "approval.",
        "More text.",
    ])
    _expect_assertion_error(
        lambda: _check_banned_absent(synthetic, [(banned, "probe")], "synthetic"),
        match="matched only after normalization",
    )


def test_negative_banned_string_emphasis_in_synthetic():
    banned = "Prefer multiple-choice"
    synthetic = "Routing: Prefer **multiple-choice** widgets here."
    _expect_assertion_error(
        lambda: _check_banned_absent(synthetic, [(banned, "probe")], "synthetic"),
        match="banned string found",
    )


def test_negative_section_scoped_clause_rejects_out_of_section_match():
    synthetic_path = "synthetic/discovery.md"
    heading = "## The three exits"
    clause = "exactly one of three exits"
    synthetic_text = "\n".join([
        heading,
        "Doctrine without the probe clause here.",
        "## FAQ",
        f"FAQ prose repeats: {clause}",
    ])

    def read_text(rel):
        if rel == synthetic_path:
            return synthetic_text
        return _read_plugin(rel)

    _expect_assertion_error(
        lambda: _assert_section_clauses(
            synthetic_path,
            {heading: [clause]},
            read_text,
        ),
        match=r"clause missing from section '## The three exits'",
    )


def test_negative_duty1_duplicate_start_boundary_raises():
    synthetic = "\n".join([
        "1. **Think at the project level.** (duplicate)",
        "1. **Think at the project level.** (duplicate)",
        "2. **Board hygiene — file and wire.**",
    ])
    _expect_error(
        lambda: _extract_duty1_block(synthetic),
        RuntimeError,
        match="duty-1 start",
    )


def test_negative_duty1_missing_start_boundary_raises():
    synthetic = "\n".join([
        "Preamble without the duty-1 start marker.",
        "2. **Board hygiene — file and wire.**",
    ])
    _expect_error(
        lambda: _extract_duty1_block(synthetic),
        RuntimeError,
        match="duty-1 start",
    )


def test_clause_tables_survive_normalization():
    _assert_clause_tables_survive_normalization(
        {
            "discovery": _DISCOVERY_SECTION_CLAUSES,
            "architect_spec": _ARCHITECT_SPEC_SECTION_CLAUSES,
        },
        {"duty1": _DUTY1_CLAUSES},
    )


def test_negative_clause_tables_survive_normalization_rejects_bad_literals():
    _expect_assertion_error(
        lambda: _assert_clause_tables_survive_normalization(
            {"synthetic": {"## Section": ["has * star"]}},
        ),
        match=r"contains '\*'",
    )
    _expect_assertion_error(
        lambda: _assert_clause_tables_survive_normalization(
            {"synthetic": {"## Section": ["has  double space"]}},
        ),
        match="consecutive spaces",
    )


def _synthetic_weight_section(
    *,
    swap_rows=False,
    corrupt_full_row_only=False,
    classification_rule=None,
    include_table=True,
):
    light_review = "one independent review seat"
    light_vet = "light vet"
    light_owner = "in-channel"
    full_review = "review-spec panel"
    full_vet = "full spec vet"
    full_owner = "scheduled owner review"
    if corrupt_full_row_only:
        full_review = "placeholder review"
        full_vet = "placeholder vet"
        full_owner = "placeholder approval"
    if swap_rows:
        light_review, full_review = full_review, light_review
        light_vet, full_vet = full_vet, light_vet
        light_owner, full_owner = full_owner, light_owner
    rule = classification_rule or "Both inputs must hold for `light`"
    lines = [
        _WEIGHT_SECTION,
        "",
        rule,
        "",
    ]
    if include_table:
        lines.extend([
            "| Weight | Review | Vet | Owner approval |",
            "| --- | --- | --- | --- |",
            f"| `light` | {light_review} | {light_vet} | {light_owner} |",
            f"| `full` | {full_review} | {full_vet} | {full_owner} |",
        ])
    return "\n".join(lines)


def test_negative_weight_table_inverted_classification_rule_fails():
    synthetic_path = "synthetic/weight-rule.md"
    synthetic_text = _synthetic_weight_section(
        classification_rule="Both inputs must hold for `full`",
    )

    def read_text(rel):
        if rel == synthetic_path:
            return synthetic_text
        return _read_plugin(rel)

    _expect_assertion_error(
        lambda: _assert_section_clauses(
            synthetic_path,
            {
                _WEIGHT_SECTION: [
                    "Both inputs must hold for `light`",
                ],
            },
            read_text,
        ),
        match=r"clause missing from section '### 7\. The weight call, then review at that weight'",
    )


def test_negative_set_gate_without_gates_line_fails(tmp_path):
    import shutil

    dest = tmp_path / "stripped.md"
    shutil.copy2(_LIGHT_SPEC_FIXTURE, dest)
    text = dest.read_text(encoding="utf-8")
    text_no_gates = re.sub(r"^gates:.*\n", "", text, flags=re.MULTILINE)
    dest.write_text(text_no_gates, encoding="utf-8")
    with pytest.raises(ValueError, match=r"no 'gates: \{review: …\}' line to update"):
        DD.set_gate(
            str(dest),
            "passed",
            expected_hash=DD.content_hash(text_no_gates),
            run_id="test-no-gates",
        )


# Pre-existing schema gap: docs/superheroes/front-half-sdlc-core-6181ee/spec.md carries
# approved: and fails the same validation — fixture mirrors real artifact practice.
def test_light_spec_fixture_schema_approved_exemption():
    jsonschema = pytest.importorskip("jsonschema")
    yaml = pytest.importorskip("yaml")

    schema_path = os.path.join(
        _REPO_ROOT, "eval", "lib", "schemas", "definition-doc.schema.json"
    )
    with open(schema_path, encoding="utf-8") as fh:
        schema = json.load(fh)

    fixture_text = open(_LIGHT_SPEC_FIXTURE, encoding="utf-8").read()
    lines = fixture_text.splitlines()
    end = lines.index("---", 1)
    fm = yaml.safe_load("\n".join(lines[1:end]))
    assert "approved" in fm

    fm_without_approved = {key: value for key, value in fm.items() if key != "approved"}
    jsonschema.validate(fm_without_approved, schema)

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(fm, schema)
