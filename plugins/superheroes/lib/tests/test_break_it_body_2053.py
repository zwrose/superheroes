"""#2053: a fixed break-it finding's test counts as kept by what it checks, not by its bytes.

Covers the core (`break_it_body`), the Python front (`break_it_body_py`) and the body search in
`break_it.check_kept` / `break_it._rewrite_command`. Real `check_kept` runs use real `python -m pytest`
commands in a throwaway fixture repo; a stub runner stands in only where a test needs to see the command."""
import ast
import hashlib
import os
import shlex
import subprocess
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import break_it  # noqa: E402
import break_it_body  # noqa: E402
import break_it_body_py as front  # noqa: E402

PY = shlex.quote(sys.executable)
# The fixture repo's commits pass an inline identity (a CI runner has no configured one); the throwaway fixture repo also signs nothing.
_ID = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]


def _git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def _commit(repo, message):
    _git(repo, "add", "-A")
    _git(repo, *_ID, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _write(repo, rel, text):
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        target.write_bytes(text)
    else:
        target.write_text(text)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _write(root, "README.md", "fixture\n")
    _write(root, "mod.py", "def value():\n    return 2\n")
    _commit(root, "base")
    return root


IMPORTS = "from math import sqrt\n\nimport pytest\n"
BODY = '''
LABEL = "nine"


@pytest.fixture
def side():
    return 9


def test_x(side):
    for n in (side, side):
        assert sqrt(n) == 3, LABEL
'''
ORIG = IMPORTS + BODY
OWN = "tests/test_k.py"
# The same test after a formatter: quotes, wrapping inside parentheses, trailing commas, comments, blank lines.
FORMATTED = '''import pytest  # the fixture library
from math import sqrt

# the label
LABEL = 'nine'

@pytest.fixture
def side():
    return (9)
def test_x(
    side,
):
    for n in (
        side,
        side,
    ):
        assert sqrt(n) == 3, (
            LABEL
        )
'''


def _host(imports=IMPORTS, before="", body=BODY, after=""):
    return imports + before + body + after


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cmd(path=OWN, extra=""):
    return "%s -m pytest -p no:cacheprovider -q %s%s" % (PY, path, extra)


def _record(content=ORIG, path=OWN, command=None, **extra):
    out = {"path": path, "command": command if command is not None else _cmd(path),
           "sha256": _sha(content), "content": content}
    out.update(extra)
    return out


def _stage(repo, files):
    """Commit ``files`` ({path: text or bytes}) on top of the fixture base; return (base, head)."""
    base = _git(repo, "rev-parse", "HEAD")
    for rel, text in files.items():
        _write(repo, rel, text)
    return base, _commit(repo, "head")


def _stub(calls, outcome="passed", reason=None):
    def runner(repo_root, head, block, **kwargs):
        calls.append(dict(block))
        return break_it._record(head, block, outcome, reason=reason, exit_code=0 if outcome == "passed" else 1)
    return runner


def _spy(calls):
    """A runner that records the block it was handed and then really runs it."""
    def runner(repo_root, head, block, **kwargs):
        calls.append(dict(block))
        return break_it.run_one(repo_root, head, block, **kwargs)
    return runner


def _got(result):
    return result["outcome"], result["reason"]


def _check(repo, base, head, record, runner=None):
    kwargs = {"runner": runner} if runner else {}
    return break_it.check_kept(str(repo), base, head, record, **kwargs)


# ---- 1. formatter case --------------------------------------------------------------------------

def test_formatter_case_is_kept_by_body_and_runs_the_original_command_byte_for_byte(repo):
    base, head = _stage(repo, {OWN: FORMATTED})
    # Doubled spaces and a quoted path: a command rebuilt from its tokens would not be these bytes.
    command = "%s  -m pytest -p no:cacheprovider -q  '%s'" % (PY, OWN)
    calls = []
    result = _check(repo, base, head, _record(command=command), _spy(calls))
    assert _got(result) == ("kept", "body-match")
    assert result["run"]["outcome"] == "passed"
    assert result["path"] == OWN
    assert [c["run"] for c in calls] == [command]
    assert calls[0]["path"] == OWN


# ---- 2. moved and renamed (the consuming project's shape) -----------------------------------------------

def test_moved_and_renamed_test_is_kept_and_the_run_names_the_new_path(repo):
    host = _host(imports="import fractions\n" + IMPORTS, body=BODY.replace("test_x", "test_x_moved"),
                 after="\n\ndef test_own():\n    assert fractions.Fraction(1, 2) * 2 == 1\n")
    base, head = _stage(repo, {"tests/test_weekly.py": host})
    calls = []
    result = _check(repo, base, head, _record(), _spy(calls))
    assert _got(result) == ("kept", "body-match")
    assert result["run"]["outcome"] == "passed"
    assert result["path"] == OWN
    assert [c["run"] for c in calls] == [_cmd("tests/test_weekly.py")]
    assert calls[0]["path"] == "tests/test_weekly.py"


# ---- 3 and 4. a changed test is not kept, at its own path or moved ------------------------------

CHANGES = {
    "assertion-value": lambda t: t.replace("== 3", "== 4"),
    "fixture-value": lambda t: t.replace("return 9", "return 16"),
    "assertion-dedented": lambda t: t.replace("    for n in (side, side):\n        assert sqrt(n) == 3, LABEL\n",
                                              "    for n in (side, side):\n        pass\n    assert sqrt(n) == 3, LABEL\n"),
}


@pytest.mark.parametrize("change", sorted(CHANGES))
def test_a_changed_test_at_its_own_path_reads_changed(repo, change):
    assert CHANGES[change](ORIG) != ORIG
    base, head = _stage(repo, {OWN: CHANGES[change](ORIG)})
    assert _got(_check(repo, base, head, _record())) == ("changed", "sha256-differs")


@pytest.mark.parametrize("change", sorted(CHANGES))
def test_a_changed_test_in_a_moved_copy_reads_missing(repo, change):
    base, head = _stage(repo, {"tests/test_moved.py": CHANGES[change](ORIG)})
    assert _got(_check(repo, base, head, _record())) == ("missing", "not-in-head")


# ---- 5. moved but failing ------------------------------------------------------------------------

def test_a_moved_test_whose_host_file_fails_reads_failing(repo):
    host = _host(after="\n\ndef test_own():\n    assert False, 'host failure'\n")
    base, head = _stage(repo, {"tests/test_weekly.py": host})
    result = _check(repo, base, head, _record())
    assert result["outcome"] == "failing"
    assert result["run"]["outcome"] == "failed"
    assert "host failure" in result["run"]["output"]


# ---- 6. uncheckable: every one reads unresolved or not kept, never kept --------------------------

def test_unparseable_original_is_body_unparseable(repo):
    content = "def test_x(:\n"
    base, head = _stage(repo, {OWN: ORIG})
    assert _got(_check(repo, base, head, _record(content=content))) == ("unresolved", "body-unparseable")


def test_original_with_only_imports_is_body_empty(repo):
    base, head = _stage(repo, {OWN: ORIG})
    assert _got(_check(repo, base, head, _record(content=IMPORTS))) == ("unresolved", "body-empty")


def test_prefilter_passing_unparseable_candidate_is_unresolved_beside_a_match(repo):
    broken = ORIG + "\nbroken = (\n"
    base, head = _stage(repo, {"tests/test_weekly.py": ORIG.replace("test_x", "test_y"), "tests/broken.py": broken})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "body-unparseable")
    assert calls == []


