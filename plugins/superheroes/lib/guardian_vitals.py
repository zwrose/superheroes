#!/usr/bin/env python3
# plugins/superheroes/lib/guardian_vitals.py
"""Guardian vitals — the small numbers each sweep gathers, their drift, and the trend file.

Stdlib-only. **Vitals is a shared component, NOT a judgment lens** (#41 §3.7): it does not
register in `guardian_lens.REGISTRY`, does not implement the lens contract, and never enters
the report card's actionability/benching accounting. A threshold crossing *renders* like a
finding; it is not a lens finding.

**Never run an expensive tool twice.** Nothing here shells out to jscpd/ncu/audit tools or to
the calibration verify command. Duplication/dependency numbers are read from lens digests the
sweep already computed; suite numbers are parsed from the verify-command run the sweep already
performed and hands in as `verify_result`. Exactly one execution per sweep, shared between fact
verification and vitals. The only subprocess this module spawns is read-only `git` (via
`store_core.run_git`, or the injected `run` when the caller supplies one).

**Unavailable never reads as a measured zero.** A vital that could not be collected is `None`
in `vitals` and carries a non-empty reason in `notCollected`; `not_collected(reason)` returns
the structured `{"status": "not-collected", "reason": …}` form for renderers. A missing vital
never participates in a delta or a crossing.

The vital set, with units:

| vital | unit |
|---|---|
| `locTotal` | lines of text in git-tracked files |
| `fileCount` | git-tracked files (binaries included) |
| `duplicationPercent` | percent of code duplicated, 0–100 |
| `todoCount` | TODO/FIXME *occurrences* (not files) in git-tracked text files |
| `majorsBehind` | count of dependencies at least one major version behind |
| `vulnCount` | count of reported vulnerabilities |
| `couplingEdges` | count of cross-cluster dependency edges |
| `suiteRuntimeSeconds` | seconds for the verify command — pytest summary duration when parseable, else wall clock |
| `suiteTestCount` | tests that ran (passed+failed+errors+skipped+xfailed+xpassed) |
| `suiteSkipped` | tests reported as skipped |

**Trend-file provenance (CONVENTIONS §2.2, deliberate reading).** `vitals.jsonl` must both
begin with a provenance record and stay valid JSONL — an HTML comment would not parse. So the
first line is a JSON provenance object (`{"schemaVersion": 1, "file": "guardian-vitals",
"created": "YYYY-MM-DD"}`), written once at creation; `read_trend` validates and skips it.
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
import time

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import file_lock       # noqa: E402
import guardian_store  # noqa: E402
import store_core      # noqa: E402

VITALS = ("locTotal", "fileCount", "duplicationPercent", "todoCount",
          "majorsBehind", "vulnCount", "couplingEdges", "suiteRuntimeSeconds",
          "suiteTestCount", "suiteSkipped")

THRESHOLD_KINDS = ("relative", "absolute", "any-increase", "none")

# Defaults; the guardian.md config layer may override any entry (see `crossings`).
# VITALS + DRIFT_THRESHOLDS are the authoritative home for this fact set (CONVENTIONS §11) —
# a test asserts the two agree in both directions.
DRIFT_THRESHOLDS = {
    "locTotal":            {"kind": "relative", "limit": 0.20},
    "fileCount":           {"kind": "relative", "limit": 0.20},
    "duplicationPercent":  {"kind": "absolute", "limit": 2.0},
    "todoCount":           {"kind": "relative", "limit": 0.25},
    "majorsBehind":        {"kind": "absolute", "limit": 5},
    "vulnCount":           {"kind": "any-increase"},
    "couplingEdges":       {"kind": "relative", "limit": 0.25},
    "suiteRuntimeSeconds": {"kind": "relative", "limit": 0.40},
    "suiteTestCount":      {"kind": "none"},
    "suiteSkipped":        {"kind": "any-increase"},
}

# Every vital worsens by going UP (more code, more clones, more TODOs, more majors behind,
# more vulns, a slower suite, more skips). A decrease is an improvement: it lands in the
# delta and never crosses. `suiteTestCount` moves in both directions for benign reasons,
# which is why its kind is "none" — tracked, never a crossing on its own.

TREND_SCHEMA_VERSION = 1
TREND_FILE_ID = "guardian-vitals"

# Lens-owned vitals: each vital names the lens(es) that may publish it via an optional
# ``vitals(digest)`` hook. The lens returns ``{vital: (value|None, reason|None)}``;
# guardian_vitals owns vital names, thresholds, and completeness semantics.
VITAL_LENS_SOURCES = {
    "duplicationPercent": ("duplication", "dup"),
    "majorsBehind": ("deps", "dependencies"),
    "vulnCount": ("deps", "dependencies"),
    "couplingEdges": ("coupling",),
}

COMPLETENESS_STATES = ("complete", "partial", "not-collected")

SUITE_VITALS = ("suiteRuntimeSeconds", "suiteTestCount", "suiteSkipped")

# Leading word boundary only: "FIXMEs" counts, "PREFIXME" does not.
_MARKER_RE = re.compile(r"\b(?:TODO|FIXME)")

_COUNT_TOKEN = re.compile(
    r"(\d+)\s+(passed|failed|error|errors|skipped|deselected|xfailed|xpassed)\b")
_DURATION_RE = re.compile(r"\bin\s+(?:(\d+)m\s*)?(\d+(?:\.\d+)?)s\b")
# A pytest summary must name at least one ran/selected category other than bare
# "errors", and the category token must be followed by a pytest-shaped separator
# (comma, "in", "=", or end) — otherwise tool output like "2 failed checks" or
# "typecheck complete: 0 errors in 3.0s" is mistaken for a suite summary.
_PYTEST_SUMMARY_ANCHOR = re.compile(
    r"\d+\s+(?:passed|failed|skipped|deselected|xfailed|xpassed)\b(?=\s*[,=]|\s+in\b|\s*$)")
# Categories that mean "a test actually ran"; `deselected` tests never ran.
_RAN_CATEGORIES = ("passed", "failed", "error", "errors", "skipped", "xfailed", "xpassed")

_MAX_FILE_BYTES = 8 * 1024 * 1024
_BINARY_SNIFF = 8192


# --------------------------------------------------------------------------- helpers

def not_collected(reason):
    """Structured not-collected marker for renderers. Never a zero, never a guess."""
    return {"status": "not-collected", "reason": reason}


def _is_number(value):
    """True for a real int/float (bools, NaN, and infinities are not measurements)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))


