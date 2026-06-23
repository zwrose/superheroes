#!/usr/bin/env python3
"""superheroes (architect): definition-doc location + frontmatter helper (CONVENTIONS §3, §6.1).

Resolution is mode-aware (CONVENTIONS §2.3/§3.3): global mode → the I1 project
store (`projects/<config-key>/docs/<work-item>/…`); in-repo mode → the location
configured by the project's doc-policy. The doc-policy (where definition-docs live
and whether they are committed or gitignored) is owned by `architect_config.py`
and set up by `architect-init`.

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
import re
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import identifiers  # noqa: E402  (sibling import; see module docstring)

SCHEMA_VERSION = 1
DOC_TYPES = ("spec", "plan", "tasks")
# The in-repo default docs location, kept in lock-step with architect_config.DEFAULT_LOCATION
# (a connascence-of-value guard test asserts they match). Defined here too, rather than
# imported, so these pure path helpers stay import-light (no module-load dependency on the
# policy/mode stack — the deferred-import design).
DEFAULT_LOCATION = "docs/superheroes"
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


def work_item_dir(work_item, root=".", location=DEFAULT_LOCATION):
    return os.path.join(root, *location.split("/"), work_item)


def doc_path(work_item, doc_type, root=".", location=DEFAULT_LOCATION):
    if doc_type not in DOC_TYPES:
        raise ValueError(f"unknown docType {doc_type!r}; expected one of {DOC_TYPES}")
    return os.path.join(work_item_dir(work_item, root, location), f"{doc_type}.md")


def _in_repo_candidate(work_item, root, cwd, store_root=None):
    import architect_config
    pol = architect_config.read_policy(cwd, store_root)
    location = pol["location"] if pol else architect_config.DEFAULT_LOCATION
    return work_item_dir(work_item, root, location)


def _global_candidate(work_item, cwd, store_root):
    import mode_registry
    return os.path.join(mode_registry.project_store_dir(cwd, store_root), "docs", work_item)


def resolve_work_item_dir(work_item, *, root, cwd, store_root=None):
    """Mode-aware, spec-anchored directory for a work-item's definition-docs.
    Propagates mode_registry.UnknownSchemaVersion (UFR-7 — caller halts)."""
    import mode_registry
    in_repo = _in_repo_candidate(work_item, root, cwd, store_root)
    global_dir = _global_candidate(work_item, cwd, store_root)
    # Spec-anchor (UFR-2): an existing work-item lives wherever its spec is — keep docs together.
    for cand in (in_repo, global_dir):
        if os.path.isfile(os.path.join(cand, "spec.md")):
            return cand
    # No existing doc → the recorded mode decides (raises UnknownSchemaVersion if newer).
    mode = mode_registry.resolve(cwd, store_root)["mode"]
    return in_repo if mode == mode_registry.IN_REPO else global_dir


class IgnoreCoverageError(RuntimeError):
    """A kept-local (gitignored) docs location could not be kept out of version control
    (already tracked or .gitignore unwritable) — UFR-8; the write must be refused. The
    offending location is the exception's single arg."""


def resolve_write_path(work_item, doc_type, *, root, cwd=None, store_root=None):
    """Resolve the mode-aware write path for a definition-doc and prepare it for writing:
    ensure ignore coverage for a kept-local (gitignored) policy, record an
    analysis-informed PROVISIONAL policy when none exists (UFR-1, only after the ignore
    gate passes), and create the target directory. Returns the resolved `<doc>.md` path.

    Raises mode_registry.UnknownSchemaVersion when the storage mode is undeterminable
    (UFR-7) and IgnoreCoverageError when a gitignored location can't be kept untracked
    (UFR-8). The `resolve-write` CLI verb is a thin wrapper over this."""
    import architect_config
    cwd = cwd if cwd is not None else root
    d = resolve_work_item_dir(work_item, root=root, cwd=cwd, store_root=store_root)
    pol = architect_config.read_policy(cwd, store_root)
    is_new = pol is None
    if is_new:
        pol = {**architect_config.analyze_repo(root), "confirmed": False}
    root_abs = os.path.abspath(root)
    d_abs = os.path.abspath(d)
    is_inrepo = d_abs == root_abs or d_abs.startswith(root_abs + os.sep)
    if is_inrepo and pol.get("visibility") == architect_config.GITIGNORED:
        if not architect_config.ensure_ignored(root, pol["location"]):
            raise IgnoreCoverageError(pol["location"])
    if is_new:
        architect_config.write_policy(cwd, pol)  # provisional (UFR-1); store contention is non-fatal
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, doc_type + ".md")


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


# --- review gate (§3.1) ----------------------------------------------------

REVIEW_STATES = ("pending", "passed", "changes-requested")
# `status` is DERIVED from gates.review (§3.1): approved iff review == passed.
_STATUS_FOR_REVIEW = {"passed": "approved", "changes-requested": "in-review", "pending": "draft"}
_GATES_RE = re.compile(r"^gates:\s*\{\s*review:\s*([a-z-]+)\s*\}\s*$")
_STATUS_RE = re.compile(r"^status:\s*[a-z-]+\s*$")
_UPDATED_RE = re.compile(r'^updated:\s*".*"\s*$')


