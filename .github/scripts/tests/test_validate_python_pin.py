import os
import sys

import pytest

import validate_python_pin as vpp

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

_PIN = "3.12"

_HEALTHY_WORKFLOW = """\
name: ci
on: push
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version-file: .python-version
      - run: python3 x.py
"""


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _scaffold_healthy(tmp_path):
    _write(tmp_path, ".python-version", _PIN + "\n")
    for rel in vpp._EXPLICIT_HOMES:
        _write(tmp_path, rel, "innocuous\n")
    _write(
        tmp_path,
        "scripts/pinned-python",
        '#!/usr/bin/env bash\nexec uv run --no-project --python "$pin" python "$@"\n',
    )
    _write(tmp_path, ".github/scripts/x.py", "# helper\n")
    _write(tmp_path, ".github/workflows/ci.yml", _HEALTHY_WORKFLOW)


def _violations(root):
    return vpp.check(root)


def _has_rule(violations, rule, path=None):
    for v in violations:
        if v.rule != rule:
            continue
        if path is not None and v.path != path:
            continue
        return True
    return False


def test_healthy_fixture(tmp_path):
    _scaffold_healthy(tmp_path)
    assert _violations(tmp_path) == []
    assert vpp.main(["--root", str(tmp_path)]) == 0


def test_pin_missing(tmp_path):
    _scaffold_healthy(tmp_path)
    os.remove(os.path.join(tmp_path, ".python-version"))
    assert _has_rule(_violations(tmp_path), "pin-missing", ".python-version")


@pytest.mark.parametrize(
    "body",
    ["3.12\n3.11\n", "latest\n", ""],
)
def test_pin_malformed(tmp_path, body):
    _scaffold_healthy(tmp_path)
    _write(tmp_path, ".python-version", body)
    assert _has_rule(_violations(tmp_path), "pin-malformed", ".python-version")


def test_home_missing_explicit(tmp_path):
    _scaffold_healthy(tmp_path)
    os.remove(os.path.join(tmp_path, "CLAUDE.md"))
    assert _has_rule(_violations(tmp_path), "home-missing", "CLAUDE.md")


def test_home_missing_workflows(tmp_path):
    _scaffold_healthy(tmp_path)
    wf_dir = os.path.join(tmp_path, ".github", "workflows")
    for name in os.listdir(wf_dir):
        os.remove(os.path.join(wf_dir, name))
    assert _has_rule(_violations(tmp_path), "home-missing", ".github/workflows")


def test_absolute_in_claude(tmp_path):
    _scaffold_healthy(tmp_path)
    _write(tmp_path, "CLAUDE.md", "run /usr/bin/python3 x.py\n")
    assert _has_rule(_violations(tmp_path), "absolute-interpreter-path", "CLAUDE.md")


def test_absolute_in_pinned_python_shebang(tmp_path):
    _scaffold_healthy(tmp_path)
    _write(
        tmp_path,
        "scripts/pinned-python",
        "#!/usr/bin/python3\nexec uv run --python \"$pin\" python \"$@\"\n",
    )
    assert _has_rule(
        _violations(tmp_path), "absolute-interpreter-path", "scripts/pinned-python"
    )


def test_absolute_in_workflow_run(tmp_path):
    _scaffold_healthy(tmp_path)
    wf = _HEALTHY_WORKFLOW.replace(
        "python3 x.py", "/usr/bin/python3 x.py"
    )
    _write(tmp_path, ".github/workflows/ci.yml", wf)
    assert _has_rule(
        _violations(tmp_path),
        "absolute-interpreter-path",
        ".github/workflows/ci.yml",
    )


@pytest.mark.parametrize(
    "snippet",
    [
        "/usr/bin/env python3",
        "scripts/pinned-python",
    ],
)
def test_absolute_negatives_not_flagged(tmp_path, snippet):
    _scaffold_healthy(tmp_path)
    _write(tmp_path, "CLAUDE.md", snippet + "\n")
    assert not _has_rule(_violations(tmp_path), "absolute-interpreter-path")


@pytest.mark.parametrize(
    "snippet",
    [
        ".venv/bin/python gate.py\n",
        "plugins/x/python gate.py\n",
    ],
)
def test_relative_interpreter_path_positives(tmp_path, snippet):
    _scaffold_healthy(tmp_path)
    _write(tmp_path, "CLAUDE.md", snippet)
    assert _has_rule(_violations(tmp_path), "absolute-interpreter-path", "CLAUDE.md")


