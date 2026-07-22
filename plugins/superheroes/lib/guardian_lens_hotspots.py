#!/usr/bin/env python3
# plugins/superheroes/lib/guardian_lens_hotspots.py
"""Guardian hotspots lens — size-normalized churn × max function complexity.

Stdlib-only. Three collectors — git churn, radon (python), lizard (js/ts) — all routed
through ``guardian_collect.run_tool`` (never subprocess directly): in production the spawn
goes through ``guardian_tools.invoke``'s hardening (neutral cwd, sanitized env, repo-local
rejection, bounded output); in tests / conformance it goes through the injected ``ctx["run"]``
seam. Churn is always size-normalized (relativeChurn); raw changed-line totals are provenance
only, never the ranking key. Shallow clones are reported honestly — never unshallowed.

Degradation is a ``not-collected`` / ``partial`` status return (never a raised exception into
the sweep). The module-local ``_Degraded`` signal is caught inside ``collect()`` and turned
into ``not-collected``; the old shared ``guardian_lens.LensDegraded`` type is gone. The prior
digest is read as camelCase ``ctx["prevDigest"]`` (a snake_case read would silently lose the
baseline).
"""
import csv
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import guardian_census  # noqa: E402
import guardian_collect as gc  # noqa: E402
import guardian_lens  # noqa: E402

MIN_CCN = 10
TOP_N = 25
DEFAULT_WINDOW = "90 days"
SCHEMA_VERSION = 1
# Per-file radon errors at/beyond this count (or all files of a language) mark that
# language's collection as failed rather than trustworthy-with-carry-forward.
PER_FILE_ERROR_DEGRADE_THRESHOLD = 3

PY_EXTS = (".py",)
JS_EXTS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")

# The one hotspots red-line kind, sourced from the authoritative tuple (I3) — not a bare
# literal. Fails closed at import if guardian_lens drops the kind.
_RED_LINE_KIND = next(
    k for k in guardian_lens.RED_LINE_KINDS if k == "new-high-complexity")

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


