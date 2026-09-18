"""Drift guard for the safety-machinery route doctrine (#1154, #1264).

Bites on: the ruled carve-out section in ``rubric/review-discipline.md`` § *The safety-machinery
route — the guard refuses the fixer* (doctrine home), and the fixer's escalation routing target
across three copies.

**Residual blind spots:**

- the pin grades the **doctrine structure**, never whether any build actually obeyed the route.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, "..", ".."))

_HOME = "rubric/review-discipline.md"
_ROUTE_SECTION = "### The safety-machinery route — the guard refuses the fixer"

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


def test_safety_machinery_route_section_exists():
    # axis: the doctrine home must carry exactly one non-empty safety-machinery route section.
    _route_section_text()


def test_fixer_routing_target_is_pinned():
    for rel, present, absent in _FIXER_ROUTING_TARGETS:
        text = _read(rel)
        assert present in text, (
            f"{rel}: fixer routing target must include current wording: {present!r}"
        )
        assert absent not in text, (
            f"{rel}: retired fixer routing wording must be absent: {absent!r}"
        )
