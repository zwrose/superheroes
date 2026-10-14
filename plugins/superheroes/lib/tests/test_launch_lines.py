"""C8a-WO2 / C6 FU4 and FU5: the cloud launch line labels have one home (`launch_lines`), and the
cloud launch carries only a full lowercase 40-hex base commit."""
import ast
import os

import pytest

import cloud_builder as cb
import launch_lines as ll
import launcher

SHA = "a" * 40
ENV_ID = "env_01ABCdef"
_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VALUE = {ll.PLACE: "cloud session", ll.VERSION: "1.2.3", ll.ENVIRONMENT: ENV_ID, ll.BASE: SHA}


# ------------------------------------------------------------------ FU4: one home for the labels

@pytest.mark.parametrize("label", ll.LABELS)
def test_a_formatted_line_parses_back_through_line_regex(label):
    value = _VALUE[label]
    line = ll.format_line(label, value)
    assert line == "%s %s" % (label, value)
    match = ll.line_regex(label, ".+").match(line)
    assert match is not None and match.group(1) == value


@pytest.mark.parametrize("label", ll.LABELS)
def test_line_regex_reads_only_its_own_label_and_the_whole_line(label):
    pattern = ll.line_regex(label, ".+")
    for other in ll.LABELS:
        if other != label:
            assert pattern.match(ll.format_line(other, "x")) is None
    assert pattern.match("  " + ll.format_line(label, "x")) is None
    assert pattern.match(label + "x") is None
    assert pattern.match(label + " ") is None


def test_cloud_builders_line_patterns_are_built_from_the_labels():
    assert cb._VERSION_LINE.match(ll.format_line(ll.VERSION, "1.2.3")).group(1) == "1.2.3"
    assert cb._ENVIRONMENT_LINE.match(ll.format_line(ll.ENVIRONMENT, ENV_ID)).group(1) == ENV_ID
    assert cb._BASE_LINE.match(ll.format_line(ll.BASE, SHA)).group(1) == SHA


def _string_literals_outside_docstrings(path):
    """Every string constant in the module's code: comments are not in the tree, and a module,
    class or function docstring is dropped."""
    tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstrings.add(id(body[0].value))
    return [(node.lineno, node.value) for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and id(node) not in docstrings]


@pytest.mark.parametrize("module", ["launcher.py", "cloud_builder.py"])
def test_no_launch_label_literal_remains_in_the_two_modules(module):
    # axis: the labels are spelled in launch_lines only, not respelled in the composer or the
    # parser (ast source scan; comments and docstrings are out of scope) — see bite-proof record
    # c8a_wo2.md
    found = [(line, text) for line, text in _string_literals_outside_docstrings(
        os.path.join(_LIB, module)) for label in ll.LABELS if label in text]
    assert found == [], "launch label literal in %s: %r" % (module, found)


def test_the_census_finds_a_label_literal_when_one_is_there(tmp_path):
    path = tmp_path / "m.py"
    path.write_text('"""Base commit: doc"""\n# Place: comment\nx = "Cloud environment: %s" % 1\n')
    assert _string_literals_outside_docstrings(str(path)) == [(3, "Cloud environment: %s")]


# ------------------------------------------------------------------ FU5: the base commit

def _compose(base, *, present=True):
    premise = {"baseCommit": base} if present else {}
    return launcher.compose_launch(
        ".", 1747, premise, model="opus", place="cloud", cloud_environment=ENV_ID,
        session_name="issue-1747-probe")


def test_a_valid_base_commit_composes_and_the_prompt_passes_intake_parsing():
    composed = _compose(SHA)
    assert composed["ok"] is True, composed
    parsed = cb.parse_launch(composed["prompt"])
    assert parsed["baseCommit"] == SHA and parsed["environment"] == ENV_ID
    assert parsed["advisorVersion"] == composed["pluginVersion"]
    for label in ll.LABELS:
        assert any(line.startswith(label + " ") for line in composed["prompt"].splitlines())


@pytest.mark.parametrize("base,reason", [
    (None, "premise-missing-field:baseCommit"),
    ("", "premise-missing-field:baseCommit"),
    ("   ", "premise-missing-field:baseCommit"),
    ("\n\t ", "premise-missing-field:baseCommit"),
    (12345, "premise-missing-field:baseCommit"),
    ("a" * 39, "premise-base-commit-invalid"),
    ("a" * 41, "premise-base-commit-invalid"),
    ("A" * 40, "premise-base-commit-invalid"),
    ("ABCDEF0123" * 4, "premise-base-commit-invalid"),
    ("HEAD", "premise-base-commit-invalid"),
    ("g" + "a" * 39, "premise-base-commit-invalid"),
    (" " + SHA + " ", "premise-base-commit-invalid"),
    (SHA + "\n", "premise-base-commit-invalid"),
], ids=["None", "empty", "whitespace", "whitespace-nl-tab", "non-string", "39-hex", "41-hex",
        "uppercase", "mixed-case", "HEAD", "non-hex-char", "padded-valid-sha", "trailing-newline"])
def test_cloud_compose_refuses_a_base_commit_cloud_intake_would_refuse(base, reason):
    # axis: the cloud launch refuses any base that is not a full lowercase 40-hex sha, and says
    # missing or invalid accordingly — see bite-proof record c8a_wo2.md
    result = _compose(base)
    assert result["ok"] is False
    assert result["reason"] == reason


def test_cloud_compose_refuses_an_absent_base_commit_as_missing():
    result = _compose(None, present=False)
    assert result["ok"] is False and result["reason"] == "premise-missing-field:baseCommit"


def test_a_local_adopt_launch_keeps_its_non_empty_base_check():
    # A local adopt prompt's base never reaches cloud intake (cloud_builder.parse_launch reads
    # only a Place: cloud session prompt), so it keeps the non-empty check and no more.
    premise = {"baseCommit": "abc123", "adoptsBranch": "feature/x", "adoptsHead": SHA}
    composed = launcher.compose_launch(".", 1747, premise, model="opus")
    assert composed["ok"] is True, composed
    assert "Base commit: abc123" in composed["prompt"]
    blank = launcher.compose_launch(".", 1747, dict(premise, baseCommit=" "), model="opus")
    assert blank["ok"] is False and blank["reason"] == "premise-missing-field:baseCommit"
