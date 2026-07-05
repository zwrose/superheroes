# plugins/superheroes/lib/tests/test_acceptance_fixture.py
import os, sys, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_fixture as af
import acceptance_deps as deps

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


def test_fixture_expected_phases_match_showrunner_source_of_truth():
    phases = deps.real_expected_phases()()
    assert af.expected_phases(FIXTURE) == phases
    assert "review-plan" in phases
    assert "workhorse" in phases
    assert "review" not in phases


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