@pytest.mark.parametrize(
    "rel,text,rule",
    [
        ("CLAUDE.md", "use python3.11 here\n", "version-literal-mismatch"),
        ("CLAUDE.md", "Python **3.9**\n", "version-literal-mismatch"),
        ("CLAUDE.md", "py311\n", "version-literal-mismatch"),
        (
            "scripts/pinned-python",
            'exec uv run --python 3.11 python "$@"\n',
            "version-literal-mismatch",
        ),
        ("CLAUDE.md", "UV_PYTHON=3.11\n", "version-literal-mismatch"),
        ("CLAUDE.md", "cpython-3.11.2\n", "version-literal-mismatch"),
        (
            "CONTRIBUTING.md",
            'python-version: "3.11"\n',
            "version-literal-mismatch",
        ),
    ],
)
def test_version_literal_mismatch_spellings(tmp_path, rel, text, rule):
    _scaffold_healthy(tmp_path)
    _write(tmp_path, rel, text)
    assert _has_rule(_violations(tmp_path), rule, rel)


@pytest.mark.parametrize(
    "text",
    [
        "Python 3.12.13\n",
        "python3.12\n",
        'exec uv run --python "$pin" python "$@"\n',
    ],
)
def test_version_agreement_not_flagged(tmp_path, text):
    _scaffold_healthy(tmp_path)
    _write(tmp_path, "CLAUDE.md", text)
    assert not _has_rule(_violations(tmp_path), "version-literal-mismatch")


def test_workflow_python_version_literal_even_when_matches_pin(tmp_path):
    _scaffold_healthy(tmp_path)
    wf = _HEALTHY_WORKFLOW.replace(
        "python-version-file: .python-version",
        'python-version: "3.12"',
    )
    _write(tmp_path, ".github/workflows/ci.yml", wf)
    assert _has_rule(
        _violations(tmp_path),
        "workflow-python-version-literal",
        ".github/workflows/ci.yml",
    )


def test_workflow_setup_python_unpinned_no_with(tmp_path):
    _scaffold_healthy(tmp_path)
    wf = _HEALTHY_WORKFLOW.replace(
        "      - uses: actions/setup-python@v5\n"
        "        with:\n"
        "          python-version-file: .python-version\n",
        "      - uses: actions/setup-python@v5\n",
    )
    _write(tmp_path, ".github/workflows/ci.yml", wf)
    assert _has_rule(
        _violations(tmp_path), "workflow-setup-python-unpinned"
    )


def test_workflow_setup_python_unpinned_wrong_file(tmp_path):
    _scaffold_healthy(tmp_path)
    wf = _HEALTHY_WORKFLOW.replace(
        "python-version-file: .python-version",
        "python-version-file: other.txt",
    )
    _write(tmp_path, ".github/workflows/ci.yml", wf)
    assert _has_rule(
        _violations(tmp_path), "workflow-setup-python-unpinned"
    )


# Axis: workflow-setup-python-unpinned — conditional setup-python is still validated.
def test_workflow_setup_python_unpinned_conditional_wrong_file(tmp_path):
    _scaffold_healthy(tmp_path)
    wf = """\
name: ci
on: push
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        if: false
        with:
          python-version-file: other.txt
"""
    _write(tmp_path, ".github/workflows/ci.yml", wf)
    assert _has_rule(
        _violations(tmp_path), "workflow-setup-python-unpinned"
    )


def test_workflow_python_before_setup_run_python(tmp_path):
    _scaffold_healthy(tmp_path)
    wf = """\
name: ci
on: push
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 x.py
      - uses: actions/setup-python@v5
        with:
          python-version-file: .python-version
"""
    _write(tmp_path, ".github/workflows/ci.yml", wf)
    assert _has_rule(
        _violations(tmp_path), "workflow-python-before-setup"
    )


def test_workflow_python_before_setup_uv_pip(tmp_path):
    _scaffold_healthy(tmp_path)
    wf = """\
name: ci
on: push
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: uv pip install --system -r requirements-dev.txt
      - uses: actions/setup-python@v5
        with:
          python-version-file: .python-version
"""
    _write(tmp_path, ".github/workflows/ci.yml", wf)
    assert _has_rule(
        _violations(tmp_path), "workflow-python-before-setup"
    )


def test_workflow_python_before_setup_no_setup_step(tmp_path):
    _scaffold_healthy(tmp_path)
    wf = """\
name: ci
on: push
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 x.py
"""
    _write(tmp_path, ".github/workflows/ci.yml", wf)
    assert _has_rule(
        _violations(tmp_path), "workflow-python-before-setup"
    )


