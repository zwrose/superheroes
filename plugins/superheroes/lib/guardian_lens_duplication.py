#!/usr/bin/env python3
# plugins/superheroes/lib/guardian_lens_duplication.py
"""Duplication-drift lens — jscpd detects file pairs; difflib re-measures them.

Stdlib-only. jscpd's per-clone `lines` field is NOT a count of duplicated source lines
for markdown-embedded code (asymmetric spans are common). This lens treats jscpd as a
detector only and prices / thresholds off difflib.SequenceMatcher(autojunk=False).

Tool invocation routes through ``guardian_collect.run_tool`` (never subprocess directly):
in production it goes through ``guardian_tools.invoke``'s hardening; in tests / conformance
it goes through the injected ``ctx["run"]`` seam. jscpd's json reporter writes a FILE, but
``run_tool`` captures stdout — so the reporter is aimed at a ``/dev/stdout`` symlink inside a
throwaway temp dir and the JSON object is parsed off stdout (a trailing "report saved"
summary line is ignored).
"""
import difflib
import json
import os
import shutil
import sys
import tempfile
import time

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import guardian_collect as gc  # noqa: E402
import guardian_lens  # noqa: E402

MIN_BLOCK_LINES = 5
TOP_N = 25

# jscpd is handed the tracked-file census as explicit operands (never the repo dir), so a
# very large repo could push the argv past the kernel's ARG_MAX. macOS ARG_MAX is 262144
# bytes and the sanitized child env consumes a share of that; cap the operand payload well
# under it. The bound is measured on the ABSOLUTIZED payload (invoke prepends the repo
# realpath + a path separator to every operand before execve), not the repo-relative bytes,
# so the guard reflects the real argv the kernel sees. On overflow the lens degrades
# HONESTLY (not-collected) rather than silently truncating the file list or falling back to
# scanning cwd (which would re-open #564).
MAX_TRACKED_OPERAND_BYTES = 100_000

# difflib re-measure budgets — rank by jscpd proxy first, then measure within caps.
MAX_PAIRS_MEASURED = 400
MAX_MEASURE_FILE_BYTES = 2_000_000
MEASURE_TIME_BUDGET_SECONDS = 20
# I2: pairs whose jscpd lines reach the clone threshold are measured even past the time
# budget (a red line must not be hidden by the time cap) — but the must-measure set is
# BOUNDED so it cannot itself defeat the declared time bound.
MAX_MUST_MEASURE = 50

# The one duplication red-line kind, sourced from the authoritative tuple (I3) — not a
# bare literal. Fails closed at import if guardian_lens drops the kind.
_RED_LINE_KIND = next(
    k for k in guardian_lens.RED_LINE_KINDS if k == "large-fresh-clone")

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


class _ReportContractError(Exception):
    """A jscpd report that is structurally usable JSON but violates the report contract.

    Local to this module (the old shared ``guardian_lens.LensDegraded`` type is gone).
    ``collect()`` catches it and returns ``not-collected`` so a contract mismatch never
    quietly erases the tracked baseline with an empty digest.
    """


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


def _git(ctx, cwd, args, timeout=gc.DEFAULT_TIMEOUT):
    """Run a git subcommand via run_tool with an absolute ``-C`` repo target.

    ``git -C <abs repo>`` targets the repo even though invoke runs collectors from a
    neutral cwd (git resolves via PATH; it is not a repo-local executable).
    """
    return gc.run_tool(["git", "-C", cwd, *args], ctx=ctx, cwd=cwd, timeout=timeout)


