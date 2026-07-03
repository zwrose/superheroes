# plugins/superheroes/lib/tests/test_build_state.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import build_state as bs


def test_parse_trailers_maps_valid_and_counts_unmapped():
    rows = [("sha1", "task 1\n\nTask-Id: 1"), ("sha2", "no trailer"), ("sha3", "Task-Id: 99"),
            ("sha4", "task 2\n\nTask-Id: 2")]
    committed, unmapped = bs.parse_trailers(rows, {"1", "2"})
    assert committed == ["1", "2"]      # only ids in valid_ids
    assert unmapped == 2                # no trailer + unknown id "99"


def test_parse_trailers_live_shape_task_id_before_co_authored_by():
    # Git trailer-block-strict would miss Task-Id here; body parse must still map.
    body = (
        "feat: implement task 1\n"
        "\n"
        "Task-Id: 1\n"
        "\n"
        "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>\n"
    )
    committed, unmapped = bs.parse_trailers([("sha", body)], {"1"})
    assert committed == ["1"]
    assert unmapped == 0


def test_parse_trailers_proper_adjacent_trailer_block():
    body = (
        "feat: implement task 1\n"
        "\n"
        "Task-Id: 1\n"
        "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>\n"
    )
    committed, unmapped = bs.parse_trailers([("sha", body)], {"1"})
    assert committed == ["1"]
    assert unmapped == 0


def test_parse_trailers_no_task_id_is_unmapped():
    committed, unmapped = bs.parse_trailers([("sha", "feat: no trailer\n")], {"1"})
    assert committed == []
    assert unmapped == 1


def test_parse_trailers_conflicting_task_ids_are_unmapped():
    body = "feat: mixed\n\nTask-Id: 1\n\nMore work\n\nTask-Id: 2\n"
    committed, unmapped = bs.parse_trailers([("sha", body)], {"1", "2"})
    assert committed == []
    assert unmapped == 1


def test_parse_trailers_duplicate_same_task_id_maps_once():
    body = "feat: wip\n\nTask-Id: 1\n\nTask-Id: 1\n"
    committed, unmapped = bs.parse_trailers([("sha", body)], {"1"})
    assert committed == ["1"]
    assert unmapped == 0


def test_engine_adapter_commit_message_maps():
    from engine_adapter import TASK_ID_TRAILER
    body = "build: apply external-engine change\n\n%s: task-42\n" % TASK_ID_TRAILER
    committed, unmapped = bs.parse_trailers([("sha", body)], {"task-42"})
    assert committed == ["task-42"]
    assert unmapped == 0


def test_read_state_missing_defaults(tmp_path):
    st = bs.read_state(str(tmp_path / "nope.json"))
    assert st == {"reviewed": {}, "final_review": None}


def test_set_reviewed_roundtrip(tmp_path):
    p = str(tmp_path / "build-state.json")
    bs.set_reviewed(p, "1")
    assert bs.read_state(p)["reviewed"] == {"1": "passed"}


def test_set_final_review_roundtrip(tmp_path):
    p = str(tmp_path / "build-state.json")
    bs.set_final_review(p, True)
    assert bs.read_state(p)["final_review"] == {"clean": True}
