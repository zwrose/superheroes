"""Tests for the setup text's dependency fill (#2044): when a project declares a Python launcher and
Python dependencies, the setup text runs the launcher once in the clone, after the setup commands;
when either is missing the text and its stamp are what they were.

Every fixture project is a real git repository under tmp_path, as in test_cloud_setup_text.
"""
import os
import subprocess

import pytest

from test_cloud_setup_text import (CS, _GOLDEN_KW, _compose, _edit_core_block, _golden, _inside,
                                   _outside, _run_script, _setup_log, _store_commands)

import cloud_setup  # noqa: E402
import mode_registry  # noqa: E402

MODES = ["outside", "inside"]


def _world(tmp_path, mode):
    return (_outside if mode == "outside" else _inside)(tmp_path)


def _requirements(w, name="requirements-dev.txt"):
    (w.repo / name).write_text("pytest\n")


def _set_core(w, verify=None, interpreter=None):
    """Stores the verify command and the break-it interpreter in the project's core record; a None
    leaves that key out."""
    def edit(obj):
        obj["verifyCommand"] = verify if verify is not None else "npm test"
        obj.pop("breakItInterpreter", None)
        if interpreter is not None:
            obj["breakItInterpreter"] = interpreter
    _edit_core_block(w, edit)


def _launcher(w, code=0, name="pinned-python"):
    """A launcher script at an absolute path that records where it ran and with what words, then
    exits `code`."""
    directory = w.tmp / "bin"
    directory.mkdir(exist_ok=True)
    path = directory / name
    calls = w.tmp / (name + "-calls.log")
    path.write_text('#!/bin/bash\necho "$PWD|$*" >> "%s"\nexit %d\n' % (calls, code))
    path.chmod(0o755)
    return str(path), calls


def _project(tmp_path, mode, code=0, requirements=True):
    """A project whose verify command runs a recording launcher, with a requirements file at its
    root; returns (world, launcher path, the launcher's call log)."""
    w = _world(tmp_path, mode)
    path, calls = _launcher(w, code)
    _set_core(w, verify="%s -m pytest" % path)
    if requirements:
        _requirements(w)
    return w, path, calls


def _fill(w):
    return CS._fill_lines(w.cwd, w.root, CS._clone_dir(w.cwd))


def _without_fill(monkeypatch):
    monkeypatch.setattr(CS, "_fill_lines", lambda *args: [])


def _fill_log_lines(log):
    return [ln for ln in log.splitlines() if ln.startswith("dependency fill")]


class _Second:
    """A second place to run a script in, for runs that must not share the first one's stubs."""

    def __init__(self, tmp):
        self.tmp = tmp
        self.home = tmp / "home"
        tmp.mkdir()
        self.home.mkdir()


# --- row 1: the step, where it sits, and that it runs the launcher in the clone ----------------

@pytest.mark.parametrize("mode", MODES)
def test_the_step_follows_the_setup_commands_and_precedes_the_marker(tmp_path, mode):
    # axis: the step sits after the setup commands and before the tool-steps marker; fails if it moves
    w, path, _ = _project(tmp_path, mode)
    _store_commands(w, ["npm ci"])
    fill = _fill(w)
    assert fill and fill[0] == ""
    text = _compose(w)["text"]
    assert text.count("\n".join(fill)) == 1
    lines = text.splitlines()
    commands_at = next(i for i, ln in enumerate(lines) if ln.startswith("# Run the project's own"))
    fill_at = lines.index(fill[1])
    assert commands_at < fill_at < lines.index(CS.TOOL_STEPS_MARKER)
    assert lines.index("wait") < fill_at
    assert "(cd \"$DIR\" && %s -c pass </dev/null >/dev/null 2>&1)" % path in text


@pytest.mark.parametrize("mode", MODES)
def test_the_step_is_in_the_text_without_setup_commands_too(tmp_path, mode):
    # axis: the step needs no setup commands to appear; fails if it is tied to them
    w, path, _ = _project(tmp_path, mode)
    text = _compose(w)["text"]
    assert "Run the project's own setup commands" not in text
    lines = text.splitlines()
    assert lines.index(_fill(w)[1]) < lines.index(CS.TOOL_STEPS_MARKER)


