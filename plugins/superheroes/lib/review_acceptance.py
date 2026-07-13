#!/usr/bin/env python3
"""#397 FR-14: the owner-acceptance ledger for parked doc reviews.

record()      — on gate-approval, persist {identity, docSection, contentHash} per accepted
                finding into plan-accept.json / tasks-accept.json in the work-item docs dir.
candidates()  — at re-review, return each accepted finding with whether its concerned-section
                content hash still matches the current doc. Suppression is the caller's job and
                requires BOTH a hash match AND the synthesis judge's sameness confirmation
                (fail-closed to re-judging) — this module never suppresses on the hash alone.

The concerned section is drawn generously: the finding's matched heading through the next
heading of the same-or-shallower level — the whole subsection. A heading that can't be
resolved, or a finding whose substance spans subsections (docSection: null), is keyed to the
whole-doc hash — the safe direction (re-judge), never a silently-stale accept."""

import argparse
import hashlib
import json
import os
import re
import sys

import finding_identity

SCHEMA_VERSION = 1
_FILENAME = {"plan": "plan-accept.json", "tasks": "tasks-accept.json"}
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.M)


def whole_doc_hash(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def section_hash(text, heading):
    """Hash the whole subsection: the matched heading line through the next heading of the same
    or shallower level. An unresolved heading falls back to the whole-doc hash (fail-closed)."""
    if not heading:
        return whole_doc_hash(text)
    matches = list(_HEADING.finditer(text or ""))
    for i, m in enumerate(matches):
        if finding_identity.normalize_title(m.group(2)) == finding_identity.normalize_title(heading):
            level = len(m.group(1))
            start = m.start()
            end = len(text)
            for n in matches[i + 1:]:
                if len(n.group(1)) <= level:
                    end = n.start()
                    break
            return hashlib.sha256(text[start:end].encode("utf-8")).hexdigest()[:16]
    return whole_doc_hash(text)


def _path(docs_dir, doc):
    return os.path.join(docs_dir, _FILENAME[doc])


def record(docs_dir, doc, findings, doc_text):
    entries = []
    for f in findings or []:
        if not isinstance(f, dict):
            continue
        section = f.get("docSection")
        content_hash = whole_doc_hash(doc_text) if section in (None, "") else section_hash(doc_text, section)
        entries.append({
            "identity": finding_identity.finding_identity(f),
            "docSection": section if section not in ("",) else None,
            "contentHash": content_hash,
        })
    payload = {"schemaVersion": SCHEMA_VERSION, "doc": doc, "accepted": entries}
    path = _path(docs_dir, doc)
    os.makedirs(docs_dir, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, sort_keys=True)
    os.replace(tmp, path)
    return {"ok": True, "path": path, "count": len(entries)}


def candidates(docs_dir, doc, doc_text):
    path = _path(docs_dir, doc)
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            led = json.load(fh)
    except (OSError, ValueError):
        return []
    out = []
    for e in led.get("accepted") or []:
        section = e.get("docSection")
        current = whole_doc_hash(doc_text) if section in (None, "") else section_hash(doc_text, section)
        out.append({"identity": e.get("identity"), "docSection": section,
                    "hashMatches": current == e.get("contentHash")})
    return out


def main(argv):
    ap = argparse.ArgumentParser(description="#397 doc-review acceptance ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--docs-dir", required=True)
    r.add_argument("--doc", required=True, choices=["plan", "tasks"])
    r.add_argument("--findings", required=True)
    r.add_argument("--doc-path", required=True)
    c = sub.add_parser("candidates")
    c.add_argument("--docs-dir", required=True)
    c.add_argument("--doc", required=True, choices=["plan", "tasks"])
    c.add_argument("--doc-path", required=True)
    args = ap.parse_args(argv)
    doc_text = open(args.doc_path, encoding="utf-8").read()
    if args.cmd == "record":
        with open(args.findings, encoding="utf-8") as fh:
            findings = json.load(fh)
        print(json.dumps(record(args.docs_dir, args.doc, findings, doc_text)))
    else:
        print(json.dumps(candidates(args.docs_dir, args.doc, doc_text)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
