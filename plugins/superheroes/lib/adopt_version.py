#!/usr/bin/env python3
"""Read-only planner for adopting a newer plugin version from the install cache."""
from __future__ import annotations

import argparse
import filecmp
import json
import os
import re
import sys

_VER = re.compile(r"^\d+\.\d+\.\d+$")
_HEAD = re.compile(r"^## (\d+\.\d+\.\d+)\s*$")
_SKIP = frozenset({"__pycache__", ".in_use", ".orphaned_at"})
_BUCKETS = ("charter", "covenantHooks", "libs", "other")


def _vt(s):
    return tuple(int(x) for x in s.split("."))


def _refuse(reason, detail):
    sys.stdout.write(json.dumps({"ok": False, "reason": reason, "detail": detail}) + "\n")
    return 1


def list_installed(cache_dir):
    if not os.path.isdir(cache_dir):
        return None
    names = [n for n in os.listdir(cache_dir) if _VER.match(n) and os.path.isdir(os.path.join(cache_dir, n))]
    names.sort(key=_vt)
    return names


def _in_range(from_v, ver, to_v):
    return _vt(from_v) < _vt(ver) <= _vt(to_v)


def _collect(root):
    root = os.path.abspath(root)
    out = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        rel = os.path.relpath(dirpath, root)
        parts = [] if rel == "." else rel.split(os.sep)
        if any(p in _SKIP for p in parts):
            dirnames.clear()
            continue
        dirnames[:] = [d for d in dirnames if d not in _SKIP]
        for fn in filenames:
            rp = parts + [fn]
            if any(p in _SKIP for p in rp):
                continue
            rel_path = "/".join(rp)
            full = os.path.join(dirpath, fn)
            out[rel_path] = ("link", os.readlink(full)) if os.path.islink(full) else ("file", full)
    return out


def _bucket(path, role):
    if path.startswith(f"skills/{role}/"):
        return "charter"
    if path == "rubric/covenant.md" or path.startswith("hooks/"):
        return "covenantHooks"
    if (path.startswith("lib/") or path.startswith("bin/")) and "tests" not in path.split("/"):
        return "libs"
    return "other"


def diff_buckets(from_root, to_root, role):
    a, b = _collect(from_root), _collect(to_root)
    buckets = {k: {"added": [], "removed": [], "changed": []} for k in _BUCKETS}
    for p in sorted(set(a) | set(b)):
        bk = _bucket(p, role)
        if p not in a:
            buckets[bk]["added"].append(p)
        elif p not in b:
            buckets[bk]["removed"].append(p)
        else:
            ta, tb = a[p], b[p]
            changed = ta[0] != tb[0] or (ta[0] == "link" and ta[1] != tb[1])
            if not changed and ta[0] == "file":
                changed = not filecmp.cmp(ta[1], tb[1], shallow=False)
            if changed:
                buckets[bk]["changed"].append(p)
    return buckets


def parse_transition(to_root, from_v, to_v):
    path = os.path.join(to_root, "TRANSITION.md")
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return None
    sections, found = [], set()
    in_fence, i, n = False, 0, len(lines)
    while i < n:
        line = lines[i]
        if line.strip().startswith("```"):
            in_fence = not in_fence
            i += 1
            continue
        if in_fence:
            i += 1
            continue
        m = _HEAD.match(line)
        if m:
            ver = m.group(1)
            found.add(ver)
            if _in_range(from_v, ver, to_v):
                subs, j, inf = [], i + 1, False
                while j < n:
                    ln = lines[j]
                    if ln.strip().startswith("```"):
                        inf = not inf
                        j += 1
                        continue
                    if inf:
                        j += 1
                        continue
                    if ln.startswith("## "):
                        break
                    if ln.startswith("### ") or ln.startswith("#### "):
                        subs.append(ln.lstrip("#").strip())
                    j += 1
                sections.append({
                    "version": ver, "line": i + 1,
                    "beforeYouUpgrade": "Before you upgrade" in subs,
                    "subheadings": subs,
                })
        i += 1
    return sections, found


def missing_sections(installed, from_v, to_v, found):
    miss = [v for v in installed if _in_range(from_v, v, to_v) and v not in found]
    if to_v not in found and to_v not in miss:
        miss.append(to_v)
    miss.sort(key=_vt)
    return miss


def plan(role, cache_dir, from_v, from_root, to_v=None):
    cache_dir = os.path.abspath(cache_dir)
    installed = list_installed(cache_dir)
    if installed is None:
        return _refuse("cache-dir-missing", "cache directory does not exist or is not a directory")
    if from_v not in installed:
        return _refuse("from-not-installed", f"version {from_v} is not installed in cache")
    to_v = to_v or installed[-1]
    if to_v not in installed:
        return _refuse("to-not-installed", f"version {to_v} is not installed in cache")
    if _vt(to_v) < _vt(from_v):
        return _refuse("to-older-than-from", f"target {to_v} is older than {from_v}")
    from_root = os.path.abspath(from_root)
    to_root = os.path.join(cache_dir, to_v)
    up = from_v == to_v
    if up:
        sections, miss = [], []
        buckets = {k: {"added": [], "removed": [], "changed": []} for k in _BUCKETS}
    else:
        parsed = parse_transition(to_root, from_v, to_v)
        if parsed is None:
            return _refuse("transition-unreadable", "TRANSITION.md is missing or unreadable")
        sections, found = parsed
        miss = missing_sections(installed, from_v, to_v, found)
        buckets = diff_buckets(from_root, to_root, role)
    counts = {b: sum(len(buckets[b][k]) for k in ("added", "removed", "changed")) for b in _BUCKETS}
    sys.stdout.write(json.dumps({
        "ok": True, "role": role, "cacheDir": cache_dir, "from": from_v, "to": to_v,
        "fromRoot": from_root, "toRoot": os.path.abspath(to_root), "installed": installed,
        "upToDate": up, "transitionSections": sections, "missingTransitionSections": miss,
        "buckets": buckets, "counts": counts,
    }) + "\n")
    return 0


def main(argv=None):
    raw = argv if argv is not None else sys.argv
    argv = raw[1:] if raw and raw[0] != "plan" else raw
    ap = argparse.ArgumentParser(description="plugin version adoption helper")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--role", required=True, choices=["showrunner", "workhorse", "detective"])
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-root")
    src.add_argument("--from", dest="from_ver")
    p.add_argument("--cache-dir")
    p.add_argument("--to")
    args = ap.parse_args(argv)
    if args.from_root:
        from_root = os.path.abspath(args.from_root)
        cache_dir = os.path.abspath(args.cache_dir or os.path.dirname(from_root))
        from_v = os.path.basename(from_root)
    else:
        if not args.cache_dir:
            p.error("--cache-dir is required with --from")
        cache_dir = os.path.abspath(args.cache_dir)
        from_v = args.from_ver
        from_root = os.path.join(cache_dir, from_v)
    return plan(args.role, cache_dir, from_v, from_root, args.to)


if __name__ == "__main__":
    sys.exit(main())
