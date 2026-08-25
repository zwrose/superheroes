"""Drift guard for the safety-machinery route doctrine (#1154).

Bites on: the ruled carve-out text in its two prose homes — ``rubric/review-discipline.md``
§ *The safety-machinery route — the guard refuses the fixer* (doctrine home) and
``skills/review-code/reference/auto-fix-loop.md`` (copy-holder pointer). Losing the carve-out or
reintroducing the retired pre-authorization rule must go red.

**Residual blind spots:**

- the clause roster is **hand-maintained**;
- the pin grades the **doctrine text and the gate's wiring**, never whether any build actually
  obeyed the route;
- clause matching is substring-based, so a clause could be present inside prose that negates it;
- leg 6 pins **direct** imports of one file, not a transitive closure (the closure reaches 21
  modules and would churn), so a fall-open introduced two hops away is not covered.
"""
import ast
import json
import os
import re

import escalation as ESC

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, "..", ".."))

_HOME = "rubric/review-discipline.md"
_COPY_HOLDER = "skills/review-code/reference/auto-fix-loop.md"
_ROUTE_SECTION = "### The safety-machinery route — the guard refuses the fixer"

# Retired pre-authorization rule — absence in both homes (substring 3: copy-holder whole file only).
_RETIRED_BOTH_FILES = (
    "Owner authorization is required when the findings are blocking",
    "owner's word comes **before** the ordered round",
    "When authorization is unavailable, park",
)
_RETIRED_COPY_HOLDER_ONLY = (
    "the owner authorization a blocking finding needs first",
)

_CARVEOUT_CLAUSES = (
    "**Blocking findings go out on advisor or builder authority.**",
    "on the advisor's or the builder's own authority",
    "the owner's mandatory touchpoint is the merge click",
    "loud disclosure",
    "the work order says the round touches safety machinery and names the files",
    "**The one exception — the owner-authority-gate family.**",
    "still needs the owner's word first, per change",
    "**Classification fails closed.**",
    "A surface you cannot confidently classify is treated as gate family",
    "which means it needs the owner's word first — and parks when that word is unavailable",
    "because the guard refuses the fixer at every severity",
    "**When the owner's word is unavailable at the gate family, park.**",
    "Outside the gate family there is nothing to wait for",
    "**This is not the runtime self-modification floor.**",
    "do not overlap",
)

_POINTER_START = "**Where those findings go next.**"
_POINTER_CLAUSES = (
    "ordered implementer work orders on advisor or builder authority",
    "the owner's word required only for the owner-authority-gate family",
    "rubric/review-discipline.md",
    "do not retry the fixer, and never narrow the guard",
)

_FAMILY_MARKER = "**The one exception — the owner-authority-gate family.**"
_PINNED_FAMILY_ROSTER = frozenset({
    "hooks/owner_authority_gate.py",
    "lib/owner_authority.py",
    "reference/owner-authority-allowlist.md",
})
_HOOKS_JSON = "hooks/hooks.json"
_OWNER_AUTHORITY_GATE = "hooks/owner_authority_gate.py"
_OWNER_AUTHORITY = "lib/owner_authority.py"
_ALLOWLIST_REF = "reference/owner-authority-allowlist.md"

# Fixer routing target — template, golden fixture, and embedded prompt must move together.
_FIXER_ROUTING_TARGETS = (
    (
        "rubric/orders/dispatch-fixer.md",
        "report it for orchestrator escalation (see Payload contract) instead",
        "report it for owner escalation (see Payload contract) instead",
    ),
    (
        "lib/tests/fixtures/orders/golden/dispatch-fixer.txt",
        "report it for orchestrator escalation (see Payload contract) instead",
        "report it for owner escalation (see Payload contract) instead",
    ),
    (
        "skills/review-code/reference/auto-fix-loop.md",
        'report it under "escalated" for the orchestrator to route instead',
        'report it under "escalated" for the owner instead',
    ),
)


def _read(rel):
    path = os.path.join(PLUGIN, rel)
    if not os.path.isfile(path):
        raise AssertionError(f"surface file missing or unreadable: {rel}")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _collapse_whitespace(text):
    return re.sub(r"\s+", " ", text)