def _frontmatter_bounds(text, path):
    """Return (lines, end) where the frontmatter is lines[1:end] (between the two `---`)."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path}: missing opening '---' frontmatter fence")
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise ValueError(f"{path}: unterminated frontmatter (no closing '---')")
    return lines, end


def read_frontmatter(path):
    """Parse a definition-doc's §3.1 frontmatter into (frontmatter_dict, body) — the reader paired
    with `render_frontmatter` (the writer), co-located so the two sides change in lockstep. `parent`
    is parsed back into its nested {workItem, docType} mapping; other fields stay scalar. This is the
    canonical frontmatter→dict reader (e.g. for the §6.3 content-hash); callers must not re-implement it.
    """
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    lines, end = _frontmatter_bounds(text, path)
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
    return fm, "\n".join(lines[end + 1:])


def read_gate(path):
    """Return the definition-doc's gates.review value, parsed from the frontmatter.

    Reads from the `---`-fenced frontmatter only (so a body line can't spoof it),
    and gives a clear error if the gates line is absent or malformed — more robust
    than a skill grepping the raw file.
    """
    with open(path, encoding="utf-8") as fh:
        lines, end = _frontmatter_bounds(fh.read(), path)
    for ln in lines[1:end]:
        m = _GATES_RE.match(ln)
        if m:
            return m.group(1)
    raise ValueError(f"{path}: no parseable 'gates: {{review: …}}' line in frontmatter")


def set_gate(path, review):
    """Set gates.review in place (and derive status, bump updated) — §3.1.

    The lib owns the frontmatter shape, so the gate flip lives here rather than a
    skill hand-editing YAML. In the Phase-1 degraded mode (no review-spec), the
    owner's recorded terminal approval is what calls this with review=passed.
    """
    if review not in REVIEW_STATES:
        raise ValueError(f"unknown review state {review!r}; expected one of {REVIEW_STATES}")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    lines, end = _frontmatter_bounds(text, path)
    status = _STATUS_FOR_REVIEW[review]
    today = datetime.date.today().isoformat()
    found = False
    for i in range(1, end):
        if _GATES_RE.match(lines[i]):
            lines[i] = f"gates: {{review: {review}}}"
            found = True
        elif _STATUS_RE.match(lines[i]):
            lines[i] = f"status: {status}"
        elif _UPDATED_RE.match(lines[i]):
            lines[i] = f'updated: "{today}"'
    if not found:
        raise ValueError(f"{path}: no 'gates: {{review: …}}' line to update")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return {"review": review, "status": status}


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

    sg = sub.add_parser("set-gate", help="record gates.review on a definition-doc (derives status)")
    sg.add_argument("--work-item", required=True)
    sg.add_argument("--doc", required=True, choices=DOC_TYPES)
    sg.add_argument("--review", required=True, choices=list(REVIEW_STATES))
    sg.add_argument("--root", default=".")

    rg = sub.add_parser("read-gate", help="print a definition-doc's gates.review value")
    rg.add_argument("--work-item", required=True)
    rg.add_argument("--doc", required=True, choices=DOC_TYPES)
    rg.add_argument("--root", default=".")
    rg.add_argument("--json", action="store_true",
                    help="emit {\"review\": <state>} on stdout (errors stay on stderr/non-zero)")

    rw = sub.add_parser("resolve-write",
                        help="resolve the mode-aware write path, ensuring ignore coverage")
    rw.add_argument("--work-item", required=True)
    rw.add_argument("--doc", required=True, choices=DOC_TYPES)
    rw.add_argument("--root", default=".")
    rw.add_argument("--cwd", default=None)
    return p


def main(argv):
    args = _build_parser().parse_args(argv[1:])
    if args.cmd == "mint":
        sys.stdout.write(mint_work_item(args.title, args.nonce) + "\n")
        return 0
    if args.cmd == "resolve-write":
        import mode_registry
        try:
            path = resolve_write_path(args.work_item, args.doc,
                                      root=args.root, cwd=args.cwd or args.root)
        except mode_registry.UnknownSchemaVersion as exc:
            sys.stderr.write("definition_doc: storage mode could not be determined (%s) — "
                             "repair the mode record first; refusing to guess.\n" % exc)
            return 1
        except IgnoreCoverageError:
            sys.stderr.write("definition_doc: refusing to write — the kept-local docs "
                             "location could not be kept out of version control "
                             "(already tracked or .gitignore unwritable). Resolve it "
                             "before writing.\n")
            return 1
        sys.stdout.write(path + "\n")
        return 0
    if args.cmd == "frontmatter":
        fm = frontmatter(
            args.doc, args.work_item, size=args.size, parent=args.parent_item,
            issue=args.issue, created=args.created, updated=args.updated)
        sys.stdout.write(render_frontmatter(fm))
        return 0
    try:
        if args.cmd in ("path", "dir", "read-gate", "set-gate"):
            d = resolve_work_item_dir(args.work_item, root=args.root, cwd=args.root)
            if args.cmd == "path":
                sys.stdout.write(os.path.join(d, f"{args.doc}.md") + "\n")
                return 0
            if args.cmd == "dir":
                sys.stdout.write(d + "\n")
                return 0
            if args.cmd == "set-gate":
                result = set_gate(os.path.join(d, f"{args.doc}.md"), args.review)
                sys.stdout.write(json.dumps(result) + "\n")
                return 0
            if args.cmd == "read-gate":
                review = read_gate(os.path.join(d, f"{args.doc}.md"))
                if getattr(args, "json", False):   # the cmdRunner JSON bridge (errors stay stderr/non-zero)
                    sys.stdout.write(json.dumps({"review": review}) + "\n")
                else:
                    sys.stdout.write(review + "\n")
                return 0
    except __import__("mode_registry").UnknownSchemaVersion as exc:
        sys.stderr.write(
            "definition_doc: storage mode could not be determined (%s) — repair the "
            "project's mode record before continuing; refusing to guess a location.\n" % exc)
        return 1
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except (ValueError, OSError) as exc:
        sys.stderr.write(f"definition_doc error: {exc}\n")
        sys.exit(1)
