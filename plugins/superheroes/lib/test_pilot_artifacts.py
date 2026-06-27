"""Render and publish test-pilot plan/result artifacts."""

import pr_comment


def _safe_text(value):
    return pr_comment.scrub(str(value or ""))


def _safe_notes(value):
    lines = []
    for line in str(value or "").splitlines():
        lowered = line.lower()
        if ("request headers" in lowered or lowered.startswith("cookie:")
                or lowered.startswith("set-cookie:")):
            continue
        lines.append(line)
    return _safe_text("\n".join(lines))


def _scenario_ids(record):
    ids = []
    for step in record.get("steps", []):
        if isinstance(step, dict):
            for sid in step.get("scenarioIds", []):
                if isinstance(sid, str) and sid not in ids:
                    ids.append(sid)
    return ids


def render_plan(records):
    lines = ["## Test-pilot plan", ""]
    for record in records or []:
        if not isinstance(record, dict):
            continue
        label = record.get("branch", "unknown")
        if record.get("slot"):
            label = "%s / %s" % (label, record["slot"])
        lines.extend(["### %s" % _safe_text(label), ""])
        ids = _scenario_ids(record)
        if ids:
            lines.append("Scenarios: %s" % ", ".join(_safe_text(sid) for sid in ids))
            lines.append("")
        rationale = record.get("coverageRationale") or record.get("coverage_rationale")
        if rationale:
            lines.extend(["Coverage: %s" % _safe_text(rationale), ""])
        for step in record.get("steps", []):
            if not isinstance(step, dict):
                continue
            sid_text = ", ".join(_safe_text(sid) for sid in step.get("scenarioIds", []))
            suffix = " (scenarios: %s)" % sid_text if sid_text else ""
            lines.append("- [ ] %s: %s%s" % (
                _safe_text(step.get("id")),
                _safe_text(step.get("instruction")),
                suffix,
            ))
            lines.append("  Expected: %s" % _safe_text(step.get("expected")))
    return pr_comment.scrub("\n".join(lines).strip() + "\n")


def render_results(status):
    lines = ["## Test-pilot results", ""]
    rationale = status.get("coverageRationale") or status.get("coverage_rationale")
    if rationale:
        lines.extend(["Coverage: %s" % _safe_text(rationale), ""])
    for record in status.get("records", []) or []:
        if not isinstance(record, dict):
            continue
        step_id = record.get("stepId") or record.get("step_id") or record.get("id")
        outcome = record.get("status") or record.get("result") or "unknown"
        lines.append("- %s: %s" % (_safe_text(step_id), _safe_text(outcome)))
        notes = record.get("notes") or record.get("diagnostics")
        if notes:
            safe = _safe_notes(notes)
            if safe:
                lines.append("  Notes: %s" % safe)
    fixes = status.get("fixes")
    if isinstance(fixes, list) and fixes:
        lines.extend(["", "Fixes:"])
        for fix in fixes:
            if not isinstance(fix, dict):
                continue
            sha = fix.get("sha") or fix.get("commit")
            summary = fix.get("summary") or fix.get("title") or ""
            lines.append("- %s %s" % (_safe_text(sha), _safe_text(summary)))
    return pr_comment.scrub("\n".join(lines).strip() + "\n")


def ensure_artifacts(pr_number, key, plan_body, results_body, poster=None,
                     fallback_writer=None, plans_dir=None):
    poster = poster or pr_comment
    fallback_writer = fallback_writer or pr_comment
    plans_dir = plans_dir or ".test-pilot"
    posting = {"ok": True}
    posted = {}
    failures = []
    for family, body in (("plan", plan_body), ("results", results_body)):
        try:
            posted[family] = poster.upsert(pr_number, family, key, body)
        except Exception as exc:
            failures.append("%s: %s" % (family, exc))
    if not failures:
        posting["posted"] = posted
        return {"ok": True, "posting": posting,
                "artifacts": {"plan": "pr-comment", "results": "pr-comment"}}
    fallback = {}
    try:
        for family, body in (("plan", plan_body), ("results", results_body)):
            path = fallback_writer.write_fallback(plans_dir, key, family, body)
            if path is None and hasattr(fallback_writer, "fallback_path"):
                path = fallback_writer.fallback_path(plans_dir, key, family)
            if not path:
                raise RuntimeError("%s fallback path missing after write" % family)
            fallback[family] = path
    except Exception as exc:
        return {"action": "park",
                "reason": "PR posting failed and fallback artifacts failed: %s" % exc,
                "posting": {"ok": False, "errors": failures}}
    return {"ok": True,
            "posting": {"ok": False, "errors": failures, "posted": posted},
            "fallback": fallback,
            "artifacts": {"plan": fallback["plan"], "results": fallback["results"],
                          "fallback": fallback}}
