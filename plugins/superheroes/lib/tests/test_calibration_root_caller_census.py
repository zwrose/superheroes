"""Static AST census: every calibration_resolve caller adjudicates UnresolvableRootError (#844)."""
import ast
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

_EXEMPT_MODULE = "calibration_resolve.py"
_REQUIRED_BASENAMES = ("review_code_config.py", "configure_view.py")

# Site key: "<module basename>::<enclosing def name>::<attr-or-name>"
# Value: how that call site handles UnresolvableRootError (must not swallow into uncalibrated-looking output).
ADJUDICATED = {
    "configure_view.py::collect::resolve_profile_path": (
        "re-raise UnresolvableRootError; fail-open other exceptions"
    ),
    "core_md.py::_evaluate_configured_dispatch_gate::resolve_profile_path": (
        "convert to gate_refusal evaluation_error (explicit refusal)"
    ),
    "model_tier_overrides.py::_resolve_profile_path::resolve_profile_path": (
        "re-raise UnresolvableRootError; return None for other exceptions"
    ),
    "model_tier_overrides.py::main::_resolve_profile_path": (
        "show/write branch propagates; bare loader fail-opens overrides to {}"
    ),
    "model_tier_overrides.py::resolve_profile_path::_resolve_profile_path": (
        "propagate via _resolve_profile_path re-raise"
    ),
    "preflight_probe.py::_dispatch_selftest_config::resolve_profile_path": (
        "convert to read_error (explicit refusal marker)"
    ),
    "preflight_probe.py::dispatch_calibration::resolve_profile_path": (
        "convert to read_error marker (explicit refusal)"
    ),
    "review_code_config.py::resolve::resolve": (
        "re-raise UnresolvableRootError; fail-open other exceptions"
    ),
    "review_store.py::create::resolve": (
        "propagate (no handler — UnresolvableRootError surfaces to caller)"
    ),
    "review_store.py::resolve::resolve": (
        "propagate (no handler — UnresolvableRootError surfaces to caller)"
    ),
}


def _call_site_tag(call):
    func = call.func
    if isinstance(func, ast.Attribute):
        if func.attr == "resolve":
            val = func.value
            if isinstance(val, ast.Name) and val.id == "calibration_resolve":
                return "resolve"
        if func.attr == "resolve_profile_path":
            return "resolve_profile_path"
    if isinstance(func, ast.Name) and func.id == "_resolve_profile_path":
        return "_resolve_profile_path"
    return None


class _CallSiteVisitor(ast.NodeVisitor):
    def __init__(self, basename):
        self.basename = basename
        self.sites = set()
        self._stack = []

    def visit_FunctionDef(self, node):
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_AsyncFunctionDef(self, node):
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_Call(self, node):
        tag = _call_site_tag(node)
        if tag is not None:
            def_name = self._stack[-1] if self._stack else "<module>"
            self.sites.add("%s::%s::%s" % (self.basename, def_name, tag))
        self.generic_visit(node)


def _parse_source(source, source_path):
    try:
        return ast.parse(source, filename=source_path)
    except SyntaxError as exc:
        raise RuntimeError(
            "Census cannot parse %s: %s" % (source_path, exc)
        ) from exc


def _lib_python_modules():
    """Every .py directly under lib/, excluding tests/ and calibration_resolve.py."""
    modules = []
    for name in sorted(os.listdir(_LIB)):
        if not name.endswith(".py"):
            continue
        if name == _EXEMPT_MODULE:
            continue
        modules.append(os.path.join(_LIB, name))
    return modules


def _path_under_tests(path):
    tests_dir = os.path.join(_LIB, "tests")
    try:
        return os.path.commonpath([os.path.realpath(path), tests_dir]) == tests_dir
    except ValueError:
        return False


def _validate_population(modules):
    if not modules:
        raise RuntimeError(
            "Calibration-root caller census population collapsed: derived zero modules from %s "
            "(expected every .py under lib/ except %s)"
            % (_LIB, _EXEMPT_MODULE)
        )
    basenames = {os.path.basename(p) for p in modules}
    missing = [n for n in _REQUIRED_BASENAMES if n not in basenames]
    if missing:
        raise RuntimeError(
            "Calibration-root caller census population collapsed: derived population missing "
            "required module(s): %s" % ", ".join(missing)
        )
    for path in modules:
        if _path_under_tests(path):
            raise RuntimeError(
                "Calibration-root caller census population includes test module: %s" % path
            )


def derive_site_keys():
    modules = _lib_python_modules()
    _validate_population(modules)
    sites = set()
    for path in modules:
        basename = os.path.basename(path)
        with open(path, encoding="utf-8") as fh:
            tree = _parse_source(fh.read(), path)
        visitor = _CallSiteVisitor(basename)
        visitor.visit(tree)
        sites.update(visitor.sites)
    return sites


def test_calibration_root_caller_census_adjudicated():
    derived = derive_site_keys()
    if derived != set(ADJUDICATED):
        new = sorted(derived - set(ADJUDICATED))
        removed = sorted(set(ADJUDICATED) - derived)
        parts = []
        if new:
            parts.append(
                "new site key(s) — adjudicate in ADJUDICATED (a site that converts the refusal "
                "into an uncalibrated-looking result re-opens #844): %s"
                % ", ".join(new)
            )
        if removed:
            parts.append(
                "removed site key(s) — update ADJUDICATED: %s" % ", ".join(removed)
            )
        raise AssertionError(
            "INVARIANT: every calibration_resolve caller must adjudicate UnresolvableRootError; "
            + "; ".join(parts)
        )


def test_matcher_catches_calibration_resolve_resolve():
    source = (
        "def bad(cwd, root):\n"
        "    import calibration_resolve\n"
        "    return calibration_resolve.resolve(cwd, root=root)\n"
    )
    path = os.path.join(_LIB, "fake_consumer.py")
    tree = _parse_source(source, path)
    visitor = _CallSiteVisitor("fake_consumer.py")
    visitor.visit(tree)
    assert visitor.sites == {"fake_consumer.py::bad::resolve"}


def test_matcher_catches_resolve_profile_path_attribute():
    source = (
        "def bad(cwd, root):\n"
        "    return model_tier_overrides.resolve_profile_path(cwd, root)\n"
    )
    path = os.path.join(_LIB, "fake_consumer.py")
    tree = _parse_source(source, path)
    visitor = _CallSiteVisitor("fake_consumer.py")
    visitor.visit(tree)
    assert visitor.sites == {"fake_consumer.py::bad::resolve_profile_path"}


def test_matcher_catches_bare_resolve_profile_path():
    source = (
        "def bad():\n"
        "    return _resolve_profile_path()\n"
    )
    path = os.path.join(_LIB, "fake_consumer.py")
    tree = _parse_source(source, path)
    visitor = _CallSiteVisitor("fake_consumer.py")
    visitor.visit(tree)
    assert visitor.sites == {"fake_consumer.py::bad::_resolve_profile_path"}
