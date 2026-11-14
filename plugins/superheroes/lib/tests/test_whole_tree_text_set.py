"""The census of the whole-tree text tests (#2462).

A build's own checks run the tests its orders name and the tests that touch the files it edited. A test
that reads a whole tree of plugin Markdown by pattern names no file, so it never runs before the push.
Those tests have one home, the pytest argument file `whole-tree-text-tests.txt` beside this file. This
module is the census that keeps that home complete: it scans every `*.py` file under the two test trees
(`lib/tests` and `eval/tests`), finds each test file that looks like it reads plugin Markdown by pattern
(a candidate), and fails unless the candidate is listed in the argument file or sits in `EXEMPT` with a
reason, pinned to the enumeration lines it was reviewed against.

The census functions take the plugin root, the test trees and the argument-file path as parameters, so
the fixture tests at the foot drive them against synthetic trees under `tmp_path` and never touch the
real tree. No subprocess runs here and no scanned module is imported: files are read and parsed.
"""
import ast
import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(os.path.dirname(_HERE))
REPO_ROOT = os.path.dirname(os.path.dirname(PLUGIN_ROOT))
TEST_TREES = (os.path.join(PLUGIN_ROOT, "lib", "tests"), os.path.join(PLUGIN_ROOT, "eval", "tests"))
ARG_FILE = os.path.join(_HERE, "whole-tree-text-tests.txt")
ARG_FILE_REL = "plugins/superheroes/lib/tests/whole-tree-text-tests.txt"

# Top-level plugin directories that are never Markdown roots: the code and its tests.
_NOT_ROOTS = ("lib", "eval")

# A source line is an enumeration line when it matches one of these calls. The bare `glob(` / `iglob(`
# forms must not follow a word character, so a name like `test_x_grep_glob():` does not match.
_ENUMERATION = re.compile(
    r"os\.walk\(|os\.listdir\(|os\.scandir\(|glob\.glob\(|glob\.iglob\("
    r"|(?<!\w)i?glob\("
    r"|\.(?:glob|rglob|iterdir)\(")

# Repo-relative path -> (reason, (normalised enumeration line, ...)). Every test file the scan flags as
# a candidate that is not in the argument file is reviewed here, with the enumeration lines it was
# reviewed against. A changed enumeration line fails the pin until the entry is re-reviewed.
_NO_MARKDOWN_DIR = "enumerates no plugin Markdown directory when run (measured): "
_P = "plugins/superheroes/lib/tests/"

