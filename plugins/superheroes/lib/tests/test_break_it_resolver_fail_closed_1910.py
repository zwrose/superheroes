import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import break_it  # noqa: E402
import test_break_it_interpreter_1910 as TI  # noqa: E402
from test_break_it import repo  # noqa: E402,F401  (the fixture, reused by name)
import test_break_it as TB  # noqa: E402


@pytest.mark.parametrize("command, expected", [
    ("scripts/pinned-python \\\n -m pytest", "scripts/pinned-python"),
    ("scripts/pinned-python \\\n  .github/scripts/x.py", "scripts/pinned-python"),
    ("make test\nscripts/pinned-python -m pytest", "scripts/pinned-python"),
    ("echo hi \\\n && scripts/pinned-python x.py", "scripts/pinned-python"),
    ("env -C scripts ./pinned-python ../.github/scripts/x.py", "scripts/pinned-python"),
    ("env -C scripts ./pinned-python x.py", "scripts/pinned-python"),
    ("env --chdir=scripts ./pinned-python x.py", "scripts/pinned-python"),
    ("env --chdir scripts ./pinned-python x.py", "scripts/pinned-python"),
    ("env -Cscripts tools/launch -m pytest", "scripts/tools/launch"),
    ("env -C a -C b ./pinned-python x.py", "b/pinned-python"),
    ("env -C plugins -C scripts ./pinned-python x.py", "scripts/pinned-python"),
    ("env -C a -C /abs ./pinned-python x.py", None),
    ("env -C /abs -C scripts ./pinned-python x.py", "scripts/pinned-python"),
    ("env -C . ./python3 -m pytest", "./python3"),
    ("env -C . ./pinned-python x.py", "./pinned-python"),
    ("env -C scripts/.. ./pinned-python x.py", "./pinned-python"),
    ("env -C scripts ../bin/pinned-python x.py", "bin/pinned-python"),
    ("env -C scripts ../../pinned-python x.py", None),
    ("env -C /abs ./pinned-python x.py", None),
    ("env -C /abs /abs/pinned-python x.py", "/abs/pinned-python"),
    ("env -C scripts python3 -m pytest", "python3"),
])
def test_resolver_continuations_and_env_chdir(command, expected):
    # axis: a line continuation joins, never splits, the command; a relative launcher after env -C fails closed to unresolved
    assert break_it.project_interpreter(command) == expected


def test_a_non_python_launcher_never_satisfies_the_readiness_probe(repo):
    # axis: an echo-like launcher exits zero without running Python, so the run reads not-run, never passed
    TB._write(repo, "scripts/echo-launcher", "#!/bin/sh\necho \"$@\"\n")
    os.chmod(str(repo / "scripts/echo-launcher"), 0o755)
    TB._commit(repo, "echo launcher")
    record = break_it.run_one(str(repo), TB._head(repo), TI._python_block(), interpreter="scripts/echo-launcher")
    assert (record["outcome"], record["reason"]) == ("not-run", "interpreter-unavailable")