@pytest.mark.parametrize("mode", MODES)
def test_a_working_launcher_runs_once_in_the_clone_and_logs_one_ok_line(tmp_path, mode):
    # axis: the launcher runs once, in the clone, with `-c pass`, logging one ok line; fails if it runs elsewhere or twice
    w, path, calls = _project(tmp_path, mode)
    proc, _ = _run_script(w, _compose(w)["text"], git_clone=True)
    assert proc.returncode == 0, proc.stderr
    assert _fill_log_lines(_setup_log(w)) == ["dependency fill ok"]
    ran = calls.read_text().splitlines()
    assert ran == [os.path.realpath(w.tmp / "work" / "corner-shop") + "|-c pass"]


def test_the_step_runs_in_the_working_directory_when_that_is_the_clone(tmp_path):
    # axis: a working directory that is itself the clone is where the step runs; fails if it looks for a subdirectory
    w, path, calls = _project(tmp_path, "inside")
    proc, _ = _run_script(w, _compose(w)["text"], git_clone="here")
    assert proc.returncode == 0, proc.stderr
    assert _fill_log_lines(_setup_log(w)) == ["dependency fill ok"]
    assert calls.read_text().splitlines() == [os.path.realpath(w.tmp / "work") + "|-c pass"]


# --- row 2: a launcher that fails ----------------------------------------------------------------

@pytest.mark.parametrize("mode", MODES)
def test_a_failing_launcher_logs_one_failed_line_with_its_exit_code(tmp_path, mode):
    # axis: a failing launcher logs one FAILED line with its exit code and runs once; fails if the code is lost or it retries
    w, path, calls = _project(tmp_path, mode, code=3)
    proc, _ = _run_script(w, _compose(w)["text"], git_clone=True)
    assert proc.returncode == 0, proc.stderr
    assert _fill_log_lines(_setup_log(w)) == [
        "dependency fill FAILED: %s -c pass exited 3" % path]
    assert len(calls.read_text().splitlines()) == 1


@pytest.mark.parametrize("commands, status", [(["true"], 0), (["false"], 1)])
def test_a_failed_fill_leaves_the_exit_status_what_it_was_without_the_step(
        tmp_path, commands, status):
    # axis: a failed fill leaves the script's exit status as it is without the step; fails if the fill changes it
    (tmp_path / "with").mkdir()
    w, path, _ = _project(tmp_path / "with", "inside", code=3)
    _store_commands(w, commands)
    fill = _fill(w)
    text = _compose(w)["text"]
    bare = text.replace("\n".join(fill) + "\n", "", 1)
    assert bare != text and "dependency fill" not in bare
    proc, _ = _run_script(w, text, git_clone=True)
    second = _Second(tmp_path / "without")
    other, _ = _run_script(second, bare, git_clone=True)
    assert proc.returncode == other.returncode == status, (proc.stderr, other.stderr)
    assert _fill_log_lines(_setup_log(w)) == [
        "dependency fill FAILED: %s -c pass exited 3" % path]
    assert not _fill_log_lines((second.home / "superheroes-cloud-setup.log").read_text())


@pytest.mark.parametrize("mode", MODES)
def test_the_stamp_is_still_published_when_the_commands_pass_and_the_fill_fails(tmp_path, mode):
    # axis: passing commands publish the stamp even when the fill fails; fails if a failed fill withholds it
    w, path, _ = _project(tmp_path, mode, code=3)
    _store_commands(w, ["true"])
    result = _compose(w)
    proc, _ = _run_script(w, result["text"], git_clone=True)
    assert proc.returncode == 0, proc.stderr
    store = mode_registry.project_store_dir(w.cwd, str(w.home / ".claude" / "superheroes"))
    assert open(os.path.join(store, CS.STAMP_FILE)).read() == result["calibration"]["stamp"] + "\n"
    assert _fill_log_lines(_setup_log(w))[0].startswith("dependency fill FAILED")