def _git(cwd, args, run=None):
    """Read-only git. Uses store_core.run_git unless the caller injected a runner."""
    if run is None:
        return store_core.run_git(cwd, *args)
    try:
        r = run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def count_markers(text):
    """TODO/FIXME occurrences in text (occurrences, not lines, not files)."""
    return len(_MARKER_RE.findall(text or ""))


def _count_lines(data):
    n = data.count(b"\n")
    if data and not data.endswith(b"\n"):
        n += 1
    return n


def _scan_tracked(top, paths):
    """Line + marker census over the tracked files. Binaries/unreadables are skipped
    (counted, so the source string can say so) and never crash the scan."""
    out = {"lines": 0, "markers": 0, "text": 0,
           "binary": 0, "unreadable": 0, "oversize": 0}
    for rel in paths:
        full = os.path.join(top, rel)
        try:
            if os.path.islink(full) or not os.path.isfile(full):
                out["unreadable"] += 1
                continue
            if os.path.getsize(full) > _MAX_FILE_BYTES:
                out["oversize"] += 1
                continue
            with open(full, "rb") as fh:
                data = fh.read()
        except OSError:
            out["unreadable"] += 1
            continue
        if b"\x00" in data[:_BINARY_SNIFF]:
            out["binary"] += 1
            continue
        out["text"] += 1
        out["lines"] += _count_lines(data)
        out["markers"] += count_markers(data.decode("utf-8", errors="replace"))
    return out


def _collect_repo_vitals(cwd, run=None):
    """locTotal / fileCount / todoCount from git-tracked files (ignored files never count).

    fileCount comes from `git ls-files` and is always complete when listing succeeds.
    locTotal / todoCount require a full text scan: if any tracked file is unreadable,
    oversize, or a symlink, those vitals are published as not-collected rather than as
    a partial number that could look like an improvement."""
    top = _git(cwd, ["rev-parse", "--show-toplevel"], run=run)
    if top is None:
        reason = "not a git repo (git rev-parse failed)"
        return ({}, {n: reason for n in ("locTotal", "fileCount", "todoCount")}, {})
    top = top or cwd
    listing = _git(top, ["ls-files", "-z"], run=run)
    if listing is None:
        reason = "git ls-files failed"
        return ({}, {n: reason for n in ("locTotal", "fileCount", "todoCount")}, {})
    paths = [p for p in listing.split("\0") if p]
    scan = _scan_tracked(top, paths)
    incomplete = scan["unreadable"] + scan["oversize"]
    sources = {
        "fileCount": "git ls-files (%d tracked files)" % len(paths),
    }
    vitals = {"fileCount": len(paths)}
    missing = {}
    if incomplete:
        reason = (
            "repository scan incomplete (%d unreadable, %d oversize of %d tracked) "
            "— locTotal/todoCount not collected rather than published as a partial count"
            % (scan["unreadable"], scan["oversize"], len(paths)))
        missing["locTotal"] = reason
        missing["todoCount"] = reason
        sources["locTotal"] = reason
        sources["todoCount"] = reason
    else:
        vitals["locTotal"] = scan["lines"]
        vitals["todoCount"] = scan["markers"]
        skipped = "skipped %d binary, %d unreadable, %d oversize" % (
            scan["binary"], scan["unreadable"], scan["oversize"])
        sources["locTotal"] = "git ls-files line count (%d lines across %d text files; %s)" % (
            scan["lines"], scan["text"], skipped)
        sources["todoCount"] = (
            "git ls-files scan for TODO/FIXME occurrences, not files "
            "(%d occurrences across %d text files; %s)"
            % (scan["markers"], scan["text"], skipped))
    return (vitals, missing, sources)


