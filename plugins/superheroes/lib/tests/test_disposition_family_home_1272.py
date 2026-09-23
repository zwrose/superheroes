"""#1272 layer 2f: disposition-family one-home census — reader/writer chokepoints only."""
import ast
import os
import sys

import pytest

import session_contract

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

_DISPOSITION_FAMILY_MEMBERS = frozenset(session_contract.DISPOSITION_FAMILY_FIELDS)

_UNAMBIGUOUS_LITERALS = (
    "dispositionRound", "dispositionReceipt", "refutedReason",
    "outOfScopeReason", "mergedInto",
)

_EXCLUDED_FROM_POPULATION = frozenset({
    "guardian_ledger.py", "guardian_report.py", "package_read_audit.py",
})

# Layer 2e sanctioned followUp sites: key-presence tests plus normalized writes that carry a
# validated followUp forward. Any other followUp read in these modules is still a census violation.
_FOLLOW_UP_SANCTIONED_LINES = frozenset({
    ("review_gate_policy.py", 'if "followUp" in rule:'),
    ("review_gate_policy.py", 'normalized_rule["followUp"] = dict(follow_up)'),
    ("review_gate_policy.py", 'action["followUp"] = dict(rule["followUp"])'),
    ("round_driver.py", 'entry["followUp"] = dict(follow_up)'),
    ("round_driver.py", 'if "followUp" not in disp:'),
    ("round_driver.py", 'if "followUp" not in artifact:'),
})


def _sanctioned_follow_up_violation(violation):
    module, _lineno, source = violation.split(":", 2)
    return (module, source.strip()) in _FOLLOW_UP_SANCTIONED_LINES

_SESSION_CONTRACT_IMPORT_MARKERS = (
    "import session_contract",
    "from session_contract",
)


def _parent_map(tree):
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _comprehension_if_nodes(tree):
    nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            for gen in node.generators:
                nodes.update(gen.ifs)
    return nodes


def _is_none_constant(node):
    return isinstance(node, ast.Constant) and node.value is None


def _get_member_from_get_call(call):
    if not isinstance(call, ast.Call):
        return None
    if len(call.args) != 1 or call.keywords:
        return None
    func = call.func
    if not isinstance(func, ast.Attribute) or func.attr != "get":
        return None
    arg = call.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    return None


def _compare_tests_none_presence(compare):
    nodes = [compare.left] + compare.comparators
    if not any(_is_none_constant(n) for n in nodes):
        return False
    presence_ops = (ast.Is, ast.IsNot, ast.Eq, ast.NotEq)
    return any(isinstance(op, presence_ops) for op in compare.ops)


def _in_presence_context(node, parents, comprehension_ifs):
    if node in comprehension_ifs:
        return True
    parent = parents.get(node)
    if parent is None:
        return False
    if isinstance(parent, (ast.If, ast.While, ast.IfExp)):
        return parent.test is node
    if isinstance(parent, ast.BoolOp):
        return node in parent.values
    if isinstance(parent, ast.UnaryOp) and isinstance(parent.op, ast.Not):
        return parent.operand is node
    if isinstance(parent, ast.Compare):
        return _compare_tests_none_presence(parent)
    if isinstance(parent, ast.Call):
        func = parent.func
        if isinstance(func, ast.Name) and func.id == "bool":
            return parent.args and parent.args[0] is node
    return False


def _flag_disposition_family_presence_reads(source, filename="<fixture>"):
    tree = ast.parse(source, filename=filename)
    parents = _parent_map(tree)
    comprehension_ifs = _comprehension_if_nodes(tree)
    lines = source.splitlines()
    violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            member = _get_member_from_get_call(node)
            if member in _DISPOSITION_FAMILY_MEMBERS and _in_presence_context(
                    node, parents, comprehension_ifs):
                line = lines[node.lineno - 1].strip()
                violations.append("%s:%s: %s" % (filename, node.lineno, line))

        if isinstance(node, ast.Compare):
            if isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
                member = node.left.value
                if member in _DISPOSITION_FAMILY_MEMBERS:
                    if any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
                        line = lines[node.lineno - 1].strip()
                        violations.append("%s:%s: %s" % (filename, node.lineno, line))

        if isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if not isinstance(target, ast.Subscript):
                    continue
                sl = target.slice
                if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                    member = sl.value
                    if member in _DISPOSITION_FAMILY_MEMBERS:
                        line = lines[node.lineno - 1].strip()
                        violations.append("%s:%s: %s" % (filename, node.lineno, line))

    return violations


def _module_in_population(path, filename):
    if filename == "session_contract.py":
        return False
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    if any(marker in source for marker in _SESSION_CONTRACT_IMPORT_MARKERS):
        return True
    return any(literal in source for literal in _UNAMBIGUOUS_LITERALS)


def _derive_census_population():
    population = []
    for name in sorted(os.listdir(_LIB)):
        if not name.endswith(".py"):
            continue
        path = os.path.join(_LIB, name)
        if not os.path.isfile(path):
            continue
        if _module_in_population(path, name):
            population.append(name)
    return population


def _fixture_module(snippet):
    return "def _fixture():\n    %s\n    pass\n" % snippet


def test_disposition_family_census_matcher_flags_and_ignores():
    flags = [
        'if row.get("mergedInto") is not None: pass',
        'if not row.get("disposition"): pass',
        'if "followUp" in row: pass',
        'row["dispositionReceipt"] = x',
        'row["disposition"] = d',
        'if "mergedInto" not in row: pass',
        'x = [f for f in fs if f.get("disposition")]',
    ]
    for idx, snippet in enumerate(flags):
        found = _flag_disposition_family_presence_reads(
            _fixture_module(snippet), "flag-%s" % idx,
        )
        assert found, "expected flag for: %s" % snippet

    ignores = [
        'if entry.get("disposition") == "fixed": pass',
        'payload = {"disposition": d}',
        'for field in DISPOSITION_FAMILY_FIELDS: pass',
        'if session_contract.has_disposition_family(row): pass',
        'x = ("disposition" == y)',
        'kwargs = dict(base, followUp=f)',
    ]
    for idx, snippet in enumerate(ignores):
        found = _flag_disposition_family_presence_reads(
            _fixture_module(snippet), "ignore-%s" % idx,
        )
        assert not found, "expected ignore for: %s but got %s" % (snippet, found)


def test_disposition_family_single_home_census():
    """Census: disposition-family presence reads/writes go through session_contract only."""
    population = _derive_census_population()
    for excluded in _EXCLUDED_FROM_POPULATION:
        assert excluded not in population, (
            "ambiguous disposition domain dragged %s into population" % excluded
        )

    violations = []
    for name in population:
        path = os.path.join(_LIB, name)
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        try:
            flagged = _flag_disposition_family_presence_reads(source, name)
        except SyntaxError as exc:
            raise AssertionError("%s failed to parse: %s" % (name, exc)) from exc
        violations.extend(flagged)

    violations = [v for v in violations if not _sanctioned_follow_up_violation(v)]

    assert not violations, "disposition-family member presence outside session_contract:\n" + "\n".join(
        sorted(violations)
    )