# --- row 3: no clone ----------------------------------------------------------------------------

@pytest.mark.parametrize("mode", MODES)
def test_no_clone_logs_one_skipped_line_and_runs_nothing(tmp_path, mode):
    # axis: with no clone the step logs one skipped line and runs nothing; fails if it runs or logs anything else
    w, path, calls = _project(tmp_path, mode)
    proc, _ = _run_script(w, _compose(w)["text"])
    assert proc.returncode == 0, proc.stderr
    work = w.tmp / "work"
    assert _fill_log_lines(_setup_log(w)) == [
        "dependency fill skipped: no clone in %s or %s/corner-shop" % (work, work)]
    assert not calls.exists()


def test_no_clone_leaves_a_failing_command_status_unchanged(tmp_path):
    # axis: the skipped step leaves the non-zero status the missing clone already gives; fails if it masks it as ok
    w, path, _ = _project(tmp_path, "inside")
    _store_commands(w, ["true"])
    proc, _ = _run_script(w, _compose(w)["text"])
    # the command is skipped for want of a clone, which already ends the script non-zero
    assert proc.returncode == 1, proc.stderr
    assert len(_fill_log_lines(_setup_log(w))) == 1
    assert "dependency fill ok" not in _setup_log(w)


# --- row 4: no step, and the text is as it was ----------------------------------------------------

def _fix_no_core(w):
    _set_core(w, verify="scripts/pinned-python -m pytest")


def _fix_no_launcher(w):
    _set_core(w, verify="scripts/pinned-python -m pytest")


def _fix_bare_python(w):
    _set_core(w, verify="scripts/pinned-python -m pytest")


def _fix_no_requirements(w):
    _requirements(w)


def _fix_env_assignment(w):
    _set_core(w, verify="scripts/pinned-python -m pytest")


def _fix_env_word(w):
    _set_core(w, verify="scripts/pinned-python -m pytest")


def _fix_invalid_interpreter(w):
    _set_core(w, verify="scripts/pinned-python -m pytest", interpreter="scripts/pinned-python")


# (name, core as stored or None for no record, requirements file present, what makes the step appear)
NO_STEP = [
    ("no core record", None, True, _fix_no_core),
    ("core with no launcher", dict(verify="npm test"), True, _fix_no_launcher),
    ("bare python launcher", dict(verify="python -m pytest"), True, _fix_bare_python),
    ("bare python interpreter key", dict(verify="npm test", interpreter="python3"), True,
     _fix_no_launcher),
    ("wrapper with no dependency file", dict(verify="tools/pinned checks.py"), False,
     _fix_no_requirements),
    ("environment assignment", dict(
        verify="UV_CACHE_DIR=.uv-cache scripts/pinned-python -m pytest"), True,
     _fix_env_assignment),
    ("env word", dict(verify="env FOO=1 scripts/pinned-python -m pytest"), True, _fix_env_word),
    ("env word alone", dict(verify="/usr/bin/env -u UV_CACHE_DIR scripts/pinned-python -m pytest"),
     True, _fix_env_word),
    ("invalid interpreter key", dict(verify="scripts/pinned-python -m pytest", interpreter="-x"),
     True, _fix_invalid_interpreter),
]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("name, core, requirements, fix", NO_STEP, ids=[c[0] for c in NO_STEP])
def test_a_project_without_the_step_has_the_text_and_stamp_it_had(
        tmp_path, monkeypatch, mode, name, core, requirements, fix):
    # axis: each project missing one fact gets no step and the text and stamp it had; fails if a step appears or the text shifts
    w = _world(tmp_path, mode)
    if core is not None:
        _set_core(w, **core)
    if requirements:
        _requirements(w)
    if core is not None:
        # storing commands writes a core record, so a project with none lists none
        _store_commands(w, ["true"])
    assert _fill(w) == []
    got = _compose(w, stamp_fn=None)
    assert got["action"] == "written" and "dependency fill" not in got["text"]
    with monkeypatch.context() as patch:
        patch.setattr(CS, "_fill_lines", lambda *args: ["", "# a step that was not there"])
        stepped = _compose(w, stamp_fn=None)
    assert stepped["text"] != got["text"]
    _without_fill(monkeypatch)
    assert _compose(w, stamp_fn=None) == got
    monkeypatch.undo()
    # the same project with the missing fact supplied does get the step
    fix(w)
    assert _fill(w)
    assert "dependency fill ok" in _compose(w)["text"]


