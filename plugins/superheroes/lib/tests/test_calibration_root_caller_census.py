"""Static AST census: every calibration_resolve caller adjudicates UnresolvableRootError (#844)."""
import ast
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
_SKILLS = os.path.realpath(os.path.join(_HERE, "..", "..", "skills"))
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
    "round_driver.py::_resolved_calibration_paths::resolve": (
        "convert to explicit gate_refusal placeholder (never 'not resolved for this project')"
    ),
}

_CALIBRATION_MODULE = "calibration_resolve"
_HANDLER_FALL_OPEN_EXISTS_FALSE = re.compile(
    r'"exists"\s*:\s*false', re.IGNORECASE
)
_HANDLER_FALL_OPEN_LOCATION_NONE = re.compile(
    r'"location"\s*:\s*"none"', re.IGNORECASE
)
_CALIBRATION_RESOLVE_INVOCATION = re.compile(
    r'calibration_resolve\.py["\s]+resolve\b'
)


def _is_calibration_module_binding(value):
    """True when value binds calibration_resolve via sys.modules.get or importlib.import_module."""
    if not isinstance(value, ast.Call):
        return False
    func = value.func
    if isinstance(func, ast.Attribute):
        if (
            isinstance(func.value, ast.Attribute)
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "sys"
            and func.value.attr == "modules"
            and func.attr == "get"
            and value.args
            and isinstance(value.args[0], ast.Constant)
        ):
            return value.args[0].value == _CALIBRATION_MODULE
        if (
            isinstance(func.value, ast.Name)
            and func.value.id == "importlib"
            and func.attr == "import_module"
            and value.args
            and isinstance(value.args[0], ast.Constant)
        ):
            return value.args[0].value == _CALIBRATION_MODULE
    return False


def _collect_calibration_bindings(tree):
    """Bound names for calibration_resolve imports in a module."""
    module_names = set()
    resolve_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if _is_calibration_module_binding(node.value):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        module_names.add(target.id)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _CALIBRATION_MODULE:
                    module_names.add(alias.asname or _CALIBRATION_MODULE)
        elif isinstance(node, ast.ImportFrom):
            if node.module == _CALIBRATION_MODULE:
                for alias in node.names:
                    bound = alias.asname or alias.name
                    if alias.name == "resolve":
                        resolve_names.add(bound)
    return module_names, resolve_names


def _call_site_tag(call, module_names, resolve_names):
    func = call.func
    if isinstance(func, ast.Attribute):
        if func.attr == "resolve":
            val = func.value
            if isinstance(val, ast.Name) and val.id in module_names:
                return "resolve"
        if func.attr == "resolve_profile_path":
            return "resolve_profile_path"
    if isinstance(func, ast.Name):
        if func.id in resolve_names:
            return "resolve"
        if func.id == "_resolve_profile_path":
            return "_resolve_profile_path"
    return None


class _CallSiteVisitor(ast.NodeVisitor):
    def __init__(self, basename, module_names, resolve_names):
        self.basename = basename
        self.module_names = module_names
        self.resolve_names = resolve_names
        self.sites = set()
        self._stack = []
        self._contradiction_check_sites = []

    def _enclosing_name(self):
        return ".".join(self._stack) if self._stack else "<module>"

    def visit_ClassDef(self, node):
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_FunctionDef(self, node):
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_AsyncFunctionDef(self, node):
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_Call(self, node):
        for kw in node.keywords:
            if kw.arg == "_contradiction_check":
                self._contradiction_check_sites.append(
                    "%s::%s" % (self.basename, self._enclosing_name())
                )
        tag = _call_site_tag(node, self.module_names, self.resolve_names)
        if tag is not None:
            self.sites.add(
                "%s::%s::%s" % (self.basename, self._enclosing_name(), tag)
            )
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


def _skills_markdown_files():
    files = []
    for dirpath, _dirnames, filenames in os.walk(_SKILLS):
        for name in filenames:
            if name.endswith(".md"):
                files.append(os.path.join(dirpath, name))
    return sorted(files)


def _validate_skills_population(md_files):
    if not md_files:
        raise RuntimeError(
            "Calibration-root shell census population collapsed: derived zero markdown files "
            "from %s" % _SKILLS
        )


def _logical_shell_lines(text):
    """Physical lines merged by trailing backslash continuation."""
    logical = []
    current = None
    for line in text.splitlines():
        if current is None:
            current = line
        else:
            current = current.rstrip().rstrip("\\").rstrip() + " " + line.lstrip()
        if not line.rstrip().endswith("\\"):
            logical.append(current)
            current = None
    if current is not None:
        logical.append(current)
    return logical


