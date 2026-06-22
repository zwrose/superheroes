"""Tests for the gate-write handshake helper (`gate_write`).

This is the unit coverage the gate machinery never had while it was inlined SKILL bash —
the exact behaviors the old manual harnesses proved: canonical-only writes, the parent-gate
precondition (downgrade passed→changes-requested), fail-closed when the frontmatter writer
errors, and the review-spec reset (revoke a stale `passed`→`pending`, never grant). Driven
through `main()` (the CLI the skills call), against a temp root. In the consolidated tree
gate_write imports `definition_doc` directly (same-tree sibling) — no the-architect symlink
fixture is needed; docs stay isolated in the temp root.
"""
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
WI = "add-thing-50c082"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GW = _load(os.path.join(_HERE, "..", "gate_write.py"), "gate_write")
DD = _load(os.path.join(_HERE, "..", "definition_doc.py"), "definition_doc_under_test")


def _docs_root(tmp_path):
    # Equivalence note: the old `with_architect` symlink fixture is gone — gate_write now
    # imports definition_doc in-tree, so there is no cross-plugin lib to symlink in. Only the
    # docs/superheroes/<wi>/ layout (owned by definition_doc) is created.
    root = tmp_path / "repo"
    os.makedirs(DD.work_item_dir(WI, str(root)))  # definition_doc owns the layout — derive, don't inline
    return str(root)


