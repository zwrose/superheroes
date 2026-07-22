#!/usr/bin/env python3
# plugins/superheroes/lib/guardian_ledger.py
"""Guardian's durable memory — the dispositions ledger and its second face, the report card.

Stdlib-only. This module owns the ledger's **write** side: the record schema, the identity
matcher, the material-worsening comparator, the advance-only state machine, the report card
(with its small-N benching guard), and the markdown renderer/writer. The **read** side is
`guardian_store.read_ledger` and stays there — this module writes the file that reader parses.

A settled finding is never re-derived. Nothing ever leaves the ledger; states only advance;
won't-fixes carry their why. The file is hand-editable markdown that outlives the plugin.

**Writer preserve rule.** The writer must never rewrite the ledger file as a whole.
The file has exactly **two machine-owned regions**; everything else is the owner's and
must remain byte-identical across updates:

1. the fenced `json guardian-ledger` block
2. the delimited report-card region (`<!-- guardian-report-card:begin … -->` …
   `<!-- guardian-report-card:end -->`)

Unknown top-level JSON keys inside the fence are preserved by merging updates into the
parsed object. Unknown per-record fields are likewise merged by id. Ledger records are
never deleted: ids present on disk but absent from an incoming roster are retained.
When the file does not exist, the full template may be authored once. When the fenced
block cannot be located, or more than one fence is present (ambiguous), the writer does
not write at all. When the report-card region is absent, it is inserted immediately
before the fence (the defined place); content outside the two machine regions stays
untouched. For roster-like fields (`sweeps[]` today), `None` means *preserve whatever is
already on disk*; an explicit list is the roster to write. Passing `None` is never an
erase.

**Compare-and-swap.** Like `guardian_store.write_snapshot_cas`, the never-clobber
writer re-reads fresh bytes immediately before each attempt and refuses to land a
stale splice — so a concurrent owner edit is never deleted. Under the sweep lock,
`_write_locked` retries up to `_WRITE_ATTEMPTS` times; exhaustion returns
`reason: raced-out` and writes nothing.

**Schema extension — `adjudicatedIn`.** Beyond the ratified §5 record shape
(`LEDGER_RECORD_FIELDS`), a record carries `adjudicatedIn`: the **sweep id** it was first
adjudicated in, set once and immutable thereafter. Reason: the report card's "≥3 sweeps"
evidence floor cannot be computed or audited from `date` alone — two sweeps on the same day
collapse into one date, and any later state change would rewrite `date` and thereby rewrite
the history the floor is measured against. A per-record, write-once sweep stamp is the only
field that survives both. Records that lack it (hand-written, legacy) make their lens's sweep
count **unknown**, which grants no benching authority — the fail-closed direction.

**`benched` is not a mute button.** A benched lens stops surfacing *ordinary drift candidates*
only. Absolute red lines still surface — they already bypass the baseline quiet rule in
`guardian_sweep.collect` — and tracked/filed status lines are unaffected. Enforcement lives in
the sweep, not here; this module only computes and states the flag. `benched` may never be read
as "suppress everything from this lens."

**Validation is stricter than the comparator, deliberately.** `validate_record` requires
`metricAtDisposition` to be an object (the §5 shape) so nothing this module writes can be
ambiguous; `materially_worsened` additionally tolerates a scalar, because a hand-written
ledger predating the object shape must still be able to re-raise rather than fail silent.
"""
import argparse
import copy
import datetime
import json
import math
import os
import re
import secrets
import sys
import tempfile

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import file_lock       # noqa: E402
import guardian_lens   # noqa: E402
import guardian_store  # noqa: E402
import store_core      # noqa: E402

# The ratified §5 record shape. `adjudicatedIn` is the documented extension above.
LEDGER_RECORD_FIELDS = (
    "id", "disposition", "date", "issue", "metricAtDisposition", "reason", "reraiseWhen",
)
ADJUDICATED_IN = "adjudicatedIn"

# The ledger's sweep roster — append-only.
SWEEP_FIELDS = ("sweepId", "sweptSha", "date")

# Report-card outcome mix, §5: "died-in-triage and owner-rated-useless count against;
# filed, fixed, and accepted count for (a recorded trade on a real finding is a useful
# finding)". Reading of that ratified prose, stated explicitly because it is a reading:
# `reopened` stays in the filed family (it was a real finding that came back), and
# `declined` is the owner-rated-useless bucket. `candidate`/`surfaced` are not yet
# adjudicated and count neither way.
OUTCOMES_FOR = ("filed", "verified-fixed", "accepted", "reopened")
OUTCOMES_AGAINST = ("triaged-out", "declined")
WONT_FIX_STATES = ("accepted", "declined")

REPORT_CARD_DEFAULTS = {"actionabilityBar": 0.90, "minAdjudicated": 10, "minSweeps": 3}

