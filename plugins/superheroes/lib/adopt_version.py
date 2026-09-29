#!/usr/bin/env python3
"""Adoption plan for a live seat moving to a newer installed plugin version.

Read-only. Reports the versions between the running one and the target, the
TRANSITION sections to read, and every changed file in one of four buckets.
Fails closed with a named refusal whenever a fact cannot be established.
"""
from __future__ import annotations

import argparse
import filecmp
import json
import os
import re
import sys

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
HEADING_RE = re.compile(r"^## (\d+\.\d+\.\d+)\s*$")
SUB_RE = re.compile(r"^(?:###|####) (.+?)\s*$")
SKIP = frozenset({"__pycache__", ".in_use", ".orphaned_at"})
ROLES = ("showrunner", "workhorse", "detective")
BUCKETS = ("charter", "covenantHooks", "libs", "other")


class Refusal(Exception):
    def __init__(self, reason, detail):
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


def vkey(version):
    return tuple(int(p) for p in version.split("."))


def installed_versions(cache_dir):
    names = [e.name for e in os.scandir(cache_dir)
             if e.is_dir() and VERSION_RE.match(e.name)]
    return sorted(names, key=vkey)


def transition_sections(path, lo, hi):
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise Refusal("transition-unreadable", f"cannot read {path}: {exc}")
    sections, current, fenced = [], None, False
    for number, line in enumerate(lines, 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        if line.startswith("## "):
            match = HEADING_RE.match(line)
            current = None
            if match and lo < vkey(match.group(1)) <= hi:
                current = {"version": match.group(1), "line": number,
                           "beforeYouUpgrade": False, "subheadings": []}
                sections.append(current)
            continue
        sub = SUB_RE.match(line)
        if current is not None and sub:
            current["subheadings"].append(sub.group(1))
            current["beforeYouUpgrade"] |= sub.group(1) == "Before you upgrade"
    return sections


def snapshot(root):
    entries = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in SKIP]
        names = dirnames + [f for f in filenames if f not in SKIP]
        for name in names:
            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                entries[os.path.relpath(full, root).replace(os.sep, "/")] = (
                    "link", os.readlink(full))
            elif name not in dirnames:
                entries[os.path.relpath(full, root).replace(os.sep, "/")] = (
                    "file", full)
    return entries


def bucket_of(rel, role):
    parts = rel.split("/")
    if rel.startswith(f"skills/{role}/"):
        return "charter"
    if rel == "rubric/covenant.md" or rel.startswith("hooks/"):
        return "covenantHooks"
    if rel.startswith(("lib/", "bin/")) and "tests" not in parts:
        return "libs"
    return "other"


def diff_buckets(from_root, to_root, role):
    old, new = snapshot(from_root), snapshot(to_root)
    buckets = {b: {"added": [], "removed": [], "changed": []} for b in BUCKETS}
    for rel in sorted(set(old) | set(new)):
        if rel not in old:
            kind = "added"
        elif rel not in new:
            kind = "removed"
        else:
            (ok, ov), (nk, nv) = old[rel], new[rel]
            same = ok == nk and (ov == nv if ok == "link"
                                 else filecmp.cmp(ov, nv, shallow=False))
            if same:
                continue
            kind = "changed"
        buckets[bucket_of(rel, role)][kind].append(rel)
    return buckets


def plan(args):
    if args.from_root:
        from_root = os.path.abspath(args.from_root)
        cache_dir = os.path.abspath(args.cache_dir or os.path.dirname(from_root))
        src = os.path.basename(from_root)
    else:
        cache_dir, src = os.path.abspath(args.cache_dir), args.from_version
    if not os.path.isdir(cache_dir):
        raise Refusal("cache-dir-missing", f"{cache_dir} is not a directory")
    installed = installed_versions(cache_dir)
    if src not in installed:
        raise Refusal("from-not-installed", f"{src!r} is not installed in {cache_dir}")
    dst = args.to or installed[-1]
    if dst not in installed:
        raise Refusal("to-not-installed", f"{dst!r} is not installed in {cache_dir}")
    if vkey(dst) < vkey(src):
        raise Refusal("to-older-than-from", f"{dst} is older than {src}")
    from_root, to_root = os.path.join(cache_dir, src), os.path.join(cache_dir, dst)
    up_to_date = src == dst
    sections, missing = [], []
    buckets = {b: {"added": [], "removed": [], "changed": []} for b in BUCKETS}
    if not up_to_date:
        sections = transition_sections(
            os.path.join(to_root, "TRANSITION.md"), vkey(src), vkey(dst))
        found = {s["version"] for s in sections}
        missing = [v for v in installed
                   if vkey(src) < vkey(v) <= vkey(dst) and v not in found]
        buckets = diff_buckets(from_root, to_root, args.role)
    return {"ok": True, "role": args.role, "cacheDir": cache_dir, "from": src,
            "to": dst, "fromRoot": from_root, "toRoot": to_root,
            "installed": installed, "upToDate": up_to_date,
            "transitionSections": sections, "missingTransitionSections": missing,
            "buckets": buckets,
            "counts": {b: sum(len(v) for v in buckets[b].values()) for b in BUCKETS}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    pl = sub.add_parser("plan")
    pl.add_argument("--role", required=True, choices=ROLES)
    origin = pl.add_mutually_exclusive_group(required=True)
    origin.add_argument("--from-root")
    origin.add_argument("--from", dest="from_version")
    pl.add_argument("--to")
    pl.add_argument("--cache-dir")
    args = parser.parse_args(argv)
    if args.from_version and not args.cache_dir:
        parser.error("--from requires --cache-dir")
    try:
        result, code = plan(args), 0
    except Refusal as refusal:
        result, code = {"ok": False, "reason": refusal.reason,
                        "detail": refusal.detail}, 1
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    sys.exit(main())