@pytest.mark.parametrize("mode", MODES)
def test_no_core_record_leaves_the_golden_text_byte_for_byte(tmp_path, mode):
    # axis: with no core record the text is the golden text byte for byte; fails if the step changes any byte
    w = _world(tmp_path, mode)
    expected = _golden(w, mode)
    _requirements(w)
    result = _compose(w, **_GOLDEN_KW)
    assert result["action"] == "written"
    assert result["text"] == expected


# --- row 5: breakItInterpreter beats the verify command's launcher ---------------------------------

@pytest.mark.parametrize("mode", MODES)
def test_the_interpreter_key_beats_the_verify_commands_launcher(tmp_path, mode):
    # axis: breakItInterpreter wins over the verify command's launcher; fails if the verify launcher runs instead
    w, verify_path, verify_calls = _project(tmp_path, mode)
    key_path, key_calls = _launcher(w, name="key-python")
    _set_core(w, verify="%s -m pytest" % verify_path, interpreter=key_path)
    text = _compose(w)["text"]
    # the placed core (outside mode) still holds the verify command; only the step's words matter
    assert "&& %s -c pass" % key_path in text and "&& %s -c pass" % verify_path not in text
    proc, _ = _run_script(w, text, git_clone=True)
    assert proc.returncode == 0, proc.stderr
    assert key_calls.exists() and not verify_calls.exists()


@pytest.mark.parametrize("mode", MODES)
def test_a_launcher_of_several_words_led_by_python_gets_the_step(tmp_path, mode):
    # axis: a launcher of several words led by a Python interpreter runs uv, so it gets the step; fails if it does not
    w = _world(tmp_path, mode)
    _set_core(w, verify="npm test", interpreter="python3 -m uv run python")
    _requirements(w)
    assert _fill(w)
    text = _compose(w)["text"]
    assert "&& python3 -m uv run python -c pass </dev/null" in text
    assert subprocess.run(["bash", "-n"], input=text, text=True,
                          capture_output=True).returncode == 0


def test_the_interpreter_key_words_are_quoted_and_the_text_parses(tmp_path):
    # axis: launcher words are shell-quoted in the step and the text still parses; fails if a word is left raw
    w = _inside(tmp_path)
    _set_core(w, verify="npm test", interpreter="'my launcher' --flag $HOME")
    _requirements(w)
    text = _compose(w)["text"]
    assert "&& 'my launcher' --flag '$HOME' -c pass </dev/null" in text
    assert '"dependency fill FAILED: "' + "'my launcher --flag $HOME'" + '" -c pass exited $rc"' in text
    assert subprocess.run(["bash", "-n"], input=text, text=True,
                          capture_output=True).returncode == 0


def test_a_failed_line_names_the_launcher_words_whatever_they_hold(tmp_path):
    # axis: the FAILED line prints the launcher words literally and the missing launcher exits 127; fails if they are expanded
    w = _inside(tmp_path)
    _set_core(w, verify="npm test", interpreter="/no/such/launcher 'a b' $HOME")
    _requirements(w)
    proc, _ = _run_script(w, _compose(w)["text"], git_clone=True)
    assert proc.returncode == 0, proc.stderr
    assert _fill_log_lines(_setup_log(w)) == [
        "dependency fill FAILED: /no/such/launcher a b $HOME -c pass exited 127"]


# --- row 6: the stamp ------------------------------------------------------------------------------

def _viewed(w, **kw):
    """(the stamp view `compose` hands the stamp function, the result)."""
    seen = []

    def stamp_fn(view):
        seen.append(view)
        return cloud_setup.calibration_stamp(view)
    result = _compose(w, stamp_fn=stamp_fn, **kw)
    return (seen[0] if seen else None), result


