import validate_skills as vs

def test_line_count_passes_at_or_under_ceiling():
    # ceiling = max allowed (inclusive): 499 for "under 500" skills
    assert vs.check_line_count("review-crew/review-code", 499, {"review-crew/review-code": 499}) == []

def test_line_count_fails_over_ceiling():
    out = vs.check_line_count("review-crew/review-code", 500, {"review-crew/review-code": 499})
    assert out and "line-count" in out[0] and "review-crew/review-code" in out[0]

def test_line_count_ignores_skills_without_a_ceiling():
    assert vs.check_line_count("test-pilot/test-pilot-plan", 700, {"review-crew/review-code": 499}) == []
