"""Census detector: decision-point contract (#1144).

Mechanical receipt for the invariant that every skill-surface site taking a default or waiting
for an answer is wrapped in a declared decision block, and owner-decision primitives are
forbidden outside such blocks (see reference/decision-points.md).

Disclosed residual: underscore-emphasis (`_..._`) is not normalized before matching — one file,
one occurrence on this tree vs 48 files for `**` — so stripping `_` would buy almost nothing and
risk mangling `snake_case` identifiers such as `review_store.py`.

Deliberately out of scope:
- Converting skill surfaces — other work orders; the shipped census is green on this tree.
- skills/architect-discovery/** — rubric-excluded per escalation-base.md § Scope (elicitation).

Carrier transport is declared in block tags but not verified by this census (owner ruling, 2026-08-25).
"""
import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SKILLS_ROOT = os.path.join(_PLUGIN_ROOT, "skills")

_DECISION_POINT_SELF = os.path.normpath(
    os.path.join(_PLUGIN_ROOT, "lib/tests/test_decision_point_census.py")
)
_CENSUS_EXCLUDED_DIRS = (
    os.path.normpath(os.path.join(_PLUGIN_ROOT, "lib/tests/bite_proofs")),
)

_VALID_MODES = frozenset({"proceed", "notify", "gate"})
_VALID_KINDS = frozenset({
    "storage-location",
    "ask-user-question",
    "interview-step",
    "owner-gate",
})

_FORBIDDEN_PRIMITIVES = (
    "AskUserQuestion",
    "decide-location)",
    "present-judgment",
    "present-stall-menu",
    "one question at a time",
    "one-question-at-a-time",
    "Ask, one at a time",
    "only on the owner's explicit confirm",
    "only what they approve",
    "Only if they decline",
    "STOP and guide",
    "ask the user to start",
)

_WAITING_TOKENS = (
    "wait for",
    "waits for",
    "until they answer",
    "until the owner answers",
    "and wait",
)

_CARRIER_REGISTRY = frozenset({
    "review-crew-layer",
    "test-pilot-layer",
    "review-spec-receipt",
    "audit-report",
    "review-code-meta",
    "doc-policy-disclosures",
    "run-output",
})

# Byte-pinned stripped lines — literals only; no rationale (#1144).
_BYTE_PIN_LINES = frozenset({
    "Open no `AskUserQuestion` on any review-code path, for any purpose.",
    "which posted to GitHub and kept its own `AskUserQuestion` review-event gate, was removed (#1121).",
    "**Write the presentation artifact — the only path.** Follow "
    "`${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/review-code/reference/headless-presentation.md`. "
    "Presence is an event, not a state a run can detect — the run never branches on whether a "
    "human is present and never opens a question that could block waiting for an answer. Never "
    "open `AskUserQuestion` on this path or any review-code path.",
    "past it, and **never** treat it like `present-judgment` (an intervention gate that folds back into",
    "**Owner gates on the durable-record path.** When `advance` parks at `present-judgment` or",
    "`present-stall-menu` because gate policy has not pre-authorized the resolution",
    "`present-judgment`, `{\"choice\": \"<stall choice>\"}` for `present-stall-menu`. The fold runs through",
    "durable records are present, hand `submit` when they are not. Owner gates (`present-judgment`,",
    "`present-stall-menu`) still park with `advance-judgment-park` / `advance-stall-park` when",
    "### Owner gates and gate policy (`present-judgment`, `present-stall-menu`)",
    "| `present-judgment` | A tradeoff/product-choice blocker is an **owner-judgment** call routed here "
    "— an **intervention gate, not a terminal**. Present each `payload.findings[]` (id, file, line, "
    "title, severity) with `payload.findings[].dispositions` (`fix-as-suggested`, `fix-with-guidance`, "
    "`skip`). Submit `{dispositions: [{id, disposition, guidance?, reason?}, ...]}` — `skip` needs a "
    "citable `reason`. Fixes fold into the round's fix batch and the loop proceeds into the fix leg; "
    "skips ride the exit disclosure. Fail-closed: a missing/unknown disposition (or a reasonless skip) "
    "folds as `fix-as-suggested` — a judgment blocker is never silently skipped. Never judge the "
    "dispute yourself. |",
    "| `present-stall-menu` | The **audit-stall owner gate** — reached only after one invisible "
    "self-recovery (never for a judgment blocker; those go to `present-judgment`). Present "
    "`payload.choices` (three-choice menu: `one-more-round`, `accept-the-disclosed-risk`, `hold`; "
    "`accept-the-disclosed-risk` only when `payload.acceptRiskEligible` — gated on a stalled audit "
    "target that is CONFIRMED with evidence; `one-more-round` only when offered — once per session). "
    "Submit `{choice}`. **`hold`** → terminal `held`, certification withheld (absorbs the retired "
    "scope-reduction choice). **`accept-the-disclosed-risk`** → certifies when eligible. "
    "**`one-more-round`** → not a terminal: clears the stall once, re-enters `dispatch-fixer` → "
    "`dispatch-audits` with the stalled targets as the batch (journaled; recorded on the round); "
    "an empty/unresolvable stall-target snapshot parks `cannot-certify` instead of re-entering. |",
    "- **Judgment gate is an intervention, not a terminal** — a tradeoff blocker routes to "
    "`present-judgment` (fix-as-suggested / fix-with-guidance / skip-with-reason) and folds back "
    "into the fix leg; a skipped blocker rides the exit disclosure. It never dead-ends in the stall "
    "menu.",
    "printf '%s\\n' '{\"schema\":\"gate-policy/1\",\"default\":\"park\",\"rules\":[{\"gate\":\"present-judgment\","
    "\"findingClass\":\"judgment:important\",\"disposition\":\"skip\"}]}' | \\",
})

