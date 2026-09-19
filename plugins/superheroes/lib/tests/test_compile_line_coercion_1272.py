"""#1272 WO-B — mechanical_compile coerces numeric-string line citations and records drops."""
import importlib.util
import os

import pytest

_TESTS = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_TESTS)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")

DIFF = (
    "diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
    "@@ -1 +1,2 @@\n-old\n+new\n+more\n"
)

DIFF_291 = (
    "diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
    "@@ -290,1 +290,2 @@\n context290\n+added291\n"
)

_FINDING = {
    "title": "bug",
    "severity": "Important",
    "file": "f.py",
}


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude"], "fixerVendor": "claude"}
    base.update(over)
    return base


def _state(diff=DIFF_291):
    state = RD.new_state(_cfg())
    state["reviewedDiff"] = diff
    return state


def test_t1_numeric_string_line_kept_as_int():
    finding = dict(_FINDING, line="291")
    compiled, drops = RD.mechanical_compile([finding], DIFF_291)
    assert len(compiled) == 1
    assert compiled[0]["line"] == 291
    assert isinstance(compiled[0]["line"], int)
    assert drops == []


def test_t2_whitespace_numeric_string_coerced():
    finding = dict(_FINDING, line=" 291 ")
    compiled, drops = RD.mechanical_compile([finding], DIFF_291)
    assert len(compiled) == 1
    assert compiled[0]["line"] == 291
    assert drops == []


def test_t3_coerced_line_out_of_scope_gets_scope_reason():
    finding = dict(_FINDING, line="291")
    compiled, drops = RD.mechanical_compile([finding], DIFF)
    assert compiled == []
    assert len(drops) == 1
    assert drops[0]["reason"] == "outside the round diff scope"
    assert drops[0]["line"] == 291


@pytest.mark.parametrize("bad_line", [
    "291a", "12-14", 29.1, [291],
    "²", "①", "１２",  # fullwidth １２ refused under ASCII rule
])
def test_t4_non_integer_lines_dropped_with_citation_reason(bad_line):
    finding = dict(_FINDING, line=bad_line)
    compiled, drops = RD.mechanical_compile([finding], DIFF_291)
    assert compiled == []
    assert len(drops) == 1
    assert drops[0]["reason"] == RD.COMPILE_DROP_LINE_NOT_INTEGER
    assert drops[0]["line"] == bad_line
    assert drops[0]["reason"] != "outside the round diff scope"


def test_t5_bool_line_refused():
    finding = dict(_FINDING, line=True)
    compiled, drops = RD.mechanical_compile([finding], DIFF_291)
    assert compiled == []
    assert len(drops) == 1
    assert drops[0]["reason"] == RD.COMPILE_DROP_LINE_NOT_INTEGER
    assert drops[0]["line"] is True


def test_t6_gapsweep_appends_compile_drops_without_overwriting_panel():
    state = _state()
    panel_drop = {
        "file": "f.py",
        "line": 999,
        "title": "panel drop",
        "reason": "outside the round diff scope",
    }
    RD._record_round(state, "compileDrops", [panel_drop])
    candidate = dict(_FINDING, line="x", title="gap candidate")
    RD._fold_gapsweep(state, state["config"], {"findings": [candidate]})
    drops = state["rounds"][str(state["round"])]["compileDrops"]
    assert len(drops) == 2
    assert drops[0] == panel_drop
    assert drops[1]["line"] == "x"
    assert drops[1]["reason"] == RD.COMPILE_DROP_LINE_NOT_INTEGER


def test_t7_scoped_fold_records_new_issue_compile_drops():
    state = _state()
    state["_newIssues"] = [
        dict(_FINDING, line="12-14", title="audit new issue"),
    ]
    RD._fold_scoped(state, state["config"], {"findings": []})
    drops = state["rounds"]["1"]["compileDrops"]
    assert len(drops) == 1
    assert drops[0]["line"] == "12-14"
    assert drops[0]["reason"] == RD.COMPILE_DROP_LINE_NOT_INTEGER