def _completeness_entry(state, reason=None, identity=None):
    """Structured completeness marker for one vital this sweep."""
    entry = {"state": state}
    if reason:
        entry["reason"] = reason
    if isinstance(identity, (list, tuple)):
        tokens = sorted({
            str(x).strip() for x in identity
            if isinstance(x, str) and x.strip()})
        if tokens:
            entry["identity"] = tokens
    return entry


def _completeness_identity(entry):
    """Canonical identity tokens for a completeness entry, or None when unusable."""
    if not isinstance(entry, dict):
        return None
    raw = entry.get("identity")
    if not isinstance(raw, (list, tuple)):
        return None
    tokens = {str(x).strip() for x in raw if isinstance(x, str) and str(x).strip()}
    return frozenset(tokens) if tokens else None


def _completeness_state(entry):
    if not isinstance(entry, dict):
        return None
    state = entry.get("state")
    return state if state in COMPLETENESS_STATES else None


def _comparable_completeness(prev_entry, cur_entry):
    """True when two sweeps' completeness states may be drift-compared.

    Partial/partial compares stable identity tokens, not reason prose — reworded
    gaps must stay comparable; different gaps with identical prose must not."""
    if prev_entry is None and cur_entry is None:
        return True
    prev_state = _completeness_state(prev_entry)
    cur_state = _completeness_state(cur_entry)
    if prev_state is None or cur_state is None:
        return False
    if prev_state == "complete" and cur_state == "complete":
        return True
    if prev_state == "partial" and cur_state == "partial":
        pi = _completeness_identity(prev_entry)
        ci = _completeness_identity(cur_entry)
        if pi is None or ci is None:
            return False
        return pi == ci
    return False


def _lens_label(entry):
    lens = entry.get("lens") if isinstance(entry, dict) else None
    return getattr(lens, "name", None) or "lens"


def _apply_partial_lens_completeness(status, entry, comp):
    """When the lens itself reported partial collection, never publish ``complete``.

    A fully-measured vital coerced to partial gets a stable lens-scoped identity so
    sibling partials elsewhere do not chronically silence its crossings."""
    if status != "partial":
        return comp
    state = _completeness_state(comp)
    lens_reason = entry.get("reason") or "lens collection was partial this sweep"
    if state == "complete":
        label = _lens_label(entry)
        return _completeness_entry(
            "partial", lens_reason,
            identity=["%s/*/lens-partial" % label])
    return comp


def _usable_partial_reason(reason):
    """True when ``reason`` names the gap for a partial vital reading."""
    return isinstance(reason, str) and bool(reason.strip())


def _interpret_vital_tuple(value, reason, identity=None, *, lens_name=None,
                           vital_name=None):
    """Map a lens ``vitals()`` 2-tuple to (published value, completeness entry)."""
    if value is not None and reason is not None:
        if not _usable_partial_reason(reason):
            label = lens_name or "lens"
            vital = vital_name or "vital"
            violation = (
                "%s lens vitals()[%s] partial reading without a usable reason "
                "(contract violation)" % (label, vital))
            return (None, _completeness_entry("not-collected", violation))
        if not _is_number(value):
            return (None, _completeness_entry(
                "not-collected", reason or "partial vital is not a number"))
        return (value, _completeness_entry("partial", reason, identity=identity))
    if value is not None and reason is None:
        if not _is_number(value):
            return (None, _completeness_entry(
                "not-collected", "extractor returned a non-number"))
        return (value, _completeness_entry("complete"))
    return (None, _completeness_entry(
        "not-collected", reason or "not collected this sweep"))


def _fresh_lens_result(lens_results, lens_names):
    """Return the fresh result dict for the first matching lens name, or None."""
    results = lens_results if isinstance(lens_results, dict) else {}
    for name in lens_names:
        entry = results.get(name)
        if isinstance(entry, dict) and entry.get("fresh"):
            return entry
    return None


