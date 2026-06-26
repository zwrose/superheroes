"""Pure browser retry/fix-loop decider for test-pilot."""

import re

from circuit_breaker import normalize_title


MAX_BROWSER_FIX_BATCHES = 3

_PATHISH = re.compile(r"(?:/private)?/tmp/\S+|/[\w./-]+(?::\d+)?")
_LINE = re.compile(r":\d+\b")


def _fix_batch(entry):
    return isinstance(entry, dict) and entry.get("type") in {
        "browser_fix_batch",
        "fix_batch",
    }


def _fix_batches(history):
    if not isinstance(history, list):
        return []
    return [entry for entry in history if _fix_batch(entry)]


def _steps(pass_result):
    if not isinstance(pass_result, dict):
        return []
    steps = pass_result.get("steps")
    if isinstance(steps, list):
        return steps
    records = pass_result.get("records")
    return records if isinstance(records, list) else []


def _step_id(step):
    if not isinstance(step, dict):
        return None
    value = step.get("id") or step.get("stepId") or step.get("step_id")
    return str(value) if value not in (None, "") else None


def _failed_steps(pass_result):
    failed = []
    for step in _steps(pass_result):
        if not isinstance(step, dict):
            continue
        status = step.get("status") or step.get("result")
        if status in {"failed", "fail"} and _step_id(step):
            failed.append(step)
    return failed


def _app_bug(step):
    return (step.get("failureType") or step.get("failure_type") or step.get("kind")) in {
        "app_bug",
        "app-bug",
        "application",
        None,
    }


def _failed_step_ids(pass_result):
    return [_step_id(step) for step in _failed_steps(pass_result)]


def _summary_for_failures(failed):
    ids = [_step_id(step) for step in failed]
    return "Fix browser app failures: " + ", ".join(ids)


def _scrub_summary(summary):
    value = str(summary or "")
    value = _PATHISH.sub(" ", value)
    value = _LINE.sub(" ", value)
    return normalize_title(value)


def _status_map(value):
    return value if isinstance(value, dict) else {}


def _made_progress(batch):
    before = _status_map(batch.get("before"))
    after = _status_map(batch.get("after"))
    for step_id, before_status in before.items():
        if before_status in {"failed", "fail"} and after.get(step_id) in {"passed", "pass"}:
            return True
    return False


def _last_two_same_without_progress(batches):
    if len(batches) < 2:
        return None
    prev, latest = batches[-2], batches[-1]
    prev_summary = _scrub_summary(prev.get("summary"))
    latest_summary = _scrub_summary(latest.get("summary"))
    if (
        prev_summary
        and prev_summary == latest_summary
        and not _made_progress(prev)
        and not _made_progress(latest)
    ):
        return latest_summary
    return None


def _affected_step_ids(changed_files, dependency_map):
    if not isinstance(dependency_map, dict):
        return None
    affected = set()
    for path in changed_files or []:
        mapped = dependency_map.get(path)
        if not isinstance(mapped, list):
            return None
        for step_id in mapped:
            if step_id not in (None, ""):
                affected.add(str(step_id))
    return sorted(affected)


def _rerun_decision(pass_result, changed_files, dependency_map):
    failed_ids = _failed_step_ids(pass_result)
    affected_ids = _affected_step_ids(changed_files, dependency_map)
    if affected_ids is None:
        return {"action": "rerun_all", "failedStepIds": failed_ids}
    step_ids = sorted(set(failed_ids) | set(affected_ids))
    return {
        "action": "rerun_subset",
        "stepIds": step_ids,
        "failedStepIds": failed_ids,
        "affectedStepIds": affected_ids,
    }


def decide(pass_result, history, changed_files=None, dependency_map=None):
    batches = _fix_batches(history)
    failed = _failed_steps(pass_result)

    if changed_files is not None and batches:
        return _rerun_decision(pass_result, changed_files, dependency_map)

    if failed and len(batches) >= MAX_BROWSER_FIX_BATCHES:
        return {
            "action": "park_cap_reached",
            "reason": "reached 3 browser fix batches with failed browser steps remaining",
        }

    no_progress = _last_two_same_without_progress(batches)
    if failed and no_progress:
        return {
            "action": "park_no_progress",
            "reason": "two consecutive browser fix batches made no progress: %s" % no_progress,
        }

    app_failures = [step for step in failed if _app_bug(step)]
    if app_failures:
        return {
            "action": "fix_batch",
            "failedStepIds": [_step_id(step) for step in app_failures],
            "summary": _summary_for_failures(app_failures),
        }

    if failed:
        return {
            "action": "park_unclassified_failure",
            "reason": "one or more browser failures are not app-bug failures",
        }

    return {"action": "passed"}
