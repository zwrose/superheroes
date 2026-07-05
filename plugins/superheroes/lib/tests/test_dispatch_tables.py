"""Structural guard: per-agent dispatch tables and prose enumerations stay in
sync with the bundled agents and the rubric's dimension list.

- review-plan and review-code dispatch every bundled REVIEWER agent: their
  substitution tables have exactly one row per `*-reviewer` file in agents/, and
  their "Specialists to dispatch" prose enumerations name every reviewer slug.
  Internal non-reviewer leaf agents (e.g. `courier`, the showrunner spine's
  command pipe) are NOT review specialists and are excluded.
- audit-debt intentionally dispatches only the ORIGINAL FOUR (Failure-Mode
  whole-repo sweep deferred) — guarded here so a four->five sweep cannot
  silently change it.
- Every dimension label used in a table row appears backticked in the rubric's
  Dimensions declaration.
- The reviewer roster re-typed in code (showrunner.js REVIEW_CODE_REVIEWERS /
  DOC_REVIEWERS, code_loop_plan/spec_loop_plan DIMENSIONS) matches the same
  agents/ home — a CONVENTIONS §11 single-source-of-truth drift guard, fail-closed
  so a renamed literal cannot pass vacuously.
"""
import ast
import os
import re

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, "..", ".."))

ORIGINAL_FOUR = {
    "architecture-reviewer", "code-reviewer", "security-reviewer", "test-reviewer",
}

ROW_RE = re.compile(
    r"^\|\s*([a-z][a-z-]*-reviewer)\s*\|\s*([a-z-]+)\s*\|\s*([A-Za-z-]+)\s*\|",
    re.M)


def _read(rel):
    with open(os.path.join(PLUGIN, rel)) as f:
        return f.read()


def _agent_slugs():
    # The review dispatch tables/prose enumerate the review SPECIALISTS — the panel of
    # `*-reviewer` agents. Internal non-reviewer leaf agents (e.g. `courier`) live in agents/
    # too but are never a review dimension, so scope this to the `-reviewer` panel.
    adir = os.path.join(PLUGIN, "agents")
    return {fn[:-3] for fn in os.listdir(adir) if fn.endswith(".md") and fn[:-3].endswith("-reviewer")}


def _table_rows(rel):
    return ROW_RE.findall(_read(rel))


def _parse_js_const_str_list(text, name, label):
    """Fail-closed core of `_js_const_str_list` (CONVENTIONS §11.2).

    A hand-maintained copy of a cross-boundary fact is only safe if its drift test
    *fails closed* — parsing nothing must raise, never return an empty list that
    makes the downstream equality assertion vacuously pass. So this asserts exactly
    one match and a non-empty string list before returning. A reformat the regex
    cannot read (an inline comment inside the brackets, a `new Set([...])` / `.concat`
    wrapper, a nested array) also raises here — a hard, honest CI failure, never a
    false clean.
    """
    matches = re.findall(r"^const\s+%s\s*=\s*(\[[^\]]+\])" % re.escape(name), text, re.M)
    assert len(matches) == 1, (
        "%s: expected exactly one plain `const %s = [...]` string-array literal, found "
        "%d (a rename, or a reformat the drift parser can't read — inline comment, "
        "Set/concat wrapper)" % (label, name, len(matches)))
    value = ast.literal_eval(matches[0])
    assert isinstance(value, list) and value and all(
        isinstance(x, str) and x for x in value), (
        "%s: `%s` must be a non-empty list of strings" % (label, name))
    return value


def _js_const_str_list(rel, name):
    """Fail-closed read of `const NAME = [ ... ]` from a JS source file (§11.2)."""
    return _parse_js_const_str_list(_read(rel), name, rel)