def _scan_shell_text_violations(rel, text):
    """Per-file shell census: each calibration_resolve.py invocation must have a halting || handler."""
    violations = []
    invocation_count = 0
    handled_count = 0
    for line in _logical_shell_lines(text):
        for match in _CALIBRATION_RESOLVE_INVOCATION.finditer(line):
            invocation_count += 1
            rest = line[match.end():]
            or_pos = rest.find("||")
            if or_pos < 0:
                violations.append(
                    "%s: missing handler on calibration_resolve.py invocation" % rel
                )
                continue
            handled_count += 1
            handler = rest[or_pos:]
            if (
                _HANDLER_FALL_OPEN_EXISTS_FALSE.search(handler)
                or _HANDLER_FALL_OPEN_LOCATION_NONE.search(handler)
            ):
                violations.append(
                    "%s: fall-open handler on calibration_resolve.py invocation" % rel
                )
    return violations, invocation_count, handled_count


def _scan_shell_fall_opens():
    md_files = _skills_markdown_files()
    _validate_skills_population(md_files)
    total_invocations = 0
    total_handled = 0
    violations = []
    for path in md_files:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        rel = os.path.relpath(path, _SKILLS)
        file_violations, invocations, handled = _scan_shell_text_violations(rel, text)
        violations.extend(file_violations)
        total_invocations += invocations
        total_handled += handled
    if total_invocations == 0:
        raise RuntimeError(
            "Calibration-root shell census population collapsed: derived zero "
            "calibration_resolve.py invocations from %s" % _SKILLS
        )
    if total_handled == 0:
        raise RuntimeError(
            "Calibration-root shell census population collapsed: derived zero "
            "calibration_resolve.py invocations with handlers from %s" % _SKILLS
        )
    return violations


def derive_site_keys():
    modules = _lib_python_modules()
    _validate_population(modules)
    sites = set()
    contradiction_sites = []
    for path in modules:
        basename = os.path.basename(path)
        with open(path, encoding="utf-8") as fh:
            tree = _parse_source(fh.read(), path)
        module_names, resolve_names = _collect_calibration_bindings(tree)
        visitor = _CallSiteVisitor(basename, module_names, resolve_names)
        visitor.visit(tree)
        sites.update(visitor.sites)
        contradiction_sites.extend(visitor._contradiction_check_sites)
    if contradiction_sites:
        raise RuntimeError(
            "Calibration-root caller census: _contradiction_check keyword at site(s): %s"
            % ", ".join(sorted(contradiction_sites))
        )
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


def test_shell_census_no_fall_open_on_calibration_resolve():
    violations = _scan_shell_fall_opens()
    if violations:
        raise AssertionError(
            "INVARIANT: every calibration_resolve.py shell invocation must have a halting "
            "|| handler that does not yield uncalibrated-looking output; violations: %s"
            % ", ".join(violations)
        )


def test_shell_census_halting_handler_clean():
    text = (
        "CAL=$(python3 -B \"$ROOT_DIR/lib/calibration_resolve.py\" resolve) "
        "|| { echo \"halting\" >&2; exit 1; }\n"
    )
    violations, invocations, handled = _scan_shell_text_violations("fake.md", text)
    assert invocations == 1
    assert handled == 1
    assert violations == []


def test_shell_census_missing_handler_violation():
    text = "CAL=$(python3 -B \"$ROOT_DIR/lib/calibration_resolve.py\" resolve)\n"
    violations, invocations, handled = _scan_shell_text_violations("fake.md", text)
    assert invocations == 1
    assert handled == 0
    assert violations == [
        "fake.md: missing handler on calibration_resolve.py invocation"
    ]


def test_shell_census_fall_open_handler_violation():
    text = (
        "CAL=$(python3 -B \"$ROOT_DIR/lib/calibration_resolve.py\" resolve) "
        "|| CAL='{\"location\":\"none\",\"exists\":false}'\n"
    )
    violations, invocations, handled = _scan_shell_text_violations("fake.md", text)
    assert invocations == 1
    assert handled == 1
    assert violations == [
        "fake.md: fall-open handler on calibration_resolve.py invocation"
    ]


def test_matcher_catches_calibration_resolve_resolve():
    source = (
        "def bad(cwd, root):\n"
        "    import calibration_resolve\n"
        "    return calibration_resolve.resolve(cwd, root=root)\n"
    )
    path = os.path.join(_LIB, "fake_consumer.py")
    tree = _parse_source(source, path)
    module_names, resolve_names = _collect_calibration_bindings(tree)
    visitor = _CallSiteVisitor("fake_consumer.py", module_names, resolve_names)
    visitor.visit(tree)
    assert visitor.sites == {"fake_consumer.py::bad::resolve"}


