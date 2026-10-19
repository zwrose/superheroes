"""The `breakItInterpreter` calibration decides the break-it launcher when set, else today's walker (#1961)."""
import json
import os
import shlex
import subprocess
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import break_it  # noqa: E402
import round_driver as RD  # noqa: E402
import test_break_it as TB  # noqa: E402  (the git-repo fixtures and the `_wire` helper live there)
import test_break_it_interpreter_1910 as T1910  # noqa: E402  (the launcher fixtures this file reuses)
import test_break_it_loop as TL  # noqa: E402  (its `World` drives `RD._fold`)
from test_break_it import repo  # noqa: E402,F401  (the fixture, reused by name)
from test_break_it_interpreter_1910 import (  # noqa: E402
    FAILING_TEST, FAKE, MARKER, PROJECT_COMMAND, _add_launchers, _driver_world, _python_block,
    _python_finding, launcher_repo)  # noqa: F401  (`launcher_repo` is a fixture, reused by name)

PASSING_TEST = "def test_ok():\n    pass\n"
PYTEST_PATH = "tests/test_pytest_block.py"
TAG = "TAG1"
AS_WRITTEN = "AS-WRITTEN"


def _echo_launcher(tmp_path):
    """A launcher script outside the repo: it echoes its own argv (and logs it), then execs the real
    interpreter with its arguments after dropping the first. Returns ``(script path, log path)``."""
    script, log = tmp_path / "echo-launcher", tmp_path / "echo-launcher.log"
    script.write_text("#!/bin/sh\necho \"ARGV: $*\"\necho \"$*\" >> %s\nshift\nexec %s \"$@\"\n"
                      % (shlex.quote(str(log)), TB.PY))
    os.chmod(str(script), 0o755)
    return str(script), log


def _pytest_block(path=PYTEST_PATH, program="pytest"):
    return TB._block(path, PASSING_TEST, run="%s %s" % (program, path))


def _add_as_written(root, *programs):
    """Commit each program as a script that prints its own argv and exits zero, so a run at the new
    head shows whether the argv ran as written. Returns the new head."""
    for rel in programs:
        TB._write(root, rel, "#!/bin/sh\necho \"%s: $*\"\n" % AS_WRITTEN)
        os.chmod(str(root / rel), 0o755)
    return TB._commit(root, "as-written programs")


def _assert_ran_as_written(record):
    assert (record["outcome"], record["exitCode"]) == ("passed", 0)
    assert "%s: %s" % (AS_WRITTEN, PYTEST_PATH) in record["output"]
    assert MARKER not in record["output"]
    assert record["interpreter"] is None


# ---- K1: the key decides ---------------------------------------------------------------------

def test_k1_a_list_prefix_runs_a_python_command_under_the_key(launcher_repo):
    # axis: `run_one` swaps a python program for the calibrated launcher prefix and records the prefix on the run
    record = break_it.run_one(str(launcher_repo), TB._head(launcher_repo), _python_block(),
                              interpreter=[FAKE])
    assert record["outcome"] == "failed"
    assert MARKER in record["output"]
    assert record["interpreter"] == FAKE


# ---- K2: the driver, a verify command that names no launcher ---------------------------------

def test_k2_the_key_decides_the_launcher_when_the_verify_command_names_none(tmp_path):
    # axis: the driver fold reads the launcher from the session's `breakItInterpreter` when the verify command names none
    world = _driver_world(tmp_path / "keyed", "pytest -q")
    world.state["config"][break_it.INTERPRETER_KEY] = FAKE
    world.fold_panel(_python_finding())
    (entry,) = world.round_record["breakItRuns"]
    assert MARKER in entry["output"]
    assert entry["outcome"] == "failed"
    assert entry["interpreter"] == FAKE
    # the same world without the key is today's not-run
    bare = _driver_world(tmp_path / "bare", "pytest -q")
    bare.fold_panel(_python_finding())
    (bare_entry,) = bare.round_record["breakItRuns"]
    assert (bare_entry["outcome"], bare_entry["reason"]) == ("not-run", "interpreter-unresolved")


def test_k2_an_invalid_key_in_the_driver_never_falls_back_to_the_verify_commands_launcher(tmp_path):
    # axis: a set-but-invalid key makes the driver's break-it run read not-run, though the verify command names a working launcher
    world = _driver_world(tmp_path, "%s -m pytest" % FAKE)
    world.state["config"][break_it.INTERPRETER_KEY] = ""
    world.fold_panel(_python_finding())
    (entry,) = world.round_record["breakItRuns"]
    assert (entry["outcome"], entry["reason"]) == ("not-run", "interpreter-key-invalid")
    assert MARKER not in entry["output"]


