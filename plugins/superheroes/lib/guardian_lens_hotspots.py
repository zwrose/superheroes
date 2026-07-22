#!/usr/bin/env python3
# plugins/superheroes/lib/guardian_lens_hotspots.py
"""Guardian hotspots lens — size-normalized churn × max function complexity.

Stdlib-only. Collectors (radon / lizard) are optional external tools resolved via
guardian_tools; this module never installs them. Churn is always size-normalized
(relativeChurn); raw changed-line totals are provenance only, never the ranking key.
Shallow clones are reported honestly — never unshallowed.
"""
import csv
import io
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import guardian_lens  # noqa: E402
import guardian_tools  # noqa: E402

MIN_CCN = 10
TOP_N = 25
DEFAULT_WINDOW = "90 days"
SCHEMA_VERSION = 1
# Per-file radon errors beyond this (or all files of a language) escalate to LensDegraded.
PER_FILE_ERROR_DEGRADE_THRESHOLD = 3

PY_EXTS = (".py",)
JS_EXTS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")

VALIDATION_GUIDANCE = (
    "Validate each hotspot candidate against CLAUDE.md, CONVENTIONS, calibration, and "
    "spec'd designs. Accept only when the measured evidence — this file's relative churn, "
    "its max function complexity, and the observed git window — makes the finding "
    "actionable for this repo. Reject rule-catalog severity tiers and anything not "
    "grounded in those measurements. When historyTruncated is true, treat the observed "
    "window (not the requested window) as the evidence bound."
)

CONSEQUENCE_TEMPLATE = (
    "Write one plain sentence citing only measured evidence: this file's relative churn, "
    "its max function complexity (and worst function), and the observed window "
    "(requestedSince / observedSince / commitsObserved). If historyTruncated is true, "
    "the sentence must say the history was truncated and quote the observed window. "
    "Never cite rule-catalog severity tiers."
)


def parse_numstat(text):
    """Parse `git log --numstat --no-renames --format=` output.

    Skips binary rows (add/delete == '-') and any path containing '=>' or '{' so
    brace-rename compact syntax can never be misattributed even if --no-renames is
    omitted by a caller.
    """
    out = {}
    if not text:
        return out
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        add_s, del_s, path = parts[0], parts[1], parts[2]
        if add_s == "-" or del_s == "-":
            continue
        if "=>" in path or "{" in path:
            continue
        try:
            added = int(add_s)
            deleted = int(del_s)
        except ValueError:
            continue
        entry = out.setdefault(path, {"added": 0, "deleted": 0})
        entry["added"] += added
        entry["deleted"] += deleted
    return out


def _iter_radon_callables(entries):
    """Yield function/method entries, recursively flattening methods + closures.

    Class aggregates are never scored — only nested callables. Closures nested under
    functions/methods are included so a high-CCN nested callable is not missed.
    """
    if not isinstance(entries, list):
        return
    for e in entries:
        if not isinstance(e, dict):
            continue
        if "error" in e:
            continue
        methods = e.get("methods") if isinstance(e.get("methods"), list) else []
        closures = e.get("closures") if isinstance(e.get("closures"), list) else []
        if e.get("type") == "class":
            yield from _iter_radon_callables(methods)
            yield from _iter_radon_callables(closures)
            continue
        if "complexity" in e:
            yield e
        yield from _iter_radon_callables(methods)
        yield from _iter_radon_callables(closures)


