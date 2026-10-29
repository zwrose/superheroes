"""The test reviewer's contract in agents/test-role.md: one test per clause, by a short phrase.

A census of the contract, not a wording pin of whole paragraphs: each test asserts that the
phrase quoted in it is present, so deleting the clause turns that test red.
"""
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
TEST_ROLE = (PLUGIN / "agents" / "test-role.md").read_text(encoding="utf-8")
AUTO_FIX_LOOP = (
    PLUGIN / "skills" / "review-code" / "reference" / "auto-fix-loop.md"
).read_text(encoding="utf-8")


def _section(text, heading):
    """The text from `## <heading>` up to the next `## ` heading."""
    start = text.index("## " + heading + "\n")
    end = text.find("\n## ", start + 1)
    return text[start:] if end == -1 else text[start:end]


def test_attached_break_it_test_on_each_provable_finding():
    # axis: an attached break-it test is asked for on each finding the reviewer can prove that way
    phrase = "On any finding you can prove that way, attach a test"
    assert phrase in TEST_ROLE


def test_per_area_tests_are_capped_at_three_per_review():
    # axis: per-area break-it tests are capped at three per review
    assert "Write at most three per review" in TEST_ROLE


def test_at_least_one_per_touched_area_while_under_the_cap():
    # axis: while under the cap each touched risk area gets at least one per-area test
    assert "While under that cap, write at least one per touched area" in TEST_ROLE


def test_the_cap_counts_only_per_area_tests():
    # axis: attached tests and a second test the loop asks for later do not count against the cap
    assert "The cap counts only per-area tests" in TEST_ROLE


def test_each_per_area_test_is_delivered_as_a_finding():
    # axis: a per-area break-it test reaches the loop as its own finding, never as a written file
    assert "delivered as its own finding" in TEST_ROLE


def test_the_build_session_never_writes_a_break_it_test():
    # axis: the build session's only edit to a reviewer's test is the small change, never authorship
    assert "The build session never writes a break-it test" in TEST_ROLE


def test_a_break_it_test_writes_only_inside_its_own_temporary_folder():
    # axis: the contract tells the reviewer a break-it test never touches a checkout file it did not create
    assert ("writes only inside its own temporary folder, and never changes or deletes a file in the "
            "checkout that it did not create") in TEST_ROLE


def test_no_throwaway_copy_or_drop_on_pass_in_the_break_it_text():
    # axis: the retired throwaway-copy run and the drop-on-pass rule stay out of both docs
    role_section = _section(TEST_ROLE, "Break-it tests")
    loop_section = _section(AUTO_FIX_LOOP, "Break-it tests")
    for name, text in (("test-role.md", role_section), ("auto-fix-loop.md", loop_section)):
        assert "throwaway" not in text, name
        assert "drops that finding" not in text, name
    assert "drops that finding" not in TEST_ROLE


def test_fr12_priority_checks_and_do_not_flag_rules():
    # axis: the FR-12 checks: chance (flaky), cannot-fail, fix with no failing test, bloat, no
    # coverage asked in low-risk code, no style preference flagged
    for phrase in (
        "which covers flaky tests too",
        "**Tests that cannot fail.**",
        "**A fix with no test that would fail.**",
        "**Test bloat.**",
        "No coverage is asked for in low-risk code",
        "No test style preference is flagged",
    ):
        assert phrase in TEST_ROLE, phrase