# ---- K3: a multi-word prefix -----------------------------------------------------------------

def test_k3_a_multi_word_prefix_reaches_both_the_probe_and_the_run(launcher_repo, tmp_path):
    # axis: the whole prefix, not its first word, launches both the readiness probe and the test run
    script, log = _echo_launcher(tmp_path)
    block = _python_block()
    record = break_it.run_one(str(launcher_repo), TB._head(launcher_repo), block,
                              interpreter=[script, TAG])
    assert record["outcome"] == "failed" and record["exitCode"] == 3
    assert "ARGV: %s %s" % (TAG, T1910.TEST_PATH) in record["output"]
    probe, run = log.read_text().splitlines()
    assert probe == "%s -c %s" % (TAG, break_it._PROBE_CODE)
    assert run == "%s %s" % (TAG, T1910.TEST_PATH)
    assert record["interpreter"] == shlex.join([script, TAG])


# ---- K4: the pytest mapping under the key ----------------------------------------------------

@pytest.mark.parametrize("program", ["pytest", "py.test", "/usr/bin/pytest"])
def test_k4_a_pytest_block_runs_as_the_prefix_dash_m_pytest(launcher_repo, tmp_path, program):
    # axis: under a list prefix a pytest program runs as `<prefix> -m pytest <args>`, not as the bare program
    script, log = _echo_launcher(tmp_path)
    record = break_it.run_one(str(launcher_repo), TB._head(launcher_repo),
                              _pytest_block(program=program), interpreter=[script, TAG])
    assert "ARGV: %s -m pytest %s" % (TAG, PYTEST_PATH) in record["output"]
    assert log.read_text().splitlines()[-1] == "%s -m pytest %s" % (TAG, PYTEST_PATH)
    assert record["interpreter"] == shlex.join([script, TAG])


@pytest.mark.parametrize("interpreter", [FAKE, None])
def test_k4_a_str_or_unset_interpreter_leaves_pytest_as_written(launcher_repo, interpreter):
    # axis: the pytest mapping belongs to the list form only — under a str (the walker's) or None launcher a pytest program runs as written, at a real head
    head = _add_as_written(launcher_repo, "scripts/pytest")
    record = break_it.run_one(str(launcher_repo), head, _pytest_block(program="scripts/pytest"),
                              interpreter=interpreter)
    _assert_ran_as_written(record)


@pytest.mark.parametrize("program", ["scripts/pytest-x", "scripts/py.test-x"])
def test_k4_a_prefix_leaves_a_pytest_lookalike_alone(launcher_repo, program):
    # axis: only the exact program names `pytest` and `py.test` are mapped, so a look-alike runs as written at a real head — see bite-proof record wo_1975_lookalike_real_head
    head = _add_as_written(launcher_repo, program)
    record = break_it.run_one(str(launcher_repo), head, _pytest_block(program=program),
                              interpreter=[FAKE])
    _assert_ran_as_written(record)


# ---- K5: an invalid key fails closed ---------------------------------------------------------

INVALID_VALUES = ["", "   ", "-x", "'unterminated", 5, ["a"]]


@pytest.mark.parametrize("value", INVALID_VALUES, ids=repr)
def test_k5_an_invalid_key_resolves_to_the_empty_prefix_never_the_walker(value):
    # axis: a set-but-invalid key resolves to `[]` even when the verify command names a launcher the walker would find
    assert break_it.project_interpreter(PROJECT_COMMAND) == "scripts/pinned-python"
    config = {break_it.INTERPRETER_KEY: value, "verifyCommand": PROJECT_COMMAND}
    assert break_it.launcher_argv(value) is None
    assert break_it.resolve_interpreter(config) == []


@pytest.mark.parametrize("value", INVALID_VALUES, ids=repr)
def test_k5_an_empty_prefix_reads_not_run_for_python_and_pytest(launcher_repo, value):
    # axis: the empty prefix an invalid key resolves to makes a python or pytest run `interpreter-key-invalid`, never run
    interpreter = break_it.resolve_interpreter({break_it.INTERPRETER_KEY: value})
    for block in (_python_block(), _pytest_block()):
        record = break_it.run_one(str(launcher_repo), TB._head(launcher_repo), block,
                                  interpreter=interpreter)
        assert (record["outcome"], record["reason"]) == ("not-run", "interpreter-key-invalid")
        assert record["interpreter"] is None and record["exitCode"] is None


@pytest.mark.parametrize("program", ["scripts/pinned-python", "npx", "python3x"])
def test_k5_the_empty_prefix_leaves_another_program_to_run_as_written(program):
    # axis: the empty prefix refuses only python and pytest runs; any other program reaches the run as written
    record = break_it.run_one("/nonexistent", "", _python_block(program=program), interpreter=[])
    assert record["reason"] == "head-unresolved"
    assert record["interpreter"] is None