EXEMPT = {
    _P + "test_adopt_version.py": (
        _NO_MARKDOWN_DIR + "snapshots a temp plugin-cache tree built under tmp_path",
        ('for dp, _, fns in os.walk(root):',)),
    _P + "test_adopt_version_cloud_start.py": (
        _NO_MARKDOWN_DIR + "snapshots a temp project directory under tmp_path",
        ('for dp, _, fns in os.walk(directory):',)),
    _P + "test_break_it_transit_redacted_2284.py": (
        _NO_MARKDOWN_DIR + "globs the plugin lib/*.py sources, no Markdown",
        ('sources = {os.path.basename(p): open(p, encoding="utf-8").read() for p in '
         'glob.glob(os.path.join(_LIB, "*.py"))}',)),
    _P + "test_c1l10_later_rounds.py": (
        _NO_MARKDOWN_DIR + "lists a review round's orders directory and walks a round run directory "
        "under a temp session",
        ('[name] = [f for f in os.listdir(orders) if f.endswith(".md")]',
         'for root, _dirs, names in os.walk(d):')),
    _P + "test_c1l10b_test_restore.py": (
        _NO_MARKDOWN_DIR + "walks a saved session run directory under tmp_path",
        ('(order,) = [os.path.join(d, f) for d, _dirs, files in os.walk(str(session)) for f in files',)),
    _P + "test_c1l11b_returning_session.py": (
        _NO_MARKDOWN_DIR + "walks the round-1 run directory of a temp session",
        ('for root, _dirs, names in os.walk(top):',)),
    _P + "test_cloud_relay.py": (
        _NO_MARKDOWN_DIR + "lists the relay state directory of a temp world",
        ('assert [n for n in os.listdir(os.path.dirname(_state_file(world))) '
         'if n.startswith("relay-")] == []',)),
    _P + "test_conformance_probe.py": (
        _NO_MARKDOWN_DIR + "lists temp repository copies and the ledger and projects directories "
        "under tmp_path",
        ('for name in os.listdir(repo):',
         'assert list(projects_dir.iterdir()) == []',
         'n for n in os.listdir(ledger_dir)',
         'legacy_names = [n for n in os.listdir(ledger_dir) if n.startswith("astra-probe-")]')),
    _P + "test_dispatch_outcome_census.py": (
        _NO_MARKDOWN_DIR + "walks the plugin lib/ directory for Python sources",
        ('for root, dirs, files in os.walk(_LIB):',)),
    _P + "test_engine_dispatch_write.py": (
        _NO_MARKDOWN_DIR + "lists temp handoff directories under tmp_path",
        ('assert list(os.listdir(handoff_base)) == []',
         'assert list(os.listdir(handoff_base)) == []',
         'assert list(os.listdir(bad_base)) == []',
         'assert list(os.listdir(handoff_base)) == []',
         'assert list(os.listdir(handoff_base)) == []')),
    _P + "test_gh_pages.py": (
        _NO_MARKDOWN_DIR + "walks the plugin lib/ directory for Python sources",
        ('for root, dirs, files in os.walk(_LIB):',)),
    _P + "test_guardian_lens_duplication.py": (
        _NO_MARKDOWN_DIR + "walks temp working directories and tmp_path",
        ('for root, dirs, files in os.walk(cwd):',
         'for root, dirs, files in os.walk(tmp_path):',
         'for root, dirs, files in os.walk(tmp_path):',
         'for root, dirs, files in os.walk(tmp_path):')),
    _P + "test_manifest_skill_wiring.py": (
        "lists skill directories and opens only plugin.json (measured: no Markdown opened)",
        ('d for d in os.listdir(_SKILLS_DIR)',)),
    _P + "test_pilot_auth_census.py": (
        _NO_MARKDOWN_DIR + "globs the plugin lib/ directory for Python sources",
        ('for py_path in sorted(lib_root.rglob("*.py")):',)),
    _P + "test_pilot_c10_census.py": (
        _NO_MARKDOWN_DIR + "globs lib/pilot_conformance*.py",
        ('paths = sorted(glob.glob(os.path.join(_LIB, "pilot_conformance*.py")))',)),
    _P + "test_pilot_probe_census.py": (
        _NO_MARKDOWN_DIR + "walks the plugin lib/ directory for Python sources",
        ('for root, dirs, files in os.walk(_LIB):',)),
    _P + "test_pr_sheet.py": (
        "globs theme/ sample JSON and its own fixtures under lib/tests, not plugin Markdown (measured)",
        ('assert list(tmp_path.glob("*.tmp")) == []',
         'return sorted(p.name for p in (folder / "pictures").iterdir()) '
         'if (folder / "pictures").is_dir() else []',
         'assert list((tmp_path / "out").iterdir()) == []',
         'assert list(out.parent.iterdir()) == []',
         'assert list(out.parent.iterdir()) == []',
         'for source in LIB.glob("*.py"):',
         'assert list(out.parent.iterdir()) == []',
         'assert not out.exists() and list(tmp_path.glob("**/*.tmp")) == []',
         'assert list(out.iterdir()) == []',
         'assert list(out.iterdir()) == []',
         'assert done.returncode == 2 and "--record is only for build" in done.stderr '
         'and list(out.iterdir()) == []',
         'assert done.returncode == 2 and "--record" in done.stderr and list(out.iterdir()) == []')),
    _P + "test_review_findings_schema.py": (
        _NO_MARKDOWN_DIR + "walks the plugin lib/ directory for Python sources",
        ('for root, dirs, files in os.walk(_LIB):',)),
    _P + "test_review_record_awaits_owner_2136.py": (
        _NO_MARKDOWN_DIR + "globs the plugin lib/ directory for Python sources",
        ('for path in sorted(LIB.rglob("*.py")):',)),
    _P + "test_review_record_carried_recheck.py": (
        _NO_MARKDOWN_DIR + "lists the git refs of a temp sentinel repository under tmp_path",
        ('assert not list((sentinel / ".git" / "refs" / "heads").iterdir())',)),
    _P + "test_round_driver_order_channel.py": (
        _NO_MARKDOWN_DIR + "walks a round run directory under a temp session",
        ('for root, _dirs, files in os.walk(rdir):',)),
    _P + "test_second_test_c1l7.py": (
        _NO_MARKDOWN_DIR + "globs the order and sidecar files of a temp run directory",
        ('(order,) = glob.glob(os.path.join(r.dir, "round-1", "orders", RD.P_SECOND_TEST, "*.md"))',
         '(sidecar,) = glob.glob(os.path.join(r.dir, "round-1", "**", RD.ORDER_SIDECAR_HELD_FILE), '
         'recursive=True)',
         'assert not glob.glob(os.path.join(r.dir, "round-1", "orders", RD.P_SECOND_TEST, "*"))')),
    _P + "test_session_context.py": (
        _NO_MARKDOWN_DIR + "snapshots a temp main repository directory under tmp_path",
        ('for dp, _, fs in os.walk(root):',)),
    _P + "test_session_pickup_and_upgrade_1721.py": (
        _NO_MARKDOWN_DIR + "walks and lists temp session folders under tmp_path",
        ('for root, dirs, files in os.walk(session_dir):',
         'assert os.path.isdir(staged) and os.listdir(staged), "no half-done commit was left"',
         'assert [n for n in os.listdir(session_dir) if "restarted" in n] == [MARKER]',
         'assert os.listdir(os.path.join(session_dir, "commits"))',
         'assert not os.listdir(os.path.join(session_dir, "commits"))',
         'assert os.listdir(os.path.join(session_dir, "commits"))')),
    _P + "test_sheet_schema.py": (
        "globs theme/ sample-*.json only and opens no Markdown by pattern (read from the file, "
        "not measured)",
        ('@pytest.mark.parametrize("sample", sorted(p.name for p in THEME.glob("sample-*.json")))',)),
    _P + "test_spec_lifecycle.py": (
        "globs the repository's docs/superheroes/*/spec.md, outside the plugin (read from the file, "
        "not measured)",
        ('paths = sorted(glob.glob(os.path.join(_REPO_ROOT, "docs/superheroes/*/spec.md")))',)),
}


