import validate_skills as vs

def test_links_resolve(tmp_path):
    (tmp_path / "rubric").mkdir()
    (tmp_path / "rubric" / "review-base.md").write_text("x")
    text = "Read the base rubric (`${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/rubric/review-base.md`)."
    assert vs.check_links("p/s", text, str(tmp_path)) == []

def test_links_flag_missing_target(tmp_path):
    text = "See `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/rubric/gone.md`."
    out = vs.check_links("p/s", text, str(tmp_path))
    assert out and "reference-link" in out[0] and "gone.md" in out[0]

# Fix A: directory targets must NOT be flagged
def test_links_accept_directory_target(tmp_path):
    (tmp_path / "lib").mkdir()
    text = 'LIB="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/lib"'
    assert vs.check_links("p/s", text, str(tmp_path)) == []

# Fix B: allowlist suppresses known sentinel references
def test_links_allowlist_suppresses_sentinel(tmp_path):
    # missing file IS flagged when not in allowlist
    text = "See `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/lib/loop_state.py`."
    out = vs.check_links("p/s", text, str(tmp_path))
    assert out and "reference-link" in out[0]

def test_gather_allowlist_suppresses_sentinel(tmp_path):
    root = str(tmp_path / "plugins"); os.makedirs(root)
    body = (
        "---\nname: workhorse\ndescription: Use when build tasks should run\n---\n"
        "LIB=\"${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/lib/loop_state.py\"\n"
    )
    d = os.path.join(root, "workhorse", "skills", "workhorse")
    os.makedirs(d)
    with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as fh:
        fh.write(body)
    reg = {"bodyCeilings": {}, "requiredPhrases": {}}

    # Without allowlist: violation present
    errors, _ = vs.gather_violations(root, reg, set(), set())
    assert any("reference-link" in e and "loop_state.py" in e for e in errors)

    # With allowlist: violation suppressed
    errors2, _ = vs.gather_violations(root, reg, set(), set(),
                                      allowed_unresolved={"workhorse/workhorse:lib/loop_state.py"})
    assert not any("loop_state.py" in e for e in errors2)

def test_conventions_section_numbers_and_refs():
    conv = "## 1. Vocabulary\n## 3. Definition docs\n### 3.1 Frontmatter\n"
    secs = vs.conventions_section_numbers(conv)
    assert "3" in secs and "3.1" in secs
    # validate only CONVENTIONS-qualified citations; bare "§N" is an ambiguous
    # internal cross-ref (skills use §N for their own sections too) and is NOT checked
    assert vs.check_conventions_refs("p/s", "see CONVENTIONS §3.1 and CONVENTIONS §3", secs) == []
    bad = vs.check_conventions_refs("p/s", "see CONVENTIONS §9.9", secs)
    assert bad and "conventions-ref" in bad[0] and "9.9" in bad[0]
    # a bare internal "§12" (not a CONVENTIONS citation) must NOT be flagged
    assert vs.check_conventions_refs("p/s", "see internal section §12 above", secs) == []

def test_depth_ok_when_reference_has_no_further_refs(tmp_path):
    (tmp_path / "reference").mkdir()
    (tmp_path / "reference" / "a.md").write_text("leaf content, no further refs")
    text = "See `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/reference/a.md`."
    assert vs.check_depth("p/s", text, str(tmp_path)) == []

def test_depth_flags_a_chain(tmp_path):
    (tmp_path / "reference").mkdir()
    (tmp_path / "reference" / "a.md").write_text(
        "more at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/reference/b.md`")
    text = "See `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/reference/a.md`."
    out = vs.check_depth("p/s", text, str(tmp_path))
    assert out and "reference-depth" in out[0]

def test_depth_ignores_unresolved_target_that_is_check_links_job(tmp_path):
    # a reference to a missing file is NOT a depth violation (resolution is check_links')
    text = "See `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/reference/missing.md`."
    assert vs.check_depth("p/s", text, str(tmp_path)) == []

def test_depth_deduplicates_same_reference(tmp_path):
    """Citing the same chained reference file twice yields exactly ONE violation."""
    (tmp_path / "reference").mkdir()
    (tmp_path / "reference" / "a.md").write_text(
        "more at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/reference/b.md`")
    # Reference a.md twice in the body
    text = (
        "First `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/reference/a.md`. "
        "Second `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/reference/a.md`."
    )
    out = vs.check_depth("p/s", text, str(tmp_path))
    depth_violations = [v for v in out if "reference-depth" in v]
    assert len(depth_violations) == 1, f"Expected 1 violation, got {len(depth_violations)}: {depth_violations}"

