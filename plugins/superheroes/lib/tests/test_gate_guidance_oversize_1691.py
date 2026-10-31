"""#1691: oversized owner guidance refuses loudly — a fixer order never carries guidance shorter than
what the owner wrote. The owner-gate submit paths are retired; the ruling path and the render backstop
that serve `rule` stay."""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from test_round_driver import RD


def test_t4_whitespace_padding_is_not_counted_on_the_ruling_path():
    """axis: one stripped measure on the ruling path"""
    padded = "  \n" + "x" * 2000 + "\n\t  "
    assert len(padded.encode("utf-8")) > 2000

    def validate(guidance):
        doc = {"_provenance": {"ruledBy": "owner", "ruledAt": "2026-08-26T00:00:00Z",
                               "records": ["rulings.json"]},
               "rulings": [{"id": "a.py::t@L1", "ruling": "guidance",
                            "reason": "r", "guidance": guidance}]}
        return RD._validate_ruling_entries(doc)

    parsed, _prov, err = validate(padded)
    assert err is None, err
    assert parsed[0]["guidance"] == "x" * 2000
    _parsed, _prov, err = validate("x" * 2001)
    assert err == RD.RULING_GUIDANCE_OVERSIZE


@pytest.mark.parametrize("ruling_channel", [False, True])
def test_t6_render_backstop_refuses_over_cap_entry(ruling_channel):
    """axis: render backstop on both channels"""
    entry = {"id": "d.py::big@L1", "title": "big", "file": "d.py", "line": 1,
             "guidance": "x" * 2001}
    if ruling_channel:
        entry["rulingChannel"] = True
    with pytest.raises(ValueError) as excinfo:
        RD._gate_guidance_block([entry])
    assert str(excinfo.value) == "order-render-refused:gate-guidance-oversize"


def test_t7_literals_pinned():
    """axis: external-contract literals pinned"""
    assert RD.GATE_GUIDANCE_OVERSIZE == "gate-guidance-oversize"
    assert RD.GATE_GUIDANCE_ROW_BYTE_CAP == 2000
    assert RD.GATE_GUIDANCE_AGGREGATE_OVERSIZE == "gate-guidance-aggregate-oversize"
    assert RD.GATE_GUIDANCE_AGGREGATE_BYTE_CAP == 8000


def test_t8_render_backstop_checks_entries_past_the_aggregate_cap():
    """axis: render backstop checks every entry, including those past the aggregate cap"""
    sizes = [2000, 2000, 2000, 2000, 2001]
    entries = [{"id": "e%d.py::t%d@L%d" % (i, i, i), "title": "t%d" % i, "file": "e%d.py" % i,
                "line": i, "guidance": "x" * size}
               for i, size in enumerate(sizes, start=1)]
    with pytest.raises(ValueError) as excinfo:
        RD._gate_guidance_block(entries)
    assert str(excinfo.value) == "order-render-refused:gate-guidance-oversize"


def test_t12_render_backstop_refuses_aggregate_overflow():
    """axis: render backstop — the render raises rather than omit when the aggregate overflows"""
    entries = [{"id": "e%d.py::t%d@L%d" % (i, i, i), "title": "t%d" % i, "file": "e%d.py" % i,
                "line": i, "guidance": "x" * 1900} for i in range(1, 6)]
    with pytest.raises(ValueError) as excinfo:
        RD._gate_guidance_block(entries)
    assert str(excinfo.value) == "order-render-refused:gate-guidance-aggregate-oversize"
