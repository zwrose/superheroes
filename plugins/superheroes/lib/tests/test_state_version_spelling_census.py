"""Census: state/receipt schema version must be spelled only from round_driver's pinned block (#1185)."""
import ast
import os
import re
import sys
from collections import namedtuple

import round_driver as RD

_TESTS = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_TESTS)
_PLUGIN_ROOT = os.path.dirname(_LIB)
_EVAL = os.path.join(_PLUGIN_ROOT, "eval")
_ROUND_DRIVER_MD = os.path.join(
    _PLUGIN_ROOT, "skills", "review-code", "reference", "round-driver.md"
)

_PINNED_SYMBOLS = frozenset({
    "STATE_SCHEMA_VERSION",
    "SUPPORTED_STATE_VERSIONS",
    "SCHEMA_VERSION",
    "RECEIPT_CERTIFIED_SCHEMA",
    "RECEIPT_ATTESTED_SCHEMA",
    "RECEIPT_INTERIM_SCHEMA",
})

_VERSION_ACCESSORS = ("_state_version", "_receipt_version")

_BEGIN_MARKER = "# --- version spelling: pinned declaration block (BEGIN) ---"
_END_MARKER = "# --- version spelling: pinned declaration block (END) ---"

_RECEIPT_CERTIFIED_LITERAL_RE = re.compile(r"receipt-certified/\d+")
_STATE_SCHEMA_PROSE_RE = re.compile(r"\(`STATE_SCHEMA_VERSION`\s*=\s*(\d+)\)")
_SCHEMA_VERSION_BULLET_RE = re.compile(
    r"`schemaVersion`\s*—\s*([^(\n]+)"
)

Finding = namedtuple("Finding", ("relpath", "line", "segment", "leg"))

# Tier-1 findings keyed by (relative path under lib/ or eval/, exact source segment).
_SPELLING_ALLOWLIST = {
    ("round_driver.py", '"schemaVersion": 2'): {
        "reason": (
            "the in-memory review-record schema, a different schema from the "
            "driver's state/receipt version"
        ),
    },
    ("architect_config.py", "SCHEMA_VERSION = 2"): {
        "reason": "architect-config manifest schema, not the driver state/receipt version",
    },
    ("control_plane.py", "SCHEMA_VERSION = 1"): {
        "reason": "control-plane meta schema, not the driver state/receipt version",
    },
    ("core_md.py", "SCHEMA_VERSION = 2"): {
        "reason": "core-md sidecar schema, not the driver state/receipt version",
    },
    ("definition_doc.py", "SCHEMA_VERSION = 1"): {
        "reason": "definition-doc manifest schema, not the driver state/receipt version",
    },
    ("eval/review_loop_runner.py", '"schemaVersion": 1'): {
        "reason": "review-loop-runner telemetry envelope schema, not the driver state/receipt version",
    },
    ("eval/review_telemetry.py", '"schemaVersion": 1'): {
        "reason": "review-telemetry record schema, not the driver state/receipt version",
    },
    ("guardian_lens_duplication.py", '"schemaVersion": 1'): {
        "reason": "guardian lens-duplication digest schema, not the driver state/receipt version",
    },
    ("guardian_lens_hotspots.py", "SCHEMA_VERSION = 1"): {
        "reason": "guardian lens-hotspots digest schema, not the driver state/receipt version",
    },
    ("liveness_cache.py", "SCHEMA_VERSION = 3"): {
        "reason": "liveness-cache snapshot schema, not the driver state/receipt version",
    },
    ("loop_plan_common.py", '"schemaVersion": 1'): {
        "reason": "loop-plan common manifest schema, not the driver state/receipt version",
        "max_count": 5,
    },
    ("mode_registry.py", "SCHEMA_VERSION = 1"): {
        "reason": "mode-registry meta schema, not the driver state/receipt version",
    },
    ("mode_registry.py", "ver < 1"): {
        "reason": "mode-registry meta schemaVersion shape check, not the driver state/receipt version",
    },
    ("panel_tally.py", "SCHEMA_VERSION = 1"): {
        "reason": "panel-tally verdict schema, not the driver state/receipt version",
    },
    ("pilot_appctl.py", 'authorized.get("schemaVersion") != 1'): {
        "reason": "pilot appctl authorization record schema, not the driver state/receipt version",
    },
    ("pilot_conformance_cleanup.py", '"schemaVersion": 1'): {
        "reason": "pilot conformance-cleanup record schema, not the driver state/receipt version",
    },
    ("pilot_provision.py", '"schemaVersion": 1'): {
        "reason": "pilot provision manifest schema, not the driver state/receipt version",
    },
    ("review_loop_plan.py", "SCHEMA_VERSION = 1"): {
        "reason": "review-loop-plan manifest schema, not the driver state/receipt version",
    },
    ("review_memory.py", 'record.get("schemaVersion") == 2'): {
        "reason": "review-memory round-record schema v2, not the driver state/receipt version",
    },
    ("review_memory.py", '"schemaVersion": 2'): {
        "reason": "review-memory round-record schema v2, not the driver state/receipt version",
        "max_count": 2,
    },
    ("spec_loop_plan.py", '"schemaVersion": 1'): {
        "reason": "spec-loop-plan manifest schema, not the driver state/receipt version",
    },
    ("state.py", "SCHEMA_VERSION = 1"): {
        "reason": "generic state manifest schema, not the driver state/receipt version",
    },
}