def test_matcher_catches_aliased_calibration_resolve_resolve():
    source = (
        "def bad(cwd, root):\n"
        "    import calibration_resolve as cr\n"
        "    return cr.resolve(cwd, root=root)\n"
    )
    path = os.path.join(_LIB, "fake_consumer.py")
    tree = _parse_source(source, path)
    module_names, resolve_names = _collect_calibration_bindings(tree)
    visitor = _CallSiteVisitor("fake_consumer.py", module_names, resolve_names)
    visitor.visit(tree)
    assert visitor.sites == {"fake_consumer.py::bad::resolve"}


def test_matcher_catches_from_import_resolve():
    source = (
        "def bad(cwd, root):\n"
        "    from calibration_resolve import resolve\n"
        "    return resolve(cwd, root=root)\n"
    )
    path = os.path.join(_LIB, "fake_consumer.py")
    tree = _parse_source(source, path)
    module_names, resolve_names = _collect_calibration_bindings(tree)
    visitor = _CallSiteVisitor("fake_consumer.py", module_names, resolve_names)
    visitor.visit(tree)
    assert visitor.sites == {"fake_consumer.py::bad::resolve"}


def test_matcher_catches_resolve_profile_path_attribute():
    source = (
        "def bad(cwd, root):\n"
        "    return model_tier_overrides.resolve_profile_path(cwd, root)\n"
    )
    path = os.path.join(_LIB, "fake_consumer.py")
    tree = _parse_source(source, path)
    module_names, resolve_names = _collect_calibration_bindings(tree)
    visitor = _CallSiteVisitor("fake_consumer.py", module_names, resolve_names)
    visitor.visit(tree)
    assert visitor.sites == {"fake_consumer.py::bad::resolve_profile_path"}


def test_matcher_catches_bare_resolve_profile_path():
    source = (
        "def bad():\n"
        "    return _resolve_profile_path()\n"
    )
    path = os.path.join(_LIB, "fake_consumer.py")
    tree = _parse_source(source, path)
    module_names, resolve_names = _collect_calibration_bindings(tree)
    visitor = _CallSiteVisitor("fake_consumer.py", module_names, resolve_names)
    visitor.visit(tree)
    assert visitor.sites == {"fake_consumer.py::bad::_resolve_profile_path"}


def test_matcher_catches_sys_modules_get_assignment_binding():
    source = (
        "import sys\n"
        "def bad(cwd, root):\n"
        '    _cr = sys.modules.get("calibration_resolve")\n'
        "    return _cr.resolve(cwd, root=root)\n"
    )
    path = os.path.join(_LIB, "fake_consumer.py")
    tree = _parse_source(source, path)
    module_names, resolve_names = _collect_calibration_bindings(tree)
    visitor = _CallSiteVisitor("fake_consumer.py", module_names, resolve_names)
    visitor.visit(tree)
    assert visitor.sites == {"fake_consumer.py::bad::resolve"}


def test_matcher_catches_importlib_import_module_assignment_binding():
    source = (
        "import importlib\n"
        "def bad(cwd, root):\n"
        '    _cr = importlib.import_module("calibration_resolve")\n'
        "    return _cr.resolve(cwd, root=root)\n"
    )
    path = os.path.join(_LIB, "fake_consumer.py")
    tree = _parse_source(source, path)
    module_names, resolve_names = _collect_calibration_bindings(tree)
    visitor = _CallSiteVisitor("fake_consumer.py", module_names, resolve_names)
    visitor.visit(tree)
    assert visitor.sites == {"fake_consumer.py::bad::resolve"}


def test_matcher_distinct_keys_for_same_named_methods_in_different_classes():
    source = (
        "import calibration_resolve as cr\n"
        "class A:\n"
        "    def go(self, cwd, root):\n"
        "        return cr.resolve(cwd, root=root)\n"
        "class B:\n"
        "    def go(self, cwd, root):\n"
        "        return cr.resolve(cwd, root=root)\n"
    )
    path = os.path.join(_LIB, "fake_consumer.py")
    tree = _parse_source(source, path)
    module_names, resolve_names = _collect_calibration_bindings(tree)
    visitor = _CallSiteVisitor("fake_consumer.py", module_names, resolve_names)
    visitor.visit(tree)
    assert visitor.sites == {
        "fake_consumer.py::A.go::resolve",
        "fake_consumer.py::B.go::resolve",
    }


def test_matcher_fails_on_contradiction_check_keyword():
    source = (
        "def bad(cwd, root):\n"
        "    import calibration_resolve\n"
        "    return calibration_resolve.resolve(cwd, root=root, _contradiction_check=False)\n"
    )
    path = os.path.join(_LIB, "fake_consumer.py")
    tree = _parse_source(source, path)
    module_names, resolve_names = _collect_calibration_bindings(tree)
    visitor = _CallSiteVisitor("fake_consumer.py", module_names, resolve_names)
    visitor.visit(tree)
    assert visitor._contradiction_check_sites == ["fake_consumer.py::bad"]
