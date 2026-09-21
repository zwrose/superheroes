"""Order lint over a charter-shaped order: the shipped implementer template inlined verbatim (#1373)."""
import importlib.util
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_PLUGIN = os.path.abspath(os.path.join(_HERE, "..", ".."))
_SHIPPED_TEMPLATE = os.path.join(_PLUGIN, "agents", "implementer.md")
_SCRIPT = os.path.join(_LIB, "order_lint.py")

if _LIB not in sys.path:
    sys.path.insert(0, _LIB)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


OL = _load("order_lint")


def _shipped_body():
    """The shipped template minus its frontmatter, the way a builder inlines it (read, never copied)."""
    with open(_SHIPPED_TEMPLATE, encoding="utf-8") as fh:
        raw = fh.read()
    _, _frontmatter, body = raw.split("---\n", 2)
    return body


def _order(body, authored_target="src/app.py"):
    return (
        "# Work order WO-1\n\n"
        "Budget: at most 4 commands.\n\n"
        + body
        + "\n\n## Your work order\n\n"
        "Edit `%s` so `main()` returns 0.\n" % authored_target
    )


@pytest.fixture
def consumer_repo(tmp_path):
    # A consuming project's repo: none of the template's plugin-relative citations resolve here.
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    return str(root)


def _cli(order_text, repo, tmp_path):
    order = tmp_path / "order.md"
    order.write_text(order_text, encoding="utf-8")
    run = subprocess.run(
        [sys.executable, "-B", _SCRIPT, "check", "--order", str(order), "--repo-root", repo],
        capture_output=True, text=True, check=False,
    )
    return run.returncode, json.loads(run.stdout)


def test_shipped_template_carries_the_example_triggers():
    # axis: fixture precondition — without the mask, the verbatim template alone refuses
    body = _shipped_body()
    assert "{{NAME}}" in body
    assert "services/__tests__/items.test.ts" in body


def test_charter_shaped_order_passes_cli(consumer_repo, tmp_path):
    # axis: a verbatim template copy inside a filled order is not graded as authored text (E1)
    code, out = _cli(_order(_shipped_body()), consumer_repo, tmp_path)
    assert (code, out["ok"], out["findings"]) == (0, True, [])
    assert out["templateCopiesMasked"] == 1


def test_authored_placeholder_refuses_and_names_the_authored_line(consumer_repo, tmp_path):
    # axis: authored text around the template is still graded; the finding names the authored placeholder (E3)
    code, out = _cli(_order(_shipped_body(), authored_target="{{TARGET_FILE}}"), consumer_repo, tmp_path)
    assert code == 1
    assert out["findings"] == [{"token": OL.TOKEN_PLACEHOLDER_UNFILLED, "detail": "TARGET_FILE"}]
    assert out["templateCopiesMasked"] == 1


def test_placeholder_planted_in_an_altered_template_copy_refuses(consumer_repo):
    # axis: only a verbatim copy is masked — an altered copy is authored text, placeholders and all (E2)
    body = _shipped_body()
    altered = body.replace("exactly one", "exactly {{COUNT}}", 1)
    assert altered != body
    out = OL.check_text(_order(altered), consumer_repo)
    assert out["ok"] is False
    assert out["templateCopiesMasked"] == 0
    details = [f["detail"] for f in out["findings"] if f["token"] == OL.TOKEN_PLACEHOLDER_UNFILLED]
    assert "COUNT" in details and "NAME" in details


def test_unreadable_template_masks_nothing(consumer_repo, tmp_path, monkeypatch):
    # axis: when the shipped template cannot be read, nothing is masked — the order is graded whole (E4)
    monkeypatch.setattr(OL, "_TEMPLATE_PATH", str(tmp_path / "missing" / "implementer.md"))
    out = OL.check_text(_order(_shipped_body()), consumer_repo)
    assert out["ok"] is False
    assert out["templateCopiesMasked"] == 0
    assert {"token": OL.TOKEN_PLACEHOLDER_UNFILLED, "detail": "NAME"} in out["findings"]


# --- the fixer-emission door (round_driver._emit_orders_manifest) ---

RD = _load("round_driver")
_DIFF = ("diff --git a/src/f.py b/src/f.py\nindex 1111111..2222222 100644\n--- a/src/f.py\n"
         "+++ b/src/f.py\n@@ -1,2 +1,3 @@\n alpha\n+beta\n delta\n")
_FIXER_SKEY = "fixer-508e7896192355de"


def _emit_fixer_with(tmp_path, monkeypatch, order_text):
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir, exist_ok=True)
    monkeypatch.setattr(RD.engine_pref, "load_engine_prefs", lambda _root: {})
    monkeypatch.setattr(RD.engine_pref, "resolve_engine", lambda _role, _prefs: "claude")
    out = RD.cmd_next(session_dir, {"leg": "code", "vendors": ["claude", "codex"], "diff": _DIFF,
                                    "fixerVendor": "claude", "verifyCommand": "none"})
    assert out["ok"], out
    ok, state = RD.load_state(session_dir)
    assert ok, state
    state["headDiff"] = _DIFF
    state["fixBatch"] = []
    monkeypatch.setattr(RD.round_orders, "render_order", lambda _p, _s, _c: (order_text, None))
    return RD._emit_orders_manifest(
        session_dir, state, state["round"], RD.P_FIXER, 0, ["fixer"],
        journal_cmd="next", pending_payload={}, seat_map={})


def _fixer_order(body, tail="Fix the batch in place."):
    return "You are the fixer.\n\n" + body + "\n\n## Your fix batch\n\n" + tail + "\n"


def test_fixer_door_passes_charter_shaped_order(tmp_path, monkeypatch):
    # axis: the fixer-emission door masks the verbatim template exactly as the CLI does (E1)
    anchor = _emit_fixer_with(tmp_path, monkeypatch, _fixer_order(_shipped_body()))
    assert "manifestSha256" in anchor


def test_fixer_door_refuses_authored_placeholder(tmp_path, monkeypatch):
    # axis: the fixer-emission door still refuses an authored placeholder beside the template (E3)
    text = _fixer_order(_shipped_body(), tail="Fix " + "{{" + "TARGET_FILE" + "}}" + ".")
    with pytest.raises(
            ValueError,
            match=r"^order-render-refused:%s:order-lint:order-placeholder-unfilled:TARGET_FILE$"
            % _FIXER_SKEY):
        _emit_fixer_with(tmp_path, monkeypatch, text)
