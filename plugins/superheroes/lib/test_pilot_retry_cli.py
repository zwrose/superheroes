#!/usr/bin/env python3
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_pilot_retry


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main(argv):
    ap = argparse.ArgumentParser(description="test-pilot retry decider")
    sub = ap.add_subparsers(dest="cmd", required=True)
    decide = sub.add_parser("decide")
    decide.add_argument("--pass-json", required=True)
    decide.add_argument("--history-json", required=True)
    decide.add_argument("--changed-file", action="append", dest="changed_files")
    decide.add_argument("--dependency-json")
    args = ap.parse_args(argv[1:])

    if args.cmd == "decide":
        try:
            pass_result = _read_json(args.pass_json)
            history = _read_json(args.history_json)
            dependency_map = _read_json(args.dependency_json) if args.dependency_json else None
            result = test_pilot_retry.decide(
                pass_result,
                history,
                changed_files=args.changed_files,
                dependency_map=dependency_map,
            )
        except (OSError, ValueError) as exc:
            result = {"action": "park_malformed_inputs", "reason": str(exc)}
        sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
