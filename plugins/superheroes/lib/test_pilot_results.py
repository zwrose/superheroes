"""Aggregate browser-derived test-pilot results into scrubbed status records."""

import pr_comment


_BROWSER_SOURCES = {"browser", "playwright", "chrome-devtools", "devtools"}


def _park(reason):
    return {"action": "park", "reason": reason}


def _source(raw):
    return raw.get("source") or raw.get("evidenceSource") or raw.get("evidence_source")


def _is_browser_source(value):
    if not isinstance(value, str):
        return False
    return value.lower() in _BROWSER_SOURCES or value.lower().startswith("browser:")


def _limit(byte_limits, key, default):
    if not isinstance(byte_limits, dict):
        return default
    aliases = {
        "diagnostics": ("diagnostics", "diagnosticBytes", "diagnosticsBytes"),
        "renderedBytes": ("renderedBytes", "rendered", "total"),
    }
    value = None
    for candidate in aliases.get(key, (key,)):
        if candidate in byte_limits:
            value = byte_limits.get(candidate)
            break
    return value if isinstance(value, int) and value >= 0 else default


def _scrub(text, scrubber, limit):
    try:
        out = scrubber(str(text or ""))
    except Exception as exc:
        return None, "scrub failed: %s" % exc
    if len(out.encode("utf-8")) > limit:
        return None, "diagnostics exceed byte limit"
    return out, None


def aggregate_browser_results(raw_results, scrubber=None, byte_limits=None):
    scrubber = scrubber or pr_comment.scrub
    if not isinstance(raw_results, dict):
        return _park("browser results must be a JSON object")
    if not _is_browser_source(_source(raw_results)):
        return _park("browser-derived evidence/source is required")
    diagnostic_limit = _limit(byte_limits, "diagnostics", 20000)
    records = []
    for step in raw_results.get("steps", []) or raw_results.get("records", []) or []:
        if not isinstance(step, dict):
            continue
        notes, problem = _scrub(step.get("notes") or step.get("diagnostics") or "",
                                scrubber, diagnostic_limit)
        if problem:
            return _park(problem)
        step_id = step.get("id") or step.get("stepId") or step.get("step_id")
        records.append({
            "stepId": str(step_id),
            "status": step.get("status") or step.get("result") or "unknown",
            "notes": notes,
            "browserExecuted": True,
        })
    result = {
        "action": "aggregated",
        "source": _source(raw_results),
        "records": records,
        "coverageRationale": raw_results.get("coverageRationale")
                             or raw_results.get("coverage_rationale"),
    }
    fixes = []
    for fix in raw_results.get("fixes", []) or []:
        if isinstance(fix, dict):
            fixes.append({"sha": fix.get("sha") or fix.get("commit"),
                          "summary": pr_comment.scrub(str(fix.get("summary") or ""))})
    if fixes:
        result["fixes"] = fixes
    rendered_limit = _limit(byte_limits, "renderedBytes", 200000)
    if len(str(result).encode("utf-8")) > rendered_limit:
        return _park("rendered output exceeds byte limit")
    return result