def parse_radon_json(text):
    """radon `cc -s -j` → ({path: {maxFunctionCCN, worstFunction}}, error_paths).

    Raises LensDegraded when the top-level shape is not a dict of path → list
    (a bare `[]` or non-dict must not erase the baseline as a quiet empty result).
    Paths whose entry list contains an 'error' key are listed in error_paths and
    omitted from the complexity map — callers must carry prior digest entries forward.
    Class aggregates are skipped; methods and closures are flattened recursively.
    """
    data = json.loads(text) if isinstance(text, str) else text
    if not isinstance(data, dict):
        raise guardian_lens.LensDegraded(
            "radon output contract mismatch: expected a JSON object of path → list, "
            "got %s" % type(data).__name__)
    result = {}
    error_paths = []
    for path, entries in data.items():
        if not isinstance(entries, list):
            raise guardian_lens.LensDegraded(
                "radon output contract mismatch: path %r value must be a list, got %s"
                % (path, type(entries).__name__))
        if any(isinstance(e, dict) and "error" in e for e in entries):
            error_paths.append(path)
            continue
        best = None
        for e in _iter_radon_callables(entries):
            try:
                ccn = int(e["complexity"])
            except (TypeError, ValueError, KeyError):
                continue
            if best is None or ccn > best[0]:
                best = (ccn, e.get("name") or "?", int(e.get("lineno") or 0))
        if best is not None:
            result[path] = {
                "maxFunctionCCN": best[0],
                "worstFunction": {"name": best[1], "line": best[2]},
            }
    return result, error_paths


def parse_lizard_csv(text):
    """lizard `--csv` (no header). Columns verified against captured fixture:
    0=nloc, 1=CCN, 2=token_count, 3=param_count, 4=length,
    5=name@start-end@file, 6=file, 7=function_name, 8=long_signature,
    9=start_line, 10=end_line.
    """
    result = {}
    if not text:
        return result
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if len(row) < 8:
            continue
        try:
            ccn = int(row[1])
        except (TypeError, ValueError):
            continue
        path = row[6].strip()
        name = row[7].strip() if len(row) > 7 else "?"
        try:
            line = int(row[9]) if len(row) > 9 else 0
        except (TypeError, ValueError):
            line = 0
        if not path:
            continue
        cur = result.get(path)
        if cur is None or ccn > cur["maxFunctionCCN"]:
            result[path] = {
                "maxFunctionCCN": ccn,
                "worstFunction": {"name": name or "?", "line": line},
            }
    return result


def relative_churn(added, deleted, current_lines):
    if not current_lines:
        return None
    return (added + deleted) / float(current_lines)


def build_candidate(path, added, deleted, current_lines, max_ccn, worst, window):
    rel = relative_churn(added, deleted, current_lines)
    if rel is None:
        return None
    score = round(rel * max_ccn, 4)
    raw = added + deleted
    cand = {
        "id": "hotspots:%s" % path,
        "path": path,
        "relativeChurn": round(rel, 4),
        "hotspotScore": score,
        "metric": score,
        "maxFunctionCCN": max_ccn,
        "worstFunction": dict(worst),
        "currentFileLines": current_lines,
        # provenance only — never the ranking key
        "addedLines": added,
        "deletedLines": deleted,
        "rawChurn": raw,
        "historyTruncated": window["historyTruncated"],
        "requestedSince": window["requestedSince"],
        "observedSince": window["observedSince"],
        "commitsObserved": window["commitsObserved"],
    }
    return cand


def rank_and_cap(candidates, top_n=TOP_N):
    ranked = sorted(candidates, key=lambda c: (-c["hotspotScore"], c["path"]))
    return ranked[:top_n]


def apply_cap(candidates, top_n=TOP_N, always_include_ccn=None):
    """Top-N by hotspotScore, unioned with every candidate at/above absolute CCN."""
    before = len(candidates)
    capped = rank_and_cap(candidates, top_n=top_n)
    union_added = 0
    if always_include_ccn is not None:
        seen = {c["id"] for c in capped}
        extras = []
        for c in candidates:
            if c["id"] in seen:
                continue
            try:
                ccn = int(c.get("maxFunctionCCN") or 0)
            except (TypeError, ValueError):
                continue
            if ccn >= always_include_ccn:
                extras.append(c)
                seen.add(c["id"])
        extras.sort(key=lambda c: (-c["hotspotScore"], c["path"]))
        capped = list(capped) + extras
        union_added = len(extras)
    return capped, {
        "candidatesBeforeCap": before,
        "capApplied": min(before, top_n),
        "redLineUnionAdded": union_added,
    }


