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


def apply_audit_results(audited, results):
    """Consume per-finding fix-audit rulings; fail-closed on ambiguity, silence, and malformation.

    `audited`  — findings already carrying a unique staged `id` (via verification.stage_ids)
                 plus file/line/title/severity.
    `results`  — audit-result dicts {id, ruling, reason, evidence?, newIssues?}.

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

        # The target names the SELECTED independent auditor vendor (round_driver._audit_targets). A
        # clearing ruling that does not echo it cannot be trusted (it may come from the fixer or a
        # misrouted worker) — fail closed. `base` also carries the recurrence class keys so the
        # audit-stall breaker's alias-tolerant match sees a retitled-but-same-class stall (#507 v0).
        expected_auditor = f.get("auditorVendor")
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

        # Provenance (trust-boundary): a ruling that CLEARS the finding must be echoed by the
        # selected independent auditor. A missing or mismatched executor vendor → not-discharged +
        # disclosed as `unauthenticated`; the validated auditor identity rides the audit entry.
        if expected_auditor and ruling in ("discharged", "discharged-but-new-issue"):
            executor = r.get("auditorVendor")
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
            base["auditor"] = executor

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