def _collect_lens_vitals(lens_results):
    """Lens-owned vitals from THIS sweep's fresh lens results only."""
    vitals, missing, sources, completeness = {}, {}, {}, {}
    results = lens_results if isinstance(lens_results, dict) else {}
    for vital_name, lens_names in VITAL_LENS_SOURCES.items():
        entry = _fresh_lens_result(results, lens_names)
        if entry is None:
            label = lens_names[0]
            reason = "%s lens did not run this sweep" % label
            missing[vital_name] = reason
            completeness[vital_name] = _completeness_entry("not-collected", reason)
            continue
        status = entry.get("status")
        if status == "not-collected":
            reason = entry.get("reason")
            if not (isinstance(reason, str) and reason.strip()):
                label = entry.get("lens")
                lens_label = getattr(label, "name", None) or lens_names[0]
                reason = "%s lens collection failed this sweep" % lens_label
            missing[vital_name] = reason
            completeness[vital_name] = _completeness_entry("not-collected", reason)
            continue
        if status not in ("collected", "partial"):
            label = entry.get("lens")
            lens_label = getattr(label, "name", None) or lens_names[0]
            reason = "%s lens status is %s this sweep" % (lens_label, status)
            missing[vital_name] = reason
            completeness[vital_name] = _completeness_entry("not-collected", reason)
            continue
        lens = entry.get("lens")
        digest = entry.get("digest")
        extractor = getattr(lens, "vitals", None) if lens is not None else None
        if not callable(extractor):
            reason = "%s lens has no vitals() hook" % lens_names[0]
            missing[vital_name] = reason
            completeness[vital_name] = _completeness_entry("not-collected", reason)
            continue
        try:
            offered = extractor(digest) or {}
        except Exception as exc:
            reason = "%s lens vitals() raised: %s" % (lens_names[0], exc)
            missing[vital_name] = reason
            completeness[vital_name] = _completeness_entry("not-collected", reason)
            continue
        if not isinstance(offered, dict):
            reason = "%s lens vitals() did not return a dict" % lens_names[0]
            missing[vital_name] = reason
            completeness[vital_name] = _completeness_entry("not-collected", reason)
            continue
        for offered_name, reading in offered.items():
            if offered_name not in VITALS:
                sys.stderr.write(
                    "guardian_vitals: lens %r offered unknown vital %r\n"
                    % (getattr(lens, "name", lens_names[0]), offered_name))
                continue
        if vital_name not in offered:
            reason = "%s lens vitals() omitted %s" % (lens_names[0], vital_name)
            missing[vital_name] = reason
            completeness[vital_name] = _completeness_entry("not-collected", reason)
            continue
        reading = offered.get(vital_name)
        if (not isinstance(reading, (tuple, list)) or len(reading) not in (2, 3)):
            reason = "%s lens vitals()[%s] is not a (value, reason[, identity]) tuple" % (
                lens_names[0], vital_name)
            missing[vital_name] = reason
            completeness[vital_name] = _completeness_entry("not-collected", reason)
            continue
        value = reading[0]
        gap_reason = reading[1]
        identity = reading[2] if len(reading) == 3 else None
        lens_name = getattr(lens, "name", lens_names[0])
        published, comp = _interpret_vital_tuple(
            value, gap_reason, identity, lens_name=lens_name, vital_name=vital_name)
        comp = _apply_partial_lens_completeness(status, entry, comp)
        completeness[vital_name] = comp
        if published is None:
            missing[vital_name] = comp.get("reason") or "not collected this sweep"
        else:
            vitals[vital_name] = published
            sources[vital_name] = "%s lens vitals() this sweep" % lens_name
    return (vitals, missing, sources, completeness)


def parse_verify_output(text):
    """Parse a verify-command transcript for suite numbers. Anything not found is None.

    Handles the common pytest summary shapes ("N passed", "N failed", "N skipped",
    "N deselected", "in 62.10s", "in 2m 3.50s"). The LAST line matching the anchored
    pytest-summary shape wins (pytest's final summary). Deselected tests never ran, so
    they are not counted. A recognized summary with no `skipped` token means zero skips —
    pytest omits empty categories — which is a reading of the summary, not a
    default-to-zero guess. Lines that only mention "N errors" (or duration alone) are
    not treated as pytest summaries."""
    out = {"suiteTestCount": None, "suiteSkipped": None, "suiteRuntimeSeconds": None}
    if not isinstance(text, str) or not text.strip():
        return out

    summary_line = None
    for line in text.splitlines():
        if _PYTEST_SUMMARY_ANCHOR.search(line) and _COUNT_TOKEN.search(line):
            summary_line = line
    if summary_line is None:
        return out

    counts = {}
    for num, cat in _COUNT_TOKEN.findall(summary_line):
        counts[cat] = counts.get(cat, 0) + int(num)
    out["suiteTestCount"] = sum(
        n for cat, n in counts.items() if cat in _RAN_CATEGORIES)
    out["suiteSkipped"] = counts.get("skipped", 0)

    m = _DURATION_RE.search(summary_line)
    if m:
        out["suiteRuntimeSeconds"] = (
            (int(m.group(1)) * 60 if m.group(1) else 0) + float(m.group(2)))
    return out