def test_toc_not_required_under_100_lines(tmp_path):
    f = tmp_path / "short.md"; f.write_text("# X\n\nbody\n")
    assert vs.check_toc(str(f)) == []

def test_toc_required_over_100_lines(tmp_path):
    f = tmp_path / "long.md"; f.write_text("# X\n\n" + "line\n" * 120)
    out = vs.check_toc(str(f))
    assert out and "table-of-contents" in out[0]

def test_toc_satisfied_by_contents_heading(tmp_path):
    f = tmp_path / "long.md"
    f.write_text("<!-- review-loop-version: 1 -->\n## Contents\n\n- a\n" + "line\n" * 120)
    assert vs.check_toc(str(f)) == []

def test_toc_fenced_code_comment_not_mistaken_for_heading(tmp_path):
    """A ```bash block with a # comment before ## Contents must NOT be flagged."""
    f = tmp_path / "long.md"
    # Open with a fenced bash block that contains a shell comment, then the real Contents heading
    body = "```bash\n# this is a shell comment, not a heading\n```\n\n## Contents\n\n- item\n"
    body += "line\n" * 120
    f.write_text(body)
    assert vs.check_toc(str(f)) == []

def test_phrases_present():
    assert vs.check_phrases("p/s", "Use when reviewing code changes on a branch", ["reviewing code changes"]) == []

def test_phrases_missing_is_flagged():
    out = vs.check_phrases("p/s", "Use when reviewing things", ["reviewing code changes"])
    assert out and "trigger-phrase" in out[0] and "reviewing code changes" in out[0]

def test_line_count_passes_at_or_under_ceiling():
    # ceiling = max allowed (inclusive): 499 for "under 500" skills
    assert vs.check_line_count("review-crew/review-code", 499, {"review-crew/review-code": 499}) == []

def test_line_count_fails_over_ceiling():
    out = vs.check_line_count("review-crew/review-code", 500, {"review-crew/review-code": 499})
    assert out and "line-count" in out[0] and "review-crew/review-code" in out[0]

def test_line_count_ignores_skills_without_a_ceiling():
    assert vs.check_line_count("test-pilot/test-pilot-plan", 700, {"review-crew/review-code": 499}) == []

import os

def _mk_skill(root, plugin, skill, body_lines, desc="Use when reviewing code changes"):
    d = os.path.join(root, plugin, "skills", skill)
    os.makedirs(d)
    with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as fh:
        fh.write(f"---\nname: {skill}\ndescription: {desc}\n---\n" + "x\n" * body_lines)

def test_known_red_suppresses_line_count_in_set():
    assert vs.known_red_ceilings({"knownRedCeilings": ["review-crew/review-code"]}) == {"review-crew/review-code"}

def test_gather_names_line_count_violation(tmp_path):
    root = str(tmp_path / "plugins"); os.makedirs(root)
    _mk_skill(root, "review-crew", "review-code", 600)
    reg = {"bodyCeilings": {"review-crew/review-code": 499}, "requiredPhrases": {}}
    errors, _ = vs.gather_violations(root, reg, set(), set())
    assert any("line-count: review-crew/review-code" in e for e in errors)

def test_gather_known_red_suppresses_the_line_count(tmp_path):
    root = str(tmp_path / "plugins"); os.makedirs(root)
    _mk_skill(root, "review-crew", "review-code", 600)
    reg = {"bodyCeilings": {"review-crew/review-code": 499}, "requiredPhrases": {}}
    errors, _ = vs.gather_violations(root, reg, {"review-crew/review-code"}, set())
    assert not any("line-count" in e for e in errors)

def test_gather_combined_size_flags_not_smaller(tmp_path):
    root = str(tmp_path / "plugins"); os.makedirs(root)
    _mk_skill(root, "p", "s", 10, desc="x" * 50)
    errors, combined = vs.gather_violations(root, {"bodyCeilings": {}, "requiredPhrases": {}},
                                            set(), set(), combined_before=10)
    assert combined == 50 and any("description-size" in e for e in errors)