def _run(ctx, argv, timeout=60):
    runner = ctx.get("run") or subprocess.run
    return runner(
        argv, capture_output=True, text=True, cwd=ctx["cwd"], timeout=timeout,
    )


def _git(ctx, *args, timeout=30):
    return _run(ctx, ["git", "-C", ctx["cwd"], *args], timeout=timeout)


def _count_lines(cwd, relpath):
    path = os.path.join(cwd, relpath)
    try:
        with open(path, "rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def tracked_existing_files(cwd, run=None):
    """Repo-relative paths that are both `git ls-files` tracked and present on disk.

    Raises LensDegraded on git failure — an empty set must never overwrite a baseline.
    """
    ctx = {"cwd": cwd, "run": run}
    proc = _git(ctx, "ls-files", "-z")
    if getattr(proc, "returncode", 1) != 0:
        raise guardian_lens.LensDegraded(
            "git ls-files failed (exit %s)" % getattr(proc, "returncode", "?"))
    out = set()
    for raw in (proc.stdout or "").split("\0"):
        if not raw:
            continue
        # Never accept brace-rename garbage into the tracked set
        if "=>" in raw or "{" in raw:
            continue
        full = os.path.join(cwd, raw)
        if os.path.isfile(full):
            out.add(raw)
    return out


def _requested_since_iso(window_spec):
    """Best-effort ISO date for a git --since spec like '90 days'."""
    now = datetime.now(timezone.utc)
    spec = (window_spec or DEFAULT_WINDOW).strip().lower()
    days = 90
    parts = spec.split()
    if parts and parts[0].isdigit():
        days = int(parts[0])
    return (now - timedelta(days=days)).date().isoformat()


def observe_window(cwd, since=DEFAULT_WINDOW, run=None):
    """Honest window accounting — never fetch/--unshallow.

    Raises LensDegraded on git failure so a broken probe cannot look like a quiet repo.
    """
    ctx = {"cwd": cwd, "run": run}
    requested = _requested_since_iso(since)
    shallow_proc = _git(ctx, "rev-parse", "--is-shallow-repository")
    if getattr(shallow_proc, "returncode", 1) != 0:
        raise guardian_lens.LensDegraded(
            "git rev-parse --is-shallow-repository failed (exit %s)"
            % getattr(shallow_proc, "returncode", "?"))
    shallow_txt = (getattr(shallow_proc, "stdout", "") or "").strip().lower()
    history_truncated = shallow_txt == "true"

    log_proc = _git(
        ctx, "log", "--since=%s" % since, "--format=%cI", "--reverse",
    )
    if getattr(log_proc, "returncode", 1) != 0:
        raise guardian_lens.LensDegraded(
            "git log failed (exit %s)" % getattr(log_proc, "returncode", "?"))
    dates = [
        line.strip() for line in (getattr(log_proc, "stdout", "") or "").splitlines()
        if line.strip()
    ]
    commits_observed = len(dates)
    if dates:
        observed = dates[0][:10]  # YYYY-MM-DD
    else:
        observed = requested
    return {
        "historyTruncated": history_truncated,
        "requestedSince": requested,
        "observedSince": observed,
        "commitsObserved": commits_observed,
        "sinceSpec": since,
    }


def _collect_churn(ctx, since):
    proc = _git(
        ctx, "log", "--since=%s" % since, "--numstat", "--no-renames", "--format=",
        timeout=60,
    )
    if getattr(proc, "returncode", 1) != 0:
        raise guardian_lens.LensDegraded(
            "git log --numstat failed (exit %s)" % getattr(proc, "returncode", "?"))
    text = getattr(proc, "stdout", "") or ""
    return parse_numstat(text)


def _paths_with_ext(tracked, exts):
    return sorted(p for p in tracked if p.lower().endswith(exts))


def _abs_paths(cwd, paths):
    """Join repo-relative paths onto cwd and guarantee absolute results.

    Callers that pass a relative cwd (e.g. ".") still get process-CWD-resolved
    absolute paths — never './foo.py' strings that break an isolated temp cwd.
    """
    out = []
    for p in paths:
        joined = p if os.path.isabs(p) else os.path.join(cwd, p)
        abs_p = os.path.abspath(joined)
        if not os.path.isabs(abs_p):
            raise ValueError(
                "hotspots._abs_paths expected an absolute path, got %r (cwd=%r, path=%r)"
                % (abs_p, cwd, p)
            )
        out.append(abs_p)
    return out


def _join_anomaly(coverage, py_paths, js_paths, churn, complexity, joined_count):
    """Detect churn×complexity join failure that would otherwise look quietly clean.

    When a language was marked collected, tracked files for that language have churn,
    and yet zero candidates emerge because complexity keys never land on those tracked
    paths, the result is an internal inconsistency — not a healthy quiet repo.
    """
    if joined_count:
        return None
    langs = []
    tracked_for = []
    if coverage.get("python") == "collected" and py_paths:
        langs.append("python")
        tracked_for.extend(py_paths)
    if coverage.get("javascript") == "collected" and js_paths:
        langs.append("javascript")
        tracked_for.extend(js_paths)
    if not langs:
        return None
    churn_paths = 0
    for path in tracked_for:
        ch = churn.get(path)
        if not ch:
            continue
        if (ch.get("added") or 0) + (ch.get("deleted") or 0) > 0:
            churn_paths += 1
    if churn_paths == 0:
        return None
    complexity_on_tracked = sum(
        1 for path in tracked_for
        if path in complexity and not (complexity[path] or {}).get("_carriedForward")
    )
    if complexity_on_tracked:
        # Keys matched tracked files; zero candidates is MIN_CCN / line filtering.
        return None
    return {
        "languages": langs,
        "trackedFiles": len(tracked_for),
        "churnPaths": churn_paths,
        "complexityKeys": len(complexity),
        "complexityOnTracked": complexity_on_tracked,
        "joinedCandidates": joined_count,
    }


def _normalize_complexity_paths(cwd, complexity):
    """Map collector path keys back to repo-relative paths."""
    out = {}
    for path, info in complexity.items():
        rel = path
        if os.path.isabs(path):
            try:
                rel = os.path.relpath(path, cwd)
            except ValueError:
                rel = path
        out[rel] = info
    return out


def _run_radon(ctx, path_bin, paths):
    """Run radon from an isolated temp cwd with absolute input paths.

    Repo-local radon.cfg / setup.cfg must not control output_file or otherwise
    redirect writes into the scanned tree.
    Returns (complexity_dict, error_paths, None) on success, or (None, None, reason)
    on failure. Shape violations raise LensDegraded.
    """
    if not paths:
        return {}, [], None
    cwd = ctx["cwd"]
    abs_paths = _abs_paths(cwd, paths)
    runner = ctx.get("run") or subprocess.run
    with tempfile.TemporaryDirectory(prefix="guardian-radon-") as tmp:
        argv = [path_bin, "cc", "-s", "-j", *abs_paths]
        try:
            proc = runner(
                argv, capture_output=True, text=True, cwd=tmp, timeout=120,
            )
        except Exception as exc:
            return None, None, "radon invocation failed: %s: %s" % (type(exc).__name__, exc)
        if getattr(proc, "returncode", 1) != 0:
            return None, None, "radon exited non-zero (exit %s)" % getattr(proc, "returncode", "?")
        text = getattr(proc, "stdout", "") or ""
        if not text.strip():
            return None, None, "radon returned empty output"
        try:
            parsed, error_paths = parse_radon_json(text)
        except guardian_lens.LensDegraded:
            raise
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            return None, None, "radon output unparseable: %s" % exc
        return _normalize_complexity_paths(cwd, parsed), [
            _normalize_one_path(cwd, p) for p in error_paths
        ], None


def _normalize_one_path(cwd, path):
    if os.path.isabs(path):
        try:
            return os.path.relpath(path, cwd)
        except ValueError:
            return path
    return path


def _run_lizard(ctx, path_bin, paths):
    """Run lizard from an isolated temp cwd with absolute input paths.

    Forces CSV on stdout; repo content must not redirect writes via --output_file.
    Returns (complexity_dict, None) on success, or (None, reason) on failure.
    """
    if not paths:
        return {}, None
    cwd = ctx["cwd"]
    abs_paths = _abs_paths(cwd, paths)
    runner = ctx.get("run") or subprocess.run
    with tempfile.TemporaryDirectory(prefix="guardian-lizard-") as tmp:
        # CSV to stdout only — never pass --output_file; cwd is an empty temp dir
        # so any relative output_file from ambient config cannot land in the repo.
        argv = [path_bin, "--csv", "-l", "javascript", *abs_paths]
        try:
            proc = runner(
                argv, capture_output=True, text=True, cwd=tmp, timeout=120,
            )
        except Exception as exc:
            return None, "lizard invocation failed: %s: %s" % (type(exc).__name__, exc)
        if getattr(proc, "returncode", 1) != 0:
            return None, "lizard exited non-zero (exit %s)" % getattr(proc, "returncode", "?")
        text = getattr(proc, "stdout", "") or ""
        try:
            parsed = parse_lizard_csv(text)
        except (TypeError, ValueError, csv.Error) as exc:
            return None, "lizard output unparseable: %s" % exc
        return _normalize_complexity_paths(cwd, parsed), None


def _is_unmeasured_file(rec):
    return isinstance(rec, dict) and rec.get("unmeasured") is True


def _diff_files_raw(prev_files, cur_files):
    if prev_files is None:
        return {
            "new": sorted(
                cid for cid, rec in cur_files.items() if not _is_unmeasured_file(rec)
            ),
            "worsened": [],
            "resolved": [],
        }
    new = []
    worsened = []
    resolved = []
    for cid, cur in cur_files.items():
        if _is_unmeasured_file(cur):
            continue
        if cid not in prev_files:
            new.append(cid)
            continue
        prev = prev_files.get(cid) or {}
        if _is_unmeasured_file(prev):
            continue
        try:
            prev_score = float((prev or {}).get("score", 0))
            cur_score = float((cur or {}).get("score", 0))
        except (TypeError, ValueError):
            continue
        if cur_score > prev_score:
            worsened.append(cid)
    for cid, prev in prev_files.items():
        if cid in cur_files:
            continue
        if _is_unmeasured_file(prev):
            continue
        resolved.append(cid)
    return {
        "new": sorted(new),
        "worsened": sorted(worsened),
        "resolved": sorted(resolved),
    }


def _count_hotspots_drift_suppressed(prev_files, cur_files, surface_ids):
    if not surface_ids:
        return 0
    raw = _diff_files_raw(prev_files, cur_files)
    suppressed = 0
    for cid in raw["new"] + raw["worsened"]:
        if cid not in surface_ids:
            suppressed += 1
    return suppressed


class HotspotsLens:
    name = "hotspots"
    # 2.0.0: digest persists the full measured set (+ explicit unmeasured/error markers)
    # and surfaceIds; incompatible with the 1.0.0 capped-only shape — bump so the shell
    # records a quiet baseline instead of mass false drift on upgrade.
    collector_version = "2.0.0"
    required_facts = ()
    cost = {
        "collectorSeconds": 0.5,
        "note": "radon (py) + lizard (js/ts) + git churn; needs git history",
    }
    validation_guidance = VALIDATION_GUIDANCE
    consequence_template = CONSEQUENCE_TEMPLATE

    def __init__(self):
        # Cached by collect() for red_lines(). Sweep ordering: collect then red_lines
        # on the same instance — see red_lines docstring.
        self._prev_digest = None
        self._complexity_threshold = None
        self._surface_ids = None

    def degrade(self, reason):
        return {"lens": self.name, "degraded": True, "reason": reason}

    def collect(self, ctx):
        # Normalize once: relative forms like "." / "./" must not reach _abs_paths,
        # git -C, or complexity path re-normalization (silent-zero under `--cwd .`).
        cwd = os.path.realpath(ctx.get("cwd") or ".")
        ctx = dict(ctx)
        ctx["cwd"] = cwd
        since = DEFAULT_WINDOW
        config = ctx.get("config") or {}
        if isinstance(config, dict) and config.get("hotspotsWindow"):
            since = config["hotspotsWindow"]

        # Cache owner-calibrated complexity threshold for red_lines() / cap union.
        self._complexity_threshold = None
        if isinstance(config, dict) and isinstance(config.get("thresholds"), dict):
            if "complexity" in config["thresholds"]:
                self._complexity_threshold = config["thresholds"]["complexity"]

        # Cache previous digest for red_lines() — the shell supplies ctx["prev_digest"]
        # (this lens does not read the store). Sweep ordering: collect then red_lines
        # on the same instance.
        self._prev_digest = ctx.get("prev_digest")

        radon_res = guardian_tools.resolve("radon", cwd, run=ctx.get("run"))
        lizard_res = guardian_tools.resolve("lizard", cwd, run=ctx.get("run"))
        radon_ok = bool(radon_res.get("found"))
        lizard_ok = bool(lizard_res.get("found"))
        radon_reason = guardian_tools.missing_tool_reason(
            "radon", rejection=radon_res.get("rejection"))
        lizard_reason = guardian_tools.missing_tool_reason(
            "lizard", rejection=lizard_res.get("rejection"))

        window = observe_window(cwd, since=since, run=ctx.get("run"))
        churn = _collect_churn(ctx, since)
        tracked = tracked_existing_files(cwd, run=ctx.get("run"))

        complexity = {}
        coverage = {}
        coverage_gaps = []
        collector_errors = []
        py_paths = _paths_with_ext(tracked, PY_EXTS)
        js_paths = _paths_with_ext(tracked, JS_EXTS)
        need_radon = bool(py_paths)
        need_lizard = bool(js_paths)

        if not radon_ok and not lizard_ok:
            raise guardian_lens.LensDegraded("%s; %s" % (radon_reason, lizard_reason))
        if need_radon and not radon_ok:
            raise guardian_lens.LensDegraded(radon_reason)
        if need_lizard and not lizard_ok:
            raise guardian_lens.LensDegraded(lizard_reason)

        if radon_ok:
            if py_paths:
                parsed, error_paths, err = _run_radon(ctx, radon_res["path"], py_paths)
                if err is not None:
                    raise guardian_lens.LensDegraded(err)
                complexity.update(parsed)
                coverage["python"] = "collected"
                # Per-file radon errors: carry prior digest entries forward so a
                # parse failure never reads as "this file is now clean". Paths with
                # no prior entry get an explicit unmeasured/error digest marker.
                prev_files = {}
                if isinstance(self._prev_digest, dict):
                    prev_files = self._prev_digest.get("files") or {}
                if not isinstance(prev_files, dict):
                    prev_files = {}
                error_paths = list(error_paths or [])
                for err_path in error_paths:
                    collector_errors.append({
                        "collector": "radon",
                        "path": err_path,
                        "kind": "parse-error",
                    })
                    cid = "hotspots:%s" % err_path
                    prev_rec = prev_files.get(cid)
                    if isinstance(prev_rec, dict) and not prev_rec.get("unmeasured"):
                        try:
                            score = float(prev_rec.get("score") or 0)
                            ccn = int(prev_rec.get("ccn") or 0)
                        except (TypeError, ValueError):
                            complexity[err_path] = {
                                "_unmeasured": True,
                                "_error": True,
                            }
                            continue
                        complexity[err_path] = {
                            "maxFunctionCCN": ccn,
                            "worstFunction": {"name": "?", "line": 0},
                            "_carriedForward": True,
                            "_carriedScore": score,
                        }
                    else:
                        complexity[err_path] = {
                            "_unmeasured": True,
                            "_error": True,
                        }
                if error_paths:
                    if len(error_paths) >= PER_FILE_ERROR_DEGRADE_THRESHOLD:
                        raise guardian_lens.LensDegraded(
                            "radon per-file errors exceeded threshold "
                            "(%d >= %d)" % (len(error_paths), PER_FILE_ERROR_DEGRADE_THRESHOLD)
                        )
                    if py_paths and set(error_paths) >= set(py_paths):
                        raise guardian_lens.LensDegraded(
                            "radon per-file errors on all %d tracked Python file(s)"
                            % len(py_paths)
                        )
            else:
                coverage["python"] = "not-collected"
        else:
            coverage_gaps.append(radon_reason)
            coverage["python"] = "missing-tool"

        if lizard_ok:
            if js_paths:
                parsed, err = _run_lizard(ctx, lizard_res["path"], js_paths)
                if err is not None:
                    raise guardian_lens.LensDegraded(err)
                complexity.update(parsed)
                coverage["javascript"] = "collected"
            else:
                coverage["javascript"] = "not-collected"
        else:
            coverage_gaps.append(lizard_reason)
            coverage["javascript"] = "missing-tool"

        candidates = []
        for path, ch in churn.items():
            if path not in tracked:
                continue
            info = complexity.get(path)
            if not info or info.get("_carriedForward") or info.get("_unmeasured"):
                continue
            lines = _count_lines(cwd, path)
            if lines <= 0:
                continue
            added = ch["added"]
            deleted = ch["deleted"]
            if added + deleted <= 0:
                continue
            max_ccn = info["maxFunctionCCN"]
            if max_ccn < MIN_CCN:
                continue
            cand = build_candidate(
                path=path,
                added=added,
                deleted=deleted,
                current_lines=lines,
                max_ccn=max_ccn,
                worst=info["worstFunction"],
                window=window,
            )
            if cand is not None:
                candidates.append(cand)

        join_anomaly = _join_anomaly(
            coverage, py_paths, js_paths, churn, complexity, len(candidates),
        )
        if join_anomaly is not None and not collector_errors:
            raise guardian_lens.LensDegraded(
                "hotspots join anomaly: complexity keys never landed on churn×tracked "
                "paths (languages=%s, churnPaths=%s, complexityOnTracked=%s)"
                % (
                    ",".join(join_anomaly["languages"]),
                    join_anomaly["churnPaths"],
                    join_anomaly["complexityOnTracked"],
                )
            )

        red_threshold = self._complexity_threshold
        if red_threshold is None:
            red_threshold = guardian_lens.RED_LINE_THRESHOLDS["complexity"]
        capped, cap_diag = apply_cap(
            candidates, top_n=TOP_N, always_include_ccn=red_threshold,
        )
        surface_ids = [c["id"] for c in capped]
        self._surface_ids = set(surface_ids)

        radon_ver = (
            guardian_tools.version("radon", cwd, run=ctx.get("run")) if radon_ok else None
        )
        lizard_ver = (
            guardian_tools.version("lizard", cwd, run=ctx.get("run")) if lizard_ok else None
        )

        # Digest = FULL measured set (identity + metric). Cap applies only to
        # the surfaced candidate list — ranking churn must not invent `new` drift.
        files_digest = {
            c["id"]: {"score": c["hotspotScore"], "ccn": c["maxFunctionCCN"]}
            for c in candidates
        }
        # Carry prior entries / explicit unmeasured markers for radon parse-error paths.
        for info_path, info in complexity.items():
            cid = "hotspots:%s" % info_path
            if info.get("_unmeasured") or info.get("_error"):
                files_digest[cid] = {"unmeasured": True, "error": True}
                continue
            if not info.get("_carriedForward"):
                continue
            files_digest[cid] = {
                "score": info.get("_carriedScore", 0),
                "ccn": info.get("maxFunctionCCN", 0),
            }
        prev_files = {}
        if isinstance(self._prev_digest, dict):
            raw_prev = self._prev_digest.get("files")
            if isinstance(raw_prev, dict):
                prev_files = raw_prev
        digest = {
            "schemaVersion": SCHEMA_VERSION,
            "toolVersions": {"radon": radon_ver, "lizard": lizard_ver},
            "files": files_digest,
            "surfaceIds": surface_ids,
            "window": {
                "historyTruncated": window["historyTruncated"],
                "requestedSince": window["requestedSince"],
                "observedSince": window["observedSince"],
                "commitsObserved": window["commitsObserved"],
                "sinceSpec": window["sinceSpec"],
            },
        }
        drift_suppressed = _count_hotspots_drift_suppressed(
            prev_files, files_digest, self._surface_ids,
        )
        diagnostics = {
            "complexityCoverage": coverage,
            "coverageGaps": coverage_gaps,
            "collectorErrors": collector_errors,
            "minCcn": MIN_CCN,
            "topN": TOP_N,
            "candidatesBeforeCap": cap_diag["candidatesBeforeCap"],
            "capApplied": cap_diag["capApplied"],
            "redLineUnionAdded": cap_diag["redLineUnionAdded"],
            "driftSuppressedByCap": drift_suppressed,
            "historyTruncated": window["historyTruncated"],
            "requestedSince": window["requestedSince"],
            "observedSince": window["observedSince"],
            "commitsObserved": window["commitsObserved"],
            "toolVersions": {"radon": radon_ver, "lizard": lizard_ver},
            "joinAnomaly": join_anomaly,
        }
        return {"candidates": capped, "digest": digest, "diagnostics": diagnostics}

    def diff(self, prev_digest, cur_digest):
        cur_files = {}
        surface = None
        if isinstance(cur_digest, dict):
            cur_files = cur_digest.get("files") or {}
            if not isinstance(cur_files, dict):
                cur_files = {}
            raw_surface = cur_digest.get("surfaceIds")
            if isinstance(raw_surface, list):
                surface = set(raw_surface)

        prev_files = None
        if isinstance(prev_digest, dict) and isinstance(prev_digest.get("files"), dict):
            prev_files = prev_digest["files"]
        raw = _diff_files_raw(prev_files, cur_files)
        if surface is None:
            raw["driftSuppressedByCap"] = 0
            return raw
        filtered_new = [cid for cid in raw["new"] if cid in surface]
        filtered_worsened = [cid for cid in raw["worsened"] if cid in surface]
        suppressed = (
            len(raw["new"]) - len(filtered_new)
            + len(raw["worsened"]) - len(filtered_worsened)
        )
        return {
            "new": filtered_new,
            "worsened": filtered_worsened,
            "resolved": raw["resolved"],
            "driftSuppressedByCap": suppressed,
        }

    def red_lines(self, candidates):
        """Emit new-high-complexity when CCN >= threshold AND new or grown vs prev.

        Depends on collect() having cached self._prev_digest first — the sweep always
        calls collect() before red_lines() on the same instance. Threshold comes from
        owner-calibrated config when collect() cached it; else RED_LINE_THRESHOLDS.
        """
        threshold = self._complexity_threshold
        if threshold is None:
            threshold = guardian_lens.RED_LINE_THRESHOLDS["complexity"]
        prev_files = {}
        if isinstance(self._prev_digest, dict):
            prev_files = self._prev_digest.get("files") or {}
        if not isinstance(prev_files, dict):
            prev_files = {}

        out = []
        for c in candidates or []:
            if not isinstance(c, dict):
                continue
            try:
                ccn = int(c.get("maxFunctionCCN") or 0)
            except (TypeError, ValueError):
                continue
            if ccn < threshold:
                continue
            cid = c.get("id")
            if not cid:
                continue
            prev = prev_files.get(cid)
            if prev is None:
                out.append({
                    "kind": "new-high-complexity",
                    "id": cid,
                    "detail": "maxFunctionCCN=%d (new)" % ccn,
                })
                continue
            if isinstance(prev, dict) and prev.get("unmeasured"):
                # Known-but-unmeasured → first real measure is not "new" drift.
                continue
            try:
                prev_ccn = int((prev or {}).get("ccn") or 0)
            except (TypeError, ValueError):
                prev_ccn = 0
            if ccn > prev_ccn:
                out.append({
                    "kind": "new-high-complexity",
                    "id": cid,
                    "detail": "maxFunctionCCN=%d (was %d)" % (ccn, prev_ccn),
                })
        return out


LENS = HotspotsLens()
