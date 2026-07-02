#!/usr/bin/env python3
"""IO entry for the content-bound completion signal (front-half #88).

Two modes over the doc at the work-item's MODE-AWARE docs dir (CONVENTIONS §2.3/§3.3 — the
storage-mode resolver decides between the in-repo location and the out-of-repo project store)
and its sidecar marker .<doc>.complete:
  * default (check): expected = the doc's BODY hash; recorded = the marker's contents; usable =
    front_half.is_usable_draft(text, recorded, expected, required_sections). The BODY hash (not
    the whole file) is used so a later set-gate frontmatter write does not invalidate the marker.
  * --write-marker: stamp the marker = the doc's current BODY hash (the engine calls this AFTER a
    successful produce leaf, deterministically — not the LLM).
The marker (.<doc>.complete) and the NOTIFY ledger (.notify.json) sit next to the doc — run-local
state that is never committed (the in-repo location is gitignored; the store is out-of-repo).
Fail-closed: any IO problem -> {"usable": false} (re-produce).
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import front_half


def _work_item_dir(work_item, root):
    """The work-item's mode-aware docs dir (same handshake as gate_write._doc): resolve via
    definition_doc; an undeterminable mode (a newer registry schema -> UnknownSchemaVersion)
    degrades to the pure in-repo default rather than crashing the completion check."""
    import definition_doc
    import mode_registry
    try:
        return definition_doc.resolve_work_item_dir(work_item, root=root, cwd=root)
    except mode_registry.UnknownSchemaVersion:
        return definition_doc.work_item_dir(work_item, root)

# the required body sections per docType (template headings, minus the conditional UI/UX).
_SECTIONS = {
    "plan": ["Overview", "Goals & non-goals", "Architecture", "Components & interfaces",
             "How the requirements are met", "Key decisions & alternatives",
             "Risks & mitigations", "Dependencies & assumptions"],
    "tasks": ["Goal", "Architecture", "Tech Stack"],
}


def _body(text):
    """The doc body (after the closing frontmatter fence), or the whole text if no frontmatter."""
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            return text[end + 4:]
    return text


def _body_hash(text):
    return hashlib.sha256(_body(text).encode("utf-8")).hexdigest()


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--work-item", required=True)
    ap.add_argument("--doc", required=True, choices=["plan", "tasks"])
    ap.add_argument("--root", default=None)
    ap.add_argument("--write-marker", action="store_true")
    ap.add_argument("--emit-signals", action="store_true",
                    help="Return {usable, recorded, expected} — verdict computed Python-side at the "
                         "IO boundary so the large doc text never crosses the cheapest-model pipe.")
    args = ap.parse_args(argv[1:])
    root = args.root or os.getcwd()
    base = _work_item_dir(args.work_item, root)
    doc_path = os.path.join(base, "%s.md" % args.doc)
    marker_path = os.path.join(base, ".%s.complete" % args.doc)
    try:
        with open(doc_path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        if args.emit_signals:
            # No doc -> not usable. Verdict computed here; large text never crosses the pipe.
            # All required sections are missing; no placeholder (no text).
            sections = tuple(_SECTIONS.get(args.doc, ()))
            print(json.dumps({
                "usable": False,
                "recorded": "",
                "expected": "",
                "missing_sections": list(sections),
                "placeholder": False,
            }))
            return 0
        print(json.dumps({"usable": False, "wrote": False})); return 0
    if args.write_marker:
        try:
            with open(marker_path, "w", encoding="utf-8") as f:
                f.write(_body_hash(text))
            print(json.dumps({"wrote": True}))
        except OSError:
            print(json.dumps({"wrote": False}))
        return 0
    if args.emit_signals:
        # Compute the usability verdict at the IO boundary (Python-side) so the large doc text
        # never crosses the cheapest-model exec pipe (live-surfaced large-payload-transport limit).
        # The spine reads signals.usable directly — no JS twin call on the doc text.
        # Also emit the specific gaps (missing_sections, placeholder) so the produce repair loop
        # can generate a targeted re-prompt hint without re-sending the large doc text (Layer 2a).
        expected = _body_hash(text)
        try:
            with open(marker_path, encoding="utf-8") as f:
                recorded = f.read().strip()
        except OSError:
            recorded = ""
        sections = tuple(_SECTIONS.get(args.doc, ()))
        usable = front_half.is_usable_draft(text, recorded, expected, sections)
        gaps = front_half.usable_draft_gaps(text, sections)
        print(json.dumps({
            "usable": bool(usable),
            "recorded": recorded,
            "expected": expected,
            "missing_sections": gaps["missing_sections"],
            "placeholder": gaps["placeholder"],
        }))
        return 0
    # check mode: marker (recorded) must equal the doc's CURRENT body hash (expected).
    expected = _body_hash(text)
    try:
        with open(marker_path, encoding="utf-8") as f:
            recorded = f.read().strip()
    except OSError:
        recorded = ""
    ok = front_half.is_usable_draft(text, recorded, expected, tuple(_SECTIONS.get(args.doc, ())))
    print(json.dumps({"usable": bool(ok)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
