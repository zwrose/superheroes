"""Tests for review-crew's gate-write handshake helper (`gate_write`).

This is the unit coverage the gate machinery never had while it was inlined SKILL bash —
the exact behaviors the old manual harnesses proved: canonical-only writes, the parent-gate
precondition (downgrade passed→changes-requested), fail-closed when the-architect lib is
absent, and the review-spec reset (revoke a stale `passed`→`pending`, never grant). Driven
through `main()` (the CLI the skills call), against a temp root with the-architect symlinked
in so the in-repo resolver finds the real lib while docs stay isolated.
"""
import importlib.util
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
_REAL_ARCHITECT = os.path.join(_REPO_ROOT, "plugins", "the-architect")
WI = "add-thing-50c082"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GW = _load(os.path.join(_HERE, "..", "gate_write.py"), "gate_write")
DD = _load(os.path.join(_REAL_ARCHITECT, "lib", "definition_doc.py"), "architect_definition_doc")


def _docs_root(tmp_path, with_architect=True):
    root = tmp_path / "repo"
    (root / "docs" / "superheroes" / WI).mkdir(parents=True)
    if with_architect:
        (root / "plugins").mkdir(parents=True)
        os.symlink(_REAL_ARCHITECT, str(root / "plugins" / "the-architect"))
    return str(root)


def _write(root, doc, *, where=None):
    """Author a real definition-doc (default pending gate) and return its path."""
    parent = None if doc == "spec" else WI  # plan→spec, tasks→plan (normalized by the lib)
    fm = DD.frontmatter(doc, WI, size="small", parent=parent,
                        created="2026-06-15", updated="2026-06-15")
    path = os.path.join(where or os.path.join(root, "docs", "superheroes", WI), doc + ".md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(DD.render_frontmatter(fm) + "\n# " + doc + "\n")
    return path


def _gate(root, doc):
    return DD.read_gate(os.path.join(root, "docs", "superheroes", WI, doc + ".md"))


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
    assert rc == 0 and out == "skipped:noncanonical"
    assert _gate(root, "plan") == "changes-requested"  # the wrong-file hole: canonical doc untouched


def test_certify_set_gate_failure_reports(tmp_path, capsys):
    root = _docs_root(tmp_path)
    canon = os.path.join(root, "docs", "superheroes", WI, "plan.md")
    with open(canon, "w", encoding="utf-8") as fh:
        fh.write("# malformed — no frontmatter\n")  # passes the -ef guard, fails set-gate
    rc, out = _run(capsys, "--mode", "certify", "--doc", "plan", "--work-item", WI,
                   "--reviewed-path", canon, "--review", "changes-requested", "--parent-doc", "plan", "--root", root)
    assert rc == 0 and out == "failed:set-gate"


def test_certify_lib_absent_fails_closed(tmp_path, capsys):
    root = _docs_root(tmp_path, with_architect=False)  # no the-architect resolvable
    plan = _write(root, "plan")
    rc, out = _run(capsys, "--mode", "certify", "--doc", "plan", "--work-item", WI,
                   "--reviewed-path", plan, "--review", "passed", "--parent-doc", "spec", "--root", root)
    assert rc == 0 and out == "skipped:lib-absent"
    assert _gate(root, "plan") == "pending"  # nothing recorded


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


def test_reset_lib_absent_fails_closed(tmp_path, capsys):
    root = _docs_root(tmp_path, with_architect=False)
    spec = _write(root, "spec"); DD.set_gate(spec, "passed")
    rc, out = _run(capsys, "--mode", "reset", "--doc", "spec", "--work-item", WI,
                   "--reviewed-path", spec, "--root", root)
    assert rc == 0 and out == "skipped:lib-absent"
    assert _gate(root, "spec") == "passed"  # could not reset; warned (stderr)


def test_certify_requires_review(tmp_path, capsys):
    root = _docs_root(tmp_path)
    plan = _write(root, "plan")
    rc, out = _run(capsys, "--mode", "certify", "--doc", "plan", "--work-item", WI,
                   "--reviewed-path", plan, "--parent-doc", "spec", "--root", root)
    assert rc == 2 and out == "error:bad-args"
