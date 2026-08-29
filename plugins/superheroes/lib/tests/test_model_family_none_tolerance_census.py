"""AST census: no None-tolerant guard on shipped model_family calls; family_for consumers enumerated.

Scanned file set: every tracked non-test ``.py`` file under the repository root — the same
enumeration as ``source_guard.watched_paths`` (includes ``plugins/superheroes/hooks/``,
repo-root ``source_guard.py``, and all other shipped Python surfaces).

Paths are resolved from this file's directory, never an ambient cwd.

bite-axis: model_family must resolve or refuse (UnknownModel) — None-tolerant guards on its
call sites are dead fall-opens; family_for legitimately returns None for an absent matrix cell
and its None-tolerant guards are allowlisted by enclosing function.
"""
import ast
import os

import pytest

import source_guard as sg

_TESTS = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.realpath(os.path.join(_TESTS, "..", "..", "..", ".."))

_KNOWN_MODEL_FAMILY_SITE = ("model_registry.py", "family_for")

FAMILY_FOR_MODULES = frozenset({
    "seat_map.py",
    "round_driver.py",
    "review_loop_runner.py",
})

# module basename -> {function name: non-empty justification}
FAMILY_FOR_NONE_TOLERANCE_ALLOWLIST = {
    "seat_map.py": {
        "_resolvable_families_for_seat": (
            "family_for returns None when the matrix cell is absent — is-None and or-not-allowed "
            "skip vendors that cannot resolve at this tier."
        ),
        "_seat_family": (
            "family_for returns None for an absent matrix cell at the seat tier; "
            "is-not-None returns the present cell, otherwise falls through to reviewer tier."
        ),
        "_resolve_at_tier": (
            "family_for returns None when matrix_config(role, vendor) is absent — "
            "the seat candidate is refused before rotation."
        ),
        "_backfill": (
            "family_for returns None when the reviewer/claude cell is absent; "
            "or 'anthropic' is the declared last-resort family string for that edge."
        ),
        "build": (
            "family_for returns None when the pinned vendor's matrix cell is absent; "
            "truthiness on fam gates grounding independence only when a family is present."
        ),
    },
    "round_driver.py": {
        "_auditor_vendor": (
            "family_for returns None when the code-fixer or verifier matrix cell is absent; "
            "degraded/independence checks branch on that absent-cell condition."
        ),
    },
    "review_loop_runner.py": {
        "_eval_live_pool_families": (
            "family_for returns None for a pool vendor with an absent matrix cell; "
            "is-not-None collects only resolved families from the live pool."
        ),
        "_validate_fixer_vendor_override": (
            "family_for returns None when the override vendor has no code-fixer cell; "
            "is-None refuses the fixture before seat-map build."
        ),
    },
}


def _norm_path(path):
    return path.replace("\\", "/")


def _is_under_tests_or_fixtures(path):
    norm = _norm_path(path)
    if "/fixtures/" in norm:
        return True
    if "/tests/" in norm or norm.endswith("/tests"):
        return True
    return False


def _scanned_py_files():
    """Every shipped Python module (tracked non-test .py, same set as source_guard)."""
    files = []
    seen = set()
    for path in sorted(sg.watched_paths(_REPO_ROOT)):
        real = os.path.realpath(path)
        if real in seen or not os.path.isfile(real):
            continue
        if _is_under_tests_or_fixtures(real):
            continue
        seen.add(real)
        files.append(real)
    return files


def _aliases_from_import(stmt, target_func):
    """Local names that refer to target_func via ImportFrom."""
    if not isinstance(stmt, ast.ImportFrom):
        return set()
    aliases = set()
    for alias in stmt.names:
        if alias.name == target_func:
            aliases.add(alias.asname or alias.name)
    return aliases


def _collect_import_aliases(stmts, target_func):
    """ImportFrom aliases for target_func declared directly in stmts."""
    aliases = set()
    for stmt in stmts:
        aliases |= _aliases_from_import(stmt, target_func)
    return aliases


def _is_target_call(node, func_name, aliases=None):
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    local_names = {func_name}
    if aliases:
        local_names |= aliases
    if isinstance(func, ast.Name) and func.id in local_names:
        return True
    if isinstance(func, ast.Attribute) and func.attr == func_name:
        return True
    return False


def _subtree_contains(root, target):
    if root is target:
        return True
    for child in ast.iter_child_nodes(root):
        if _subtree_contains(child, target):
            return True
    return False


def _is_none_constant(node):
    return isinstance(node, ast.Constant) and node.value is None


def _same_subject(operand, subject):
    if operand is subject:
        return True
    if isinstance(operand, ast.Name) and isinstance(subject, ast.Name):
        return operand.id == subject.id
    return False