def _heading_level(line):
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None
    match = re.match(r"^(#+)\s", stripped)
    return len(match.group(1)) if match else None


def _section_span(lines, heading, label):
    indices = [i for i, line in enumerate(lines) if line.strip() == heading]
    if len(indices) != 1:
        raise AssertionError(
            f"{label}: expected exactly one {heading!r} line, found {len(indices)}"
        )
    start = indices[0]
    start_level = _heading_level(lines[start])
    end = len(lines)
    for i in range(start + 1, len(lines)):
        level = _heading_level(lines[i])
        if level is not None and level <= start_level:
            end = i
            break
    return start, end


def _route_section_text():
    text = _read(_HOME)
    lines = text.splitlines()
    start, end = _section_span(lines, _ROUTE_SECTION, _HOME)
    section = "\n".join(lines[start:end])
    assert section.strip(), (
        f"{_HOME}: extracted safety-machinery section is empty — "
        "section extractor would vacuously pass absence legs"
    )
    return section


def _pointer_paragraph_text():
    text = _read(_COPY_HOLDER)
    start = text.find(_POINTER_START)
    assert start != -1, (
        f"{_COPY_HOLDER}: pointer paragraph start {_POINTER_START!r} not found"
    )
    rest = text[start:]
    end = rest.find("\n\n")
    paragraph = rest if end == -1 else rest[:end]
    assert paragraph.strip(), f"{_COPY_HOLDER}: extracted pointer paragraph is empty"
    return paragraph


def test_retired_preauthorization_rule_is_absent():
    home_text = _collapse_whitespace(_read(_HOME))
    copy_text = _collapse_whitespace(_read(_COPY_HOLDER))
    for substring in _RETIRED_BOTH_FILES:
        if substring in home_text:
            raise AssertionError(
                f"{_HOME}: retired rule substring must be absent, found: {substring!r}"
            )
        if substring in copy_text:
            raise AssertionError(
                f"{_COPY_HOLDER}: retired rule substring must be absent, found: {substring!r}"
            )
    for substring in _RETIRED_COPY_HOLDER_ONLY:
        if substring in copy_text:
            raise AssertionError(
                f"{_COPY_HOLDER}: retired rule substring must be absent, found: {substring!r}"
            )


def test_carveout_clauses_present_in_doctrine_home():
    section = _collapse_whitespace(_route_section_text())
    for clause in _CARVEOUT_CLAUSES:
        assert clause in section, (
            f"{_HOME} (section {_ROUTE_SECTION}): missing carve-out clause: {clause!r}"
        )


def test_copyholder_pointer_states_the_new_shape():
    paragraph = _collapse_whitespace(_pointer_paragraph_text())
    for clause in _POINTER_CLAUSES:
        assert clause in paragraph, (
            f"{_COPY_HOLDER} (pointer paragraph): missing clause: {clause!r}"
        )


def _extract_doctrine_family_paths():
    text = _read(_HOME)
    marker_idx = text.find(_FAMILY_MARKER)
    assert marker_idx != -1, (
        f"{_HOME}: family marker {_FAMILY_MARKER!r} not found"
    )
    rest = text[marker_idx + len(_FAMILY_MARKER):]
    bullet_re = re.compile(r"^- `([^`]+)`")
    paths = set()
    for line in rest.splitlines():
        stripped = line.strip()
        if not stripped:
            if paths:
                break
            continue
        match = bullet_re.match(stripped)
        if match:
            paths.add(match.group(1))
            continue
        if paths:
            break
    return paths


def _direct_lib_local_imports(rel_py):
    text = _read(rel_py)
    try:
        tree = ast.parse(text, filename=rel_py)
    except SyntaxError as exc:
        raise AssertionError(
            f"{rel_py}: unparseable Python — {exc}"
        ) from exc
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split(".")[0]
                lib_path = os.path.join(PLUGIN, "lib", f"{module}.py")
                if os.path.isfile(lib_path):
                    found.add(module)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module is not None:
                module = node.module.split(".")[0]
                lib_path = os.path.join(PLUGIN, "lib", f"{module}.py")
                if os.path.isfile(lib_path):
                    found.add(module)
            elif node.level > 0:
                for alias in node.names:
                    module = alias.name
                    lib_path = os.path.join(PLUGIN, "lib", f"{module}.py")
                    if os.path.isfile(lib_path):
                        found.add(module)
    return found