def _verify_unavailable_reason(verify_result, budget_seconds):
    """Why the suite vitals cannot be read from this sweep's verify run, or None."""
    if not isinstance(verify_result, dict):
        return "verify command not run this sweep"
    status = verify_result.get("status")
    if status in (None, "not-run"):
        return "verify command not run this sweep"
    if status == "absent":
        return "no verify command in calibration"
    if status == "failed":
        return "verify command failed (%s)" % (verify_result.get("receipt") or "no receipt")
    if status != "ok":
        return "verify command not collected (%s)" % (
            verify_result.get("receipt") or status)
    duration = verify_result.get("durationSeconds")
    if (_is_number(budget_seconds) and _is_number(duration)
            and duration > budget_seconds):
        return "exceeded time budget (%ss > %ss)" % (
            _fmt_number(duration), _fmt_number(budget_seconds))
    return None


def _collect_suite_vitals(verify_result, budget_seconds):
    """suiteRuntimeSeconds / suiteTestCount / suiteSkipped from the ALREADY-PERFORMED
    verify run handed in by the caller. This function never spawns a subprocess."""
    reason = _verify_unavailable_reason(verify_result, budget_seconds)
    if reason:
        return ({}, {n: reason for n in SUITE_VITALS}, {})

    parsed = parse_verify_output(verify_result.get("stdout"))
    vitals, missing, sources = {}, {}, {}
    for name in ("suiteTestCount", "suiteSkipped"):
        if parsed[name] is None:
            missing[name] = "could not read %s from the verify command output" % name
        else:
            vitals[name] = parsed[name]
            sources[name] = "verify command run this sweep (test-summary line)"

    # Prefer the pytest summary's own duration when parseable (excludes harness/startup
    # noise); fall back to the verify command's wall clock only when the summary has no
    # `in Ns` token. `sources` records which path was taken.
    if parsed["suiteRuntimeSeconds"] is not None:
        vitals["suiteRuntimeSeconds"] = parsed["suiteRuntimeSeconds"]
        sources["suiteRuntimeSeconds"] = (
            "verify command run this sweep (test-summary line)")
    elif _is_number(verify_result.get("durationSeconds")):
        vitals["suiteRuntimeSeconds"] = verify_result["durationSeconds"]
        sources["suiteRuntimeSeconds"] = "verify command run this sweep (wall clock)"
    else:
        missing["suiteRuntimeSeconds"] = (
            "could not read a runtime from the verify command output")
    return (vitals, missing, sources)


def collect(cwd, *, root=None, run=None, lens_results=None, verify_result=None,
            budget_seconds=None):
    """Gather the vital set. Returns {"vitals", "notCollected", "sources", "completeness"}.

    `run` is the sweep's injectable subprocess runner; it is used ONLY for read-only git.
    `verify_result` is the verify-command run the sweep already performed — this function
    never spawns the suite. `lens_results` is the per-lens fresh-result map the sweep
    built. Every collector degrades honestly: a number it cannot get is `None` plus a
    reason, and no collector failure fails the sweep."""
    vitals = {name: None for name in VITALS}
    missing = {}
    sources = {}
    completeness = {name: _completeness_entry("not-collected") for name in VITALS}

    for collector in (
        lambda: _collect_repo_vitals(cwd, run=run),
        lambda: _collect_lens_vitals(lens_results),
        lambda: _collect_suite_vitals(verify_result, budget_seconds),
    ):
        try:
            got = collector()
            if len(got) == 4:
                got_vitals, gone, src, comp = got
            else:
                got_vitals, gone, src = got
                comp = {}
        except Exception as exc:  # never fail the sweep over a vital
            got_vitals, gone, src, comp = {}, {}, {}, {}
            sys.stderr.write("guardian_vitals: collector failed: %s\n" % exc)
        vitals.update({k: v for k, v in got_vitals.items() if k in VITALS})
        missing.update({k: v for k, v in gone.items() if k in VITALS})
        sources.update({k: v for k, v in src.items() if k in VITALS})
        for name, entry in (comp or {}).items():
            if name in VITALS:
                completeness[name] = entry

    for name in VITALS:
        if vitals.get(name) is None:
            vitals[name] = None
            missing.setdefault(name, "not collected this sweep (no source available)")
            if _completeness_state(completeness.get(name)) != "not-collected":
                completeness[name] = _completeness_entry(
                    "not-collected", missing[name])
            sources.pop(name, None)
        else:
            missing.pop(name, None)
            if _completeness_state(completeness.get(name)) in (None, "not-collected"):
                completeness[name] = _completeness_entry("complete")
    return {
        "vitals": vitals,
        "notCollected": missing,
        "sources": sources,
        "completeness": completeness,
    }


# ------------------------------------------------------------------- delta + crossings

def _fmt_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, int):
        return str(value)
    text = "%.2f" % value
    return text.rstrip("0").rstrip(".") if "." in text else text


def _fmt_pct(pct):
    return "%d%%" % round(abs(pct) * 100)


