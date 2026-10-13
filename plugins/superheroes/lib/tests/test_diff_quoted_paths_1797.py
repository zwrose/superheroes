"""#1797: the head-lane re-check reads canonical paths from git-quoted diff headers."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import round_driver as RD  # noqa: E402
import seat_map as SM  # noqa: E402

_AREA = {"name": "Payments", "covers": ["src/payments/*"], "why": "Charges customers.",
         "undo": "Hard: a charge needs a refund."}


def _diff(a, b=None):
    b = b or a.replace("a/", "b/", 1)
    return "diff --git %s %s\n--- %s\n+++ %s\n@@ -1 +1 @@\n-o\n+n\n" % (a, b, a, b)


def test_quoted_headers_decode_to_canonical_paths():
    assert RD._diff_changed_paths(_diff('"a/docs/\\303\\251.md"', '"b/docs/\\303\\251.md"')) == ["docs/é.md"]
    assert RD._diff_changed_paths(_diff('"a/t\\tab.md"', '"b/t\\tab.md"')) == ["t\tab.md"]
    assert RD._diff_changed_paths(_diff("a/plain.md", '"b/\\303\\251.md"')) == ["plain.md", "é.md"]
    assert RD._diff_changed_paths(_diff('"a/\\303\\251.md"', "b/plain.md")) == ["é.md", "plain.md"]
    assert RD._diff_changed_paths(_diff("a/x y.md", "b/x y.md")) == ["x y.md"]


def test_a_malformed_quoted_header_is_still_unreadable():
    assert RD._diff_changed_paths(_diff('"a/\\9zz.md"', '"b/\\9zz.md"')) is None
    assert RD._diff_changed_paths('diff --git "a/x b/x\n') is None


def _reduced(tmp_path, monkeypatch):
    import core_md
    import lane_call
    repo, store = str(tmp_path / "repo"), str(tmp_path / "store")
    os.makedirs(repo)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    core_md.write(repo, {"verifyCommand": "npm test", "stackTags": ["node"],
                         "threatModel": "single-user", "patterns": "- x: a.ts:1"},
                  "confirmed", root=store, now="2026-06-26")
    core_md.write_project_config_item(repo, core_md.RISK_AREAS_KEY, [_AREA], root=store)
    real = lane_call.call
    monkeypatch.setattr(lane_call, "call", lambda cwd, paths, proposed=None, root=None:
                        real(cwd, paths, proposed=proposed, root=store))
    return RD.new_state({"repoRoot": repo, "diff": _diff("a/docs/readme.md"),
                         "seatMap": {"roster": list(SM.BASE_ROSTER), "laneBasis": {"floor": None}}})


def test_a_non_ascii_filename_outside_every_risk_area_does_not_halt(tmp_path, monkeypatch):
    state = _reduced(tmp_path, monkeypatch)
    assert not state.get("terminal")
    diff = _diff('"a/docs/\\303\\251.md"', '"b/docs/\\303\\251.md"')
    assert RD._reevaluate_lane_dimensions(state, state["config"], diff) is False
    assert not state.get("terminal")


def test_a_non_ascii_filename_inside_a_risk_area_halts(tmp_path, monkeypatch):
    state = _reduced(tmp_path, monkeypatch)
    diff = _diff('"a/src/payments/\\303\\251.py"', '"b/src/payments/\\303\\251.py"')
    assert RD._reevaluate_lane_dimensions(state, state["config"], diff) is True
    assert state["terminal"] == "halted"