def test_prefilter_passing_unparseable_candidate_without_a_match_is_unresolved(repo):
    broken = ORIG + "\nbroken = (\n"
    base, head = _stage(repo, {"tests/broken.py": broken})
    assert _got(_check(repo, base, head, _record())) == ("unresolved", "body-unparseable")


def test_unparseable_candidate_that_fails_the_prefilter_is_never_parsed(repo):
    base, head = _stage(repo, {"tests/test_weekly.py": ORIG.replace("test_x", "test_y"), "tests/broken.py": "def (:\n"})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("kept", "body-match")
    assert len(calls) == 1


def test_undecodable_candidate_is_unresolved(repo):
    base, head = _stage(repo, {"tests/test_weekly.py": ORIG.replace("test_x", "test_y"),
                               "tests/binary.py": b"\xff\xfe sqrt side LABEL pytest\n"})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "body-unparseable")
    assert calls == []


def test_two_matching_copies_are_ambiguous(repo):
    base, head = _stage(repo, {"tests/test_a.py": ORIG.replace("test_x", "test_a"),
                               "tests/test_b.py": ORIG.replace("test_x", "test_b")})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "match-ambiguous")
    assert calls == []


def test_a_copy_beside_the_changed_original_is_ambiguous(repo):
    base, head = _stage(repo, {OWN: FORMATTED, "tests/test_b.py": ORIG.replace("test_x", "test_b")})
    assert _got(_check(repo, base, head, _record())) == ("unresolved", "match-ambiguous")


def test_host_that_lacks_an_import_the_test_binds_is_a_binding_conflict(repo):
    base, head = _stage(repo, {"tests/test_weekly.py": _host(imports="import pytest\n")})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "binding-conflict")
    assert calls == []


def test_host_that_binds_an_imported_name_another_way_is_a_binding_conflict(repo):
    imports = "from math import sqrt\nimport math as sqrt\n\nimport pytest\n"
    base, head = _stage(repo, {"tests/test_weekly.py": _host(imports=imports)})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "binding-conflict")
    assert calls == []


def test_host_star_import_is_host_setup(repo):
    base, head = _stage(repo, {"tests/test_weekly.py": _host(imports=IMPORTS + "from os.path import *\n")})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "host-setup")
    assert calls == []


@pytest.mark.parametrize("before", [
    "def sqrt(x):\n    return 3\n\n\n",
    "LABEL = 'ten'\n\n\n",
], ids=["helper-def", "assignment"])
def test_host_statement_that_rebinds_a_name_the_test_uses_is_a_binding_conflict(repo, before):
    base, head = _stage(repo, {"tests/test_weekly.py": _host(before=before)})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "binding-conflict")
    assert calls == []


def test_host_loop_that_rebinds_a_name_the_test_uses_is_host_setup(repo):
    base, head = _stage(repo, {"tests/test_weekly.py": _host(before="for side in (1, 2):\n    pass\n\n\n")})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "host-setup")
    assert calls == []


@pytest.mark.parametrize("before", [
    "@pytest.fixture(autouse=True)\ndef _env():\n    pass\n\n\n",
    "pytestmark = pytest.mark.filterwarnings('ignore')\n\n\n",
], ids=["autouse-fixture", "pytestmark"])
def test_host_module_level_test_setup_is_host_setup(repo, before):
    base, head = _stage(repo, {"tests/test_weekly.py": _host(before=before)})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "host-setup")
    assert calls == []


def test_host_fixture_with_autouse_false_is_still_host_setup(repo):
    before = "@pytest.fixture(autouse=False)\ndef other():\n    return 1\n\n\n"
    base, head = _stage(repo, {"tests/test_weekly.py": _host(before=before)})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "host-setup")
    assert calls == []


@pytest.mark.parametrize("imports", [
    "from helpers import setup_module\n",
    "from helpers import setUpModule\n",
    "from helpers import anything as pytestmark\n",
    "from helpers import *\n",
], ids=["setup_module", "setUpModule", "aliased-pytestmark", "star"])
def test_an_imported_runner_hook_binding_is_host_setup(imports):
    original = "def test_a():\n    assert 1 == 1\n"
    got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", imports + original)])
    assert (got["status"], got["reason"]) == ("unresolved", "host-setup")


def test_a_from_import_of_a_standard_library_name_the_host_adds_is_host_setup():
    original = "def test_a():\n    assert 1 == 1\n"
    got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", "from os import path\n" + original)])
    assert (got["status"], got["reason"]) == ("unresolved", "host-setup")


def test_a_from_import_of_a_name_a_project_file_may_shadow_is_host_setup():
    original = "def test_a():\n    assert False\n"
    got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", "from code import shared_environment\n" + original)])
    assert (got["status"], got["reason"]) == ("unresolved", "host-setup")


def test_a_plain_module_import_the_host_adds_is_still_allowed():
    original = "def test_a():\n    assert 1 == 1\n"
    got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", "import os\nimport json as j\n" + original)])
    assert got["status"] == "found"


def test_a_name_imported_from_a_project_module_may_be_an_autouse_fixture_and_is_refused():
    original = "def test_a():\n    assert False\n"
    got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", "from shared_fixtures import shared_environment\n" + original)])
    assert (got["status"], got["reason"]) == ("unresolved", "host-setup")


def test_a_relative_future_from_import_the_host_adds_is_never_found():
    # the pinned CPython refuses to compile this shape (it reads the module as a future statement), so the
    # front cannot read it; where an interpreter does read it, the level check makes it host-setup
    original = "def test_a():\n    assert False\n"
    got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", "from .__future__ import shared_environment\n" + original)])
    assert got["status"] == "unresolved" and got["reason"] in ("host-setup", "body-unparseable")


def test_a_relative_future_from_import_of_a_real_feature_name_is_host_setup():
    # compiles, yet loads the package's own __future__.py, whose ``annotations`` can be an autouse fixture
    original = "def test_a():\n    assert False\n"
    got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", "from .__future__ import annotations\n" + original)])
    assert (got["status"], got["reason"]) == ("unresolved", "host-setup")


def test_the_relative_future_pair_alone_is_classed_as_a_possible_fixture():
    assert break_it_body._may_import_fixture(("shared_environment", ("from", 1, "__future__", "shared_environment")))
    assert not break_it_body._may_import_fixture(("annotations", ("from", 0, "__future__", "annotations")))


def test_reversed_imports_binding_one_name_twice_are_a_binding_conflict():
    original = "from math import floor as value\nfrom math import ceil as value\n\n\ndef test_a():\n    assert value(0.1) == 0\n"
    host = "from math import ceil as value\nfrom math import floor as value\n\n\ndef test_a():\n    assert value(0.1) == 0\n"
    got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", host)])
    assert (got["status"], got["reason"]) == ("unresolved", "binding-conflict")


def test_a_host_that_binds_an_imported_name_by_a_later_assignment_is_a_binding_conflict():
    original = "from math import floor as value\n\n\ndef test_a():\n    assert value(0.1) == 0\n"
    got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", original + "\n\nvalue = 1\n")])
    assert (got["status"], got["reason"]) == ("unresolved", "binding-conflict")


def test_one_import_per_name_is_unaffected_by_the_rebinding_rule():
    original = "from math import floor as value\nimport os\n\n\ndef test_a():\n    assert value(0.1) == 0 and os.sep\n"
    got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", original)])
    assert (got["status"], got["path"]) == ("found", "tests/test_b.py")


