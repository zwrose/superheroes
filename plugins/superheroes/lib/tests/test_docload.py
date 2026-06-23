import identifiers
import docload
import definition_doc


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
    (d / "tasks.md").write_text(_DOC, encoding="utf-8")
    h = docload.content_hash_for(wi, str(tmp_path))
    fm, body = definition_doc.read_frontmatter(str(d / "tasks.md"))
    assert h == identifiers.content_hash(fm, body)
    assert len(h) == 16