class _Degraded(Exception):
    """Module-local degradation signal — caught by ``collect()`` → ``not-collected``.

    Replaces the removed shared ``guardian_lens.LensDegraded``. A degraded collection must
    never erase the tracked baseline with an empty digest, so ``collect()`` returns
    ``not-collected`` (digest None) and the sweep preserves the prior snapshot.
    """


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

    Raises _Degraded when the top-level shape is not a dict of path → list (a bare `[]`
    or non-dict must not erase the baseline as a quiet empty result). Paths whose entry
    list contains an 'error' key are listed in error_paths and omitted from the complexity
    map — callers must carry prior digest entries forward. Class aggregates are skipped;
    methods and closures are flattened recursively.
    """
    data = json.loads(text) if isinstance(text, str) else text
    if not isinstance(data, dict):
        raise _Degraded(
            "radon output contract mismatch: expected a JSON object of path → list, "
            "got %s" % type(data).__name__)
    result = {}
    error_paths = []
    for path, entries in data.items():
        if not isinstance(entries, list):
            raise _Degraded(
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
        # A short/garbage row is SKIPPED, never indexed past its length — the guard must
        # protect every row[...] access below so a malformed row can never raise an
        # uncaught IndexError out of collect(). (_run_lizard turns an all-garbage,
        # non-empty output into an honest js degrade rather than a silent empty dict.)
        if len(row) < 8:
            continue
        try:
            ccn = int(row[1])
            path = row[6].strip()
            name = row[7].strip() or "?"
            line = int(row[9]) if len(row) > 9 else 0
        except (TypeError, ValueError, IndexError):
            continue
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


def _count_lines(cwd, relpath):
    path = os.path.join(cwd, relpath)
    try:
        with open(path, "rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def _git(ctx, cwd, args, timeout=gc.DEFAULT_TIMEOUT):
    """Run a git subcommand via run_tool with an absolute ``-C`` repo target.

    ``git -C <abs repo>`` targets the repo even though invoke runs collectors from a
    neutral cwd (git resolves via PATH; it is not a repo-local executable).
    """
    return gc.run_tool(
        ["git", "-C", cwd, *args], ctx=ctx, cwd=cwd, timeout=timeout)


def _requested_since_iso(window_spec):
    """Best-effort ISO date for a git --since spec like '90 days'."""
    now = datetime.now(timezone.utc)
    spec = (window_spec or DEFAULT_WINDOW).strip().lower()
    days = 90
    parts = spec.split()
    if parts and parts[0].isdigit():
        days = int(parts[0])
    return (now - timedelta(days=days)).date().isoformat()


def observe_window(ctx, cwd, since=DEFAULT_WINDOW):
    """Honest window accounting — never fetch/--unshallow.

    Raises _Degraded on git failure or malformed shallow output so a broken probe cannot
    look like a quiet repo. `git rev-parse --is-shallow-repository` always reports exactly
    "true" or "false"; anything else (empty / garbage) is a malfunction, not history.
    """
    requested = _requested_since_iso(since)
    shallow_res = _git(ctx, cwd, ["rev-parse", "--is-shallow-repository"])
    if not shallow_res["ok"]:
        raise _Degraded(
            "git rev-parse --is-shallow-repository failed: %s" % shallow_res["reason"])
    shallow_lines = (shallow_res.get("stdout") or "").splitlines()
    shallow_txt = shallow_lines[0].strip().lower() if shallow_lines else ""
    if shallow_txt not in ("true", "false"):
        raise _Degraded(
            "git rev-parse --is-shallow-repository returned unexpected output %r "
            "(expected 'true' or 'false')" % shallow_txt)
    history_truncated = shallow_txt == "true"

    log_res = _git(ctx, cwd, ["log", "--since=%s" % since, "--format=%cI", "--reverse"])
    if not log_res["ok"]:
        raise _Degraded("git log failed: %s" % log_res["reason"])
    dates = [
        line.strip() for line in (log_res.get("stdout") or "").splitlines()
        if line.strip()
    ]
    commits_observed = len(dates)
    observed = dates[0][:10] if dates else requested
    return {
        "historyTruncated": history_truncated,
        "requestedSince": requested,
        "observedSince": observed,
        "commitsObserved": commits_observed,
        "sinceSpec": since,
    }


def _collect_churn(ctx, cwd, since):
    res = _git(
        ctx, cwd,
        ["log", "--since=%s" % since, "--numstat", "--no-renames", "--format="],
    )
    if not res["ok"]:
        raise _Degraded("git log --numstat failed: %s" % res["reason"])
    return parse_numstat(res.get("stdout") or "")


def _paths_with_ext(tracked, exts):
    return sorted(p for p in tracked if p.lower().endswith(exts))


def _lang_of_path(path):
    low = path.lower()
    if low.endswith(PY_EXTS):
        return "python"
    if low.endswith(JS_EXTS):
        return "javascript"
    return None


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


def _is_real_complexity(info):
    """True when a complexity entry is a genuine fresh measurement (not carried / not
    an explicit unmeasured marker). Carried-forward and unmeasured records must never
    count as evidence that a tool joined its churn×tracked paths."""
    info = info or {}
    return not info.get("_carriedForward") and not info.get("_unmeasured")


def _join_anomaly(coverage, py_paths, js_paths, churn, complexity):
    """Detect a PER-LANGUAGE churn×complexity join MALFUNCTION (I5 / A / B).

    For each collected language with churn on its tracked files but zero real (not
    carried / not unmeasured) complexity landing on those tracked paths, this fires ONLY
    when the tool nonetheless produced real complexity keys that match NO tracked file of
    that language — i.e. keys ORPHANED by a path-join bug. A language whose tool ran
    cleanly yet produced no usable key for a legitimately function-less churn set (no
    orphaned keys) is a valid collected-empty, not an anomaly (B: a repo whose only churn
    is function-less files — ``__init__.py``, ``settings.py`` — must not false-degrade).

    Evaluated per language so a python-side radon per-file error can never suppress a
    js-side join failure, and vice versa (A: the old global ``collector_errors`` gate is
    gone — a carried/unmeasured radon entry is simply not a real key here). Returns a dict
    keyed by language, or None when every collected language joined cleanly.
    """
    anomalies = {}
    for lang, paths in (("python", py_paths), ("javascript", js_paths)):
        if coverage.get(lang) != "collected" or not paths:
            continue
        tracked_lang = set(paths)
        churn_paths = [
            p for p in paths
            if churn.get(p) and ((churn[p].get("added") or 0)
                                 + (churn[p].get("deleted") or 0)) > 0
        ]
        if not churn_paths:
            continue
        complexity_on_tracked = sum(
            1 for p in churn_paths
            if p in complexity and _is_real_complexity(complexity.get(p))
        )
        if complexity_on_tracked:
            # Keys matched this language's tracked files; zero candidates is MIN_CCN /
            # line filtering, not a join failure.
            continue
        orphan_keys = [
            p for p, info in complexity.items()
            if _lang_of_path(p) == lang and _is_real_complexity(info)
            and p not in tracked_lang
        ]
        if not orphan_keys:
            # No real key produced for this language landed anywhere off its tracked set:
            # a function-less churn set (legit collected-empty), never a malfunction.
            continue
        anomalies[lang] = {
            "trackedChurnFiles": len(churn_paths),
            "orphanComplexityKeys": len(orphan_keys),
            "complexityOnTracked": complexity_on_tracked,
        }
    return anomalies or None


def _normalize_one_path(cwd, path):
    if os.path.isabs(path):
        try:
            return os.path.relpath(path, cwd)
        except ValueError:
            return path
    return path


def _normalize_complexity_paths(cwd, complexity):
    """Map collector path keys back to repo-relative paths."""
    out = {}
    for path, info in complexity.items():
        out[_normalize_one_path(cwd, path)] = info
    return out


def _run_radon(ctx, cwd, paths):
    """Run radon over absolute input paths via run_tool.

    Returns (complexity_dict, error_paths, None) on success, or (None, None, reason) on
    failure. A radon parse / contract failure is routed into the PYTHON-failed path (a
    reason string), NOT re-raised — so it degrades python (→ partial when js still
    collects) instead of aborting the whole lens before lizard runs (I4 / D).
    """
    if not paths:
        return {}, [], None
    abs_paths = _abs_paths(cwd, paths)
    res = gc.run_tool(
        ["radon", "cc", "-s", "-j", *abs_paths], ctx=ctx, cwd=cwd, ok_exits=(0,))
    if not res["ok"]:
        return None, None, "radon failed: %s" % res["reason"]
    text = res.get("stdout") or ""
    if not text.strip():
        return None, None, "radon returned empty output"
    try:
        parsed, error_paths = parse_radon_json(text)
    except _Degraded as exc:
        return None, None, str(exc)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return None, None, "radon output unparseable: %s" % exc
    return (
        _normalize_complexity_paths(cwd, parsed),
        [_normalize_one_path(cwd, p) for p in error_paths],
        None,
    )


def _run_lizard(ctx, cwd, paths):
    """Run lizard over absolute input paths via run_tool.

    Returns (complexity_dict, None) on success, or (None, reason) on failure. Empty output
    for a needed language is a failure (I4 fail-direction — mirrors radon's empty guard),
    never a clean zero-complexity read.
    """
    if not paths:
        return {}, None
    abs_paths = _abs_paths(cwd, paths)
    res = gc.run_tool(
        ["lizard", "--csv", "-l", "javascript", *abs_paths],
        ctx=ctx, cwd=cwd, ok_exits=(0,))
    if not res["ok"]:
        return None, "lizard failed: %s" % res["reason"]
    text = res.get("stdout") or ""
    if not text.strip():
        return None, "lizard returned empty output"
    try:
        parsed = parse_lizard_csv(text)
    except (TypeError, ValueError, csv.Error, IndexError) as exc:
        return None, "lizard output unparseable: %s" % exc
    # Honesty mirror of radon's guard: lizard produced NON-EMPTY output but parsing
    # yielded zero usable rows (short / garbage CSV). That is a tool malfunction, not a
    # clean zero-complexity read — degrade js rather than fail open with a silent {}.
    if not parsed:
        return None, (
            "lizard reported output but parsing yielded zero usable rows "
            "(reported-nonzero-parsed-zero)")
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
    # M1 (E): a first-ever baseline (``prev_files is None``) reports zero suppression —
    # there is no prior baseline to have suppressed drift against, so a first sweep with
    # more than TOP_N candidates must not report a false driftSuppressedByCap. Mirror
    # duplication._count_drift_suppressed_by_cap exactly (prev is None, not {}).
    if prev_files is None:
        return 0
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
    # 2.1.0 (#564): the census POPULATION changed — tracked symlinks are now excluded
    # because radon/lizard read file content from the census paths. A tracked symlink
    # whose target is an untracked file under the repo would otherwise pass os.path.isfile
    # (which follows the link) and have its untracked bytes analyzed. The digest SCHEMA is
    # unchanged, but a prior baseline may hold candidates from now-excluded symlinked paths;
    # bump the version so guardian_sweep.py (any version delta ⇒ lens_new) records a quiet
    # re-baseline FOR DRIFT — the new/worsened/resolved diff runs with _prev_digest treated
    # as absent, so the excluded paths do not surface as false `resolved` drift. This
    # "quiet" scope is DRIFT ONLY: red_lines() still runs unconditionally (with prev_files
    # empty on a version-delta sweep), so a genuine hotspot at/above threshold re-fires as a
    # `new-high-complexity` red line on the first post-fix sweep. That is by design — a red
    # line must always surface, even across a re-baseline.
    collector_version = "2.1.0"
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

    def conformance_cases(self):
        """Lens-supplied ``reported-nonzero-parsed-zero`` payload (see lens-contract.md).

        This lens runs THREE tools (git churn, radon, lizard) but the conformance harness
        feeds the SAME stubbed stdout to every ``ctx["run"]`` call and drives no real files
        on disk — so radon / lizard are never invoked (there are no tracked, existing
        .py/.js files under the harness cwd). Both payloads are therefore shaped for the
        GIT layer, whose ``git rev-parse --is-shallow-repository`` probe fires first:

        - ``clean_stdout`` = ``"false\\n"``. Read as a non-shallow repo; fed to `ls-files`
          and `--numstat` it yields zero tracked files and empty churn ⇒ genuinely-clean
          ``collected`` with zero candidates.
        - ``stdout`` reports churn (numstat rows) but, fed to `ls-files`, yields zero
          tracked+existing files. Churn reported with no measurable surface ⇒ the honesty
          gate degrades it (``not-collected``) — it must never read as ``collected``.

        The first line of both is ``false`` so the shallow probe passes; the harness-owned
        degraded scenarios (missing-tool / timeout / nonzero-exit / empty / unparseable)
        all trip that same first probe and degrade honestly.
        """
        clean = "false\n"
        reported = "false\n10\t2\tsrc/hot_a.py\n7\t3\tsrc/hot_b.py\n"
        return {
            "reported-nonzero-parsed-zero": {
                "stdout": reported,
                "clean_stdout": clean,
                "exit": 0,
            },
        }

    def collect(self, ctx):
        try:
            return self._collect(ctx)
        except _Degraded as exc:
            return {
                "candidates": [],
                "digest": None,
                **gc.not_collected(str(exc)),
            }

    def _collect(self, ctx):
        # Normalize once: relative forms like "." / "./" must not reach _abs_paths,
        # git -C, or complexity path re-normalization (silent-zero under `--cwd .`).
        cwd = os.path.realpath(ctx.get("cwd") or ".")
        ctx = dict(ctx)
        ctx["cwd"] = cwd
        since = DEFAULT_WINDOW

        config = ctx.get("config") or {}
        # Cache owner-calibrated complexity threshold for red_lines() / cap union.
        self._complexity_threshold = None
        if isinstance(config, dict) and isinstance(config.get("thresholds"), dict):
            if "complexity" in config["thresholds"]:
                self._complexity_threshold = config["thresholds"]["complexity"]

        # Cache previous digest for red_lines(). The shell supplies it as camelCase
        # ctx["prevDigest"]; a snake_case read would silently lose the baseline. Sweep
        # ordering: collect then red_lines on the same instance.
        self._prev_digest = ctx.get("prevDigest")
        prev_files = {}
        # M1 (E): distinguish "no prior baseline at all" from "a prior baseline that was
        # empty". Only a usable prior digest counts as a baseline for drift suppression —
        # a first-ever sweep passes None (never {}) so >TOP_N candidates do not read as
        # cap-suppressed drift. Mirrors duplication's prev_pairs handling.
        has_prev_baseline = False
        if isinstance(self._prev_digest, dict):
            raw_prev = self._prev_digest.get("files")
            if isinstance(raw_prev, dict):
                prev_files = raw_prev
                has_prev_baseline = True

        window = observe_window(ctx, cwd, since=since)
        churn = _collect_churn(ctx, cwd, since)
        tracked, census_reason = guardian_census.tracked_existing_files(
            ctx, cwd, exclude_symlinks=True)
        if tracked is None:
            raise _Degraded("git ls-files failed: %s" % census_reason)

        # Honesty gate (git layer): churn reported on ≥1 path but ZERO tracked+existing
        # files means there is no measurable surface — an active repo cannot have churn
        # with no tracked files on disk. Never read that as a clean baseline.
        if churn and not tracked:
            raise _Degraded(
                "git reported churn on %d path(s) but ls-files reported zero tracked, "
                "existing files — no measurable surface" % len(churn))

        py_paths = _paths_with_ext(tracked, PY_EXTS)
        js_paths = _paths_with_ext(tracked, JS_EXTS)

        # Each language collects INDEPENDENTLY: a tool malfunction degrades only that
        # language; a clean run yielding zero complexity for function-less files is a
        # legitimate collected-empty for that language.
        (complexity, coverage, coverage_gaps, collector_errors,
         failed_langs) = self._collect_complexity(
            ctx, cwd, py_paths, js_paths, prev_files)

        # I4 fail-direction: if EVERY needed language failed (or the only needed one did),
        # nothing trustworthy remains → not-collected. If SOME needed language collected
        # while another failed → partial (baseline preserved for the failed portion).
        needed_langs = []
        if py_paths:
            needed_langs.append("python")
        if js_paths:
            needed_langs.append("javascript")
        failed_names = {lang for lang, _ in failed_langs}
        if needed_langs and failed_names >= set(needed_langs):
            raise _Degraded(
                "; ".join("%s: %s" % (lang, reason) for lang, reason in failed_langs))

        candidates = self._build_candidates(cwd, churn, tracked, complexity, window)

        # A/B: the join anomaly is now evaluated per language and fires only on a genuine
        # path-join malfunction (orphaned real keys) — not on radon per-file errors (A)
        # and not on legitimately function-less churn (B). No global collector_errors gate.
        join_anomaly = _join_anomaly(coverage, py_paths, js_paths, churn, complexity)
        if join_anomaly is not None:
            raise _Degraded(
                "hotspots join anomaly: complexity keys never landed on churn×tracked "
                "paths for %s" % ", ".join(sorted(join_anomaly)))

        red_threshold = self._complexity_threshold
        if red_threshold is None:
            red_threshold = guardian_lens.RED_LINE_THRESHOLDS["complexity"]
        capped, cap_diag = apply_cap(
            candidates, top_n=TOP_N, always_include_ccn=red_threshold,
        )
        surface_ids = [c["id"] for c in capped]
        self._surface_ids = set(surface_ids)

        # Digest = FULL measured set (identity + metric). Cap applies only to the surfaced
        # candidate list — ranking churn must not invent `new` drift.
        files_digest = self._build_files_digest(candidates, complexity)

        # Partial: merge prevDigest for the language(s) that could not collect so a failed
        # collector never erases prior findings or emits false `resolved`.
        partial_reason = None
        if failed_langs:
            partial_reason = "partial complexity coverage — %s" % "; ".join(
                "%s: %s" % (lang, reason) for lang, reason in failed_langs)
            self._merge_prev_for_failed(prev_files, files_digest, failed_names)

        digest = {
            "schemaVersion": SCHEMA_VERSION,
            # Versions are not probed under the run_tool/stdout contract (a second
            # --version spawn would confuse the single-invocation conformance seam).
            "toolVersions": {"radon": None, "lizard": None},
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
            prev_files if has_prev_baseline else None, files_digest, self._surface_ids,
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
            "toolVersions": {"radon": None, "lizard": None},
            "joinAnomaly": join_anomaly,
        }
        result = {
            "candidates": capped,
            "digest": digest,
            "diagnostics": diagnostics,
        }
        if partial_reason is not None:
            result.update(gc.partial(partial_reason))
        else:
            result.update(gc.collected())
        return result

    def _collect_complexity(self, ctx, cwd, py_paths, js_paths, prev_files):
        """Collect radon (python) + lizard (js/ts) INDEPENDENTLY (H / I1 extraction).

        Each language collects on its own seam so ``_collect`` reads as orchestration.
        A tool malfunction (radon/lizard failure, empty output, contract mismatch, or
        non-empty-parsed-zero) degrades ONLY that language — appended to ``failed_langs``
        as ``(lang, reason)`` and marked ``failed`` in coverage. A clean run yielding zero
        complexity for function-less files is a legitimate ``collected``-empty for that
        language. Returns
        ``(complexity, coverage, coverage_gaps, collector_errors, failed_langs)``.
        """
        complexity = {}
        coverage = {}
        coverage_gaps = []
        collector_errors = []
        failed_langs = []  # [(lang, reason)] — needed language that did not collect

        # ---- radon (python) --------------------------------------------------------
        if py_paths:
            parsed, error_paths, err = _run_radon(ctx, cwd, py_paths)
            if err is not None:
                coverage["python"] = "failed"
                coverage_gaps.append(err)
                failed_langs.append(("python", err))
            else:
                complexity.update(parsed)
                coverage["python"] = "collected"
                radon_lang_failed = self._absorb_radon_errors(
                    list(error_paths or []), py_paths, prev_files, complexity,
                    collector_errors)
                if radon_lang_failed is not None:
                    coverage["python"] = "failed"
                    coverage_gaps.append(radon_lang_failed)
                    failed_langs.append(("python", radon_lang_failed))
        else:
            coverage["python"] = "not-collected"

        # ---- lizard (js/ts) --------------------------------------------------------
        if js_paths:
            parsed, err = _run_lizard(ctx, cwd, js_paths)
            if err is not None:
                coverage["javascript"] = "failed"
                coverage_gaps.append(err)
                failed_langs.append(("javascript", err))
            else:
                complexity.update(parsed)
                coverage["javascript"] = "collected"
        else:
            coverage["javascript"] = "not-collected"

        return complexity, coverage, coverage_gaps, collector_errors, failed_langs

    @staticmethod
    def _build_files_digest(candidates, complexity):
        """Full measured digest (H / I1 extraction): every candidate's identity+metric,
        plus carried-prior / explicit-unmeasured markers for radon parse-error paths so a
        parse failure never reads as "this file is now clean" or invents `new` drift."""
        files_digest = {
            c["id"]: {"score": c["hotspotScore"], "ccn": c["maxFunctionCCN"]}
            for c in candidates
        }
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
        return files_digest

    def _absorb_radon_errors(self, error_paths, py_paths, prev_files, complexity,
                             collector_errors):
        """Record radon per-file errors: carry prior digest entries forward or mark
        unmeasured. Returns a failure reason when the errors are severe enough to mark the
        whole python collection untrustworthy (≥ threshold, or all tracked py files), else
        None. A parse failure must never read as "this file is now clean".
        """
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
                    complexity[err_path] = {"_unmeasured": True, "_error": True}
                    continue
                complexity[err_path] = {
                    "maxFunctionCCN": ccn,
                    "worstFunction": {"name": "?", "line": 0},
                    "_carriedForward": True,
                    "_carriedScore": score,
                }
            else:
                complexity[err_path] = {"_unmeasured": True, "_error": True}
        if not error_paths:
            return None
        if len(error_paths) >= PER_FILE_ERROR_DEGRADE_THRESHOLD:
            return ("radon per-file errors exceeded threshold (%d >= %d)"
                    % (len(error_paths), PER_FILE_ERROR_DEGRADE_THRESHOLD))
        if py_paths and set(error_paths) >= set(py_paths):
            return ("radon per-file errors on all %d tracked Python file(s)"
                    % len(py_paths))
        return None

    def _build_candidates(self, cwd, churn, tracked, complexity, window):
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
                path=path, added=added, deleted=deleted, current_lines=lines,
                max_ccn=max_ccn, worst=info["worstFunction"], window=window,
            )
            if cand is not None:
                candidates.append(cand)
        return candidates

    def _merge_prev_for_failed(self, prev_files, files_digest, failed_names):
        """Carry prior digest entries for files of a failed language into this run's
        digest so a partial collection preserves the baseline for the uncollected portion.
        """
        for cid, rec in prev_files.items():
            if cid in files_digest:
                continue
            if not isinstance(cid, str) or not cid.startswith("hotspots:"):
                continue
            path = cid[len("hotspots:"):]
            if _lang_of_path(path) in failed_names:
                files_digest[cid] = dict(rec) if isinstance(rec, dict) else rec

    def diff(self, prev_digest, cur_digest):
        # Stopped-looking / no digest ⇒ no drift claims at all (never `resolved`).
        if cur_digest is None:
            return {"new": [], "worsened": [], "resolved": []}
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
            return {
                "new": raw["new"],
                "worsened": raw["worsened"],
                "resolved": raw["resolved"],
            }
        filtered_new = [cid for cid in raw["new"] if cid in surface]
        filtered_worsened = [cid for cid in raw["worsened"] if cid in surface]
        return {
            "new": filtered_new,
            "worsened": filtered_worsened,
            "resolved": raw["resolved"],
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
                    "kind": _RED_LINE_KIND,
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
                    "kind": _RED_LINE_KIND,
                    "id": cid,
                    "detail": "maxFunctionCCN=%d (was %d)" % (ccn, prev_ccn),
                })
        return out


LENS = HotspotsLens()
# Module-level roster the production loader registers (guardian_lens.PRODUCTION_LENS_MODULES).
LENSES = (LENS,)
