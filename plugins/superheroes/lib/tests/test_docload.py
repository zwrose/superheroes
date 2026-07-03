import identifiers
import docload
import definition_doc
import json
import os
import subprocess
import sys

_DOC = (
    "---\n"
    "superheroes: doc\n"
    "docType: tasks\n"
    "workItem: wi-abc123\n"
    "parent: {workItem: wi-abc123, docType: plan}\n"
    "size: large\n"
    "---\n"
    "# Title\n\nbody line\n"
)


def test_load_doc_parses_stable_fields_and_parent(tmp_path):
    p = tmp_path / "tasks.md"
    p.write_text(_DOC, encoding="utf-8")
    fm, body = docload.load_doc(str(p))
    assert fm["docType"] == "tasks"
    assert fm["workItem"] == "wi-abc123"
    assert fm["size"] == "large"
    assert fm["parent"] == {"workItem": "wi-abc123", "docType": "plan"}
    assert body.strip() == "# Title\n\nbody line"
    # The §6.3 content-hash reads exactly STABLE_FIELDS, so the load-bearing property is that load_doc
    # surfaces every stable field in the shape content_hash consumes. Assert that set explicitly — it
    # is self-updating if STABLE_FIELDS grows, and (unlike a hash==hash check that the field asserts
    # above already imply) catches a dropped/mis-shaped stable field directly.
    expected_fm = {"docType": "tasks", "workItem": "wi-abc123",
                   "parent": {"workItem": "wi-abc123", "docType": "plan"}, "size": "large"}
    assert {k: fm[k] for k in identifiers.STABLE_FIELDS} == \
           {k: expected_fm[k] for k in identifiers.STABLE_FIELDS}
    assert len(identifiers.content_hash(fm, body)) == 16


def test_content_hash_for_resolves_the_tasks_doc(tmp_path):
    # content_hash_for resolves docs/superheroes/<wi>/tasks.md under root, then hashes it — exercise
    # the doc_path integration (not just load_doc) so a path-resolution regression is caught (a wrong
    # path would raise FileNotFoundError here rather than silently passing).
    wi = "wi-abc123"
    d = tmp_path / "docs" / "superheroes" / wi
    d.mkdir(parents=True)
    (d / "spec.md").write_text("---\ndocType: spec\ngates: {review: passed}\n---\n# S\n", encoding="utf-8")
    (d / "tasks.md").write_text(_DOC, encoding="utf-8")
    h = docload.content_hash_for(wi, str(tmp_path))
    fm, body = definition_doc.read_frontmatter(str(d / "tasks.md"))
    assert h == identifiers.content_hash(fm, body)
    assert len(h) == 16


def _git(path):
    subprocess.run(["git", "init", "-q", str(path)], check=True)


def _setup_global_tasks(tmp_path, wi="wi-store"):
    """Out-of-repo project: tasks doc lives in the project store, not under repo root."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo)
    import mode_registry
    assert mode_registry.write_registry(str(repo), mode_registry.GLOBAL, None)
    store_dir = os.path.join(mode_registry.project_store_dir(str(repo)), "docs", wi)
    os.makedirs(store_dir)
    with open(os.path.join(store_dir, "spec.md"), "w", encoding="utf-8") as fh:
        fh.write("---\ndocType: spec\ngates: {review: passed}\n---\n# S\n")
    doc = _DOC.replace("wi-abc123", wi)
    with open(os.path.join(store_dir, "tasks.md"), "w", encoding="utf-8") as fh:
        fh.write(doc)
    return repo, store_dir


def test_content_hash_for_resolves_store_tasks_doc(tmp_path):
    # Regression for the 2026-07-02 live park: legacy in-repo path cannot find out-of-repo docs.
    repo, store_dir = _setup_global_tasks(tmp_path)
    h = docload.content_hash_for("wi-store", str(repo))
    fm, body = definition_doc.read_frontmatter(os.path.join(store_dir, "tasks.md"))
    assert h == identifiers.content_hash(fm, body)
    assert len(h) == 16


def test_content_hash_for_in_repo_unchanged(tmp_path):
    # In-repo mode must stay byte-identical with the legacy docs/superheroes/<wi>/tasks.md path.
    wi = "wi-abc123"
    d = tmp_path / "docs" / "superheroes" / wi
    d.mkdir(parents=True)
    (d / "spec.md").write_text("---\ndocType: spec\ngates: {review: passed}\n---\n# S\n", encoding="utf-8")
    (d / "tasks.md").write_text(_DOC, encoding="utf-8")
    legacy = definition_doc.doc_path(wi, "tasks", str(tmp_path))
    assert docload.tasks_doc_path(wi, str(tmp_path)) == legacy
    assert docload.content_hash_for(wi, str(tmp_path)) == identifiers.content_hash(
        *definition_doc.read_frontmatter(legacy))
