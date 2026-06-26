#!/usr/bin/env python3
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_pilot_publish


def main(argv):
    ap = argparse.ArgumentParser(description="test-pilot publish gate")
    sub = ap.add_subparsers(dest="cmd", required=True)
    publish = sub.add_parser("publish")
    publish.add_argument("--work-item", required=True)
    publish.add_argument("--head", required=True)
    publish.add_argument("--status-json", required=True)
    args = ap.parse_args(argv[1:])

    if args.cmd == "publish":
        result = test_pilot_publish.publish(args.work_item, args.head, args.status_json)
        sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
