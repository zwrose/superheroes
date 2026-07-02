#!/usr/bin/env python3
"""Startup pipe: print core.md's enginePreferences as JSON for the JS spine to load once
into globalThis.__SR_ENGINE_PREFS (mirrors model_tier_overrides.py's startup pattern).
Belt-and-suspenders fail-open: ANY failure prints both 'claude'. Exit 0 always."""
import argparse
import json
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)


def main(argv):
    ap = argparse.ArgumentParser(prog="engine_pref_load")
    ap.add_argument("--cwd", default=".")
    ap.add_argument("--root", default=None)
    args = ap.parse_args(argv[1:])
    degenerate = {"reviewer": "claude", "implementation": "claude", "effort": {}}
    try:
        import engine_pref
        prefs = engine_pref.load_engine_prefs(args.cwd, args.root)
        if not isinstance(prefs, dict):
            prefs = degenerate
    except Exception:
        prefs = degenerate
    sys.stdout.write(json.dumps(prefs) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
