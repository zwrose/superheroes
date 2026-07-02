#!/usr/bin/env python3
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import idempotent_write
import test_pilot_status


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _normalized(status):
    data = dict(status)
    data.setdefault("schemaVersion", test_pilot_status.SCHEMA_VERSION)
    return data


def _reflects(path, intended):
    try:
        current = test_pilot_status.read(path)
    except (OSError, ValueError) as exc:
        return None, {"read_back": False, "error": str(exc)}
    read_back = current == _normalized(intended)
    return read_back, {"read_back": read_back, "head": current.get("head"), "status_path": path}


def _apply(path, intended):
    written = test_pilot_status.write(path, _normalized(intended))
    reflects, detail = _reflects(path, intended)
    detail["head"] = written.get("head")
    detail["status_path"] = path
    return reflects is True, detail


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
        except (OSError, ValueError) as exc:
            result = {"ok": False, "read_back": False, "reason": str(exc)}
            sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
            return 0
        key = "test-pilot-status:%s:%s:%s" % (
            args.work_item,
            data.get("head"),
            data.get("verdict"),
        )
        result = idempotent_write.idempotent_apply(
            key,
            lambda: _reflects(path, data),
            lambda: _apply(path, data),
        )
        detail = result.get("detail") or {}
        out = {
            "ok": bool(result.get("ok")),
            "already": bool(result.get("already")),
            "read_back": bool(detail.get("read_back")),
            "status_path": detail.get("status_path") or path,
            "head": detail.get("head") or data.get("head"),
        }
        if not out["ok"]:
            out["reason"] = result.get("reason")
        sys.stdout.write(json.dumps(out, sort_keys=True) + "\n")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
