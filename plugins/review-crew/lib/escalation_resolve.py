#!/usr/bin/env python3
"""review-crew-local wrapper for the cross-plugin escalation core (F5).

The skills call THIS (at a known ${CLAUDE_PLUGIN_ROOT}/lib path), never the resolved
cross-plugin path directly — exactly as they call gate_write.py. It resolves
the-architect's escalation.py via architect_lib, subprocesses it, and owns the
fail-closed degradation: if the lib is unresolvable, it falls back to the conservative
posture (GATE / refuse), never to a silent proceed/allow. Output: JSON to stdout with a
`degraded` flag so the skill can note the fallback.
"""
import argparse
import json
import os
import subprocess
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
import architect_lib  # noqa: E402

_PLUGIN_ROOT = os.path.dirname(_LIB_DIR)               # review-crew plugin root
_ESC = ("the-architect", "lib", "escalation.py")
_RUBRIC = ("the-architect", "rubric", "escalation-base.md")


def _say(detail):
    sys.stderr.write(detail + "\n")


def _resolve(root):
    return architect_lib.resolve_target(_ESC, root=root, plugin_root=_PLUGIN_ROOT)


def _subprocess_json(lib, cli_args):
    p = subprocess.run([sys.executable, lib, *cli_args], capture_output=True, text=True)
    if p.returncode != 0:
        return None
    try:
        return json.loads(p.stdout.strip())
    except (ValueError, json.JSONDecodeError):
        return None


def _band_roots(root):
    """Resolved plugin roots to anchor the canonical-path guard against: this review-crew
    install, the resolved the-architect install, and — when --root is given (dogfood / in-repo)
    — the in-repo plugin dirs. The guard refuses a safety-named file under ANY of them, so a
    like-named file in the target repo (outside these roots) is NOT falsely refused.
    """
    roots = [_PLUGIN_ROOT]
    arch = _resolve(root)                               # .../the-architect[/<ver>]/lib/escalation.py
    if arch:
        roots.append(os.path.dirname(os.path.dirname(arch)))
    if root:
        for p in ("review-crew", "the-architect"):
            cand = os.path.join(root, "plugins", p)
            if os.path.isdir(cand):
                roots.append(cand)
    return roots


def _build_parser():
    ap = argparse.ArgumentParser(description="escalation core wrapper (review-crew)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_root(parser):
        parser.add_argument("--root", default=None)

    r = sub.add_parser("route"); add_root(r)
    for f in ("--on-floor", "--ground-truth-locus", "--owner-weighable",
              "--reversible", "--confidence"):
        r.add_argument(f, required=True)
    c = sub.add_parser("classify"); add_root(c); c.add_argument("--action", required=True)
    g = sub.add_parser("guard"); add_root(g); g.add_argument("--path", required=True)
    rb = sub.add_parser("rubric"); add_root(rb)
    return ap


def main(argv):
    args = _build_parser().parse_args(argv[1:])          # --root lives on each subparser

    if args.cmd == "rubric":
        path = architect_lib.resolve_target(_RUBRIC, root=args.root, plugin_root=_PLUGIN_ROOT)
        if path is None:
            _say("escalation-base.md not resolvable — the skill must apply the embedded "
                 "fail-closed posture (apply the floor; GATE anything owner-weighable).")
            sys.stdout.write(json.dumps({"path": None, "degraded": True}) + "\n")
            return 0
        sys.stdout.write(json.dumps({"path": path, "degraded": False}) + "\n")
        return 0

    lib = _resolve(args.root)

    if args.cmd == "route":
        if lib is None:
            _say("escalation.py not resolvable — applying the conservative fallback (GATE).")
            sys.stdout.write(json.dumps({"mode": "gate", "degraded": True}) + "\n")
            return 0
        res = _subprocess_json(lib, ["route", "--on-floor", args.on_floor,
                                     "--ground-truth-locus", args.ground_truth_locus,
                                     "--owner-weighable", args.owner_weighable,
                                     "--reversible", args.reversible,
                                     "--confidence", args.confidence])
        mode = res["mode"] if res and "mode" in res else "gate"   # fail closed
        sys.stdout.write(json.dumps({"mode": mode, "degraded": res is None}) + "\n")
        return 0

    if args.cmd == "classify":
        if lib is None:
            sys.stdout.write(json.dumps({"on_floor": True, "degraded": True}) + "\n")  # conservative
            return 0
        res = _subprocess_json(lib, ["classify", "--action", args.action])
        on_floor = res["on_floor"] if res and "on_floor" in res else True
        sys.stdout.write(json.dumps({"on_floor": on_floor, "degraded": res is None}) + "\n")
        return 0

    if args.cmd == "guard":
        if lib is None:
            sys.stdout.write(json.dumps({"allow": False, "degraded": True}) + "\n")  # refuse
            return 0
        band_args = []
        for r in _band_roots(args.root):
            band_args += ["--band-root", r]
        res = _subprocess_json(lib, ["guard", "--path", args.path, *band_args])
        allow = res["allow"] if res and "allow" in res else False
        sys.stdout.write(json.dumps({"allow": allow, "degraded": res is None}) + "\n")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