@pytest.mark.parametrize("mode", MODES)
def test_both_stamp_views_hold_the_step_exactly_when_the_text_does(tmp_path, mode):
    # axis: both stamp views hold the step's bytes exactly when the text does; fails if either view drops or alters it
    w, _, _ = _project(tmp_path, mode)
    _store_commands(w, ["true"])
    fill = _fill(w)
    expected = ("\n".join(fill) + "\n").encode("utf-8")
    view, result = _viewed(w)
    assert view[CS.SETUP_FILL_STAMP_KEY] == expected == CS.stamped_files(w.cwd, w.root)[
        CS.SETUP_FILL_STAMP_KEY]
    assert CS.SETUP_FILL_STAMP_KEY == "setup-dependency-fill"
    assert result["calibration"]["stamp"] == cloud_setup.calibration_stamp(
        CS.stamped_files(w.cwd, w.root))
    assert CS.stamped_files(w.cwd, w.root) == view


def test_the_outside_view_holds_the_step_with_no_setup_commands(tmp_path):
    # axis: the outside stamp view holds the step with no setup commands; fails if the view needs commands to carry it
    w, _, _ = _project(tmp_path, "outside")
    view, _ = _viewed(w)
    assert view[CS.SETUP_FILL_STAMP_KEY] == ("\n".join(_fill(w)) + "\n").encode("utf-8")
    assert CS.stamped_files(w.cwd, w.root) == view


@pytest.mark.parametrize("mode", MODES)
def test_a_project_without_the_step_keeps_the_stamp_it_has(tmp_path, monkeypatch, mode):
    # axis: a project with no step has no fill key in its stamp view and the stamp it had; fails if the key leaks in
    w, _, _ = _project(tmp_path, mode, requirements=False)
    _store_commands(w, ["true"])
    assert _fill(w) == []
    view, result = _viewed(w)
    assert CS.SETUP_FILL_STAMP_KEY not in view
    assert CS.SETUP_FILL_STAMP_KEY not in CS.stamped_files(w.cwd, w.root)
    before_view = CS.stamped_files(w.cwd, w.root)
    _without_fill(monkeypatch)
    assert CS.stamped_files(w.cwd, w.root) == before_view
    assert _viewed(w)[1]["calibration"]["stamp"] == result["calibration"]["stamp"]


def test_a_text_with_no_stamp_gets_none_from_the_step(tmp_path):
    # axis: a text composed with no stamp function stays stampless; fails if the step makes or adds a stamp
    w, _, _ = _project(tmp_path, "inside")
    assert _fill(w)
    result = _compose(w)
    assert result["calibration"]["stamp"] is None
    assert CS.SETUP_FILL_STAMP_KEY not in CS.stamped_files(w.cwd, w.root)


@pytest.mark.parametrize("mode", MODES)
def test_changing_the_steps_lines_moves_the_stamp(tmp_path, monkeypatch, mode):
    # axis: the step's lines are stamped input; fails if changing them leaves the stamp where it was
    w, _, _ = _project(tmp_path, mode)
    _store_commands(w, ["true"])
    fill = _fill(w)
    base_view = CS.stamped_files(w.cwd, w.root)
    base = _viewed(w)[1]["calibration"]["stamp"]
    monkeypatch.setattr(CS, "_fill_lines", lambda *args: fill + ["# changed"])
    assert cloud_setup.calibration_stamp(CS.stamped_files(w.cwd, w.root)) \
        != cloud_setup.calibration_stamp(base_view)
    assert _viewed(w)[1]["calibration"]["stamp"] != base


# --- row 7: the text parses -----------------------------------------------------------------------

@pytest.mark.parametrize("mode", MODES)
def test_the_text_with_the_step_passes_bash_n(tmp_path, mode):
    # axis: the composed text with the step is valid bash; fails if the step breaks the script's syntax
    w, _, _ = _project(tmp_path, mode)
    _store_commands(w, ["npm ci"])
    text = _compose(w)["text"]
    assert "dependency fill ok" in text
    proc = subprocess.run(["bash", "-n"], input=text, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