_OPEN_TAG_RE = re.compile(
    r"<!--\s*decision-point:\s*"
    r"id=(?P<id>[^\s]+)\s+"
    r"mode=(?P<mode>[^\s]+)\s+"
    r"kind=(?P<kind>[^\s]+)\s+"
    r'default="(?P<default>[^"]*)"\s+'
    r"carrier=(?P<carrier>[^\s]+)\s*-->"
)
_CLOSE_TAG_RE = re.compile(r"<!--\s*/decision-point:\s*id=(?P<id>[^\s]+)\s*-->")


def _census_excluded(path):
    norm = os.path.normpath(path)
    if norm == _DECISION_POINT_SELF:
        return True
    return any(norm.startswith(d + os.sep) for d in _CENSUS_EXCLUDED_DIRS)


def _normalize_match_text(text):
    """E1: normalize markdown * emphasis before literal matching (length-preserving: * -> space)."""
    return text.replace("*", " ")


def _match_search_text(norm_text):
    """Join lines for cross-line literals; length-preserving (newline -> space)."""
    return norm_text.replace("\n", " ")


def _walk_skills_files(skills_root=None):
    root = skills_root or _SKILLS_ROOT
    if not os.path.isdir(root):
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
        for name in filenames:
            yield os.path.join(dirpath, name)


def _plugin_rel(path, skills_root=None):
    root = skills_root or _SKILLS_ROOT
    if os.path.commonpath([os.path.normpath(path), os.path.normpath(root)]) == os.path.normpath(root):
        under_skills = os.path.relpath(path, root)
        skills_rel = os.path.relpath(root, _PLUGIN_ROOT)
        return os.path.normpath(os.path.join(skills_rel, under_skills))
    return os.path.relpath(path, _PLUGIN_ROOT)


def _is_rubric_excluded(rel):
    """§1d rubric-excluded surface — architect-discovery is elicitation, not escalation."""
    norm = rel.replace("\\", "/")
    return norm.startswith("skills/architect-discovery/")


def _is_byte_pinned(stripped_line):
    return stripped_line in _BYTE_PIN_LINES


def _read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _line_starts(text):
    """Map each character offset to 1-based line number."""
    starts = [0]
    for m in re.finditer("\n", text):
        starts.append(m.end())
    return starts


def _offset_to_line(starts, offset):
    lo, hi = 0, len(starts) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if starts[mid] <= offset:
            lo = mid + 1
        else:
            hi = mid - 1
    return hi + 1


