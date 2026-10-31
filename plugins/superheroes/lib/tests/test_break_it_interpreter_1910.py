"""Break-it runs execute under the project's own interpreter launcher, or read not-run (#1910)."""
import json
import os
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import break_it  # noqa: E402
import round_driver as RD  # noqa: E402
import test_break_it as TB  # noqa: E402  (the git-repo fixtures and the `_wire` helper live there)
import test_break_it_loop as TL  # noqa: E402  (its `World` drives `RD._fold`)
from test_break_it import repo  # noqa: E402,F401  (the fixture, reused by name)

FAKE = "scripts/fake-python"
MARKER = "PINNED-LAUNCHER"
# The project's calibrated verify command, abridged: a shell string with if/then/else and `&&` chains.
PROJECT_COMMAND = (
    "if [ -x scripts/pinned-python ]; then scripts/pinned-python .github/scripts/validate_python_pin.py"
    " && scripts/pinned-python .github/scripts/validate_marketplace.py"
    " && scripts/pinned-python .github/scripts/verify_touched_tests.py --base {baseRef};"
    " else /abs/venv/bin/python .github/scripts/validate_marketplace.py"
    " && /usr/bin/python3 .github/scripts/verify_touched_tests.py --base {baseRef}; fi")
FAILING_TEST = "import sys\nsys.exit(3)\n"
TEST_PATH = "tests/test_always_fails.py"
LAUNCHERS = {
    # prints the marker, then runs the test's real interpreter with the same arguments
    FAKE: "#!/bin/sh\necho %s\nexec %s \"$@\"\n" % (MARKER, TB.PY),
    "scripts/broken-python": "#!/bin/sh\necho launcher-is-broken >&2\nexit 127\n",
    "scripts/slow-python": "#!/bin/sh\nsleep 30\n",
}


def _add_launchers(root):
    for rel, body in LAUNCHERS.items():
        TB._write(root, rel, body)
        os.chmod(str(root / rel), 0o755)
    return TB._commit(root, "launchers")


@pytest.fixture
def launcher_repo(repo):
    _add_launchers(repo)
    return repo


def _python_block(path=TEST_PATH, content=FAILING_TEST, program="python3"):
    return TB._block(path, content, run="%s %s" % (program, path))


# ---- T1: dispatched with the pinned interpreter ---------------------------------------------

def test_t1_run_one_runs_a_python_command_under_the_supplied_launcher(launcher_repo):
    # axis: `run_one` swaps a python program for the supplied launcher and records it on the run
    record = break_it.run_one(str(launcher_repo), TB._head(launcher_repo), _python_block(),
                              interpreter=FAKE)
    assert record["outcome"] == "failed"
    assert MARKER in record["output"]
    assert record["interpreter"] == FAKE


def _driver_world(tmp_path, verify_command):
    """A loop `World` whose head also carries the launchers, with `verify_command` as the session's."""
    world = TL.World(tmp_path)
    world.head = _add_launchers(world.repo)
    (world.session / RD.round_records.META_FILE).write_text(json.dumps(
        {"repoRoot": str(world.repo), "headSha": world.head}))
    world.state["config"]["verifyCommand"] = verify_command
    return world


def _python_finding():
    return TL._break_it_finding(suggestion=TB._wire(
        TL.TEST_PATH, "python3 %s" % TL.TEST_PATH, FAILING_TEST))


def test_t1_the_driver_threads_the_verify_commands_launcher_into_the_run(tmp_path):
    # axis: the driver fold resolves the session's verify-command launcher and passes it to the break-it run
    world = _driver_world(tmp_path, "%s -m pytest" % FAKE)
    world.fold_panel(_python_finding())
    (entry,) = world.round_record["breakItRuns"]
    assert MARKER in entry["output"]
    assert entry["interpreter"] == FAKE
    assert entry["outcome"] == "failed"


# ---- T2: an unresolvable launcher reads not-run ---------------------------------------------

def test_t2_the_driver_reads_not_run_when_the_verify_command_names_no_launcher(tmp_path):
    # axis: a verify command naming no launcher makes the driver's break-it run read not-run, never failed
    world = _driver_world(tmp_path, "none")
    world.fold_panel(_python_finding())
    (entry,) = world.round_record["breakItRuns"]
    assert entry["outcome"] == "not-run"
    assert entry["reason"] == "interpreter-unresolved"
    assert entry["interpreter"] is None


@pytest.mark.parametrize("verify_command", [None, "", "none", "python3 -m 'pytest", "make test"])
def test_t2_each_unresolvable_verify_command_reads_not_run_never_failed(launcher_repo, verify_command):
    # axis: every verify-command shape with no resolvable launcher yields `interpreter-unresolved`, not a failed run
    interpreter = break_it.project_interpreter(verify_command)
    assert interpreter is None
    record = break_it.run_one(str(launcher_repo), TB._head(launcher_repo), _python_block(),
                              interpreter=interpreter)
    assert (record["outcome"], record["reason"]) == ("not-run", "interpreter-unresolved")
    assert record["interpreter"] is None and record["exitCode"] is None


# ---- T3: a launcher that cannot start reads not-run -----------------------------------------

@pytest.mark.parametrize("launcher, kwargs", [
    ("scripts/missing-python", {}),
    ("scripts/broken-python", {}),
    ("scripts/slow-python", {"timeout": 1}),
])
def test_t3_a_launcher_that_does_not_start_reads_not_run_never_failed(launcher_repo, launcher, kwargs):
    # axis: a missing, crashing, or timed-out launcher yields `interpreter-unavailable`, not a failed test run
    record = break_it.run_one(str(launcher_repo), TB._head(launcher_repo), _python_block(),
                              interpreter=launcher, **kwargs)
    assert (record["outcome"], record["reason"]) == ("not-run", "interpreter-unavailable")
    assert record["interpreter"] == launcher
    assert record["exitCode"] is None