# Advance-only state machine (§5): candidate → surfaced → triaged-out|filed|accepted|declined;
# filed → verified-fixed|reopened; reopened → filed|verified-fixed|accepted|declined.
# Every state in guardian_lens.FINDING_STATES has an entry; an empty tuple is terminal.
ALLOWED_TRANSITIONS = {
    "candidate": ("surfaced",),
    "surfaced": ("triaged-out", "filed", "accepted", "declined"),
    "triaged-out": (),
    "filed": ("verified-fixed", "reopened"),
    "accepted": (),
    "declined": (),
    "verified-fixed": (),
    "reopened": ("filed", "verified-fixed", "accepted", "declined"),
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TRAILING_LINES_RE = re.compile(r":\d+(?:-\d+)?$")
_WS_RE = re.compile(r"\s+")
_LOCATION_JOIN = "<->"
_CREATED_RE = re.compile(r"created=(\S+)")
REPORT_CARD_BEGIN = "<!-- guardian-report-card:begin"
REPORT_CARD_END = "<!-- guardian-report-card:end -->"
_REPORT_CARD_BEGIN_RE = re.compile(
    r"<!--\s*guardian-report-card:begin(?:\s+updated=\S+)?\s*-->")
_REPORT_CARD_END_RE = re.compile(
    r"<!--\s*guardian-report-card:end\s*-->")
_REPORT_CARD_REGION = re.compile(
    r"<!--\s*guardian-report-card:begin(?:\s+updated=\S+)?\s*-->"
    r".*?"
    r"<!--\s*guardian-report-card:end\s*-->",
    re.DOTALL)
_WRITE_ATTEMPTS = 5


def _today():
    return datetime.date.today().strftime("%Y-%m-%d")


# --------------------------------------------------------------------------- schema


def _is_str_or_none(val):
    return val is None or isinstance(val, str)


def validate_record(rec):
    """Fail-closed record check → (ok, reasons).

    An `id` must be a non-empty str: a list/dict id is unhashable and crashes the reader
    when it builds `byId`, so it must never reach the file."""
    reasons = []
    if not isinstance(rec, dict):
        return (False, ["record must be an object"])

    rid = rec.get("id")
    if not isinstance(rid, str) or not rid.strip():
        reasons.append("id must be a non-empty str (got %r)" % (rid,))

    disposition = rec.get("disposition")
    if disposition not in guardian_lens.FINDING_STATES:
        reasons.append("disposition must be one of %s (got %r)"
                       % (", ".join(guardian_lens.FINDING_STATES), disposition))

    date = rec.get("date")
    if date is not None:
        if not isinstance(date, str) or not _DATE_RE.match(date):
            reasons.append("date must be YYYY-MM-DD (got %r)" % (date,))
        else:
            try:
                datetime.datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                reasons.append("date is not a real calendar date (got %r)" % (date,))

    if not _is_str_or_none(rec.get("issue")):
        reasons.append("issue must be a str or null")
    metric_at = rec.get("metricAtDisposition")
    if metric_at is not None:
        if not isinstance(metric_at, dict):
            reasons.append("metricAtDisposition must be an object of metric → number, or null")
        else:
            for key, val in metric_at.items():
                if not isinstance(key, str) or not key.strip():
                    reasons.append(
                        "metricAtDisposition keys must be non-empty strings (got %r)" % (key,))
                    continue
                if isinstance(val, bool) or not isinstance(val, (int, float)):
                    reasons.append(
                        "metricAtDisposition[%r] must be a finite number (got %r)"
                        % (key, val))
                elif not math.isfinite(float(val)):
                    reasons.append(
                        "metricAtDisposition[%r] must be a finite number (got %r)"
                        % (key, val))
    if not _is_str_or_none(rec.get("reason")):
        reasons.append("reason must be a str or null")
    if not _is_str_or_none(rec.get("reraiseWhen")):
        reasons.append("reraiseWhen must be a str or null")
    if not _is_str_or_none(rec.get(ADJUDICATED_IN)):
        reasons.append("%s must be a str or null" % ADJUDICATED_IN)

    if disposition in WONT_FIX_STATES:
        why = rec.get("reason")
        if not isinstance(why, str) or not why.strip():
            reasons.append("a %s record must carry a non-empty reason — won't-fixes carry "
                           "their why" % disposition)

    return (len(reasons) == 0, reasons)


def validate_records(records):
    """Validate a whole ledger body → (ok, reasons). Duplicate ids are rejected."""
    reasons = []
    if not isinstance(records, list):
        return (False, ["records must be a list"])
    seen = {}
    for i, rec in enumerate(records):
        ok, why = validate_record(rec)
        if not ok:
            reasons.extend("record[%d]: %s" % (i, r) for r in why)
        rid = rec.get("id") if isinstance(rec, dict) else None
        if isinstance(rid, str):
            if rid in seen:
                reasons.append("record[%d]: duplicate id %r (first seen at record[%d])"
                               % (i, rid, seen[rid]))
            else:
                seen[rid] = i
    return (len(reasons) == 0, reasons)


def lens_of(finding_id):
    """The lens name — the id's first `:`-segment. '' for a non-str/empty id."""
    if not isinstance(finding_id, str) or not finding_id.strip():
        return ""
    return finding_id.strip().split(":", 1)[0]


# --------------------------------------------------------------------------- matcher


def normalize_id(finding_id):
    """Line-drift-tolerant identity form of `lens:tool:normalized-location`.

    Strips a trailing `:<line>` / `:<start>-<end>` from each location segment, collapses
    whitespace, normalizes separators to `/`, and sorts multi-location segments so
    `a<->b` and `b<->a` are one identity. Non-str/empty ids normalize to ''.

    TRADEOFF (§5 / the FindBugs new-vs-old caveat): dropping the line number can merge two
    genuinely distinct findings in the same file into one identity, and the design accepts
    that — the matcher deliberately errs toward "already known" rather than re-raising a
    settled finding on every line shift. It is safe because a merged match still re-raises
    on material worsening (`materially_worsened`), and because an ambiguous merge across
    *ledger records* fails open (see `match`)."""
    if not isinstance(finding_id, str):
        return ""
    s = _WS_RE.sub(" ", finding_id).strip()
    if not s:
        return ""
    s = s.replace("\\", "/")
    parts = s.split(":", 2)
    if len(parts) >= 3:
        prefix = "%s:%s" % (parts[0].strip(), parts[1].strip())
        location = parts[2]
    else:
        prefix = ""
        location = s
    segments = []
    for seg in location.split(_LOCATION_JOIN):
        seg = seg.strip()
        seg = _TRAILING_LINES_RE.sub("", seg).strip()
        segments.append(seg)
    normalized_location = _LOCATION_JOIN.join(sorted(segments))
    return "%s:%s" % (prefix, normalized_location) if prefix else normalized_location


def match(finding_id, ledger_by_id):
    """Find the ledger record for a candidate id → (record_or_None, note_or_None).

    Normalized collision is checked before exact id. Exactness must never silence an
    ambiguous line-drift group: if more than one ledger record shares the normalized
    identity, the finding SURFACES with a collision note even when one raw id matches
    exactly (see `normalize_id` for the tradeoff).

    COLLISION RULE — ambiguity fails OPEN. If the normalized form matches more than one
    ledger record, the identity is ambiguous: no record is returned (so the finding
    SURFACES) and the note names the colliding ids. Erring toward "already known" must
    never become "silently suppressed a finding we could not identify."

    FAIL-SAFE: a malformed/newer ledger yields an empty `byId` from `read_ledger`; an
    empty or None mapping therefore matches nothing, and nothing is suppressed."""
    if not ledger_by_id:
        return (None, None)

    target = normalize_id(finding_id) if isinstance(finding_id, str) else None
    hits = []
    if target:
        for rid, rec in ledger_by_id.items():
            if not isinstance(rid, str):
                continue
            if normalize_id(rid) == target:
                hits.append((rid, rec))
    if len(hits) > 1:
        return (None, "ambiguous identity %r matches %d ledger records: %s — surfacing "
                      "rather than suppressing"
                      % (target, len(hits), ", ".join(sorted(rid for rid, _ in hits))))
    if isinstance(finding_id, str) and finding_id in ledger_by_id:
        return (ledger_by_id[finding_id], None)
    if len(hits) == 1:
        return (hits[0][1], None)
    return (None, None)


# ------------------------------------------------------------- material worsening


def _as_number(val):
    """Numeric value of a metric, or None when it is not comparable. bool is not a metric."""
    if isinstance(val, bool) or val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val.strip())
        except ValueError:
            return None
    return None


def _candidate_metric(candidate, key):
    """The candidate's current value for a metric key — top level, then a `metrics` sub-dict."""
    if not isinstance(candidate, dict):
        return None
    val = _as_number(candidate.get(key))
    if val is not None:
        return val
    metrics = candidate.get("metrics")
    if isinstance(metrics, dict):
        return _as_number(metrics.get(key))
    return None


def _scoped_keys(metric_at, reraise_when):
    """Metric keys to compare, honoring `reraiseWhen` when it names known keys."""
    keys = [k for k in sorted(metric_at) if _as_number(metric_at[k]) is not None]
    if isinstance(reraise_when, str) and reraise_when.strip():
        named = [k for k in keys if k in reraise_when]
        if named:
            return named
    return keys