def test_workflow_unparseable(tmp_path):
    _scaffold_healthy(tmp_path)
    _write(tmp_path, ".github/workflows/ci.yml", "jobs: [\n")
    assert _has_rule(
        _violations(tmp_path), "workflow-unparseable", ".github/workflows/ci.yml"
    )


def test_self_exclusion_validate_script_not_scanned(tmp_path):
    _scaffold_healthy(tmp_path)
    _write(
        tmp_path,
        ".github/scripts/validate_python_pin.py",
        "/usr/bin/python3\n",
    )
    assert _violations(tmp_path) == []


def test_home_unreadable(tmp_path):
    _scaffold_healthy(tmp_path)
    path = os.path.join(tmp_path, "CLAUDE.md")
    with open(path, "wb") as fh:
        fh.write(b"\xff\xfe")
    assert _has_rule(_violations(tmp_path), "home-unreadable", "CLAUDE.md")


def test_yaml_unavailable(monkeypatch, tmp_path):
    _scaffold_healthy(tmp_path)
    real_import = __import__

    def guarded_import(name, *args, **kwargs):
        if name == "yaml":
            raise ImportError("forced for test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", guarded_import)
    assert _has_rule(_violations(tmp_path), "yaml-unavailable")


def test_real_tree_healthy():
    assert vpp.check(_REPO_ROOT) == []


def test_main_stdout_single_violation(tmp_path, capsys):
    _scaffold_healthy(tmp_path)
    _write(tmp_path, "CLAUDE.md", "run /usr/bin/python3 x.py\n")
    code = vpp.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    lines = [ln for ln in out.strip().splitlines() if ln]
    assert any(
        ln.startswith(
            "validate_python_pin: absolute-interpreter-path: CLAUDE.md:"
        )
        for ln in lines
    )
    assert lines[-1] == "validate_python_pin: FAIL (1 violation(s))"


# Axis: pin-home-duplicate — a second pin file anywhere competes with the root pin.
def test_pin_home_duplicate_root_python_versions(tmp_path):
    _scaffold_healthy(tmp_path)
    _write(tmp_path, ".python-versions", "3.11\n")
    assert _has_rule(_violations(tmp_path), "pin-home-duplicate", ".python-versions")


def test_pin_home_duplicate_nested_python_version(tmp_path):
    _scaffold_healthy(tmp_path)
    _write(tmp_path, "eval/.python-version", "3.12\n")
    assert _has_rule(
        _violations(tmp_path), "pin-home-duplicate", "eval/.python-version"
    )


def test_pin_home_duplicate_root_tool_versions(tmp_path):
    _scaffold_healthy(tmp_path)
    _write(tmp_path, ".tool-versions", "python 3.11\n")
    assert _has_rule(
        _violations(tmp_path), "pin-home-duplicate", ".tool-versions"
    )


def test_pin_home_duplicate_root_only_ok(tmp_path):
    _scaffold_healthy(tmp_path)
    assert not _has_rule(_violations(tmp_path), "pin-home-duplicate")


# Axis: bare-interpreter-command — ambient python/pip in non-workflow homes.
@pytest.mark.parametrize(
    "text",
    [
        "python3 x.py\n",
        "- python3 x.py\n",
        "`pip install x`\n",
        "$ python -m y\n",
        "cd a && python3 b.py\n",
        "a; pip3 install z\n",
        "x | python3 -\n",
        "(python3 z)\n",
        "python3\n",
        "`python3`\n",
        "env python3 x.py\n",
        "/usr/bin/env python3 x.py\n",
        "FOO=1 python3 x.py\n",
        "A=1 B=2 pip install x\n",
    ],
)
def test_bare_interpreter_command_positives(tmp_path, text):
    _scaffold_healthy(tmp_path)
    _write(tmp_path, "CLAUDE.md", text)
    assert _has_rule(_violations(tmp_path), "bare-interpreter-command", "CLAUDE.md")


@pytest.mark.parametrize(
    "text",
    [
        "scripts/pinned-python -m pytest\n",
        "#!/usr/bin/env python3\n",
        'exec uv run --no-project --python "$pin" python "$@"\n',
        "Python 3.12\n",
        "pytest\n",
        "the python3 interpreter\n",
        "import subprocess\n",
    ],
)
def test_bare_interpreter_command_negatives(tmp_path, text):
    _scaffold_healthy(tmp_path)
    _write(tmp_path, "CLAUDE.md", text)
    assert not _has_rule(_violations(tmp_path), "bare-interpreter-command")