def test_a_host_that_adds_future_annotations_is_refused():
    original = "def helper(value: int):\n    return value\n\n\ndef test_a():\n    assert helper.__annotations__['value'] == 'int'\n"
    got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", "from __future__ import annotations\n" + original)])
    assert (got["status"], got["reason"]) == ("unresolved", "binding-conflict")


def test_a_rename_that_loses_the_test_underscore_prefix_is_refused():
    original = "def test_regression():\n    assert False\n"
    got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", original.replace("test_regression", "testing_regression"))])
    assert (got["status"], got["reason"]) == ("unresolved", "binding-conflict")


def test_an_ordinary_helper_parameter_is_no_fixture_dependency():
    original = "def helper(value):\n    return value + 1\n\n\ndef test_x():\n    assert helper(1) == 2\n"
    got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", "value = 99\n" + original)])
    assert got["status"] == "found"


@pytest.mark.parametrize("source", [
    "def test_x(value):\n    assert value\n",
    "class TestX:\n    def test_x(self, value):\n        assert value\n",
    "@pytest.fixture\ndef value(other):\n    return other\n",
    "@fx\ndef value(other):\n    return other\n",
], ids=["test-function", "test-method", "fixture", "aliased-fixture"])
def test_a_test_or_fixture_parameter_is_still_a_dependency(source):
    source = "import pytest\nfrom pytest import fixture as fx\n" + source
    got = break_it_body.locate(source, "tests/test_a.py", [("tests/test_b.py", "value = 1\nother = 2\n" + source)])
    assert (got["status"], got["reason"]) == ("unresolved", "binding-conflict")


def test_a_test_methods_self_parameter_is_no_dependency():
    original = "class TestX:\n    def test_x(self):\n        assert 1\n"
    got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", "self = 1\n" + original)])
    assert got["status"] == "found"


@pytest.mark.parametrize("helper", [
    "def helper(_=setattr(TestR, '__unittest_skip__', True)):\n    pass\n",
    "def helper(*, _=print()):\n    pass\n",
    "def helper(x: print() = 1):\n    pass\n",
    "def helper() -> print():\n    pass\n",
], ids=["default", "kw-default", "annotation", "return"])
def test_a_host_def_whose_signature_runs_code_is_host_setup(helper):
    original = "class TestR:\n    def test_a(self):\n        assert 1 == 1\n"
    for host in (helper + "\n\n" + original, original + "\n\n" + helper):
        got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", host)])
        assert (got["status"], got["reason"]) == ("unresolved", "host-setup")


def test_a_host_method_whose_signature_runs_code_is_host_setup():
    original = "class TestR:\n    def test_a(self):\n        assert 1 == 1\n"
    host = original + "\n\nclass Aux:\n    def meth(self, _=print()):\n        pass\n"
    got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", host)])
    assert (got["status"], got["reason"]) == ("unresolved", "host-setup")


def test_a_plain_host_def_is_allowed():
    original = "def test_a():\n    assert 1 == 1\n"
    host = "def helper(x=1, *, y: int = 2) -> int:\n    return x\n\n\n" + original
    assert break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", host)])["status"] == "found"


@pytest.mark.parametrize("order", ["after", "before"])
def test_a_rename_onto_another_retained_tests_name_is_a_binding_conflict(order):
    original = "def test_regression():\n    assert 1 == 2\n"
    renamed = "def test_x():\n    assert 1 == 2\n"
    other = "def test_x():\n    assert True\n"
    host = renamed + "\n\n" + other if order == "after" else other + "\n\n" + renamed
    got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", host)])
    assert (got["status"], got["reason"]) == ("unresolved", "binding-conflict")


def test_a_rename_onto_a_sibling_test_inside_one_class_is_a_binding_conflict():
    original = "class TestX:\n    def test_regression(self):\n        assert 1 == 2\n\n    def test_smoke(self):\n        assert True\n"
    renamed = original.replace("test_regression", "test_smoke", 1)
    got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", renamed)])
    assert (got["status"], got["reason"]) == ("unresolved", "binding-conflict")


def test_a_rename_that_collides_two_classes_of_one_module_is_a_binding_conflict():
    original = ("class TestFirst:\n    def test_a(self):\n        assert 1 == 2\n\n    def test_b(self):\n        assert 1 == 4\n\n\n"
                "class TestSecond:\n    def test_a(self):\n        assert 1 == 3\n")
    # the whole file still holds two distinct test names, yet TestFirst runs only its last test_x
    renamed = (original.replace("TestFirst:\n    def test_a", "TestFirst:\n    def test_x").replace("def test_b", "def test_x")
               .replace("TestSecond:\n    def test_a", "TestSecond:\n    def test_y"))
    got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", renamed)])
    assert (got["status"], got["reason"]) == ("unresolved", "binding-conflict")


def test_independent_renames_in_different_classes_are_found():
    original = ("class TestA:\n    def test_x(self):\n        assert 1 == 2\n\n\n"
                "class TestB:\n    def test_y(self):\n        assert 1 == 3\n")
    renamed = original.replace("test_x", "test_one").replace("test_y", "test_one")
    got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", renamed)])
    assert got["status"] == "found"


def test_a_duplicated_setup_statement_in_the_host_is_host_setup():
    original = "state = []\nstate.append(1)\n\n\ndef test_a():\n    assert state == [1]\n"
    host = "state.append(1)\n\n\n" + original
    got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", host)])
    assert (got["status"], got["reason"]) == ("unresolved", "host-setup")


def test_a_host_with_import_pytest_and_a_moved_test_is_found():
    original = "def test_a():\n    assert 1 == 1\n"
    got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", "import pytest\n\n\n" + original)])
    assert got["status"] == "found"


def test_a_host_importing_pytest_under_another_name_or_a_hook_name_is_host_setup():
    original = "def test_a():\n    assert 1 == 1\n"
    for line in ("import pytest as setup_module\n", "import pytest_cov as pytest\n", "from pytest import pytestmark\n"):
        got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", line + "\n\n" + original)])
        assert (got["status"], got["reason"]) == ("unresolved", "host-setup"), line


def test_a_staticmethod_first_parameter_is_a_fixture_dependency():
    original = "class TestX:\n    @staticmethod\n    def test_x(value):\n        assert value\n"
    got = break_it_body.locate(original, "tests/test_a.py", [("tests/test_b.py", "import os\nvalue = 1\n" + original)])
    assert (got["status"], got["reason"]) == ("unresolved", "binding-conflict")


def test_an_added_skip_decorator_is_not_kept(repo):
    skipped = ORIG.replace("def test_x", "@pytest.mark.skip\ndef test_x")
    base, head = _stage(repo, {OWN: skipped})
    assert _got(_check(repo, base, head, _record())) == ("changed", "sha256-differs")


def test_an_added_type_ignore_directive_is_not_kept(repo):
    ignored = ORIG.replace("return 9", "return 9  # type: ignore")
    base, head = _stage(repo, {OWN: ignored})
    assert _got(_check(repo, base, head, _record())) == ("changed", "sha256-differs")


def test_a_renamed_helper_is_not_a_title_and_reads_changed(repo):
    content = ORIG + "\n\ndef helper():\n    return 1\n"
    base, head = _stage(repo, {OWN: content.replace("def helper", "def helper2")})
    assert _got(_check(repo, base, head, _record(content=content))) == ("changed", "sha256-differs")