def _scanned_py_paths():
    paths = []
    for root in (_LIB, _EVAL):
        if not os.path.isdir(root):
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            if "tests" in dirpath.split(os.sep):
                continue
            for name in filenames:
                if name.endswith(".py"):
                    paths.append(os.path.join(dirpath, name))
    return sorted(paths)


def _relpath(path):
    if path.startswith(_LIB + os.sep):
        return os.path.relpath(path, _LIB)
    if path.startswith(_EVAL + os.sep):
        return os.path.join("eval", os.path.relpath(path, _EVAL))
    return os.path.basename(path)


def _segment(source, node):
    seg = ast.get_source_segment(source, node)
    if seg is not None:
        return seg.strip()
    lines = source.splitlines()
    if 1 <= node.lineno <= len(lines):
        return lines[node.lineno - 1].strip()
    return "<unknown>"


def _is_pinned_name(node):
    if isinstance(node, ast.Name):
        return node.id in _PINNED_SYMBOLS
    if isinstance(node, ast.Attribute):
        return node.attr in _PINNED_SYMBOLS
    return False


def _module_references_pinned_symbols(tree):
    for node in ast.walk(tree):
        if _is_pinned_name(node):
            return True
    return False


def _pinned_block_line_range(source):
    begin = end = None
    for i, line in enumerate(source.splitlines(), start=1):
        if line.strip() == _BEGIN_MARKER:
            begin = i
        elif line.strip() == _END_MARKER:
            end = i
    if begin is None or end is None:
        raise ValueError("pinned declaration block markers missing or incomplete")
    if end <= begin:
        raise ValueError("pinned declaration block END must follow BEGIN")
    return begin, end


def _module_has_pinned_markers(source):
    try:
        _pinned_block_line_range(source)
    except ValueError:
        return False
    return True


def _line_in_pinned_block(line, begin, end):
    return begin <= line <= end


def _is_int_constant(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, int)


def _int_constants_from_container(node):
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        vals = []
        for elt in node.elts:
            if _is_int_constant(elt):
                vals.append(elt.value)
            else:
                return None
        return vals
    if _is_int_constant(node):
        return [node.value]
    return None


def _is_version_accessor_call(node):
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name) and func.id in _VERSION_ACCESSORS:
        return True
    if isinstance(func, ast.Attribute) and func.attr in _VERSION_ACCESSORS:
        return True
    return False