def _tracked_existing_files(ctx, cwd):
    """Repo-relative paths that are both ``git ls-files`` tracked and present on disk.

    Shares its census shape with ``guardian_lens_hotspots.tracked_existing_files`` but now
    DIVERGES from it: this lens excludes symlinks (see below) because it hands the census to
    jscpd as content to scan, whereas hotspots only reads churn metadata. Unifying the two
    into a shared param'd helper (symlink policy as a parameter) is a tracked follow-up — do
    NOT extract here. Returns ``(files, None)`` on success or ``(None, reason)`` on a git
    failure — a git failure must NEVER be read as an empty tracked set (that would erase the
    baseline); collect() turns the reason into ``not-collected`` so the prior snapshot
    survives.
    """
    res = _git(ctx, cwd, ["ls-files", "-z"])
    if not res["ok"]:
        return None, res["reason"]
    out = set()
    for raw in (res.get("stdout") or "").split("\0"):
        if not raw:
            continue
        # Never accept brace-rename garbage into the tracked set.
        if "=>" in raw or "{" in raw:
            continue
        full = os.path.join(cwd, raw)
        # Census only regular, NON-symlink files. os.path.isfile follows symlinks, so a
        # tracked symlink whose target is an UNTRACKED file under the repo would pass both
        # this filter and invoke's under-repo check (realpath stays under-repo) — jscpd
        # would then scan the untracked target's bytes, re-opening #564 for the symlink
        # case. A tracked symlink's own "content" is the link, not source to dedup, so
        # excluding it keeps the census faithful to tracked content only.
        if os.path.isfile(full) and not os.path.islink(full):
            out.add(raw)
    return out, None


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


def _decode_report(stdout):
    """Read the jscpd JSON object off captured stdout.

    jscpd's json reporter is aimed at /dev/stdout, so the JSON object appears first; a
    trailing human summary ("report saved to …") is ignored via raw_decode. Returns
    (report, None) on success or (None, reason) so collect() can degrade honestly.
    """
    so = stdout or ""
    i = so.find("{")
    if i < 0:
        return None, "jscpd produced no JSON report"
    try:
        obj, _end = json.JSONDecoder().raw_decode(so[i:])
    except ValueError:
        return None, "unparseable jscpd report"
    return obj, None


def _reported_clone_count(report):
    """jscpd's own summary count of clones (or duplicated lines/tokens) — 0 when absent."""
    stats = report.get("statistics") if isinstance(report, dict) else None
    total = stats.get("total") if isinstance(stats, dict) else None
    if not isinstance(total, dict):
        return 0
    for key in ("clones", "duplicatedLines", "duplicatedTokens"):
        try:
            v = int(total.get(key) or 0)
        except (TypeError, ValueError):
            v = 0
        if v > 0:
            return v
    return 0


def _validate_report(report):
    """Require a dict with a list-valued 'duplicates' field — else _ReportContractError.

    A jscpd upgrade that returns valid JSON without `duplicates` as a list must not
    quietly erase the tracked baseline with an empty digest.
    """
    if not isinstance(report, dict):
        raise _ReportContractError(
            "jscpd report contract mismatch: expected a JSON object")
    dups = report.get("duplicates")
    if not isinstance(dups, list):
        raise _ReportContractError(
            "jscpd report contract mismatch: missing list-valued 'duplicates' field")


