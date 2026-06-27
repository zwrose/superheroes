#!/usr/bin/env python3
"""IO entry for the content-bound completion signal (front-half #88).

Two modes over the doc at docs/superheroes/<work-item>/<doc>.md and its sidecar marker
.<doc>.complete:
  * default (check): expected = the doc's BODY hash; recorded = the marker's contents; usable =
    front_half.is_usable_draft(text, recorded, expected, required_sections). The BODY hash (not
    the whole file) is used so a later set-gate frontmatter write does not invalidate the marker.
  * --write-marker: stamp the marker = the doc's current BODY hash (the engine calls this AFTER a
    successful produce leaf, deterministically — not the LLM).
The marker (.<doc>.complete) and the NOTIFY ledger (.notify.json) live under docs/superheroes/<wi>/,
which is gitignored (CLAUDE.md), so they are run-local state and are never committed.
Fail-closed: any IO problem -> {"usable": false} (re-produce). stdlib only.
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import front_half

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
                    help="Return {text, recorded, expected, sections} so the JS twin can call "
                         "isUsableDraft() in-process (#115 Task 12). No decision is made here.")
    args = ap.parse_args(argv[1:])
    root = args.root or os.getcwd()
    base = os.path.join(root, "docs", "superheroes", args.work_item)
    doc_path = os.path.join(base, "%s.md" % args.doc)
    marker_path = os.path.join(base, ".%s.complete" % args.doc)
    try:
        with open(doc_path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        if args.emit_signals:
            print(json.dumps({"text": "", "recorded": "", "expected": "", "sections": _SECTIONS.get(args.doc, [])}))
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
        # #115 Task 12: emit the raw signals so the JS twin (front_half.isUsableDraft) can decide.
        expected = _body_hash(text)
        try:
            with open(marker_path, encoding="utf-8") as f:
                recorded = f.read().strip()
        except OSError:
            recorded = ""
        print(json.dumps({"text": text, "recorded": recorded, "expected": expected,
                          "sections": list(_SECTIONS.get(args.doc, ()))}))
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
