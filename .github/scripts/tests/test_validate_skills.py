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

def test_line_count_passes_at_or_under_ceiling():
    # ceiling = max allowed (inclusive): 499 for "under 500" skills
    assert vs.check_line_count("review-crew/review-code", 499, {"review-crew/review-code": 499}) == []

def test_line_count_fails_over_ceiling():
    out = vs.check_line_count("review-crew/review-code", 500, {"review-crew/review-code": 499})
    assert out and "line-count" in out[0] and "review-crew/review-code" in out[0]

def test_line_count_ignores_skills_without_a_ceiling():
    assert vs.check_line_count("test-pilot/test-pilot-plan", 700, {"review-crew/review-code": 499}) == []
