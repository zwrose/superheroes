#!/usr/bin/env python3
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_pilot_results


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main(argv):
    ap = argparse.ArgumentParser(description="test-pilot result aggregator")
    sub = ap.add_subparsers(dest="cmd", required=True)
    aggregate = sub.add_parser("aggregate")
    aggregate.add_argument("--raw-json", required=True)
    args = ap.parse_args(argv[1:])
    try:
        raw = _read_json(args.raw_json)
        result = test_pilot_results.aggregate_browser_results(raw)
    except (OSError, ValueError) as exc:
        result = {"action": "park", "reason": "malformed inputs: %s" % exc}
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