def test_bare_interpreter_command_requirements_dev_pytest_line(tmp_path):
    _scaffold_healthy(tmp_path)
    _write(tmp_path, "requirements-dev.txt", "pytest>=8.0\n")
    assert not _has_rule(
        _violations(tmp_path), "bare-interpreter-command", "requirements-dev.txt"
    )


# Axis: workflow-python-before-setup — shell: python runs before pinned setup-python.
def test_workflow_python_before_setup_shell_python(tmp_path):
    _scaffold_healthy(tmp_path)
    wf = """\
name: ci
on: push
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - shell: python
        run: print(1)
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version-file: .python-version
"""
    _write(tmp_path, ".github/workflows/ci.yml", wf)
    assert _has_rule(
        _violations(tmp_path), "workflow-python-before-setup"
    )


def test_workflow_python_before_setup_job_default_shell_python(tmp_path):
    _scaffold_healthy(tmp_path)
    wf = """\
name: ci
on: push
jobs:
  validate:
    runs-on: ubuntu-latest
    defaults:
      run:
        shell: python
    steps:
      - uses: actions/checkout@v4
      - run: print(1)
      - uses: actions/setup-python@v5
        with:
          python-version-file: .python-version
"""
    _write(tmp_path, ".github/workflows/ci.yml", wf)
    assert _has_rule(
        _violations(tmp_path), "workflow-python-before-setup"
    )


# Axis: workflow-python-before-setup — conditional setup-python never counts as pinned.
def test_workflow_python_before_setup_conditional_setup_python(tmp_path):
    _scaffold_healthy(tmp_path)
    wf = """\
name: ci
on: push
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v5
        if: false
        with:
          python-version-file: .python-version
      - run: python3 x.py
"""
    _write(tmp_path, ".github/workflows/ci.yml", wf)
    assert _has_rule(
        _violations(tmp_path), "workflow-python-before-setup"
    )


def test_workflow_unconditional_setup_python_then_run_stays_clean(tmp_path):
    _scaffold_healthy(tmp_path)
    wf = """\
name: ci
on: push
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version-file: .python-version
      - run: python3 x.py
"""
    _write(tmp_path, ".github/workflows/ci.yml", wf)
    assert not _has_rule(
        _violations(tmp_path), "workflow-python-before-setup"
    )


def test_workflow_explicit_bash_overrides_job_default_shell_python(tmp_path):
    _scaffold_healthy(tmp_path)
    wf = """\
name: ci
on: push
jobs:
  validate:
    runs-on: ubuntu-latest
    defaults:
      run:
        shell: python
    steps:
      - uses: actions/checkout@v4
      - shell: bash
        run: echo safe
      - uses: actions/setup-python@v5
        with:
          python-version-file: .python-version
"""
    _write(tmp_path, ".github/workflows/ci.yml", wf)
    assert not _has_rule(
        _violations(tmp_path), "workflow-python-before-setup"
    )


# Axis: absolute-interpreter-path — declared maintainer-command homes stay path-free.
def test_absolute_in_keep_or_retire_home(tmp_path):
    _scaffold_healthy(tmp_path)
    _write(
        tmp_path,
        "docs/superheroes/KEEP-OR-RETIRE.md",
        "/usr/bin/python3 -B plugins/superheroes/lib/dispatch_entry_doc.py --check\n",
    )
    assert _has_rule(
        _violations(tmp_path),
        "absolute-interpreter-path",
        "docs/superheroes/KEEP-OR-RETIRE.md",
    )


def test_absolute_in_github_script_home(tmp_path):
    _scaffold_healthy(tmp_path)
    _write(tmp_path, ".github/scripts/x.py", "/usr/bin/python3\n")
    assert _has_rule(
        _violations(tmp_path),
        "absolute-interpreter-path",
        ".github/scripts/x.py",
    )


# Axis: running-interpreter-mismatch — --require-running-pin compares major.minor.
def test_running_interpreter_mismatch_flag(tmp_path, monkeypatch, capsys):
    _scaffold_healthy(tmp_path)
    monkeypatch.setattr(vpp.sys, "version_info", (3, 11, 0, "final", 0))
    assert vpp.check(tmp_path) == []
    code = vpp.main(["--root", str(tmp_path), "--require-running-pin"])
    out = capsys.readouterr().out
    assert code == 1
    assert "running-interpreter-mismatch" in out
    monkeypatch.undo()
    code_green = vpp.main(["--root", str(tmp_path), "--require-running-pin"])
    out_green = capsys.readouterr().out
    assert code_green == 0
    assert "running-interpreter-mismatch" not in out_green