def _walk_skip_nested_functions(node):
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        yield child
        yield from _walk_skip_nested_functions(child)


def _all_scopes(tree):
    scopes = [tree]
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scopes.append(node)
    return scopes


def _schema_version_aliases_in_scope(scope):
    aliases = set()
    for node in _walk_skip_nested_functions(scope):
        if isinstance(node, ast.Assign) and _is_schema_version_read(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    aliases.add(target.id)
    return aliases


def _compares_in_scope(scope):
    compares = []
    for node in _walk_skip_nested_functions(scope):
        if isinstance(node, ast.Compare):
            compares.append(node)
    return compares


def _is_schema_version_read(node, aliases=None):
    if aliases and isinstance(node, ast.Name) and node.id in aliases:
        return True
    if _is_version_accessor_call(node):
        return True
    if isinstance(node, ast.Subscript):
        sl = node.slice
        if isinstance(sl, ast.Constant) and sl.value == "schemaVersion":
            return True
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "get":
            for arg in node.args:
                if isinstance(arg, ast.Constant) and arg.value == "schemaVersion":
                    return True
            for kw in node.keywords:
                if kw.arg is None and isinstance(kw.value, ast.Constant):
                    if kw.value.value == "schemaVersion":
                        return True
    if isinstance(node, ast.Attribute) and node.attr == "schemaVersion":
        return True
    return False


def _schema_version_read_nodes(tree):
    for node in ast.walk(tree):
        if _is_schema_version_read(node):
            yield node


def _is_receipt_certified_schema(node):
    if isinstance(node, ast.Name):
        return node.id == "RECEIPT_CERTIFIED_SCHEMA"
    if isinstance(node, ast.Attribute):
        return node.attr == "RECEIPT_CERTIFIED_SCHEMA"
    return False


def _dict_binding_targets_schema_version(key):
    if isinstance(key, ast.Constant) and key.value == "schemaVersion":
        return True
    return False


def _scan_mod_format(tree, source, relpath):
    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Mod):
            continue
        if not _is_receipt_certified_schema(node.left):
            continue
        if not _is_int_constant(node.right):
            continue
        yield Finding(
            relpath,
            node.lineno,
            _segment(source, node),
            "mod-format",
        )


def _binding_segment(source, key_node, val_node):
    if isinstance(key_node, ast.Constant) and key_node.value == "schemaVersion":
        if _is_int_constant(val_node):
            return '"schemaVersion": %d' % val_node.value
    return _segment(source, val_node)


def _scan_comparisons(tree, source, relpath):
    for scope in _all_scopes(tree):
        aliases = _schema_version_aliases_in_scope(scope)
        for node in _compares_in_scope(scope):
            operands = [node.left] + list(node.comparators)
            for i, opnd in enumerate(operands):
                if not _is_schema_version_read(opnd, aliases):
                    continue
                for j, other in enumerate(operands):
                    if i == j:
                        continue
                    ints = _int_constants_from_container(other)
                    if ints is not None:
                        yield Finding(
                            relpath,
                            node.lineno,
                            _segment(source, node),
                            "comparison",
                        )
                        break
                else:
                    continue
                break