def materially_worsened(candidate, record):
    """True when a settled finding has moved past its disposition-time metric.

    Replaces `guardian_sweep._materially_worsened`, which did `float(rec["metricAtDisposition"])`
    against the §5 OBJECT shape ({"cloneLines": 177}) — a TypeError swallowed by a bare except,
    so a worsened trade never re-raised. Movement, not nagging: missing or uncomparable data
    yields False, but a present comparable pair is never silently dropped."""
    if not isinstance(record, dict) or not isinstance(candidate, dict):
        return False
    metric_at = record.get("metricAtDisposition")
    if metric_at is None:
        return False

    if isinstance(metric_at, dict):
        for key in _scoped_keys(metric_at, record.get("reraiseWhen")):
            baseline = _as_number(metric_at[key])
            current = _candidate_metric(candidate, key)
            if baseline is None or current is None:
                continue
            if current > baseline:
                return True
        return False

    # Back-compat: a scalar metricAtDisposition from a hand-written ledger.
    baseline = _as_number(metric_at)
    current = _as_number(candidate.get("metric"))
    if baseline is None or current is None:
        return False
    return current > baseline


def metric_improved(candidate, record):
    """True when every scoped comparable metric moved in the fixed direction (down).

    Shares `_scoped_keys` with `materially_worsened` so closure and re-raise agree on
    which metrics matter. A worsening (or missing) scoped metric never counts as fixed,
    even when an ancillary metric improved. Mixed or incomplete comparisons return False
    so the caller keeps the record filed or advances to reopened — never verified-fixed."""
    if not isinstance(record, dict) or not isinstance(candidate, dict):
        return False
    metric_at = record.get("metricAtDisposition")
    if metric_at is None:
        return False

    if isinstance(metric_at, dict):
        keys = _scoped_keys(metric_at, record.get("reraiseWhen"))
        if not keys:
            return False
        saw_improvement = False
        for key in keys:
            baseline = _as_number(metric_at[key])
            current = _candidate_metric(candidate, key)
            if baseline is None or current is None:
                return False
            if current > baseline:
                return False
            if current < baseline:
                saw_improvement = True
        return saw_improvement

    baseline = _as_number(metric_at)
    current = _as_number(candidate.get("metric"))
    if baseline is None or current is None:
        return False
    return current < baseline


# ----------------------------------------------------------------- report card


def _coerce_actionability_bar(val):
    """Finite numeric bar in (0, 1], or None when the override is unusable."""
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    bar = float(val)
    if not (0.0 < bar <= 1.0):
        return None
    return bar


def _coerce_positive_int(val):
    """Positive non-bool int, or None when the override is unusable."""
    if isinstance(val, bool) or not isinstance(val, int):
        return None
    if val <= 0:
        return None
    return val


def _resolve_thresholds(overrides, *, config_status=None):
    """Merge report-card overrides → (cfg, notes, benching_allowed).

    Hand-edited guardian-config values are coerced. A mistyped override is named in
    `notes` and **revokes benching authority for the sweep** — defaults must never
    become a silent mute button after a config typo. A non-healthy `config_status`
    (unreadable / malformed guardian-config) likewise revokes benching even when
    overrides are absent."""
    cfg = dict(REPORT_CARD_DEFAULTS)
    notes = []
    if config_status == "degraded":
        notes.append(
            "guardian-config is degraded — benching disabled for this sweep "
            "(defaults are not applied as a mute)")
        if not isinstance(overrides, dict):
            return cfg, notes, False
    if not isinstance(overrides, dict):
        return cfg, notes, True
    for key in REPORT_CARD_DEFAULTS:
        if overrides.get(key) is None:
            continue
        raw = overrides[key]
        if key == "actionabilityBar":
            coerced = _coerce_actionability_bar(raw)
        else:
            coerced = _coerce_positive_int(raw)
        if coerced is None:
            notes.append(
                "reportCard.%s=%r invalid — benching disabled for this sweep "
                "(defaults are not applied as a mute)" % (key, raw))
        else:
            cfg[key] = coerced
    return cfg, notes, (len(notes) == 0)


def _percent(actionability):
    return "n/a" if actionability is None else "%.0f%%" % (actionability * 100)


def _ambiguous_normalized_ids(records):
    """Ids that share a normalized identity with a different id — fail-open evidence."""
    groups = {}
    for rec in records or []:
        if not isinstance(rec, dict):
            continue
        rid = rec.get("id")
        if not isinstance(rid, str) or not rid.strip():
            continue
        key = normalize_id(rid)
        if not key:
            continue
        groups.setdefault(key, set()).add(rid)
    ambiguous = set()
    for ids in groups.values():
        if len(ids) > 1:
            ambiguous.update(ids)
    return ambiguous


def _duplicate_exact_ids(records):
    """Exact ids that appear more than once in the raw record list."""
    seen = set()
    dups = set()
    for rec in records or []:
        if not isinstance(rec, dict):
            continue
        rid = rec.get("id")
        if not isinstance(rid, str):
            continue
        if rid in seen:
            dups.add(rid)
        else:
            seen.add(rid)
    return dups


def _report_card(records, overrides=None, *, notes_out=None, config_status=None):
    cfg, notes, benching_allowed = _resolve_thresholds(
        overrides, config_status=config_status)
    if notes_out is not None:
        notes_out.extend(notes)
    bar = cfg["actionabilityBar"]
    min_adjudicated = cfg["minAdjudicated"]
    min_sweeps = cfg["minSweeps"]

    ambiguous_ids = _ambiguous_normalized_ids(records)
    duplicate_ids = _duplicate_exact_ids(records)
    excluded_ids = ambiguous_ids | duplicate_ids
    if ambiguous_ids:
        notes_msg = (
            "normalized-identity collision excludes %d record(s) from report-card "
            "evidence (matcher fail-open; no benching from ambiguous groups)"
            % len(ambiguous_ids))
        if notes_out is not None:
            notes_out.append(notes_msg)
    if duplicate_ids:
        notes_msg = (
            "duplicate exact ids exclude %d id(s) from report-card evidence "
            "(no benching authority from ambiguous ledger identity)"
            % len(duplicate_ids))
        if notes_out is not None:
            notes_out.append(notes_msg)

    by_lens = {}
    for rec in records or []:
        if not isinstance(rec, dict) or not isinstance(rec.get("id"), str):
            continue
        rid = rec["id"]
        if rid in excluded_ids:
            continue
        lens = lens_of(rid)
        entry = by_lens.setdefault(
            lens, {"for": 0, "against": 0, "sweepIds": set(), "unstamped": 0})
        disposition = rec.get("disposition")
        if disposition in OUTCOMES_FOR:
            entry["for"] += 1
        elif disposition in OUTCOMES_AGAINST:
            entry["against"] += 1
        else:
            continue  # candidate/surfaced/unknown — not adjudicated, no sweep claim
        stamp = rec.get(ADJUDICATED_IN)
        if isinstance(stamp, str) and stamp.strip():
            entry["sweepIds"].add(stamp.strip())
        else:
            entry["unstamped"] += 1

    card = {}
    for lens in sorted(by_lens):
        entry = by_lens[lens]
        adjudicated = entry["for"] + entry["against"]
        actionability = (entry["for"] / adjudicated) if adjudicated else None
        # Fail-closed sweep counting: one adjudicated record without a sweep stamp makes
        # the whole lens's history unverifiable, so it gets NO benching authority.
        sweeps = None if entry["unstamped"] else len(entry["sweepIds"])

        # Each floor is an independent precondition, ANDed. Below EITHER floor there is no
        # benching authority at all, whatever the actionability rate — computing the three
        # booleans separately keeps that from being reordered into a bug.
        enough_adjudicated = adjudicated >= min_adjudicated
        enough_sweeps = sweeps is not None and sweeps >= min_sweeps
        below_bar = actionability is not None and actionability < bar
        benched = (
            benching_allowed and enough_adjudicated and enough_sweeps and below_bar)

        reason = _bench_reason(
            lens, adjudicated, actionability, sweeps, benched,
            enough_adjudicated, enough_sweeps, cfg)
        if not benching_allowed:
            reason = (
                "%s has no benching authority this sweep: reportCard tuning is "
                "invalid — fix the guardian-config overrides before a lens can bench."
                % lens)
            if config_status == "degraded":
                reason = (
                    "%s has no benching authority this sweep: guardian-config is "
                    "degraded — fix the layer before a lens can bench." % lens)

        card[lens] = {
            "adjudicated": adjudicated,
            "for": entry["for"],
            "against": entry["against"],
            "actionability": actionability,
            "sweeps": sweeps,
            "benched": benched,
            "reason": reason,
        }
    return card


