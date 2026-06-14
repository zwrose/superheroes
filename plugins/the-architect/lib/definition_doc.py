#!/usr/bin/env python3
"""the-architect: definition-doc location + frontmatter helper (CONVENTIONS §3, §6.1).

Phase 1 is deliberately MINIMAL and in-repo only: definition-docs live at
`docs/superheroes/<work-item>/{spec,plan,tasks}.md` in the target repo. Global
mode, the project/registry store, and the unified resolver are deferred to 2a
(CONVENTIONS §2.3/§4.2) — this module hard-codes the in-repo layout and takes a
`--root` so callers can point at a repo root other than the cwd.

Two jobs:
  - mint + locate: freeze a `<work-item>` slug (§6.1, via the vendored
    identifiers) and resolve the on-disk path for each doc-type.
  - frontmatter: build + render the §3.1 shared additive header so a skill never
    hand-writes (and never invalidates) the machine-read linkage. The body prose
    is authored separately (the `writing-specs` skill); the renderer here owns
    only the `---`-fenced frontmatter block.

Run as a script from this directory; the sibling `identifiers` module imports
directly because the script dir is on sys.path (same convention as test-pilot's
engine.py). We also insert the lib dir explicitly so importing this module by
path (the conformance test) still resolves `identifiers`.
"""
import argparse
import datetime
import json
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import identifiers  # noqa: E402  (sibling import; see module docstring)

SCHEMA_VERSION = 1
DOC_TYPES = ("spec", "plan", "tasks")
# Each doc-type's parent referent (§3.1): plan→spec, tasks→plan, spec→none.
_PARENT_DOCTYPE = {"spec": None, "plan": "spec", "tasks": "plan"}


def _plugin_version():
    """Read this plugin's version from its manifest, so `producedBy` has one source."""
    manifest = os.path.join(_LIB_DIR, "..", ".claude-plugin", "plugin.json")
    with open(manifest, encoding="utf-8") as fh:
        return json.load(fh)["version"]


def produced_by():
    return f"the-architect@{_plugin_version()}"


# --- mint + locate ---------------------------------------------------------

def mint_work_item(title, nonce=None):
    """Freeze a `<work-item>` slug for `title` (§6.1).

    The slug is minted ONCE per work-item and never re-derived. `nonce` is the
    creation nonce that disambiguates same-titled items; callers normally omit
    it and we draw a fresh random one (the resulting slug is what gets frozen).
    Tests pass an explicit nonce for determinism.
    """
    if nonce is None:
        nonce = os.urandom(8).hex()
    return identifiers.work_item_slug(title, nonce)


def work_item_dir(work_item, root="."):
    return os.path.join(root, "docs", "superheroes", work_item)


def doc_path(work_item, doc_type, root="."):
    if doc_type not in DOC_TYPES:
        raise ValueError(f"unknown docType {doc_type!r}; expected one of {DOC_TYPES}")
    return os.path.join(work_item_dir(work_item, root), f"{doc_type}.md")


# --- frontmatter (§3.1) ----------------------------------------------------

def frontmatter(doc_type, work_item, *, size, parent=None, issue=None,
                created=None, updated=None, status="draft", review="pending"):
    """Build the §3.1 frontmatter dict, enforcing the parent-linkage invariant.

    `spec` must have a null parent; `plan` must parent a `spec`; `tasks` must
    parent a `plan` (§3.1). We fail closed on a mismatch rather than emit a doc
    that violates the contract. `parent` may be passed as the work-item slug of
    the parent (a string) or as a full `{workItem, docType}` dict.
    """
    if doc_type not in DOC_TYPES:
        raise ValueError(f"unknown docType {doc_type!r}; expected one of {DOC_TYPES}")
    expected_parent = _PARENT_DOCTYPE[doc_type]
    parent_obj = _normalize_parent(parent, expected_parent, doc_type)
    today = datetime.date.today().isoformat()
    return {
        "superheroes": "doc",
        "schemaVersion": SCHEMA_VERSION,
        "docType": doc_type,
        "workItem": work_item,
        "issue": issue,
        "parent": parent_obj,
        "size": size,
        "status": status,
        "gates": {"review": review},
        "producedBy": produced_by(),
        "created": created or today,
        "updated": updated or today,
    }


