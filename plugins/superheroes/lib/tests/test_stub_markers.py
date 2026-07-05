# plugins/superheroes/lib/tests/test_stub_markers.py
import stub_markers

GOOD = "    x = 0  # STUB(#231): spend ceiling inert in live runs\n"
BAD_NOISSUE = "def _default_spend_sampler():  # STUB(): fake sampler\n"
BAD_BADREF = "y = 1  # STUB(TODO): not a real ref\n"


def test_bare_stub_word_without_parens_is_not_a_marker():
    # The convention marker is STUB(#NNN); a bare "stub"/"STUB:" in prose is not policed.
    assert stub_markers.find_markers("# this is just a stub for now\n") == []
    assert stub_markers.find_violations("# TODO: STUB: fake sampler\n") == []


def test_find_markers_wellformed():
    ms = stub_markers.find_markers(GOOD)
    assert ms == [{"issue": 231, "description": "spend ceiling inert in live runs", "line": 1}]


def test_find_markers_ignores_malformed():
    assert stub_markers.find_markers(BAD_NOISSUE) == []
    assert stub_markers.find_markers(BAD_BADREF) == []


def test_find_violations_flags_missing_issue():
    v = stub_markers.find_violations(BAD_NOISSUE)
    assert len(v) == 1 and "no issue reference" in v[0]["reason"]


def test_find_violations_flags_bad_ref():
    v = stub_markers.find_violations(BAD_BADREF)
    assert len(v) == 1 and "malformed" in v[0]["reason"]


def test_find_violations_passes_wellformed():
    assert stub_markers.find_violations(GOOD) == []


def test_js_comment_marker_is_found():
    assert stub_markers.find_markers("const f = () => 0  // STUB(#12): unwired\n") == [
        {"issue": 12, "description": "unwired", "line": 1}]


DIFF = """diff --git a/acceptance_launch.py b/acceptance_launch.py
index 111..222 100644
--- a/acceptance_launch.py
+++ b/acceptance_launch.py
@@ -1,3 +1,4 @@
 import os
+def _default_spend_sampler():  # STUB(#231): spend ceiling inert in live runs
+    return 0
 # unchanged line with STUB(#999): should NOT resurface (context, not added)
diff --git a/other.js b/other.js
--- a/other.js
+++ b/other.js
@@ -0,0 +1 @@
+const x = 1  // STUB(#232): ceiling-config wiring missing
"""


def test_markers_in_diff_added_lines_only():
    ms = stub_markers.markers_in_diff(DIFF)
    assert ms == [
        {"file": "acceptance_launch.py", "issue": 231,
         "description": "spend ceiling inert in live runs"},
        {"file": "other.js", "issue": 232, "description": "ceiling-config wiring missing"},
    ]


def test_markers_in_diff_ignores_context_lines():
    # the STUB(#999) on the unchanged (context) line must not appear
    assert all(m["issue"] != 999 for m in stub_markers.markers_in_diff(DIFF))


def test_markers_in_diff_empty_when_no_markers():
    assert stub_markers.markers_in_diff("diff --git a/x b/x\n+++ b/x\n+clean line\n") == []


# --- regressions: two markers on one line must both be seen (no greedy-tail swallow) ---

def test_two_markers_one_line_both_found():
    line = "x = 0  # STUB(#5): a real one; STUB(#6): another real one\n"
    ms = stub_markers.find_markers(line)
    assert [m["issue"] for m in ms] == [5, 6]
    assert ms[0]["description"] == "a real one;"
    assert ms[1]["description"] == "another real one"


def test_malformed_marker_after_valid_one_is_still_flagged():
    line = "x = 0  # STUB(#5): real; STUB(): missing issue\n"
    v = stub_markers.find_violations(line)
    assert len(v) == 1 and "no issue reference" in v[0]["reason"]


def test_two_markers_one_diff_line_both_surface():
    diff = "+++ b/f.py\n+x = 0  # STUB(#1): a  STUB(#2): b\n"
    ms = stub_markers.markers_in_diff(diff)
    assert [m["issue"] for m in ms] == [1, 2]


def test_issue_zero_is_not_a_valid_marker():
    assert stub_markers.find_markers("# STUB(#0): bogus\n") == []
    v = stub_markers.find_violations("# STUB(#0): bogus\n")
    assert len(v) == 1 and "malformed" in v[0]["reason"]