def delta(prev_vitals, cur_vitals, *, prev_completeness=None, cur_completeness=None):
    """Per-vital movement. A vital missing (or not collected) on either side is absent —
    it never gets a fabricated prev/cur. `pct` is None when the base is zero.

    When both sides carry a number but completeness states are not comparable, the vital
    is recorded under ``_notComparable`` with a reason and omitted from numeric delta."""
    out = {}
    not_comparable = {}
    prev_vitals = prev_vitals or {}
    cur_vitals = cur_vitals or {}
    prev_comp = prev_completeness if isinstance(prev_completeness, dict) else {}
    cur_comp = cur_completeness if isinstance(cur_completeness, dict) else {}
    for name in VITALS:
        prev = prev_vitals.get(name)
        cur = cur_vitals.get(name)
        if not _is_number(prev) or not _is_number(cur):
            continue
        if not _comparable_completeness(prev_comp.get(name), cur_comp.get(name)):
            not_comparable[name] = (
                "completeness not comparable across sweeps "
                "(%r → %r)"
                % (_completeness_state(prev_comp.get(name)),
                   _completeness_state(cur_comp.get(name))))
            continue
        change = cur - prev
        pct = None if prev == 0 else round(change / prev, 6)
        out[name] = {"prev": prev, "cur": cur, "change": change, "pct": pct}
    if not_comparable:
        out["_notComparable"] = not_comparable
    return out


def _sentence(name, prev, cur, change, pct):
    """Plain language, both numbers named. No severity words, no rule-catalog language."""
    p, c, ch = _fmt_number(prev), _fmt_number(cur), _fmt_number(change)
    if name == "locTotal":
        return ("your tracked code grew from %s to %s lines (%s more) since the last sweep"
                % (p, c, ch))
    if name == "fileCount":
        return ("your tracked file count grew from %s to %s files (%s more) since the "
                "last sweep" % (p, c, ch))
    if name == "duplicationPercent":
        return ("duplication rose from %s%% to %s%% of your code since the last sweep"
                % (p, c))
    if name == "todoCount":
        return ("TODO/FIXME markers grew from %s to %s (%s more) since the last sweep"
                % (p, c, ch))
    if name == "majorsBehind":
        return ("dependencies a major version or more behind went from %s to %s since "
                "the last sweep" % (p, c))
    if name == "vulnCount":
        noun = "vulnerability" if change == 1 else "vulnerabilities"
        return "%s new %s since the last sweep (%s → %s)" % (ch, noun, p, c)
    if name == "couplingEdges":
        noun = "cross-cluster edge" if change == 1 else "cross-cluster edges"
        return "%s more %s since the last sweep (%s → %s)" % (ch, noun, p, c)
    if name == "suiteRuntimeSeconds":
        pct_part = ("%s slower" % _fmt_pct(pct)) if pct else "slower"
        return "your suite got %s since the last sweep (%ss → %ss)" % (pct_part, p, c)
    if name == "suiteSkipped":
        noun = "skipped test" if change == 1 else "skipped tests"
        return "%s more %s since the last sweep (%s → %s)" % (ch, noun, p, c)
    return "%s went from %s to %s since the last sweep" % (name, p, c)


def _crosses(kind, spec, prev, change):
    if kind == "none":
        return False
    if change <= 0:            # only worsening (upward) movement crosses
        return False
    if kind == "any-increase":
        return True
    limit = spec.get("limit")
    if not _is_number(limit):
        return False
    if kind == "absolute":
        return change >= limit
    if kind == "relative":
        if prev is None or prev <= 0:   # no usable base — no crossing, no ZeroDivisionError
            return False
        return (change / prev) >= limit
    return False


def _valid_threshold_override(spec):
    """True when an override is a complete, usable per-kind threshold."""
    if not isinstance(spec, dict):
        return False
    kind = spec.get("kind")
    if kind not in THRESHOLD_KINDS:
        return False
    if kind in ("none", "any-increase"):
        return True
    if kind in ("relative", "absolute"):
        limit = spec.get("limit")
        if not _is_number(limit):
            return False
        return float(limit) >= 0
    return False


def crossings(prev_vitals, cur_vitals, thresholds=None, *, notes_out=None,
              prev_completeness=None, cur_completeness=None):
    """Threshold crossings between two sweeps. Defaults come from DRIFT_THRESHOLDS;
    `thresholds` (the guardian.md config layer) overrides entry by entry.

    Only worsening movement crosses; an improvement lands in `delta` and nothing else. A
    vital missing from either side — first sweep, or not collected — never crosses, which
    is what keeps the first sweep quiet. Partial vitals cross only when the previous
    sweep's partial state carried the same gap reason.

    Invalid overrides are ignored: the authoritative default is retained and a note is
    appended to `notes_out` when provided. A typo must never silently disable detection."""
    merged = dict(DRIFT_THRESHOLDS)
    if isinstance(thresholds, dict):
        for key, spec in thresholds.items():
            if not isinstance(spec, dict):
                continue
            if _valid_threshold_override(spec):
                merged[key] = spec
                continue
            note = (
                "invalid threshold override for %r retained default "
                "(override must be a complete per-kind spec)" % (key,)
            )
            if notes_out is not None:
                notes_out.append(note)
    moves = delta(prev_vitals, cur_vitals,
                  prev_completeness=prev_completeness,
                  cur_completeness=cur_completeness)
    out = []
    for name in VITALS:
        move = moves.get(name)
        spec = merged.get(name)
        if move is None or not isinstance(spec, dict):
            continue
        if not _crosses(spec.get("kind"), spec, move["prev"], move["change"]):
            continue
        out.append({
            "vital": name,
            "prev": move["prev"],
            "cur": move["cur"],
            "change": move["change"],
            "pct": move["pct"],
            "threshold": dict(spec),
            "sentence": _sentence(name, move["prev"], move["cur"], move["change"],
                                  move["pct"]),
        })
    return out


