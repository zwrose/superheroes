# plugins/superheroes/lib/tests/test_acceptance_cleanup.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_fixture as af
import acceptance_cleanup as cl

STAMP = af.make_stamp("run-1")
OTHER = af.make_stamp("run-2")


def test_empty_input_is_empty_plan_idempotent():
    p = cl.plan([], run_stamp=STAMP)
    assert p["reap"] == [] and p["leave_behind"] == []


def test_matching_full_stamp_is_reaped():
    arts = [{"kind": "branch", "name": "wi-%s" % STAMP},
            {"kind": "pr", "name": "PR: %s fixture" % STAMP}]
    p = cl.plan(arts, run_stamp=STAMP)
    assert {a["name"] for a in p["reap"]} == {a["name"] for a in arts}
    assert p["leave_behind"] == []


def test_reserved_prefix_but_unparseable_is_left_behind_never_reaped():
    arts = [{"kind": "branch", "name": af.RESERVED_PREFIX + "!!garbage"}]
    p = cl.plan(arts, run_stamp=None)
    assert p["reap"] == []
    assert len(p["leave_behind"]) == 1


def test_other_runs_stamp_is_not_reaped_when_run_stamp_pinned():
    arts = [{"kind": "branch", "name": "wi-%s" % OTHER}]
    p = cl.plan(arts, run_stamp=STAMP)
    assert p["reap"] == []


def test_recordless_discovery_reaps_any_valid_full_stamp():
    arts = [{"kind": "branch", "name": "wi-%s" % OTHER}]
    p = cl.plan(arts, run_stamp=None)   # UFR-8: parse each independently
    assert {a["name"] for a in p["reap"]} == {"wi-%s" % OTHER}


def test_non_harness_artifact_is_ignored_never_reaped_or_left():
    arts = [{"kind": "branch", "name": "feature/real-owner-work"}]
    p = cl.plan(arts, run_stamp=None)
    assert p["reap"] == [] and p["leave_behind"] == []
