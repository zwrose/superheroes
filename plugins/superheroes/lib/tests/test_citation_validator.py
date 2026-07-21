"""Conformance: the deterministic dangling-citation validator (#517 / #514 D3).

The provenance pincer's review-side deterministic leg. The-architect authors an inline
`[cite: <path> § <anchor>]` provenance marker on every load-bearing **mirror-fact**
(CONVENTIONS §3.2); this validator is review-spec's compile-step check that each such
citation **resolves** — the cited path exists, and (when given) the anchor text occurs in
that file. It fails closed: a dangling path, an absent anchor, or an unreadable spec all
yield a blocking finding, never a silent clean.

These tests use a REAL filesystem seam (CONVENTIONS §12.2 — no monkeypatching of
`os.path.isfile`/`open`): every case builds real temp dirs/files with `tmp_path` and drives
`citation_validator.check(...)` plus the `python3 lib/citation_validator.py check` CLI over
real argv. The §11 drift test reads the raw `templates/spec.md` and re-parses the canonical
example through the module's own `CITATION_RE`/`parse_citations`, so the template can never
silently drift from the parser (mirrors the fail-closed spirit of `test_dispatch_tables.py`).
"""
import importlib.util
import json
import os
import subprocess
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_MODULE_PATH = os.path.join(_REPO_ROOT, "plugins/superheroes/lib/citation_validator.py")
_TEMPLATE_PATH = os.path.join(_REPO_ROOT, "plugins/superheroes/templates/spec.md")

# The canonical example the shared contract pins (the §11 drift witness).
_CANON_PATH = "plugins/superheroes/lib/definition_doc.py"
_CANON_ANCHOR = "mint"


def _load(rel_path, mod_name):
    path = os.path.join(_REPO_ROOT, rel_path)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CV = _load("plugins/superheroes/lib/citation_validator.py", "citation_validator")


# --- helpers ---------------------------------------------------------------

def _spec(tmp_path, body):
    p = tmp_path / "spec.md"
    p.write_text(body, encoding="utf-8")
    return str(p)


def _touch(root, rel, content="x"):
    target = os.path.join(str(root), rel)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(content)
    return target


