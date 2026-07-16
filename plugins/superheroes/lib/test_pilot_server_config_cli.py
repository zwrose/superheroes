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


def _jsonable(value):
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()
                if key != "_proc"}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def main(argv):
    ap = argparse.ArgumentParser(description="test-pilot server context resolver")
    sub = ap.add_subparsers(dest="cmd", required=True)
    resolve = sub.add_parser("resolve")
    resolve.add_argument("--profile-json", required=True)
    resolve.add_argument("--detection-json", required=True)
    resolve.add_argument("--work-item", required=True)
    resolve.add_argument("--worktree", default=None,
                         help="Launch worktree. Its .env.local PORT wins over the band "
                              "default so the readiness probe follows the real bind (#451).")
    launch = sub.add_parser("launch")
    launch.add_argument("--context-json", required=True)
    launch.add_argument("--worktree", default=None,
                        help="Launch worktree. Overrides the context's embedded cwd for "
                             "starting the dev server.")
    finish = sub.add_parser("finish")
    finish.add_argument("--context-json", required=True)
    finish.add_argument("--outcome-json", required=True)
    args = ap.parse_args(argv[1:])

    if args.cmd == "resolve":
        try:
            profile = _read_json(args.profile_json)
            detection = _read_json(args.detection_json)
            result = test_pilot_server_config.resolve(profile, detection, args.work_item, cwd=args.worktree)
        except (OSError, ValueError) as exc:
            result = {"schemaVersion": test_pilot_server_config.SCHEMA_VERSION,
                      "verdict": "park", "reason": "malformed inputs: %s" % exc,
                      "workItem": args.work_item}
        sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
        return 0
    if args.cmd == "launch":
        try:
            context = _read_json(args.context_json)
            launch_cwd = args.worktree or (context.get("cwd") if isinstance(context, dict) else None)
            result = test_pilot_server_config.launch(context, cwd=launch_cwd)
        except (OSError, ValueError) as exc:
            result = {"schemaVersion": test_pilot_server_config.SCHEMA_VERSION,
                      "verdict": "park", "reason": "malformed inputs: %s" % exc}
        sys.stdout.write(json.dumps(_jsonable(result), sort_keys=True) + "\n")
        return 0
    if args.cmd == "finish":
        try:
            context = _read_json(args.context_json)
            outcome = _read_json(args.outcome_json)
            result = test_pilot_server_config.finish(context, outcome)
        except (OSError, ValueError) as exc:
            result = {"action": "park", "reason": "malformed inputs: %s" % exc}
        sys.stdout.write(json.dumps(_jsonable(result), sort_keys=True) + "\n")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