def _compare_none_pattern(node, subject):
    """P3 or P4 when subject is compared to None, else None."""
    involved = _subtree_contains(node.left, subject) or _same_subject(node.left, subject)
    if not involved:
        for comp in node.comparators:
            if _subtree_contains(comp, subject) or _same_subject(comp, subject):
                involved = True
                break
    if not involved:
        return None
    for op, comp in zip(node.ops, node.comparators):
        left_none = _is_none_constant(node.left)
        right_none = _is_none_constant(comp)
        if not left_none and not right_none:
            continue
        if isinstance(op, (ast.Is, ast.IsNot)):
            return "P3"
        if isinstance(op, (ast.Eq, ast.NotEq)):
            return "P4"
    return None


def _operand_none_tolerant(operand, subject):
    if _same_subject(operand, subject):
        return True
    if isinstance(operand, ast.Compare):
        return _compare_none_pattern(operand, subject) is not None
    if isinstance(operand, ast.UnaryOp) and isinstance(operand.op, ast.Not):
        return _same_subject(operand.operand, subject)
    return False


def _bare_truthiness_test(test, subject):
    return _same_subject(test, subject)


def _patterns_for_subject(subject, tree):
    """Return pattern ids (P1–P6) where subject participates in a None-tolerant construct."""
    patterns = []
    seen = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.BoolOp):
            for operand in node.values:
                if not _operand_none_tolerant(operand, subject):
                    continue
                if isinstance(node.op, ast.Or):
                    pat = "P1"
                elif isinstance(node.op, ast.And):
                    pat = "P2"
                else:
                    pat = "P6"
                key = (pat, node.lineno)
                if key not in seen:
                    seen.add(key)
                    patterns.append(pat)
        elif isinstance(node, ast.Compare):
            pat = _compare_none_pattern(node, subject)
            if pat is None:
                continue
            key = (pat, node.lineno)
            if key not in seen:
                seen.add(key)
                patterns.append(pat)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            if _same_subject(node.operand, subject):
                key = ("P5", node.lineno)
                if key not in seen:
                    seen.add(key)
                    patterns.append("P5")
        elif isinstance(node, (ast.If, ast.IfExp, ast.While)):
            if not _bare_truthiness_test(node.test, subject):
                continue
            key = ("P6", node.lineno)
            if key not in seen:
                seen.add(key)
                patterns.append("P6")
    return patterns


def _linear_stmts(block):
    """Statements in a scope, including nested blocks but not nested functions."""
    out = []

    def rec(stmts):
        for stmt in stmts:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            out.append(stmt)
            if isinstance(stmt, (ast.For, ast.While)):
                rec(stmt.body)
                rec(stmt.orelse)
            elif isinstance(stmt, ast.If):
                rec(stmt.body)
                rec(stmt.orelse)
            elif isinstance(stmt, ast.Try):
                rec(stmt.body)
                for handler in stmt.handlers:
                    rec(handler.body)
                rec(stmt.orelse)
            elif isinstance(stmt, ast.With):
                rec(stmt.body)

    rec(block)
    return out


def _scope_expr_nodes(stmt):
    """Expression nodes in stmt, excluding nested function bodies."""
    nested = set()
    for child in ast.walk(stmt):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child is not stmt:
            for n in ast.walk(child):
                nested.add(n)
    for node in ast.walk(stmt):
        if node not in nested:
            yield node


def _analyze_scope(body, basename, func_name, target_func, enclosing_aliases=None):
    violations = []
    bound = {}
    aliases = set(enclosing_aliases or ())

    def check_subject(subject, stmt, lineno, bound_name=None, bind_line=None):
        patterns = _patterns_for_subject(subject, stmt)
        if not patterns:
            return
        for pat in patterns:
            detail = "%s:%d pattern %s" % (basename, lineno, pat)
            if bound_name is not None:
                detail += " bound name %s (bound at line %d)" % (bound_name, bind_line)
            violations.append({
                "func": func_name,
                "lineno": lineno,
                "pattern": pat,
                "detail": detail,
            })

    def walk_stmt(stmt):
        for node in _scope_expr_nodes(stmt):
            if _is_target_call(node, target_func, aliases):
                check_subject(node, stmt, node.lineno)
            elif isinstance(node, ast.Name) and node.id in bound:
                check_subject(node, stmt, node.lineno, node.id, bound[node.id])

    def update_bindings(stmt):
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            target = stmt.targets[0]
            if isinstance(target, ast.Name):
                if _is_target_call(stmt.value, target_func, aliases):
                    bound[target.id] = stmt.lineno
                else:
                    bound.pop(target.id, None)
        elif (
            isinstance(stmt, ast.AnnAssign)
            and isinstance(stmt.target, ast.Name)
            and stmt.value is not None
        ):
            if _is_target_call(stmt.value, target_func, aliases):
                bound[stmt.target.id] = stmt.lineno
            else:
                bound.pop(stmt.target.id, None)

    for stmt in _linear_stmts(body):
        aliases |= _aliases_from_import(stmt, target_func)
        walk_stmt(stmt)
        update_bindings(stmt)

    return violations