def test_doctrine_family_list_matches_pinned_roster():
    extracted = _extract_doctrine_family_paths()
    assert extracted, (
        f"{_HOME}: doctrine family extractor yielded empty set — "
        "vacuous pass if compared to pinned roster"
    )
    assert extracted == _PINNED_FAMILY_ROSTER, (
        f"{_HOME}: doctrine family list {sorted(extracted)!r} "
        f"!= pinned roster {sorted(_PINNED_FAMILY_ROSTER)!r}"
    )
    for rel in sorted(_PINNED_FAMILY_ROSTER):
        path = os.path.join(PLUGIN, rel)
        assert os.path.isfile(path), (
            f"pinned family member does not resolve under plugin root: {rel!r}"
        )


def test_gate_wiring_edges_hold():
    hooks_text = _read(_HOOKS_JSON)
    try:
        hooks_data = json.loads(hooks_text)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"{_HOOKS_JSON}: unparseable JSON — {exc}"
        ) from exc
    pre_tool_use = hooks_data.get("hooks", {}).get("PreToolUse", [])
    registration_found = False
    for entry in pre_tool_use:
        for hook in entry.get("hooks", []):
            command = hook.get("command", "")
            if "hooks/owner_authority_gate.py" in command:
                registration_found = True
                break
        if registration_found:
            break
    assert registration_found, (
        f"{_HOOKS_JSON}: PreToolUse hook command must reference "
        "hooks/owner_authority_gate.py"
    )

    gate_text = _read(_OWNER_AUTHORITY_GATE)
    assert re.search(r"\bimport owner_authority\b", gate_text), (
        f"{_OWNER_AUTHORITY_GATE}: must import owner_authority (hook→classifier edge)"
    )

    classifier_text = _read(_OWNER_AUTHORITY)
    assert _ALLOWLIST_REF in classifier_text, (
        f"{_OWNER_AUTHORITY}: must cite {_ALLOWLIST_REF} "
        "(classifier→allowlist edge)"
    )


def test_classifier_direct_dependencies_are_classified():
    # mode_registry is a gate-critical dependency (its read decides calibration_state); it is now
    # in SAFETY_MACHINERY (WO-F #1154), so the fixer refuses it. It is deliberately not a
    # gate-family member — an ordered round touching it needs no owner pre-authorization.
    direct = _direct_lib_local_imports(_OWNER_AUTHORITY)
    expected = {"mode_registry"}
    assert direct == expected, (
        f"{_OWNER_AUTHORITY}: direct lib-local imports {sorted(direct)!r} "
        f"!= expected {sorted(expected)!r}"
    )


def test_every_family_member_is_refused_to_the_fixer():
    band_roots = [PLUGIN]
    for rel in sorted(_PINNED_FAMILY_ROSTER):
        abs_path = os.path.join(PLUGIN, rel)
        assert ESC.is_safety_machinery(abs_path, band_roots) is True, (
            f"family member {rel!r} must be refused to the fixer "
            f"(is_safety_machinery({abs_path!r}, {band_roots!r}))"
        )


def test_fixer_routing_target_is_pinned():
    for rel, present, absent in _FIXER_ROUTING_TARGETS:
        text = _read(rel)
        assert present in text, (
            f"{rel}: fixer routing target must include current wording: {present!r}"
        )
        assert absent not in text, (
            f"{rel}: retired fixer routing wording must be absent: {absent!r}"
        )


def test_gate_dependencies_are_fixer_refused():
    band_roots = [PLUGIN]
    for module in sorted(_direct_lib_local_imports(_OWNER_AUTHORITY)):
        abs_path = os.path.join(PLUGIN, "lib", f"{module}.py")
        assert ESC.is_safety_machinery(abs_path, band_roots) is True, (
            f"gate dependency {module!r} must be refused to the fixer "
            f"(is_safety_machinery({abs_path!r}, {band_roots!r}))"
        )
