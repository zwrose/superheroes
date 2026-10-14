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


def test_a_path_with_a_space_before_b_slash_is_read_whole():
    # v0: the driver reads headers through sanitized_view's canonical reader; a hand-rolled splitter
    # read "src/space b/child.py" as two paths and missed a cover such as "src/space b/*".
    assert RD._diff_changed_paths(_diff("a/src/space b/child.py")) == ["src/space b/child.py"]


def test_the_driver_keeps_no_path_decoder_of_its_own():
    assert not hasattr(RD, "_git_unquote") and not hasattr(RD, "_DIFF_GIT_HEADER")


def test_a_quoted_non_ascii_path_and_an_unparseable_header_through_the_shared_reader():
    assert RD._diff_header_sides('diff --git "a/docs/\\303\\251.md" "b/docs/\\303\\251.md"') == (
        "docs/é.md", "docs/é.md")
    assert RD._diff_header_sides('diff --git "a/x\\9.md" "b/x\\9.md"') is None
    assert RD._diff_changed_paths(_diff('"a/x\\9.md"', '"b/x\\9.md"')) is None


# axis: the driver's header reader is the shared reader — a spy standing in for it is what answers.
def test_the_header_reader_is_delegated_to_the_shared_reader(monkeypatch):
    import sanitized_view
    seen = []

    def spy(raw):
        seen.append(raw)
        return ("sentinel-a", "sentinel-b")

    monkeypatch.setattr(sanitized_view, "sides_from_diff_git_line", spy)
    assert RD._diff_header_sides("diff --git a/x b/y") == ("sentinel-a", "sentinel-b")
    assert seen == [b"diff --git a/x b/y"]