def _pairs_from_report(report):
    """Return [(path_a, path_b, jscpd_lines, is_self, tokens), ...] for each well-formed duplicate.

    Raises _ReportContractError when any entry is malformed (missing usable
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
        raise _ReportContractError(
            "jscpd report contract mismatch: %d malformed duplicate entr%s "
            "(first offending index %d; each needs usable firstFile.name and "
            "secondFile.name)"
            % (malformed, "y" if malformed == 1 else "ies", first_bad_index))
    return pairs


def _dedupe_pairs(report, cwd):
    """Normalize the report's duplicate entries into deduped cross-file pairs.

    Returns (pair_jscpd, self_clones_deferred, jscpd_clones_reported), where pair_jscpd
    maps pid -> (rel_a, rel_b, max_jscpd_lines, max_jscpd_tokens). Raises
    _ReportContractError (via _pairs_from_report) on any malformed entry.
    """
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
    return pair_jscpd, self_clones_deferred, jscpd_clones_reported


def _plan_measurement(pair_jscpd, red_threshold):
    """Rank pairs by the cheap jscpd proxy and build the measurement order.

    Honors MAX_PAIRS_MEASURED and unions in the bounded must-measure set (pairs whose
    jscpd lines reach the clone threshold). Returns a dict of plan fields consumed by
    _measure_pairs — collect() reads as orchestration, not a 230-line method.
    """
    # Rank BEFORE measuring — cheap jscpd proxy keeps the budget on promising pairs.
    ranked = sorted(
        pair_jscpd.items(),
        key=lambda item: (-item[1][3], -item[1][2], item[0]),
    )
    pairs_considered = len(ranked)

    # A2/I2: pairs whose jscpd-reported lines could reach the clone threshold must be
    # measured even past MAX_PAIRS_MEASURED and past the time budget — token-proxy rank
    # must not hide an absolute red line. BOUNDED by MAX_MUST_MEASURE (top by rank) so
    # the must-measure set cannot itself defeat the declared time bound.
    must_measure_ranked = []
    for pid, (_ra, _rb, j_lines, _jt) in ranked:
        try:
            if int(j_lines) >= int(red_threshold):
                must_measure_ranked.append(pid)
        except (TypeError, ValueError):
            continue
    must_measure = set(must_measure_ranked[:MAX_MUST_MEASURE])

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
    return {
        "pairs_considered": pairs_considered,
        "must_measure": must_measure,
        "measure_order": measure_order,
        "deferred": deferred,
        "measurement_union_added": measurement_union_added,
    }


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


def _measure_pairs(measure_order, deferred, must_measure, cwd, prev_pairs):
    """Run the difflib re-measurement loop within the size / pairs / time budgets.

    Mandatory (must-measure) pairs are exempt from the TIME budget so an absolute red
    line is never hidden by the time cap (I2). Still-present pairs skipped by any budget
    carry the prior measured metric forward, or record an explicit unmeasured marker —
    never omitted. Returns (candidates, digest_pairs, counts).
    """
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
        mandatory = pid in must_measure
        if budget_exhausted is None:
            if (time.monotonic() - t0) >= MEASURE_TIME_BUDGET_SECONDS:
                budget_exhausted = "time"

        # Only NON-mandatory pairs are skipped by the time budget; a mandatory pair
        # (jscpd lines >= clone threshold, bounded by MAX_MUST_MEASURE) is always
        # measured. The time budget still trips budget_exhausted for accounting.
        if budget_exhausted is not None and not mandatory:
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

    return candidates, digest_pairs, {
        "pairsMeasured": pairs_measured,
        "pairsSkippedBudget": pairs_skipped_budget,
        "pairsSkippedOversize": pairs_skipped_oversize,
        "pairsCarriedForward": pairs_carried_forward,
        "pairsUnmeasured": pairs_unmeasured,
        "budgetExhausted": budget_exhausted,
        "unreadableFiles": unreadable,
    }


def _count_drift_suppressed_by_cap(prev_pairs, cur_pairs, surface_ids):
    """How many new/worsened ids exist in the full digest but not the capped surface.

    M1: a first-ever baseline (``prev_pairs is None``) reports zero suppression — there is
    no prior baseline to have suppressed drift against, so treat prev as None (not {}).
    """
    if prev_pairs is None:
        return 0
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
    # surfaceIds; incompatible with the 1.0.0 capped-only shape.
    # 2.1.0 (#564): the census POPULATION changed — jscpd now scans only git-tracked,
    # on-disk files instead of the whole repo dir (which walked untracked checkouts/ and
    # nested .git internals). The digest SCHEMA is unchanged, but a prior baseline may
    # hold now-excluded junk pairs; bump the version so guardian_sweep.py (any version
    # delta ⇒ lens_new) records a quiet re-baseline FOR DRIFT — the new/worsened/resolved
    # diff runs with _prev_digest treated as absent, so the excluded junk pairs do not
    # surface as false `resolved` drift. This "quiet" scope is DRIFT ONLY: red_lines()
    # still runs unconditionally (with prev_pairs empty on a version-delta sweep), so a
    # genuine tracked clone at/above threshold re-fires as a `large-fresh-clone` red line
    # on the first post-fix sweep. That is by design — a red line must always surface,
    # even across a re-baseline.
    collector_version = "2.1.0"
    required_facts = ()
    cost = {
        "collectorSeconds": 0.9,
        "note": "jscpd over git-tracked files + difflib re-measure of deduped file pairs",
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

    # A single tracked fixture file so the git census is non-empty and jscpd actually
    # fires under the injected conformance seam — otherwise zero tracked files would
    # short-circuit to not-collected and the honesty gate would never be exercised.
    _CONFORMANCE_FIXTURE_FILE = "dup.py"

    def conformance_fixture(self):
        """Files the harness writes into the per-scenario workspace (see
        test_guardian_conformance._scenario_workspace / _lens_fixture_files).

        The census filters by ``os.path.isfile``; this file must exist on disk so it
        survives the filter and becomes a jscpd operand. Its path must EXACTLY match the
        name the ``git`` payload below reports.
        """
        return {self._CONFORMANCE_FIXTURE_FILE: "print('conformance fixture')\n"}

    def conformance_cases(self):
        """Lens-supplied `reported-nonzero-parsed-zero` payload (see lens-contract.md).

        The lens co-fires TWO tools: ``git ls-files`` (the #564 census) then ``jscpd``.
        The harness dispatches stdout per-tool on argv[0] via ``stdout_by_tool`` /
        ``clean_stdout_by_tool``:

        - ``git`` → a NUL-separated ``ls-files -z`` payload naming the conformance_fixture
          file, so the census is non-empty and jscpd runs. It MUST appear in BOTH maps and
          its filename MUST match conformance_fixture exactly — if git is missing from
          either map the harness falls back to the jscpd JSON payload for git, which parses
          to no tracked file → zero tracked → the not-collected short-circuit fires and the
          honesty-gate assertion fails confusingly.
        - ``jscpd`` → the jscpd json reports this lens parses (JSON object first).
          ``stdout`` reports clones in its summary but carries an EMPTY ``duplicates``
          array — the honesty gate degrades it. ``clean_stdout`` reports zero clones — a
          genuine quiet collection.
        """
        reported = json.dumps({
            "statistics": {"total": {"clones": 3, "duplicatedLines": 42}},
            "duplicates": [],
        }) + "\nreport saved to /dev/stdout\n"
        clean = json.dumps({
            "statistics": {"total": {"clones": 0, "duplicatedLines": 0}},
            "duplicates": [],
        }) + "\nreport saved to /dev/stdout\n"
        git_ls = self._CONFORMANCE_FIXTURE_FILE + "\0"
        return {
            "reported-nonzero-parsed-zero": {
                "stdout": reported,
                "clean_stdout": clean,
                "exit": 0,
                "stdout_by_tool": {"git": git_ls, "jscpd": reported},
                "clean_stdout_by_tool": {"git": git_ls, "jscpd": clean},
            },
        }

    def collect(self, ctx):
        cwd = ctx.get("cwd") or "."
        cwd = os.path.realpath(cwd)
        # Cache previous digest for red_lines() — see __init__ ordering comment. The
        # shell supplies it as camelCase ctx["prevDigest"]; a snake_case read would
        # silently lose the baseline.
        self._prev_digest = ctx.get("prevDigest")

        config = ctx.get("config") or {}
        self._clone_lines_threshold = None
        if isinstance(config, dict) and isinstance(config.get("thresholds"), dict):
            if "cloneLines" in config["thresholds"]:
                self._clone_lines_threshold = config["thresholds"]["cloneLines"]

        repo_config_present = os.path.isfile(os.path.join(cwd, ".jscpd.json"))

        red_threshold = self._clone_lines_threshold
        if red_threshold is None:
            red_threshold = guardian_lens.RED_LINE_THRESHOLDS["cloneLines"]

        # #564: census the GIT-TRACKED, on-disk files and hand jscpd those as operands —
        # never the repo dir. Scanning the dir walked untracked build worktrees
        # (checkouts/) and nested .git internals, pairing every file with its repo twin
        # (173 false-positive large-fresh-clone red lines in the inaugural sweep).
        tracked, census_reason = _tracked_existing_files(ctx, cwd)
        if tracked is None:
            # A git failure must degrade — NEVER become an empty digest that erases the
            # baseline. not-collected (digest None) hits diff()'s cur_digest-is-None guard.
            return {
                "candidates": [],
                "digest": None,
                **gc.not_collected("git ls-files failed: %s" % census_reason),
            }
        if not tracked:
            # Zero tracked files ⇒ short-circuit to not-collected. A `collected` empty
            # digest (pairs: {}) would make diff()'s _diff_pairs_raw mark EVERY prior pair
            # `resolved` (diff() only guards cur_digest is None), a false "all clones
            # fixed." not-collected returns digest None → cur_digest-is-None guard →
            # baseline preserved. And we must NEVER spawn jscpd with no operands: it would
            # default-scan cwd and re-open #564.
            return {
                "candidates": [],
                "digest": None,
                **gc.not_collected(
                    "zero tracked files (git ls-files) — no measurable surface"),
            }

        operands = sorted(tracked)
        # ARG_MAX guard: the operand payload could push argv past the kernel limit on a
        # huge repo. Degrade honestly (no silent cwd fallback, no truncation of the list).
        # invoke absolutizes every operand before execve (prepends realpath(cwd) + a path
        # sep), so measure the ABSOLUTIZED size — the repo-relative byte count undercounts
        # the real argv and could pass a payload that then hits E2BIG. An absolutized
        # operand is at most `realpath(cwd)/` + the relative path, so this is a safe upper
        # bound.
        abs_prefix_bytes = len(os.path.realpath(cwd).encode("utf-8")) + 1
        operand_bytes = sum(
            len(p.encode("utf-8")) + abs_prefix_bytes for p in operands)
        if operand_bytes > MAX_TRACKED_OPERAND_BYTES:
            return {
                "candidates": [],
                "digest": None,
                **gc.not_collected(
                    "tracked-file operand payload is %d bytes across %d files, exceeding "
                    "the %d-byte cap (ARG_MAX headroom) — cannot scan without risking a "
                    "truncated argv" % (operand_bytes, len(operands),
                                        MAX_TRACKED_OPERAND_BYTES)),
            }

        # jscpd's json reporter writes a FILE, but run_tool captures stdout — aim the
        # reporter at /dev/stdout (via a symlink in a throwaway temp dir OUTSIDE the
        # repo) and read the JSON object off stdout. The mkdtemp + symlink setup lives
        # INSIDE the try so any failure there (F) converts to not-collected — collect()
        # must never RAISE; the finally still cleans up whatever tmp dir was created.
        tmp = None
        try:
            tmp = tempfile.mkdtemp(prefix="guardian-jscpd-")
            os.symlink("/dev/stdout", os.path.join(tmp, "jscpd-report.json"))
            # No trailing scan target — the tracked-file census is passed as ``targets``,
            # which invoke absolutizes + validates under-repo and separates with ``--``.
            # --absolute (-a) is REQUIRED with file operands: jscpd 5.0.12 emits an EMPTY
            # firstFile/secondFile `name` for operand scans (only a DIRECTORY scan
            # populates the relative name), so without it every pair reads as a malformed
            # entry and the lens degrades to not-collected. With --absolute the report
            # carries the absolute path, which the existing _repo_rel(cwd, path) normalizes
            # back to a repo-relative path.
            argv = [
                "jscpd", "-o", tmp, "--no-tips", "--absolute",
                "--reporters", "json",
                "--mode", "strict",
                "--min-lines", str(MIN_BLOCK_LINES),
                "--min-tokens", "50",
            ]
            res = gc.run_tool(argv, ctx=ctx, cwd=cwd, ok_exits=(0,), targets=operands)
        except OSError as exc:
            return {
                "candidates": [],
                "digest": None,
                **gc.not_collected("jscpd reporter setup failed: %s" % exc),
            }
        finally:
            if tmp is not None:
                shutil.rmtree(tmp, ignore_errors=True)

        if not res["ok"]:
            return {"candidates": [], "digest": None, **gc.not_collected(res["reason"])}

        report, decode_reason = _decode_report(res.get("stdout") or "")
        if report is None:
            return {"candidates": [], "digest": None, **gc.not_collected(decode_reason)}

        try:
            _validate_report(report)
        except _ReportContractError as exc:
            return {"candidates": [], "digest": None, **gc.not_collected(str(exc))}

        # Honesty gate: jscpd's summary reports clones but the duplicates detail array
        # is empty — we cannot normalize anything and must NOT read as a clean baseline.
        reported_clones = _reported_clone_count(report)
        if reported_clones > 0 and not report.get("duplicates"):
            return {
                "candidates": [],
                "digest": None,
                **gc.not_collected(
                    "jscpd reported duplicates but normalization yielded zero candidates"),
            }

        try:
            pair_jscpd, self_clones_deferred, jscpd_clones_reported = _dedupe_pairs(
                report, cwd)
        except _ReportContractError as exc:
            return {"candidates": [], "digest": None, **gc.not_collected(str(exc))}

        plan = _plan_measurement(pair_jscpd, red_threshold)

        # M1: no prior digest ⇒ prev_pairs is None (not {}), so drift-suppression
        # diagnostics report zero on a first-ever baseline.
        prev_pairs = None
        if isinstance(self._prev_digest, dict):
            raw_prev = self._prev_digest.get("pairs")
            if isinstance(raw_prev, dict):
                prev_pairs = raw_prev

        candidates, digest_pairs, measure_counts = _measure_pairs(
            plan["measure_order"], plan["deferred"], plan["must_measure"],
            cwd, prev_pairs,
        )

        capped, cap_diag = apply_cap(
            candidates, top_n=TOP_N, always_include_clone_lines=red_threshold,
        )
        surface_ids = [c["id"] for c in capped]
        self._surface_ids = set(surface_ids)

        digest = {
            "schemaVersion": 1,
            # Version is not probed under the run_tool/stdout contract (a second
            # --version spawn would confuse the single-invocation conformance seam);
            # jscpd does not carry its version in the json report.
            "toolVersions": {"jscpd": None},
            "pairs": digest_pairs,
            "surfaceIds": surface_ids,
        }
        drift_suppressed = _count_drift_suppressed_by_cap(
            prev_pairs, digest_pairs, self._surface_ids,
        )
        diagnostics = {
            "toolVersions": {"jscpd": None},
            "jscpdClonesReported": jscpd_clones_reported,
            "pairsConsidered": plan["pairs_considered"],
            "pairsMeasured": measure_counts["pairsMeasured"],
            "pairsSkippedBudget": measure_counts["pairsSkippedBudget"],
            "pairsSkippedOversize": measure_counts["pairsSkippedOversize"],
            "pairsCarriedForward": measure_counts["pairsCarriedForward"],
            "pairsUnmeasured": measure_counts["pairsUnmeasured"],
            "budgetExhausted": measure_counts["budgetExhausted"],
            "measurementUnionAdded": plan["measurement_union_added"],
            "driftSuppressedByCap": drift_suppressed,
            "selfClonesDeferred": self_clones_deferred,
            "unreadableFiles": measure_counts["unreadableFiles"],
            "minBlockLines": MIN_BLOCK_LINES,
            "maxPairsMeasured": MAX_PAIRS_MEASURED,
            "maxMustMeasure": MAX_MUST_MEASURE,
            "maxMeasureFileBytes": MAX_MEASURE_FILE_BYTES,
            "measureTimeBudgetSeconds": MEASURE_TIME_BUDGET_SECONDS,
            "topN": TOP_N,
            "candidatesBeforeCap": cap_diag["candidatesBeforeCap"],
            "capApplied": cap_diag["capApplied"],
            "redLineUnionAdded": cap_diag["redLineUnionAdded"],
            "repoConfigPresent": repo_config_present,
            "censusSource": "git ls-files",
            "trackedFilesCensused": len(tracked),
        }
        return {
            "candidates": capped,
            "digest": digest,
            "diagnostics": diagnostics,
            **gc.collected(),
        }

    def diff(self, prev_digest, cur_digest):
        # Stopped-looking / no digest ⇒ no drift claims at all (never `resolved`).
        if cur_digest is None:
            return {"new": [], "worsened": [], "resolved": []}
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
        # M2: diff() returns ONLY {new, worsened, resolved}. The cap-suppression count is
        # a diagnostics-channel concern (collect() reports driftSuppressedByCap) — it is
        # not a diff field.
        if surface is None:
            return {
                "new": raw["new"],
                "worsened": raw["worsened"],
                "resolved": raw["resolved"],
            }
        filtered_new = [pid for pid in raw["new"] if pid in surface]
        filtered_worsened = [pid for pid in raw["worsened"] if pid in surface]
        return {
            "new": filtered_new,
            "worsened": filtered_worsened,
            "resolved": raw["resolved"],
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
                    "kind": _RED_LINE_KIND,
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
# Module-level roster the production loader registers (guardian_lens.PRODUCTION_LENS_MODULES).
LENSES = (LENS,)
