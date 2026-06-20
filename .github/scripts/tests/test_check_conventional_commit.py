import importlib.util, os, subprocess, sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_M = os.path.join(_HERE, "..", "check_conventional_commit.py")
_spec = importlib.util.spec_from_file_location("check_conventional_commit", _M)
CC = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(CC)


def test_accepts_feat_with_scope():
    assert CC.validate("feat(workhorse): add live gate") is None

def test_accepts_breaking_marker():
    assert CC.validate("feat(review-crew)!: drop old API") is None

def test_accepts_plain_type():
    assert CC.validate("docs: tidy README") is None

def test_accepts_squash_subject_with_pr_number():
    assert CC.validate("ci: add release workflow (#42)") is None

def test_rejects_unknown_type():
    assert CC.validate("feet(x): typo in type") is not None

def test_rejects_missing_colon():
    assert CC.validate("feat add a thing") is not None

def test_rejects_empty():
    assert CC.validate("") is not None

def test_only_first_line_considered():
    assert CC.validate("feat: ok subject\n\nbody can be anything at all") is None

def test_cli_exit_codes():
    ok = subprocess.run([sys.executable, _M, "feat: ok"], capture_output=True)
    assert ok.returncode == 0
    bad = subprocess.run([sys.executable, _M, "nope not valid"], capture_output=True)
    assert bad.returncode == 1