def _run_cli(spec_path, root):
    proc = subprocess.run(
        [sys.executable, _MODULE_PATH, "check", "--spec", str(spec_path), "--root", str(root)],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr  # findings array is the product, exit is always 0
    return json.loads(proc.stdout)


def _assert_schema_complete(f, require_line=True):
    """Every emitted finding is base-rubric-schema-complete. A per-citation finding
    carries a non-null line; the fail-closed (unreadable-spec) finding has no line to
    point at (line is null by design), so callers pass require_line=False for it."""
    assert f["severity"] == "Important"
    assert f["dimension"] == "Grounding"
    assert f["taxonomy"] == "dangling-citation"
    assert f["confidence"] == "High"
    assert f["file"] is not None
    assert f["evidence"] is not None
    assert f["id"] is not None
    if require_line:
        assert f["line"] is not None


# --- (a) path resolves → no finding ---------------------------------------

def test_resolving_path_no_finding(tmp_path):
    _touch(tmp_path, "lib/foo.py")
    spec = _spec(tmp_path, "The build reuses [cite: lib/foo.py] as its base.\n")
    assert CV.check(spec, str(tmp_path)) == []
    assert _run_cli(spec, tmp_path) == []


# --- (b) path + anchor both resolve → no finding --------------------------

def test_resolving_path_and_anchor_no_finding(tmp_path):
    _touch(tmp_path, "lib/foo.py", "def mint():\n    return 1\n")
    spec = _spec(tmp_path, "Reuses the existing [cite: lib/foo.py § mint] helper.\n")
    assert CV.check(spec, str(tmp_path)) == []
    assert _run_cli(spec, tmp_path) == []


# --- (c) dangling path → one finding at the right line --------------------

def test_dangling_path_one_finding_right_line(tmp_path):
    spec = _spec(tmp_path, "line one\nThe system extends [cite: lib/missing.py] today.\nline three\n")
    findings = CV.check(spec, str(tmp_path))
    assert len(findings) == 1
    f = findings[0]
    _assert_schema_complete(f)
    assert f["line"] == 2
    assert f["file"] == spec
    assert f["id"] == "citation-001"
    assert "lib/missing.py" in f["title"]
    # and identically through the CLI over real argv
    cli = _run_cli(spec, tmp_path)
    assert cli == findings


# --- (d) resolving path but absent anchor → one dangling-anchor finding ----

def test_resolving_path_absent_anchor_one_finding(tmp_path):
    _touch(tmp_path, "lib/foo.py", "def other():\n    pass\n")
    spec = _spec(tmp_path, "Reuses [cite: lib/foo.py § mint] which is gone.\n")
    findings = CV.check(spec, str(tmp_path))
    assert len(findings) == 1
    f = findings[0]
    _assert_schema_complete(f)
    assert f["line"] == 1
    assert "mint" in f["title"]
    assert "anchor" in f["title"].lower()
    assert _run_cli(spec, tmp_path) == findings


# --- (e) unreadable/missing spec → exactly one fail-closed finding ---------

def test_missing_spec_fails_closed_one_finding(tmp_path):
    missing = str(tmp_path / "nope.md")
    findings = CV.check(missing, str(tmp_path))
    assert len(findings) == 1  # never empty — fail closed
    f = findings[0]
    _assert_schema_complete(f, require_line=False)
    assert f["file"] == missing
    assert _run_cli(missing, tmp_path) == findings


def test_unreadable_spec_fails_closed(tmp_path):
    # A directory in place of the spec file is unreadable via open() → one fail-closed finding.
    d = tmp_path / "spec_dir.md"
    d.mkdir()
    findings = CV.check(str(d), str(tmp_path))
    assert len(findings) == 1
    _assert_schema_complete(findings[0], require_line=False)


# --- (f) no citations → [] -------------------------------------------------

def test_no_citations_returns_empty(tmp_path):
    spec = _spec(tmp_path, "# Spec\n\nA plain requirement with no provenance markers.\n")
    assert CV.check(spec, str(tmp_path)) == []
    assert _run_cli(spec, tmp_path) == []


# --- (g) multiple citations on multiple lines → line numbers + ids ---------

def test_multiple_dangling_citations_line_numbers_and_ids(tmp_path):
    spec = _spec(
        tmp_path,
        "intro\n"
        "first [cite: lib/a.py] fact\n"
        "middle prose\n"
        "second [cite: lib/b.py] fact\n"
        "third [cite: lib/c.py § sym] fact\n")
    findings = CV.check(spec, str(tmp_path))
    assert len(findings) == 3
    assert [f["line"] for f in findings] == [2, 4, 5]
    assert [f["id"] for f in findings] == ["citation-001", "citation-002", "citation-003"]
    for f in findings:
        _assert_schema_complete(f)
    assert _run_cli(spec, tmp_path) == findings


def test_mixed_resolving_and_dangling_only_reports_dangling(tmp_path):
    _touch(tmp_path, "lib/real.py", "def mint():\n    pass\n")
    spec = _spec(
        tmp_path,
        "ok [cite: lib/real.py § mint] here\n"
        "bad [cite: lib/ghost.py] there\n")
    findings = CV.check(spec, str(tmp_path))
    assert len(findings) == 1
    assert findings[0]["line"] == 2
    assert findings[0]["id"] == "citation-001"  # ids number the FINDINGS, not the citations


# --- parse_citations unit coverage (the single parse entrypoint) -----------

def test_parse_citations_path_only_and_with_anchor():
    text = "a [cite: lib/x.py] b\nc [cite: lib/y.py § foo bar] d\n"
    got = CV.parse_citations(text)
    assert got == [("lib/x.py", None, 1), ("lib/y.py", "foo bar", 2)]


# --- §11 drift test (fail-closed): the template's example never drifts ------

def test_template_canonical_example_matches_parser_and_resolves():
    """CONVENTIONS §11: the citation grammar's one authoritative machine home is this
    module's CITATION_RE. The template's canonical example is the drift WITNESS — parse the
    raw template with the module's own parser and assert the canonical
    `plugins/superheroes/lib/definition_doc.py § mint` example is present, is path+anchor,
    and resolves against the repo root. FAILS CLOSED: if the template's example is renamed,
    removed, or malformed, no match is found (or the wrong one) and this raises — so the
    template can never silently drift from the parser (cf. test_dispatch_tables.py).
    """
    with open(_TEMPLATE_PATH, encoding="utf-8") as fh:
        template_text = fh.read()

    citations = CV.parse_citations(template_text)
    # AT LEAST ONE example must be found — an empty parse is a silent-drift escape.
    assert citations, "templates/spec.md carries no [cite: …] example for the drift witness"

    canonical = [(p, a) for (p, a, _line) in citations
                 if p == _CANON_PATH and a == _CANON_ANCHOR]
    assert canonical == [(_CANON_PATH, _CANON_ANCHOR)], (
        "templates/spec.md must contain the canonical drift-witness example "
        "`[cite: %s § %s]` exactly (path+anchor); parsed citations were %r"
        % (_CANON_PATH, _CANON_ANCHOR, citations))

    # And the cited path resolves against the real repo root — the witness itself must not dangle.
    assert os.path.isfile(os.path.join(_REPO_ROOT, _CANON_PATH)), (
        "the canonical cited path %s does not resolve against the repo root" % _CANON_PATH)


def test_template_example_would_be_flagged_if_it_dangled(tmp_path):
    """Cross-check: run check() over the template body against an EMPTY root — the canonical
    example must then surface as a dangling-citation finding. This proves the witness is a
    live citation the validator actually parses, not inert prose the drift test reads by luck.
    """
    with open(_TEMPLATE_PATH, encoding="utf-8") as fh:
        template_text = fh.read()
    spec = _spec(tmp_path, template_text)  # empty root: no plugins/… files exist under tmp_path
    findings = CV.check(spec, str(tmp_path))
    assert any(_CANON_PATH in f["title"] for f in findings), (
        "the canonical template example was not parsed as a live citation")
