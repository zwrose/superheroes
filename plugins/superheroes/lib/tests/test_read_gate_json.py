# plugins/superheroes/lib/tests/test_read_gate_json.py
import json
import os
import subprocess
import sys

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DD = os.path.join(_LIB, "definition_doc.py")


def _mk_spec(root, wi, review):
    d = os.path.join(root, "docs", "superheroes", wi)
    os.makedirs(d)
    with open(os.path.join(d, "spec.md"), "w") as fh:
        fh.write("---\nsuperheroes: doc\ndocType: spec\nworkItem: %s\n"
                 "gates: {review: %s}\n---\n# x\n" % (wi, review))


def test_read_gate_json_emits_review_object(tmp_path):
    _mk_spec(str(tmp_path), "wi", "passed")
    out = subprocess.run(
        [sys.executable, _DD, "read-gate", "--doc", "spec", "--work-item", "wi",
         "--root", str(tmp_path), "--json"],
        capture_output=True, text=True)
    assert out.returncode == 0
    assert json.loads(out.stdout) == {"review": "passed"}


def test_read_gate_json_error_stays_on_stderr_nonzero(tmp_path):
    # no spec on disk -> error path: stderr + non-zero, empty stdout (cmdRunner fails closed)
    out = subprocess.run(
        [sys.executable, _DD, "read-gate", "--doc", "spec", "--work-item", "missing",
         "--root", str(tmp_path), "--json"],
        capture_output=True, text=True)
    assert out.returncode != 0
    assert out.stdout.strip() == ""