def _normalize_parent(parent, expected_doctype, doc_type):
    if expected_doctype is None:
        if parent is not None:
            raise ValueError(f"{doc_type} must have a null parent (§3.1), got {parent!r}")
        return None
    if parent is None:
        raise ValueError(f"{doc_type} requires a parent {expected_doctype} (§3.1)")
    if isinstance(parent, str):
        return {"workItem": parent, "docType": expected_doctype}
    if isinstance(parent, dict):
        if parent.get("docType") != expected_doctype:
            raise ValueError(
                f"{doc_type} parent must be a {expected_doctype} (§3.1), "
                f"got {parent.get('docType')!r}")
        if not parent.get("workItem"):
            raise ValueError(f"{doc_type} parent missing workItem (§3.1)")
        return {"workItem": parent["workItem"], "docType": expected_doctype}
    raise ValueError(f"parent must be a slug string or {{workItem, docType}} dict, got {parent!r}")


def render_frontmatter(fm):
    """Render the frontmatter dict as a deterministic `---`-fenced YAML block.

    We emit the fixed §3.1 field set in schema order and quote the values that a
    YAML reader would otherwise coerce (dates → date objects; `producedBy` holds
    `@`). The constrained fields (slugs, enums) are safe bare scalars.
    """
    parent = fm["parent"]
    if parent is None:
        parent_str = "null"
    else:
        parent_str = "{workItem: %s, docType: %s}" % (parent["workItem"], parent["docType"])
    issue = fm["issue"]
    issue_str = "null" if issue is None else str(issue)
    lines = [
        "---",
        "superheroes: doc",
        f"schemaVersion: {fm['schemaVersion']}",
        f"docType: {fm['docType']}",
        f"workItem: {fm['workItem']}",
        f"issue: {issue_str}",
        f"parent: {parent_str}",
        f"size: {fm['size']}",
        f"status: {fm['status']}",
        f"gates: {{review: {fm['gates']['review']}}}",
        f'producedBy: "{fm["producedBy"]}"',
        f'created: "{fm["created"]}"',
        f'updated: "{fm["updated"]}"',
        "---",
    ]
    return "\n".join(lines) + "\n"


# --- CLI -------------------------------------------------------------------

def _build_parser():
    p = argparse.ArgumentParser(description="the-architect definition-doc helper (§3, §6.1)")
    sub = p.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("mint", help="freeze a <work-item> slug for a title (§6.1)")
    m.add_argument("--title", required=True)
    m.add_argument("--nonce", default=None)

    pa = sub.add_parser("path", help="resolve the on-disk path for a definition-doc")
    pa.add_argument("--work-item", required=True)
    pa.add_argument("--doc", required=True, choices=DOC_TYPES)
    pa.add_argument("--root", default=".")

    d = sub.add_parser("dir", help="resolve the work-item directory")
    d.add_argument("--work-item", required=True)
    d.add_argument("--root", default=".")

    f = sub.add_parser("frontmatter", help="render the §3.1 frontmatter block")
    f.add_argument("--doc", required=True, choices=DOC_TYPES)
    f.add_argument("--work-item", required=True)
    f.add_argument("--size", required=True, choices=["small", "medium", "large"])
    f.add_argument("--issue", type=int, default=None)
    f.add_argument("--parent-item", default=None,
                   help="parent work-item slug (required for plan/tasks)")
    f.add_argument("--created", default=None)
    f.add_argument("--updated", default=None)
    return p


def main(argv):
    args = _build_parser().parse_args(argv[1:])
    if args.cmd == "mint":
        sys.stdout.write(mint_work_item(args.title, args.nonce) + "\n")
        return 0
    if args.cmd == "path":
        sys.stdout.write(doc_path(args.work_item, args.doc, args.root) + "\n")
        return 0
    if args.cmd == "dir":
        sys.stdout.write(work_item_dir(args.work_item, args.root) + "\n")
        return 0
    if args.cmd == "frontmatter":
        fm = frontmatter(
            args.doc, args.work_item, size=args.size, parent=args.parent_item,
            issue=args.issue, created=args.created, updated=args.updated)
        sys.stdout.write(render_frontmatter(fm))
        return 0
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except (ValueError, OSError) as exc:
        sys.stderr.write(f"definition_doc error: {exc}\n")
        sys.exit(1)
