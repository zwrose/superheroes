#!/usr/bin/env python3
"""Ensure kind:machinery and kind:product labels exist on a consuming repository.

Read-only by default (`report`). `--apply` creates only labels that are missing.
Every `gh` call passes an explicit `--repo`; the helper never lets `gh` infer the
repository from the current working directory."""
import argparse
import json
import shutil
import subprocess
import sys

GH_TIMEOUT = 120

KIND_LABELS = (
    {
        "name": "kind:machinery",
        "color": "5319E7",
        "description": (
            "Work whose subject is the development process rather than "
            "the product's behavior."
        ),
    },
    {
        "name": "kind:product",
        "color": "0E8A16",
        "description": "Work whose subject is the product's own behavior.",
    },
)

KIND_LABEL_NAMES = tuple(label["name"] for label in KIND_LABELS)

_ALREADY_EXISTS = "already exists"


def _label_by_name(name):
    for label in KIND_LABELS:
        if label["name"] == name:
            return label
    return None


def _gh_not_found_reason():
    return "gh not on PATH"


def _gh_auth_argv():
    return ["gh", "auth", "status"]


def _gh_label_list_argv(repo):
    return [
        "gh",
        "label",
        "list",
        "--repo",
        repo,
        "--limit",
        "200",
        "--json",
        "name,color,description",
    ]


def _gh_label_create_argv(repo, label):
    return [
        "gh",
        "label",
        "create",
        label["name"],
        "--repo",
        repo,
        "--color",
        label["color"],
        "--description",
        label["description"],
    ]


def _run(argv, run, timeout=GH_TIMEOUT):
    try:
        return run(argv, capture_output=True, text=True, timeout=timeout), None
    except subprocess.TimeoutExpired:
        return None, "gh call timed out"
    except FileNotFoundError:
        return None, _gh_not_found_reason()
    except OSError as exc:
        return None, str(exc)


def _stderr(proc):
    return ((proc.stdout or "") + (proc.stderr or "")).strip()


def _is_repo_unresolved(stderr):
    return "Could not resolve to a Repository" in stderr


def _is_unauthenticated(stderr):
    lowered = stderr.lower()
    return (
        "auth" in lowered
        or "login" in lowered
        or "not logged in" in lowered
        or "token" in lowered
    )


def _parse_label_list(stdout):
    text = (stdout or "").strip()
    if not text:
        return [], None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if parsed is not None:
        if not isinstance(parsed, list):
            return None, "gh label list returned JSON that is not a list"
        entries = parsed
    else:
        entries = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                return None, "gh label list returned output that is not JSON"
            entries.append(item)
    names = []
    for entry in entries:
        if not isinstance(entry, dict):
            return None, "gh label list entry is not an object"
        name = entry.get("name")
        if not name:
            return None, "gh label list entry has no name"
        names.append(name)
    return names, None


def _present_and_missing(label_names):
    present = [name for name in KIND_LABEL_NAMES if name in label_names]
    missing = [name for name in KIND_LABEL_NAMES if name not in label_names]
    return present, missing


def _read_labels(repo, run):
    proc, err = _run(_gh_label_list_argv(repo), run)
    if proc is None:
        return None, err
    if proc.returncode != 0:
        detail = _stderr(proc)
        if _is_repo_unresolved(detail):
            return None, detail
        if _is_unauthenticated(detail):
            return None, detail
        return None, detail or "gh label list failed"
    names, parse_err = _parse_label_list(proc.stdout)
    if parse_err:
        return None, parse_err
    return names, None


def _create_label(repo, label, run):
    proc, err = _run(_gh_label_create_argv(repo, label), run)
    if proc is None:
        return False, err
    if proc.returncode == 0:
        return True, None
    detail = _stderr(proc)
    if _ALREADY_EXISTS in detail:
        return False, None
    return False, detail or "gh label create failed"


def ensure_kind_labels(repo, *, apply=False, run=None):
    """Return the label report dict. Never raises."""
    if run is None:
        run = subprocess.run
    base = {
        "ok": False,
        "repo": repo,
        "present": [],
        "missing": list(KIND_LABEL_NAMES),
        "created": [],
        "reason": None,
    }
    if not shutil.which("gh"):
        base["reason"] = _gh_not_found_reason()
        return base
    auth_proc, auth_err = _run(_gh_auth_argv(), run)
    if auth_proc is None:
        base["reason"] = auth_err
        return base
    if auth_proc.returncode != 0:
        base["reason"] = _stderr(auth_proc) or "gh not authenticated"
        return base
    label_names, read_err = _read_labels(repo, run)
    if read_err:
        base["reason"] = read_err
        return base
    present, missing = _present_and_missing(label_names)
    created = []
    create_errors = []
    if apply:
        for name in missing:
            label = _label_by_name(name)
            if label is None:
                continue
            did_create, create_err = _create_label(repo, label, run)
            if did_create:
                created.append(name)
            elif create_err:
                create_errors.append("%s: %s" % (name, create_err))
        label_names, read_err = _read_labels(repo, run)
        if read_err:
            base.update(
                {
                    "present": present,
                    "missing": missing,
                    "created": created,
                    "reason": read_err,
                }
            )
            return base
        present, missing = _present_and_missing(label_names)
    result = {
        "ok": not create_errors,
        "repo": repo,
        "present": present,
        "missing": missing,
        "created": created,
        "reason": "; ".join(create_errors) if create_errors else None,
    }
    if not create_errors:
        result["ok"] = True
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kind_labels")
    ap.add_argument(
        "--repo",
        required=True,
        help="Repository selector in HOST/OWNER/REPO form",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Create only missing kind labels, then re-read",
    )
    args = ap.parse_args(argv)
    result = ensure_kind_labels(args.repo, apply=args.apply)
    sys.stdout.write(json.dumps(result) + "\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
