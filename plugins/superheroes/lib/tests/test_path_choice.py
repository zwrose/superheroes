import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import path_choice

def test_record_then_read_roundtrips(tmp_path):
    wi = "wi-x"
    assert path_choice.read(wi, cwd=str(tmp_path), root=str(tmp_path)) is None
    path_choice.record(wi, "showrunner", cwd=str(tmp_path), root=str(tmp_path))
    assert path_choice.read(wi, cwd=str(tmp_path), root=str(tmp_path)) == "showrunner"

def test_unknown_workitem_reads_none(tmp_path):
    assert path_choice.read("nope", cwd=str(tmp_path), root=str(tmp_path)) is None