def _scan_bindings(tree, source, relpath):
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, val in zip(node.keys, node.values):
                if key is None:
                    continue
                if _dict_binding_targets_schema_version(key) and _is_int_constant(val):
                    yield Finding(
                        relpath,
                        val.lineno,
                        _binding_segment(source, key, val),
                        "binding",
                    )
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if not isinstance(target, ast.Subscript):
                    continue
                sl = target.slice
                if isinstance(sl, ast.Constant) and sl.value == "schemaVersion":
                    if _is_int_constant(node.value):
                        yield Finding(
                            relpath,
                            node.lineno,
                            _segment(source, node),
                            "binding",
                        )
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "update":
                for arg in node.args:
                    if isinstance(arg, ast.Dict):
                        for key, val in zip(arg.keys, arg.values):
                            if key is None:
                                continue
                            if (_dict_binding_targets_schema_version(key)
                                    and _is_int_constant(val)):
                                yield Finding(
                                    relpath,
                                    val.lineno,
                                    _binding_segment(source, key, val),
                                    "binding",
                                )
            if isinstance(func, ast.Attribute) and func.attr in ("get", "setdefault"):
                if len(node.args) >= 2:
                    key, val = node.args[0], node.args[1]
                    if (isinstance(key, ast.Constant) and key.value == "schemaVersion"
                            and _is_int_constant(val)):
                        yield Finding(
                            relpath,
                            val.lineno,
                            "schemaVersion=%d" % val.value,
                            "binding",
                        )
            for kw in node.keywords:
                if kw.arg == "schemaVersion" and _is_int_constant(kw.value):
                    yield Finding(
                        relpath,
                        kw.value.lineno,
                        "schemaVersion=%d" % kw.value.value,
                        "binding",
                    )


def _scan_constant_assignments(tree, source, relpath, pinned_begin, pinned_end):
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if _line_in_pinned_block(node.lineno, pinned_begin, pinned_end):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in _PINNED_SYMBOLS:
                    pass
                elif isinstance(target, ast.Attribute) and target.attr in _PINNED_SYMBOLS:
                    pass
                else:
                    continue
                yield Finding(
                    relpath,
                    node.lineno,
                    _segment(source, node),
                    "constant-assignment",
                )
        elif isinstance(node, ast.AnnAssign):
            if _line_in_pinned_block(node.lineno, pinned_begin, pinned_end):
                continue
            target = node.target
            if isinstance(target, ast.Name) and target.id in _PINNED_SYMBOLS:
                pass
            elif isinstance(target, ast.Attribute) and target.attr in _PINNED_SYMBOLS:
                pass
            else:
                continue
            yield Finding(
                relpath,
                node.lineno,
                _segment(source, node),
                "constant-assignment",
            )


def _scan_string_literals(tree, source, relpath):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if _RECEIPT_CERTIFIED_LITERAL_RE.search(node.value):
            yield Finding(
                relpath,
                node.lineno,
                _segment(source, node),
                "string-literal",
            )


def census_module(path, source, *, pinned_range=None):
    """Return findings for one module source string."""
    relpath = _relpath(path)
    tree = ast.parse(source, filename=path)
    refs_pinned = _module_references_pinned_symbols(tree)
    findings = []

    if pinned_range is None:
        try:
            pinned_range = _pinned_block_line_range(source)
        except ValueError:
            pinned_range = (0, 0)
    pinned_begin, pinned_end = pinned_range

    if refs_pinned:
        findings.extend(_scan_mod_format(tree, source, relpath))
    findings.extend(_scan_comparisons(tree, source, relpath))
    findings.extend(_scan_bindings(tree, source, relpath))
    if refs_pinned:
        findings.extend(_scan_constant_assignments(
            tree, source, relpath, pinned_begin, pinned_end,
        ))

    findings.extend(_scan_string_literals(tree, source, relpath))
    return findings


def _is_allowlisted(finding):
    key = (finding.relpath, finding.segment)
    return key in _SPELLING_ALLOWLIST


def _unexpected_findings(findings):
    """Return findings that are not covered by the tier-1 allowlist.

    Each allowlist entry may set ``max_count`` (default 1). When more live sites
    share the same ``(relpath, segment)`` key than ``max_count``, the extras are
    unexpected — a second copy-and-paste regression must not hide behind one slot.
    """
    from collections import defaultdict

    by_key = defaultdict(list)
    unexpected = []
    for finding in findings:
        key = (finding.relpath, finding.segment)
        if key in _SPELLING_ALLOWLIST:
            by_key[key].append(finding)
        else:
            unexpected.append(finding)
    for key, grouped in by_key.items():
        max_count = _SPELLING_ALLOWLIST[key].get("max_count", 1)
        if len(grouped) > max_count:
            sorted_group = sorted(grouped, key=lambda f: (f.line, f.leg))
            unexpected.extend(sorted_group[max_count:])
    return unexpected