def report_card(records, overrides=None, *, notes_out=None, config_status=None):
    """Per-lens outcome mix + the small-N benching guard → {lens: {...}}.

    Benching needs an evidence base first (advisor read, finding ii): no authority until a
    lens has ≥ minAdjudicated adjudicated candidates across ≥ minSweeps distinct sweeps.
    One unlucky sweep is not evidence. See the module docstring: `benched` never silences
    a red line.

    Mistyped `overrides` revoke benching for the sweep (never raise; never mute via
    defaults). A degraded `config_status` (unreadable/malformed guardian-config) likewise
    revokes benching. Ambiguous normalized-identity groups and duplicate exact ids are
    excluded from evidence so the matcher's fail-open collision rule cannot be defeated by
    benching. When `notes_out` is a list, degradation notes are appended to it."""
    return _report_card(records, overrides, notes_out=notes_out,
                        config_status=config_status)


def _bench_reason(lens, adjudicated, actionability, sweeps, benched,
                  enough_adjudicated, enough_sweeps, cfg):
    """One plain-language line, per §5's 'stated in one line'."""
    if benched:
        return ("%s is benched: only %s of its %d adjudicated findings were useful, under "
                "the %s bar across %d sweeps — it collects silently until its validation "
                "rules are tuned."
                % (lens, _percent(actionability), adjudicated,
                   _percent(cfg["actionabilityBar"]), sweeps))
    if adjudicated == 0:
        return ("%s has no adjudicated findings yet — nothing to grade, and no benching "
                "authority." % lens)
    if sweeps is None:
        return ("%s cannot be graded for benching: an adjudicated record has no %s sweep "
                "stamp, so its sweep history is unverifiable — it keeps surfacing."
                % (lens, ADJUDICATED_IN))
    if not enough_adjudicated:
        return ("%s has %d of the %d adjudicated findings the bar needs before it can bench "
                "a lens — still gathering evidence." % (lens, adjudicated,
                                                        cfg["minAdjudicated"]))
    if not enough_sweeps:
        return ("%s has been adjudicated across %d of the %d sweeps the bar needs before it "
                "can bench a lens — still gathering evidence."
                % (lens, sweeps, cfg["minSweeps"]))
    return ("%s is active: %s of its %d adjudicated findings were useful, at or above the "
            "%s bar." % (lens, _percent(actionability), adjudicated,
                         _percent(cfg["actionabilityBar"])))


# --------------------------------------------------------------------- state machine


def can_advance(from_state, to_state):
    """Is `from_state → to_state` a legal advance? → (ok, reason). Nothing ever regresses."""
    if from_state not in guardian_lens.FINDING_STATES:
        return (False, "unknown from-state %r" % (from_state,))
    if to_state not in guardian_lens.FINDING_STATES:
        return (False, "unknown to-state %r" % (to_state,))
    allowed = ALLOWED_TRANSITIONS.get(from_state, ())
    if to_state in allowed:
        return (True, None)
    if not allowed:
        return (False, "%s is a settled disposition — it never regresses (asked for %s)"
                       % (from_state, to_state))
    return (False, "%s → %s is not an allowed advance (allowed: %s)"
                   % (from_state, to_state, ", ".join(allowed)))


_STAMPABLE = ("issue", "reason", "metricAtDisposition", "reraiseWhen", "sweptSha")


def advance(records, finding_id, to_state, **fields):
    """Advance one finding's disposition → (new_records, result).

    Returns a NEW list — the caller's records are never mutated — and no record is ever
    removed. An illegal transition is refused with a reason (never applied, never raised).
    Stamps `date` (today unless supplied) plus issue/reason/metricAtDisposition/reraiseWhen/
    sweptSha when supplied. `adjudicatedIn` (or `sweepId`) is stamped only when the target is
    an adjudicated outcome, and only if the record does not already carry one: it records the
    sweep a finding was FIRST adjudicated in, so it is write-once.

    An id with no record is CREATED at the target state when that state is legal from
    `candidate` — creation is a record's birth, not an advance, so `candidate` itself is also
    a legal creation target. Any more advanced target is refused with a reason.

    The proposed record is validated before the advance is accepted: a state that cannot
    legally be persisted (e.g. `accepted` without a reason) returns ok=False and leaves
    the caller's records unchanged."""
    new_records = copy.deepcopy(list(records or []))
    date = fields.get("date") or _today()

    index = None
    for i, rec in enumerate(new_records):
        if isinstance(rec, dict) and rec.get("id") == finding_id:
            index = i
            break

    if index is None:
        ok, reason = can_advance("candidate", to_state)
        if to_state == "candidate" and to_state in guardian_lens.FINDING_STATES:
            ok, reason = True, None
        if not ok:
            return (new_records, {
                "ok": False,
                "id": finding_id,
                "created": False,
                "reason": "cannot create %r directly at %r: %s"
                          % (finding_id, to_state, reason),
            })
        rec = {"id": finding_id, "disposition": to_state, "date": date}
        _stamp(rec, to_state, fields)
        ok_v, reasons = validate_record(rec)
        if not ok_v:
            return (new_records, {
                "ok": False, "id": finding_id, "from": None, "to": to_state,
                "created": False, "reason": "; ".join(reasons), "errors": reasons,
            })
        new_records.append(rec)
        return (new_records, {
            "ok": True, "id": finding_id, "from": None, "to": to_state, "created": True,
        })

    rec = new_records[index]
    from_state = rec.get("disposition")
    ok, reason = can_advance(from_state, to_state)
    if not ok:
        return (new_records, {
            "ok": False, "id": finding_id, "from": from_state, "to": to_state,
            "created": False, "reason": reason,
        })

    proposed = copy.deepcopy(rec)
    proposed["disposition"] = to_state
    proposed["date"] = date
    _stamp(proposed, to_state, fields)
    ok_v, reasons = validate_record(proposed)
    if not ok_v:
        return (new_records, {
            "ok": False, "id": finding_id, "from": from_state, "to": to_state,
            "created": False, "reason": "; ".join(reasons), "errors": reasons,
        })
    new_records[index] = proposed
    return (new_records, {
        "ok": True, "id": finding_id, "from": from_state, "to": to_state, "created": False,
    })


