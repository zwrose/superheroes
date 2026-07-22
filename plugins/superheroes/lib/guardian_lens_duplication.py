#!/usr/bin/env python3
# plugins/superheroes/lib/guardian_lens_duplication.py
"""Duplication-drift lens — jscpd detects file pairs; difflib re-measures them.

Stdlib-only. jscpd's per-clone `lines` field is NOT a count of duplicated source lines
for markdown-embedded code (asymmetric spans are common). This lens treats jscpd as a
detector only and prices / thresholds off difflib.SequenceMatcher(autojunk=False).
"""
import difflib
import json
import os
import subprocess
import sys
import tempfile
import time

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import guardian_lens  # noqa: E402
import guardian_tools  # noqa: E402

MIN_BLOCK_LINES = 5
TOP_N = 25

# difflib re-measure budgets — rank by jscpd proxy first, then measure within caps.
MAX_PAIRS_MEASURED = 400
MAX_MEASURE_FILE_BYTES = 2_000_000
MEASURE_TIME_BUDGET_SECONDS = 20

# Pricing rule (DoD): duplication consequences speak ONLY of change cost and
# consistency risk — never bug/defect/fault risk.
CONSEQUENCE_TEMPLATE = (
    "State the CHANGE COST and CONSISTENCY RISK of this duplicated block: every "
    "future edit must find all N copies and keep them aligned. Speak only of "
    "maintenance burden and drift across copies — never imply the copies are "
    "unsafe or that divergence itself proves a failure mode."
)

VALIDATION_GUIDANCE = (
    "Validate that the pair is a real duplicated block worth tracking for change "
    "cost and consistency risk (every future edit must find all copies). Reject "
    "noise and generated twins. Price it only as change-cost / consistency risk — "
    "never as a claim that the copies are unsafe or that divergence proves a "
    "failure mode."
)


def _strip_format_suffix(name):
    """jscpd's `name` may carry a ':<format>' suffix — strip it."""
    if not isinstance(name, str) or not name:
        return ""
    if ":" not in name:
        return name
    base, suffix = name.rsplit(":", 1)
    if suffix and "/" not in suffix and "\\" not in suffix:
        return base
    return name


def _pair_id(path_a, path_b):
    a, b = sorted([path_a, path_b])
    return "duplication:%s|%s" % (a, b)


def _repo_rel(cwd, path):
    """Normalize a jscpd path to a repo-relative path."""
    if os.path.isabs(path):
        try:
            return os.path.relpath(path, cwd)
        except ValueError:
            return path
    return path


def _read_normalized_lines(path):
    """Return rstrip'd lines, or None if unreadable/binary."""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return None
    if b"\0" in data:
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return [ln.rstrip() for ln in text.splitlines()]


def _measure_pair(path_a, path_b):
    """difflib re-measure. Returns (longestBlockLines, sharedLines) or None."""
    a_lines = _read_normalized_lines(path_a)
    b_lines = _read_normalized_lines(path_b)
    if a_lines is None or b_lines is None:
        return None
    # autojunk=False is REQUIRED — autojunk=True changes sharedLines on real input.
    sm = difflib.SequenceMatcher(None, a_lines, b_lines, autojunk=False)
    longest = 0
    shared = 0
    for _i, _j, n in sm.get_matching_blocks():
        if n > longest:
            longest = n
        if n >= MIN_BLOCK_LINES:
            shared += n
    return (longest, shared)


