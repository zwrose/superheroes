#!/usr/bin/env python3
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_pilot_applicability


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main(argv):
    ap = argparse.ArgumentParser(description="test-pilot applicability")
    sub = ap.add_subparsers(dest="cmd", required=True)
    decide = sub.add_parser("decide")
    decide.add_argument("--diff-json", required=True)
    decide.add_argument("--detectors-json", required=True)
    decide.add_argument("--profile-json", required=True)
    decide.add_argument("--plan-result-json")
    args = ap.parse_args(argv[1:])

    if args.cmd == "decide":
        try:
            diff = _read_json(args.diff_json)
            detectors = _read_json(args.detectors_json)
            profile = _read_json(args.profile_json)
            plan_result = _read_json(args.plan_result_json) if args.plan_result_json else None
            result = test_pilot_applicability.decide(diff, detectors, profile, plan_result)
        except (OSError, ValueError) as exc:
            result = {"verdict": "park", "reason": "malformed inputs: %s" % exc}
        sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