def test_k5_launcher_argv_is_the_one_validator():
    # axis: a valid value splits into its shell words; every invalid shape is None and none raises
    assert break_it.launcher_argv("uv run python") == ["uv", "run", "python"]
    assert break_it.launcher_argv("'my python' -u") == ["my python", "-u"]
    assert break_it.launcher_argv("''") is None
    for bad in (None, b"python", 0, [], {}, "", " ", "--python", "'x"):
        assert break_it.launcher_argv(bad) is None
    assert break_it.resolve_interpreter("not a dict") is None
    assert break_it.resolve_interpreter(None) is None


def test_k5_a_key_whose_launcher_does_not_start_reads_not_run_unavailable(launcher_repo):
    # axis: a valid key naming a launcher that cannot start reads `interpreter-unavailable`, as a str launcher does
    record = break_it.run_one(str(launcher_repo), TB._head(launcher_repo), _python_block(),
                              interpreter=["scripts/broken-python"])
    assert (record["outcome"], record["reason"]) == ("not-run", "interpreter-unavailable")
    assert record["interpreter"] == "scripts/broken-python"


def test_k5_a_kept_check_under_an_invalid_key_is_not_kept(launcher_repo):
    # axis: a kept-check whose key is invalid reads failing (`interpreter-key-invalid`), never kept
    base, head, record = TB._kept_fixture(launcher_repo, "pass\n")
    record["command"] = "python3 tests/test_k.py"
    result = break_it.check_kept(str(launcher_repo), base, head, record, interpreter=[])
    assert (result["outcome"], result["reason"]) == ("failing", "interpreter-key-invalid")
    assert result["run"]["outcome"] == "not-run"


# ---- K6: an unset key is today's resolver ----------------------------------------------------

def _t4_commands():
    # copied by reference from test_break_it_interpreter_1910.test_t4_project_interpreter's parametrize list
    (mark,) = [m for m in T1910.test_t4_project_interpreter.pytestmark if m.name == "parametrize"]
    return [command for command, _ in mark.args[1]]


CENSUS = _t4_commands() + ["pytest -q", "uv run pytest", "make test", "tox", "poetry run pytest",
                           "none", "", None]


@pytest.mark.parametrize("command", CENSUS, ids=repr)
def test_k6_an_absent_or_none_key_is_the_walker_unchanged(command):
    # axis: with the key absent or None the resolver returns exactly what `project_interpreter` returns
    expected = break_it.project_interpreter(command)
    assert break_it.resolve_interpreter({"verifyCommand": command}) == expected
    assert break_it.resolve_interpreter({"verifyCommand": command, break_it.INTERPRETER_KEY: None}) == expected


def test_k6_the_census_covers_the_t4_list():
    # axis: the census is built from the existing T4 list, so it cannot silently shrink to nothing
    assert PROJECT_COMMAND in CENSUS and len(_t4_commands()) == 6


def test_k6_a_str_launcher_run_is_the_record_it_was_at_base(launcher_repo):
    # axis: a str launcher (the walker's) still records the str and runs python only, as before the key
    record = break_it.run_one(str(launcher_repo), TB._head(launcher_repo), _python_block(), interpreter=FAKE)
    assert (record["outcome"], record["interpreter"]) == ("failed", FAKE)
    assert MARKER in record["output"]


# ---- K7: the kept-check under the key --------------------------------------------------------

def _fixed_world(tmp_path):
    """A `TL.World` on `pytest -q` whose break-it finding was run under the key and then fixed."""
    world = TL.World(tmp_path)
    world.state["config"]["verifyCommand"] = "pytest -q"
    world.state["config"][break_it.INTERPRETER_KEY] = TL.PY
    world.fold_panel(TL._break_it_finding())
    world.disposition("fixed")
    world.fix(TL._TEST_FAILING)
    return world


def test_k7_a_fixed_break_it_finding_certifies_under_the_key(tmp_path):
    # axis: the kept-check re-run takes its launcher from the key, so a fixed finding on a launcher-less verify command is kept
    world = _fixed_world(tmp_path)
    assert RD._break_it_kept_step(world.state, world.state["config"]) is False
    (row,) = world.round_record["breakItKept"]
    assert row["outcome"] == "kept" and row["path"] == TL.TEST_PATH
    assert row["run"]["interpreter"] == sys.executable


def test_k7_the_same_world_without_the_key_parks(tmp_path):
    # axis: without the key the launcher-less verify command leaves the kept-check unresolved, so the fixed finding parks
    world = _fixed_world(tmp_path)
    del world.state["config"][break_it.INTERPRETER_KEY]
    assert RD._break_it_kept_step(world.state, world.state["config"]) is True
    (row,) = world.round_record["breakItKept"]
    assert row["outcome"] != "kept"
    assert row["reason"] == "interpreter-unresolved"