def test_code_reviewer_rosters_match_bundled_agents():
    """CONVENTIONS §11: the reviewer roster is a cross-boundary fact re-typed as a
    hand-maintained copy in JS (`showrunner.js` REVIEW_CODE_REVIEWERS / DOC_REVIEWERS)
    and Python (`code_loop_plan` / `spec_loop_plan` DIMENSIONS, and the same roster
    re-keyed as AGENT_SUFFIX). The authoritative home is the set of `agents/*-reviewer`
    files; each copy must equal it, so adding/removing/renaming a reviewer breaks CI in
    every enumerated copy-holder rather than letting them silently diverge (the PR #205
    class). This enumeration is only as complete as the copies listed below — a NEW copy
    must be added here (see the §11.2 caveat). The generated `showrunner.bundle.js` copy
    is guarded separately by test_bundle_drift.
    """
    home = _agent_slugs()

    import code_loop_plan
    import spec_loop_plan
    js = os.path.join("lib", "showrunner.js")
    rosters = {
        "showrunner.js REVIEW_CODE_REVIEWERS": _js_const_str_list(js, "REVIEW_CODE_REVIEWERS"),
        "showrunner.js DOC_REVIEWERS": _js_const_str_list(js, "DOC_REVIEWERS"),
        "code_loop_plan.DIMENSIONS": list(code_loop_plan.DIMENSIONS),
        "spec_loop_plan.DIMENSIONS": list(spec_loop_plan.DIMENSIONS),
        # AGENT_SUFFIX is the same roster re-keyed — its keys are a copy too.
        "code_loop_plan.AGENT_SUFFIX": list(code_loop_plan.AGENT_SUFFIX),
        "spec_loop_plan.AGENT_SUFFIX": list(spec_loop_plan.AGENT_SUFFIX),
    }
    for label, roster in rosters.items():
        # duplicate-sensitive: set() alone would let a copy that duplicates one slug
        # while dropping another pass (sizes coincide once the set collapses the dup).
        assert len(roster) == len(set(roster)), "%s has a duplicate entry: %r" % (label, roster)
        assert set(roster) == home, "%s drifted from the agents/*-reviewer home" % label


@pytest.mark.parametrize("text, name, match", [
    # literal renamed / removed → zero matches
    ("const OTHER = ['a', 'b']\n", "REVIEWERS", "expected exactly one"),
    # literal declared twice → ambiguous, refuse
    ("const R = ['a']\nconst R = ['b']\n", "R", "found 2"),
    # a non-string element → not a plain string-array
    ("const R = ['a', 2]\n", "R", "non-empty list of strings"),
    # an empty-string element → not a non-empty string
    ("const R = ['a', '']\n", "R", "non-empty list of strings"),
])
def test_js_const_str_list_fails_closed(text, name, match):
    """§11.2: the drift reader must RAISE (not return a partial/empty list) on every
    shape that isn't exactly one plain string-array — otherwise the equality assertion
    that guards each roster copy could pass vacuously. Mirrors the canonical Pattern-2
    reference's fail-closed tests (test_acceptance_fixture.py)."""
    with pytest.raises(AssertionError, match=match):
        _parse_js_const_str_list(text, name, "<test>")


def _rubric_dimensions():
    text = _read(os.path.join("rubric", "review-base.md"))
    m = re.search(r"\*\*Dimensions\*\*.*?:\s*(`[A-Za-z-]+`(?:,\s*`[A-Za-z-]+`)*)", text, re.S)
    assert m, "rubric Dimensions declaration not found"
    return set(re.findall(r"`([A-Za-z-]+)`", m.group(1)))


@pytest.mark.parametrize("skill", ["review-plan", "review-code", "review-spec", "review-tasks"])
def test_full_crew_table_has_one_row_per_agent(skill):
    rows = _table_rows(os.path.join("skills", skill, "SKILL.md"))
    expected_set = _agent_slugs()
    slugs = [slug for slug, _, _ in rows]
    assert sorted(slugs) == sorted(expected_set)


def test_audit_debt_table_lists_exactly_the_original_four():
    rows = _table_rows(os.path.join("skills", "audit-debt", "SKILL.md"))
    slugs = [slug for slug, _, _ in rows]
    assert sorted(slugs) == sorted(ORIGINAL_FOUR)


@pytest.mark.parametrize("skill,expected_slugs", [
    ("review-plan", "ALL"),
    ("review-code", "ALL"),
    ("review-spec", "ALL"),
    ("review-tasks", "ALL"),
    ("audit-debt", "FOUR"),
])
def test_specialists_to_dispatch_prose_enumeration(skill, expected_slugs):
    text = _read(os.path.join("skills", skill, "SKILL.md"))
    want = _agent_slugs() if expected_slugs == "ALL" else ORIGINAL_FOUR
    enumerated = set(re.findall(r"^\s*-\s*`([a-z][a-z-]*-reviewer)`\s*→", text, re.M))
    assert enumerated == want


@pytest.mark.parametrize("skill", ["review-plan", "review-code", "review-spec", "review-tasks", "audit-debt"])
def test_table_dimensions_exist_in_rubric(skill):
    dims = _rubric_dimensions()
    for slug, _findings, dimension in _table_rows(os.path.join("skills", skill, "SKILL.md")):
        assert dimension in dims, f"{skill}: {slug} row uses unknown dimension {dimension}"