# --------------------------------------------------------------------------- the census

def normalise(line):
    """Strip a source line and collapse runs of whitespace to one space."""
    return " ".join(line.split())


def _holds_markdown(directory):
    for _dirpath, _dirnames, filenames in os.walk(directory):
        if any(name.endswith(".md") for name in filenames):
            return True
    return False


def markdown_roots(plugin_root):
    """Names of the plugin root's top-level directories that hold a `.md` file anywhere beneath them,
    excluding `lib`, `eval` and any name starting with `.`. Derived from the tree, never listed."""
    roots = []
    for name in sorted(os.listdir(plugin_root)):
        if name in _NOT_ROOTS or name.startswith("."):
            continue
        top = os.path.join(plugin_root, name)
        if os.path.isdir(top) and _holds_markdown(top):
            roots.append(name)
    return roots


def enumeration_lines(source):
    """The normalised enumeration lines of a source text, in file order."""
    return tuple(normalise(line) for line in source.split("\n") if _ENUMERATION.search(line))


def _string_literals(tree):
    return [node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)]


def _is_md(node):
    return isinstance(node, ast.Constant) and node.value == ".md"


def _is_suffix(node):
    return (isinstance(node, ast.Attribute) and node.attr == "suffix") or (
        isinstance(node, ast.Name) and node.id == "suffix")


def _has_markdown_filter(tree, literals):
    """(a) a Markdown-suffix filter: `.endswith(".md")` or a tuple starting with ".md", a string literal
    containing `*.md`, or `suffix == ".md"`."""
    if any("*.md" in text for text in literals):
        return True
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "endswith" and node.args):
            first = node.args[0]
            if _is_md(first) or (isinstance(first, ast.Tuple) and first.elts and _is_md(first.elts[0])):
                return True
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq):
            sides = (node.left, node.comparators[0])
            if any(_is_md(side) for side in sides) and any(_is_suffix(side) for side in sides):
                return True
    return False


def _names_a_root_or_transition(literals, roots):
    """(b) a string literal that equals a Markdown root name or starts with `<root>/`, or (c) a string
    literal containing TRANSITION."""
    for text in literals:
        if text in roots or any(text.startswith(root + "/") for root in roots):
            return True
        if "TRANSITION" in text:
            return True
    return False


