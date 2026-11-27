"""Raw HTML examples must not redirect cleanup to another cloud builder."""
import pytest

from test_cloud_cleanup import (
    CC, PARENT, REPO, _T1, _as_layer, _lane, _stack, w,
)


@pytest.mark.parametrize("opening,closing", [
    pytest.param("<![CDATA[", "]]>", id="cdata"),
    pytest.param("<?example", "?>", id="processing-instruction"),
    pytest.param("<!DOCTYPE example", ">", id="declaration"),
])
def test_raw_html_across_blank_lines_cannot_select_an_unrelated_builder(w, opening, closing):
    # axis: non-prose closing examples must not redirect a stack layer's archive target to another active lane.
    _stack(w)
    _lane(w, "l-other", 999, session="session-z", ts=_T1)
    w.gh.pulls[501]["body"] += "\n\n" + opening + "\n\nFixes #999\n\n" + closing + "\n"
    # The layer is a stack layer: only the description's first line nominates issues, GitHub's timeline confirms,
    # and it records a cross-reference from this layer for the unrelated issue 999 too (a trap the first line never reaches).
    _as_layer(w, 501, 201, extra=(999,))

    planned = CC.plan(w.repo, REPO, 501, env=w.env, run=w.gh)

    assert planned["ok"], planned
    assert (planned["issue"], planned["launchId"], planned["session"]) == (
        PARENT, "l-1", "session-a",
    ), planned
    assert planned.get("viaParent") is True, planned
    assert planned["linkSource"] == "timeline", planned