def test_a_moved_test_whose_command_names_no_path_is_command_unmapped(repo):
    base, head = _stage(repo, {"tests/test_weekly.py": _host()})
    calls = []
    record = _record(command="%s -m pytest -p no:cacheprovider -q" % PY)
    assert _got(_check(repo, base, head, record, _stub(calls))) == ("unresolved", "command-unmapped")
    assert calls == []


def test_a_renamed_moved_test_whose_command_carries_k_is_command_selects_tests(repo):
    base, head = _stage(repo, {"tests/test_weekly.py": _host(body=BODY.replace("test_x", "test_y"))})
    calls = []
    record = _record(command=_cmd(extra=" -k regression"))
    assert _got(_check(repo, base, head, record, _stub(calls))) == ("unresolved", "command-selects-tests")
    assert calls == []


def test_a_renamed_test_at_its_own_path_with_a_selector_is_command_selects_tests(repo):
    base, head = _stage(repo, {OWN: FORMATTED.replace("test_x", "test_y")})
    calls = []
    record = _record(command=_cmd(OWN + "::test_x"))
    assert _got(_check(repo, base, head, record, _stub(calls))) == ("unresolved", "command-selects-tests")
    assert calls == []


def test_a_moved_test_that_is_not_renamed_keeps_a_name_filter_free_command(repo):
    base, head = _stage(repo, {"tests/test_weekly.py": _host()})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("kept", "body-match")
    assert [c["run"] for c in calls] == [_cmd("tests/test_weekly.py")]


def test_a_found_test_that_the_run_does_not_pass_reads_failing_with_the_run_reason(repo):
    base, head = _stage(repo, {OWN: FORMATTED})
    result = _check(repo, base, head, _record(), _stub([], "not-run", "timeout"))
    assert result["outcome"] == "failing" and result["reason"] == "timeout"
    assert result["run"]["outcome"] == "not-run" and result["run"]["reason"] == "timeout"


def test_a_rename_is_unresolved_when_pytest_ini_sets_python_functions(repo):
    base, head = _stage(repo, {"pytest.ini": "[pytest]\npython_functions = check_*\n", OWN: FORMATTED.replace("test_x", "test_y")})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "binding-conflict")
    assert calls == []


def test_the_same_rename_without_a_collection_override_is_found(repo):
    base, head = _stage(repo, {"pytest.ini": "[pytest]\nminversion = 6\n", OWN: FORMATTED.replace("test_x", "test_y")})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("kept", "body-match")


def test_a_rename_is_unresolved_when_pytest_ini_sets_addopts(repo):
    base, head = _stage(repo, {"pytest.ini": "[pytest]\naddopts = -k test_x\n", OWN: FORMATTED.replace("test_x", "test_y")})
    calls = []
    assert _got(_check(repo, base, head, _record(), _stub(calls))) == ("unresolved", "binding-conflict")
    assert calls == []


# ---- 7. census: every other reason reads exactly as today, with a content-bearing record ---------

def test_census_input_missing(repo):
    base, head = _stage(repo, {OWN: FORMATTED})
    assert _got(_check(repo, base, head, _record(command=""))) == ("unresolved", "input-missing")


def test_census_input_unsafe(repo):
    base, head = _stage(repo, {OWN: FORMATTED})
    assert _got(_check(repo, base, head, _record(path="../x.py"))) == ("unresolved", "input-unsafe")


def test_census_ls_tree_failed(repo):
    base, head = _stage(repo, {OWN: FORMATTED})
    assert _got(_check(repo, base, "no-such-rev", _record())) == ("unresolved", "ls-tree-failed")


def test_census_not_a_regular_file(repo):
    (repo / "tests").mkdir()
    os.symlink("../README.md", str(repo / OWN))
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit(repo, "symlink")
    assert _got(_check(repo, base, head, _record())) == ("not-regular", "not-a-regular-file")


def test_census_diff_failed(repo):
    _, head = _stage(repo, {OWN: FORMATTED})
    assert _got(_check(repo, "no-such-rev", head, _record())) == ("unresolved", "diff-failed")


def test_census_cat_file_failed(repo, monkeypatch):
    base, head = _stage(repo, {OWN: FORMATTED})
    real = break_it._git

    def fake(repo_root, *args):
        if args[0] == "cat-file":
            return subprocess.CompletedProcess(args, 1, b"", b"boom")
        return real(repo_root, *args)
    monkeypatch.setattr(break_it, "_git", fake)
    assert _got(_check(repo, base, head, _record())) == ("unresolved", "cat-file-failed")


def test_census_git_failed(repo, monkeypatch):
    base, head = _stage(repo, {OWN: FORMATTED})

    def fake(repo_root, *args):
        raise OSError("no git")
    monkeypatch.setattr(break_it, "_git", fake)
    assert _got(_check(repo, base, head, _record())) == ("unresolved", "git-failed")


def test_census_kept_by_exact_bytes_has_no_reason(repo):
    base, head = _stage(repo, {OWN: ORIG})
    assert _got(_check(repo, base, head, _record())) == ("kept", None)


def test_census_failing_by_exact_bytes(repo):
    failing = ORIG.replace("== 3", "== 4")
    base, head = _stage(repo, {OWN: failing})
    assert _got(_check(repo, base, head, _record(content=failing)))[0] == "failing"


def test_a_record_without_content_keeps_the_byte_exact_check(repo):
    base, head = _stage(repo, {OWN: FORMATTED})
    record = _record()
    del record["content"]
    calls = []
    assert _got(_check(repo, base, head, record, _stub(calls))) == ("changed", "sha256-differs")
    assert calls == []
    base, head = _stage(repo, {"tests/test_moved.py": ORIG})
    assert _got(_check(repo, base, head, record, _stub(calls))) == ("missing", "not-in-diff")
    assert calls == []


def test_a_record_whose_content_is_not_a_string_keeps_the_byte_exact_check(repo):
    base, head = _stage(repo, {OWN: FORMATTED})
    record = _record()
    record["content"] = None
    assert _got(_check(repo, base, head, record)) == ("changed", "sha256-differs")


# ---- 8. unsupported language ---------------------------------------------------------------------

def test_a_go_record_with_content_and_changed_bytes_reads_changed(repo):
    content = "package pkg\n\nfunc TestX(t *testing.T) {}\n"
    base, head = _stage(repo, {"pkg/x_test.go": content + "\n// edited\n", "tests/test_k.py": ORIG})
    record = _record(content=content, path="pkg/x_test.go", command="go test ./pkg")
    calls = []
    assert _got(_check(repo, base, head, record, _stub(calls))) == ("changed", "sha256-differs")
    assert calls == []


def test_a_go_record_missing_from_head_reads_missing(repo):
    base, head = _stage(repo, {"tests/test_k.py": ORIG})
    record = _record(content="package pkg\n", path="pkg/x_test.go", command="go test ./pkg")
    assert _got(_check(repo, base, head, record)) == ("missing", "not-in-head")


GO = "package pkg\n\nfunc TestX(t *testing.T) {\n\tif 1 != 1 {\n\t\tt.Fatal(\"x\")\n\t}\n}\n"


def test_a_go_record_with_content_and_changed_bytes_reads_changed_never_searched(repo):
    reformatted = GO.replace("\t", "    ")
    base, head = _stage(repo, {"pkg/x_test.go": reformatted, "pkg/copy_test.go": GO})
    record = _record(content=GO, path="pkg/x_test.go", command="go test ./pkg")
    calls = []
    assert _got(_check(repo, base, head, record, _stub(calls))) == ("changed", "sha256-differs")
    assert calls == []


