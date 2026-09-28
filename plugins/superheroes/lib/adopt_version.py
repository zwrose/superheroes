#!/usr/bin/env python3
"""Plan a plugin version adoption from the installed plugin cache.

Given the version a live seat is running and the cache beside it, `plan` reports the versions in
between, the TRANSITION sections the seat must read, and every changed file in one of four buckets.
Read-only and fail-closed: a fact it cannot establish is a named refusal, never a guess.
"""
import argparse
import filecmp
import json
import os
import re
import sys

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
_HEADING_RE = re.compile(r"^## (\d+\.\d+\.\d+)\s*$")
_SKIP = frozenset({"__pycache__", ".in_use", ".orphaned_at"})
_ROLES = ("showrunner", "workhorse", "detective")
_BUCKETS = ("charter", "covenantHooks", "libs", "other")


class _Refusal(Exception):
    def __init__(self, reason, detail):
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


def _key(version):
    return tuple(int(part) for part in version.split("."))


def _installed(cache_dir):
    names = [n for n in os.listdir(cache_dir)
             if _VERSION_RE.match(n) and os.path.isdir(os.path.join(cache_dir, n))]
    return sorted(names, key=_key)


def _sections(text, lo, hi):
    out, cur, fenced = [], None, False
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif fenced:
            continue
        elif line.startswith("## "):
            match = _HEADING_RE.match(line)
            cur = None
            if match and lo < _key(match.group(1)) <= hi:
                cur = {"version": match.group(1), "line": number, "subheadings": []}
                out.append(cur)
        elif cur is not None and line.startswith(("### ", "#### ")):
            cur["subheadings"].append(line.lstrip("#").strip())
    return [{"version": s["version"], "line": s["line"],
             "beforeYouUpgrade": "Before you upgrade" in s["subheadings"],
             "subheadings": s["subheadings"]} for s in out]


def _walk(root):
    found = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in _SKIP]
        linked_dirs = [d for d in dirnames if os.path.islink(os.path.join(dirpath, d))]
        for name in filenames + linked_dirs:
            if name in _SKIP:
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            found[rel] = os.readlink(full) if os.path.islink(full) else None
    return found


def _bucket(rel, role):
    if rel.startswith("skills/%s/" % role):
        return "charter"
    if rel == "rubric/covenant.md" or rel.startswith("hooks/"):
        return "covenantHooks"
    if rel.startswith(("lib/", "bin/")) and "tests" not in rel.split("/"):
        return "libs"
    return "other"


def _diff(from_root, to_root, role):
    buckets = {b: {"added": [], "removed": [], "changed": []} for b in _BUCKETS}
    old, new = _walk(from_root), _walk(to_root)
    for rel in sorted(set(old) | set(new)):
        if rel not in old:
            kind = "added"
        elif rel not in new:
            kind = "removed"
        elif old[rel] != new[rel] or (
                old[rel] is None and not filecmp.cmp(
                    os.path.join(from_root, rel), os.path.join(to_root, rel), shallow=False)):
            kind = "changed"
        else:
            continue
        buckets[_bucket(rel, role)][kind].append(rel)
    return buckets


def _plan(args):
    if args.from_root:
        from_root = os.path.abspath(args.from_root)
        cache_dir = os.path.abspath(args.cache_dir or os.path.dirname(from_root))
        from_version = os.path.basename(from_root)
    else:
        cache_dir = os.path.abspath(args.cache_dir)
        from_version = args.from_version
    if not os.path.isdir(cache_dir):
        raise _Refusal("cache-dir-missing", "cache dir is not a directory: %s" % cache_dir)
    installed = _installed(cache_dir)
    if from_version not in installed:
        raise _Refusal("from-not-installed", "%r is not an installed version" % from_version)
    to_version = args.to or installed[-1]
    if to_version not in installed:
        raise _Refusal("to-not-installed", "%r is not an installed version" % to_version)
    if _key(to_version) < _key(from_version):
        raise _Refusal("to-older-than-from", "%s is older than %s" % (to_version, from_version))
    from_root, to_root = (os.path.join(cache_dir, v) for v in (from_version, to_version))
    sections, missing = [], []
    buckets = {b: {"added": [], "removed": [], "changed": []} for b in _BUCKETS}
    up_to_date = from_version == to_version
    if not up_to_date:
        try:
            with open(os.path.join(to_root, "TRANSITION.md"), encoding="utf-8") as handle:
                text = handle.read()
        except (OSError, UnicodeDecodeError) as exc:
            raise _Refusal("transition-unreadable", "cannot read TRANSITION.md: %s" % exc)
        lo, hi = _key(from_version), _key(to_version)
        sections = _sections(text, lo, hi)
        headed = {s["version"] for s in sections}
        missing = [v for v in installed if lo < _key(v) <= hi and v not in headed]
        buckets = _diff(from_root, to_root, args.role)
    return {"ok": True, "role": args.role, "cacheDir": cache_dir, "from": from_version,
            "to": to_version, "fromRoot": from_root, "toRoot": to_root, "installed": installed,
            "upToDate": up_to_date, "transitionSections": sections,
            "missingTransitionSections": missing, "buckets": buckets,
            "counts": {b: sum(len(v) for v in buckets[b].values()) for b in _BUCKETS}}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="adopt_version")
    plan = parser.add_subparsers(dest="command", required=True).add_parser("plan")
    plan.add_argument("--role", required=True, choices=_ROLES)
    source = plan.add_mutually_exclusive_group(required=True)
    source.add_argument("--from-root")
    source.add_argument("--from", dest="from_version")
    plan.add_argument("--to")
    plan.add_argument("--cache-dir")
    args = parser.parse_args(argv)
    if args.from_version and not args.cache_dir:
        parser.error("--from requires --cache-dir")
    try:
        result, code = _plan(args), 0
    except _Refusal as refusal:
        result, code = {"ok": False, "reason": refusal.reason, "detail": refusal.detail}, 1
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    sys.exit(main())
