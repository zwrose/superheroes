"""AST census: no unsanctioned repo-root resolution outside store_core (issue #742 item 3).

Walks every production module under plugins/superheroes/lib/ (not tests/) and flags:
  1. git argv literals --show-toplevel, --git-common-dir, --absolute-git-dir
  2. manual .git ancestor walks (join + exists/isdir/isfile/lstat + dirname loop)

Allowlisted modules are disclosed live instances, not dismissals.
"""
import ast
import glob
import os
import sys
import textwrap

import pytest

_LIB = os.path.join(os.path.dirname(__file__), "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

_FLAGGED_GIT_ARGS = frozenset({
    "--show-toplevel",
    "--show-cdup",
    "--git-common-dir",
    "--git-dir",
    "--absolute-git-dir",
})

_EXISTS_ATTRS = frozenset({"exists", "isdir", "isfile", "lstat", "access"})

# module basename -> non-empty justification (disclosure, not dismissal)
ALLOWLIST = {
    "store_core.py": (
        "The chokepoint itself. This is the one sanctioned implementation."
    ),
    "control_plane.py": (
        "KNOWN LIVE INSTANCE OF THIS DEFECT, not a benign exception. "
        "`_common_git_dir` falls back to `realpath(cwd)` and `checkout_key()` hashes it, so "
        "leases, journals, checkpoints and allowances can key a wrong path. Deliberately "
        "outside issue #742's ratified enumeration because converting it propagates a refusal "
        "through the lease/journal surface; it needs its own issue with a never-raise audit of "
        "every `checkout_dir`/`issue_dir` consumer."
    ),
    "guardian_vitals.py": (
        "Spawns `rev-parse --show-toplevel` through an injectable `run`, publishes "
        "`not-collected` with a reason when it fails, and never derives a store key."
    ),
    "engine_dispatch.py": (
        "Dispatch-time preflight validation of a build worktree, not calibration/config "
        "store-key derivation."
    ),
    "review_base_guard.py": (
        "Review dispatch metadata binding (meta.repoRoot vs checkout toplevel); never "
        "derives a calibration/config store key."
    ),
}


def _lib_py_modules():
    return sorted(glob.glob(os.path.join(_LIB, "*.py")))


def _string_literals(node):
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            yield child.value


def _call_attr_name(node):
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _is_git_arg_literal_call(node):
    if not isinstance(node, ast.Call):
        return False
    for lit in _string_literals(node):
        if lit in _FLAGGED_GIT_ARGS:
            return True
    return False


def _walk_nodes(subtree):
    if isinstance(subtree, list):
        for item in subtree:
            yield from _walk_nodes(item)
        return
    for node in ast.walk(subtree):
        yield node


def _subtree_has_git_join(subtree):
    for node in _walk_nodes(subtree):
        if not isinstance(node, ast.Call):
            continue
        if _call_attr_name(node.func) != "join":
            continue
        if any(isinstance(a, ast.Constant) and a.value == ".git" for a in node.args):
            return True
    return False


def _subtree_has_pathlib_parents_walk(subtree):
    for node in _walk_nodes(subtree):
        if not isinstance(node, ast.For):
            continue
        iter_attr = None
        if isinstance(node.iter, ast.Attribute):
            iter_attr = node.iter.attr
        if iter_attr != "parents":
            continue
        body = node.body + getattr(node, "orelse", [])
        if _subtree_has_git_entry_test(body):
            return True
    return False


def _subtree_has_git_entry_test(subtree):
    for node in _walk_nodes(subtree):
        if not isinstance(node, ast.Call):
            continue
        attr = _call_attr_name(node.func)
        if attr in _EXISTS_ATTRS:
            return True
    return False


def _subtree_has_dirname_walk(subtree):
    for node in _walk_nodes(subtree):
        if isinstance(node, ast.Call) and _call_attr_name(node.func) == "dirname":
            return True
    return False


def _is_manual_git_ancestor_loop(node):
    if not isinstance(node, (ast.While, ast.For)):
        return False
    if _subtree_has_pathlib_parents_walk(node):
        return True
    body = node.body + getattr(node, "orelse", [])
    return (_subtree_has_git_join(body)
            and _subtree_has_git_entry_test(body)
            and _subtree_has_dirname_walk(body))


def find_violations(source, filename="<unknown>"):
    """Return [{kind, lineno, detail}, ...] for one module source string."""
    tree = ast.parse(source, filename=filename)
    out = []
    for node in ast.walk(tree):
        if _is_git_arg_literal_call(node):
            flagged = sorted({lit for lit in _string_literals(node)
                              if lit in _FLAGGED_GIT_ARGS})
            out.append({
                "kind": "git-arg-literal",
                "lineno": node.lineno,
                "detail": "call includes %s" % ", ".join(flagged),
            })
        if _is_manual_git_ancestor_loop(node):
            detail = "loop joins .git and walks os.path.dirname"
            if _subtree_has_pathlib_parents_walk(node):
                detail = "loop walks pathlib Path.parents and tests a .git entry"
            out.append({
                "kind": "manual-git-ancestor-walk",
                "lineno": node.lineno,
                "detail": detail,
            })
    return out


def census_module(path):
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    return find_violations(source, filename=path)


def test_allowlist_justifications_are_non_empty():
    for mod, justification in ALLOWLIST.items():
        assert justification.strip(), "empty allowlist justification for %s" % mod


def test_allowlist_entries_are_disclosed_violations():
    for mod in ALLOWLIST:
        path = os.path.join(_LIB, mod)
        assert os.path.isfile(path), "allowlisted module missing: %s" % mod
        violations = census_module(path)
        assert violations, (
            "%s is allowlisted but the census found no violation to disclose" % mod
        )


def test_lib_repo_root_census_no_unallowlisted_violations():
    unexpected = {}
    for path in _lib_py_modules():
        mod = os.path.basename(path)
        violations = census_module(path)
        if not violations:
            continue
        if mod in ALLOWLIST:
            continue
        unexpected[mod] = violations
    assert not unexpected, (
        "unsanctioned repo-root resolution outside store_core:\n"
        + "\n".join(
            "  %s:%s %s %s" % (mod, v["lineno"], v["kind"], v["detail"])
            for mod, vs in sorted(unexpected.items())
            for v in vs
        )
    )


def test_census_flags_pathlib_only_manual_git_walk(tmp_path):
    """Pathlib-only ancestor walk must be flagged without an os.path rogue in the fixture."""
    decoy = tmp_path / "pathlib_decoy.py"
    decoy.write_text(textwrap.dedent("""\
        from pathlib import Path

        def rogue_repo_root_pathlib(cwd):
            for parent in Path(cwd).resolve().parents:
                if (parent / ".git").exists():
                    return str(parent)
            return cwd
    """))
    violations = census_module(str(decoy))
    kinds = {v["kind"] for v in violations}
    assert kinds == {"manual-git-ancestor-walk"}


def test_census_flags_synthetic_fall_open_resolver(tmp_path):
    """A census that cannot fail is worthless — prove this one catches a fresh resolver."""
    decoy = tmp_path / "decoy_resolver.py"
    decoy.write_text(textwrap.dedent("""\
        import os
        import subprocess
        from pathlib import Path

        def rogue_repo_root_cwd(cwd):
            path = os.path.realpath(cwd)
            while True:
                git_entry = os.path.join(path, ".git")
                if os.path.isdir(git_entry):
                    return path
                parent = os.path.dirname(path)
                if parent == path:
                    break
                path = parent
            out = subprocess.run(
                ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                capture_output=True, text=True,
            )
            return out.stdout.strip() or cwd

        def rogue_repo_root_pathlib(cwd):
            for parent in Path(cwd).resolve().parents:
                if (parent / ".git").exists():
                    return str(parent)
            out = subprocess.run(
                ["git", "-C", cwd, "rev-parse", "--show-cdup"],
                capture_output=True, text=True,
            )
            return out.stdout.strip() or cwd

        def rogue_repo_root_git_dir(cwd):
            out = subprocess.run(
                ["git", "-C", cwd, "rev-parse", "--git-dir"],
                capture_output=True, text=True,
            )
            return out.stdout.strip() or cwd
    """))
    violations = census_module(str(decoy))
    kinds = {v["kind"] for v in violations}
    flagged_args = set()
    for v in violations:
        if v["kind"] == "git-arg-literal":
            for lit in ("--show-toplevel", "--show-cdup", "--git-dir"):
                if lit in v["detail"]:
                    flagged_args.add(lit)
    assert "manual-git-ancestor-walk" in kinds
    assert "git-arg-literal" in kinds
    assert flagged_args == {"--show-toplevel", "--show-cdup", "--git-dir"}