def test_a_go_record_with_content_missing_from_head_reads_missing_though_a_copy_is_carried(repo):
    base, head = _stage(repo, {"pkg/moved_test.go": GO})
    record = _record(content=GO, path="pkg/x_test.go", command="go test ./pkg")
    calls = []
    assert _got(_check(repo, base, head, record, _stub(calls))) == ("missing", "not-in-head")
    assert calls == []


# ---- 9. _record and _rewrite_command -------------------------------------------------------------

def test_record_carries_content():
    block = {"path": "t/x.py", "run": "python t/x.py", "content": "assert True\n", "sha256": "s"}
    assert break_it._record("H", block, "passed")["content"] == "assert True\n"
    assert break_it._record("H", None, "not-run", "path-unsafe")["content"] is None


def test_rewrite_same_path_returns_the_original_string():
    command = "FOO=1   python  'a.py'"
    assert break_it._rewrite_command(command, "a.py", "a.py", []) == (command, None)
    assert break_it._rewrite_command(command, "a.py", "a.py", [("test_x", "test_y")]) == (command, None)


def test_rewrite_keeps_and_quotes_env_entries_on_a_move():
    got = break_it._rewrite_command("FOO=1 BAR='a b' python -q a.py", "a.py", "b/c.py", [])
    assert got == ("FOO=1 'BAR=a b' python -q b/c.py", None)
    argv, env, refusal = break_it.parse_command(got[0])
    assert refusal is None and env == {"FOO": "1", "BAR": "a b"} and argv == ["python", "-q", "b/c.py"]


def test_rewrite_replaces_a_selector_token_on_a_move():
    assert break_it._rewrite_command("python -m pytest a.py::test_x", "a.py", "b.py", []) == (
        "python -m pytest b.py", None)


def test_rewrite_a_path_token_that_contains_an_old_title_is_no_filter():
    titles = [("test_x", "test_y")]
    assert break_it._rewrite_command("python -m pytest t/test_x.py", "t/test_x.py", "t/test_y.py", titles) == (
        "python -m pytest t/test_y.py", None)
    assert break_it._rewrite_command("python -m pytest t/test_x.py", "t/test_x.py", "t/test_x.py", titles) == (
        "python -m pytest t/test_x.py", None)


def test_rewrite_a_path_selector_token_still_refuses_when_the_path_contains_an_old_title():
    titles = [("test_x", "test_y")]
    assert break_it._rewrite_command("python -m pytest t/test_x.py::other", "t/test_x.py", "t/test_y.py", titles) == (
        None, "command-selects-tests")
    assert break_it._rewrite_command("python -m pytest t/test_x.py test_x", "t/test_x.py", "t/test_y.py", titles) == (
        None, "command-selects-tests")


def test_a_test_file_named_after_its_own_test_is_kept_when_the_test_is_renamed_in_place(repo):
    path = "tests/test_x.py"
    base, head = _stage(repo, {path: FORMATTED.replace("test_x", "test_y")})
    calls = []
    assert _got(_check(repo, base, head, _record(path=path), _spy(calls))) == ("kept", "body-match")
    assert [c["run"] for c in calls] == [_cmd(path)]


def test_rewrite_replaces_every_path_token():
    assert break_it._rewrite_command("python a.py a.py", "a.py", "b.py", []) == ("python b.py b.py", None)


@pytest.mark.parametrize("command", ["python a.py | cat", "", "python $(x) a.py", "bash a.py"])
def test_rewrite_refuses_a_command_it_cannot_parse(command):
    assert break_it._rewrite_command(command, "a.py", "a.py", []) == (None, "command-unmapped")


def test_rewrite_refuses_a_move_when_no_token_names_the_old_path():
    assert break_it._rewrite_command("python ./a.py", "a.py", "b.py", []) == (None, "command-unmapped")


@pytest.mark.parametrize("extra", [
    "-k foo", "-t foo", "-g foo", "-kfoo", "-tfoo", "-gfoo", "--testNamePattern foo", "--grep foo", "--filter foo",
    "--match foo", "--testNamePattern=foo", "--grep=foo", "--filter=foo", "--match=foo", "a.py::test_old",
    "test_old",
])
def test_rewrite_refuses_a_renamed_test_whose_command_selects_tests(extra):
    got = break_it._rewrite_command("python -m pytest a.py " + extra, "a.py", "b.py", [("test_old", "test_new")])
    assert got == (None, "command-selects-tests")
    # the same command is fine when no title changed
    assert break_it._rewrite_command("python -m pytest a.py " + extra, "a.py", "a.py", [])[1] is None


def test_rewrite_ignores_environment_data_that_is_not_runner_options():
    titles = [("test_original", "test_moved")]
    for assign in ("PYTHONPATH=/tmp/test_original_support", "APP_LABEL=\"owner's\"", "TESTS_DIR=-k"):
        got = break_it._rewrite_command("%s python -m pytest a.py" % assign, "a.py", "b.py", titles)
        assert got[1] is None, assign


@pytest.mark.parametrize("assign", [
    "PYTEST_ADDOPTS='-k test_original'", "PYTEST_ADDOPTS='a.py::test_original'", "VITEST_OPTIONS='--grep=x'",
    "NODE_OPTIONS='-t x'", "MY_ADDOPTS=\"it's\"", "PYTEST_ADDOPTS=test_original",
])
def test_rewrite_refuses_a_selector_carried_by_a_runner_options_variable(assign):
    got = break_it._rewrite_command("%s python -m pytest a.py" % assign, "a.py", "b.py", [("test_original", "test_moved")])
    assert got == (None, "command-selects-tests")


# ---- 10. the Python front ------------------------------------------------------------------------

def _keys(text):
    return [rec["key"] for rec in front.parse(text)]


@pytest.mark.parametrize("left, right", [
    ("x = 'a'\n", 'x = "a"\n'),
    ("x = (1)\n", "x = 1\n"),
    ("x = foo(1,\n        2)\n", "x = foo(1, 2,)\n"),
    ("x = 'a' 'b'\n", "x = 'ab'\n"),
    ("# lead\n\n\nx = 1  # tail\n", "x = 1\n"),
    ("def f(a,\n      b):\n    return a\n", "def f(a, b): return a\n"),
    ("x = 1  # type: ignore\n", "x = 1  #  type:   ignore\n"),
    ("# type: ignore\nx = 1\n", "x = 1\n"),
])
def test_front_equal_keys_for_formatting_differences(left, right):
    assert _keys(left) == _keys(right)


@pytest.mark.parametrize("left, right", [
    ("x = (1,)\n", "x = (1)\n"),
    ("if c:\n    a = 1\nelse:\n    b = 2\n", "if c:\n    a = 1\n    b = 2\nelse:\n    pass\n"),
    ("def f(): pass\n", "@d\ndef f(): pass\n"),
    ("x = 1\n", "x = 1  # type: ignore\n"),
    ("x = 1  # type: ignore\n", "x = 1  # noqa\n"),
    ("x = foo(\n    1,  # type: ignore\n)\n", "x = foo(\n    1,\n)\n"),
    ("@d  # noqa\ndef f(): pass\n", "@d\ndef f(): pass\n"),
    ("x = 'a'\n", "x = 'b'\n"),
])
def test_front_unequal_keys_for_semantic_differences(left, right):
    assert _keys(left) != _keys(right)