def _stamp(rec, to_state, fields):
    for key in _STAMPABLE:
        if fields.get(key) is not None:
            rec[key] = fields[key]
    sweep_id = fields.get(ADJUDICATED_IN) or fields.get("sweepId")
    is_adjudication = to_state in OUTCOMES_FOR or to_state in OUTCOMES_AGAINST
    if sweep_id and is_adjudication and not rec.get(ADJUDICATED_IN):
        rec[ADJUDICATED_IN] = sweep_id


# ---------------------------------------------------------------------- sweep roster


def make_sweep(swept_sha, date=None, sweep_id=None):
    """A `sweeps[]` entry. `sweepId` is caller-supplied, else minted unique per run.

    Deliberate identity rule (not an accident — review finding on same-sha same-day
    collisions): the vitals trend treats two sweeps of the same commit as two sweeps, so a
    default id must be unique per collect. The report-card benching floor, however, must
    stay hard to inflate — it counts distinct `adjudicatedIn` stamps on adjudicated
    records, never the roster length — so same-sha same-day repeats that mint new sweep
    ids still cannot manufacture benching evidence without new adjudications. `sweptSha`
    and `date` remain audit fields on the entry; they are not the identity. Pass the
    collect-time `sweepId` back into finalize (and into a retried finalize of the same
    bundle) so a retry dedupes rather than double-counting."""
    day = date or _today()
    if sweep_id:
        sid = sweep_id
    else:
        sid = store_core.short_hash(
            "%s|%s|%s" % (swept_sha, day, secrets.token_hex(8)))[:8]
    return {"sweepId": sid, "sweptSha": swept_sha, "date": day}


def append_sweep(sweeps, sweep):
    """Append-only roster add → a NEW list. A sweepId already present is not duplicated."""
    out = [dict(s) for s in (sweeps or []) if isinstance(s, dict)]
    if not isinstance(sweep, dict) or not sweep.get("sweepId"):
        return out
    if any(s.get("sweepId") == sweep["sweepId"] for s in out):
        return out
    out.append(dict(sweep))
    return out


# --------------------------------------------------------------------------- writer


_PREAMBLE = """\
This is the Guardian's memory: every finding it has settled, and why. A settled finding is
never re-derived — the sweep reads this file and stays quiet about anything already adjudicated
here, re-raising only when a finding has materially worsened past the metric recorded below.

- **Hand-editable.** Plain markdown with one fenced JSON block. Edit it by hand, keep it in
  code review, and it still reads if the plugin ever goes away.
- **States only advance, and nothing is ever deleted.** `candidate` → `surfaced` →
  `triaged-out` / `filed` / `accepted` / `declined`; `filed` → `verified-fixed` / `reopened`.
- **Won't-fixes carry their why.** An `accepted` or `declined` record states its reason, and
  `reraiseWhen` names the metric whose growth should bring it back.
"""

_CARD_HEADER = ("| lens | adjudicated | for | against | actionability | sweeps | status |\n"
                "| --- | --- | --- | --- | --- | --- | --- |")

_RECORD_KEY_ORDER = LEDGER_RECORD_FIELDS + (ADJUDICATED_IN,)


def _ordered(mapping, key_order):
    """Deterministic key order for JSON output; unknown keys are preserved, sorted, last."""
    out = {}
    for key in key_order:
        if key in mapping:
            out[key] = mapping[key]
    for key in sorted(mapping):
        if key not in out:
            out[key] = mapping[key]
    return out


def _status_word(entry):
    if entry["benched"]:
        return "benched"
    if entry["adjudicated"] == 0 or entry["sweeps"] is None:
        return "ungraded"
    return "active"


def render(records, *, report_card=None, sweeps=None, now=None, created=None):
    """The ledger file text: provenance line, preamble, report card region, fenced JSON.

    Deterministic — the same inputs and the same `now` render byte-identical output, so a
    retried write is safe. `report_card` defaults to the card computed from `records`;
    `created` preserves the file's original creation date across rewrites."""
    day = now or _today()
    card = report_card if report_card is not None else _report_card(records)
    block = {
        "schemaVersion": guardian_store.LEDGER_SCHEMA_VERSION,
        "records": [_ordered(r, _RECORD_KEY_ORDER)
                    for r in (records or []) if isinstance(r, dict)],
        "sweeps": [_ordered(s, SWEEP_FIELDS)
                   for s in (sweeps or []) if isinstance(s, dict)],
    }

    lines = [
        "<!-- %s: schemaVersion=%d status=confirmed created=%s updated=%s -->"
        % (guardian_store.LEDGER_FENCE, guardian_store.LEDGER_SCHEMA_VERSION,
           created or day, day),
        "",
        "# Guardian dispositions ledger",
        "",
    ]
    lines.extend(_PREAMBLE.rstrip("\n").splitlines())
    lines.extend(["", _render_report_card_region(card, now=day), ""])

    lines.append("```json %s" % guardian_store.LEDGER_FENCE)
    lines.extend(json.dumps(block, indent=2).splitlines())
    lines.append("```")
    return "\n".join(lines) + "\n"


def _render_report_card_region(card, *, now=None):
    """Machine-owned report-card region body (including begin/end markers)."""
    day = now or _today()
    lines = [
        "%s updated=%s -->" % (REPORT_CARD_BEGIN, day),
        "",
        "## Report card",
        "",
    ]
    if card:
        lines.extend(_CARD_HEADER.splitlines())
        for lens in sorted(card):
            entry = card[lens]
            lines.append("| %s | %d | %d | %d | %s | %s | %s |" % (
                lens, entry["adjudicated"], entry["for"], entry["against"],
                _percent(entry["actionability"]),
                "unknown" if entry["sweeps"] is None else entry["sweeps"],
                _status_word(entry)))
        lines.append("")
        for lens in sorted(card):
            if card[lens]["benched"]:
                lines.append("- %s" % card[lens]["reason"])
        if any(card[lens]["benched"] for lens in card):
            lines.append("")
    else:
        lines.extend(["_No findings adjudicated yet._", ""])
    lines.append(REPORT_CARD_END)
    return "\n".join(lines)


def _read_created(path):
    """The `created=` date already on disk, so a rewrite does not reset it."""
    try:
        with open(path, "rb") as fh:
            first = fh.readline().decode("utf-8", errors="replace")
    except OSError:
        return None
    if guardian_store.LEDGER_FENCE not in first:
        return None
    m = _CREATED_RE.search(first)
    return m.group(1) if m else None