def run_tree_census():
    all_findings = []
    marker_modules = []
    paths_and_sources = []
    for path in _scanned_py_paths():
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        paths_and_sources.append((path, source))
        if _module_has_pinned_markers(source):
            marker_modules.append(_relpath(path))
    if len(marker_modules) > 1:
        for relpath in marker_modules:
            all_findings.append(Finding(
                relpath,
                1,
                "duplicate pinned declaration block markers",
                "constant-assignment",
            ))
    for path, source in paths_and_sources:
        all_findings.extend(census_module(path, source))
    return all_findings


def _format_findings(findings):
    return "\n".join(
        "  %s:%s [%s] %r — %s"
        % (f.relpath, f.line, f.leg, f.segment, f.leg)
        for f in sorted(findings, key=lambda f: (f.relpath, f.line, f.leg))
    )


def census_prose(doc_text=None):
    """Return prose-leg mismatch messages (empty when doc matches code)."""
    if doc_text is None:
        with open(_ROUND_DRIVER_MD, encoding="utf-8") as fh:
            doc_text = fh.read()

    errors = []
    m = _STATE_SCHEMA_PROSE_RE.search(doc_text)
    if not m:
        errors.append(
            "prose leg: round-driver.md missing (`STATE_SCHEMA_VERSION` = N) parenthetical"
        )
    else:
        doc_state = int(m.group(1))
        if doc_state != RD.STATE_SCHEMA_VERSION:
            errors.append(
                "prose leg: round-driver.md states STATE_SCHEMA_VERSION=%d but "
                "round_driver.STATE_SCHEMA_VERSION=%d"
                % (doc_state, RD.STATE_SCHEMA_VERSION)
            )

    m = _SCHEMA_VERSION_BULLET_RE.search(doc_text)
    if not m:
        errors.append(
            "prose leg: round-driver.md missing schemaVersion supported-version list"
        )
    else:
        doc_supported = {int(v) for v in re.findall(r"`(\d+)`", m.group(1))}
        if not doc_supported:
            errors.append(
                "prose leg: round-driver.md schemaVersion bullet has no backticked versions"
            )
            return errors
        code_supported = set(RD.SUPPORTED_STATE_VERSIONS)
        missing_from_doc = sorted(code_supported - doc_supported)
        missing_from_code = sorted(doc_supported - code_supported)
        if missing_from_doc:
            errors.append(
                "prose leg: code SUPPORTED_STATE_VERSIONS %r not stated in round-driver.md "
                "(missing %s)"
                % (RD.SUPPORTED_STATE_VERSIONS, ", ".join(str(v) for v in missing_from_doc))
            )
        if missing_from_code:
            errors.append(
                "prose leg: round-driver.md states receipt schemaVersion %s but code "
                "SUPPORTED_STATE_VERSIONS=%r"
                % (sorted(doc_supported), RD.SUPPORTED_STATE_VERSIONS)
            )
    return errors


def test_spelling_allowlist_reasons_are_non_empty():
    for key, entry in _SPELLING_ALLOWLIST.items():
        assert entry["reason"].strip(), "empty allowlist reason for %r" % (key,)


def test_spelling_allowlist_entries_match_live_sites():
    """Stale allowlist entries must fail loudly."""
    live = {(f.relpath, f.segment) for f in run_tree_census()}
    for key in _SPELLING_ALLOWLIST:
        assert key in live, "stale allowlist entry %r — no matching site in tree" % (key,)


def test_state_version_spelling_census():
    findings = run_tree_census()
    unexpected = _unexpected_findings(findings)
    assert not unexpected, (
        "hand-spelled state/receipt version sites:\n" + _format_findings(unexpected)
    )


def test_state_version_spelling_prose_census():
    errors = census_prose()
    assert not errors, "\n".join(errors)