def _parse_decision_blocks(text, rel):
    """Return (blocks, errors). blocks: list of dict with id, mode, kind, default, carrier,
    open_line, close_line, prose."""
    blocks = []
    errors = []
    opens = []
    for m in _OPEN_TAG_RE.finditer(text):
        opens.append((m.start(), m))
    closes = [(m.start(), m) for m in _CLOSE_TAG_RE.finditer(text)]

    for pos, m in sorted(opens, key=lambda x: x[0]):
        block_id = m.group("id")
        close_match = None
        close_pos = None
        for cpos, cm in closes:
            if cpos <= pos:
                continue
            if cm.group("id") == block_id:
                close_match = cm
                close_pos = cpos
                break
        if close_match is None:
            errors.append(f"{rel}:{_offset_to_line(_line_starts(text), pos)}: "
                           f"unmatched decision-point open id={block_id!r}")
            continue
        for opos, om in opens:
            if opos <= pos or opos >= close_pos:
                continue
            errors.append(
                f"{rel}:{_offset_to_line(_line_starts(text), opos)}: "
                f"nested decision-point blocks are forbidden (id={om.group('id')!r} inside "
                f"id={block_id!r})"
            )
        mode = m.group("mode")
        kind = m.group("kind")
        default = m.group("default")
        carrier = m.group("carrier")
        open_line = _offset_to_line(_line_starts(text), pos)
        close_line = _offset_to_line(_line_starts(text), close_pos)
        if mode not in _VALID_MODES:
            errors.append(f"{rel}:{open_line}: invalid mode={mode!r}")
        if kind not in _VALID_KINDS:
            errors.append(f"{rel}:{open_line}: invalid kind={kind!r}")
        if not default:
            errors.append(f"{rel}:{open_line}: empty default= for id={block_id!r}")
        if carrier not in _CARRIER_REGISTRY:
            errors.append(f"{rel}:{open_line}: unknown carrier={carrier!r}")
        prose = text[m.end():close_pos]
        blocks.append({
            "id": block_id,
            "mode": mode,
            "kind": kind,
            "default": default,
            "carrier": carrier,
            "open_line": open_line,
            "close_line": close_line,
            "prose": prose,
            "rel": rel,
        })

    for cpos, cm in closes:
        block_id = cm.group("id")
        matched = any(
            b["id"] == block_id and _offset_to_line(_line_starts(text), cpos) == b["close_line"]
            for b in blocks
        )
        if not matched:
            errors.append(
                f"{rel}:{_offset_to_line(_line_starts(text), cpos)}: "
                f"orphan decision-point close id={block_id!r}"
            )

    id_counts = {}
    for b in blocks:
        id_counts[b["id"]] = id_counts.get(b["id"], 0) + 1
    for block_id, count in id_counts.items():
        if count > 1:
            hits = [b for b in blocks if b["id"] == block_id]
            for b in hits:
                errors.append(
                    f"{rel}:{b['open_line']}: duplicate decision-point id={block_id!r}"
                )

    # E4: malformed open tags that look like decision-point but fail to parse
    for m in re.finditer(r"<!--\s*decision-point:", text):
        if not _OPEN_TAG_RE.match(text, m.start()):
            errors.append(
                f"{rel}:{_offset_to_line(_line_starts(text), m.start())}: "
                "malformed decision-point open tag"
            )

    return blocks, errors


def _line_in_block(line_no, blocks):
    for b in blocks:
        if b["open_line"] <= line_no <= b["close_line"]:
            return True
    return False


def _hit_on_pinned_offset(norm_text, offset, primitive, lines):
    """True when the match at offset is exempted by a byte-pinned line."""
    line_starts = _line_starts(norm_text)
    norm_primitive = _normalize_match_text(primitive)
    plen = len(norm_primitive)
    line_no = _offset_to_line(line_starts, offset)
    if line_no > len(lines):
        return False
    line_end = line_starts[line_no] if line_no < len(line_starts) else len(norm_text)
    if offset + plen <= line_end:
        return _is_byte_pinned(lines[line_no - 1].strip())
    # Match spans past the starting line — exempt only when the start line is pinned.
    return _is_byte_pinned(lines[line_no - 1].strip())