# ----------------------------------------------------------------- append-only trend file

def _today(now=None):
    return now or time.strftime("%Y-%m-%d")


def _provenance(created):
    return {"schemaVersion": TREND_SCHEMA_VERSION, "file": TREND_FILE_ID,
            "created": created}


def _is_provenance(obj):
    """True for any object that *claims* to be trend provenance (file id match).

    Callers that need the supported contract must use `_provenance_gate` — a file-id
    match alone is not enough to treat the stream as readable or appendable."""
    return isinstance(obj, dict) and obj.get("file") == TREND_FILE_ID


def _provenance_gate(obj):
    """Validate a candidate first-line provenance object → (status, provenance|None).

    CONVENTIONS §2.2 / §6.4: the first non-blank JSONL object must be the supported
    provenance shape; missing/malformed/newer fail closed with no records."""
    if not isinstance(obj, dict):
        return "malformed", None
    if obj.get("file") != TREND_FILE_ID:
        return "malformed", None
    ver = obj.get("schemaVersion")
    if not isinstance(ver, int) or isinstance(ver, bool):
        return "malformed", None
    if ver > TREND_SCHEMA_VERSION:
        return "newer", None
    if ver != TREND_SCHEMA_VERSION:
        return "malformed", None
    created = obj.get("created")
    if not isinstance(created, str) or not created.strip():
        return "malformed", None
    return "ok", obj


def _first_nonblank_obj(text):
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        return _parse_line(line)
    return None


def _parse_line(line):
    try:
        obj = json.loads(line)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def append_unlocked(cwd, vitals, *, sweep_id, swept_sha=None, root=None, now=None,
                    completeness=None):
    """Append one sweep record to vitals.jsonl WITHOUT taking the sweep lock.

    **The two entry points are load-bearing.** The sweep lock is not reentrant
    (`file_lock` uses exclusive lock-file creation), so a writer that acquires it while
    `finalize` already holds it self-deadlocks. `finalize` calls THIS function; standalone
    callers use `append`, which takes the lock and delegates here.

    Append-only: existing lines are never rewritten or truncated. Idempotent on `sweepId`
    (a retried finalize does not double-append); keyed on `sweepId`, never `sweptSha`, since
    two sweeps of the same commit are two sweeps. A torn trailing line from a crashed append
    is kept as evidence, reported as `recovered`, and appended past. Never runs git, never
    commits. An I/O failure returns ok=False rather than raising — losing a trend point must
    never fail a sweep.

    **Fail closed on unknown schema:** an existing trend whose first non-blank line is not
    the supported provenance (missing / malformed / newer) is not appended into — a plugin
    rollback must not write v1 records into a future-schema stream."""
    path = guardian_store.vitals_path(cwd, root)
    known = {k: v for k, v in (vitals or {}).items() if k in VITALS}
    dropped = sorted(k for k in (vitals or {}) if k not in VITALS)
    comp_known = {}
    if isinstance(completeness, dict):
        comp_known = {k: v for k, v in completeness.items() if k in VITALS}

    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            existing = fh.read()
    except FileNotFoundError:
        existing = None
    except OSError as exc:
        return {"ok": False, "path": path, "reason": "read failed: %s" % exc}

    if existing and existing.strip():
        status, _prov = _provenance_gate(_first_nonblank_obj(existing))
        if status != "ok":
            return {"ok": False, "path": path, "reason": "trend-%s" % status,
                    "status": status}
        for line in existing.splitlines():
            obj = _parse_line(line)
            if obj is not None and not _is_provenance(obj) and obj.get("sweepId") == sweep_id:
                return {"ok": True, "path": path, "skipped": "duplicate-sweepId",
                        "sweepId": sweep_id}

    recovered = None
    prefix = ""
    if existing:
        if not existing.endswith("\n"):
            recovered = "torn-trailing-line"
            prefix = "\n"
        else:
            body = [ln for ln in existing.splitlines() if ln.strip()]
            if body and _parse_line(body[-1]) is None:
                recovered = "torn-trailing-line"

    created = not existing or not existing.strip()
    stamp = _today(now)
    record = {"date": stamp, "sweepId": sweep_id, "sweptSha": swept_sha,
              "vitals": known}
    if comp_known:
        record["completeness"] = comp_known
    payload = prefix
    if created:
        payload += json.dumps(_provenance(stamp)) + "\n"
    payload += json.dumps(record) + "\n"

    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
    except OSError as exc:
        return {"ok": False, "path": path, "reason": str(exc)}

    out = {"ok": True, "path": path, "appended": True, "created": created,
           "sweepId": sweep_id}
    if recovered:
        out["recovered"] = recovered
    if dropped:
        out["droppedKeys"] = dropped
    return out