def test_k7_a_fixed_finding_under_an_invalid_key_parks(tmp_path):
    # axis: a set-but-invalid key parks a fixed finding with `interpreter-key-invalid`, never certifies it
    world = _fixed_world(tmp_path)
    world.state["config"][break_it.INTERPRETER_KEY] = "-x"
    assert RD._break_it_kept_step(world.state, world.state["config"]) is True
    (row,) = world.round_record["breakItKept"]
    assert row["outcome"] != "kept"
    assert row["reason"] == "interpreter-key-invalid"


# ---- K8: the `next` flag ---------------------------------------------------------------------

def _guard_argv(session_dir, fresh=True):
    """The extra argv a CLI `next` needs to satisfy the base guard: a real two-commit repo, the
    session's meta.json and the round diff. Mirrors test_round_driver_advance's helper, with the
    fixture repo's identity and signing pinned inline."""
    repo_dir = os.path.join(session_dir, "_gitrepo")
    git = ["git", "-C", repo_dir] + TB._ID
    if not os.path.isdir(os.path.join(repo_dir, ".git")):
        os.makedirs(repo_dir)
        subprocess.check_call(["git", "init", "-q", "-b", "main", repo_dir])
        subprocess.check_call(git + ["commit", "-q", "--allow-empty", "-m", "init"])
        pin = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "HEAD"], text=True).strip()
        with open(os.path.join(repo_dir, "f.py"), "w", encoding="utf-8") as fh:
            fh.write("a\n")
        subprocess.check_call(["git", "-C", repo_dir, "add", "f.py"])
        subprocess.check_call(git + ["commit", "-q", "-m", "change"])
    else:
        pin = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "HEAD~1"], text=True).strip()
    toplevel = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "--show-toplevel"],
                                       text=True).strip()
    meta_path = os.path.join(session_dir, RD.round_records.META_FILE)
    meta = {}
    if os.path.isfile(meta_path):
        with open(meta_path, encoding="utf-8") as fh:
            meta = json.load(fh)
        pin = meta.get("baseRef") or pin
    meta.update({"mode": "branch", "baseRef": pin, "baseBranch": "main", "baseFetch": "fetched",
                 "repoRoot": toplevel})
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    diff_path = os.path.join(session_dir, "round-1", "diff.txt")
    os.makedirs(os.path.dirname(diff_path), exist_ok=True)
    with open(diff_path, "w", encoding="utf-8") as fh:
        fh.write(subprocess.check_output(["git", "-C", repo_dir, "diff", "%s...HEAD" % pin], text=True))
    argv = ["--repo-root", repo_dir]
    if fresh:
        argv += ["--diff-path", diff_path]
    return argv


@pytest.mark.parametrize("value", ["uv run python", "scripts/pinned-python", ""], ids=repr)
def test_k8_the_flag_stores_its_value_in_the_state_config(tmp_path, value):
    # axis: `next --break-it-interpreter X` on a fresh session stores X (the empty string too) as `breakItInterpreter`
    d = str(tmp_path / "s")
    os.makedirs(d)
    assert RD.main(["next", "--session-dir", d, "--break-it-interpreter", value] + _guard_argv(d)) == 0
    ok, state = RD.load_state(d)
    assert ok and state["config"][break_it.INTERPRETER_KEY] == value


def test_k8_an_unset_flag_leaves_the_state_config_without_the_key(tmp_path):
    # axis: a session started without the flag carries no `breakItInterpreter`, so an unset session's config keeps its shape
    d = str(tmp_path / "s")
    os.makedirs(d)
    assert RD.main(["next", "--session-dir", d] + _guard_argv(d)) == 0
    ok, state = RD.load_state(d)
    assert ok and break_it.INTERPRETER_KEY not in state["config"]


def test_k8_the_flag_on_an_existing_state_refuses(tmp_path, capsys):
    # axis: `--break-it-interpreter` on a non-fresh session refuses `break-it-interpreter-not-fresh-state`, never silently ignored
    d = str(tmp_path / "s")
    os.makedirs(d)
    # A/B: fresh state accepts it
    assert RD.main(["next", "--session-dir", d, "--break-it-interpreter", "python3"] + _guard_argv(d)) == 0
    capsys.readouterr()
    rc = RD.main(["next", "--session-dir", d, "--break-it-interpreter", "python3"]
                 + _guard_argv(d, fresh=False))
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert rc == 1
    assert out == {"ok": False, "reason": "break-it-interpreter-not-fresh-state", "value": "python3"}