def test_front_fixture_explicit_name_is_a_binding():
    rec = front.parse("@pytest.fixture(name=\"side\")\ndef z_host_side():\n    return 1\n")[0]
    assert {"z_host_side", "side"} <= rec["binds"]
    other = front.parse("@marker(name=\"side\")\ndef z_host_side():\n    return 1\n")[0]
    assert other["binds"] == frozenset(["z_host_side"])
    plain = front.parse("@pytest.fixture(scope=\"module\")\ndef z_host_side():\n    return 1\n")[0]
    assert plain["binds"] == frozenset(["z_host_side"])


def test_front_records_have_exactly_the_contract_keys():
    records = front.parse("import os\nx = 1\n")
    assert [set(rec) for rec in records] == [{"kind", "key", "titles", "imports", "binds", "uses", "defs", "hook", "relative"}] * 2
    assert [rec["kind"] for rec in records] == ["import", "stmt"]
    assert front.EXTENSIONS == (".py",) and front.TITLE == "\x00title"


def test_front_titles_are_test_prefixed_defs_only():
    assert front.parse("def test_a(): pass\n")[0]["titles"] == ("test_a",)
    assert front.parse("async def test_a(): pass\n")[0]["titles"] == ("test_a",)
    assert front.parse("def helper(): pass\n")[0]["titles"] == ()
    assert front.parse("class T:\n    def test_m(self): pass\n    def helper(self): pass\n"
                       "    def test_n(self): pass\n")[0]["titles"] == ("test_m", "test_n")
    assert front.parse("def test_a():\n    def test_inner(): pass\n")[0]["titles"] == ("test_a",)
    assert front.parse("if c:\n    def test_a(): pass\n")[0]["titles"] == ()


def test_front_a_title_does_not_change_the_key_but_any_other_name_does():
    assert _keys("def test_a(): pass\n") == _keys("def test_b(): pass\n")
    assert _keys("class T:\n    def test_m(self): pass\n") == _keys("class T:\n    def test_z(self): pass\n")
    assert _keys("def check_a(): pass\n") != _keys("def check_b(): pass\n")
    assert _keys("class T:\n    def helper(self): pass\n") != _keys("class T:\n    def other(self): pass\n")
    assert _keys("class T:\n    def test_m(self): pass\n") != _keys("class U:\n    def test_m(self): pass\n")


@pytest.mark.parametrize("text", ["def f(:\n", "x = 'abc\n", "x = 1\0\n", "  x = 1\n", "x = (" * 1])
def test_front_unreadable_text_raises_value_error_only(text):
    with pytest.raises(ValueError):
        front.parse(text)


def test_front_non_text_raises_value_error():
    with pytest.raises(ValueError):
        front.parse(None)


def test_front_imports():
    rec = front.parse("import a.b\nimport a.b as c\nfrom .m import n as k\nfrom m import *\nfrom . import q\n")
    assert [r["imports"] for r in rec] == [
        (("a", ("import", "a")),), (("c", ("import", "a.b")),), (("k", ("from", 1, "m", "n")),),
        (("*", ("from", 0, "m", "*")),), (("q", ("from", 1, "", "q")),)]
    assert [r["binds"] for r in rec] == [frozenset({"a"}), frozenset({"c"}), frozenset({"k"}), frozenset(), frozenset({"q"})]
    assert all(r["kind"] == "import" and r["titles"] == () for r in rec)


def test_front_binds_stay_at_module_scope():
    def binds(text):
        return front.parse(text)[0]["binds"]
    assert binds("def f(a=(d := 1)):\n    inner = 1\n") == frozenset({"f", "d"})
    assert binds("@deco\nclass C(Base, metaclass=M):\n    attr = 1\n") == frozenset({"C"})
    assert binds("x, (y, *z) = v\n") == frozenset({"x", "y", "z"})
    assert binds("for i in v:\n    t = i\n") == frozenset({"i", "t"})
    assert binds("with a as b:\n    pass\n") == frozenset({"b"})
    assert binds("try:\n    pass\nexcept E as err:\n    pass\n") == frozenset({"err"})
    assert binds("try:\n    import json\nexcept ImportError:\n    json = None\n") == frozenset({"json"})
    assert binds("match v:\n    case [a, *rest]:\n        pass\n    case {'k': 1, **kw}:\n        pass\n"
                 "    case C() as whole:\n        pass\n") == frozenset({"a", "rest", "kw", "whole"})
    assert binds("global g\n") == frozenset({"g"})
    assert binds("del x\n") == frozenset({"x"})
    assert binds("y = [i for i in v]\n") == frozenset({"y"})
    assert binds("y = [(w := i) for i in v]\n") == frozenset({"y", "w"})
    assert binds("f = lambda a=(q := 1): a\n") == frozenset({"f", "q"})


def test_front_uses_exclude_keyword_names_and_attributes():
    rec = front.parse("def test_a(fx):\n    assert obj.attr == call(kw=val)\n")[0]
    assert rec["uses"] == frozenset({"test_a", "fx", "obj", "call", "val"})
    assert front.parse("class K:\n    pass\n")[0]["uses"] == frozenset({"K"})
    assert front.parse("import a.b as c\n")[0]["uses"] == frozenset({"c"})


def test_front_uses_respect_nested_scopes():
    def uses(text):
        return front.parse(text)[0]["uses"]
    for local in ("len = 0", "import len", "def len(): pass", "class len: pass", "for len in (): pass"):
        text = "def test_x():\n    def helper():\n        %s\n    assert len([]) == 1\n" % local
        assert "len" in uses(text), local
    assert "value" not in uses("def test_x():\n    value = 1\n    assert value == 1\n")
    assert "value" not in uses("def test_x():\n    import value\n    assert value\n")
    assert "len" in uses("def test_x():\n    assert [len for len in (1,)] and len([])\n")
    assert "g" in uses("def test_x():\n    def h():\n        global g\n        g = 1\n")
    assert "z" not in uses("def test_x():\n    z = 1\n    def h():\n        return z\n")
    assert "fx" in uses("class K:\n    def test_a(self, fx):\n        pass\n")


def test_front_uses_ignore_implicit_generator_parameters():
    def uses(text):
        return front.parse(text)[0]["uses"]
    got = uses("total = sum(i for i in range(3))\n")
    assert all(name.isidentifier() for name in got)
    assert "i" not in got and "range" in got
    assert "x" not in uses("f = lambda x: x\n")


def test_class_body_global_fallback_read_is_a_dependency():
    content = ("class TestExample:\n    len = len([])\n\n    def test_x(self):\n        assert self.len == 1\n")
    assert "len" in front.parse(content)[0]["uses"]
    host = "len = lambda xs: 1\n\n" + content
    got = break_it_body.locate(content, "a.py", [("b.py", host)])
    assert (got["status"], got["reason"]) == ("unresolved", "host-setup")


def test_class_private_name_keeps_source_spelling_and_moves():
    content = "class TestExample:\n    __value = 1\n\n    def test_x(self):\n        assert self._TestExample__value == 1\n"
    assert "__value" not in front.parse(content)[0]["uses"]
    content = "class TestExample:\n    x = __value\n\n    def test_x(self):\n        assert self.x\n"
    assert "__value" in front.parse(content)[0]["uses"]
    moved = "class _Example:\n    y = __value\n"
    assert "__value" in front.parse(moved)[0]["uses"]
    got = break_it_body.locate(moved, "a.py", [("b.py", "import os\n\n" + moved)])
    assert (got["status"], got["path"]) == ("found", "b.py")