def _imported_modules(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def _repo_root(plugin_root):
    return os.path.dirname(os.path.dirname(os.path.abspath(plugin_root)))


def _rel(path, repo_root):
    return os.path.relpath(os.path.abspath(path), repo_root).replace(os.sep, "/")


def scan(plugin_root, test_trees):
    """Scan every `*.py` file under the test trees. Returns `(test_files, candidates)`: the sorted
    repo-relative paths of every `test_*.py` file, and a dict of repo-relative path -> the file's own
    normalised enumeration lines (in file order) for every candidate.

    A test file is a candidate when it has an enumeration line and a Markdown-suffix filter, a literal
    naming a Markdown root, or a literal containing TRANSITION; or when it imports a local helper (a
    non-test module directly in a test tree) that is itself a candidate by that rule."""
    roots = markdown_roots(plugin_root)
    if not roots:
        raise AssertionError("no Markdown roots found under %s" % plugin_root)
    repo_root = _repo_root(plugin_root)
    tests, helpers = {}, {}
    for tree in test_trees:
        if not os.path.isdir(tree):
            raise AssertionError("test tree missing: %s" % tree)
        for dirpath, dirnames, filenames in os.walk(tree):
            dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
            for name in sorted(filenames):
                if not name.endswith(".py"):
                    continue
                path = os.path.join(dirpath, name)
                with open(path, encoding="utf-8") as handle:
                    source = handle.read()
                tree_ast = ast.parse(source, filename=path)
                literals = _string_literals(tree_ast)
                lines = enumeration_lines(source)
                direct = bool(lines) and (_has_markdown_filter(tree_ast, literals)
                                          or _names_a_root_or_transition(literals, roots))
                record = {"lines": lines, "direct": direct, "imports": _imported_modules(tree_ast)}
                if name.startswith("test_"):
                    tests[_rel(path, repo_root)] = record
                elif dirpath == tree:
                    helpers[name[:-3]] = record
    helper_candidates = {name for name, record in helpers.items() if record["direct"]}
    candidates = {}
    for path, record in tests.items():
        if record["direct"] or record["imports"] & helper_candidates:
            candidates[path] = record["lines"]
    return sorted(tests), candidates


def empty_walk_errors(test_files, candidates):
    """The scan must find at least one test file and at least one candidate; zero is a failure."""
    errors = []
    if not test_files:
        errors.append("the scan found no test file under the two test trees")
    if not candidates:
        errors.append("the scan found no candidate: a whole-tree scan that finds nothing is a broken "
                      "scan, not a pass")
    return errors


def parse_argument_file(arg_file, plugin_root, test_trees):
    """Read the members from the argument file only. Returns `(members, errors)`; every error names
    its line."""
    repo_root = _repo_root(plugin_root)
    if not os.path.isfile(arg_file):
        return [], ["the argument file does not exist: %s" % arg_file]
    with open(arg_file, encoding="utf-8", newline="") as handle:
        text = handle.read()
    if text == "":
        return [], ["the argument file is empty"]
    lines = text.split("\n")
    errors = []
    if lines[-1] == "":
        lines.pop()
    else:
        errors.append("the argument file does not end with a newline")
    trees = [os.path.abspath(tree) for tree in test_trees]
    members, seen = [], {}
    previous = None
    for number, line in enumerate(lines, 1):
        if line.strip() == "":
            errors.append("line %d: blank line" % number)
            continue
        if line != line.strip():
            errors.append("line %d: leading or trailing whitespace: %r" % (number, line))
            continue
        if line.startswith("#"):
            errors.append("line %d: comment line (an argument file holds arguments only): %s"
                          % (number, line))
            continue
        if line in seen:
            errors.append("line %d: duplicate of line %d: %s" % (number, seen[line], line))
            continue
        seen[line] = number
        if previous is not None and line < previous[1]:
            errors.append("line %d: out of sorted order (it sorts before line %d): %s"
                          % (number, previous[0], line))
        previous = (number, line)
        full = os.path.abspath(os.path.join(repo_root, line))
        if not os.path.isfile(full):
            errors.append("line %d: path does not exist: %s" % (number, line))
            continue
        base = os.path.basename(full)
        if not (base.startswith("test_") and base.endswith(".py")
                and any(full.startswith(tree + os.sep) for tree in trees)):
            errors.append("line %d: not a test_*.py file under one of the two test trees: %s"
                          % (number, line))
            continue
        members.append(line)
    return members, errors


def uncovered_errors(candidates, members, exempt):
    """Every candidate is a member or exempt; one error naming each file that is neither."""
    errors = []
    for path in sorted(candidates):
        if path in members or path in exempt:
            continue
        errors.append(
            "%s reads plugin Markdown by pattern (enumeration lines: %s) and is in neither the set nor "
            "EXEMPT: add it to %s, or, if it does not read plugin Markdown by pattern, add it to EXEMPT "
            "with a reason and its enumeration lines." % (path, list(candidates[path]), ARG_FILE_REL))
    return errors


def exempt_shape_errors(exempt):
    """Each EXEMPT entry is `(reason, (line, ...))` with a non-empty reason."""
    errors = []
    for path in sorted(exempt):
        entry = exempt[path]
        if not (isinstance(entry, tuple) and len(entry) == 2 and isinstance(entry[0], str)
                and isinstance(entry[1], tuple) and all(isinstance(line, str) for line in entry[1])):
            errors.append("%s: the EXEMPT entry must be (reason, (enumeration line, ...))" % path)
        elif not entry[0].strip():
            errors.append("%s: the EXEMPT entry has an empty reason" % path)
    return errors


def exempt_stale_errors(exempt, candidates):
    return ["%s: stale EXEMPT entry, the scan no longer flags this file as a candidate: remove the entry"
            % path for path in sorted(exempt) if path not in candidates]


def exempt_member_errors(exempt, members):
    return ["%s: the file is both a member of the set and in EXEMPT: keep it in one place" % path
            for path in sorted(exempt) if path in members]


def exempt_pin_errors(exempt, candidates):
    """An exempt file whose current enumeration lines differ from the recorded tuple."""
    errors = []
    for path in sorted(exempt):
        if path not in candidates:
            continue
        current = tuple(candidates[path])
        recorded = tuple(exempt[path][1])
        if current != recorded:
            errors.append(
                "%s: the exempt file's enumeration changed; re-review whether it now reads plugin "
                "Markdown by pattern, then update its entry or move it to the set. recorded: %s; "
                "current: %s" % (path, list(recorded), list(current)))
    return errors


def _fail_on(errors):
    if errors:
        pytest.fail("\n".join(errors), pytrace=False)


# --------------------------------------------------------------------------- the real tree

@pytest.fixture(scope="module")
def real_scan():
    test_files, candidates = scan(PLUGIN_ROOT, TEST_TREES)
    members, arg_errors = parse_argument_file(ARG_FILE, PLUGIN_ROOT, TEST_TREES)
    return test_files, candidates, members, arg_errors


def test_markdown_roots_are_derived_from_the_real_tree():
    roots = markdown_roots(PLUGIN_ROOT)
    assert roots, "no Markdown roots found under the plugin root"
    assert "skills" in roots and "templates" in roots, roots
    assert "lib" not in roots and "eval" not in roots, roots
    assert not any(name.startswith(".") for name in roots), roots


def test_the_real_scan_is_not_empty(real_scan):
    test_files, candidates, _members, _arg_errors = real_scan
    _fail_on(empty_walk_errors(test_files, candidates))


def test_the_argument_file_is_well_formed(real_scan):
    _test_files, _candidates, members, arg_errors = real_scan
    assert _rel(ARG_FILE, REPO_ROOT) == ARG_FILE_REL
    _fail_on(arg_errors)
    assert members, "the argument file lists no member"
    assert _rel(__file__, REPO_ROOT) in members, "the census is a member of its own set"


def test_every_candidate_is_a_member_or_exempt(real_scan):
    """Axis: a test file that reads plugin Markdown by pattern and is in neither the argument file nor
    EXEMPT fails here, naming the file (#2462, G1)."""
    _test_files, candidates, members, arg_errors = real_scan
    _fail_on(arg_errors)
    _fail_on(uncovered_errors(candidates, members, EXEMPT))


def test_every_exempt_entry_is_well_formed():
    _fail_on(exempt_shape_errors(EXEMPT))


def test_no_exempt_entry_is_stale(real_scan):
    _test_files, candidates, _members, _arg_errors = real_scan
    _fail_on(exempt_stale_errors(EXEMPT, candidates))


def test_no_exempt_file_is_also_a_member(real_scan):
    _test_files, _candidates, members, _arg_errors = real_scan
    _fail_on(exempt_member_errors(EXEMPT, members))


def test_exempt_enumeration_lines_are_pinned(real_scan):
    """Axis: an exempt file's current normalised enumeration lines equal the tuple it was reviewed
    against; a new or changed enumeration line fails here, naming the file (#2462, G2)."""
    _test_files, candidates, _members, _arg_errors = real_scan
    _fail_on(exempt_pin_errors(EXEMPT, candidates))


# --------------------------------------------------------------------------- fixture trees

_PLUGIN_REL = "plugins/superheroes"


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def _synthetic(tmp_path):
    """A synthetic repository: plugin root with Markdown under skills and templates, and two empty test
    trees. Returns `(plugin_root, lib_tests, eval_tests, repo_root)`."""
    repo = str(tmp_path)
    plugin = os.path.join(repo, *_PLUGIN_REL.split("/"))
    _write(os.path.join(plugin, "skills", "alpha", "SKILL.md"), "# alpha\n")
    _write(os.path.join(plugin, "templates", "t.md"), "# t\n")
    lib_tests = os.path.join(plugin, "lib", "tests")
    eval_tests = os.path.join(plugin, "eval", "tests")
    os.makedirs(lib_tests)
    os.makedirs(eval_tests)
    return plugin, lib_tests, eval_tests, repo


def _scan_synthetic(tmp_path, files):
    plugin, lib_tests, eval_tests, repo = _synthetic(tmp_path)
    for relative, text in files.items():
        _write(os.path.join(lib_tests, relative), text)
    test_files, candidates = scan(plugin, (lib_tests, eval_tests))
    prefix = _PLUGIN_REL + "/lib/tests/"
    return [p[len(prefix):] for p in test_files], {p[len(prefix):]: v for p, v in candidates.items()}


def test_a_new_top_level_directory_holding_markdown_becomes_a_root(tmp_path):
    plugin, _lib, _eval, _repo = _synthetic(tmp_path)
    assert markdown_roots(plugin) == ["skills", "templates"]
    _write(os.path.join(plugin, "newroot", "deep", "er", "page.md"), "# page\n")
    assert markdown_roots(plugin) == ["newroot", "skills", "templates"]


def test_roots_exclude_lib_eval_dot_names_and_directories_without_markdown(tmp_path):
    plugin, _lib, _eval, _repo = _synthetic(tmp_path)
    _write(os.path.join(plugin, "lib", "notes.md"), "# lib\n")
    _write(os.path.join(plugin, "eval", "notes.md"), "# eval\n")
    _write(os.path.join(plugin, ".hidden", "notes.md"), "# hidden\n")
    _write(os.path.join(plugin, "data", "rows.json"), "{}\n")
    _write(os.path.join(plugin, "stray.md"), "# a file at the root is not a directory\n")
    assert markdown_roots(plugin) == ["skills", "templates"]


def test_a_plugin_tree_without_markdown_fails_the_scan(tmp_path):
    plugin = os.path.join(str(tmp_path), "plugins", "superheroes")
    lib_tests = os.path.join(plugin, "lib", "tests")
    os.makedirs(lib_tests)
    _write(os.path.join(lib_tests, "test_a.py"), "import os\nos.listdir('.')\n")
    assert markdown_roots(plugin) == []
    with pytest.raises(AssertionError, match="no Markdown roots"):
        scan(plugin, (lib_tests,))


def test_a_missing_test_tree_fails_the_scan(tmp_path):
    plugin, lib_tests, _eval, _repo = _synthetic(tmp_path)
    with pytest.raises(AssertionError, match="test tree missing"):
        scan(plugin, (lib_tests, os.path.join(plugin, "no", "such", "tree")))


@pytest.mark.parametrize("line", [
    "for root, dirs, files in os.walk(PLUGIN):",
    "names = os.listdir(d)",
    "with os.scandir(d) as it:",
    "hits = glob.glob(os.path.join(d, '*'))",
    "hits = glob.iglob(pattern)",
    "hits = glob(pattern)",
    "hits = iglob(pattern)",
    "hits = (glob(pattern))",
    "hits = sorted(PLUGIN.glob('*'))",
    "hits = PLUGIN.rglob('*')",
    "kids = list(PLUGIN.iterdir())",
    "    for p in (PLUGIN / 'templates').iterdir():",
])
def test_enumeration_pattern_matches_the_calls(line):
    assert enumeration_lines(line) == (normalise(line),)


@pytest.mark.parametrize("line", [
    "def test_x_grep_glob():",
    "def test_read_grep_glob():",
    "x = my_iglob(pattern)",
    "x = xglob(pattern)",
    "x = os.path.join(a, b)",
    "x = os.walker(a)",
    "glob.escape(name)",
    "glob = 1",
])
def test_enumeration_pattern_does_not_match(line):
    assert enumeration_lines(line) == ()


def test_enumeration_lines_are_normalised_in_file_order():
    source = "a = 1\n    names  =   os.listdir(d)   \nb = 2\n\tfor p in  PLUGIN.rglob('*'):\n"
    assert enumeration_lines(source) == ("names = os.listdir(d)", "for p in PLUGIN.rglob('*'):")


def test_a_templates_iterdir_with_no_suffix_filter_is_a_candidate(tmp_path):
    files = {"test_templates.py": (
        "import pathlib\n"
        "PLUGIN = pathlib.Path(__file__).parents[2]\n"
        "\n"
        "def test_templates():\n"
        "    names = [p.name for p in (PLUGIN / \"templates\").iterdir()]\n"
        "    assert names\n")}
    test_files, candidates = _scan_synthetic(tmp_path, files)
    assert test_files == ["test_templates.py"]
    assert candidates == {"test_templates.py": ("names = [p.name for p in (PLUGIN / \"templates\").iterdir()]",)}


def test_the_same_file_is_not_a_candidate_when_templates_holds_no_markdown(tmp_path):
    plugin, lib_tests, eval_tests, _repo = _synthetic(tmp_path)
    os.remove(os.path.join(plugin, "templates", "t.md"))
    _write(os.path.join(plugin, "templates", "t.json"), "{}\n")
    _write(os.path.join(lib_tests, "test_templates.py"),
           "def test_templates(PLUGIN):\n    return list((PLUGIN / \"templates\").iterdir())\n")
    test_files, candidates = scan(plugin, (lib_tests, eval_tests))
    assert test_files == [_PLUGIN_REL + "/lib/tests/test_templates.py"]
    assert candidates == {}


@pytest.mark.parametrize("body", [
    "names = [n for n in os.listdir(d) if n.endswith(\".md\")]",
    "names = [n for n in os.listdir(d) if n.endswith((\".md\", \".txt\"))]",
    "names = glob.glob(os.path.join(d, \"*.md\"))",
    "names = [p for p in d.iterdir() if p.suffix == \".md\"]",
    "names = os.listdir(os.path.join(d, \"skills\", \"alpha\"))",
    "names = os.listdir(os.path.join(d, \"skills/alpha\"))",
    "names = os.listdir(d + \"/TRANSITION.md\")",
    "names = os.listdir(d + \"/docs/TRANSITION\")",
])
def test_each_candidate_rule_flags_a_file(tmp_path, body):
    test_files, candidates = _scan_synthetic(
        tmp_path, {"test_rule.py": "import os\nimport glob\n\ndef test_rule(d):\n    %s\n" % body})
    assert list(candidates) == ["test_rule.py"], body


@pytest.mark.parametrize("body", [
    "names = os.listdir(d)",
    "names = [n for n in os.listdir(d) if n.endswith(\".txt\")]",
    "names = os.listdir(os.path.join(d, \"fixtures\"))",
    "names = os.listdir(os.path.join(d, \"skillset\"))",
    "name = \"skills\"",
    "name = os.path.join(d, \"templates\")",
])
def test_a_file_without_both_halves_is_not_a_candidate(tmp_path, body):
    """The first four have an enumeration line and no Markdown half; the last two name a root and have
    no enumeration line."""
    files = {"test_rule.py": "import os\n\ndef test_rule(d):\n    %s\n" % body,
             "test_control.py": "import os\n\ndef test_control(d):\n    os.listdir(\"skills\")\n"}
    _test_files, candidates = _scan_synthetic(tmp_path, files)
    assert list(candidates) == ["test_control.py"], body


def test_a_function_name_holding_glob_is_not_a_candidate(tmp_path):
    files = {
        "test_name_only.py": "def test_read_grep_glob():\n    assert \"skills\" in \"skills and agents\"\n",
        "test_control.py": "import glob\n\ndef test_control():\n    glob.glob(\"skills/*\")\n",
    }
    test_files, candidates = _scan_synthetic(tmp_path, files)
    assert test_files == ["test_control.py", "test_name_only.py"]
    assert list(candidates) == ["test_control.py"]


def test_a_comment_mentioning_a_root_does_not_make_a_file_a_candidate(tmp_path):
    files = {
        "test_comment_only.py": ("import os\n"
                                 "# the skills directory and the templates directory are not read here\n"
                                 "# names must not end with .md, and TRANSITION is not read either\n"
                                 "def test_a(d):\n    return os.listdir(d)\n"),
        "test_control.py": "import os\n\ndef test_control():\n    os.listdir(\"skills\")\n",
    }
    _test_files, candidates = _scan_synthetic(tmp_path, files)
    assert list(candidates) == ["test_control.py"]


def test_a_test_importing_a_local_helper_that_enumerates_skills_is_a_candidate(tmp_path):
    files = {
        "tree_helper.py": ("import os\n\ndef skill_names(plugin):\n"
                           "    return os.listdir(os.path.join(plugin, \"skills\"))\n"),
        "quiet_helper.py": "import os\n\ndef join(a, b):\n    return os.path.join(a, b)\n",
        "test_via_import.py": "import tree_helper\n\ndef test_a():\n    assert tree_helper.skill_names\n",
        "test_via_from.py": "from tree_helper import skill_names\n\ndef test_b():\n    assert skill_names\n",
        "test_via_quiet.py": "import quiet_helper\n\ndef test_c():\n    assert quiet_helper.join\n",
        "test_no_import.py": "def test_d():\n    assert True\n",
    }
    test_files, candidates = _scan_synthetic(tmp_path, files)
    assert sorted(candidates) == ["test_via_from.py", "test_via_import.py"]
    assert candidates["test_via_import.py"] == ()
    assert "tree_helper.py" not in test_files and "quiet_helper.py" not in test_files


def test_a_helper_below_the_tree_top_does_not_propagate(tmp_path):
    files = {
        "sub/tree_helper.py": ("import os\n\ndef skill_names(plugin):\n"
                               "    return os.listdir(os.path.join(plugin, \"skills\"))\n"),
        "test_via_import.py": "import tree_helper\n\ndef test_a():\n    assert tree_helper\n",
    }
    _test_files, candidates = _scan_synthetic(tmp_path, files)
    assert candidates == {}


def test_the_empty_walk_guard_fails_on_zero_test_files_and_on_zero_candidates(tmp_path):
    assert empty_walk_errors(["a/test_x.py"], {"a/test_x.py": ()}) == []
    assert any("no test file" in error for error in empty_walk_errors([], {}))
    assert any("no candidate" in error for error in empty_walk_errors(["a/test_x.py"], {}))
    plugin, lib_tests, eval_tests, _repo = _synthetic(tmp_path)
    test_files, candidates = scan(plugin, (lib_tests, eval_tests))
    assert test_files == [] and candidates == {}
    assert len(empty_walk_errors(test_files, candidates)) == 2


def _members_fixture(tmp_path, names=("test_a.py", "test_b.py")):
    plugin, lib_tests, eval_tests, repo = _synthetic(tmp_path)
    for name in names:
        _write(os.path.join(lib_tests, name), "def test_x():\n    pass\n")
    _write(os.path.join(lib_tests, "helper.py"), "X = 1\n")
    _write(os.path.join(plugin, "skills", "alpha", "test_in_skills.py"), "def test_x():\n    pass\n")
    arg_file = os.path.join(lib_tests, "set.txt")
    return plugin, (lib_tests, eval_tests), arg_file


_A = _PLUGIN_REL + "/lib/tests/test_a.py"
_B = _PLUGIN_REL + "/lib/tests/test_b.py"


def test_a_well_formed_argument_file_parses(tmp_path):
    plugin, trees, arg_file = _members_fixture(tmp_path)
    _write(arg_file, _A + "\n" + _B + "\n")
    assert parse_argument_file(arg_file, plugin, trees) == ([_A, _B], [])


@pytest.mark.parametrize("label, text, fragment", [
    ("empty file", "", "argument file is empty"),
    ("only a newline", "\n", "line 1: blank line"),
    ("blank line in the middle", _A + "\n\n" + _B + "\n", "line 2: blank line"),
    ("blank line at the end", _A + "\n" + _B + "\n\n", "line 3: blank line"),
    ("whitespace-only line", _A + "\n   \n" + _B + "\n", "line 2: blank line"),
    ("leading whitespace", " " + _A + "\n", "line 1: leading or trailing whitespace"),
    ("trailing whitespace", _A + " \n", "line 1: leading or trailing whitespace"),
    ("carriage return", _A + "\r\n", "line 1: leading or trailing whitespace"),
    ("comment line", "# the set\n" + _A + "\n", "line 1: comment line"),
    ("duplicate", _A + "\n" + _A + "\n", "line 2: duplicate of line 1"),
    ("out of order", _B + "\n" + _A + "\n", "line 2: out of sorted order"),
    ("missing path", _A + "\n" + _PLUGIN_REL + "/lib/tests/test_gone.py\n",
     "line 2: path does not exist"),
    ("not a test file", _PLUGIN_REL + "/lib/tests/helper.py\n", "line 1: not a test_*.py file"),
    ("a test file outside the trees", _PLUGIN_REL + "/skills/alpha/test_in_skills.py\n",
     "line 1: not a test_*.py file"),
    ("no trailing newline", _A + "\n" + _B, "does not end with a newline"),
])
def test_the_argument_file_edges_fail_naming_the_line(tmp_path, label, text, fragment):
    plugin, trees, arg_file = _members_fixture(tmp_path)
    _write(arg_file, text)
    _members, errors = parse_argument_file(arg_file, plugin, trees)
    assert any(fragment in error for error in errors), (label, errors)


def test_a_missing_argument_file_fails(tmp_path):
    plugin, trees, arg_file = _members_fixture(tmp_path)
    members, errors = parse_argument_file(arg_file, plugin, trees)
    assert members == [] and any("does not exist" in error for error in errors)


def test_a_candidate_in_neither_the_set_nor_exempt_fails_naming_the_file():
    candidates = {_A: ("names = os.listdir(d)",), _B: ()}
    errors = uncovered_errors(candidates, [_B], {})
    assert len(errors) == 1 and errors[0].startswith(_A + " ")
    assert "add it to " + ARG_FILE_REL + ", or, if it does not read plugin Markdown by pattern, add it " \
        "to EXEMPT with a reason and its enumeration lines" in errors[0]
    assert uncovered_errors(candidates, [_B], {_A: ("a reason", ("names = os.listdir(d)",))}) == []
    assert uncovered_errors(candidates, [_A, _B], {}) == []


def test_exempt_edges_fail_naming_the_file():
    candidates = {_A: ("x = os.listdir(d)",), _B: ("y = os.listdir(e)",)}
    good = {_A: ("a reason", ("x = os.listdir(d)",))}
    assert exempt_shape_errors(good) == [] and exempt_stale_errors(good, candidates) == []
    assert exempt_member_errors(good, [_B]) == [] and exempt_pin_errors(good, candidates) == []

    gone = _PLUGIN_REL + "/lib/tests/test_gone.py"
    stale = exempt_stale_errors({gone: ("a reason", ())}, candidates)
    assert len(stale) == 1 and stale[0].startswith(gone + ":") and "stale" in stale[0]

    both = exempt_member_errors(good, [_A, _B])
    assert len(both) == 1 and both[0].startswith(_A + ":") and "both a member" in both[0]

    for entry in (("", ("x = os.listdir(d)",)), ("   ", ()), "no tuple", ("reason",), ("reason", ["x"])):
        errors = exempt_shape_errors({_A: entry})
        assert len(errors) == 1 and errors[0].startswith(_A + ":"), entry
    assert "empty reason" in exempt_shape_errors({_A: ("", ())})[0]


def test_a_changed_enumeration_line_fails_the_pin(tmp_path):
    files = {"test_pinned.py": "import os\n\ndef test_a(d):\n    names = os.listdir(os.path.join(d, \"skills\"))\n"}
    _test_files, candidates = _scan_synthetic(tmp_path, files)
    recorded = ("names = os.listdir(os.path.join(d, \"skills\"))",)
    assert candidates == {"test_pinned.py": recorded}
    assert exempt_pin_errors({"test_pinned.py": ("reviewed", recorded)}, candidates) == []

    changed = {"test_pinned.py": files["test_pinned.py"].replace(
        "names = os.listdir(os.path.join(d, \"skills\"))",
        "names = sorted(os.listdir(os.path.join(d, \"skills\")))")}
    other = tmp_path / "other"
    other.mkdir()
    _test_files, candidates_after = _scan_synthetic(other, changed)
    errors = exempt_pin_errors({"test_pinned.py": ("reviewed", recorded)}, candidates_after)
    assert len(errors) == 1 and errors[0].startswith("test_pinned.py:")
    assert ("the exempt file's enumeration changed; re-review whether it now reads plugin Markdown by "
            "pattern, then update its entry or move it to the set") in errors[0]

    added = {"test_pinned.py": files["test_pinned.py"] + "    _unused = os.listdir(d)\n"}
    third = tmp_path / "third"
    third.mkdir()
    _test_files, candidates_added = _scan_synthetic(third, added)
    assert len(exempt_pin_errors({"test_pinned.py": ("reviewed", recorded)}, candidates_added)) == 1
