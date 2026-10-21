"""Tests for #2021: the generated dependency hook script behaves the same under an inherited `nounset`.

The script is written into a throwaway git repository under tmp_path and run with bash, once with
`SHELLOPTS=nounset` in the environment and once without. Every git and bash subprocess pins its global
and system git configuration away and keeps no inherited GIT_* routing.
"""
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_dependency_hook as hook  # noqa: E402

COMMANDS = ["true"]
INPUTS = ["package-lock.json"]
# the two names the script's behaviour depends on are dropped, so a test never inherits them
_BASE_ENV = {**{k: v for k, v in os.environ.items()
                if not k.startswith("GIT_") and k not in ("SHELLOPTS", "CLAUDE_CODE_REMOTE")},
             "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}

# (id, arguments from the fingerprint, CLAUDE_CODE_REMOTE or None for unset, exit status the script defines)
MODES = [
    ("no-args-local", lambda fp: [], None, 0),
    ("no-args-cloud", lambda fp: [], "true", 0),
    ("record-no-fingerprint", lambda fp: ["--record"], None, 2),
    ("record-right-fingerprint", lambda fp: ["--record", fp], None, 0),
    ("record-wrong-fingerprint", lambda fp: ["--record", "0" * 64], None, 2),
]


def _repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], env=_BASE_ENV, check=True,
                   capture_output=True)
    done = hook.sync(str(repo), list(COMMANDS), list(INPUTS), True)
    assert done["action"] == "written", done
    return repo / hook.SCRIPT_REL.replace("/", os.sep)


def _run(script, args, remote, nounset):
    env = dict(_BASE_ENV)
    if nounset:
        env["SHELLOPTS"] = "nounset"
    if remote is not None:
        env["CLAUDE_CODE_REMOTE"] = remote
    return subprocess.run(["bash", str(script), *args], capture_output=True, env=env, timeout=60)


@pytest.mark.parametrize("make_args,remote,expected", [m[1:] for m in MODES], ids=[m[0] for m in MODES])
def test_the_script_never_dies_of_an_unbound_variable_under_nounset(
        tmp_path, make_args, remote, expected):
    script = _repo(tmp_path)
    args = make_args(hook.fingerprint(COMMANDS, INPUTS))
    plain = _run(script, args, remote, nounset=False)
    strict = _run(script, args, remote, nounset=True)
    err = strict.stderr.decode("utf-8", "replace")
    assert strict.returncode != 1, err
    assert "unbound variable" not in err, err
    assert plain.returncode == expected, plain.stdout.decode() + plain.stderr.decode()
    assert strict.returncode == plain.returncode, err
    assert strict.stdout == plain.stdout