def _read_sweeps_result(path):
    """Tri-state roster read → (status, sweeps).

    status is one of:
      - ``ok`` — authoritative list (may be empty)
      - ``absent`` — file missing, or block/roster genuinely absent/empty-shaped
      - ``read-failed`` — OSError / UnicodeDecodeError (indistinguishable from empty
        only if collapsed; callers that must not erase history must fail closed)

    Malformed fence/block without I/O failure is treated as ``absent`` (empty list) —
    same as the historical `_read_sweeps` contract for non-I/O cases — so callers that
    only need a best-effort roster keep working. The commit path uses ``read-failed``
    to refuse a write rather than land closures while unable to append this sweep.
    """
    try:
        with open(path, "rb") as fh:
            text = fh.read().decode("utf-8")
    except FileNotFoundError:
        return "absent", []
    except (OSError, UnicodeDecodeError):
        return "read-failed", []
    block, err = guardian_store._parse_ledger_block(text)
    if err or not isinstance(block, dict):
        return "absent", []
    raw = block.get("sweeps")
    if not isinstance(raw, list):
        return "absent", []
    return "ok", [dict(s) for s in raw if isinstance(s, dict)]


def _read_sweeps(path):
    """The `sweeps[]` roster already on disk, so a rewrite with sweeps=None preserves it.

    `guardian_store.read_ledger` does not yet return the roster; this mirrors `_read_created`
    and reads the fenced JSON block directly. Absent/malformed/read-failed → empty list
    (legacy contract — prefer `_read_sweeps_result` when erasure must be avoided)."""
    _status, sweeps = _read_sweeps_result(path)
    return sweeps


def _merge_record_preserving_unknown(old, new):
    """Merge `new` over `old`, keeping unknown keys the renderer does not model.

    `adjudicatedIn` is write-once: a non-empty stamp already on disk is never replaced
    by a different or empty value (the benching floor depends on the first adjudication)."""
    if not isinstance(old, dict):
        return _ordered(new, _RECORD_KEY_ORDER) if isinstance(new, dict) else new
    if not isinstance(new, dict):
        return old
    merged = dict(old)
    merged.update(new)
    old_stamp = old.get(ADJUDICATED_IN)
    if isinstance(old_stamp, str) and old_stamp.strip():
        merged[ADJUDICATED_IN] = old_stamp
    return _ordered(merged, _RECORD_KEY_ORDER)


def _merge_records_preserving_unknown(existing_records, new_records):
    """Merge by id; never drop a disk-only id (ledger records are never deleted)."""
    by_old = {}
    if isinstance(existing_records, list):
        for rec in existing_records:
            if isinstance(rec, dict) and isinstance(rec.get("id"), str):
                by_old[rec["id"]] = rec
    out = []
    seen = set()
    for rec in new_records or []:
        if not isinstance(rec, dict):
            continue
        rid = rec.get("id")
        old = by_old.get(rid) if isinstance(rid, str) else None
        out.append(_merge_record_preserving_unknown(old, rec))
        if isinstance(rid, str):
            seen.add(rid)
    # Roster lacking a disk id is stale input, not an instruction to remove it.
    if isinstance(existing_records, list):
        for rec in existing_records:
            if not isinstance(rec, dict):
                continue
            rid = rec.get("id")
            if isinstance(rid, str) and rid not in seen:
                out.append(dict(rec))
                seen.add(rid)
    return out


def _merge_sweeps_preserving(existing_sweeps, new_sweeps):
    """Append-only roster merge by sweepId; never drop a disk-only entry.

    Mirrors `_merge_records_preserving_unknown`: keep every on-disk sweep id, add new
    ones, dedup by `sweepId`. First-write wins for a repeated id."""
    out = []
    seen = set()
    if isinstance(existing_sweeps, list):
        for sweep in existing_sweeps:
            if not isinstance(sweep, dict):
                continue
            sid = sweep.get("sweepId")
            if isinstance(sid, str) and sid and sid not in seen:
                out.append(_ordered(dict(sweep), SWEEP_FIELDS))
                seen.add(sid)
    for sweep in new_sweeps or []:
        if not isinstance(sweep, dict):
            continue
        sid = sweep.get("sweepId")
        if not isinstance(sid, str) or not sid or sid in seen:
            continue
        out.append(_ordered(dict(sweep), SWEEP_FIELDS))
        seen.add(sid)
    return out


def _report_card_markers_status(text):
    """Classify report-card marker balance → (status, match_or_none).

    status:
      - ``absent`` — no begin and no end markers
      - ``ok`` — exactly one balanced begin…end region
      - ``ambiguous`` — unbalanced, duplicated, or end-before-begin (fail closed)
    """
    begins = list(_REPORT_CARD_BEGIN_RE.finditer(text))
    ends = list(_REPORT_CARD_END_RE.finditer(text))
    if not begins and not ends:
        return "absent", None
    if len(begins) != 1 or len(ends) != 1:
        return "ambiguous", None
    if ends[0].start() < begins[0].start():
        return "ambiguous", None
    cards = list(_REPORT_CARD_REGION.finditer(text))
    if len(cards) != 1:
        return "ambiguous", None
    # The sole balanced pair must be exactly the matched region (no stray span).
    if cards[0].start() != begins[0].start() or cards[0].end() != ends[0].end():
        return "ambiguous", None
    return "ok", cards[0]


def _splice_machine_regions(text, block_obj, card_region):
    """Replace the two machine-owned regions; preserve all other bytes.

    Returns (new_text, None) on success, or (None, reason) when the fence is missing,
    ambiguous, or report-card markers are ambiguous (including unbalanced begin/end).
    When the report-card region is absent, it is inserted immediately before the sole
    fence."""
    fences = guardian_store.find_ledger_fences(text)
    if not fences:
        return None, "no-fence"
    if len(fences) > 1:
        return None, "ambiguous"
    card_status, card = _report_card_markers_status(text)
    if card_status == "ambiguous":
        return None, "ambiguous-report-card"

    fence = fences[0]
    body = json.dumps(block_obj, indent=2)
    fence_repl = "```json %s\n%s\n```" % (guardian_store.LEDGER_FENCE, body)

    if card_status == "ok":
        if card.end() <= fence.start():
            new_text = (
                text[:card.start()] + card_region + text[card.end():fence.start()]
                + fence_repl + text[fence.end():]
            )
        elif fence.end() <= card.start():
            new_text = (
                text[:fence.start()] + fence_repl + text[fence.end():card.start()]
                + card_region + text[card.end():]
            )
        else:
            return None, "overlapping-regions"
        return new_text, None

    # No marked report-card region: insert immediately before the fence.
    new_text = (
        text[:fence.start()] + card_region + "\n\n" + fence_repl + text[fence.end():]
    )
    return new_text, None


def _existing_report_card_updated(text):
    """The `updated=` date on an existing report-card begin marker, or None."""
    m = _REPORT_CARD_BEGIN_RE.search(text or "")
    if not m:
        return None
    marker = m.group(0)
    um = re.search(r"updated=(\S+)", marker)
    return um.group(1) if um else None


def _card_body_sans_updated(card_region):
    """Report-card region with the begin-marker date normalized away (for idempotence)."""
    if not card_region:
        return card_region
    return _REPORT_CARD_BEGIN_RE.sub(
        "<!-- guardian-report-card:begin updated=DATE -->", card_region, count=1)