def test_t3_the_broken_launchers_output_tail_is_recorded(launcher_repo):
    # axis: a launcher that cannot start leaves its stderr tail on the not-run record
    record = break_it.run_one(str(launcher_repo), TB._head(launcher_repo), _python_block(),
                              interpreter="scripts/broken-python")
    assert "launcher-is-broken" in record["output"]


# ---- T4: the resolver and the program match -------------------------------------------------

@pytest.mark.parametrize("command, expected", [
    (PROJECT_COMMAND, "scripts/pinned-python"),
    ("python3 -m pytest -q", "python3"),
    ("FOO=1 uv run x.py", None),
    ("FOO=1 tools/py x.py", "tools/py"),
    ("make test", None),
    ("[ -x a/b ] && a/b c.py", "a/b"),
])
def test_t4_project_interpreter(command, expected):
    # axis: the resolver picks the first program of a verify command that runs a script, or none when it cannot tell
    assert break_it.project_interpreter(command) == expected


@pytest.mark.parametrize("program", ["python3", "python", "python3.12", "/usr/bin/python3"])
def test_t4_a_python_program_is_substituted(program):
    # axis: every python spelling in the run command is replaced by the launcher, so none runs as written
    record = break_it.run_one("/nonexistent", "", _python_block(program=program), interpreter=None)
    assert (record["outcome"], record["reason"]) == ("not-run", "interpreter-unresolved")


@pytest.mark.parametrize("program", ["scripts/pinned-python", "pytest", "npx", "python3x"])
def test_t4_a_non_python_program_is_not_substituted(program):
    # axis: only a python program is replaced — a launcher, pytest, npx, or `python3x` is left to run as written
    record = break_it.run_one("/nonexistent", "", _python_block(program=program), interpreter=None)
    assert record["reason"] == "head-unresolved"
    assert record["interpreter"] is None


def test_t4_a_non_python_run_with_a_launcher_supplied_runs_as_written(launcher_repo):
    # axis: a supplied launcher is not consulted for a non-python run, so a broken one cannot turn it into not-run
    record = break_it.run_one(str(launcher_repo), TB._head(launcher_repo),
                              _python_block(program=FAKE), interpreter="scripts/missing-python")
    assert record["outcome"] == "failed"
    assert MARKER in record["output"]
    assert record["interpreter"] is None


def test_t4_the_resolver_executes_nothing(tmp_path):
    # axis: resolving the launcher only reads the verify-command text; no part of it is ever executed
    marker = tmp_path / "ran"
    command = "touch %s && %s/x.py -m" % (marker, tmp_path)
    break_it.project_interpreter(command)
    break_it.project_interpreter("%s/tool %s/x.py" % (tmp_path, tmp_path))
    assert not marker.exists()


# ---- E5: no interpreter supplied is today's behaviour ---------------------------------------

def test_e5_without_an_interpreter_the_command_runs_as_written(repo):
    # axis: with no interpreter argument `run_one` behaves as before and records `interpreter` as None
    record = break_it.run_one(str(repo), TB._head(repo), TB._block(TEST_PATH, FAILING_TEST))
    assert record["outcome"] == "failed" and record["exitCode"] == 3
    assert record["interpreter"] is None
    assert "interpreter" in break_it._record("H", {}, "passed")


def test_e5_intercept_forwards_an_interpreter_only_when_one_is_supplied(repo):
    # axis: `intercept` adds the `interpreter` kwarg to the runner call only when the caller passed one
    seen = []

    def runner(repo_root, head, block, **kwargs):
        seen.append(kwargs)
        return break_it._record(head, block, "passed", exit_code=0)

    findings = [TB._finding("t/real.py")]
    break_it.intercept(findings, str(repo), "H", runner=runner)
    break_it.intercept(findings, str(repo), "H", runner=runner, interpreter=FAKE)
    break_it.intercept(findings, str(repo), "H", runner=runner, interpreter=None)
    assert seen == [{}, {"interpreter": FAKE}, {"interpreter": None}]


# ---- T5: the kept-check -----------------------------------------------

def test_t5_check_kept_reruns_under_the_launcher(launcher_repo):
    # axis: the kept-check re-run uses the supplied launcher, so a kept test is judged on the project's interpreter
    base, head, record = TB._kept_fixture(launcher_repo, "pass\n")
    record["command"] = "python3 tests/test_k.py"
    result = break_it.check_kept(str(launcher_repo), base, head, record, interpreter=FAKE)
    assert result["outcome"] == "kept"
    assert MARKER in result["run"]["output"]
    assert result["run"]["interpreter"] == FAKE


def test_t5_check_kept_with_no_launcher_is_not_a_pass(launcher_repo):
    # axis: a kept-check with no resolvable launcher reads failing (`interpreter-unresolved`), never kept
    base, head, record = TB._kept_fixture(launcher_repo, "pass\n")
    record["command"] = "python3 tests/test_k.py"
    result = break_it.check_kept(str(launcher_repo), base, head, record, interpreter=None)
    assert (result["outcome"], result["reason"]) == ("failing", "interpreter-unresolved")
    assert result["run"]["outcome"] == "not-run"


def test_the_run_rules_state_the_launcher_rule():
    # axis: the break-it run rules shown to the finder state the launcher rule
    assert "project's own interpreter launcher" in break_it.RUN_RULES
