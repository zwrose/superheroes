#!/usr/bin/env python3
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_pilot_budget


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main(argv):
    ap = argparse.ArgumentParser(description="test-pilot budget decider")
    sub = ap.add_subparsers(dest="cmd", required=True)
    decide = sub.add_parser("decide")
    decide.add_argument("--counts-json", required=True)
    decide.add_argument("--limits-json")
    args = ap.parse_args(argv[1:])

    if args.cmd == "decide":
        try:
            counts = _read_json(args.counts_json)
            limits = _read_json(args.limits_json) if args.limits_json else None
            result = test_pilot_budget.decide(counts, limits)
        except (OSError, ValueError) as exc:
            result = {"action": "park_budget_exceeded", "reason": "malformed inputs: %s" % exc}
        sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