def _prepare_ledger_write(path, records, *, report_card=None, sweeps=None, now=None):
    """Build a ledger write without mutating disk.

    Returns a dict:
      - ``{"kind": "fail", "result": {...}}`` — fail-closed skip / invalid
      - ``{"kind": "author", "bytes": b...}`` — file absent; full template ready
      - ``{"kind": "splice", "spliced": str, "on_disk_id": ..., "existing_raw": b...}``
        — ready to CAS-write; ``existing_raw`` is the exact bytes the splice was built from

    The persisted report card is always computed from the FINAL merged record set
    (post disk-only-merge). A caller-supplied `report_card` is ignored for the written
    card so a collect-time snapshot cannot describe a ledger that differs after merge.
    `report_card` remains accepted for API compatibility.
    """
    del report_card  # persisted card always derived from merged records (Fix 4)
    ok, reasons = validate_records(records if records is not None else [])
    if not ok:
        return {
            "kind": "fail",
            "result": {
                "ok": False, "reason": "invalid-records", "errors": reasons, "path": path,
            },
        }

    day = now or _today()

    if not os.path.isfile(path):
        card = _report_card(records if records is not None else [])
        text = render(records, report_card=card, sweeps=sweeps or [], now=day,
                      created=_read_created(path) if os.path.lexists(path) else None)
        return {"kind": "author", "bytes": text.encode("utf-8")}

    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        return {
            "kind": "fail",
            "result": {
                "ok": False,
                "skipped": "ledger-unreadable",
                "reason": "ledger write skipped: unreadable (%s)" % type(exc).__name__,
                "path": path,
            },
        }
    try:
        existing_text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {
            "kind": "fail",
            "result": {
                "ok": False,
                "skipped": "ledger-unreadable",
                "reason": "ledger write skipped: not valid UTF-8",
                "path": path,
            },
        }

    on_disk_id = guardian_store.ledger_fence_identity(existing_text)

    fences = guardian_store.find_ledger_fences(existing_text)
    if len(fences) > 1:
        return {
            "kind": "fail",
            "result": {
                "ok": False,
                "skipped": "ledger-ambiguous",
                "reason": "ledger write skipped: multiple guardian-ledger fences "
                          "(ambiguous; on-disk bytes left untouched)",
                "path": path,
            },
        }

    existing_block, err = guardian_store._parse_ledger_block(existing_text)
    if err or not isinstance(existing_block, dict):
        skipped = "ledger-ambiguous" if err == "ambiguous" else "ledger-no-fence"
        return {
            "kind": "fail",
            "result": {
                "ok": False,
                "skipped": skipped,
                "reason": "ledger write skipped: fenced guardian-ledger block not found "
                          "or ambiguous (on-disk bytes left untouched)",
                "path": path,
            },
        }

    # WO-1d Fix B / WO-1e Fix 1: re-validate the FRESH on-disk block fail-closed.
    # An owner edit between the earlier opaque-ledger guard and this splice read
    # must not be merged and written. Mirror `_ledger_fully_readable`: schemaVersion
    # must be exactly LEDGER_SCHEMA_VERSION (a newer ledger is never overwritten);
    # records must be a list (never coerce null/missing) and validate (incl. no
    # duplicate ids); every sweeps[] entry must be a dict with a non-empty string
    # sweepId.
    ver = existing_block.get("schemaVersion")
    if (isinstance(ver, int) and not isinstance(ver, bool)
            and ver > guardian_store.LEDGER_SCHEMA_VERSION):
        return {
            "kind": "fail",
            "result": {
                "ok": False,
                "skipped": "ledger-newer",
                "reason": "ledger write skipped: fresh on-disk schemaVersion newer "
                          "(on-disk bytes left untouched)",
                "path": path,
            },
        }
    if not (isinstance(ver, int) and not isinstance(ver, bool)
            and ver == guardian_store.LEDGER_SCHEMA_VERSION):
        return {
            "kind": "fail",
            "result": {
                "ok": False,
                "skipped": "ledger-malformed",
                "reason": "ledger write skipped: fresh on-disk schemaVersion invalid "
                          "(on-disk bytes left untouched)",
                "path": path,
            },
        }
    fresh_records = existing_block.get("records")
    if not isinstance(fresh_records, list):
        return {
            "kind": "fail",
            "result": {
                "ok": False,
                "skipped": "ledger-malformed",
                "reason": "ledger write skipped: fresh on-disk records invalid "
                          "(on-disk bytes left untouched)",
                "path": path,
            },
        }
    ok_fresh, _fresh_reasons = validate_records(fresh_records)
    if not ok_fresh:
        return {
            "kind": "fail",
            "result": {
                "ok": False,
                "skipped": "ledger-malformed",
                "reason": "ledger write skipped: fresh on-disk records invalid "
                          "(on-disk bytes left untouched)",
                "path": path,
            },
        }
    if "sweeps" in existing_block:
        fresh_sweeps = existing_block.get("sweeps")
        if not isinstance(fresh_sweeps, list):
            return {
                "kind": "fail",
                "result": {
                    "ok": False,
                    "skipped": "ledger-malformed",
                    "reason": "ledger write skipped: fresh on-disk sweeps malformed "
                              "(on-disk bytes left untouched)",
                    "path": path,
                },
            }
        for entry in fresh_sweeps:
            sid = entry.get("sweepId") if isinstance(entry, dict) else None
            if not isinstance(entry, dict) or not isinstance(sid, str) or not sid.strip():
                return {
                    "kind": "fail",
                    "result": {
                        "ok": False,
                        "skipped": "ledger-malformed",
                        "reason": "ledger write skipped: fresh on-disk roster entry "
                                  "malformed (on-disk bytes left untouched)",
                        "path": path,
                    },
                }

    # Merge into the parsed object so unknown top-level keys survive.
    block = dict(existing_block)
    block["schemaVersion"] = guardian_store.LEDGER_SCHEMA_VERSION
    block["records"] = _merge_records_preserving_unknown(
        existing_block.get("records"), records if records is not None else [])
    if sweeps is not None:
        # Append-only by sweepId — never blind-replace (concurrent append survives).
        block["sweeps"] = _merge_sweeps_preserving(
            existing_block.get("sweeps"), sweeps)
    # else: leave existing sweeps (or absence) untouched

    # Persisted card describes the ledger actually written (post merge).
    card = _report_card(block["records"])
    card_day = day
    # Fix 8: same effective ledger + card on a later date must not rewrite updated=.
    # Freeze the marker only when merged records/sweeps are unchanged AND the card
    # body (aside from updated=) matches — a real append/closure still refreshes it.
    existing_card_status, existing_card_m = _report_card_markers_status(existing_text)
    if existing_card_status == "ok" and existing_card_m is not None:
        prior_updated = _existing_report_card_updated(existing_card_m.group(0))
        records_same = (
            json.dumps(block.get("records") or [], sort_keys=True, separators=(",", ":"))
            == json.dumps(existing_block.get("records") or [], sort_keys=True,
                          separators=(",", ":")))
        if sweeps is None:
            sweeps_same = True
        else:
            sweeps_same = (
                json.dumps(block.get("sweeps") or [], sort_keys=True,
                           separators=(",", ":"))
                == json.dumps(existing_block.get("sweeps") or [], sort_keys=True,
                              separators=(",", ":")))
        if prior_updated and records_same and sweeps_same:
            candidate = _render_report_card_region(card, now=prior_updated)
            if _card_body_sans_updated(candidate) == _card_body_sans_updated(
                    existing_card_m.group(0)):
                card_day = prior_updated

    card_region = _render_report_card_region(card, now=card_day)
    spliced, splice_err = _splice_machine_regions(existing_text, block, card_region)
    if spliced is None:
        skipped = {
            "ambiguous": "ledger-ambiguous",
            "ambiguous-report-card": "ledger-ambiguous",
            "overlapping-regions": "ledger-ambiguous",
            "no-fence": "ledger-no-fence",
        }.get(splice_err, "ledger-no-fence")
        return {
            "kind": "fail",
            "result": {
                "ok": False,
                "skipped": skipped,
                "reason": "ledger write skipped: %s (on-disk bytes left untouched)"
                          % (splice_err or "fence not found"),
                "path": path,
            },
        }
    return {
        "kind": "splice",
        "spliced": spliced,
        "on_disk_id": on_disk_id,
        "existing_raw": raw,
    }


