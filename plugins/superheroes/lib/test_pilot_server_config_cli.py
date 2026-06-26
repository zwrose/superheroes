#!/usr/bin/env python3
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_pilot_server_config


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main(argv):
    ap = argparse.ArgumentParser(description="test-pilot server context resolver")
    sub = ap.add_subparsers(dest="cmd", required=True)
    resolve = sub.add_parser("resolve")
    resolve.add_argument("--profile-json", required=True)
    resolve.add_argument("--detection-json", required=True)
    resolve.add_argument("--work-item", required=True)
    args = ap.parse_args(argv[1:])

    if args.cmd == "resolve":
        try:
            profile = _read_json(args.profile_json)
            detection = _read_json(args.detection_json)
            result = test_pilot_server_config.resolve(profile, detection, args.work_item)
        except (OSError, ValueError) as exc:
            result = {"schemaVersion": test_pilot_server_config.SCHEMA_VERSION,
                      "verdict": "park", "reason": "malformed inputs: %s" % exc,
                      "workItem": args.work_item}
        sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