def test_class_assignment_only_attribute_is_not_a_dependency():
    content = "class TestExample:\n    label = 1\n\n    def test_x(self):\n        assert self.label == 1\n"
    assert "label" not in front.parse(content)[0]["uses"]
    host = "label = 'x'\n\n" + content
    got = break_it_body.locate(content, "a.py", [("b.py", host)])
    assert (got["status"], got["path"]) == ("found", "b.py")


def test_front_hook():
    def hook(text):
        return front.parse(text)[0]["hook"]
    assert hook("@pytest.fixture(autouse=True)\ndef f(): pass\n")
    assert hook("@pytest.fixture(scope='module', autouse=flag)\ndef f(): pass\n")
    assert hook("@pytest.fixture(autouse=False)\ndef f(): pass\n")
    assert hook("@pytest.fixture\ndef f(): pass\n")
    assert hook("@pytest.fixture(scope='module')\ndef f(): pass\n")
    for name in ("pytestmark", "pytest_plugins", "setup_module", "teardown_module", "setUpModule", "tearDownModule",
                 "setup_function", "teardown_function", "load_tests"):
        assert hook("%s = 1\n" % name)
        assert hook("def %s(): pass\n" % name)
    assert not hook("x = 1\n")


# ---- the core -------------------------------------------------------------------------------------

def test_core_supports_python_and_skips_a_missing_front(monkeypatch):
    assert ".py" in break_it_body.supported_suffixes()
    monkeypatch.setattr(break_it_body, "_FRONTS", ("break_it_body_py", "break_it_body_no_such_front"))
    assert break_it_body.supported_suffixes() == frozenset({".py"})
    assert break_it_body.locate("x = 1\n", "a.go", [("a.py", "x = 1\n")])["status"] == "unsupported"


def test_core_unsupported_suffix_and_result_shape():
    got = break_it_body.locate("package p\n", "x_test.go", [("x_test.go", "package p\n")])
    assert got["status"] == "unsupported"
    assert set(got) == {"status", "reason", "path", "titles"}
    found = break_it_body.locate("x = 1\n", "a.py", [("b.py", "y = 2\nx = 1\n")])
    assert found == {"status": "found", "reason": None, "path": "b.py", "titles": []}


def test_core_none_when_no_candidate_holds_the_body():
    assert break_it_body.locate("x = 1\n", "a.py", [("b.py", "x = 2\n"), ("c.py", "x = 1 + 0\n")])["status"] == "none"
    assert break_it_body.locate("x = 1\n", "a.py", [])["status"] == "none"
    assert break_it_body.locate("x = 1\n", "a.py", [("b.go", "x = 1\n")])["status"] == "none"


def test_core_lists_only_the_titles_that_differ():
    content = "def test_a(): assert 1\n\ndef test_b(): assert 2\n"
    host = "def test_a(): assert 1\n\ndef test_c(): assert 2\n"
    got = break_it_body.locate(content, "a.py", [("b.py", host)])
    assert got["status"] == "found" and got["titles"] == [("test_b", "test_c")]


def test_core_a_window_is_consecutive_statements():
    content = "x = 1\ny = 2\n"
    assert break_it_body.locate(content, "a.py", [("b.py", "x = 1\nz = 0\ny = 2\n")])["status"] == "none"
    assert break_it_body.locate(content, "a.py", [("b.py", "z = 0\nx = 1\ny = 2\n")])["status"] == "found"


_PRIVATE = ("class TestExample:\n    def test_a(self):\n        try:\n            value = __value\n"
            "        except NameError:\n            value = 0\n        assert value == 1\n")


def test_core_a_host_binding_the_runtime_name_of_a_private_class_read_is_a_binding_conflict():
    got = break_it_body.locate(_PRIVATE, "a.py", [("b.py", "_TestExample__value = 1\n\n" + _PRIVATE)])
    assert got["status"] == "unresolved" and got["reason"] == "binding-conflict"


def test_core_an_unchanged_moved_class_with_a_private_attribute_is_found():
    got = break_it_body.locate(_PRIVATE, "a.py", [("b.py", "import os\n\n" + _PRIVATE)])
    assert got["status"] == "found"


_RELATIVE = "from . import helpers\n\n\ndef test_x():\n    assert helpers.ok()\n"


def test_core_a_relative_import_moved_to_another_directory_is_a_binding_conflict():
    got = break_it_body.locate(_RELATIVE, "pkg/a.py", [("other/b.py", _RELATIVE)])
    assert (got["status"], got["reason"]) == ("unresolved", "binding-conflict")


def test_core_a_relative_import_in_the_same_directory_is_found():
    got = break_it_body.locate(_RELATIVE, "pkg/a.py", [("pkg/b.py", _RELATIVE)])
    assert (got["status"], got["path"]) == ("found", "pkg/b.py")


def test_core_a_comment_only_runtime_spelling_does_not_fail_the_prefilter():
    content = "class TestR:\n    # note: _TestR__v\n    x = __v\n\n    def test_x(self):\n        assert self.x\n"
    assert "__v" in front.parse(content)[0]["uses"]
    candidate = content.replace("    # note: _TestR__v\n", "")
    got = break_it_body.locate(content, "a.py", [("b.py", "import os\n\n" + candidate)])
    assert (got["status"], got["path"]) == ("found", "b.py")


def test_core_a_host_statement_that_references_the_moved_test_is_host_setup():
    content = "class TestR:\n    def test_x(self):\n        assert True\n"
    host = "import os\n\n" + content + "\nTestR.__unittest_skip__ = True\n"
    got = break_it_body.locate(content, "a.py", [("b.py", host)])
    assert (got["status"], got["reason"]) == ("unresolved", "host-setup")


def test_core_a_host_that_never_mentions_the_moved_tests_names_is_found():
    content = "class TestR:\n    def test_x(self):\n        assert True\n"
    host = "import os\n\n" + content + "\n\ndef helper():\n    return os.name\n"
    got = break_it_body.locate(content, "a.py", [("b.py", host)])
    assert (got["status"], got["path"]) == ("found", "b.py")


_NESTED = "def test_x():\n    from .impl import value\n    assert value\n"


def test_core_a_nested_relative_import_moved_to_another_directory_is_a_binding_conflict():
    got = break_it_body.locate(_NESTED, "pkg_a/test_old.py", [("pkg_b/test_host.py", _NESTED)])
    assert (got["status"], got["reason"]) == ("unresolved", "binding-conflict")


def test_core_a_nested_relative_import_in_the_same_directory_is_found():
    got = break_it_body.locate(_NESTED, "pkg_a/test_old.py", [("pkg_a/test_host.py", _NESTED)])
    assert (got["status"], got["path"]) == ("found", "pkg_a/test_host.py")


_V = "def test_x(value):\n    assert value == 1\n"


def test_core_a_host_pytest_generate_tests_hook_is_host_setup():
    host = _V + "\n\ndef pytest_generate_tests(metafunc):\n    metafunc.parametrize('value', [])\n"
    got = break_it_body.locate(_V, "a.py", [("b.py", host)])
    assert (got["status"], got["reason"]) == ("unresolved", "host-setup")


def test_core_a_host_fixture_under_an_aliased_fixture_import_with_the_same_name_is_host_setup():
    orig = "from pytest import fixture as fx\n\n\n@fx(name='value')\ndef base_value():\n    return 0\n\n\n" + _V
    host = orig + "\n\n@fx(name='value')\ndef z_host_value():\n    return 1\n"
    got = break_it_body.locate(orig, "a.py", [("b.py", host)])
    assert (got["status"], got["reason"]) == ("unresolved", "host-setup")