def test_synthetic_injection_mod_format():
    path = os.path.join(_LIB, "round_driver.py")
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    injected = source.replace(
        "return RECEIPT_CERTIFIED_SCHEMA % _receipt_version(state)",
        "return RECEIPT_CERTIFIED_SCHEMA % 99",
        1,
    )
    findings = census_module(path, injected)
    hits = [f for f in findings if f.leg == "mod-format" and " % 99" in f.segment]
    assert hits, "expected mod-format leg on injected RECEIPT_CERTIFIED_SCHEMA % 99"


def test_synthetic_injection_mint_binding():
    path = os.path.join(_LIB, "round_driver.py")
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    injected = source.replace(
        '"schemaVersion": STATE_SCHEMA_VERSION,',
        '"schemaVersion": 99,',
        1,
    )
    findings = census_module(path, injected)
    hits = [f for f in findings if f.leg == "binding" and "99" in f.segment]
    assert hits, "expected binding leg on injected mint-site schemaVersion literal"


def test_synthetic_injection_string_literal():
    path = os.path.join(_LIB, "handback_gate.py")
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    injected = source + '\n_SYNTH = "receipt-certified/9"\n'
    findings = census_module(path, injected)
    hits = [f for f in findings if f.leg == "string-literal"]
    assert hits, "expected string-literal leg on injected receipt-certified/9"


def test_synthetic_injection_comparison():
    path = os.path.join(_LIB, "round_driver.py")
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    injected = source.replace(
        "if _state_version(loaded) != STATE_SCHEMA_VERSION:",
        "if _state_version(loaded) != 99:",
        1,
    )
    findings = census_module(path, injected)
    hits = [f for f in findings if f.leg == "comparison"]
    assert hits, "expected comparison leg on injected schemaVersion == 99"


def test_synthetic_injection_aliased_comparison():
    path = os.path.join(_LIB, "build_lane.py")
    source = (
        "def check(state):\n"
        "    version = state.get(\"schemaVersion\")\n"
        "    return version == 99\n"
    )
    findings = census_module(path, source)
    hits = [f for f in findings if f.leg == "comparison"]
    assert hits, (
        "expected comparison leg on aliased local (version = state.get then version == 99)"
    )


def test_synthetic_injection_constant_assignment_attribute():
    path = os.path.join(_LIB, "round_state_io.py")
    source = (
        "import round_driver\n"
        "def current_version():\n"
        "    return round_driver.STATE_SCHEMA_VERSION\n"
        "round_driver.STATE_SCHEMA_VERSION = 99\n"
    )
    findings = census_module(path, source)
    hits = [f for f in findings if f.leg == "constant-assignment"]
    assert hits, (
        "expected constant-assignment leg on round_driver.STATE_SCHEMA_VERSION = 99"
    )


def test_synthetic_injection_constant_assignment_other_module():
    path = os.path.join(_LIB, "round_state_io.py")
    source = (
        "import round_driver\n"
        "def current_version():\n"
        "    return round_driver.STATE_SCHEMA_VERSION\n"
        "STATE_SCHEMA_VERSION = 99\n"
    )
    findings = census_module(path, source)
    hits = [f for f in findings if f.leg == "constant-assignment"]
    assert hits, (
        "expected constant-assignment leg on pinned symbol assigned outside "
        "round_driver.py (falls open before census_module chokepoint fix)"
    )


def test_synthetic_injection_constant_assignment_outside_block():
    path = os.path.join(_LIB, "round_driver.py")
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    _begin, end = _pinned_block_line_range(source)
    lines = source.splitlines()
    lines.insert(end, "STATE_SCHEMA_VERSION = 99")
    injected = "\n".join(lines) + "\n"
    findings = census_module(path, injected)
    hits = [f for f in findings if f.leg == "constant-assignment"]
    assert hits, (
        "expected constant-assignment leg on pinned symbol assigned outside "
        "the marker-delimited block"
    )


