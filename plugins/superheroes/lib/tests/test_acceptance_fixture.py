# plugins/superheroes/lib/tests/test_acceptance_fixture.py
import os, sys, tempfile, shutil
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_fixture as af
import acceptance_deps as deps
import acceptance_phases

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "..", "eval", "fixtures", "acceptance")


def test_reserved_prefix_and_full_stamp_roundtrip():
    stamp = af.make_stamp("abc123")
    assert stamp.startswith(af.RESERVED_PREFIX)
    assert af.parse_stamp("wi-%s-branch" % stamp) == stamp
    assert af.parse_stamp(stamp) == stamp


def test_bare_prefix_that_is_not_a_full_stamp_does_not_parse():
    # a prefix match that is NOT a full structurally-valid stamp must return None
    # (cleanup routes it to the reported-left-behind path, never a delete).
    assert af.parse_stamp(af.RESERVED_PREFIX) is None
    assert af.parse_stamp(af.RESERVED_PREFIX + "!!not-a-valid-id") is None


def test_two_materializations_never_collide():
    store = tempfile.mkdtemp()
    try:
        a = af.materialize("id-one", FIXTURE, store)
        b = af.materialize("id-two", FIXTURE, store)
        assert a["work_item"] != b["work_item"]
        assert a["branch"] != b["branch"]
        assert a["pr_title"] != b["pr_title"]
        # the materialized tasks doc carries a passed review gate so preflight admits it
        tasks = os.path.join(store, a["work_item"], "tasks.md")
        assert os.path.isfile(tasks)
        assert "gates: {review: passed}" in open(tasks).read()
    finally:
        shutil.rmtree(store, ignore_errors=True)


def test_drift_check_passes_when_phases_match_and_target_exists():
    # the committed fixture declares expected_phases; feed the same list.
    phases = af.expected_phases(FIXTURE)
    res = af.drift_check(FIXTURE, pipeline_phases=phases, target_exists=True)
    assert res["ok"] is True


def test_committed_fixture_target_is_one_newline_terminated_line():
    # #419: the fixture-dir target.txt is the ONLY source of the seeded baseline the tasks
    # doc copies onto the branch; its steps assert `wc -l` == 1 pre-append and == 2 after.
    # A second line or a lost trailing newline would corrupt the append mid-run, deep in a
    # paid acceptance run — pin the shape here instead.
    p = os.path.join(FIXTURE, "target.txt")
    assert os.path.isfile(p)
    body = open(p, encoding="utf-8").read()
    assert body.endswith("\n")
    assert body.count("\n") == 1


def test_materialize_copies_target_alongside_docs():
    # #419: the tasks doc's seed step reads target.txt from the SAME directory as the
    # materialized docs — materialize() silently skips a missing source (os.path.isfile
    # guard), so assert the copy actually lands and is reported in paths.
    store = tempfile.mkdtemp()
    try:
        out = af.materialize("target-copy-check", FIXTURE, store)
        assert any(p.endswith("target.txt") for p in out["paths"])
        assert os.path.isfile(os.path.join(store, out["work_item"], "target.txt"))
    finally:
        shutil.rmtree(store, ignore_errors=True)


def test_fixture_tasks_doc_seeds_its_own_baseline():
    # #419: the branch carries no target.txt; the tasks doc must keep seeding it from the
    # doc-adjacent copy. Pin the executable seed mechanics (not prose) so a future edit
    # cannot silently revert to the pre-#419 false premise ("modify the existing tracked
    # file") that strict spec-compliance reviewers correctly fail.
    text = open(os.path.join(FIXTURE, "tasks.md"), encoding="utf-8").read()
    assert 'cp "$TASKS_DOC_DIR/target.txt" target.txt' in text
    assert "Task-Id: 1" in text


def test_fixture_expected_phases_match_showrunner_source_of_truth():
    phases = deps.real_expected_phases()()
    assert af.expected_phases(FIXTURE) == phases
    assert "review-plan" in phases
    assert "workhorse" in phases
    assert "review" not in phases


def test_pipeline_phase_reader_ignores_commented_decoy_literal(tmp_path):
    source = tmp_path / "showrunner.js"
    source.write_text(
        "// const PHASES = ['fake']\n"
        "const PHASES = ['plan', 'review-plan', 'ship']\n",
        encoding="utf-8",
    )

    assert acceptance_phases.read_pipeline_phases(str(source)) == [
        "plan", "review-plan", "ship",
    ]


def test_pipeline_phase_reader_fails_closed_when_literal_declared_twice(tmp_path):
    source = tmp_path / "showrunner.js"
    source.write_text(
        "const PHASES = ['plan']\n"
        "const PHASES = ['ship']\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="multiple"):
        acceptance_phases.read_pipeline_phases(str(source))


def test_pipeline_phase_reader_fails_closed_when_literal_missing(tmp_path):
    source = tmp_path / "showrunner.js"
    source.write_text("const OTHER = ['plan']\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="not found"):
        acceptance_phases.read_pipeline_phases(str(source))


def test_pipeline_phase_reader_fails_closed_when_literal_unparseable(tmp_path):
    source = tmp_path / "showrunner.js"
    source.write_text("const PHASES = [plan]\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="not parseable"):
        acceptance_phases.read_pipeline_phases(str(source))


def test_pipeline_phase_reader_fails_closed_when_literal_is_not_string_list(tmp_path):
    source = tmp_path / "showrunner.js"
    source.write_text("const PHASES = ['plan', 1]\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="non-empty string list"):
        acceptance_phases.read_pipeline_phases(str(source))


def test_drift_check_fails_on_phase_list_drift():
    res = af.drift_check(FIXTURE, pipeline_phases=["only-one-phase"], target_exists=True)
    assert res["ok"] is False
    assert "phase" in res["reason"].lower()


def test_drift_check_fails_on_missing_target():
    phases = af.expected_phases(FIXTURE)
    res = af.drift_check(FIXTURE, pipeline_phases=phases, target_exists=False)
    assert res["ok"] is False
    assert "target" in res["reason"].lower()


def test_drift_check_fails_on_absent_fixture():
    res = af.drift_check("/no/such/fixture/dir", pipeline_phases=["x"], target_exists=True)
    assert res["ok"] is False
    assert "fixture" in res["reason"].lower()