def _scan_forbidden_violations(skills_root=None):
    violations = []
    root = skills_root or _SKILLS_ROOT
    file_count = 0
    for path in _walk_skills_files(root):
        if _census_excluded(path):
            continue
        try:
            text = _read_text(path)
        except (UnicodeDecodeError, OSError):
            continue
        file_count += 1
        rel = _plugin_rel(path, root)
        if _is_rubric_excluded(rel):
            continue
        lines = text.splitlines()
        blocks, _ = _parse_decision_blocks(text, rel)
        norm_text = _normalize_match_text(text)
        search_text = _match_search_text(norm_text)
        line_starts = _line_starts(norm_text)
        seen = set()
        for primitive in _FORBIDDEN_PRIMITIVES:
            norm_primitive = _normalize_match_text(primitive)
            start = 0
            while True:
                idx = search_text.casefold().find(norm_primitive.casefold(), start)
                if idx < 0:
                    break
                line_no = _offset_to_line(line_starts, idx)
                if _hit_on_pinned_offset(norm_text, idx, primitive, lines):
                    start = idx + max(len(norm_primitive), 1)
                    continue
                if not _line_in_block(line_no, blocks):
                    key = (rel, line_no, primitive)
                    if key not in seen:
                        seen.add(key)
                        violations.append(f"{rel}:{line_no}: {primitive}")
                start = idx + max(len(norm_primitive), 1)
    return violations, file_count


def _collect_all_blocks(skills_root=None):
    all_blocks = []
    errors = []
    root = skills_root or _SKILLS_ROOT
    for path in _walk_skills_files(root):
        if _census_excluded(path):
            continue
        try:
            text = _read_text(path)
        except (UnicodeDecodeError, OSError):
            continue
        rel = _plugin_rel(path, root)
        if _is_rubric_excluded(rel):
            continue
        blocks, block_errors = _parse_decision_blocks(text, rel)
        all_blocks.extend(blocks)
        errors.extend(block_errors)
    return all_blocks, errors


