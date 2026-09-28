#!/usr/bin/env python3
"""Read-only planner for adopting a newer installed plugin cache version."""
import argparse
import filecmp
import json
import os
import re
import sys

_VER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_HVER = re.compile(r"^## (\d+\.\d+\.\d+)\s*$")
_SKIP = frozenset({"__pycache__", ".in_use", ".orphaned_at"})

def _vt(v):
    m = _VER.match(v)
    return tuple(int(x) for x in m.groups()) if m else None

def _installed(cache):
    names = [n for n in os.listdir(cache) if os.path.isdir(os.path.join(cache, n)) and _VER.match(n)]
    names.sort(key=_vt)
    return names

def _refuse(reason, detail):
    sys.stdout.write(json.dumps({"ok": False, "reason": reason, "detail": detail}) + "\n")
    return 1

def _collect(root):
    out, bad = {}, lambda ps: any(p in _SKIP for p in ps)

    def _on_walk_error(err):
        raise err

    for dp, dns, fns in os.walk(root, followlinks=False, onerror=_on_walk_error):
        rel = os.path.relpath(dp, root)
        parts = rel.replace("\\", "/").split("/") if rel != "." else []
        if bad(parts):
            dns[:] = []
            continue
        dns[:] = [d for d in dns if d not in _SKIP]
        for fn in fns:
            rel_p = "/".join(parts + [fn]) if parts else fn
            if bad(rel_p.split("/")):
                continue
            full = os.path.join(dp, fn)
            if os.path.islink(full):
                out[rel_p] = ("link", os.readlink(full))
            elif os.path.isfile(full):
                out[rel_p] = ("file", full)
    return out

def _bucket(path, role):
    if path.startswith(f"skills/{role}/"):
        return "charter"
    if path == "rubric/covenant.md" or path.startswith("hooks/"):
        return "covenantHooks"
    if path.startswith(("lib/", "bin/")) and "tests" not in path.split("/"):
        return "libs"
    return "other"

def _parse_transition(path, fv, tv, installed):
    try:
        with open(path, encoding="utf-8") as fh:
            lines = [ln.rstrip("\n") for ln in fh]
    except OSError:
        return None
    fence, sections, found = False, [], set()
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("```"):
            fence = not fence
            i += 1
            continue
        if not fence:
            m = _HVER.match(lines[i])
            if m:
                ver = m.group(1)
                found.add(ver)
                if _vt(fv) < _vt(ver) <= _vt(tv):
                    subs, j, inf = [], i + 1, False
                    while j < len(lines):
                        if lines[j].strip().startswith("```"):
                            inf = not inf
                        elif not inf:
                            if _HVER.match(lines[j]):
                                break
                            if lines[j].startswith(("### ", "#### ")):
                                subs.append(lines[j].lstrip("#").strip())
                        j += 1
                    sections.append({"version": ver, "line": i + 1,
                                     "beforeYouUpgrade": "Before you upgrade" in subs,
                                     "subheadings": subs})
        i += 1
    missing = [v for v in installed if _vt(fv) < _vt(v) <= _vt(tv) and v not in found]
    if tv not in found and tv not in missing:
        missing.append(tv)
    missing.sort(key=_vt)
    return sections, missing

def _plan(role, cache, from_v, to_v):
    if not os.path.isdir(cache):
        return _refuse("cache-dir-missing", "cache dir missing or not a directory")
    cache = os.path.abspath(cache)
    inst = _installed(cache)
    if from_v not in inst:
        return _refuse("from-not-installed", f"version {from_v} is not installed")
    if to_v not in inst:
        return _refuse("to-not-installed", f"version {to_v} is not installed")
    if _vt(to_v) < _vt(from_v):
        return _refuse("to-older-than-from", f"to {to_v} is older than from {from_v}")
    fr, tr = os.path.join(cache, from_v), os.path.join(cache, to_v)
    buckets = {k: {"added": [], "removed": [], "changed": []}
               for k in ("charter", "covenantHooks", "libs", "other")}
    up, trans, miss = from_v == to_v, [], []
    if not up:
        parsed = _parse_transition(os.path.join(tr, "TRANSITION.md"), from_v, to_v, inst)
        if parsed is None:
            return _refuse("transition-unreadable", "TRANSITION.md missing or unreadable")
        trans, miss = parsed
        try:
            ca, cb = _collect(fr), _collect(tr)
        except OSError as exc:
            return _refuse("version-tree-unreadable", str(exc))
        for k in sorted(set(ca) | set(cb)):
            if k not in ca:
                kind = "added"
            elif k not in cb:
                kind = "removed"
            else:
                ak, bk = ca[k], cb[k]
                if ak[0] == bk[0] and (ak[0] == "link" and ak[1] == bk[1] or ak[0] == "file" and filecmp.cmp(ak[1], bk[1], shallow=False)):
                    continue
                kind = "changed"
            buckets[_bucket(k, role)][kind].append(k)
    counts = {k: len(buckets[k]["added"]) + len(buckets[k]["removed"]) + len(buckets[k]["changed"]) for k in buckets}
    payload = {"ok": True, "role": role, "cacheDir": cache, "from": from_v, "to": to_v, "fromRoot": fr,
               "toRoot": tr, "installed": inst, "upToDate": up, "transitionSections": trans,
               "missingTransitionSections": miss, "buckets": buckets, "counts": counts}
    sys.stdout.write(json.dumps(payload) + "\n")
    return 0

def main(argv=None):
    ap = argparse.ArgumentParser()
    p = ap.add_subparsers(dest="cmd", required=True).add_parser("plan")
    p.add_argument("--role", required=True, choices=["showrunner", "workhorse", "detective"])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--from-root")
    g.add_argument("--from", dest="from_ver")
    p.add_argument("--to")
    p.add_argument("--cache-dir")
    args = ap.parse_args(argv)
    if args.from_root:
        fr = os.path.abspath(args.from_root)
        from_v, cache = os.path.basename(fr), os.path.abspath(args.cache_dir or os.path.dirname(fr))
    else:
        from_v = args.from_ver
        if not args.cache_dir:
            p.error("--cache-dir is required with --from")
        cache = os.path.abspath(args.cache_dir)
    inst = _installed(cache) if os.path.isdir(cache) else []
    return _plan(args.role, cache, from_v, args.to or (inst[-1] if inst else from_v))

if __name__ == "__main__":
    sys.exit(main())
