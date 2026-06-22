import identifiers
import docload


def test_load_doc_parses_stable_fields_and_parent(tmp_path):
    p = tmp_path / "tasks.md"
    p.write_text(
        "---\n"
        "superheroes: doc\n"
        "docType: tasks\n"
        "workItem: wi-abc123\n"
        "parent: {workItem: wi-abc123, docType: plan}\n"
        "size: large\n"
        "---\n"
        "# Title\n\nbody line\n", encoding="utf-8")
    fm, body = docload.load_doc(str(p))
    assert fm["docType"] == "tasks"
    assert fm["workItem"] == "wi-abc123"
    assert fm["size"] == "large"
    assert fm["parent"] == {"workItem": "wi-abc123", "docType": "plan"}
    # parity: the §6.3 hash over docload's parsed fm+body equals the hash over the SAME stable
    # fields built by hand — so a mutation in load_doc's parse (a dropped field, a mis-shaped
    # parent) changes fm and breaks this. (Not a tautology — the RHS fm is independent.)
    expected_fm = {"docType": "tasks", "workItem": "wi-abc123",
                   "parent": {"workItem": "wi-abc123", "docType": "plan"}, "size": "large"}
    assert identifiers.content_hash(fm, body) == identifiers.content_hash(expected_fm, body)
    assert len(identifiers.content_hash(fm, body)) == 16
