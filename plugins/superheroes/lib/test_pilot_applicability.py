"""Pure test-pilot applicability decision.

The helper is intentionally conservative: browser-relevant evidence sends work
to test-pilot, positive no-browser evidence may skip it, and uncertainty parks.
"""

import json

WEB_KEYS = {
    "user_facing",
    "userFacing",
    "browser",
    "route",
    "routes",
    "page",
    "pages",
    "frontend",
    "baseUrl",
    "base_url",
    "dev-server",
    "dev_server",
    "devServer",
    "runnable_web",
    "runnableWeb",
    "web",
}
PROFILE_WEB_KEYS = WEB_KEYS - {"baseUrl", "base_url"}

NO_BROWSER_KEYS = {
    "docs_only": "docs-only",
    "docsOnly": "docs-only",
    "cli_only": "CLI-only",
    "cliOnly": "CLI-only",
    "library_only": "library-only",
    "libraryOnly": "library-only",
    "internal_only": "internal-only",
    "internalOnly": "internal-only",
}

DOC_EXTS = {".md", ".mdx", ".rst", ".txt", ".adoc"}
CLI_PATH_PARTS = {"/cli/", "/commands/", "/bin/"}
LIB_PATH_PARTS = {"/lib/", "/src/lib/", "/pkg/"}
INTERNAL_PATH_PARTS = {"/internal/", "/private/"}
WEB_EXTS = {".html", ".css", ".jsx", ".tsx", ".vue", ".svelte"}
WEB_PATH_PARTS = {"/web/", "/frontend/", "/pages/", "/routes/", "/app/", "/public/"}


def _verdict(verdict, reason):
    return {"verdict": verdict, "reason": reason}


def _is_object(value):
    return value is None or isinstance(value, dict)


def _walk(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield key, nested
            yield from _walk(nested)
    elif isinstance(value, list):
        for nested in value:
            yield None, nested


def _truthy_signal(obj, keys):
    if not isinstance(obj, dict):
        return None
    for key, value in _walk(obj):
        if key in keys and value not in (False, None, "", [], {}):
            return key
    return None


def _files(diff):
    if not isinstance(diff, dict):
        return []
    files = diff.get("files") or diff.get("paths") or diff.get("changed_files")
    if isinstance(files, list) and all(isinstance(path, str) for path in files):
        return files
    return []


def _ext(path):
    base = path.rsplit("/", 1)[-1]
    if "." not in base:
        return ""
    return "." + base.rsplit(".", 1)[-1].lower()


def _docs_only(files):
    # A doc-extension check (DOC_EXTS) already covers README.md / CHANGELOG.md / CONTRIBUTING.md and
    # every other .md/.rst/.txt doc; the earlier per-name allowlist was dead (path.upper() never equals
    # a mixed-case "README.md") and redundant, so it was removed.
    return bool(files) and all(
        path.startswith(("docs/", "documentation/"))
        or _ext(path) in DOC_EXTS
        for path in files
    )


def _path_signal(files, parts, exts=None):
    exts = exts or set()
    for path in files:
        normalized = "/" + path.strip("/")
        if any(part in normalized for part in parts) or _ext(path) in exts:
            return True
    return False


def _web_path_signal(files):
    for path in files:
        normalized = "/" + path.strip("/")
        if any(part in normalized for part in WEB_PATH_PARTS):
            return True
        if _ext(path) in WEB_EXTS and not _path_signal([path], CLI_PATH_PARTS | LIB_PATH_PARTS | INTERNAL_PATH_PARTS):
            return True
    return False


def _plan_failed(plan_result):
    if plan_result is None:
        return None
    if not isinstance(plan_result, dict):
        return "malformed plan result"
    if plan_result.get("ok") is False or plan_result.get("status") in {"failed", "error"}:
        return str(plan_result.get("reason") or "plan derivation failed")
    return None


def _plan_empty_applicable(plan_result):
    if not isinstance(plan_result, dict):
        return False
    applicable = plan_result.get("applicable") is True or plan_result.get("verdict") == "applicable"
    steps = plan_result.get("steps")
    return applicable and isinstance(steps, list) and not steps


def _missing_required_setup(detectors, profile):
    if not isinstance(detectors, dict):
        required = []
    else:
        required = detectors.get("requires_setup") or detectors.get("required_setup") or []
    if isinstance(required, str):
        required = [required]
    if not isinstance(required, list):
        return []
    profile = profile if isinstance(profile, dict) else {}
    missing = []
    for key in required:
        if isinstance(key, str) and profile.get(key) in (None, "", [], {}):
            missing.append(key)
    return missing


def _coerce_json_object(value):
    """Defense-in-depth: parse a string that the courier may have stringified.

    If *value* is a string that JSON-parses to a dict or None, return the parsed
    result (so the decision can classify).  A non-parseable string, or a string
    that parses to something other than a dict/None, is returned unchanged so that
    the _is_object guard below can still park on it (fail-closed preserved).
    """
    if not isinstance(value, str):
        return value
    try:
        parsed = json.loads(value)
    except (ValueError, TypeError):
        return value  # non-parseable string -> stays a string -> _is_object parks
    if parsed is None or isinstance(parsed, dict):
        return parsed
    return value  # parsed to something else (list, int, …) -> unchanged -> parks


def decide(diff=None, detectors=None, profile=None, plan_result=None):
    """Return {"verdict": applicable|not_applicable|park, "reason": str}.

    All inputs are JSON-like dicts (or None). String inputs that JSON-parse to a
    dict or None are coerced (defense-in-depth against courier stringification —
    same posture as verify_gate).  A non-parseable string still parks (fail-closed).
    """
    diff = _coerce_json_object(diff)
    detectors = _coerce_json_object(detectors)
    profile = _coerce_json_object(profile)
    plan_result = _coerce_json_object(plan_result)
    if not all(_is_object(value) for value in (diff, detectors, profile, plan_result)):
        return _verdict("park", "malformed inputs")

    diff = diff or {}
    detectors = detectors or {}
    profile = profile or {}
    plan_failed = _plan_failed(plan_result)
    if plan_failed:
        return _verdict("park", plan_failed)
    if _plan_empty_applicable(plan_result):
        return _verdict("park", "empty applicable plan derivation")

    files = _files(diff)
    web_signal = (
        _truthy_signal(detectors, WEB_KEYS)
        or _truthy_signal(profile, PROFILE_WEB_KEYS)
        or _truthy_signal(plan_result, WEB_KEYS)
    )
    if not web_signal and _web_path_signal(files):
        web_signal = "frontend path"

    if web_signal:
        missing = _missing_required_setup(detectors, profile)
        if missing:
            return _verdict("park", "missing required setup: " + ", ".join(missing))
        return _verdict("applicable", "browser/user-facing signal: %s" % web_signal)

    for key, label in NO_BROWSER_KEYS.items():
        if detectors.get(key) is True:
            return _verdict("not_applicable", label + " change with no browser signal")

    if _docs_only(files):
        return _verdict("not_applicable", "docs-only change with no browser signal")
    if _path_signal(files, CLI_PATH_PARTS):
        return _verdict("not_applicable", "CLI-only change with no browser signal")
    if _path_signal(files, LIB_PATH_PARTS):
        return _verdict("not_applicable", "library-only change with no browser signal")
    if _path_signal(files, INTERNAL_PATH_PARTS):
        return _verdict("not_applicable", "internal-only change with no browser signal")

    return _verdict("park", "uncertain applicability")