class _ModuleCensusVisitor(ast.NodeVisitor):
    def __init__(self, basename, target_func, tree):
        self.basename = basename
        self.target_func = target_func
        self.violations = []
        self.call_sites = []
        self.family_for_modules = set()
        self._scope_stack = ["<module>"]
        self._alias_stack = [_collect_import_aliases(tree.body, target_func)]

    def _current_func(self):
        return self._scope_stack[-1]

    def _current_aliases(self):
        return self._alias_stack[-1]

    def _analyze_function(self, node):
        self._scope_stack.append(node.name)
        self._alias_stack.append(set(self._current_aliases()))
        self.violations.extend(
            _analyze_scope(
                node.body,
                self.basename,
                node.name,
                self.target_func,
                self._current_aliases(),
            )
        )
        self.generic_visit(node)
        self._scope_stack.pop()
        self._alias_stack.pop()

    def visit_FunctionDef(self, node):
        self._analyze_function(node)

    def visit_AsyncFunctionDef(self, node):
        self._analyze_function(node)

    def visit_Module(self, node):
        self.violations.extend(
            _analyze_scope(
                node.body,
                self.basename,
                "<module>",
                self.target_func,
                self._current_aliases(),
            )
        )
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        for alias in node.names:
            if alias.name == self.target_func:
                self._current_aliases().add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_Call(self, node):
        if _is_target_call(node, self.target_func, self._current_aliases()):
            self.call_sites.append((self.basename, self._current_func(), node.lineno))
            if self.target_func == "family_for":
                self.family_for_modules.add(self.basename)
        self.generic_visit(node)


def _parse_file(path):
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        raise AssertionError(
            "census cannot parse scanned file %s: %s" % (path, exc)
        ) from exc
    return tree


def _census_file(path, target_func):
    basename = os.path.basename(path)
    tree = _parse_file(path)
    visitor = _ModuleCensusVisitor(basename, target_func, tree)
    visitor.visit(tree)
    return visitor


def _collect_census(target_func):
    scanned = _scanned_py_files()
    if not scanned:
        raise AssertionError(
            "model_family census enumeration went empty — glob matched no scanned files"
        )
    all_violations = []
    all_call_sites = []
    family_for_modules = set()
    family_for_violations_by_module = {}
    for path in scanned:
        result = _census_file(path, target_func)
        all_violations.extend(result.violations)
        all_call_sites.extend(result.call_sites)
        if target_func == "family_for":
            if result.family_for_modules:
                family_for_modules.add(result.basename)
            if result.violations:
                mod = result.basename
                bucket = family_for_violations_by_module.setdefault(mod, {})
                for v in result.violations:
                    bucket.setdefault(v["func"], v["detail"])
    return {
        "violations": all_violations,
        "call_sites": all_call_sites,
        "family_for_modules": family_for_modules,
        "family_for_violations_by_module": family_for_violations_by_module,
    }


def test_family_for_allowlist_justifications_are_non_empty():
    for mod, entries in FAMILY_FOR_NONE_TOLERANCE_ALLOWLIST.items():
        for func, justification in entries.items():
            assert justification.strip(), (
                "empty allowlist justification for %s in %s" % (func, mod)
            )


def test_model_family_none_tolerance_census():
    result = _collect_census("model_family")
    call_sites = result["call_sites"]
    if not call_sites:
        pytest.fail(
            "model_family census enumeration went empty — no shipped model_family call sites found"
        )
    known_present = any(
        site[0] == _KNOWN_MODEL_FAMILY_SITE[0] and site[1] == _KNOWN_MODEL_FAMILY_SITE[1]
        for site in call_sites
    )
    assert known_present, (
        "known model_family call site missing: expected %s inside %s"
        % (_KNOWN_MODEL_FAMILY_SITE[1], _KNOWN_MODEL_FAMILY_SITE[0])
    )
    violations = result["violations"]
    assert not violations, (
        "None-tolerant guard on shipped model_family call:\n"
        + "\n".join("  %s" % v["detail"] for v in violations)
    )