def _write(root, doc, *, where=None):
    """Author a real definition-doc (default pending gate) and return its path."""
    parent = None if doc == "spec" else WI  # plan→spec, tasks→plan (normalized by the lib)
    fm = DD.frontmatter(doc, WI, size="small", parent=parent,
                        created="2026-06-15", updated="2026-06-15")
    # Canonical path comes from the-architect (the layout owner); `where` (a dir) overrides for
    # the deliberately-noncanonical cases. No inline path literal — see test_canonical_path_*.
    path = os.path.join(where, doc + ".md") if where else DD.doc_path(WI, doc, root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(DD.render_frontmatter(fm) + "\n# " + doc + "\n")
    return path


def _gate(root, doc):
    return DD.read_gate(DD.doc_path(WI, doc, root))


def test_canonical_path_matches_the_architect(tmp_path):
    # arch-r3-001: gate_write._canonical re-encodes definition_doc's docs/superheroes/<wi>/<doc>.md
    # layout so the samefile guard runs without a subprocess. definition_doc's doc_path() OWNS that
    # layout; pin the two equal so a layout change there (e.g. a versioned subdir) can't silently
    # drift gate_write's guard — which would re-open the wrong-file hole the guard exists to close.
    root = str(tmp_path / "repo")
    os.makedirs(DD.work_item_dir(WI, root), exist_ok=True)
    with open(DD.doc_path(WI, "spec", root), "w") as fh:
        fh.write("x")
    for doc in ("spec", "plan", "tasks"):
        assert GW._canonical(root, WI, doc) == DD.doc_path(WI, doc, root)


def _run(capsys, *args):
    rc = GW.main(["gate_write.py", *args])
    return rc, capsys.readouterr().out.strip()


# --- certify (review-plan / review-tasks) ---------------------------------

def test_certify_records_passed_when_parent_approved(tmp_path, capsys):
    root = _docs_root(tmp_path)
    spec = _write(root, "spec"); DD.set_gate(spec, "passed")
    plan = _write(root, "plan")
    rc, out = _run(capsys, "--mode", "certify", "--doc", "plan", "--work-item", WI,
                   "--reviewed-path", plan, "--review", "passed", "--parent-doc", "spec", "--root", root)
    assert rc == 0 and out == "recorded:passed"
    assert _gate(root, "plan") == "passed"


def test_certify_downgrades_when_parent_not_approved(tmp_path, capsys):
    root = _docs_root(tmp_path)
    _write(root, "spec")  # parent spec left pending
    plan = _write(root, "plan")
    rc, out = _run(capsys, "--mode", "certify", "--doc", "plan", "--work-item", WI,
                   "--reviewed-path", plan, "--review", "passed", "--parent-doc", "spec", "--root", root)
    assert rc == 0 and out == "recorded:changes-requested"
    assert _gate(root, "plan") == "changes-requested"  # never passed with an unapproved parent


def test_certify_changes_requested_writes_through(tmp_path, capsys):
    root = _docs_root(tmp_path)
    with open(DD.doc_path(WI, "spec", root), "w") as fh:
        fh.write("x")
    _write(root, "plan")  # tasks parent (plan) irrelevant — review isn't 'passed'
    tasks = _write(root, "tasks")
    rc, out = _run(capsys, "--mode", "certify", "--doc", "tasks", "--work-item", WI,
                   "--reviewed-path", tasks, "--review", "changes-requested", "--parent-doc", "plan", "--root", root)
    assert rc == 0 and out == "recorded:changes-requested"
    assert _gate(root, "tasks") == "changes-requested"


def test_certify_noncanonical_skips_and_leaves_canonical_untouched(tmp_path, capsys):
    root = _docs_root(tmp_path)
    spec = _write(root, "spec"); DD.set_gate(spec, "passed")
    plan = _write(root, "plan"); DD.set_gate(plan, "changes-requested")  # marker on the canonical doc
    external = _write(root, "plan", where=str(tmp_path / "elsewhere" / WI))  # same WI, different file
    rc, out = _run(capsys, "--mode", "certify", "--doc", "plan", "--work-item", WI,
                   "--reviewed-path", external, "--review", "passed", "--parent-doc", "spec", "--root", root)
    assert rc == 3 and out == "skipped:noncanonical"  # certify produced a verdict but did NOT record it → non-zero
    assert _gate(root, "plan") == "changes-requested"  # the wrong-file hole: canonical doc untouched


def test_certify_downgrades_when_parent_gate_unreadable(tmp_path, capsys):
    # A malformed parent spec → read-gate errors → parent resolves to 'unreadable' (not 'passed')
    # → certify must downgrade to changes-requested, never stamp passed on an unverifiable parent.
    root = _docs_root(tmp_path)
    canon_spec = os.path.join(root, "docs", "superheroes", WI, "spec.md")
    with open(canon_spec, "w", encoding="utf-8") as fh:
        fh.write("# malformed spec — no frontmatter\n")
    plan = _write(root, "plan")
    rc, out = _run(capsys, "--mode", "certify", "--doc", "plan", "--work-item", WI,
                   "--reviewed-path", plan, "--review", "passed", "--parent-doc", "spec", "--root", root)
    assert rc == 0 and out == "recorded:changes-requested"
    assert _gate(root, "plan") == "changes-requested"


def test_certify_set_gate_failure_reports(tmp_path, capsys):
    root = _docs_root(tmp_path)
    with open(DD.doc_path(WI, "spec", root), "w") as fh:
        fh.write("x")
    canon = os.path.join(root, "docs", "superheroes", WI, "plan.md")
    with open(canon, "w", encoding="utf-8") as fh:
        fh.write("# malformed — no frontmatter\n")  # passes the -ef guard, fails set-gate
    rc, out = _run(capsys, "--mode", "certify", "--doc", "plan", "--work-item", WI,
                   "--reviewed-path", canon, "--review", "changes-requested", "--parent-doc", "plan", "--root", root)
    assert rc == 3 and out == "failed:set-gate"  # certify could not record the verdict → non-zero


# Equivalence note: the old `test_certify_lib_absent_fails_closed` / `test_reset_lib_absent_fails_closed`
# tested a state (the-architect's cross-plugin lib unresolvable -> `skipped:lib-absent` / exit 3)
# that can no longer occur in one tree — definition_doc is a same-tree sibling, never absent. They
# are deleted. The wrapping try/except IS still reachable (a definition_doc CALL raising); the
# replacement test below covers that preserved fail-closed branch (the self-certify-hole floor:
# the gate is NOT advanced to `passed`, the outcome is `failed:set-gate`, exit 3).

def test_certify_set_gate_raises_fails_closed(tmp_path, capsys, monkeypatch):
    # GATE-INTEGRITY (the self-certify hole), via the direct seam: if definition_doc.set_gate
    # RAISES, certify produces a verdict it cannot record. It must NOT advance the gate to
    # 'passed' (a green gate with no real review) and must exit NON-ZERO (failed:set-gate) so
    # the failure isn't silently swallowed. The gate stays at its prior 'pending'.
    root = _docs_root(tmp_path)
    spec = _write(root, "spec"); DD.set_gate(spec, "passed")
    plan = _write(root, "plan")  # canonical, pending
    monkeypatch.setattr(GW.definition_doc, "set_gate",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("induced write failure")))
    rc, out = _run(capsys, "--mode", "certify", "--doc", "plan", "--work-item", WI,
                   "--reviewed-path", plan, "--review", "passed", "--parent-doc", "spec", "--root", root)
    assert rc == 3 and out == "failed:set-gate"
    assert _gate(root, "plan") == "pending"  # NOT advanced to passed — the floor holds


# --- reset (review-spec stale approval) -----------------------------------

def test_reset_revokes_stale_approval(tmp_path, capsys):
    root = _docs_root(tmp_path)
    spec = _write(root, "spec"); DD.set_gate(spec, "passed")
    rc, out = _run(capsys, "--mode", "reset", "--doc", "spec", "--work-item", WI,
                   "--reviewed-path", spec, "--root", root)
    assert rc == 0 and out == "reset:pending"
    assert _gate(root, "spec") == "pending"  # stale approval revoked; never re-granted


def test_reset_noop_when_not_approved(tmp_path, capsys):
    root = _docs_root(tmp_path)
    spec = _write(root, "spec")  # pending
    rc, out = _run(capsys, "--mode", "reset", "--doc", "spec", "--work-item", WI,
                   "--reviewed-path", spec, "--root", root)
    assert rc == 0 and out == "noop:not-approved"
    assert _gate(root, "spec") == "pending"


