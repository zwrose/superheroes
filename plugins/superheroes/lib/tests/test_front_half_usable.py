import json
import os
import subprocess
import sys

LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
if os.path.abspath(LIB) not in sys.path:
    sys.path.insert(0, os.path.abspath(LIB))


def _run(tmp_root, doc, *extra):
    return subprocess.run(
        [sys.executable, os.path.join(LIB, "front_half_usable.py"),
         "--work-item", "wi", "--doc", doc, "--root", tmp_root, *extra],
        capture_output=True, text=True)


def _setup_doc(tmp_path, doc, body):
    d = tmp_path / "docs" / "superheroes" / "wi"
    d.mkdir(parents=True)
    # spec.md anchors the mode-aware resolver in-repo (a live run always has an approved spec).
    (d / "spec.md").write_text("---\ndocType: spec\ngates: {review: passed}\n---\n# S\n")
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


# --- storage-mode awareness: the doc/marker paths must go through the resolver ---
# Regression for the 2026-07-02 live run: an out-of-repo (global) calibrated project keeps its
# definition-docs in the project store; the hard-wired docs/superheroes/<wi> path read nothing,
# reported every section missing, and parked the run after 3 produce attempts.

def _git(path):
    subprocess.run(["git", "init", "-q", str(path)], check=True)


def _setup_global_project(tmp_path, doc, body):
    """A project calibrated for out-of-repo docs: registry says global; the definition-docs
    (including the spec anchor) live in the project store, NOT under the repo root."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo)
    import mode_registry
    rec = mode_registry.write_registry(str(repo), mode_registry.GLOBAL, None)
    assert rec, "global-mode registry write must succeed"
    d = os.path.join(mode_registry.project_store_dir(str(repo)), "docs", "wi")
    os.makedirs(d)
    with open(os.path.join(d, "spec.md"), "w") as fh:
        fh.write("---\ndocType: spec\ngates: {review: passed}\n---\n# S\n")
    with open(os.path.join(d, "%s.md" % doc), "w") as fh:
        fh.write("---\ndocType: %s\ngates: {review: pending}\n---\n# T\n\n%s" % (doc, body))
    return repo, d


def test_global_mode_reads_doc_from_store(tmp_path):
    repo, _ = _setup_global_project(tmp_path, "tasks", _TASKS_BODY)
    out = json.loads(_run(str(repo), "tasks", "--emit-signals").stdout)
    assert out["usable"] is False  # no marker stamped yet
    assert out["missing_sections"] == [], (
        "the doc lives in the project store — a hard-wired in-repo path reads nothing and "
        "wrongly reports every section missing: %r" % (out,))


def test_global_mode_write_marker_stamps_in_store(tmp_path):
    repo, d = _setup_global_project(tmp_path, "tasks", _TASKS_BODY)
    assert json.loads(_run(str(repo), "tasks", "--write-marker").stdout)["wrote"] is True
    assert os.path.isfile(os.path.join(d, ".tasks.complete")), (
        "the completion marker must sit next to the doc in the project store")
    assert json.loads(_run(str(repo), "tasks").stdout)["usable"] is True
    assert json.loads(_run(str(repo), "tasks", "--emit-signals").stdout)["usable"] is True


def test_unknown_registry_schema_degrades_to_inrepo(tmp_path):
    """A newer registry schema is undeterminable: degrade to the pure in-repo default
    (gate_write._doc parity) rather than crash the completion check."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo)
    import mode_registry
    store = mode_registry.project_store_dir(str(repo))
    os.makedirs(store, exist_ok=True)
    with open(os.path.join(store, "registry.json"), "w") as fh:
        json.dump({"schemaVersion": 999, "storageMode": "global",
                   "remoteKey": None, "createdAt": "t"}, fh)
    d = _setup_doc(repo, "tasks", _TASKS_BODY)
    r = _run(str(repo), "tasks", "--write-marker")
    assert json.loads(r.stdout)["wrote"] is True, r.stderr
    assert (d / ".tasks.complete").exists()
    assert json.loads(_run(str(repo), "tasks").stdout)["usable"] is True
