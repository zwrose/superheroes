import json
import os
import subprocess
import sys

LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def _run(tmp_root, doc, *extra):
    return subprocess.run(
        [sys.executable, os.path.join(LIB, "front_half_usable.py"),
         "--work-item", "wi", "--doc", doc, "--root", tmp_root, *extra],
        capture_output=True, text=True)


def _setup_doc(tmp_path, doc, body):
    d = tmp_path / "docs" / "superheroes" / "wi"
    d.mkdir(parents=True)
    (d / ("%s.md" % doc)).write_text(
        "---\ndocType: %s\ngates: {review: pending}\n---\n# T\n\n%s" % (doc, body))
    return d


_TASKS_BODY = "## Goal\ng\n## Architecture\na\n## Tech Stack\nt\n"


def test_no_marker_is_not_usable(tmp_path):
    _setup_doc(tmp_path, "tasks", _TASKS_BODY)
    assert json.loads(_run(str(tmp_path), "tasks").stdout)["usable"] is False


def test_write_marker_then_usable(tmp_path):
    _setup_doc(tmp_path, "tasks", _TASKS_BODY)
    assert json.loads(_run(str(tmp_path), "tasks", "--write-marker").stdout)["wrote"] is True
    assert json.loads(_run(str(tmp_path), "tasks").stdout)["usable"] is True


def test_stale_marker_after_body_change_is_not_usable(tmp_path):
    d = _setup_doc(tmp_path, "tasks", _TASKS_BODY)
    _run(str(tmp_path), "tasks", "--write-marker")
    (d / "tasks.md").write_text((d / "tasks.md").read_text() + "\nMORE BODY\n")
    assert json.loads(_run(str(tmp_path), "tasks").stdout)["usable"] is False


def test_frontmatter_change_keeps_marker_valid(tmp_path):
    # a set-gate-style frontmatter edit (gates/status/updated) must NOT invalidate the body-bound marker.
    d = _setup_doc(tmp_path, "tasks", _TASKS_BODY)
    _run(str(tmp_path), "tasks", "--write-marker")
    (d / "tasks.md").write_text((d / "tasks.md").read_text().replace("review: pending", "review: passed"))
    assert json.loads(_run(str(tmp_path), "tasks").stdout)["usable"] is True


def test_missing_doc_is_not_usable(tmp_path):
    assert json.loads(_run(str(tmp_path), "plan").stdout)["usable"] is False


# --emit-signals: boundary-compute mode. Verdict computed Python-side; no large text in payload.
def test_emit_signals_missing_doc_returns_small_not_usable(tmp_path):
    out = json.loads(_run(str(tmp_path), "plan", "--emit-signals").stdout)
    assert out["usable"] is False
    assert "recorded" in out
    assert "expected" in out
    assert "text" not in out, "--emit-signals must NOT return the large doc text"
    assert "sections" not in out, "--emit-signals must NOT return sections list"


def test_emit_signals_usable_draft_returns_small_usable(tmp_path):
    _setup_doc(tmp_path, "tasks", _TASKS_BODY)
    _run(str(tmp_path), "tasks", "--write-marker")
    out = json.loads(_run(str(tmp_path), "tasks", "--emit-signals").stdout)
    assert out["usable"] is True
    assert "text" not in out, "--emit-signals must NOT return the large doc text"
    assert "sections" not in out, "--emit-signals must NOT return sections list"
    assert out["recorded"] == out["expected"], "recorded must equal expected for a usable draft"


def test_emit_signals_stale_marker_returns_not_usable(tmp_path):
    d = _setup_doc(tmp_path, "tasks", _TASKS_BODY)
    _run(str(tmp_path), "tasks", "--write-marker")
    (d / "tasks.md").write_text((d / "tasks.md").read_text() + "\nMORE BODY\n")
    out = json.loads(_run(str(tmp_path), "tasks", "--emit-signals").stdout)
    assert out["usable"] is False
    assert "text" not in out, "--emit-signals must NOT return the large doc text"