def test_synthetic_injection_prose_doc_has_extra_version():
    with open(_ROUND_DRIVER_MD, encoding="utf-8") as fh:
        real = fh.read()
    injected = real.replace(
        "`2`, `3` or `4`",
        "`2`, `3`, `4` or `5`",
        1,
    )
    errors = census_prose(injected)
    assert any(
        "states receipt schemaVersion" in e for e in errors
    ), "expected prose leg error when doc lists a version absent from code"


def test_synthetic_injection_prose_doc_missing_code_version():
    with open(_ROUND_DRIVER_MD, encoding="utf-8") as fh:
        real = fh.read()
    injected = real.replace(
        "`2`, `3` or `4`",
        "`2` or `3`",
        1,
    )
    errors = census_prose(injected)
    assert any(
        "not stated in round-driver.md" in e for e in errors
    ), "expected prose leg error when code version is omitted from doc"


def test_synthetic_injection_get_default_binding():
    path = os.path.join(_LIB, "round_driver.py")
    source = (
        "import round_driver\n"
        "def _synth_get_default(state):\n"
        "    return state.get(\"schemaVersion\", 3)\n"
    )
    findings = census_module(path, source)
    hits = [f for f in findings if f.leg == "binding" and "schemaVersion=3" in f.segment]
    assert hits, "expected binding leg on injected state.get(\"schemaVersion\", 3)"


def test_synthetic_injection_setdefault_binding():
    path = os.path.join(_LIB, "round_state_io.py")
    source = (
        "def migrate(state):\n"
        "    state.setdefault(\"schemaVersion\", 4)\n"
    )
    findings = census_module(path, source)
    hits = [f for f in findings if f.leg == "binding" and "schemaVersion=4" in f.segment]
    assert hits, "expected binding leg on injected state.setdefault(\"schemaVersion\", 4)"


def test_synthetic_injection_ann_assign_constant():
    path = os.path.join(_LIB, "round_state_io.py")
    source = (
        "import round_driver\n"
        "def current_version():\n"
        "    return round_driver.STATE_SCHEMA_VERSION\n"
        "STATE_SCHEMA_VERSION: int = 99\n"
    )
    findings = census_module(path, source)
    hits = [f for f in findings if f.leg == "constant-assignment"]
    assert hits, (
        "expected constant-assignment leg on pinned symbol AnnAssign outside "
        "round_driver.py pinned block"
    )


def test_synthetic_injection_no_pinned_symbol_module():
    path = os.path.join(_LIB, "build_lane.py")
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    assert not _module_references_pinned_symbols(ast.parse(source)), (
        "build_lane.py must not reference a pinned symbol for this invariant test"
    )
    injected = source + (
        "\n"
        "def _synth_no_pinned_symbol_checks(state):\n"
        "    if state[\"schemaVersion\"] != 99:\n"
        "        return False\n"
        "    return {\"schemaVersion\": 99}\n"
    )
    findings = census_module(path, injected)
    comparison_hits = [f for f in findings if f.leg == "comparison"]
    binding_hits = [f for f in findings if f.leg == "binding"]
    assert comparison_hits, (
        "comparison leg must run on a module with no pinned-symbol reference"
    )
    assert binding_hits, (
        "binding leg must run on a module with no pinned-symbol reference"
    )


def test_synthetic_injection_embedded_string_literal():
    path = os.path.join(_LIB, "handback_gate.py")
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    embedded_literal = "prefix receipt-certified/9 suffix"
    assert embedded_literal != "receipt-certified/9", (
        "injected string must not be a whole-string match for receipt-certified/9"
    )
    injected = source + '\n_SYNTH = "%s"\n' % embedded_literal
    findings = census_module(path, injected)
    hits = [
        f for f in findings
        if f.leg == "string-literal" and "receipt-certified/9" in f.segment
    ]
    assert hits, (
        "string-literal leg must find an embedded `receipt-certified/<n>`, "
        "not only a whole-string match"
    )