def test_core_a_global_assignment_inside_a_host_class_body_is_host_setup():
    orig = "from math import sqrt\n\n\ndef test_x():\n    assert sqrt(4) == 3\n"
    host = orig + "\n\nclass Host:\n    global sqrt\n    sqrt = lambda n: 3\n"
    got = break_it_body.locate(orig, "a.py", [("b.py", host)])
    assert (got["status"], got["reason"]) == ("unresolved", "host-setup")


@pytest.mark.parametrize("extra", [
    "import sqrt_helpers as value\n",
    "def value():\n    return 2\n",
    "value = 2\n",
], ids=["import", "undecorated-def", "constant"])
def test_core_an_allowed_host_shape_that_rebinds_a_used_name_is_a_binding_conflict(extra):
    got = break_it_body.locate(_V, "a.py", [("b.py", extra + "\n\n" + _V)])
    assert (got["status"], got["reason"]) == ("unresolved", "binding-conflict")


def test_core_an_autouse_fixture_inside_module_level_control_flow_is_host_setup():
    host = _V + "\n\nif True:\n    @pytest.fixture(autouse=True)\n    def _env():\n        pass\n"
    got = break_it_body.locate(_V, "a.py", [("b.py", host)])
    assert (got["status"], got["reason"]) == ("unresolved", "host-setup")


# ---- the closed-world host check (#2060) -----------------------------------------------------------

@pytest.mark.parametrize("extra", [
    "if True:\n    def helper():\n        return 1\n",
    "setup_things()\n",
    "@functools.lru_cache\ndef helper():\n    return 1\n",
    "COUNT += 1\n",
    "CONFIG = load()\n",
], ids=["if-holding-a-def", "call-statement", "decorated-helper", "augassign", "call-in-assignment"])
def test_core_a_host_that_adds_anything_but_plain_code_is_host_setup(extra):
    got = break_it_body.locate(_V, "a.py", [("b.py", _V + "\n\n" + extra)])
    assert (got["status"], got["reason"]) == ("unresolved", "host-setup")


@pytest.mark.parametrize("extra", [
    "def helper():\n    return 1\n",
    "class Helper:\n    size = 2\n\n    def grow(self):\n        return self.size + 1\n",
    "LIMIT = 3\n",
    '"""Notes on this module."""\n',
], ids=["helper-def", "helper-class", "constant", "docstring"])
def test_core_a_host_that_adds_plain_code_is_found(extra):
    got = break_it_body.locate(_V, "a.py", [("b.py", extra + "\n\n" + _V)])
    assert (got["status"], got["path"]) == ("found", "b.py")


@pytest.mark.parametrize("text", [
    "import os\n",
    "from os import path as p\n",
    "def helper():\n    return 1\n",
    "async def helper():\n    return 1\n",
    "def check_setup():\n    return 1\n",
    "class Helper:\n    size = 2\n\n    def grow(self):\n        return self.size\n",
    "class Helper(Base, metaclass=Meta):\n    '''Doc.'''\n    size: int = 2\n\n    async def grow(self):\n        return self.size\n",
    "LIMIT = 3\n",
    "A = B = (1, 'x', [2])\n",
    "LIMIT: int = 3\n",
    "LIMIT: int\n",
    '"""A docstring."""\n',
], ids=["import", "import-from", "def", "async-def", "def-with-setup-inside", "class", "class-with-bases-and-doc", "assign", "chained-assign",
        "annotated-assign", "bare-annotation", "docstring"])
def test_allowed_host_accepts_each_allowed_shape(text):
    assert front._allowed_host(ast.parse(text).body[0])


@pytest.mark.parametrize("text", [
    "@pytest.fixture\ndef f():\n    pass\n",
    "@fx(autouse=True)\nasync def f():\n    pass\n",
    "def pytest_generate_tests(metafunc):\n    pass\n",
    "def pytestmark():\n    pass\n",
    "def setup_module():\n    pass\n",
    "def setUpModule():\n    pass\n",
    "def tearDownModule():\n    pass\n",
    "def load_tests(loader, tests, pattern):\n    pass\n",
    "@register\nclass K:\n    pass\n",
    "class K:\n    global g\n    g = 1\n",
    "class K:\n    def f(self):\n        nonlocal_ = 1\n\n    class Inner:\n        @property\n        def p(self):\n            return 1\n",
    "class K(make()):\n    pass\n",
    "class K(metaclass=make()):\n    pass\n",
    "class K:\n    register()\n",
    "class K:\n    if c:\n        x = 1\n",
    "class K:\n    x = f()\n",
    "class K:\n    pytestmark = 1\n",
    "class K:\n    x += 1\n",
    "PYTESTMARK = 1\n",
    "pytestmark = 1\n",
    "pytest_plugins = ['x']\n",
    "setup_module = other\n",
    "__unittest_skip__ = True\n",
    "A.b = 1\n",
    "x, y = 1, 2\n",
    "x = f()\n",
    "x = lambda: 1\n",
    "x = (y := 1)\n",
    "x = [i for i in range(3)]\n",
    "x = {i for i in ()}\n",
    "x = (i for i in ())\n",
    "x: int = f()\n",
    "if c:\n    x = 1\n",
    "try:\n    x = 1\nexcept E:\n    pass\n",
    "for i in v:\n    pass\n",
    "while c:\n    pass\n",
    "with c:\n    pass\n",
    "match c:\n    case 1:\n        pass\n",
    "f()\n",
    "'a' + 'b'\n",
    "x += 1\n",
    "global g\n",
    "del x\n",
    "assert x\n",
    "raise E\n",
], ids=["decorated-def", "decorated-async-def", "pytest-hook-def", "pytestmark-def", "setup-def", "setUpModule-def", "tearDownModule-def",
        "load_tests-def", "decorated-class", "class-global", "class-nested-decorator", "class-call-base",
        "class-call-keyword", "class-call-statement", "class-if-body", "class-call-assignment",
        "class-pytest-assign", "class-augassign", "pytestmark-upper", "pytestmark", "pytest_plugins",
        "setup-assign", "dunder-assign", "attribute-target", "tuple-target", "call-value", "lambda-value",
        "walrus-value", "listcomp-value", "setcomp-value", "generator-value", "annotated-call", "if", "try", "for",
        "while", "with", "match", "call-statement", "non-docstring-expr", "augassign", "global", "del", "assert",
        "raise"])
def test_allowed_host_refuses_each_forbidden_shape(text):
    assert not front._allowed_host(ast.parse(text).body[0])


def test_front_records_hook_is_the_negation_of_allowed_host():
    for text in ("import os\n", "x = 1\n", "x = f()\n", "@d\ndef f(): pass\n", "if c:\n    pass\n"):
        node = ast.parse(text).body[0]
        assert front.parse(text)[0]["hook"] is (not front._allowed_host(node))


@pytest.mark.parametrize("flag", ["--test-name-pattern=regression", "--test-skip-pattern=smoke"])
def test_node_name_filters_refuse_a_renamed_test_command(flag):
    import break_it
    command, reason = break_it._rewrite_command(
        "node --test %s web/a.test.mjs" % flag, "web/a.test.mjs", "web/b.test.mjs", [("regression case", "renamed case")])
    assert (command, reason) == (None, "command-selects-tests")
    command, reason = break_it._rewrite_command(
        "node --test %s web/a.test.mjs" % flag, "web/a.test.mjs", "web/b.test.mjs", [])
    assert reason is None
