#!/usr/bin/env python3
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_pilot_seed


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main(argv):
    ap = argparse.ArgumentParser(description="test-pilot seed workflow helper")
    sub = ap.add_subparsers(dest="cmd", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--records-json", required=True)
    restore = sub.add_parser("restore-baseline")
    restore.add_argument("--records-json", required=True)
    args = ap.parse_args(argv[1:])
    try:
        records = _read_json(args.records_json)
        if args.cmd == "prepare":
            result = test_pilot_seed.prepare_records(records)
        else:
            result = test_pilot_seed.restore_baseline(records)
    except (OSError, ValueError) as exc:
        result = {"action": "park", "reason": "malformed inputs: %s" % exc}
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