def _file_size_bytes(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def _validate_report(report):
    """Require a dict with a list-valued 'duplicates' field — else LensDegraded.

    A jscpd upgrade that returns valid JSON without `duplicates` as a list must not
    quietly erase the tracked baseline with an empty digest.
    """
    if not isinstance(report, dict):
        raise guardian_lens.LensDegraded(
            "jscpd report contract mismatch: expected a JSON object")
    dups = report.get("duplicates")
    if not isinstance(dups, list):
        raise guardian_lens.LensDegraded(
            "jscpd report contract mismatch: missing list-valued 'duplicates' field")


def _pairs_from_report(report):
    """Return [(path_a, path_b, jscpd_lines, is_self, tokens), ...] for each well-formed duplicate.

    Raises LensDegraded when any entry is malformed (missing usable
    firstFile.name / secondFile.name) — a bad entry must not be silently skipped.
    Names the malformed count and the first offending index so the shell can
    preserve the prior baseline.
    """
    dups = report.get("duplicates") if isinstance(report, dict) else None
    if not isinstance(dups, list):
        return []
    pairs = []
    malformed = 0
    first_bad_index = None
    for idx, dup in enumerate(dups):
        if not isinstance(dup, dict):
            malformed += 1
            if first_bad_index is None:
                first_bad_index = idx
            continue
        first = dup.get("firstFile")
        second = dup.get("secondFile")
        if not isinstance(first, dict) or not isinstance(second, dict):
            malformed += 1
            if first_bad_index is None:
                first_bad_index = idx
            continue
        a = _strip_format_suffix(first.get("name"))
        b = _strip_format_suffix(second.get("name"))
        if not a or not b:
            malformed += 1
            if first_bad_index is None:
                first_bad_index = idx
            continue
        lines = dup.get("lines")
        try:
            lines = int(lines)
        except (TypeError, ValueError):
            lines = 0
        tokens = dup.get("tokens")
        try:
            tokens = int(tokens)
        except (TypeError, ValueError):
            tokens = 0
        pairs.append((a, b, lines, a == b, tokens))
    if malformed:
        raise guardian_lens.LensDegraded(
            "jscpd report contract mismatch: %d malformed duplicate entr%s "
            "(first offending index %d; each needs usable firstFile.name and "
            "secondFile.name)"
            % (malformed, "y" if malformed == 1 else "ies", first_bad_index))
    return pairs


def _is_unmeasured(rec):
    return isinstance(rec, dict) and rec.get("unmeasured") is True


def _carry_or_unmeasured(pid, prev_pairs, digest_pairs):
    """Carry prior digest metrics for an unmeasured-but-present pair, or mark unmeasured.

    Returning True means a prior *measured* entry was carried forward; False means the
    pair is recorded as explicit ``{"unmeasured": True}`` (caller records pairsUnmeasured).
    Never omit a still-present pair — omission invents `new` drift on the next measure.
    """
    prev_rec = prev_pairs.get(pid) if isinstance(prev_pairs, dict) else None
    if isinstance(prev_rec, dict) and not prev_rec.get("unmeasured"):
        try:
            longest = int(prev_rec.get("longest") or 0)
        except (TypeError, ValueError):
            longest = 0
        try:
            shared = int(prev_rec.get("shared") or 0)
        except (TypeError, ValueError):
            shared = 0
        digest_pairs[pid] = {
            "longest": longest,
            "shared": shared,
            "carriedForward": True,
        }
        return True
    digest_pairs[pid] = {"unmeasured": True}
    return False


def _count_drift_suppressed_by_cap(prev_pairs, cur_pairs, surface_ids):
    """How many new/worsened ids exist in the full digest but not the capped surface."""
    if not surface_ids:
        return 0
    raw = _diff_pairs_raw(prev_pairs, cur_pairs)
    suppressed = 0
    for pid in raw["new"] + raw["worsened"]:
        if pid not in surface_ids:
            suppressed += 1
    return suppressed


def _diff_pairs_raw(prev_pairs, cur_pairs):
    """Full-digest drift (ignores presentation cap)."""
    if prev_pairs is None:
        return {
            "new": sorted(
                pid for pid, rec in cur_pairs.items() if not _is_unmeasured(rec)
            ),
            "worsened": [],
            "resolved": [],
        }
    new = []
    worsened = []
    resolved = []
    for pid, cur_rec in cur_pairs.items():
        if _is_unmeasured(cur_rec):
            continue
        if pid not in prev_pairs:
            new.append(pid)
            continue
        prev_rec = prev_pairs.get(pid) or {}
        if _is_unmeasured(prev_rec):
            # unmeasured → measured: already known, not `new`, not worsened
            continue
        try:
            cur_shared = int((cur_rec or {}).get("shared", 0))
        except (TypeError, ValueError):
            cur_shared = 0
        try:
            prev_shared = int((prev_rec or {}).get("shared", 0))
        except (TypeError, ValueError):
            prev_shared = 0
        if cur_shared > prev_shared:
            worsened.append(pid)
    for pid, prev_rec in prev_pairs.items():
        if pid in cur_pairs:
            continue
        if _is_unmeasured(prev_rec):
            # Unmeasured entries never count as resolved.
            continue
        resolved.append(pid)
    return {
        "new": sorted(new),
        "worsened": sorted(worsened),
        "resolved": sorted(resolved),
    }


def rank_and_cap(candidates, top_n=TOP_N):
    ranked = sorted(candidates, key=lambda c: (-c["sharedLines"], c["id"]))
    return ranked[:top_n]


def apply_cap(candidates, top_n=TOP_N, always_include_clone_lines=None):
    """Top-N by sharedLines, unioned with every pair at/above absolute clone threshold."""
    before = len(candidates)
    capped = rank_and_cap(candidates, top_n=top_n)
    union_added = 0
    if always_include_clone_lines is not None:
        seen = {c["id"] for c in capped}
        extras = []
        for c in candidates:
            if c["id"] in seen:
                continue
            try:
                longest = int(c.get("longestBlockLines") or 0)
            except (TypeError, ValueError):
                continue
            if longest >= always_include_clone_lines:
                extras.append(c)
                seen.add(c["id"])
        extras.sort(key=lambda c: (-c["sharedLines"], c["id"]))
        capped = list(capped) + extras
        union_added = len(extras)
    return capped, {
        "candidatesBeforeCap": before,
        "capApplied": min(before, top_n),
        "redLineUnionAdded": union_added,
    }


class DuplicationLens:
    name = "duplication"
    # 2.0.0: digest persists the full measured set (+ explicit unmeasured markers) and
    # surfaceIds; incompatible with the 1.0.0 capped-only shape — bump so the shell
    # records a quiet baseline instead of mass false drift on upgrade.
    collector_version = "2.0.0"
    required_facts = ()
    cost = {
        "collectorSeconds": 0.9,
        "note": "jscpd over the repo + difflib re-measure of deduped file pairs",
    }
    consequence_template = CONSEQUENCE_TEMPLATE
    validation_guidance = VALIDATION_GUIDANCE

    def __init__(self):
        # Sweep ordering dependency: collect() always runs before red_lines() on the
        # same instance. red_lines() reads _prev_digest cached here (from ctx) to decide
        # whether a large clone is fresh or already known.
        self._prev_digest = None
        self._clone_lines_threshold = None
        self._surface_ids = None

    def collect(self, ctx):
        cwd = ctx.get("cwd") or "."
        cwd = os.path.realpath(cwd)
        # Cache previous digest for red_lines() — see __init__ ordering comment.
        self._prev_digest = ctx.get("prev_digest")

        config = ctx.get("config") or {}
        self._clone_lines_threshold = None
        if isinstance(config, dict) and isinstance(config.get("thresholds"), dict):
            if "cloneLines" in config["thresholds"]:
                self._clone_lines_threshold = config["thresholds"]["cloneLines"]

        res = guardian_tools.resolve("jscpd", cwd)
        if not res.get("found"):
            raise guardian_lens.LensDegraded(
                guardian_tools.missing_tool_reason(
                    "jscpd", rejection=res.get("rejection")))

        runner = ctx.get("run") or subprocess.run
        jscpd_version = guardian_tools.version("jscpd", cwd, run=runner)
        repo_config_present = os.path.isfile(os.path.join(cwd, ".jscpd.json"))

        with tempfile.TemporaryDirectory(prefix="guardian-jscpd-") as tmp:
            # OUR flags LAST so they win over any repo .jscpd.json (owner config is
            # otherwise honored — we only record whether one was present).
            # Force --output into the temp dir so the report cannot land in the repo.
            argv = [
                res["path"], cwd,
                "--reporters", "json",
                "--output", tmp,
                "--silent",
                "--min-lines", str(MIN_BLOCK_LINES),
                "--min-tokens", "50",
            ]
            try:
                proc = runner(
                    argv, capture_output=True, text=True, cwd=cwd, timeout=600)
            except Exception as exc:
                raise guardian_lens.LensDegraded(
                    "jscpd invocation failed: %s: %s" % (type(exc).__name__, exc))
            if getattr(proc, "returncode", 1) != 0:
                raise guardian_lens.LensDegraded(
                    "jscpd exited non-zero (exit %s)" % getattr(proc, "returncode", "?"))

            report_path = os.path.join(tmp, "jscpd-report.json")
            if not os.path.isfile(report_path):
                raise guardian_lens.LensDegraded(
                    "jscpd produced no jscpd-report.json in output dir")
            try:
                with open(report_path, encoding="utf-8") as fh:
                    report = json.load(fh)
            except (OSError, ValueError, TypeError) as exc:
                raise guardian_lens.LensDegraded(
                    "jscpd report unparseable: %s" % exc)

        _validate_report(report)

        # Deduplicate unordered pairs; keep max jscpd lines + tokens as rank proxy.
        # Shape: pid -> (rel_a, rel_b, j_lines, j_tokens)
        pair_jscpd = {}
        self_clones_deferred = 0
        jscpd_clones_reported = 0
        for path_a, path_b, j_lines, is_self, j_tokens in _pairs_from_report(report):
            jscpd_clones_reported += 1
            rel_a = _repo_rel(cwd, path_a)
            rel_b = _repo_rel(cwd, path_b)
            if is_self or rel_a == rel_b:
                self_clones_deferred += 1
                continue
            pid = _pair_id(rel_a, rel_b)
            prev = pair_jscpd.get(pid)
            if prev is None:
                pair_jscpd[pid] = (rel_a, rel_b, j_lines, j_tokens)
            else:
                pair_jscpd[pid] = (
                    prev[0], prev[1],
                    max(prev[2], j_lines),
                    max(prev[3], j_tokens),
                )

        # Rank BEFORE measuring — cheap jscpd proxy keeps the budget on promising pairs.
        ranked = sorted(
            pair_jscpd.items(),
            key=lambda item: (-item[1][3], -item[1][2], item[0]),
        )
        pairs_considered = len(ranked)

        red_threshold = self._clone_lines_threshold
        if red_threshold is None:
            red_threshold = guardian_lens.RED_LINE_THRESHOLDS["cloneLines"]

        # A2: pairs whose jscpd-reported lines could reach the clone threshold must be
        # measured even past MAX_PAIRS_MEASURED — token-proxy rank must not hide an
        # absolute red line forever.
        must_measure = set()
        for pid, (_ra, _rb, j_lines, _jt) in ranked:
            try:
                if int(j_lines) >= int(red_threshold):
                    must_measure.add(pid)
            except (TypeError, ValueError):
                continue

        measure_order = []
        seen_measure = set()
        for pid, data in ranked[:MAX_PAIRS_MEASURED]:
            measure_order.append((pid, data))
            seen_measure.add(pid)
        measurement_union_added = 0
        for pid, data in ranked:
            if pid in seen_measure:
                continue
            if pid in must_measure:
                measure_order.append((pid, data))
                seen_measure.add(pid)
                measurement_union_added += 1
        deferred = [(pid, data) for pid, data in ranked if pid not in seen_measure]

        prev_pairs = {}
        if isinstance(self._prev_digest, dict):
            raw_prev = self._prev_digest.get("pairs")
            if isinstance(raw_prev, dict):
                prev_pairs = raw_prev

        candidates = []
        digest_pairs = {}
        unreadable = 0
        pairs_measured = 0
        pairs_skipped_budget = 0
        pairs_skipped_oversize = 0
        pairs_carried_forward = 0
        pairs_unmeasured = 0
        budget_exhausted = None
        t0 = time.monotonic()

        def _skip_unmeasured(pid):
            nonlocal pairs_carried_forward, pairs_unmeasured
            if _carry_or_unmeasured(pid, prev_pairs, digest_pairs):
                pairs_carried_forward += 1
            else:
                pairs_unmeasured += 1

        for pid, (rel_a, rel_b, j_lines, _j_tokens) in measure_order:
            if budget_exhausted is None:
                if (time.monotonic() - t0) >= MEASURE_TIME_BUDGET_SECONDS:
                    budget_exhausted = "time"

            if budget_exhausted is not None:
                pairs_skipped_budget += 1
                _skip_unmeasured(pid)
                continue

            abs_a = os.path.join(cwd, rel_a)
            abs_b = os.path.join(cwd, rel_b)
            size_a = _file_size_bytes(abs_a)
            size_b = _file_size_bytes(abs_b)
            if (
                size_a is None or size_b is None
                or size_a > MAX_MEASURE_FILE_BYTES
                or size_b > MAX_MEASURE_FILE_BYTES
            ):
                if size_a is None or size_b is None:
                    unreadable += 1
                else:
                    pairs_skipped_oversize += 1
                _skip_unmeasured(pid)
                continue

            measured = _measure_pair(abs_a, abs_b)
            if measured is None:
                unreadable += 1
                _skip_unmeasured(pid)
                continue
            pairs_measured += 1
            longest, shared = measured
            if longest < MIN_BLOCK_LINES:
                continue
            files = sorted([rel_a, rel_b])
            candidates.append({
                "id": pid,
                "files": files,
                "longestBlockLines": longest,
                "sharedLines": shared,
                "jscpdReportedLines": j_lines,
                "metric": shared,
            })
            digest_pairs[pid] = {"longest": longest, "shared": shared}

        if deferred and budget_exhausted is None:
            budget_exhausted = "pairs"
        for pid, _data in deferred:
            pairs_skipped_budget += 1
            _skip_unmeasured(pid)

        capped, cap_diag = apply_cap(
            candidates, top_n=TOP_N, always_include_clone_lines=red_threshold,
        )
        surface_ids = [c["id"] for c in capped]
        self._surface_ids = set(surface_ids)

        digest = {
            "schemaVersion": 1,
            "toolVersions": {"jscpd": jscpd_version},
            "pairs": digest_pairs,
            "surfaceIds": surface_ids,
        }
        drift_suppressed = _count_drift_suppressed_by_cap(
            prev_pairs, digest_pairs, self._surface_ids,
        )
        diagnostics = {
            "toolVersions": {"jscpd": jscpd_version},
            "jscpdClonesReported": jscpd_clones_reported,
            "pairsConsidered": pairs_considered,
            "pairsMeasured": pairs_measured,
            "pairsSkippedBudget": pairs_skipped_budget,
            "pairsSkippedOversize": pairs_skipped_oversize,
            "pairsCarriedForward": pairs_carried_forward,
            "pairsUnmeasured": pairs_unmeasured,
            "budgetExhausted": budget_exhausted,
            "measurementUnionAdded": measurement_union_added,
            "driftSuppressedByCap": drift_suppressed,
            "selfClonesDeferred": self_clones_deferred,
            "unreadableFiles": unreadable,
            "minBlockLines": MIN_BLOCK_LINES,
            "maxPairsMeasured": MAX_PAIRS_MEASURED,
            "maxMeasureFileBytes": MAX_MEASURE_FILE_BYTES,
            "measureTimeBudgetSeconds": MEASURE_TIME_BUDGET_SECONDS,
            "topN": TOP_N,
            "candidatesBeforeCap": cap_diag["candidatesBeforeCap"],
            "capApplied": cap_diag["capApplied"],
            "redLineUnionAdded": cap_diag["redLineUnionAdded"],
            "repoConfigPresent": repo_config_present,
        }
        return {
            "candidates": capped,
            "digest": digest,
            "diagnostics": diagnostics,
        }

    def diff(self, prev_digest, cur_digest):
        cur_pairs = {}
        surface = None
        if isinstance(cur_digest, dict):
            if isinstance(cur_digest.get("pairs"), dict):
                cur_pairs = cur_digest["pairs"]
            raw_surface = cur_digest.get("surfaceIds")
            if isinstance(raw_surface, list):
                surface = set(raw_surface)
        prev_pairs = None
        if isinstance(prev_digest, dict) and isinstance(prev_digest.get("pairs"), dict):
            prev_pairs = prev_digest["pairs"]
        raw = _diff_pairs_raw(prev_pairs, cur_pairs)
        if surface is None:
            raw["driftSuppressedByCap"] = 0
            return raw
        filtered_new = [pid for pid in raw["new"] if pid in surface]
        filtered_worsened = [pid for pid in raw["worsened"] if pid in surface]
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
        """Price red lines off the RE-MEASURED longest block, never jscpd's lines.

        Depends on collect() having cached _prev_digest on this instance first
        (sweep always calls collect() before red_lines() on the same lens object).
        Threshold comes from owner-calibrated config when collect() cached it;
        else RED_LINE_THRESHOLDS.
        """
        threshold = self._clone_lines_threshold
        if threshold is None:
            threshold = guardian_lens.RED_LINE_THRESHOLDS["cloneLines"]
        prev_pairs = {}
        prev = self._prev_digest
        if isinstance(prev, dict) and isinstance(prev.get("pairs"), dict):
            prev_pairs = prev["pairs"]

        out = []
        for c in candidates or []:
            if not isinstance(c, dict):
                continue
            try:
                longest = int(c.get("longestBlockLines") or 0)
            except (TypeError, ValueError):
                longest = 0
            if longest < threshold:
                continue
            cid = c.get("id")
            if not cid:
                continue
            prev_rec = prev_pairs.get(cid)
            if prev_rec is None:
                fresh = True
                grew = False
            elif _is_unmeasured(prev_rec):
                # Known-but-unmeasured → first real measure is not "fresh" drift.
                fresh = False
                grew = False
            else:
                fresh = False
                try:
                    prev_longest = int(prev_rec.get("longest") or 0)
                except (TypeError, ValueError):
                    prev_longest = 0
                grew = longest > prev_longest
            if fresh or grew:
                out.append({
                    "kind": "large-fresh-clone",
                    "id": cid,
                    "detail": (
                        "re-measured longestBlockLines=%d (threshold=%d); "
                        "priced from difflib, not jscpdReportedLines"
                        % (longest, threshold)
                    ),
                })
        return out

    def degrade(self, reason):
        return {"lens": self.name, "degraded": True, "reason": reason}


LENS = DuplicationLens()