def test_reset_noncanonical_skips_and_leaves_canonical(tmp_path, capsys):
    root = _docs_root(tmp_path)
    spec = _write(root, "spec"); DD.set_gate(spec, "passed")
    external = _write(root, "spec", where=str(tmp_path / "elsewhere" / WI))
    rc, out = _run(capsys, "--mode", "reset", "--doc", "spec", "--work-item", WI,
                   "--reviewed-path", external, "--root", root)
    assert rc == 0 and out == "skipped:noncanonical"
    assert _gate(root, "spec") == "passed"  # canonical approval untouched


def test_reset_skipped_when_gate_unreadable(tmp_path, capsys):
    # A malformed (was-approved) spec → read-gate errors → reset must surface skipped:unreadable
    # (warn the owner the approval may be stale), not silently no-op.
    root = _docs_root(tmp_path)
    canon = os.path.join(root, "docs", "superheroes", WI, "spec.md")
    with open(canon, "w", encoding="utf-8") as fh:
        fh.write("# malformed — no frontmatter\n")
    rc, out = _run(capsys, "--mode", "reset", "--doc", "spec", "--work-item", WI,
                   "--reviewed-path", canon, "--root", root)
    assert rc == 0 and out == "skipped:unreadable"


# Equivalence note: `test_reset_lib_absent_fails_closed` (the reset control for the deleted
# certify lib-absent test) is removed for the same reason — no cross-plugin lib to be absent in
# one tree. reset mode's preserved fail-closed branch (set-gate fails -> stale 'passed' remains,
# token failed:set-gate) is covered by test_reset_set_gate_failure_reports below.

def test_reset_set_gate_failure_reports(tmp_path, capsys, monkeypatch):
    # The reset twin of test_certify_set_gate_failure_reports. read-gate must SUCCEED and return
    # 'passed' first (so a malformed file can't induce it the way certify's test does) — force
    # _set_gate to fail after a clean read. The stale 'passed' must remain on disk (the hazard the
    # helper warns the owner about), and the outcome token must be failed:set-gate.
    root = _docs_root(tmp_path)
    spec = _write(root, "spec"); DD.set_gate(spec, "passed")
    monkeypatch.setattr(GW, "_set_gate", lambda *a, **k: (False, "induced write failure"))
    rc, out = _run(capsys, "--mode", "reset", "--doc", "spec", "--work-item", WI,
                   "--reviewed-path", spec, "--root", root)
    assert rc == 0 and out == "failed:set-gate"
    assert _gate(root, "spec") == "passed"  # stale approval still on disk — the warned-about state


def test_certify_requires_review(tmp_path, capsys):
    root = _docs_root(tmp_path)
    plan = _write(root, "plan")
    rc, out = _run(capsys, "--mode", "certify", "--doc", "plan", "--work-item", WI,
                   "--reviewed-path", plan, "--parent-doc", "spec", "--root", root)
    assert rc == 2 and out == "error:bad-args"


# --- mode-aware resolver tests (Task 7) -----------------------------------

def test_canonical_resolves_mode_aware(tmp_path):
    import gate_write, definition_doc
    wi = "wi-abc123"
    # spec present in-repo → spec-anchored resolution equals the in-repo doc_path
    d = os.path.join(str(tmp_path), "docs", "superheroes", wi)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "spec.md"), "w").write("x")
    assert gate_write._canonical(str(tmp_path), wi, "plan") == \
        definition_doc.doc_path(wi, "plan", str(tmp_path))


def test_set_gate_targets_resolved_path(tmp_path, monkeypatch):
    # When resolution points at the global store, the gate is written THERE, not in-repo.
    import gate_write, definition_doc
    wi = "wi-def456"
    store_dir = os.path.join(str(tmp_path), "store", "docs", wi)
    os.makedirs(store_dir, exist_ok=True)
    monkeypatch.setattr(definition_doc, "resolve_work_item_dir",
                        lambda work_item, *, root, cwd: store_dir)
    captured = {}
    monkeypatch.setattr(definition_doc, "set_gate",
                        lambda path, review: captured.update(path=path))
    gate_write._set_gate("plan", wi, "passed", str(tmp_path))
    assert captured["path"] == os.path.join(store_dir, "plan.md")


def test_doc_falls_back_to_in_repo_on_unknown_schema(tmp_path, monkeypatch):
    # gate_write._doc degrades (not crashes) when the mode is undeterminable: a newer
    # registry schema (UnknownSchemaVersion) falls back to the pure in-repo doc_path.
    import gate_write, definition_doc, mode_registry

    def boom(work_item, *, root, cwd):
        raise mode_registry.UnknownSchemaVersion("newer")

    monkeypatch.setattr(definition_doc, "resolve_work_item_dir", boom)
    wi = "wi-fallback"
    assert gate_write._doc(wi, "plan", str(tmp_path)) == \
        definition_doc.doc_path(wi, "plan", str(tmp_path))