def append(cwd, vitals, *, sweep_id, swept_sha=None, root=None, now=None,
           completeness=None):
    """Append one sweep record under the sweep lock, for standalone callers.

    **Do NOT call this from `finalize`** — it already holds the (non-reentrant) sweep lock,
    so acquiring it again self-deadlocks; `finalize` calls `append_unlocked`. All the
    append-only, idempotency and recovery behavior lives there."""
    lock_path = guardian_store.sweep_lock_path(cwd, root)
    try:
        file_lock.acquire(lock_path, ttl=guardian_store.SWEEP_LOCK_TTL)
    except file_lock.LockHeld as exc:
        return {"ok": False, "reason": "raced", "lockHeld": exc.holder}
    except OSError as exc:
        return {"ok": False, "reason": "lock failed: %s" % exc}
    try:
        return append_unlocked(cwd, vitals, sweep_id=sweep_id, swept_sha=swept_sha,
                               root=root, now=now, completeness=completeness)
    finally:
        file_lock.release(lock_path)


def completeness_for_sweep(cwd, sweep_id, *, root=None):
    """Return completeness for the trend record whose ``sweepId`` matches, or {} if unknown.

    Joins on identity rather than taking the newest trend row — a trend that advanced
    past a stale snapshot must not supply completeness for the wrong sweep."""
    if not isinstance(sweep_id, str) or not sweep_id.strip():
        return {}
    trend = read_trend(cwd, root=root)
    if trend.get("status") != "ok":
        return {}
    for rec in reversed(trend.get("records") or []):
        if rec.get("sweepId") == sweep_id:
            comp = rec.get("completeness")
            return comp if isinstance(comp, dict) else {}
    return {}


def read_trend(cwd, *, root=None, limit=None):
    """Read vitals.jsonl → {status, path, provenance, records, malformed}.

    The first non-blank JSONL object must be the exact supported provenance shape
    (schemaVersion == TREND_SCHEMA_VERSION, file == guardian-vitals, created set).
    Missing, malformed, or newer provenance fails closed: status is non-ok and records
    are empty — never silently presented as current history. Unparseable body lines are
    counted in `malformed`. `limit` tails the last N records."""
    path = guardian_store.vitals_path(cwd, root)
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except FileNotFoundError:
        return {"status": "absent", "path": path, "provenance": None,
                "records": [], "malformed": 0}
    except OSError as exc:
        return {"status": "unreadable", "path": path, "provenance": None,
                "records": [], "malformed": 0, "note": str(exc)}

    if not text.strip():
        return {"status": "malformed", "path": path, "provenance": None,
                "records": [], "malformed": 0,
                "note": "vitals trend has no provenance record"}

    first = _first_nonblank_obj(text)
    status, provenance = _provenance_gate(first)
    if status != "ok":
        return {"status": status, "path": path, "provenance": None,
                "records": [], "malformed": 0,
                "note": "vitals trend provenance is %s" % status}

    records = []
    malformed = 0
    seen_first = False
    for line in text.splitlines():
        if not line.strip():
            continue
        obj = _parse_line(line)
        if not seen_first:
            seen_first = True
            continue  # provenance already validated
        if obj is None:
            malformed += 1
            continue
        if _is_provenance(obj):
            # A second provenance claim mid-file is not a sweep record.
            malformed += 1
            continue
        if "sweepId" not in obj:
            malformed += 1
            continue
        records.append(obj)
    if isinstance(limit, int) and limit > 0:
        records = records[-limit:]
    return {"status": "ok", "path": path, "provenance": provenance,
            "records": records, "malformed": malformed}


def main(argv=None):
    ap = argparse.ArgumentParser(description="guardian vitals: collect + trend")
    sub = ap.add_subparsers(dest="cmd", required=True)

    cp = sub.add_parser("collect", help="collect the vital set (no verify run)")
    cp.add_argument("--cwd", default=".")
    cp.add_argument("--root", default=None)

    rp = sub.add_parser("read", help="tail the append-only trend file")
    rp.add_argument("--cwd", default=".")
    rp.add_argument("--root", default=None)
    rp.add_argument("--limit", type=int, default=None)

    args = ap.parse_args(argv)
    try:
        if args.cmd == "collect":
            out = collect(args.cwd, root=args.root)
        else:
            out = read_trend(args.cwd, root=args.root, limit=args.limit)
    except Exception as exc:
        out = {"error": str(exc)}
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
