# plugins/superheroes/lib/docload.py
"""Load a definition-doc's (frontmatter, body) and compute its §6.3 content-hash — one canonical
implementation shared by recover_entry (resume) and build_entry (branch creation), so the hash
agrees across them (CONVENTIONS §6.3)."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import definition_doc
import identifiers


def load_doc(path):
    """(frontmatter_dict, body). Uses definition_doc._frontmatter_bounds (the canonical fence
    finder) and builds the dict of the STABLE_FIELDS identifiers.content_hash needs — `parent` as
    the nested {workItem, docType} mapping, the rest scalar."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    lines, end = definition_doc._frontmatter_bounds(text, path)
    fm = {}
    for ln in lines[1:end]:
        m = re.match(r"([A-Za-z]+):\s*(.+)$", ln)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if key == "parent" and val.startswith("{"):
            pm = dict(re.findall(r"(\w+):\s*([\w-]+)", val))
            fm["parent"] = {"workItem": pm.get("workItem"), "docType": pm.get("docType")}
        else:
            fm[key] = val
    body = "\n".join(lines[end + 1:])
    return fm, body


def content_hash_for(work_item, root):
    fm, body = load_doc(definition_doc.doc_path(work_item, "tasks", root))
    return identifiers.content_hash(fm, body)
