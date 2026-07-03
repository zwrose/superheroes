# plugins/superheroes/lib/build_state.py
"""Durable per-task build-state (FR-11): the KEYED record build_progress.reconcile reads — which
tasks have a PASSED per-task review, and the whole-branch final-review entry/clean state — plus the
pure Task-Id trailer parse (the reality-wins commit->task mapping, UFR-7). The append-only
events.jsonl journal is the audit log; THIS file is the keyed lookup the resume reconcile needs."""
import json
import os
import re

import control_plane

# Must match engine_adapter.TASK_ID_TRAILER (the sole committer for engine leaves).
_TASK_ID_LINE = re.compile(r"^Task-Id:\s*(\S+)\s*$", re.MULTILINE)


def extract_task_ids(body):
    """All Task-Id values anywhere in the commit message body (not trailer-block-strict)."""
    return _TASK_ID_LINE.findall(body or "")


def task_id_from_body(body, valid_ids):
    """Map one commit message body to its task id. Returns (task_id, unmapped).
    Fail-closed: no Task-Id, ambiguous distinct values, or id not in valid_ids -> unmapped."""
    ids = extract_task_ids(body)
    if not ids:
        return "", True
    distinct = set(ids)
    if len(distinct) > 1:
        return "", True
    tid = ids[0].strip()
    if tid and tid in set(valid_ids or []):
        return tid, False
    return "", True


def parse_trailers(rows, valid_ids):
    """rows: [(sha, commit_message_body)] for commits ABOVE the branch merge-base. Returns
    (committed_task_ids, unmapped_count): a trailer-less commit, an ambiguous one, or one whose id
    is not in valid_ids is unmapped (fail-closed — never absorbed)."""
    committed, unmapped = [], 0
    for _sha, body in rows:
        tid, is_unmapped = task_id_from_body(body, valid_ids)
        if is_unmapped:
            unmapped += 1
        else:
            committed.append(tid)
    return committed, unmapped


def state_path(cwd, work_item):
    return os.path.join(control_plane.paths(cwd, work_item)["issue_dir"], "build-state.json")


def read_state(path):
    if not os.path.isfile(path):
        return {"reviewed": {}, "final_review": None}
    try:
        with open(path, encoding="utf-8") as fh:
            obj = json.load(fh)
    except (OSError, ValueError):
        return {"reviewed": {}, "final_review": None}
    if not isinstance(obj, dict):
        return {"reviewed": {}, "final_review": None}
    obj.setdefault("reviewed", {})
    obj.setdefault("final_review", None)
    return obj


def set_reviewed(path, task_id):
    st = read_state(path)
    st["reviewed"][str(task_id)] = "passed"
    control_plane.atomic_write(path, json.dumps(st))
    return st


def set_final_review(path, clean):
    st = read_state(path)
    st["final_review"] = {"clean": bool(clean)}
    control_plane.atomic_write(path, json.dumps(st))
    return st
