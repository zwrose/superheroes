"""Census: each declaration placeholder has exactly one literal home in the library (#866).

`{namespace}` and `{sentinel}` were each spelled out in more than one module — `{namespace}` in
three (`pilot_contract`, `pilot_policy`, `pilot_cleanup`), `{sentinel}` in two (`pilot_policy`,
`pilot_cleanup`). Two review seats flagged the drift risk: the modules validate and substitute the
same token, so a change to the grammar in one home leaves the others silently accepting the old
spelling. The literal now lives once per token, at the module that owns that token's grammar, and
every other module reads the name from there. This census is what keeps that true — it fails on a
re-spelled literal anywhere in `lib/`, including a module that does not exist yet, and on a
re-spelling embedded inside a larger *code* literal (e.g. an argv string like
`"--namespace={namespace}"`) as well as a literal that equals the token outright.

It deliberately does NOT count a comment or a docstring that merely names the token while
explaining the grammar it consumes — prose describing what a module does with the placeholder is
not a second home for it, the same way a comment already isn't. Comments get that exemption for
free (they are not AST nodes at all); a docstring is an `ast.Constant` like any other string
literal, so the walk below excludes it explicitly.
"""
import ast
import os

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# token -> the module that owns its grammar and carries the single literal.
_PLACEHOLDER_HOMES = {
    "{namespace}": "pilot_contract.py",
    "{sentinel}": "pilot_policy.py",
    "{account}": "pilot_policy.py",
}


def _library_modules():
    return sorted(
        name for name in os.listdir(_LIB)
        if name.endswith(".py") and os.path.isfile(os.path.join(_LIB, name))
    )


def _docstring_constant_ids(tree):
    """Return the set of ``id()``s of every docstring `ast.Constant` node in ``tree``.

    A docstring is the first statement of a module/class/function body when that statement is a
    bare string-literal expression — `ast.get_docstring` is how the stdlib itself recognizes that
    shape. Its `ast.Constant` node is excluded from the census below: prose explaining what a
    module does with a placeholder is not a second home for it, the same way a comment already
    isn't (comments get that exemption for free, since they are not AST nodes at all).
    """
    ids = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if ast.get_docstring(node, clean=False) is None:
            continue
        ids.add(id(node.body[0].value))
    return ids


def _literal_sites(token):
    """Return [(module, lineno)] for every CODE string literal containing ``token`` in lib/*.py.

    Walks the AST rather than grepping so a token named in a *comment* never counts — a comment
    explaining the grammar is prose, not a second home — while a literal nested inside a
    collection, an f-string-free format string, or a call argument does count. Matches by
    containment, not equality: the production grammar puts placeholders INSIDE argv strings (e.g.
    a module could hard-code `"--namespace={namespace}"`), so a literal that merely embeds the
    token is as much a second home as one that equals it outright. A module/class/function
    docstring that merely names the token while documenting the grammar is excluded for the same
    reason a comment is — it is prose, not a literal the module actually uses.
    """
    sites = []
    for module in _library_modules():
        path = os.path.join(_LIB, module)
        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()
        tree = ast.parse(source, filename=path)
        docstring_ids = _docstring_constant_ids(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if id(node) in docstring_ids:
                continue
            if token not in node.value:
                continue
            sites.append((module, node.lineno))
    return sites


@pytest.mark.parametrize("token", sorted(_PLACEHOLDER_HOMES))
def test_placeholder_literal_has_exactly_one_home(token):
    # axis: a second spelling of the token anywhere in lib/ reddens, wherever it is added.
    sites = _literal_sites(token)
    assert len(sites) == 1, (
        "%s must have exactly one literal home in lib/; found %d: %s"
        % (token, len(sites), ", ".join("%s:%d" % site for site in sites))
    )


@pytest.mark.parametrize(("token", "home"), sorted(_PLACEHOLDER_HOMES.items()))
def test_placeholder_home_is_the_declared_owner(token, home):
    # axis: non-vacuity — the census found a real site, and it is the module named above. A
    # census that passed by finding zero sites would be proving nothing.
    sites = _literal_sites(token)
    assert sites, "%s: census found no literal at all in lib/" % token
    assert sites[0][0] == home, (
        "%s is homed in %s, expected %s" % (token, sites[0][0], home)
    )


def test_consumers_read_the_placeholders_from_their_home():
    # axis: the modules that no longer declare the literals still expose the same values, so
    # single-homing did not quietly change what a consumer sees.
    import pilot_cleanup
    import pilot_contract
    import pilot_policy

    assert pilot_policy.NAMESPACE_PLACEHOLDER is pilot_contract.NAMESPACE_PLACEHOLDER
    assert pilot_cleanup.NAMESPACE_PLACEHOLDER is pilot_contract.NAMESPACE_PLACEHOLDER
    assert pilot_cleanup.SENTINEL_PLACEHOLDER is pilot_policy.SENTINEL_PLACEHOLDER
    assert pilot_contract.NAMESPACE_PLACEHOLDER == "{namespace}"
    assert pilot_policy.SENTINEL_PLACEHOLDER == "{sentinel}"
    assert pilot_policy.ACCOUNT_PLACEHOLDER == "{account}"


def _placeholder_re_compile_sites():
    """Return [(module, lineno)] for every ``re.compile`` of the placeholder pattern in lib/."""
    pattern = r"\{[^{}]*\}"
    sites = []
    for module in _library_modules():
        path = os.path.join(_LIB, module)
        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()
        tree = ast.parse(source, filename=path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (
                isinstance(func, ast.Attribute)
                and func.attr == "compile"
                and isinstance(func.value, ast.Name)
                and func.value.id == "re"
            ):
                continue
            if not node.args:
                continue
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and arg.value == pattern:
                sites.append((module, node.lineno))
    return sites


def test_placeholder_regex_has_exactly_one_compile_home():
    # axis: exactly one ``re.compile`` of the placeholder pattern exists in lib/ (#830 WO-4).
    sites = _placeholder_re_compile_sites()
    assert len(sites) == 1, (
        "PLACEHOLDER_RE must be compiled exactly once in lib/; found %d: %s"
        % (len(sites), ", ".join("%s:%d" % site for site in sites))
    )
    assert sites[0][0] == "pilot_contract.py"
