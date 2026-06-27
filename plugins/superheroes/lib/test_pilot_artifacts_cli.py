#!/usr/bin/env python3
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_pilot_artifacts


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main(argv):
    ap = argparse.ArgumentParser(description="test-pilot artifact helper")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ensure = sub.add_parser("ensure")
    ensure.add_argument("--plan-json", required=True)
    ensure.add_argument("--results-json", required=True)
    ensure.add_argument("--pr", required=True)
    ensure.add_argument("--key")
    args = ap.parse_args(argv[1:])
    if args.cmd == "ensure":
        try:
            plan = _read_json(args.plan_json)
            results = _read_json(args.results_json)
            plan_key = plan.get("key") if isinstance(plan, dict) else None
            results_key = results.get("key") if isinstance(results, dict) else None
            key = args.key or plan_key or results_key
            if not key:
                raise ValueError("artifact key missing")
            records = plan.get("records", plan) if isinstance(plan, dict) else plan
            plan_body = test_pilot_artifacts.render_plan(records)
            results_body = test_pilot_artifacts.render_results(results)
            result = test_pilot_artifacts.ensure_artifacts(
                args.pr, key, plan_body, results_body)
        except (OSError, ValueError) as exc:
            result = {"action": "park", "reason": "malformed inputs: %s" % exc}
        sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
