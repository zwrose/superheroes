# plugins/superheroes/lib/docload.py
"""Load a definition-doc's (frontmatter, body) and compute its §6.3 content-hash — one canonical
implementation shared by recover_entry (resume) and build_entry (branch creation), so the hash
agrees across them (CONVENTIONS §6.3)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import definition_doc
import identifiers


def load_doc(path):
    """(frontmatter_dict, body) for the §6.3 content-hash. Delegates to the canonical
    `definition_doc.read_frontmatter` reader (paired with `render_frontmatter`, the writer) so the
    parse and serialize sides never drift — a drift would silently change the content-hash."""
    return definition_doc.read_frontmatter(path)


def tasks_doc_path(work_item, root):
    """Mode-aware path to the tasks definition-doc — same degrade semantics as
    front_half_usable._work_item_dir (gate_write._doc parity): resolve via definition_doc;
    an undeterminable mode (a newer registry schema -> UnknownSchemaVersion) degrades to the
    pure in-repo default rather than crashing the hash/read."""
    import mode_registry
    try:
        base = definition_doc.resolve_work_item_dir(work_item, root=root, cwd=root)
    except mode_registry.UnknownSchemaVersion:
        base = definition_doc.work_item_dir(work_item, root)
    return os.path.join(base, "tasks.md")


def content_hash_for(work_item, root):
    fm, body = load_doc(tasks_doc_path(work_item, root))
    return identifiers.content_hash(fm, body)
