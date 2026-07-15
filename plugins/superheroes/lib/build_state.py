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

# #375: the reserved Task-Id for WHOLE-BRANCH final-review fix commits — the ones that serve no single
# task, so they carry no numeric task id. Both the fixer (build_phase.js: the native/default path's
# inline fix prompt + the external dispatch taskId that engine_adapter.commit_result stamps) and this
# gate (task_id_from_body below) key off this ONE value, so the spine's own final-review fix commits no
# longer fail the spine's own UFR-7 resume gate. This is the SSOT for the sentinel VALUE; the JS side
# pins itself equal to it via build_phase_finalreview_trailer_smoke.js so the two sides cannot drift
# apart into a self-rejecting resume again. It is deliberately NON-NUMERIC so it can never collide with
# a real task id.
FINAL_REVIEW_TASK_ID = "final-review"


def extract_task_ids(body):
    """All Task-Id values anywhere in the commit message body (not trailer-block-strict)."""
    return _TASK_ID_LINE.findall(body or "")


def task_id_from_body(body, valid_ids):
    """Map one commit message body to its task id. Returns (task_id, unmapped).
    Fail-closed: no Task-Id, ambiguous distinct values, or an id that is neither in valid_ids NOR the
    reserved final-review sentinel (#375) -> unmapped. Accepting the sentinel keeps UFR-7 MEANINGFUL —
    every above-base commit is still attributable to a known build activity (a numbered task or the
    whole-branch final review); it is NOT "accept any string" (an arbitrary hand-picked id still fails
    closed, so a stray/forged commit cannot sail through)."""
    ids = extract_task_ids(body)
    if not ids:
        return "", True
    distinct = set(ids)
    if len(distinct) > 1:
        return "", True
    tid = ids[0].strip()
    if tid and (tid in set(valid_ids or []) or tid == FINAL_REVIEW_TASK_ID):
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
