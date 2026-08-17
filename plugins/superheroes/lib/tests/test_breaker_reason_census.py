"""Two-direction census: every consumer that switches on breaker `reason` names each member.

Direction 1 — every BREAKER_REASONS member is handled at every consumer that switches on reasons
(either via an explicit arm, a documented allow-list for deliberate subset handlers, or a final
else that parks). Direction 2 — a synthetic unregistered member is reported unhandled.
"""
import os
import re

import circuit_breaker as cb

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)

_REASON_CMP_RE = re.compile(r'\.get\("reason"\)\s*==\s*"([^"]+)"')
_REASON_CONST_RE = re.compile(
    r'\.get\("reason"\)\s*==\s*circuit_breaker\.ROUND_CEILING_REASON'
)

# Consumers that deliberately handle only a subset of breaker reasons. A new under-handling
# consumer must be registered here or the census fails loud.
_UNDER_HANDLING_ALLOWLIST = {
    ("round_driver.py", "_challenged_recurring_halt"): {
        "handles": frozenset({"challenged-principle-recurring"}),
        "reason": (
            "Acts only on challenged-principle-recurring; plain recurrence is the audit-breaker's job"
        ),
    },
    ("round_driver.py", "_settle_delta"): {
        "handles": frozenset({"max-iterations", "audit-stall", cb.ROUND_CEILING_REASON}),
        "reason": (
            "round-ceiling is claimed by _ceiling_halt before the reason switch; unlisted reasons "
            "park fail-closed via the final branch"
        ),
    },
}

# check_circuit_breaker reasons reachable at review_loop_plan.tally_round_decider; round-ceiling must
# be named explicitly in the haltKind switch (only check_round_ceiling emits it elsewhere).
_CIRCUIT_BREAKER_EMITTED = frozenset({
    "max-iterations", "no-net-progress", "challenged-principle-recurring", "recurring-finding",
})


def _lib_py_paths():
    return sorted(
        os.path.join(_LIB, name)
        for name in os.listdir(_LIB)
        if name.endswith(".py")
    )


def _scan_breaker_reason_literals(source):
    literals = set(_REASON_CMP_RE.findall(source))
    if _REASON_CONST_RE.search(source):
        literals.add(cb.ROUND_CEILING_REASON)
    return literals & cb.BREAKER_REASONS


def _enclosing_function(lines, line_index):
    for j in range(line_index, -1, -1):
        m = re.match(r"^def (\w+)", lines[j])
        if m:
            return m.group(1)
    return None


def _consumer_sites():
    """Map (filename, function) -> set of breaker reason literals compared in that function."""
    sites = {}
    for path in _lib_py_paths():
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
        source = "".join(lines)
        if not _REASON_CMP_RE.search(source) and not _REASON_CONST_RE.search(source):
            continue
        fname = os.path.basename(path)
        for i, line in enumerate(lines):
            matched = set(_REASON_CMP_RE.findall(line))
            if _REASON_CONST_RE.search(line):
                matched.add(cb.ROUND_CEILING_REASON)
            matched &= cb.BREAKER_REASONS
            if not matched:
                continue
            func = _enclosing_function(lines, i)
            sites.setdefault((fname, func), set()).update(matched)
    return sites


def _handled_reasons_for_consumer(filename, function, compared_literals):
    if (filename, function) in _UNDER_HANDLING_ALLOWLIST:
        return _UNDER_HANDLING_ALLOWLIST[(filename, function)]["handles"]
    if filename == "review_loop_plan.py":
        # Explicit arms plus the final else for check_circuit_breaker halts only; round-ceiling must
        # be explicit — it is not emitted by this decider's breaker call.
        else_handled = _CIRCUIT_BREAKER_EMITTED - compared_literals
        return compared_literals | else_handled
    return compared_literals


def compute_unhandled_reasons(reason_set):
    """Return BREAKER_REASONS members with no consumer arm in ``reason_set``."""
    handled = set()
    for (fname, func), literals in _consumer_sites().items():
        handled |= _handled_reasons_for_consumer(fname, func, literals)
    return reason_set - handled


def test_every_breaker_reason_is_handled_at_every_consumer():
    unhandled = compute_unhandled_reasons(cb.BREAKER_REASONS)
    assert unhandled == set(), "unhandled breaker reasons: %s" % sorted(unhandled)


def test_synthetic_reason_is_reported_unhandled():
    synthetic = cb.BREAKER_REASONS | {"synthetic-unregistered-reason"}
    unhandled = compute_unhandled_reasons(synthetic)
    assert "synthetic-unregistered-reason" in unhandled


def test_review_loop_plan_names_round_ceiling_and_parks():
    path = os.path.join(_LIB, "review_loop_plan.py")
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    assert cb.ROUND_CEILING_REASON in source or "ROUND_CEILING_REASON" in source
    assert 'halt_kind = "other"' in source
    ceiling_arm = (
        'brk.get("reason") == circuit_breaker.ROUND_CEILING_REASON'
    )
    assert ceiling_arm in source
    # The ceiling arm must sit before the final else and must not assign round-cap.
    idx = source.index(ceiling_arm)
    tail = source[idx:idx + 400]
    assert 'halt_kind = "round-cap"' not in tail
    assert 'halt_kind = "other"' in tail


def test_under_handling_allowlist_is_explicit():
    sites = _consumer_sites()
    for key, entry in _UNDER_HANDLING_ALLOWLIST.items():
        assert key in sites, "%s must appear in the consumer census" % (key,)
        assert entry["handles"], "%s allow-list must name handled reasons" % (key,)
        assert entry["reason"].strip(), "%s allow-list must state why" % (key,)
