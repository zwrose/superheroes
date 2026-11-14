"""Issue 2452: order lint reads its budget, --timeout and suite-command keywords outside path spans."""
import importlib.util
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


def _load():
    spec = importlib.util.spec_from_file_location(
        "order_lint", os.path.join(_LIB, "order_lint.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


OL = _load()

_BUDGET_LINE = "Command budget: at most 3 commands.\n"


def _repo(tmp_path, files=()):
    root = tmp_path / "repo"
    root.mkdir()
    for rel in files:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n", encoding="utf-8")
    return str(root)


def _tokens(result):
    return [f["token"] for f in result["findings"]]


def _warned(result):
    return [w["token"] for w in result["warnings"]] == [OL.WARN_TIMEOUT_MISSING]


# E1: a path holding "budget" near a digit, with no other budget line
@pytest.mark.parametrize("cite, files", [
    ("budget/v2", ()),
    ("budget/v2.md", ("budget/v2.md",)),
    ("budget2.md", ()),
])
def test_e1_budget_word_only_inside_a_path_is_missing(tmp_path, cite, files):
    # axis: a budget keyword inside a path span does not satisfy the budget rule — see bite-proof record i2452_order_lint
    root = _repo(tmp_path, files)
    r = OL.check_text("# WO\n\nSee %s for details.\n" % cite, repo_root=root)
    assert _tokens(r) == [OL.TOKEN_BUDGET_MISSING]


# E1, sentence-final: a filename that ends a sentence keeps its period outside the extension test
@pytest.mark.parametrize("cite", ["budget2.md.", "budget2.md..."])
def test_e1_a_sentence_final_filename_is_still_a_path(tmp_path, cite):
    # axis: a filename followed by a sentence period is still a path span — see bite-proof record i2452_order_lint
    root = _repo(tmp_path)
    r = OL.check_text("# WO\n\nSee %s\n" % cite, repo_root=root)
    assert _tokens(r) == [OL.TOKEN_BUDGET_MISSING]


# E2: a real budget line beside a path
def test_e2_real_budget_line_beside_a_path_passes(tmp_path):
    root = _repo(tmp_path)
    r = OL.check_text("# WO\n\nCommand budget: 4 commands (see docs/x)\n", repo_root=root)
    assert r["ok"] is True
    assert _tokens(r) == []


# E3: a budget label in a Markdown link whose target is a path
def test_e3_budget_label_in_a_link_to_a_path_passes(tmp_path):
    root = _repo(tmp_path)
    r = OL.check_text("# WO\n\n[Budget](docs/order): 5 commands\n", repo_root=root)
    assert r["ok"] is True
    assert _tokens(r) == []


# E4: --timeout only inside a path, with a suite command
@pytest.mark.parametrize("cite", ["docs/--timeout", "docs/--timeout.md", "notes--timeout.md"])
def test_e4_timeout_flag_only_inside_a_path_warns(tmp_path, cite):
    # axis: a --timeout inside a path span is not the flag, so the missing-timeout warning stays — see bite-proof record i2452_order_lint
    root = _repo(tmp_path)
    r = OL.check_text("# WO\n\nRun pytest. See %s for notes.\n%s" % (cite, _BUDGET_LINE),
                      repo_root=root)
    assert _warned(r)


# E5: a real flag beside a redirection
@pytest.mark.parametrize("flag", [
    "pytest --timeout=600</dev/null",
    "pytest --timeout=600",
    "pytest --timeout 600",
    "pytest --timeout",
])
def test_e5_real_flag_beside_a_redirection_does_not_warn(tmp_path, flag):
    root = _repo(tmp_path)
    r = OL.check_text("# WO\n\nRun %s now.\n%s" % (flag, _BUDGET_LINE), repo_root=root)
    assert r["warnings"] == []


# E6: a suite word only inside a path, with no suite command
@pytest.mark.parametrize("cite", ["lib/pytest-plugin", "lib/pytest-plugin.py", "pytest-plugin.py"])
def test_e6_suite_word_only_inside_a_path_does_not_warn(tmp_path, cite):
    root = _repo(tmp_path, ("lib/pytest-plugin.py",))
    r = OL.check_text("# WO\n\nRead %s with care.\n%s" % (cite, _BUDGET_LINE), repo_root=root)
    assert r["warnings"] == []


# E7: --timeout inside a longer word, with a suite command
@pytest.mark.parametrize("word", ["--timeout-notes", "--timeouts", "x--timeout"])
def test_e7_timeout_inside_a_longer_word_warns(tmp_path, word):
    # axis: only a whole --timeout flag token counts as setting a timeout — see bite-proof record i2452_order_lint
    root = _repo(tmp_path)
    r = OL.check_text("# WO\n\nRun pytest. Mind %s here.\n%s" % (word, _BUDGET_LINE),
                      repo_root=root)
    assert _warned(r)


# E8: the "at most N commands" form still passes
def test_e8_at_most_n_commands_form_passes(tmp_path):
    root = _repo(tmp_path)
    r = OL.check_text("# WO\n\nYou may run at most 7 commands.\n", repo_root=root)
    assert r["ok"] is True
    assert _tokens(r) == []
