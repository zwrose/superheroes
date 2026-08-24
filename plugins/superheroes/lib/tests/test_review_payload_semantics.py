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
    kinds_result = set(EA.REVIEW_RESULT_KINDS)
    kinds_matchers = {kind for kind, _ in EA._REVIEW_CONTRACT_MATCHERS}
    kinds_parsers = set(EA._REVIEW_CONTRACT_PARSERS)
    kinds_semantics = set(EA._REVIEW_PAYLOAD_SEMANTICS)
    all_sets = (kinds_result, kinds_matchers, kinds_parsers, kinds_semantics)
    if len({frozenset(s) for s in all_sets}) != 1:
        symdiff = set()
        for left in all_sets:
            symdiff ^= left
        raise AssertionError(
            "review result kind registries differ; symmetric difference=%r" % sorted(symdiff))


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


def test_unregistered_kind_fails_closed_at_runtime():
    assert EA.review_payload_carried({}, "sentiment") == (False, None)
    assert EA.review_payload_carried(None, "sentiment") == (False, None)
    assert EA.review_payload_nonempty("sentiment", []) is False
    assert EA.review_payload_engaged({}, "sentiment") is False
    assert EA.review_payload_engaged(None, "sentiment") is False
