#!/usr/bin/env python3
"""Deterministic consumer of a delta round's fix-audit stage (#507).

Sibling of verification.apply_verdicts: a delta round re-audits each fixed finding and rules it
`discharged` (the fix resolved it), `not-discharged` (it did not), or `discharged-but-new-issue`
(the fix resolved the original finding but introduced a fresh problem). A model makes the
judgments; this fold consumes them DETERMINISTICALLY so accounting stays reproducible.

stdlib only; never raises on bad input; fail-closed — a wrong `discharged` certifies an
unaudited fix (the expensive failure direction: a real defect ships believed fixed), so every
uncertain / malformed / missing ruling collapses to `not-discharged` and is disclosed.
"""

AUDIT_RULINGS = ("discharged", "not-discharged", "discharged-but-new-issue")

# The rulings whose fix counts as discharged for stall/continuation accounting. A
# `discharged-but-new-issue` clears the ORIGINAL finding (a new candidate is emitted separately),
# so it is not a stall on that finding; only `not-discharged` is.
_CLEARS = ("discharged", "discharged-but-new-issue")


def _valid_new_issues(candidates, origin_id):
    """The dict-shaped new-issue candidates from a discharged-but-new-issue claim, each tagged
    with its originating audit id. Non-dict entries are dropped (fail-closed); an empty result
    means the claim carried no usable candidate."""
    out = []
    if not isinstance(candidates, list):
        return out
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        tagged = dict(cand)
        tagged["originAuditId"] = origin_id
        out.append(tagged)
    return out


def _resolve_expected_auditor(fid, finding, expected_auditors):
    """The TRUSTED independent-auditor selection for a target — the DRIVER's record, never the
    result's own echo (#507 R2). Prefer the explicit `expected_auditors` map the driver passes
    (round_driver._audit_targets); fall back to the target's driver-stamped `auditorVendor`. Returns
    (expected_vendor_or_None, enforced): `enforced` is True whenever the driver supplied a provenance
    signal (a map, or an auditorVendor on the target). When enforced but the expected vendor is falsy
    (a target with NO recorded selection), a clearing ruling cannot prove independence → fail closed."""
    if isinstance(expected_auditors, dict):
        v = expected_auditors.get(fid)
        return (v if isinstance(v, str) and v else None), True
    v = finding.get("auditorVendor") if isinstance(finding, dict) else None
    if isinstance(v, str) and v:
        return v, True
    return None, False


