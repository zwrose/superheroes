"""review-crew-local wrapper over the-architect's model_tier.py core.

Resolves role -> dispatch model name by subprocessing the shared core (so
review-code and the trio get the band-wide knob without re-implementing the
table). Fail-OPEN: if the core is unresolvable or errors, return the embedded
default for the role (a wrong/absent tier is a cost concern, never a safety one).
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import architect_lib  # noqa: E402

_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MT = ("the-architect", "lib", "model_tier.py")

# Embedded fallback mirrors the core's DEFAULT_TIERS (used only when the core is
# unresolvable). The core is the source of truth; this is the degrade path.
_FALLBACK = {
    "orchestrator": None,
    "reviewer": "sonnet",
    "reviewer-deep": "opus",
    "mechanical": "haiku",
}


def _resolve(root):
    return architect_lib.resolve_target(_MT, root=root, plugin_root=_PLUGIN_ROOT)


def _subprocess_json(lib, cli_args):
    try:
        p = subprocess.run([sys.executable, lib, *cli_args],
                           capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        return None
    if p.returncode != 0:
        return None
    try:
        return json.loads(p.stdout.strip())
    except (ValueError, json.JSONDecodeError):
        return None


def _fallback(role):
    return _FALLBACK.get(role, _FALLBACK["reviewer"])


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description="model-tier resolver (review-crew)")
    ap.add_argument("--role", required=True)
    ap.add_argument("--root", default=None)
    ap.add_argument("--overrides", default=None)
    args = ap.parse_args(argv[1:])

    lib = _resolve(args.root)
    if lib is None:
        sys.stdout.write(json.dumps({"role": args.role, "model": _fallback(args.role),
                                     "degraded": True}) + "\n")
        return 0
    cli = ["resolve", "--role", args.role]
    if args.overrides:
        cli += ["--overrides", args.overrides]
    res = _subprocess_json(lib, cli)
    if not res or "model" not in res:
        sys.stdout.write(json.dumps({"role": args.role, "model": _fallback(args.role),
                                     "degraded": True}) + "\n")
        return 0
    res["degraded"] = False
    sys.stdout.write(json.dumps(res) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
