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


# --- Layer 2a: --emit-signals gap fields (missing_sections + placeholder) ---

def test_emit_signals_usable_doc_has_no_gaps(tmp_path):
    """Usable doc: missing_sections=[], placeholder=False."""
    _setup_doc(tmp_path, "tasks", _TASKS_BODY)
    _run(str(tmp_path), "tasks", "--write-marker")
    out = json.loads(_run(str(tmp_path), "tasks", "--emit-signals").stdout)
    assert out["usable"] is True
    assert out.get("missing_sections") == []
    assert out.get("placeholder") is False


def test_emit_signals_bold_label_doc_lists_missing_sections(tmp_path):
    """Old bold-label format: all required sections absent as headings -> in missing_sections."""
    bold_body = "**Goal:** g\n**Architecture:** a\n**Tech Stack:** t\n"
    _setup_doc(tmp_path, "tasks", bold_body)
    # no write-marker (signal mismatch) — emit-signals still returns gap fields even when not usable
    out = json.loads(_run(str(tmp_path), "tasks", "--emit-signals").stdout)
    assert out["usable"] is False
    for sec in ("Goal", "Architecture", "Tech Stack"):
        assert sec in out.get("missing_sections", []), (
            f"Expected '{sec}' in missing_sections, got {out.get('missing_sections')}"
        )
    assert out.get("placeholder") is False


def test_emit_signals_placeholder_detected(tmp_path):
    """Placeholder token in doc: placeholder=True in gap fields."""
    placeholder_body = (
        "## Goal\n\nImplement X. TBD\n\n"
        "## Architecture\n\na\n\n"
        "## Tech Stack\n\nt\n\n"
    )
    _setup_doc(tmp_path, "tasks", placeholder_body)
    out = json.loads(_run(str(tmp_path), "tasks", "--emit-signals").stdout)
    assert out.get("placeholder") is True


def test_emit_signals_missing_doc_has_gap_fields(tmp_path):
    """Missing doc: gap fields present (empty, but present) even on not-usable."""
    out = json.loads(_run(str(tmp_path), "tasks", "--emit-signals").stdout)
    assert out["usable"] is False
    assert "missing_sections" in out
    assert "placeholder" in out


def test_emit_signals_gap_fields_not_in_large_text(tmp_path):
    """--emit-signals must NOT include large doc text or sections list."""
    _setup_doc(tmp_path, "tasks", _TASKS_BODY)
    _run(str(tmp_path), "tasks", "--write-marker")
    out = json.loads(_run(str(tmp_path), "tasks", "--emit-signals").stdout)
    assert "text" not in out, "--emit-signals must NOT return the large doc text"
    assert "sections" not in out, "--emit-signals must NOT return sections list"
