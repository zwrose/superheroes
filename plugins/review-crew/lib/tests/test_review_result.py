import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RR = _load(os.path.join(_HERE, "..", "review_result.py"), "review_result")


def test_write_terminal_result(tmp_path):
    out = tmp_path / "res.json"
    RR.write_result(str(out), action="exit_skipped", rnd=3, reason="skipped blocker")
    got = json.loads(out.read_text())
    assert got == {"action": "exit_skipped", "round": 3, "reason": "skipped blocker"}


def test_read_result_present(tmp_path):
    out = tmp_path / "res.json"
    RR.write_result(str(out), action="exit_clean", rnd=1, reason="")
    assert RR.read_result(str(out))["action"] == "exit_clean"


def test_read_missing_is_gate_fail_closed(tmp_path):
    # Workhorse reads this: a missing/garbled result must NOT read as clean.
    assert RR.read_result(str(tmp_path / "nope.json"))["action"] == "halt"


def test_read_garbled_is_gate_fail_closed(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json")
    assert RR.read_result(str(bad))["action"] == "halt"


def test_cli_write(capsys, tmp_path):
    out = tmp_path / "r.json"
    rc = RR.main(["review_result.py", "write", "--path", str(out),
                  "--action", "halt", "--round", "5", "--reason", "cap"])
    assert rc == 0 and json.loads(out.read_text())["action"] == "halt"
