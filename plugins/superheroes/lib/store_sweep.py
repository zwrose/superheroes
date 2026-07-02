#!/usr/bin/env python3
# plugins/superheroes/lib/store_sweep.py
"""Orphan report + sweep for the per-project stores under store_root()/projects/.

Store keys are one-way hashes of the source repo, so an abandoned store is untraceable
without the mint-time `sourcePath` provenance ensure_project_store/ensure_store now
record in meta.json. Classification (fail-closed — any doubt reads as MORE alive):

- `real`    — the store has real content (docs/ with files, git commits, or ANY file
              the classifier does not recognize as pure bookkeeping), OR its recorded
              sourcePath still exists on disk. Never deleted.
- `orphan`  — sourcePath is recorded but the path no longer exists, and the store holds
              nothing but bookkeeping. The only class `sweep` deletes by default.
- `unknown` — no (or unreadable) sourcePath and no real content: a pre-provenance store.
              Deleted only with the explicit --include-unknown opt-in.

Stdlib-only, no subprocess: git history is detected via .git/refs + packed-refs, so the
report stays fast across a thousand stores.
"""
import argparse
import json
import os
import shutil
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import control_plane  # noqa: E402

REAL, ORPHAN, UNKNOWN = "real", "orphan", "unknown"

# Files every store mints or accretes regardless of use — never evidence of life.
# Anything NOT named here counts as real content (fail-closed for future state files).
_BOOKKEEPING = {"meta.json", "registry.json", "config.lock", "doc-policy.json", ".DS_Store"}


def projects_root(root=None):
    return os.path.join(root or control_plane.store_root(), "projects")


def _git_has_commits(git_dir):
    """True when the store's git repo has any ref (a bare `git init` has none).
    Filesystem-only; an unreadable .git reads as True (doubt → alive)."""
    try:
        for _base, _dirs, files in os.walk(os.path.join(git_dir, "refs")):
            if files:
                return True
        packed = os.path.join(git_dir, "packed-refs")
        if os.path.isfile(packed):
            with open(packed, encoding="utf-8", errors="replace") as fh:
                return any(ln.strip() and not ln.startswith(("#", "^")) for ln in fh)
        return False
    except OSError:
        return True


def _dir_has_files(path):
    try:
        for _base, _dirs, files in os.walk(path):
            if any(f != ".DS_Store" for f in files):
                return True
        return False
    except OSError:
        return True


def _content_signals(store_dir):
    """Reasons this store holds real content; empty list = bookkeeping only."""
    signals = []
    try:
        entries = sorted(os.listdir(store_dir))
    except OSError:
        return ["unreadable"]
    for name in entries:
        p = os.path.join(store_dir, name)
        if name == ".git":
            if not os.path.isdir(p) or _git_has_commits(p):
                signals.append("git-commits")
        elif name in _BOOKKEEPING:
            continue
        elif os.path.isdir(p):
            if _dir_has_files(p):
                signals.append(f"content:{name}/")
        else:
            signals.append(f"content:{name}")
    return signals


def _source_path(store_dir):
    try:
        with open(os.path.join(store_dir, "meta.json"), encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        return None
    sp = meta.get("sourcePath") if isinstance(meta, dict) else None
    return sp if isinstance(sp, str) and sp else None


def classify(store_dir):
    """One store dir -> {class, reasons, sourcePath}. Fail-closed by construction:
    content or a live sourcePath means real; doubt never lands in the orphan class."""
    reasons = _content_signals(store_dir)
    source = _source_path(store_dir)
    if reasons:
        cls = REAL
    elif source is not None:
        if os.path.exists(source):
            cls, reasons = REAL, ["source-path-exists"]
        else:
            cls, reasons = ORPHAN, ["source-path-missing"]
    else:
        cls, reasons = UNKNOWN, ["no-source-path"]
    return {"class": cls, "reasons": reasons, "sourcePath": source}


def report(root=None):
    base = projects_root(root)
    stores = []
    counts = {REAL: 0, ORPHAN: 0, UNKNOWN: 0}
    try:
        keys = sorted(os.listdir(base))
    except OSError:
        keys = []
    for key in keys:
        d = os.path.join(base, key)
        if not os.path.isdir(d):
            continue
        entry = classify(d)
        entry.update({"key": key, "path": d})
        counts[entry["class"]] += 1
        stores.append(entry)
    return {"projectsRoot": base, "stores": stores, "counts": counts}


def sweep(root=None, include_unknown=False):
    """Delete orphan-class stores (plus unknown-class only on the explicit opt-in).
    Each dir is re-classified immediately before deletion and must still be a direct
    child of the projects root — real stores are never deleted, under any flag."""
    base = os.path.realpath(projects_root(root))
    doomed = {ORPHAN} | ({UNKNOWN} if include_unknown else set())
    deleted, kept, errors = [], {REAL: 0, ORPHAN: 0, UNKNOWN: 0}, []
    for entry in report(root)["stores"]:
        d = entry["path"]
        fresh = classify(d)  # re-check at delete time; doubt → kept
        if fresh["class"] not in doomed or os.path.dirname(os.path.realpath(d)) != base:
            kept[fresh["class"]] += 1
            continue
        try:
            shutil.rmtree(d)
            deleted.append(d)
        except OSError as exc:
            errors.append({"path": d, "error": str(exc)})
    return {"projectsRoot": base, "deleted": deleted, "kept": kept,
            "includeUnknown": include_unknown, "errors": errors}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("report", help="classify every per-project store (read-only)")
    rp.add_argument("--root", default=None, help="store root override (default: store_root())")
    sw = sub.add_parser("sweep", help="delete orphan-class stores; prints what it did")
    sw.add_argument("--root", default=None, help="store root override (default: store_root())")
    sw.add_argument("--include-unknown", action="store_true",
                    help="also delete pre-provenance stores with no content (owner opt-in)")
    args = ap.parse_args(argv)
    if args.cmd == "report":
        out = report(root=args.root)
    else:
        out = sweep(root=args.root, include_unknown=args.include_unknown)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
