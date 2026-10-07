"""The spec review gate, driven through the workflow with the CLI calls the docs name.

A spec's review gate keeps three states: `pending`, `changes-requested`, `passed`. It passes only
when the owner approves (discovery step 8). A fix that changes approved content resets it to
`pending` (spec-checks.md, The review gate). These tests run the same commands those docs name,
in a throwaway definition-doc fixture, and census the docs so no other surface writes `passed`.
"""
import importlib.util
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.normpath(os.path.join(_HERE, ".."))
_PLUGIN = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SKILLS = os.path.join(_PLUGIN, "skills")
_DISCOVERY = os.path.join(_SKILLS, "architect-discovery", "SKILL.md")
_SPEC_CHECKS = os.path.join(_SKILLS, "architect-discovery", "reference", "spec-checks.md")
WI = "add-thing-50c082"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DD = _load(os.path.join(_LIB, "definition_doc.py"), "definition_doc_spec_review_gate")


def _cli(script, *args):
    return subprocess.run(
        [sys.executable, "-B", os.path.join(_LIB, script), *args],
        capture_output=True, text=True, check=False,
    )


def _spec(tmp_path):
    """A fresh spec draft in the canonical layout. Returns (root, spec path)."""
    root = str(tmp_path / "repo")
    os.makedirs(DD.work_item_dir(WI, root))
    fm = DD.frontmatter("spec", WI, size="small", created="2026-06-15", updated="2026-06-15")
    path = DD.doc_path(WI, "spec", root)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(DD.render_frontmatter(fm) + "\n# spec\n")
    return root, path


def _hash(path):
    out = _cli("definition_doc.py", "content-hash", "--path", path)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def _set_gate(root, path, review, run_id):
    return _cli(
        "definition_doc.py", "set-gate", "--doc", "spec", "--work-item", WI,
        "--review", review, "--root", root,
        "--expected-hash", _hash(path), "--run-id", run_id,
    )


def _reset(root, path):
    return _cli(
        "gate_write.py", "--mode", "reset", "--doc", "spec", "--work-item", WI,
        "--reviewed-path", path, "--root", root,
        "--expected-hash", _hash(path), "--run-id", "spec-checks-" + WI,
    )


def _gate(path):
    return DD.read_gate(path)


def _status(path):
    fm, _body = DD.read_frontmatter(path)
    return fm["status"]


def _edit_content(path):
    """A fix that changes the spec's content."""
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\nThe fix changed this line.\n")


def test_fresh_spec_draft_reads_pending(tmp_path):
    _root, path = _spec(tmp_path)
    # axis: a spec starts at the draft state, before any check or approval
    assert _gate(path) == "pending"
    assert _status(path) == "draft"


def test_owner_asks_for_changes_records_changes_requested(tmp_path):
    root, path = _spec(tmp_path)
    out = _set_gate(root, path, "changes-requested", "owner-changes-" + WI)
    # axis: the owner's change request is a recordable gate transition
    assert out.returncode == 0, out.stderr
    assert _gate(path) == "changes-requested"
    # axis: the derived status follows the gate into review
    assert _status(path) == "in-review"


def test_owner_approval_after_changes_records_passed(tmp_path):
    root, path = _spec(tmp_path)
    assert _set_gate(root, path, "changes-requested", "owner-changes-" + WI).returncode == 0
    out = _set_gate(root, path, "passed", "selfcert-" + WI)
    # axis: the owner's approval is the transition that writes passed
    assert out.returncode == 0, out.stderr
    assert _gate(path) == "passed"
    # axis: the derived status follows the gate to approved
    assert _status(path) == "approved"


def test_reset_on_approved_spec_after_content_change_returns_to_pending(tmp_path):
    root, path = _spec(tmp_path)
    assert _set_gate(root, path, "passed", "selfcert-" + WI).returncode == 0
    _edit_content(path)
    out = _reset(root, path)
    # axis: a fix that changes approved content revokes the stale approval
    assert out.stdout.strip() == "reset:pending", (out.stdout, out.stderr)
    assert _gate(path) == "pending"
    # axis: the derived status leaves approved with the gate
    assert _status(path) == "draft"


@pytest.mark.parametrize("state", ["pending", "changes-requested"])
def test_reset_on_spec_that_is_not_passed_changes_nothing(tmp_path, state):
    root, path = _spec(tmp_path)
    if state != "pending":
        assert _set_gate(root, path, state, "owner-changes-" + WI).returncode == 0
    before = open(path, encoding="utf-8").read()
    out = _reset(root, path)
    # axis: the reset only revokes an approval, so a gate that is not passed is a no-op
    assert out.stdout.strip() == "noop:not-approved", (out.stdout, out.stderr)
    # axis: the reset never grants and never moves a gate that was not approved
    assert _gate(path) == state
    assert open(path, encoding="utf-8").read() == before


def _skill_files():
    for base, _dirs, names in os.walk(_SKILLS):
        for name in names:
            path = os.path.join(base, name)
            try:
                with open(path, encoding="utf-8") as fh:
                    yield os.path.relpath(path, _SKILLS), fh.read()
            except (UnicodeDecodeError, OSError):
                continue


def test_only_the_discovery_owner_approval_block_writes_passed():
    writers = sorted(rel for rel, text in _skill_files() if "--review passed" in text)
    # axis: the owner's approval is the one place a skill records passed
    assert writers == [os.path.join("architect-discovery", "SKILL.md")], writers
    with open(_SPEC_CHECKS, encoding="utf-8") as fh:
        checks = fh.read()
    # axis: the checks never write passed
    assert "--review passed" not in checks


def test_docs_name_the_reset_and_the_changes_requested_record():
    with open(_SPEC_CHECKS, encoding="utf-8") as fh:
        checks = fh.read()
    with open(_DISCOVERY, encoding="utf-8") as fh:
        discovery = fh.read()
    # axis: the stale-approval reset has one doc home, the checks doc
    assert 'gate_write.py" --mode reset' in checks
    # axis: discovery records the owner's change request before the re-run
    assert "--review changes-requested" in discovery


def test_reset_snippet_binds_spec_path_from_definition_doc_path():
    with open(_SPEC_CHECKS, encoding="utf-8") as fh:
        checks = fh.read()
    # axis: the reset snippet is self-contained, so SPEC_PATH is never an unassigned variable
    assert 'SPEC_PATH=$(python3 -B "$ROOT_DIR/lib/definition_doc.py" path' in checks
    assert checks.index('SPEC_PATH=$(') < checks.index('gate_write.py" --mode reset')
