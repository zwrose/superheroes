# plugins/superheroes/lib/tests/test_build_state.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import build_state as bs


def test_parse_trailers_maps_valid_and_counts_unmapped():
    rows = [("sha1", "1"), ("sha2", ""), ("sha3", "99"), ("sha4", "2")]
    committed, unmapped = bs.parse_trailers(rows, {"1", "2"})
    assert committed == ["1", "2"]      # only ids in valid_ids
    assert unmapped == 2                # the empty trailer + the unknown id "99"


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