def apply_audit_results(audited, results, expected_auditors=None):
    """Consume per-finding fix-audit rulings; fail-closed on ambiguity, silence, and malformation.

    `audited`  — findings already carrying a unique staged `id` (via verification.stage_ids)
                 plus file/line/title/severity.
    `results`  — audit-result dicts {id, ruling, reason, evidence?, newIssues?}.
    `expected_auditors` — {finding_id: auditor_vendor} recorded by the DRIVER
                 (round_driver._audit_targets) naming the SELECTED independent auditor per target. A
                 clearing ruling is authenticated against THIS trusted map, NEVER the result's own
                 echo; a target absent from it (no recorded selection) cannot be authenticated →
                 not-discharged + disclosed. When None, the target's driver-stamped `auditorVendor`
                 is the fallback signal; a target with neither is not provenance-enforced.

    Returns {audits, discharged, notDischarged, newIssues, unaudited, ambiguous, malformed,
    unmatched, unauthenticated}. Each `audits` entry carries the EFFECTIVE (post-fail-closed)
    ruling. The disclosure lists (unaudited/ambiguous/malformed/unauthenticated) are subsets of
    notDischarged that name WHY the finding could not be certified discharged; `unmatched` names
    results that hit no finding. `unauthenticated` names clearing rulings that did not echo the
    target's selected independent auditor vendor (trust-boundary failure).
    """
    # Build the id→result map, detecting duplicate ids. A finding id carried by MORE THAN ONE
    # result is ambiguous — honor none of them so a wrong `discharged` cannot silently win and
    # certify an unaudited fix. `seen_ids` is every id any result carried (used to tell silence
    # from a matched-but-unhonored result).
    by_id = {}
    seen_ids = set()
    ambiguous_ids = set()
    if isinstance(results, list):
        for r in results:
            if isinstance(r, dict) and isinstance(r.get("id"), str):
                rid = r["id"]
                if rid in seen_ids:
                    ambiguous_ids.add(rid)
                    by_id.pop(rid, None)
                    continue
                seen_ids.add(rid)
                by_id[rid] = r

    if not isinstance(audited, list):
        audited = []

    audits = []
    discharged, not_discharged = [], []
    new_issues = []
    unaudited, malformed = [], []
    unauthenticated = []
    matched_ids = set()

    for f in audited:
        if not isinstance(f, dict):
            continue
        fid = f.get("id")
        if not isinstance(fid, str):
            fid = None
        r = by_id.get(fid) if fid is not None else None
        if r is not None and fid is not None:
            matched_ids.add(fid)

        # The DRIVER records the SELECTED independent auditor vendor per target (round_driver.
        # _audit_targets) and passes it here as trusted provenance. A clearing ruling is authenticated
        # against THAT record — never the result's own claimant-controlled echo. `base` also carries
        # the recurrence class keys so the audit-stall breaker's alias-tolerant match sees a
        # retitled-but-same-class stall (#507 v0).
        expected_auditor, provenance_enforced = _resolve_expected_auditor(fid, f, expected_auditors)
        base = {"id": fid, "file": f.get("file"), "title": f.get("title"),
                "classKey": f.get("classKey"), "dimension": f.get("dimension"),
                "taxonomy": f.get("taxonomy")}

        # No matching result (silence) → fail-closed not-discharged, disclosed as unaudited.
        # An ambiguous id is IN seen_ids, so it never counts as silent — it is disclosed via
        # `ambiguous` instead.
        if r is None:
            if fid is not None and fid in ambiguous_ids:
                base.update(ruling="not-discharged",
                            reason="more than one audit result claimed this finding — honoring none")
            else:
                if fid is not None:
                    unaudited.append(fid)
                base.update(ruling="not-discharged",
                            reason="no audit result for this finding — cannot certify the fix discharged")
            audits.append(base)
            if fid is not None:
                not_discharged.append(fid)
            continue

        ruling = r.get("ruling")
        reason = r.get("reason")
        has_reason = isinstance(reason, str) and bool(reason.strip())
        evidence = r.get("evidence")

        # Provenance (trust-boundary): a ruling that CLEARS the finding is authenticated against the
        # DRIVER-recorded selected auditor — NEVER the result's own echo. Two fail-closed rejections
        # (each → not-discharged + disclosed as `unauthenticated`): a target with NO recorded auditor
        # selection cannot prove independence at all; a result echoing anything OTHER than the recorded
        # auditor may be the fixer or a misrouted worker. When authenticated, the recorded auditor is
        # the TRUSTED driver value (not the claimant echo) — a matching echo authenticates nothing the
        # driver's record did not already establish.
        if provenance_enforced and ruling in ("discharged", "discharged-but-new-issue"):
            executor = r.get("auditorVendor")
            if not expected_auditor:
                if fid is not None:
                    unauthenticated.append(fid)
                    not_discharged.append(fid)
                base.update(
                    ruling="not-discharged",
                    reason=("no independent auditor was recorded for this target — cannot prove the "
                            "audit came from an independent auditor; treated as not-discharged"))
                audits.append(base)
                continue
            if not (isinstance(executor, str) and executor == expected_auditor):
                if fid is not None:
                    unauthenticated.append(fid)
                    not_discharged.append(fid)
                base.update(
                    ruling="not-discharged",
                    reason=("audit result did not come from the selected independent auditor "
                            "(expected %r, got %r) — treated as not-discharged"
                            % (expected_auditor, executor)))
                audits.append(base)
                continue
            base["auditor"] = expected_auditor

        if ruling == "discharged":
            if has_reason:
                base.update(ruling="discharged", reason=reason.strip())
                if isinstance(evidence, str) and evidence.strip():
                    base["evidence"] = evidence
                audits.append(base)
                if fid is not None:
                    discharged.append(fid)
                continue
            # reasonless `discharged` is unusable — a bare "fixed" is exactly the unproven claim
            # this fold exists to reject.
            if fid is not None:
                malformed.append(fid)
            base.update(ruling="not-discharged",
                        reason="`discharged` with no reason — treated as not-discharged")
            audits.append(base)
            if fid is not None:
                not_discharged.append(fid)
            continue

        if ruling == "discharged-but-new-issue":
            candidates = _valid_new_issues(r.get("newIssues"), fid)
            if candidates:
                base.update(ruling="discharged-but-new-issue",
                            reason=reason.strip() if has_reason else "fix discharged; new issue emitted")
                if isinstance(evidence, str) and evidence.strip():
                    base["evidence"] = evidence
                audits.append(base)
                new_issues.extend(candidates)
                if fid is not None:
                    discharged.append(fid)
                continue
            # a discharged-but-new-issue with no usable candidate is an unusable claim.
            if fid is not None:
                malformed.append(fid)
            base.update(ruling="not-discharged",
                        reason="`discharged-but-new-issue` with no usable newIssues — treated as not-discharged")
            audits.append(base)
            if fid is not None:
                not_discharged.append(fid)
            continue

        if ruling == "not-discharged":
            base.update(ruling="not-discharged",
                        reason=reason.strip() if has_reason else "not discharged")
            audits.append(base)
            if fid is not None:
                not_discharged.append(fid)
            continue

        # Unknown ruling string (or a non-str) → fail-closed not-discharged + malformed.
        if fid is not None:
            malformed.append(fid)
        base.update(ruling="not-discharged",
                    reason="unrecognized ruling %r — treated as not-discharged" % (ruling,))
        audits.append(base)
        if fid is not None:
            not_discharged.append(fid)

    unmatched = [rid for rid in by_id if rid not in matched_ids]
    return {
        "audits": audits,
        "discharged": discharged,
        "notDischarged": not_discharged,
        "newIssues": new_issues,
        "unaudited": unaudited,
        "ambiguous": sorted(ambiguous_ids),
        "malformed": malformed,
        "unmatched": unmatched,
        "unauthenticated": unauthenticated,
    }