def _author_exclusive(path, payload_bytes):
    """Create `path` exclusively via temp + no-clobber link publish.

    Returns True on fresh create, False if `path` already exists. Writes the full
    payload to a private temp in the same directory first (flush+fsync), chmods
    to ``0o644 & ~umask`` so the published mode matches the pre-mkstemp guardian
    artifact story, then publishes with ``os.link(tmp, path)`` which fails if the
    destination exists — so concurrent authors fall through to the splice-retry
    path without clobbering or exposing partial bytes at ``path``. The temp inode
    is always unlinked in ``finally`` (after a successful link only the temp name
    goes away; ``path`` keeps the inode).
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".ledger-author-", dir=directory)
    try:
        try:
            with os.fdopen(fd, "wb") as fh:
                fd = -1  # ownership transferred to the file object
                fh.write(payload_bytes)
                fh.flush()
                os.fsync(fh.fileno())
        finally:
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass
        # mkstemp creates 0600; restore the intended public mode (0644 & ~umask).
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(tmp, 0o644 & ~umask)
        try:
            os.link(tmp, path)
        except FileExistsError:
            return False
        return True
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _write_locked(cwd, records, *, root=None, report_card=None, sweeps=None, now=None):
    """Never-clobber ledger write assuming the caller already holds the sweep lock.

    Mirrors the lock-assuming vitals/sweep writers: `write` acquires the lock then
    calls this; `commit_ledger` holds the lock itself and must call this directly
    (the lock is non-reentrant)."""
    path = guardian_store.ledger_path(cwd, root)
    last = None
    for _attempt in range(1, _WRITE_ATTEMPTS + 1):
        prepared = _prepare_ledger_write(
            path, records, report_card=report_card, sweeps=sweeps, now=now)
        if prepared["kind"] == "fail":
            return prepared["result"]
        if prepared["kind"] == "author":
            # Fix 3: exclusive create — if a concurrent session authored between the
            # absence check and this write, fall through to the splice path (retry).
            if _author_exclusive(path, prepared["bytes"]):
                return {"ok": True, "path": path}
            last = {
                "ok": False,
                "reason": "raced-retry",
                "path": path,
            }
            continue

        on_disk_id = prepared["on_disk_id"]
        existing_raw = prepared["existing_raw"]
        # Final full-byte check immediately before write (prose + fence + card).
        try:
            with open(path, "rb") as fh:
                recheck_raw = fh.read()
        except OSError as exc:
            return {
                "ok": False,
                "skipped": "ledger-unreadable",
                "reason": "ledger write skipped: unreadable at final check (%s)"
                          % type(exc).__name__,
                "path": path,
            }
        if recheck_raw != existing_raw:
            try:
                recheck_text = recheck_raw.decode("utf-8")
                recheck_id = guardian_store.ledger_fence_identity(recheck_text)
            except UnicodeDecodeError:
                recheck_id = None
            last = {
                "ok": False,
                "reason": "raced-retry",
                "onDisk": recheck_id,
                "expected": on_disk_id,
                "path": path,
            }
            continue
        guardian_store.atomic_write_bytes(path, prepared["spliced"].encode("utf-8"))
        return {"ok": True, "path": path}

    return {
        "ok": False,
        "reason": "raced-out",
        "attempts": _WRITE_ATTEMPTS,
        "onDisk": (last or {}).get("onDisk"),
        "expected": (last or {}).get("expected"),
        "path": path,
    }


def write(cwd, records, *, root=None, report_card=None, sweeps=None, now=None):
    """Advisor sole writer for ledger.md — bounded never-clobber re-read/re-splice loop.

    The fenced JSON block and the report-card region are **machine-owned** (the advisor is
    their sole writer); owner hand-edits belong to the surrounding prose, which the
    never-clobber re-splice preserves.

    Under the sweep lock (against a concurrent *sweep*; the owner's editor honors no lock),
    runs up to `_WRITE_ATTEMPTS` (5) attempts. Each attempt re-reads fresh bytes, re-merges
    the caller's records onto that fresh content, re-splices from scratch, and re-checks
    **full file bytes** (not just fence identity) **immediately before** `atomic_write_bytes`.
    Any change — including prose-only edits that leave the fence unchanged — triggers another
    attempt — never a clobber with a stale splice. Exhaustion returns ``reason: raced-out``
    and writes nothing.

    `sweeps=None` preserves the on-disk roster; pass an explicit list to append-merge by
    `sweepId` (disk-only entries are never dropped). On contention for the sweep lock
    returns ``{"ok": False, "reason": "raced"}``. Never runs git."""
    path = guardian_store.ledger_path(cwd, root)
    lock_path = guardian_store.sweep_lock_path(cwd, root)
    try:
        file_lock.acquire(lock_path, ttl=guardian_store.SWEEP_LOCK_TTL)
    except file_lock.LockHeld as exc:
        return {"ok": False, "reason": "raced", "lockHeld": exc.holder, "path": path}
    try:
        return _write_locked(
            cwd, records, root=root, report_card=report_card, sweeps=sweeps, now=now)
    finally:
        file_lock.release(lock_path)


# ------------------------------------------------------------------------------ CLI


def main(argv=None):
    ap = argparse.ArgumentParser(description="guardian dispositions ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)

    rc = sub.add_parser("report-card", help="per-lens outcome mix from the on-disk ledger")
    rc.add_argument("--cwd", default=".")
    rc.add_argument("--root", default=None)

    rd = sub.add_parser("render", help="re-render the on-disk ledger (read-only)")
    rd.add_argument("--cwd", default=".")
    rd.add_argument("--root", default=None)

    args = ap.parse_args(argv)
    try:
        ledger = guardian_store.read_ledger(args.cwd, args.root)
        if args.cmd == "report-card":
            out = report_card(ledger["records"])
        else:
            out = {
                "ledgerStatus": ledger["status"],
                "markdown": render(ledger["records"]),
            }
    except Exception as exc:
        out = {"error": str(exc)}
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