_FENCED_BASH_RE = re.compile(r"```(?:bash|sh)\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_SOURCE_CAPTURE_RE = re.compile(r"SOURCE\s*=\s*\$\([^)]*\.source", re.IGNORECASE)
_SOURCE_GUARD_RE = re.compile(r'\[\s*-n\s+"\$SOURCE"\s*\]')


def _fenced_bash_blocks(text):
    return [m.group(1) for m in _FENCED_BASH_RE.finditer(text)]


def _mode_structure_violations(block):
    prose_cf = block["prose"].casefold()
    rel = block["rel"]
    line = block["open_line"]
    mode = block["mode"]
    hits = []
    if mode == "gate":
        if "write" not in prose_cf and "written" not in prose_cf:
            hits.append(f"{rel}:{line}: gate block must state the decision is written down")
        if "hand back" not in prose_cf and "hands back" not in prose_cf:
            hits.append(f"{rel}:{line}: gate block must state the run hands back")
    elif mode == "notify":
        if "continu" not in prose_cf:
            hits.append(f"{rel}:{line}: notify block must state the run continues")
    elif mode == "proceed":
        if "continu" not in prose_cf and "record" not in prose_cf:
            hits.append(f"{rel}:{line}: proceed block must record and continue")
    return hits


# axis: E3 — an empty skills walk is a failure, not a pass. Not other census roots.
def test_skills_census_walk_non_empty():
    """#1144: a census that silently walks nothing is green-because-broken."""
    count = sum(1 for _ in _walk_skills_files())
    assert count > 0, "#1144 decision-point census found zero files under skills/"


# axis: E3 — an empty forbidden-primitive registry is a failure. Not block grammar.
def test_forbidden_primitive_registry_non_empty():
    """#1144: an empty primitive list would vacuously pass the prohibition census."""
    assert _FORBIDDEN_PRIMITIVES, "#1144 forbidden-primitive set must not be empty"


# axis: E6 — carrier registry must be non-empty and resolvable. Not transport shape.
def test_carrier_registry_non_empty():
    """#1144: every carrier= value must resolve to a registry key."""
    assert _CARRIER_REGISTRY, "#1144 carrier registry must not be empty"


# axis: E5 — dead byte-pins must fail the suite. Not rubric-excluded surfaces.
def test_byte_pin_lines_exist():
    """#1144: a pin for a line that no longer exists must fail, not sit in the table."""
    stale = []
    all_stripped = set()
    for path in _walk_skills_files():
        if _census_excluded(path):
            continue
        try:
            lines = _read_text(path).splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        all_stripped.update(ln.strip() for ln in lines)
    for pinned in _BYTE_PIN_LINES:
        if pinned not in all_stripped:
            stale.append(repr(pinned))
    assert not stale, (
        "#1144 byte-pin table contains dead entries — re-adjudicate (#1144). Stale:\n"
        + "\n".join(stale)
    )


# axis: forbidden primitives under skills/ must live inside a decision block, byte-pin, or
# rubric-excluded surface — every hit reported. Not waiting tokens.
def test_forbidden_primitives_outside_decision_blocks():
    """#1144: owner-decision primitives outside declared blocks must go red until converted."""
    violations, file_count = _scan_forbidden_violations()
    assert file_count > 0, "#1144 skills census walk found zero files"
    assert not violations, (
        "#1144 forbidden primitive outside decision block, byte-pin, or rubric exclusion. "
        "Every hit:\n" + "\n".join(sorted(set(violations)))
    )


# axis: decision block well-formedness — unique ids, matched open/close, no nesting, valid
# mode/kind/default/carrier. Not prohibition hits.
def test_decision_blocks_well_formed():
    """#1144: malformed or duplicate decision blocks are errors, not ignored (E4)."""
    _, errors = _collect_all_blocks()
    assert not errors, (
        "#1144 decision block well-formedness violations. Every hit:\n" + "\n".join(errors)
    )


# axis: no waiting token inside any decision block, any mode. Not outside-block prohibition.
def test_no_waiting_tokens_in_decision_blocks():
    """#1144: waiting tokens inside blocks contradict escalation-base.md v3."""
    hits = []
    blocks, _ = _collect_all_blocks()
    for block in blocks:
        norm_prose = _normalize_match_text(block["prose"]).casefold()
        for token in _WAITING_TOKENS:
            if token.casefold() in norm_prose:
                hits.append(
                    f"{block['rel']}:{block['open_line']}: waiting token {token!r} inside block "
                    f"id={block['id']!r}"
                )
    assert not hits, (
        "#1144 waiting token inside decision block. Every hit:\n" + "\n".join(hits)
    )


# axis: mode-specific structure per reference/decision-points.md §1a. Not carrier transport.
def test_decision_block_mode_structure():
    """#1144: gate/notify/proceed blocks must carry mode-specific disclosure prose."""
    hits = []
    blocks, _ = _collect_all_blocks()
    for block in blocks:
        hits.extend(_mode_structure_violations(block))
    assert not hits, (
        "#1144 decision block mode-structure violations. Every hit:\n" + "\n".join(hits)
    )


# axis: storage-location blocks must capture SOURCE and guard $SOURCE in block bash — shell text
# only, not carrier delivery. Not block grammar or follow-up prose.
def test_storage_decision_blocks_capture_source():
    """#1144: storage-location blocks require SOURCE capture and $SOURCE guard in block bash.

    Asserts shell text inside the block only — does not assert that any disclosure reaches any writer.
    """
    hits = []
    blocks, _ = _collect_all_blocks()
    for block in blocks:
        if block["kind"] != "storage-location":
            continue
        rel = block["rel"]
        line = block["open_line"]
        prose = block["prose"]
        bash_blocks = _fenced_bash_blocks(prose)
        if not bash_blocks:
            hits.append(
                f"{rel}:{line}: storage-location block requires a fenced bash block"
            )
            continue
        if not any(_SOURCE_CAPTURE_RE.search(b) for b in bash_blocks):
            hits.append(
                f"{rel}:{line}: storage-location block requires a SOURCE assignment from "
                "decide-location .source in its block bash"
            )
        if not any(_SOURCE_GUARD_RE.search(b) for b in bash_blocks):
            hits.append(
                f"{rel}:{line}: storage-location block usable-value guard must cover $SOURCE"
            )
    assert not hits, (
        "#1144 storage-location SOURCE capture/guard violations. Every hit:\n"
        + "\n".join(hits)
    )


# axis: every block must name /superheroes:configure follow-up — any kind, any carrier. Not bash
# shell text or carrier delivery.
def test_decision_block_names_configure_follow_up():
    """#1144: block prose must name /superheroes:configure regardless of kind or carrier."""
    hits = []
    blocks, _ = _collect_all_blocks()
    for block in blocks:
        if "/superheroes:configure" not in block["prose"]:
            hits.append(
                f"{block['rel']}:{block['open_line']}: block prose must name /superheroes:configure"
            )
    assert not hits, (
        "#1144 decision block follow-up violations. Every hit:\n" + "\n".join(hits)
    )


# --- bite-proof fixture helpers (monkeypatch _SKILLS_ROOT) ---

_VALID_BLOCK = (
    '<!-- decision-point: id=fixture-storage mode=notify kind=storage-location '
    'default="global provisional" carrier=review-crew-layer -->\n'
    "NOTIFY: take the lib default, disclose in ## Setup disclosures, run continues. "
    "Follow-up: `/superheroes:configure`.\n"
    "<!-- /decision-point: id=fixture-storage -->\n"
)


# axis: duplicate decision-point id — bite-proof element for block well-formedness.
def test_fixture_duplicate_decision_block_id_fails(tmp_path, monkeypatch):
    """#1144 bite-proof: duplicate id must fail well-formedness check."""
    monkeypatch.setattr(
        "test_decision_point_census._SKILLS_ROOT", str(tmp_path / "skills")
    )
    skills = tmp_path / "skills" / "demo"
    skills.mkdir(parents=True)
    content = (
        _VALID_BLOCK
        + '<!-- decision-point: id=fixture-storage mode=gate kind=owner-gate '
        'default="hold" carrier=audit-report -->\n'
        "GATE: write down and hand back. `/superheroes:configure`.\n"
        "<!-- /decision-point: id=fixture-storage -->\n"
    )
    (skills / "SKILL.md").write_text(content, encoding="utf-8")
    _, errors = _collect_all_blocks(str(tmp_path / "skills"))
    assert errors, "duplicate id fixture must produce well-formedness errors"


# axis: orphan close — bite-proof element for block well-formedness.
def test_fixture_orphan_close_fails(tmp_path, monkeypatch):
    """#1144 bite-proof: orphan close must fail well-formedness check."""
    monkeypatch.setattr(
        "test_decision_point_census._SKILLS_ROOT", str(tmp_path / "skills")
    )
    skills = tmp_path / "skills" / "demo"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text(
        "<!-- /decision-point: id=orphan -->\n", encoding="utf-8"
    )
    _, errors = _collect_all_blocks(str(tmp_path / "skills"))
    assert any("orphan" in e for e in errors), "orphan close fixture must be reported"


# axis: waiting token inside block — bite-proof element.
def test_fixture_waiting_token_in_block_fails(tmp_path, monkeypatch):
    """#1144 bite-proof: waiting token inside block must fail."""
    monkeypatch.setattr(
        "test_decision_point_census._SKILLS_ROOT", str(tmp_path / "skills")
    )
    skills = tmp_path / "skills" / "demo"
    skills.mkdir(parents=True)
    content = (
        '<!-- decision-point: id=wait-test mode=gate kind=owner-gate default="hold" '
        'carrier=audit-report -->\n'
        "GATE: write down, hand back, and wait for the owner. `/superheroes:configure`.\n"
        "<!-- /decision-point: id=wait-test -->\n"
    )
    (skills / "SKILL.md").write_text(content, encoding="utf-8")
    blocks, _ = _collect_all_blocks(str(tmp_path / "skills"))
    hits = []
    for block in blocks:
        norm_prose = _normalize_match_text(block["prose"]).casefold()
        for token in _WAITING_TOKENS:
            if token.casefold() in norm_prose:
                hits.append(token)
    assert hits, "waiting-token fixture must be detected inside block"


# axis: storage-location block without fenced bash — exercises the shipped B1 fenced-bash check.
def test_fixture_storage_block_without_bash_fails(tmp_path, monkeypatch):
    """#1144 bite-proof: storage-location block without fenced bash must fail B1."""
    monkeypatch.setattr(
        "test_decision_point_census._SKILLS_ROOT", str(tmp_path / "skills")
    )
    skills = tmp_path / "skills" / "demo"
    skills.mkdir(parents=True)
    content = (
        '<!-- decision-point: id=storage-no-bash mode=notify kind=storage-location '
        'default="global" carrier=review-crew-layer -->\n'
        "NOTIFY: continues. `/superheroes:configure`.\n"
        "<!-- /decision-point: id=storage-no-bash -->\n"
    )
    (skills / "SKILL.md").write_text(content, encoding="utf-8")
    with pytest.raises(AssertionError, match="requires a fenced bash block"):
        test_storage_decision_blocks_capture_source()


# axis: E3 empty walk — bite-proof element (monkeypatch skills root to empty dir).
def test_fixture_empty_skills_walk_fails(tmp_path, monkeypatch):
    """#1144 bite-proof: zero files under skills/ must fail the shipped walk guard."""
    empty = tmp_path / "skills"
    empty.mkdir()
    monkeypatch.setattr("test_decision_point_census._SKILLS_ROOT", str(empty))
    with pytest.raises(AssertionError, match="zero files"):
        test_skills_census_walk_non_empty()


# axis: prohibition census green on fixture with wrapped primitive — bite-proof inverted proof.
def test_fixture_wrapped_primitive_passes_prohibition(tmp_path, monkeypatch):
    """#1144 bite-proof: a primitive inside a valid block must not appear in violations."""
    monkeypatch.setattr(
        "test_decision_point_census._SKILLS_ROOT", str(tmp_path / "skills")
    )
    skills = tmp_path / "skills" / "demo"
    skills.mkdir(parents=True)
    content = (
        '<!-- decision-point: id=storage mode=notify kind=storage-location '
        'default="provisional global" carrier=review-crew-layer -->\n'
        'DEC=$(python3 store.py decide-location) || exit 1\n'
        "## Setup disclosures\n"
        "$REVIEW_LAYER_BODY piped to write-layer --hero review-crew\n"
        "NOTIFY: continues after disclosure. `/superheroes:configure`.\n"
        "<!-- /decision-point: id=storage -->\n"
    )
    (skills / "SKILL.md").write_text(content, encoding="utf-8")
    violations, file_count = _scan_forbidden_violations(str(tmp_path / "skills"))
    assert file_count == 1
    assert not violations, "wrapped decide-location) must not violate prohibition"


# axis: prohibition census red when block removed — bite-proof inverted proof complement.
def test_fixture_unwrapped_primitive_fails_prohibition(tmp_path, monkeypatch):
    """#1144 bite-proof: primitive outside block must appear in violations."""
    monkeypatch.setattr(
        "test_decision_point_census._SKILLS_ROOT", str(tmp_path / "skills")
    )
    skills = tmp_path / "skills" / "demo"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text(
        'DEC=$(python3 store.py decide-location) || exit 1\n', encoding="utf-8"
    )
    violations, _ = _scan_forbidden_violations(str(tmp_path / "skills"))
    assert violations, "unwrapped decide-location) must violate prohibition"


# axis: disclosure mention must not false-positive — bite-proof element for normalization.
def test_fixture_disclosure_mention_no_violation(tmp_path, monkeypatch):
    """#1144 bite-proof: disclosure prose mentioning decide-location must not violate."""
    monkeypatch.setattr(
        "test_decision_point_census._SKILLS_ROOT", str(tmp_path / "skills")
    )
    skills = tmp_path / "skills" / "demo"
    skills.mkdir(parents=True)
    content = (
        "**Storage location (`decide-location`).** `decide-location` returns JSON: "
        "`.mode` is `in-repo` or `global`.\n"
    )
    (skills / "SKILL.md").write_text(content, encoding="utf-8")
    violations, file_count = _scan_forbidden_violations(str(tmp_path / "skills"))
    assert file_count == 1
    assert not violations, (
        "disclosure mention of decide-location must not violate prohibition"
    )


# axis: real invocation must still violate — bite-proof complement for normalization.
def test_fixture_real_invocation_violates(tmp_path, monkeypatch):
    """#1144 bite-proof: bare decide-location) invocation must violate."""
    monkeypatch.setattr(
        "test_decision_point_census._SKILLS_ROOT", str(tmp_path / "skills")
    )
    skills = tmp_path / "skills" / "demo"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text(
        'DEC=$(python3 store.py decide-location) || exit 1\n', encoding="utf-8"
    )
    violations, _ = _scan_forbidden_violations(str(tmp_path / "skills"))
    assert any("decide-location)" in v for v in violations), (
        "bare decide-location) invocation must violate prohibition"
    )


# axis: multi-line literal attributed to match-start line — bite-proof element for offset search.
def test_fixture_multiline_literal_start_line(tmp_path, monkeypatch):
    """#1144 bite-proof: cross-line primitive attributed to line where match starts."""
    monkeypatch.setattr(
        "test_decision_point_census._SKILLS_ROOT", str(tmp_path / "skills")
    )
    skills = tmp_path / "skills" / "demo"
    skills.mkdir(parents=True)
    content = (
        "Present drift to the user and apply\n"
        "only what they approve. Hand-edits preserved.\n"
    )
    (skills / "SKILL.md").write_text(content, encoding="utf-8")
    violations, _ = _scan_forbidden_violations(str(tmp_path / "skills"))
    assert len(violations) == 1, f"expected single hit, got {violations!r}"
    assert violations[0].endswith(":2: only what they approve"), (
        f"expected hit on line 2, got {violations[0]!r}"
    )
