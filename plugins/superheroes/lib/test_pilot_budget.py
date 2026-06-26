"""Pure test-pilot budget decision helpers."""

import math


DEFAULT_LIMITS = {
    "planRecords": 20,
    "browserSteps": 80,
    "browserPasses": 4,
    "browserFixBatches": 3,
    "uniqueScenarios": 40,
    "seedOperations": 120,
    "elapsedSeconds": 3600,
    "renderedBytes": 200000,
}


def _within():
    return {"action": "within_budget"}


def _park(reason):
    return {"action": "park_budget_exceeded", "reason": reason}


def _valid_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def _validate_mapping(obj, label):
    if not isinstance(obj, dict):
        return "%s must be a JSON object" % label
    for key, value in obj.items():
        if not _valid_number(value):
            return "malformed numeric value for %s.%s" % (label, key)
    return None


def decide(counts, limits=None):
    """Return a budget decision for JSON-like operation counts.

    Missing known count dimensions are optional and normalize to zero. Present
    dimensions, custom limits, and unknown dimensions still must be numeric so a
    corrupted operation vector parks instead of silently continuing.
    """
    problem = _validate_mapping(counts, "counts")
    if problem:
        return _park(problem)

    merged_limits = dict(DEFAULT_LIMITS)
    if limits is not None:
        problem = _validate_mapping(limits, "limits")
        if problem:
            return _park(problem)
        merged_limits.update(limits)

    for key, limit in merged_limits.items():
        value = counts.get(key, 0)
        if value > limit:
            return _park("%s exceeded budget: %s > %s" % (key, value, limit))

    return _within()
