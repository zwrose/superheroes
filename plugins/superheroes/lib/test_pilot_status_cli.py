#!/usr/bin/env python3
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_pilot_status


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main(argv):
    ap = argparse.ArgumentParser(description="test-pilot readiness status")
    sub = ap.add_subparsers(dest="cmd", required=True)
    assert_current = sub.add_parser("assert-current")
    assert_current.add_argument("--work-item", required=True)
    assert_current.add_argument("--head", required=True)
    write = sub.add_parser("write")
    write.add_argument("--work-item", required=True)
    write.add_argument("--status-json", required=True)
    args = ap.parse_args(argv[1:])

    path = test_pilot_status.status_path(os.getcwd(), args.work_item)
    if args.cmd == "assert-current":
        result = test_pilot_status.assert_current(path, args.head)
        sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
        return 0
    if args.cmd == "write":
        try:
            data = _read_json(args.status_json)
            written = test_pilot_status.write(path, data)
            result = {"ok": True, "path": path, "head": written.get("head")}
        except (OSError, ValueError) as exc:
            result = {"ok": False, "reason": str(exc)}
        sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
