#!/usr/bin/env python3
"""PR size counters: tripwire vs bar, with whole-file deletions listed (#1447). stdlib only."""
import argparse
import json
import subprocess
import sys


def is_test_path(path):
    """True when ``path`` has a ``tests`` directory component."""
    return "tests" in path.replace("\\", "/").split("/")


def _normalized_path(path):
    return "/" + path.replace("\\", "/").strip("/") + "/"


def is_bar_exempt_path(path):
    """True when additions must not count toward the 300/600 bars (review-discipline § Size)."""
    norm = _normalized_path(path)
    if "/lib/tests/bite_proofs/" in norm:
        return True
    if norm.endswith("/skills/workhorse/reference/dispatch-entry.md/"):
        return True
    if "/lib/tests/fixtures/round_certification_generated/" in norm:
        return True
    return False


def count(numstat_rows, deleted_paths):
    """Pure size count from parsed numstat rows and deleted path names."""
    tripwire = 0
    bar = 0
    deleted_files = []
    binary = []

    for added, deleted, path in numstat_rows:
        if is_test_path(path):
            continue
        if added is None or deleted is None:
            binary.append(path)
            continue
        if path in deleted_paths and added == 0:
            deleted_files.append({"path": path, "lines": deleted})
            continue
        tripwire += added + deleted
        if not is_bar_exempt_path(path):
            bar += added

    deleted_files.sort(key=lambda item: item["path"])
    binary.sort()
    return {
        "tripwireCount": tripwire,
        "barCount": bar,
        "deletedFiles": deleted_files,
        "binary": binary,
    }


def _parse_numstat_z(raw_bytes):
    text = raw_bytes.decode("utf-8", errors="surrogateescape")
    fields = text.split("\0")
    while fields and fields[-1] == "":
        fields.pop()
    rows = []
    i = 0
    n = len(fields)
    while i < n:
        row = fields[i]
        parts = row.split("\t")
        if len(parts) < 2:
            i += 1
            continue
        a, d = parts[0], parts[1]
        if a == "-" or d == "-":
            added, deleted = None, None
        else:
            try:
                added, deleted = int(a), int(d)
            except ValueError:
                i += 1
                continue
        if len(parts) >= 3 and parts[2] != "":
            path = parts[2]
            i += 1
        elif len(parts) >= 3 and parts[2] == "":
            if i + 2 < n:
                path = fields[i + 2]
                i += 3
            else:
                i += 1
                continue
        else:
            i += 1
            continue
        rows.append((added, deleted, path))
    return rows


def _parse_deleted_paths(raw_bytes):
    text = raw_bytes.decode("utf-8", errors="surrogateescape")
    fields = text.split("\0")
    while fields and fields[-1] == "":
        fields.pop()
    deleted = set()
    i = 0
    while i < len(fields):
        if fields[i] == "D" and i + 1 < len(fields):
            deleted.add(fields[i + 1])
            i += 2
        else:
            i += 1
    return deleted


def _git_failed(stderr_bytes):
    line = stderr_bytes.decode("utf-8", errors="replace").splitlines()
    return {"ok": False, "reason": "git-failed", "detail": line[0] if line else ""}


def collect(repo_root, base, head="HEAD"):
    """Run git diffs between ``base`` and ``head`` and return size JSON."""
    numstat = subprocess.run(
        ["git", "-C", repo_root, "diff", "--numstat", "-z", "-M", base, head],
        capture_output=True,
    )
    if numstat.returncode != 0:
        return _git_failed(numstat.stderr)
    status = subprocess.run(
        [
            "git",
            "-C",
            repo_root,
            "diff",
            "--name-status",
            "-z",
            "-M",
            "--diff-filter=D",
            base,
            head,
        ],
        capture_output=True,
    )
    if status.returncode != 0:
        return _git_failed(status.stderr)

    rows = _parse_numstat_z(numstat.stdout)
    deleted_paths = _parse_deleted_paths(status.stdout)
    result = count(rows, deleted_paths)
    result["base"] = base
    result["head"] = head
    result["ok"] = True
    return result


def _emit(result):
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")


def main(argv):
    ap = argparse.ArgumentParser(description="PR size tripwire/bar counters")
    sub = ap.add_subparsers(dest="cmd", required=True)
    cnt = sub.add_parser("count")
    cnt.add_argument("--base", required=True)
    cnt.add_argument("--head", default="HEAD")
    cnt.add_argument("--repo-root", default=".")
    args = ap.parse_args(argv[1:])
    if args.cmd == "count":
        result = collect(args.repo_root, args.base, args.head)
        _emit(result)
        return 0 if result.get("ok") else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
