"""Machine-readable terminal-result contract for review-code's auto-fix loop.

review-code writes its final loop_state decision here (when invoked with
--result-file) so a CALLER (Workhorse ②) can branch deterministically instead of
parsing prose — closing the loop-skipping gap at the skill boundary. The reader
fails CLOSED: a missing or garbled result reads as 'halt' (GATE), never as clean.
"""
import json
import os
import sys

_GATE = {"action": "halt", "round": 0, "reason": "result missing/unreadable (fail-closed)"}


def write_result(path, action, rnd, reason=""):
    payload = {"action": action, "round": int(rnd), "reason": reason or ""}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(payload))
    os.replace(tmp, path)
    return payload


def read_result(path):
    """Return the terminal result dict. Missing/garbled/invalid -> the GATE
    sentinel (action 'halt'), so a caller never mistakes absence for clean."""
    try:
        with open(path, encoding="utf-8") as fh:
            obj = json.load(fh)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(_GATE)
    if not isinstance(obj, dict) or obj.get("action") not in \
            ("review", "exit_clean", "exit_skipped", "halt"):
        return dict(_GATE)
    return obj


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description="review-code terminal-result writer")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write")
    w.add_argument("--path", required=True)
    w.add_argument("--action", required=True)
    w.add_argument("--round", type=int, required=True)
    w.add_argument("--reason", default="")
    args = ap.parse_args(argv[1:])
    write_result(args.path, args.action, args.round, args.reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
