import importlib.util
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_engine_adapter():
    spec = importlib.util.spec_from_file_location(
        "engine_adapter", os.path.join(_HERE, "..", "engine_adapter.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_engine_dispatch():
    spec = importlib.util.spec_from_file_location(
        "engine_dispatch", os.path.join(_HERE, "..", "engine_dispatch.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


EA = _load_engine_adapter()
ED = _load_engine_dispatch()


def test_every_registered_kind_has_payload_semantics():
    registries = {
        "REVIEW_RESULT_KINDS": set(EA.REVIEW_RESULT_KINDS),
        "matchers": {kind for kind, _ in EA._REVIEW_CONTRACT_MATCHERS},
        "parsers": set(EA._REVIEW_CONTRACT_PARSERS),
        "_REVIEW_PAYLOAD_SEMANTICS": set(EA._REVIEW_PAYLOAD_SEMANTICS),
        "REVIEW_PAYLOAD_SEMANTIC_KINDS": set(EA.REVIEW_PAYLOAD_SEMANTIC_KINDS),
    }
    union = set()
    for registry_set in registries.values():
        union |= registry_set
    if len({frozenset(s) for s in registries.values()}) != 1:
        parts = ["review result kind registries differ; union=%r" % sorted(union)]
        for name in sorted(registries):
            registry_set = registries[name]
            if registry_set != union:
                parts.append("%s missing=%r" % (name, sorted(union - registry_set)))
        raise AssertionError("; ".join(parts))


def test_every_semantics_record_declares_all_three_predicates():
    for kind, record in EA._REVIEW_PAYLOAD_SEMANTICS.items():
        assert record.key == kind
        assert callable(record.carries)
        assert callable(record.nonempty)
        assert callable(record.engaged)


def _parse_result_from_dispatch(result):
    out = {"ok": True, "resultKind": result["resultKind"]}
    for key in ("findings", "verdicts", "grouping", "ruling"):
        if key in result:
            out[key] = result[key]
    return out


_PARITY_FIXTURES = []

_PARITY_FIXTURES.extend([
    ("findings", {"resultKind": "findings", "findings": [{"id": "f1"}]},
     {"findings": [{"id": "f1"}]}),
    ("findings", {"resultKind": "findings", "findings": []},
     {"findings": []}),
    ("findings", {"resultKind": "findings", "findings": "oops"},
     {"findings": "oops"}),
    ("findings", {"resultKind": "findings"},
     {}),
])

_PARITY_FIXTURES.extend([
    ("verdicts", {"resultKind": "verdicts", "verdicts": [{"layer": "L1"}]},
     {"verdicts": [{"layer": "L1"}]}),
    ("verdicts", {"resultKind": "verdicts", "verdicts": []},
     {"verdicts": []}),
    ("verdicts", {"resultKind": "verdicts", "verdicts": "oops"},
     {"verdicts": "oops"}),
    ("verdicts", {"resultKind": "verdicts"},
     {}),
])

_PARITY_FIXTURES.extend([
    ("grouping", {"resultKind": "grouping", "grouping": ["item1"]},
     {"grouping": ["item1"]}),
    ("grouping", {"resultKind": "grouping", "grouping": []},
     {"grouping": []}),
    ("grouping", {"resultKind": "grouping", "grouping": None},
     {"grouping": None}),
    ("grouping", {"resultKind": "grouping", "grouping": "oops"},
     {"grouping": "oops"}),
    ("grouping", {"resultKind": "grouping"},
     {}),
])

_PARITY_FIXTURES.extend([
    ("ruling", {"resultKind": "ruling",
                "ruling": {"id": "a1", "ruling": "accept", "reason": "ok"}},
     {"ruling": {"id": "a1", "ruling": "accept", "reason": "ok"}}),
    ("ruling", {"resultKind": "ruling", "ruling": {}},
     {"ruling": {}}),
    ("ruling", {"resultKind": "ruling", "ruling": "oops"},
     {"ruling": "oops"}),
    ("ruling", {"resultKind": "ruling"},
     {}),
    ("ruling", {"resultKind": "ruling",
                "ruling": {"ruling": "accept", "reason": "ok"}},
     {"ruling": {"ruling": "accept", "reason": "ok"}}),
    ("ruling", {"resultKind": "ruling",
                "ruling": {"id": "a1", "reason": "ok"}},
     {"ruling": {"id": "a1", "reason": "ok"}}),
    ("ruling", {"resultKind": "ruling",
                "ruling": {"id": "a1", "ruling": "accept"}},
     {"ruling": {"id": "a1", "ruling": "accept"}}),
])


@pytest.mark.parametrize("kind,dispatch_result,engagement_input", _PARITY_FIXTURES)
def test_derived_sites_agree_with_the_registry(kind, dispatch_result, engagement_input):
    assert ED._review_result_payload(dispatch_result, kind) == (
        EA.review_payload_carried(dispatch_result, kind))

    carried, value = EA.review_payload_carried(dispatch_result, kind)
    if carried:
        parse_res = _parse_result_from_dispatch(dispatch_result)
        assert ED._parse_review_has_payload(parse_res) == EA.review_payload_nonempty(kind, value)

    assert (EA.engagement_read(engagement_input) == "engaged") == (
        EA.review_payload_engaged(engagement_input, kind))


_CARRIES_NOT_CARRIED_WRONG_TYPED = {
    "findings": "oops",
    "verdicts": "oops",
    "grouping": "oops",
    "ruling": "oops",
}
assert set(_CARRIES_NOT_CARRIED_WRONG_TYPED) == set(EA._REVIEW_PAYLOAD_SEMANTICS)


def _absent_payload_result(kind):
    return {"resultKind": kind}


def _wrong_typed_not_carried_result(kind):
    if kind == "grouping":
        # grouping carries any present key; only absence is not-carried.
        return {"resultKind": kind}
    return {"resultKind": kind, kind: _CARRIES_NOT_CARRIED_WRONG_TYPED[kind]}


@pytest.mark.parametrize("kind", EA._REVIEW_PAYLOAD_SEMANTICS)
def test_carries_returns_no_value_when_not_carried(kind):
    assert EA.review_payload_carried(_absent_payload_result(kind), kind) == (False, None)
    assert EA.review_payload_carried(_wrong_typed_not_carried_result(kind), kind) == (False, None)


def test_unregistered_kind_fails_closed_at_runtime():
    assert EA.review_payload_carried({}, "sentiment") == (False, None)
    assert EA.review_payload_carried(None, "sentiment") == (False, None)
    assert EA.review_payload_nonempty("sentiment", []) is False
    assert EA.review_payload_engaged({}, "sentiment") is False
    assert EA.review_payload_engaged(None, "sentiment") is False