def test_family_for_consumer_modules_enumerated():
    result = _collect_census("family_for")
    actual = result["family_for_modules"]
    assert actual == set(FAMILY_FOR_MODULES), (
        "family_for consumer module set drifted — update FAMILY_FOR_MODULES consciously; "
        "known non-Python consumer: plugins/superheroes/skills/review-code/reference/setup.md "
        "(shell python3 -c family_for(...) or '' for author-family-unresolved). "
        "expected %s got %s"
        % (sorted(FAMILY_FOR_MODULES), sorted(actual))
    )


@pytest.mark.parametrize("src,expected", [
    ("def f():\n    return model_family(v, m) or 'x'\n", "P1"),
    (
        "def f():\n    fam = model_family(v, m)\n    if fam and fam in EX:\n        return None\n",
        "P2",
    ),
    (
        "def f():\n    fam = model_family(v, m)\n    if fam is None:\n        return None\n",
        "P3",
    ),
    (
        "def f():\n    fam = model_family(v, m)\n    if fam == None:\n        return None\n",
        "P4",
    ),
    (
        "def f():\n    fam = model_family(v, m)\n    if not fam:\n        return None\n",
        "P5",
    ),
    (
        "def f():\n    fam = model_family(v, m)\n    if fam:\n        return fam\n",
        "P6",
    ),
])
def test_pattern_matcher_arms(src, expected):
    tree = ast.parse(src)
    vios = _analyze_scope(tree.body[0].body, "synthetic.py", "f", "model_family")
    assert expected in {v["pattern"] for v in vios}, vios


def test_pattern_matcher_ignores_clean_call():
    tree = ast.parse("def f():\n    return model_family(v, m)\n")
    assert _analyze_scope(tree.body[0].body, "synthetic.py", "f", "model_family") == []


def test_pattern_matcher_annassign_then_guard():
    src = (
        "def f():\n"
        "    fam: str = model_family(v, m)\n"
        "    if not fam:\n"
        "        return None\n"
    )
    tree = ast.parse(src)
    vios = _analyze_scope(tree.body[0].body, "synthetic.py", "f", "model_family")
    assert vios, vios
    assert "P5" in {v["pattern"] for v in vios}, vios


def test_model_family_census_scans_hooks_tree():
    scanned = {os.path.realpath(p) for p in _scanned_py_files()}
    hooks_dir = os.path.join(_REPO_ROOT, "plugins", "superheroes", "hooks")
    missing = sorted(
        os.path.join(hooks_dir, name)
        for name in os.listdir(hooks_dir)
        if name.endswith(".py")
        and os.path.join(hooks_dir, name) not in scanned
        and os.path.realpath(os.path.join(hooks_dir, name)) not in scanned
    )
    assert not missing, "hooks modules absent from census scan set: %s" % missing


def test_hooks_consumer_assign_then_guard_detected():
    """Red-axis: assign-then-guard under a hooks module basename is a violation when scanned."""
    src = (
        "def _strike(v, m):\n"
        "    fam = model_family(v, m)\n"
        "    if not fam:\n"
        "        return None\n"
    )
    tree = ast.parse(src)
    visitor = _ModuleCensusVisitor("session_start.py", "model_family", tree)
    visitor.visit(tree)
    assert visitor.call_sites, "model_family call in hooks-shaped consumer must be enumerated"
    assert visitor.violations, (
        "truthiness guard on model_family binding in hooks-shaped consumer must be a violation"
    )
    assert "P5" in {v["pattern"] for v in visitor.violations}, visitor.violations


def test_model_family_aliased_import_detected():
    src = (
        "from model_registry import model_family as mf\n"
        "\n"
        "def consumer(v, m):\n"
        "    fam = mf(v, m)\n"
        "    if not fam:\n"
        "        return None\n"
    )
    tree = ast.parse(src)
    visitor = _ModuleCensusVisitor("synthetic.py", "model_family", tree)
    visitor.visit(tree)
    assert visitor.call_sites, "aliased model_family call must appear in call_sites"
    assert visitor.violations, (
        "truthiness guard on aliased model_family binding must be a violation"
    )
    patterns = {v["pattern"] for v in visitor.violations}
    assert "P5" in patterns, patterns


def test_family_for_none_tolerance_allowlist_matches_live_sites():
    result = _collect_census("family_for")
    actual = {
        mod: set(funcs.keys())
        for mod, funcs in result["family_for_violations_by_module"].items()
    }
    expected = {
        mod: set(funcs.keys())
        for mod, funcs in FAMILY_FOR_NONE_TOLERANCE_ALLOWLIST.items()
    }
    assert actual == expected, (
        "family_for None-tolerance allowlist drifted — derive from AST, key by function name:\n"
        "  actual: %s\n  expected: %s"
        % (actual, expected)
    )
